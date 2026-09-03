"""
Streamlit Operator Dashboard for Bag Counter Edge.

Features:
- Real-time updates via WebSocket (no page refresh)
- Live video streaming option
- Modern elegant UI with custom CSS
- Prometheus metrics endpoint
- Event log with auto-scroll
- Shift/Wagon management

Architecture:
- Uses WebSocket for real-time bag count updates
- Optional MJPEG stream for live video
- Custom CSS for modern look (no 90s style!)
- Prometheus-compatible /metrics endpoint
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any
import threading

from dotenv import load_dotenv
import streamlit as st
import requests
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.sql import text

from src.db.models import SessionLocal, Shift, Wagon, BagEvent, BagClass
from src.config import settings

# Load environment variables from .env file
load_dotenv()

# Page config - must be first Streamlit command
st.set_page_config(
    page_title="🎯 Bag Counter Edge | Kiosk",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS for Modern UI ─────────────────────────────────────────────────
CUSTOM_CSS = """
<style>
/* Global styles */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* Hide Streamlit branding */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Modern card styling */
.metric-card {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 16px;
    padding: 24px;
    color: white;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    margin-bottom: 16px;
}

.metric-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 12px rgba(0, 0, 0, 0.15);
}

.metric-card h3 {
    font-size: 14px;
    font-weight: 500;
    opacity: 0.9;
    margin: 0 0 8px 0;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.metric-card .value {
    font-size: 36px;
    font-weight: 700;
    margin: 0;
}

.metric-card .unit {
    font-size: 14px;
    font-weight: 400;
    opacity: 0.8;
    margin-left: 4px;
}

/* Status indicators */
.status-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.status-active {
    background: rgba(34, 197, 94, 0.2);
    color: #22c55e;
}

.status-inactive {
    background: rgba(148, 163, 184, 0.2);
    color: #94a3b8;
}

/* Event log table */
.event-log-table {
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.event-log-table th {
    background: #f8fafc;
    font-weight: 600;
    color: #475569;
    padding: 12px 16px;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.5px;
}

.event-log-table td {
    padding: 12px 16px;
    border-bottom: 1px solid #f1f5f9;
}

/* Bag class badges */
.bag-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    border-radius: 8px;
    font-weight: 500;
    font-size: 13px;
}

.bag-25kg {
    background: rgba(234, 179, 8, 0.15);
    color: #ca8a04;
}

.bag-50kg {
    background: rgba(249, 115, 22, 0.15);
    color: #ea580c;
}

.bag-empty {
    background: rgba(148, 163, 184, 0.15);
    color: #64748b;
}

/* Video container */
.video-container {
    position: relative;
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    background: #0f172a;
}

.video-overlay {
    position: absolute;
    top: 12px;
    right: 12px;
    background: rgba(0, 0, 0, 0.7);
    color: white;
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 500;
    backdrop-filter: blur(4px);
}

.live-indicator {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: #ef4444;
    font-weight: 600;
}

.live-dot {
    width: 8px;
    height: 8px;
    background: #ef4444;
    border-radius: 50%;
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
}

/* Action buttons */
.action-btn {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: 12px;
    font-weight: 600;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s ease;
    box-shadow: 0 2px 4px rgba(102, 126, 234, 0.3);
}

.action-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 8px rgba(102, 126, 234, 0.4);
}

.action-btn.secondary {
    background: white;
    color: #475569;
    border: 1px solid #e2e8f0;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.action-btn.danger {
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
    box-shadow: 0 2px 4px rgba(239, 68, 68, 0.3);
}

/* Sidebar styling */
.css-1dhrbxs {
    background: #f8fafc;
}

/* Metrics grid */
.metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 8px;
}

/* Reduce top padding for main content */
.main > div:first-child {
    padding-top: 10px !important;
}

/* Remove extra spacing from headers */
.css-1l02zno, .css-53h4ph {
    margin-top: 0 !important;
    margin-bottom: 0 !important;
}

/* Animations */
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

.fade-in {
    animation: fadeIn 0.3s ease-out;
}

