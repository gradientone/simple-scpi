# Used to lookup the right instrument class based on the
# instrument model and manufacturer parameters

import collections
from instruments import base
from instruments.rigol import RigolInstrument
from instruments.agilent import AgilentInstrument
from instruments.tektronix import TektronixInstrument
from instruments.rigolDS2000 import RigolDS2000
from instruments.tektronixDPO5000 import TektronixDPO5000
from instruments.instrument_utils import InstrumentConnectionError
from scpi_logger import logger


class InstrumentAnalyzer(object):
    """Analyzes an ambiguous instrument to determine usage"""

    def open_instrument(self, raw_instr):
        """Opens the instrument with the right driver

        Summary:
            Given a raw unidentified instrument, this
            analyzes the instrument to get its identity data
            and uses that to look up the right driver class
            to send commands with. The driver class is then
            used to instantiate the instrument with the
            resource_descriptor (aka the address)

        Parameters:
            raw_instr: the raw unidentified instrument

        Returns:
            instrument: the opened instrument that can accept commands
        """
        id_dict = self.identify_instrument(raw_instr)
        driver_cls = self._driver_from_id_dict(id_dict)
        instrument = driver_cls(id_dict['resource_descriptor'])
        instrument.id_dict = id_dict
        return instrument

    def identify_instrument(self, instrument):
        """Interrogates instrument for id data

        Summary:
            Asks the instrument for identity data

        Parameters:
            A vxi11 instrument

        Returns:
            an identity dictionary about an instrument
        """
        # if it's already been identified, just return the id dict
        if hasattr(instrument, 'id_dict') and instrument.id_dict:
            return instrument.id_dict
        else:
            id_str = self._get_id_string_from_instrument(instrument)
            id_dict = self._identity_string_to_dict(id_str)
            id_dict['resource_descriptor'] = instrument.resource_descriptor
            return id_dict

    def _driver_from_id_dict(self, id_dict):
        driver = self._manf_model_driver_lookup(id_dict['manufacturer'],
                                                id_dict['model'])
        return driver

    def _get_id_string_from_instrument(self, instrument):
        identity_string = ''
        try:
            identity_string = instrument.ask("*IDN?")
        except Exception as e:
            print("Unexpected error creating Instrument with err: {}; "
                  .format(e))
        return identity_string

    def _identity_string_to_dict(self, identity_string, connection='eth0'):
        """Returns a defaultdict with the instrument data

        If no instrument data can be found, this returns an empty defaultdict
        """
        defdict = collections.defaultdict(str)
        identity_parts = identity_string.split(',')
        if len(identity_parts) < 3:
            print("Invalid identity data: {};".format(identity_parts))
            raise InstrumentConnectionError

        manufacturer = identity_parts[0].title()
        model = identity_parts[1]
        instrument_dict = {
            'instrument_type': manufacturer + model,
            'manufacturer': manufacturer,
            'model': model,
            'connection': connection,
            'serial': identity_parts[2],
            'id': manufacturer + model + ':' + identity_parts[2]
        }
        defdict.update(instrument_dict)
        return defdict

    def _manf_model_driver_lookup(self, manf, model):
        """Looks up the instrument driver class to use

        Parameters:
            manf: string with the manufacturer name
            model: string with the model name

        Returns:
            a class that most closely matches the manf and model
            args that are passed. At the very least this will be
            an Instrument class, though it could also be a more
            precise match like a RigolDS2000. This will just
            return the instrument class, not an instance, so the
            class will still need to be instantiated before commands
            can be passed to the real instrument.
        """
        manf = manf.lower()
        model = model.lower()
        i_key = manf + '_' + model
        instr_dict = {
            'agilent': AgilentInstrument,
            'rigol': RigolInstrument,
            'rigol technologies': RigolInstrument,
            'rigol_ds2000': RigolDS2000,
            'tektronix': TektronixInstrument,
            'tektronix_dpo5000': TektronixDPO5000,
        }

        while i_key not in instr_dict:
            i_key = i_key[0:len(i_key) - 1]
            if i_key == '':
                break

        # check for most specific the manf and model match first
        if i_key in instr_dict:
            return instr_dict[i_key]
        # else check for at least a manufacter match for next best
        elif manf in instr_dict:
            return instr_dict[manf]
        # else by default just return an Instrument class
        else:
            logger.info("Using default Instrument class. "
                        "Only basic SCPI command strings are supported.")
            return base.Instrument

def test():
    manf = 'rohde&schwarz'
    model = 'hmc8042'
    logger.info("Testing InstrumentAnalyzer manufacturer "
                "and model lookup")
    response = InstrumentAnalyzer()._manf_model_driver_lookup(manf, model)
    print("response: {}".format(response))
    # because rohde&schwarze is not in the InstrumentAnalyzer instr_dict,
    # we expect the base Instrument class
    assert response == base.Instrument
