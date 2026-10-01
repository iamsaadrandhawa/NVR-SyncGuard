"""
UI-facing actions.

Every command that a button, a menu item, or the tray can trigger lives here:
adding/removing NVRs, saving settings, changing the report folder, starting
the scan, exporting the Excel report, restarting, and exiting.

Widgets are owned by popup dialogs in ui/dialogs_forms.py. Each dialog
assigns its widgets to state.* while it is open, and clears them back to None
when it closes. The guards below check for that None and show a helpful
message if the relevant dialog is not currently open.

Step 3: after every scan, the results are also written to the local SQLite
database (core/cloud/local_db.py) so that the Server panel can display
history across sessions.
"""

import os
import time
import threading
import webbrowser
import tkinter as tk
from tkinter import messagebox, filedialog

import state
from logger import log_line
from ui.theme import COLORS
from ui.dialogs import request_admin_authorization
from core.url_utils import normalize_nvr_url, _nvr_host_only
from core.chrome import find_chrome_path, get_chromedriver_path, setup_chrome_driver
from core.nvr_scan import _scan_one_nvr, _fmt_duration
from core.excel import save_excel_report


# =========================================================
# NVR LIST ACTIONS
# =========================================================
def add_nvr_from_ui():
    if state.nvr_entry is None:
        messagebox.showinfo(
            "Dialog not open",
            "Click '+ Add NVR' on the top bar first."
        )
        return

    raw_url = state.nvr_entry.get()
    raw_user = state.nvr_user_entry.get().strip()
    raw_pass = state.nvr_pass_entry.get()

    try:
        nvr_url = normalize_nvr_url(raw_url)
    except ValueError as error:
        messagebox.showwarning("Check the NVR address", str(error))
        state.nvr_entry.focus_set()
        return

    if not raw_user:
        messagebox.showwarning("Username required",
                               "Enter the username for this NVR.")
        state.nvr_user_entry.focus_set()
        return
    if not raw_pass:
        if not messagebox.askyesno("Password empty",
                                   "Password is empty. Add this NVR anyway?"):
            state.nvr_pass_entry.focus_set()
            return

    for existing in state.NVR_LIST:
        if existing["url"] == nvr_url:
            messagebox.showinfo("Already added", "This NVR is already in the list.")
            return

    state.NVR_LIST.append({
        "url": nvr_url,
        "username": raw_user,
        "password": raw_pass,
    })

    # If the Configure dialog is open, mirror the new entry in its listbox.
    try:
        if state.nvr_listbox is not None:
            state.nvr_listbox.insert(tk.END, f"{nvr_url}  -  {raw_user}")
    except Exception:
        pass

    # Also mirror into the local DB (site-scoped)
    try:
        _mirror_nvr_to_db(nvr_url, raw_user, raw_pass)
    except Exception as e:
        log_line(f"[DB] Could not mirror NVR to local DB: {e}")

    state.nvr_entry.set("")
    state.nvr_user_entry.set("")
    state.nvr_pass_entry.set("")
    state.save_config()
    refresh_nvr_count()


def remove_selected_nvr():
    if state.nvr_listbox is None:
        messagebox.showinfo(
            "Dialog not open",
            "Open 'Configure NVR' first."
        )
        return

    selected = state.nvr_listbox.curselection()
    if not selected:
        messagebox.showinfo("Select an NVR", "Choose an NVR from the list first.")
        return
    index = selected[0]

    if not request_admin_authorization(
        state.root,
        "Removing an NVR requires password approval."
    ):
        return

    removed_url = state.NVR_LIST[index]["url"]
    state.nvr_listbox.delete(index)
    del state.NVR_LIST[index]

    try:
        removed_host = _nvr_host_only(removed_url)
        state.NVR_STATE.pop(removed_host, None)
        state.NVR_PING_HISTORY.pop(removed_host, None)
    except Exception:
        pass

    # Also remove from local DB
    try:
        _remove_nvr_from_db(removed_url)
    except Exception as e:
        log_line(f"[DB] Could not remove NVR from local DB: {e}")

    state.save_config()
    refresh_nvr_count()


def refresh_nvr_count():
    try:
        if state.nvr_count_label is not None:
            state.nvr_count_label.config(text=f"{len(state.NVR_LIST)} configured")
    except Exception:
        pass


# =========================================================
# MISC
# =========================================================
def open_company_website(event=None):
    try:
        webbrowser.open_new(state.CODRAZE_URL)
    except Exception as e:
        messagebox.showerror("Error", f"Could not open website: {str(e)}")