/* Scrollbar styling */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}

::-webkit-scrollbar-track {
    background: #f1f5f9;
    border-radius: 4px;
}

::-webkit-scrollbar-thumb {
    background: #cbd5e1;
    border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
    background: #94a3b8;
}
</style>
"""

# ── State Management ─────────────────────────────────────────────────────────
def init_session_state():
    """Initialize Streamlit session state."""
    if "ws_connected" not in st.session_state:
        st.session_state.ws_connected = False
    if "last_update" not in st.session_state:
        st.session_state.last_update = None
    if "stats_cache" not in st.session_state:
        st.session_state.stats_cache = {
            "total": 0,
            "by_class": {"25kg": 0, "50kg": 0, "empty": 0},
            "total_weight_kg": 0,
        }
    if "events_cache" not in st.session_state:
        st.session_state.events_cache = []
    if "live_video_enabled" not in st.session_state:
        st.session_state.live_video_enabled = False
    if "auto_scroll" not in st.session_state:
        st.session_state.auto_scroll = True


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


# ── WebSocket Client for Real-time Updates ──────────────────────────────────
class WebSocketClient:
    """Async WebSocket client for receiving real-time updates."""
    
    def __init__(self, url: str):
        self.url = url
        self.websocket = None
        self.running = False
        self._loop = None
        self._task = None
        
    async def connect_and_listen(self, on_message_callback):
        """Connect to WebSocket and listen for messages."""
        import websockets
        try:
            async with websockets.connect(self.url) as websocket:
                self.websocket = websocket
                self.running = True
                while self.running:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        data = json.loads(message)
                        on_message_callback(data)
                    except asyncio.TimeoutError:
                        continue
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            st.error(f"WebSocket error: {e}")
            self.running = False
    
    def start(self, on_message_callback):
        """Start WebSocket listener in background thread."""
        def run_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.connect_and_listen(on_message_callback))
        
        self._thread = threading.Thread(target=run_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        """Stop WebSocket listener."""
        self.running = False


# ── UI Components ───────────────────────────────────────────────────────────
def render_header():
    """Render modern header."""
    # Use tighter columns and remove bottom margin
    col1, col2, col3 = st.columns([4, 1, 1])
    
    with col1:
        # Remove margin-bottom and use compact layout - no icon
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 0px;">
            <div>
                <h1 style="margin: 0; font-size: 22px; font-weight: 700; color: #1e293b;">
                    Bag Counter Edge
                </h1>
                <p style="margin: 0; font-size: 12px; color: #64748b;">
                    Real-time Operator Dashboard
                </p>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # Connection status
        status_color = "#22c55e" if st.session_state.ws_connected else "#94a3b8"
        status_text = "Connected" if st.session_state.ws_connected else "Offline"
        st.markdown(f"""
        <div style="text-align: right; padding-top: 8px;">
            <span class="status-badge" style="background: rgba({status_color}, 0.2); color: {status_color};">
                ● {status_text}
            </span>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        # Timestamp with UTC+5 timezone
        from datetime import timedelta
        utc_now = datetime.now(timezone.utc)
        utc_plus_5 = utc_now + timedelta(hours=5)
        now = utc_plus_5.strftime("%H:%M:%S")
        st.markdown(f"""
        <div style="text-align: right; color: #64748b; font-size: 13px; padding-top: 10px;">
            {now} <span style="font-size: 11px;">(UTC+5)</span>
        </div>
        """, unsafe_allow_html=True)
    
    # Remove the horizontal line to save space
    # st.markdown("---")


def render_metric_card(title: str, value: str, unit: str = "", icon: str = "📊"):
    """Render a modern metric card."""
    st.markdown(f"""
    <div class="metric-card fade-in">
        <h3>{icon} {title}</h3>
        <p class="value">{value}<span class="unit">{unit}</span></p>
    </div>
    """, unsafe_allow_html=True)


