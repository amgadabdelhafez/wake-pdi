import requests
import time
from logger import setup_logger

logger = setup_logger(__name__)

def wait_for_magic_link(driver, max_attempts=5):
    """Wait and retry for magic link capture"""
    magic_link = None
    attempt = 0
    while attempt < max_attempts and not magic_link:
        try:
            # Check all requests for magic link
            for request in driver.requests:
                if request.path and '/api/snc/fetch_magic_link_url' in request.path:
                    if request.response and request.response.body:
                        logger.debug(f"Found magic link on attempt {attempt + 1}")
                        return request.response.body
            
            attempt += 1
            if attempt < max_attempts:
                logger.debug(f"Magic link not found, attempt {attempt}/{max_attempts}")
                time.sleep(2)  # Wait before next attempt
        except Exception as e:
            logger.debug(f"Error in attempt {attempt}: {e}")
    
    return None

def create_session_from_cookies(cookies, magic_link=None):
    """Create a requests session from cookies and magic link"""
    session = requests.Session()
    for cookie in cookies:
        session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])
    
    session.magic_link = magic_link
    session.processed_cookies = session.cookies.get_dict()
    return session
