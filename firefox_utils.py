"""Restricted-runtime Firefox WebDriver setup for scheduled Portal access."""

import os
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.firefox.service import Service

from logger import setup_logger


logger = setup_logger(__name__)
DEFAULT_FIREFOX_BINARY = "/usr/bin/firefox-esr"
DEFAULT_GECKODRIVER = "/usr/local/bin/geckodriver"
PAGE_LOAD_TIMEOUT_SECONDS = 45


def _executable_from_env(variable: str, default: str) -> str:
    candidate = Path(os.environ.get(variable, default))
    if not candidate.is_file() or not os.access(candidate, os.X_OK):
        raise RuntimeError(f"required browser executable is unavailable: {candidate}")
    return str(candidate)


def setup_firefox_driver():
    """Create a headless Firefox driver without weakening its sandbox."""
    firefox_binary = _executable_from_env("FIREFOX_BINARY", DEFAULT_FIREFOX_BINARY)
    geckodriver = _executable_from_env("GECKODRIVER_PATH", DEFAULT_GECKODRIVER)

    options = webdriver.FirefoxOptions()
    options.binary_location = firefox_binary
    # The Portal's analytics resources are deliberately not a readiness signal.
    # Return at DOMContentLoaded and let the explicit element waits in auth.py
    # determine whether the actual sign-in form is usable.
    options.page_load_strategy = "eager"
    if os.environ.get("CHROME_HEADLESS", "true").lower() == "true":
        options.add_argument("-headless")
    options.set_preference("browser.cache.disk.enable", False)
    options.set_preference("browser.search.suggest.enabled", False)
    options.set_preference("browser.urlbar.suggest.searches", False)
    options.set_preference("datareporting.healthreport.uploadEnabled", False)
    options.set_preference("toolkit.telemetry.enabled", False)
    options.set_preference("app.normandy.enabled", False)
    options.set_preference("network.captive-portal-service.enabled", False)
    options.set_preference("network.connectivity-service.enabled", False)

    service = Service(
        executable_path=geckodriver,
        service_args=["--log", "fatal"],
        log_output=os.devnull,
    )
    logger.info("Starting Firefox WebDriver")
    driver = webdriver.Firefox(service=service, options=options)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT_SECONDS)
    return driver
