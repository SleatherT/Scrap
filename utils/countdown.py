import time

class countdown:
    ''' Not Thread-safe
    
    '''
    def start_countdown(self, countdown_time):
        self.countdown_time = countdown_time
        self.called_time = time.time()
    
    def get_time_left(self):
        current_time = time.time()
        
        passed_time = current_time - self.called_time
        
        self.countdown_time = self.countdown_time - passed_time
        
        return self.countdown_time