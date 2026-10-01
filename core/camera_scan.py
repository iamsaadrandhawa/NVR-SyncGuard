"""
Camera scan for a single NVR.

Runs after time_sync in the same session: navigates to
Configuration -> Camera Settings, reads the camera table, and for each
row extracts the camera name/IP and status. Updates state counters,
pushes rows into the Treeview, and registers offline cameras for the
background ping worker.
"""

import tkinter as tk
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

import state
from core.selenium_helpers import _wait, _any_clickable, _safe_click, _small_buffer
from core.camera_extract import extract_camera_ip_from_row, extract_camera_name_from_row


def _register_offline_camera(ip, nvr_host="", name=""):
    """Add a camera IP to the offline watch list. Idempotent."""
    from core.url_utils import is_ipv4
    if not ip or not is_ipv4(ip):
        return
    with state.OFFLINE_CAMERA_LOCK:
        if ip not in state.OFFLINE_CAMERA_IPS:
            state.OFFLINE_CAMERA_IPS[ip] = {
                "since": datetime.now(),
                "last_check": None,
                "nvr": nvr_host,
                "name": name,
            }
            from logger import log_line
            log_line(f"[CAMERA] Registered offline camera {ip} ({name})")


def _run_camera_scan_for_nvr(driver, nvr_host, log, tree, status_label):
    """Do the full camera-scan flow for one NVR. Never raises."""
    try:
        # -------- 1) Configuration --------
        cfg_el = _wait(
            driver, state.TIMEOUT_CONFIG_CLICK,
            _any_clickable(
                "//a[contains(text(),'Configuration')]",
                "//a[@ng-click=\"jumpTo('config')\"]",
            ),
            "Configuration link", log,
        )
        if cfg_el is None:
            log.insert(tk.END, "[ERROR] Configuration not found.\n")
            return
        if not _safe_click(driver, cfg_el, log, "Configuration"):
            log.insert(tk.END, "[ERROR] Configuration click failed.\n")
            return
        _small_buffer(log)

        # -------- 2) Camera Settings --------
        cs_el = _wait(
            driver, state.TIMEOUT_CAMERA_MENU,
            _any_clickable(
                '//*[@id="menu"]/div/div[2]/div[5]',
                "//div[contains(text(),'Camera Settings')]",
                "//*[contains(text(),'Camera') and contains(text(),'Settings')]",
            ),
            "Camera Settings", log,
        )
        if cs_el is None:
            log.insert(tk.END, "[ERROR] Camera Settings not found.\n")
            return
        if not _safe_click(driver, cs_el, log, "Camera Settings"):
            log.insert(tk.END, "[ERROR] Camera Settings click failed.\n")
            return
        _small_buffer(log)

        # -------- 3) Wait for the camera table --------
        table = _wait(
            driver, state.TIMEOUT_CAMERA_TABLE,
            EC.presence_of_element_located((By.ID, "tableDigitalChannels")),
            "camera table", log,
        )

        camera_rows = []
        if table is not None:
            _wait(
                driver, state.TIMEOUT_CAMERA_TABLE,
                lambda d: len(d.find_elements(
                    By.XPATH,
                    "//*[@id='tableDigitalChannels']//div[contains(@class,'row')]"
                )) > 0,
                "first camera row", log,
            )
            try:
                camera_rows = table.find_elements(
                    By.XPATH, ".//div[contains(@class, 'row')]")
                log.insert(tk.END, f"[OK] Found {len(camera_rows)} cameras\n")
            except Exception:
                camera_rows = []

        # Fallback selector if the primary one missed
        if not camera_rows:
            try:
                camera_rows = driver.find_elements(
                    By.CLASS_NAME, "digital-channel-item")
                if camera_rows:
                    log.insert(tk.END,
                               f"[OK] Found {len(camera_rows)} cameras (fallback)\n")
            except Exception:
                camera_rows = []

        if not camera_rows:
            log.insert(tk.END, "[ERROR] No cameras found.\n")
            return

        # -------- 4) Iterate cameras --------
        checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        nvr_cameras = 0
        nvr_online = 0
        nvr_offline = 0

        for i, row in enumerate(camera_rows):
            if state.stop_requested:
                break
            try:
                camera_ip = extract_camera_ip_from_row(row, nvr_host) or ""
                camera_name = extract_camera_name_from_row(row, camera_ip)
                if camera_name == "Name unavailable":
                    camera_name = f"Camera {i + 1}"

                row_text = row.text.lower()
                status = "Online"
                if any(w in row_text for w in ["offline", "disconnect"]):
                    status = "Offline"
                    nvr_offline += 1
                elif any(w in row_text for w in ["abnormal", "error"]):
                    status = "Abnormal"
                    nvr_offline += 1
                else:
                    nvr_online += 1

                record = {
                    "nvr_ip": nvr_host,
                    "camera_name": camera_name,
                    "camera_ip": camera_ip,
                    "status": status,
                    "checked_at": checked_at,
                }
                state.camera_data.append(record)

                if status in ("Offline", "Abnormal"):
                    state.offline_cameras_data.append(record)
                    try:
                        tree.insert(
                            "", tk.END,
                            values=(len(state.offline_cameras_data),
                                    camera_name, camera_ip,
                                    status, nvr_host),
                            tags=(("offline",) if status == "Offline"
                                  else ("abnormal",)),
                        )
                    except Exception:
                        pass
                    log.insert(tk.END,
                               f"[WARN] {camera_name} | {camera_ip} - {status}\n")
                    if state.CAMERA_PING_ENABLED and camera_ip:
                        _register_offline_camera(camera_ip, nvr_host, camera_name)
                else:
                    log.insert(tk.END,
                               f"[OK] {camera_name} | {camera_ip} - Online\n")

                nvr_cameras += 1
            except Exception:
                continue

        # -------- 5) Update global counters --------
        state.total_cameras_count += nvr_cameras
        state.online_cameras_count += nvr_online
        state.offline_cameras_count += nvr_offline

        log.insert(tk.END,
                   f"\nSummary: {nvr_cameras} total, "
                   f"{nvr_online} online, {nvr_offline} offline/abnormal\n")
        try:
            status_label.config(
                text=f"Status: {state.total_cameras_count} total - "
                     f"{state.online_cameras_count} online - "
                     f"{state.offline_cameras_count} offline"
            )
        except Exception:
            pass

        # Refresh tray tooltip if the tray is up
        try:
            from tray.tray import _refresh_tray_tooltip
            _refresh_tray_tooltip()
        except Exception:
            pass

    except Exception as e:
        log.insert(tk.END, f"[ERROR] Camera scan failed: {e}\n")