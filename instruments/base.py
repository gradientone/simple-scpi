# Common base instrument command handling

import os
import re
import sys
from math import log10


def thisdir():
    """Returns the directory name of current file"""
    if getattr(sys, 'frozen', False):
        # The application is frozen
        return os.path.dirname(sys.executable)
    else:
        # The application is not frozen
        # Change this bit to match where you store your data files:
        return os.path.dirname(__file__)

sys.path.append(os.path.join(thisdir(), '../..'))
import settings

# try importing drivers
# python-vxi11 for LAN instruments
try:
    import vxi11
except ImportError:
    pass

# python-usbtmc for USBTMC instrument support
try:
    import usbtmc
except ImportError:
    pass

# linuxgpib wrapper for linux-gpib Gpib class
# for GPIB interfaces
try:
    from .interface import linuxgpib
except ImportError:
    pass

# pySerial wrapper for serial instrument support
try:
    from .interface import pyserial
except ImportError:
    pass

# pyvisa wrapper for PyVISA library support
try:
    from .interface import pyvisa
except ImportError:
    pass

# set to True to try loading PyVISA first before
# other interface libraries
_prefer_pyvisa = False


def get_prefer_pyvisa():
    global _prefer_pyvisa
    return _prefer_pyvisa


def set_prefer_pyvisa(value=True):
    global _prefer_pyvisa
    _prefer_pyvisa = bool(value)


class IOException(IOError):
    pass


class InstrumentException(Exception):
    pass


class NotInitializedException(InstrumentException):
    pass


class UnexpectedResponseException(InstrumentException):
    pass


class InvalidAcquisitionTypeException(InstrumentException):
    pass


class ValueNotSupportedException(InstrumentException):
    pass


def decode_ieee_block(data):
    "Decode IEEE block"
    # IEEE block binary data is prefixed with #lnnnnnnnn
    # where l is length of n and n is the
    # length of the data
    # ex: #800002000 prefixes 2000 data bytes
    if len(data) == 0:
        return b''

    ind = 0
    c = '#'.encode('utf-8')
    while data[ind:ind+1] != c:
        ind += 1

    ind += 1
    l = int(data[ind:ind+1])
    ind += 1

    if (l > 0):
        num = int(data[ind:ind+l].decode('utf-8'))
        ind += l

        return data[ind:ind+num]
    else:
        return data[ind:]


ScreenshotImageFormats = {
    'tif': 'tif',
    'tiff': 'tif',
    'bmp': 'bmp',
    'bmp24': 'bmp',
    'png': 'png',
    'png24': 'png',
    'jpg': 'jpg',
    'jpeg': 'jpg',
    'gif': 'gif'
}


def round_dec(val, decimal_place=3):
    """Rounds to a given decimal place and rounds up on 5
       >>> round_dec(0.0045)
       0.005
       >>> round_dec(4.5e-05)
       0.0
       >>> round_dec(4.5e-05, 5)
       5e-05
       """
    val += 0.01 * 10 ** -decimal_place
    rounded_val = round(val, decimal_place)
    if rounded_val > 1e+36:
        rounded_val = float(str(rounded_val))
    return rounded_val


def round_sig(val):
    """Rounds value to specified significant digits by determining
       decimal place needed to round number value and calling round_dec.
       Assuming ROUND_SIG_DIGITS is 4 (the default) then this yields:
       >>> round_sig(6.3193e-9)
       6.32e-09
       >>> round_sig(0.55550)
       0.556
       """
    if val == 0:
        return 0.0

    # if it's not set in settings, round to the default digits
    if not hasattr(settings, 'ROUND_SIG_DIGITS'):
        digits = 4  # by default round to 4
    elif settings.ROUND_SIG_DIGITS:
        digits = settings.ROUND_SIG_DIGITS
    # if the settings value is explicitly set to Falsey, don't round at all
    else:
        return val

    decimal_place = int(-log10(abs(val))) + digits
    return round_dec(val, decimal_place)


class Channel(object):

    def __init__(self, name=''):
        self.name = name


