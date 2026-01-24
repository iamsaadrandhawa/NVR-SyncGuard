import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from openpyxl import Workbook, load_workbook
from datetime import datetime
from PIL import Image, ImageTk
import threading
import os
import time
import sys
import webbrowser

# --- CONFIG ---
NVR_LIST = [
    "http://192.168.110.11/",
    "http://192.168.110.12/",
    "http://192.168.110.13/",
    "http://192.168.110.14/",
    "http://192.168.100.12/",
    "http://192.168.100.13/",
    "http://192.168.100.14/",
    "http://192.168.100.15/",
    "http://192.168.100.16/",
    "http://192.168.100.17/",
    "http://192.168.100.18/",
]

USERNAME = "admin"
PASSWORD = "Javaid786"
DOWNLOADS_DIR = os.path.join(os.path.expanduser("~"), "Downloads")
EXCEL_FILE = os.path.join(DOWNLOADS_DIR, "OfflineCameras.xlsx")
QODIGI_URL = "https://qodigi.netlify.app"

# Handle both relative path and PyInstaller bundle path
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    base_path = sys._MEIPASS
    LOGO_PATH = os.path.join(base_path, "images", "logo.png")
    ICO_PATH = os.path.join(base_path, "images", "logo.ico")
else:
    # Running as script
    LOGO_PATH = os.path.join("images", "logo.png")
    ICO_PATH = os.path.join("images", "logo.ico")

stop_requested = False

# Function to open Qodigi website
def open_qodigi_website(event=None):
    try:
        webbrowser.open_new(QODIGI_URL)
    except Exception as e:
        messagebox.showerror("Error", f"Could not open website: {str(e)}")

# --- TASKS ---
def sync_time(log):
    options = Options()
    options.add_argument("--start-maximized")

    for ip in NVR_LIST:
        if stop_requested: break
        log.insert(tk.END, f"\n🔁 Starting time sync for {ip}\n")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        wait = WebDriverWait(driver, 15)
        try:
            driver.get(ip)
            time.sleep(10)
            wait.until(EC.presence_of_element_located((By.ID, "username"))).send_keys(USERNAME)
            wait.until(EC.presence_of_element_located((By.ID, "password"))).send_keys(PASSWORD + Keys.RETURN)
            log.insert(tk.END, "✅ Logged in\n")
            time.sleep(10)
            wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(),'Configuration')]"))).click()
            time.sleep(10)
            wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(),'Time Settings')]"))).click()
            time.sleep(5)
            checkbox = wait.until(EC.presence_of_element_located((By.XPATH, "//label[contains(text(),'Sync. with computer time')]/preceding-sibling::input[@type='checkbox']")))
            if not checkbox.is_selected(): checkbox.click()
            wait.until(EC.element_to_be_clickable((By.XPATH, "//*[@id='settingTime']/button"))).click()
            log.insert(tk.END, f"✅ Time sync saved for {ip}\n")
            time.sleep(5)
        except Exception as e:
            log.insert(tk.END, f"❌ Error for {ip}: {e}\n")
        finally:
            driver.quit()


