from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
import time

By = webdriver.common.by.By

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

wait = WebDriverWait(browser, timeout=10, poll_frequency=0.5)

wait.until(lambda browser : type(browser.find_element(by=By.CLASS_NAME, value='_akau').get_attribute('data-ref')) is str )

qrelement = browser.find_element(by=By.CLASS_NAME, value='_akau')

qrcode = qrelement.get_attribute('data-ref')

with open('misc/qrstring.txt', 'w') as file:
    file.write(qrcode)

#--------

browser.save_screenshot('misc/screenshot.png')

#--------

htmlDoc = browser.page_source

soup = BeautifulSoup(htmlDoc, 'html.parser')

with open('misc/sourcepage.txt', 'w') as file:
    file.write(soup.prettify())

browser.quit()