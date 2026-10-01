"""
Password dialogs and the scheduled auto-close dialog.

Holds every Tk dialog that used to live at module level in main.py:
  - _prompt_password               (authorization prompt)
  - request_admin_authorization    (wrapper around the prompt + verify)
  - _open_change_password_dialog   (change password)
  - _schedule_auto_close           (background thread that triggers close)
  - _perform_auto_close            (the actual close dialog)

Depends on auth.py for password verification and on state for the root
window reference.
"""

import time
import threading
import tkinter as tk
from tkinter import messagebox

import state
from auth import _verify_admin_password, _set_new_admin_password, ADMIN_STATE
from config import config
from logger import log_line


# =========================================================
# AUTHORIZATION PROMPT
# =========================================================
def _prompt_password(parent, reason=""):
    """Show a modal password prompt. Returns the entered string, or None
    if the user cancels."""
    dlg = tk.Toplevel(parent) if parent else tk.Toplevel()
    dlg.title("Authorization required")
    dlg.configure(bg="#ffffff")
    dlg.resizable(False, False)
    dlg.transient(parent)
    dlg.grab_set()

    msg = "Enter the administrator password to continue."
    if reason:
        msg = f"{reason}\n\n{msg}"

    tk.Label(dlg, text=msg, bg="#ffffff", fg="#0f172a",
             font=("Segoe UI", 10, "bold"),
             justify="left", wraplength=340).pack(padx=20, pady=(18, 8))

    entry = tk.Entry(dlg, show="\u25cf", font=("Segoe UI", 11),
                     bg="#f1f5f9", relief=tk.FLAT, width=30)
    entry.pack(padx=20, pady=(0, 10), ipady=8)
    entry.focus_set()

    result = {"value": None}

    def ok():
        result["value"] = entry.get()
        dlg.destroy()

    def cancel():
        result["value"] = None
        dlg.destroy()

    btn_row = tk.Frame(dlg, bg="#ffffff")
    btn_row.pack(padx=20, pady=(0, 16), fill=tk.X)
    tk.Button(btn_row, text="Cancel", command=cancel,
              bg="#f1f5f9", fg="#0f172a", relief=tk.FLAT,
              font=("Segoe UI", 10), padx=14, pady=6).pack(side=tk.RIGHT, padx=(6, 0))
    tk.Button(btn_row, text="Authorize", command=ok,
              bg="#2563eb", fg="#ffffff", relief=tk.FLAT,
              font=("Segoe UI", 10, "bold"), padx=14, pady=6).pack(side=tk.RIGHT)

    dlg.bind("<Return>", lambda e: ok())
    dlg.bind("<Escape>", lambda e: cancel())

    dlg.update_idletasks()
    try:
        x = (dlg.winfo_screenwidth() - dlg.winfo_width()) // 2
        y = (dlg.winfo_screenheight() - dlg.winfo_height()) // 3
        dlg.geometry(f"+{x}+{y}")
    except Exception:
        pass

    if parent:
        parent.wait_window(dlg)
    else:
        dlg.wait_window()
    return result["value"]


def request_admin_authorization(parent=None, reason=""):
    """Prompt for the password and verify it. Returns True if authorized."""
    # Refresh ADMIN_STATE from the live config - the password might have
    # been changed in this session.
    ADMIN_STATE["hash"] = (config.get("ADMIN_PASSWORD_HASH")
                           or ADMIN_STATE.get("hash", "")).strip()
    ADMIN_STATE["salt"] = (config.get("ADMIN_PASSWORD_SALT")
                           or ADMIN_STATE.get("salt", "")).strip()

    pwd = _prompt_password(parent, reason)
    if pwd is None:
        return False
    if _verify_admin_password(pwd):
        return True
    messagebox.showerror("Denied", "Incorrect administrator password.",
                         parent=parent)
    return False


