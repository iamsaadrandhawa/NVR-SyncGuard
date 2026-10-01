"""
URL helpers used everywhere: validation, host extraction.
No dependencies on the rest of the app except the standard library.
"""

import re
from urllib.parse import urlparse


def normalize_nvr_url(value):
    """Validate and normalize an NVR address.

    Accepts '192.168.1.10', 'nvr.local', 'http://x/', 'https://x/'.
    Raises ValueError with a user-friendly message on bad input.
    """
    value = value.strip()
    if not value:
        raise ValueError("Enter an NVR IP address or host name.")
    if not re.match(r"^https?://", value, re.IGNORECASE):
        value = "http://" + value

    parsed = urlparse(value)
    if not parsed.hostname or not re.fullmatch(r"[A-Za-z0-9.-]+", parsed.hostname):
        raise ValueError("Enter a valid NVR IP address, host name, or URL.")
    if parsed.scheme not in ("http", "https"):
        raise ValueError("NVR URLs must use HTTP or HTTPS.")
    return value.rstrip("/") + "/"


def _nvr_host_only(url):
    """Return just the host portion of an NVR URL (no scheme, no path)."""
    return re.sub(r"^https?://", "", url, flags=re.IGNORECASE).strip("/")


def is_ipv4(text):
    """True if text is a valid dotted-quad IPv4 string."""
    if not text:
        return False
    return bool(re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", text))