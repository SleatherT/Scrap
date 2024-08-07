from bs4 import BeautifulSoup
from selenium import webdriver

options = webdriver.EdgeOptions()

options.add_argument('--headless=new')

#--------

browser = webdriver.Edge(options=options)

browser.get('https://google.com')

#--------

htmlDoc = browser.page_source

soup = BeautifulSoup(htmlDoc, 'html.parser')

with open('SourcePage.txt', 'w') as file:
    file.write(soup.prettify())

browser.quit()