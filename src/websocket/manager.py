"""
WebSocket manager for real-time communication with dashboard.

Handles:
- Client connections/disconnections
- Broadcasting events to all connected clients
- Per-channel subscriptions
"""
import asyncio
import json
from typing import Dict, Set, Any
from datetime import datetime, timezone

from loguru import logger


class WebSocketManager:
    """Manage WebSocket connections and broadcast messages."""
    
    def __init__(self):
        # Store active connections: {websocket: set of subscribed channels}
        self.active_connections: Dict[Any, Set[str]] = {}
        self._lock = asyncio.Lock()
        
    async def connect(self, websocket: Any, channel: str = "general") -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self.active_connections[websocket] = {channel}
        logger.info(f"WebSocket client connected on channel '{channel}'")
        
    async def disconnect(self, websocket: Any) -> None:
        """Remove a disconnected client."""
        async with self._lock:
            if websocket in self.active_connections:
                del self.active_connections[websocket]
        logger.info("WebSocket client disconnected")
        
    async def subscribe(self, websocket: Any, channel: str) -> None:
        """Subscribe a client to an additional channel."""
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections[websocket].add(channel)
                logger.debug(f"Client subscribed to channel '{channel}'")
                
    async def unsubscribe(self, websocket: Any, channel: str) -> None:
        """Unsubscribe a client from a channel."""
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections[websocket].discard(channel)
                logger.debug(f"Client unsubscribed from channel '{channel}'")
    
    async def broadcast(self, message: dict, channel: str = "general") -> None:
        """
        Broadcast a message to all clients subscribed to a channel.
        
        Args:
            message: Message dictionary to send
            channel: Channel name to broadcast to
        """
        message_with_timestamp = {
            **message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        message_json = json.dumps(message_with_timestamp)
        
        disconnected = set()
        async with self._lock:
            for websocket, channels in list(self.active_connections.items()):
                if channel in channels or "general" in channels:
                    try:
                        await websocket.send_text(message_json)
                    except Exception as e:
                        logger.warning(f"Failed to send to client: {e}")
                        disconnected.add(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected:
            await self.disconnect(websocket)
    
    async def send_personal(self, message: dict, websocket: Any) -> None:
        """Send a message to a specific client."""
        try:
            message_with_timestamp = {
                **message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await websocket.send_text(json.dumps(message_with_timestamp))
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")
    
    def get_connected_clients_count(self) -> int:
        """Get the number of currently connected clients."""
        return len(self.active_connections)
    
    async def broadcast_stats(self, stats: dict) -> None:
        """Broadcast updated statistics to dashboard clients."""
        await self.broadcast(
            {"type": "stats_update", "data": stats},
            channel="dashboard"
        )
    
    async def broadcast_event(self, event_data: dict) -> None:
        """Broadcast a new bag detection event."""
        await self.broadcast(
            {"type": "bag_detected", "data": event_data},
            channel="events"
        )
    
    async def broadcast_alert(self, alert_data: dict) -> None:
        """Broadcast an alert (camera error, low stock, etc.)."""
        await self.broadcast(
            {"type": "alert", "data": alert_data},
            channel="alerts"
        )


# Global instance
ws_manager = WebSocketManager()


def get_ws_manager() -> WebSocketManager:
    """Get the global WebSocket manager instance."""
    return ws_manager
