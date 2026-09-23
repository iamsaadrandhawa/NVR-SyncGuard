"""
NVR SyncGuard - Automated Time Synchronization & Camera Monitoring
Developed by Codraze
Version: 2.7.5 (bulletproof Excel writer — IP always lands in column C)
"""

import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

# --- Selenium (explicit imports for PyInstaller) ---
import selenium
import selenium.webdriver
import selenium.webdriver.common
import selenium.webdriver.chrome
import selenium.webdriver.chrome.service
import selenium.webdriver.chrome.options
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

# --- Other dependencies ---
from webdriver_manager.chrome import ChromeDriverManager
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from datetime import datetime, timedelta

import threading
import os
import time
import sys
import webbrowser
import re
import json
import subprocess
import winreg
import shutil
import tempfile
import importlib
import hashlib
import hmac
import secrets

try:
    import selenium.webdriver.chrome.webdriver
except ImportError:
    pass


# =========================================================
# CONFIG
# =========================================================
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    base_path = getattr(sys, "_MEIPASS", BASE_DIR)
    LOGO_PATH = os.path.join(base_path, "images", "logo.png")
    ICO_PATH = os.path.join(base_path, "images", "logo.ico")
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    LOGO_PATH = os.path.join(BASE_DIR, "images", "logo.png")
    ICO_PATH = os.path.join(BASE_DIR, "images", "logo.ico")

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

DEFAULT_ADMIN_PASSWORD = "Saad@18977"

DEFAULT_CONFIG = {
    "NVR_LIST": [],
    "DOWNLOADS_DIR": os.path.join(os.path.expanduser("~"), "Downloads"),
    "EXCEL_FILE": "OfflineCameras.xlsx",
    "CODRAZE_URL": "https://codraze.vercel.app/",
    "AUTO_START": True,
    "SCAN_DELAY_SECONDS": 2,
    "COLLECT_ALL_IPS": False,
    "ADMIN_PASSWORD_HASH": "",
    "ADMIN_PASSWORD_SALT": "",
    "ADMIN_PASSWORD_SET_AT": "",
}


def _hash_password(password, salt):
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return DEFAULT_CONFIG.copy()
    else:
        try:
            with open(CONFIG_FILE, 'w', encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, indent=4)
        except Exception:
            pass
        return DEFAULT_CONFIG.copy()


config = load_config()


# =========================================================
# ADMIN PASSWORD STATE
# =========================================================
ADMIN_STATE = {"hash": "", "salt": "", "set_at": ""}


def _load_admin_state_from_config():
    global ADMIN_STATE
    ADMIN_STATE["hash"] = (config.get("ADMIN_PASSWORD_HASH") or "").strip()
    ADMIN_STATE["salt"] = (config.get("ADMIN_PASSWORD_SALT") or "").strip()
    ADMIN_STATE["set_at"] = (config.get("ADMIN_PASSWORD_SET_AT") or "").strip()

    if not ADMIN_STATE["hash"] or not ADMIN_STATE["salt"]:
        salt = secrets.token_hex(16)
        ADMIN_STATE["salt"] = salt
        ADMIN_STATE["hash"] = _hash_password(DEFAULT_ADMIN_PASSWORD, salt)
        ADMIN_STATE["set_at"] = datetime.now().strftime("%Y-%m-%d")

        config["ADMIN_PASSWORD_HASH"] = ADMIN_STATE["hash"]
        config["ADMIN_PASSWORD_SALT"] = ADMIN_STATE["salt"]
        config["ADMIN_PASSWORD_SET_AT"] = ADMIN_STATE["set_at"]
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
        except Exception:
            pass


def _persist_admin_state():
    config["ADMIN_PASSWORD_HASH"] = ADMIN_STATE["hash"]
    config["ADMIN_PASSWORD_SALT"] = ADMIN_STATE["salt"]
    config["ADMIN_PASSWORD_SET_AT"] = ADMIN_STATE["set_at"]
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
    except Exception:
        pass


def _verify_admin_password(entered):
    salt = ADMIN_STATE.get("salt", "")
    expected = ADMIN_STATE.get("hash", "")
    if not salt or not expected:
        return False
    return hmac.compare_digest(_hash_password(entered, salt), expected)


def _set_new_admin_password(new_password):
    salt = secrets.token_hex(16)
    ADMIN_STATE["salt"] = salt
    ADMIN_STATE["hash"] = _hash_password(new_password, salt)
    ADMIN_STATE["set_at"] = datetime.now().strftime("%Y-%m-%d")
    _persist_admin_state()


def request_admin_authorization(parent=None, reason=""):
    global ADMIN_STATE
    ADMIN_STATE["hash"] = (config.get("ADMIN_PASSWORD_HASH") or ADMIN_STATE.get("hash", "")).strip()
    ADMIN_STATE["salt"] = (config.get("ADMIN_PASSWORD_SALT") or ADMIN_STATE.get("salt", "")).strip()

    pwd = _prompt_password(parent, reason)
    if pwd is None:
        return False
    if _verify_admin_password(pwd):
        return True
    messagebox.showerror("Denied", "Incorrect administrator password.", parent=parent)
    return False


def _prompt_password(parent, reason=""):
    dlg = tk.Toplevel(parent) if parent else tk.Toplevel()
    dlg.title("Authorization required")
    dlg.configure(bg="#ffffff")
    dlg.resizable(False, False)
    dlg.transient(parent)
    dlg.grab_set()

    msg = "Enter the administrator password to continue."
    if reason:
        msg = f"{reason}\n\n{msg}"
    tk.Label(dlg, text=msg, bg="#ffffff", fg="#0f172a",
             font=("Segoe UI", 10, "bold"),
             justify="left", wraplength=340).pack(padx=20, pady=(18, 8))

    entry = tk.Entry(dlg, show="●", font=("Segoe UI", 11),
                     bg="#f1f5f9", relief=tk.FLAT, width=30)
    entry.pack(padx=20, pady=(0, 10), ipady=8)
    entry.focus_set()

    result = {"value": None}

    def ok():
        result["value"] = entry.get()
        dlg.destroy()

    def cancel():
        result["value"] = None
        dlg.destroy()

    btn_row = tk.Frame(dlg, bg="#ffffff")
    btn_row.pack(padx=20, pady=(0, 16), fill=tk.X)
    tk.Button(btn_row, text="Cancel", command=cancel,
              bg="#f1f5f9", fg="#0f172a", relief=tk.FLAT,
              font=("Segoe UI", 10), padx=14, pady=6).pack(side=tk.RIGHT, padx=(6, 0))
    tk.Button(btn_row, text="Authorize", command=ok,
              bg="#2563eb", fg="#ffffff", relief=tk.FLAT,
              font=("Segoe UI", 10, "bold"), padx=14, pady=6).pack(side=tk.RIGHT)

    dlg.bind("<Return>", lambda e: ok())
    dlg.bind("<Escape>", lambda e: cancel())

    dlg.update_idletasks()
    try:
        x = (dlg.winfo_screenwidth() - dlg.winfo_width()) // 2
        y = (dlg.winfo_screenheight() - dlg.winfo_height()) // 3
        dlg.geometry(f"+{x}+{y}")
    except Exception:
        pass

    parent.wait_window(dlg) if parent else dlg.wait_window()
    return result["value"]