def check_cameras(log, tree):
    wb = Workbook()
    ws = wb.active
    ws.title = f"Offline Cameras {datetime.now().strftime('%Y-%m-%d %H.%M.%S')}"
    ws.append(["NVR IP", "Camera IP", "Status", "Checked At"])

    options = Options()
    options.add_argument("--start-maximized")

    for ip in NVR_LIST:
        if stop_requested: 
            break
        log.insert(tk.END, f"\n🔁 Starting camera check for {ip}\n")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        wait = WebDriverWait(driver, 20)
        try:
            driver.get(ip)
            time.sleep(5)
            wait.until(EC.presence_of_element_located((By.ID, "username"))).send_keys(USERNAME)
            wait.until(EC.presence_of_element_located((By.ID, "password"))).send_keys(PASSWORD + Keys.RETURN)
            log.insert(tk.END, "✅ Logged in\n")
            time.sleep(10)
            
            # Click Configuration
            wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(),'Configuration')]"))).click()
            log.insert(tk.END, "✅ Clicked Configuration\n")
            time.sleep(10)
            
            # Click Camera Settings - Try multiple possible selectors
            try:
                # First try the original selector
                wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="menu"]/div/div[2]/div[5]'))).click()
                log.insert(tk.END, "✅ Clicked Camera Settings (original selector)\n")
            except:
                try:
                    # Try alternative selector - click on text "Camera Settings"
                    wait.until(EC.element_to_be_clickable((By.XPATH, "//div[contains(text(),'Camera Settings')]"))).click()
                    log.insert(tk.END, "✅ Clicked Camera Settings (text selector)\n")
                except:
                    try:
                        # Try another alternative - click on any element with camera settings
                        wait.until(EC.element_to_be_clickable((By.XPATH, "//*[contains(text(),'Camera') and contains(text(),'Settings')]"))).click()
                        log.insert(tk.END, "✅ Clicked Camera Settings (general selector)\n")
                    except Exception as e:
                        log.insert(tk.END, f"❌ Could not find Camera Settings: {e}\n")
                        driver.quit()
                        continue
            
            time.sleep(5)
            
            # Wait for camera table to load and get camera rows
            try:
                # Wait for the table to be present
                table_container = wait.until(EC.presence_of_element_located((By.ID, "tableDigitalChannels")))
                log.insert(tk.END, "✅ Found camera table\n")
                
                # Find all camera rows - try multiple selectors
                rows = []
                try:
                    rows = table_container.find_elements(By.XPATH, ".//div[contains(@class, 'row')]")
                except:
                    try:
                        rows = driver.find_elements(By.XPATH, "//div[contains(@id, 'channel') or contains(@class, 'channel')]")
                    except:
                        rows = driver.find_elements(By.CLASS_NAME, "digital-channel-item")
                
                log.insert(tk.END, f"✅ Found {len(rows)} camera rows\n")
                
                if len(rows) == 0:
                    # Try to find cameras using a more generic approach
                    all_divs = driver.find_elements(By.TAG_NAME, "div")
                    camera_divs = []
                    for div in all_divs:
                        text = div.text.lower()
                        if any(word in text for word in ["camera", "channel", "ip camera", "ipc"]):
                            if "192.168" in text or "camera" in text:
                                camera_divs.append(div)
                    rows = camera_divs
                    log.insert(tk.END, f"✅ Found {len(rows)} camera elements (alternative method)\n")
                
                checked_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cameras_found = 0
                offline_cameras = 0
                
                for i, row in enumerate(rows[:50]):  # Limit to 50 cameras to avoid infinite loops
                    try:
                        row_html = row.get_attribute('outerHTML')
                        row_text = row.text
                        
                        # Extract camera name/IP - look for patterns
                        camera_ip = f"Camera {i+1}"
                        status = "Unknown"
                        
                        # Look for IP address pattern
                        import re
                        ip_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
                        ip_matches = re.findall(ip_pattern, row_text)
                        if ip_matches:
                            camera_ip = ip_matches[0]
                        
                        # Look for status indicators
                        status_lower = row_text.lower()
                        if "offline" in status_lower or "disconnect" in status_lower:
                            status = "Offline"
                            offline_cameras += 1
                        elif "online" in status_lower or "normal" in status_lower:
                            status = "Online"
                        elif "abnormal" in status_lower:
                            status = "Abnormal"
                            offline_cameras += 1
                        
                        # If we found an offline camera, add to report
                        if status in ["Offline", "Abnormal"]:
                            ws.append([ip, camera_ip, status, checked_at])
                            tree.insert("", tk.END, values=(camera_ip, status))
                            log.insert(tk.END, f"⚠️ Found offline camera: {camera_ip} - {status}\n")
                        
                        cameras_found += 1
                        
                    except Exception as e:
                        log.insert(tk.END, f"❌ Error processing camera row: {e}\n")
                        continue
                
                log.insert(tk.END, f"✅ Processed {cameras_found} cameras, {offline_cameras} offline\n")
                
            except Exception as e:
                log.insert(tk.END, f"❌ Error finding camera table: {e}\n")
                # Take screenshot for debugging
                try:
                    screenshot_path = os.path.join(DOWNLOADS_DIR, f"debug_{ip.replace('://', '_').replace('/', '')}.png")
                    driver.save_screenshot(screenshot_path)
                    log.insert(tk.END, f"📷 Screenshot saved to: {screenshot_path}\n")
                except:
                    pass
            
        except Exception as e:
            log.insert(tk.END, f"❌ General error for {ip}: {e}\n")
        finally:
            driver.quit()

    wb.save(EXCEL_FILE)
    log.insert(tk.END, f"\n📄 Report saved to: {EXCEL_FILE}\n")





