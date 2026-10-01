"""
Custom Tk widgets: rounded frames, buttons and entries.

Tk has no built-in rounded corners, so each widget is a Canvas with a
smooth polygon drawn on it. This module is self-contained - it imports
only tkinter and does not depend on the rest of the app.
"""

import tkinter as tk


# =========================================================
# SHAPE HELPERS
# =========================================================
def _round_rect(canvas, x1, y1, x2, y2, r, **kwargs):
    """Draw a rounded rectangle on a canvas using a smooth polygon."""
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def _safe_parent_bg(widget, fallback="#eef2f6"):
    """Return a widget's background colour, or a fallback if it has none."""
    try:
        return widget.cget("bg")
    except Exception:
        return fallback


# =========================================================
# ROUNDED FRAME
# =========================================================
class RoundedFrame:
    """A card-like container with a rounded rectangle background.

    Usage:
        card = RoundedFrame(parent, radius=16, bg="#ffffff",
                            border="#e2e8f0", padding=20)
        card.pack(fill=tk.BOTH, expand=True)
        tk.Label(card.inner, text="Hello").pack()   # put children in .inner
    """

    def __init__(self, parent, radius=14, bg="#ffffff", border="#e2e8f0",
                 border_width=1, padding=0, width=200, height=100):
        parent_bg = _safe_parent_bg(parent)

        self.outer = tk.Frame(parent, bg=parent_bg, width=width, height=height,
                              highlightthickness=0, bd=0)
        self.outer.pack_propagate(False)
        self.outer.grid_propagate(False)

        self.canvas = tk.Canvas(self.outer, highlightthickness=0, bd=0,
                                bg=parent_bg)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)

        self.inner = tk.Frame(self.outer, bg=bg)
        self.inner.place(x=padding, y=padding,
                         relwidth=1, relheight=1,
                         width=-2 * padding, height=-2 * padding)

        self._radius = radius
        self._bg = bg
        self._border = border
        self._bw = border_width
        self._w = width
        self._h = height

        self.outer.bind("<Configure>", self._redraw)
        self.outer.after(80, self._redraw)

    def _redraw(self, event=None):
        w = self.outer.winfo_width() or self._w
        h = self.outer.winfo_height() or self._h
        if w < 4 or h < 4:
            return
        self.canvas.delete("all")
        _round_rect(self.canvas, 1, 1, w - 1, h - 1, self._radius,
                    fill=self._bg, outline=self._border, width=self._bw)

    # Convenience passthroughs so this behaves like a normal widget
    def configure(self, **kwargs):
        return self.outer.configure(**kwargs)

    def config(self, **kwargs):
        return self.outer.configure(**kwargs)

    def pack(self, **kwargs):
        return self.outer.pack(**kwargs)

    def grid(self, **kwargs):
        return self.outer.grid(**kwargs)

    def place(self, **kwargs):
        return self.outer.place(**kwargs)


