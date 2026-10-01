"""
Popup form dialogs for the top nav bar.

Each function opens a non-modal Toplevel window with a self-contained form.
While a dialog is open, its widgets are assigned to state.* so that
actions.py finds them the same way it did when they lived in the left panel.

Exposed:
    open_add_nvr_dialog()
    open_configure_nvr_dialog()
    open_settings_dialog()
    open_reports_dialog()
    open_about_dialog()
    open_add_site_dialog(on_saved=None)
    close_all_dialogs()
"""

import tkinter as tk

import state
from ui.theme import COLORS
from ui.widgets import RoundedFrame, RoundedButton, RoundedEntry


_OPEN = {}


# =========================================================
# SHARED HELPERS
# =========================================================
def _center(dlg, parent, w, h):
    dlg.update_idletasks()
    try:
        if parent is not None and parent.winfo_exists():
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
            ph = parent.winfo_height()
            x = px + (pw - w) // 2
            y = py + (ph - h) // 3
        else:
            x = (dlg.winfo_screenwidth() - w) // 2
            y = (dlg.winfo_screenheight() - h) // 3
        dlg.geometry(f"{w}x{h}+{x}+{y}")
    except Exception:
        pass


def _bring_to_front(dlg):
    try:
        dlg.deiconify()
        dlg.lift()
        dlg.focus_force()
    except Exception:
        pass


def _new_dialog(key, title, parent, width, height, resizable=False):
    existing = _OPEN.get(key)
    if existing is not None:
        try:
            if existing.winfo_exists():
                _bring_to_front(existing)
                return None
        except Exception:
            pass

    dlg = tk.Toplevel(parent) if parent else tk.Toplevel()
    dlg.title(title)
    dlg.configure(bg=COLORS["card"])
    dlg.resizable(resizable, resizable)
    dlg.transient(parent)
    dlg.minsize(320, 240)

    _OPEN[key] = dlg
    _center(dlg, parent, width, height)
    return dlg


def _on_dialog_close(key, clear_state=()):
    dlg = _OPEN.pop(key, None)
    for attr in clear_state:
        try:
            setattr(state, attr, None)
        except Exception:
            pass
    try:
        if dlg is not None and dlg.winfo_exists():
            dlg.destroy()
    except Exception:
        pass


def close_all_dialogs():
    for key in list(_OPEN.keys()):
        try:
            dlg = _OPEN.pop(key, None)
            if dlg is not None and dlg.winfo_exists():
                dlg.destroy()
        except Exception:
            pass


