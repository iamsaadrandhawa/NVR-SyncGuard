"""
Local SQLite database for NVR SyncGuard.

Stores sites, NVRs, scan reports, camera results, and NVR live state.
This is the source of truth for all local data; the cloud (Firebase)
is only a mirror.

The DB file lives at: <BASE_DIR>/data/local_sites.db

Public API:
    init_db()                          - create file + tables if missing
    get_connection()                   - raw sqlite3 connection (rarely needed)

    Sites:
        insert_site(name, location="", pc_name="")   -> site_id
        get_all_sites()                              -> list of dicts
        get_site(site_id)                            -> dict or None
        update_site(site_id, **fields)
        delete_site(site_id)

    NVRs:
        insert_nvr(site_id, url, username, password_encrypted="") -> nvr_id
        get_nvrs_for_site(site_id)                   -> list of dicts
        get_all_nvrs()                               -> list of dicts
        delete_nvr(nvr_id)

    Scan reports:
        insert_scan_report(site_id, started_at, finished_at,
                           total_nvrs, total_cameras,
                           online_cameras, offline_cameras,
                           excel_path)                   -> report_id
        get_recent_reports(site_id, limit=20)        -> list of dicts
        get_unsynced_reports()                       -> list of dicts
        mark_report_synced(report_id)
        mark_report_failed(report_id, error)

    Camera results:
        insert_camera_results(report_id, rows)       - bulk insert
        get_camera_results(report_id)                -> list of dicts

    NVR live state:
        upsert_nvr_state(nvr_id, state, latency_ms=None, last_ping_at=None)
        get_nvr_state(nvr_id)                        -> dict or None

    Sync retry tracking:
        record_sync_attempt(report_id, error)
        get_sync_attempt(report_id)                  -> dict or None
        clear_sync_attempt(report_id)

Thread safety:
    All public functions acquire a module-level lock, so they are safe to
    call from the main thread and from background worker threads.
"""

import os
import uuid
import sqlite3
import threading
from datetime import datetime, timedelta

from paths import BASE_DIR
from logger import log_line


# =========================================================
# PATHS & LOCK
# =========================================================
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "local_sites.db")

_LOCK = threading.RLock()
_INITIALIZED = False


# =========================================================
# CONNECTION HELPERS
# =========================================================
def _ensure_data_dir():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except Exception as e:
        log_line(f"[DB] Could not create data dir: {e}")


def get_connection():
    """Return a fresh sqlite3 connection. Caller must close it."""
    _ensure_data_dir()
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys (off by default in SQLite)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
    except Exception:
        pass
    return conn


def _row_to_dict(row):
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


def _rows_to_dicts(rows):
    return [_row_to_dict(r) for r in rows]


def _now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _new_id():
    return uuid.uuid4().hex


