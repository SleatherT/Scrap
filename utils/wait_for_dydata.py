import logging

# Defaulted to aprox 10 seconds in waiting to load the data
def wait_for_dydata(Web_Driver, byLocator, elementID: str, attributeName: str, expectedType, aproxTimeout=10):
    # Returns the attribute data if it changed in the expected time, otherwise raises an Exception
    logger = logging.getLogger(f'__main__.utils.{__name__}')
    
    pollFrequency = 0.5
    numLoops = int(aproxTimeout/pollFrequency)
    
    for loop in range(numLoops):
        attributeData = Web_Driver.find_element(by=byLocator, value=elementID).get_attribute(attributeName)
        
        if type(attributeData) is expectedType:
            return attributeData
        else:
            time.sleep(pollFrequency)
            continue
    
    raise Exception(f'Expected type attribute failed, type: {type(attributeData)}, expected type: {expectedType}')