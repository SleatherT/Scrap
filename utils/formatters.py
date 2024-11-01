import logging
import time

class base_formatter(logging.Formatter):
    def formatException(self, exc_info):
        result = super().formatException(exc_info)
        padding = '        '
        result = '\n' + padding + result.replace('\n', f'\n{padding}') 
        return result
    
    def format(self, record):
        s = super().format(record)
        if record.exc_text:
            s = f'{s}\n'
        return s

class utc_formatter(base_formatter):
    converter = time.gmtime