class Instrument(vxi11.Instrument):
    """docstring for Instrument"""

    scpi_commands = []
    resource_descriptor = ''

    def __init__(self, resource=None, *args, **kwargs):
        super(Instrument, self).__init__(resource, *args, **kwargs)
        self._initialized = True
        self._interface = None
        self._driver_operation_simulate = False
        self._display_screenshot_image_format_mapping = ScreenshotImageFormats
        self._channel_count = 2
        self._prefer_pyvisa = False

        self._set_channels()

        if resource is not None:
            self._init_resource(resource)

        if self._interface is None:
            print("WARNING: interface is not initialized. "
                  "Commands may not send properly")

    def fetch_waveform(self, channels=[]):
        """Iterates through channels and fetches data for each

        Summary:
            Converts the trace fetched to a list of y values to assign
            to the trace_data dictionary that will be returned.
            If more than the y values are needed then override this method
            to refactor the conversion of the trace object to the trace_data
            dictionary and returning a JSON serializeable format is
            recommended for saving to file and using the GradienOne API

        Returns:
            trace_data: a dictionary with a channels list of data for each
                channel with y_values and time_step
        """
        trace_data = {'channels': []}
        if channels:
            self._set_channels(channels)
        for channel in self.channels:
            chdata = {}
            xyvals = list(self._fetch_trace(channel.name))
            chdata['time_step'] = xyvals[0][0] - xyvals[1][0]
            chdata['y_values'] = [round_sig(val[1]) for val in xyvals]
            chdata['name'] = channel.name
            trace_data['channels'].append(chdata)

        return trace_data

    def _fetch_trace(self, channel_name=''):
        """Should be overridden for each instrument manufacturer model"""
        if self._driver_operation_simulate:
            return []

        return TraceXY()

    def _init_resource(self, resource=None):
        """Handles a resource value to initialize Instrument

        Summary:
            Sets class attributes based on the resource parameter.
            This includes the _driver_operation_simulate, _interface,
            and _initialized.

        Parameters:
            resource: the resource string associated with the
                instrument to be controlled. Typically this will
                include a TCPIP address.

        Returns:
            None: this method does not return a value
        """
        if self._driver_operation_simulate:
            print("Simulating; ignoring resource")
        elif resource is None:
            raise IOException('No resource specified!')
        elif type(resource) == str:
            self._init_str_resource(resource)
        elif 'vxi11' in globals() and resource.__class__ == vxi11.Instrument:
            # Got a vxi11 instrument, can use it as is
            self._interface = resource
        elif 'usbtmc' in globals() and resource.__class__ == usbtmc.Instrument:
            # Got a usbtmc instrument, can use it as is
            self._interface = resource
        elif set(['read_raw', 'write_raw']).issubset(set(resource.__class__.__dict__)):  # noqa
            # has read_raw and write_raw, so should be a usable interface
            self._interface = resource
        else:
            # don't have a usable resource
            raise IOException('Invalid resource')

        self._initialized = True

    def _init_str_resource(self, resource):
        """Parse VISA resource string

        valid resource strings:
            TCPIP::10.0.0.1::INSTR
            TCPIP0::10.0.0.1::INSTR
            TCPIP::10.0.0.1::gpib,5::INSTR
            TCPIP0::10.0.0.1::gpib,5::INSTR
            TCPIP0::10.0.0.1::usb0::INSTR
            TCPIP0::10.0.0.1::usb0[1234::5678::MYSERIAL::0]::INSTR
            USB::1234::5678::INSTR
            USB::1234::5678::SERIAL::INSTR
            USB0::0x1234::0x5678::INSTR
            USB0::0x1234::0x5678::SERIAL::INSTR
            USB0::0x1234::0x5678::SERIAL::0::INSTR
            GPIB::10::INSTR
            GPIB0::10::INSTR
            ASRL1::INSTR
            ASRL::COM1,9600,8n1::INSTR
            ASRL::/dev/ttyUSB0,9600::INSTR
            ASRL::/dev/ttyUSB0,9600,8n1::INSTR

        The resource string is matched against a regex to determine
        the type of resource and what method to initialize the interface
        with.
        """
        m = re.match('^(?P<prefix>(?P<type>TCPIP|USB|GPIB|ASRL)\d*)(::(?P<arg1>[^\s:]+))?(::(?P<arg2>[^\s:]+(\[.+\])?))?(::(?P<arg3>[^\s:]+))?(::(?P<arg4>[^\s:]+))?(::(?P<suffix>INSTR))$', resource, re.I)  # noqa

        # Below we only need the res_type (resource type) but if
        # needed the regex also matches prefix, suffix, and args.
        # args, prefix, or suffix is needed they can be assigned with:
        # res_prefix = m.group('prefix')
        # res_arg1 = m.group('arg1')
        # res_arg2 = m.group('arg2')
        # res_arg3 = m.group('arg3')
        # res_suffix = m.group('suffix')

        if m is None:
            if 'pyvisa' in globals():
                # connect with PyVISA
                self._interface = pyvisa.PyVisaInstrument(resource)
            else:
                raise IOException('Invalid resource string')
        else:
            res_type = m.group('type').upper()
            res_type_init_methods = {
                'TCPIP': self._init_tcpip_resource,
                'USB': self._init_usb_resource,
                'GPIB': self._init_gpib_resource,
                'ASRL': self._init_asrl_resource,
            }
            if res_type not in res_type_init_methods:
                if 'pyvisa' not in globals():
                    raise IOException('Unknown resource type {} and pyvisa '
                                      'unavailable'.format(res_type))
                else:
                    # at least attempt to connect with PyVISA
                    self._interface = pyvisa.PyVisaInstrument(resource)
            elif self._prefer_pyvisa and 'pyvisa' in globals():
                self._interface = pyvisa.PyVisaInstrument(resource)
            else:
                # interface will be set within the init method
                res_type_init_methods[res_type](resource)

        # save the resource string to the class attribute
        self.resource_descriptor = resource
        self._initialized = True

    def _init_tcpip_resource(self, resource):
        """Sets the _interface with a TCPIP resource

        Parameters:
            resource: the resource string of the instrument

        Returns:
            None: this method does not return a value

        Raises:
            IOException: if the resource is invalid
        """
        if 'vxi11' in globals():
            # connect with VXI-11
            self._interface = vxi11.Instrument(resource)
        elif 'pyvisa' in globals():
            # connect with PyVISA
            self._interface = pyvisa.PyVisaInstrument(resource)
        else:
            raise IOException('Cannot use resource {}'.format(resource))

    def _init_usb_resource(self, resource):
        """Sets the _interface with a USB resource

        Parameters:
            resource: the resource string of the instrument

        Returns:
            None: this method does not return a value

        Raises:
            IOException: if the resource is invalid
        """
        if 'usbtmc' in globals():
            # connect with USBTMC
            self._interface = usbtmc.Instrument(resource)
        elif 'pyvisa' in globals():
            # connect with PyVISA
            self._interface = pyvisa.PyVisaInstrument(resource)
        else:
            raise IOException('Cannot use resource type {}'.format(resource))

    def _init_gpib_resource(self, resource):
        """Sets the _interface with a GPIB resource

        Parameters:
            resource: the resource string of the instrument

        Returns:
            None: this method does not return a value

        Raises:
            IOException: if the resource is invalid
        """
        if 'linuxgpib' in globals():
            # connect with linux-gpib
            self._interface = linuxgpib.LinuxGpibInstrument(resource)
        elif 'pyvisa' in globals():
            # connect with PyVISA
            self._interface = pyvisa.PyVisaInstrument(resource)
        else:
            raise IOException('Cannot use resource type {}'.format(resource))

    def _init_asrl_resource(self, resource):
        # Serial connection
        if 'pyserial' in globals():
            # connect with PySerial
            self._interface = pyserial.SerialInstrument(resource)
        elif 'pyvisa' in globals():
            # connect with PyVISA
            self._interface = pyvisa.PyVisaInstrument(resource)
        else:
            raise IOException('Cannot use resource type {}'.format(resource))

    def _set_channels(self, channel_names=[]):
        self.channels = []
        self._channel_names = []
        if not channel_names:
            for i in range(self._channel_count):
                channel_names.append("channel{}".format(i+1))

        for channel_name in channel_names:
            channel = Channel(channel_name)
            self.channels.append(channel)
            self._channel_names.append(channel.name)

    def simulate(self):
        self._driver_operation_simulate = True

    def _read_raw(self, num=-1):
        "Read binary data from instrument"
        if self._driver_operation_simulate:
            return b''

        if not self._initialized or self._interface is None:
            raise NotInitializedException()
        return self._interface.read_raw(num)

    def _read_ieee_block(self):
        "Read IEEE block"
        # IEEE block binary data is prefixed with #lnnnnnnnn
        # where l is length of n and n is the
        # length of the data
        # ex: #800002000 prefixes 2000 data bytes

        data = self._read_raw(1)

        if len(data) == 0:
            return b''

        while data != b'#':
            data = self._read_raw(1)

        l = int(self._read_raw(1))
        if l > 0:
            num = int(self._read_raw(l))
            raw_data = self._read_raw(num)
        else:
            raw_data = self._read_raw()

        return raw_data

    def _write_raw(self, data):
        "Write binary data to instrument"
        if self._driver_operation_simulate:
            print("[simulating] Call to write_raw")
            return
        if not self._initialized or self._interface is None:
            raise NotInitializedException()
        self._interface.write_raw(data)

    def _ask_raw(self, data, num=-1):
        "Write then read binary data"
        if self._driver_operation_simulate:
            print("[simulating] Call to ask_raw")
            return b''
        if not self._initialized or self._interface is None:
            raise NotInitializedException()

        if hasattr(self._interface, 'ask_raw'):
            return self._interface.ask_raw(data, num)
        else:
            # if interface does not implement ask_raw, emulate it
            self._write_raw(data)
            return self._read_raw(num)

    def _ask_for_ieee_block(self, data, encoding = 'utf-8'):
        "Write string then read IEEE block"
        self._write(data, encoding)
        return self._read_ieee_block()

    def _write(self, data, encoding = 'utf-8'):
        "Write string to instrument"
        if self._driver_operation_simulate:
            print("[simulating] Write (%s) '%s'" % (encoding, data))
            return
        if not self._initialized or self._interface is None:
            raise NotInitializedException()
        try:
            self._interface.write(data, encoding)
        except AttributeError:
            if type(data) is tuple or type(data) is list:
                # recursive call for a list of commands
                for data_i in data:
                    self._write(data_i, encoding)
                return

            self._write_raw(str(data).encode(encoding))

    def _read(self, num=-1, encoding = 'utf-8'):
        "Read string from instrument"
        if self._driver_operation_simulate:
            print("[simulating] Read (%s)" % encoding)
            return ''
        if not self._initialized or self._interface is None:
            raise NotInitializedException()
        try:
            return self._interface.read(num, encoding)
        except AttributeError:
            return self._read_raw(num).decode(encoding).rstrip('\r\n')

    def _ask(self, data, num=-1, encoding = 'utf-8'):
        "Write then read string"
        if self._driver_operation_simulate:
            print("[simulating] Ask (%s) '%s'" % (encoding, data))
            return ''
        if not self._initialized or self._interface is None:
            raise NotInitializedException()
        try:
            return self._interface.ask(data, num, encoding)
        except AttributeError:
            # if interface does not implement ask, emulate it
            if type(data) is tuple or type(data) is list:
            #    # recursive call for a list of commands
                val = list()
                for data_i in data:
                    val.append(self._ask(data_i, num, encoding))
                return val

            self._write(data, encoding)
            return self._read(num, encoding)