# =========================================================
# SCHEMA INIT
# =========================================================
_SCHEMA = """
CREATE TABLE IF NOT EXISTS sites (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    location        TEXT DEFAULT '',
    pc_name         TEXT DEFAULT '',
    created_at      TEXT NOT NULL,
    cloud_synced    INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS nvrs (
    id                  TEXT PRIMARY KEY,
    site_id             TEXT NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    url                 TEXT NOT NULL,
    username            TEXT DEFAULT '',
    password_encrypted  TEXT DEFAULT '',
    created_at          TEXT NOT NULL,
    cloud_synced        INTEGER DEFAULT 0,
    UNIQUE(site_id, url)
);

CREATE TABLE IF NOT EXISTS scan_reports (
    id                  TEXT PRIMARY KEY,
    site_id             TEXT NOT NULL REFERENCES sites(id),
    started_at          TEXT NOT NULL,
    finished_at         TEXT,
    total_nvrs          INTEGER DEFAULT 0,
    total_cameras       INTEGER DEFAULT 0,
    online_cameras      INTEGER DEFAULT 0,
    offline_cameras     INTEGER DEFAULT 0,
    excel_path          TEXT DEFAULT '',
    cloud_synced        INTEGER DEFAULT 0,
    cloud_synced_at     TEXT,
    cloud_error         TEXT
);

CREATE TABLE IF NOT EXISTS camera_results (
    id              TEXT PRIMARY KEY,
    report_id       TEXT NOT NULL REFERENCES scan_reports(id) ON DELETE CASCADE,
    camera_name     TEXT DEFAULT '',
    camera_ip       TEXT DEFAULT '',
    nvr_ip          TEXT DEFAULT '',
    status          TEXT DEFAULT '',
    checked_at      TEXT
);

CREATE TABLE IF NOT EXISTS nvr_state (
    nvr_id          TEXT PRIMARY KEY REFERENCES nvrs(id) ON DELETE CASCADE,
    last_ping_at    TEXT,
    last_state      TEXT DEFAULT 'unknown',
    latency_ms      INTEGER,
    last_scan_at    TEXT,
    last_scan_ok    INTEGER,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_attempts (
    report_id       TEXT PRIMARY KEY REFERENCES scan_reports(id) ON DELETE CASCADE,
    attempts        INTEGER DEFAULT 0,
    last_error      TEXT,
    next_retry_at   TEXT
);

CREATE INDEX IF NOT EXISTS idx_scan_reports_synced
    ON scan_reports(cloud_synced);

CREATE INDEX IF NOT EXISTS idx_scan_reports_site
    ON scan_reports(site_id, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_camera_results_report
    ON camera_results(report_id);

CREATE INDEX IF NOT EXISTS idx_nvrs_site
    ON nvrs(site_id);
"""


def init_db():
    """Create the DB file and tables if they do not exist. Idempotent."""
    global _INITIALIZED
    with _LOCK:
        if _INITIALIZED:
            return True
        _ensure_data_dir()
        try:
            conn = get_connection()
            try:
                conn.executescript(_SCHEMA)
                conn.commit()
            finally:
                conn.close()
            _INITIALIZED = True
            log_line(f"[DB] Local database ready at {DB_PATH}")
            return True
        except Exception as e:
            log_line(f"[DB] init_db failed: {e}")
            return False


# =========================================================
# SITES
# =========================================================
def insert_site(name, location="", pc_name=""):
    """Create a new site. Returns the new site_id, or None on failure
    (e.g. duplicate name)."""
    init_db()
    site_id = _new_id()
    with _LOCK:
        try:
            conn = get_connection()
            try:
                conn.execute(
                    "INSERT INTO sites (id, name, location, pc_name, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (site_id, name.strip(), location.strip(),
                     pc_name.strip(), _now_iso()),
                )
                conn.commit()
                log_line(f"[DB] Site created: {name} ({site_id})")
                return site_id
            finally:
                conn.close()
        except sqlite3.IntegrityError:
            log_line(f"[DB] Site already exists: {name}")
            return None
        except Exception as e:
            log_line(f"[DB] insert_site failed: {e}")
            return None


def get_all_sites():
    """Return all sites as a list of dicts."""
    init_db()
    with _LOCK:
        try:
            conn = get_connection()
            try:
                rows = conn.execute(
                    "SELECT * FROM sites ORDER BY created_at ASC"
                ).fetchall()
                return _rows_to_dicts(rows)
            finally:
                conn.close()
        except Exception as e:
            log_line(f"[DB] get_all_sites failed: {e}")
            return []


def get_site(site_id):
    """Return a single site by id, or None."""
    init_db()
    with _LOCK:
        try:
            conn = get_connection()
            try:
                row = conn.execute(
                    "SELECT * FROM sites WHERE id = ?", (site_id,)
                ).fetchone()
                return _row_to_dict(row)
            finally:
                conn.close()
        except Exception as e:
            log_line(f"[DB] get_site failed: {e}")
            return None


