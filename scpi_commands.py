import datetime
import json
import os
import re
import requests
import ssl
import settings
from requests_toolbelt.multipart.encoder import MultipartEncoder
from requesters import Requester
from settings import COMMAND_TIMEOUT, BASE_URL, SCREENSHOT_FILE
from script_tools import timeout
from scpi_logger import logger
from instruments.base import TraceXY, NotInitializedException


class Waveform(TraceXY):
    pass


class APIException(Exception):

    def __init__(self, *args, **kwargs):
        msg = "API Exception"
        super(APIException, self).__init__(msg, *args, **kwargs)


class InvalidResultRequestError(Exception):

    def __init__(self, *args, **kwargs):
        msg = "Invalid Result Request Error"
        super(InvalidResultRequestError, self).__init__(msg, *args, **kwargs)


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
            self.response = self.instrument.ask(self.command).rstrip('\r\n')
        else:
            self.response = self.instrument.write(self.command)
        logger.info("SCPICommand: {}; Response: {}"
                    .format(self.command, self.response))
        return self.response


class FetchWaveformCommand(SCPICommand):

    def __init__(self, command, instrument, *args, **kwargs):
        self.instrument = instrument
        self.command = command
        self.response = ''
        self.channels = self._parse_channels(command)

    def _parse_channels(self, command):
        channels = []
        if '(' in command:
            rematch = re.search('\((.*)\)', command)
            if rematch:
                chlist = rematch.group(1).split(',')
                channels = [c.strip().lower() for c in chlist if c]
        return channels

    def _get_instrument_type(self):
        if 'instrument_type' in self.instrument.id_dict:
            return self.instrument.id_dict['instrument_type']
        else:
            return 'Unknown'

    @timeout(COMMAND_TIMEOUT)
    def run(self):
        logger.info("Running FetchWaveformCommand")
        waveform = self.instrument.fetch_waveform(self.channels)
        waveform['instrument_type'] = self._get_instrument_type()
        self.response = self.save_to_file(waveform)
        logger.info("FetchWaveformCommand response: {}".format(self.response))
        return self.response

    def save_to_file(self, data, filepath=''):
        """saves data to filepath designated in settings.py"""
        if not filepath:
            filepath = settings.WAVEFORM_FILE
        response = 'No waveform saved'  # default msg until success
        try:
            with open(filepath, 'wb') as f:
                f.write(json.dumps(data))
        except IOError as e:
            logger.warning(e)
        except OSError as e:
            logger.warning(e)
        except Exception as e:
            logger.error("Unexpected error: {}".format(e),
                         exc_info=True)
        else:
            # success!
            response = "Waveform saved to: {}".format(filepath)
        return response


class FetchScreenshotCommand(SCPICommand):

    def __init__(self, command, instrument, *args, **kwargs):
        self.instrument = instrument
        self.command = command

    @timeout(COMMAND_TIMEOUT)
    def run(self):
        """Runs the Fetch Screenshot Command

        Summary:
            Fetches the screenshot and writes it to file
        """
        scn = None
        try:
            scn = self.instrument.fetch_screenshot()
        except NotInitializedException as e:
            logger.warning("instrument not initialized for screenshot")
        except IOError as e:
            logger.warning(e)
        except OSError as e:
            logger.warning(e)
        except Exception as e:
            logger.error("Unexpected error: {}".format(e),
                         exc_info=True)
        if scn:
            response = self.save_to_file(scn)
        else:
            response = "Unable to fetch screenshot!"
            logger.warning(response)
        self.response = response
        logger.info("FetchScreenshotCommand response: {}".format(response))
        return self.response

    def save_to_file(self, data, filepath=''):
        """saves data to filepath designated in settings.py"""
        if not filepath:
            filepath = SCREENSHOT_FILE
        response = 'No screenshot saved'  # default msg until success
        try:
            with open(SCREENSHOT_FILE, 'wb') as f:
                f.write((data))
        except IOError as e:
            logger.warning(e)
        except OSError as e:
            logger.warning(e)
        except Exception as e:
            logger.error("Unexpected error: {}".format(e),
                         exc_info=True)
        else:
            # success!
            response = "Screenshot saved to: {}".format(filepath)
        return response


