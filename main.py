# This is the main script, its rol its to be the 'main' entry point to the rest of the code, giving to the user from any of the active API's access 
# to the functions the code has to offer

# Built-in modules
import sys
import ast
import os
import signal
import hashlib
import re
import time
import asyncio
import logging
import logging.config
import threading
import concurrent.futures
from functools import partial

# Telegram
import telethon

# 
import config
import utils

'''
Before writing the code i will asume some things are true, so if in the future it is show that they aren't, then the code must be changed
    
*I assume that when using a thread pool, context switching can be avoided with Locks
*I assume that primitive locks can be used safetly to block between asynchronous and synchronous threads
*I assume that Events have this same capabilities -'All threads waiting for it to become true are awakened'

*With the previous assumptions I conclude that locking the access to the cpu using locks and letting only one thread run a heavy cpu-bound task improves performance

Notes

I wanted to override the threading.excephook as the docs say to control how uncaught exceptions are raised in threads, so I can log it, but I dont have the 
knowledge to do it, what should I be carefull about? what are the consequences of doing it?.

A note about how threads are treated, since in most systems when the main thread exits other threads ´´are killed without executing try … finally clauses 
or executing object destructors´´ the ideal way to finish executing the script is always signaling the main thread to do it not killing it, either with a 
KeyboardInterrupt in Windows/Linux, or calling SIGTERM (kill command) on Linux only one time, and then the main thread signals the other threads to do it 
so they can exit properly

In howto-logging-cookbook, page 11, its recommended to use a different approach when logging in async code, to avoid blocking the event loop, `` it should 
be noted that when logging from async code, network and even file handlers could lead to problems `` this seems serious so it should be implemented

When using ffmpeg, I tried to implement a way to raise an error when the command is waiting for input, but i couldn't found a way of achive this, so its
absolute necessary to avoid this, and if it happens, a timeout is raised using the last output sent to stderr (ffmpeg logs stream) to check if there is 
no activity, which it can mean that the process is waiting input but there is a lot of reasons why there is no new logs apart from waiting for input so 
its not an ideal method

'''

global_lock = threadLock = threading.Lock()

logging.config.fileConfig('logging.conf')

def get_logger():
    # INFO: Using the default name given to the main thread
    if threading.current_thread().name != 'MainThread':
        logger = logging.getLogger(f'__main__.{threading.current_thread().name}')
    else:
        logger = logging.getLogger(__name__)
        
    return logger


