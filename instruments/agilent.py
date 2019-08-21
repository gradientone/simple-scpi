# For Agilent Specific Command Handling

import sys
import array
from base import Instrument, ValueNotSupportedException
from base import InvalidAcquisitionTypeException, UnexpectedResponseException


class AgilentInstrument(Instrument):

    def fetch_screenshot(self, file_fmt='png', invert=False):

        if file_fmt not in self._display_screenshot_image_format_mapping:
            raise ValueNotSupportedException()

        file_fmt = self._display_screenshot_image_format_mapping[file_fmt]
        self._write(":display:data? {}, screen, on, {}"
                    .format(file_fmt, 'invert' if invert else 'normal'))

        scr = self._read_ieee_block()
        self._read_raw()  # flush buffer

        return scr

    def _fetch_trace(self, channel_name):
        if self._driver_operation_simulate:
            return []

        if sys.byteorder == 'little':
            self._write(":waveform:byteorder lsbfirst")
        else:
            self._write(":waveform:byteorder msbfirst")
        self._write(":waveform:format word")
        self._write(":waveform:streaming on")
        self._write(":waveform:source {}".format(channel_name))

        # Read preamble

        pre = self._ask(":waveform:preamble?").split(',')

        wformat = int(pre[0])
        if wformat != 2:
            raise UnexpectedResponseException()

        wtype = int(pre[1])
        if wtype == 1:
            raise InvalidAcquisitionTypeException()

        points = int(pre[2])
        count = int(pre[3])
        xincrement = float(pre[4])
        xorigin = float(pre[5])
        xreference = int(float(pre[6]))
        yincrement = float(pre[7])
        yorigin = float(pre[8])
        yreference = int(float(pre[9]))

        # Read waveform data
        raw_data = self._ask_for_ieee_block(":waveform:data?")

        # Split out points and convert to time and voltage pairs
        y_data = array.array('h', raw_data[0:points*2])

        data = [(((i - xreference) * xincrement) + xorigin, float('nan') if y == 31232 else ((y - yreference) * yincrement) + yorigin) for i, y in enumerate(y_data)]  # noqa

        return data
