import sys
import os
import time
import getpass
import json
import logging
import requests
from datetime import datetime
import logging
from dotenv import dotenv_values

import certifi
import urllib3

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from seleniumwire import webdriver

from webdriver_manager.chrome import ChromeDriverManager

from cryptography.fernet import Fernet


def get_args():

    args = {}
    if len(sys.argv) == 1:
        print("\n\
Control your SN Dev PDIs using this CLI tool. \n\
You can wake your instances up, reset, upgrade, or release your instances, request a new instance with specific version.\n\
--wake-up             wakes up all instances in config file \n\
--request-instance    requests an instance with a specific version [TODO] \n\
--reset-instance      resets an instance to its out-of-the-box settings \n\
--release-instance    releases an instance back to pool \n\
--upgrade-instance    upgrades an instance back to pool [TODO] \n\
--add-account         add a new account credentials to config file \n\
--config-file         use a specific config file instead of default config.json \n\
--not-headless        show browser window (for debugging)\
        ")
        return False
    # TODO --schedule
    if '--not-headless' in sys.argv:
        args['not-headless'] = True

    if '--add-account' in sys.argv:
        args['add-account'] = True

    if '--config-file' in sys.argv:
        args['config_file'] = True
        if sys.argv[sys.argv.index("--config-file") + 1] != '':
            args['config_file_name'] = sys.argv[sys.argv.index(
                "--config-file") + 1]
    else:
        args['config_file'] = False

    if '--release-instance' in sys.argv:
        args['release_instance'] = True
        if sys.argv[sys.argv.index("--release-instance") + 1] != '':
            args['release_instance_name'] = sys.argv[sys.argv.index(
                "--release-instance") + 1]
    else:
        args['release_instance'] = False

    if '--reset-instance' in sys.argv:
        args['reset_instance'] = True
        if sys.argv[sys.argv.index("--reset-instance") + 1] != '':
            args['reset_instance_name'] = sys.argv[sys.argv.index(
                "--reset-instance") + 1]
    else:
        args['reset_instance'] = False

    return args


def add_account(number_of_accounts):
    # get username and password from user
    sn_dev_username = input("Enter username (SN Dev Portal Email):")
    # config["sn_dev_username"] = sn_dev_username
    sn_dev_password = getpass.getpass(
        "Enter password (SN Dev Portal Password):")

    nickname = input("Enter account nickname (default: PDI_{}):".format(
        number_of_accounts + 1))
    if nickname == "":
        nickname = "PDI_{}".format(number_of_accounts + 1)

    preferred_version = input(
        "Enter preferred version (default: 1 (latest version)):")
    if preferred_version == "":
        preferred_version = "1"

    # encrypt the password and write it in a file
    key = get_key()
    refKey = Fernet(key)
    # convert into byte
    mypwdbyt = bytes(sn_dev_password, 'utf-8')
    encrypted_password = refKey.encrypt(mypwdbyt)

    new_account = {
        nickname: {
            "sn_dev_username": sn_dev_username,
            "sn_dev_password": str(encrypted_password),
            "instance_name": "",
            "instance_password": "",
            "preferred_version": preferred_version,
            "instance_release": "",
            "instance_version": "",
            "last_checked": ""
        }
    }

    return new_account


def get_config(args):
    if args['config_file'] == True:
        config_file_name = args['config_file_name']
    else:
        config_file_name = "config.json"

    # check if config file is available
    if os.path.exists(config_file_name):
        print("config file found: {}".format(config_file_name))
        with open(config_file_name, "r") as config_file:
            config_file_content = config_file.read()
            if config_file_content != '':
                if "add-account" in args.keys():
                    config = json.loads(config_file_content)
                    new_account = add_account(number_of_accounts=0)
                    config[list(new_account.keys())[0]] = list(
                        new_account.values())[0]
                    # save into config file
                    with open(config_file_name, "w") as config_file:
                        config_file.write(json.dumps(config, indent=4))
                        config_file.close()

                config = json.loads(config_file_content)
                print("number of accounts found: {}".format(len(config.keys())))
            else:
                print("no accounts found, updating config file..")
                config = first_run(config_file_name)
    else:
        print("no config found, generating config file..")
        config = first_run()
    return config


def get_key():
    return bytes(dotenv_values('dec_key.bin')['key'], 'utf-8')


def generate_key():
    # generate key to encrypt password before saving local config file
    key = Fernet.generate_key()
    # save into new key file
    with open('dec_key.bin', "w") as key_file:
        key_file.write("key=" + key.decode("utf-8") + "\n")
        key_file.close()
    return key


