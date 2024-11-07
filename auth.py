from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from cryptography.fernet import Fernet
from config import get_key
from chrome_utils import setup_chrome_driver
from auth_utils import wait_for_magic_link, create_session_from_cookies
from logger import setup_logger
import time
from typing import Optional, Dict, Any

logger = setup_logger(__name__)

def handle_login_error(driver) -> str:
    """Handle and return login error message"""
    try:
        error_placeholder = driver.find_element(By.ID, "errorPlaceholder").text
        if error_placeholder:
            return f"Login error: {error_placeholder}"
    except Exception:
        pass
    return "Unknown login error"

def enter_credentials(driver: Any, username: str, password: str) -> bool:
    """Enter login credentials and submit"""
    try:
        # Enter username
        username_field = WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.ID, "email"))
        )
        username_field.click()
        username_field.send_keys(username)
        username_submit_button = driver.find_element(By.ID, "username_submit_button")
        username_submit_button.click()

        # Enter password
        password_field = WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.ID, "password"))
        )
        password_field.click()
        password_field.send_keys(password)
        password_submit_button = WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.ID, "password_submit_button"))
        )
        password_submit_button.click()
        return True
    except Exception as e:
        logger.error(f"Error entering credentials: {e}")
        return False

def wait_for_login_completion(driver: Any) -> bool:
    """Wait for login to complete successfully"""
    try:
        WebDriverWait(driver, 30).until(
            EC.url_to_be("https://developer.servicenow.com/dev.do#!/home")
        )
        logger.info("signin success")
        return True
    except Exception as e:
        logger.error(f"Error waiting for login completion: {e}")
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

    logger.info(f"account: {sn_dev_username}")

    # Initialize Chrome driver
    driver = setup_chrome_driver()
    
    try:
        # Navigate to login page
        signon_url = "https://signon.service-now.com/ssologin.do?RelayState=%252Fapp%252Fservicenow_ud%252Fexks6phcbx6R8qjln0x7%252Fsso%252Fsaml%253FRelayState%253Dhttps%25253A%25252F%25252Fdeveloper.servicenow.com%25252Fnavpage.do&redirectUri=&email="
        driver.get(signon_url)
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

        # Get cookies and create session
        cookies = driver.get_cookies()
        return create_session_from_cookies(cookies, magic_link)

    except Exception as e:
        logger.error(f"Unexpected error during sign in: {e}")
        return None

    finally:
        driver.quit()
