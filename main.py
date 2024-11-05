# This is the main script, its rol its to be the 'main' entry point to the rest of the code, giving to the user from any of the active API's access 
# to the functions the code has to offer

# Built-in modules
import sys
import os
import signal
import re
import asyncio
import logging
import logging.config
import threading
import concurrent.futures
from functools import partial

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

logging.config.fileConfig('logging.conf')

def get_logger():
    # INFO: Using the default name given to the main thread
    if threading.current_thread().name != 'MainThread':
        logger = logging.getLogger(f'__main__.{threading.current_thread().name}')
    else:
        logger = logging.getLogger(__name__)
        
    return logger

class Telegram_Api():
    logger = get_logger()
    
    _tel_api_id = os.getenv('ID_TEL')
    _tel_api_hash = os.getenv('HASH_TEL')
    
    secrets_available = False
    if not _tel_api_id or not _tel_api_hash:
        logger.info('Telegram Api data not provided, telegram client will not start and cross-platform commands will not work')
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
        self.logger = get_logger()
        asyncio.run(self.start_telegram())
    
    async def start_telegram(self):
        # // Login/Starting
        
        self.t_client = TelegramClient("Main", self._tel_api_id, self._tel_api_hash)
        await self.t_client.start()
        
        # // Adding the handler and pattern to the NewMessage event
        
        # Using the id of the administrator chat from the config file
        telAdminEntity = await self.t_client.get_input_entity(config.t_admin_user)
        telAdminId = telAdminEntity.user_id
        
        self.t_client.add_event_handler(self.process_command, events.NewMessage(chats=telAdminId, pattern=self.check_for_command))
        
        # // Adding a task to periodically check if the thread/process should continue running or should exit
        
        loop = asyncio.get_event_loop()
        loop.create_task(self.confirm_execution())
        
        # // If ThreadEvent was passed, it signals that has finished starting
        
        if self.THREAD_EVENT:
            self.THREAD_EVENT.set()
        
        # // Starting to listen updates
        await self.t_client.run_until_disconnected()
        
    def check_for_command(self, string):
        match = self.valid_command_match(string)
        
        self.logger.debug(f'match variable in check_for_command() is: {match}')
        if match is None:
            return False
        
        command = match.group()[1:]
        if command not in self.tel_commands:
            return False
        
        return match
    
    async def process_command(self, event):
        fullString = event.pattern_match.string
        command = event.pattern_match.group()[1:]
        self.logger.debug(f'Executing command: {command}')
    
    async def confirm_execution(self):
        while True:
            await asyncio.sleep(30)
            self.logger.debug('About to confirm execution')
            
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
class Control_Thread():
    keepAliveEvents = dict()
    
    telegram_event = threading.Event()
    keepAliveEvents['telegram'] = telegram_event
    
    whatsapp_event = threading.Event()
    keepAliveEvents['whatsapp'] = whatsapp_event
    
    # INFO: Setting to True the events, they are allowed to run, this is only to made the code intuitive
    for event in keepAliveEvents.values():
        event.set()
    
    def __init__(self, start_telegram=False, start_whatsapp=False, 
                 exit_if_telegram_ends=True, 
                 exit_if_whatsapp_ends=True):
        
        self.start_telegram = start_telegram
        self.start_whatsapp = start_whatsapp
        
        self.exit_if_telegram_ends = exit_if_telegram_ends
        self.exit_if_whatsapp_ends = exit_if_whatsapp_ends
    
    
    def start_control_thread(self, handler):
        self.logger = get_logger()
        try:
            self.start_threads()
        except Exception as e:
            self.logger.exception('Exception found when running start_threads, calling handler to exit started threads')
            handler()
    
    def start_threads(self):
        telegramThreadName = 'telegram'
        threads = list()
        
        # NOTE: First it should start the API's and their threads, one at a time
        if self.start_telegram and Telegram_Api.secrets_available:
            telegram_event = self.keepAliveEvents['telegram']
            telegram_api = Telegram_Api(ThreadEvent=telegram_event)
            telegram_thread = threading.Thread(target=telegram_api.start, name=telegramThreadName)
            
            telegram_thread.start()
            
            logger.debug('About to call telegram_event.wait')
            telegram_event.wait()
            logger.debug('Finished telegram_event.wait')
            
            threads.append(telegram_thread)
        
        if self.start_whatsapp:
            pass
        
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=(len(threads) + 1))
        
        thread_futures = dict()
        for thread in threads:
            # INFO: Submiting to the executor
            thread_futures[self.executor.submit(thread.join)] = thread.name
        
        while True:
            thread_name = None
            for future in concurrent.futures.as_completed(thread_futures):
                thread_name = thread_futures[future]
                self.logger.debug('thread_name var: %s', thread_name)
                break
            
            if not thread_name:
                break
            
            if self.exit_if_telegram_ends and thread_name == 'telegram':
                break
            
            if self.exit_if_whatsapp_ends and thread_name == 'whatsapp':
                break
            
            del thread_futures[future]
            
            if len(thread_futures) == 0:
                break
        
        for event in self.keepAliveEvents.values():
            self.logger.debug('About to call event.clear')
            event.clear()
        
        self.logger.debug('About to call executor.shutdown')
        
        self.executor.shutdown()
        
    
def signal_handler(signum=None, frame=None, *, control_thread_obj):
    logger = get_logger()
    
    if signum is None and frame is None:
        logger.info('Calling signal_handler manually')
    else:
        logger.info(f'Received signal, signum: {signum}')
    
    if hasattr(control_thread_obj, 'keepAliveEvents'):
        logger.debug('Confirmed that control_thread has keepAliveEvents attribute')
        for event in control_thread_obj.keepAliveEvents.values():
            event.clear()
    
    if hasattr(control_thread_obj, 'executor'):
        logger.debug('Confirmed that control_thread has executor attribute' )
        logger.info('About to call executor.shutdown')
        control_thread_obj.executor.shutdown()
        logger.info('Finished shutting down executor')
    
    logger.info('Finishing up signal_handler func')
    


if __name__ == '__main__':
    logger = get_logger()
    control_thread_obj = Control_Thread(start_telegram=True)
    
    handler = partial(signal_handler, control_thread_obj=control_thread_obj)
    
    signal.signal(2, handler)
    signal.signal(15, handler)
    
    control_thread = threading.Thread(target=control_thread_obj.start_control_thread, args=[handler], name='Control_Thread')
    
    control_thread.start()
    
    # FIX: An awfull, terrible, painfull, abominable, constrained but even worse, bloated code, I didn't found another way of keeping 
    # the main thread active to be able to receive signals without looping on windows, on linux, macOS and other os, locks can receive 
    # POSIX signals so it will be added in the near future
    if sys.platform in ['win32', 'linux', 'darwin']:
        logger.debug('Starting loop to receive signals')
        while True:
            # INFO: A timeout of 5 seconds, if a signal was sent it will take a max of those seconds to call the handler
            control_thread.join(timeout=5.0)
            
            if not control_thread.is_alive():
                break
            logger.debug('Looped')
        logger.info('Finishing up main thread, signals will not be processed after this point')
        
    else:
        logger.critical('OS doesnt have a way to keep the main thread alive, add a personalized way or use the win32 method')
        handler()