# =========================================================
# ROUNDED BUTTON
# =========================================================
class RoundedButton:
    """A clickable rounded button drawn on a canvas.

    Usage:
        b = RoundedButton(parent, text="Save", command=save_fn)
        b.pack(side=tk.LEFT)
        b.set_text("Saving...")
        b.set_colors(bg="#dc2626", hover="#b91c1c")
        b.set_state("disabled")   # or "normal"
    """

    def __init__(self, parent, text, command=None, radius=10,
                 bg="#2563eb", fg="#ffffff", hover_bg="#1d4ed8",
                 active_bg="#1e40af", width=140, height=40,
                 font=("Segoe UI", 10, "bold")):
        parent_bg = _safe_parent_bg(parent)

        self.canvas = tk.Canvas(parent, width=width, height=height,
                                highlightthickness=0, bd=0,
                                bg=parent_bg, cursor="hand2")
        self.command = command
        self.radius = radius
        self._bg = bg
        self._fg = fg
        self._hover = hover_bg
        self._active = active_bg
        self._text = text
        self._font = font
        self._w = width
        self._h = height
        self._enabled = True

        self.canvas.bind("<Configure>", self._draw)
        self.canvas.bind("<Enter>",
                         lambda e: self._paint(self._hover) if self._enabled else None)
        self.canvas.bind("<Leave>", lambda e: self._paint(self._bg))
        self.canvas.bind("<ButtonPress-1>",
                         lambda e: self._paint(self._active) if self._enabled else None)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        self.canvas.after(80, self._draw)

    def _draw(self, event=None):
        self.canvas.delete("all")
        w = self.canvas.winfo_width() or self._w
        h = self.canvas.winfo_height() or self._h
        if w < 4 or h < 4:
            w, h = self._w, self._h
        _round_rect(self.canvas, 1, 1, w - 1, h - 1, self.radius,
                    fill=self._bg, outline="", tags="shape")
        self.canvas.create_text(w / 2, h / 2, text=self._text,
                                fill=self._fg, font=self._font, tags="label")

    def _paint(self, color):
        try:
            self.canvas.itemconfigure("shape", fill=color)
        except Exception:
            pass

    def _on_release(self, event):
        if not self._enabled:
            return
        inside = (0 <= event.x <= self.canvas.winfo_width()
                  and 0 <= event.y <= self.canvas.winfo_height())
        self._paint(self._hover if inside else self._bg)
        if inside and self.command:
            self.command()

    def set_text(self, text):
        self._text = text
        self._draw()

    def set_colors(self, bg=None, hover=None, active=None, fg=None):
        if bg:
            self._bg = bg
        if hover:
            self._hover = hover
        if active:
            self._active = active
        if fg:
            self._fg = fg
        self._draw()

    def set_state(self, state):
        self._enabled = (state == "normal")
        self.canvas.configure(cursor="hand2" if self._enabled else "arrow")

    # Layout passthroughs
    def pack(self, **kwargs):
        return self.canvas.pack(**kwargs)

    def grid(self, **kwargs):
        return self.canvas.grid(**kwargs)

    def place(self, **kwargs):
        return self.canvas.place(**kwargs)

    def configure(self, **kwargs):
        return self.canvas.configure(**kwargs)


# =========================================================
# ROUNDED ENTRY
# =========================================================
class RoundedEntry:
    """A text input with rounded border and focus highlight.

    Exposes a `.var` (StringVar) and `.entry` (the inner tk.Entry) so
    callers can bind events, toggle `show`, or read/write values directly.
    """

    def __init__(self, parent, radius=10, bg="#ffffff", border="#cbd5e1",
                 focus_border="#2563eb", font=("Segoe UI", 10),
                 placeholder="", show=None, width=300, height=42):
        parent_bg = _safe_parent_bg(parent)

        self.outer = tk.Frame(parent, bg=parent_bg, width=width, height=height,
                              highlightthickness=0, bd=0)
        self.outer.pack_propagate(False)
        self.outer.grid_propagate(False)

        self.canvas = tk.Canvas(self.outer, highlightthickness=0, bd=0,
                                bg=parent_bg)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)

        self.radius = radius
        self._bg = bg
        self._border = border
        self._focus_border = focus_border
        self._w = width
        self._h = height
        self._focused = False

        self.var = tk.StringVar()
        self.entry = tk.Entry(self.outer, textvariable=self.var, bd=0,
                              relief="flat", bg=bg, fg="#0f172a",
                              insertbackground="#0f172a",
                              font=font, show=show or "",
                              highlightthickness=0)
        self.entry.place(x=14, y=10, relwidth=1, relheight=1,
                         width=-28, height=-20)

        self.entry.bind("<FocusIn>", self._on_focus_in)
        self.entry.bind("<FocusOut>", self._on_focus_out)

        self.outer.bind("<Configure>", self._redraw)
        self.outer.after(80, self._redraw)

    def _on_focus_in(self, event):
        self._focused = True
        self._redraw()

    def _on_focus_out(self, event):
        self._focused = False
        self._redraw()

    def _redraw(self, event=None):
        w = self.outer.winfo_width() or self._w
        h = self.outer.winfo_height() or self._h
        if w < 4 or h < 4:
            return
        self.canvas.delete("all")
        _round_rect(self.canvas, 1, 1, w - 1, h - 1, self.radius,
                    fill=self._bg,
                    outline=self._focus_border if self._focused else self._border,
                    width=1.4)

    # Value access
    def get(self):
        return self.var.get()

    def set(self, value):
        self.var.set(value)

    def delete(self, a, b):
        self.var.set("")

    def insert(self, index, value):
        self.var.set(value)

    def focus_set(self):
        self.entry.focus_set()

    # Layout passthroughs
    def pack(self, **kwargs):
        return self.outer.pack(**kwargs)

    def grid(self, **kwargs):
        return self.outer.grid(**kwargs)

    def place(self, **kwargs):
        return self.outer.place(**kwargs)

    def configure(self, **kwargs):
        return self.outer.configure(**kwargs)