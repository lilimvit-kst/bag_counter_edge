import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from src.db.dashboard_migration import migrate
from src.dashboard import queries


@pytest.fixture
def database(tmp_path):
    path = tmp_path / 'counts.db'
    with sqlite3.connect(path) as db:
        db.executescript('''CREATE TABLE wagons(id INTEGER PRIMARY KEY, wagon_number TEXT, shift_id INTEGER, is_active BOOLEAN);
        CREATE TABLE bag_events(id INTEGER PRIMARY KEY, wagon_id INTEGER, bag_class TEXT, counted_at TEXT, clip_path TEXT);
        INSERT INTO wagons VALUES(1, 'W001', 4, 1), (2, 'OLD', 4, 0);
        INSERT INTO bag_events VALUES(1,1,'CLASS_25KG','2026-09-07 10:00:00','evidence.mp4'),
        (2,1,'CLASS_50KG','2026-09-07 10:02:00',NULL),
        (3,2,'CLASS_50KG','2026-09-07 10:01:00',NULL),
        (4,1,'EMPTY',NULL,NULL);''')
    migrate(path)
    return path


def test_migration_idempotent_and_preserves_events(database):
    with sqlite3.connect(database) as db:
        before = db.execute('SELECT * FROM bag_events').fetchall()
    migrate(database)
    with sqlite3.connect(database) as db:
        assert before == db.execute('SELECT * FROM bag_events').fetchall()
        assert db.execute('SELECT revision FROM wagons').fetchall() == [(0,), (0,)]
        assert 'ix_bag_events_car_time' in {r[1] for r in db.execute('PRAGMA index_list(bag_events)')}


def test_scoped_snapshot(database):
    result = queries.snapshot(database)
    assert result['totals'] == {'total': 2, 'by_class': {'25kg':1, '50kg':1, 'empty':0}, 'weight_kg':75}
    assert [e['id'] for e in result['recent']['events']] == [2,1]
    assert result['recent']['events'][0]['counted_at'].endswith('+00:00')


def test_zero_fill_bounds_and_pagination(database):
    with queries.connection(database) as db:
        result = queries.series(db, 1, datetime(2026,9,7,10,tzinfo=timezone.utc), datetime(2026,9,7,10,2,tzinfo=timezone.utc))
        assert [b['count'] for b in result['buckets']] == [1,0]
        page = queries.history(db, 1, 1)
        assert page['next_cursor'] == 2
        assert queries.history(db, 1, 1, page['next_cursor'])['events'][0]['id'] == 1


def test_edit_concurrency_and_ownership(database):
    def edit(number):
        try:
            return queries.correct_car(database, 1, number, 0)
        except queries.CarConflict:
            return 'conflict'
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(edit, ['00123456', '00999999']))
    assert results.count('conflict') == 1
    assert queries.snapshot(database)['totals']['total'] == 2
    with queries.connection(database) as db:
        assert [r[0] for r in db.execute('SELECT wagon_id FROM bag_events ORDER BY id')] == [1,1,2,1]


def test_no_unique_car(database):
    with sqlite3.connect(database) as db:
        db.execute('UPDATE wagons SET is_active=1')
    assert queries.snapshot(database)['context_error'] == 'multiple_active_cars'
    with pytest.raises(queries.CarConflict):
        queries.correct_car(database, 1, 'new', 0)
    with sqlite3.connect(database) as db:
        db.execute('UPDATE wagons SET is_active=0')
    assert queries.snapshot(database)['context_error'] == 'no_active_car'


@pytest.mark.parametrize('offset', [None, timezone.utc, timezone(timedelta(hours=5))])
@pytest.mark.parametrize('boundary', ['start', 'end'])
@pytest.mark.parametrize('delta', [-1, 0, 1])
def test_series_exact_interval_boundaries(database, offset, boundary, delta):
    start = datetime(2026, 9, 8, 10, tzinfo=timezone.utc)
    end = start + timedelta(minutes=1)
    instant = (start if boundary == 'start' else end) + timedelta(microseconds=delta)
    stored = instant.astimezone(offset).isoformat() if offset else instant.replace(tzinfo=None).isoformat(' ')
    with queries.connection(database, write=True) as db:
        db.execute('INSERT INTO bag_events VALUES(5,1,?,?,NULL)', ('CLASS_25KG', stored))
        db.execute('INSERT INTO bag_events VALUES(6,2,?,?,NULL)', ('CLASS_25KG', stored))
        result = queries.series(db, 1, start, end)
    assert result['buckets'] == [{'at': start.isoformat(), 'count': int(start <= instant < end)}]


def test_series_exact_bucket_floor_and_fractional_offset_bounds(database):
    start = datetime.fromisoformat('2026-09-08T15:00:59.999999+05:00')
    end = datetime.fromisoformat('2026-09-08T15:01:00.000001+05:00')
    with queries.connection(database, write=True) as db:
        for identity, stamp in enumerate(['2026-09-08 10:00:59.999998',
                '2026-09-08 10:00:59.999999', '2026-09-08T15:01:00+05:00',
                '2026-09-08T10:01:00.000001Z'], 5):
            db.execute('INSERT INTO bag_events VALUES(?,1,?,?,NULL)', (identity, 'CLASS_25KG', stamp))
        result = queries.series(db, 1, start, end)
    assert result['buckets'] == [{'at':'2026-09-08T10:00:00+00:00', 'count':1},
                                 {'at':'2026-09-08T10:01:00+00:00', 'count':1}]
