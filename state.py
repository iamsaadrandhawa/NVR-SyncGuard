"""
NVR SyncGuard - Runtime state.

This module replaces every module-level global that used to live at the top
of main.py:

  - Configuration-derived constants (TIMEOUT_*, CAMERA_PING_*, etc.)
  - Runtime mutables (NVR_LIST, scan_running, camera_data, ...)
  - Thread primitives (MONITOR_STOP, OFFLINE_CAMERA_LOCK)
  - The UI update queue (UI_QUEUE)
  - save_config() (the JSON persistence writer)

Any module that used to do `global X; X = value` in main.py must now do
`state.X = value`. Any module that used to read `X` must now read `state.X`.
"""

import os
import re
import json
import queue
import threading
from datetime import datetime

from config import config
from paths import CONFIG_FILE
from logger import log_line


# =========================================================
# APP METADATA
# =========================================================
APP_NAME = "NVR SyncGuard"
APP_VERSION = "4.4.0"
APP_AUTHOR = "Codraze"
APP_YEAR = datetime.now().year


# =========================================================
# NVR LIST NORMALIZATION (runs once at import time)
# =========================================================
def _normalize_nvr_entry(entry, default_user="admin"):
    if isinstance(entry, dict):
        url = str(entry.get("url", "")).strip()
        username = str(entry.get("username", default_user)).strip() or default_user
        password = str(entry.get("password", ""))
        if url:
            return {"url": url, "username": username, "password": password}
        return None
    if isinstance(entry, str):
        url = entry.strip()
        if url:
            return {"url": url, "username": default_user, "password": ""}
    return None


_legacy_user = config.get("USERNAME", "admin") or "admin"
NVR_LIST = []
for _item in config.get("NVR_LIST", []):
    _norm = _normalize_nvr_entry(_item, default_user=_legacy_user)
    if _norm:
        NVR_LIST.append(_norm)


# =========================================================
# CONFIG-DERIVED CONSTANTS (read at import time)
# =========================================================
DOWNLOADS_DIR = config.get("DOWNLOADS_DIR")
BASE_EXCEL_FILENAME = config.get("EXCEL_FILE", "OfflineCameras.xlsx")
EXCEL_FILE = os.path.join(DOWNLOADS_DIR, BASE_EXCEL_FILENAME)
CODRAZE_URL = config.get("CODRAZE_URL")
AUTO_START = bool(config.get("AUTO_START", True))
SCAN_DELAY_SECONDS = int(config.get("SCAN_DELAY_SECONDS", 2))
COLLECT_ALL_IPS = bool(config.get("COLLECT_ALL_IPS", False))

AUTO_CLOSE_ENABLED = bool(config.get("AUTO_CLOSE_ENABLED", True))
AUTO_CLOSE_HOUR = int(config.get("AUTO_CLOSE_HOUR", 12))
AUTO_CLOSE_MINUTE = int(config.get("AUTO_CLOSE_MINUTE", 0))

TIMEOUT_LOGIN = int(config.get("TIMEOUT_LOGIN", 120))
TIMEOUT_DASHBOARD = int(config.get("TIMEOUT_DASHBOARD", 120))
TIMEOUT_CONFIG_CLICK = int(config.get("TIMEOUT_CONFIG_CLICK", 60))
TIMEOUT_TIME_MENU = int(config.get("TIMEOUT_TIME_MENU", 60))
TIMEOUT_TIME_FORM = int(config.get("TIMEOUT_TIME_FORM", 60))
TIMEOUT_SAVE_CONFIRM = int(config.get("TIMEOUT_SAVE_CONFIRM", 30))
TIMEOUT_CAMERA_MENU = int(config.get("TIMEOUT_CAMERA_MENU", 90))
TIMEOUT_CAMERA_TABLE = int(config.get("TIMEOUT_CAMERA_TABLE", 180))
TIMEOUT_BETWEEN_NVR = int(config.get("TIMEOUT_BETWEEN_NVR", 3))
STABILITY_BUFFER = float(config.get("STABILITY_BUFFER", 1.5))
USE_DATE_STAMPED_FILES = bool(config.get("USE_DATE_STAMPED_FILES", True))
OVERLAY_WAIT_TIMEOUT = float(config.get("OVERLAY_WAIT_TIMEOUT", 8))
CLICK_MAX_ATTEMPTS = int(config.get("CLICK_MAX_ATTEMPTS", 3))

NVR_RETRY_ATTEMPTS = int(config.get("NVR_RETRY_ATTEMPTS", 3))
NVR_RETRY_WAIT_SECONDS = config.get("NVR_RETRY_WAIT_SECONDS", [30, 60, 90])
if not isinstance(NVR_RETRY_WAIT_SECONDS, list) or not NVR_RETRY_WAIT_SECONDS:
    NVR_RETRY_WAIT_SECONDS = [30, 60, 90]