def first_run(config_file_name):
    key = generate_key()

    new_account = add_account(number_of_accounts=0)

    # save into new config file
    with open(config_file_name, "w") as config_file:
        config_file.write(json.dumps(new_account, indent=4))
        config_file.close()

    # return list(new_account.keys())[0].split(":")[0]
    return new_account


def get_login_info(account):
    if '--env' in sys.argv:
        env = sys.argv[sys.argv.index('--env') + 1]
        config = dotenv_values(env)
        encpwdbyt = bytes(config['encrypted_password'], 'utf-8')
        refKeybyt = get_key()
        config["sn_dev_password"] = (
            Fernet(refKeybyt).decrypt(encpwdbyt)).decode("utf-8")

    # if  .env file exists
    elif len(dotenv_values()) > 0:
        env = ".env"
        config = dotenv_values()
        encpwdbyt = bytes(config['encrypted_password'], 'utf-8')
        refKeybyt = get_key()
        config["sn_dev_password"] = (
            Fernet(refKeybyt).decrypt(encpwdbyt)).decode("utf-8")

    elif len(dotenv_values()) == 0:
        config = {}
        # if a .env file does not exist, create one
    return config


def do_sign_in(config):
    # Sign-in to instance via headless chromium to wake up.
    sn_dev_username = config["sn_dev_username"]
    # get password and decrypt
    encpwdbyt = bytes(config['sn_dev_password'].replace(
        "b'", "").replace("'", ""), 'utf-8')
    refKeybyt = get_key()
    sn_dev_password = (
        Fernet(refKeybyt).decrypt(encpwdbyt)).decode("utf-8")

    instance_name = config["instance_name"] if "instance_name" in config else ""
    instance_release = config["instance_release"] if "instance_release" in config else ""
    # print("signing in to account: {} instance name: {} instance release: {}".format(
    print("account: {}".format(sn_dev_username))

    http = urllib3.PoolManager(
        cert_reqs="CERT_REQUIRED",
        ca_certs=certifi.where()
    )

    chrome_options = Options()
    if '--not-headless' not in sys.argv:
        chrome_options.add_argument("--headless")

    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--window-size=1400,800")

    chrome_options.add_experimental_option(
        "excludeSwitches", ["enable-logging"])
    chrome_options.add_experimental_option(
        "excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    # os.environ["WDM_SSL_VERIFY"] = "0"
    os.environ["WDM_LOG_LEVEL"] = "0"

    dev_portal_url = "https://developer.servicenow.com/dev.do#!/home"
    signon_url = "https://signon.service-now.com/ssologin.do?RelayState=%252Fapp%252Fservicenow_ud%252Fexks6phcbx6R8qjln0x7%252Fsso%252Fsaml%253FRelayState%253Dhttps%25253A%25252F%25252Fdeveloper.servicenow.com%25252Fnavpage.do&redirectUri=&email="

    driver = webdriver.Chrome(service=Service(
        ChromeDriverManager().install()), options=chrome_options)
    driver.get(signon_url)
    # Sign In
    print("signin in progress...")
    # username input box
    driver.find_element(By.ID, "username").click()
    driver.find_element(By.ID, "username").send_keys(sn_dev_username)
    # username submit button
    driver.find_element(By.ID, "usernameSubmitButton").click()
    WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable(driver.find_element(By.ID, "password"))
    )
    # password input box
    driver.find_element(By.ID, "password").click()
    driver.find_element(By.ID, "password").send_keys(sn_dev_password)
    # password submit button
    driver.find_element(By.ID, "submitButton").click()
    # wait to redirect to dev portal homepage
    try:
        WebDriverWait(driver, 30).until(
            EC.url_to_be(dev_portal_url)
        )
        print("signin success")
    except Exception as e:
        try:
            driver.find_element(By.ID, "errorPlaceholder")
            error_placeholder = driver.find_element(
                By.ID, "errorPlaceholder").text
            if error_placeholder == 'ⓘYour username or password is invalid. Please try again or reset your password. If on mobile, please reset from your desktop device.':
                error = "invalid password"
            if error_placeholder == 'ⓘYour account is locked due to a high number of unsuccessful login attempts in a short amount of time. Please wait 30 minutes before trying again.':
                error = "account locked"
            print("signin failed!")
            print(error)
        except Exception as errorPlaceholderException:
            if (str(errorPlaceholderException).find("Unable to locate element") > -1):
                print("Unable to locate error")
        return False

    # get active session headers to use  API calls
    try:
        # if fetch magic link request was made, get the headers from there
        magic = next(item for item in driver.requests if item.path ==
                     '/api/snc/fetch_magic_link_url')
        # Cleanup active browser,
        driver.quit()
    except:
        # TODO handle login failure
        print("signin failed!")
        return False

    return magic.headers


