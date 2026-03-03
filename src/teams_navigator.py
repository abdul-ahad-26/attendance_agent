"""Teams UI interactions: navigate to team/channel, detect meeting, join, mute, leave."""

import logging
from typing import Optional

from playwright.sync_api import Page, Locator

from . import selectors


logger = logging.getLogger("attendance_agent")


def _find_first(page: Page, selector_list: list, timeout: int = 5_000) -> Optional[Locator]:
    """Try each selector in the list and return the first visible match."""
    for sel in selector_list:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=timeout):
                return loc
        except Exception:
            continue
    return None


def _click_first(page: Page, selector_list: list, timeout: int = 10_000, description: str = "") -> bool:
    """Try each selector and click the first visible match.

    Returns True if a click succeeded.
    """
    for sel in selector_list:
        try:
            loc = page.locator(sel).first
            loc.wait_for(state="visible", timeout=timeout)
            loc.click()
            logger.info("Clicked %s (selector: %s)", description or sel, sel)
            return True
        except Exception:
            continue
    logger.warning("Could not click: %s", description or selector_list[0])
    return False


def navigate_to_channel(page: Page, team_name: str, channel_name: str) -> bool:
    """Navigate to a specific Team > Channel in the Teams UI.

    Returns True if the channel view is reached.
    """
    logger.info("Navigating to %s > %s ...", team_name, channel_name)

    # Step 1: Click Teams in the app bar
    if not _click_first(page, selectors.TEAMS_APP_BAR_TEAMS_BUTTON, description="Teams tab"):
        return False
    page.wait_for_timeout(2_000)

    # Step 2: Find and click the team
    team_sels = selectors.team_item(team_name)
    if not _click_first(page, team_sels, timeout=10_000, description=f"Team '{team_name}'"):
        logger.error("Team '%s' not found in the list.", team_name)
        return False
    page.wait_for_timeout(1_500)

    # Step 3: Find and click the channel
    channel_sels = selectors.channel_item(channel_name)
    if not _click_first(page, channel_sels, timeout=10_000, description=f"Channel '{channel_name}'"):
        logger.error("Channel '%s' not found under team '%s'.", channel_name, team_name)
        return False
    page.wait_for_timeout(2_000)

    logger.info("Reached channel: %s > %s", team_name, channel_name)
    return True


def is_meeting_active(page: Page) -> bool:
    """Check if there is an active meeting in the current channel."""
    return _find_first(page, selectors.ACTIVE_MEETING_INDICATOR, timeout=3_000) is not None


def click_join_meeting(page: Page) -> bool:
    """Click the Join button on the meeting banner in the channel."""
    return _click_first(page, selectors.MEETING_JOIN_BUTTON, timeout=10_000, description="Join meeting")


def mute_mic(page: Page) -> bool:
    """Ensure microphone is muted on the pre-join screen.

    Clicks the mic toggle. Teams defaults to mic ON, so one click mutes it.
    If the mic is already showing as muted, we skip.
    """
    for sel in selectors.MIC_TOGGLE:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=5_000):
                aria = loc.get_attribute("aria-label") or ""
                aria_pressed = loc.get_attribute("aria-pressed")
                # If aria-label says "Unmute" or aria-pressed is "false", mic is already muted
                if "unmute" in aria.lower() or aria_pressed == "false":
                    logger.info("Mic already muted.")
                    return True
                loc.click()
                logger.info("Muted microphone.")
                return True
        except Exception:
            continue
    logger.warning("Could not find mic toggle.")
    return False


def turn_off_camera(page: Page) -> bool:
    """Ensure camera is off on the pre-join screen."""
    for sel in selectors.CAMERA_TOGGLE:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=5_000):
                aria = loc.get_attribute("aria-label") or ""
                aria_pressed = loc.get_attribute("aria-pressed")
                if "turn on" in aria.lower() or aria_pressed == "false":
                    logger.info("Camera already off.")
                    return True
                loc.click()
                logger.info("Turned off camera.")
                return True
        except Exception:
            continue
    logger.warning("Could not find camera toggle.")
    return False


def click_join_now(page: Page) -> bool:
    """Click the 'Join now' button on the pre-join screen."""
    return _click_first(page, selectors.JOIN_NOW_BUTTON, timeout=15_000, description="Join now")


def is_in_meeting(page: Page) -> bool:
    """Check if we are currently inside a meeting."""
    return _find_first(page, selectors.IN_MEETING_INDICATOR, timeout=3_000) is not None


def leave_meeting(page: Page) -> bool:
    """Click the hangup/leave button to exit the meeting."""
    return _click_first(page, selectors.HANGUP_BUTTON, timeout=10_000, description="Leave meeting")
