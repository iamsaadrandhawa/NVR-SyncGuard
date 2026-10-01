"""
Tk widget proxies.

Two families of proxies live here:

1. Tk*Proxy  - wrap a real Tk widget and marshal every call to the main
   thread via `root.after(0, ...)`. Used by code that runs in worker
   threads but needs to update the UI.

2. UiQueue*  - do not touch Tk at all; they push updates onto
   state.UI_QUEUE. The main thread reads this queue in its pump loop and
   applies the updates. Preferred for background workers because it never
   blocks and can never deadlock on Tk.

Both families expose the same method names (`insert`, `delete`, `see`,
`config`, `get_children`) so calling code does not need to know which one
it is using.
"""

import tkinter as tk

import state


# =========================================================
# TK WIDGET PROXIES (thread -> main thread via root.after)
# =========================================================
class TkLogProxy:
    """Wrap a Text/ScrolledText widget. All calls are marshalled to the
    main thread."""

    def __init__(self, widget):
        self.widget = widget

    def insert(self, *args):
        if state.root is None:
            return
        state.root.after(0, lambda: self.widget.insert(*args))

    def delete(self, *args):
        if state.root is None:
            return
        state.root.after(0, lambda: self.widget.delete(*args))

    def see(self, *args):
        if state.root is None:
            return
        state.root.after(0, lambda: self.widget.see(*args))


class TkTreeProxy:
    """Wrap a ttk.Treeview widget."""

    def __init__(self, widget):
        self.widget = widget

    def insert(self, *args, **kwargs):
        if state.root is None:
            return
        state.root.after(0, lambda: self.widget.insert(*args, **kwargs))

    def delete(self, *args):
        if state.root is None:
            return
        state.root.after(0, lambda: self.widget.delete(*args))

    def get_children(self):
        return self.widget.get_children()


class TkLabelProxy:
    """Wrap a Label widget (used for the status line)."""

    def __init__(self, widget):
        self.widget = widget

    def config(self, **kwargs):
        if state.root is None:
            return
        state.root.after(0, lambda: self.widget.config(**kwargs))


# =========================================================
# UI-QUEUE PROXIES (thread-safe, do not touch Tk)
# =========================================================
class UiQueueLog:
    """Log sink for background workers. Writes to the log file AND pushes
    the line to state.UI_QUEUE for the main thread to insert."""

    def insert(self, *a, **k):
        try:
            txt = str(a[1] if len(a) > 1 else (a[0] if a else ""))
            from logger import log_line
            log_line(txt.rstrip("\n"))
            state.UI_QUEUE.put(("log", txt))
        except Exception:
            pass

    def delete(self, *a, **k):
        pass

    def see(self, *a, **k):
        pass


class UiQueueTree:
    """Treeview sink for background workers. Pushes insert calls to
    state.UI_QUEUE. `get_children` always returns an empty list because
    a background thread cannot safely read the treeview."""

    def insert(self, *a, **k):
        state.UI_QUEUE.put(("tree", (a, k)))

    def delete(self, *a, **k):
        pass

    def get_children(self):
        return []


class UiQueueStatus:
    """Status-label sink for background workers."""

    def config(self, **k):
        state.UI_QUEUE.put(("status", k))