"""
Background camera ping monitor.

Every state.CAMERA_PING_INTERVAL_SECONDS, pings each camera IP registered
in state.OFFLINE_CAMERA_IPS. When a camera responds, it is removed from the
offline list and a toast is shown.

Runs in a daemon thread. Exit signal: state.MONITOR_STOP set.
"""

from datetime import datetime

import state
from logger import log_line
from core.ping import _is_camera_reachable


def _ping_log(text):
    """Write to the Ping panel via state.PING_LOG_LINES + state.UI_QUEUE."""
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


def _refresh_tray():
    try:
        from tray.tray import _refresh_tray_tooltip
        _refresh_tray_tooltip()
    except Exception:
        pass


def _camera_ping_worker():
    """Main loop. Never returns until state.MONITOR_STOP is set."""
    log_line("[CAMERA] Camera-ping worker started")
    _ping_log("[CAMERA] Camera-ping worker started")

    while not state.MONITOR_STOP.is_set():
        try:
            if not state.CAMERA_PING_ENABLED:
                state.MONITOR_STOP.wait(5)
                continue

            # Snapshot the currently-offline cameras
            with state.OFFLINE_CAMERA_LOCK:
                ips = list(state.OFFLINE_CAMERA_IPS.keys())

            if not ips:
                state.UI_QUEUE.put(("stats", None))
                state.MONITOR_STOP.wait(min(state.CAMERA_PING_INTERVAL_SECONDS, 5))
                continue

            recovered = []

            for ip in ips:
                if state.MONITOR_STOP.is_set():
                    break

                with state.OFFLINE_CAMERA_LOCK:
                    info = state.OFFLINE_CAMERA_IPS.get(ip)
                if not info:
                    # Camera was removed while we were iterating
                    continue

                t0 = datetime.now()
                ok = _is_camera_reachable(ip)
                latency = int((datetime.now() - t0).total_seconds() * 1000)

                state.CAMERA_PING_HISTORY[ip] = {
                    "last": datetime.now(),
                    "state": "up" if ok else "down",
                    "latency_ms": latency if ok else None,
                }

                with state.OFFLINE_CAMERA_LOCK:
                    if ip in state.OFFLINE_CAMERA_IPS:
                        state.OFFLINE_CAMERA_IPS[ip]["last_check"] = datetime.now()

                if ok:
                    recovered.append(ip)
                    _ping_log(f"[CAMERA] {ip} replied ({latency} ms) - back online")
                else:
                    _ping_log(f"[CAMERA] {ip} still offline")

            if recovered:
                for ip in recovered:
                    with state.OFFLINE_CAMERA_LOCK:
                        state.OFFLINE_CAMERA_IPS.pop(ip, None)
                _show_toast(
                    "Camera back online",
                    f"{len(recovered)} camera(s) responded: "
                    + ", ".join(recovered[:5])
                    + ("" if len(recovered) <= 5 else " ..."),
                )
                _refresh_tray()

            state.UI_QUEUE.put(("stats", None))
            state.MONITOR_STOP.wait(max(1, state.CAMERA_PING_INTERVAL_SECONDS))

        except Exception as e:
            log_line(f"[CAMERA] Worker error: {e}")
            state.MONITOR_STOP.wait(5)

    log_line("[CAMERA] Camera-ping worker stopped")
    _ping_log("[CAMERA] Camera-ping worker stopped")