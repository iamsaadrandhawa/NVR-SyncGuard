"""
Extract camera IP and camera name from a single camera table row.

The NVR web UI is inconsistent about where it puts the IP (inside a span, a
div, a text node, an attribute), so these functions scan the row's subtree
deeply and try multiple getters before giving up.
"""

import re

from selenium.webdriver.common.by import By

from core.url_utils import _nvr_host_only, is_ipv4


_IP_PATTERN = re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b")


def extract_camera_ip_from_row_deep(row, nvr_ip):
    """Scan every text-ish node under `row` for an IPv4 address that is not
    the NVR's own host. Returns the first match or None."""
    nvr_host = _nvr_host_only(nvr_ip)

    def _valid(ip):
        if ip == nvr_host:
            return False
        if not is_ipv4(ip):
            return False
        try:
            return all(0 <= int(p) <= 255 for p in ip.split("."))
        except ValueError:
            return False

    candidates = []

    # 1) Text from common child tags
    for tag in ("span", "div", "td", "li", "p", "label"):
        try:
            for el in row.find_elements(By.XPATH, f".//{tag}"):
                for getter in (
                    lambda: el.text,
                    lambda: el.get_attribute("textContent"),
                    lambda: el.get_attribute("innerText"),
                ):
                    try:
                        t = (getter() or "").strip()
                        if t:
                            candidates.append(t)
                    except Exception:
                        pass
        except Exception:
            continue

    # 2) The row's own text
    for getter in (
        lambda: row.text,
        lambda: row.get_attribute("textContent"),
        lambda: row.get_attribute("innerText"),
    ):
        try:
            t = (getter() or "").strip()
            if t:
                candidates.append(t)
        except Exception:
            pass

    for text in candidates:
        if not text:
            continue
        for ip in _IP_PATTERN.findall(text):
            if _valid(ip):
                return ip
    return None


def extract_camera_ip_from_row(row, nvr_ip):
    """First try the deep scan. If that fails, do a plain regex search on
    row.text. Returns the IP string or None."""
    ip = extract_camera_ip_from_row_deep(row, nvr_ip)
    if ip:
        return ip
    try:
        for candidate in _IP_PATTERN.findall(row.text):
            if candidate != _nvr_host_only(nvr_ip):
                return candidate
    except Exception:
        pass
    return None


def extract_camera_name_from_row(row, camera_ip=None):
    """Best-effort camera name extraction.

    Tries every text fragment under the row, strips the IP and status
    keywords, and returns the first plausible human-readable string.
    Falls back to "Name unavailable".
    """
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

    ignored = {
        "online", "offline", "abnormal", "error",
        "connected", "disconnected", "enable", "disable",
    }

    for candidate in candidates:
        for line in candidate.splitlines():
            value = " ".join(line.split()).strip(" -:|\t")
            if not value or value.lower() in ignored or re.fullmatch(
                r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b", value
            ):
                continue
            # Strip any embedded IP
            value = re.sub(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b", "", value)
            value = value.strip(" -:|\t")
            # Strip status keywords
            for status_word in ignored:
                value = re.sub(
                    rf"\b{re.escape(status_word)}\b", "", value,
                    flags=re.IGNORECASE
                ).strip(" -:|\t")
            # Reject pure numbers and status-only strings
            if value and value.lower() not in ignored and not re.fullmatch(r"\d+", value):
                return value[:80]

    return "Name unavailable"