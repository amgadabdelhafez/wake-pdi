from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from cryptography.fernet import Fernet
from config import get_key
from browser_utils import setup_browser_driver
from auth_utils import wait_for_magic_link, create_session_from_cookies
from logger import setup_logger
import os
import time
from typing import Optional, Dict, Any
from urllib.parse import urlparse

logger = setup_logger(__name__)
PORTAL_LOGIN_TRANSITION_SECONDS = 10
DEFAULT_LOGIN_COMPLETION_TIMEOUT_SECONDS = 60
INTERACTIVE_LOGIN_COMPLETION_TIMEOUT_SECONDS = 600


def _safe_browser_location(driver: Any) -> str:
    """Return only an origin host and path for diagnostics, never a query value."""
    try:
        location = urlparse(driver.current_url)
        host = location.hostname or "unknown-host"
        route = location.path or "/"
        return f"{host}{route}"
    except Exception:
        return "unavailable"


def _safe_browser_form_state(driver: Any) -> str:
    """Describe only known control identifiers, never values or page text."""
    controls = (
        "username",
        "email",
        "identify-submit",
        "username_submit_button",
        "password",
        "challenge-authenticator-submit",
        "password_submit_button",
    )
    try:
        visible = []
        for control in controls:
            elements = driver.find_elements(By.ID, control)
            if any(element.is_displayed() for element in elements):
                visible.append(control)
        iframe_present = bool(driver.find_elements(By.TAG_NAME, "iframe"))
        return "controls=%s;iframe=%s" % (",".join(visible) or "none", iframe_present)
    except Exception:
        return "unavailable"

def handle_login_error(driver) -> str:
    """Detect a Portal login error without placing page content in logs."""
    try:
        # legacy container
        error_placeholder = driver.find_element(By.ID, "errorPlaceholder")
        if error_placeholder.is_displayed():
            return "The Portal reported a sign-in error"
    except Exception:
        pass
    try:
        # 2026 flow renders inline error/alert nodes
        for el in driver.find_elements(By.CSS_SELECTOR, "[role='alert'], [class*='error']"):
            if el.is_displayed():
                return "The Portal reported a sign-in error"
    except Exception:
        pass
    return "Unknown login error"

def _first_visible(driver: Any, wait: int, locators) -> Any:
    """Return the first locator that becomes visible; raise if none do."""
    last_error = None
    for by, value in locators:
        try:
            return WebDriverWait(driver, wait).until(
                EC.visibility_of_element_located((by, value))
            )
        except Exception as e:
            last_error = e
    raise last_error


def enter_credentials(driver: Any, username: str, password: str) -> bool:
    """Enter login credentials and submit.

    2026 flow (signon.servicenow.com/x_snc_sso_auth.do?pageId=login), two steps:
      step 1: #username then #identify-submit ("Next")
      step 2: #password then #challenge-authenticator-submit ("Sign in")
    The submit buttons stay disabled until real input events fire; Selenium
    send_keys produces real events, so no JS injection is needed.
    Old pre-2025 ids are kept as fallbacks.
    """
    try:
        # Step 1: identifier
        username_field = _first_visible(driver, 30, [
            (By.ID, "username"),          # 2026 flow
            (By.ID, "email"),             # legacy flow
        ])
        username_field.click()
        username_field.clear()
        username_field.send_keys(username)
        next_button = _first_visible(driver, 15, [
            (By.ID, "identify-submit"),          # 2026 flow
            (By.ID, "username_submit_button"),   # legacy flow
        ])
        WebDriverWait(driver, 15).until(lambda d: next_button.is_enabled())
        next_button.click()
    except Exception as error:
        logger.error(
            "Portal identifier stage failed (%s at %s)",
            type(error).__name__,
            "%s; %s" % (_safe_browser_location(driver), _safe_browser_form_state(driver)),
        )
        return False

    try:
        # Step 2: password
        password_field = _first_visible(driver, 30, [
            (By.ID, "password"),
        ])
        password_field.click()
        password_field.send_keys(password)
        signin_button = _first_visible(driver, 15, [
            (By.ID, "challenge-authenticator-submit"),  # 2026 flow
            (By.ID, "password_submit_button"),          # legacy flow
        ])
        WebDriverWait(driver, 15).until(lambda d: signin_button.is_enabled())
        signin_button.click()
        return True
    except Exception as error:
        logger.error(
            "Portal password stage failed (%s at %s)",
            type(error).__name__,
            "%s; %s" % (_safe_browser_location(driver), _safe_browser_form_state(driver)),
        )
        return False