class Telegram_Api():
    class countdown_dict(dict, utils.countdown):
        pass
    
    tel_condition_lock = threading.Condition()
    
    last_logged_thread = 0
    
    # Only the messages that start with '!' are valid commands, its possible to change it by only modifying this regex
    valid_command_match = re.compile(r'!\w*').match
    
    arg_searcher = re.compile(r'\S+').search
    arg_finditer = re.compile(r'\S+').finditer
    
    findall_arg = re.compile(r'\S+').findall
    findall_opt_arg = re.compile(r'-\S+').findall
    
    search_media_format = re.compile(r'\S*[.]\S+').search
    
    
    # TODO: Since i havent read the documentation about process yet ProcessEvent does nothing right now
    def __init__(self, *, ThreadEvent=None, ProcessEvent=None, id_secret_env_name, hash_secret_env_name, thread_log_in_order):
        
        assert ProcessEvent is None, 'ProcessEvent is not implemented right now'
        
        if not isinstance(ThreadEvent, threading.Event):
            raise TypeError('ThreadEvent argument passed to Telegram_Api is not an instance of threading.Event')
            
        self.THREAD_EVENT = ThreadEvent
        self.PROCESS_EVENT = ProcessEvent
        
        self.id_secret_env_name = id_secret_env_name
        self.hash_secret_env_name = hash_secret_env_name
        self.thread_log_in_order = thread_log_in_order
        
        self.user_tasks = dict()
        
        self.rpcFlooded = self.countdown_dict(status=False, wait_time=None)
        self.last_time_forwarded = time.time()
        self.forward_wait_time = 1
        self.forward_info = {'amount_fw_after_time_update': 0}
    
    
    def get_secrets(self):
        ''' This function retrieves the API credentials and generates a unique name for the database based on them. 
        
        By default, after the initial login, Telegram sessions allow access without requiring the same credentials again,
        since the session file stores the authorization key. This means that anyone with access to the session file 
        can use the account, regardless of the original credentials used to create it.
        
        To enforce a one-to-one mapping between credentials and session files, this function hashes the API credentials 
        to create a unique session filename. This approach does not enhance security but ensures that each Telegram 
        account (or API credential pair) corresponds to a distinct session file, preventing the need to manually delete 
        previous session files when switching accounts.
        
        Credentials issue source: https://github.com/LonamiWebs/Telethon/issues/1569
        
        '''
        logger = get_logger()
        self._tel_api_id = os.getenv(self.id_secret_env_name)
        self._tel_api_hash = os.getenv(self.hash_secret_env_name)
        
        if not self._tel_api_id or not self._tel_api_hash:
            logger.info('Telegram Api data not provided, telegram client will not start and cross-platform commands will not work')
        else:
            try:
                self._tel_api_id = int(self._tel_api_id)
            except ValueError:
                raise ValueError('Telegram Api ID is not a number')
        
        self.database_name = hashlib.sha256(f"{self._tel_api_id}{self._tel_api_hash}{os.getenv('password')}".encode('utf-8')).hexdigest()
    
    
    def start(self):
        self.logger = get_logger()
        
        asyncio.run(self.start_telegram())
    
    
    async def start_telegram(self):
        # // Adding a task to periodically check if the thread/process should continue running or should exit
        
        loop = asyncio.get_event_loop()
        loop.create_task(self.confirm_execution())
        
        try:
            self.get_secrets()
            await self.connect_to_telegram()
        except Exception as e:
            self.logger.exception('Exception when trying to start telegram')
            
            return None
        
        # // Starting to listen updates
        
        await self.t_client.run_until_disconnected()
    
    
    async def connect_to_telegram(self):
        # // Login/Starting
        
        self.t_client = telethon.TelegramClient(f"databases/{self.database_name}", self._tel_api_id, self._tel_api_hash)
        
        # Blocking threads until its his turn to log in
        with self.tel_condition_lock:
            self.logger.debug(f'Entered condition block num: {self.thread_log_in_order}, self.last_logged_thread: {self.last_logged_thread}, self.thread_log_in_order: {self.thread_log_in_order}')
            
            self.tel_condition_lock.wait_for(lambda: self.last_logged_thread + 1 == self.thread_log_in_order)
            
            self.logger.info(f'About to log in with the entered credentials number {self.thread_log_in_order}')
            
            # Removing the console handler to avoid filling it with outputs while waiting for input
            utils.handlers_controler.remove_handler_by_type(logging.StreamHandler)
            
            await self.t_client.start()
            
            # Restoring console handler
            utils.handlers_controler.restore_removed_handlers()
        
            # MUST ADD or it will deadlock the other telegram threads waiting for log in
            type(self).last_logged_thread += 1
            
            self.logger.debug(f'Finishing condition block {self.thread_log_in_order}')
            
            self.tel_condition_lock.notify()
        
        # // Adding the handler and pattern to the NewMessage event
        
        # Using the id of the administrator chat from the config file
        self.telAdminEntity = await self.t_client.get_input_entity(config.t_admin_user)
        self.telAdminId = self.telAdminEntity.user_id
        
        self.t_client.add_event_handler(self.process_command, telethon.events.NewMessage(chats=self.telAdminId, pattern=self.check_for_command))
        
    
    def check_for_command(self, string):
        match = self.valid_command_match(string)
        
        self.logger.debug(f'Match variable in check_for_command() is: {match}')
        if match is None:
            return False
        
        command = match.group()[1:] # [1:] removes the '!'
        
        if command not in self.tel_commands:
            return False
        
        return match
    
    
    async def process_command(self, event):
        fullString = event.pattern_match.string
        command = event.pattern_match.group()[1:] # [1:] removes the '!'
        self.logger.debug(f'Executing command: {command}')
        
        func = self.tel_commands[command]
        
        #global_lock.acquire()
        try:
            function = func(self, event)
            self.user_tasks[f'{event.text} | {event.id}'] = function
            await function
        except AssertionError as e:
            self.logger.exception(f'Catched AssertionError')
            await event.reply(str(e))
        except asyncio.CancelledError as e:
            self.logger.exception('Task cancelled')
            await event.reply('Task cancelled')
        except Exception as e:
            self.logger.exception(f'Catched Unhandled Error')
            await event.reply(str(e))
        finally:
            #global_lock.release()
            self.logger.debug(f'Deleting key from user_tasks: {event.text} / var: {self.user_tasks}')
            del self.user_tasks[f'{event.text} | {event.id}']
    
    
    async def confirm_execution(self):
        while True:
            await asyncio.sleep(30)
            self.logger.debug(f'About to confirm execution. Value: {self.THREAD_EVENT.is_set()}')
            
            if self.THREAD_EVENT.is_set():
                continue
            else:
                break
        
        sys.exit()
    
    
    async def send_runtime_log(self, event):
        path_log = os.path.abspath('runtime.log')
        
        assert os.path.exists(path_log) is True, 'No logs has been created'
        
        await self.t_client.send_file(self.telAdminEntity, path_log)
    
    
    async def forward_screenshot(self, event):
        # Is this the correct way to do it?
        filePath = os.path.abspath('misc/screenshots/WAscreenshot.png')
        
        await self.t_client.send_file(self.telAdminEntity, filePath)
    
    
    async def last_id_entities_interacted(self, event):
        ''' Forwards the last ids of the user, channels or groups where the user sent a message
        
        Usage: !get_last_ids <-dialogs:int> <-messages:int>
        
        dialogs its the amount of recent chats to check, defauts to 30. messages indicates the same, it will check those
        recent messages in the chat, defaults to 100
        
        '''
        
        user_args_opt = self.findall_opt_arg(event.text)
        
        dialogs_limit = 30
        messages_limit = 100
        for opt in user_args_opt:
            if opt.startswith('-dialogs:'):
                dialogs_limit = self.assert_num(opt.removeprefix('-dialogs:'))
            elif opt.startswith('-messages:'):
                messages_limit = self.assert_num(opt.removeprefix('-messages:'))
        
        interacted_chats = list()
        async for dialog in self.t_client.iter_dialogs(dialogs_limit):
            async for message in self.t_client.iter_messages(dialog.entity, messages_limit):
                if message.sender_id == self.telAdminId:
                    interacted_chats.append(dialog.id)
                    break
        
        await self.t_client.send_message(self.telAdminEntity, f'Last entities interacted: {interacted_chats}')
    
    
    async def get_tasks(self, event):
        '''Returns the keys of the self.user_tasks variable
        
        Usage: !get_tasks
        
        '''
        await event.reply(str(self.user_tasks.keys()))
        await event.reply(str(self.t_client.list_event_handlers()))
    
    
    async def cancel_user_task(self, event):
        ''' Cancel the selected task
        
        Usage: !cancel_task <name of the task>
        
        '''
        user_args = self.findall_arg(event.text)
        
        assert len(user_args) >= 2, 'Not enough arguments passed'
        
        index_handler = None
        try:
            index_handler = int(user_args[1])
        except ValueError:
            pass
        
        if type(index_handler) is int:
            pair = self.t_client.list_event_handlers()[index_handler]
            self.t_client.remove_event_handler(pair[0])
            self.logger.debug(f'Cancelling callback: {pair}')
            await event.reply(f'Cancelling callback: {pair}')
        else:
            # Broken, coroutines dont have cancel method
            assert event.text[13:] in self.user_tasks, 'Task name not valid'
            function = self.user_tasks[event.text[13:]]
            function.cancel()
    
    
    async def scale(self, event):
        ''' Scales a video to a lower resolution or the same if its desired to re-encode it slower to (maybe) reduce the file size and an 
        optional argument to select the video streams
        
        Usage: !scale <resolution> select_streams
        
        Resolution: It must be one of the general used resolutions 1080p, 720p, 480p, 360p... e.g., !scale 360p
        
        select_streams: If passed, a message will be sent with the streams of the video to be selected, it must be replied to continue the
        command
        
        '''
        valid_resolutions =['480p', '360p']
        
        allowed_mime_types = ['video/x-matroska', 'video/mp4']
        
        user_args = self.arg_finditer(event.text)
        user_args.__next__()
        
        user_args_itered = iter([match.group() for match in user_args])
        
        resolution = None
        
        for arg in user_args_itered:
            pass
        
        self.media_converter(event=event, cmd='', mime_types_allowed=allowed_mime_types)
        
        
    async def media_converter(self, event, *, cmd=None, mime_types_allowed=None):
        ''' A very low-level user command, is used basically by all the commands that work with multimedia, like scale or convert
        
        Usage: !media_converter -map a:1 -map s c:a -copy -c:s mov_text -codec:v libx264 -preset slower -x264opts level=31 -filter_complex 
        [0:v]scale=640:480[out] -map [out] filename.mkv .mp4 ... 
        The output name, more specifically, the format output is used as the end of the the command, if not found AssertionError is raised
        If output name only indicates the desired target format and not the name of the output file, e.g. '.mp4' then the same
        name of the input file is used but adding 'converted' at the end of the file
        
        '''
        
        message, file = await self.check_file(event)
        
        self.logger.debug(f'Mime type passed: {file.mime_type} {file.title}')
        if mime_types_allowed is not None:
            assert file.mime_type in mime_types_allowed, 'mime_type not allowed'
        
        if not cmd:
            cmd = event.text
        
        user_args = self.arg_finditer(cmd)
        user_args.__next__() # The first argument / command is not used, is implied that this will always be true
        
        user_args_itered = iter([match.group() for match in user_args])
        
        self.logger.debug(f'user_args_itered var: {user_args_itered}')
        
        target_format = None
        ffmpeg_maps = list()
        ffmpeg_dict = dict()
        for arg in user_args_itered:
            if self.search_media_format(arg):
                target_format = arg
                break
            elif arg == '-map':
                stream_i = user_args_itered.__next__()
                ffmpeg_maps.append(stream_i)
            elif arg.startswith('-'):
                key = arg.removeprefix('-')
                value = user_args_itered.__next__()
                ffmpeg_dict[key] = value
        
        assert target_format is not None, 'Not target format specified'
        
        filepath = await self.download_file(message)
        
        if target_format.startswith('.'):
            extracted_name = os.path.basename(filepath).split('.')[0]
            target_format = f'{extracted_name} converted{target_format}'
        
        return_code, processed_filepath = utils.call_ffmpeg(Filepath=filepath, maps=ffmpeg_maps, kwargs=ffmpeg_dict, target_format=target_format)
        
        assert return_code == 0, f'Error executing ffmpeg: code = {return_code}'
        
        assert os.path.exists(processed_filepath) is True, 'Error executing ffmpeg command: The file container was not created'
        
        await self.t_client.send_file(self.telAdminEntity, processed_filepath)
    
    
    async def forward_to_chat(self, event):
        ''' Fowards messages from a chat/channel to another selected chat. The self-bot/client must be in the chat to forward
        
        Usage: !fw_chat <'link source chat'> <'link target chat'> / optional <-min_id:'NUMBER'> / opt <-keep_alive> / opt <-kwargs:'STRING'>
                optional <-fw_only:'message property'> e.g. -fw_only:file
        
        min_id is the id of the message in the chat from where starts to forward, its not ideal but its a patch until find a
        way to dinamically adjust the wait between forwards to avoid the flood error
        
        If keep_alive is passed, new messages will be forwarded
        
        If kwargs passed must be a string in the form of a python dict to be evaluated by ast.literal_eval
        
        '''
        user_args = self.findall_arg(event.text)
        
        assert len(user_args) >= 3, 'Not enough arguments passed'
        
        try:
            source_chat = self.assert_num(user_args[1])
        except AssertionError:
            source_chat = user_args[1]
        
        try:
            target_chat = self.assert_num(user_args[2])
        except AssertionError:
            target_chat = user_args[2]
        
        min_id = 1
        keep_alive = False
        fw_only = None
        kwargs = dict()
        
        source_entity = await self.t_client.get_entity(source_chat)
        target_entity = await self.t_client.get_entity(target_chat)
        
        user_args_opt = self.findall_opt_arg(event.text)
        
        for optional in user_args_opt:
            if optional.startswith('-fw_only:'):
                fw_only = optional.removeprefix('-fw_only:')
            elif optional.startswith('-min_id:'):
                min_id = optional.removeprefix('-min_id:')
                min_id = self.assert_num(min_id, var_name='min_id')
            elif optional.startswith('-keep_alive'):
                keep_alive = True
            elif optional.startswith('-kwargs:'):
                kwargs = ast.literal_eval(optional.removeprefix('-kwargs:'))
                assert type(kwargs) is dict, 'kwargs is not a dictionary'
        
        await event.reply(f'Chats successfully obtained. keep_alive: {keep_alive}, fw_only: {fw_only}, min_id: {min_id}')
        
        async for message in self.t_client.iter_messages(source_entity, reverse=True, min_id=min_id, **kwargs):
            # A variable to be used only by the logger
            debug_name = source_entity.id if type(source_entity) == telethon.tl.types.User else source_entity.title
            
            self.logger.debug(f'Last id obtained: {message.id} / {debug_name}')
            
            if type(message) is telethon.tl.patched.MessageService:
                continue
            
            if fw_only is not None:
                if not getattr(message, fw_only, None):
                    continue
            
            try:
                func = self.t_client.forward_messages
                await self.forward_controled(func, target_entity, message)
            except telethon.errors.rpcerrorlist.MessageIdInvalidError as e:
                self.logger.exception(f'Message that caused error MessageIdInvalidError: {message}')
                
            self.logger.debug(f'Last id forwarded: {message.id} / {debug_name}')
            
            self.forward_info[debug_name] = message.id
        
        await event.reply(f'Finished forwarding, last message id forwarded: {message.id}')
        
        if keep_alive is False:
            return None
        
        @self.t_client.on(telethon.events.NewMessage(chats=source_entity))
        async def handler(event):
            debug_name = source_entity.id if type(source_entity) == telethon.tl.types.User else source_entity.title
            
            if fw_only is not None:
                if not getattr(event, fw_only, None):
                    return None
            
            func = event.forward_to
            await self.forward_controled(func, target_entity)
            
            self.logger.debug(f'Last id forwarded: {event.id} / {debug_name}')
            self.forward_info[debug_name] = event.id
    
    
    async def permanent_forward(self, event):
        ''' Fowards new messages from a chat/channel to another selected chat. The self-bot/client must be in the chat to forward
        
        Usage: !fw_new_messages <'source chat link'> <'target chat link'> / optional <-fw_only:'message property'> e.g. -fw_only:file
        
        If -fw_only is passed those properties will be checked in the message and if they are they will be forwarded
        
        '''
        user_args = self.findall_arg(event.text)
        
        assert len(user_args) >= 3, 'Not enough arguments passed'
        
        source_chat = user_args[1]
        target_chat = user_args[2]
        
        source_entity = await self.t_client.get_entity(source_chat)
        target_entity = await self.t_client.get_entity(target_chat)
        
        user_args_opt = self.findall_opt_arg(event.text)
        
        fw_only = None
        
        for optional in user_args_opt:
            if optional.startswith('-fw_only:'):
                fw_only = optional.removeprefix('-fw_only:')
        
        await event.reply(f'Chats successfully obtained')
        
        @self.t_client.on(telethon.events.NewMessage(chats=source_entity))
        async def handler(event):
            debug_name = source_entity.id if type(source_entity) == telethon.tl.types.User else source_entity.title
            
            if fw_only is not None:
                if not getattr(event, fw_only, None):
                    return None
            
            func = event.forward_to
            await self.forward_controled(func, target_entity)
            
            self.logger.debug(f'Last id forwarded: {event.id} / {debug_name}')
            self.forward_info[debug_name] = event.id
        
    
    async def get_forward_info(self, event):
        ''' Returns the forward_info variable
        
        Usage: !fw_info
        
        '''
        await event.reply(f'{self.forward_info.items()}, Wait time: {self.forward_wait_time}')
    
    
    async def update_forward_time(self, event):
        ''' Updates forward_wait_time variable
        
        Usage: !fw_update_time <number>
        
        '''
        user_args = self.findall_arg(event.text)
        
        assert len(user_args) >= 2, 'Not enough arguments passed'
        
        new_time = self.assert_num(user_args[1], var_name='New time', num_class=float)
        
        self.forward_wait_time = new_time
    
    # ------ No user functions
    
    async def forward_controled(self, func, *args, **kwargs):
        '''Controls the time the forward requests are sent, if an exception is catched, is re-raised
        
        Usage: 
            ´´
            forward_function = event.forward_to
            await forward_controled(forward_function, entity)
            
            # or
            
            forward_function = self.t_client.forward_messages
            await forward_controled(forward_function, target_entity, message)
            ´´
        
        Issues: Requests catched by ´if self.rpcFlooded['status'] is True:´ after finishing sleep execute arbitrary so order is lost
        
        '''
        try:
            actual_time = time.time()
            
            if self.last_time_forwarded <= actual_time:
                self.last_time_forwarded = actual_time + self.forward_wait_time
            elif self.last_time_forwarded > actual_time:
                self.last_time_forwarded += self.forward_wait_time
            
            self.logger.debug(f'Time calculated of sleep: {self.last_time_forwarded - actual_time}')
            
            await asyncio.sleep(self.last_time_forwarded - actual_time)
            
            await func(*args, **kwargs)
            
            self.forward_info['amount_fw_after_time_update'] += 1
            
            if self.forward_info['amount_fw_after_time_update'] >= 1000:
                self.forward_wait_time -= 0.1
                self.forward_info['amount_fw_after_time_update'] = 0
        
        except telethon.errors.rpcerrorlist.FloodWaitError as e:
            
            if self.rpcFlooded['status'] is True:
                time_to_sleep = self.rpcFlooded.get_time_left()
                self.logger.debug(f'Time to sleep got from rpcFlooded: {time_to_sleep}')
                await asyncio.sleep(time_to_sleep)
                
                # Recursive!!
                await self.forward_controled(func, *args, **kwargs)
                
                return None
            
            # The first function to execute the following should be also the only one to update the rpcFlooded status to false 
            # after the wait_time passed, implying this function is not thread-safe
            
            letters = self.findall_arg(str(e))
            wait_sleep = None
            
            for letter in letters:
                try:
                    wait_sleep = int(letter) + 3
                except ValueError:
                    pass
            
            if wait_sleep is None:
                raise e
            
            self.logger.debug(f'Catching FloodWaitError and containing it, rpc message: {str(e)}, wait_sleep: {wait_sleep}')
            await self.t_client.send_message(self.telAdminEntity, f'FloodWaitError caused by Forward, time to sleep: {wait_sleep}')
            
            self.rpcFlooded['status'] = True
            self.rpcFlooded.start_countdown(wait_sleep)
            
            # 
            self.forward_wait_time += 0.4
            
            await asyncio.sleep(wait_sleep)
            
            self.rpcFlooded['status'] = False
            
            # Recursive!! This shouldn't cause errors or unexpected behavior, I hope
            await self.forward_controled(func, *args, **kwargs)
        
        except Exception:
            raise
        
    
    async def check_file(self, event):
        '''Checks if there is a file in the message or replied message, and returns this message and the file or raises and error if there 
        is no file
        
        '''
        message = event.message
        file = event.file
        
        if file is None:
            message = await event.get_reply_message()
            assert message is not None, 'No file in the message and no replied message'
            file = message.file
        
        assert file is not None, 'Message does not contain file'
        
        return message, file
    
    
    async def download_file(self, message, *, path='misc/', defaultname=None):
        '''Returns the path where the file was downloaded
        
        The message argument must be a telethon message object. The path must be a string where the file in the script directory will be downloaded, 
        since os.path.abspath() is used, directory separators can be '/' independently of the executing os, defaults to misc/ if not passed
        If the file has a name, it will be used, if not, defaultname is used instead, if no defaultname was set then a unique name using the time this
        function was called will be used as name
        
        '''
        file = message.file
        filename = file.name if file.name is not None else defaultname
        if filename is None:
            filename = f'File_{time.monotonic_ns()}'
        
        path = os.path.abspath(f'{path}{filename}')
        
        # Copied from the docs
        def callback(current, total):
            self.logger.info(f'Downloaded {current} out of {total} {"bytes: {:.2%}".format(current / total)}')
        
        returned_path = await message.download_media(path, progress_callback=callback)
        
        self.logger.debug(f'Downloaded file; path passed: {path}, path returned: {returned_path}')
        
        return returned_path
        
    
    def assert_num(self, string, *, var_name='Argument', num_class=int):
        ''' Return a integer if the string is a number, if not raises AssertionError with the name of the var that wasn't possible to convert
        
        '''
        try:
            i = num_class(string)
        except ValueError:
            raise AssertionError(f'{var_name} is not a number')
        
        return i
    
    
    # Saving the telegram codes in a dict with their coro
    tel_commands = {'fwscreenshot': forward_screenshot, 'media_converter': media_converter, 'scale': scale, 'runtime_log': send_runtime_log,
                    'fw_chat': forward_to_chat, 'get_tasks':get_tasks, 'cancel_task': cancel_user_task, 'fw_new_messages': permanent_forward,
                    'fw_info': get_forward_info, 'fw_update_time': update_forward_time, 'get_last_ids': last_id_entities_interacted
    }
    


