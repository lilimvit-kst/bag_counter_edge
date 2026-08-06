"""
Notification service for sending wagon-close reports via Email and Telegram.
"""
from __future__ import annotations

import json
import smtplib
from dataclasses import dataclass
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Optional

import requests
from loguru import logger

from src.config import settings


@dataclass
class WagonReport:
    wagon_number: str
    shift_operator: str
    started_at: datetime
    ended_at: datetime
    total_bags: int
    bags_25kg: int
    bags_50kg: int
    empty_bags: int
    total_weight_kg: int
    avg_volume_liters: float
    top_clip_paths: List[str]


class NotificationService:
    def __init__(self) -> None:
        # Email settings
        self.smtp_host = getattr(settings, "SMTP_HOST", "")
        self.smtp_port = int(getattr(settings, "SMTP_PORT", 587))
        self.smtp_user = getattr(settings, "SMTP_USER", "")
        self.smtp_pass = getattr(settings, "SMTP_PASS", "")
        self.email_from = getattr(settings, "EMAIL_FROM", self.smtp_user)
        self.email_to = getattr(settings, "EMAIL_TO", "").split(",")

        # Telegram settings
        self.tg_token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
        self.tg_chat_id = getattr(settings, "TELEGRAM_CHAT_ID", "")

    def _enabled_email(self) -> bool:
        return all([self.smtp_host, self.smtp_user, self.smtp_pass, self.email_to])

    def _enabled_telegram(self) -> bool:
        return bool(self.tg_token and self.tg_chat_id)

    def format_message(self, report: WagonReport) -> str:
        duration = report.ended_at - report.started_at
        mins = int(duration.total_seconds() / 60)

        msg = f"""🚂 <b>Wagon Closed: {report.wagon_number}</b>

👤 Operator: {report.shift_operator}
🕒 Duration: {mins} min
📅 {report.ended_at.strftime('%Y-%m-%d %H:%M')}

📦 <b>Bags:</b> {report.total_bags}
   • 25 kg: {report.bags_25kg}
   • 50 kg: {report.bags_50kg}
   • Empty: {report.empty_bags}

⚖️ <b>Est. Weight:</b> {report.total_weight_kg} kg
📐 <b>Avg Volume:</b> {report.avg_volume_liters:.1f} L
"""
        return msg

    def send_email(self, report: WagonReport) -> bool:
        if not self._enabled_email():
            logger.debug("Email not configured, skipping.")
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[BagCounter] Wagon {report.wagon_number} Closed"
            msg["From"] = self.email_from
            msg["To"] = ", ".join(self.email_to)

            body = self.format_message(report)
            msg.attach(MIMEText(body, "plain", "utf-8"))
            msg.attach(MIMEText(body.replace("\n", "<br>"), "html", "utf-8"))

            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.sendmail(self.email_from, self.email_to, msg.as_string())

            logger.info(f"Email sent to {self.email_to}")
            return True
        except Exception as e:
            logger.error(f"Email send failed: {e}")
            return False

    def send_telegram(self, report: WagonReport) -> bool:
        if not self._enabled_telegram():
            logger.debug("Telegram not configured, skipping.")
            return False

        try:
            text = self.format_message(report)
            url = f"https://api.telegram.org/bot{self.tg_token}/sendMessage"
            payload = {
                "chat_id": self.tg_chat_id,
                "text": text,
                "parse_mode": "HTML",
            }
            resp = requests.post(url, json=payload, timeout=15)
            resp.raise_for_status()
            logger.info("Telegram notification sent.")
            return True
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    def notify_wagon_closed(self, report: WagonReport) -> None:
        self.send_email(report)
        self.send_telegram(report)


def build_report_from_wagon(wagon_id: int, db_session) -> Optional[WagonReport]:
    """Helper to construct WagonReport from DB records."""
    from src.db.models import Wagon, BagEvent, Shift

    wagon = db_session.query(Wagon).filter_by(id=wagon_id).first()
    if not wagon:
        return None
    shift = db_session.query(Shift).filter_by(id=wagon.shift_id).first()

    bags = db_session.query(BagEvent).filter_by(wagon_id=wagon_id).all()
    total = len(bags)
    b25 = sum(1 for b in bags if b.bag_class and b.bag_class.value == "25kg")
    b50 = sum(1 for b in bags if b.bag_class and b.bag_class.value == "50kg")
    bempty = sum(1 for b in bags if b.bag_class and b.bag_class.value == "empty")
    weight = b25 * 25 + b50 * 50
    avg_vol = statistics.mean([b.estimated_volume_liters for b in bags if b.estimated_volume_liters]) if bags else 0.0

    clips = [b.clip_path for b in bags if b.clip_path][:5]

    return WagonReport(
        wagon_number=wagon.wagon_number,
        shift_operator=shift.operator_name if shift else "unknown",
        started_at=wagon.started_at,
        ended_at=wagon.ended_at or datetime.now(timezone.utc),
        total_bags=total,
        bags_25kg=b25,
        bags_50kg=b50,
        empty_bags=bempty,
        total_weight_kg=weight,
        avg_volume_liters=round(avg_vol, 2),
        top_clip_paths=clips,
    )


import statistics
