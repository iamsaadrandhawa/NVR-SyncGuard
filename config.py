"""
NVR SyncGuard - Configuration.

Holds DEFAULT_CONFIG, load_config() and the module-level `config` dict.

IMPORTANT: this file does NOT contain save_config(). That function writes
runtime state (NVR_LIST, DOWNLOADS_DIR, etc.) which lives in state.py, so
save_config() lives there too. Keeping it here would create a circular
import: state imports config, and config would need state.
"""

import os
import json
from datetime import datetime

from paths import CONFIG_FILE, DEFAULT_REPORTS_DIR


# ---------------------------------------------------------
# Defaults applied on first run and merged on every launch
# ---------------------------------------------------------
DEFAULT_CONFIG = {
    "NVR_LIST": [],
    "DOWNLOADS_DIR": DEFAULT_REPORTS_DIR,
    "EXCEL_FILE": "OfflineCameras.xlsx",
    "CODRAZE_URL": "https://codraze.vercel.app/",
    "AUTO_START": True,
    "SCAN_DELAY_SECONDS": 2,
    "COLLECT_ALL_IPS": False,
    "ADMIN_PASSWORD_HASH": "",
    "ADMIN_PASSWORD_SALT": "",
    "ADMIN_PASSWORD_SET_AT": "",
    "AUTO_CLOSE_HOUR": 12,
    "AUTO_CLOSE_MINUTE": 0,
    "AUTO_CLOSE_ENABLED": True,
    "TIMEOUT_LOGIN": 120,
    "TIMEOUT_DASHBOARD": 120,
    "TIMEOUT_CONFIG_CLICK": 60,
    "TIMEOUT_TIME_MENU": 60,
    "TIMEOUT_TIME_FORM": 60,
    "TIMEOUT_SAVE_CONFIRM": 30,
    "TIMEOUT_CAMERA_MENU": 90,
    "TIMEOUT_CAMERA_TABLE": 180,
    "TIMEOUT_BETWEEN_NVR": 3,
    "STABILITY_BUFFER": 1.5,
    "USE_DATE_STAMPED_FILES": True,
    "OVERLAY_WAIT_TIMEOUT": 8,
    "CLICK_MAX_ATTEMPTS": 3,
    "BACKGROUND_MODE": True,
    "START_MINIMIZED_TO_TRAY": True,
    "MONITOR_INTERVAL_MINUTES": 5,
    "SHOW_TOASTS": True,
    "AUTOSTART_WITH_WINDOWS": True,
    "NVR_DOWN_RETRY_BASE_SECONDS": 30,
    "NVR_DOWN_RETRY_MAX_SECONDS": 300,
    "RUN_SCAN_ON_LAUNCH": True,
    "BACKGROUND_PING_MONITOR": True,
    "AUTO_SCAN_ON_RECOVERY": True,
    "NVR_RETRY_ATTEMPTS": 3,
    "NVR_RETRY_WAIT_SECONDS": [30, 60, 90],
    "ELEMENT_READY_TIMEOUT": 20,
    "PAGE_READY_TIMEOUT": 15,
    # ---- v4.3.0 additions ----
    "MONITOR_INTERVAL_SECONDS": 30,
    "CAMERA_PING_ENABLED": True,
    "CAMERA_PING_INTERVAL_SECONDS": 15,
    "CAMERA_PING_TIMEOUT_SECONDS": 3,
    "CAMERA_PING_METHOD": "tcp",     # "tcp" or "icmp"
    # ---- v4.4.0 additions ----
    "DAILY_RESTART_ENABLED": True,
    "DAILY_RESTART_HOUR": 8,
    "DAILY_RESTART_MINUTE": 30,
    "LAST_RESTART_DATE": "",
    "DOWN_ALERT_REPEAT_MINUTES": 5,
}


# ---------------------------------------------------------
# Load / create config.json
# ---------------------------------------------------------
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = DEFAULT_CONFIG.copy()
            merged.update(data)
            return merged
        except Exception:
            return DEFAULT_CONFIG.copy()
    else:
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, indent=4)
        except Exception:
            pass
        return DEFAULT_CONFIG.copy()


# The one and only live config dict. state.py, actions.py and auth.py
# mutate this in place; save_config() writes it back to disk.
config = load_config()