def _open_change_password_dialog(parent=None):
    dlg = tk.Toplevel(parent) if parent else tk.Toplevel()
    dlg.title("Change administrator password")
    dlg.configure(bg="#ffffff")
    dlg.resizable(False, False)
    dlg.transient(parent)
    dlg.grab_set()

    tk.Label(dlg, text="Change administrator password",
             bg="#ffffff", fg="#0f172a",
             font=("Segoe UI", 13, "bold")).pack(padx=24, pady=(20, 4))
    tk.Label(dlg, text="Used only to authorize NVR removal.",
             bg="#ffffff", fg="#64748b",
             font=("Segoe UI", 9)).pack(padx=24, pady=(0, 14))

    tk.Label(dlg, text="Current password", bg="#ffffff", fg="#64748b",
             font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=24)
    e_cur = tk.Entry(dlg, show="●", font=("Segoe UI", 11),
                     bg="#f1f5f9", relief=tk.FLAT, width=32)
    e_cur.pack(padx=24, pady=(2, 10), ipady=8)

    tk.Label(dlg, text="New password", bg="#ffffff", fg="#64748b",
             font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=24)
    e_new = tk.Entry(dlg, show="●", font=("Segoe UI", 11),
                     bg="#f1f5f9", relief=tk.FLAT, width=32)
    e_new.pack(padx=24, pady=(2, 10), ipady=8)

    tk.Label(dlg, text="Confirm new password", bg="#ffffff", fg="#64748b",
             font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=24)
    e_cnf = tk.Entry(dlg, show="●", font=("Segoe UI", 11),
                     bg="#f1f5f9", relief=tk.FLAT, width=32)
    e_cnf.pack(padx=24, pady=(2, 14), ipady=8)

    def save():
        cur = e_cur.get()
        new1 = e_new.get()
        new2 = e_cnf.get()

        if not cur:
            messagebox.showwarning("Missing", "Enter the current password.", parent=dlg)
            return
        if not _verify_admin_password(cur):
            messagebox.showerror("Denied", "Current password is incorrect.", parent=dlg)
            return
        if len(new1) < 6:
            messagebox.showwarning("Too short",
                                   "New password must be at least 6 characters.",
                                   parent=dlg)
            return
        if new1 != new2:
            messagebox.showwarning("Mismatch",
                                   "New passwords do not match.",
                                   parent=dlg)
            return
        if new1 == cur:
            messagebox.showwarning("No change",
                                   "New password must differ from the current one.",
                                   parent=dlg)
            return

        _set_new_admin_password(new1)
        messagebox.showinfo("Saved", "Administrator password updated.", parent=dlg)
        dlg.destroy()

    def cancel():
        dlg.destroy()

    row = tk.Frame(dlg, bg="#ffffff")
    row.pack(fill=tk.X, padx=24, pady=(0, 18))
    tk.Button(row, text="Cancel", command=cancel,
              bg="#f1f5f9", fg="#0f172a", relief=tk.FLAT,
              font=("Segoe UI", 10), padx=14, pady=6).pack(side=tk.RIGHT, padx=(6, 0))
    tk.Button(row, text="Save", command=save,
              bg="#2563eb", fg="#ffffff", relief=tk.FLAT,
              font=("Segoe UI", 10, "bold"), padx=14, pady=6).pack(side=tk.RIGHT)

    e_cur.focus_set()
    dlg.bind("<Return>", lambda e: save())
    dlg.bind("<Escape>", lambda e: cancel())

    dlg.update_idletasks()
    try:
        x = (dlg.winfo_screenwidth() - dlg.winfo_width()) // 2
        y = (dlg.winfo_screenheight() - dlg.winfo_height()) // 3
        dlg.geometry(f"+{x}+{y}")
    except Exception:
        pass

    parent.wait_window(dlg) if parent else dlg.wait_window()


_load_admin_state_from_config()


# --- NVR list normalization ---
def _normalize_nvr_entry(entry, default_user="admin"):
    if isinstance(entry, dict):
        url = str(entry.get("url", "")).strip()
        username = str(entry.get("username", default_user)).strip() or default_user
        password = str(entry.get("password", ""))
        if url:
            return {"url": url, "username": username, "password": password}
        return None
    if isinstance(entry, str):
        url = entry.strip()
        if url:
            return {"url": url, "username": default_user, "password": ""}
    return None


_legacy_user = config.get("USERNAME", "admin") or "admin"
NVR_LIST = []
for _item in config.get("NVR_LIST", []):
    _norm = _normalize_nvr_entry(_item, default_user=_legacy_user)
    if _norm:
        NVR_LIST.append(_norm)

DOWNLOADS_DIR = config.get("DOWNLOADS_DIR", DEFAULT_CONFIG["DOWNLOADS_DIR"])
EXCEL_FILE = os.path.join(DOWNLOADS_DIR, config.get("EXCEL_FILE", DEFAULT_CONFIG["EXCEL_FILE"]))
CODRAZE_URL = config.get("CODRAZE_URL", DEFAULT_CONFIG["CODRAZE_URL"])
AUTO_START = config.get("AUTO_START", True)
SCAN_DELAY_SECONDS = int(config.get("SCAN_DELAY_SECONDS", 2))
COLLECT_ALL_IPS = bool(config.get("COLLECT_ALL_IPS", False))

stop_requested = False
total_nvrs_count = 0
total_cameras_count = 0
online_cameras_count = 0
offline_cameras_count = 0
camera_data = []
offline_cameras_data = []
last_saved_file = None
scan_running = False


# =========================================================
# CHROME HELPERS
# =========================================================
def find_chrome_path():
    chrome_paths = [
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        os.path.join(os.environ.get('LOCALAPPDATA', ''),
                     'Google\\Chrome\\Application\\chrome.exe'),
        os.path.join(os.environ.get('PROGRAMFILES', ''),
                     'Google\\Chrome\\Application\\chrome.exe'),
        os.path.join(os.environ.get('PROGRAMFILES(X86)', ''),
                     'Google\\Chrome\\Application\\chrome.exe'),
    ]
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"
        )
        chrome_path = winreg.QueryValue(key, None)
        winreg.CloseKey(key)
        if os.path.exists(chrome_path):
            return chrome_path
    except Exception:
        pass
    for path in chrome_paths:
        if os.path.exists(path):
            return path
    try:
        result = subprocess.run(['where', 'chrome'],
                                capture_output=True, text=True)
        if result.returncode == 0:
            paths = result.stdout.strip().split('\n')
            if paths and os.path.exists(paths[0]):
                return paths[0]
    except Exception:
        pass
    return None


def get_chromedriver_path(log=None):
    try:
        chromedriver_path = ChromeDriverManager().install()
        if log:
            log.insert(tk.END, f"[OK] ChromeDriver: {os.path.basename(chromedriver_path)}\n")
        return chromedriver_path
    except Exception as e:
        if log:
            log.insert(tk.END, f"[WARN] WebDriverManager failed: {e}\n")
        try:
            chromedriver_path = shutil.which('chromedriver')
            if chromedriver_path:
                return chromedriver_path
        except Exception:
            pass
        common_paths = [
            os.path.join(os.environ.get('USERPROFILE', ''),
                         '.wdm', 'drivers', 'chromedriver', 'win64'),
            os.path.join(os.environ.get('USERPROFILE', ''),
                         '.cache', 'selenium', 'chromedriver'),
            os.path.join(os.environ.get('PROGRAMFILES', ''), 'chromedriver.exe'),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'chromedriver.exe'),
        ]
        for base_path in common_paths:
            if os.path.exists(base_path):
                for root, dirs, files in os.walk(base_path):
                    for file in files:
                        if file in ('chromedriver.exe', 'chromedriver'):
                            return os.path.join(root, file)
        return None


def setup_chrome_driver(log=None):
    options = Options()
    chrome_path = find_chrome_path()
    if chrome_path:
        options.binary_location = chrome_path

    options.add_argument("--start-maximized")
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
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    options.add_experimental_option('useAutomationExtension', False)
    prefs = {
        "profile.default_content_setting_values.notifications": 2,
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
    }
    options.add_experimental_option("prefs", prefs)
    return options


# =========================================================
# CONFIG PERSISTENCE
# =========================================================
def save_config():
    config["NVR_LIST"] = NVR_LIST
    config["DOWNLOADS_DIR"] = DOWNLOADS_DIR
    config["EXCEL_FILE"] = os.path.basename(EXCEL_FILE)
    config["AUTO_START"] = AUTO_START
    config["SCAN_DELAY_SECONDS"] = SCAN_DELAY_SECONDS
    config["COLLECT_ALL_IPS"] = COLLECT_ALL_IPS
    config["ADMIN_PASSWORD_HASH"] = ADMIN_STATE.get("hash", config.get("ADMIN_PASSWORD_HASH", ""))
    config["ADMIN_PASSWORD_SALT"] = ADMIN_STATE.get("salt", config.get("ADMIN_PASSWORD_SALT", ""))
    config["ADMIN_PASSWORD_SET_AT"] = ADMIN_STATE.get("set_at", config.get("ADMIN_PASSWORD_SET_AT", ""))
    config.pop("USERNAME", None)
    config.pop("PASSWORD", None)
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as config_file:
            json.dump(config, config_file, indent=4)
    except OSError as error:
        messagebox.showerror("Settings could not be saved", str(error))


