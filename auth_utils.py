from seleniumwire import webdriver
import requests
import time
from typing import Optional, List, Dict, Any
from logger import setup_logger

logger = setup_logger(__name__)

class AuthError(Exception):
    """Custom exception for authentication-related errors"""
    pass

def wait_for_magic_link(driver: webdriver.Chrome, max_attempts: int = 5) -> Optional[bytes]:
    """
    Wait and retry for magic link capture from browser requests
    
    Args:
        driver: Selenium Wire Chrome WebDriver instance
        max_attempts: Maximum number of attempts to find magic link
        
    Returns:
        bytes: Magic link data if found, None otherwise
        
    Raises:
        AuthError: If there's an error processing requests
    """
    attempt = 0
    while attempt < max_attempts:
        try:
            # Check all requests for magic link
            for request in driver.requests:
                if not request.path:
                    continue
                    
                if '/api/snc/fetch_magic_link_url' in request.path:
                    if request.response and request.response.body:
                        logger.debug(f"Found magic link on attempt {attempt + 1}")
                        return request.response.body
            
            attempt += 1
            if attempt < max_attempts:
                logger.debug(f"Magic link not found, attempt {attempt}/{max_attempts}")
                time.sleep(2)  # Wait before next attempt
        except Exception as e:
            logger.debug(f"Error in attempt {attempt}: {e}")
            attempt += 1
    
    return None

def create_session_from_cookies(
    cookies: List[Dict[str, Any]], 
    magic_link: Optional[bytes] = None
) -> requests.Session:
    """
    Create a requests session from cookies and magic link
    
    Args:
        cookies: List of cookie dictionaries from Selenium
        magic_link: Optional magic link data
        
    Returns:
        requests.Session: Configured session with cookies and magic link
        
    Raises:
        AuthError: If session creation fails
    """
    try:
        session = requests.Session()
        
        # Add cookies to session
        for cookie in cookies:
            if not all(k in cookie for k in ('name', 'value', 'domain')):
                logger.warning(f"Skipping invalid cookie: {cookie}")
                continue
            session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])
        
        # Add magic link and processed cookies to session
        session.magic_link = magic_link
        session.processed_cookies = session.cookies.get_dict()
        
        return session
    except Exception as e:
        raise AuthError(f"Failed to create session from cookies: {e}")

def validate_session(session: requests.Session) -> bool:
    """
    Validate that a session has required cookies and attributes
    
    Args:
        session: requests.Session to validate
        
    Returns:
        bool: True if session is valid, False otherwise
    """
    required_attributes = ['magic_link', 'processed_cookies']
    for attr in required_attributes:
        if not hasattr(session, attr):
            logger.warning(f"Session missing required attribute: {attr}")
            return False
    
    if not session.cookies:
        logger.warning("Session has no cookies")
        return False
    
    return True
