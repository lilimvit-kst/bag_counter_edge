"""
Streamlit Operator Dashboard for Bag Counter Edge.

Features:
- Live video preview with real-time counting overlay
- Current shift / wagon stats with auto-refresh (no page flicker)
- Bag count by class (25kg / 50kg / empty)
- Event log table with filtering
- "Close Wagon" / "Start New Wagon" / "End Shift" actions
- Modern elegant UI design
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import requests
from requests.exceptions import RequestException

import streamlit as st
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.db.models import SessionLocal, Shift, Wagon, BagEvent, BagClass
from src.config import settings

# ── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="🎯 Bag Counter Edge",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS for Modern UI ─────────────────────────────────────────────────
def load_custom_css():
    st.markdown("""
    <style>
    /* Main container */
    .main > div {
        padding: 2rem 3rem;
    }
    
    /* Header styling */
    .dashboard-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .dashboard-header h1 {
        color: white !important;
        margin: 0;
        font-size: 2.5rem;
        font-weight: 700;
    }
    .dashboard-header p {
        color: rgba(255,255,255,0.9);
        margin: 0.5rem 0 0 0;
        font-size: 1.1rem;
    }
    
    /* Status cards */
    .status-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        text-align: center;
        transition: transform 0.2s;
        height: 100%;
        border-left: 4px solid #667eea;
    }
    .status-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(0,0,0,0.12);
    }
    .status-card .label {
        color: #666;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 0.5rem;
    }
    .status-card .value {
        color: #333;
        font-size: 1.8rem;
        font-weight: 700;
    }
    .status-card .subtext {
        color: #999;
        font-size: 0.8rem;
        margin-top: 0.3rem;
    }
    
    /* Bag class cards */
    .bag-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.08);
        text-align: center;
        height: 100%;
    }
    .bag-card .emoji {
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
    }
    .bag-card .count {
        color: #333;
        font-size: 2rem;
        font-weight: 700;
    }
    .bag-card .label {
        color: #666;
        font-size: 0.9rem;
        text-transform: uppercase;
    }
    
    /* Video container */
    .video-container {
        background: #1a1a2e;
        padding: 1rem;
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    
    /* Event log table */
    .event-log-container {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.08);
    }
    
    /* Action buttons */
    .stButton > button {
        border-radius: 8px;
        font-weight: 600;
        padding: 0.75rem 1.5rem;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    
    /* Metrics override */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
    }
    
    /* Hide default Streamlit decorations */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

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
    
    # Get last event time
    last_event = q.order_by(BagEvent.counted_at.desc()).first()
    last_count_time = last_event.counted_at.strftime("%H:%M:%S") if last_event and last_event.counted_at else "—"
    
    return {
        "total": total,
        "by_class": by_class,
        "total_weight_kg": total_weight,
        "last_count_time": last_count_time,
    }


def get_recent_events(db: Session, limit: int = 50):
    return (
        db.query(BagEvent)
        .order_by(BagEvent.counted_at.desc())
        .limit(limit)
        .all()
    )


# ── Live Video Component ─────────────────────────────────────────────────────
def get_latest_frame_url() -> Optional[str]:
    """Get URL of the latest frame from the API."""
    try:
        # Assuming API endpoint exists for latest frame
        api_url = f"http://{settings.API_HOST}:{settings.API_PORT}/api/v1/live/frame"
        response = requests.get(api_url, timeout=2)
        if response.status_code == 200:
            return api_url
    except RequestException:
        pass
    return None


def render_live_video():
    """Render live video feed with counting overlay."""
    st.subheader("📹 Live Feed")
    
    # Try to get live frame from API
    frame_url = get_latest_frame_url()
    
    if frame_url:
        st.image(frame_url, use_container_width=True, caption="Live camera feed • Auto-updating")
    else:
        # Fallback: show placeholder or last clip
        st.info("📡 Waiting for video stream... Ensure the detection service is running.")
        
        # Show last recorded clip if available
        clips_dir = Path(settings.CLIPS_DIR)
        if clips_dir.exists():
            clips = list(clips_dir.glob("*.mp4"))
            if clips:
                latest_clip = max(clips, key=lambda p: p.stat().st_mtime)
                st.video(str(latest_clip))
                st.caption(f"Last recorded clip: {latest_clip.name}")


# ── UI Components ────────────────────────────────────────────────────────────
def render_header():
    """Render modern header with gradient background."""
    st.markdown("""
    <div class="dashboard-header">
        <h1>🎯 Bag Counter Edge</h1>
        <p>Real-time flour bag counting & monitoring system</p>
    </div>
    """, unsafe_allow_html=True)


