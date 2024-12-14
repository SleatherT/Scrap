import threading
import logging

def get_logger():
    # INFO: Using the default name given to the main thread
    if threading.current_thread().name != 'MainThread':
        logger = logging.getLogger(f'__main__.{threading.current_thread().name}')
    else:
        logger = logging.getLogger(__name__)
        
    return logger