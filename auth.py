from seleniumwire import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from cryptography.fernet import Fernet
from config import get_key
import requests
import logging
import json
import pickle

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

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

    service = Service()

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
        return None, None

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
    # driver.quit()

    # Convert cookies to a format that can be used with requests
    session = requests.Session()
    for cookie in cookies:
        session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])

    # Add the magic link to the session
    session.magic_link = magic_link
    session.processed_cookies = session.cookies.get_dict()
    # save the whole session object to file for later use
    # with open('session.pickle', 'wb') as f:
    #     pickle.dump(session, f)

    return session
