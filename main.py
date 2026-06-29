"""
NVR SyncGuard - Automated Time Synchronization & Camera Monitoring
Developed by Qodigi Technologies
Version: 1.0.0
"""

import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

# Import selenium with all submodules explicitly for PyInstaller
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

# Import other dependencies
from webdriver_manager.chrome import ChromeDriverManager
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from datetime import datetime
from PIL import Image, ImageTk

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

# Force import of webdriver module to ensure it's included
try:
    import selenium.webdriver.chrome.webdriver
except ImportError:
    # If import fails, try to load it explicitly
    pass

# --- CONFIG ---
# Get the directory where the EXE is located
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

# Default configuration
DEFAULT_CONFIG = {
    "NVR_LIST": [
        "http://192.168.110.12/",
        "http://192.168.100.11/",
        "http://192.168.100.12/",
        "http://192.168.100.13/",
        "http://192.168.100.14/",
        "http://192.168.100.15/",
        "http://192.168.100.16/",
        "http://192.168.100.17/",
        "http://192.168.100.18/",
        "http://192.168.100.19/",
        "http://192.168.100.21/"
    ],
    "USERNAME": "admin",
    "PASSWORD": "Javaid786",
    "DOWNLOADS_DIR": os.path.join(os.path.expanduser("~"), "Downloads"),
    "EXCEL_FILE": "OfflineCameras.xlsx",
    "QODIGI_URL": "https://qodigi.netlify.app",
    "AUTO_START": True
}

# Load or create config
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            return DEFAULT_CONFIG.copy()
    else:
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(DEFAULT_CONFIG, f, indent=4)
        except:
            pass
        return DEFAULT_CONFIG.copy()

config = load_config()

NVR_LIST = config.get("NVR_LIST", DEFAULT_CONFIG["NVR_LIST"])
USERNAME = config.get("USERNAME", DEFAULT_CONFIG["USERNAME"])
PASSWORD = config.get("PASSWORD", DEFAULT_CONFIG["PASSWORD"])
DOWNLOADS_DIR = config.get("DOWNLOADS_DIR", DEFAULT_CONFIG["DOWNLOADS_DIR"])
EXCEL_FILE = os.path.join(DOWNLOADS_DIR, config.get("EXCEL_FILE", DEFAULT_CONFIG["EXCEL_FILE"]))
QODIGI_URL = config.get("QODIGI_URL", DEFAULT_CONFIG["QODIGI_URL"])
AUTO_START = config.get("AUTO_START", True)

# Handle both relative path and PyInstaller bundle path
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
    LOGO_PATH = os.path.join(base_path, "images", "logo.png")
    ICO_PATH = os.path.join(base_path, "images", "logo.ico")
else:
    LOGO_PATH = os.path.join("images", "logo.png")
    ICO_PATH = os.path.join("images", "logo.ico")

stop_requested = False
total_cameras_count = 0
offline_cameras_count = 0
camera_data = []

# Function to find Chrome executable path
def find_chrome_path():
    """Find Chrome executable path from registry or common locations"""
    chrome_paths = [
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google\\Chrome\\Application\\chrome.exe'),
        os.path.join(os.environ.get('PROGRAMFILES', ''), 'Google\\Chrome\\Application\\chrome.exe'),
        os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Google\\Chrome\\Application\\chrome.exe')
    ]
    
    # Try registry
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe")
        chrome_path = winreg.QueryValue(key, None)
        winreg.CloseKey(key)
        if os.path.exists(chrome_path):
            return chrome_path
    except:
        pass
    
    # Try common paths
    for path in chrome_paths:
        if os.path.exists(path):
            return path
    
    # Try using where command
    try:
        result = subprocess.run(['where', 'chrome'], capture_output=True, text=True)
        if result.returncode == 0:
            paths = result.stdout.strip().split('\n')
            if paths and os.path.exists(paths[0]):
                return paths[0]
    except:
        pass
    
    return None