class FileTransmitter(object):

    def __init__(self, category=''):
        self.category = category
        self.requester = Requester()

    def transmit(self, filepath, file_key='', mode='rb'):
        """transmits file to server"""
        with open(filepath, mode) as f:
            filename = os.path.basename(f.name)
        if not file_key:
            file_key = filename
        fields = {
            'file': (filename, open(filepath, mode)),
            'file_key': file_key,
            'category': self.category,
        }
        multipartblob = MultipartEncoder(fields=fields)

        # get the temporary upload url to post the file to
        resp = self.requester.https_get(BASE_URL + "/upload/geturl")
        if not resp:
            logger.warning("No response from {}. Aborting upload."
                           .format(BASE_URL + "/upload/geturl"))
            return

        headers = {'Content-Type': multipartblob.content_type}
        response = None
        try:
            response = requests.post(resp.text, data=multipartblob,
                                     headers=headers)
        except TypeError:
            logger.warning("TypeError during transmit_file call",
                           exc_info=True)
        except ssl.SSLError:
            logger.warning("SSLError! during transmit_file",
                           exc_info=True)
        self._log_upload_response(response)
        return response

    def _log_upload_response(self, response):
        if response and response.status_code == 200:
            logger.info("File upload succeeded!")
        else:
            logger.warning("File upload failed")
            response_text = None
            if hasattr(response, 'text'):
                response_text = response.text
            if not response_text:
                logger.warning("No response text to log")
            else:
                logger.warning("Non 200 response {}".format(response_text))


class PostScreenshotCommand(object):

    def __init__(self, *args, **kwargs):
        self.requester = Requester()

    def __str__(self):
        return 'PostScreenshotCommand'

    @timeout(COMMAND_TIMEOUT)
    def run(self):
        """Posts the screenshot file to the server

        Summary:
            Transmits the screenshot file with a file_key to
            look up the file at a later date. The file_key
            is set with date and time to the second, e.g.
                "screenshot-2019-08-14T15:50:43"
            If this was successful a result_id is generated
            and will be logged.
        """
        transmitter = FileTransmitter(category='fetch_screenshot')
        dt_str = datetime.datetime.now().isoformat()
        file_key = 'screenshot-' + dt_str.split(',')[0]
        logger.info("Using file_key: " + file_key)
        response = transmitter.transmit(SCREENSHOT_FILE, file_key=file_key)
        result_id = self._handle_response(response)
        if result_id:
            logger.info("Result ID for screenshot: {}".format(result_id))
            rid_url = BASE_URL + '/results/{}'.format(result_id)
            logger.info("You can view the result at: {}".format(rid_url))
        else:
            logger.warning("No Result ID from waveform upload")


    def _handle_response(self, response):
        """Handles the response from the result upload

        Returns:
            result_id: a string with the result id value
        """
        result_id = ''
        try:
            result_id = json.loads(response.text)['result']['id']
        except TypeError:
            # likely due to nothing in response text
            error_msg = "TypeError in fetch_screenshot response"
            self._log_activity(error_msg, level='warning')
        except ValueError:
            # likely due to invalid json in response
            error_msg = "ValueError in fetch_screenshot response"
            self._log_activity(error_msg, level='warning')
        except KeyError:
            # valid json response, but missing result or id
            error_msg = "KeyError in fetch_screenshot response"
            self._log_activity(error_msg, level='warning')
        except Exception as e:
            error_msg = "Unexpected Exception {}".format(e)
            self._log_activity(error_msg, level='warning')
        return result_id


