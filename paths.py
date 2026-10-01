"""
NVR SyncGuard - Path resolution.

This module resolves filesystem paths at import time. It is the lowest layer
of the app: nothing else here imports from the rest of the codebase.

When frozen by PyInstaller:
  - BASE_DIR is the folder containing the .exe (read-only code lives in
    sys._MEIPASS, which is where bundled resources like images/ are placed).
  - User-writable files (config.json, logs/, reports) live next to the .exe.

When running from source:
  - BASE_DIR is the folder containing this file (the project root).
"""

import os
import sys


# ---------------------------------------------------------
# Determine BASE_DIR (the "app folder")
# ---------------------------------------------------------
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
    _BUNDLE_DIR = getattr(sys, "_MEIPASS", BASE_DIR)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    _BUNDLE_DIR = BASE_DIR


# ---------------------------------------------------------
# Bundled resources (read-only, travel inside the .exe)
# ---------------------------------------------------------
IMAGES_DIR = os.path.join(_BUNDLE_DIR, "images")
LOGO_PATH = os.path.join(IMAGES_DIR, "logo.png")
ICO_PATH = os.path.join(IMAGES_DIR, "logo.ico")

DRIVERS_DIR = os.path.join(_BUNDLE_DIR, "drivers")
CHROMEDRIVER_PATH = os.path.join(DRIVERS_DIR, "chromedriver.exe")


# ---------------------------------------------------------
# User-writable files (live next to the .exe / project root)
# ---------------------------------------------------------
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)


# ---------------------------------------------------------
# Default report location (user's Documents folder)
# ---------------------------------------------------------
_DEFAULT_REPORTS_DIR = os.path.join(
    os.path.expanduser("~"), "Documents", "NVR_SyncGuard"
)
DEFAULT_REPORTS_DIR = _DEFAULT_REPORTS_DIR


# ---------------------------------------------------------
# Default admin password (only used on first run)
# ---------------------------------------------------------
DEFAULT_ADMIN_PASSWORD = "Saad@18977"