def get_chromedriver_path(log=None):
    """Get ChromeDriver path - either from cache or download"""
    try:
        # Try to get from webdriver_manager
        chromedriver_path = ChromeDriverManager().install()
        if log:
            log.insert(tk.END, f"✅ ChromeDriver: {os.path.basename(chromedriver_path)}\n")
            log.see(tk.END)
        return chromedriver_path
    except Exception as e:
        if log:
            log.insert(tk.END, f"⚠️ WebDriverManager failed: {e}\n")
            log.insert(tk.END, "🔄 Trying alternative method...\n")
            log.see(tk.END)
        
        # Alternative: Use chromedriver from PATH
        try:
            import shutil
            chromedriver_path = shutil.which('chromedriver')
            if chromedriver_path:
                if log:
                    log.insert(tk.END, f"✅ Found ChromeDriver in PATH: {chromedriver_path}\n")
                    log.see(tk.END)
                return chromedriver_path
        except:
            pass
        
        # Alternative: Try common locations
        common_paths = [
            os.path.join(os.environ.get('USERPROFILE', ''), '.wdm', 'drivers', 'chromedriver', 'win64'),
            os.path.join(os.environ.get('USERPROFILE', ''), '.cache', 'selenium', 'chromedriver'),
            os.path.join(os.environ.get('PROGRAMFILES', ''), 'chromedriver.exe'),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'chromedriver.exe'),
        ]
        
        for base_path in common_paths:
            if os.path.exists(base_path):
                for root, dirs, files in os.walk(base_path):
                    for file in files:
                        if file == 'chromedriver.exe' or file == 'chromedriver':
                            full_path = os.path.join(root, file)
                            if log:
                                log.insert(tk.END, f"✅ Found ChromeDriver: {full_path}\n")
                                log.see(tk.END)
                            return full_path
        
        if log:
            log.insert(tk.END, "❌ ChromeDriver not found. Please install ChromeDriver manually.\n")
            log.see(tk.END)
        return None

def setup_chrome_driver(log=None):
    """Setup ChromeDriver with proper options for EXE"""
    options = Options()
    
    # Find Chrome path
    chrome_path = find_chrome_path()
    if chrome_path:
        options.binary_location = chrome_path
        if log:
            log.insert(tk.END, f"✅ Chrome: {chrome_path}\n")
            log.see(tk.END)
    else:
        if log:
            log.insert(tk.END, "⚠️ Chrome not found. Please install Google Chrome.\n")
            log.see(tk.END)
    
    # Chrome options for better compatibility
    options.add_argument("--start-maximized")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--log-level=3")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # Disable notifications
    prefs = {
        "profile.default_content_setting_values.notifications": 2,
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False
    }
    options.add_experimental_option("prefs", prefs)
    
    return options

def open_qodigi_website(event=None):
    try:
        webbrowser.open_new(QODIGI_URL)
    except Exception as e:
        messagebox.showerror("Error", f"Could not open website: {str(e)}")

# --- TASKS ---
def sync_time(log):
    options = setup_chrome_driver(log)
    
    # Get ChromeDriver path
    chromedriver_path = get_chromedriver_path(log)
    if not chromedriver_path:
        log.insert(tk.END, "❌ Cannot proceed without ChromeDriver\n")
        log.see(tk.END)
        return
    
    for ip in NVR_LIST:
        if stop_requested: break
        log.insert(tk.END, f"\n🔁 Starting time sync for {ip}\n")
        log.see(tk.END)
        driver = None
        try:
            service = Service(chromedriver_path)
            driver = webdriver.Chrome(service=service, options=options)
            wait = WebDriverWait(driver, 15)
            
            driver.get(ip)
            time.sleep(10)
            wait.until(EC.presence_of_element_located((By.ID, "username"))).send_keys(USERNAME)
            wait.until(EC.presence_of_element_located((By.ID, "password"))).send_keys(PASSWORD + Keys.RETURN)
            log.insert(tk.END, "✅ Logged in\n")
            log.see(tk.END)
            time.sleep(10)
            wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(),'Configuration')]"))).click()
            time.sleep(10)
            wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(),'Time Settings')]"))).click()
            time.sleep(5)
            checkbox = wait.until(EC.presence_of_element_located((By.XPATH, "//label[contains(text(),'Sync. with computer time')]/preceding-sibling::input[@type='checkbox']")))
            if not checkbox.is_selected(): checkbox.click()
            wait.until(EC.element_to_be_clickable((By.XPATH, "//*[@id='settingTime']/button"))).click()
            log.insert(tk.END, f"✅ Time sync saved for {ip}\n")
            log.see(tk.END)
            time.sleep(5)
        except Exception as e:
            log.insert(tk.END, f"❌ Error: {str(e)}\n")
            log.see(tk.END)
        finally:
            if driver:
                driver.quit()