def instance_action(active_session_headers, instance_id, action):
    props_url = "https://developer.servicenow.com/api/snc/dev/props?sysparm_data=%7B%22action%22:%22all.properties%22,%22data%22:%7B%7D%7D"
    props_response = requests.request(
        "GET", props_url, headers=active_session_headers, data={})
    props = json.loads(props_response.text)['result']
    props_data = props['data']['system_properties']

    # instance_id = active_session_headers[]
    # instance_id = "21f29d5c1354374048523ac2e144b051"

    if action == 'reset_instance':
        reset_instance_cat_item = props_data['dev.cat_item.releaseInstance']
        reset_instance_url = "https://developer.servicenow.com/devportal.do?sysparm_data=%7B%22action%22:%22instance.ops.execute_cat_item%22,%22data%22:%7B%22ins_id%22:%22" + \
            instance_id + "%22,%22cat_item_id%22:%22" + \
            reset_instance_cat_item + "%22,%22additionalParams%22:%7B%7D%7D%7D"
        reset_instance_response = requests.request(
            "GET", reset_instance_url, headers=active_session_headers, data={})
        reset_instance_result = json.loads(reset_instance_response.text)
        if reset_instance_result['status'] == 'SUCCESS':
            print('instance reset complete')
            sample_info_reset = {
                "instanceInfo": {
                    "btn_extend_instance_tooltip": "{\r\n    \"enabled\": \"Resets the inactivity timer on your personal developer instance so that you have another {$1} days with your instance.\",\r\n    \"disabled\": \"Your instance is recovering from the last time you extended your instance; please give it some time to rest before you extend it again.\"\r\n}",
                    "canUpgrade": "no",
                    "catItem": {
                        "clientPollInterval": "",
                        "clientPollMaxNum": "",
                        "confirmMessage": "This will reset your instance to its out-of-the-box settings. You will also receive new instance login credentials after the reset is complete.",
                        "confirmViewName": "op_confirmation",
                        "display_image": "reset-and-reset-instance-icon.svg",
                        "exceedMaxPollMessage": "",
                        "inProgressMessage": "Instance reset in progress",
                        "is_active": True,
                        "markOffline": "True",
                        "name": "Reset and reset instance",
                        "needAlwaysOn": "False",
                        "needBlockOther": "True",
                        "needConfirmed": "True",
                        "needsPolling": "False",
                        "oldAppConfirmMessage": "This will reset your instance to its out-of-the-box settings, allowing you to start over fresh. Are you sure you want to reset your instance?",
                        "requestSubmittedMessage": "An instance reset request has been submitted and the instance may not be available temporarily. You will receive an email when the instance is back up",
                        "skipWakeUp": True,
                        "statusText": "Instance reset is in progress",
                        "sys_id": "0f4b8d152fd971003f8ea31c91a18916",
                        "tooltip_text": "We are resetting your instance to its baseline state. You will receive an email when the reset process completes."
                    },
                    "daysSinceExtended": 0,
                    "display_btn_extend_instance": True,
                    "forced_maintenance": False,
                    "full_release": "glide-tokyo-07-08-2022__patch1-09-01-2022_09-16-2022_1610",
                    "inactivityWarningSent": False,
                    "installedApps": {
                        "AES": "not installed"
                    },
                    "instanceStatus": {
                        "additional_info": {
                            "dashboard_show_exclamation": False,
                            "dashboard_show_spinner": True,
                            "start_building_disabled": True,
                            "start_building_subtext": "Instance reset is in progress",
                            "start_building_tooltip": "We are resetting your instance to its baseline state. You will receive an email when the reset process completes.",
                            "status_icon": "instanceFulfilling"
                        },
                        "display_state": "Reset and Wiping Instance",
                        "state": "Reset and reset instance"
                    },
                    "isQuickResetAndWipeInProgress": False,
                    "isUnderMaintenance": True,
                    "lastActivityHint": "This indicates last developer type activity on your instance.  For example, adding a table, field, or script include.",
                    "lastInfoUpdated": "12 Minutes ago",
                    "lastInfoUpdatedDate": 723442,
                    "name": "dev123916",
                    "opStatus": "Instance reset is in progress",
                    "release": "Tokyo",
                    "releaseName": "Tokyo Patch 1",
                    "remaingHoursOfMaintenenace": 0,
                    "remainingInactivityDays": 10,
                    "remainingInactivityDaysUnitStr": "days",
                    "shortDesc": "EMAIL DISABLED",
                    "state": "Offline",
                    "sys_id": "1a67429b1b114594702ec8ca234bcba1",
                    "tempPassword": "IH5%z4z/ilXD",
                    "timeToLastActivity": "less than 1 hour",
                    "underUnplannedMaintenance": False,
                    "url": "https://dev123916.service-now.com/",
                    "wakeupInProgress": False
                },
                "message": "Successfully retrieved instance information.",
                "status": "SUCCESS"
            }

    if action == 'release_instance':
        release_options = [
            "I am no longer using my instance",
            "I want a fresh instance with no data",
            "I'm not able to login to my instance",
            "My instance is not a waking from hibernation",
            "I'm having a different technical problem with my instance",
        ]
        release_reason = release_options[1].replace(" ", "+")

        release_instance_cat_item = props_data['dev.cat_item.releaseInstance']
        release_instance_url = 'https://developer.servicenow.com/devportal.do?sysparm_data=%7B%22action%22:%22instance.ops.execute_cat_item%22,%22data%22:%7B%22ins_id%22:%22' + \
            instance_id + '%22,%22cat_item_id%22:%22' + release_instance_cat_item + '%22,%22additionalParams%22:%7B%22selected%22:%22' + \
            release_reason + '%22,%22textBoxVal%22:%22%22%7D%7D%7D'
        # request_url        = "https://developer.servicenow.com/devportal.do?sysparm_data={"action":"instance.ops.execute_cat_item","data":{"ins_id":"" + instance_id + "","cat_item_id":"0df800f26f2ab10015241035eb3ee4f2","additionalParams":{"selected":"I+am+no+longer+using+my+instance","textBoxVal":""}}}"
        release_instance_response = requests.request(
            "GET", release_instance_url, headers=active_session_headers, data={})
        release_instance_result = json.loads(release_instance_response.text)
        if release_instance_result['status'] == 'SUCCESS':
            print('instance released')

    return True


