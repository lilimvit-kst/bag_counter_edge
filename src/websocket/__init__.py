"""
WebSocket module for real-time communication.
"""
from .manager import WebSocketManager, ws_manager, get_ws_manager

__all__ = [
    "WebSocketManager",
    "ws_manager",
    "get_ws_manager",
]
