# This is the main script, its rol its to be the 'main' entry point to the rest of the code, giving to the user from any of the active API's access 
# to the functions the code has to offer

# Built-in modules
import sys
import os
import re
import asyncio
import logging
import logging.config
import threading

# Telegram
from telethon import TelegramClient, events

# Config variables
import config

'''
Before writing the code i will asume some things are true, so if in the future it is show that they aren't, then the code must be changed
    
*I assume that when using a thread pool, context switching can be avoided with Locks
*I assume that primitive locks can be used safetly to block between asynchronous and synchronous threads
*I assume that Events have this same capabilities -'All threads waiting for it to become true are awakened'

*With the previous assumptions I conclude that locking the access to the cpu using locks and letting only one thread run a heavy cpu-bound task improves performance

Also, I wanted to override the threading.excephook as the docs say to control how uncaught exceptions are raised in threads, so I can log it, but I dont have the 
knowledge to do it, what should I be carefull about? what are the consequences of doing it?.

A note about how threads are treated, since in most systems when the main thread exits other threads ´´are killed without executing try … finally clauses 
or executing object destructors´´ the ideal way to finish executing the script is always signaling the main thread to do it not killing it, either with a 
KeyboardInterrupt in Windows/Linux, or calling SIGTERM (kill command) on Linux only one time, and then the main thread signals the other threads to do it 
so they can exit properly
'''

class Telegram_Api():
    logger = logging.getLogger(__name__)
    
    _tel_api_id = os.getenv('ID_TEL')
    _tel_api_hash = os.getenv('HASH_TEL')
    
    secrets_available = False
    if not _tel_api_id or not _tel_api_hash:
        logger.info('Telegram Api data not provided, telegram client will not start and cross-plataform commands will not work')
    else:
        try:
            _tel_api_id = int(_tel_api_id)
        except ValueError:
            raise ValueError('Telegram Api ID is not a number')
        
        secrets_available = True
    
    # Only the messages that start with '!' are valid commands, its possible to change it by only modifying this regex
    valid_command_match = re.compile(r'!\w*').match
    
    # TODO: Since i havent read the documentation about process yet ProcessEvent does nothing right now
    def __init__(self, *, ThreadEvent=None, ProcessEvent=None):
        
        assert ProcessEvent is None, 'ProcessEvent is not implemented right now'
        
        if not isinstance(ThreadEvent, threading.Event):
            raise TypeError('ThreadEvent argument passed to Telegram_Api is not an instance of threading.Event')
            
        self.THREAD_EVENT = ThreadEvent
        self.PROCESS_EVENT = ProcessEvent
        
    def start(self):
        asyncio.run(self.start_telegram)
    
    async def start_telegram(self):
        # // Login/Starting
        
        t_client = TelegramClient("Main", self._tel_api_id, self._tel_api_hash)
        t_client.start()
        
        # // Adding the handler and pattern to the NewMessage event
        
        # Using the id of the administrator chat from the config file
        telAdminEntity = await t_client.get_input_entity(config.t_admin_user)
        telAdminId = telAdminEntity.user_id
        
        self.t_client.add_event_handler(self.process_command, events.NewMessage(chats=telAdminId, pattern=self.check_for_command))
        
        # // Adding a task to periodically check if the thread/process should continue running or should exit
        
        loop = asyncio.get_event_loop()
        loop.create_task(self.confirm_execution())
        
        # // If ThreadEvent was passed, it signals that has finished starting
        
        if self.THREAD_EVENT:
            self.THREAD_EVENT.set()
        
        # // Starting to listen updates
        self.t_client.run_until_disconnected()
        
        # The Event was set before actually listening, because (from what i understand) run_until_disconnected will not execute any code below this,
        # but is this what should the code do? there is not an 'ideal' way? I am missing something?
        
        # Delete after testing
        print('\n\PRINT: tel_listen_messages executed code below run_until_disconnected()\n\n')
        
    def check_for_command(self, string):
        match = self.valid_command_match(string)
        
        self.logger.debug(f'match variable in check_for_command() is: {match}')
        if match is None:
            return False
        
        command = match.group()[1:]
        if command not in self.tel_commands:
            return False
        
        return match
    
    async def process_command(self.event):
        fullString = event.pattern_match.string
        command = event.pattern_match.group()[1:]
        
        
        
        
    
    async def confirm_execution(self):
        while True:
            await asyncio.sleep(30)
            
            if self.THREAD_EVENT.is_set():
                continue
            else:
                break
        
        sys.exit()
    
    async def forward_screenshot(self):
        # Is this the correct way to do it?
        filePath = os.path.abspath('misc/screenshots/WAscreenshot.png')
        
        await self.t_client.send_file(self.telAdminEntity, filePath)
    
    # Saving the telegram codes in dict with their coro
    tel_commands = {'fwscreenshot': forward_screenshot}
    


# TODO: Since i will first deploy this code in a cloud vm with one core, a thread pool will be used, in the future a process pool should be implemented
# for multicore machines along with only one core receiving requests (asynchronous) and the rest executing that (probably cpu-bound) requests 
# NOTE: This one core code implementation should stop receiving new petitions if previouly received a heavy task, however if its show that the context switching to 
# the selenium thread reduce performance executing light tasks it should always lock the threads when receiving/processing a petition
class Apis():
    logger = logging.getLogger(__name__)
    
    # NOTE: First it should start the API's and their threads, one at a time
    def __init__(self):
        if self.startTelegram:
            self.mainEvent = threading.Event()
            self.controlThreadList = list()
            
            # Creating and appending the threads
            self.telegramEvent = threading.Event()
            self.telegramThread = threading.Thread(target=telegram_thread, name='Telegram')
            self.controlThreadList.append(self.telegramThread)
            
            self.start_control_thread()
            # Waiting for the telegram client to start listening
            self.mainEvent.wait()
            
    # This function starts a thread for each api thread with the only objective to signal when a this api thread has stopped
    def start_control_thread(self):
        for apiThread in self.controlThreadList:
            threading.Thread(target=apiThread.start)
            thread.start()
            self.mainEvent.wait()
        
    
    def ask_if_alive(self):
        self.threadFlags = dict()
        for thread in self.controlThreadList:
            self.threadFlags[thread.is_alive()] = thread.name
    
    def close_threads(self):
        pass
    
    




if __name__ == '__main__':
    logging.config.fileConfig('logging.conf')
    Apis()
    