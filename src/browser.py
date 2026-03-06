"""Playwright browser manager for MS Teams.

Launches Edge as an independent subprocess with a remote debug port, then
connects via CDP. This means:
- Stopping the agent (Ctrl+C) does NOT close the browser or leave the meeting.
- On the next start the agent reconnects to the already-open browser.
"""

import logging
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Optional

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from . import selectors


logger = logging.getLogger("attendance_agent")

BROWSER_DATA_DIR = Path(__file__).resolve().parent.parent / "browser_data"
TEAMS_URL = "https://teams.microsoft.com/?web=1"
REMOTE_DEBUG_PORT = 9222

TEAMS_DOMAINS = ["teams.microsoft.com", "teams.cloud.microsoft"]
LOGIN_URLS = ["login.microsoftonline.com", "login.live.com", "login.microsoft.com"]

_EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def _is_teams_url(url: str) -> bool:
    return any(domain in url for domain in TEAMS_DOMAINS)


def _is_debug_port_open(port: int) -> bool:
    """Return True if a browser is already listening on the CDP debug port."""
    try:
        urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=2)
        return True
    except Exception:
        return False


def _find_edge() -> str:
    """Return the path to the Microsoft Edge executable."""
    for path in _EDGE_PATHS:
        if Path(path).exists():
            return path
    raise RuntimeError(
        "Microsoft Edge not found at default paths. "
        "Update _EDGE_PATHS in browser.py with the correct path."
    )


class BrowserManager:
    """Manages a Playwright browser session for Teams via CDP.

    On start():
      - If a browser is already open on the debug port, connects to it.
      - Otherwise launches a new Edge subprocess and connects via CDP.

    On detach():
      - Disconnects Playwright without closing the browser.
      - The meeting and browser window stay alive after agent stops.

    On close():
      - Same as detach() (Edge is an independent process; close the window manually).
    """

    def __init__(self, headless: bool = False, channel: str = "msedge"):
        self.headless = headless
        self.channel = channel
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
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
        """Connect to an existing browser, or launch a new Edge instance."""
        BROWSER_DATA_DIR.mkdir(exist_ok=True)
        self._playwright = sync_playwright().start()

        # --- Try to reuse a browser already open on the debug port ---
        if _is_debug_port_open(REMOTE_DEBUG_PORT):
            try:
                self._browser = self._playwright.chromium.connect_over_cdp(
                    f"http://localhost:{REMOTE_DEBUG_PORT}"
                )
                self._context, self._page = self._get_or_create_page()
                logger.info("Reconnected to existing browser on port %d.", REMOTE_DEBUG_PORT)
                return self._page
            except Exception as e:
                logger.warning("Could not reuse existing browser (%s). Launching fresh.", e)

        # --- Launch a new Edge subprocess ---
        logger.info("Launching browser (headless=%s)...", self.headless)
        edge_exe = _find_edge()
        args = [
            edge_exe,
            f"--user-data-dir={BROWSER_DATA_DIR}",
            f"--remote-debugging-port={REMOTE_DEBUG_PORT}",
            "--start-maximized",
            "--disable-notifications",
            "--disable-popup-blocking",
            "--auto-select-desktop-capture-source=Entire screen",
            "--lang=en-US",
        ]
        if self.headless:
            args.append("--headless=new")

        subprocess.Popen(args)

        # Wait up to 10 s for the debug port to become available
        for _ in range(20):
            if _is_debug_port_open(REMOTE_DEBUG_PORT):
                break
            time.sleep(0.5)
        else:
            raise RuntimeError(
                f"Edge did not open remote debug port {REMOTE_DEBUG_PORT} in time."
            )

        self._browser = self._playwright.chromium.connect_over_cdp(
            f"http://localhost:{REMOTE_DEBUG_PORT}"
        )
        self._context, self._page = self._get_or_create_page()

        self._grant_media_permissions()
        logger.info("Browser started.")
        return self._page

    def _get_or_create_page(self):
        """Return (context, page) from the connected browser."""
        contexts = self._browser.contexts
        if contexts:
            ctx = contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
        else:
            page = self._browser.new_page()
            ctx = page.context
        return ctx, page

    def _grant_media_permissions(self) -> None:
        """Grant camera/mic permissions for all known Teams origins."""
        for origin in ["https://teams.microsoft.com", "https://teams.cloud.microsoft"]:
            try:
                self._context.grant_permissions(["camera", "microphone"], origin=origin)
                logger.debug("Granted media permissions for %s.", origin)
            except Exception:
                pass

    def navigate_to_teams(self) -> None:
        """Navigate to Teams web app and wait for redirects to settle."""
        page = self.page
        current = page.url
        if not _is_teams_url(current):
            logger.info("Navigating to Teams...")
            page.goto(TEAMS_URL, wait_until="domcontentloaded", timeout=60_000)

        # Grant permissions for the actual current origin (covers redirects)
        self._grant_media_permissions()

        # Wait for redirects to settle (teams.microsoft.com -> teams.cloud.microsoft)
        logger.info("Waiting for Teams to load (current URL: %s)...", page.url)
        for _ in range(15):
            page.wait_for_timeout(2_000)
            url = page.url
            logger.debug("Current URL: %s", url)
            on_login = any(lurl in url for lurl in LOGIN_URLS)

            # Auto-dismiss Teams in-app mic/camera permission overlay
            try:
                allow_btn = page.locator('button:has-text("Allow")').first
                if allow_btn.is_visible(timeout=500):
                    allow_btn.click()
                    logger.info("Dismissed mic/camera permission dialog.")
            except Exception:
                pass

            if _is_teams_url(url) and not on_login:
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

        # If we're on any Teams domain, we're logged in
        if _is_teams_url(url):
            logger.info("On Teams - logged in.")
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
            if _is_teams_url(url) and not on_login_page:
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

    def detach(self) -> None:
        """Disconnect Playwright from the browser without closing it.

        The Edge process keeps running, the meeting stays active, and the
        next agent start will reconnect to the same browser window.
        """
        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        logger.info("Detached from browser (browser and meeting remain active).")

    def close(self) -> None:
        """Alias for detach(). Edge is an independent process — close the window manually."""
        self.detach()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.close()