def normalize_nvr_url(value):
    value = value.strip()
    if not value:
        raise ValueError("Enter an NVR IP address or host name.")
    if not re.match(r"^https?://", value, re.IGNORECASE):
        value = "http://" + value
    from urllib.parse import urlparse
    parsed = urlparse(value)
    if not parsed.hostname or not re.fullmatch(r"[A-Za-z0-9.-]+", parsed.hostname):
        raise ValueError("Enter a valid NVR IP address, host name, or URL.")
    if parsed.scheme not in ("http", "https"):
        raise ValueError("NVR URLs must use HTTP or HTTPS.")
    return value.rstrip("/") + "/"


def _nvr_host_only(url):
    return re.sub(r"^https?://", "", url, flags=re.IGNORECASE).strip("/")


# =========================================================
# UI ACTIONS
# =========================================================
def add_nvr_from_ui():
    global NVR_LIST
    raw_url = nvr_entry.get()
    raw_user = nvr_user_entry.get().strip()
    raw_pass = nvr_pass_entry.get()

    try:
        nvr_url = normalize_nvr_url(raw_url)
    except ValueError as error:
        messagebox.showwarning("Check the NVR address", str(error))
        nvr_entry.focus_set()
        return

    if not raw_user:
        messagebox.showwarning("Username required",
                               "Enter the username for this NVR.")
        nvr_user_entry.focus_set()
        return
    if not raw_pass:
        if not messagebox.askyesno("Password empty",
                                   "Password is empty. Add this NVR anyway?"):
            nvr_pass_entry.focus_set()
            return

    for existing in NVR_LIST:
        if existing["url"] == nvr_url:
            messagebox.showinfo("Already added",
                                "This NVR is already in the list.")
            return

    NVR_LIST.append({"url": nvr_url,
                     "username": raw_user,
                     "password": raw_pass})

    nvr_listbox.insert(tk.END, f"{nvr_url}  ·  {raw_user}")
    nvr_entry.set("")
    nvr_user_entry.set("")
    nvr_pass_entry.set("")
    save_config()
    refresh_nvr_count()


def remove_selected_nvr():
    global NVR_LIST
    selected = nvr_listbox.curselection()
    if not selected:
        messagebox.showinfo("Select an NVR", "Choose an NVR from the list first.")
        return
    index = selected[0]

    if not request_admin_authorization(root,
                                       "Removing an NVR requires password approval."):
        return

    nvr_listbox.delete(index)
    del NVR_LIST[index]
    save_config()
    refresh_nvr_count()


def refresh_nvr_count():
    try:
        nvr_count_label.config(text=f"{len(NVR_LIST)} configured")
    except Exception:
        pass


def open_company_website(event=None):
    try:
        webbrowser.open_new(CODRAZE_URL)
    except Exception as e:
        messagebox.showerror("Error", f"Could not open website: {str(e)}")


def save_collect_ips_setting():
    global COLLECT_ALL_IPS
    try:
        COLLECT_ALL_IPS = bool(collect_ips_var.get())
    except Exception:
        COLLECT_ALL_IPS = False
    config["COLLECT_ALL_IPS"] = COLLECT_ALL_IPS
    save_config()
    state = "ON" if COLLECT_ALL_IPS else "OFF"
    try:
        log.insert(tk.END, f"[SAVED] Collect ALL camera IPs = {state}\n")
    except Exception:
        pass
    messagebox.showinfo("Saved",
                        f"Collect ALL camera IPs is now {state}.\n"
                        "This setting is stored in config.json.")


# =========================================================
# IFRAME-AWARE TIME SYNC
# =========================================================
def sync_time(log):
    options = setup_chrome_driver(log)
    chromedriver_path = get_chromedriver_path(log)
    if not chromedriver_path:
        log.insert(tk.END, "[ERROR] Cannot proceed without ChromeDriver\n")
        return

    for entry in NVR_LIST:
        if stop_requested:
            break
        nvr_url = entry["url"]
        user = entry["username"]
        pwd = entry["password"]
        log.insert(tk.END, f"\n>> Time sync: {nvr_url}  (user: {user})\n")

        driver = None
        try:
            service = Service(chromedriver_path)
            driver = webdriver.Chrome(service=service, options=options)
            wait = WebDriverWait(driver, 15)

            driver.get(nvr_url)
            time.sleep(8)
            wait.until(EC.presence_of_element_located(
                (By.ID, "username"))).send_keys(user)
            wait.until(EC.presence_of_element_located(
                (By.ID, "password"))).send_keys(pwd + Keys.RETURN)
            log.insert(tk.END, "[OK] Logged in\n")
            time.sleep(10)

            clicked_config = False
            for xp in [
                "//a[contains(text(),'Configuration')]",
                "//*[contains(text(),'Configuration') and (self::a or self::li or self::div or self::span)]",
            ]:
                try:
                    wait.until(EC.element_to_be_clickable(
                        (By.XPATH, xp))).click()
                    clicked_config = True
                    log.insert(tk.END, "[OK] Configuration clicked\n")
                    break
                except Exception:
                    continue

            if not clicked_config:
                log.insert(tk.END,
                           "[WARN] Could not open Configuration menu — "
                           "skipping time sync.\n")
                continue

            time.sleep(6)

            clicked_time = False

            def _try_time_settings():
                nonlocal clicked_time
                for xp in [
                    "//a[contains(text(),'Time Settings')]",
                    "//li[contains(text(),'Time Settings')]",
                    "//*[contains(text(),'Time Settings')]",
                    "//a[contains(text(),'Time')]",
                    "//li[contains(text(),'Time')]",
                ]:
                    try:
                        el = WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, xp)))
                        el.click()
                        clicked_time = True
                        return True
                    except Exception:
                        continue
                return False

            if _try_time_settings():
                log.insert(tk.END, "[OK] Time Settings clicked\n")
            else:
                frames = driver.find_elements(By.TAG_NAME, "iframe")
                for idx in range(len(frames)):
                    try:
                        driver.switch_to.default_content()
                        frames = driver.find_elements(By.TAG_NAME, "iframe")
                        if idx >= len(frames):
                            break
                        driver.switch_to.frame(frames[idx])
                        if _try_time_settings():
                            log.insert(tk.END,
                                       f"[OK] Time Settings clicked inside iframe[{idx}]\n")
                            break
                    except Exception:
                        continue
                driver.switch_to.default_content()

            if not clicked_time:
                log.insert(tk.END,
                           "[WARN] Time Settings not reachable — "
                           "skipping time sync for this NVR.\n")
                continue

            time.sleep(4)

            def _try_checkbox_and_save():
                for xp in [
                    "//label[contains(text(),'Sync')]/preceding-sibling::input[@type='checkbox']",
                    "//input[@type='checkbox' and contains(@name,'sync')]",
                    "//input[@type='checkbox' and contains(@name,'Sync')]",
                ]:
                    try:
                        cb = WebDriverWait(driver, 3).until(
                            EC.presence_of_element_located((By.XPATH, xp)))
                        if not cb.is_selected():
                            cb.click()
                        break
                    except Exception:
                        continue

                for xp in [
                    "//*[@id='settingTime']/button",
                    "//button[contains(text(),'Save')]",
                    "//input[@type='button' and contains(@value,'Save')]",
                    "//input[@type='submit' and contains(@value,'Save')]",
                ]:
                    try:
                        WebDriverWait(driver, 3).until(
                            EC.element_to_be_clickable((By.XPATH, xp))).click()
                        return True
                    except Exception:
                        continue
                return False

            saved = _try_checkbox_and_save()
            if not saved:
                frames = driver.find_elements(By.TAG_NAME, "iframe")
                for idx in range(len(frames)):
                    try:
                        driver.switch_to.default_content()
                        frames = driver.find_elements(By.TAG_NAME, "iframe")
                        if idx >= len(frames):
                            break
                        driver.switch_to.frame(frames[idx])
                        if _try_checkbox_and_save():
                            saved = True
                            break
                    except Exception:
                        continue
                driver.switch_to.default_content()

            if saved:
                log.insert(tk.END, f"[OK] Time sync saved for {nvr_url}\n")
            else:
                log.insert(tk.END,
                           f"[WARN] Save button not found for {nvr_url} — "
                           "please set time manually.\n")

            time.sleep(3)

        except Exception as e:
            first_line = (str(e).splitlines() or [""])[0] or "unknown error"
            log.insert(tk.END,
                       f"[WARN] Time sync step failed for {nvr_url}: {first_line}\n")
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
                time.sleep(3)