class TraceY(object):
    "Y trace object"
    def __init__(self):
        self.average_count = 1
        self.y_increment = 0
        self.y_origin = 0
        self.y_reference = 0
        self.y_raw = None
        self.y_hole = None

    @property
    def y(self):
        return ((self.y_raw - self.y_reference) * self.y_increment) + self.y_origin

    def __getitem__(self, index):
        y = self.y_raw[index]
        if y == self.y_hole:
            y = float('nan')
        return ((y - self.y_reference) * self.y_increment) + self.y_origin

    def __iter__(self):
        return (float('nan') if y == self.y_hole else ((y - self.y_reference) * self.y_increment + self.y_origin) for i, y in enumerate(self.y_raw))

    def __len__(self):
        return len(self.y_raw)

    def count(self):
        return len(self.y_raw)


class TraceXY(TraceY):
    """An X,Y Trace class to hold x,y data"""
    def __init__(self):
        super(TraceXY, self).__init__()
        self.x_increment = 0
        self.x_origin = 0
        self.x_reference = 0

    @property
    def x(self):
        return ((range(len(self.y_raw)) - self.x_reference) * self.x_increment) + self.x_origin

    @property
    def t(self):
        return self.x

    def __getitem__(self, index):
        y = self.y_raw[index]
        if y == self.y_hole:
            y = float('nan')
        return (((index - self.x_reference) * self.x_increment) + self.x_origin, ((y - self.y_reference) * self.y_increment) + self.y_origin)

    def __iter__(self):
        return ((((i - self.x_reference) * self.x_increment) + self.x_origin, float('nan') if y == self.y_hole else ((y - self.y_reference) * self.y_increment) + self.y_origin) for i, y in enumerate(self.y_raw))
