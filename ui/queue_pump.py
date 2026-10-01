"""
UI queue pump and stats refresher.

Two functions that were inner closures inside main() in the original:

  _pump_ui_queue  - drains state.UI_QUEUE and applies updates to the log
                    widget, the ping widget, the tree, and the status label.
  update_stats    - periodically refreshes the six stat cards and the
                    running-state painter.

Both are wired to the Tk event loop by ui/window.py via root.after().
"""

import os
import queue
import tkinter as tk

import state


def _pump_ui_queue(log_widget, ping_widget, tree, status_label_widget,
                   ping_count_lbl):
    """Drain state.UI_QUEUE. Re-registers itself via root.after(300, ...).

    Each message is a tuple (kind, payload) where kind is one of:
      "log"      - insert text into the Activity log
      "ping_log" - insert text into the Ping monitor panel
      "tree"     - insert a row into the camera Treeview
      "status"   - call status_label_widget.config(**payload)
      "stats"    - refresh the offline-camera count label
    """
    try:
        # Drain up to 200 messages per tick so a flood does not freeze the UI
        for _ in range(200):
            kind, payload = state.UI_QUEUE.get_nowait()

            if kind == "ping_log":
                try:
                    ping_widget.insert(tk.END, payload + "\n")
                    total_lines = int(ping_widget.index("end-1c").split(".")[0])
                    if total_lines > state.PING_LOG_MAX:
                        ping_widget.delete("1.0", "2.0")
                    ping_widget.see(tk.END)
                except Exception:
                    pass

            elif kind == "log":
                try:
                    log_widget.insert(tk.END, payload)
                    if int(log_widget.index("end-1c").split(".")[0]) > 5000:
                        log_widget.delete("1.0", "500.0")
                    log_widget.see(tk.END)
                except Exception:
                    pass

            elif kind == "tree":
                try:
                    a, k = payload
                    tree.insert(*a, **k)
                except Exception:
                    pass

            elif kind == "status":
                try:
                    status_label_widget.config(**payload)
                except Exception:
                    pass

            elif kind == "stats":
                try:
                    with state.OFFLINE_CAMERA_LOCK:
                        n_cam_off = len(state.OFFLINE_CAMERA_IPS)
                    ping_count_lbl.config(
                        text=f"{n_cam_off} offline camera"
                             f"{'s' if n_cam_off != 1 else ''}")
                except Exception:
                    pass

    except queue.Empty:
        pass

    if state.root is not None:
        state.root.after(
            300, _pump_ui_queue,
            log_widget, ping_widget, tree, status_label_widget, ping_count_lbl,
        )


def update_stats(stat_widgets, apply_running_state_fn, last_saved_label):
    """Refresh the six stat cards and re-register every 800 ms.

    stat_widgets is a dict with keys:
      nvr_total, nvr_checked, nvr_skipped,
      cam_total, cam_online, cam_offline

    apply_running_state_fn is the callback defined in ui/window.py that
    swaps the START/RUNNING button colors and subtitle text.
    """
    try:
        stat_widgets["nvr_total"].config(text=str(len(state.NVR_LIST)))
        stat_widgets["nvr_checked"].config(text=str(state.CHECKED_NVRS))
        stat_widgets["nvr_skipped"].config(text=str(state.SKIPPED_NVRS))
        stat_widgets["cam_total"].config(text=str(state.total_cameras_count))
        stat_widgets["cam_online"].config(text=str(state.online_cameras_count))
        stat_widgets["cam_offline"].config(text=str(state.offline_cameras_count))
    except Exception:
        pass

    if state.last_saved_file:
        try:
            last_saved_label.config(
                text=f"Last: {os.path.basename(state.last_saved_file)}")
        except Exception:
            pass

    try:
        apply_running_state_fn()
    except Exception:
        pass

    if state.root is not None:
        state.root.after(
            800, update_stats,
            stat_widgets, apply_running_state_fn, last_saved_label,
        )