# =========================================================
# CAMERA SCAN (deep IP extraction)
# =========================================================
def extract_camera_ip_from_row_deep(row, nvr_ip):
    """
    Deep IP extraction:
    Walks every descendant span/div/td/li/p and reads text, textContent,
    and innerText — this is what captures IPs that sit inside child cells
    (like your NVR's <span>[4]</span> layout).
    Returns the first valid IPv4 that isn't the NVR itself.
    """
    ip_pattern = re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b')
    nvr_host = _nvr_host_only(nvr_ip)

    def _valid(ip):
        if ip == nvr_host:
            return False
        parts = ip.split(".")
        if len(parts) != 4:
            return False
        try:
            return all(0 <= int(p) <= 255 for p in parts)
        except ValueError:
            return False

    candidates = []

    for tag in ("span", "div", "td", "li", "p", "label"):
        try:
            for el in row.find_elements(By.XPATH, f".//{tag}"):
                try:
                    t = (el.text or "").strip()
                    if t:
                        candidates.append(t)
                except Exception:
                    pass
                try:
                    tc = (el.get_attribute("textContent") or "").strip()
                    if tc:
                        candidates.append(tc)
                except Exception:
                    pass
                try:
                    iv = (el.get_attribute("innerText") or "").strip()
                    if iv:
                        candidates.append(iv)
                except Exception:
                    pass
        except Exception:
            continue

    try:
        candidates.append((row.text or "").strip())
    except Exception:
        pass
    try:
        candidates.append((row.get_attribute("textContent") or "").strip())
    except Exception:
        pass
    try:
        candidates.append((row.get_attribute("innerText") or "").strip())
    except Exception:
        pass

    for text in candidates:
        if not text:
            continue
        for ip in ip_pattern.findall(text):
            if _valid(ip):
                return ip
    return None


def extract_camera_ip_from_row(row, nvr_ip):
    """Try the deep method first, fall back to the shallow one."""
    ip = extract_camera_ip_from_row_deep(row, nvr_ip)
    if ip:
        return ip
    try:
        row_text = row.text
        ip_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
        ip_matches = re.findall(ip_pattern, row_text)
        nvr_ip_clean = _nvr_host_only(nvr_ip)
        for ip in ip_matches:
            if ip != nvr_ip_clean:
                return ip
        return None
    except Exception:
        return None


def extract_camera_name_from_row(row, camera_ip=None):
    candidates = []
    try:
        for element in row.find_elements(By.XPATH, ".//*"):
            text = (element.text or "").strip()
            if text and len(text) < 100:
                candidates.append(text)
    except Exception:
        pass
    try:
        candidates.extend((row.text or "").splitlines())
    except Exception:
        pass

    ip_pattern = r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b"
    ignored = {"online", "offline", "abnormal", "error",
               "connected", "disconnected", "enable", "disable"}
    for candidate in candidates:
        for line in candidate.splitlines():
            value = " ".join(line.split()).strip(" -:|\t")
            if not value or value.lower() in ignored or re.fullmatch(ip_pattern, value):
                continue
            value = re.sub(ip_pattern, "", value).strip(" -:|\t")
            for status_word in ignored:
                value = re.sub(rf"\b{re.escape(status_word)}\b", "", value,
                               flags=re.IGNORECASE).strip(" -:|\t")
            if value and value.lower() not in ignored and not re.fullmatch(r"\d+", value):
                return value[:80]
    return "Name unavailable"


def save_excel_report(log):
    global camera_data, offline_cameras_data, total_cameras_count
    global online_cameras_count, offline_cameras_count
    global total_nvrs_count, EXCEL_FILE, last_saved_file, COLLECT_ALL_IPS

    try:
        wb = Workbook()
        wb.remove(wb.active)
        ws = wb.create_sheet("Camera Report")

        rows_to_write = camera_data if COLLECT_ALL_IPS else offline_cameras_data
        report_title = ("NVR SyncGuard - Full Camera Inventory"
                        if COLLECT_ALL_IPS
                        else "NVR SyncGuard - Offline Camera Report")

        # ---------- Title ----------
        ws.merge_cells('A1:F1')
        c = ws['A1']
        c.value = report_title
        c.font = Font(name='Calibri', size=16, bold=True, color="FFFFFF")
        c.fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
        c.alignment = Alignment(horizontal="center", vertical="center")

        # ---------- Summary row ----------
        ws.merge_cells('A2:B2')
        c = ws['A2']
        c.value = f"TOTAL CAMERAS: {total_cameras_count}"
        c.font = Font(name='Calibri', size=12, bold=True, color="FFFFFF")
        c.fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
        c.alignment = Alignment(horizontal="center", vertical="center")

        ws.merge_cells('C2:D2')
        c = ws['C2']
        c.value = f"ONLINE: {online_cameras_count}"
        c.font = Font(name='Calibri', size=12, bold=True, color="FFFFFF")
        c.fill = PatternFill(start_color="059669", end_color="059669", fill_type="solid")
        c.alignment = Alignment(horizontal="center", vertical="center")

        ws.merge_cells('E2:F2')
        c = ws['E2']
        c.value = f"OFFLINE / ABNORMAL: {offline_cameras_count}"
        c.font = Font(name='Calibri', size=12, bold=True, color="FFFFFF")
        c.fill = PatternFill(start_color="DC2626", end_color="DC2626", fill_type="solid")
        c.alignment = Alignment(horizontal="center", vertical="center")

        ws.merge_cells('A3:F3')
        c = ws['A3']
        c.value = f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        c.font = Font(name='Calibri', size=10, italic=True, color="475569")
        c.fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        c.alignment = Alignment(horizontal="center", vertical="center")

        ws.row_dimensions[4].height = 15

        # ---------- Table header ----------
        ws.merge_cells('A5:F5')
        c = ws['A5']
        c.value = ("ALL CAMERAS (ONLINE + OFFLINE)"
                   if COLLECT_ALL_IPS
                   else "OFFLINE / ABNORMAL CAMERAS")
        c.font = Font(name='Calibri', size=13, bold=True, color="FFFFFF")
        c.fill = PatternFill(start_color="DC2626", end_color="DC2626", fill_type="solid")
        c.alignment = Alignment(horizontal="center", vertical="center")

        headers = ["No", "Camera Name", "IP Address", "NVR IP", "Status", "Checked At"]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=6, column=col)
            cell.value = header
            cell.font = Font(bold=True, color="FFFFFF", size=11)
            cell.fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = Border(left=Side(style='thin'), right=Side(style='thin'),
                                 top=Side(style='thin'), bottom=Side(style='thin'))

        # ---------- Data rows (defensive: coerce everything to str) ----------
        def _s(v, fallback=""):
            try:
                if v is None:
                    return fallback
                s = str(v).strip()
                return s if s else fallback
            except Exception:
                return fallback

        row_num = 7
        if rows_to_write:
            for idx, data in enumerate(rows_to_write, start=1):
                cam_name = _s(data.get('camera_name'), "Name unavailable")
                cam_ip   = _s(data.get('camera_ip'),   "Not shown by NVR")
                nvr_ip   = _s(data.get('nvr_ip'),      "")
                status   = _s(data.get('status'),      "")
                checked  = _s(data.get('checked_at'),  "")

                ws.cell(row=row_num, column=1).value = idx
                ws.cell(row=row_num, column=2).value = cam_name
                ws.cell(row=row_num, column=3).value = cam_ip
                ws.cell(row=row_num, column=4).value = nvr_ip
                ws.cell(row=row_num, column=5).value = status
                ws.cell(row=row_num, column=6).value = checked

                # Debug line so you can see exactly what went into the file
                try:
                    log.insert(tk.END,
                               f"[EXCEL] Row {idx}: {cam_name} | "
                               f"{cam_ip} | {nvr_ip} | {status}\n")
                except Exception:
                    pass

                sc = ws.cell(row=row_num, column=5)
                if status == "Offline":
                    sc.fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
                    sc.font = Font(color="991B1B", bold=True)
                elif status == "Abnormal":
                    sc.fill = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
                    sc.font = Font(color="92400E", bold=True)
                elif status == "Online":
                    sc.fill = PatternFill(start_color="D1FAE5", end_color="D1FAE5", fill_type="solid")
                    sc.font = Font(color="065F46", bold=True)

                for col in range(1, 7):
                    ws.cell(row=row_num, column=col).border = Border(
                        left=Side(style='thin', color="E2E8F0"),
                        right=Side(style='thin', color="E2E8F0"),
                        top=Side(style='thin', color="E2E8F0"),
                        bottom=Side(style='thin', color="E2E8F0"),
                    )
                row_num += 1
        else:
            ws.merge_cells(f'A{row_num}:F{row_num}')
            b = ws.cell(row=row_num, column=1)
            b.value = (f"All {total_cameras_count} cameras are online"
                       if not COLLECT_ALL_IPS
                       else "No cameras discovered")
            b.font = Font(name='Calibri', size=13, bold=True, color="065F46")
            b.fill = PatternFill(start_color="D1FAE5", end_color="D1FAE5", fill_type="solid")
            b.alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[row_num].height = 32

        for col, width in {'A': 8, 'B': 30, 'C': 22, 'D': 22, 'E': 14, 'F': 22}.items():
            ws.column_dimensions[col].width = width
        ws.freeze_panes = "A7"
        if rows_to_write:
            ws.auto_filter.ref = f"A6:F{max(6, row_num - 1)}"

        os.makedirs(DOWNLOADS_DIR, exist_ok=True)
        if os.path.exists(EXCEL_FILE):
            try:
                os.remove(EXCEL_FILE)
                time.sleep(0.2)
            except Exception:
                pass

        wb.save(EXCEL_FILE)
        wb.close()
        last_saved_file = EXCEL_FILE

        log.insert(tk.END, f"\n{'=' * 60}\n")
        log.insert(tk.END, f"[SAVED] {EXCEL_FILE}\n")
        log.insert(tk.END, f"Total: {total_cameras_count} | "
                           f"Online: {online_cameras_count} | "
                           f"Offline/Abnormal: {offline_cameras_count}\n")
        log.insert(tk.END, f"{'=' * 60}\n")
        return True
    except Exception as e:
        log.insert(tk.END, f"[ERROR] Saving failed: {e}\n")
        return False