# --- GUI ---
def start_all(log, btn, tree, status_label):
    global stop_requested

    # If already running and clicked again (to stop)
    if btn["text"] == "Stop":
        stop_requested = True
        btn.config(state=tk.DISABLED, text="Stopping...", bg="#d35400")
        return

    stop_requested = False
    btn.config(text="Stop", bg="#c0392b")
    status_label.config(text="Status: Running...", fg="#27ae60")
    log.delete(1.0, tk.END)
    tree.delete(*tree.get_children())

    def task():
        # Run time sync first
        sync_time(log)
        
        # Check if stop was requested during time sync
        if stop_requested:
            log.insert(tk.END, "\n⛔ Task stopped by user after time sync.\n")
            status_label.config(text="Status: Stopped", fg="#e74c3c")
        else:
            # Run camera check only if not stopped
            log.insert(tk.END, "\n" + "="*50 + "\n")
            log.insert(tk.END, "Starting Camera Status Check...\n")
            log.insert(tk.END, "="*50 + "\n")
            
            check_cameras(log, tree)
            
            if not stop_requested:
                log.insert(tk.END, "\n🎉 All tasks completed.\n")
                status_label.config(text="Status: Completed", fg="#27ae60")
            else:
                log.insert(tk.END, "\n⛔ Camera check stopped by user.\n")
                status_label.config(text="Status: Stopped", fg="#e74c3c")

        # Reset button
        btn.config(state=tk.NORMAL, text="Start Sync & Camera Check", bg="#2980b9")
        
        # Reset status if not stopped
        if not stop_requested:
            status_label.config(text="Status: Ready", fg="#7f8c8d")

    threading.Thread(target=task, daemon=True).start()
# Update layout on window resize
def update_layout(event=None):
    width = root.winfo_width()
    
    # Adjust font sizes based on window width
    if width < 1000:
        # Small window adjustments
        header_font_size = 20
        subheader_font_size = 10
        label_font_size = 9
        button_font_size = 11
        footer_font_size = 9
        log_font_size = 9
    elif width < 1400:
        # Medium window adjustments
        header_font_size = 22
        subheader_font_size = 11
        label_font_size = 10
        button_font_size = 12
        footer_font_size = 10
        log_font_size = 10
    else:
        # Large window adjustments
        header_font_size = 24
        subheader_font_size = 12
        label_font_size = 11
        button_font_size = 13
        footer_font_size = 11
        log_font_size = 11
    
    # Update header fonts
    try:
        header_title.config(font=("Segoe UI", header_font_size, "bold"))
        header_subtitle.config(font=("Segoe UI", subheader_font_size))
        
        # Update info labels
        report_label.config(font=("Segoe UI", label_font_size, "bold"))
        status_label.config(font=("Segoe UI", label_font_size))
        
        # Update frame titles
        log_frame.config(font=("Segoe UI", label_font_size + 2, "bold"))
        table_frame.config(font=("Segoe UI", label_font_size + 2, "bold"))
        
        # Update button
        btn.config(font=("Segoe UI", button_font_size, "bold"))
        
        # Update footer
        qodigi_label.config(font=("Segoe UI", footer_font_size, "italic"))
        
        # Update log text
        log.config(font=("Consolas", log_font_size))
        
        # Update treeview
        style.configure("Treeview", font=("Segoe UI", log_font_size))
        style.configure("Treeview.Heading", font=("Segoe UI", log_font_size + 1, "bold"))
    except:
        pass