def extract_camera_ip_from_row(row, nvr_ip):
    """Extract camera IP from a row element"""
    try:
        row_text = row.text
        ip_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
        ip_matches = re.findall(ip_pattern, row_text)
        
        nvr_ip_clean = nvr_ip.replace('http://', '').replace('/', '')
        for ip in ip_matches:
            if ip != nvr_ip_clean:
                return ip
        return None
    except:
        return None

def save_excel_report(log):
    """Save the Excel report"""
    global camera_data, total_cameras_count, offline_cameras_count
    
    try:
        wb = Workbook()
        wb.remove(wb.active)
        ws = wb.create_sheet("Offline Cameras Report")
        
        # Header
        ws.merge_cells('A1:D1')
        header_cell = ws['A1']
        header_cell.value = "NVR SyncGuard - Scan Summary"
        header_cell.font = Font(name='Arial', size=16, bold=True, color="FFFFFF")
        header_cell.fill = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
        header_cell.alignment = Alignment(horizontal="center", vertical="center")
        
        # Total Cameras
        ws.merge_cells('A2:B2')
        total_cell = ws['A2']
        total_cell.value = f"TOTAL CAMERAS: {total_cameras_count}"
        total_cell.font = Font(name='Arial', size=12, bold=True, color="FFFFFF")
        total_cell.fill = PatternFill(start_color="2980B9", end_color="2980B9", fill_type="solid")
        total_cell.alignment = Alignment(horizontal="center", vertical="center")
        
        # Report Generated
        ws.merge_cells('C2:D2')
        date_cell = ws['C2']
        date_cell.value = f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        date_cell.font = Font(name='Arial', size=11, bold=True, color="FFFFFF")
        date_cell.fill = PatternFill(start_color="34495E", end_color="34495E", fill_type="solid")
        date_cell.alignment = Alignment(horizontal="center", vertical="center")
        
        ws.row_dimensions[3].height = 15
        
        # Table header
        ws.merge_cells('A4:D4')
        table_header = ws['A4']
        table_header.value = "OFFLINE / ABNORMAL CAMERAS"
        table_header.font = Font(name='Arial', size=13, bold=True, color="FFFFFF")
        table_header.fill = PatternFill(start_color="E74C3C", end_color="E74C3C", fill_type="solid")
        table_header.alignment = Alignment(horizontal="center", vertical="center")
        
        # Column headers
        headers = ["NVR IP", "Camera IP", "Status", "Checked At"]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=5, column=col)
            cell.value = header
            cell.font = Font(bold=True, color="FFFFFF", size=11)
            cell.fill = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
        
        # Add data
        row_num = 6
        offline_count = 0
        for data in camera_data:
            if data['status'] in ["Offline", "Abnormal"]:
                ws.cell(row=row_num, column=1).value = data['nvr_ip']
                ws.cell(row=row_num, column=2).value = data['camera_ip']
                ws.cell(row=row_num, column=3).value = data['status']
                ws.cell(row=row_num, column=4).value = data['checked_at']
                
                status_cell = ws.cell(row=row_num, column=3)
                if data['status'] == "Offline":
                    status_cell.fill = PatternFill(start_color="E74C3C", end_color="E74C3C", fill_type="solid")
                    status_cell.font = Font(color="FFFFFF", bold=True)
                elif data['status'] == "Abnormal":
                    status_cell.fill = PatternFill(start_color="F39C12", end_color="F39C12", fill_type="solid")
                    status_cell.font = Font(color="FFFFFF", bold=True)
                
                offline_count += 1
                row_num += 1
        
        # If no offline cameras
        if offline_count == 0:
            ws.merge_cells(f'A{row_num}:D{row_num}')
            no_offline_cell = ws.cell(row=row_num, column=1)
            no_offline_cell.value = "✅ All cameras are online!"
            no_offline_cell.font = Font(name='Arial', size=12, bold=True, color="27AE60")
            no_offline_cell.fill = PatternFill(start_color="D5F5E3", end_color="D5F5E3", fill_type="solid")
            no_offline_cell.alignment = Alignment(horizontal="center", vertical="center")
        
        # Set column widths
        for col, width in {'A': 22, 'B': 25, 'C': 15, 'D': 22}.items():
            ws.column_dimensions[col].width = width
        
        # Save
        if os.path.exists(EXCEL_FILE):
            try:
                os.remove(EXCEL_FILE)
                time.sleep(0.3)
            except:
                pass
        
        wb.save(EXCEL_FILE)
        wb.close()
        
        log.insert(tk.END, f"\n{'='*60}\n")
        log.insert(tk.END, f"✅ Report Saved: {EXCEL_FILE}\n")
        log.insert(tk.END, f"📊 Total: {total_cameras_count} | Offline: {offline_count}\n")
        log.insert(tk.END, f"{'='*60}\n")
        log.see(tk.END)
        
        return True
    except Exception as e:
        log.insert(tk.END, f"❌ Error saving: {e}\n")
        log.see(tk.END)
        return False

