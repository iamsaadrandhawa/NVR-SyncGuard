"""
Repeating down-alert worker.

Every state.DOWN_ALERT_REPEAT_MINUTES, checks if any NVR or camera is still
down and, if so, shows a single toast summarising them. Avoids spamming by
respecting the interval.

Runs in a daemon thread. Exit signal: state.MONITOR_STOP set.
"""

import time
from datetime import datetime

import state
from logger import log_line
from core.url_utils import _nvr_host_only


def _ping_log(text):
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} {text}"
        state.PING_LOG_LINES.append(line)
        if len(state.PING_LOG_LINES) > state.PING_LOG_MAX:
            del state.PING_LOG_LINES[:len(state.PING_LOG_LINES) - state.PING_LOG_MAX]
        state.UI_QUEUE.put(("ping_log", line))
    except Exception:
        pass


def _show_toast(title, message):
    try:
        from core.toasts import show_toast
        show_toast(title, message)
    except Exception:
        pass


def _down_alert_worker():
    """Main loop. Never returns until state.MONITOR_STOP is set."""
    log_line("[ALERT] Down-alert worker started")

    last_sent = 0.0

    while not state.MONITOR_STOP.is_set():
        state.MONITOR_STOP.wait(10)
        try:
            interval = max(1, state.DOWN_ALERT_REPEAT_MINUTES) * 60
            if time.time() - last_sent < interval:
                continue

            # --- Which NVRs are down? ---
            hosts = {_nvr_host_only(e["url"]) for e in state.NVR_LIST}
            down_nvrs = sorted(
                h for h, i in list(state.NVR_PING_HISTORY.items())
                if i.get("state") == "down" and h in hosts
            )

            # --- Which cameras are offline? ---
            with state.OFFLINE_CAMERA_LOCK:
                cams = [
                    (ip, info.get("name", ""))
                    for ip, info in state.OFFLINE_CAMERA_IPS.items()
                ]

            if not down_nvrs and not cams:
                continue

            # --- Build the message ---
            parts = []
            if down_nvrs:
                parts.append(
                    f"{len(down_nvrs)} NVR down: "
                    + ", ".join(down_nvrs[:5])
                    + (" ..." if len(down_nvrs) > 5 else "")
                )
            if cams:
                parts.append(
                    f"{len(cams)} camera offline: "
                    + ", ".join(ip for ip, _ in cams[:5])
                    + (" ..." if len(cams) > 5 else "")
                )

            msg = "\n".join(parts)
            _show_toast("Devices still offline", msg)
            _ping_log("[ALERT] " + " | ".join(parts))

            last_sent = time.time()

        except Exception as e:
            log_line(f"[ALERT] Worker error: {e}")

    log_line("[ALERT] Down-alert worker stopped")