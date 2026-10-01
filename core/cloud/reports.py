"""
Save a scan's results to the local database.

Called from actions.py after every scan (successful or partial).
Also updates the NVR live state table.

Public API:
    save_scan_to_db(...)    - persist the scan, return report_id or None
    save_nvr_states(...)    - bulk update NVR live state
"""

from datetime import datetime

from core.cloud import local_db
from logger import log_line


def _now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def save_scan_to_db(site_id, started_at, finished_at,
                    total_nvrs, total_cameras,
                    online_cameras, offline_cameras,
                    excel_path, camera_rows):
    """Write a scan report + its camera rows into the local DB.

    site_id       - which site this scan belongs to
    started_at    - ISO string
    finished_at   - ISO string
    camera_rows   - list of dicts {camera_name, camera_ip, nvr_ip,
                                    status, checked_at}

    Returns the report_id (str) or None on failure.
    """
    if not site_id:
        log_line("[DB] save_scan_to_db: no site_id, skipping")
        return None

    report_id = local_db.insert_scan_report(
        site_id=site_id,
        started_at=started_at,
        finished_at=finished_at,
        total_nvrs=total_nvrs,
        total_cameras=total_cameras,
        online_cameras=online_cameras,
        offline_cameras=offline_cameras,
        excel_path=excel_path or "",
    )

    if not report_id:
        log_line("[DB] save_scan_to_db: insert_scan_report returned None")
        return None

    if camera_rows:
        inserted = local_db.insert_camera_results(report_id, camera_rows)
        log_line(f"[DB] Saved report {report_id} with {inserted} camera row(s)")
    else:
        log_line(f"[DB] Saved report {report_id} (no camera rows)")

    return report_id


def save_nvr_states(nvr_map):
    """Bulk update nvr_state table.

    nvr_map is a dict {nvr_id: {"state": "up"/"down", "latency_ms": int}}
    """
    for nvr_id, info in (nvr_map or {}).items():
        try:
            local_db.upsert_nvr_state(
                nvr_id=nvr_id,
                state=info.get("state", "unknown"),
                latency_ms=info.get("latency_ms"),
            )
        except Exception as e:
            log_line(f"[DB] save_nvr_states failed for {nvr_id}: {e}")