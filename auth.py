"""
NVR SyncGuard - Password hashing and verification.

This module holds the password logic ONLY. The Tk dialogs that ask the user
for a password live in ui/dialogs.py. Splitting them keeps auth.py free of
Tkinter, which means it can be imported from workers and tray code without
pulling in the GUI.
"""

import hmac
import hashlib
import secrets
from datetime import datetime

from config import config
from paths import CONFIG_FILE, DEFAULT_ADMIN_PASSWORD
from logger import log_line


# =========================================================
# ADMIN PASSWORD STATE
# =========================================================
ADMIN_STATE = {"hash": "", "salt": "", "set_at": ""}


def _hash_password(password, salt):
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def _load_admin_state_from_config():
    """Read the hash/salt from config.json. On first run, seed them from the
    default password and persist."""
    global ADMIN_STATE
    ADMIN_STATE["hash"] = (config.get("ADMIN_PASSWORD_HASH") or "").strip()
    ADMIN_STATE["salt"] = (config.get("ADMIN_PASSWORD_SALT") or "").strip()
    ADMIN_STATE["set_at"] = (config.get("ADMIN_PASSWORD_SET_AT") or "").strip()

    if not ADMIN_STATE["hash"] or not ADMIN_STATE["salt"]:
        salt = secrets.token_hex(16)
        ADMIN_STATE["salt"] = salt
        ADMIN_STATE["hash"] = _hash_password(DEFAULT_ADMIN_PASSWORD, salt)
        ADMIN_STATE["set_at"] = datetime.now().strftime("%Y-%m-%d")

        config["ADMIN_PASSWORD_HASH"] = ADMIN_STATE["hash"]
        config["ADMIN_PASSWORD_SALT"] = ADMIN_STATE["salt"]
        config["ADMIN_PASSWORD_SET_AT"] = ADMIN_STATE["set_at"]
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                import json
                json.dump(config, f, indent=4)
        except Exception:
            pass


def _persist_admin_state():
    """Write the current ADMIN_STATE back into config.json."""
    config["ADMIN_PASSWORD_HASH"] = ADMIN_STATE["hash"]
    config["ADMIN_PASSWORD_SALT"] = ADMIN_STATE["salt"]
    config["ADMIN_PASSWORD_SET_AT"] = ADMIN_STATE["set_at"]
    try:
        import json
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
    except Exception:
        pass


def _verify_admin_password(entered):
    """Compare a candidate password against the stored hash."""
    salt = ADMIN_STATE.get("salt", "")
    expected = ADMIN_STATE.get("hash", "")
    if not salt or not expected:
        return False
    return hmac.compare_digest(_hash_password(entered, salt), expected)


def _set_new_admin_password(new_password):
    """Generate a new salt, hash the new password, persist."""
    salt = secrets.token_hex(16)
    ADMIN_STATE["salt"] = salt
    ADMIN_STATE["hash"] = _hash_password(new_password, salt)
    ADMIN_STATE["set_at"] = datetime.now().strftime("%Y-%m-%d")
    _persist_admin_state()


# Seed ADMIN_STATE at import time
_load_admin_state_from_config()