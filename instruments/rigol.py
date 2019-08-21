# For Rigol Specific Command Handling

import array
from base import Instrument, decode_ieee_block, TraceXY
from base import UnexpectedResponseException


class RigolInstrument(Instrument):

    def __init__(self, *args, **kwargs):
        super(RigolInstrument, self).__init__(*args, **kwargs)

    def fetch_screenshot(self, file_fmt='bmp', invert=False):

        self._write(":display:data?")
        return self._read_ieee_block()

        # if _read_ieee_block does not work, use decode_ieee_block func
        # data = self._read_raw()
        # return decode_ieee_block(data)

    def _fetch_trace(self, channel_name):
        if self._driver_operation_simulate:
            return []

        self._write(":waveform:source {}".format(channel_name))
        self._write(":waveform:format byte")

        trace = TraceXY()

        # Read preamble
        pre = self._ask(":waveform:preamble?").split(',')

        acq_format = int(pre[0])
        acq_type = int(pre[1])
        points = int(pre[2])
        trace.average_count = int(pre[3])
        trace.x_increment = float(pre[4])
        trace.x_origin = float(pre[5])
        trace.x_reference = int(float(pre[6]))
        trace.y_increment = float(pre[7])
        trace.y_origin = 0.0
        trace.y_reference = int(float(pre[9]) + float(pre[8]))

        if acq_format != 0:
            raise UnexpectedResponseException()

        # Read waveform data
        data = bytearray()

        for offset in range(1, points+1, 250000):
            self._write(":waveform:start %d" % offset)
            self._write(":waveform:stop %d" % min(points, offset+249999))
            self._write(":waveform:data?")
            raw_data = self._read_raw()
            data.extend(decode_ieee_block(raw_data))

        # Store in trace object
        trace.y_raw = array.array('B', data[0:points])

        return trace
