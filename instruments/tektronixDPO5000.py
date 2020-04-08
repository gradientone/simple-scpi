import array
import sys
from instruments.base import TraceXY
from instruments.base import UnexpectedResponseException
from instruments.tektronix import TektronixInstrument


class TektronixDPO5000(TektronixInstrument):

    def __init__(self, *args, **kwargs):
        super(TektronixDPO5000, self).__(*args, **kwargs)

    def _fetch_trace(self, channel_name=''):

        if self._driver_operation_simulate:
            return TraceXY()

        self._write(":data:source {}".format(channel_name))
        self._write(":data:encdg fastest")
        self._write(":data:width 2")
        self._write(":data:start 1")
        self._write(":data:stop 1e10")

        trace = TraceXY()

        # Read preamble
        pre = self._ask(":wfmoutpre?").split(';')
        print("pre = {}".format(self._ask("WFMOutpre?")))
        print("byt_nr {}".format(self._ask("WFMOUTpre:BYT_NR?")))
        print("bit_nr {}".format(self._ask("WFMOUTpre:BIT_NR?")))
        print("ENCDG {}".format(self._ask("WFMOUTpre:ENCDG?")))
        print("BNFMT {}".format(self._ask("WFMOUTpre:BN_FMT?")))
        print("BYTOR {}".format(self._ask("WFMOUTpre:BYT_OR?")))
        print("NRFMT {}".format(self._ask("WFMOUTpre:NR_PT?")))
        print("PTFMT {}".format(self._ask("WFMOUTpre:PT_FMT?")))
        print("XINC {}".format(self._ask("WFMOUTpre:XINCR?")))
        print("XZERO {}".format(self._ask("WFMOUTpre:XZERO?")))
        print("PTOFF {}".format(self._ask("WFMOUTpre:PT_OFF?")))
        print("YMULT {}".format(self._ask("WFMOUTpre:YMULT?")))
        print("YOFOF {}".format(self._ask("WFMOUTpre:YOFF?")))
        print("YZERO {}".format(self._ask("WFMOUTpre:YZERO?")))
        print("NR_nr {}".format(self._ask("WFMOUTpre:NR_FR?")))
        acq_format = pre[7].strip().upper()
        points = int(pre[6])
        point_size = int(pre[0])
        point_enc = pre[2].strip().upper()
        point_fmt = pre[3].strip().upper()
        byte_order = pre[4].strip().upper()
        trace.x_reference = float(pre[11])  # pt_off
        trace.x_increment = float(pre[9])  # xincr
        trace.x_origin = float(pre[10])  # xzero
        trace.y_increment = float(pre[13])  # ymult
        trace.y_reference = int(float(pre[14]))  # yoff
        trace.y_origin = (float(pre[15]))  # yzero

        if acq_format != 'Y':
            raise UnexpectedResponseException()

        if point_enc != 'BINARY':
            raise UnexpectedResponseException()

        # Read waveform data
        raw_data = self._ask_for_ieee_block(":curve?")
        self._read_raw()  # flush buffer

        # Store in trace object
        if point_fmt == 'RP' and point_size == 1:
            trace.y_raw = array.array('B', raw_data[0:points*2])
        elif point_fmt == 'RP' and point_size == 2:
            trace.y_raw = array.array('H', raw_data[0:points*2])
        elif point_fmt == 'RI' and point_size == 1:
            trace.y_raw = array.array('b', raw_data[0:points*2])
        elif point_fmt == 'RI' and point_size == 2:
            trace.y_raw = array.array('h', raw_data[0:points*2])
        elif point_fmt == 'FP' and point_size == 4:
            trace.y_increment = 1
            trace.y_reference = 0
            trace.y_origin = 0
            trace.y_raw = array.array('f', raw_data[0:points*4])
        else:
            raise UnexpectedResponseException()

        if (byte_order == 'LSB') != sys.byteorder == 'little':
            trace.y_raw.byteswap()

        trace.y_raw.byteswap()

        return trace
