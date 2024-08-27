from config import w_admin_number
from utils.print_qr import print_qr

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common import TimeoutException, StaleElementReferenceException

import time
import sys

By = webdriver.common.by.By

#--------

options = webdriver.EdgeOptions()

options.add_argument('--headless=new')

options.add_argument('User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3')

#--------

browser = webdriver.Edge(options=options)

browser.get('https://web.whatsapp.com')

#--------

browser.implicitly_wait(30)

#--------

qrdiv = browser.find_element(by=By.CLASS_NAME, value='_aj-b')

browser.execute_script('arguments[0].scrollIntoView(true);', qrdiv)

#-------

# Defaulted to aprox 10 seconds in waiting to load the data
def wait_for_dydata(Web_Driver, byLocator, elementID: str, attributeName: str, expectedType, numLoops=20, pollFrequency=0.5):
    
    for loop in range(numLoops):
        attributeData = Web_Driver.find_element(by=byLocator, value=elementID).get_attribute(attributeName)
        
        if type(attributeData) is expectedType:
            return attributeData
        else:
            time.sleep(pollFrequency)
            continue
    
    raise Exception(f'Expected type attribute failed, type: {type(attributeData)}, expected type: {expectedType}')
    
#-------

# Loops to check if an element has been dynamically loaded using the data that has changed
def check_element_changes(element, someAttributeName: str, timeout: int):
    # Returns True if a change has happened, False if it reached the timeout
    pollFrequency = 0.5
    numLoops = int(timeout/pollFrequency)
    dataToCompare = None
    
    dataChanged_flag = False
    for num in range(numLoops):
        dataCurrent = element.get_attribute(someAttributeName)
        
        if dataToCompare is None:
            dataToCompare = dataCurrent
        
        if dataToCompare == dataCurrent:
            time.sleep(pollFrequency)
            continue
        else:
            dataChanged_flag = True
            break
    
    if dataChanged_flag is True:
        return True
    else:
        return False

#--------

# Checks if the qr has changed and printed again if it happened
def log_in(timeout: int):
    startTime = time.time()
    
    while True:
        timePassed = int(time.time() - startTime)
        
        if timePassed > timeout:
            return False
        
        qrcode = wait_for_dydata(Web_Driver=browser, byLocator=By.CLASS_NAME, elementID='_akau', attributeName='data-ref', expectedType=str)
        
        print_qr(qrcode)
        
        with open('misc/qrstring.txt', 'w') as file:
            file.write(qrcode)
        
        browser.save_screenshot('misc/sceenshotQR.png')
        
        qrelement = browser.find_element(by=By.CLASS_NAME, value='_akau')
        confirmation = check_element_changes(qrelement, 'data-ref', timeout=60)
        
        if confirmation:
            continue
        else:
            raise Exception(f'Reached check_element_changes timeout')

# Checks if the log in was successful or not and waits for the new web app to load

confirmation = log_in(timeout=120)

#--------

time.sleep(60)

browser.save_screenshot('misc/sceenshotLAST.png')

#--------

htmlDoc = browser.page_source

soup = BeautifulSoup(htmlDoc, 'html.parser')

with open('misc/sourcepage.txt', 'w') as file:
    file.write(soup.prettify())

browser.quit()
