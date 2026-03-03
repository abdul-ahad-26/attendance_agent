"""APScheduler-based timetable scheduler."""

import logging
from typing import Callable, List

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from .config_loader import ClassEntry, Settings


logger = logging.getLogger("attendance_agent")

DAY_MAP = {
    "monday": "mon",
    "tuesday": "tue",
    "wednesday": "wed",
    "thursday": "thu",
    "friday": "fri",
    "saturday": "sat",
    "sunday": "sun",
}


def _compute_early_time(time_str: str, early_minutes: int) -> tuple:
    """Subtract early_minutes from HH:MM and return (hour, minute)."""
    hour, minute = int(time_str.split(":")[0]), int(time_str.split(":")[1])
    total_minutes = hour * 60 + minute - early_minutes
    if total_minutes < 0:
        total_minutes += 24 * 60  # Wrap around midnight
    return total_minutes // 60, total_minutes % 60


def build_scheduler(
    timetable: List[ClassEntry],
    settings: Settings,
    join_callback: Callable[[ClassEntry], None],
) -> BlockingScheduler:
    """Create an APScheduler with one CronTrigger job per class.

    Args:
        timetable: List of class entries from config.
        settings: App settings (for join_early_minutes, etc.).
        join_callback: Function called with (ClassEntry) when it's time to join.

    Returns:
        Configured BlockingScheduler (not yet started).
    """
    scheduler = BlockingScheduler()

    for entry in timetable:
        day_abbrev = DAY_MAP.get(entry.day)
        if not day_abbrev:
            logger.error("Invalid day '%s' for class '%s', skipping.", entry.day, entry.name)
            continue

        hour, minute = _compute_early_time(entry.time, settings.join_early_minutes)

        trigger = CronTrigger(
            day_of_week=day_abbrev,
            hour=hour,
            minute=minute,
            misfire_grace_time=300,  # 5 min grace if PC was asleep
        )

        scheduler.add_job(
            join_callback,
            trigger=trigger,
            args=[entry],
            id=f"class_{entry.name}_{entry.day}_{entry.time}",
            name=f"{entry.name} ({entry.day} {entry.time})",
            replace_existing=True,
        )

        logger.info(
            "Scheduled: %s -> %s %02d:%02d (class at %s, joining %d min early)",
            entry.name, day_abbrev.upper(), hour, minute, entry.time, settings.join_early_minutes,
        )

    return scheduler
