"""
Excel report generation.

Builds a styled .xlsx workbook summarising the scan and writes it atomically
to the reports folder. Uses a temp-file + os.replace pattern so a crash
mid-write cannot leave a corrupt workbook behind.
"""

import os
import time
import tempfile
import tkinter as tk
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

import state
from logger import log_line


def _build_target_excel_path():
    """Return the full path for the next report.

    When state.USE_DATE_STAMPED_FILES is True, appends a timestamp to the
    base name so each run produces a new file; otherwise returns the plain
    base filename, overwriting the previous one.
    """
    base_name = state.BASE_EXCEL_FILENAME or "OfflineCameras.xlsx"
    root_, ext = os.path.splitext(base_name)
    if not ext:
        ext = ".xlsx"

    if state.USE_DATE_STAMPED_FILES:
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        new_name = f"{root_}_{stamp}{ext}"
    else:
        new_name = base_name

    return os.path.join(state.DOWNLOADS_DIR, new_name)


def _safe_replace_excel(wb, target_path, log):
    """Save workbook to a temp file, then atomically replace target_path.

    Retries the replace a few times on PermissionError (Excel may have the
    file open briefly). Returns target_path on success, raises on failure.
    """
    target_dir = os.path.dirname(target_path) or "."
    os.makedirs(target_dir, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        prefix=".nvr_sync_", suffix=".xlsx", dir=target_dir
    )
    os.close(fd)

    # 1) Write to temp
    try:
        wb.save(tmp_path)
    except Exception as e:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        raise RuntimeError(f"Could not write temporary workbook: {e}")

    # 2) Move existing target out of the way
    if os.path.exists(target_path):
        backup_path = target_path + ".bak"
        moved = False
        try:
            if os.path.exists(backup_path):
                try:
                    os.remove(backup_path)
                except Exception:
                    pass
            os.replace(target_path, backup_path)
            moved = True
        except PermissionError:
            # Excel sometimes holds a lock briefly - retry a few times
            for _ in range(6):
                try:
                    os.remove(target_path)
                    moved = True
                    break
                except FileNotFoundError:
                    moved = True
                    break
                except PermissionError:
                    time.sleep(0.5)
                except Exception:
                    break
        except Exception:
            pass

        if not moved and os.path.exists(target_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            raise RuntimeError(f"Excel file is locked: {target_path}")

    # 3) Atomically rename temp -> target
    try:
        os.replace(tmp_path, target_path)
    except Exception as e:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        raise RuntimeError(f"Could not finalize Excel file: {e}")

    if log:
        try:
            log.insert(tk.END,
                       f"[OK] Excel saved: {os.path.basename(target_path)}\n")
        except Exception:
            pass
    return target_path


def save_excel_report(log):
    """Build the workbook from state and write it to disk.

    Returns True on success, False on any failure (including "no data to
    write"). Never raises.
    """
    try:
        rows_to_write = (state.camera_data if state.COLLECT_ALL_IPS
                         else state.offline_cameras_data)
        if not state.camera_data and not state.offline_cameras_data:
            log.insert(tk.END,
                       "[SKIP] No camera data collected - Excel file left untouched.\n")
            return False

        target_path = _build_target_excel_path()
        state.EXCEL_FILE = target_path

        wb = Workbook()
        wb.remove(wb.active)
        ws = wb.create_sheet("Camera Report")

        report_title = ("NVR SyncGuard - Full Camera Inventory"
                        if state.COLLECT_ALL_IPS
                        else "NVR SyncGuard - Offline Camera Report")

        # ---- Header rows ----
        ws.merge_cells("A1:F1")
        c = ws["A1"]
        c.value = report_title
        c.font = Font(name="Calibri", size=16, bold=True, color="FFFFFF")
        c.fill = PatternFill(start_color="0F172A", end_color="0F172A",
                             fill_type="solid")
        c.alignment = Alignment(horizontal="center", vertical="center")

        ws.merge_cells("A2:B2")
        c = ws["A2"]
        c.value = f"TOTAL CAMERAS: {state.total_cameras_count}"
        c.font = Font(name="Calibri", size=12, bold=True, color="FFFFFF")
        c.fill = PatternFill(start_color="2563EB", end_color="2563EB",
                             fill_type="solid")
        c.alignment = Alignment(horizontal="center", vertical="center")

        ws.merge_cells("C2:D2")
        c = ws["C2"]
        c.value = f"ONLINE: {state.online_cameras_count}"
        c.font = Font(name="Calibri", size=12, bold=True, color="FFFFFF")
        c.fill = PatternFill(start_color="059669", end_color="059669",
                             fill_type="solid")
        c.alignment = Alignment(horizontal="center", vertical="center")

        ws.merge_cells("E2:F2")
        c = ws["E2"]
        c.value = f"OFFLINE / ABNORMAL: {state.offline_cameras_count}"
        c.font = Font(name="Calibri", size=12, bold=True, color="FFFFFF")
        c.fill = PatternFill(start_color="DC2626", end_color="DC2626",
                             fill_type="solid")
        c.alignment = Alignment(horizontal="center", vertical="center")

        ws.merge_cells("A3:F3")
        c = ws["A3"]
        c.value = f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        c.font = Font(name="Calibri", size=10, italic=True, color="475569")
        c.fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9",
                             fill_type="solid")
        c.alignment = Alignment(horizontal="center", vertical="center")

        ws.row_dimensions[4].height = 15

        ws.merge_cells("A5:F5")
        c = ws["A5"]
        c.value = ("ALL CAMERAS (ONLINE + OFFLINE)"
                   if state.COLLECT_ALL_IPS
                   else "OFFLINE / ABNORMAL CAMERAS")
        c.font = Font(name="Calibri", size=13, bold=True, color="FFFFFF")
        c.fill = PatternFill(start_color="DC2626", end_color="DC2626",
                             fill_type="solid")
        c.alignment = Alignment(horizontal="center", vertical="center")

        # ---- Column headers ----
        headers = ["No", "Camera Name", "IP Address", "NVR IP",
                   "Status", "Checked At"]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=6, column=col)
            cell.value = header
            cell.font = Font(bold=True, color="FFFFFF", size=11)
            cell.fill = PatternFill(start_color="0F172A", end_color="0F172A",
                                    fill_type="solid")
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = Border(
                left=Side(style="thin"), right=Side(style="thin"),
                top=Side(style="thin"), bottom=Side(style="thin"),
            )

        # ---- Data rows ----
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
                cam_name = _s(data.get("camera_name"), "Name unavailable")
                cam_ip = _s(data.get("camera_ip"), "Not shown by NVR")
                nvr_ip = _s(data.get("nvr_ip"), "")
                status = _s(data.get("status"), "")
                checked = _s(data.get("checked_at"), "")

                ws.cell(row=row_num, column=1).value = idx
                ws.cell(row=row_num, column=2).value = cam_name
                ws.cell(row=row_num, column=3).value = cam_ip
                ws.cell(row=row_num, column=4).value = nvr_ip
                ws.cell(row=row_num, column=5).value = status
                ws.cell(row=row_num, column=6).value = checked

                sc = ws.cell(row=row_num, column=5)
                if status == "Offline":
                    sc.fill = PatternFill(start_color="FEE2E2",
                                          end_color="FEE2E2",
                                          fill_type="solid")
                    sc.font = Font(color="991B1B", bold=True)
                elif status == "Abnormal":
                    sc.fill = PatternFill(start_color="FEF3C7",
                                          end_color="FEF3C7",
                                          fill_type="solid")
                    sc.font = Font(color="92400E", bold=True)
                elif status == "Online":
                    sc.fill = PatternFill(start_color="D1FAE5",
                                          end_color="D1FAE5",
                                          fill_type="solid")
                    sc.font = Font(color="065F46", bold=True)

                for col in range(1, 7):
                    ws.cell(row=row_num, column=col).border = Border(
                        left=Side(style="thin", color="E2E8F0"),
                        right=Side(style="thin", color="E2E8F0"),
                        top=Side(style="thin", color="E2E8F0"),
                        bottom=Side(style="thin", color="E2E8F0"),
                    )
                row_num += 1
        else:
            ws.merge_cells(f"A{row_num}:F{row_num}")
            b = ws.cell(row=row_num, column=1)
            b.value = (f"All {state.total_cameras_count} cameras are online"
                       if not state.COLLECT_ALL_IPS
                       else "No cameras discovered")
            b.font = Font(name="Calibri", size=13, bold=True, color="065F46")
            b.fill = PatternFill(start_color="D1FAE5", end_color="D1FAE5",
                                 fill_type="solid")
            b.alignment = Alignment(horizontal="center", vertical="center")
            ws.row_dimensions[row_num].height = 32

        # ---- Column widths, freeze, filter ----
        for col, width in {"A": 8, "B": 30, "C": 22, "D": 22,
                           "E": 14, "F": 22}.items():
            ws.column_dimensions[col].width = width
        ws.freeze_panes = "A7"
        if rows_to_write:
            ws.auto_filter.ref = f"A6:F{max(6, row_num - 1)}"

        # ---- Write to disk ----
        try:
            _safe_replace_excel(wb, target_path, log)
            state.last_saved_file = target_path
        finally:
            try:
                wb.close()
            except Exception:
                pass

        log.insert(tk.END, f"\n{'=' * 60}\n")
        log.insert(tk.END, f"[SAVED] {target_path}\n")
        log.insert(tk.END, f"Total: {state.total_cameras_count} | "
                           f"Online: {state.online_cameras_count} | "
                           f"Offline/Abnormal: {state.offline_cameras_count}\n")
        log.insert(tk.END, f"{'=' * 60}\n")
        return True

    except Exception as e:
        log.insert(tk.END, f"[ERROR] Saving failed: {e}\n")
        try:
            from tkinter import messagebox
            messagebox.showerror("Excel save failed", str(e))
        except Exception:
            pass
        return False