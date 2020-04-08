# For Rigol DS2000 Family Instrument Command Handling

from instruments.base import ValueNotSupportedException
from instruments.rigol import RigolInstrument


class RigolDS2000(RigolInstrument):

    def __init__(self, *args, **kwargs):
        super(RigolDS2000, self).__init__(*args, **kwargs)

    def fetch_screenshot(self, format='bmp', invert=False):
        if self._driver_operation_simulate:
            return b''

        if format not in self._display_screenshot_image_format_mapping:
            raise ValueNotSupportedException()

        self._write(":display:data?")
        return self._read_ieee_block()
