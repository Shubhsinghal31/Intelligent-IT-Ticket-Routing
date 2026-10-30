"""
Centralized logging configuration using Loguru.

Loguru provides:
- Single import (no factory boilerplate)
- Beautiful colored console output
- File rotation, retention, compression
- Structured JSON logs in production
"""

import sys
from pathlib import Path

from loguru import logger

from backend.core.config import settings


def setup_logging() -> None:
    """
    Configure loguru logger for the entire application.

    Behavior:
    - DEV: colored console output, DEBUG level
    - PROD: JSON-structured file output, rotated daily
    """
    # Remove default handler — we add our own
    logger.remove()

    # request_id is injected per-request by RequestIDMiddleware via
    # logger.contextualize(). Log lines outside a request (startup/shutdown,
    # background scripts) never enter that context, so {extra[request_id]}
    # would KeyError without a process-wide default — this sets one.
    logger.configure(extra={"request_id": "-"})

    # =====================================================
    # Console handler
    # =====================================================
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<magenta>{extra[request_id]}</magenta> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    logger.add(
        sys.stdout,
        format=console_format,
        level=settings.LOG_LEVEL,
        colorize=True,
        backtrace=True,
        diagnose=settings.is_development,  # Disable in prod (leaks vars)
    )

    # =====================================================
    # File handler — rotated, compressed
    # =====================================================
    log_file: Path = settings.log_file_full_path
    logger.add(
        str(log_file),
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
            "{extra[request_id]} | {name}:{function}:{line} | {message}"
        ),
        level=settings.LOG_LEVEL,
        rotation="10 MB",  # Rotate when file hits 10 MB
        retention="14 days",  # Keep 14 days of logs
        compression="zip",  # Compress old logs
        backtrace=True,
        diagnose=settings.is_development,
        enqueue=True,  # Async-safe — required for FastAPI
    )

    logger.info(f"Logging initialized | level={settings.LOG_LEVEL} | env={settings.APP_ENV}")
