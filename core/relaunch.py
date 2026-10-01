"""
Relaunch helper.

Spawns a fresh detached instance of the app and lets the current one exit.
Used by:
  - the Restart button in the UI
  - the tray's Restart menu item
  - the daily scheduled restart

Setting PYINSTALLER_RESET_ENVIRONMENT=1 is required for PyInstaller onefile
builds: without it, the new process would inherit the _MEIxxxx temp dir
pointers and crash.
"""

import os
import sys
import subprocess


def _spawn_new_instance():
    """Launch a detached copy of this app with --background.

    Never raises; failures are silently swallowed because the caller is
    usually about to exit anyway.
    """
    env = os.environ.copy()
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"

    flags = 0
    try:
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    except AttributeError:
        # Non-Windows or Python build missing these constants; fall back to 0.
        pass

    if getattr(sys, "frozen", False):
        # Running from a PyInstaller-built exe
        cmd = [sys.executable, "--background"]
    else:
        # Running from source: prefer pythonw.exe so no console appears
        pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        runner = pyw if os.path.exists(pyw) else sys.executable

        # __file__ points at this file (core/relaunch.py).
        # The real entry point is one level up: main.py.
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        main_script = os.path.join(project_root, "main.py")

        cmd = [runner, main_script, "--background"]

    subprocess.Popen(cmd, close_fds=True, env=env, creationflags=flags)