def check_cameras(log, tree, status_label):
    global total_cameras_count, offline_cameras_count, camera_data
    
    total_cameras_count = 0
    offline_cameras_count = 0
    camera_data = []
    
    options = setup_chrome_driver(log)
    
    # Get ChromeDriver path
    chromedriver_path = get_chromedriver_path(log)
    if not chromedriver_path:
        log.insert(tk.END, "❌ Cannot proceed without ChromeDriver\n")
        log.see(tk.END)
        return
    
    for nvr_index, nvr_ip in enumerate(NVR_LIST):
        if stop_requested: 
            break
            
        log.insert(tk.END, f"\n{'='*60}\n")
        log.insert(tk.END, f"📹 NVR {nvr_index+1}/{len(NVR_LIST)}: {nvr_ip}\n")
        log.insert(tk.END, f"{'='*60}\n")
        log.see(tk.END)
        
        driver = None
        try:
            service = Service(chromedriver_path)
            driver = webdriver.Chrome(service=service, options=options)
            wait = WebDriverWait(driver, 20)
            
            # Login
            driver.get(nvr_ip)
            time.sleep(5)
            wait.until(EC.presence_of_element_located((By.ID, "username"))).send_keys(USERNAME)
            wait.until(EC.presence_of_element_located((By.ID, "password"))).send_keys(PASSWORD + Keys.RETURN)
            log.insert(tk.END, "✅ Logged in\n")
            log.see(tk.END)
            time.sleep(10)
            
            # Configuration
            wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(),'Configuration')]"))).click()
            log.insert(tk.END, "✅ Configuration\n")
            log.see(tk.END)
            time.sleep(10)
            
            # Camera Settings
            camera_settings_clicked = False
            for selector in [
                '//*[@id="menu"]/div/div[2]/div[5]',
                "//div[contains(text(),'Camera Settings')]",
                "//*[contains(text(),'Camera') and contains(text(),'Settings')]"
            ]:
                try:
                    wait.until(EC.element_to_be_clickable((By.XPATH, selector))).click()
                    log.insert(tk.END, "✅ Camera Settings\n")
                    log.see(tk.END)
                    camera_settings_clicked = True
                    break
                except:
                    continue
            
            if not camera_settings_clicked:
                log.insert(tk.END, "❌ Camera Settings not found\n")
                log.see(tk.END)
                continue
            
            time.sleep(5)
            
            # Find cameras
            camera_rows = []
            try:
                table = wait.until(EC.presence_of_element_located((By.ID, "tableDigitalChannels")))
                camera_rows = table.find_elements(By.XPATH, ".//div[contains(@class, 'row')]")
                log.insert(tk.END, f"✅ Found {len(camera_rows)} cameras\n")
                log.see(tk.END)
            except:
                try:
                    camera_rows = driver.find_elements(By.CLASS_NAME, "digital-channel-item")
                    log.insert(tk.END, f"✅ Found {len(camera_rows)} cameras\n")
                    log.see(tk.END)
                except:
                    log.insert(tk.END, "❌ No cameras found\n")
                    log.see(tk.END)
                    continue
            
            checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            nvr_cameras = 0
            nvr_offline = 0
            
            for i, row in enumerate(camera_rows[:64]):
                try:
                    camera_ip = extract_camera_ip_from_row(row, nvr_ip)
                    if not camera_ip:
                        camera_ip = f"Camera {i+1}"
                    
                    row_text = row.text.lower()
                    status = "Online"
                    if any(w in row_text for w in ["offline", "disconnect"]):
                        status = "Offline"
                        nvr_offline += 1
                    elif any(w in row_text for w in ["abnormal", "error"]):
                        status = "Abnormal"
                        nvr_offline += 1
                    
                    camera_data.append({
                        'nvr_ip': nvr_ip,
                        'camera_ip': camera_ip,
                        'status': status,
                        'checked_at': checked_at
                    })
                    
                    if status in ["Offline", "Abnormal"]:
                        tree.insert("", tk.END, values=(camera_ip, status))
                        log.insert(tk.END, f"⚠️ {camera_ip} - {status}\n")
                        log.see(tk.END)
                    
                    nvr_cameras += 1
                except:
                    continue
            
            total_cameras_count += nvr_cameras
            offline_cameras_count += nvr_offline
            
            log.insert(tk.END, f"\n📊 Summary: {nvr_cameras} total, {nvr_offline} offline\n")
            log.see(tk.END)
            status_label.config(text=f"Status: {total_cameras_count} total, {offline_cameras_count} offline")
            
        except Exception as e:
            log.insert(tk.END, f"❌ Error: {e}\n")
            log.see(tk.END)
        finally:
            if driver:
                driver.quit()
    
    if not stop_requested and camera_data:
        save_excel_report(log)

