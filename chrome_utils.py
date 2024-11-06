from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from seleniumwire import webdriver
import subprocess
import os
import re
from logger import setup_logger

logger = setup_logger(__name__)

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

def setup_chrome_driver():
    """Set up and configure Chrome driver"""
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--window-size=1400,800")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    # Selenium Wire specific options
    seleniumwire_options = {
        'enable_har': True,
        'ignore_http_methods': ['OPTIONS'],
        'verify_ssl': False
    }

    # Get ChromeDriver path and verify it
    driver_path = get_chromedriver()
    logger.debug(f"ChromeDriver path: {driver_path}")
    verify_chromedriver(driver_path)
    service = Service(executable_path=driver_path)

    return webdriver.Chrome(
        service=service,
        options=chrome_options,
        seleniumwire_options=seleniumwire_options
    )
