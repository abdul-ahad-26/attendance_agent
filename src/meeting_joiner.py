"""Orchestrates the full meeting join lifecycle: navigate, poll, join, stay, leave."""

import logging
import time

from .browser import BrowserManager
from .config_loader import ClassEntry, Settings
from .teams_navigator import (
    navigate_to_channel,
    is_meeting_active,
    click_join_meeting,
    mute_mic,
    turn_off_camera,
    click_join_now,
    is_in_meeting,
    leave_meeting,
)
from .utils import retry


logger = logging.getLogger("attendance_agent")


class MeetingJoiner:
    """Handles the complete join-stay-leave cycle for a single class."""

    def __init__(self, browser: BrowserManager, settings: Settings):
        self.browser = browser
        self.settings = settings

    def join_class(self, class_entry: ClassEntry) -> bool:
        """Execute the full join flow for a scheduled class.

        Steps:
            1. Verify logged in
            2. Navigate to team > channel
            3. Poll for active meeting
            4. Click Join on banner
            5. Mute mic, turn off camera
            6. Click "Join now"
            7. Stay for class duration
            8. Leave meeting

        Returns True if successfully joined and completed.
        """
        page = self.browser.page
        name = class_entry.name

        logger.info("=" * 60)
        logger.info("Starting join flow for: %s", name)
        logger.info("Team: %s | Channel: %s", class_entry.team, class_entry.channel)
        logger.info("=" * 60)

        # Step 1: Verify session
        self.browser.navigate_to_teams()
        if not self.browser.is_logged_in():
            logger.error("Not logged in! Run --login to authenticate first.")
            return False

        # Step 2: Navigate to channel
        if not self._navigate_with_retry(class_entry):
            logger.error("Failed to navigate to channel for %s.", name)
            return False

        # Step 3: Poll for active meeting
        if not self._poll_for_meeting(page, name):
            logger.error("No meeting found for %s after polling.", name)
            return False

        # Step 4-6: Join the meeting
        if not self._attempt_join(page, name):
            logger.error("Failed to join meeting for %s.", name)
            return False

        logger.info("Successfully joined: %s", name)

        # Step 7: Stay in meeting
        stay_minutes = class_entry.duration_minutes + self.settings.stay_extra_minutes
        self._stay_in_meeting(page, name, stay_minutes)

        # Step 8: Leave
        self._leave(page, name)

        logger.info("Completed class: %s", name)
        return True

    def _navigate_with_retry(self, class_entry: ClassEntry) -> bool:
        """Navigate to channel with retries."""
        page = self.browser.page
        for attempt in range(self.settings.retry_join_attempts):
            if navigate_to_channel(page, class_entry.team, class_entry.channel):
                return True
            logger.warning("Navigate attempt %d/%d failed, retrying...", attempt + 1, self.settings.retry_join_attempts)
            time.sleep(3)
        return False

    def _poll_for_meeting(self, page, class_name: str) -> bool:
        """Poll the channel for an active meeting.

        Checks every poll_interval_seconds for up to max_wait_for_meeting minutes.
        """
        max_polls = (self.settings.max_wait_for_meeting * 60) // self.settings.poll_interval_seconds
        logger.info(
            "Polling for meeting in channel (every %ds, up to %d min)...",
            self.settings.poll_interval_seconds,
            self.settings.max_wait_for_meeting,
        )

        for i in range(max_polls):
            if is_meeting_active(page):
                logger.info("Meeting detected for %s!", class_name)
                return True

            remaining = (max_polls - i - 1) * self.settings.poll_interval_seconds
            logger.debug("No meeting yet. Next check in %ds (%ds remaining).", self.settings.poll_interval_seconds, remaining)
            time.sleep(self.settings.poll_interval_seconds)

        return False

    def _attempt_join(self, page, class_name: str) -> bool:
        """Click Join, configure media, click Join now."""
        for attempt in range(self.settings.retry_join_attempts):
            try:
                # Click Join on the meeting banner
                if not click_join_meeting(page):
                    logger.warning("Join button click failed (attempt %d).", attempt + 1)
                    time.sleep(3)
                    continue

                # Wait for pre-join screen to load
                page.wait_for_timeout(3_000)

                # Mute mic and turn off camera
                mute_mic(page)
                turn_off_camera(page)

                page.wait_for_timeout(1_000)

                # Click "Join now"
                if not click_join_now(page):
                    logger.warning("'Join now' button click failed (attempt %d).", attempt + 1)
                    time.sleep(3)
                    continue

                # Wait and verify we're in the meeting
                page.wait_for_timeout(5_000)
                if is_in_meeting(page):
                    return True

                logger.warning("Join verification failed (attempt %d).", attempt + 1)
                time.sleep(3)

            except Exception as e:
                logger.warning("Join attempt %d error: %s", attempt + 1, e)
                time.sleep(3)

        return False

    def _stay_in_meeting(self, page, class_name: str, duration_minutes: int) -> None:
        """Stay in the meeting for the specified duration.

        Periodically checks if we're still connected. If disconnected early,
        logs a warning and returns.
        """
        logger.info("Staying in meeting '%s' for %d minutes...", class_name, duration_minutes)
        check_interval = 60  # Check every minute
        total_seconds = duration_minutes * 60
        elapsed = 0

        while elapsed < total_seconds:
            time.sleep(min(check_interval, total_seconds - elapsed))
            elapsed += check_interval

            if not is_in_meeting(page):
                logger.warning("Disconnected from meeting '%s' after %d minutes.", class_name, elapsed // 60)
                return

            remaining = (total_seconds - elapsed) // 60
            if remaining > 0 and remaining % 10 == 0:
                logger.info("Still in meeting '%s'. %d minutes remaining.", class_name, remaining)

    def _leave(self, page, class_name: str) -> None:
        """Leave the meeting."""
        if is_in_meeting(page):
            if leave_meeting(page):
                logger.info("Left meeting: %s", class_name)
            else:
                logger.warning("Could not click leave for %s. Meeting may have already ended.", class_name)
        else:
            logger.info("Already out of meeting: %s", class_name)