# =========================================================
# ADD NVR DIALOG
# =========================================================
def open_add_nvr_dialog():
    parent = state.root
    dlg = _new_dialog("add_nvr", "Add NVR", parent, 400, 400)
    if dlg is None:
        return

    def close():
        _on_dialog_close("add_nvr",
                         clear_state=("nvr_entry", "nvr_user_entry",
                                      "nvr_pass_entry"))

    dlg.protocol("WM_DELETE_WINDOW", close)

    body = tk.Frame(dlg, bg=COLORS["card"])
    body.pack(fill=tk.BOTH, expand=True, padx=22, pady=20)

    tk.Label(body, text="ADD NEW NVR", bg=COLORS["card"], fg=COLORS["ink"],
             font=("Segoe UI", 14, "bold")).pack(anchor="w")
    tk.Label(body, text="Fill the fields, then click Add NVR.",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 14))

    tk.Label(body, text="IP ADDRESS / HOST / URL",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 5))
    nvr_entry = RoundedEntry(body, radius=10, width=340, height=42)
    nvr_entry.pack(fill=tk.X)

    tk.Label(body, text="USERNAME",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(10, 5))
    nvr_user_entry = RoundedEntry(body, radius=10, width=340, height=42)
    nvr_user_entry.pack(fill=tk.X)
    nvr_user_entry.set("admin")

    tk.Label(body, text="PASSWORD",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(10, 5))
    pwd_row = tk.Frame(body, bg=COLORS["card"])
    pwd_row.pack(fill=tk.X)
    nvr_pass_entry = RoundedEntry(pwd_row, radius=10, width=290,
                                  height=42, show="\u25cf")
    nvr_pass_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def toggle_pwd():
        cur = nvr_pass_entry.entry.cget("show")
        nvr_pass_entry.entry.config(show="" if cur else "\u25cf")

    RoundedButton(pwd_row, text="\U0001f441", command=toggle_pwd,
                  bg="#f1f5f9", fg=COLORS["ink"],
                  hover_bg="#e2e8f0", active_bg="#cbd5e1",
                  width=42, height=42, font=("Segoe UI", 12)
                  ).pack(side=tk.LEFT, padx=(8, 0))

    state.nvr_entry = nvr_entry
    state.nvr_user_entry = nvr_user_entry
    state.nvr_pass_entry = nvr_pass_entry

    actions_row = tk.Frame(body, bg=COLORS["card"])
    actions_row.pack(fill=tk.X, pady=(18, 0))

    def do_add():
        from actions import add_nvr_from_ui
        add_nvr_from_ui()

    def do_change_pwd():
        from ui.dialogs import _open_change_password_dialog
        _open_change_password_dialog(dlg)

    RoundedButton(actions_row, text="+  ADD NVR", command=do_add,
                  bg=COLORS["blue"], hover_bg=COLORS["blue_dark"],
                  active_bg="#1e40af", width=200, height=42,
                  font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)

    RoundedButton(actions_row, text="\U0001f512",
                  command=do_change_pwd,
                  bg="#f1f5f9", fg=COLORS["ink"],
                  hover_bg="#e2e8f0", active_bg="#cbd5e1",
                  width=42, height=42, font=("Segoe UI", 13, "bold")
                  ).pack(side=tk.LEFT, padx=(8, 0))


# =========================================================
# CONFIGURE NVR DIALOG
# =========================================================
def open_configure_nvr_dialog():
    parent = state.root
    dlg = _new_dialog("configure_nvr", "Configure NVR", parent, 460, 460)
    if dlg is None:
        return

    def close():
        _on_dialog_close("configure_nvr",
                         clear_state=("nvr_listbox", "nvr_count_label"))

    dlg.protocol("WM_DELETE_WINDOW", close)

    body = tk.Frame(dlg, bg=COLORS["card"])
    body.pack(fill=tk.BOTH, expand=True, padx=22, pady=20)

    header = tk.Frame(body, bg=COLORS["card"])
    header.pack(fill=tk.X, pady=(0, 6))
    tk.Label(header, text="CONFIGURE NVR", bg=COLORS["card"], fg=COLORS["ink"],
             font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)
    nvr_count_label = tk.Label(header,
                               text=f"{len(state.NVR_LIST)} configured",
                               bg=COLORS["card"], fg=COLORS["muted"],
                               font=("Segoe UI", 9))
    nvr_count_label.pack(side=tk.RIGHT)

    tk.Label(body, text="Select an NVR to remove it.",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 10))

    list_wrap = RoundedFrame(body, radius=10, bg="#f8fafc",
                             border=COLORS["line"], padding=6,
                             width=400, height=280)
    list_wrap.pack(fill=tk.BOTH, expand=True)

    nvr_listbox = tk.Listbox(list_wrap.inner, font=("Consolas", 9),
                             bg="#f8fafc", fg=COLORS["ink"], relief=tk.FLAT,
                             selectbackground=COLORS["blue"],
                             selectforeground="#ffffff",
                             activestyle="none", highlightthickness=0)
    nvr_listbox.pack(fill=tk.BOTH, expand=True)
    for entry in state.NVR_LIST:
        nvr_listbox.insert(tk.END, f"{entry['url']}  -  {entry['username']}")

    state.nvr_listbox = nvr_listbox
    state.nvr_count_label = nvr_count_label

    def do_remove():
        from actions import remove_selected_nvr
        remove_selected_nvr()
        try:
            nvr_count_label.config(text=f"{len(state.NVR_LIST)} configured")
        except Exception:
            pass

    RoundedButton(body, text="\U0001f512  Remove selected (password)",
                  command=do_remove,
                  bg=COLORS["red_pale"], fg=COLORS["red_dark"],
                  hover_bg="#fee2e2", active_bg="#fecaca",
                  width=280, height=38,
                  font=("Segoe UI", 9, "bold")
                  ).pack(anchor="w", pady=(12, 0))


