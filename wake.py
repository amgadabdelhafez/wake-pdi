import sys
import os
import time
import getpass
import schedule
import urllib3
from datetime import datetime
from dotenv import dotenv_values
from collections import OrderedDict
from pyvirtualdisplay import Display
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from cryptography.fernet import Fernet


# Command line parametes:
# --env arg          override .env and use the passed argument as .env file
# --silent           don't print logs
# --not-headless     run headfull
# --daily arg        run daily and use arg as waketime

# if --env flag used it overrides default .env
if '--env' in sys.argv:
    env = sys.argv[sys.argv.index('--env') + 1]
    config = dotenv_values(env)
elif len(dotenv_values()) > 0:
# if a .env file exists
    config = dotenv_values()
    encpwdbyt = bytes(config['encrypted_password'], 'utf-8')
    refKeybyt = bytes(config['key'], 'utf-8')
    keytouse = Fernet(refKeybyt)
    config["sn_dev_password"] = (Fernet(refKeybyt).decrypt(encpwdbyt)).decode("utf-8") 

elif len(dotenv_values()) == 0:
    # if a .env file does not exist, create one
    env = ".env"
    # get username and password from user
    sn_dev_username = input("Please Enter Username (SN Dev Portal Email):") 
    sn_dev_password = getpass.getpass("Please Enter Password (SN Dev Portal Password):") 

    # generate key to encrypt passord
    key = Fernet.generate_key()

    # encrypt the password and write it in a file
    refKey = Fernet(key)
    # convert into byte
    mypwdbyt = bytes(sn_dev_password, 'utf-8')
    encrypted_password = refKey.encrypt(mypwdbyt)
 
    # save into new .env file
    with open(env, "w") as dot_env_file:
        dot_env_file.write("sn_dev_username=" + sn_dev_username + "\n")
        dot_env_file.write("encrypted_password=" + encrypted_password.decode("utf-8")  + "\n")
        dot_env_file.write("key=" + key.decode("utf-8") + "\n")
        dot_env_file.close()

    config = dotenv_values()
    config["sn_dev_password"] = sn_dev_password

silent = '--silent' in sys.argv

if not silent:
    print(datetime.today().strftime("%Y-%m-%d"), datetime.now().strftime("%H:%M:%S"), "SN Dev username:", config["sn_dev_username"])

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# display = Display(visible=0, size=(1400, 800))
# display.start()

# Signin to instance via headless chromium to wake up.
def wake(config):
    sn_dev_username = config["sn_dev_username"]
    sn_dev_password = config["sn_dev_password"]
    if "instance_name" in config:
        instance_name = config["instance_name"]
    else:
        instance_name = ''
    
    chrome_options = Options()
    if '--not-headless' not in sys.argv:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-extensions")                                                                                                                                  
    chrome_options.add_argument("--start-maximized")                                                                                                                                  
    chrome_options.add_argument("--window-size=1400,800")                                                                                                                                  

    chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    os.environ["WDM_SSL_VERIFY"] = "0"
    os.environ["WDM_LOG_LEVEL"] = "0"

    dev_portal_url = "https://developer.servicenow.com/dev.do#!/home"
    signon_url = "https://signon.service-now.com/ssologin.do?RelayState=%252Fapp%252Fservicenow_ud%252Fexks6phcbx6R8qjln0x7%252Fsso%252Fsaml%253FRelayState%253Dhttps%25253A%25252F%25252Fdeveloper.servicenow.com%25252Fnavpage.do&redirectUri=&email="
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.get(signon_url)
    # Sign In
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
    WebDriverWait(driver, 10).until(
        EC.url_to_be(dev_portal_url)
    )
    # wait for header avatar to be available 
    avatar_query = "return document.querySelector('dps-app').shadowRoot.querySelector('div').querySelector('header').querySelector('dps-navigation-header').shadowRoot.querySelector('header>div>div>ul>li>dps-login')"
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(driver.execute_script(avatar_query))
    )
    # click on header avatar
    driver.execute_script(avatar_query).click()
    time.sleep(5)
    # get instance status
    instance_status = ''
    while instance_status != 'Online':
        status_query = "return document.querySelector('dps-app').shadowRoot.querySelector('div').querySelector('header').querySelector('dps-navigation-header').shadowRoot.querySelector('header').querySelector('dps-navigation-header-dropdown').querySelector('dps-navigation-login-management').shadowRoot.querySelector('dps-navigation-header-dropdown-content').querySelector('dps-navigation-section').querySelector('dps-navigation-instance-management').shadowRoot.querySelector('dps-content-stack')"
        instance_status = driver.execute_script(status_query).text.split('\n')[1]
        if instance_status != 'Online':
            time.sleep(60)
        if not silent:
            print(datetime.today().strftime('%Y-%m-%d'), datetime.now().strftime("%H:%M:%S"), "Instance status:", instance_status)

    # get instance name (only available when instance is online)
    if instance_name == '':
        instance_name_query = "return document.querySelector('dps-app').shadowRoot.querySelector('div').querySelector('header').querySelector('dps-navigation-header').shadowRoot.querySelector('header').querySelector('dps-navigation-header-dropdown').querySelector('dps-navigation-login-management').shadowRoot.querySelector('dps-navigation-header-dropdown-content').querySelector('dps-navigation-section').querySelector('dps-navigation-instance-management').shadowRoot.querySelector('ul')"
        WebDriverWait(driver, 10).until(
            # we find the instance name by clicking on Manage Password item in the Dev portal header menu
            # which is the 6th element in that list
            EC.element_to_be_clickable(driver.execute_script(instance_name_query).find_element(By.XPATH, "li[6]"))
        )
        driver.execute_script(instance_name_query).find_element(By.XPATH, "li[6]").click()
        time.sleep(2)
        instance_name = driver.execute_script("return document.querySelector('dps-app').shadowRoot.querySelector('div').querySelector('header').querySelector('dps-instance-modal').shadowRoot.querySelector('dps-modal')").text.split('\n')[20]
        # save into current .env file
        with open(env, "a") as dot_env_file:
            dot_env_file.write("instance_name=" + instance_name.split(': ')[1] + "\n")
            dot_env_file.close()
    if not silent:
        print(datetime.today().strftime('%Y-%m-%d'), datetime.now().strftime("%H:%M:%S"), "Instance name  :", instance_name)

    # Save Img of signin proof.
    # driver.get_screenshot_as_file("capture.png")
    # print(datetime.today().strftime('%Y-%m-%d'), datetime.now().strftime("%H:%M:%S"), "Done, cleaning up.")
    
    # Cleanup active browser.
    driver.quit()

def sunsup():
    wake(config)

# Set Schedule for continuous waking.
if '--daily' in sys.argv:
    wakeuptime = sys.argv[sys.argv.index('--daily') + 1]
    schedule.every().day.at(wakeuptime).do(sunsup)
    while True:
        schedule.run_pending()
        time.sleep(1)
sunsup()