# =========================================================
# SETTINGS
# =========================================================
def save_all_settings():
    if state.date_stamp_var is None:
        messagebox.showinfo(
            "Dialog not open",
            "Open 'Settings' first."
        )
        return

    try:
        if state.date_stamp_var is not None:
            state.USE_DATE_STAMPED_FILES = bool(state.date_stamp_var.get())
    except Exception:
        pass
    try:
        if state.collect_ips_var is not None:
            state.COLLECT_ALL_IPS = bool(state.collect_ips_var.get())
    except Exception:
        pass
    try:
        if state.run_scan_on_launch_var is not None:
            state.RUN_SCAN_ON_LAUNCH = bool(state.run_scan_on_launch_var.get())
    except Exception:
        pass
    try:
        if state.bg_ping_var is not None:
            state.BACKGROUND_PING_MONITOR = bool(state.bg_ping_var.get())
    except Exception:
        pass
    try:
        if state.auto_recovery_var is not None:
            state.AUTO_SCAN_ON_RECOVERY = bool(state.auto_recovery_var.get())
    except Exception:
        pass
    try:
        if state.ping_interval_var is not None:
            val = int(state.ping_interval_var.get())
            val = max(1, min(1440, val))
            state.MONITOR_INTERVAL_MINUTES = val
    except Exception:
        pass

    # Daily restart HH:MM
    try:
        if state.restart_enabled_var is not None:
            state.DAILY_RESTART_ENABLED = bool(state.restart_enabled_var.get())
        if state.restart_time_var is not None:
            hh, mm = state.restart_time_var.get().strip().split(":")
            hh, mm = int(hh), int(mm)
            if not (0 <= hh <= 23 and 0 <= mm <= 59):
                raise ValueError("out of range")
            state.DAILY_RESTART_HOUR = hh
            state.DAILY_RESTART_MINUTE = mm
    except Exception:
        messagebox.showwarning("Invalid time",
                               "Enter the restart time as HH:MM (24h), e.g. 08:30")
        return

    # Down-alert repeat
    try:
        if state.alert_interval_var is not None:
            state.DOWN_ALERT_REPEAT_MINUTES = max(
                1, min(120, int(state.alert_interval_var.get()))
            )
    except Exception:
        pass

    # Persist through config + state
    state.config["USE_DATE_STAMPED_FILES"] = state.USE_DATE_STAMPED_FILES
    state.config["COLLECT_ALL_IPS"] = state.COLLECT_ALL_IPS
    state.config["RUN_SCAN_ON_LAUNCH"] = state.RUN_SCAN_ON_LAUNCH
    state.config["BACKGROUND_PING_MONITOR"] = state.BACKGROUND_PING_MONITOR
    state.config["AUTO_SCAN_ON_RECOVERY"] = state.AUTO_SCAN_ON_RECOVERY
    state.config["MONITOR_INTERVAL_MINUTES"] = state.MONITOR_INTERVAL_MINUTES

    state.save_config()

    messagebox.showinfo(
        "Settings saved",
        f"New file each scan: {'ON' if state.USE_DATE_STAMPED_FILES else 'OFF'}\n"
        f"Collect ALL IPs: {'ON' if state.COLLECT_ALL_IPS else 'OFF'}\n"
        f"Run scan on launch: {'ON' if state.RUN_SCAN_ON_LAUNCH else 'OFF'}\n"
        f"Background ping monitor: {'ON' if state.BACKGROUND_PING_MONITOR else 'OFF'}\n"
        f"Auto-scan on recovery: {'ON' if state.AUTO_SCAN_ON_RECOVERY else 'OFF'}\n"
        f"Ping interval: {state.MONITOR_INTERVAL_MINUTES} min\n"
        f"Daily restart: {'ON' if state.DAILY_RESTART_ENABLED else 'OFF'} "
        f"at {state.DAILY_RESTART_HOUR:02d}:{state.DAILY_RESTART_MINUTE:02d}\n"
        f"Down-alert repeat: {state.DOWN_ALERT_REPEAT_MINUTES} min\n\n"
        "Saved to config.json."
    )


