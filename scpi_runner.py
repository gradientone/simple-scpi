import functools
import errno
import os
import socket
import time
import vxi11
import scpi_logger
from threading import Thread
from settings import COMMAND_TIMEOUT, SCRIPT_TIMEOUT


HOME = os.path.expanduser("~")
SCPIDIR = os.path.join(HOME, 'scpi')
if not os.path.exists(SCPIDIR):
    os.makedirs(SCPIDIR)

SCPI_FILENAME = 'scpi_script'
SCPI_FILEPATH = os.path.join(SCPIDIR, SCPI_FILENAME)


logger = scpi_logger.get_logger()


class TimeoutError(Exception):
    def __init__(self, *args):
        super(TimeoutError, self).__init__('Timeout',*args)


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
                except Exception, e:
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


class G1Script(object):
    """A GradientOne script parsed from the SCPI script file

    When the script is run the class will iterate through each
    command to call its 'run' method. Each command can either
    be a SCPICommand or a ScriptLogic object.

    Responses will be added to the responses attribute. If the
    response is also a list it will extend responses, else it
    will just be appended to the list.
    """
    commands = []
    responses = []

    def __init__(self, commands):
        logger.info("building G1Script with commands: {}".format(commands))
        self.commands = commands

    @timeout(SCRIPT_TIMEOUT)
    def run(self):
        for command in self.commands:
            try:
                response = command.run()
            except TimeoutError:
                logger.warning("Command {} timed out!".format(command))
            except Exception as e:
                logger.warning("Command {} encountered an unexpected "
                               "exception: {}".format(command, e))
            else:
                if isinstance(response, list):
                    self.responses.extend(response)
                else:
                    self.responses.append(response)


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
    def __init__(self, seconds=0, *args, **kwargs):
        super(Sleep, self).__init__(*args, **kwargs)
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
                    response = "Command {} timed out!".format(command)
                    logger.warning(response)
                except Exception as e:
                    response = ("Command {} encountered an unexpected "
                                "exception: {}".format(command, e))
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


class SCPICommand():
    command = ''  # command string e.g. '*ESR?'
    method = 'write'  # vxi11 method used on instrument (write or ask)
    response = ''  # response from instrument

    def __init__(self, command, instrument, *args, **kwargs):
        self.instrument = instrument
        self.command = command
        if command[-1] == '?':
            self.method = 'ask'
        else:
            self.method = 'write'

    def __str__(self):
        return self.command

    @timeout(COMMAND_TIMEOUT)
    def run(self):
        if self.method == 'ask':
            self.response = self.instrument.ask_raw(self.command).rstrip('\r\n')
        else:
            self.response = self.instrument.write(self.command)
        logger.info("SCPICommand: {}; Response: {}"
                    .format(self.command, self.response))
        return self.response


class Instrument(vxi11.Instrument):
    vxi11_addr = ''
    scpi_commands = []