def _login_completion_timeout_seconds() -> int:
    """Choose a bounded login window without extending unattended runs."""
    configured = os.environ.get("WAKE_PDI_LOGIN_COMPLETION_TIMEOUT_SECONDS")
    if configured:
        try:
            timeout_seconds = int(configured)
        except ValueError:
            timeout_seconds = 0
        if timeout_seconds > 0:
            return timeout_seconds
        logger.warning("Ignoring invalid interactive login timeout configuration")

    if os.environ.get("CHROME_HEADLESS", "").lower() == "false":
        return INTERACTIVE_LOGIN_COMPLETION_TIMEOUT_SECONDS
    return DEFAULT_LOGIN_COMPLETION_TIMEOUT_SECONDS


def wait_for_login_completion(driver: Any) -> bool:
    """Wait for login to land anywhere on the developer portal."""
    timeout_seconds = _login_completion_timeout_seconds()
    try:
        WebDriverWait(driver, timeout_seconds).until(
            EC.url_contains("developer.servicenow.com")
        )
        logger.info("signin success")
        return True
    except Exception as error:
        logger.error(
            "Portal sign-in did not return to Developer Portal (%s at %s)",
            type(error).__name__,
            "%s; %s" % (_safe_browser_location(driver), _safe_browser_form_state(driver)),
        )
        return False

def do_sign_in(config: Dict[str, str]) -> Optional[Any]:
    """
    Handle ServiceNow Developer Portal sign-in process
    
    Args:
        config: Dictionary containing login configuration
        
    Returns:
        Optional[Session]: Authenticated session if successful, None otherwise
    """
    # Decrypt credentials
    sn_dev_username = config["sn_dev_username"]
    encpwdbyt = bytes(config['sn_dev_password'].replace("b'", "").replace("'", ""), 'utf-8')
    refKeybyt = get_key()
    sn_dev_password = (Fernet(refKeybyt).decrypt(encpwdbyt)).decode("utf-8")

    logger.info("Starting Developer Portal sign-in")

    driver = None
    try:
        # Initialize the selected local browser driver.
        driver = setup_browser_driver()
        # Navigate to login page
        signon_url = "https://signon.servicenow.com/x_snc_sso_auth.do?pageId=login&RelayState=%252Fapp%252Fservicenow_ud%252Fexks6phcbx6R8qjln0x7%252Fsso%252Fsaml%253FRelayState%253Dhttps%25253A%25252F%25252Fdeveloper.servicenow.com%25252Fnavpage.do&redirectUri=&email="
        driver.get(signon_url)
        # Firefox returns at DOM readiness while ServiceNow continues its
        # browser-side handoff to the sign-in form. The current route settles
        # into the username controls within this bounded interval.
        time.sleep(PORTAL_LOGIN_TRANSITION_SECONDS)
        logger.info("signin in progress...")

        # Handle login process
        if not enter_credentials(driver, sn_dev_username, sn_dev_password):
            return None

        if not wait_for_login_completion(driver):
            logger.error(handle_login_error(driver))
            return None

        # Wait for requests to complete
        time.sleep(2)

        # Capture magic link
        magic_link = wait_for_magic_link(driver)
        if magic_link:
            logger.info("Successfully captured magic link")
        else:
            logger.warning("Could not capture magic link after multiple attempts")

        # Get cookies and create session. Also capture the dev-portal user token
        # (window.g_ck), which is a JS variable rather than a cookie and is required
        # for devportal.do provisioning calls (they 401 without X-UserToken).
        cookies = driver.get_cookies()
        g_ck = None
        try:
            g_ck = driver.execute_script(
                "return window.g_ck "
                "|| (window.NOW && window.NOW.g_ck) "
                "|| (typeof g_ck !== 'undefined' ? g_ck : '') "
                "|| '';"
            )
        except Exception as error:
            logger.warning("Developer Portal session token was unavailable (%s)", type(error).__name__)
        logger.info("Developer Portal session token captured: %s", "yes" if g_ck else "no")
        return create_session_from_cookies(cookies, magic_link, g_ck)

    except Exception as error:
        logger.error("Unexpected browser sign-in failure (%s)", type(error).__name__)
        return None

    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception as error:
                logger.warning("Unable to close the Portal browser (%s)", type(error).__name__)
