"""
Main window construction - top nav bar version.

Layout:
    [header: logo, title, clock, codraze button]
    [top nav bar: + Add NVR | ⚙ Configure NVR | 🔧 Settings | 📁 Reports | 🖥 Server | ℹ About]
    [body: optional left Server panel | dashboard fills the rest]
    [footer]

Nav buttons open non-modal dialogs from ui.dialogs_forms, EXCEPT the
Server button, which toggles an inline panel on the left side.
"""

import os
import tkinter as tk
from tkinter import ttk, scrolledtext

import state
from logger import log_line
from ui.theme import COLORS
from ui.widgets import RoundedFrame, RoundedButton
from ui.proxies import TkLogProxy, TkTreeProxy, TkLabelProxy
from ui.queue_pump import _pump_ui_queue, update_stats

from core.autostart import is_autostart_registered  # noqa: F401


def _load_logo(logo_path, ico_path):
    """Load the app logo as a Tk PhotoImage, or None on failure."""
    for path in [logo_path, ico_path,
                 os.path.join("images", "logo.png"),
                 os.path.join("images", "logo.ico")]:
        if not path or not os.path.exists(path):
            continue
        try:
            from PIL import Image, ImageTk
            img = Image.open(path).convert("RGBA").resize((72, 72), Image.LANCZOS)
            return ImageTk.PhotoImage(img)
        except Exception:
            try:
                return tk.PhotoImage(file=path)
            except Exception:
                continue
    return None


def _on_window_close():
    """X button - hide to tray; the app keeps running."""
    try:
        if state.root is None:
            return
        state.root.withdraw()
        log_line("[APP] Window hidden to tray (X pressed)")
        if state.TRAY_ICON is None and (
            state.BACKGROUND_MODE or state.START_MINIMIZED_TO_TRAY
        ):
            from tray.tray import start_tray_icon
            start_tray_icon()
    except Exception:
        try:
            state.root.destroy()
        except Exception:
            pass


