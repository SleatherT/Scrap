from bs4 import BeautifulSoup
from selenium import webdriver

options = webdriver.EdgeOptions()

options.add_argument('--headless=new')

options.add_argument('User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3')

#--------

browser = webdriver.Edge(options=options)

browser.get('https://google.com')

#--------

browser.save_screenshot('misc/screenshot.png')

#--------

htmlDoc = browser.page_source

soup = BeautifulSoup(htmlDoc, 'html.parser')

with open('misc/sourcepage.txt', 'w') as file:
    file.write(soup.prettify())

browser.quit()