try:
    NVR_RETRY_WAIT_SECONDS = [int(x) for x in NVR_RETRY_WAIT_SECONDS]
except Exception:
    NVR_RETRY_WAIT_SECONDS = [30, 60, 90]

ELEMENT_READY_TIMEOUT = int(config.get("ELEMENT_READY_TIMEOUT", 20))
PAGE_READY_TIMEOUT = int(config.get("PAGE_READY_TIMEOUT", 15))

BACKGROUND_MODE = bool(config.get("BACKGROUND_MODE", True))
START_MINIMIZED_TO_TRAY = bool(config.get("START_MINIMIZED_TO_TRAY", True))
MONITOR_INTERVAL_MINUTES = int(config.get("MONITOR_INTERVAL_MINUTES", 5))
SHOW_TOASTS = bool(config.get("SHOW_TOASTS", True))
AUTOSTART_WITH_WINDOWS = bool(config.get("AUTOSTART_WITH_WINDOWS", True))
NVR_DOWN_RETRY_BASE_SECONDS = int(config.get("NVR_DOWN_RETRY_BASE_SECONDS", 30))
NVR_DOWN_RETRY_MAX_SECONDS = int(config.get("NVR_DOWN_RETRY_MAX_SECONDS", 300))

RUN_SCAN_ON_LAUNCH = bool(config.get("RUN_SCAN_ON_LAUNCH", True))
BACKGROUND_PING_MONITOR = bool(config.get("BACKGROUND_PING_MONITOR", True))
AUTO_SCAN_ON_RECOVERY = bool(config.get("AUTO_SCAN_ON_RECOVERY", True))

# v4.3.0 additions
MONITOR_INTERVAL_SECONDS = int(config.get("MONITOR_INTERVAL_SECONDS", 30))
CAMERA_PING_ENABLED = bool(config.get("CAMERA_PING_ENABLED", True))
CAMERA_PING_INTERVAL_SECONDS = int(config.get("CAMERA_PING_INTERVAL_SECONDS", 15))
CAMERA_PING_TIMEOUT_SECONDS = int(config.get("CAMERA_PING_TIMEOUT_SECONDS", 3))
CAMERA_PING_METHOD = str(config.get("CAMERA_PING_METHOD", "tcp")).lower()
if CAMERA_PING_METHOD not in ("tcp", "icmp"):
    CAMERA_PING_METHOD = "tcp"

# v4.4.0 additions
DAILY_RESTART_ENABLED = bool(config.get("DAILY_RESTART_ENABLED", True))
DAILY_RESTART_HOUR = int(config.get("DAILY_RESTART_HOUR", 8))
DAILY_RESTART_MINUTE = int(config.get("DAILY_RESTART_MINUTE", 30))
DOWN_ALERT_REPEAT_MINUTES = int(config.get("DOWN_ALERT_REPEAT_MINUTES", 5))


# =========================================================
# GLOBAL UI / RUNTIME STATE
# =========================================================
# These are the "settings panel" Tk variables. They are created in the UI
# at window-build time and stored here so actions.py and the workers can
# read them without a circular import.
date_stamp_var = None
run_scan_on_launch_var = None
bg_ping_var = None
auto_recovery_var = None
ping_interval_var = None
restart_enabled_var = None
restart_time_var = None
alert_interval_var = None

# Scan progress counters
stop_requested = False
total_nvrs_count = 0
total_cameras_count = 0
online_cameras_count = 0
offline_cameras_count = 0
camera_data = []
offline_cameras_data = []
last_saved_file = None
scan_running = False

# NVR health
NVR_STATE = {}
MONITOR_STOP = threading.Event()
TRAY_ICON = None
_background_scan_flag = [False]

# Camera offline tracking
OFFLINE_CAMERA_IPS = {}
OFFLINE_CAMERA_LOCK = threading.Lock()

# v4.3.1 counters and buffers
CHECKED_NVRS = 0
SKIPPED_NVRS = 0
PING_LOG_LINES = []
PING_LOG_MAX = 500
NVR_PING_HISTORY = {}
CAMERA_PING_HISTORY = {}
UI_STATE = {"running": False, "phase": "idle"}
UI_QUEUE = queue.Queue()

# Widget references (populated by ui/window.py at build time)
root = None
log = None
btn = None
tree_proxy = None
status_label_proxy = None
last_saved_label = None
nvr_entry = None
nvr_user_entry = None
nvr_pass_entry = None
nvr_listbox = None
nvr_count_label = None
collect_ips_var = None

# Additional widget references used by ui/window.py and actions.py
tree_widget = None
log_widget = None
folder_path_label = None


