"""Additive dashboard migration. Run with services stopped and a DB backup."""
import argparse
import sqlite3
from contextlib import closing
from pathlib import Path


def migrate(path: Path) -> None:
    if not path.is_file():
        raise ValueError('Initialize the application database before migrating it')
    with closing(sqlite3.connect(path, timeout=5)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        columns = {row[1] for row in db.execute('PRAGMA table_info(wagons)')}
        if not columns:
            raise ValueError('Missing wagons table')
        if 'revision' not in columns:
            db.execute('ALTER TABLE wagons ADD COLUMN revision INTEGER NOT NULL DEFAULT 0')
        db.execute('CREATE INDEX IF NOT EXISTS ix_bag_events_car_time ON bag_events(wagon_id, counted_at, id)')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    migrate(parser.parse_args().db)
