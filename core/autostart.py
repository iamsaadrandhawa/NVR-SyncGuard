"""
Windows autostart registration.

Uses the per-user Run key in the registry
(HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run).

When frozen, the launch command is:
    "<path-to-exe>" --background

When running from source, the launch command uses pythonw.exe (no console)
if available, otherwise python.exe:
    "<pythonw.exe>" "<path-to-main.py>" --background
"""

import os
import sys
import winreg

from logger import log_line


_AUTOSTART_REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
_AUTOSTART_VALUE_NAME = "NVR_SyncGuard"


def _get_launch_command():
    """Return the full command line that should run at login."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --background'

    py = sys.executable
    pyw = os.path.join(os.path.dirname(py), "pythonw.exe")
    runner = pyw if os.path.exists(pyw) else py

    # __file__ points at this file (core/autostart.py).
    # The real entry point is one level up: main.py.
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    main_script = os.path.join(project_root, "main.py")

    return f'"{runner}" "{main_script}" --background'


def register_autostart():
    """Add (or overwrite) the Run key entry. Returns True on success."""
    try:
        cmd = _get_launch_command()
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _AUTOSTART_REG_PATH,
            0, winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key, _AUTOSTART_VALUE_NAME, 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        log_line(f"[AUTOSTART] Registered: {cmd}")
        return True
    except Exception as e:
        log_line(f"[AUTOSTART] Register failed: {e}")
        return False


def unregister_autostart():
    """Remove the Run key entry. Missing entry is not an error."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _AUTOSTART_REG_PATH,
            0, winreg.KEY_SET_VALUE,
        )
        try:
            winreg.DeleteValue(key, _AUTOSTART_VALUE_NAME)
            log_line("[AUTOSTART] Unregistered")
        except FileNotFoundError:
            pass
        winreg.CloseKey(key)
        return True
    except Exception as e:
        log_line(f"[AUTOSTART] Unregister failed: {e}")
        return False


def is_autostart_registered():
    """True if the Run key currently holds our value."""
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _AUTOSTART_REG_PATH,
            0, winreg.KEY_READ,
        )
        try:
            winreg.QueryValueEx(key, _AUTOSTART_VALUE_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception:
        return False