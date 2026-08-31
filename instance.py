import json
import requests
import time
import gzip
import io
import os
from logger import setup_logger

logger = setup_logger(__name__)
REQUEST_TIMEOUT_SECONDS = 30

def get_headers(cookies):
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'X-UserToken': cookies.get('glide_user_token', ''),
        'X-WantSessionNotificationMessages': 'true',
        'X-Transaction-Source': 'developer-portal',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': 'https://developer.servicenow.com/dev.do',
        'Origin': 'https://developer.servicenow.com',
        'X-sysparm-ck': cookies.get('sysparm_ck', '') or cookies.get('g_ck', ''),
        'X-g-ck': cookies.get('g_ck', ''),
        'Cookie': '; '.join([f"{k}={v}" for k, v in cookies.items() if k != 'g_ck']),
    }
    return headers

def get_instance_details(magic_link):
    instance_details = {}
    try:
        # Decompress the binary string using GZIP
        compressed_data = io.BytesIO(magic_link)
        with gzip.GzipFile(fileobj=compressed_data, mode='rb') as f:
            decompressed_data = f.read()

        instance_url = json.loads(decompressed_data.decode('utf-8')).get('result', {}).get('url')

        instance_details['instance_id'] = instance_url.split('/')[-2].split(".")[0]
        instance_details['instance_username'] = instance_url.split('/')[-1].split("=")[1].split("&")[0]
        instance_details['instance_password'] = instance_url.split('/')[-1].split("=")[3].split("&")[0]

    except json.JSONDecodeError:
        logger.error("Failed to parse magic link JSON")

    return instance_details