def render_status_cards(db: Session):
    """Render status cards with current shift/wagon info."""
    shift = get_active_shift(db)
    wagon = get_active_wagon(db)
    stats = get_stats(db, wagon.id if wagon else None)
    
    # Cache stats for comparison
    old_stats = st.session_state.stats_cache.copy()
    st.session_state.stats_cache = stats
    
    # Modern metrics grid
    st.markdown('<div class="metrics-grid">', unsafe_allow_html=True)
    
    cols = st.columns(4)
    
    with cols[0]:
        status_class = "status-active" if shift and shift.is_active else "status-inactive"
        status_text = shift.operator_name if shift else "No Shift"
        st.markdown(f"""
        <div class="metric-card" style="background: linear-gradient(135deg, #10b981 0%, #059669 100%);">
            <h3>👤 Shift Operator</h3>
            <p class="value" style="font-size: 20px;">{status_text}</p>
            <span class="status-badge {status_class}" style="margin-top: 8px;">
                {'Active' if shift and shift.is_active else 'Inactive'}
            </span>
        </div>
        """, unsafe_allow_html=True)
    
    with cols[1]:
        st.markdown(f"""
        <div class="metric-card" style="background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);">
            <h3>🚂 Active Wagon</h3>
            <p class="value" style="font-size: 20px;">{wagon.wagon_number if wagon else "—"}</p>
            <span class="status-badge {status_class}" style="margin-top: 8px;">
                {'Loading' if wagon and wagon.is_active else 'None'}
            </span>
        </div>
        """, unsafe_allow_html=True)
    
    with cols[2]:
        # Animate counter change
        total = stats["total"]
        old_total = old_stats["total"]
        animation = "color: #22c55e;" if total > old_total else ""
        st.markdown(f"""
        <div class="metric-card" style="background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);">
            <h3>📦 Bags Counted</h3>
            <p class="value" style="{animation}">{total}</p>
            <p style="margin: 8px 0 0 0; opacity: 0.8; font-size: 13px;">
                +{total - old_total} since last update
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with cols[3]:
        st.markdown(f"""
        <div class="metric-card" style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);">
            <h3>⚖️ Est. Weight</h3>
            <p class="value">{stats["total_weight_kg"]:,}<span class="unit">kg</span></p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    return shift, wagon, stats


def render_class_breakdown(stats: dict):
    """Render bag class breakdown with modern badges."""
    st.markdown("### Bag Classification Breakdown")
    
    cols = st.columns(3)
    classes = [
        ("25kg", "🟡", "bag-25kg", "Standard 25kg"),
        ("50kg", "🟠", "bag-50kg", "Heavy 50kg"),
        ("empty", "⚪", "bag-empty", "Empty/Defective"),
    ]
    
    for (name, emoji, badge_class, description), col in zip(classes, cols):
        count = stats["by_class"].get(name, 0)
        percentage = (count / max(stats["total"], 1)) * 100
        
        col.markdown(f"""
        <div style="
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        ">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <span class="bag-badge {badge_class}">{emoji} {name}</span>
                <span style="font-size: 28px; font-weight: 700; color: #1e293b;">{count}</span>
            </div>
            <div style="
                background: #f1f5f9;
                border-radius: 8px;
                height: 8px;
                overflow: hidden;
            ">
                <div style="
                    width: {percentage}%;
                    height: 100%;
                    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
                    border-radius: 8px;
                    transition: width 0.3s ease;
                "></div>
            </div>
            <p style="margin: 8px 0 0 0; font-size: 12px; color: #64748b;">
                {percentage:.1f}% of total • {description}
            </p>
        </div>
        """, unsafe_allow_html=True)