# =========================================================
# CHANGE PASSWORD DIALOG
# =========================================================
def _open_change_password_dialog(parent=None):
    dlg = tk.Toplevel(parent) if parent else tk.Toplevel()
    dlg.title("Change administrator password")
    dlg.configure(bg="#ffffff")
    dlg.resizable(False, False)
    dlg.transient(parent)
    dlg.grab_set()

    tk.Label(dlg, text="Change administrator password",
             bg="#ffffff", fg="#0f172a",
             font=("Segoe UI", 13, "bold")).pack(padx=24, pady=(20, 4))
    tk.Label(dlg, text="Used to authorize NVR removal and folder changes.",
             bg="#ffffff", fg="#64748b",
             font=("Segoe UI", 9)).pack(padx=24, pady=(0, 14))

    tk.Label(dlg, text="Current password", bg="#ffffff", fg="#64748b",
             font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=24)
    e_cur = tk.Entry(dlg, show="\u25cf", font=("Segoe UI", 11),
                     bg="#f1f5f9", relief=tk.FLAT, width=32)
    e_cur.pack(padx=24, pady=(2, 10), ipady=8)

    tk.Label(dlg, text="New password", bg="#ffffff", fg="#64748b",
             font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=24)
    e_new = tk.Entry(dlg, show="\u25cf", font=("Segoe UI", 11),
                     bg="#f1f5f9", relief=tk.FLAT, width=32)
    e_new.pack(padx=24, pady=(2, 10), ipady=8)

    tk.Label(dlg, text="Confirm new password", bg="#ffffff", fg="#64748b",
             font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=24)
    e_cnf = tk.Entry(dlg, show="\u25cf", font=("Segoe UI", 11),
                     bg="#f1f5f9", relief=tk.FLAT, width=32)
    e_cnf.pack(padx=24, pady=(2, 14), ipady=8)

    def save():
        cur = e_cur.get()
        new1 = e_new.get()
        new2 = e_cnf.get()

        if not cur:
            messagebox.showwarning("Missing",
                                   "Enter the current password.", parent=dlg)
            return
        if not _verify_admin_password(cur):
            messagebox.showerror("Denied",
                                 "Current password is incorrect.", parent=dlg)
            return
        if len(new1) < 6:
            messagebox.showwarning("Too short",
                                   "New password must be at least 6 characters.",
                                   parent=dlg)
            return
        if new1 != new2:
            messagebox.showwarning("Mismatch",
                                   "New passwords do not match.", parent=dlg)
            return
        if new1 == cur:
            messagebox.showwarning("No change",
                                   "New password must differ from the current one.",
                                   parent=dlg)
            return

        _set_new_admin_password(new1)
        messagebox.showinfo("Saved",
                            "Administrator password updated.", parent=dlg)
        dlg.destroy()

    def cancel():
        dlg.destroy()

    row = tk.Frame(dlg, bg="#ffffff")
    row.pack(fill=tk.X, padx=24, pady=(0, 18))
    tk.Button(row, text="Cancel", command=cancel,
              bg="#f1f5f9", fg="#0f172a", relief=tk.FLAT,
              font=("Segoe UI", 10), padx=14, pady=6).pack(side=tk.RIGHT, padx=(6, 0))
    tk.Button(row, text="Save", command=save,
              bg="#2563eb", fg="#ffffff", relief=tk.FLAT,
              font=("Segoe UI", 10, "bold"), padx=14, pady=6).pack(side=tk.RIGHT)

    e_cur.focus_set()
    dlg.bind("<Return>", lambda e: save())
    dlg.bind("<Escape>", lambda e: cancel())

    dlg.update_idletasks()
    try:
        x = (dlg.winfo_screenwidth() - dlg.winfo_width()) // 2
        y = (dlg.winfo_screenheight() - dlg.winfo_height()) // 3
        dlg.geometry(f"+{x}+{y}")
    except Exception:
        pass

    if parent:
        parent.wait_window(dlg)
    else:
        dlg.wait_window()


# =========================================================
# AUTO-CLOSE
# =========================================================
def _schedule_auto_close():
    """Spawn a daemon thread that waits for the configured time and then
    asks the main thread to show the auto-close dialog."""
    if not state.AUTO_CLOSE_ENABLED:
        return

    def _worker():
        last_fired_date = None
        while True:
            try:
                from datetime import datetime
                now = datetime.now()
                if (now.hour == state.AUTO_CLOSE_HOUR
                        and now.minute == state.AUTO_CLOSE_MINUTE
                        and last_fired_date != now.date()):
                    last_fired_date = now.date()
                    try:
                        if state.root is not None:
                            state.root.after(0, _perform_auto_close)
                    except Exception:
                        pass
            except Exception:
                pass
            time.sleep(20)

    threading.Thread(target=_worker, daemon=True).start()


def _perform_auto_close():
    """Show a 10-second countdown dialog, then quit the app."""
    try:
        state.stop_requested = True
    except Exception:
        pass

    root = state.root
    if root is None:
        return

    dlg = tk.Toplevel(root)
    dlg.title("Auto-close")
    dlg.configure(bg="#ffffff")
    dlg.resizable(False, False)
    dlg.transient(root)
    dlg.grab_set()

    tk.Label(dlg, text="Scheduled auto-close", bg="#ffffff", fg="#0f172a",
             font=("Segoe UI", 14, "bold")).pack(padx=26, pady=(22, 4))

    tk.Label(dlg,
             text=f"It is now {state.AUTO_CLOSE_HOUR:02d}:{state.AUTO_CLOSE_MINUTE:02d}. "
                  "The application will close automatically.",
             bg="#ffffff", fg="#475569",
             font=("Segoe UI", 10), wraplength=340,
             justify="center").pack(padx=26, pady=(0, 10))

    countdown_lbl = tk.Label(dlg, text="Closing in 10 seconds...",
                             bg="#ffffff", fg="#dc2626",
                             font=("Segoe UI", 11, "bold"))
    countdown_lbl.pack(padx=26, pady=(0, 16))

    counter = {"remaining": 10}

    def _force_close():
        try:
            dlg.destroy()
        except Exception:
            pass
        try:
            root.quit()
        except Exception:
            pass
        try:
            root.destroy()
        except Exception:
            pass
        try:
            import os
            os._exit(0)
        except Exception:
            pass

    def _tick():
        try:
            if counter["remaining"] <= 0:
                _force_close()
                return
            plural = "s" if counter["remaining"] != 1 else ""
            countdown_lbl.config(
                text=f"Closing in {counter['remaining']} second{plural}...")
            counter["remaining"] -= 1
            dlg.after(1000, _tick)
        except Exception:
            _force_close()

    def _cancel():
        try:
            dlg.destroy()
        except Exception:
            pass

    tk.Button(dlg, text="Cancel auto-close", command=_cancel,
              bg="#f1f5f9", fg="#0f172a", relief=tk.FLAT,
              font=("Segoe UI", 10), padx=14, pady=6).pack(pady=(0, 20))

    dlg.protocol("WM_DELETE_WINDOW", _cancel)
    dlg.update_idletasks()
    try:
        x = (dlg.winfo_screenwidth() - dlg.winfo_width()) // 2
        y = (dlg.winfo_screenheight() - dlg.winfo_height()) // 3
        dlg.geometry(f"+{x}+{y}")
    except Exception:
        pass
    dlg.after(1000, _tick)