from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

from pyvirtualdisplay import Display
import os
import time
import schedule
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# display = Display(visible=0, size=(800, 600))
# display.start()

instances = [
    {
        "username": "aabdelhafez@paypal.com",
        "pass": "Efta7YaDev66^",
    },
    {
        "username": "tbmdemo@protonmail.com",
        "pass": "Efta7YaSn66^",
    },
]

wakeuptime = '08:00'

# Signin to instance via headless chromium to wake up.
def wake(username, passwerd):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    # chrome_options.add_argument('--silent')
    

    # chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    os.environ['WDM_SSL_VERIFY'] = '0'
    os.environ['WDM_LOG_LEVEL'] = '0'

    driver = webdriver.Chrome(service = Service(ChromeDriverManager().install()))
    
    instance = "https://signon.service-now.com/ssologin.do?RelayState=%252Fapp%252Fservicenow_ud%252Fexks6phcbx6R8qjln0x7%252Fsso%252Fsaml%253FRelayState%253Dhttps%25253A%25252F%25252Fdeveloper.servicenow.com%25252Fnavpage.do&redirectUri=&email="
    print("Signing in User:".format(instance))
    print(username.format(instance))
    
    driver.get(instance)

    # Collect HTML Elements we'll be using
    name_input = driver.find_element(By.ID, "username")
    name_submit = driver.find_element(By.ID, "usernameSubmitButton")
    pass_input = driver.find_element(By.ID, "password")
    login_button = driver.find_element(By.ID, "submitButton")

    # Sign In
    name_input.click()
    time.sleep(1)
    name_input.send_keys(username)
    # print("Filled in Username".format(instance))
    time.sleep(2)
    name_submit.click()
    # print("Clicked Username Submit Button".format(instance))
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(pass_input)
    )

    pass_input.click()
    time.sleep(1)
    pass_input.send_keys(passwerd)
    # print("Filled in Pass".format(instance))

    time.sleep(2)
    login_button.click()
    # print("Clicked Login Button".format(instance))
    # print("waiting to redirect to dev portal".format(instance))
    WebDriverWait(driver, 30).until(
        EC.url_to_be('https://developer.servicenow.com/dev.do#!/home')
    )
    time.sleep(2)
    # find the acount avatar
    avatar_query = "return document.querySelector('dps-app').shadowRoot.querySelector('div').querySelector('header').querySelector('dps-navigation-header').shadowRoot.querySelector('header>div>div>ul>li>dps-login')"
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(driver.execute_script(avatar_query))
    )
    driver.execute_script(avatar_query).click()
    time.sleep(2)

    status_query = "return document.querySelector('dps-app').shadowRoot.querySelector('div').querySelector('header').querySelector('dps-navigation-header').shadowRoot.querySelector('header').querySelector('dps-navigation-header-dropdown').querySelector('dps-navigation-login-management').shadowRoot.querySelector('dps-navigation-header-dropdown-content').querySelector('dps-navigation-section').querySelector('dps-navigation-instance-management').shadowRoot.querySelector('dps-content-stack')"
    instance_status = driver.execute_script(status_query).text
    print(instance_status.format(instance))

    # Save Img of signin proof.
    # driver.get_screenshot_as_file("capture.png")
    print("Done, cleaning up.".format(instance))
    
    # Cleanup active browser.
    driver.quit()
    # display.stop()
# 

# Loop through instances to wake.
def sunsup():
    for inst in instances:
        wake(inst["username"], inst["pass"])


# # Set Schedule for continuous waking.
# schedule.every().day.at(wakeuptime).do(sunsup)
# while True:
#     schedule.run_pending()
#     time.sleep(1)

sunsup()