# =========================================================
# SETTINGS DIALOG
# =========================================================
def open_settings_dialog():
    parent = state.root
    dlg = _new_dialog("settings", "Settings", parent, 460, 620,
                      resizable=True)
    if dlg is None:
        return

    def close():
        _on_dialog_close("settings",
                         clear_state=("date_stamp_var", "collect_ips_var",
                                      "run_scan_on_launch_var", "bg_ping_var",
                                      "auto_recovery_var", "ping_interval_var",
                                      "restart_enabled_var", "restart_time_var",
                                      "alert_interval_var", "folder_path_label"))

    dlg.protocol("WM_DELETE_WINDOW", close)

    body = tk.Frame(dlg, bg=COLORS["card"])
    body.pack(fill=tk.BOTH, expand=True, padx=22, pady=20)

    tk.Label(body, text="SETTINGS", bg=COLORS["card"], fg=COLORS["ink"],
             font=("Segoe UI", 14, "bold")).pack(anchor="w")

    folder_line = tk.Frame(body, bg=COLORS["card"])
    folder_line.pack(fill=tk.X, pady=(12, 8))
    tk.Label(folder_line, text="\U0001f4c1", bg=COLORS["card"],
             fg=COLORS["muted"],
             font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=(0, 6))
    folder_path_lbl = tk.Label(folder_line, text=state.DOWNLOADS_DIR,
                               bg=COLORS["card"], fg=COLORS["ink"],
                               font=("Consolas", 8),
                               anchor="w", justify="left", wraplength=200)
    folder_path_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
    state.folder_path_label = folder_path_lbl

    def do_change_folder():
        from actions import change_report_location
        change_report_location()
        try:
            folder_path_lbl.config(text=state.DOWNLOADS_DIR)
        except Exception:
            pass

    def do_open_folder():
        from actions import open_reports_folder
        open_reports_folder()

    RoundedButton(folder_line, text="\U0001f512 Change",
                  command=do_change_folder,
                  bg="#f1f5f9", fg=COLORS["ink"],
                  hover_bg="#e2e8f0", active_bg="#cbd5e1",
                  width=80, height=28,
                  font=("Segoe UI", 8, "bold")
                  ).pack(side=tk.LEFT, padx=(6, 0))
    RoundedButton(folder_line, text="\U0001f4c2 Open",
                  command=do_open_folder,
                  bg="#eff6ff", fg="#1d4ed8",
                  hover_bg="#dbeafe", active_bg="#bfdbfe",
                  width=70, height=28,
                  font=("Segoe UI", 8, "bold")
                  ).pack(side=tk.LEFT, padx=(6, 0))

    checks_line = tk.Frame(body, bg=COLORS["card"])
    checks_line.pack(fill=tk.X, pady=(6, 8))

    date_stamp_var = tk.BooleanVar(value=state.USE_DATE_STAMPED_FILES)
    tk.Checkbutton(checks_line, text="New file each scan",
                   variable=date_stamp_var,
                   bg=COLORS["card"], fg=COLORS["ink"],
                   activebackground=COLORS["card"],
                   selectcolor="#ffffff",
                   font=("Segoe UI", 9),
                   anchor="w", justify="left").pack(side=tk.LEFT)

    collect_ips_var = tk.BooleanVar(value=state.COLLECT_ALL_IPS)
    tk.Checkbutton(checks_line, text="Collect ALL IPs",
                   variable=collect_ips_var,
                   bg=COLORS["card"], fg=COLORS["ink"],
                   activebackground=COLORS["card"],
                   selectcolor="#ffffff",
                   font=("Segoe UI", 9),
                   anchor="w", justify="left").pack(side=tk.LEFT, padx=(16, 0))

    tk.Label(body, text="Background monitor",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(6, 2))

    bg_checks = tk.Frame(body, bg=COLORS["card"])
    bg_checks.pack(fill=tk.X, pady=(0, 6))

    run_scan_on_launch_var = tk.BooleanVar(value=state.RUN_SCAN_ON_LAUNCH)
    tk.Checkbutton(bg_checks, text="Run scan on launch",
                   variable=run_scan_on_launch_var,
                   bg=COLORS["card"], fg=COLORS["ink"],
                   activebackground=COLORS["card"],
                   selectcolor="#ffffff",
                   font=("Segoe UI", 9),
                   anchor="w", justify="left").pack(anchor="w")

    bg_ping_var = tk.BooleanVar(value=state.BACKGROUND_PING_MONITOR)
    tk.Checkbutton(bg_checks, text="Background ping monitor",
                   variable=bg_ping_var,
                   bg=COLORS["card"], fg=COLORS["ink"],
                   activebackground=COLORS["card"],
                   selectcolor="#ffffff",
                   font=("Segoe UI", 9),
                   anchor="w", justify="left").pack(anchor="w")

    auto_recovery_var = tk.BooleanVar(value=state.AUTO_SCAN_ON_RECOVERY)
    tk.Checkbutton(bg_checks, text="Auto-scan on recovery",
                   variable=auto_recovery_var,
                   bg=COLORS["card"], fg=COLORS["ink"],
                   activebackground=COLORS["card"],
                   selectcolor="#ffffff",
                   font=("Segoe UI", 9),
                   anchor="w", justify="left").pack(anchor="w")

    interval_row = tk.Frame(body, bg=COLORS["card"])
    interval_row.pack(fill=tk.X, pady=(6, 6))
    tk.Label(interval_row, text="Ping interval (minutes):",
             bg=COLORS["card"], fg=COLORS["ink"],
             font=("Segoe UI", 9)).pack(side=tk.LEFT)
    ping_interval_var = tk.StringVar(value=str(state.MONITOR_INTERVAL_MINUTES))
    tk.Entry(interval_row, textvariable=ping_interval_var, width=6,
             font=("Segoe UI", 9), justify="center",
             bg="#f1f5f9", relief=tk.FLAT
             ).pack(side=tk.LEFT, padx=(6, 0), ipady=3)

    restart_row = tk.Frame(body, bg=COLORS["card"])
    restart_row.pack(fill=tk.X, pady=(4, 6))
    restart_enabled_var = tk.BooleanVar(value=state.DAILY_RESTART_ENABLED)
    tk.Checkbutton(restart_row, text="Daily restart at",
                   variable=restart_enabled_var,
                   bg=COLORS["card"], fg=COLORS["ink"],
                   activebackground=COLORS["card"],
                   selectcolor="#ffffff",
                   font=("Segoe UI", 9),
                   anchor="w", justify="left").pack(side=tk.LEFT)
    restart_time_var = tk.StringVar(
        value=f"{state.DAILY_RESTART_HOUR:02d}:{state.DAILY_RESTART_MINUTE:02d}")
    tk.Entry(restart_row, textvariable=restart_time_var, width=7,
             font=("Segoe UI", 9), justify="center",
             bg="#f1f5f9", relief=tk.FLAT
             ).pack(side=tk.LEFT, padx=(6, 0), ipady=3)
    tk.Label(restart_row, text="(HH:MM, 24h)",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=(6, 0))

    alert_row = tk.Frame(body, bg=COLORS["card"])
    alert_row.pack(fill=tk.X, pady=(0, 6))
    tk.Label(alert_row, text="Repeat down-alert (minutes):",
             bg=COLORS["card"], fg=COLORS["ink"],
             font=("Segoe UI", 9)).pack(side=tk.LEFT)
    alert_interval_var = tk.StringVar(value=str(state.DOWN_ALERT_REPEAT_MINUTES))
    tk.Entry(alert_row, textvariable=alert_interval_var, width=6,
             font=("Segoe UI", 9), justify="center",
             bg="#f1f5f9", relief=tk.FLAT
             ).pack(side=tk.LEFT, padx=(6, 0), ipady=3)

    state.date_stamp_var = date_stamp_var
    state.collect_ips_var = collect_ips_var
    state.run_scan_on_launch_var = run_scan_on_launch_var
    state.bg_ping_var = bg_ping_var
    state.auto_recovery_var = auto_recovery_var
    state.ping_interval_var = ping_interval_var
    state.restart_enabled_var = restart_enabled_var
    state.restart_time_var = restart_time_var
    state.alert_interval_var = alert_interval_var

    def do_save():
        from actions import save_all_settings
        save_all_settings()

    RoundedButton(body, text="\U0001f4be  Save settings",
                  command=do_save,
                  bg="#2563eb", fg="#ffffff",
                  hover_bg="#1d4ed8", active_bg="#1e40af",
                  width=200, height=36,
                  font=("Segoe UI", 9, "bold")
                  ).pack(anchor="w", pady=(14, 0))