# --- Main ---
def main():
    global root, header_title, header_subtitle, report_label, status_label
    global log_frame, table_frame, btn, qodigi_label, log, style

    root = tk.Tk()
    root.title("NVR SyncGuard - by Qodigi Technologies")
    root.geometry("1200x800")
    root.minsize(900, 700)
    root.configure(bg='#f5f7fa')

    # Set window icon
    try:
        if os.path.exists(ICO_PATH):
            root.iconbitmap(ICO_PATH)
        else:
            icon_image = Image.open(LOGO_PATH)
            icon_photo = ImageTk.PhotoImage(icon_image)
            root.iconphoto(True, icon_photo)
    except Exception as e:
        print(f"Could not set window icon: {e}")

    # Create main container with padding
    main_container = tk.Frame(root, bg='#f5f7fa')
    main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

    # Header Section
    header_frame = tk.Frame(main_container, bg='#2c3e50', height=90)
    header_frame.pack(fill=tk.X, pady=(0, 15))
    header_frame.pack_propagate(False)
    
    header_content = tk.Frame(header_frame, bg='#2c3e50')
    header_content.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
    
    header_title = tk.Label(header_content, text="NVR SyncGuard", 
             font=("Segoe UI", 24, "bold"), fg="white", bg='#2c3e50')
    header_title.pack()
    
    header_subtitle = tk.Label(header_content, text="Automated Time Synchronization & Camera Monitoring", 
             font=("Segoe UI", 12), fg="#ecf0f1", bg='#2c3e50')
    header_subtitle.pack(pady=5)

    # Info Panel
    info_frame = tk.Frame(main_container, bg='white', bd=1, relief=tk.RAISED)
    info_frame.pack(fill=tk.X, pady=(0, 15))
    
    # Report path
    path_frame = tk.Frame(info_frame, bg='white', padx=15, pady=8)
    path_frame.pack(fill=tk.X)
    
    report_label = tk.Label(path_frame, text="📊 Report Location:", 
             font=("Segoe UI", 11, "bold"), fg="#34495e", bg='white')
    report_label.pack(anchor=tk.W)
    
    path_display_frame = tk.Frame(path_frame, bg='#e8e9ea')
    path_display_frame.pack(fill=tk.X, pady=5)
    
    path_text = tk.Text(path_display_frame, height=1, font=("Consolas", 10), 
                       fg="#2c3e50", bg='#f8f9fa', relief=tk.FLAT, wrap=tk.WORD,
                       padx=10, pady=8)
    path_text.pack(fill=tk.X, padx=1, pady=1)
    path_text.insert(1.0, EXCEL_FILE)
    path_text.config(state=tk.DISABLED)

    # Status Panel
    status_frame = tk.Frame(info_frame, bg='white', padx=15, pady=8)
    status_frame.pack(fill=tk.X)
    
    status_label = tk.Label(status_frame, text="Status: Ready", 
                           font=("Segoe UI", 10), fg="#7f8c8d", bg='white')
    status_label.pack(anchor=tk.W)

    # Main Content Area (Log + Table)
    content_frame = tk.Frame(main_container, bg='#f5f7fa')
    content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

    # Configure content frame grid
    content_frame.grid_rowconfigure(0, weight=1)
    content_frame.grid_columnconfigure(0, weight=3)  # Log gets more space
    content_frame.grid_columnconfigure(1, weight=2)  # Table gets less space

    # LEFT PANEL: Process Log
    log_frame = tk.LabelFrame(content_frame, text="Process Log", 
                             font=("Segoe UI", 12, "bold"), 
                             fg="#2c3e50", bg='white', relief=tk.GROOVE, bd=2)
    log_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
    log_frame.grid_rowconfigure(0, weight=1)
    log_frame.grid_columnconfigure(0, weight=1)
    
    log = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD,
                                   font=("Consolas", 10),
                                   bg='#f8f9fa', relief=tk.FLAT)
    log.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    # RIGHT PANEL: Offline Cameras Table
    table_frame = tk.LabelFrame(content_frame, text="Offline Cameras Detected", 
                               font=("Segoe UI", 12, "bold"), 
                               fg="#2c3e50", bg='white', relief=tk.GROOVE, bd=2)
    table_frame.grid(row=0, column=1, sticky="nsew")
    table_frame.grid_rowconfigure(0, weight=1)
    table_frame.grid_columnconfigure(0, weight=1)
    
    tree_container = tk.Frame(table_frame, bg='white')
    tree_container.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
    tree_container.grid_rowconfigure(0, weight=1)
    tree_container.grid_columnconfigure(0, weight=1)
    
    # Configure Treeview style
    style = ttk.Style()
    style.theme_use('clam')
    
    style.configure("Treeview", 
                    background="#f8f9fa",
                    foreground="#2c3e50",
                    rowheight=28,
                    fieldbackground="#f8f9fa",
                    font=("Segoe UI", 10))
    style.configure("Treeview.Heading",
                    font=("Segoe UI", 11, "bold"),
                    background="#e8e9ea",
                    foreground="#2c3e50",
                    relief=tk.FLAT)
    style.map("Treeview", background=[('selected', '#3498db')])
    
    # Create Treeview with scrollbars
    tree = ttk.Treeview(tree_container, columns=("camera", "status"), 
                       show="headings", height=10)
    tree.heading("camera", text="Camera Name / IP Address")
    tree.heading("status", text="Status")
    
    # Configure columns
    tree.column("camera", width=200, anchor=tk.W, stretch=True)
    tree.column("status", width=80, anchor=tk.W, stretch=True)
    
    tree.grid(row=0, column=0, sticky="nsew")

    # Vertical scrollbar
    v_scrollbar = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscroll=v_scrollbar.set)
    v_scrollbar.grid(row=0, column=1, sticky="ns")

    # Horizontal scrollbar for treeview
    h_scrollbar = ttk.Scrollbar(tree_container, orient=tk.HORIZONTAL, command=tree.xview)
    tree.configure(xscroll=h_scrollbar.set)
    h_scrollbar.grid(row=1, column=0, sticky="ew", columnspan=2)

    # Button Container (below main content)
    btn_container = tk.Frame(main_container, bg='#f5f7fa')
    btn_container.pack(pady=(0, 10))
    
    btn = tk.Button(btn_container, text="Start Sync & Camera Check", 
                   font=("Segoe UI", 13, "bold"), bg="#2980b9", 
                   fg="white", height=2,
                   activebackground="#3498db", activeforeground="white",
                   relief=tk.RAISED, bd=2, cursor="hand2",
                   padx=30)
    btn.pack()

    # Footer Section
    footer_frame = tk.Frame(main_container, bg='#ecf0f1', height=35)
    footer_frame.pack(fill=tk.X, side=tk.BOTTOM)
    
    # Create clickable link for Qodigi Technologies
    qodigi_label = tk.Label(
        footer_frame, 
        text="Developed by Qodigi Technologies", 
        font=("Segoe UI", 10, "italic"), 
        fg="#2980b9",
        bg='#ecf0f1',
        cursor="hand2"
    )
    qodigi_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
    
    # Bind click event to the label
    qodigi_label.bind("<Button-1>", open_qodigi_website)
    
    # Add hover effects
    def on_enter(e):
        qodigi_label.config(fg="#1abc9c")
    
    def on_leave(e):
        qodigi_label.config(fg="#2980b9")
    
    qodigi_label.bind("<Enter>", on_enter)
    qodigi_label.bind("<Leave>", on_leave)

    # Configure main container grid for proper expansion
    main_container.grid_rowconfigure(0, weight=0)  # Header
    main_container.grid_rowconfigure(1, weight=0)  # Info panel
    main_container.grid_rowconfigure(2, weight=1)  # Content area
    main_container.grid_rowconfigure(3, weight=0)  # Button
    main_container.grid_rowconfigure(4, weight=0)  # Footer

    # Bind resize event
    root.bind('<Configure>', update_layout)

    # Start the task automatically when GUI opens
    root.after(500, lambda: start_all(log, btn, tree, status_label))

    root.mainloop()


if __name__ == "__main__":
    main()