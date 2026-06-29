# setup.py
import PyInstaller.__main__
import os
import sys

# Determine the correct separator for add-data
if sys.platform == 'win32':
    separator = ';'
else:
    separator = ':'

PyInstaller.__main__.run([
    'main.py',
    '--onefile',
    '--windowed',
    '--icon=images/logo.ico',
    '--name=NVR_SKP SyncGuard',  # Changed to underscore (no spaces is better)
    '--add-data=images/logo.png{}images'.format(separator),
    '--add-data=images/logo.ico{}images'.format(separator),
    '--hidden-import=openpyxl',
    '--hidden-import=PIL',
    '--hidden-import=selenium',
    '--hidden-import=webdriver_manager',
    '--collect-all=selenium.webdriver.chrome.service',
    '--collect-all=selenium.webdriver.chrome.options',
    '--collect-all=selenium.webdriver.common.by',
    '--collect-all=selenium.webdriver.support',
    '--collect-all=selenium.webdriver.support.ui',
])