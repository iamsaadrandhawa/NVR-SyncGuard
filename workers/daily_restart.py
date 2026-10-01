"""
Daily auto-restart scheduler.

Every 15 seconds, checks whether the current time matches the configured
HH:MM. If it does, and we haven't already restarted today, relaunches the
app and exits.

The LAST_RESTART_DATE key in config.json prevents double-firing if the app
somehow gets restarted within the same minute.
"""

import time
import os

import state
from logger import log_line
from core.relaunch import _spawn_new_instance


def _ping_log(text):
    try:
        from datetime import datetime
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} {text}"
        state.PING_LOG_LINES.append(line)
        if len(state.PING_LOG_LINES) > state.PING_LOG_MAX:
            del state.PING_LOG_LINES[:len(state.PING_LOG_LINES) - state.PING_LOG_MAX]
        state.UI_QUEUE.put(("ping_log", line))
    except Exception:
        pass


def _perform_scheduled_restart():
    """Set stop flags, spawn a new instance, and exit this one.

    Waits up to 30 seconds for a running scan to finish, so Chrome closes
    cleanly. Then performs the swap.
    """
    log_line("[RESTART] Scheduled daily restart")
    _ping_log("[RESTART] Scheduled daily restart - relaunching")

    # Let a running scan finish so Chrome closes cleanly
    if state.scan_running:
        state.stop_requested = True
        for _ in range(30):
            if not state.scan_running:
                break
            time.sleep(1)

    state.MONITOR_STOP.set()

    try:
        if state.TRAY_ICON is not None:
            state.TRAY_ICON.stop()
    except Exception:
        pass

    try:
        _spawn_new_instance()
    except Exception as e:
        log_line(f"[RESTART] Relaunch failed: {e}")

    # Ask the GUI to close
    try:
        state.root.after(0, state.root.destroy)
    except Exception:
        pass

    time.sleep(0.5)
    os._exit(0)


def _daily_restart_worker():
    """Main loop. Checks every 15 seconds; exits the process on match."""
    log_line("[RESTART] Daily-restart scheduler started")

    while not state.MONITOR_STOP.is_set():
        try:
            if state.DAILY_RESTART_ENABLED:
                from datetime import datetime
                now = datetime.now()
                today = now.strftime("%Y-%m-%d")

                if (now.hour == state.DAILY_RESTART_HOUR
                        and now.minute == state.DAILY_RESTART_MINUTE
                        and _config.get("LAST_RESTART_DATE", "") != today):
                    # Persist BEFORE restarting so the new process doesn't
                    # see the same minute and loop forever.
                    _config["LAST_RESTART_DATE"] = today
                    state.save_config()
                    _perform_scheduled_restart()
                    return
        except Exception as e:
            log_line(f"[RESTART] Scheduler error: {e}")

        state.MONITOR_STOP.wait(15)