def main(start_hidden=False):
    """Build the GUI and start all background threads. Blocks on mainloop()."""
    from paths import ICO_PATH, LOGO_PATH

    state.scan_running = False

    # ---------- ROOT ----------
    root = tk.Tk()
    root.title(f"{state.APP_NAME} v{state.APP_VERSION} "
               f"- Time Sync & Camera Health Monitor - {state.APP_AUTHOR}")
    root.geometry("1480x980")
    root.minsize(1180, 800)
    root.configure(bg=COLORS["bg"])
    root.protocol("WM_DELETE_WINDOW", _on_window_close)

    try:
        if os.path.exists(ICO_PATH):
            root.iconbitmap(ICO_PATH)
    except Exception:
        pass

    state.root = root

    # ---------- TTK STYLE ----------
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("Treeview",
                    background=COLORS["card"],
                    foreground=COLORS["ink"],
                    fieldbackground=COLORS["card"],
                    rowheight=36, borderwidth=0,
                    font=("Segoe UI", 10))
    style.configure("Treeview.Heading",
                    background=COLORS["ink_soft"],
                    foreground="white",
                    font=("Segoe UI", 10, "bold"),
                    relief="flat", padding=(10, 10))
    style.map("Treeview",
              background=[("selected", COLORS["blue_pale"])],
              foreground=[("selected", COLORS["ink"])])
    style.configure("Vertical.TScrollbar",
                    background=COLORS["card"], troughcolor=COLORS["card"],
                    borderwidth=0, arrowsize=12)

    outer = tk.Frame(root, bg=COLORS["bg"])
    outer.pack(fill=tk.BOTH, expand=True, padx=22, pady=18)

    # ---------- HEADER ----------
    header = RoundedFrame(outer, radius=16, bg=COLORS["header"],
                          border=COLORS["header"], border_width=0,
                          padding=0, width=1000, height=110)
    header.pack(fill=tk.X, pady=(0, 12))
    header.configure(height=110)
    h = header.inner

    brand_container = tk.Frame(h, bg=COLORS["header"])
    brand_container.place(x=22, y=18, width=76, height=76)

    logo_photo = _load_logo(LOGO_PATH, ICO_PATH)
    if logo_photo is not None:
        logo_tile = RoundedFrame(brand_container, radius=14,
                                 bg=COLORS["blue"], border=COLORS["blue"],
                                 border_width=0, padding=6, width=72, height=72)
        logo_tile.pack(fill=tk.BOTH, expand=True)
        logo_label = tk.Label(logo_tile.inner, image=logo_photo,
                              bg=COLORS["blue"], bd=0)
        logo_label.image = logo_photo
        logo_label.pack(expand=True)
    else:
        tk.Label(brand_container, text="C", bg=COLORS["blue"], fg="#ffffff",
                 font=("Segoe UI", 26, "bold"), width=2, height=1
                 ).pack(fill=tk.BOTH, expand=True)

    title_area = tk.Frame(h, bg=COLORS["header"])
    title_area.place(x=118, y=22)
    tk.Label(title_area, text=state.APP_NAME, bg=COLORS["header"], fg="#ffffff",
             font=("Segoe UI", 22, "bold")).pack(anchor="w")

    subtitle_lbl = tk.Label(
        title_area,
        text="Background tray - Camera ping - Auto-sync on recovery",
        bg=COLORS["header"], fg="#94a3b8",
        font=("Segoe UI", 10))
    subtitle_lbl.pack(anchor="w", pady=(2, 0))

    clock_label = tk.Label(h, text="", bg=COLORS["header"], fg="#cbd5e1",
                           font=("Segoe UI", 11))
    clock_label.place(relx=1.0, x=-115, y=42)

    codraze_btn = RoundedButton(
        h, text=f"{state.APP_AUTHOR.upper()}  \u2197",
        command=lambda: _open_company_website(),
        radius=12,
        bg="#1f2937", fg="#93c5fd",
        hover_bg="#273449", active_bg="#0f172a",
        width=170, height=42, font=("Segoe UI", 10, "bold"),
    )
    codraze_btn.place(relx=1.0, x=-305, y=32)

    def tick():
        from datetime import datetime
        clock_label.config(text=datetime.now().strftime("%H:%M:%S"))
        root.after(1000, tick)
    tick()

    # ---------- TOP NAV BAR ----------
    nav = RoundedFrame(outer, radius=14, bg=COLORS["card"],
                       border=COLORS["line"], padding=10,
                       width=1000, height=66)
    nav.pack(fill=tk.X, pady=(0, 12))
    nav.configure(height=66)
    nav_inner = nav.inner

    def _open_add_nvr():
        from ui.dialogs_forms import open_add_nvr_dialog
        open_add_nvr_dialog()

    def _open_configure():
        from ui.dialogs_forms import open_configure_nvr_dialog
        open_configure_nvr_dialog()

    def _open_settings():
        from ui.dialogs_forms import open_settings_dialog
        open_settings_dialog()

    def _open_reports():
        from ui.dialogs_forms import open_reports_dialog
        open_reports_dialog()

    def _open_about():
        from ui.dialogs_forms import open_about_dialog
        open_about_dialog()

    # Server is a TOGGLE for an inline panel, not a dialog opener
    def _toggle_server_panel():
        _do_toggle_server_panel()

    nav_specs = [
        ("+  Add NVR", _open_add_nvr,
         COLORS["blue"], COLORS["blue_dark"], "#1e40af"),
        ("\u2699  Configure NVR", _open_configure,
         "#eff6ff", "#dbeafe", "#bfdbfe"),
        ("\U0001f527  Settings", _open_settings,
         "#eff6ff", "#dbeafe", "#bfdbfe"),
        ("\U0001f4c1  Reports", _open_reports,
         "#eff6ff", "#dbeafe", "#bfdbfe"),
        ("\U0001f5a5  Server", _toggle_server_panel,
         COLORS["blue"], COLORS["blue_dark"], "#1e40af"),
        ("\u2139  About", _open_about,
         "#eff6ff", "#dbeafe", "#bfdbfe"),
    ]

    for text, cmd, bg, hover, active in nav_specs:
        fg = "#ffffff" if bg == COLORS["blue"] else COLORS["blue_dark"]
        RoundedButton(nav_inner, text=text, command=cmd,
                      radius=8, bg=bg, fg=fg,
                      hover_bg=hover, active_bg=active,
                      width=165, height=44,
                      font=("Segoe UI", 10, "bold")
                      ).pack(side=tk.LEFT, padx=(0, 8))

    # ---------- BODY (grid with optional left panel) ----------
    body = tk.Frame(outer, bg=COLORS["bg"])
    body.pack(fill=tk.BOTH, expand=True)
    body.grid_rowconfigure(0, weight=1)
    body.grid_columnconfigure(0, weight=0)   # left panel column (hidden by default)
    body.grid_columnconfigure(1, weight=1)   # dashboard column

    # Left panel holder - initially hidden (grid_remove)
    server_panel_holder = tk.Frame(body, bg=COLORS["bg"], width=360)
    server_panel_holder.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
    server_panel_holder.grid_propagate(False)
    server_panel_holder.grid_remove()

    server_panel_state = {"visible": False, "widget": None}

    def _show_server_panel():
        if server_panel_state["visible"]:
            return
        if server_panel_state["widget"] is None:
            from ui.server_panel import build_server_panel
            widget = build_server_panel(
                server_panel_holder,
                on_close=_hide_server_panel,
            )
            widget.pack(fill=tk.BOTH, expand=True)
            server_panel_state["widget"] = widget
        server_panel_holder.grid()
        server_panel_state["visible"] = True

    def _hide_server_panel():
        if not server_panel_state["visible"]:
            return
        server_panel_holder.grid_remove()
        server_panel_state["visible"] = False

    def _do_toggle_server_panel():
        if server_panel_state["visible"]:
            _hide_server_panel()
        else:
            _show_server_panel()

    # Dashboard (right side, always visible)
    right = tk.Frame(body, bg=COLORS["bg"])
    right.grid(row=0, column=1, sticky="nsew")
    right.grid_columnconfigure(0, weight=1)
    right.grid_rowconfigure(3, weight=3)
    right.grid_rowconfigure(4, weight=2)

    action_bar = RoundedFrame(right, radius=16, bg=COLORS["card"],
                              border=COLORS["line"], padding=16,
                              width=900, height=96)
    action_bar.grid(row=0, column=0, sticky="ew", pady=(0, 14))
    action_bar.configure(height=96)
    ab = action_bar.inner

    status_label_widget = tk.Label(ab, text="* Ready to scan",
                                   bg=COLORS["card"], fg=COLORS["green"],
                                   font=("Segoe UI", 11, "bold"))
    status_label_widget.pack(side=tk.LEFT, padx=(4, 0))
    status_label = TkLabelProxy(status_label_widget)
    state.status_label_proxy = status_label

    export_btn = RoundedButton(ab, text="\u2913  EXPORT EXCEL",
                               command=lambda: _export_report(),
                               bg="#f1f5f9", fg=COLORS["ink"],
                               hover_bg="#e2e8f0", active_bg="#cbd5e1",
                               width=160, height=46,
                               font=("Segoe UI", 10, "bold"))
    export_btn.pack(side=tk.RIGHT)

    restart_btn = RoundedButton(ab, text="\u27f3  RESTART",
                                command=lambda: _restart_app(),
                                bg="#fef3c7", fg="#92400e",
                                hover_bg="#fde68a", active_bg="#fcd34d",
                                width=140, height=46,
                                font=("Segoe UI", 10, "bold"))
    restart_btn.pack(side=tk.RIGHT, padx=(0, 8))

    exit_btn = RoundedButton(ab, text="\u2715  EXIT",
                             command=lambda: _full_exit(),
                             bg="#fee2e2", fg="#991b1b",
                             hover_bg="#fecaca", active_bg="#fca5a5",
                             width=120, height=46,
                             font=("Segoe UI", 10, "bold"))
    exit_btn.pack(side=tk.RIGHT, padx=(0, 8))

    btn = RoundedButton(ab, text="\u25b6  START SCAN",
                        command=lambda: _start_all(),
                        bg=COLORS["blue"], hover_bg=COLORS["blue_dark"],
                        active_bg="#1e40af", width=180, height=46,
                        font=("Segoe UI", 11, "bold"))
    btn.pack(side=tk.RIGHT, padx=(0, 8))
    state.btn = btn

    # ---------- STAT CARDS ----------
    stats_row1 = tk.Frame(right, bg=COLORS["bg"])
    stats_row1.grid(row=1, column=0, sticky="ew", pady=(0, 8))
    stats_row2 = tk.Frame(right, bg=COLORS["bg"])
    stats_row2.grid(row=2, column=0, sticky="ew", pady=(0, 14))
    for r in (stats_row1, stats_row2):
        for c in range(3):
            r.grid_columnconfigure(c, weight=1)

    def _make_stat(parent, label, value, bg, fg, border):
        card = RoundedFrame(parent, radius=14, bg=bg, border=border,
                            padding=14, width=210, height=86)
        tk.Label(card.inner, text=label, bg=bg, fg=COLORS["muted"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        num = tk.Label(card.inner, text=value, bg=bg, fg=fg,
                       font=("Segoe UI", 22, "bold"))
        num.pack(anchor="w", pady=(2, 0))
        return card, num

    nvr1_card, stat_nvr_total = _make_stat(
        stats_row1, "TOTAL NVRS", "0",
        COLORS["blue_pale"], COLORS["blue"], COLORS["blue_border"])
    nvr1_card.grid(row=0, column=0, sticky="ew", padx=(0, 8))

    nvr2_card, stat_nvr_checked = _make_stat(
        stats_row1, "CHECKED NVRS", "0",
        COLORS["green_pale"], COLORS["green"], COLORS["green_border"])
    nvr2_card.grid(row=0, column=1, sticky="ew", padx=(0, 8))

    nvr3_card, stat_nvr_skipped = _make_stat(
        stats_row1, "SKIPPED NVRS", "0",
        COLORS["amber_pale"], "#92400e", "#fcd34d")
    nvr3_card.grid(row=0, column=2, sticky="ew")

    cam1_card, stat_cam_total = _make_stat(
        stats_row2, "TOTAL CAMERAS", "0",
        COLORS["purple_pale"], COLORS["purple"], COLORS["purple_border"])
    cam1_card.grid(row=0, column=0, sticky="ew", padx=(0, 8))

    cam2_card, stat_cam_online = _make_stat(
        stats_row2, "ONLINE CAMERAS", "0",
        COLORS["green_pale"], COLORS["green"], COLORS["green_border"])
    cam2_card.grid(row=0, column=1, sticky="ew", padx=(0, 8))

    cam3_card, stat_cam_offline = _make_stat(
        stats_row2, "OFFLINE / ABNORMAL", "0",
        COLORS["red_pale"], COLORS["red_dark"], COLORS["red_border"])
    cam3_card.grid(row=0, column=2, sticky="ew")

    stat_widgets = {
        "nvr_total": stat_nvr_total,
        "nvr_checked": stat_nvr_checked,
        "nvr_skipped": stat_nvr_skipped,
        "cam_total": stat_cam_total,
        "cam_online": stat_cam_online,
        "cam_offline": stat_cam_offline,
    }

    # ---------- CAMERA TABLE ----------
    results_card = RoundedFrame(right, radius=16, bg=COLORS["card"],
                                border=COLORS["line"], padding=16,
                                width=900, height=280)
    results_card.grid(row=3, column=0, sticky="nsew", pady=(0, 14))
    rc = results_card.inner
    rc.grid_columnconfigure(0, weight=1)
    rc.grid_rowconfigure(1, weight=1)

    header_line = tk.Frame(rc, bg=COLORS["card"])
    header_line.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
    tk.Label(header_line, text="Camera exceptions",
             bg=COLORS["card"], fg=COLORS["ink"],
             font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT)
    tk.Label(header_line,
             text="Only offline / abnormal cameras are listed below",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(10, 0))

    columns = ("no", "name", "ip", "status", "nvr")
    tree = ttk.Treeview(rc, columns=columns, show="headings")
    for key, caption, width, anchor in [
        ("no", "No", 55, tk.CENTER),
        ("name", "Camera Name", 220, tk.W),
        ("ip", "IP Address", 150, tk.W),
        ("status", "Status", 130, tk.CENTER),
        ("nvr", "NVR IP", 170, tk.W),
    ]:
        tree.heading(key, text=caption)
        tree.column(key, width=width, anchor=anchor, stretch=True)
    tree.grid(row=1, column=0, sticky="nsew")
    tree.tag_configure("offline", background="#fef2f2", foreground="#991b1b")
    tree.tag_configure("abnormal", background="#fffbeb", foreground="#92400e")

    tree_scroll = ttk.Scrollbar(rc, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=tree_scroll.set)
    tree_scroll.grid(row=1, column=1, sticky="ns", padx=(6, 0))

    tree_proxy = TkTreeProxy(tree)
    state.tree_proxy = tree_proxy
    state.tree_widget = tree

    # ---------- LOGS ROW ----------
    logs_row = tk.Frame(right, bg=COLORS["bg"])
    logs_row.grid(row=4, column=0, sticky="nsew")
    logs_row.grid_columnconfigure(0, weight=1, uniform="logcol")
    logs_row.grid_columnconfigure(1, weight=1, uniform="logcol")
    logs_row.grid_rowconfigure(0, weight=1)

    log_card = RoundedFrame(logs_row, radius=16, bg=COLORS["card"],
                            border=COLORS["line"], padding=14,
                            width=440, height=260)
    log_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
    lc = log_card.inner
    lc.grid_columnconfigure(0, weight=1)
    lc.grid_rowconfigure(1, weight=1)
    tk.Label(lc, text="Activity log", bg=COLORS["card"], fg=COLORS["ink"],
             font=("Segoe UI", 11, "bold")).grid(row=0, column=0,
                                                 sticky="w", pady=(0, 6))
    log_widget = scrolledtext.ScrolledText(lc, wrap=tk.WORD,
                                           font=("Consolas", 9),
                                           bg="#0b1220", fg="#cbd5e1",
                                           relief=tk.FLAT,
                                           insertbackground="#93c5fd",
                                           selectbackground="#1e3a8a")
    log_widget.grid(row=1, column=0, sticky="nsew")
    log = TkLogProxy(log_widget)
    state.log = log
    state.log_widget = log_widget

    ping_card = RoundedFrame(logs_row, radius=16, bg=COLORS["card"],
                             border=COLORS["line"], padding=14,
                             width=440, height=260)
    ping_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
    pc = ping_card.inner
    pc.grid_columnconfigure(0, weight=1)
    pc.grid_rowconfigure(1, weight=1)

    ping_header = tk.Frame(pc, bg=COLORS["card"])
    ping_header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
    tk.Label(ping_header, text="Ping monitor",
             bg=COLORS["card"], fg=COLORS["ink"],
             font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT)
    ping_count_lbl = tk.Label(ping_header, text="0 offline cameras",
                              bg=COLORS["card"], fg=COLORS["muted"],
                              font=("Segoe UI", 9))
    ping_count_lbl.pack(side=tk.RIGHT)

    ping_widget = scrolledtext.ScrolledText(pc, wrap=tk.WORD,
                                            font=("Consolas", 9),
                                            bg="#0b1220", fg="#a7f3d0",
                                            relief=tk.FLAT,
                                            insertbackground="#93c5fd",
                                            selectbackground="#1e3a8a",
                                            height=10)
    ping_widget.grid(row=1, column=0, sticky="nsew")

    for _l in state.PING_LOG_LINES:
        ping_widget.insert(tk.END, _l + "\n")
    ping_widget.see(tk.END)

    # ---------- FOOTER ----------
    footer = tk.Frame(outer, bg=COLORS["bg"])
    footer.pack(fill=tk.X, pady=(12, 0))
    tk.Label(footer,
             text=f"{state.APP_NAME} v{state.APP_VERSION}  -  "
                  f"by {state.APP_AUTHOR}  -  (c) {state.APP_YEAR}",
             bg=COLORS["bg"], fg=COLORS["muted"],
             font=("Segoe UI", 9)).pack(side=tk.LEFT)
    last_saved_label = tk.Label(footer, text=f"Folder: {state.DOWNLOADS_DIR}",
                                bg=COLORS["bg"], fg=COLORS["muted"],
                                font=("Segoe UI", 9))
    last_saved_label.pack(side=tk.RIGHT)
    state.last_saved_label = last_saved_label

    # ---------- RUNNING STATE PAINTER ----------
    def _apply_running_state():
        running = bool(state.UI_STATE.get("running")) or state.scan_running
        if running:
            btn.set_text("\u25cf  RUNNING...")
            btn.set_colors(bg=COLORS["green"], hover=COLORS["green"],
                           active=COLORS["green"], fg="#ffffff")
            subtitle_lbl.config(
                text="* Running in background - closing this window "
                     "keeps it alive in the tray",
                fg="#86efac")
        else:
            btn.set_text("\u25b6  START SCAN")
            btn.set_colors(bg=COLORS["blue"], hover=COLORS["blue_dark"],
                           active="#1e40af", fg="#ffffff")
            subtitle_lbl.config(
                text="Background tray - Camera ping - Auto-sync on recovery",
                fg="#94a3b8")

    # ---------- LAZY ACTION WRAPPERS ----------
    def _export_report():
        from actions import export_report
        export_report(log)

    def _start_all():
        from actions import start_all
        start_all(log, btn, tree_proxy, status_label)

    def _restart_app():
        from actions import restart_app
        restart_app()

    def _full_exit():
        from actions import full_exit
        full_exit()

    def _open_company_website():
        from actions import open_company_website
        open_company_website()

    # ---------- AUTO LAUNCH ----------
    def auto_launch():
        if not state.NVR_LIST:
            log.insert(tk.END,
                       "[INFO] No NVR configured yet - click '+ Add NVR' "
                       "on the top bar, then START SCAN.\n")
            status_label.config(text="* Waiting for first NVR",
                                fg=COLORS["muted"])
            return
        if not state.RUN_SCAN_ON_LAUNCH:
            log.insert(tk.END,
                       "[INFO] 'Run scan on launch' is OFF - waiting. "
                       "Background ping monitor will still watch NVRs.\n")
            status_label.config(text="* Ready (auto-scan off)",
                                fg=COLORS["muted"])
            return
        log.insert(tk.END,
                   f"[INFO] Auto-start - launching scan of "
                   f"{len(state.NVR_LIST)} NVR(s)...\n")
        from actions import start_all
        start_all(log, btn, tree_proxy, status_label, auto_start=True)

    root.after(state.SCAN_DELAY_SECONDS * 1000, auto_launch)

    # ---------- START PUMPS ----------
    _pump_ui_queue(log_widget, ping_widget, tree,
                   status_label_widget, ping_count_lbl)
    update_stats(stat_widgets, _apply_running_state, last_saved_label)

    # ---------- START WORKERS ----------
    import threading
    from workers.nvr_monitor import _monitor_worker
    from workers.camera_monitor import _camera_ping_worker
    from workers.daily_restart import _daily_restart_worker
    from workers.down_alert import _down_alert_worker
    from ui.dialogs import _schedule_auto_close
    from core.autostart import register_autostart

    state.UI_STATE["running"] = bool(state.BACKGROUND_PING_MONITOR)
    state.UI_STATE["phase"] = ("monitoring" if state.BACKGROUND_PING_MONITOR
                               else "idle")

    threading.Thread(target=_monitor_worker, daemon=True).start()
    log_line("[MONITOR] NVR monitor thread started")

    if state.CAMERA_PING_ENABLED:
        threading.Thread(target=_camera_ping_worker, daemon=True).start()
        log_line("[CAMERA] Camera-ping thread started")

    threading.Thread(target=_daily_restart_worker, daemon=True).start()
    threading.Thread(target=_down_alert_worker, daemon=True).start()

    _schedule_auto_close()

    # ---------- TRAY ----------
    if state.BACKGROUND_MODE or state.START_MINIMIZED_TO_TRAY:
        from tray.tray import start_tray_icon
        start_tray_icon()

    if start_hidden and (state.BACKGROUND_MODE or state.START_MINIMIZED_TO_TRAY):
        try:
            root.withdraw()
            log_line("[APP] Window hidden; use tray icon to open.")
        except Exception:
            pass

    root.after(500, _apply_running_state)

    # ---------- CLOSE DIALOGS ON EXIT ----------
    def _on_destroy(event=None):
        try:
            if event is not None and event.widget is not root:
                return
        except Exception:
            pass
        try:
            from ui.dialogs_forms import close_all_dialogs
            close_all_dialogs()
        except Exception:
            pass

    root.bind("<Destroy>", _on_destroy)

    # ---------- STARTUP LOGGING ----------
    log.insert(tk.END, f"[INFO] {state.APP_NAME} v{state.APP_VERSION} - ready.\n")
    if state.AUTO_CLOSE_ENABLED:
        log.insert(tk.END,
                   f"[INFO] Auto-close scheduled at "
                   f"{state.AUTO_CLOSE_HOUR:02d}:{state.AUTO_CLOSE_MINUTE:02d} "
                   f"(local time).\n")
    if state.DAILY_RESTART_ENABLED:
        log.insert(tk.END,
                   f"[INFO] Daily restart scheduled at "
                   f"{state.DAILY_RESTART_HOUR:02d}:{state.DAILY_RESTART_MINUTE:02d} "
                   f"(local time).\n")

    log_line(f"App started (hidden={start_hidden}, "
             f"background={state.BACKGROUND_MODE}, "
             f"ping_monitor={state.BACKGROUND_PING_MONITOR}, "
             f"recovery_scan={state.AUTO_SCAN_ON_RECOVERY}, "
             f"launch_scan={state.RUN_SCAN_ON_LAUNCH})")

    if not is_autostart_registered():
        try:
            register_autostart()
        except Exception as e:
            log_line(f"[AUTOSTART] Register failed: {e}")

    root.mainloop()