import errno
import os
import socket
import sys

from instruments.base import Instrument
from instruments.instrument_utils import InstrumentConnectionError
from settings import SCRIPT_TIMEOUT
from settings import BASE_URL, SCPIDIR
from instruments import instrument_drivers
from requesters import Requester
from scpi_logger import logger
from script_tools import timeout, TimeoutError, Sleep, G1Loop
from scpi_commands import SCPICommand, FetchWaveformCommand
from scpi_commands import FetchScreenshotCommand
from scpi_commands import PostWaveformCommand, PostScreenshotCommand


SCPI_FILENAME = 'scpi_script.txt'
SCPI_FILEPATH = os.path.join(SCPIDIR, SCPI_FILENAME)


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
        script = [str(command) for command in commands]
        logger.info("building G1Script: {}".format(script))
        self.commands = commands

    @timeout(SCRIPT_TIMEOUT)
    def run(self):
        for command in self.commands:
            try:
                response = command.run()
            except TimeoutError:
                logger.warning("Command '{}' timed out!".format(command))
            except Exception as e:
                logger.warning("Command '{}' encountered an unexpected "
                               "exception: {};".format(command, e))
            else:
                if isinstance(response, list):
                    self.responses.extend(response)
                else:
                    self.responses.append(response)


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
                cmdstr = self._sanitize_command_string(row)
                if cmdstr:
                    try:
                        self._parse_command_string(cmdstr)
                    except socket.error as e:
                        self._handle_socket_err(e)
        return G1Script(commands=self.commands)

    def _sanitize_command_string(self, row):
        val = row.rstrip()
        if val.startswith('#'):
            # the row is just a comment, ignore it
            return ''
        else:
            return val

    def write(self, file='', mode='r', content=''):
        try:
            with open(file, mode) as f:
                f.write(content)
        except IOError as e:
            # not able to read the file
            logger.warning("IOError write(): {}".format(e))
        except TypeError as e:
            # bad data in the file
            logger.warning("TypeError write(): {}".format(e))
        except Exception as e:
            logger.error("Unexpected error in write(): {}".format(e))

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
        if cmdcaps.startswith('G1:OPEN') or cmdcaps.startswith('TCPIP'):
            try:
                self.instrument = self._open_instrument(cmdstr)
            except InstrumentConnectionError:
                logger.warning("Encountered InstrumentConnectionError when "
                               "attempting to open with '{}'".format(cmdstr))
                logger.warning("Exiting...")
                sys.exit()
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
        g1_commands = {
            'G1:SLEEP': Sleep,
            'G1:FETCHWAVEFORM': FetchWaveformCommand,
            'G1:FETCHSCREENSHOT': FetchScreenshotCommand,
            'G1:POSTWAVEFORM': PostWaveformCommand,
            'G1:POSTSCREENSHOT': PostScreenshotCommand,
        }
        cmdstr = cmdstr.upper()
        # if cmdstr in g1_commands:
        if cmdstr.startswith(tuple(g1_commands.keys())):
            key = cmdstr.split('(')[0]
            command = g1_commands[key](command=cmdstr,
                                       instrument=self.instrument)
        else:
            command = SCPICommand(command=cmdstr, instrument=self.instrument)
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

    def _open_instrument(self, cmdstr, retry=True):
        """Opens connection with the Instrument"""
        addr = cmdstr.upper().split('G1:OPEN:')[-1]
        logger.info("Initializing instrument at: {}".format(addr))
        try:
            raw_instr = Instrument(addr)
        except socket.error as serr:
            if serr.errno != errno.ECONNREFUSED:
                raise serr
            # handle connection refused
            if retry:
                return self._open_instrument(addr, retry=False)
            else:
                raise serr

        ianalyzer = instrument_drivers.InstrumentAnalyzer()
        self.instrument = ianalyzer.open_instrument(raw_instr)
        if not self.instrument:
            raise InstrumentConnectionError
        else:
            return self.instrument

    def _handle_socket_err(self, err):
        logger.warning("Socket Error: {}".format(err))


class Result(object):

    def __init__(self, *args, **kwargs):
        self.category = ''  # fetch_screenshot, results_table, etc.
        self.file_key = ''
        self.command_id = ''
        self.requester = Requester()

    def save_to_server(self):
        """Saves Result to server

        Summary:
            First makes a GET request for a upload url.
            Then makes a POST to the upload url.

        Parameters:
            None

        Returns:
            A requests module response object
        """
        BASE_URL + '/upload/geturl'
        upload_url = self.requester.https_get(BASE_URL + '/upload/geturl')
        data = {
            'category': self.category,
            'file_key': self.file_key,
            'command_id': self.command_id,
        }
        response = self.requester.https_post(upload_url, data)
        return response


if __name__ == '__main__':
    scpiclient = SCPIClient()
    scpiclient.handle_scpi_file()
    scpiclient.run_script()