def check_cameras(log, tree, status_label):
    global total_cameras_count, online_cameras_count, offline_cameras_count
    global camera_data, offline_cameras_data

    total_cameras_count = 0
    online_cameras_count = 0
    offline_cameras_count = 0
    camera_data = []
    offline_cameras_data = []

    options = setup_chrome_driver(log)
    chromedriver_path = get_chromedriver_path(log)
    if not chromedriver_path:
        log.insert(tk.END, "[ERROR] Cannot proceed without ChromeDriver\n")
        return

    for nvr_index, entry in enumerate(NVR_LIST):
        if stop_requested:
            break
        nvr_url = entry["url"]
        nvr_host = _nvr_host_only(nvr_url)
        user = entry["username"]
        pwd = entry["password"]

        log.insert(tk.END, f"\n{'=' * 60}\n")
        log.insert(tk.END, f"NVR {nvr_index + 1}/{len(NVR_LIST)}: {nvr_url}  (user: {user})\n")
        log.insert(tk.END, f"{'=' * 60}\n")

        driver = None
        try:
            service = Service(chromedriver_path)
            driver = webdriver.Chrome(service=service, options=options)
            wait = WebDriverWait(driver, 20)

            driver.get(nvr_url)
            time.sleep(5)
            wait.until(EC.presence_of_element_located(
                (By.ID, "username"))).send_keys(user)
            wait.until(EC.presence_of_element_located(
                (By.ID, "password"))).send_keys(pwd + Keys.RETURN)
            log.insert(tk.END, "[OK] Logged in\n")
            time.sleep(10)

            wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//a[contains(text(),'Configuration')]"))).click()
            log.insert(tk.END, "[OK] Configuration\n")
            time.sleep(10)

            camera_settings_clicked = False
            for selector in [
                '//*[@id="menu"]/div/div[2]/div[5]',
                "//div[contains(text(),'Camera Settings')]",
                "//*[contains(text(),'Camera') and contains(text(),'Settings')]",
            ]:
                try:
                    wait.until(EC.element_to_be_clickable(
                        (By.XPATH, selector))).click()
                    log.insert(tk.END, "[OK] Camera Settings\n")
                    camera_settings_clicked = True
                    break
                except Exception:
                    continue

            if not camera_settings_clicked:
                log.insert(tk.END, "[ERROR] Camera Settings not found\n")
                continue

            time.sleep(5)

            camera_rows = []
            try:
                table = wait.until(EC.presence_of_element_located(
                    (By.ID, "tableDigitalChannels")))
                camera_rows = table.find_elements(
                    By.XPATH, ".//div[contains(@class, 'row')]")
                log.insert(tk.END, f"[OK] Found {len(camera_rows)} cameras\n")
            except Exception:
                try:
                    camera_rows = driver.find_elements(
                        By.CLASS_NAME, "digital-channel-item")
                    log.insert(tk.END, f"[OK] Found {len(camera_rows)} cameras\n")
                except Exception:
                    log.insert(tk.END, "[ERROR] No cameras found\n")
                    continue

            checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            nvr_cameras = 0
            nvr_online = 0
            nvr_offline = 0

            for i, row in enumerate(camera_rows[:64]):
                try:
                    camera_ip = extract_camera_ip_from_row(row, nvr_host) or ""
                    camera_name = extract_camera_name_from_row(row, camera_ip)
                    if camera_name == "Name unavailable":
                        camera_name = f"Camera {i + 1}"

                    row_text = row.text.lower()
                    status = "Online"
                    if any(w in row_text for w in ["offline", "disconnect"]):
                        status = "Offline"
                        nvr_offline += 1
                    elif any(w in row_text for w in ["abnormal", "error"]):
                        status = "Abnormal"
                        nvr_offline += 1
                    else:
                        nvr_online += 1

                    record = {
                        'nvr_ip': nvr_host,
                        'camera_name': camera_name,
                        'camera_ip': camera_ip,
                        'status': status,
                        'checked_at': checked_at,
                    }
                    camera_data.append(record)

                    if status in ["Offline", "Abnormal"]:
                        offline_cameras_data.append(record)
                        tree.insert("", tk.END,
                                    values=(len(offline_cameras_data),
                                            camera_name, camera_ip,
                                            status, nvr_host),
                                    tags=("offline",) if status == "Offline" else ("abnormal",))
                        log.insert(tk.END,
                                   f"[WARN] {camera_name} | {camera_ip} - {status}\n")
                    else:
                        log.insert(tk.END, f"[OK] {camera_name} | {camera_ip} - Online\n")

                    nvr_cameras += 1
                except Exception:
                    continue

            total_cameras_count += nvr_cameras
            online_cameras_count += nvr_online
            offline_cameras_count += nvr_offline

            log.insert(tk.END,
                       f"\nSummary: {nvr_cameras} total, "
                       f"{nvr_online} online, {nvr_offline} offline/abnormal\n")
            status_label.config(
                text=f"Status: {total_cameras_count} total · "
                     f"{online_cameras_count} online · "
                     f"{offline_cameras_count} offline")

        except Exception as e:
            log.insert(tk.END, f"[ERROR] {e}\n")
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
                time.sleep(3)

    if not stop_requested:
        save_excel_report(log)


