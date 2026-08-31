"""Select a browser driver without importing unused browser dependencies."""

import os


class BrowserError(RuntimeError):
    """Raised when the requested browser implementation is unavailable."""


def setup_browser_driver():
    browser = os.environ.get("WAKE_PDI_BROWSER", "chrome").strip().lower()
    if browser == "firefox":
        from firefox_utils import setup_firefox_driver

        return setup_firefox_driver()
    if browser == "chrome":
        from chrome_utils import setup_chrome_driver

        return setup_chrome_driver()
    raise BrowserError(f"unsupported WAKE_PDI_BROWSER value: {browser}")
