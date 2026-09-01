"""
Unit tests for notification service.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

from src.notifications.notifier import NotificationService, WagonReport


@pytest.fixture
def sample_report():
    """Create a sample WagonReport for testing."""
    return WagonReport(
        wagon_number="WGN-12345",
        shift_operator="John Doe",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        total_bags=100,
        bags_25kg=60,
        bags_50kg=30,
        empty_bags=10,
        total_weight_kg=3000,
        avg_volume_liters=25.5,
        top_clip_paths=["/path/to/clip1.mp4", "/path/to/clip2.mp4"]
    )


@pytest.fixture
def notifier():
    """Create a NotificationService instance."""
    return NotificationService()


class TestNotificationService:
    """Tests for NotificationService class."""
    
    def test_format_message(self, notifier, sample_report):
        """Test message formatting for notifications."""
        message = notifier.format_message(sample_report)
        
        assert "WGN-12345" in message
        assert "John Doe" in message
        assert "100" in message
        assert "60" in message  # 25kg bags
        assert "30" in message  # 50kg bags
        assert "3000" in message  # weight
    
    def test_email_disabled_when_not_configured(self, notifier):
        """Test email is disabled when settings are missing."""
        assert notifier._enabled_email() is False
    
    def test_telegram_disabled_when_not_configured(self, notifier):
        """Test Telegram is disabled when settings are missing."""
        assert notifier._enabled_telegram() is False
    
    @patch('smtplib.SMTP')
    def test_send_email_success(self, mock_smtp, notifier, sample_report, monkeypatch):
        """Test successful email sending."""
        # Configure mock SMTP
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__ = lambda s: mock_server
        mock_smtp.return_value.__exit__ = lambda s, *args: None
        
        # Monkeypatch settings
        monkeypatch.setattr(notifier, 'smtp_host', 'smtp.example.com')
        monkeypatch.setattr(notifier, 'smtp_port', 587)
        monkeypatch.setattr(notifier, 'smtp_user', 'user@example.com')
        monkeypatch.setattr(notifier, 'smtp_pass', 'password')
        monkeypatch.setattr(notifier, 'email_from', 'user@example.com')
        monkeypatch.setattr(notifier, 'email_to', ['recipient@example.com'])
        
        result = notifier.send_email(sample_report)
        
        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.sendmail.assert_called_once()
    
    @patch('requests.post')
    def test_send_telegram_success(self, mock_post, notifier, sample_report, monkeypatch):
        """Test successful Telegram notification."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        monkeypatch.setattr(notifier, 'tg_token', 'test_token')
        monkeypatch.setattr(notifier, 'tg_chat_id', '123456')
        
        result = notifier.send_telegram(sample_report)
        
        assert result is True
        mock_post.assert_called_once()
    
    def test_notify_wagon_closed_calls_both_channels(self, notifier, sample_report):
        """Test that notify_wagon_closed calls both email and telegram."""
        with patch.object(notifier, 'send_email') as mock_email, \
             patch.object(notifier, 'send_telegram') as mock_telegram:
            
            notifier.notify_wagon_closed(sample_report)
            
            mock_email.assert_called_once_with(sample_report)
            mock_telegram.assert_called_once_with(sample_report)