# =========================================================
# REPORT FOLDER
# =========================================================
def change_report_location():
    if not request_admin_authorization(
        state.root,
        "Changing the report folder requires administrator approval."
    ):
        return

    try:
        chosen = filedialog.askdirectory(
            parent=state.root,
            title="Select a folder to save the Excel reports",
            initialdir=(state.DOWNLOADS_DIR
                        if os.path.isdir(state.DOWNLOADS_DIR)
                        else os.path.expanduser("~")),
            mustexist=False,
        )
    except Exception as e:
        messagebox.showerror("Folder chooser failed", str(e), parent=state.root)
        return

    if not chosen:
        return

    chosen = os.path.abspath(chosen)
    try:
        os.makedirs(chosen, exist_ok=True)
    except Exception as e:
        messagebox.showerror(
            "Folder not usable",
            f"Could not create/access this folder:\n{chosen}\n\n{e}",
            parent=state.root,
        )
        return

    state.DOWNLOADS_DIR = chosen
    state.EXCEL_FILE = os.path.join(state.DOWNLOADS_DIR, state.BASE_EXCEL_FILENAME)
    state.config["DOWNLOADS_DIR"] = state.DOWNLOADS_DIR
    state.save_config()

    try:
        state.last_saved_label.config(text=f"Folder: {state.DOWNLOADS_DIR}")
    except Exception:
        pass
    try:
        if state.folder_path_label is not None:
            state.folder_path_label.config(text=state.DOWNLOADS_DIR)
    except Exception:
        pass

    messagebox.showinfo(
        "Report folder updated",
        f"Reports will now be saved in:\n\n{state.DOWNLOADS_DIR}",
        parent=state.root,
    )


def open_reports_folder():
    try:
        folder = state.DOWNLOADS_DIR
        if not os.path.isdir(folder):
            os.makedirs(folder, exist_ok=True)
        os.startfile(folder)
    except Exception as e:
        messagebox.showerror("Could not open folder", str(e), parent=state.root)


