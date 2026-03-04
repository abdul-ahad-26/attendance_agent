"""Playwright persistent browser context manager for MS Teams."""

import logging
import time
from pathlib import Path
from typing import Optional

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright

from . import selectors


logger = logging.getLogger("attendance_agent")

BROWSER_DATA_DIR = Path(__file__).resolve().parent.parent / "browser_data"
TEAMS_URL = "https://teams.microsoft.com/?web=1"

# URLs that indicate the user is on a login page (not yet authenticated)
LOGIN_URLS = ["login.microsoftonline.com", "login.live.com", "login.microsoft.com"]


class BrowserManager:
    """Manages a persistent Playwright browser context for Teams.

    Uses launch_persistent_context so the full browser profile (cookies,
    localStorage, IndexedDB, service workers) is saved between runs.
    After one manual login the session persists indefinitely.
    """

    def __init__(self, headless: bool = False, channel: str = "msedge"):
        self.headless = headless
        self.channel = channel
        self._playwright: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    @property
    def page(self) -> Page:
        if self._page is None or self._page.is_closed():
            raise RuntimeError("Browser page not available. Call start() first.")
        return self._page

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError("Browser context not available. Call start() first.")
        return self._context

    def start(self) -> Page:
        """Launch (or reconnect to) the persistent browser context."""
        BROWSER_DATA_DIR.mkdir(exist_ok=True)

        logger.info("Launching browser (channel=%s, headless=%s)...", self.channel, self.headless)
        self._playwright = sync_playwright().start()

        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_DATA_DIR),
            channel=self.channel,
            headless=self.headless,
            args=[
                "--use-fake-ui-for-media-stream",
                "--disable-notifications",
                "--disable-popup-blocking",
                "--auto-select-desktop-capture-source=Entire screen",
            ],
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )

        # Use existing page or open a new one
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = self._context.new_page()

        logger.info("Browser started.")
        return self._page

    def navigate_to_teams(self) -> None:
        """Navigate to Teams web app and wait for redirects to settle."""
        page = self.page
        current = page.url
        if "teams.microsoft.com" not in current:
            logger.info("Navigating to Teams...")
            page.goto(TEAMS_URL, wait_until="domcontentloaded", timeout=60_000)

        # Wait for redirects to settle (Teams may redirect through login)
        # Poll URL for up to 30s until it stabilizes on teams.microsoft.com
        logger.info("Waiting for Teams to load (current URL: %s)...", page.url)
        for _ in range(15):
            page.wait_for_timeout(2_000)
            url = page.url
            logger.debug("Current URL: %s", url)
            on_login = any(lurl in url for lurl in LOGIN_URLS)
            if "teams.microsoft.com" in url and not on_login:
                logger.info("Teams loaded. URL: %s", url)
                return
        logger.warning("Teams may not have fully loaded. URL: %s", page.url)

    def is_logged_in(self) -> bool:
        """Check if the user is currently logged in to Teams.

        Uses URL-based detection: if we're on teams.microsoft.com and NOT
        being redirected to a login page, we're logged in.
        Also tries UI selectors as a secondary check.
        """
        page = self.page
        url = page.url

        logger.info("Checking login status. Current URL: %s", url)

        # If we're on a login page, definitely not logged in
        for login_url in LOGIN_URLS:
            if login_url in url:
                logger.warning("On login page: %s", url)
                return False

        # If we're on teams.microsoft.com, we're likely logged in
        if "teams.microsoft.com" in url:
            # Double-check: try to find any Teams UI element
            for selector in selectors.LOGGED_IN_INDICATOR:
                try:
                    if page.locator(selector).first.is_visible(timeout=5_000):
                        return True
                except Exception:
                    continue
            # Even if selectors didn't match, URL says we're on Teams
            # (selectors may be outdated but session is valid)
            logger.info("On Teams URL but no UI selector matched - assuming logged in.")
            return True

        return False

    def wait_for_login(self, timeout_seconds: int = 300) -> bool:
        """Poll until the user completes manual login.

        Checks every 3 seconds if the URL has moved from a login page
        to teams.microsoft.com.

        Args:
            timeout_seconds: Max wait time in seconds (default 5 minutes).

        Returns:
            True if login detected, False on timeout.
        """
        page = self.page
        logger.info("Waiting for login (up to %ds)...", timeout_seconds)

        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            url = page.url

            # Check if we've landed on Teams (not a login page)
            on_login_page = any(lurl in url for lurl in LOGIN_URLS)
            if "teams.microsoft.com" in url and not on_login_page:
                logger.info("Login detected! URL: %s", url)
                # Give the app a moment to load
                page.wait_for_timeout(3_000)
                return True

            time.sleep(3)

        logger.warning("Login not detected within %ds.", timeout_seconds)
        return False

    def open_pause_inspector(self) -> None:
        """Open Playwright Inspector for discovering selectors.

        This pauses the page so you can use the Playwright Inspector
        to find real CSS selectors, data-tid attributes, etc.
        """
        logger.info("Opening Playwright Inspector. Use it to find selectors.")
        logger.info("Press the Resume button in the Inspector to continue.")
        self.page.pause()

    def close(self) -> None:
        """Close browser context and playwright."""
        if self._context:
            try:
                self._context.close()
            except Exception:
                pass
            self._context = None
            self._page = None

        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

        logger.info("Browser closed.")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.close()