def get_active_instance(active_session_headers):

    # check if there is an active instance

    # get magic link, check if instance still active
    magic_link_url = "https://developer.servicenow.com/api/snc/fetch_magic_link_url"
    magic_link_response = requests.request(
        "GET", magic_link_url, headers=active_session_headers, data={})
    magic_link = json.loads(magic_link_response.text)['result']
    active_instance = magic_link['url']
    # TODO handle return values
    # if active_instance == None:
    #     return None
    return active_instance


def get_instance_info(active_session_headers):
    # check instance info
    instance_info_url = "https://developer.servicenow.com/api/snc/v1/dev/instanceInfo?sysparm_data=%7B%22action%22:%22instance.ops.get_instance_info%22,%22data%22:%7B%22direct_wake_up%22:False%7D%7D"
    instance_info_response = requests.request(
        "GET", instance_info_url, headers=active_session_headers, data={})
    instance_info_raw = json.loads(instance_info_response.text)[
        'result']['instanceInfo']

    instance_info = {
        'instance_name': instance_info_raw['name'],
        'instance_password': instance_info_raw['tempPassword'],
        'instance_id': instance_info_raw['sys_id'],
        'instance_state': instance_info_raw['instanceStatus']['state'],
        'instance_release': instance_info_raw['release'],
        'instance_release_name': instance_info_raw['releaseName'],
        'remaining_inactivity_days': instance_info_raw['remainingInactivityDays'],
        'last_info_updated': instance_info_raw['lastInfoUpdated'],
        'time_to_last_activity': instance_info_raw['timeToLastActivity'],
    }
    print('instance name: {}'.format(
        instance_info['instance_name']))
    print('instance release: {}'.format(
        instance_info['instance_release']))
    print('instance release name: {}'.format(
        instance_info['instance_release_name']))

    print('instance state: {}'.format(
        instance_info['instance_state']))

    print('remaining inactivity days: {}'.format(
        instance_info['remaining_inactivity_days']))
    print('last info updated: {}'.format(
        instance_info['last_info_updated']))
    return instance_info