def update_site(site_id, **fields):
    """Update selected fields of a site. Returns True on success."""
    allowed = {"name", "location", "pc_name", "cloud_synced"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False
    init_db()
    with _LOCK:
        try:
            conn = get_connection()
            try:
                set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
                values = list(updates.values()) + [site_id]
                conn.execute(
                    f"UPDATE sites SET {set_clause} WHERE id = ?",
                    values,
                )
                conn.commit()
                return True
            finally:
                conn.close()
        except Exception as e:
            log_line(f"[DB] update_site failed: {e}")
            return False


def delete_site(site_id):
    """Delete a site and cascade all NVRs, reports, camera results."""
    init_db()
    with _LOCK:
        try:
            conn = get_connection()
            try:
                conn.execute("DELETE FROM sites WHERE id = ?", (site_id,))
                conn.commit()
                log_line(f"[DB] Site deleted: {site_id}")
                return True
            finally:
                conn.close()
        except Exception as e:
            log_line(f"[DB] delete_site failed: {e}")
            return False


# =========================================================
# NVRS
# =========================================================
def insert_nvr(site_id, url, username="", password_encrypted=""):
    """Add an NVR under a site. Returns nvr_id or None on failure."""
    init_db()
    nvr_id = _new_id()
    with _LOCK:
        try:
            conn = get_connection()
            try:
                conn.execute(
                    "INSERT INTO nvrs (id, site_id, url, username, "
                    "password_encrypted, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (nvr_id, site_id, url.strip(), username.strip(),
                     password_encrypted, _now_iso()),
                )
                conn.commit()
                return nvr_id
            finally:
                conn.close()
        except sqlite3.IntegrityError:
            log_line(f"[DB] NVR already exists for site {site_id}: {url}")
            return None
        except Exception as e:
            log_line(f"[DB] insert_nvr failed: {e}")
            return None


def get_nvrs_for_site(site_id):
    """Return all NVRs belonging to a site."""
    init_db()
    with _LOCK:
        try:
            conn = get_connection()
            try:
                rows = conn.execute(
                    "SELECT * FROM nvrs WHERE site_id = ? ORDER BY created_at ASC",
                    (site_id,),
                ).fetchall()
                return _rows_to_dicts(rows)
            finally:
                conn.close()
        except Exception as e:
            log_line(f"[DB] get_nvrs_for_site failed: {e}")
            return []


def get_all_nvrs():
    """Return every NVR across every site."""
    init_db()
    with _LOCK:
        try:
            conn = get_connection()
            try:
                rows = conn.execute(
                    "SELECT * FROM nvrs ORDER BY created_at ASC"
                ).fetchall()
                return _rows_to_dicts(rows)
            finally:
                conn.close()
        except Exception as e:
            log_line(f"[DB] get_all_nvrs failed: {e}")
            return []


def delete_nvr(nvr_id):
    init_db()
    with _LOCK:
        try:
            conn = get_connection()
            try:
                conn.execute("DELETE FROM nvrs WHERE id = ?", (nvr_id,))
                conn.commit()
                return True
            finally:
                conn.close()
        except Exception as e:
            log_line(f"[DB] delete_nvr failed: {e}")
            return False


# =========================================================
# SCAN REPORTS
# =========================================================
def insert_scan_report(site_id, started_at, finished_at,
                       total_nvrs, total_cameras,
                       online_cameras, offline_cameras,
                       excel_path=""):
    """Create a scan_reports row. Returns report_id or None."""
    init_db()
    report_id = _new_id()
    with _LOCK:
        try:
            conn = get_connection()
            try:
                conn.execute(
                    "INSERT INTO scan_reports "
                    "(id, site_id, started_at, finished_at, total_nvrs, "
                    "total_cameras, online_cameras, offline_cameras, excel_path) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (report_id, site_id, started_at, finished_at,
                     int(total_nvrs), int(total_cameras),
                     int(online_cameras), int(offline_cameras),
                     excel_path),
                )
                conn.commit()
                return report_id
            finally:
                conn.close()
        except Exception as e:
            log_line(f"[DB] insert_scan_report failed: {e}")
            return None


