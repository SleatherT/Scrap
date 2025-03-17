import logging
from utils import get_logger

class handlers_controler():
    # If new loggers are registered, they must be added to this list so output isn't sent to the console while waiting for input
    loggers_name = [
        '__main__',
        'telethon'
    ]
    
    removed_handlers_flag = False
    removed_handlers = dict()
    
    
    @classmethod
    def remove_handler_by_type(cls, handler_type):
        class_logger = get_logger()
        if cls.removed_handlers_flag:
            class_logger.critical('remove_handler_by_type called again before restoring removed handlers')
            return None
        
        parent_loggers = [logging.getLogger(name) for name in cls.loggers_name]
        
        for logger in parent_loggers:
            for handler in logger.handlers:
                if type(handler) is handler_type:
                    logger.removeHandler(handler)
                    cls.removed_handlers[logger.name] = handler
                    break
        
        cls.removed_handlers_flag = True
    
    
    @classmethod
    def restore_removed_handlers(cls):
        for name, handler in cls.removed_handlers.items():
            logger = logging.getLogger(name)
            logger.addHandler(handler)
        
        cls.removed_handlers_flag = False