# =========================================================
# REPORTS DIALOG
# =========================================================
def open_reports_dialog():
    parent = state.root
    dlg = _new_dialog("reports", "Reports", parent, 400, 240)
    if dlg is None:
        return

    def close():
        _on_dialog_close("reports")

    dlg.protocol("WM_DELETE_WINDOW", close)

    body = tk.Frame(dlg, bg=COLORS["card"])
    body.pack(fill=tk.BOTH, expand=True, padx=22, pady=20)

    tk.Label(body, text="REPORTS", bg=COLORS["card"], fg=COLORS["ink"],
             font=("Segoe UI", 14, "bold")).pack(anchor="w")
    tk.Label(body, text="Open or change the Excel report folder.",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 16))

    def do_open():
        from actions import open_reports_folder
        open_reports_folder()

    def do_change():
        from actions import change_report_location
        change_report_location()

    def do_export():
        from actions import export_report
        export_report(state.log)

    RoundedButton(body, text="\U0001f4c2  Open reports folder",
                  command=do_open,
                  bg="#eff6ff", fg="#1d4ed8",
                  hover_bg="#dbeafe", active_bg="#bfdbfe",
                  width=340, height=40,
                  font=("Segoe UI", 10, "bold")
                  ).pack(anchor="w", pady=(0, 8))

    RoundedButton(body, text="\U0001f512  Change report folder",
                  command=do_change,
                  bg="#f1f5f9", fg=COLORS["ink"],
                  hover_bg="#e2e8f0", active_bg="#cbd5e1",
                  width=340, height=40,
                  font=("Segoe UI", 10, "bold")
                  ).pack(anchor="w", pady=(0, 8))

    RoundedButton(body, text="\u2913  Export last scan to Excel",
                  command=do_export,
                  bg=COLORS["blue"], fg="#ffffff",
                  hover_bg=COLORS["blue_dark"], active_bg="#1e40af",
                  width=340, height=40,
                  font=("Segoe UI", 10, "bold")
                  ).pack(anchor="w")