# --- GUI ---
def start_all(log, btn, tree, status_label, auto_start=False):
    global stop_requested, total_cameras_count, offline_cameras_count, camera_data
    
    if btn["text"] == "Stop":
        stop_requested = True
        btn.config(state=tk.DISABLED, text="Stopping...", bg="#d35400")
        return

    stop_requested = False
    total_cameras_count = 0
    offline_cameras_count = 0
    camera_data = []
    
    btn.config(text="Stop", bg="#c0392b")
    status_label.config(text="Status: Running...", fg="#27ae60")
    log.delete(1.0, tk.END)
    tree.delete(*tree.get_children())

    def task():
        # Check Chrome
        chrome_path = find_chrome_path()
        if not chrome_path:
            log.insert(tk.END, "❌ Chrome not found!\n")
            log.see(tk.END)
            status_label.config(text="Status: Error - Chrome not found", fg="#e74c3c")
            btn.config(state=tk.NORMAL, text="Start", bg="#2980b9")
            return
        
        log.insert(tk.END, f"✅ Chrome: {chrome_path}\n")
        log.see(tk.END)
        
        # If auto-start, add a message
        if auto_start:
            log.insert(tk.END, "\n🔄 Auto-starting process...\n")
            log.see(tk.END)
        
        # Run time sync
        sync_time(log)
        
        if stop_requested:
            log.insert(tk.END, "\n⛔ Stopped\n")
            status_label.config(text="Status: Stopped", fg="#e74c3c")
        else:
            log.insert(tk.END, "\n🚀 Checking cameras...\n")
            log.see(tk.END)
            check_cameras(log, tree, status_label)
            
            if not stop_requested:
                log.insert(tk.END, "\n🎉 Done!\n")
                status_label.config(text=f"Status: Done - {total_cameras_count} total, {offline_cameras_count} offline", fg="#27ae60")
            else:
                log.insert(tk.END, "\n⛔ Stopped\n")
                status_label.config(text="Status: Stopped", fg="#e74c3c")

        btn.config(state=tk.NORMAL, text="Start", bg="#2980b9")
        if not stop_requested:
            status_label.config(text=f"Status: Ready - Last: {total_cameras_count} total, {offline_cameras_count} offline", fg="#7f8c8d")

    threading.Thread(target=task, daemon=True).start()

def update_layout(event=None):
    pass