def render_status_cards(db: Session):
    """Render status cards with modern styling."""
    shift = get_active_shift(db)
    wagon = get_active_wagon(db)
    stats = get_stats(db, wagon.id if wagon else None)

    st.markdown("### 📊 Current Status")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="status-card">
            <div class="label">👤 Operator</div>
            <div class="value">{shift.operator_name if shift else "—"}</div>
            <div class="subtext">Active Shift</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="status-card">
            <div class="label">🚂 Wagon</div>
            <div class="value">{wagon.wagon_number if wagon else "—"}</div>
            <div class="subtext">Loading in progress</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="status-card">
            <div class="label">📦 Total Bags</div>
            <div class="value">{stats["total"]:,}</div>
            <div class="subtext">Last: {stats["last_count_time"]}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="status-card">
            <div class="label">⚖️ Est. Weight</div>
            <div class="value">{stats["total_weight_kg"]:,} kg</div>
            <div class="subtext">Total loaded</div>
        </div>
        """, unsafe_allow_html=True)

    return shift, wagon, stats


def render_class_breakdown(stats: dict):
    """Render bag class breakdown with emoji cards."""
    st.markdown("### 📦 Bag Classification")
    
    cols = st.columns(3)
    classes = [
        ("25kg", "🟡", "Standard 25kg bags"),
        ("50kg", "🟠", "Standard 50kg bags"),
        ("empty", "⚪", "Empty/defective bags"),
    ]
    
    for (name, emoji, description), col in zip(classes, cols):
        count = stats["by_class"].get(name, 0)
        percentage = (count / max(stats["total"], 1)) * 100
        
        col.markdown(f"""
        <div class="bag-card">
            <div class="emoji">{emoji}</div>
            <div class="count">{count:,}</div>
            <div class="label">{name}</div>
            <div style="color: #999; font-size: 0.75rem; margin-top: 0.3rem;">{percentage:.1f}% • {description}</div>
        </div>
        """, unsafe_allow_html=True)


def render_event_log(db: Session):
    """Render event log with improved table styling."""
    st.markdown("### 📝 Recent Events")
    
    events = get_recent_events(db, limit=30)
    
    if not events:
        st.info("📭 No events recorded yet. Waiting for bags on conveyor...")
        return

    data = []
    for e in events:
        data.append({
            "🆔 ID": e.id,
            "🔢 Track": e.track_id,
            "🏷️ Class": e.bag_class.value if e.bag_class else "—",
            "📏 Volume (L)": round(e.estimated_volume_liters, 1) if e.estimated_volume_liters else "—",
            "⏰ Time": e.counted_at.strftime("%H:%M:%S") if e.counted_at else "—",
            "🎬 Clip": "✅" if e.clip_path else "—",
        })
    
    st.dataframe(
        data, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "🆔 ID": st.column_config.NumberColumn(format="%d"),
            "🔢 Track": st.column_config.NumberColumn(format="%d"),
        }
    )


def render_actions(db: Session):
    """Render action buttons with modern styling."""
    st.markdown("### ⚡ Control Panel")
    
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🚪 Close Wagon", type="primary", use_container_width=True, key="close_wagon"):
            wagon = get_active_wagon(db)
            if wagon:
                wagon.is_active = False
                wagon.ended_at = datetime.now(timezone.utc)
                db.commit()
                st.success(f"✅ Wagon {wagon.wagon_number} closed successfully!")
                time.sleep(1)
                st.rerun()
            else:
                st.warning("⚠️ No active wagon to close.")

    with col2:
        if st.button("🔄 New Wagon", use_container_width=True, key="new_wagon"):
            shift = get_active_shift(db)
            if not shift or not shift.is_active:
                st.error("❌ No active shift. Start a new shift first.")
                return

            # Close any existing active wagon
            existing = db.query(Wagon).filter_by(is_active=True).first()
            if existing:
                existing.is_active = False
                existing.ended_at = datetime.now(timezone.utc)
                db.commit()

            st.session_state.show_wagon_input = True
            st.rerun()
        
        # Show wagon input if requested
        if st.session_state.get("show_wagon_input", False):
            with st.form("wagon_form"):
                new_num = st.text_input("Wagon Number", value=f"W{int(time.time()) % 10000:04d}")
                submitted = st.form_submit_button("✅ Confirm")
                if submitted:
                    shift = get_active_shift(db)
                    new_wagon = Wagon(
                        shift_id=shift.id,
                        wagon_number=new_num,
                        is_active=True,
                    )
                    db.add(new_wagon)
                    db.commit()
                    st.success(f"✅ Wagon {new_num} started!")
                    st.session_state.show_wagon_input = False
                    time.sleep(1)
                    st.rerun()

    with col3:
        if st.button("🌙 End Shift", use_container_width=True, key="end_shift"):
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
            st.success("✅ New shift started automatically.")
            time.sleep(1)
            st.rerun()


def render_system_info():
    """Render system info in expander."""
    with st.expander("🔧 System Information"):
        st.code(f"""
Database: {settings.DB_PATH}
Clips Directory: {settings.CLIPS_DIR}
API Host: {settings.API_HOST}:{settings.API_PORT}
        """)
        st.caption("Auto-refresh enabled • Updates every 3 seconds without page reload")


# ── Main Application ─────────────────────────────────────────────────────────
def main():
    # Load custom CSS
    load_custom_css()
    
    # Initialize session state
    if "show_wagon_input" not in st.session_state:
        st.session_state.show_wagon_input = False
    
    # Auto-refresh using st_autorefresh (no page flicker!)
    # Updates every 3 seconds - only refreshes data, not entire page
    from streamlit_autorefresh import st_autorefresh
    
    count = st_autorefresh(interval=3000, limit=None, key="datarefresh")
    
    # Render UI
    render_header()
    
    # Two-column layout: video on left, stats on right
    col_video, col_stats = st.columns([2, 1])
    
    with col_video:
        render_live_video()
    
    with col_stats:
        db = get_db()
        shift, wagon, stats = render_status_cards(db)
        render_class_breakdown(stats)
    
    st.markdown("---")
    
    render_actions(db)
    
    st.markdown("---")
    
    render_event_log(db)
    
    render_system_info()


if __name__ == "__main__":
    main()