# =========================================================
# ABOUT DIALOG (with single Update button)
# =========================================================
def open_about_dialog():
    parent = state.root
    dlg = _new_dialog("about", "About NVR SyncGuard", parent, 440, 400)
    if dlg is None:
        return

    def close():
        _on_dialog_close("about")

    dlg.protocol("WM_DELETE_WINDOW", close)

    body = tk.Frame(dlg, bg=COLORS["card"])
    body.pack(fill=tk.BOTH, expand=True, padx=24, pady=22)

    tk.Label(body, text=state.APP_NAME, bg=COLORS["card"], fg=COLORS["ink"],
             font=("Segoe UI", 16, "bold")).pack(anchor="w")
    tk.Label(body, text=f"Version {state.APP_VERSION}",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 4))
    tk.Label(body, text=f"by {state.APP_AUTHOR}  -  (c) {state.APP_YEAR}",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 12))

    tk.Label(body,
             text="Automated NVR time synchronization\n"
                  "and camera health monitoring.",
             bg=COLORS["card"], fg=COLORS["ink"],
             font=("Segoe UI", 10), justify="left").pack(anchor="w", pady=(0, 16))

    # ---------- UPDATE SECTION ----------
    tk.Frame(body, bg=COLORS["line"], height=1).pack(fill=tk.X, pady=(0, 14))

    tk.Label(body, text="APPLY CHANGES",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 6))

    tk.Label(body,
             text="Restart the app to reload code changes.\n"
                  "Useful after editing source files.",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 9), justify="left").pack(anchor="w", pady=(0, 12))

    def do_update():
        from tkinter import messagebox
        if not messagebox.askyesno(
            "Update & Restart",
            "Restart now to apply changes?\n\n"
            "The current window will close and the app will relaunch.",
            parent=dlg,
        ):
            return
        try:
            _on_dialog_close("about")
        except Exception:
            pass
        try:
            from actions import restart_app
            restart_app()
        except Exception as e:
            from logger import log_line
            log_line(f"[ABOUT] Restart failed: {e}")

    RoundedButton(body, text="\u21bb  Update",
                  command=do_update,
                  bg=COLORS["blue"], fg="#ffffff",
                  hover_bg=COLORS["blue_dark"], active_bg="#1e40af",
                  width=200, height=42,
                  font=("Segoe UI", 11, "bold")).pack(anchor="w")

    # ---------- BOTTOM ----------
    tk.Frame(body, bg=COLORS["line"], height=1).pack(fill=tk.X, pady=(16, 14))

    bottom_row = tk.Frame(body, bg=COLORS["card"])
    bottom_row.pack(fill=tk.X)

    def do_open_site():
        from actions import open_company_website
        open_company_website()

    RoundedButton(bottom_row, text=f"{state.APP_AUTHOR.upper()}  \u2197",
                  command=do_open_site,
                  bg="#eff6ff", fg="#1d4ed8",
                  hover_bg="#dbeafe", active_bg="#bfdbfe",
                  width=180, height=40,
                  font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)

    RoundedButton(bottom_row, text="Close",
                  command=close,
                  bg="#f1f5f9", fg=COLORS["ink"],
                  hover_bg="#e2e8f0", active_bg="#cbd5e1",
                  width=120, height=40,
                  font=("Segoe UI", 10, "bold")).pack(side=tk.RIGHT)


