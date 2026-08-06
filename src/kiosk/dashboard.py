"""
Streamlit Operator Dashboard for Bag Counter Edge.

Features:
- Live video preview (optional)
- Current shift / wagon stats
- Bag count by class (25kg / 50kg / empty)
- Event log table
- "Close Wagon" button
- "Start New Shift" button
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import streamlit as st
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.db.models import SessionLocal, Shift, Wagon, BagEvent, BagClass
from src.config import settings

st.set_page_config(page_title="Bag Counter Edge", layout="wide")


# ── DB helpers ──────────────────────────────────────────────────────────────
@st.cache_resource
def get_db() -> Session:
    return SessionLocal()


def get_active_shift(db: Session) -> Optional[Shift]:
    return db.query(Shift).filter_by(is_active=True).first()


def get_active_wagon(db: Session) -> Optional[Wagon]:
    return db.query(Wagon).filter_by(is_active=True).first()


def get_stats(db: Session, wagon_id: Optional[int] = None) -> dict:
    q = db.query(BagEvent)
    if wagon_id:
        q = q.filter_by(wagon_id=wagon_id)
    total = q.count()
    by_class = {}
    for cls in BagClass:
        by_class[cls.value] = q.filter_by(bag_class=cls).count()
    # Total estimated weight
    weight_25 = by_class.get("25kg", 0) * 25
    weight_50 = by_class.get("50kg", 0) * 50
    total_weight = weight_25 + weight_50
    return {
        "total": total,
        "by_class": by_class,
        "total_weight_kg": total_weight,
    }


def get_recent_events(db: Session, limit: int = 50):
    return (
        db.query(BagEvent)
        .order_by(BagEvent.counted_at.desc())
        .limit(limit)
        .all()
    )


# ── UI ──────────────────────────────────────────────────────────────────────
def render_header():
    st.title("🎯 Bag Counter Edge — Operator Dashboard")
    st.markdown("---")


def render_status_cards(db: Session):
    shift = get_active_shift(db)
    wagon = get_active_wagon(db)
    stats = get_stats(db, wagon.id if wagon else None)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Shift", shift.operator_name if shift else "—")
    with col2:
        st.metric("Wagon", wagon.wagon_number if wagon else "—")
    with col3:
        st.metric("Bags Counted", stats["total"])
    with col4:
        st.metric("Est. Weight (kg)", stats["total_weight_kg"])

    return shift, wagon, stats


def render_class_breakdown(stats: dict):
    st.subheader("📦 Bag Breakdown")
    cols = st.columns(3)
    classes = [("25kg", "🟡"), ("50kg", "🟠"), ("empty", "⚪")]
    for (name, emoji), col in zip(classes, cols):
        count = stats["by_class"].get(name, 0)
        col.metric(f"{emoji} {name}", count)


def render_event_log(db: Session):
    st.subheader("📝 Recent Events")
    events = get_recent_events(db, limit=30)
    if not events:
        st.info("No events recorded yet.")
        return

    data = []
    for e in events:
        data.append({
            "ID": e.id,
            "Track": e.track_id,
            "Class": e.bag_class.value if e.bag_class else "—",
            "Volume (L)": round(e.estimated_volume_liters, 1) if e.estimated_volume_liters else "—",
            "Time": e.counted_at.strftime("%H:%M:%S") if e.counted_at else "—",
            "Clip": "🎬" if e.clip_path else "—",
        })
    st.dataframe(data, use_container_width=True, hide_index=True)


def render_actions(db: Session):
    st.subheader("⚡ Actions")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🚪 Close Current Wagon", type="primary", use_container_width=True):
            wagon = get_active_wagon(db)
            if wagon:
                wagon.is_active = False
                wagon.ended_at = datetime.now(timezone.utc)
                db.commit()
                st.success(f"Wagon {wagon.wagon_number} closed.")
                time.sleep(1)
                st.rerun()
            else:
                st.warning("No active wagon to close.")

    with col2:
        if st.button("🔄 Start New Wagon", use_container_width=True):
            shift = get_active_shift(db)
            if not shift or not shift.is_active:
                st.error("No active shift. Start a new shift first.")
                return

            # Close any existing active wagon
            existing = db.query(Wagon).filter_by(is_active=True).first()
            if existing:
                existing.is_active = False
                existing.ended_at = datetime.now(timezone.utc)

            new_num = st.text_input("Wagon Number", value="W002", key="wagon_input")
            if st.button("Confirm New Wagon", key="confirm_wagon"):
                new_wagon = Wagon(
                    shift_id=shift.id,
                    wagon_number=new_num,
                    is_active=True,
                )
                db.add(new_wagon)
                db.commit()
                st.success(f"Wagon {new_num} started!")
                time.sleep(1)
                st.rerun()

    st.markdown("---")
    if st.button("🌙 End Shift & Start New", use_container_width=True):
        shift = get_active_shift(db)
        if shift:
            shift.is_active = False
            shift.ended_at = datetime.now(timezone.utc)
            # Close active wagon too
            wagon = get_active_wagon(db)
            if wagon:
                wagon.is_active = False
                wagon.ended_at = datetime.now(timezone.utc)
            db.commit()

        new_shift = Shift(operator_name="auto", is_active=True)
        db.add(new_shift)
        db.commit()
        db.refresh(new_shift)
        st.success("New shift started.")
        time.sleep(1)
        st.rerun()


# ── Main ────────────────────────────────────────────────────────────────────
def main():
    db = get_db()
    render_header()

    # Auto-refresh every 5 seconds
    st_autorefresh = st.empty()
    st_autorefresh.markdown(
        """<meta http-equiv="refresh" content="5">""",
        unsafe_allow_html=True,
    )

    shift, wagon, stats = render_status_cards(db)
    render_class_breakdown(stats)
    render_actions(db)
    render_event_log(db)

    # Debug: show DB path
    with st.expander("🔧 System Info"):
        st.code(f"DB: {settings.DB_PATH}\nClips: {settings.CLIPS_DIR}")


if __name__ == "__main__":
    main()