# --- Main ---
def main():
    global root, header_title, header_subtitle, report_label, status_label
    global log_frame, table_frame, btn, qodigi_label, log, style

    root = tk.Tk()
    root.title("NVR SyncGuard")
    root.geometry("1200x800")
    root.minsize(900, 700)
    root.configure(bg='#f5f7fa')

    main_container = tk.Frame(root, bg='#f5f7fa')
    main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

    # Header
    header_frame = tk.Frame(main_container, bg='#2c3e50', height=90)
    header_frame.pack(fill=tk.X, pady=(0, 15))
    header_frame.pack_propagate(False)
    
    header_content = tk.Frame(header_frame, bg='#2c3e50')
    header_content.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
    
    header_title = tk.Label(header_content, text="NVR SyncGuard", 
             font=("Segoe UI", 24, "bold"), fg="white", bg='#2c3e50')
    header_title.pack()
    
    header_subtitle = tk.Label(header_content, text="Automated Time Sync & Camera Monitoring", 
             font=("Segoe UI", 12), fg="#ecf0f1", bg='#2c3e50')
    header_subtitle.pack(pady=5)

    # Info Panel
    info_frame = tk.Frame(main_container, bg='white', bd=1, relief=tk.RAISED)
    info_frame.pack(fill=tk.X, pady=(0, 15))
    
    path_frame = tk.Frame(info_frame, bg='white', padx=15, pady=8)
    path_frame.pack(fill=tk.X)
    
    report_label = tk.Label(path_frame, text="📊 Report:", 
             font=("Segoe UI", 11, "bold"), fg="#34495e", bg='white')
    report_label.pack(anchor=tk.W)
    
    path_text = tk.Text(path_frame, height=1, font=("Consolas", 10), 
                       fg="#2c3e50", bg='#f8f9fa', relief=tk.FLAT, wrap=tk.WORD,
                       padx=10, pady=8)
    path_text.pack(fill=tk.X, pady=5)
    path_text.insert(1.0, EXCEL_FILE)
    path_text.config(state=tk.DISABLED)

    status_frame = tk.Frame(info_frame, bg='white', padx=15, pady=8)
    status_frame.pack(fill=tk.X)
    
    status_label = tk.Label(status_frame, text="Status: Ready", 
                           font=("Segoe UI", 10), fg="#7f8c8d", bg='white')
    status_label.pack(anchor=tk.W)

    # Content
    content_frame = tk.Frame(main_container, bg='#f5f7fa')
    content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
    content_frame.grid_rowconfigure(0, weight=1)
    content_frame.grid_columnconfigure(0, weight=3)
    content_frame.grid_columnconfigure(1, weight=2)

    # Log
    log_frame = tk.LabelFrame(content_frame, text="Log", 
                             font=("Segoe UI", 12, "bold"), 
                             fg="#2c3e50", bg='white', relief=tk.GROOVE, bd=2)
    log_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
    log_frame.grid_rowconfigure(0, weight=1)
    log_frame.grid_columnconfigure(0, weight=1)
    
    log = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD,
                                   font=("Consolas", 10),
                                   bg='#f8f9fa', relief=tk.FLAT)
    log.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    # Table
    table_frame = tk.LabelFrame(content_frame, text="Offline Cameras", 
                               font=("Segoe UI", 12, "bold"), 
                               fg="#2c3e50", bg='white', relief=tk.GROOVE, bd=2)
    table_frame.grid(row=0, column=1, sticky="nsew")
    table_frame.grid_rowconfigure(0, weight=1)
    table_frame.grid_columnconfigure(0, weight=1)
    
    tree_container = tk.Frame(table_frame, bg='white')
    tree_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
    tree_container.grid_rowconfigure(0, weight=1)
    tree_container.grid_columnconfigure(0, weight=1)
    
    style = ttk.Style()
    style.theme_use('clam')
    style.configure("Treeview", background="#f8f9fa", rowheight=28, font=("Segoe UI", 10))
    style.configure("Treeview.Heading", font=("Segoe UI", 11, "bold"), background="#e8e9ea")
    
    tree = ttk.Treeview(tree_container, columns=("camera", "status"), 
                       show="headings", height=10)
    tree.heading("camera", text="Camera IP")
    tree.heading("status", text="Status")
    tree.column("camera", width=200, anchor=tk.W, stretch=True)
    tree.column("status", width=80, anchor=tk.W, stretch=True)
    tree.grid(row=0, column=0, sticky="nsew")

    v_scrollbar = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscroll=v_scrollbar.set)
    v_scrollbar.grid(row=0, column=1, sticky="ns")

    # Button
    btn_container = tk.Frame(main_container, bg='#f5f7fa')
    btn_container.pack(pady=(0, 10))
    
    btn = tk.Button(btn_container, text="Start", 
                   font=("Segoe UI", 13, "bold"), bg="#2980b9", 
                   fg="white", height=2,
                   activebackground="#3498db", activeforeground="white",
                   relief=tk.RAISED, bd=2, cursor="hand2",
                   padx=30, command=lambda: start_all(log, btn, tree, status_label, False))
    btn.pack()

    # Footer
    footer_frame = tk.Frame(main_container, bg='#ecf0f1', height=35)
    footer_frame.pack(fill=tk.X, side=tk.BOTTOM)
    
    qodigi_label = tk.Label(footer_frame, text="Qodigi Technologies", 
                           font=("Segoe UI", 10, "italic"), fg="#2980b9",
                           bg='#ecf0f1', cursor="hand2")
    qodigi_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
    qodigi_label.bind("<Button-1>", lambda e: webbrowser.open(QODIGI_URL))

    # Auto-start after GUI is fully loaded (only if enabled)
    if AUTO_START:
        root.after(1000, lambda: start_all(log, btn, tree, status_label, True))

    root.mainloop()

if __name__ == "__main__":
    main()