# =========================================================
# ADD SITE DIALOG (Step 3)
# =========================================================
def open_add_site_dialog(on_saved=None):
    """Add a new site to the local DB.

    on_saved - optional callback invoked after a successful save (used
               by the Server panel to refresh its list).
    """
    parent = state.root
    dlg = _new_dialog("add_site", "Add Site", parent, 440, 400)
    if dlg is None:
        return

    def close():
        _on_dialog_close("add_site")

    dlg.protocol("WM_DELETE_WINDOW", close)

    body = tk.Frame(dlg, bg=COLORS["card"])
    body.pack(fill=tk.BOTH, expand=True, padx=22, pady=20)

    tk.Label(body, text="ADD SITE", bg=COLORS["card"], fg=COLORS["ink"],
             font=("Segoe UI", 14, "bold")).pack(anchor="w")
    tk.Label(body, text="Create a new site to group NVRs and reports.",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 14))

    tk.Label(body, text="SITE NAME",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 5))
    name_entry = RoundedEntry(body, radius=10, width=340, height=42)
    name_entry.pack(fill=tk.X)

    tk.Label(body, text="LOCATION (optional)",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(10, 5))
    loc_entry = RoundedEntry(body, radius=10, width=340, height=42)
    loc_entry.pack(fill=tk.X)

    try:
        import socket
        default_pc = socket.gethostname()
    except Exception:
        default_pc = ""

    tk.Label(body, text="PC NAME",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(10, 5))
    pc_entry = RoundedEntry(body, radius=10, width=340, height=42)
    pc_entry.pack(fill=tk.X)
    pc_entry.set(default_pc)

    actions_row = tk.Frame(body, bg=COLORS["card"])
    actions_row.pack(fill=tk.X, pady=(18, 0))

    def do_save():
        from tkinter import messagebox
        from core.cloud import local_db

        name = name_entry.get().strip()
        loc = loc_entry.get().strip()
        pc = pc_entry.get().strip()

        if not name:
            messagebox.showwarning("Missing name",
                                   "Enter a site name.", parent=dlg)
            return

        existing = local_db.get_all_sites()
        for s in existing:
            if s["name"].lower() == name.lower():
                messagebox.showinfo("Already exists",
                                    f"A site named '{name}' already exists.",
                                    parent=dlg)
                return

        sid = local_db.insert_site(name=name, location=loc, pc_name=pc)
        if not sid:
            messagebox.showerror("Save failed",
                                 "Could not save the site. See logs.",
                                 parent=dlg)
            return

        messagebox.showinfo("Site added",
                            f"Site '{name}' has been created.",
                            parent=dlg)
        if callable(on_saved):
            try:
                on_saved()
            except Exception:
                pass
        close()

    def do_cancel():
        close()

    RoundedButton(actions_row, text="Save Site", command=do_save,
                  bg=COLORS["blue"], fg="#ffffff",
                  hover_bg=COLORS["blue_dark"], active_bg="#1e40af",
                  width=160, height=42,
                  font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)

    RoundedButton(actions_row, text="Cancel", command=do_cancel,
                  bg="#f1f5f9", fg=COLORS["ink"],
                  hover_bg="#e2e8f0", active_bg="#cbd5e1",
                  width=120, height=42,
                  font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(8, 0))

                  # =========================================================
