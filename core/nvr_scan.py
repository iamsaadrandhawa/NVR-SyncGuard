"""
Full scan of one NVR: login, time sync, camera scan.

Three layers:
  _scan_one_nvr_attempt  - single attempt, no retry
  _scan_one_nvr_inner    - retry loop around the attempt
  _scan_one_nvr          - timing wrapper around the inner (public API)

Retry waits come from state.NVR_RETRY_WAIT_SECONDS; the loop honours
state.stop_requested so the user can abort mid-retry.
"""

import time
import tkinter as tk

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

import state
from core.url_utils import _nvr_host_only
from core.selenium_helpers import _wait
from core.time_sync import _run_time_sync_for_nvr
from core.camera_scan import _run_camera_scan_for_nvr


# Local duration formatter so this module doesn't need core/time_utils.py.
def _fmt_duration(sec):
    sec = int(sec)
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def _scan_one_nvr_attempt(driver, entry, tree, status_label, log):
    """One full attempt: login -> time sync -> camera scan.

    Returns True on success, False on any failure. Never raises.
    """
    nvr_url = entry["url"]
    nvr_host = _nvr_host_only(nvr_url)
    user = entry["username"]
    pwd = entry["password"]

    log.insert(tk.END, f"\n{'=' * 60}\n")
    log.insert(tk.END, f"NVR: {nvr_url}  (user: {user})\n")
    log.insert(tk.END, f"{'=' * 60}\n")

    try:
        try:
            driver.delete_all_cookies()
        except Exception:
            pass

        driver.get(nvr_url)

        # -------- Login --------
        user_el = _wait(
            driver, state.TIMEOUT_LOGIN,
            EC.presence_of_element_located((By.ID, "username")),
            "login username", log,
        )
        if user_el is None:
            log.insert(tk.END, "[ERROR] Username field not found.\n")
            return False
        user_el.clear()
        user_el.send_keys(user)

        pass_el = _wait(
            driver, state.TIMEOUT_LOGIN,
            EC.presence_of_element_located((By.ID, "password")),
            "login password", log,
        )
        if pass_el is None:
            log.insert(tk.END, "[ERROR] Password field not found.\n")
            return False
        pass_el.clear()
        pass_el.send_keys(pwd + Keys.RETURN)
        log.insert(tk.END, "[OK] Logged in\n")

        # -------- Time sync --------
        log.insert(tk.END, "[INFO] Time sync phase...\n")
        _run_time_sync_for_nvr(driver, log)

        # -------- Camera scan --------
        log.insert(tk.END, "[INFO] Camera scan phase...\n")
        _run_camera_scan_for_nvr(driver, nvr_host, log, tree, status_label)
        return True

    except Exception as e:
        first = (str(e).splitlines() or [""])[0][:200]
        log.insert(tk.END, f"[ERROR] NVR attempt failed: {first}\n")
        return False


def _scan_one_nvr_inner(driver, entry, tree, status_label, log):
    """Retry wrapper around _scan_one_nvr_attempt.

    Total attempts = 1 + state.NVR_RETRY_ATTEMPTS. Waits between attempts
    come from state.NVR_RETRY_WAIT_SECONDS (last value repeats if the list
    is shorter than the number of retries). Returns True if any attempt
    succeeded.
    """
    nvr_url = entry["url"]
    total_attempts = max(1, state.NVR_RETRY_ATTEMPTS + 1)

    for attempt in range(1, total_attempts + 1):
        if state.stop_requested:
            log.insert(tk.END, "[INFO] Stop requested - aborting NVR retries.\n")
            return False

        log.insert(tk.END,
                   f"\n>>> Attempt {attempt}/{total_attempts} for {nvr_url}\n")

        ok = _scan_one_nvr_attempt(driver, entry, tree, status_label, log)
        if ok:
            return True

        if attempt < total_attempts:
            idx = min(attempt - 1, len(state.NVR_RETRY_WAIT_SECONDS) - 1)
            wait_s = state.NVR_RETRY_WAIT_SECONDS[idx]
            log.insert(tk.END,
                       f"[RETRY] {nvr_url} failed attempt {attempt}. "
                       f"Waiting {wait_s}s before retry {attempt + 1}...\n")
            # Sleep in 1s slices so stop_requested is honoured promptly
            for _ in range(int(wait_s)):
                if state.stop_requested:
                    log.insert(tk.END,
                               "[INFO] Stop requested during retry wait.\n")
                    return False
                time.sleep(1)

    log.insert(tk.END,
               f"[SKIP] {nvr_url} - all {total_attempts} attempts failed. "
               f"Moving to next NVR.\n")
    return False


def _scan_one_nvr(driver, entry, tree, status_label, log):
    """Public API: runs the inner retry loop and logs the total time taken."""
    t0 = time.time()
    ok = _scan_one_nvr_inner(driver, entry, tree, status_label, log)
    log.insert(tk.END,
               f"[TIME] {entry['url']} took "
               f"{_fmt_duration(time.time() - t0)} "
               f"({'OK' if ok else 'SKIPPED'})\n")
    return ok