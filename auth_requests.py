import json
import re
import time

import requests
from cryptography.fernet import Fernet

from config import get_key
from logger import setup_logger

logger = setup_logger(__name__)
REQUEST_TIMEOUT_SECONDS = 30

def _attach_portal_session_state(session: requests.Session, tokens: dict[str, str]) -> None:
    """Give an HTTP-authenticated session the same narrow interface as browser auth.

    ``instance.py`` only needs the Portal cookies and its CSRF token.  Keep the
    values in memory on the Session object and never log or persist them.
    """
    processed_cookies = session.cookies.get_dict()
    g_ck = tokens.get("g_ck") or tokens.get("glide_user_token")
    if g_ck:
        processed_cookies["g_ck"] = g_ck
        processed_cookies["glide_user_token"] = g_ck
        session.g_ck = g_ck
    session.magic_link = None
    session.processed_cookies = processed_cookies


def _is_guest_portal_session(session: requests.Session) -> bool:
    """Fail closed when the lightweight sign-in flow reaches guest Portal state."""
    url = "https://developer.servicenow.com/api/snc/v1/dev/instanceInfo"
    params = {
        "sysparm_data": json.dumps(
            {
                "action": "instance.ops.get_instance_info",
                "data": {"direct_wake_up": False},
            }
        )
    }
    cookies = session.processed_cookies
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Referer": "https://developer.servicenow.com/dev.do",
        "Origin": "https://developer.servicenow.com",
        "X-UserToken": cookies.get("glide_user_token", ""),
        "X-sysparm-ck": cookies.get("g_ck", ""),
        "X-g-ck": cookies.get("g_ck", ""),
        "Cookie": "; ".join(f"{key}={value}" for key, value in cookies.items()),
    }
    try:
        response = session.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        payload = response.json() if response.status_code == 200 else {}
    except (requests.RequestException, ValueError):
        return True
    result = payload.get("result") if isinstance(payload, dict) else None
    data = result.get("data") if isinstance(result, dict) else None
    return not isinstance(data, dict) or data.get("is_guest_user") is not False


def do_sign_in_requests(config):
    """Authenticate without a browser and return a Portal-ready requests Session."""
    sn_dev_username = config["sn_dev_username"]
    encpwdbyt = bytes(config['sn_dev_password'].replace("b'", "").replace("'", ""), 'utf-8')
    refKeybyt = get_key()
    sn_dev_password = (Fernet(refKeybyt).decrypt(encpwdbyt)).decode("utf-8")

    logger.info("Attempting requests-based sign-in")

    session = requests.Session()
    try:
        # Initial request to get necessary cookies.
        initial_url = "https://developer.servicenow.com/dev.do"
        session.get(initial_url, timeout=REQUEST_TIMEOUT_SECONDS)
        time.sleep(2)

        login_url = "https://signon.service-now.com/ssologin.do?RelayState=%252Fapp%252Fservicenow_ud%252Fexks6phcbx6R8qjln0x7%252Fsso%252Fsaml%253FRelayState%253Dhttps%25253A%25252F%25252Fdeveloper.servicenow.com%25252Fdev.do"
        session.get(login_url, timeout=REQUEST_TIMEOUT_SECONDS)
        time.sleep(2)

        response = session.post(
            login_url,
            data={"username": sn_dev_username, "email": sn_dev_username},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        time.sleep(2)

        response = session.post(
            login_url,
            data={"password": sn_dev_password},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        time.sleep(2)

        redirect_count = 0
        while response.status_code in (301, 302, 303, 307, 308) and redirect_count < 10:
            redirect_url = response.headers.get("Location")
            if not redirect_url:
                logger.error("Requests-based sign-in received a redirect without a location")
                return None
            response = session.get(
                redirect_url, allow_redirects=False, timeout=REQUEST_TIMEOUT_SECONDS
            )
            redirect_count += 1
            time.sleep(1)

        response = session.get(initial_url, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as error:
        logger.error("Requests-based sign-in transport failure: %s", type(error).__name__)
        return None

    tokens = {
        "g_ck": response.headers.get("X-UserToken", ""),
        "glide_user_token": session.cookies.get("glide_user_token", ""),
    }
    if not tokens["glide_user_token"]:
        glide_user_token_match = re.search(
            r'glide_user_token\s*=\s*["\']([^"\']+)["\']', response.text
        )
        if glide_user_token_match:
            tokens["glide_user_token"] = glide_user_token_match.group(1)

    logger.info(
        "Requests-based sign-in extracted session tokens: %s",
        "yes" if any(tokens.values()) else "no",
    )
    if "developer.servicenow.com" not in response.url or not any(tokens.values()):
        logger.error("Requests-based sign-in failed")
        session.close()
        return None

    _attach_portal_session_state(session, tokens)
    if _is_guest_portal_session(session):
        logger.error("Requests-based sign-in reached a guest Portal session")
        session.close()
        return None
    logger.info("Requests-based sign-in successful")
    return session
