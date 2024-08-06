import os
from bs4 import BeautifulSoup
from selenium import webdriver

# Get the directory path of the current script
script_directory = os.path.dirname(os.path.abspath(__file__))

edgePath = f"{script_directory}\\msedgedriver.exe"

service = webdriver.EdgeService(executable_path=edgePath)

#--------

options = webdriver.EdgeOptions()

options.add_argument('--headless=new')

#--------

browser = webdriver.Edge(service=service, options=options)

browser.get('https://google.com')

#--------

htmlDoc = browser.page_source

soup = BeautifulSoup(htmlDoc, 'html.parser')

with open('SourcePage.txt', 'w') as file:
    file.write(soup.prettify())
    