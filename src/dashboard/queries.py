"""Short-lived SQLite transactions for operator reads and number correction."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

CLASSES = {'EMPTY': 'empty', 'CLASS_25KG': '25kg', 'CLASS_50KG': '50kg',
           'empty': 'empty', '25kg': '25kg', '50kg': '50kg'}


def utc_datetime(value):
    dt = datetime.fromisoformat(value) if isinstance(value, str) else value
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def utc(value):
    return utc_datetime(value).isoformat() if value is not None else None


@contextmanager
def connection(path, write=False):
    # mode=rw prevents silently creating an empty production DB on a bad path.
    db = sqlite3.connect(f'{path.as_uri()}?mode=rw', uri=True, timeout=2)
    db.row_factory = sqlite3.Row
    try:
        db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def car_context(db):
    rows = db.execute('SELECT id, wagon_number, revision, shift_id FROM wagons WHERE is_active = 1 LIMIT 2').fetchall()
    if len(rows) != 1:
        return None, 'no_active_car' if not rows else 'multiple_active_cars'
    row = rows[0]
    return {'id': row['id'], 'number': row['wagon_number'], 'revision': row['revision'], 'shift_id': row['shift_id']}, None


def event(row):
    return {'id': row['id'], 'car_id': row['wagon_id'], 'counted_at': utc(row['counted_at']),
            'class': CLASSES.get(row['bag_class'], 'unknown'), 'state': 'Count saved'}


def history(db, car_id, limit=6, before=None):
    where = 'wagon_id = ? AND counted_at IS NOT NULL'
    args = [car_id]
    if before is not None:
        where += ' AND id < ?'
        args.append(before)
    rows = db.execute(f'SELECT * FROM bag_events WHERE {where} ORDER BY id DESC LIMIT ?', args + [limit + 1]).fetchall()
    return {'events': [event(r) for r in rows[:limit]],
            'next_cursor': rows[limit-1]['id'] if len(rows) > limit else None}


def series(db, car_id, start, end):
    start = utc_datetime(start)
    end = utc_datetime(end)
    # Stream the car-scoped index: stored timestamps may be naive UTC or carry
    # offsets, so lexical SQL bounds are unsafe. Python preserves microseconds
    # both at [start, end) boundaries and when flooring a minute bucket.
    rows = db.execute('''SELECT counted_at FROM bag_events
        WHERE wagon_id = ? AND counted_at IS NOT NULL''', (car_id,))
    counts = {}
    for row in rows:
        observed = utc_datetime(row['counted_at'])
        if start <= observed < end:
            minute = observed.replace(second=0, microsecond=0).isoformat()
            counts[minute] = counts.get(minute, 0) + 1
    cursor = start.replace(second=0, microsecond=0)
    buckets = []
    while cursor < end:
        stamp = cursor.isoformat()
        buckets.append({'at': stamp, 'count': counts.get(stamp, 0)})
        cursor += timedelta(minutes=1)
    return {'from': start.isoformat(), 'to': end.isoformat(), 'buckets': buckets}


def snapshot(path):
    now = datetime.now(timezone.utc)
    with connection(path) as db:
        car, context_error = car_context(db)
        totals = {'total': 0, 'by_class': {'empty': 0, '25kg': 0, '50kg': 0}, 'weight_kg': 0}
        recent = {'events': [], 'next_cursor': None}
        graph = {'buckets': []}
        if car:
            rows = db.execute('SELECT bag_class, count(*) n FROM bag_events WHERE wagon_id = ? AND counted_at IS NOT NULL GROUP BY bag_class', (car['id'],)).fetchall()
            for row in rows:
                totals['total'] += row['n']
                cls = CLASSES.get(row['bag_class'])
                if cls:
                    totals['by_class'][cls] += row['n']
            totals['weight_kg'] = totals['by_class']['25kg'] * 25 + totals['by_class']['50kg'] * 50
            recent = history(db, car['id'])
            end = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
            graph = series(db, car['id'], end - timedelta(minutes=30), end)
        return {'car': car, 'context_error': context_error, 'totals': totals, 'recent': recent,
                'series': graph, 'database_at': now.isoformat()}


class CarConflict(Exception):
    def __init__(self, current):
        self.current = current


def correct_car(path, car_id, number, revision):
    with connection(path, write=True) as db:
        car, error = car_context(db)
        if error or car['id'] != car_id or car['revision'] != revision:
            raise CarConflict(car)
        db.execute('UPDATE wagons SET wagon_number = ?, revision = revision + 1 WHERE id = ? AND revision = ?', (number, car_id, revision))
        car['number'], car['revision'] = number, revision + 1
        return car
