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
    """Try each selector and click the first visible match."""
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


def _click_last(page: Page, selector_list: list, timeout: int = 10_000, description: str = "") -> bool:
    """Try each selector and click the LAST visible match.

    Used for Join buttons — when multiple meetings show in a channel,
    the active/current meeting is the most recent one (last on page).
    """
    for sel in selector_list:
        try:
            all_matches = page.locator(sel)
            count = all_matches.count()
            if count == 0:
                continue

            # Click the last match (most recent = active meeting)
            loc = all_matches.nth(count - 1)
            loc.wait_for(state="visible", timeout=timeout)
            loc.click()
            logger.info("Clicked %s (selector: %s, match %d/%d)", description or sel, sel, count, count)
            return True
        except Exception:
            continue
    logger.warning("Could not click: %s", description or selector_list[0])
    return False


def close_extra_tabs(page: Page) -> None:
    """Close any extra tabs that Teams may have opened, keep only the first."""
    context = page.context
    while len(context.pages) > 1:
        extra = context.pages[-1]
        try:
            extra.close()
            logger.info("Closed extra tab.")
        except Exception:
            break


def dismiss_notification_popup(page: Page) -> None:
    """Dismiss the Teams notification popup (bottom-right) if present."""
    try:
        # The notification popup has a close/X button
        close_btn = page.locator('[data-tid="notification-close"]').first
        if close_btn.is_visible(timeout=1_000):
            close_btn.click()
            logger.info("Dismissed notification popup.")
    except Exception:
        pass


def navigate_to_channel(page: Page, team_name: str, channel_name: str) -> bool:
    """Navigate to a specific Team > Channel in the Teams UI."""
    logger.info("Navigating to %s > %s ...", team_name, channel_name)

    # Close extra tabs first
    close_extra_tabs(page)

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
    """Click the Join button on the ACTIVE meeting in the channel.

    Uses _click_last because when multiple meetings exist in a channel,
    the currently active one is the most recent (last on page).
    The old/scheduled meetings have grayed out Join buttons that do nothing.
    """
    # First try the notification popup Join button (most specific to active meeting)
    try:
        notif_join = page.locator('div:has-text("started the meeting") >> button:has-text("Join")').last
        if notif_join.is_visible(timeout=2_000):
            notif_join.click()
            logger.info("Clicked Join from notification popup.")
            return True
    except Exception:
        pass

    # Click the LAST Join button on the page (active meeting = most recent)
    return _click_last(page, selectors.MEETING_JOIN_BUTTON, timeout=10_000, description="Join meeting")


def mute_mic(page: Page) -> bool:
    """Ensure microphone is muted on the pre-join screen."""
    for sel in selectors.MIC_TOGGLE:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=3_000):
                aria = (loc.get_attribute("aria-label") or "").lower()
                logger.info("Found mic toggle (aria-label: '%s')", aria)
                if "unmute" in aria:
                    logger.info("Mic already muted.")
                    return True
                loc.click()
                logger.info("Muted microphone via button.")
                return True
        except Exception:
            continue

    logger.info("Mic toggle not found via selectors, using Ctrl+Shift+M shortcut.")
    page.keyboard.press("Control+Shift+m")
    page.wait_for_timeout(500)
    return True


def turn_off_camera(page: Page) -> bool:
    """Ensure camera is off on the pre-join screen."""
    for sel in selectors.CAMERA_TOGGLE:
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=3_000):
                aria = (loc.get_attribute("aria-label") or "").lower()
                logger.info("Found camera toggle (aria-label: '%s')", aria)
                if "turn on" in aria:
                    logger.info("Camera already off.")
                    return True
                loc.click()
                logger.info("Turned off camera via button.")
                return True
        except Exception:
            continue

    logger.info("Camera toggle not found via selectors, using Ctrl+Shift+O shortcut.")
    page.keyboard.press("Control+Shift+o")
    page.wait_for_timeout(500)
    return True


def click_join_now(page: Page) -> bool:
    """Click the 'Join now' button on the pre-join screen."""
    return _click_first(page, selectors.JOIN_NOW_BUTTON, timeout=15_000, description="Join now")


def is_in_meeting(page: Page) -> bool:
    """Check if we are currently inside a meeting."""
    return _find_first(page, selectors.IN_MEETING_INDICATOR, timeout=3_000) is not None


def leave_meeting(page: Page) -> bool:
    """Click the hangup/leave button to exit the meeting."""
    return _click_first(page, selectors.HANGUP_BUTTON, timeout=10_000, description="Leave meeting")
