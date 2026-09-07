# Event Storage Design

## Current implementation

- `src/db/models.py` uses SQLAlchemy and a SQLite file under `storage/db/bag_counter.db`.
- Models: `Shift`, `Wagon`, `BagEvent`; enum: `BagClass`.
- The engine uses `check_same_thread=False`, `StaticPool`, and `pool_pre_ping=True`.
- `init_db()` creates schema metadata directly; Alembic is listed as a dependency but migration flow is not the runtime initialization path.
- `BagCountingPipeline._ensure_shift_wagon()` auto-creates defaults (`operator_name="auto"`, `wagon_number="W001"`) when active records are absent.
