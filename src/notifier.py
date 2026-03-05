"""Desktop toast notifications and optional Discord webhook alerts."""

import json
import logging
import urllib.request
from typing import Optional

from .config_loader import NotificationSettings


logger = logging.getLogger("attendance_agent")


def send_desktop_toast(title: str, message: str) -> None:
    """Show a desktop notification using plyer."""
    try:
        from plyer import notification

        notification.notify(
            title=title,
            message=message,
            app_name="Teams Attendance Agent",
            timeout=10,
        )
    except Exception as e:
        logger.debug("Desktop notification failed: %s", e)


def send_discord_webhook(webhook_url: str, title: str, message: str) -> None:
    """Send a message to a Discord channel via webhook."""
    if not webhook_url:
        return

    payload = {
        "embeds": [
            {
                "title": title,
                "description": message,
                "color": 0x7289DA,
            }
        ]
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
        logger.debug("Discord notification sent.")
    except Exception as e:
        logger.debug("Discord notification failed: %s", e)


class Notifier:
    """Sends notifications through configured channels."""

    def __init__(self, settings: NotificationSettings):
        self.settings = settings

    def notify(self, title: str, message: str) -> None:
        """Send notification through all enabled channels."""
        logger.info("[NOTIFY] %s: %s", title, message)

        if self.settings.desktop_toast:
            send_desktop_toast(title, message)

        if self.settings.discord_webhook_url:
            send_discord_webhook(self.settings.discord_webhook_url, title, message)

    def join_success(self, class_name: str, stay_minutes: int = 0) -> None:
        msg = f"Successfully joined: {class_name}"
        if stay_minutes > 0:
            msg += f" (staying ~{stay_minutes} min)"
        self.notify("Joined Class", msg)

    def join_failed(self, class_name: str, reason: str = "") -> None:
        detail = f" ({reason})" if reason else ""
        self.notify("Join Failed", f"Could not join: {class_name}{detail}")

    def meeting_not_found(self, class_name: str) -> None:
        self.notify("No Meeting Found", f"No active meeting for: {class_name}. Class may be cancelled.")

    def meeting_left(self, class_name: str) -> None:
        self.notify("Class Ended", f"Left meeting: {class_name}")

    def browser_crashed(self, class_name: str) -> None:
        self.notify("Browser Crashed", f"Lost connection during: {class_name}. Will retry next class.")

    def session_expired(self) -> None:
        self.notify("Session Expired", "Teams login expired. Run --login to re-authenticate.")
