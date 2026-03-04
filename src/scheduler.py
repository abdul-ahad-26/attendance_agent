"""Simple main-thread timetable scheduler.

Runs everything in one thread (required for Playwright) and prints
live status so the user knows the agent is alive.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Callable, List, Optional

from .config_loader import ClassEntry, Settings


logger = logging.getLogger("attendance_agent")

DAY_MAP = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _get_class_start(entry: ClassEntry, now: datetime) -> Optional[datetime]:
    """Get today's class start time, or None if not today."""
    day_num = DAY_MAP[entry.day]
    if now.weekday() != day_num:
        return None
    hour, minute = int(entry.time.split(":")[0]), int(entry.time.split(":")[1])
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _get_class_end(entry: ClassEntry, now: datetime) -> Optional[datetime]:
    """Get today's class end time, or None if not today."""
    start = _get_class_start(entry, now)
    if start is None:
        return None
    return start + timedelta(minutes=entry.duration_minutes)


def _next_occurrence(entry: ClassEntry, early_minutes: int, now: datetime) -> datetime:
    """Calculate the next datetime this class should be joined."""
    day_num = DAY_MAP[entry.day]
    hour, minute = int(entry.time.split(":")[0]), int(entry.time.split(":")[1])

    # Subtract early_minutes for the join trigger time
    total_minutes = hour * 60 + minute - early_minutes
    if total_minutes < 0:
        total_minutes += 24 * 60
    join_hour, join_minute = total_minutes // 60, total_minutes % 60

    days_ahead = day_num - now.weekday()
    if days_ahead < 0:
        days_ahead += 7

    target = now.replace(hour=join_hour, minute=join_minute, second=0, microsecond=0) + timedelta(days=days_ahead)

    if target <= now:
        # Check if class is still ongoing today — if so, don't skip to next week
        class_end = _get_class_end(entry, now)
        if class_end and now < class_end:
            # Class is still running, return the join time (even though it's in the past)
            return target
        target += timedelta(weeks=1)

    return target


def find_next_class(timetable: List[ClassEntry], early_minutes: int, now: datetime) -> Optional[tuple]:
    """Find the next class to join (or currently ongoing class).

    Returns (ClassEntry, next_join_datetime) or None if timetable is empty.
    """
    if not timetable:
        return None

    best_entry = None
    best_time = None

    # First priority: any class that is currently ongoing and not yet joined
    for entry in timetable:
        class_start = _get_class_start(entry, now)
        class_end = _get_class_end(entry, now)
        if class_start and class_end and class_start <= now <= class_end:
            # This class is happening right now
            return entry, class_start

    # Otherwise find the next upcoming class
    for entry in timetable:
        next_time = _next_occurrence(entry, early_minutes, now)
        if next_time > now and (best_time is None or next_time < best_time):
            best_time = next_time
            best_entry = entry

    if best_entry:
        return best_entry, best_time
    return None


def is_class_joinable(entry: ClassEntry, early_minutes: int, now: datetime) -> bool:
    """Check if a class should be joined right now.

    Returns True if:
    - It's the right day, AND
    - Current time is between (class_start - early_minutes) and class_end

    This means: if the agent starts mid-class, it will still join.
    """
    class_start = _get_class_start(entry, now)
    if class_start is None:
        return False

    join_time = class_start - timedelta(minutes=early_minutes)
    class_end = class_start + timedelta(minutes=entry.duration_minutes)

    return join_time <= now <= class_end


def run_scheduler(
    timetable: List[ClassEntry],
    settings: Settings,
    join_callback: Callable[[ClassEntry], None],
) -> None:
    """Run the scheduler loop in the main thread.

    Checks every 30 seconds if a class should be joined. All Playwright
    operations happen in this same thread, avoiding threading issues.

    On startup, immediately detects any ongoing class and joins it.
    """
    early = settings.join_early_minutes
    joined_today = set()  # Track (class_name, date) to avoid double-joining

    logger.info("Scheduler running. Checking every 30 seconds.")

    # Check if any class is happening RIGHT NOW on startup
    now = datetime.now()
    for entry in timetable:
        if is_class_joinable(entry, early, now):
            class_end = _get_class_end(entry, now)
            remaining = int((class_end - now).total_seconds() // 60) if class_end else 0
            logger.info(">>> Class in progress: %s (%d min remaining). Joining now!", entry.name, remaining)
            joined_today.add((entry.name, now.strftime("%Y-%m-%d")))
            try:
                join_callback(entry)
            except Exception as e:
                logger.exception("Error joining %s: %s", entry.name, e)

    # Show what's coming up next
    now = datetime.now()
    result = find_next_class(timetable, early, now)
    if result:
        next_entry, next_time = result
        if next_time > now:
            time_until = next_time - now
            hours, remainder = divmod(int(time_until.total_seconds()), 3600)
            minutes = remainder // 60
            logger.info(
                "Next class: %s at %s (%dh %dm from now)",
                next_entry.name, next_time.strftime("%a %H:%M"), hours, minutes,
            )
        else:
            logger.info("Next class: %s (now)", next_entry.name)

    last_status_log = time.time()

    while True:
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        for entry in timetable:
            key = (entry.name, today_str)
            if key in joined_today:
                continue

            if is_class_joinable(entry, early, now):
                logger.info(">>> Time to join: %s", entry.name)
                joined_today.add(key)
                try:
                    join_callback(entry)
                except Exception as e:
                    logger.exception("Error joining %s: %s", entry.name, e)

        # Clean up old dates from joined_today
        joined_today = {(n, d) for n, d in joined_today if d == today_str}

        # Log status every 5 minutes so user knows it's alive
        if time.time() - last_status_log >= 300:
            result = find_next_class(timetable, early, now)
            if result:
                next_entry, next_time = result
                if next_time > now:
                    time_until = next_time - now
                    hours, remainder = divmod(int(time_until.total_seconds()), 3600)
                    minutes = remainder // 60
                    logger.info(
                        "Waiting... Next: %s at %s (%dh %dm)",
                        next_entry.name, next_time.strftime("%a %H:%M"), hours, minutes,
                    )
                else:
                    logger.info("Ongoing: %s", next_entry.name)
            last_status_log = time.time()

        time.sleep(30)