def get_instance_info(session, direct_wake_up=False):
    """Return current instance status, optionally requesting a direct Portal wake.

    Callers must make the mutating ``direct_wake_up=True`` path explicit. The
    daily scheduler always retrieves status first before deciding whether to use
    this action.
    """
    url = "https://developer.servicenow.com/api/snc/v1/dev/instanceInfo"
    params = {
        "sysparm_data": json.dumps(
            {
                "action": "instance.ops.get_instance_info",
                "data": {"direct_wake_up": bool(direct_wake_up)},
            }
        )
    }
    headers = get_headers(session.processed_cookies)

    try:
        response = session.get(
            url,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

        if response.status_code == 200:
            return response.json().get("result", {}).get("instanceInfo")

        else:
            logger.warning("Failed to get instance info (HTTP %s)", response.status_code)
            return None
    except (requests.RequestException, ValueError) as error:
        logger.error("Instance-info request failed (%s)", type(error).__name__)
        return None


def wake_instance(session):
    """Send the Portal's explicit direct-wake request for an assigned PDI."""
    return get_instance_info(session, direct_wake_up=True)

def get_user_info(session):
    url = "https://developer.servicenow.com/api/snc/v1/dev/user_session_info?sysparm_data=%7B%22action%22:%22dev.user.session%22,%22data%22:%7B%22sysparm_okta%22:true%7D%7D"
    headers = get_headers(session.processed_cookies)

    try:
        response = session.get(
            url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS
        )
        if response.status_code == 200:
            data = response.json()
            # Ensure data directory exists
            os.makedirs('data', exist_ok=True)
            # save response to file for later use
            # with open('data/user_info.json', 'w') as f:
            #     json.dump(data, f, indent=2)
            return data
        else:
            logger.warning("Failed to get user info (HTTP %s)", response.status_code)
            return False, None
    except requests.RequestException as error:
        logger.error("User-info request failed (%s)", type(error).__name__)
        return False, None

def get_available_versions(session):
    """Get available PDI versions"""
    url = "https://developer.servicenow.com/devportal.do"
    params = {
        "sysparm_data": json.dumps({
            "action": "product.release.versions",
            "data": {}
        })
    }
    headers = get_headers(session.processed_cookies)
    
    try:
        response = requests.get(
            url, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS
        )
        if response.status_code == 200:
            return response.json()
        logger.error("Failed to get versions (HTTP %s)", response.status_code)
        return None
    except Exception as error:
        logger.error("Release-version request failed (%s)", type(error).__name__)
        return None

def check_user_in_queue(session):
    """Check if user is in queue for an instance"""
    url = "https://developer.servicenow.com/devportal.do"
    params = {
        "sysparm_data": json.dumps({
            "action": "dashboard.user_in_queue",
            "data": {"release": "none"}
        })
    }
    headers = get_headers(session.processed_cookies)
    
    try:
        response = requests.get(
            url, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS
        )
        if response.status_code == 200:
            return response.json()
        logger.error("Failed to check queue (HTTP %s)", response.status_code)
        return None
    except Exception as error:
        logger.error("Queue-status request failed (%s)", type(error).__name__)
        return None

def request_instance(session, family="xanadu"):
    """Request a new PDI instance"""
    url = "https://developer.servicenow.com/devportal.do"
    params = {
        "sysparm_data": json.dumps({
            "action": "dashboard.instance_request",
            "data": {"family": family}
        })
    }
    headers = get_headers(session.processed_cookies)
    
    try:
        response = requests.get(
            url, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS
        )
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "SUCCESS" and result.get("req_id"):
                return result
            # A 200 with status FAIL carries an actionable reason (e.g. the account
            # has not signed the legal agreement / completed the lead-tracking form,
            # which is a one-time manual onboarding step, not a code failure).
            logger.error("Instance request was refused by the Portal (status=%s)", result.get("status"))
            return None
        logger.error("Failed to request an instance (HTTP %s)", response.status_code)
        return None
    except Exception as error:
        logger.error("Instance-request call failed (%s)", type(error).__name__)
        return None

def check_request_status(session, req_id):
    """Check the status of an instance request"""
    url = "https://developer.servicenow.com/devportal.do"
    params = {
        "sysparm_data": json.dumps({
            "action": "instance.ops.get_assign_req_status",
            "data": {"assign_req_id": req_id}
        })
    }
    headers = get_headers(session.processed_cookies)
    
    try:
        response = requests.get(
            url, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS
        )
        if response.status_code == 200:
            return response.json()
        logger.error("Failed to check provisioning status (HTTP %s)", response.status_code)
        return None
    except Exception as error:
        logger.error("Provisioning-status request failed (%s)", type(error).__name__)
        return None

def request_new_instance(session, family="xanadu", max_retries=30, retry_delay=10):
    """
    Main function to handle the complete instance request process
    
    Args:
        session: The authenticated session object
        family: The PDI family version to request (default: xanadu)
        max_retries: Maximum number of status check retries
        retry_delay: Delay between status checks in seconds
        
    Returns:
        dict: Instance details if successful, None if failed
    """
    logger.info("Starting instance request process")
    
    # Check available versions
    versions = get_available_versions(session)
    if not versions:
        logger.error("Failed to get available versions")
        return None
    
    if family not in versions.get("family_name", []):
        logger.error(f"Requested family {family} not available")
        return None
        
    # Check if user is in queue
    queue_status = check_user_in_queue(session)
    if queue_status is None:
        logger.error("Failed to check queue status")
        return None
    
    # Request instance
    request_result = request_instance(session, family)
    if not request_result or not request_result.get("req_id"):
        logger.error("Failed to request instance")
        return None
    
    req_id = request_result["req_id"]
    logger.info(f"Instance requested successfully. Request ID: {req_id}")
    
    # Check request status with retries
    for attempt in range(max_retries):
        status_result = check_request_status(session, req_id)
        if not status_result:
            logger.error("Failed to check request status")
            return None
            
        status = status_result.get("status")
        if status == "complete_success":
            logger.info("Instance successfully provisioned")
            return {
                "instance_url": status_result.get("loginURL"),
                "username": "admin",
                "password": status_result.get("temp_password"),
                "status": "success"
            }
        elif status in ["error", "failed"]:
            logger.error("Instance request was rejected by the Portal")
            return None
            
        logger.info(f"Instance not ready yet, checking again in {retry_delay} seconds...")
        time.sleep(retry_delay)
    
    logger.error("Instance request timed out")
    return None

def check_available_endpoints(session):
    base_url = "https://developer.servicenow.com/api/snc/v1/dev"
    endpoints = [
        "/instanceInfo",
        "/user_info",
        "/check_instance_awake",
        "/releaseInfo",
        "/props",
    ]
    
    for endpoint in endpoints:
        url = base_url + endpoint
        headers = get_headers(session.processed_cookies)
        try:
            response = session.get(
                url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS
            )
            logger.debug("Endpoint %s status code: %s", endpoint, response.status_code)
            logger.debug(
                "Endpoint %s response received (%d bytes)", endpoint, len(response.content)
            )
        except requests.RequestException as error:
            logger.error("Endpoint %s request failed (%s)", endpoint, type(error).__name__)