# =========================================================
# SCAN START
# =========================================================
def start_all(log, btn, tree, status_label, auto_start=False):
    """Start a scan. If a scan is already running, request a stop instead."""
    if state.scan_running:
        state.stop_requested = True
        btn.set_text("Stopping...")
        return

    if not state.NVR_LIST:
        if not auto_start:
            messagebox.showwarning("No NVRs configured",
                                   "Add at least one NVR before starting a scan.")
        return

    try:
        if state.collect_ips_var is not None:
            state.COLLECT_ALL_IPS = bool(state.collect_ips_var.get())
    except Exception:
        state.COLLECT_ALL_IPS = False

    # -------- Reset scan state --------
    state.stop_requested = False
    state.scan_running = True
    state._background_scan_flag[0] = False
    state.total_nvrs_count = len(state.NVR_LIST)
    state.total_cameras_count = 0
    state.online_cameras_count = 0
    state.offline_cameras_count = 0
    state.camera_data = []
    state.offline_cameras_data = []
    state.CHECKED_NVRS = 0
    state.SKIPPED_NVRS = 0

    state.UI_STATE["running"] = True
    state.UI_STATE["phase"] = "scanning"

    btn.set_text("\u25a0  STOP SCAN")
    btn.set_colors(bg=COLORS["red"], hover=COLORS["red_dark"], active="#991b1b")
    status_label.config(text="* Scanning NVRs...", fg=COLORS["blue"])
    log.delete(1.0, tk.END)
    tree.delete(*tree.get_children())

    def task():
        driver = None
        scan_t0 = time.time()
        try:
            chrome_path = find_chrome_path()
            if not chrome_path:
                log.insert(tk.END, "[ERROR] Google Chrome not found.\n")
                status_label.config(text="* Chrome not found", fg=COLORS["red"])
                return

            log.insert(tk.END,
                       f"[INFO] {state.APP_NAME} v{state.APP_VERSION} "
                       f"by {state.APP_AUTHOR}\n")
            log.insert(tk.END, f"[INFO] Chrome detected: {chrome_path}\n")
            log.insert(tk.END, f"[INFO] {len(state.NVR_LIST)} NVR(s) queued\n")
            log.insert(tk.END,
                       "[INFO] Foreground scan - browser will be visible.\n")
            log.insert(tk.END,
                       f"[INFO] Retry policy: {state.NVR_RETRY_ATTEMPTS} retries, "
                       f"waits {state.NVR_RETRY_WAIT_SECONDS}\n")

            chromedriver_path = get_chromedriver_path(log)
            if not chromedriver_path:
                log.insert(tk.END,
                           "[ERROR] Cannot proceed without ChromeDriver\n")
                return

            options = setup_chrome_driver(log)

            try:
                from selenium import webdriver
                from selenium.webdriver.chrome.service import Service
                service = Service(chromedriver_path)
                driver = webdriver.Chrome(service=service, options=options)
                log.insert(tk.END, "[OK] Chrome started\n")
            except Exception as e:
                log.insert(tk.END, f"[ERROR] Could not start Chrome: {e}\n")
                return

            try:
                for nvr_index, entry in enumerate(state.NVR_LIST):
                    if state.stop_requested:
                        break
                    log.insert(tk.END,
                               f"\n[{nvr_index + 1}/{len(state.NVR_LIST)}] "
                               f"{entry['url']}\n")
                    ok = _scan_one_nvr(driver, entry, tree, status_label, log)
                    if ok:
                        state.NVR_STATE[_nvr_host_only(entry["url"])] = "up"
                        state.CHECKED_NVRS += 1
                    else:
                        state.NVR_STATE[_nvr_host_only(entry["url"])] = "down"
                        state.SKIPPED_NVRS += 1
                    state.UI_QUEUE.put(("stats", None))

                    if (not state.stop_requested
                            and state.TIMEOUT_BETWEEN_NVR > 0):
                        time.sleep(state.TIMEOUT_BETWEEN_NVR)

                if state.camera_data or state.offline_cameras_data:
                    if state.stop_requested:
                        log.insert(tk.END,
                                   "[INFO] Scan stopped - saving partial results...\n")
                    save_excel_report(log)

                # ---------- Save to local DB (Step 3) ----------
                _save_scan_to_local_db(log, scan_t0)

                total_time = _fmt_duration(time.time() - scan_t0)
                log.insert(tk.END,
                           f"\n[DONE] Scan finished - total time {total_time}\n")

                if state.stop_requested:
                    status_label.config(
                        text=f"* Scan stopped by user - {total_time}",
                        fg=COLORS["amber"])
                else:
                    status_label.config(
                        text=f"* Completed in {total_time} - "
                             f"Total {state.total_cameras_count} - "
                             f"Online {state.online_cameras_count} - "
                             f"Offline {state.offline_cameras_count}",
                        fg=COLORS["green"])
                _refresh_tray()
            finally:
                if driver:
                    try:
                        driver.quit()
                    except Exception:
                        pass

        except Exception as error:
            log.insert(tk.END, f"\n[ERROR] Scan failed: {error}\n")
            status_label.config(text="* Scan ended with an error",
                                fg=COLORS["red"])
        finally:
            state.scan_running = False
            state.UI_STATE["running"] = bool(state.BACKGROUND_PING_MONITOR)
            state.UI_STATE["phase"] = ("monitoring"
                                       if state.BACKGROUND_PING_MONITOR
                                       else "idle")
            state.UI_QUEUE.put(("stats", None))
            try:
                state.root.after(0, lambda: (
                    btn.set_text("\u25b6  START SCAN"),
                    btn.set_colors(bg=COLORS["blue"],
                                   hover=COLORS["blue_dark"],
                                   active="#1e40af"),
                    btn.set_state("normal"),
                ))
            except Exception:
                pass

    threading.Thread(target=task, daemon=True).start()


# =========================================================
# EXPORT
# =========================================================
def export_report(log_widget):
    if not state.camera_data:
        messagebox.showinfo("Nothing to export",
                            "Run a camera scan first, then export its results.")
        return
    if save_excel_report(log_widget):
        messagebox.showinfo("Excel exported",
                            f"Report saved to:\n{state.last_saved_file}")


# =========================================================
# RESTART / EXIT  (called from ui/window.py)
# =========================================================
def _refresh_tray():
    try:
        from tray.tray import _refresh_tray_tooltip
        _refresh_tray_tooltip()
    except Exception:
        pass


def restart_app():
    if not messagebox.askyesno(
        "Restart NVR SyncGuard",
        "Restart the application now?\n\n"
        "The current window will close and the app will relaunch.",
    ):
        return
    try:
        state.MONITOR_STOP.set()
    except Exception:
        pass
    try:
        from core.relaunch import _spawn_new_instance
        _spawn_new_instance()
    except Exception as e:
        log_line(f"[RESTART] Failed to relaunch: {e}")
    try:
        if state.TRAY_ICON is not None:
            state.TRAY_ICON.stop()
    except Exception:
        pass
    try:
        state.root.destroy()
    except Exception:
        pass
    os._exit(0)


