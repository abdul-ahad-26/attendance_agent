"""Orchestrates the full meeting join lifecycle: navigate, poll, join, stay, leave."""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from .browser import BrowserManager
from .config_loader import ClassEntry, Settings
from .notifier import Notifier
from .teams_navigator import (
    navigate_to_channel,
    is_meeting_active,
    click_join_meeting,
    mute_mic,
    turn_off_camera,
    click_join_now,
    is_in_meeting,
    leave_meeting,
    close_extra_tabs,
)


logger = logging.getLogger("attendance_agent")


class MeetingJoiner:
    """Handles the complete join-stay-leave cycle for a single class."""

    def __init__(self, browser: BrowserManager, settings: Settings, notifier: Notifier):
        self.browser = browser
        self.settings = settings
        self.notifier = notifier

    def join_class(self, class_entry: ClassEntry, leave_by: Optional[datetime] = None) -> bool:
        """Execute the full join flow for a scheduled class.

        Args:
            class_entry: The class to join.
            leave_by: Hard deadline to leave (e.g., when next class starts).
                      If None, stays for full duration + extra minutes.

        Returns True if successfully joined and completed.
        """
        name = class_entry.name

        logger.info("=" * 60)
        logger.info("Starting join flow for: %s", name)
        logger.info("Team: %s | Channel: %s", class_entry.team, class_entry.channel)
        if leave_by:
            logger.info("Must leave by: %s (next class)", leave_by.strftime("%H:%M"))
        logger.info("=" * 60)

        # Check browser is alive
        if not self._is_browser_alive():
            logger.error("Browser is closed or crashed! Cannot join %s.", name)
            self.notifier.browser_crashed(name)
            return False

        page = self.browser.page

        # Step 1: Verify session
        try:
            self.browser.navigate_to_teams()
        except Exception as e:
            logger.error("Browser error navigating to Teams: %s", e)
            return False

        if not self.browser.is_logged_in():
            logger.error("Not logged in! Run --login to authenticate first.")
            self.notifier.session_expired()
            return False

        # Step 2: Navigate to channel
        if not self._navigate_with_retry(class_entry):
            logger.error("Failed to navigate to channel for %s.", name)
            return False

        # Step 3: Poll for active meeting
        if not self._poll_for_meeting(page, name):
            logger.warning("No meeting found for %s. Class may be cancelled.", name)
            self.notifier.meeting_not_found(name)
            return False

        # Step 4-6: Join the meeting
        if not self._attempt_join(page, name):
            logger.error("Failed to join meeting for %s.", name)
            self.notifier.join_failed(name, "Could not click join buttons")
            return False

        logger.info("Successfully joined: %s", name)

        # Step 7: Calculate how long to stay (stay exactly until class ends)
        now = datetime.now()
        class_start_hour, class_start_min = int(class_entry.time.split(":")[0]), int(class_entry.time.split(":")[1])
        class_end = now.replace(hour=class_start_hour, minute=class_start_min, second=0) + timedelta(
            minutes=class_entry.duration_minutes
        )

        # If there's a next class, leave before it starts (with 2 min buffer)
        if leave_by:
            hard_deadline = leave_by - timedelta(minutes=2)
            if hard_deadline < class_end:
                logger.info(
                    "Cutting stay short: next class at %s (leaving at %s instead of %s)",
                    leave_by.strftime("%H:%M"), hard_deadline.strftime("%H:%M"), class_end.strftime("%H:%M"),
                )
                class_end = hard_deadline

        stay_seconds = max(0, int((class_end - now).total_seconds()))
        stay_minutes = stay_seconds // 60

        # Notify: successfully joined
        self.notifier.join_success(name, stay_minutes)

        if stay_minutes > 0:
            self._stay_in_meeting(page, name, stay_seconds)
        else:
            logger.info("No time left to stay in %s, leaving immediately.", name)

        # Step 8: Leave
        self._leave(page, name)
        self.notifier.meeting_left(name)

        logger.info("Completed class: %s", name)
        return True

    def _is_browser_alive(self) -> bool:
        """Check if the browser page is still usable."""
        try:
            page = self.browser.page
            # Try a simple operation to verify the page is alive
            _ = page.url
            return True
        except Exception as e:
            logger.error("Browser check failed: %s", e)
            return False

    def _navigate_with_retry(self, class_entry: ClassEntry) -> bool:
        """Navigate to channel with retries."""
        page = self.browser.page
        for attempt in range(self.settings.retry_join_attempts):
            try:
                if navigate_to_channel(page, class_entry.team, class_entry.channel):
                    return True
            except Exception as e:
                logger.warning("Navigate error (attempt %d): %s", attempt + 1, e)
            logger.warning("Navigate attempt %d/%d failed, retrying...", attempt + 1, self.settings.retry_join_attempts)
            time.sleep(3)
        return False

    def _poll_for_meeting(self, page, class_name: str) -> bool:
        """Poll the channel for an active meeting."""
        max_polls = (self.settings.max_wait_for_meeting * 60) // self.settings.poll_interval_seconds
        logger.info(
            "Polling for meeting (every %ds, up to %d min)...",
            self.settings.poll_interval_seconds,
            self.settings.max_wait_for_meeting,
        )

        for i in range(max_polls):
            try:
                if is_meeting_active(page):
                    logger.info("Meeting detected for %s!", class_name)
                    return True
            except Exception as e:
                logger.warning("Error checking meeting: %s", e)

            elapsed = (i + 1) * self.settings.poll_interval_seconds
            remaining = (max_polls - i - 1) * self.settings.poll_interval_seconds
            if elapsed % 60 == 0:
                logger.info("No meeting yet for %s. Waited %ds, %ds remaining.", class_name, elapsed, remaining)
            time.sleep(self.settings.poll_interval_seconds)

        logger.warning("No meeting started for %s after %d minutes.", class_name, self.settings.max_wait_for_meeting)
        return False

    def _attempt_join(self, page, class_name: str) -> bool:
        """Click Join, configure media, click Join now."""
        for attempt in range(self.settings.retry_join_attempts):
            try:
                if not click_join_meeting(page):
                    logger.warning("Join button click failed (attempt %d).", attempt + 1)
                    time.sleep(3)
                    continue

                page.wait_for_timeout(3_000)

                mute_mic(page)
                turn_off_camera(page)

                page.wait_for_timeout(1_000)

                if not click_join_now(page):
                    logger.warning("'Join now' button click failed (attempt %d).", attempt + 1)
                    time.sleep(3)
                    continue

                page.wait_for_timeout(5_000)
                if is_in_meeting(page):
                    logger.info("In meeting. Ensuring mic is muted...")
                    page.keyboard.press("Control+Shift+m")
                    page.wait_for_timeout(500)
                    return True

                logger.warning("Join verification failed (attempt %d).", attempt + 1)
                time.sleep(3)

            except Exception as e:
                logger.warning("Join attempt %d error: %s", attempt + 1, e)
                time.sleep(3)

        return False

    def _stay_in_meeting(self, page, class_name: str, stay_seconds: int) -> None:
        """Stay in the meeting for the specified duration.

        Checks every minute if still connected. Handles browser crashes.
        """
        stay_minutes = stay_seconds // 60
        logger.info("Staying in meeting '%s' for ~%d minutes...", class_name, stay_minutes)
        check_interval = 60
        elapsed = 0

        while elapsed < stay_seconds:
            sleep_time = min(check_interval, stay_seconds - elapsed)
            time.sleep(sleep_time)
            elapsed += sleep_time

            # Check if browser/page is still alive
            try:
                still_in = is_in_meeting(page)
            except Exception as e:
                logger.error("Browser error while in meeting '%s': %s", class_name, e)
                logger.error("Browser may have crashed. Moving on.")
                self.notifier.browser_crashed(class_name)
                return

            if not still_in:
                logger.warning("Disconnected from meeting '%s' after %d minutes.", class_name, elapsed // 60)
                return

            remaining = (stay_seconds - elapsed) // 60
            if remaining > 0 and remaining % 10 == 0:
                logger.info("Still in '%s'. %d min remaining.", class_name, remaining)

        logger.info("Stay time complete for '%s'.", class_name)

    def _leave(self, page, class_name: str) -> None:
        """Leave the meeting."""
        try:
            if is_in_meeting(page):
                if leave_meeting(page):
                    logger.info("Left meeting: %s", class_name)
                else:
                    logger.warning("Could not click leave for %s. Meeting may have already ended.", class_name)
            else:
                logger.info("Already out of meeting: %s", class_name)
        except Exception as e:
            logger.error("Error leaving meeting '%s': %s", class_name, e)
