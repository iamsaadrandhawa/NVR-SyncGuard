"""
Server module panel - appears on the LEFT side of the main window
when the user clicks the "Server" button in the top nav bar.

Now:
  - Shows all sites from the local SQLite DB.
  - Marks this PC's own site with a star (★) and "(This PC)" label.
  - Supports Add, View, Rename, Delete, Export.

Exposed:
    build_server_panel(parent, on_close=None)
"""

import tkinter as tk
from tkinter import messagebox

import state
from ui.theme import COLORS
from ui.widgets import RoundedFrame, RoundedButton


def build_server_panel(parent, on_close=None):
    """Build the server panel. Returns the outer Frame."""
    container = tk.Frame(parent, bg=COLORS["bg"], width=360)
    container.grid_propagate(False)
    container.pack_propagate(False)

    card = RoundedFrame(container, radius=16, bg=COLORS["card"],
                        border=COLORS["line"], padding=16,
                        width=340, height=700)
    card.pack(fill=tk.BOTH, expand=True)
    inner = card.inner

    # ---------- HEADER ----------
    header = tk.Frame(inner, bg=COLORS["card"])
    header.pack(fill=tk.X, pady=(0, 12))

    tk.Label(header, text="SERVER MODULE",
             bg=COLORS["card"], fg=COLORS["ink"],
             font=("Segoe UI", 13, "bold")).pack(side=tk.LEFT)

    def _close():
        if callable(on_close):
            try:
                on_close()
            except Exception:
                pass

    RoundedButton(header, text="\u2715", command=_close,
                  radius=6,
                  bg="#f1f5f9", fg=COLORS["ink"],
                  hover_bg="#e2e8f0", active_bg="#cbd5e1",
                  width=32, height=32,
                  font=("Segoe UI", 11, "bold")).pack(side=tk.RIGHT)

    # ---------- SUBTITLE ----------
    tk.Label(inner, text="Multi-site reporting dashboard",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 12))

    # ---------- SITES BOX ----------
    sites_header = tk.Frame(inner, bg=COLORS["card"])
    sites_header.pack(fill=tk.X, pady=(0, 6))

    tk.Label(sites_header, text="SITES",
             bg=COLORS["card"], fg=COLORS["ink"],
             font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)

    sites_count_lbl = tk.Label(sites_header, text="0 configured",
                               bg=COLORS["card"], fg=COLORS["muted"],
                               font=("Segoe UI", 8))
    sites_count_lbl.pack(side=tk.RIGHT)

    list_wrap = RoundedFrame(inner, radius=8, bg="#f8fafc",
                             border=COLORS["line"], padding=4,
                             width=300, height=180)
    list_wrap.pack(fill=tk.BOTH, expand=True)

    sites_listbox = tk.Listbox(list_wrap.inner, font=("Consolas", 9),
                               bg="#f8fafc", fg=COLORS["ink"],
                               relief=tk.FLAT,
                               selectbackground=COLORS["blue"],
                               selectforeground="#ffffff",
                               activestyle="none",
                               highlightthickness=0)
    sites_listbox.pack(fill=tk.BOTH, expand=True)

    # Cache: parallel list of site ids, matching listbox indices
    site_ids = []
    my_site_id = {"id": ""}

    def _resolve_my_site():
        """Return the local site id (auto-creating if needed)."""
        try:
            from actions import _ensure_local_site
            sid = _ensure_local_site()
            return sid or ""
        except Exception:
            return ""

    def _refresh_sites():
        """Load sites from the local DB."""
        site_ids.clear()
        sites_listbox.delete(0, tk.END)

        my_site_id["id"] = _resolve_my_site()

        try:
            from core.cloud import local_db
            sites = local_db.get_all_sites()
        except Exception:
            sites = []

        if not sites:
            sites_listbox.insert(tk.END, "(no sites configured yet)")
            sites_count_lbl.config(text="0 configured")
            return

        # Sort: my site first, then alphabetical by name
        def _sort_key(s):
            is_mine = 0 if s["id"] == my_site_id["id"] else 1
            return (is_mine, s["name"].lower())

        for s in sorted(sites, key=_sort_key):
            site_ids.append(s["id"])
            is_mine = (s["id"] == my_site_id["id"])
            if is_mine:
                label = f"★ {s['name']}  (This PC)"
            else:
                label = f"  {s['name']}"
            sites_listbox.insert(tk.END, label)

        sites_count_lbl.config(text=f"{len(sites)} configured")

    _refresh_sites()

    # ---------- ACTION BUTTONS ----------
    actions = tk.Frame(inner, bg=COLORS["card"])
    actions.pack(fill=tk.X, pady=(12, 6))

    def _get_selected_site_id():
        sel = sites_listbox.curselection()
        if not sel or not site_ids:
            messagebox.showinfo("Select a site",
                                "Choose a site from the list first.",
                                parent=state.root)
            return None
        idx = sel[0]
        if idx >= len(site_ids):
            return None
        return site_ids[idx]

    def _add_site():
        from ui.dialogs_forms import open_add_site_dialog
        open_add_site_dialog(on_saved=_refresh_sites)

    def _view_details():
        sid = _get_selected_site_id()
        if not sid:
            return
        _open_site_details(sid, is_mine=(sid == my_site_id["id"]))

    def _rename_site():
        sid = _get_selected_site_id()
        if not sid:
            return
        from ui.dialogs_forms import open_rename_site_dialog
        open_rename_site_dialog(sid, on_saved=_refresh_sites)

    def _delete_site():
        sid = _get_selected_site_id()
        if not sid:
            return

        from core.cloud import local_db
        site = local_db.get_site(sid)
        if not site:
            return

        is_mine = (sid == my_site_id["id"])
        warn_extra = ""
        if is_mine:
            warn_extra = ("\n\n⚠ This is YOUR PC's site. "
                          "Deleting it will remove all local scans and NVRs "
                          "for this machine. A new empty site will be created "
                          "the next time you scan.")

        # Ask for password
        from ui.dialogs import request_admin_authorization
        if not request_admin_authorization(
            state.root,
            f"Deleting site '{site['name']}' requires administrator approval."
        ):
            return

        ok = messagebox.askyesno(
            "Delete site?",
            f"Delete '{site['name']}'?\n\n"
            f"This removes:\n"
            f"  • The site record\n"
            f"  • All NVRs belonging to it\n"
            f"  • All scan reports and camera results"
            + warn_extra,
            parent=state.root,
        )
        if not ok:
            return

        if local_db.delete_site(sid):
            # If we just deleted our own site, clear the cache
            if is_mine:
                state.LOCAL_SITE_ID = ""
                try:
                    state.config.pop("LOCAL_SITE_ID", None)
                    state.save_config()
                except Exception:
                    pass
                my_site_id["id"] = ""
            messagebox.showinfo("Deleted",
                                f"Site '{site['name']}' has been deleted.",
                                parent=state.root)
            _refresh_sites()
        else:
            messagebox.showerror("Delete failed",
                                 "Could not delete the site. See logs.",
                                 parent=state.root)

    def _export_report():
        sid = _get_selected_site_id()
        if not sid:
            return
        _export_latest_report(sid)

    RoundedButton(actions, text="+  Add Site",
                  command=_add_site,
                  bg=COLORS["blue"], fg="#ffffff",
                  hover_bg=COLORS["blue_dark"], active_bg="#1e40af",
                  width=300, height=34,
                  font=("Segoe UI", 9, "bold")
                  ).pack(anchor="w", pady=(0, 5))

    RoundedButton(actions, text="\U0001f4cb  View Details",
                  command=_view_details,
                  bg="#eff6ff", fg="#1d4ed8",
                  hover_bg="#dbeafe", active_bg="#bfdbfe",
                  width=300, height=34,
                  font=("Segoe UI", 9, "bold")
                  ).pack(anchor="w", pady=(0, 5))

    row2 = tk.Frame(actions, bg=COLORS["card"])
    row2.pack(fill=tk.X, pady=(0, 5))

    RoundedButton(row2, text="\u270f  Rename",
                  command=_rename_site,
                  bg="#f1f5f9", fg=COLORS["ink"],
                  hover_bg="#e2e8f0", active_bg="#cbd5e1",
                  width=146, height=34,
                  font=("Segoe UI", 9, "bold")
                  ).pack(side=tk.LEFT)

    RoundedButton(row2, text="\U0001f5d1  Delete",
                  command=_delete_site,
                  bg="#fee2e2", fg="#991b1b",
                  hover_bg="#fecaca", active_bg="#fca5a5",
                  width=146, height=34,
                  font=("Segoe UI", 9, "bold")
                  ).pack(side=tk.RIGHT)

    RoundedButton(actions, text="\u2913  Export Report",
                  command=_export_report,
                  bg="#f1f5f9", fg=COLORS["ink"],
                  hover_bg="#e2e8f0", active_bg="#cbd5e1",
                  width=300, height=34,
                  font=("Segoe UI", 9, "bold")
                  ).pack(anchor="w", pady=(0, 5))

    # ---------- BOTTOM ----------
    footer = tk.Frame(inner, bg=COLORS["card"])
    footer.pack(fill=tk.X, pady=(10, 0))

    tk.Frame(footer, bg=COLORS["line"], height=1).pack(fill=tk.X, pady=(0, 10))

    RoundedButton(footer, text="\u21bb  Refresh",
                  command=_refresh_sites,
                  bg="#f1f5f9", fg=COLORS["ink"],
                  hover_bg="#e2e8f0", active_bg="#cbd5e1",
                  width=140, height=32,
                  font=("Segoe UI", 9, "bold")
                  ).pack(side=tk.LEFT)

    tk.Label(footer, text="\u25cf  Cloud: not configured",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 8)).pack(side=tk.RIGHT)

    return container


