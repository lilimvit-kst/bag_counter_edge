"""
FastAPI service for local stats and health.
"""
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

from src.db.models import SessionLocal, Wagon, BagEvent

app = FastAPI(title="Bag Counter Edge API")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/v1/wagons/active")
def active_wagon(db: Session = Depends(get_db)):
    wagon = db.query(Wagon).filter_by(is_active=True).first()
    if not wagon:
        return {"detail": "No active wagon"}
    return {
        "id": wagon.id,
        "number": wagon.wagon_number,
        "started_at": wagon.started_at,
    }


@app.get("/api/v1/stats/today")
def today_stats(db: Session = Depends(get_db)):
    # Simplified: count all bags in DB
    total = db.query(BagEvent).count()
    by_class = {}
    for cls in ["25kg", "50kg", "empty"]:
        by_class[cls] = db.query(BagEvent).filter_by(bag_class=cls).count()
    return {"total_counted": total, "by_class": by_class}