class SCPIClient():
    """Checks for SCPI commands and handles them if found"""
    def __init__(self):
        self.instrument = None
        self.loops = []
        self.commands = []
        self.script = None

    def handle_scpi_file(self, filepath=SCPI_FILEPATH):
        """Checks file location for scpi script

        Description:
            Checks for a scpi file at the filepath parameter.
            This method is a wrapper for the read_scpi_file
            method, which gets called as long as a file exists
            at the filepath. This will build the G1Script that
            can be run later by calling the run_script method.
            Exceptions raised by the read_scpi_file method are
            logged here.

        Parameters:
            filepath: the location to check with os.path.exists
                to see if a scpi file exists.

        Returns:
            None. This command does not return a value
        """
        if not os.path.exists(filepath):
            logger.error("No SCPI file at {}".format(filepath))
            return

        self.script = None
        try:
            self.script = self.read_scpi_file(filepath)
        except IOError as e:
            logger.warning(e)
        except OSError as e:
            logger.warning(e)
        except Exception as e:
            logger.error("Unexpected error: {}".format(e),
                         exc_info=True)

    def run_script(self):
        if self.script:
            self.script.run()
        else:
            logger.error("No script to run")

    def read_scpi_file(self, filepath):
        """Reads contents and handles commands of scpi script file

        Summary:
            Iterates through each line of the scpi file. If a command
            string is found then it is passed to _handle_scpi_command
            to send the command to the instrument.

        Parameters:
            filepath: the filepath of the scpi file

        Returns:
            G1Script object
        """
        with open(filepath, 'r') as scpifile:
            for row in scpifile:
                cmdstr = row.rstrip()
                if cmdstr:
                    try:
                        self._parse_command_string(cmdstr)
                    except socket.error as e:
                        self._handle_socket_err(e)
        return G1Script(commands=self.commands)

    def _parse_command_string(self, cmdstr):
        """Parses the commands string and adds it to the G1Script

        Summary:
            Either initializes the instrument or handles a scpi
            command. Handling a scpi command will instantiate a
            SCPICommand object to use for controlling the instrument.

        Returns:
            None
        """
        cmdcaps = cmdstr.upper()
        if cmdcaps.startswith('TCPIP'):
            self.instrument = self._init_instrument(cmdstr)
        elif not self.instrument:
            logger.warning("No instrument to run command: {}".format(cmdstr))
        elif cmdcaps.startswith('G1:STARTLOOP') or cmdcaps == 'G1:ENDLOOP':
            self._parse_loop_cmd(cmdstr)
        else:
            self._parse_basic_cmd(cmdstr)

    def _parse_basic_cmd(self, cmdstr):
        """Parses a basic command string

        This will either create a Sleep or SCPICommand to
        add to the commands to be run by the G1Script. If there
        is an active loop (i.e. self.loops has a loop in it), then
        the command will be appended to the last loop's commands.
        Otherwise the command will just be appended to the regular
        list of commands.
        """
        if cmdstr.upper().startswith('G1:SLEEP'):
            command = Sleep(seconds=float(cmdstr.split('=')[-1]))
        else:
            command = SCPICommand(cmdstr, self.instrument)
        if self.loops:
            self.loops[-1].commands.append(command)
        else:
            self.commands.append(command)

    def _parse_loop_cmd(self, cmdstr):
        """Parses the loop command string

        This will either create a new loop or it will end a loop
        and add the loop to the list of commands.
        """
        if cmdstr.upper().startswith('G1:STARTLOOP'):
            self.loops.append(self._create_loop(cmdstr))
        elif cmdstr.upper() == 'G1:ENDLOOP':
            loopcmd = self.loops.pop()
            self.commands.append(loopcmd)
        else:
            logger.error("Unexpected loop string: {}".format(cmdstr))

    def _create_loop(self, loopstr):
        """Parses the loopstr to build a G1Loop

        This will set the basics of the loop, but not the commands in it.
        """
        items = loopstr.split(':')
        maxcount = 1
        break_on = None
        for item in items:
            if item.upper().startswith('MAX'):
                maxcount = int(item.split('=')[-1])
            elif item.upper().startswith('BREAKON='):
                break_on = item.split('=')[-1]
        return G1Loop(maxcount=maxcount, break_on=break_on)

    def _init_instrument(self, addr, retry=True):
        """Initializes the vxi11 Instrument"""
        logger.info("Initializing instrument at: {}".format(addr))
        try:
            self.instrument = Instrument(addr)
        except socket.error as serr:
            if serr.errno != errno.ECONNREFUSED:
                raise serr
            # handle connection refused
            if retry:
                self._init_instrument(addr, retry=False)
            else:
                raise serr

        return self.instrument

    def _handle_socket_err(self, err):
        logger.warning("Socket Error: {}".format(err))


if __name__ == '__main__':
    scpiclient = SCPIClient()
    scpiclient.handle_scpi_file()
    scpiclient.run_script()
