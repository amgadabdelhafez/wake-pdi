import requests
import json
from urllib.parse import urlparse, parse_qs
from cryptography.fernet import Fernet
from config import get_key
import re
import time
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def do_sign_in_requests(config):
    sn_dev_username = config["sn_dev_username"]
    encpwdbyt = bytes(config['sn_dev_password'].replace("b'", "").replace("'", ""), 'utf-8')
    refKeybyt = get_key()
    sn_dev_password = (Fernet(refKeybyt).decrypt(encpwdbyt)).decode("utf-8")

    logger.info(f"Attempting to sign in with account: {sn_dev_username}")

    session = requests.Session()

    # Initial request to get necessary cookies
    initial_url = "https://developer.servicenow.com/dev.do"
    response = session.get(initial_url)
    logger.debug(f"Initial request status code: {response.status_code}")
    logger.debug(f"Initial cookies: {session.cookies.get_dict()}")

    time.sleep(2)  # Add a delay to mimic human behavior

    # Get the login URL
    login_url = "https://signon.service-now.com/ssologin.do?RelayState=%252Fapp%252Fservicenow_ud%252Fexks6phcbx6R8qjln0x7%252Fsso%252Fsaml%253FRelayState%253Dhttps%25253A%25252F%25252Fdeveloper.servicenow.com%25252Fdev.do"
    response = session.get(login_url)
    logger.debug(f"Login page request status code: {response.status_code}")
    logger.debug(f"Login page cookies: {session.cookies.get_dict()}")

    time.sleep(2)  # Add a delay to mimic human behavior

    # Submit username
    username_data = {
        "username": sn_dev_username,
        "email": sn_dev_username
    }
    response = session.post(login_url, data=username_data)
    logger.debug(f"Username submission status code: {response.status_code}")
    logger.debug(f"Username submission cookies: {session.cookies.get_dict()}")

    time.sleep(2)  # Add a delay to mimic human behavior

    # Submit password
    password_data = {
        "password": sn_dev_password
    }
    response = session.post(login_url, data=password_data)
    logger.debug(f"Password submission status code: {response.status_code}")
    logger.debug(f"Password submission cookies: {session.cookies.get_dict()}")

    time.sleep(2)  # Add a delay to mimic human behavior

    # Follow redirects manually
    redirect_count = 0
    while response.status_code in (301, 302, 303, 307, 308) and redirect_count < 10:
        redirect_url = response.headers['Location']
        logger.debug(f"Redirecting to: {redirect_url}")
        response = session.get(redirect_url, allow_redirects=False)
        logger.debug(f"Redirect response status code: {response.status_code}")
        logger.debug(f"Redirect cookies: {session.cookies.get_dict()}")
        redirect_count += 1
        time.sleep(1)  # Add a delay between redirects

    # Make a final request to the developer portal
    final_url = "https://developer.servicenow.com/dev.do"
    response = session.get(final_url)
    logger.debug(f"Final request status code: {response.status_code}")
    logger.debug(f"Final URL: {response.url}")
    logger.debug(f"Final cookies: {session.cookies.get_dict()}")

    # Extract tokens and cookies
    tokens = {}
    tokens['g_ck'] = response.headers.get('X-UserToken', '')
    tokens['glide_user_token'] = session.cookies.get('glide_user_token', '')
    
    # If glide_user_token is not in cookies, try to find it in the response content
    if not tokens['glide_user_token']:
        glide_user_token_match = re.search(r'glide_user_token\s*=\s*["\']([^"\']+)["\']', response.text)
        if glide_user_token_match:
            tokens['glide_user_token'] = glide_user_token_match.group(1)

    logger.info(f"Extracted tokens: {tokens}")

    # Check if we've successfully logged in
    if "developer.servicenow.com" in response.url and (tokens['g_ck'] or tokens['glide_user_token']):
        logger.info("Sign in successful")
        return session, {**session.cookies.get_dict(), **tokens}
    else:
        logger.error("Sign in failed")
        logger.debug(f"Final URL: {response.url}")
        logger.debug(f"Final cookies: {session.cookies.get_dict()}")
        return None, None
