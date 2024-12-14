import logging
import time
import subprocess
import io
import os
import threading

import ffmpeg

from utils import get_logger

# A class that stores only the last log of ffmpeg, there is probably a better way to save the last log and be able to see it
# in another thread
class dummy():
    def __init__(self):
        self.string = None

def log(process, dummy_object):
    logger = get_logger()
    
    stderr_wrapped_stream = io.TextIOWrapper(process.stderr, newline=None)
    
    while process.poll() is None:
        try:
            output = stderr_wrapped_stream.readline().removesuffix('\n')
        except ValueError as e:
            # The ValueError error is raised when trying to read from a closed stream, that can happen in cases when 
            # between the process.poll call returns None but it has closed the stream (the process is finishing)
            logger.exception('Expected ValueError raised')
            break
        
        logger.info(output)
        
        dummy_object.string = output


def call_ffmpeg(*, Filepath, maps: list, kwargs: dict, target_format: str):
    ''' A wrapper for ffmpeg-python (a wrapper of a wrapper lol). Returns the exit code and the output file path, however
    this doesn't mean it was correctly processed or it exists since runtime errors like passing codecs incorrectly dont
    raise a fatal return code and return the successful code (0), the only way to know if it was truly successful is 
    checking the logs
    
    Filepath should be a path returned by a previous function, its not recommended to use a manually created path, maps is a
    list of the streams to choose; audio, subtitles or video, e.g. ['a:1', 's', 'v'] respectively, kwargs is a dictionary that
    will be passed to ffmpeg-python kwargs output function
    target_format is basically the output name
    
    If the process failed then the process returncode is returned, if succeed then the path to the file is returned
    
    '''
    logger = get_logger()
    
    input_file = ffmpeg.input(Filepath)
    
    # Before this line was repo_path = os.path.dirname(os.path.dirname(os.path.abspath('None'))) and 
    # output_path = os.path.abspath(f'{repo_path}/misc/{target_format}') it makes sense, if the main script was executed in
    # this directory which it was not, I didn't know that os.path.abspath returned the path  using the path of the script 
    # file executing
    
    output_path = os.path.abspath(f'misc/{target_format}')
    
    video = None
    audio = None
    subs = None
    
    for stream in maps:
        if stream.startswith('v'):
            video = input_file[stream]
        elif stream.startswith('a'):
            audio = input_file[stream]
        elif stream.startswith('s'):
            subs = input_file[stream]
    
    streams = [video, audio, subs]
    
    selected_streams = [stream for stream in streams if stream is not None]
    
    graph = ffmpeg.output(
        *selected_streams,
        output_path,
        **kwargs
    )
    
    process = ffmpeg.run_async(
        graph,
        pipe_stdin=True,
        pipe_stdout=False,
        pipe_stderr=True,
        overwrite_output=True
    )
    
    dummy_obj = dummy()
    
    log_thread = threading.Thread(target=log, args=[process, dummy_obj], name='ffmpeg_logger')
    log_thread.start()
    
    # INFO: The loop to check if the process is waiting for output by using the last time the an output was registered
    while process.poll() is None:
        saved_output = dummy_obj.string
        time.sleep(10)
        
        logger.debug(f'dummy_obj.string and saved_output vars: {dummy_obj.string} // {saved_output}')
        
        if saved_output == dummy_obj.string and process.poll() is None:
            logger.debug('About to call terminate()')
            process.terminate()
            break
    
    try:
        outs, errs = process.communicate(timeout=60)
    except subprocess.TimeoutExpired:
        logger.exception('The ffmpeg process took too much time to finish, about to call kill()')
        process.kill()
    
    # This should not raise TimeoutExpired, probably, I hope
    outs, errs = process.communicate(timeout=60)
    logger.info(f'Last bytes not read from ffmpeg process: {errs}')
    
    logger.debug(f'Popen returncode: {process.returncode}')
    
    return process.poll(), output_path