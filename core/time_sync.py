"""
Time synchronization for a single NVR.

Runs inside an already-logged-in Selenium session: navigates to
Configuration -> Time Settings, ticks "Sync with computer time", clicks Save.
Handles iframes and multiple candidate XPaths because different NVR firmware
versions present the page differently.
"""

import time
import tkinter as tk

from selenium.webdriver.common.by import By

import state
from core.selenium_helpers import _wait, _any_clickable, _any_present, _safe_click, _small_buffer


def _run_time_sync_for_nvr(driver, log):
    """Do the full time-sync flow for one NVR. Never raises."""
    try:
        # -------- 1) Open Configuration --------
        cfg_el = _wait(
            driver, state.TIMEOUT_DASHBOARD,
            _any_clickable(
                "//a[contains(text(),'Configuration')]",
                "//a[@ng-click=\"jumpTo('config')\"]",
                "//*[contains(text(),'Configuration') and (self::a or self::li or self::div or self::span)]",
            ),
            "Configuration link", log,
        )
        if cfg_el is None:
            log.insert(tk.END, "[WARN] Configuration link not found - time sync skipped.\n")
            return
        if not _safe_click(driver, cfg_el, log, "Configuration"):
            log.insert(tk.END, "[WARN] Configuration click failed - time sync skipped.\n")
            return
        _small_buffer(log)

        # -------- 2) Click Time Settings (top-level first) --------
        clicked_time = False
        t_el = _wait(
            driver, state.TIMEOUT_TIME_MENU,
            _any_clickable(
                "//a[contains(text(),'Time Settings')]",
                "//li[contains(text(),'Time Settings')]",
                "//*[contains(text(),'Time Settings')]",
                "//a[contains(text(),'Time')]",
                "//li[contains(text(),'Time')]",
            ),
            "Time Settings link", log,
        )
        if t_el is not None:
            if _safe_click(driver, t_el, log, "Time Settings"):
                clicked_time = True

        # -------- 2b) If not found, search inside each iframe --------
        if not clicked_time:
            try:
                iframes = driver.find_elements(By.TAG_NAME, "iframe")
            except Exception:
                iframes = []

            for idx in range(len(iframes)):
                if state.stop_requested:
                    break
                try:
                    driver.switch_to.default_content()
                    frames = driver.find_elements(By.TAG_NAME, "iframe")
                    if idx >= len(frames):
                        break
                    driver.switch_to.frame(frames[idx])
                    el = _wait(
                        driver, 15,
                        _any_clickable(
                            "//a[contains(text(),'Time Settings')]",
                            "//li[contains(text(),'Time Settings')]",
                            "//*[contains(text(),'Time Settings')]",
                            "//a[contains(text(),'Time')]",
                            "//li[contains(text(),'Time')]",
                        ),
                        f"Time Settings iframe[{idx}]", log,
                    )
                    if el is not None:
                        if _safe_click(driver, el, log,
                                       f"Time Settings (iframe[{idx}])"):
                            clicked_time = True
                            break
                except Exception:
                    continue
            try:
                driver.switch_to.default_content()
            except Exception:
                pass

        if not clicked_time:
            log.insert(tk.END, "[WARN] Time Settings not reachable.\n")
            return

        _small_buffer(log)

        # -------- 3) Tick "Sync" checkbox and click Save --------
        def _try_save():
            sync_cb = _wait(
                driver, state.TIMEOUT_TIME_FORM,
                _any_present(
                    "//label[contains(text(),'Sync')]/preceding-sibling::input[@type='checkbox']",
                    "//input[@type='checkbox' and contains(@name,'sync')]",
                    "//input[@type='checkbox' and contains(@name,'Sync')]",
                    "//input[@type='checkbox']",
                ),
                "Sync checkbox", log,
            )
            if sync_cb is not None:
                try:
                    if not sync_cb.is_selected():
                        _safe_click(driver, sync_cb, log, "Sync checkbox")
                except Exception:
                    pass

            save_btn = _wait(
                driver, state.TIMEOUT_SAVE_CONFIRM,
                _any_clickable(
                    "//*[@id='settingTime']/button",
                    "//button[contains(text(),'Save')]",
                    "//input[@type='button' and contains(@value,'Save')]",
                    "//input[@type='submit' and contains(@value,'Save')]",
                ),
                "Save button", log,
            )
            if save_btn is not None:
                return _safe_click(driver, save_btn, log, "Save button")
            return False

        saved = _try_save()

        # -------- 3b) If save failed, retry inside each iframe --------
        if not saved:
            try:
                iframes = driver.find_elements(By.TAG_NAME, "iframe")
            except Exception:
                iframes = []

            for idx in range(len(iframes)):
                if state.stop_requested or saved:
                    break
                try:
                    driver.switch_to.default_content()
                    frames = driver.find_elements(By.TAG_NAME, "iframe")
                    if idx >= len(frames):
                        break
                    driver.switch_to.frame(frames[idx])
                    if _try_save():
                        saved = True
                        log.insert(tk.END, f"[OK] Time sync saved in iframe[{idx}]\n")
                        break
                except Exception:
                    continue
            try:
                driver.switch_to.default_content()
            except Exception:
                pass

        # -------- 4) Report result --------
        if saved:
            log.insert(tk.END, "[OK] Time sync saved\n")
        else:
            log.insert(tk.END, "[WARN] Save button not found - set time manually.\n")
        _small_buffer(log)

    except Exception as e:
        first_line = (str(e).splitlines() or [""])[0] or "unknown error"
        log.insert(tk.END, f"[WARN] Time sync failed: {first_line}\n")