# TODO: Since i will first deploy this code in a cloud vm with one core, a thread pool will be used, in the future a process pool should be implemented
# for multicore machines along with only one core receiving requests (asynchronous) and the rest executing that (probably cpu-bound) requests 
# NOTE: This one core code implementation should stop receiving new petitions if previouly received a heavy task, however if its show that the context switching to 
# the selenium thread reduce performance executing light tasks it should always lock the threads when receiving/processing a petition
class Control_Thread():
    keepAliveEvents = dict()
    
    telegramDefaultThreadName = 'telegram'
    whatsappDefaultThreadName = 'whatsapp'
    
    telegram_env_secret_default_name_ID = 'ID_TEL'
    telegram_env_secret_default_name_HASH = 'HASH_TEL'
    
    
    def __init__(self, start_telegram=False, start_whatsapp=False, min_of_telegram_clients=1, min_of_whatsapp_clients=1,
                 quantity_of_telegram_clients=1, quantity_of_whatsapp_clients=1):
        ''' If set to false the start of an api, the other arguments related are not used, they are overridden to 0.
        
        Minimum of clients arguments (e.g. min_of_whatsapp_clients) specify the minimum amount of threads/clients of that 
        app that must be active, if not, all threads are exited and the program ends.
        
        Quantity of clients (e.g. quantity_of_telegram_clients) specify the amount of apis of an app the control thread must
        created, since enviromental variables are used at the momment for telegram, the telegram_env_secret_default_name_ID
        is used for the first thread/client and for the next client it will use the same name but adding '_' and the number
        so it would end up looking like this 'ID_TEL_2', that is the example of how the enviromental variable should be set
        for the second telegram client
        
        '''
        self.start_telegram = start_telegram
        self.start_whatsapp = start_whatsapp
        
        self.min_of_telegram_clients = min_of_telegram_clients if start_telegram else 0
        self.quantity_of_telegram_clients = quantity_of_telegram_clients if start_telegram else 0
        
        self.min_of_whatsapp_clients = min_of_whatsapp_clients if start_whatsapp else 0
        self.quantity_of_whatsapp_clients = quantity_of_whatsapp_clients if start_whatsapp else 0
    
    
    def start_control_thread(self, handler):
        self.logger = get_logger()
        try:
            self.start_threads()
        except Exception as e:
            self.logger.exception('Exception found when running start_threads, calling handler to exit started threads')
            handler()
    
    
    def start_threads(self):
        threads = list()
        
        # NOTE: Threads are started, if they failed to start by any cause, the control thread will continue executing the 
        # other threads or terminate them depending of the aguments passed at the creation of the control thread
        if self.start_telegram:
            for n in range(1, self.quantity_of_telegram_clients + 1):
                if n > 1:
                    telegramThreadName = f'{self.telegramDefaultThreadName}_{n}'
                    telegram_env_secret_name_ID = f'{self.telegram_env_secret_default_name_ID}_{n}'
                    telegram_env_secret_name_HASH = f'{self.telegram_env_secret_default_name_HASH}_{n}'
                else:
                    telegramThreadName = self.telegramDefaultThreadName
                    telegram_env_secret_name_ID = self.telegram_env_secret_default_name_ID
                    telegram_env_secret_name_HASH = self.telegram_env_secret_default_name_HASH
                
                telegram_event = threading.Event()
                
                # Setting to True the Events = They are allowed to run
                telegram_event.set()
                
                
                self.keepAliveEvents[telegramThreadName] = telegram_event
                telegram_api = Telegram_Api(ThreadEvent=telegram_event, id_secret_env_name=telegram_env_secret_name_ID,
                                            hash_secret_env_name=telegram_env_secret_name_HASH, thread_log_in_order=n)
                
                telegram_thread = threading.Thread(target=telegram_api.start, name=telegramThreadName)
                
                telegram_thread.start()
                
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
            
            del thread_futures[future]
            
            active_clients = self.check_clients_active(thread_futures.values())
            
            if active_clients[self.telegramDefaultThreadName] < self.min_of_telegram_clients:
                break
            
            if active_clients[self.whatsappDefaultThreadName] < self.min_of_whatsapp_clients:
                break
            
            if len(thread_futures) == 0:
                break
        
        for event in self.keepAliveEvents.values():
            self.logger.debug('About to call event.clear')
            event.clear()
        
        self.logger.debug('About to call executor.shutdown')
        
        self.executor.shutdown()
        
    def check_clients_active(self, threads_list):
        clients_dict = dict()
        clients_dict[self.telegramDefaultThreadName] = 0
        clients_dict[self.whatsappDefaultThreadName] = 0
        
        for thread_name in threads_list:
            if thread_name.startswith(self.telegramDefaultThreadName):
                clients_dict[self.telegramDefaultThreadName] = clients_dict[self.telegramDefaultThreadName] + 1
            elif thread_name.startswith(self.whatsappDefaultThreadName):
                clients_dict[self.whatsappDefaultThreadName] = clients_dict[self.whatsappDefaultThreadName] + 1
        
        self.logger.info(f'clients_dict var: {clients_dict}')
        
        return clients_dict