def check_instance_awake(active_session_headers):
    check_instance_awake_url = "https://developer.servicenow.com/api/snc/v1/dev/check_instance_awake"
    check_instance_awake_response = requests.request(
        "GET", check_instance_awake_url, headers=active_session_headers, data={})
    check_instance_awake = json.loads(
        check_instance_awake_response.text)['result']

    if check_instance_awake['isAwake'] == True:
        # do something when awake
        return 'isAwake'
    elif check_instance_awake['wakeupInProgress'] == True:
        # do something when wakeup
        return 'wakeupInProgress'
    elif check_instance_awake['isHibernating'] == True:
        # do something when isHibernating
        return 'isHibernating'

    # check_instance_awake_sample = {
    #     "status": "SUCCESS",
    #     "isAwake": True,
    #     "wakeupInProgress": False,
    #     "isHibernating": False
    # }

    # return check_instance_awake


def get_available_versions(active_session_headers):
    # get available versions
    versions_url = "https://developer.servicenow.com/api/snc/v1/dev/releaseInfo?sysparm_data=%7B%22action%22:%22release.versions%22,%22data%22:%7B%7D%7D"

    versions_response = requests.request(
        "GET", versions_url, headers=active_session_headers, data={})
    # TODO return default latest version?
    default_version = json.loads(versions_response.text)[
        'result']['data']['version_selector']['dev.defaultVersionSelected']

    available_versions = json.loads(versions_response.text)[
        'result']['data']['version_selector']['available_versions']
    return {
        'available_versions': available_versions,
        'default_version': default_version
    }


def request_new_instance(active_session_headers, version):
    # request a new instance
    request_instance_url = 'https://developer.servicenow.com/devportal.do?sysparm_data=%7B%22action%22:%22dashboard.instance_request%22,%22data%22:%7B%22family%22:%22' + version + '%22%7D%7D'
    request_instance_response = requests.request(
        "GET", request_instance_url, headers=active_session_headers, data={})
    request_instance = json.loads(request_instance_response.text)

    # request_instance_sample = {
    #     "assign_now": "yes",
    #     "is_version_preference_updated": False,
    #     "message": "Thank you for participating in the ServiceNow Developer Program.  Your request for an instance has been approved.",
    #     "req_id": "jkhfjhfdvbkjmbnbftyuyjhgkljlkgkjg",
    #     "req_status": "approved",
    #     "status": "SUCCESS"
    # }
    req_id = request_instance['req_id']
    # TODO handle other return status
    # if request_instance['req_status'] != 'approved':
    request_instance_status_result = request_instance_status(
        active_session_headers, req_id)
    return request_instance_status_result


def request_instance_status(active_session_headers, req_id):
    get_assign_req_status_url = "https://developer.servicenow.com/devportal.do?sysparm_data=%7B%22action%22:%22instance.ops.get_assign_req_status%22,%22data%22:%7B%22assign_req_id%22:%22'" + req_id + "'%22%7D%7D"
    get_assign_req_status_response = requests.request(
        "GET", get_assign_req_status_url, headers=active_session_headers, data={})
    assign_req_status = json.loads(get_assign_req_status_response.text)
    # TODO handle returns
    assign_req_status_sample = {
        "is_version_preference_updated": False,
        "message": None,
        "status": "approved"
    }
    new_instance_info = {
        "instance_status": "Online",
        "is_version_preference_updated": True,
        "loginURL": "https://dev123916.service-now.com/login.do?user_name=admin&sys_action=sysverb_login&user_password=IH5%25z4z%2FilXD",
        "message": "Instance successfully assigned to user.",
        "new_user_version": "Tokyo",
        "previous_user_version": "rome",
        "status": "complete_success",
        "temp_password": "IH5%z4z/ilXD"
    }

    return assign_req_status
    # return 'new_instance'


def update_env_instance(env, instance_info):
    # save into current .env file
    with open(env, "a") as dot_env_file:
        dot_env_file.write("instance_name=" +
                           instance_info['instance_name'] + "\n")
        dot_env_file.write("instance_release=" +
                           instance_info['instance_release'] + "\n")
        dot_env_file.close()