# =========================================================
# THREAD-SAFE TK PROXIES
# =========================================================
class TkLogProxy:
    def __init__(self, widget):
        self.widget = widget

    def insert(self, *args):
        root.after(0, lambda: self.widget.insert(*args))

    def delete(self, *args):
        root.after(0, lambda: self.widget.delete(*args))

    def see(self, *args):
        root.after(0, lambda: self.widget.see(*args))


class TkTreeProxy:
    def __init__(self, widget):
        self.widget = widget

    def insert(self, *args, **kwargs):
        root.after(0, lambda: self.widget.insert(*args, **kwargs))

    def delete(self, *args):
        root.after(0, lambda: self.widget.delete(*args))

    def get_children(self):
        return self.widget.get_children()


class TkLabelProxy:
    def __init__(self, widget):
        self.widget = widget

    def config(self, **kwargs):
        root.after(0, lambda: self.widget.config(**kwargs))


# =========================================================
# ROUNDED WIDGETS
# =========================================================
def _round_rect(canvas, x1, y1, x2, y2, r, **kwargs):
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


def _safe_parent_bg(widget, fallback="#eef2f6"):
    try:
        return widget.cget("bg")
    except Exception:
        return fallback


class RoundedFrame:
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


class RoundedButton:
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

    def pack(self, **kwargs):
        return self.canvas.pack(**kwargs)

    def grid(self, **kwargs):
        return self.canvas.grid(**kwargs)

    def place(self, **kwargs):
        return self.canvas.place(**kwargs)

    def configure(self, **kwargs):
        return self.canvas.configure(**kwargs)


class RoundedEntry:
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

    def pack(self, **kwargs):
        return self.outer.pack(**kwargs)

    def grid(self, **kwargs):
        return self.outer.grid(**kwargs)

    def place(self, **kwargs):
        return self.outer.place(**kwargs)

    def configure(self, **kwargs):
        return self.outer.configure(**kwargs)


# =========================================================
# START / STOP
# =========================================================
def start_all(log, btn, tree, status_label, auto_start=False):
    global stop_requested, total_nvrs_count, total_cameras_count
    global online_cameras_count, offline_cameras_count
    global camera_data, offline_cameras_data, scan_running, COLLECT_ALL_IPS

    if scan_running:
        stop_requested = True
        btn.set_text("Stopping…")
        return
    if not NVR_LIST:
        if not auto_start:
            messagebox.showwarning("No NVRs configured",
                                   "Add at least one NVR before starting a scan.")
        return

    try:
        COLLECT_ALL_IPS = bool(collect_ips_var.get())
    except Exception:
        COLLECT_ALL_IPS = False

    stop_requested = False
    scan_running = True
    total_nvrs_count = len(NVR_LIST)
    total_cameras_count = 0
    online_cameras_count = 0
    offline_cameras_count = 0
    camera_data = []
    offline_cameras_data = []

    btn.set_text("■  STOP SCAN")
    btn.set_colors(bg=COLORS["red"], hover=COLORS["red_dark"], active="#991b1b")
    status_label.config(text="● Scanning NVRs…", fg=COLORS["blue"])
    log.delete(1.0, tk.END)
    tree.delete(*tree.get_children())

    def task():
        global scan_running
        try:
            chrome_path = find_chrome_path()
            if not chrome_path:
                log.insert(tk.END,
                           "[ERROR] Google Chrome not found. Install Chrome and retry.\n")
                status_label.config(text="● Chrome not found", fg=COLORS["red"])
                return
            log.insert(tk.END, f"[INFO] Chrome detected: {chrome_path}\n")
            log.insert(tk.END, f"[INFO] {len(NVR_LIST)} NVR(s) queued\n")
            if COLLECT_ALL_IPS:
                log.insert(tk.END,
                           "[INFO] Collect-all-IPs mode: all camera IPs will be saved.\n")
            else:
                log.insert(tk.END,
                           "[INFO] Default mode: only offline/abnormal cameras will be saved.\n")
            sync_time(log)
            if not stop_requested:
                log.insert(tk.END, "\n[INFO] Camera scan started…\n")
                check_cameras(log, tree, status_label)
            if stop_requested:
                status_label.config(text="● Scan stopped by user",
                                    fg=COLORS["amber"])
            else:
                status_label.config(
                    text=f"● Completed · Total {total_cameras_count} · "
                         f"Online {online_cameras_count} · "
                         f"Offline {offline_cameras_count}",
                    fg=COLORS["green"])
        except Exception as error:
            log.insert(tk.END, f"\n[ERROR] Scan failed: {error}\n")
            status_label.config(text="● Scan ended with an error",
                                fg=COLORS["red"])
        finally:
            scan_running = False
            root.after(0, lambda: (
                btn.set_text("▶  START SCAN"),
                btn.set_colors(bg=COLORS["blue"],
                               hover=COLORS["blue_dark"],
                               active="#1e40af"),
                btn.set_state("normal"),
            ))

    threading.Thread(target=task, daemon=True).start()


def export_report(log_widget):
    if not camera_data:
        messagebox.showinfo("Nothing to export",
                            "Run a camera scan first, then export its results.")
        return
    if save_excel_report(log_widget):
        messagebox.showinfo("Excel exported",
                            f"Report saved to:\n{last_saved_file}")


