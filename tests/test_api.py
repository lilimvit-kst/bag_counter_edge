"""
Integration tests for API endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.api.app import app
from src.config import settings


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def auth_token():
    """Generate a valid JWT token for testing."""
    from jose import jwt
    payload = {"sub": "test_user"}
    return jwt.encode(payload, settings.API_SECRET_KEY, algorithm="HS256")


class TestAPIEndpoints:
    """Tests for API endpoints."""
    
    def test_health_check(self, client):
        """Test health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    
    def test_active_wagon_no_auth(self, client):
        """Test active wagon endpoint without authentication."""
        response = client.get("/api/v1/wagons/active")
        # Should work without auth for read operations
        assert response.status_code in [200, 401]
    
    def test_send_notification_requires_auth(self, client):
        """Test notification endpoint requires authentication."""
        response = client.post(
            "/api/v1/tasks/send-notification",
            json={"event_type": "test", "data": {}}
        )
        assert response.status_code == 401
    
    def test_send_notification_with_auth(self, client, auth_token):
        """Test notification endpoint with valid authentication."""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        with patch('src.tasks.tasks.send_notification_task.delay') as mock_delay:
            mock_delay.return_value = MagicMock(id="test-task-id")
            
            response = client.post(
                "/api/v1/tasks/send-notification",
                json={"event_type": "wagon_closed", "data": {"wagon_id": 1}},
                headers=headers
            )
            
            assert response.status_code == 200
            assert "task_id" in response.json()
            mock_delay.assert_called_once()
    
    def test_generate_report_requires_auth(self, client):
        """Test report generation requires authentication."""
        response = client.post("/api/v1/tasks/generate-report/1")
        assert response.status_code == 401
    
    def test_update_dashboard_non_blocking(self, client, auth_token):
        """Test dashboard update is non-blocking."""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        with patch('src.tasks.tasks.update_dashboard_task.delay') as mock_delay:
            mock_delay.return_value = MagicMock(id="dashboard-task-id")
            
            response = client.post(
                "/api/v1/tasks/update-dashboard",
                json={"wagon_id": 1},
                headers=headers
            )
            
            assert response.status_code == 200
            assert response.json()["status"] == "queued"
            assert "task_id" in response.json()
            # Should not block waiting for result
            assert "result" not in response.json()


class TestJWTAuthentication:
    """Tests for JWT authentication."""
    
    def test_invalid_token_rejected(self, client):
        """Test that invalid JWT tokens are rejected."""
        headers = {"Authorization": "Bearer invalid_token"}
        
        response = client.post(
            "/api/v1/tasks/send-notification",
            json={"event_type": "test", "data": {}},
            headers=headers
        )
        assert response.status_code == 401
    
    def test_expired_token_rejected(self, client):
        """Test that expired JWT tokens are rejected."""
        from jose import jwt
        from datetime import datetime, timezone, timedelta
        
        # Create expired token
        payload = {
            "sub": "test_user",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1)
        }
        expired_token = jwt.encode(payload, settings.API_SECRET_KEY, algorithm="HS256")
        
        headers = {"Authorization": f"Bearer {expired_token}"}
        
        response = client.post(
            "/api/v1/tasks/send-notification",
            json={"event_type": "test", "data": {}},
            headers=headers
        )
        assert response.status_code == 401
