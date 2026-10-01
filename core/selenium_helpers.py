"""
Selenium wait/click helpers shared by time_sync, camera_scan, and nvr_scan.

Everything here is defensive: every function returns rather than raising,
because the original app was designed to keep going even when a page element
misbehaves. That behavior is preserved exactly.
"""

import re
import time
import tkinter as tk

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, WebDriverException

import state


# =========================================================
# REDACTION
# =========================================================
_PWD_KEYS = re.compile(r'(?i)(pass(word)?|pwd)\s*[:=]\s*("[^"]*"|\'[^\']*\'|\S+)')


def redact(text):
    """Mask anything that looks like a password in a log line."""
    if text is None:
        return ""
    try:
        return _PWD_KEYS.sub(r'\1: <redacted>', str(text))
    except Exception:
        return ""


# =========================================================
# BASIC WAITS
# =========================================================
def _wait(driver, timeout, condition, desc, log=None, fatal=False):
    """Wait until `condition` is true. Returns the result, or None on timeout.
    Never raises unless fatal=True."""
    try:
        return WebDriverWait(driver, timeout).until(condition)
    except TimeoutException:
        if log:
            try:
                log.insert(tk.END, f"[WARN] Timeout waiting for {desc} ({timeout}s)\n")
            except Exception:
                pass
        if fatal:
            raise
        return None
    except WebDriverException as e:
        if log:
            try:
                msg = (str(e).splitlines() or [""])[0]
                log.insert(tk.END, f"[WARN] WebDriver error for {desc}: {msg}\n")
            except Exception:
                pass
        if fatal:
            raise
        return None


def _any_present(*xpaths):
    """Return a predicate that succeeds on the first displayed element
    matching any of the given XPaths."""
    def _predicate(driver):
        for xp in xpaths:
            try:
                for el in driver.find_elements(By.XPATH, xp):
                    if el.is_displayed():
                        return el
            except Exception:
                continue
        return False
    return _predicate


def _any_clickable(*xpaths):
    """Return a predicate that succeeds on the first element that is
    displayed, enabled, has non-zero size, and is not covered by another
    element at its center point."""
    def _predicate(driver):
        # Wait for document.readyState first - no point probing a half-loaded DOM
        try:
            ready = driver.execute_script("return document.readyState")
            if ready != "complete":
                return False
        except Exception:
            pass

        for xp in xpaths:
            try:
                els = driver.find_elements(By.XPATH, xp)
                for el in els:
                    try:
                        if not el.is_displayed() or not el.is_enabled():
                            continue
                        rect = el.rect
                        if rect.get("width", 0) <= 0 or rect.get("height", 0) <= 0:
                            continue
                        # Not covered by another element?
                        try:
                            cx = rect["x"] + rect["width"] / 2
                            cy = rect["y"] + rect["height"] / 2
                            top = driver.execute_script(
                                "return document.elementFromPoint(arguments[0], arguments[1]);",
                                cx, cy
                            )
                            if top is None:
                                continue
                            if top == el:
                                return el
                            if driver.execute_script(
                                "return arguments[0].contains(arguments[1]) || arguments[1].contains(arguments[0]);",
                                top, el
                            ):
                                return el
                        except Exception:
                            return el
                    except Exception:
                        continue
            except Exception:
                continue
        return False
    return _predicate


def _small_buffer(log=None):
    """Sleep for state.STABILITY_BUFFER seconds to let animations settle."""
    try:
        if state.STABILITY_BUFFER > 0:
            time.sleep(state.STABILITY_BUFFER)
    except Exception:
        pass


# =========================================================
# OVERLAY-SAFE CLICK
# =========================================================
def _wait_overlay_gone(driver, timeout=None):
    """Wait for any modal/dark overlay to disappear before clicking.
    Returns True if the screen looks clear, False if still covered."""
    if timeout is None:
        timeout = state.OVERLAY_WAIT_TIMEOUT
    end_time = time.time() + timeout

    overlay_xpaths = [
        "//div[contains(@style,'height: 100%') and "
        "(contains(@style,'rgb(0, 0, 0)') or contains(@style,'rgba(0, 0, 0'))]",
        "//div[contains(@style,'position: fixed') and "
        "contains(@style,'z-index') and contains(@style,'opacity')]",
        "//div[contains(@class,'loading') and contains(@class,'mask')]",
        "//div[contains(@class,'mask') and contains(@class,'show')]",
    ]

    while time.time() < end_time:
        try:
            blocking = False
            for xp in overlay_xpaths:
                try:
                    for el in driver.find_elements(By.XPATH, xp):
                        try:
                            if not el.is_displayed():
                                continue
                            opacity = el.value_of_css_property("opacity")
                            try:
                                op_val = float(opacity)
                            except Exception:
                                op_val = 1.0
                            if op_val > 0.05:
                                blocking = True
                                break
                        except Exception:
                            continue
                    if blocking:
                        break
                except Exception:
                    continue
            if not blocking:
                return True
        except Exception:
            return True
        time.sleep(0.4)

    return False


def _safe_click(driver, element, log=None, desc="element",
                max_attempts=None, wait_overlay=True):
    """Click an element robustly: native -> JS -> synthetic MouseEvents.

    Returns True on success, False after all attempts fail. Never raises.
    """
    if max_attempts is None:
        max_attempts = state.CLICK_MAX_ATTEMPTS

    def _log(msg):
        if log:
            try:
                log.insert(tk.END, redact(msg))
            except Exception:
                pass

    # Make sure the page is fully loaded before we start
    try:
        WebDriverWait(driver, state.PAGE_READY_TIMEOUT).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
    except Exception:
        pass

    for attempt in range(1, max_attempts + 1):
        if wait_overlay:
            _wait_overlay_gone(driver)

        # Scroll into view so the element isn't off-screen
        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center', inline:'center'});",
                element
            )
            time.sleep(0.3)
        except Exception:
            pass

        # Attempt 1: native Selenium click
        try:
            element.click()
            _log(f"[OK] {desc} clicked\n")
            return True
        except Exception as e1:
            first = (str(e1).splitlines() or [""])[0][:100]
            _log(f"[..] {desc}: native click failed ({first}), trying JS...\n")

        # Attempt 2: JS click
        try:
            driver.execute_script("arguments[0].click();", element)
            _log(f"[OK] {desc} clicked (JS)\n")
            return True
        except Exception:
            pass

        # Attempt 3: synthetic MouseEvents
        try:
            driver.execute_script(
                """
                var el = arguments[0];
                ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(function(t){
                    try {
                        el.dispatchEvent(new MouseEvent(t, {
                            bubbles:true, cancelable:true, view:window
                        }));
                    } catch(e) {}
                });
                """,
                element
            )
            _log(f"[OK] {desc} clicked (synthetic)\n")
            return True
        except Exception:
            pass

        # Backoff between attempts
        if attempt < max_attempts:
            wait_s = min(2 ** attempt, 8)
            _log(f"[..] {desc}: attempt {attempt} failed, backoff {wait_s}s\n")
            time.sleep(wait_s)

    _log(f"[WARN] Could not click {desc} after {max_attempts} attempts\n")
    return False