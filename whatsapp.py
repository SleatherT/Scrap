import sys
import time
import logging

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common import TimeoutException, StaleElementReferenceException

from config import w_admin_number
import utils

#class whatsapp()

# Loops to check if an element has been dynamically loaded using the data that has changed
def check_element_changes(element, someAttributeName: str, timeout: int):
    # Returns True if a change has happened, False if it reached the timeout, a StaleElementReferenceException if encountered (could mean the page changed or the element got relocated)
    pollFrequency = 0.5
    numLoops = int(timeout/pollFrequency)
    dataToCompare = None
    
    dataChanged_flag = False
    for num in range(numLoops):
        try:
            dataCurrent = element.get_attribute(someAttributeName)
        except StaleElementReferenceException as e:
            return e
        
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
        
        qrcode = utils.wait_for_dydata(Web_Driver=browser, byLocator=By.CLASS_NAME, elementID='_akau', attributeName='data-ref', expectedType=str)
        
        utils.print_qr(qrcode)
        
        with open('misc/qrstring.txt', 'w') as file:
            file.write(qrcode)
        
        browser.save_screenshot('misc/screenshotQR.png')
        
        qrelement = browser.find_element(by=By.CLASS_NAME, value='_akau')
        confirmation = check_element_changes(qrelement, 'data-ref', timeout=60)
        
        if confirmation is True:
            continue
        elif confirmation is False:
            raise Exception(f'Reached check_element_changes timeout')
        elif confirmation is StaleElementReferenceException:
            
            


if __name__ == '__main__':
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
    
    # Checks if the log in was successful or not and waits for the new web app to load
    
    confirmation = log_in(timeout=120)
    
    #--------
    
    time.sleep(60)
    
    browser.save_screenshot('misc/screenshotLAST.png')
    
    #--------
    
    htmlDoc = browser.page_source
    
    soup = BeautifulSoup(htmlDoc, 'html.parser')
    
    with open('misc/sourcepage.txt', 'w') as file:
        file.write(soup.prettify())
    
    browser.quit()