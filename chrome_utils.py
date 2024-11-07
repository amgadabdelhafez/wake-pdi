from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from seleniumwire import webdriver
import subprocess
import os
import re
import platform
from typing import Optional
from logger import setup_logger

logger = setup_logger(__name__)

class ChromeError(Exception):
    """Custom exception for Chrome-related errors"""
    pass

def get_chrome_path() -> Optional[str]:
    """
    Get Chrome executable path based on platform
    
    Returns:
        str: Path to Chrome executable or None if not found
    """
    system = platform.system()
    if system == "Darwin":  # macOS
        return "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    elif system == "Windows":
        return "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
    elif system == "Linux":
        chrome_paths = [
            "/usr/bin/google-chrome",
            "/usr/bin/chrome",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
        ]
        for path in chrome_paths:
            if os.path.exists(path):
                return path
    return None

def get_chrome_version() -> Optional[str]:
    """
    Get installed Chrome version
    
    Returns:
        str: Chrome version or None if not found
        
    Raises:
        ChromeError: If Chrome is not found or version cannot be determined
    """
    try:
        chrome_path = get_chrome_path()
        if not chrome_path:
            raise ChromeError("Chrome executable not found")

        output = subprocess.check_output(
            [chrome_path, "--version"],
            stderr=subprocess.STDOUT
        )
        version_match = re.search(r"Chrome (\d+\.\d+\.\d+)", output.decode())
        if not version_match:
            raise ChromeError("Could not determine Chrome version")
        
        return version_match.group(1)
    except subprocess.CalledProcessError as e:
        raise ChromeError(f"Error executing Chrome: {e}")
    except Exception as e:
        logger.debug(f"Error getting Chrome version: {e}")
        return None

def get_chromedriver() -> str:
    """
    Get ChromeDriver with fallback mechanisms
    
    Returns:
        str: Path to ChromeDriver executable
        
    Raises:
        ChromeError: If ChromeDriver cannot be installed or found
    """
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
        system_driver = "/usr/local/bin/chromedriver"
        if os.path.exists(system_driver):
            return system_driver
        raise ChromeError("Could not find or install ChromeDriver")

def verify_chromedriver(driver_path: str) -> None:
    """
    Remove quarantine attribute from chromedriver if it exists
    
    Args:
        driver_path: Path to ChromeDriver executable
        
    Raises:
        ChromeError: If verification fails
    """
    if not os.path.exists(driver_path):
        raise ChromeError(f"ChromeDriver not found at {driver_path}")

    try:
        if platform.system() == "Darwin":  # macOS only
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
        raise ChromeError(f"Failed to verify ChromeDriver: {e}")

def setup_chrome_driver() -> webdriver.Chrome:
    """
    Set up and configure Chrome driver
    
    Returns:
        webdriver.Chrome: Configured Chrome WebDriver instance
        
    Raises:
        ChromeError: If driver setup fails
    """
    try:
        chrome_options = webdriver.ChromeOptions()
        
        # Basic options
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--window-size=1400,800")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        # Handle Docker/CI environment
        if os.environ.get('CHROME_NO_SANDBOX') or os.environ.get('CI'):
            chrome_options.add_argument("--no-sandbox")
        
        # Handle headless mode
        if os.environ.get('CHROME_HEADLESS', '').lower() == 'true':
            chrome_options.add_argument("--headless")

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
    except Exception as e:
        raise ChromeError(f"Failed to setup Chrome driver: {e}")
