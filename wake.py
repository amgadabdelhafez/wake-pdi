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
# import schedule

# display = Display(visible=0, size=(800, 600))
# display.start()

chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")


# driver= webdriver.Chrome()
# driver = webdriver.Chrome(ChromeDriverManager().install())
os.environ['WDM_SSL_VERIFY'] = '0'
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
# driver = webdriver.Chrome("/home/gitpod/.wdm/drivers/chromedriver/linux64/98.0.4758.80/chromedriver")

# driver = webdriver.Chrome(executable_path='/home/gitpod/.wdm/drivers/chromedriver/linux64/98.0.4758.80/chromedriver')


instances = [
    {
        # "instance": "https://signon.service-now.com/ssologin.do",
        # "instance": "https://dev113938.service-now.com/",
        "instance": "https://signon.service-now.com/ssologin.do?RelayState=%252Fapp%252Fservicenow_ud%252Fexks6phcbx6R8qjln0x7%252Fsso%252Fsaml%253FRelayState%253Dhttps%25253A%25252F%25252Fdeveloper.servicenow.com%25252Fnavpage.do&redirectUri=&email=",
        "username": "tbmdemo@protonmail.com",
        "pass": "Efta7YaSn66^",
        # "username": "aabdelhafez@paypal.com",
        # "pass": "Efta7YaDev66^",
    },
]

wakeuptime = '07:00'

# Signin to instance via headless chromium to wake up.
def wake(instance, username, passwerd):
    print("URL ".format(instance))
    print(instance.format(instance))

    driver.get(instance)

    # Collect HTML Elements we'll be using
    name_input = driver.find_element(By.ID, "username")
    name_submit = driver.find_element(By.ID, "usernameSubmitButton")
    pass_input = driver.find_element(By.ID, "password")
    login_button = driver.find_element(By.ID, "submitButton")

    
    # Sign In
    name_input.click()
    name_input.send_keys(username)
    print("Filled in Username".format(instance))
    time.sleep(3)
    name_submit.click()
    print("Clicked Username Submit Button".format(instance))
    print("waiting for element_to_be_clickable(pass_input)".format(instance))
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(pass_input)
    )

    # t.until(ExpectedConditions.visibilityOf(element));  
    # t.until(ExpectedConditions.elementToBeClickable(element));

    # time.sleep(5)  
    pass_input.click()
    pass_input.send_keys(passwerd)
    print("Filled in Pass".format(instance))
    time.sleep(3)
    login_button.click()
    print("Clicked Login Button".format(instance))
    print("waiting 10 seconds to redirect to https://developer.servicenow.com/dev.do#!/home".format(instance))

    WebDriverWait(driver, 10).until(
        EC.url_to_be('https://developer.servicenow.com/dev.do#!/home')
    )
    q = "return document.querySelector('dps-app').shadowRoot.querySelector('div').querySelector('header').querySelector('dps-navigation-header').shadowRoot.querySelector('header').querySelector('dps-navigation-header-dropdown').querySelector('dps-navigation-login-management').shadowRoot.querySelector('dps-navigation-header-dropdown-content').querySelector('dps-navigation-section').querySelector('dps-navigation-instance-management').shadowRoot.querySelector('dps-content-stack')"
    instance_status = driver.execute_script(q).text
    print("instance_status".format(instance))
    print(instance_status.format(instance))

    # instance_avatar = driver.find_element(By.XPATH, "/html/body/dps-app//div/header/dps-navigation-header//header/div/div[2]/ul/li[2]/dps-login//div/button/div")
#   /html/body/dps-app//div/header/dps-navigation-header//header/div/div[2]/ul/li[2]/dps-login//div/button
    # instance_avatar.click()
    # /html/body/dps-app//div/header/dps-navigation-header//header/div/div[2]/ul/li[2]/dps-login//div/button/div
    # instance_status = driver.find_element(By.XPATH, "/html/body/dps-app//div/header/dps-navigation-header//header/dps-navigation-header-dropdown/dps-navigation-login-management//dps-navigation-header-dropdown-content/dps-navigation-section[1]/dps-navigation-instance-management//div/div[1]/dps-content-stack[1]/p")

    # Save Img of signin proof.
    driver.get_screenshot_as_file("capture.png")
    print("Done, cleaning up.".format(instance))
    # Cleanup active browser.
    driver.quit()
    display.stop()
# 

# Loop through instances to wake.
def sunsup():
    for inst in instances:
        wake(inst["instance"], inst["username"], inst["pass"])


# # Set Schedule for continuous waking.
# schedule.every().day.at(wakeuptime).do(sunsup)
# while True:
#     schedule.run_pending()
#     time.sleep(1)

sunsup()
