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


def get_todays_classes(timetable: List[ClassEntry], now: datetime) -> List[ClassEntry]:
    """Return today's classes sorted by start time."""
    today_num = now.weekday()
    today_classes = [e for e in timetable if DAY_MAP.get(e.day) == today_num]
    today_classes.sort(key=lambda e: e.time)
    return today_classes


def get_next_class_start(entry: ClassEntry, timetable: List[ClassEntry], now: datetime) -> Optional[datetime]:
    """Get the start time of the class that comes AFTER the given entry today."""
    today_classes = get_todays_classes(timetable, now)

    found_current = False
    for cls in today_classes:
        if cls.name == entry.name and cls.time == entry.time:
            found_current = True
            continue
        if found_current:
            start = _get_class_start(cls, now)
            if start:
                return start
    return None


def _next_occurrence(entry: ClassEntry, early_minutes: int, now: datetime) -> datetime:
    """Calculate the next datetime this class should be joined."""
    day_num = DAY_MAP[entry.day]
    hour, minute = int(entry.time.split(":")[0]), int(entry.time.split(":")[1])

    total_minutes = hour * 60 + minute - early_minutes
    if total_minutes < 0:
        total_minutes += 24 * 60
    join_hour, join_minute = total_minutes // 60, total_minutes % 60

    days_ahead = day_num - now.weekday()
    if days_ahead < 0:
        days_ahead += 7

    target = now.replace(hour=join_hour, minute=join_minute, second=0, microsecond=0) + timedelta(days=days_ahead)

    if target <= now:
        class_end = _get_class_end(entry, now)
        if class_end and now < class_end:
            return target
        target += timedelta(weeks=1)

    return target


def find_next_class(timetable: List[ClassEntry], early_minutes: int, now: datetime) -> Optional[tuple]:
    """Find the next class to join (or currently ongoing class).

    Returns (ClassEntry, next_join_datetime) or None.
    """
    if not timetable:
        return None

    best_entry = None
    best_time = None

    for entry in timetable:
        class_start = _get_class_start(entry, now)
        class_end = _get_class_end(entry, now)
        if class_start and class_end and class_start <= now <= class_end:
            return entry, class_start

    for entry in timetable:
        next_time = _next_occurrence(entry, early_minutes, now)
        if next_time > now and (best_time is None or next_time < best_time):
            best_time = next_time
            best_entry = entry

    if best_entry:
        return best_entry, best_time
    return None


def is_class_joinable(entry: ClassEntry, early_minutes: int, now: datetime) -> bool:
    """Check if a class should be joined right now."""
    class_start = _get_class_start(entry, now)
    if class_start is None:
        return False

    join_time = class_start - timedelta(minutes=early_minutes)
    class_end = class_start + timedelta(minutes=entry.duration_minutes)

    return join_time <= now <= class_end


def _log_time_until(label: str, entry: ClassEntry, target: datetime, now: datetime) -> None:
    """Log how long until a class fires."""
    if target > now:
        time_until = target - now
        hours, remainder = divmod(int(time_until.total_seconds()), 3600)
        minutes = remainder // 60
        logger.info("%s: %s at %s (%dh %dm from now)", label, entry.name, target.strftime("%a %H:%M"), hours, minutes)
    else:
        logger.info("%s: %s (now)", label, entry.name)


def run_scheduler(
    timetable: List[ClassEntry],
    settings: Settings,
    join_callback: Callable[[ClassEntry, Optional[datetime]], None],
) -> None:
    """Run the scheduler loop in the main thread.

    The join_callback receives (ClassEntry, leave_by_datetime_or_None).
    """
    early = settings.join_early_minutes
    joined_today = set()

    logger.info("Scheduler running. Checking every 30 seconds.")

    # On startup: join any class that is currently in progress
    now = datetime.now()
    for entry in get_todays_classes(timetable, now):
        if is_class_joinable(entry, early, now):
            key = (entry.name, now.strftime("%Y-%m-%d"))
            if key in joined_today:
                continue

            class_end = _get_class_end(entry, now)
            remaining = int((class_end - now).total_seconds() // 60) if class_end else 0
            logger.info(">>> Class in progress: %s (%d min remaining). Joining now!", entry.name, remaining)
            joined_today.add(key)

            next_start = get_next_class_start(entry, timetable, now)
            try:
                join_callback(entry, next_start)
            except Exception as e:
                logger.exception("Error joining %s: %s", entry.name, e)

    # Show what's coming up
    now = datetime.now()
    result = find_next_class(timetable, early, now)
    if result:
        next_entry, next_time = result
        _log_time_until("Next class", next_entry, next_time, now)

    last_status_log = time.time()

    while True:
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        for entry in get_todays_classes(timetable, now):
            key = (entry.name, today_str)
            if key in joined_today:
                continue

            if is_class_joinable(entry, early, now):
                logger.info(">>> Time to join: %s", entry.name)
                joined_today.add(key)

                # Find when the NEXT class starts (so we leave in time)
                next_start = get_next_class_start(entry, timetable, now)
                if next_start:
                    logger.info("Next class after this: %s", next_start.strftime("%H:%M"))

                try:
                    join_callback(entry, next_start)
                except Exception as e:
                    logger.exception("Error joining %s: %s", entry.name, e)

        # Clean up old dates
        joined_today = {(n, d) for n, d in joined_today if d == today_str}

        # Status log every 5 minutes
        if time.time() - last_status_log >= 300:
            result = find_next_class(timetable, early, now)
            if result:
                next_entry, next_time = result
                _log_time_until("Waiting... Next", next_entry, next_time, now)
            else:
                logger.info("No more classes today.")
            last_status_log = time.time()

        time.sleep(30)
