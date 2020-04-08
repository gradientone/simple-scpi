# For Tektronix Specific Command Handling

from instruments.base import Instrument, TraceXY


class TektronixInstrument(Instrument):

    def fetch_screenshot(self, file_fmt='png', invert=False):
        self._write(":hardcopy:inksaver {}".format(int(bool(invert))))
        self._write(":save:image:fileformat {}".format(file_fmt))
        self._write(":hardcopy start")

        return self._read_raw()

    def _fetch_trace(self, channel_name=''):

        if self._driver_operation_simulate:
            return TraceXY()

        trace = TraceXY()

        return trace