# =========================================================
# MAIN GUI
# =========================================================
def main():
    global root, status_label, btn, log, nvr_listbox, nvr_entry
    global nvr_user_entry, nvr_pass_entry, collect_ips_var
    global nvr_count_label, COLORS, scan_running, last_saved_label

    scan_running = False
    COLORS = {
        "bg": "#eef2f6",
        "card": "#ffffff",
        "ink": "#0f172a",
        "ink_soft": "#1e293b",
        "muted": "#64748b",
        "line": "#e2e8f0",
        "blue": "#2563eb",
        "blue_dark": "#1d4ed8",
        "blue_pale": "#eff6ff",
        "blue_border": "#bfdbfe",
        "red": "#dc2626",
        "red_dark": "#b91c1c",
        "red_pale": "#fef2f2",
        "red_border": "#fecaca",
        "green": "#059669",
        "green_pale": "#ecfdf5",
        "green_border": "#a7f3d0",
        "amber": "#d97706",
        "amber_pale": "#fffbeb",
        "header": "#0b1220",
        "header_2": "#111827",
        "chip": "#1f2937",
    }

    root = tk.Tk()
    root.title("NVR SyncGuard · Time Sync & Camera Health Monitor · Codraze")
    root.geometry("1480x920")
    root.minsize(1180, 760)
    root.configure(bg=COLORS["bg"])

    try:
        if os.path.exists(ICO_PATH):
            root.iconbitmap(ICO_PATH)
    except Exception:
        pass

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("Treeview", background=COLORS["card"],
                    foreground=COLORS["ink"],
                    fieldbackground=COLORS["card"], rowheight=36,
                    borderwidth=0, font=("Segoe UI", 10))
    style.configure("Treeview.Heading", background=COLORS["ink_soft"],
                    foreground="white",
                    font=("Segoe UI", 10, "bold"),
                    relief="flat", padding=(10, 10))
    style.map("Treeview",
              background=[("selected", COLORS["blue_pale"])],
              foreground=[("selected", COLORS["ink"])])
    style.configure("Vertical.TScrollbar",
                    background=COLORS["card"],
                    troughcolor=COLORS["card"], borderwidth=0, arrowsize=12)

    outer = tk.Frame(root, bg=COLORS["bg"])
    outer.pack(fill=tk.BOTH, expand=True, padx=22, pady=18)

    # ---------------- HEADER ----------------
    header = RoundedFrame(outer, radius=16, bg=COLORS["header"],
                          border=COLORS["header"], border_width=0,
                          padding=0, width=1000, height=120)
    header.pack(fill=tk.X, pady=(0, 16))
    header.configure(height=120)

    h = header.inner

    brand_container = tk.Frame(h, bg=COLORS["header"])
    brand_container.place(x=22, y=22, width=76, height=76)

    _logo_image_holder = {"img": None}

    def _load_logo():
        candidates = [LOGO_PATH, ICO_PATH,
                      os.path.join("images", "logo.png"),
                      os.path.join("images", "logo.ico")]
        for path in candidates:
            if not path or not os.path.exists(path):
                continue
            try:
                from PIL import Image, ImageTk
                img = Image.open(path).convert("RGBA")
                img = img.resize((72, 72), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                _logo_image_holder["img"] = photo
                return photo
            except Exception:
                try:
                    photo = tk.PhotoImage(file=path)
                    _logo_image_holder["img"] = photo
                    return photo
                except Exception:
                    continue
        return None

    logo_photo = _load_logo()

    if logo_photo is not None:
        logo_tile = RoundedFrame(brand_container, radius=14,
                                 bg=COLORS["blue"], border=COLORS["blue"],
                                 border_width=0, padding=6,
                                 width=72, height=72)
        logo_tile.pack(fill=tk.BOTH, expand=True)
        logo_label = tk.Label(logo_tile.inner, image=logo_photo,
                              bg=COLORS["blue"], bd=0)
        logo_label.image = logo_photo
        logo_label.pack(expand=True)
    else:
        brand_mark = tk.Label(brand_container, text="C",
                              bg=COLORS["blue"], fg="#ffffff",
                              font=("Segoe UI", 26, "bold"),
                              width=2, height=1)
        brand_mark.pack(fill=tk.BOTH, expand=True)

    title_area = tk.Frame(h, bg=COLORS["header"])
    title_area.place(x=118, y=26)
    tk.Label(title_area, text="NVR SyncGuard",
             bg=COLORS["header"], fg="#ffffff",
             font=("Segoe UI", 22, "bold")).pack(anchor="w")
    tk.Label(title_area,
             text="Auto-scan on launch  ·  Per-NVR credentials  ·  Single Excel report",
             bg=COLORS["header"], fg="#94a3b8",
             font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 0))

    clock_label = tk.Label(h, text="", bg=COLORS["header"], fg="#cbd5e1",
                           font=("Segoe UI", 10))
    clock_label.place(relx=1.0, x=-110, y=46)

    codraze_btn = RoundedButton(
        h, text="CODRAZE  ↗",
        command=open_company_website,
        radius=12,
        bg="#1f2937", fg="#93c5fd",
        hover_bg="#273449", active_bg="#0f172a",
        width=170, height=42,
        font=("Segoe UI", 10, "bold"),
    )
    codraze_btn.place(relx=1.0, x=-300, y=38)

    def tick():
        clock_label.config(text=datetime.now().strftime("%H:%M:%S"))
        root.after(1000, tick)
    tick()

    # ---------------- BODY ----------------
    body = tk.Frame(outer, bg=COLORS["bg"])
    body.pack(fill=tk.BOTH, expand=True)
    body.grid_columnconfigure(0, weight=0, minsize=380)
    body.grid_columnconfigure(1, weight=1)
    body.grid_rowconfigure(0, weight=1)

    left = tk.Frame(body, bg=COLORS["bg"])
    left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))

    nvr_card = RoundedFrame(left, radius=16, bg=COLORS["card"],
                            border=COLORS["line"], padding=20,
                            width=360, height=560)
    nvr_card.pack(fill=tk.BOTH, expand=True)
    nvr_card.configure(height=560)

    nv = nvr_card.inner
    tk.Label(nv, text="ADD NEW NVR", bg=COLORS["card"],
             fg=COLORS["ink"],
             font=("Segoe UI", 12, "bold")).pack(anchor="w")
    tk.Label(nv, text="Password needed only to remove an NVR.",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 14))

    tk.Label(nv, text="IP ADDRESS / HOST / URL",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 5))
    nvr_entry = RoundedEntry(nv, radius=10, width=320, height=42)
    nvr_entry.pack(fill=tk.X)

    tk.Label(nv, text="USERNAME",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(10, 5))
    nvr_user_entry = RoundedEntry(nv, radius=10, width=320, height=42)
    nvr_user_entry.pack(fill=tk.X)
    nvr_user_entry.set("admin")

    tk.Label(nv, text="PASSWORD",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(10, 5))

    pwd_row = tk.Frame(nv, bg=COLORS["card"])
    pwd_row.pack(fill=tk.X)
    nvr_pass_entry = RoundedEntry(pwd_row, radius=10, width=270,
                                  height=42, show="●")
    nvr_pass_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def toggle_pwd():
        current = nvr_pass_entry.entry.cget("show")
        nvr_pass_entry.entry.config(show="" if current else "●")

    eye_btn = RoundedButton(pwd_row, text="👁", command=toggle_pwd,
                            bg="#f1f5f9", fg=COLORS["ink"],
                            hover_bg="#e2e8f0", active_bg="#cbd5e1",
                            width=42, height=42, font=("Segoe UI", 12))
    eye_btn.pack(side=tk.LEFT, padx=(8, 0))

    add_row = tk.Frame(nv, bg=COLORS["card"])
    add_row.pack(fill=tk.X, pady=(14, 14))
    add_btn = RoundedButton(add_row, text="+  ADD NVR",
                            command=add_nvr_from_ui,
                            bg=COLORS["blue"], hover_bg=COLORS["blue_dark"],
                            active_bg="#1e40af", width=180, height=42)
    add_btn.pack(side=tk.LEFT)

    lock_btn = RoundedButton(
        add_row, text="🔒",
        command=lambda: _open_change_password_dialog(root),
        bg="#f1f5f9", fg=COLORS["ink"],
        hover_bg="#e2e8f0", active_bg="#cbd5e1",
        width=42, height=42,
        font=("Segoe UI", 13, "bold"),
    )
    lock_btn.pack(side=tk.LEFT, padx=(8, 0))

    collect_row = tk.Frame(nv, bg=COLORS["card"])
    collect_row.pack(fill=tk.X, pady=(0, 14))

    collect_ips_var = tk.BooleanVar(value=COLLECT_ALL_IPS)
    chk = tk.Checkbutton(
        collect_row,
        text="Collect ALL camera IPs in Excel",
        variable=collect_ips_var,
        bg=COLORS["card"], fg=COLORS["ink"],
        activebackground=COLORS["card"],
        selectcolor="#ffffff",
        font=("Segoe UI", 9),
        anchor="w", justify="left",
    )
    chk.pack(anchor="w")

    tk.Label(collect_row,
             text="(unchecked = offline/abnormal cameras only)",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 8)).pack(anchor="w", pady=(0, 6))

    save_choice_btn = RoundedButton(
        collect_row,
        text="💾  Save choice",
        command=save_collect_ips_setting,
        bg="#f1f5f9", fg=COLORS["ink"],
        hover_bg="#e2e8f0", active_bg="#cbd5e1",
        width=150, height=32,
        font=("Segoe UI", 9, "bold"),
    )
    save_choice_btn.pack(anchor="w")

    count_row = tk.Frame(nv, bg=COLORS["card"])
    count_row.pack(fill=tk.X, pady=(0, 6))
    tk.Label(count_row, text="SAVED NVRS", bg=COLORS["card"],
             fg=COLORS["ink"],
             font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
    nvr_count_label = tk.Label(count_row,
                               text=f"{len(NVR_LIST)} configured",
                               bg=COLORS["card"], fg=COLORS["muted"],
                               font=("Segoe UI", 9))
    nvr_count_label.pack(side=tk.RIGHT)

    list_wrap = RoundedFrame(nv, radius=10, bg="#f8fafc",
                             border=COLORS["line"], padding=6,
                             width=320, height=170)
    list_wrap.pack(fill=tk.BOTH, expand=True)
    list_wrap.configure(height=170)
    nvr_listbox = tk.Listbox(list_wrap.inner, font=("Consolas", 9),
                             bg="#f8fafc", fg=COLORS["ink"], relief=tk.FLAT,
                             selectbackground=COLORS["blue"],
                             selectforeground="#ffffff",
                             activestyle="none", highlightthickness=0)
    nvr_listbox.pack(fill=tk.BOTH, expand=True)
    for entry in NVR_LIST:
        nvr_listbox.insert(tk.END, f"{entry['url']}  ·  {entry['username']}")

    remove_btn = RoundedButton(nv, text="🔒  Remove selected (password)",
                               command=remove_selected_nvr,
                               bg=COLORS["red_pale"], fg=COLORS["red_dark"],
                               hover_bg="#fee2e2", active_bg="#fecaca",
                               width=210, height=34,
                               font=("Segoe UI", 9, "bold"))
    remove_btn.pack(anchor="w", pady=(10, 0))

    right = tk.Frame(body, bg=COLORS["bg"])
    right.grid(row=0, column=1, sticky="nsew")
    right.grid_columnconfigure(0, weight=1)
    right.grid_rowconfigure(2, weight=3)
    right.grid_rowconfigure(3, weight=2)

    action_bar = RoundedFrame(right, radius=16, bg=COLORS["card"],
                              border=COLORS["line"], padding=16,
                              width=900, height=96)
    action_bar.grid(row=0, column=0, sticky="ew", pady=(0, 14))
    action_bar.configure(height=96)
    ab = action_bar.inner

    status_label_widget = tk.Label(ab, text="● Ready to scan",
                                   bg=COLORS["card"], fg=COLORS["green"],
                                   font=("Segoe UI", 11, "bold"))
    status_label_widget.pack(side=tk.LEFT, padx=(4, 0))
    status_label = TkLabelProxy(status_label_widget)

    btn = RoundedButton(ab, text="▶  START SCAN",
                        command=lambda: start_all(log, btn, tree_proxy,
                                                  status_label),
                        bg=COLORS["blue"], hover_bg=COLORS["blue_dark"],
                        active_bg="#1e40af", width=180, height=46,
                        font=("Segoe UI", 11, "bold"))
    btn.pack(side=tk.RIGHT, padx=(10, 0))

    export_btn = RoundedButton(ab, text="⤓  EXPORT EXCEL",
                               command=lambda: export_report(log),
                               bg="#f1f5f9", fg=COLORS["ink"],
                               hover_bg="#e2e8f0", active_bg="#cbd5e1",
                               width=170, height=46,
                               font=("Segoe UI", 10, "bold"))
    export_btn.pack(side=tk.RIGHT)

    stats_row = tk.Frame(right, bg=COLORS["bg"])
    stats_row.grid(row=1, column=0, sticky="ew", pady=(0, 14))
    for c in range(4):
        stats_row.grid_columnconfigure(c, weight=1)

    stat_specs = [
        ("TOTAL NVRS", "0", COLORS["blue_pale"],
         COLORS["blue"], COLORS["blue_border"]),
        ("TOTAL CAMERAS", "0", "#f5f3ff",
         "#6d28d9", "#ddd6fe"),
        ("ONLINE CAMERAS", "0", COLORS["green_pale"],
         COLORS["green"], COLORS["green_border"]),
        ("OFFLINE / ABNORMAL", "0", COLORS["red_pale"],
         COLORS["red_dark"], COLORS["red_border"]),
    ]
    stat_cards = []
    for i, (label, value, bg, fg, border) in enumerate(stat_specs):
        card = RoundedFrame(stats_row, radius=14, bg=bg, border=border,
                            padding=14, width=210, height=86)
        card.grid(row=0, column=i, sticky="ew",
                  padx=(0 if i == 0 else 8, 8 if i < 3 else 0))
        card.configure(height=86)
        tk.Label(card.inner, text=label, bg=bg, fg=COLORS["muted"],
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        num = tk.Label(card.inner, text=value, bg=bg, fg=fg,
                       font=("Segoe UI", 22, "bold"))
        num.pack(anchor="w", pady=(2, 0))
        stat_cards.append(num)

    results_card = RoundedFrame(right, radius=16, bg=COLORS["card"],
                                border=COLORS["line"], padding=16,
                                width=900, height=320)
    results_card.grid(row=2, column=0, sticky="nsew", pady=(0, 14))
    rc = results_card.inner
    rc.grid_columnconfigure(0, weight=1)
    rc.grid_rowconfigure(1, weight=1)

    header_line = tk.Frame(rc, bg=COLORS["card"])
    header_line.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
    tk.Label(header_line, text="Camera exceptions",
             bg=COLORS["card"], fg=COLORS["ink"],
             font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT)
    tk.Label(header_line,
             text="Only offline / abnormal cameras are listed below",
             bg=COLORS["card"], fg=COLORS["muted"],
             font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(10, 0))

    columns = ("no", "name", "ip", "status", "nvr")
    tree = ttk.Treeview(rc, columns=columns, show="headings")
    for key, caption, width, anchor in [
        ("no", "No", 55, tk.CENTER),
        ("name", "Camera Name", 220, tk.W),
        ("ip", "IP Address", 150, tk.W),
        ("status", "Status", 130, tk.CENTER),
        ("nvr", "NVR IP", 170, tk.W),
    ]:
        tree.heading(key, text=caption)
        tree.column(key, width=width, anchor=anchor,
                    stretch=(key in ("name", "nvr")))
    tree.grid(row=1, column=0, sticky="nsew")
    tree.tag_configure("offline", background="#fef2f2", foreground="#991b1b")
    tree.tag_configure("abnormal", background="#fffbeb", foreground="#92400e")

    tree_scroll = ttk.Scrollbar(rc, orient=tk.VERTICAL,
                                command=tree.yview)
    tree.configure(yscrollcommand=tree_scroll.set)
    tree_scroll.grid(row=1, column=1, sticky="ns", padx=(6, 0))
    tree_proxy = TkTreeProxy(tree)

    log_card = RoundedFrame(right, radius=16, bg=COLORS["card"],
                            border=COLORS["line"], padding=14,
                            width=900, height=260)
    log_card.grid(row=3, column=0, sticky="nsew")
    lc = log_card.inner
    lc.grid_columnconfigure(0, weight=1)
    lc.grid_rowconfigure(1, weight=1)

    tk.Label(lc, text="Activity log", bg=COLORS["card"], fg=COLORS["ink"],
             font=("Segoe UI", 11, "bold")).grid(row=0, column=0,
                                                 sticky="w", pady=(0, 6))

    log_widget = scrolledtext.ScrolledText(lc, wrap=tk.WORD,
                                           font=("Consolas", 9),
                                           bg="#0b1220", fg="#cbd5e1",
                                           relief=tk.FLAT,
                                           insertbackground="#93c5fd",
                                           selectbackground="#1e3a8a")
    log_widget.grid(row=1, column=0, sticky="nsew")
    log = TkLogProxy(log_widget)

    footer = tk.Frame(outer, bg=COLORS["bg"])
    footer.pack(fill=tk.X, pady=(12, 0))
    tk.Label(footer, text="NVR SyncGuard  ·  by Codraze",
             bg=COLORS["bg"], fg=COLORS["muted"],
             font=("Segoe UI", 9)).pack(side=tk.LEFT)

    last_saved_label = tk.Label(footer,
                                text=f"Report: {EXCEL_FILE}",
                                bg=COLORS["bg"], fg=COLORS["muted"],
                                font=("Segoe UI", 9))
    last_saved_label.pack(side=tk.RIGHT)

    def update_stats():
        stat_cards[0].config(text=str(len(NVR_LIST)))
        stat_cards[1].config(text=str(total_cameras_count))
        stat_cards[2].config(text=str(online_cameras_count))
        stat_cards[3].config(text=str(offline_cameras_count))
        if last_saved_file:
            last_saved_label.config(
                text=f"Report: {os.path.basename(last_saved_file)}")
        root.after(800, update_stats)
    update_stats()

    def auto_launch():
        if not NVR_LIST:
            log.insert(tk.END,
                       "[INFO] No NVR configured yet — add one on the left, "
                       "then click START SCAN.\n")
            status_label.config(text="● Waiting for first NVR",
                                fg=COLORS["muted"])
            return
        log.insert(tk.END,
                   f"[INFO] Auto-start — launching scan of "
                   f"{len(NVR_LIST)} NVR(s)…\n")
        start_all(log, btn, tree_proxy, status_label, auto_start=True)

    root.after(SCAN_DELAY_SECONDS * 1000, auto_launch)

    root.mainloop()


# =========================================================
if __name__ == "__main__":
    main()