"""
Background recovery scan.

When the NVR monitor detects an NVR coming back online, it spawns this
function in a daemon thread. Waits 30 seconds (so the network and NVR web
server have time to settle), then runs a full scan of that one NVR using a
fresh Chrome session, and saves the Excel report.

All UI updates go through state.UI_QUEUE, using the UiQueue* proxies so
this thread never touches Tk widgets directly.
"""

import time
import tkinter as tk

import state
from logger import log_line
from core.chrome import get_chromedriver_path, setup_chrome_driver
from core.nvr_scan import _scan_one_nvr, _fmt_duration
from core.excel import save_excel_report
from core.url_utils import _nvr_host_only


def _ping_log(text):
    """Write a line to the Ping panel and to the log file."""
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


def _background_scan_one_nvr(entry):
    """Run a full scan of one NVR in the background. Never raises.

    Skips silently if a scan is already running (foreground or background).
    """
    if state.scan_running:
        log_line("[MONITOR] A scan is already running - skipping recovery")
        return

    state._background_scan_flag[0] = True
    state.scan_running = True

    # Deferred import of the UI proxies - they live in ui.proxies, and
    # importing that at module load would pull in Tkinter. We only need it
    # inside this function, which runs after the GUI exists.
    from ui.proxies import UiQueueLog, UiQueueTree, UiQueueStatus
    ui_log = UiQueueLog()
    ui_tree = UiQueueTree()
    ui_status = UiQueueStatus()

    t_start = time.time()
    driver = None
    try:
        # --- Driver setup ---
        chromedriver_path = get_chromedriver_path()
        if not chromedriver_path:
            ui_log.insert(tk.END,
                          "[MONITOR] No ChromeDriver - cannot recovery-scan\n")
            return

        options = setup_chrome_driver()
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        driver = webdriver.Chrome(service=Service(chromedriver_path),
                                  options=options)

        # --- Status update ---
        ui_status.config(
            text=f"* Recovery scan: {_nvr_host_only(entry['url'])}",
            fg="#2563eb",  # COLORS["blue"] - hardcoded because state.COLORS
                           # is populated by the GUI at build time.
        )
        ui_log.insert(tk.END, "[MONITOR] Waiting 30s before recovery scan...\n")
        time.sleep(30)

        # --- Run the scan ---
        ui_log.insert(tk.END, f"[MONITOR] Recovery scan for {entry['url']}\n")
        _scan_one_nvr(driver, entry, ui_tree, ui_status, ui_log)

        # --- Save report ---
        try:
            save_excel_report(ui_log)
        except Exception as e:
            ui_log.insert(tk.END,
                          f"[MONITOR] Excel save after recovery failed: {e}\n")

        # --- Done ---
        total = _fmt_duration(time.time() - t_start)
        ui_log.insert(tk.END,
                      f"[DONE] Recovery scan finished - total time {total}\n")
        ui_status.config(text=f"* Recovery scan done - {total}",
                         fg="#059669")  # COLORS["green"]
        _refresh_tray()

    except Exception as e:
        ui_log.insert(tk.END,
                      f"[MONITOR] Recovery scan failed for {entry['url']}: {e}\n")

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        state.scan_running = False
        state._background_scan_flag[0] = False


def _refresh_tray():
    try:
        from tray.tray import _refresh_tray_tooltip
        _refresh_tray_tooltip()
    except Exception:
        pass