"""
UI colour palette.

Single source of truth for every colour used in the app. Previously this
was a local dict inside main(), which meant workers and dialogs could not
read it. Now anything can do:

    from ui.theme import COLORS
    COLORS["blue"]
"""

COLORS = {
    # Backgrounds
    "bg": "#eef2f6",
    "card": "#ffffff",

    # Text
    "ink": "#0f172a",
    "ink_soft": "#1e293b",
    "muted": "#64748b",
    "line": "#e2e8f0",

    # Blue (primary)
    "blue": "#2563eb",
    "blue_dark": "#1d4ed8",
    "blue_pale": "#eff6ff",
    "blue_border": "#bfdbfe",

    # Red (danger / offline)
    "red": "#dc2626",
    "red_dark": "#b91c1c",
    "red_pale": "#fef2f2",
    "red_border": "#fecaca",

    # Green (success / online)
    "green": "#059669",
    "green_pale": "#ecfdf5",
    "green_border": "#a7f3d0",

    # Amber (warning)
    "amber": "#d97706",
    "amber_pale": "#fffbeb",

    # Purple (info accents)
    "purple": "#6d28d9",
    "purple_pale": "#f5f3ff",
    "purple_border": "#ddd6fe",

    # Header / dark chrome
    "header": "#0b1220",
    "header_2": "#111827",
    "chip": "#1f2937",
}