def render_live_video():
    """Render live video stream from MJPEG endpoint."""
    st.markdown("### Live Camera Feed")
    
    if not st.session_state.live_video_enabled:
        st.info("👆 Enable live video in the sidebar to see real-time camera feed")
        return
    
    # Определяем базовый URL для API динамически
    # Логика приоритетов:
    # 1. Явные переменные DASHBOARD_API_HOST и DASHBOARD_API_PORT имеют наивысший приоритет
    # 2. Если их нет, используем RUN_MODE=docker → http://edge-cv:<port>
    # 3. Иначе конструируем из API_HOST:API_PORT (для local и network режимов)
    
    dashboard_api_host = os.getenv("DASHBOARD_API_HOST")
    dashboard_api_port = os.getenv("DASHBOARD_API_PORT")
    
    if dashboard_api_host and dashboard_api_port:
        # Явные настройки для Dashboard имеют приоритет
        api_base_url = f"http://{dashboard_api_host}:{dashboard_api_port}"
    else:
        run_mode = os.getenv("RUN_MODE", "local")
        
        if run_mode == "docker":
            # Для режима docker используем имя сервиса edge-cv
            # Работает только когда браузер находится внутри той же Docker-сети
            api_port = os.getenv("API_PORT", "8000")
            api_base_url = f"http://edge-cv:{api_port}"
        else:
            # Для local и network режимов используем API_HOST
            # Это должен быть IP-адрес или домен, доступный из вашей сети
            api_host = os.getenv("API_HOST", "localhost")
            api_port = os.getenv("API_PORT", "8000")
            api_base_url = f"http://{api_host}:{api_port}"
    
    video_url = f"{api_base_url}/api/v1/video/stream"
    
    # Try to fetch a frame to test connectivity
    try:
        response = requests.get(video_url, timeout=2, stream=True)
        if response.status_code != 200:
            st.error(f"❌ Video stream unavailable (HTTP {response.status_code})")
            st.warning(f"Check that API server is running at {api_base_url}")
            return
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Cannot connect to video stream: {str(e)}")
        st.warning(f"Current API URL: {api_base_url}")
        if dashboard_api_host and dashboard_api_port:
            st.info(f"💡 Using explicit DASHBOARD_API_HOST={dashboard_api_host}:{dashboard_api_port} - check that this address is reachable from your browser")
        elif run_mode == "docker":
            st.info("💡 Running in Docker mode - make sure dashboard and edge-cv are in the same Docker network")
        else:
            st.info(f"💡 Running in {run_mode} mode - check that API_HOST={api_host} is correct and reachable from your browser")
        return
    
    # Render video with HTML img tag for MJPEG stream
    st.markdown(f"""
    <div class="video-container">
        <div class="video-overlay">
            <span class="live-indicator">
                <span class="live-dot"></span>
                LIVE
            </span>
        </div>
        <img src="{video_url}" style="width: 100%; height: auto; border-radius: 16px;" alt="Live stream">
    </div>
    """, unsafe_allow_html=True)


def render_event_log(db: Session):
    """Render event log with modern styling."""
    st.markdown("### Recent Detection Events")
    
    events = get_recent_events(db, limit=20)
    
    if not events:
        st.info("📭 No events recorded yet. Waiting for bags on conveyor...")
        return
    
    # Build event data with styling
    event_rows = []
    for e in events:
        badge_class = f"bag-{e.bag_class.value}" if e.bag_class else ""
        emoji = {"25kg": "🟡", "50kg": "🟠", "empty": "⚪"}.get(e.bag_class.value if e.bag_class else "", "⚪")
        
        event_rows.append({
            "time": e.counted_at.strftime("%H:%M:%S") if e.counted_at else "—",
            "class": f'<span class="bag-badge {badge_class}">{emoji} {e.bag_class.value if e.bag_class else "—"}</span>',
            "volume": f"{e.estimated_volume_liters:.1f} L" if e.estimated_volume_liters else "—",
            "confidence": f"{e.confidence:.0%}" if e.confidence else "—",
            "clip": "🎬" if e.clip_path else "—",
        })
    
    # Display as styled table
    st.dataframe(
        event_rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "time": "Time",
            "class": st.column_config.TextColumn("Class"),
            "volume": "Volume",
            "confidence": "Confidence",
            "clip": "Clip",
        },
    )


