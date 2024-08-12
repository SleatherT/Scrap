import os
from telethon import TelegramClient
import logging
import asyncio

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.WARNING
)

# I think is more secure to use enviroment variables for remote vm (not sure). In any case the format and commands to set this variables are:

# Linux: export VARIABLE=VALUE
# Windows: set VARIABLE=VALUE

# NOTE: Environment variables are considered strings

api_id = int(os.getenv('ID_TEL'))
api_hash = os.getenv('HASH_TEL')
client = TelegramClient("Main", api_id, api_hash)

async def sendfile():
    # To get the path the following commands can be used
    
    # Linux: pwd
    # Windows: cd
    
    # Alternatively the following variable can be used to just add the file name if the file is in the script folder
    script_directory = os.path.dirname(os.path.abspath(__file__))
    
    # NOTE: Linux and windows paths are differents the former uses '/' and the latter '\' and in Python '\' is a escape character so use it twice to denote it as a literal blackslash '\\'
    # Linux: f'{script_directory}/example.png'
    # Windows: f'{script_directory}\\example.png'
    
    filepath = f'{script_directory}/misc/screenshot.png'
    
    await client.send_file('me', filepath)
    
with client:
    client.loop.run_until_complete(sendfile())