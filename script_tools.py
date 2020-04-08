import time
import functools
import re
from threading import Thread
from scpi_logger import logger
from settings import COMMAND_TIMEOUT


class TimeoutError(Exception):
    def __init__(self, *args):
        super(TimeoutError, self).__init__('Timeout', *args)


def timeout(timeout):
    def deco(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            origResult = TimeoutError(
                         'function [{}] timeout [{} seconds] exceeded!'
                         .format(func.__name__, timeout))
            res = [origResult]

            def newFunc():
                try:
                    result = func(*args, **kwargs)
                except Exception as e:
                    result = e
                res[0] = result
            t = Thread(target=newFunc)
            t.daemon = True
            try:
                t.start()
                t.join(timeout)
            except Exception as e:
                logger.error('error starting thread')
                raise e
            result = res[0]  # get result from thread
            if isinstance(result, TimeoutError):
                logger.error('function [{}] timeout [{} seconds] exceeded!'
                             .format(func.__name__, timeout))
                raise result
            elif isinstance(result, BaseException):
                logger.error("Unexpected exception in {}"
                             .format(func.__name__))
                raise result
            return result
        return wrapper
    return deco


class ScriptLogic(object):
    """Handles loops and conditionals for a SCPI script"""
    def __init__(self, name='', *args, **kwargs):
        self.name = name

    def __str__(self):
        if self.name:
            return self.name
        else:
            return 'ScriptLogicObject'


class Sleep(ScriptLogic):
    """When running the script this will time.sleep()"""
    def __init__(self, command='', *args, **kwargs):
        super(Sleep, self).__init__(name='Sleep', *args, **kwargs)
        rematch = re.search('\((.*)\)', command)
        if rematch:
            secstr = rematch.group(1)
            try:
                seconds = float(secstr)
            except ValueError:
                seconds = 1
        else:
            seconds = 1
        self.seconds = seconds

    @timeout(COMMAND_TIMEOUT)
    def run(self):
        time.sleep(self.seconds)


class G1Loop(ScriptLogic):
    """GraidienOne class for handling commands in a loop"""
    def __init__(self, commands=[], maxcount=1, break_on=None,
                 *args, **kwargs):
        super(G1Loop, self).__init__(*args, **kwargs)
        self.responses = []

        # list of commands to run each iteration
        self.commands = commands

        # maximum number of times to loop
        self.maxcount = maxcount

        # response to break loop
        self.break_on = break_on

    def run(self):
        for i in range(self.maxcount):
            for command in self.commands:
                try:
                    response = command.run()
                except TimeoutError:
                    response = "G1Loop: '{}' timed out!".format(command)
                    logger.warning(response)
                except Exception as e:
                    response = ("G1Loop: '{}' encountered an unexpected "
                                "exception: {};".format(command, e))
                    logger.warning(response)
                self.responses.append(response)
                if self.break_on is not None and response == self.break_on:
                    # Note: will break from the outer range() loop also
                    logger.info("Received response {}; Breaking from loop"
                                .format(response))
                    return

    def __str__(self):
        if self.name:
            return self.name
        else:
            return 'G1LoopObject'


class Comparison(ScriptLogic):
    comparson_value = ''