def use_ui(driver):
    # wait for header avatar to be available
    avatar_query = "return document.querySelector('dps-app').shadowRoot.querySelector('div').querySelector('header').querySelector('dps-navigation-header').shadowRoot.querySelector('header>div>div>ul>li>dps-login')"
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(driver.execute_script(avatar_query))
    )

    # click on header avatar
    driver.execute_script(avatar_query).click()

    time.sleep(5)

    # check if instance still there, if request_instance is present, then current instance was expired and reclaimed
    request_instance_query = "return document.querySelector('dps-app').shadowRoot.querySelector('div').querySelector('header').querySelector('dps-navigation-header').shadowRoot.querySelector('header>div').querySelectorAll('div.dps-navigation-header-utility>ul>li')"
    try:
        request_instance_elem = driver.execute_script(request_instance_query)
        # request new instance
        request_instance_elem[1].click()

    except:
        request_instance_elem = False

    # get instance status
    instance_status = ''

    while instance_status != 'Online':
        status_query = "return document.querySelector('dps-app').shadowRoot.querySelector('div').querySelector('header').querySelector('dps-navigation-header').shadowRoot.querySelector('header').querySelector('dps-navigation-header-dropdown').querySelector('dps-navigation-login-management').shadowRoot.querySelector('dps-navigation-header-dropdown-content').querySelector('dps-navigation-section').querySelector('dps-navigation-instance-management').shadowRoot.querySelector('dps-content-stack')"
        instance_status_raw = driver.execute_script(status_query)
        instance_status = instance_status_raw.text.split('\n')[1]

        if instance_status != 'Online':

            time.sleep(100)
    release_query = "return document.querySelector('dps-app').shadowRoot.querySelector('div').querySelector('header').querySelector('dps-navigation-header').shadowRoot.querySelector('header').querySelector('dps-navigation-header-dropdown').querySelector('dps-navigation-login-management').shadowRoot.querySelector('dps-navigation-header-dropdown-content').querySelectorAll('dps-navigation-section')[0]"
    instance_release = driver.execute_script(release_query).text.split(
        "\n")[driver.execute_script(release_query).text.split("\n").index("RELEASE") + 1]

    # get instance name (only available when instance is online)
    if instance_name == '':
        instance_name_query = "return document.querySelector('dps-app').shadowRoot.querySelector('div').querySelector('header').querySelector('dps-navigation-header').shadowRoot.querySelector('header').querySelector('dps-navigation-header-dropdown').querySelector('dps-navigation-login-management').shadowRoot.querySelector('dps-navigation-header-dropdown-content').querySelector('dps-navigation-section').querySelector('dps-navigation-instance-management').shadowRoot.querySelector('ul')"
        WebDriverWait(driver, 10).until(
            # we find the instance name by clicking on Manage Password item in the Dev portal header menu
            # which is the 6th element in that list
            EC.element_to_be_clickable(driver.execute_script(
                instance_name_query).find_element(By.XPATH, "li[6]"))
        )
        driver.execute_script(instance_name_query).find_element(
            By.XPATH, "li[6]").click()
        time.sleep(2)
        instance_name_result = driver.execute_script(
            "return document.querySelector('dps-app').shadowRoot.querySelector('div').querySelector('header').querySelector('dps-instance-modal').shadowRoot.querySelector('dps-modal')").text.split('\n')[20]
        instance_name = instance_name_result.split(': ')[1]

    datetimestamp = datetime.today().strftime(
        '%Y-%m-%d'), datetime.now().strftime("%H:%M:%S")

    print("{}: Instance name   : {}".format(datetimestamp, instance_name))
    print("{}: Instance release: {}".format(
        datetimestamp, instance_release))
    print("{}: Instance status : {}".format(
        datetimestamp, instance_status))

    # Cleanup active browser
    driver.quit()


def main():
    args = get_args()
    if args == False:
        exit(0)
    config = get_config(args)

    # ===== main loop through accounts =====
    for account in config:
        # login_info = get_login_info(config[account])
        print("config: {}".format(account))
        login_info = config[account]
        active_session_headers = do_sign_in(login_info)
        if active_session_headers:
            is_active_instance = get_active_instance(active_session_headers)

        else:
            logging.critical('login failed')
            continue

        if is_active_instance:
            instance_info = get_instance_info(active_session_headers)

            if args['release_instance'] and args['release_instance_name'] == account:
                instance_id = instance_info['instance_id']
                instance_action(active_session_headers,
                                instance_id, "release_instance")

            if args['reset_instance'] and args['reset_instance_name'] == account:
                instance_id = instance_info['instance_id']
                instance_action(active_session_headers,
                                instance_id, "reset_instance")
            instance_awake = check_instance_awake(active_session_headers)
            print('instance wake status: {}'.format(instance_awake))
        else:
            preferred_version = int(login_info['preferred_version']) - 1
            version = get_available_versions(active_session_headers)[
                'available_versions'][preferred_version]
            new_instance_result = request_new_instance(
                active_session_headers, version)


if __name__ == '__main__':
    main()