# =========================================================
# RENAME SITE DIALOG (Step 3)
# =========================================================
def open_rename_site_dialog(site_id, on_saved=None):
    """Rename a site and change its location."""
    parent = state.root
    dlg = _new_dialog("rename_site", "Rename Site", parent, 440, 340)
    if dlg is None:
        return

    from core.cloud import local_db
    site = local_db.get_site(site_id)
    if not site:
        return

    def close():
        _on_dialog_close("rename_site")

    dlg.protocol("WM_DELETE_WINDOW", close)

    body = tk.Frame(dlg, bg=COLORS["card"])
    body.pack(fill=tk.BOTH, expand=True, padx=22, pady=20)

    tk.Label(body, text="RENAME SITE", bg=COLORS["card"], fg=COLORS["ink"],
             font=("Segoe UI", 14, "bold")).pack(anchor="w")
    tk.Label(body, text="Update the site name or location.",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 14))

    tk.Label(body, text="SITE NAME",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 5))
    name_entry = RoundedEntry(body, radius=10, width=340, height=42)
    name_entry.pack(fill=tk.X)
    name_entry.set(site["name"])

    tk.Label(body, text="LOCATION (optional)",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(10, 5))
    loc_entry = RoundedEntry(body, radius=10, width=340, height=42)
    loc_entry.pack(fill=tk.X)
    loc_entry.set(site.get("location", ""))

    actions_row = tk.Frame(body, bg=COLORS["card"])
    actions_row.pack(fill=tk.X, pady=(18, 0))

    def do_save():
        from tkinter import messagebox

        new_name = name_entry.get().strip()
        new_loc = loc_entry.get().strip()

        if not new_name:
            messagebox.showwarning("Missing name",
                                   "Enter a site name.", parent=dlg)
            return

        # Check for duplicates (excluding self)
        for s in local_db.get_all_sites():
            if s["id"] == site_id:
                continue
            if s["name"].lower() == new_name.lower():
                messagebox.showinfo("Already exists",
                                    f"A site named '{new_name}' already exists.",
                                    parent=dlg)
                return

        ok = local_db.update_site(site_id, name=new_name, location=new_loc)
        if not ok:
            messagebox.showerror("Save failed",
                                 "Could not update the site. See logs.",
                                 parent=dlg)
            return

        messagebox.showinfo("Updated",
                            "Site has been updated.",
                            parent=dlg)
        if callable(on_saved):
            try:
                on_saved()
            except Exception:
                pass
        close()

    RoundedButton(actions_row, text="Save", command=do_save,
                  bg=COLORS["blue"], fg="#ffffff",
                  hover_bg=COLORS["blue_dark"], active_bg="#1e40af",
                  width=140, height=42,
                  font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)

    RoundedButton(actions_row, text="Cancel", command=close,
                  bg="#f1f5f9", fg=COLORS["ink"],
                  hover_bg="#e2e8f0", active_bg="#cbd5e1",
                  width=120, height=42,
                  font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(8, 0))
    """Rename a site and change its location."""
    parent = state.root
    dlg = _new_dialog("rename_site", "Rename Site", parent, 440, 340)
    if dlg is None:
        return

    from core.cloud import local_db
    site = local_db.get_site(site_id)
    if not site:
        return

    def close():
        _on_dialog_close("rename_site")

    dlg.protocol("WM_DELETE_WINDOW", close)

    body = tk.Frame(dlg, bg=COLORS["card"])
    body.pack(fill=tk.BOTH, expand=True, padx=22, pady=20)

    tk.Label(body, text="RENAME SITE", bg=COLORS["card"], fg=COLORS["ink"],
             font=("Segoe UI", 14, "bold")).pack(anchor="w")
    tk.Label(body, text="Update the site name or location.",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 14))

    tk.Label(body, text="SITE NAME",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 5))
    name_entry = RoundedEntry(body, radius=10, width=340, height=42)
    name_entry.pack(fill=tk.X)
    name_entry.set(site["name"])

    tk.Label(body, text="LOCATION (optional)",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(10, 5))
    loc_entry = RoundedEntry(body, radius=10, width=340, height=42)
    loc_entry.pack(fill=tk.X)
    loc_entry.set(site.get("location", ""))

    actions_row = tk.Frame(body, bg=COLORS["card"])
    actions_row.pack(fill=tk.X, pady=(18, 0))

    def do_save():
        from tkinter import messagebox

        new_name = name_entry.get().strip()
        new_loc = loc_entry.get().strip()

        if not new_name:
            messagebox.showwarning("Missing name",
                                   "Enter a site name.", parent=dlg)
            return

        # Check for duplicates (excluding self)
        for s in local_db.get_all_sites():
            if s["id"] == site_id:
                continue
            if s["name"].lower() == new_name.lower():
                messagebox.showinfo("Already exists",
                                    f"A site named '{new_name}' already exists.",
                                    parent=dlg)
                return

        ok = local_db.update_site(site_id, name=new_name, location=new_loc)
        if not ok:
            messagebox.showerror("Save failed",
                                 "Could not update the site. See logs.",
                                 parent=dlg)
            return

        messagebox.showinfo("Updated",
                            "Site has been updated.",
                            parent=dlg)
        if callable(on_saved):
            try:
                on_saved()
            except Exception:
                pass
        close()

    RoundedButton(actions_row, text="Save", command=do_save,
                  bg=COLORS["blue"], fg="#ffffff",
                  hover_bg=COLORS["blue_dark"], active_bg="#1e40af",
                  width=140, height=42,
                  font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)

    RoundedButton(actions_row, text="Cancel", command=close,
                  bg="#f1f5f9", fg=COLORS["ink"],
                  hover_bg="#e2e8f0", active_bg="#cbd5e1",
                  width=120, height=42,
                  font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(8, 0))