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

def is_arm() -> bool:
    """
    Check if running on ARM architecture
    
    Returns:
        bool: True if running on ARM, False otherwise
    """
    machine = platform.machine().lower()
    return any(arm in machine for arm in ['arm', 'aarch'])

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
        # ARM-specific paths first
        if is_arm():
            chrome_paths = [
                "/usr/bin/chromium",
                "/usr/bin/chromium-browser",
                "/usr/bin/chromium-chromium",
                "/usr/bin/google-chrome",
            ]
        else:
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
    Get installed Chrome/Chromium version
    
    Returns:
        str: Chrome/Chromium version or None if not found
        
    Raises:
        ChromeError: If Chrome/Chromium is not found or version cannot be determined
    """
    try:
        chrome_path = get_chrome_path()
        if not chrome_path:
            raise ChromeError("Chrome/Chromium executable not found")

        output = subprocess.check_output(
            [chrome_path, "--version"],
            stderr=subprocess.STDOUT
        )
        # Support both Chrome and Chromium version strings
        version_match = re.search(r"(?:Chrome|Chromium) (\d+\.\d+\.\d+)", output.decode())
        if not version_match:
            raise ChromeError("Could not determine Chrome/Chromium version")
        
        return version_match.group(1)
    except subprocess.CalledProcessError as e:
        raise ChromeError(f"Error executing Chrome/Chromium: {e}")
    except Exception as e:
        logger.info(f"Error getting Chrome/Chromium version: {e}")
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
        # Check for system binary first
        system_drivers = [
            "/usr/local/bin/chromedriver",
            "/usr/bin/chromedriver",
            "/snap/bin/chromium.chromedriver"
        ]
        for driver in system_drivers:
            if os.path.exists(driver):
                logger.info(f"Using existing system ChromeDriver: {driver}")
                return driver

        chrome_version = get_chrome_version()
        
        # Handle ARM architecture
        if is_arm():
            
            # Try installing one for ARM
            try:
                if chrome_version:
                    major_version = chrome_version.split('.')[0]
                    return ChromeDriverManager(version=f"{major_version}.0.0").install()
                return ChromeDriverManager().install()
            except Exception as e:
                logger.error(f"Failed to install ChromeDriver for ARM: {e}")
                raise ChromeError("Could not find or install ChromeDriver for ARM architecture")
        
        # Non-ARM architecture handling - only try to install if no system binary was found
        if chrome_version:
            major_version = chrome_version.split('.')[0]
            try:
                # Try to get the latest driver version compatible with current Chrome
                return ChromeDriverManager(chrome_type="google-chrome", version="latest").install()
            except Exception as e:
                logger.info(f"Could not get latest version, trying fallback: {e}")
                try:
                    # Fallback to major version
                    return ChromeDriverManager(version=major_version).install()
                except Exception as e:
                    logger.info(f"Could not get major version, trying latest: {e}")
        
        # Final fallback to latest version if all else fails
        return ChromeDriverManager(chrome_type="google-chrome").install()
    except Exception as e:
        logger.error(f"Error installing ChromeDriver: {e}")
        raise ChromeError("Could not find or install ChromeDriver")

def is_system_binary(path: str) -> bool:
    """
    Check if a path points to a system binary
    
    Args:
        path: Path to check
        
    Returns:
        bool: True if path is a system binary, False otherwise
    """
    system_paths = ['/usr/bin/', '/usr/local/bin/', '/snap/bin/']
    return any(path.startswith(sys_path) for sys_path in system_paths)

def verify_chromedriver(driver_path: str) -> None:
    """
    Remove quarantine attribute from chromedriver if it exists and set permissions
    if needed. System binaries are skipped as they should already be properly configured.
    
    Args:
        driver_path: Path to ChromeDriver executable
        
    Raises:
        ChromeError: If verification fails
    """
    if not os.path.exists(driver_path):
        raise ChromeError(f"ChromeDriver not found at {driver_path}")

    try:
        # Skip permission modifications for system binaries
        if is_system_binary(driver_path):
            # logger.info(f"Skipping permission modifications for system binary: {driver_path}")
            return

        if platform.system() == "Darwin":  # macOS only
            # Check if quarantine attribute exists
            result = subprocess.run(['xattr', '-l', driver_path], capture_output=True, text=True)
            if 'com.apple.quarantine' in result.stdout:
                subprocess.run(['xattr', '-d', 'com.apple.quarantine', driver_path], check=True)
                logger.info(f"Successfully removed quarantine attribute from {driver_path}")
            else:
                logger.info(f"No quarantine attribute found on {driver_path}")
        
        # Set executable permission only for non-system binaries
        os.chmod(driver_path, 0o755)
        logger.info(f"Set executable permission on {driver_path}")
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

        # Handle Docker/CI environment or ARM
        if os.environ.get('CHROME_NO_SANDBOX') or os.environ.get('CI') or is_arm():
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-gpu")  # Often needed on ARM
        
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
        logger.info(f"ChromeDriver path: {driver_path}")
        verify_chromedriver(driver_path)
        service = Service(executable_path=driver_path)

        return webdriver.Chrome(
            service=service,
            options=chrome_options,
            seleniumwire_options=seleniumwire_options
        )
    except Exception as e:
        raise ChromeError(f"Failed to setup Chrome driver: {e}")