# =========================================================
# save_config()
# =========================================================
def save_config():
    """Write the current runtime state back to config.json."""
    config["NVR_LIST"] = NVR_LIST
    config["DOWNLOADS_DIR"] = DOWNLOADS_DIR
    config["EXCEL_FILE"] = BASE_EXCEL_FILENAME
    config["AUTO_START"] = AUTO_START
    config["SCAN_DELAY_SECONDS"] = SCAN_DELAY_SECONDS
    config["COLLECT_ALL_IPS"] = COLLECT_ALL_IPS

    # Admin state is filled in by auth.py; read from the live config
    config["ADMIN_PASSWORD_HASH"] = config.get("ADMIN_PASSWORD_HASH", "")
    config["ADMIN_PASSWORD_SALT"] = config.get("ADMIN_PASSWORD_SALT", "")
    config["ADMIN_PASSWORD_SET_AT"] = config.get("ADMIN_PASSWORD_SET_AT", "")

    config["AUTO_CLOSE_ENABLED"] = AUTO_CLOSE_ENABLED
    config["AUTO_CLOSE_HOUR"] = AUTO_CLOSE_HOUR
    config["AUTO_CLOSE_MINUTE"] = AUTO_CLOSE_MINUTE

    config["TIMEOUT_LOGIN"] = TIMEOUT_LOGIN
    config["TIMEOUT_DASHBOARD"] = TIMEOUT_DASHBOARD
    config["TIMEOUT_CONFIG_CLICK"] = TIMEOUT_CONFIG_CLICK
    config["TIMEOUT_TIME_MENU"] = TIMEOUT_TIME_MENU
    config["TIMEOUT_TIME_FORM"] = TIMEOUT_TIME_FORM
    config["TIMEOUT_SAVE_CONFIRM"] = TIMEOUT_SAVE_CONFIRM
    config["TIMEOUT_CAMERA_MENU"] = TIMEOUT_CAMERA_MENU
    config["TIMEOUT_CAMERA_TABLE"] = TIMEOUT_CAMERA_TABLE
    config["TIMEOUT_BETWEEN_NVR"] = TIMEOUT_BETWEEN_NVR
    config["STABILITY_BUFFER"] = STABILITY_BUFFER
    config["USE_DATE_STAMPED_FILES"] = USE_DATE_STAMPED_FILES
    config["OVERLAY_WAIT_TIMEOUT"] = OVERLAY_WAIT_TIMEOUT
    config["CLICK_MAX_ATTEMPTS"] = CLICK_MAX_ATTEMPTS

    config["NVR_RETRY_ATTEMPTS"] = NVR_RETRY_ATTEMPTS
    config["NVR_RETRY_WAIT_SECONDS"] = NVR_RETRY_WAIT_SECONDS
    config["ELEMENT_READY_TIMEOUT"] = ELEMENT_READY_TIMEOUT
    config["PAGE_READY_TIMEOUT"] = PAGE_READY_TIMEOUT

    config["BACKGROUND_MODE"] = BACKGROUND_MODE
    config["START_MINIMIZED_TO_TRAY"] = START_MINIMIZED_TO_TRAY
    config["MONITOR_INTERVAL_MINUTES"] = MONITOR_INTERVAL_MINUTES
    config["SHOW_TOASTS"] = SHOW_TOASTS
    config["AUTOSTART_WITH_WINDOWS"] = AUTOSTART_WITH_WINDOWS
    config["NVR_DOWN_RETRY_BASE_SECONDS"] = NVR_DOWN_RETRY_BASE_SECONDS
    config["NVR_DOWN_RETRY_MAX_SECONDS"] = NVR_DOWN_RETRY_MAX_SECONDS

    config["RUN_SCAN_ON_LAUNCH"] = RUN_SCAN_ON_LAUNCH
    config["BACKGROUND_PING_MONITOR"] = BACKGROUND_PING_MONITOR
    config["AUTO_SCAN_ON_RECOVERY"] = AUTO_SCAN_ON_RECOVERY

    config["MONITOR_INTERVAL_SECONDS"] = MONITOR_INTERVAL_SECONDS
    config["CAMERA_PING_ENABLED"] = CAMERA_PING_ENABLED
    config["CAMERA_PING_INTERVAL_SECONDS"] = CAMERA_PING_INTERVAL_SECONDS
    config["CAMERA_PING_TIMEOUT_SECONDS"] = CAMERA_PING_TIMEOUT_SECONDS
    config["CAMERA_PING_METHOD"] = CAMERA_PING_METHOD

    config["DAILY_RESTART_ENABLED"] = DAILY_RESTART_ENABLED
    config["DAILY_RESTART_HOUR"] = DAILY_RESTART_HOUR
    config["DAILY_RESTART_MINUTE"] = DAILY_RESTART_MINUTE
    config["DOWN_ALERT_REPEAT_MINUTES"] = DOWN_ALERT_REPEAT_MINUTES

    # Legacy keys that are no longer used
    config.pop("USERNAME", None)
    config.pop("PASSWORD", None)

    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
    except OSError as error:
        log_line(f"[ERROR] save_config: {error}")