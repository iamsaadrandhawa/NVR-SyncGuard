"""
Ping helpers: TCP and ICMP checks for NVRs and cameras.

All functions are pure - they return a bool and never touch UI state.
Read-only access to state constants (timeouts, method).
"""

import re
import socket
import subprocess

import state
from core.url_utils import is_ipv4


def _ping_tcp(ip, port=80, timeout=3):
    """Try a TCP connect to ip:port. Returns True if the port accepts."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((ip, port))
        return True
    except Exception:
        return False


def _ping_icmp(ip, timeout=3):
    """Use the Windows ping.exe command. Returns True if a reply was seen."""
    try:
        cmd = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), ip]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout + 2
        )
        out = (result.stdout or "").lower()
        return ("ttl=" in out) or ("reply from" in out)
    except Exception:
        return False


def _is_camera_reachable(ip, timeout=None):
    """Check whether a camera IP is reachable.

    Uses state.CAMERA_PING_METHOD ('tcp' or 'icmp') and tries several
    common camera ports when using TCP.
    """
    if not ip or not is_ipv4(ip):
        return False
    if timeout is None:
        timeout = state.CAMERA_PING_TIMEOUT_SECONDS

    if state.CAMERA_PING_METHOD == "icmp":
        return _ping_icmp(ip, timeout=timeout)

    # TCP: try RTSP, HTTP, and a common alt port
    for port in (80, 554, 8000):
        try:
            if _ping_tcp(ip, port=port, timeout=timeout):
                return True
        except Exception:
            continue
    return False


def _is_nvr_reachable(url, timeout=4):
    """TCP connect to the NVR web port.

    This is more reliable than an HTTP request: a 401/403 response or a slow
    web server no longer looks like 'down'.
    """
    from urllib.parse import urlparse
    try:
        p = urlparse(url)
        host = p.hostname
        port = p.port or (443 if p.scheme == "https" else 80)
        if not host:
            return False
    except Exception:
        return False

    # Two tries = fewer false "DOWN" alerts
    for _ in range(2):
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception:
            continue
    return False