def get_recent_reports(site_id, limit=20):
    """Return the N most recent reports for a site."""
    init_db()
    with _LOCK:
        try:
            conn = get_connection()
            try:
                rows = conn.execute(
                    "SELECT * FROM scan_reports WHERE site_id = ? "
                    "ORDER BY started_at DESC LIMIT ?",
                    (site_id, int(limit)),
                ).fetchall()
                return _rows_to_dicts(rows)
            finally:
                conn.close()
        except Exception as e:
            log_line(f"[DB] get_recent_reports failed: {e}")
            return []


def get_all_reports(limit=100):
    """Return the N most recent reports across all sites."""
    init_db()
    with _LOCK:
        try:
            conn = get_connection()
            try:
                rows = conn.execute(
                    "SELECT * FROM scan_reports ORDER BY started_at DESC LIMIT ?",
                    (int(limit),),
                ).fetchall()
                return _rows_to_dicts(rows)
            finally:
                conn.close()
        except Exception as e:
            log_line(f"[DB] get_all_reports failed: {e}")
            return []


def get_unsynced_reports():
    """Return all reports that have not been uploaded to the cloud yet."""
    init_db()
    with _LOCK:
        try:
            conn = get_connection()
            try:
                rows = conn.execute(
                    "SELECT * FROM scan_reports "
                    "WHERE cloud_synced = 0 "
                    "ORDER BY started_at ASC"
                ).fetchall()
                return _rows_to_dicts(rows)
            finally:
                conn.close()
        except Exception as e:
            log_line(f"[DB] get_unsynced_reports failed: {e}")
            return []


def mark_report_synced(report_id):
    init_db()
    with _LOCK:
        try:
            conn = get_connection()
            try:
                conn.execute(
                    "UPDATE scan_reports "
                    "SET cloud_synced = 1, cloud_synced_at = ?, cloud_error = NULL "
                    "WHERE id = ?",
                    (_now_iso(), report_id),
                )
                conn.commit()
                return True
            finally:
                conn.close()
        except Exception as e:
            log_line(f"[DB] mark_report_synced failed: {e}")
            return False


def mark_report_failed(report_id, error):
    init_db()
    with _LOCK:
        try:
            conn = get_connection()
            try:
                conn.execute(
                    "UPDATE scan_reports SET cloud_error = ? WHERE id = ?",
                    (str(error)[:500], report_id),
                )
                conn.commit()
                return True
            finally:
                conn.close()
        except Exception as e:
            log_line(f"[DB] mark_report_failed failed: {e}")
            return False


# =========================================================
# CAMERA RESULTS
# =========================================================
def insert_camera_results(report_id, rows):
    """Bulk-insert camera rows for a report.

    rows is a list of dicts with keys:
        camera_name, camera_ip, nvr_ip, status, checked_at
    """
    if not rows:
        return 0
    init_db()
    with _LOCK:
        try:
            conn = get_connection()
            try:
                payload = [
                    (_new_id(), report_id,
                     r.get("camera_name", ""),
                     r.get("camera_ip", ""),
                     r.get("nvr_ip", ""),
                     r.get("status", ""),
                     r.get("checked_at", _now_iso()))
                    for r in rows
                ]
                conn.executemany(
                    "INSERT INTO camera_results "
                    "(id, report_id, camera_name, camera_ip, nvr_ip, "
                    "status, checked_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    payload,
                )
                conn.commit()
                return len(payload)
            finally:
                conn.close()
        except Exception as e:
            log_line(f"[DB] insert_camera_results failed: {e}")
            return 0


def get_camera_results(report_id):
    init_db()
    with _LOCK:
        try:
            conn = get_connection()
            try:
                rows = conn.execute(
                    "SELECT * FROM camera_results WHERE report_id = ? "
                    "ORDER BY camera_name ASC",
                    (report_id,),
                ).fetchall()
                return _rows_to_dicts(rows)
            finally:
                conn.close()
        except Exception as e:
            log_line(f"[DB] get_camera_results failed: {e}")
            return []


