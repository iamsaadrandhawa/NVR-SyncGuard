"""
NVR SyncGuard - Logging.

Configures a rotating file log inside logs/ and a console handler.
Import `log_line()` from anywhere in the app.
"""

import os
import sys
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler

from paths import LOG_DIR


def _setup_logging():
    log_file = os.path.join(
        LOG_DIR, f"syncguard_{datetime.now().strftime('%Y-%m-%d')}.log"
    )

    logger = logging.getLogger("syncguard")
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers if the module is imported twice
    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler (2 MB per file, keep 7 backups)
    fh = RotatingFileHandler(
        log_file, maxBytes=2_000_000, backupCount=7, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Console handler - wrapped in try/except because pythonw.exe on Windows
    # has no stdout; without this guard the app crashes before the GUI appears.
    try:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        logger.addHandler(sh)
    except Exception:
        pass

    return logger


LOGGER = _setup_logging()


def log_line(text):
    """Write one line to the log. Safe to call from any thread."""
    try:
        LOGGER.info(str(text).rstrip("\n"))
    except Exception:
        pass