class PostWaveformCommand(object):

    def __init__(self, *args, **kwargs):
        self.waveform_filepath = settings.WAVEFORM_FILE
        self.instr = None
        self.trace_dict = {}
        self.result_id = ''
        self.requester = Requester()
        self._set_divisions()

    def __str__(self):
        return 'PostWaveformCommand'

    def _read_trace_data(self, filepath=''):
        if not filepath:
            filepath = settings.WAVEFORM_FILE
        data = None
        with open(filepath, 'rb') as f:
            try:
                data = json.loads(f.read())
            except IOError as e:
                logger.warning(e)
            except OSError as e:
                logger.warning(e)
            except Exception as e:
                logger.error("Unexpected error: {}".format(e),
                             exc_info=True)
        if not data:
            data = {}

        return data


    @timeout(COMMAND_TIMEOUT)
    def run(self):
        self.trace_dict = self._read_trace_data()
        self.result_id = self._create_waveform_result()
        tfilename = 'full-trace-{}.json'.format(self.result_id)
        self._write_trace_dict(tfilename)

    def _create_waveform_result(self):
        """Creates a waveform result on the server"""
        dt_str = datetime.datetime.now().isoformat()
        waveform_id = 'waveform-' + dt_str.split(',')[0]
        if 'instrument_type' in self.trace_dict:
            instrument_type = self.trace_dict.pop('instrument_type')
        else:
            instrument_type = 'sample_instrument_type'
        data = {
            'command_id': waveform_id,
            'config_name': waveform_id,
            'instrument_type': instrument_type,
            'kind': 'Result_Summary',
            'upload_kind': 'Waveform',
            'info': {},
            'waveform': self.trace_dict,
        }

        # assuming these are set in settings them
        # data['instrument_type'] = settings.INSTRUMENT_TYPE,
        # data['device_under_test'] = settings.DUT

        r_url = BASE_URL + '/results'
        json_data = json.dumps(data, ensure_ascii=True)
        response = self.requester.https_post(r_url, data=json_data)
        result_id = ''
        if not response:
            return

        logger.info("Request to {} response.status_code: {}"
                    .format(r_url, response.status_code))
        try:
            result_id = json.loads(response.text)['result']['id']
        except ValueError:
            logger.warning("ValueError in _create_waveform_results")
            logger.info("response text: {}".format(response.text))
        except KeyError:
            logger.warning("KeyError in _create_waveform_results")
        except Exception as e:
            logger.warning("Unexpected error: {}".format(e), exc_info=True)
        else:
            logger.info("Result created successfully with result_id: {}"
                        .format(result_id))
            rid_url = r_url + '/{}'.format(result_id)
            logger.info("You can view the result at: {}".format(rid_url))
        self.trace_dict['result_id'] = result_id
        return result_id

    def _write_trace_dict(self, filename=''):
        if filename == '':
            filename = 'full-trace-{}.json'.format(self.result_id)
        self.trace_file = os.path.join(settings.DATADIR, filename)
        logger.info("Writing full trace to file: {}".format(self.trace_file))
        with open(self.trace_file, 'w') as f:
            f.write(json.dumps(self.trace_dict))

    def _set_divisions(self, h_divs=0, v_divs=0):
        """Checks the instrument for divisions

        If the instrument does not have them then default values
        are used. If vertical and horizontal divisions are passed
        in as parameters then those will take priority in setting
        the class attributes.
        """
        DEFAULT_HORIZONTAL_DIVS = 10
        DEFAULT_VERTICAL_DIVS = 8
        if self.instr and self.instr._horizontal_divisions:
            self._horizontal_divisions = self.instr._horizontal_divisions
        else:
            self._horizontal_divisions = DEFAULT_HORIZONTAL_DIVS
        if self.instr and self.instr._vertical_divisions:
            self._vertical_divisions = self.instr._vertical_divisions
        else:
            self._vertical_divisions = DEFAULT_VERTICAL_DIVS
        if h_divs:
            self._horizontal_divisions = h_divs
        if v_divs:
            self._vertical_divisions = v_divs
        if not isinstance(self.trace_dict, dict):
            print(self.trace_dict)
            logger.warning("trace data not properly initialized")
            self.trace_dict = {}
        self.trace_dict['h_divs'] = self._horizontal_divisions
        self.trace_dict['v_divs'] = self._vertical_divisions
