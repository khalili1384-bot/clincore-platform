# src/clincore/api/logging_conf.py
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()

    # جلوگیری از دوباره‌سازی handler
    if logging.getLogger().handlers:
        return

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Rotating file handler (۵MB ، ۳ نسخه بایگانی)
    file_handler = RotatingFileHandler(
        log_dir / "clincore.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)