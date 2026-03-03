"""Retry decorator, logging setup, and miscellaneous helpers."""

import functools
import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure root logger with console + rotating file output."""
    LOG_DIR.mkdir(exist_ok=True)

    logger = logging.getLogger("attendance_agent")
    if logger.handlers:
        return logger

    logger.setLevel(level)
    fmt = logging.Formatter("[%(asctime)s] %(levelname)-8s %(name)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # Console
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    # Rotating file (5 MB, keep 5 backups)
    file_handler = RotatingFileHandler(
        LOG_DIR / "agent.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


def retry(attempts: int = 3, delay: float = 2.0, backoff: float = 2.0, exceptions: tuple = (Exception,)):
    """Retry decorator with exponential backoff.

    Args:
        attempts: Maximum number of tries.
        delay: Initial delay between retries in seconds.
        backoff: Multiplier applied to delay after each retry.
        exceptions: Tuple of exception types to catch.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = logging.getLogger("attendance_agent")
            current_delay = delay
            last_exception = None

            for attempt in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < attempts:
                        logger.warning(
                            "%s failed (attempt %d/%d): %s. Retrying in %.1fs...",
                            func.__name__, attempt, attempts, e, current_delay,
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error("%s failed after %d attempts: %s", func.__name__, attempts, e)

            raise last_exception

        return wrapper

    return decorator


def retry_async(attempts: int = 3, delay: float = 2.0, backoff: float = 2.0, exceptions: tuple = (Exception,)):
    """Async retry decorator with exponential backoff."""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            logger = logging.getLogger("attendance_agent")
            current_delay = delay
            last_exception = None

            for attempt in range(1, attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < attempts:
                        logger.warning(
                            "%s failed (attempt %d/%d): %s. Retrying in %.1fs...",
                            func.__name__, attempt, attempts, e, current_delay,
                        )
                        import asyncio
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error("%s failed after %d attempts: %s", func.__name__, attempts, e)

            raise last_exception

        return wrapper

    return decorator
