"""Load and validate the YAML configuration file."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import yaml


VALID_DAYS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}


@dataclass
class ClassEntry:
    name: str
    day: str
    time: str
    duration_minutes: int
    team: str
    channel: str


@dataclass
class BrowserSettings:
    headless: bool = False
    channel: str = "msedge"


@dataclass
class NotificationSettings:
    desktop_toast: bool = True
    discord_webhook_url: str = ""


@dataclass
class Settings:
    join_early_minutes: int = 3
    stay_extra_minutes: int = 5
    max_wait_for_meeting: int = 15
    poll_interval_seconds: int = 15
    retry_join_attempts: int = 3
    browser: BrowserSettings = field(default_factory=BrowserSettings)
    notifications: NotificationSettings = field(default_factory=NotificationSettings)


@dataclass
class Config:
    email: str
    timetable: List[ClassEntry]
    settings: Settings


def _parse_time(time_str: str) -> tuple:
    """Validate HH:MM format and return (hour, minute)."""
    parts = time_str.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time format '{time_str}', expected HH:MM")
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Time out of range: {time_str}")
    return hour, minute


def _validate_class(entry: dict, index: int) -> ClassEntry:
    """Validate a single timetable entry."""
    required = ["name", "day", "time", "duration_minutes", "team", "channel"]
    for key in required:
        if key not in entry:
            raise ValueError(f"Timetable entry #{index + 1} missing required field: '{key}'")

    day = entry["day"].strip().lower()
    if day not in VALID_DAYS:
        raise ValueError(f"Timetable entry '{entry['name']}': invalid day '{entry['day']}'")

    _parse_time(entry["time"])

    duration = entry["duration_minutes"]
    if not isinstance(duration, int) or duration <= 0:
        raise ValueError(f"Timetable entry '{entry['name']}': duration_minutes must be a positive integer")

    return ClassEntry(
        name=entry["name"],
        day=day,
        time=entry["time"].strip(),
        duration_minutes=duration,
        team=entry["team"].strip(),
        channel=entry["channel"].strip(),
    )


def load_config(config_path: str | Path | None = None) -> Config:
    """Load and validate config from YAML file.

    Args:
        config_path: Path to config file. Defaults to config/config.yaml
                     relative to the project root.
    """
    if config_path is None:
        config_path = Path(__file__).resolve().parent.parent / "config" / "config.yaml"
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(
            f"Config not found at {config_path}. "
            "Copy config/config.example.yaml to config/config.yaml and fill in your details."
        )

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError("Config file must be a YAML mapping")

    # Student
    student = raw.get("student", {})
    email = student.get("email", "")
    placeholders = {"your.email@university.edu", "23-AI-XX@students.duet.edu.pk"}
    if not email or email in placeholders:
        raise ValueError("Please set your email in config.yaml (change XX to your roll number)")

    # Timetable
    timetable_raw = raw.get("timetable", [])
    if not timetable_raw:
        raise ValueError("Timetable is empty. Add at least one class.")
    timetable = [_validate_class(entry, i) for i, entry in enumerate(timetable_raw)]

    # Settings
    settings_raw = raw.get("settings", {})
    browser_raw = settings_raw.get("browser", {})
    notif_raw = settings_raw.get("notifications", {})

    browser_settings = BrowserSettings(
        headless=browser_raw.get("headless", False),
        channel=browser_raw.get("channel", "msedge"),
    )
    notif_settings = NotificationSettings(
        desktop_toast=notif_raw.get("desktop_toast", True),
        discord_webhook_url=notif_raw.get("discord_webhook_url", ""),
    )
    settings = Settings(
        join_early_minutes=settings_raw.get("join_early_minutes", 3),
        stay_extra_minutes=settings_raw.get("stay_extra_minutes", 5),
        max_wait_for_meeting=settings_raw.get("max_wait_for_meeting", 15),
        poll_interval_seconds=settings_raw.get("poll_interval_seconds", 15),
        retry_join_attempts=settings_raw.get("retry_join_attempts", 3),
        browser=browser_settings,
        notifications=notif_settings,
    )

    return Config(email=email, timetable=timetable, settings=settings)
