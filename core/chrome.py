"""
Chrome / ChromeDriver helpers.

Finds the Chrome browser, finds (or downloads) a matching ChromeDriver, and
builds a Selenium Options object. Uses drivers/chromedriver.exe bundled with
the app when present, falls back to webdriver_manager otherwise.
"""

import os
import shutil
import subprocess
import winreg

from selenium.webdriver.chrome.options import Options

from paths import CHROMEDRIVER_PATH
from logger import log_line
import state


def find_chrome_path():
    """Locate chrome.exe. Registry first, then common install paths, then PATH."""
    chrome_paths = [
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""),
                     "Google\\Chrome\\Application\\chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", ""),
                     "Google\\Chrome\\Application\\chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""),
                     "Google\\Chrome\\Application\\chrome.exe"),
    ]

    # 1) Windows registry "App Paths"
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
        )
        chrome_path = winreg.QueryValue(key, None)
        winreg.CloseKey(key)
        if os.path.exists(chrome_path):
            return chrome_path
    except Exception:
        pass

    # 2) Common install locations
    for path in chrome_paths:
        if os.path.exists(path):
            return path

    # 3) Anything on PATH
    try:
        result = subprocess.run(["where", "chrome"],
                                capture_output=True, text=True)
        if result.returncode == 0:
            paths = result.stdout.strip().split("\n")
            if paths and os.path.exists(paths[0]):
                return paths[0]
    except Exception:
        pass

    return None


def get_chromedriver_path(log=None):
    """Return the path to a usable chromedriver.exe.

    Priority:
      1. drivers/chromedriver.exe bundled with the app (paths.CHROMEDRIVER_PATH)
      2. webdriver_manager download
      3. chromedriver on PATH
      4. Common webdriver_manager cache locations
    """
    # 1) Bundled driver
    try:
        if os.path.exists(CHROMEDRIVER_PATH):
            return CHROMEDRIVER_PATH
    except Exception:
        pass

    # 2) webdriver_manager
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        return ChromeDriverManager().install()
    except Exception as e:
        log_line(f"[WARN] WebDriverManager failed: {e}")

    # 3) PATH
    try:
        found = shutil.which("chromedriver")
        if found:
            return found
    except Exception:
        pass

    # 4) Common cache folders
    common_paths = [
        os.path.join(os.environ.get("USERPROFILE", ""),
                     ".wdm", "drivers", "chromedriver", "win64"),
        os.path.join(os.environ.get("USERPROFILE", ""),
                     ".cache", "selenium", "chromedriver"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "chromedriver.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "chromedriver.exe"),
    ]
    for base_path in common_paths:
        if os.path.exists(base_path):
            for rt, _dirs, files in os.walk(base_path):
                for file in files:
                    if file in ("chromedriver.exe", "chromedriver"):
                        return os.path.join(rt, file)

    return None


def setup_chrome_driver(log=None):
    """Build a Selenium Chrome Options object with all the flags we need.

    Headless when running in background mode and no manual scan is active;
    visible otherwise so the user can watch a foreground scan.
    """
    options = Options()

    chrome_path = find_chrome_path()
    if chrome_path:
        options.binary_location = chrome_path

    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--log-level=3")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--remote-allow-origins=*")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-features=NetworkService")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--page-load-strategy=eager")

    if state.BACKGROUND_MODE and not _manual_scan_in_progress():
        options.add_argument("--headless=new")
    else:
        options.add_argument("--start-maximized")

    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    options.add_experimental_option("useAutomationExtension", False)
    prefs = {
        "profile.default_content_setting_values.notifications": 2,
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
    }
    options.add_experimental_option("prefs", prefs)
    return options


def _manual_scan_in_progress():
    """True when a user-initiated (not background) scan is currently running."""
    try:
        return bool(state.scan_running) and not state._background_scan_flag[0]
    except Exception:
        return False