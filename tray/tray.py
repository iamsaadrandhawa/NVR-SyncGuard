"""
System tray icon and menu.

Wraps pystray. Uses the app logo (or a solid blue square if the logo can't
be loaded). Every menu action is thread-safe: it marshals to the main
thread via state.root.after() when it needs to touch the GUI.

Exposes:
  start_tray_icon()          - create and start the icon (call once)
  _refresh_tray_tooltip()    - update the tooltip text (safe to call anytime)
  _build_tray_tooltip()      - produce the tooltip string
"""

import os
import time
import threading

import state
from logger import log_line
from paths import ICO_PATH, LOGO_PATH, LOG_DIR
from core.autostart import is_autostart_registered, register_autostart, unregister_autostart
from core.relaunch import _spawn_new_instance


# =========================================================
# ICON IMAGE
# =========================================================
def _load_tray_image():
    """Load the logo as a PIL Image. Falls back to a solid blue square."""
    try:
        from PIL import Image
        for path in (ICO_PATH, LOGO_PATH):
            if path and os.path.exists(path):
                img = Image.open(path).convert("RGBA")
                img = img.resize((64, 64), Image.LANCZOS)
                return img
    except Exception as e:
        log_line(f"[TRAY] Image load failed: {e}")

    try:
        from PIL import Image
        return Image.new("RGBA", (64, 64), (37, 99, 235, 255))
    except Exception:
        return None


# =========================================================
# TOOLTIP
# =========================================================
def _build_tray_tooltip():
    base = f"NVR SyncGuard v{state.APP_VERSION}"
    try:
        n_down = sum(1 for s in state.NVR_STATE.values() if s == "down")
        with state.OFFLINE_CAMERA_LOCK:
            n_cam_off = len(state.OFFLINE_CAMERA_IPS)
        parts = [base]
        if n_down:
            parts.append(f"{n_down} NVR down")
        if n_cam_off:
            parts.append(f"{n_cam_off} camera(s) offline")
        if len(parts) == 1:
            parts.append("all healthy")
        return " - ".join(parts)
    except Exception:
        return base


def _refresh_tray_tooltip():
    try:
        if state.TRAY_ICON is not None:
            state.TRAY_ICON.title = _build_tray_tooltip()
    except Exception:
        pass


# =========================================================
# MENU HANDLERS
# =========================================================
def _tray_open_window(icon, item):
    try:
        if state.root is not None:
            state.root.after(0, lambda: (
                state.root.deiconify(),
                state.root.lift(),
                state.root.focus_force(),
            ))
    except Exception as e:
        log_line(f"[TRAY] Open window failed: {e}")


def _tray_run_now(icon, item):
    try:
        if state.root is not None:
            state.root.after(0, _trigger_manual_scan_from_tray)
    except Exception as e:
        log_line(f"[TRAY] Run-now failed: {e}")


def _tray_open_logs(icon, item):
    try:
        os.startfile(LOG_DIR)
    except Exception as e:
        log_line(f"[TRAY] Open logs failed: {e}")


def _tray_open_reports(icon, item):
    try:
        os.startfile(state.DOWNLOADS_DIR)
    except Exception as e:
        log_line(f"[TRAY] Open reports failed: {e}")


def _tray_toggle_autostart(icon, item):
    try:
        if is_autostart_registered():
            unregister_autostart()
        else:
            register_autostart()
    except Exception as e:
        log_line(f"[TRAY] Toggle autostart failed: {e}")


def _tray_exit(icon, item):
    """User-initiated full exit. Only this stops the app completely."""
    try:
        state.MONITOR_STOP.set()
    except Exception:
        pass
    try:
        icon.stop()
    except Exception:
        pass
    try:
        if state.root is not None:
            state.root.after(0, state.root.destroy)
    except Exception:
        pass
    log_line("[TRAY] Exit requested by user")
    try:
        time.sleep(0.4)
        os._exit(0)
    except Exception:
        pass


def _tray_restart(icon, item):
    try:
        state.MONITOR_STOP.set()
    except Exception:
        pass
    try:
        icon.stop()
    except Exception:
        pass
    try:
        _spawn_new_instance()
    except Exception as e:
        log_line(f"[TRAY] Restart failed: {e}")
    try:
        if state.root is not None:
            state.root.after(0, state.root.destroy)
    except Exception:
        pass
    time.sleep(0.4)
    os._exit(0)


def _trigger_manual_scan_from_tray():
    """Runs on the main thread (scheduled via root.after)."""
    try:
        if state.scan_running:
            log_line("[TRAY] Scan already running")
            return
        if state.log is not None and state.btn is not None and state.tree_proxy is not None:
            from actions import start_all
            start_all(state.log, state.btn, state.tree_proxy,
                      state.status_label_proxy, auto_start=False)
    except Exception as e:
        log_line(f"[TRAY] Manual scan failed: {e}")


# =========================================================
# START THE ICON
# =========================================================
def start_tray_icon():
    global _tray_icon_holder  # pylint: disable=global-statement

    try:
        import pystray
    except ImportError:
        log_line("[TRAY] pystray not installed - running without tray icon")
        return

    image = _load_tray_image()
    if image is None:
        log_line("[TRAY] No icon image available")
        return

    def _autostart_label(item):
        return "Autostart: ON" if is_autostart_registered() else "Autostart: OFF"

    def _status_label(item):
        return _build_tray_tooltip()

    menu = pystray.Menu(
        pystray.MenuItem(_status_label, None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Open NVR SyncGuard", _tray_open_window, default=True),
        pystray.MenuItem("Run scan now", _tray_run_now),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Open reports folder", _tray_open_reports),
        pystray.MenuItem("Open logs folder", _tray_open_logs),
        pystray.MenuItem(_autostart_label, _tray_toggle_autostart),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Restart app", _tray_restart),
        pystray.MenuItem("Exit (fully close)", _tray_exit),
    )

    try:
        state.TRAY_ICON = pystray.Icon(
            "nvrsyncguard", image, _build_tray_tooltip(), menu
        )
        thread = threading.Thread(target=state.TRAY_ICON.run, daemon=True)
        thread.start()
        log_line("[TRAY] Tray icon started")
    except Exception as e:
        log_line(f"[TRAY] Failed to start tray icon: {e}")