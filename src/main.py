"""Entry point for the MS Teams Auto-Join Attendance Agent.

Usage:
    python -m src.main              # Start the scheduler (normal operation)
    python -m src.main --login      # One-time manual login to save session
    python -m src.main --join-now "Class Name"  # Immediately join a specific class
"""

import argparse
import logging
import signal
import sys

from .browser import BrowserManager
from .config_loader import ClassEntry, Config, load_config
from .meeting_joiner import MeetingJoiner
from .notifier import Notifier
from .scheduler import run_scheduler
from .utils import setup_logging


logger = logging.getLogger("attendance_agent")


def mode_login(config: Config) -> None:
    """Open the browser for manual Teams login. Session is saved automatically."""
    browser = BrowserManager(
        headless=False,  # Must be visible for manual login
        channel=config.settings.browser.channel,
    )

    try:
        browser.start()
        browser.navigate_to_teams()

        if browser.is_logged_in():
            logger.info("Already logged in! Session is saved.")
            logger.info("You can now close this and run the agent normally.")
            input("Press Enter to close the browser...")
        else:
            logger.info("Please log in to Teams in the browser window.")
            logger.info("The session will be saved automatically.")

            # Try auto-detecting login via URL change
            if browser.wait_for_login(timeout_seconds=300):
                logger.info("Login successful! Session saved.")
                logger.info("You can now run: python -m src.main --join-now \"ClassName\"")
            else:
                # Fallback: let user confirm manually
                logger.info("Could not auto-detect login.")
                input("If you are logged in, press Enter to save and close...")

            logger.info("Session saved.")
    except KeyboardInterrupt:
        logger.info("Interrupted. Session saved up to this point.")
    finally:
        browser.close()


def mode_pause(config: Config) -> None:
    """Open Teams with Playwright Inspector for discovering selectors."""
    browser = BrowserManager(
        headless=False,
        channel=config.settings.browser.channel,
    )

    try:
        browser.start()
        browser.navigate_to_teams()
        logger.info("Use the Playwright Inspector to discover selectors.")
        logger.info("Right-click elements > Inspect to find data-tid, aria-label, etc.")
        logger.info("Update src/selectors.py with what you find.")
        browser.open_pause_inspector()
    except KeyboardInterrupt:
        logger.info("Done.")
    finally:
        browser.close()


def mode_join_now(config: Config, class_name: str) -> None:
    """Immediately join a specific class by name (for testing)."""
    # Find the class in the timetable
    entry = None
    for cls in config.timetable:
        if cls.name.lower() == class_name.lower():
            entry = cls
            break

    if entry is None:
        logger.error("Class '%s' not found in timetable. Available classes:", class_name)
        for cls in config.timetable:
            logger.error("  - %s (%s %s)", cls.name, cls.day, cls.time)
        sys.exit(1)

    notifier = Notifier(config.settings.notifications)
    browser = BrowserManager(
        headless=config.settings.browser.headless,
        channel=config.settings.browser.channel,
    )

    try:
        browser.start()
        joiner = MeetingJoiner(browser, config.settings, notifier)
        joiner.join_class(entry)
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
    except Exception as e:
        logger.exception("Error during join: %s", e)
        notifier.join_failed(entry.name, str(e))
    finally:
        browser.close()


def mode_scheduler(config: Config) -> None:
    """Start the timetable scheduler (main operation mode)."""
    notifier = Notifier(config.settings.notifications)
    browser = BrowserManager(
        headless=config.settings.browser.headless,
        channel=config.settings.browser.channel,
    )

    browser.start()

    # Verify session on startup
    browser.navigate_to_teams()
    if not browser.is_logged_in():
        logger.error("Not logged in! Run: python -m src.main --login")
        notifier.session_expired()
        browser.close()
        sys.exit(1)

    logger.info("Session valid. Starting scheduler...")

    joiner = MeetingJoiner(browser, config.settings, notifier)

    def on_class_triggered(entry: ClassEntry, leave_by=None) -> None:
        """Called in the main thread when it's time to join a class."""
        logger.info("Triggered: %s", entry.name)
        try:
            joiner.join_class(entry, leave_by=leave_by)
        except Exception as e:
            logger.exception("Error joining %s: %s", entry.name, e)
            notifier.join_failed(entry.name, str(e))

    logger.info("Agent is running. Press Ctrl+C to stop.")
    logger.info("Today's classes:")
    from datetime import datetime
    today = datetime.now().strftime("%A").lower()
    today_classes = [c for c in config.timetable if c.day == today]
    if today_classes:
        for cls in today_classes:
            logger.info("  - %s at %s (%d min)", cls.name, cls.time, cls.duration_minutes)
    else:
        logger.info("  (no classes today)")

    try:
        run_scheduler(config.timetable, config.settings, on_class_triggered)
    except KeyboardInterrupt:
        logger.info("Agent stopped. Browser and meeting remain active.")
    finally:
        try:
            browser.detach()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(
        description="MS Teams Auto-Join Attendance Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.main --login           # One-time login (saves session)
  python -m src.main --pause           # Discover selectors with Playwright Inspector
  python -m src.main --join-now "Data Structures"  # Test join a class now
  python -m src.main                   # Start scheduled auto-join
        """,
    )
    parser.add_argument("--login", action="store_true", help="Open browser for manual Teams login")
    parser.add_argument("--join-now", metavar="CLASS", help="Immediately join a class by name")
    parser.add_argument("--pause", action="store_true", help="Open Teams with Playwright Inspector to discover selectors")
    parser.add_argument("--config", metavar="PATH", help="Path to config.yaml (default: config/config.yaml)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(level)

    # Load config
    try:
        config = load_config(args.config)
    except (FileNotFoundError, ValueError) as e:
        logger.error("Config error: %s", e)
        sys.exit(1)

    # Dispatch to the right mode
    if args.login:
        mode_login(config)
    elif args.pause:
        mode_pause(config)
    elif args.join_now:
        mode_join_now(config, args.join_now)
    else:
        mode_scheduler(config)


if __name__ == "__main__":
    main()