# =========================================================
# NVR LIVE STATE
# =========================================================
def upsert_nvr_state(nvr_id, state, latency_ms=None,
                     last_ping_at=None, last_scan_ok=None):
    """Insert or update the live state row for an NVR."""
    init_db()
    now = _now_iso()
    if last_ping_at is None:
        last_ping_at = now
    with _LOCK:
        try:
            conn = get_connection()
            try:
                conn.execute(
                    "INSERT INTO nvr_state "
                    "(nvr_id, last_ping_at, last_state, latency_ms, "
                    "last_scan_at, last_scan_ok, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(nvr_id) DO UPDATE SET "
                    "  last_ping_at = excluded.last_ping_at, "
                    "  last_state = excluded.last_state, "
                    "  latency_ms = excluded.latency_ms, "
                    "  last_scan_at = COALESCE(excluded.last_scan_at, "
                    "                            nvr_state.last_scan_at), "
                    "  last_scan_ok = COALESCE(excluded.last_scan_ok, "
                    "                            nvr_state.last_scan_ok), "
                    "  updated_at = excluded.updated_at",
                    (nvr_id, last_ping_at, state, latency_ms,
                     now if last_scan_ok is not None else None,
                     last_scan_ok, now),
                )
                conn.commit()
                return True
            finally:
                conn.close()
        except Exception as e:
            log_line(f"[DB] upsert_nvr_state failed: {e}")
            return False


def get_nvr_state(nvr_id):
    init_db()
    with _LOCK:
        try:
            conn = get_connection()
            try:
                row = conn.execute(
                    "SELECT * FROM nvr_state WHERE nvr_id = ?", (nvr_id,)
                ).fetchone()
                return _row_to_dict(row)
            finally:
                conn.close()
        except Exception as e:
            log_line(f"[DB] get_nvr_state failed: {e}")
            return None


# =========================================================
# SYNC RETRY TRACKING
# =========================================================
def record_sync_attempt(report_id, error,
                        backoff_seconds=None):
    """Record a failed sync attempt and schedule the next retry.

    Default backoff schedule: 30s, 60s, 120s, 300s, 900s, then 3600s.
    """
    init_db()
    schedule = [30, 60, 120, 300, 900, 3600]
    with _LOCK:
        try:
            conn = get_connection()
            try:
                existing = conn.execute(
                    "SELECT attempts FROM sync_attempts WHERE report_id = ?",
                    (report_id,),
                ).fetchone()
                attempts = (existing["attempts"] if existing else 0) + 1

                if backoff_seconds is None:
                    idx = min(attempts - 1, len(schedule) - 1)
                    backoff_seconds = schedule[idx]

                next_retry = (datetime.now()
                              + timedelta(seconds=backoff_seconds)
                              ).strftime("%Y-%m-%d %H:%M:%S")

                conn.execute(
                    "INSERT INTO sync_attempts "
                    "(report_id, attempts, last_error, next_retry_at) "
                    "VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(report_id) DO UPDATE SET "
                    "  attempts = excluded.attempts, "
                    "  last_error = excluded.last_error, "
                    "  next_retry_at = excluded.next_retry_at",
                    (report_id, attempts, str(error)[:500], next_retry),
                )
                conn.commit()
                return attempts
            finally:
                conn.close()
        except Exception as e:
            log_line(f"[DB] record_sync_attempt failed: {e}")
            return 0


def get_sync_attempt(report_id):
    init_db()
    with _LOCK:
        try:
            conn = get_connection()
            try:
                row = conn.execute(
                    "SELECT * FROM sync_attempts WHERE report_id = ?",
                    (report_id,),
                ).fetchone()
                return _row_to_dict(row)
            finally:
                conn.close()
        except Exception as e:
            log_line(f"[DB] get_sync_attempt failed: {e}")
            return None


def clear_sync_attempt(report_id):
    init_db()
    with _LOCK:
        try:
            conn = get_connection()
            try:
                conn.execute(
                    "DELETE FROM sync_attempts WHERE report_id = ?",
                    (report_id,),
                )
                conn.commit()
                return True
            finally:
                conn.close()
        except Exception as e:
            log_line(f"[DB] clear_sync_attempt failed: {e}")
            return False