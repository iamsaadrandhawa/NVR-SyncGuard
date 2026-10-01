"""
Toast notifications.

Three backends tried in order:
  1. winotify  - modern Windows 10/11 toast notifications
  2. win10toast - legacy fallback
  3. Tk popup   - last-resort corner popup if no toast library is present

Public function: show_toast(title, message)
Reads state.SHOW_TOASTS and state.root.
"""

import tkinter as tk

import state
from logger import log_line


def _toast_winotify(title, message):
    """Modern Windows toast. Returns True if shown."""
    try:
        from winotify import Notification
        toast = Notification(
            app_id="NVR SyncGuard",
            title=title,
            msg=message,
            duration="short",
        )
        toast.show()
        return True
    except Exception as e:
        log_line(f"[WARN] winotify failed: {e}")
        return False


def _toast_win10toast(title, message):
    """Legacy toast. Returns True if shown."""
    try:
        from win10toast import ToastNotifier
        ToastNotifier().show_toast(
            title, message, duration=6, threaded=True,
        )
        return True
    except Exception as e:
        log_line(f"[WARN] win10toast failed: {e}")
        return False


def _toast_tk_fallback(title, message):
    """Show a small always-on-top Tk popup in the bottom-right corner.
    Requires state.root to exist; returns False otherwise."""
    try:
        def _show():
            try:
                popup = tk.Toplevel()
                popup.title("NVR SyncGuard")
                popup.configure(bg="#0b1220")
                popup.attributes("-topmost", True)
                popup.geometry("420x140+{}+{}".format(
                    popup.winfo_screenwidth() - 440,
                    popup.winfo_screenheight() - 200,
                ))
                tk.Label(popup, text=title, bg="#0b1220", fg="#ffffff",
                         font=("Segoe UI", 12, "bold")).pack(pady=(14, 4))
                tk.Label(popup, text=message, bg="#0b1220", fg="#cbd5e1",
                         font=("Segoe UI", 10), wraplength=380,
                         justify="center").pack(pady=(0, 14))
                popup.after(7000, popup.destroy)
            except Exception:
                pass

        if state.root is not None:
            state.root.after(0, _show)
            return True
        return False
    except Exception as e:
        log_line(f"[WARN] Tk toast fallback failed: {e}")
        return False


def show_toast(title, message):
    """Show a toast via the first available backend.

    Does nothing if state.SHOW_TOASTS is False. Always logs the attempt.
    """
    if not state.SHOW_TOASTS:
        return
    log_line(f"[TOAST] {title} — {message}")

    if _toast_winotify(title, message):
        return
    if _toast_win10toast(title, message):
        return
    _toast_tk_fallback(title, message)