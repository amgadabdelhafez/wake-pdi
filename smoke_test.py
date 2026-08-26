"""Credential-free smoke test for the 2026 SSO flow.

Proves, without any password: the signon page loads, step-1 selectors exist,
a valid-format identifier enables Next, and clicking Next reaches step 2
(#password visible) or a server-rendered error. Exits 0 only on step-2 reached.

Usage: python smoke_test.py [identifier-email]
"""
import sys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from chrome_utils import setup_chrome_driver
from auth import _first_visible, handle_login_error
from logger import setup_logger

logger = setup_logger(__name__)

SIGNON_URL = ("https://signon.service-now.com/ssologin.do?RelayState=%252Fapp%252F"
              "servicenow_ud%252Fexks6phcbx6R8qjln0x7%252Fsso%252Fsaml%253FRelayState"
              "%253Dhttps%25253A%25252F%25252Fdeveloper.servicenow.com%25252Fnavpage.do"
              "&redirectUri=&email=")

def main() -> int:
    identifier = sys.argv[1] if len(sys.argv) > 1 else "smoke.test@example.com"
    driver = setup_chrome_driver()
    try:
        driver.get(SIGNON_URL)
        logger.info(f"landed on: {driver.current_url}")
        username_field = _first_visible(driver, 30, [(By.ID, "username"), (By.ID, "email")])
        logger.info("step-1 identifier field found")
        username_field.click(); username_field.clear(); username_field.send_keys(identifier)
        next_button = _first_visible(driver, 15, [(By.ID, "identify-submit"), (By.ID, "username_submit_button")])
        WebDriverWait(driver, 15).until(lambda d: next_button.is_enabled())
        logger.info("Next button enabled by real input events")
        next_button.click()
        try:
            WebDriverWait(driver, 20).until(EC.visibility_of_element_located((By.ID, "password")))
            logger.info("SMOKE PASS: step-2 password page reached; selectors are current")
            return 0
        except Exception:
            logger.error(f"step 2 not reached; page said: {handle_login_error(driver)} | url: {driver.current_url}")
            return 1
    finally:
        driver.quit()

if __name__ == "__main__":
    sys.exit(main())
