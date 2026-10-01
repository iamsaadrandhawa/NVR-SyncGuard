"""
Background NVR ping monitor.

Every state.MONITOR_INTERVAL_SECONDS, pings every configured NVR in parallel
using a TCP connect to the web port. Updates state.NVR_STATE and
state.NVR_PING_HISTORY, shows toasts on up/down transitions, and (when
state.AUTO_SCAN_ON_RECOVERY is True) launches a recovery scan for any NVR
that comes back online.

Runs in a daemon thread. Exit signal: state.MONITOR_STOP set.
"""

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import state
from logger import log_line
from core.ping import _is_nvr_reachable
from core.url_utils import _nvr_host_only


def _ping_log(text):
    """Local helper - writes to the Ping panel via state.PING_LOG_LINES
    and pushes a UI update through state.UI_QUEUE."""
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} {text}"
        state.PING_LOG_LINES.append(line)
        if len(state.PING_LOG_LINES) > state.PING_LOG_MAX:
            del state.PING_LOG_LINES[:len(state.PING_LOG_LINES) - state.PING_LOG_MAX]
        state.UI_QUEUE.put(("ping_log", line))
    except Exception:
        pass


def _ping_one_nvr(entry):
    """Worker function for the thread pool. Returns (entry, host, ok, ms)."""
    url = entry["url"]
    t0 = datetime.now()
    ok = _is_nvr_reachable(url)
    ms = int((datetime.now() - t0).total_seconds() * 1000)
    return entry, _nvr_host_only(url), ok, ms


def _monitor_worker():
    """Main loop for the background NVR ping monitor. Never returns until
    state.MONITOR_STOP is set."""
    log_line("[MONITOR] Background ping monitor started")
    _ping_log("[MONITOR] Background ping monitor started")

    while not state.MONITOR_STOP.is_set():
        try:
            if not state.BACKGROUND_PING_MONITOR:
                state.MONITOR_STOP.wait(15)
                continue

            entries = list(state.NVR_LIST)
            if not entries:
                state.MONITOR_STOP.wait(30)
                continue

            _ping_log(f"[MONITOR] Ping check on {len(entries)} NVR(s)...")

            # Parallel ping
            with ThreadPoolExecutor(max_workers=min(16, len(entries))) as ex:
                results = list(ex.map(_ping_one_nvr, entries))

            for entry, nvr_id, reachable, latency in results:
                if state.MONITOR_STOP.is_set():
                    break

                now_state = "up" if reachable else "down"
                state.NVR_PING_HISTORY[nvr_id] = {
                    "last": datetime.now(),
                    "state": now_state,
                    "latency_ms": latency if reachable else None,
                }
                _ping_log(
                    f"[PING] {nvr_id}: "
                    + (f"UP ({latency} ms)" if reachable else "DOWN (no reply)")
                )

                prev = state.NVR_STATE.get(nvr_id)
                if prev is None:
                    # First observation - record silently, toast only if down
                    state.NVR_STATE[nvr_id] = now_state
                    if now_state == "down":
                        _show_toast("NVR DOWN", f"{nvr_id} is not responding.")
                    continue

                if prev == "up" and now_state == "down":
                    state.NVR_STATE[nvr_id] = "down"
                    _show_toast("NVR DOWN", f"{nvr_id} is not responding.")
                    _refresh_tray()

                elif prev == "down" and now_state == "up":
                    state.NVR_STATE[nvr_id] = "up"
                    _ping_log(f"[MONITOR] {nvr_id}: BACK ONLINE ({latency} ms)")
                    _show_toast(
                        "NVR BACK ONLINE",
                        f"{nvr_id} is reachable."
                        + (" Syncing now..." if state.AUTO_SCAN_ON_RECOVERY
                           else " (recovery scan disabled)"),
                    )
                    _refresh_tray()

                    if state.AUTO_SCAN_ON_RECOVERY:
                        # Lazy import to avoid a circular import at module load
                        from workers.recovery import _background_scan_one_nvr
                        threading.Thread(
                            target=_background_scan_one_nvr,
                            args=(entry,),
                            daemon=True,
                        ).start()

            state.UI_QUEUE.put(("stats", None))
            state.MONITOR_STOP.wait(max(5, state.MONITOR_INTERVAL_SECONDS))

        except Exception as e:
            log_line(f"[MONITOR] Worker error: {e}")
            state.MONITOR_STOP.wait(10)

    log_line("[MONITOR] Background ping monitor stopped")
    _ping_log("[MONITOR] Background ping monitor stopped")


# -----------------------------------------------------------------
# Thin wrappers so this module doesn't import UI code at load time.
# -----------------------------------------------------------------
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