# =========================================================
# SITE DETAILS WINDOW
# =========================================================
def _open_site_details(site_id, is_mine=False):
    """Open a window showing a site's info + recent scans."""
    from core.cloud import local_db

    site = local_db.get_site(site_id)
    if not site:
        messagebox.showerror("Not found", "Site not found.",
                             parent=state.root)
        return

    dlg = tk.Toplevel(state.root)
    dlg.title(f"Site - {site['name']}")
    dlg.configure(bg=COLORS["card"])
    dlg.geometry("640x520")
    dlg.transient(state.root)
    dlg.minsize(500, 400)

    body = tk.Frame(dlg, bg=COLORS["card"])
    body.pack(fill=tk.BOTH, expand=True, padx=20, pady=18)

    # Title
    title_row = tk.Frame(body, bg=COLORS["card"])
    title_row.pack(fill=tk.X, anchor="w")
    tk.Label(title_row, text=site["name"],
             bg=COLORS["card"], fg=COLORS["ink"],
             font=("Segoe UI", 15, "bold")).pack(side=tk.LEFT)

    if is_mine:
        badge = tk.Frame(title_row, bg=COLORS["blue_pale"])
        badge.pack(side=tk.LEFT, padx=(10, 0))
        tk.Label(badge, text="★ This PC",
                 bg=COLORS["blue_pale"], fg=COLORS["blue"],
                 font=("Segoe UI", 8, "bold"),
                 padx=8, pady=3).pack()

    tk.Label(body, text=f"Location: {site.get('location') or '-'}   "
                        f"PC: {site.get('pc_name') or '-'}",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 12))

    # ---------- NVRS ----------
    tk.Label(body, text="NVRS",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 8, "bold")).pack(anchor="w")

    nvr_frame = tk.Frame(body, bg=COLORS["card"])
    nvr_frame.pack(fill=tk.X, pady=(2, 12))
    nvrs = local_db.get_nvrs_for_site(site_id)
    if nvrs:
        for n in nvrs:
            tk.Label(nvr_frame, text=f"  {n['url']}  -  {n['username']}",
                     bg=COLORS["card"], fg=COLORS["ink"],
                     font=("Consolas", 9)).pack(anchor="w")
    else:
        tk.Label(nvr_frame, text="  (no NVRs)",
                 bg=COLORS["card"], fg=COLORS["muted"],
                 font=("Segoe UI", 9)).pack(anchor="w")

    # ---------- RECENT SCANS ----------
    tk.Label(body, text="RECENT SCANS",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(6, 4))

    scans_wrap = RoundedFrame(body, radius=8, bg="#f8fafc",
                              border=COLORS["line"], padding=8,
                              width=560, height=200)
    scans_wrap.pack(fill=tk.BOTH, expand=True)

    scans_text = tk.Text(scans_wrap.inner, font=("Consolas", 9),
                         bg="#f8fafc", fg=COLORS["ink"],
                         relief=tk.FLAT, wrap="none",
                         highlightthickness=0)
    scans_text.pack(fill=tk.BOTH, expand=True)

    reports = local_db.get_recent_reports(site_id, limit=50)
    if not reports:
        scans_text.insert(tk.END, "  (no scans yet)")
    else:
        scans_text.insert(
            tk.END,
            f"{'Date':<22}{'Total':>6}{'Online':>8}{'Offline':>9}\n"
        )
        scans_text.insert(tk.END, "-" * 45 + "\n")
        for r in reports:
            scans_text.insert(
                tk.END,
                f"{r['started_at']:<22}"
                f"{r.get('total_cameras', 0):>6}"
                f"{r.get('online_cameras', 0):>8}"
                f"{r.get('offline_cameras', 0):>9}\n"
            )
    scans_text.config(state="disabled")

    # ---------- CLOSE ----------
    RoundedButton(body, text="Close",
                  command=dlg.destroy,
                  bg="#f1f5f9", fg=COLORS["ink"],
                  hover_bg="#e2e8f0", active_bg="#cbd5e1",
                  width=120, height=34,
                  font=("Segoe UI", 9, "bold")
                  ).pack(anchor="w", pady=(12, 0))


# =========================================================
# EXPORT HELPER
# =========================================================
def _export_latest_report(site_id):
    """Open the latest Excel for this site, or show its details."""
    from core.cloud import local_db
    reports = local_db.get_recent_reports(site_id, limit=1)
    if not reports:
        messagebox.showinfo("No reports",
                            "This site has no scans yet.",
                            parent=state.root)
        return
    r = reports[0]
    path = r.get("excel_path") or ""
    if path and __import__("os").path.exists(path):
        try:
            __import__("os").startfile(path)
            return
        except Exception:
            pass
    messagebox.showinfo(
        "Report",
        f"Latest report for this site:\n"
        f"Date: {r['started_at']}\n"
        f"Cameras: {r.get('total_cameras', 0)}\n"
        f"Online: {r.get('online_cameras', 0)}\n"
        f"Offline: {r.get('offline_cameras', 0)}\n\n"
        f"Excel path: {path or '(not saved)'}",
        parent=state.root,
    )