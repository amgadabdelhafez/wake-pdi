from seleniumwire import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from cryptography.fernet import Fernet
from webdriver_manager.chrome import ChromeDriverManager
from config import get_key
import requests
import logging
import json
import pickle
import subprocess
import os
import re

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# File handler
file_handler = logging.FileHandler('logs/wake.log')
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(levelname)s: %(message)s')
console_handler.setFormatter(console_formatter)

# Add handlers to logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

def get_chrome_version():
    """Get installed Chrome version"""
    try:
        if os.path.exists("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
            output = subprocess.check_output(
                ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--version"],
                stderr=subprocess.STDOUT
            )
            version = re.search(r"Google Chrome (\d+\.\d+\.\d+)", output.decode()).group(1)
            return version
    except Exception as e:
        logger.debug(f"Error getting Chrome version: {e}")
    return None

def get_chromedriver():
    """Get ChromeDriver with fallback mechanisms"""
    try:
        # First try with exact version
        chrome_version = get_chrome_version()
        if chrome_version:
            major_version = chrome_version.split('.')[0]
            try:
                return ChromeDriverManager(version=f"{major_version}.0.0").install()
            except Exception as e:
                logger.debug(f"Could not get exact version, trying latest: {e}")

        # Fallback to latest version
        return ChromeDriverManager().install()
    except Exception as e:
        logger.error(f"Error installing ChromeDriver: {e}")
        # Final fallback to system ChromeDriver
        if os.path.exists("/usr/local/bin/chromedriver"):
            return "/usr/local/bin/chromedriver"
        raise Exception("Could not find or install ChromeDriver")

def verify_chromedriver(driver_path):
    """Remove quarantine attribute from chromedriver if it exists"""
    try:
        if driver_path and os.path.exists(driver_path):
            # Check if quarantine attribute exists
            result = subprocess.run(['xattr', '-l', driver_path], capture_output=True, text=True)
            if 'com.apple.quarantine' in result.stdout:
                subprocess.run(['xattr', '-d', 'com.apple.quarantine', driver_path], check=True)
                logger.info(f"Successfully removed quarantine attribute from {driver_path}")
            else:
                logger.debug(f"No quarantine attribute found on {driver_path}")
            
            # Set executable permission
            os.chmod(driver_path, 0o755)
            logger.debug(f"Set executable permission on {driver_path}")
    except Exception as e:
        logger.debug(f"Chromedriver verification note: {e}")

def do_sign_in(config):
    sn_dev_username = config["sn_dev_username"]
    encpwdbyt = bytes(config['sn_dev_password'].replace("b'", "").replace("'", ""), 'utf-8')
    refKeybyt = get_key()
    sn_dev_password = (Fernet(refKeybyt).decrypt(encpwdbyt)).decode("utf-8")

    logger.info(f"account: {sn_dev_username}")

    chrome_options = webdriver.ChromeOptions()
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--window-size=1400,800")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    # Get ChromeDriver path and verify it
    driver_path = get_chromedriver()
    logger.debug(f"ChromeDriver path: {driver_path}")
    verify_chromedriver(driver_path)
    service = Service(executable_path=driver_path)

    signon_url = "https://signon.service-now.com/ssologin.do?RelayState=%252Fapp%252Fservicenow_ud%252Fexks6phcbx6R8qjln0x7%252Fsso%252Fsaml%253FRelayState%253Dhttps%25253A%25252F%25252Fdeveloper.servicenow.com%25252Fnavpage.do&redirectUri=&email="

    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.get(signon_url)
    logger.info("signin in progress...")

    try:
        username_field = WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.ID, "email"))
        )
        username_field.click()
        username_field.send_keys(sn_dev_username)
        username_submit_button = driver.find_element(By.ID, "username_submit_button")
        username_submit_button.click()
    except Exception as e:
        logger.error(f"Error entering username: {str(e)}")
    
    try:
        password_field = WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.ID, "password"))
        )
        password_field.click()
        password_field.send_keys(sn_dev_password)
    except Exception as e:
        logger.error(f"Error entering password: {str(e)}")
    
    try:
        password_submit_button = WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located((By.ID, "password_submit_button"))
        )
        password_submit_button.click()
    except Exception as e:
        logger.error(f"Error submitting password: {str(e)}")

    try:
        WebDriverWait(driver, 30).until(
            EC.url_to_be("https://developer.servicenow.com/dev.do#!/home")
        )
        logger.info("signin success")
    except Exception as e:
        logger.error(f"Error during sign in: {str(e)}")
        try:
            error_placeholder = driver.find_element(By.ID, "errorPlaceholder").text
            if error_placeholder == 'ⓘYour username or password is invalid. Please try again or reset your password. If on mobile, please reset from your desktop device.':
                error = "invalid password"
            if error_placeholder == 'ⓘYour account is locked due to a high number of unsuccessful login attempts in a short amount of time. Please wait 30 minutes before trying again.':
                error = "account locked"
            logger.error(f"signin failed: {error}")
        except Exception as errorPlaceholderException:
            if (str(errorPlaceholderException).find("Unable to locate element") > -1):
                logger.error("Unable to locate error")
        driver.quit()
        return None

    # Capture the magic link request
    try:
        magic = next(item for item in driver.requests if item.path == '/api/snc/fetch_magic_link_url')
        logger.info(f"Magic link request URL: {magic.url}")
        logger.info(f"Magic link request headers: {magic.headers}")
        logger.info(f"Magic link response: {magic.response.body}")
        magic_link = magic.response.body
    except StopIteration:
        logger.error("Failed to capture magic link")
        magic_link = None

    # Get the cookies after successful login
    cookies = driver.get_cookies()
    driver.quit()

    # Convert cookies to a format that can be used with requests
    session = requests.Session()
    for cookie in cookies:
        session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])

    # Add the magic link to the session
    session.magic_link = magic_link
    session.processed_cookies = session.cookies.get_dict()

    return session
