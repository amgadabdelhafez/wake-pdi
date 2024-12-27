import json
import requests
import time
import logging
import gzip
import io
import os

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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
    logger.debug(f"Headers being sent: {json.dumps(headers, indent=2)}")
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


def get_instance_info(session):
    url = "https://developer.servicenow.com/api/snc/v1/dev/instanceInfo?sysparm_data=%7B%22action%22:%22instance.ops.get_instance_info%22,%22data%22:%7B%22direct_wake_up%22:False%7D%7D"
    headers = get_headers(session.processed_cookies)
    payload={}

    try:
        logger.debug(f"Sending request to: {url}")
        response = requests.request("GET", url, headers=headers, data=payload)

        if response.status_code == 200:
            instance_info = json.loads(response.text)['result']['instanceInfo']
            # Ensure data directory exists
            # os.makedirs('data', exist_ok=True)
            # save instance info to file for later use
            # with open('data/instance_info.json', 'w') as f:
            #     json.dump(instance_info, f, indent=2)
            return instance_info

        else:
            logger.warning(f"Failed to get instance info. Status code: {response.status_code}")
            return None
    except requests.RequestException as e:
        logger.error(f"Instance info request failed: {e}")
        return None

def get_user_info(session):
    url = "https://developer.servicenow.com/api/snc/v1/dev/user_session_info?sysparm_data=%7B%22action%22:%22dev.user.session%22,%22data%22:%7B%22sysparm_okta%22:true%7D%7D"
    headers = get_headers(session.processed_cookies)

    try:
        logger.debug(f"Sending request to: {url}")
        response = session.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            # Ensure data directory exists
            os.makedirs('data', exist_ok=True)
            # save response to file for later use
            # with open('data/user_info.json', 'w') as f:
            #     json.dump(data, f, indent=2)
            return data
        else:
            logger.warning(f"Failed to get user info. Status code: {response.status_code}")
            return False, None
    except requests.RequestException as e:
        logger.error(f"User info request failed: {e}")
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
        response = requests.get(url, params=params, headers=headers, verify=False)
        if response.status_code == 200:
            return response.json()
        logger.error(f"Failed to get versions. Status code: {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Error getting versions: {e}")
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
        response = requests.get(url, params=params, headers=headers, verify=False)
        if response.status_code == 200:
            return response.json()
        logger.error(f"Failed to check queue. Status code: {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Error checking queue: {e}")
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
        response = requests.get(url, params=params, headers=headers, verify=False)
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "SUCCESS" and result.get("req_id"):
                return result
        logger.error(f"Failed to request instance. Status code: {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Error requesting instance: {e}")
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
        response = requests.get(url, params=params, headers=headers, verify=False)
        if response.status_code == 200:
            return response.json()
        logger.error(f"Failed to check status. Status code: {response.status_code}")
        return None
    except Exception as e:
        logger.error(f"Error checking status: {e}")
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
            logger.error(f"Instance request failed: {status_result.get('message')}")
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
            logger.debug(f"Sending request to: {url}")
            response = session.get(url, headers=headers)
            logger.debug(f"Endpoint {endpoint} status code: {response.status_code}")
            logger.debug(f"Endpoint {endpoint} response content: {response.text[:200]}...")  # Log first 200 characters
        except requests.RequestException as e:
            logger.error(f"Request to {endpoint} failed: {e}")