def signal_handler(signum=None, frame=None, *, control_thread_obj):
    logger = get_logger()
    
    if signum is None and frame is None:
        logger.info('Calling signal_handler manually')
    else:
        logger.info(f'Received signal, signum: {signum}')
    
    if hasattr(control_thread_obj, 'keepAliveEvents'):
        logger.debug(f'Confirmed that control_thread has keepAliveEvents attribute of length: {len(control_thread_obj.keepAliveEvents)}')
        for event in control_thread_obj.keepAliveEvents.values():
            event.clear()
    
    if hasattr(control_thread_obj, 'executor'):
        logger.info('About to call executor.shutdown')
        control_thread_obj.executor.shutdown()
        logger.info('Finished shutting down executor')
    
    logger.info('Finishing up signal_handler func')
    


if __name__ == '__main__':
    # Storing the main thread references in a local data so it doesnt spread to other threads (added because I found that I may call 
    # logger instead self.logger and nothing would alert me)
    MainThreadVars = threading.local()
    
    MainThreadVars.logger = get_logger()
    
    # // Notifying that a 'password' enviroment variable is going to be used to enhance the security of hashed strings like
    # the name for the telegram session files
    if os.getenv('password'):
        MainThreadVars.logger.warning('''Using a "password" enviroment variable to enhance session filenames. If you haven't set this variable for this, stop the script and change it''')
        time.sleep(5)
    else:
        MainThreadVars.logger.critical('Not found "password" enviroment variable, to enhance session filenames please add it before log into accounts')
        if config.ask_for_password:
            sys.exit()
    
    MainThreadVars.control_thread_obj = Control_Thread(start_telegram=True, 
        quantity_of_telegram_clients=config.start_telegram_clients,
        min_of_telegram_clients=config.minimum_of_telegram_clients
    )
    
    MainThreadVars.handler = partial(signal_handler, control_thread_obj=MainThreadVars.control_thread_obj)
    
    signal.signal(2, MainThreadVars.handler)
    signal.signal(15, MainThreadVars.handler)
    
    MainThreadVars.control_thread = threading.Thread(target=MainThreadVars.control_thread_obj.start_control_thread, 
                                                     args=[MainThreadVars.handler], name='Control_Thread')
    MainThreadVars.control_thread.start()
    
    # FIX: An awfull, terrible, painfull, abominable, constrained but even worse, bloated code, I didn't found another way of keeping 
    # the main thread active to be able to receive signals without looping on windows, on linux, macOS and other os, locks can receive 
    # POSIX signals so it will be added in the near future
    if sys.platform in ['win32', 'linux', 'darwin']:
        MainThreadVars.logger.debug('Starting loop to receive signals')
        while True:
            # INFO: A timeout of 5 seconds, if a signal was sent it will take a max of those seconds to call the handler
            MainThreadVars.control_thread.join(timeout=5.0)
            
            if not MainThreadVars.control_thread.is_alive():
                break
            MainThreadVars.logger.debug('Looped')
        MainThreadVars.logger.info('Finishing up main thread, signals will not be processed after this point')
        
    else:
        MainThreadVars.logger.critical('OS doesnt have a way to keep the main thread alive, add a personalized way or use the win32 method')
        MainThreadVars.handler()