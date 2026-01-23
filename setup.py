# setup.py
import PyInstaller.__main__
import os

PyInstaller.__main__.run([
    'main.py',
    '--onefile',
    '--windowed',
    '--icon=images/logo.ico',
    '--name=NVR SyncGuard',
    '--add-data=images/logo.png;images',
    '--add-data=images/logo.ico;images',
])