def full_exit():
    if not messagebox.askyesno(
        "Exit NVR SyncGuard",
        "Exit fully?\n\nBackground ping monitoring and the tray icon will stop.",
    ):
        return
    try:
        state.MONITOR_STOP.set()
    except Exception:
        pass
    try:
        if state.TRAY_ICON is not None:
            state.TRAY_ICON.stop()
    except Exception:
        pass
    try:
        state.root.destroy()
    except Exception:
        pass
    log_line("[APP] Full exit")
    try:
        time.sleep(0.4)
        os._exit(0)
    except Exception:
        pass


# =========================================================
# LOCAL DB HELPERS (Step 3)
# =========================================================
def _ensure_local_site():
    """Return the local site id, creating one if needed.

    On first run, the site is named after the PC (hostname). Its id is
    saved in state.LOCAL_SITE_ID and in config.
    """
    try:
        import socket
        from core.cloud import local_db

        # Already set in state?
        sid = getattr(state, "LOCAL_SITE_ID", "") or ""
        if sid:
            return sid

        # Check config
        sid = state.config.get("LOCAL_SITE_ID", "")
        if sid:
            state.LOCAL_SITE_ID = sid
            return sid

        # Check DB - is there exactly one site already?
        existing = local_db.get_all_sites()
        if existing:
            sid = existing[0]["id"]
            state.LOCAL_SITE_ID = sid
            state.LOCAL_SITE_NAME = existing[0]["name"]
            try:
                state.config["LOCAL_SITE_ID"] = sid
                state.save_config()
            except Exception:
                pass
            return sid

        # Create a new site named after the PC
        try:
            pc_name = socket.gethostname()
        except Exception:
            pc_name = "Unknown-PC"

        sid = local_db.insert_site(
            name=pc_name,
            location="",
            pc_name=pc_name,
        )
        if sid:
            state.LOCAL_SITE_ID = sid
            state.LOCAL_SITE_NAME = pc_name
            try:
                state.config["LOCAL_SITE_ID"] = sid
                state.save_config()
            except Exception:
                pass
        return sid
    except Exception as e:
        log_line(f"[DB] _ensure_local_site failed: {e}")
        return ""


def _save_scan_to_local_db(log, scan_started_time):
    """Persist the just-finished scan to the local SQLite DB.

    Called after every scan (complete or partial). Errors are logged but
    never propagate to the UI.
    """
    try:
        from datetime import datetime
        from core.cloud.reports import save_scan_to_db

        site_id = _ensure_local_site()
        if not site_id:
            log.insert(tk.END,
                       "[DB] Could not determine site - scan not saved.\n")
            return

        started = datetime.fromtimestamp(scan_started_time).strftime(
            "%Y-%m-%d %H:%M:%S")
        finished = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        report_id = save_scan_to_db(
            site_id=site_id,
            started_at=started,
            finished_at=finished,
            total_nvrs=state.total_nvrs_count,
            total_cameras=state.total_cameras_count,
            online_cameras=state.online_cameras_count,
            offline_cameras=state.offline_cameras_count,
            excel_path=state.last_saved_file or "",
            camera_rows=list(state.camera_data or []),
        )

        if report_id:
            state.LAST_DB_REPORT_ID = report_id
            log.insert(tk.END,
                       f"[DB] Scan saved locally (report {report_id[:8]}...)\n")
        else:
            log.insert(tk.END, "[DB] Failed to save scan locally.\n")
    except Exception as e:
        try:
            log.insert(tk.END, f"[DB] Local save error: {e}\n")
        except Exception:
            pass


def _mirror_nvr_to_db(url, username, password):
    """Insert an NVR into the local DB under the current local site."""
    try:
        from core.cloud import local_db
        site_id = _ensure_local_site()
        if not site_id:
            return
        # Skip if already present
        existing = local_db.get_nvrs_for_site(site_id)
        for n in existing:
            if n["url"] == url:
                return
        local_db.insert_nvr(
            site_id=site_id,
            url=url,
            username=username,
            password_encrypted="",  # encryption comes in a later step
        )
    except Exception as e:
        log_line(f"[DB] _mirror_nvr_to_db failed: {e}")


def _remove_nvr_from_db(url):
    """Delete an NVR from the local DB by URL."""
    try:
        from core.cloud import local_db
        site_id = getattr(state, "LOCAL_SITE_ID", "") or ""
        if not site_id:
            return
        for n in local_db.get_nvrs_for_site(site_id):
            if n["url"] == url:
                local_db.delete_nvr(n["id"])
                return
    except Exception as e:
        log_line(f"[DB] _remove_nvr_from_db failed: {e}")