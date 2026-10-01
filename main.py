"""
NVR SyncGuard - Entry point.

The real code lives in:
    paths, logger, config, state, auth          (foundation)
    core/*                                      (business logic)
    workers/*                                   (background threads)
    ui/*                                        (Tk GUI)
    tray/tray.py                                (system tray)
    actions.py                                  (UI commands)

This file only wires them together and calls ui.window.main().
"""

import sys

from logger import log_line
from state import AUTOSTART_WITH_WINDOWS
from core.autostart import register_autostart, is_autostart_registered


def _run():
    # Register autostart on first launch if enabled
    if AUTOSTART_WITH_WINDOWS and not is_autostart_registered():
        try:
            register_autostart()
        except Exception as e:
            log_line(f"[AUTOSTART] First-run register failed: {e}")

    # Launch the GUI (start_hidden=True when launched with --background)
    from ui.window import main
    start_hidden = "--background" in sys.argv
    main(start_hidden=start_hidden)


if __name__ == "__main__":
    try:
        _run()
    except Exception:
        import traceback
        tb = traceback.format_exc()
        log_line(f"[FATAL] {tb}")
        try:
            print(tb)
            input("\nPress Enter to close...")
        except Exception:
            pass