def render_actions(db: Session):
    """Render action buttons with modern styling."""
    st.markdown("### Quick Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🚪 Close Current Wagon", type="primary", use_container_width=True):
            wagon = get_active_wagon(db)
            if wagon:
                wagon.is_active = False
                wagon.ended_at = datetime.now(timezone.utc)
                db.commit()
                st.success(f"Wagon {wagon.wagon_number} closed successfully!")
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
            
            # Show input dialog
            with st.form("new_wagon_form"):
                new_num = st.text_input("Wagon Number", value="W002")
                submitted = st.form_submit_button("Confirm New Wagon")
                if submitted:
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
    
    with col3:
        if st.button("🌙 End Shift & Start New", type="secondary", use_container_width=True):
            shift = get_active_shift(db)
            if shift:
                shift.is_active = False
                shift.ended_at = datetime.now(timezone.utc)
                wagon = get_active_wagon(db)
                if wagon:
                    wagon.is_active = False
                    wagon.ended_at = datetime.now(timezone.utc)
                db.commit()
            
            new_shift = Shift(operator_name="auto", is_active=True)
            db.add(new_shift)
            db.commit()
            db.refresh(new_shift)
            st.success("New shift started automatically.")
            time.sleep(1)
            st.rerun()


def render_sidebar():
    """Render sidebar with settings."""
    with st.sidebar:
        st.markdown("### Dashboard Settings")
        
        st.session_state.live_video_enabled = st.toggle(
            "📹 Live Video",
            value=st.session_state.live_video_enabled,
            help="Enable real-time camera feed"
        )
        
        st.session_state.auto_scroll = st.toggle(
            "📜 Auto-scroll Events",
            value=st.session_state.auto_scroll,
            help="Automatically scroll to latest events"
        )
        
        st.markdown("---")
        st.markdown("### System Info")
        
        st.code(f"""DB: {settings.DB_PATH}
Clips: {settings.CLIPS_DIR}
Model: {settings.DETECTION_MODEL}""")
        
        # Prometheus metrics link
        st.markdown("""
        ### Monitoring
        
        [📈 View Prometheus Metrics](/metrics)
        
        [📊 Grafana Dashboard](http://grafana:3000)
        """)


# ── Main Application ────────────────────────────────────────────────────────
def main():
    # Initialize session state
    init_session_state()
    
    # Inject custom CSS
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    
    # Render sidebar
    render_sidebar()
    
    # Render header
    render_header()
    
    # Get DB session
    db = get_db()
    
    # Render main content
    shift, wagon, stats = render_status_cards(db)
    
    # Two-column layout with reduced gap
    col1, col2 = st.columns([2, 1], gap="small")
    
    with col1:
        render_class_breakdown(stats)
        render_event_log(db)
    
    with col2:
        if st.session_state.live_video_enabled:
            render_live_video()
            
            # Turn OFF button below video
            st.markdown("<div style='margin-top: 16px;'>", unsafe_allow_html=True)
            if st.button(
                "⏹️ Выключить видео",
                key="turn_off_video",
                use_container_width=True,
                help="Отключить трансляцию видео с камеры"
            ):
                st.session_state.live_video_enabled = False
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.markdown("""
            ### Live Preview
            
            <div style="
                background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
                border-radius: 16px;
                padding: 40px;
                text-align: center;
                color: #64748b;
            ">
                <div style="font-size: 48px; margin-bottom: 16px;">📷</div>
                <p style="font-size: 14px;">Live video disabled</p>
                <p style="font-size: 12px; margin-top: 8px;">Enable to view camera feed with detection</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Turn ON button below placeholder
            st.markdown("<div style='margin-top: 16px;'>", unsafe_allow_html=True)
            if st.button(
                "▶️ Включить видео",
                key="turn_on_video",
                use_container_width=True,
                type="primary",
                help="Включить трансляцию видео с камеры для наблюдения за детекцией мешков"
            ):
                st.session_state.live_video_enabled = True
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        
        render_actions(db)
    
    # Auto-refresh logic using Streamlit's experimental rerun
    # This replaces the old meta refresh approach
    if "counter" not in st.session_state:
        st.session_state.counter = 0
    st.session_state.counter += 1
    
    # Trigger rerun every 3 seconds for real-time updates
    time.sleep(0.1)  # Small delay to allow WebSocket messages
    st.rerun()


if __name__ == "__main__":
    main()
