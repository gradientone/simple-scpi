import ConfigParser
import errno
import os
import sys
from shutil import copy
from os.path import expanduser


HOME = expanduser("~")


def thisdir():
    """Returns the directory name of current file"""
    if getattr(sys, 'frozen', False):
        # The application is frozen
        return os.path.dirname(sys.executable)
    else:
        # The application is not frozen
        # Change this bit to match where you store your data files:
        return os.path.dirname(__file__)

SCPIDIR = thisdir()

DATADIR = os.path.join(SCPIDIR, 'data')
if not os.path.exists(DATADIR):
    try:
        os.makedirs(DATADIR)
    except OSError as e:
        print("OSError creating data directory, e: {}".format(e))
        raise
    except Exception as e:
        print("Exception creating data directory, e: {}".format(e))
        raise

LOGDIR = os.path.join(SCPIDIR, 'logs')
if not os.path.exists(LOGDIR):
    try:
        os.makedirs(LOGDIR)
    except OSError as e:
        print("OSError creating log directory, e: {}".format(e))
        raise
    except Exception as e:
        print("Exception creating log directory, e: {}".format(e))
        raise

WAVEFORM_FILE = os.path.join(DATADIR, 'waveform.json')
SCREENSHOT_FILE = os.path.join(DATADIR, 'screenshot.png')
COMMAND_TIMEOUT = 60
SCRIPT_TIMEOUT = 3600
MAX_LOGFILE_SIZE = 2000000

# keys of known instrument_manufacturer strings with
# values of GradientOne manufacturer strings
KNOWN_MANF_DICT = {
    'Rigol': 'Rigol',
    'Rigol Technologies': 'Rigol',
    'Keysight': 'Keysight',
    'Keysight Technologies': 'Keysight',
    'Copley': 'Copley',
    'Tektronix': 'Tektronix',
    'Agilent': 'Agilent',
    'Agilent Technologies': 'Agilent',
    'simulate': 'simulate',
}


# sets the number of significant digits to round measurement values to
ROUND_SIG_DIGITS = 3

# NOTE: to force no rounding, set ROUND_SIG_DIGITS to any Falsey value.

DUT = 'SCPI_DUT'
INSTRUMENT_TYPE = 'SCPI_InstrumentType'


def find_file(fname):
    """
    Look for a configfile in relative Downloads directory.
    If found, copy it to a relative etc director and remove the original.
    A configfile should typcally be GradientOneConfig.txt
    (previously gradientoneone.cfg or gradientone_one.cfg)
    """
    etc = os.path.join(SCPIDIR, 'etc')
    downloads = os.path.join(HOME, 'Downloads')
    configfile = os.path.join(downloads, fname)
    if os.access(configfile, os.R_OK):
        try:
            os.mkdir(etc)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
        copy(configfile, etc)
        os.remove(configfile)
    configfile = os.path.join(etc, fname)
    try:
        fp = open(configfile)
    except IOError as e:
        if e.errno == errno.EACCES:
            # default data:
            default_file = os.path.join(SCPIDIR, fname)
            print("Using default data file in {}".format(default_file))
            return default_file
        # Not a permission error.
        raise
    else:
        fp.close()
        return configfile


def build_config_parser(filename='GradientOneAuthConfig.txt'):
    """Builds a ConfigParser from config file info

    Parameters:
        filename: the filename of the config file. This gets passed
            the find_file function to

    """
    cfg = ConfigParser.ConfigParser(dict_type=dict)
    cfg.optionxform = str
    cfgfile = None
    try:
        cfgfile = find_file(filename)
    except IOError:
        raise ValueError("Could not find a {} file. Please download "
                         "one for this machine.".format(filename))
    try:
        cfg.read(cfgfile)
    except IOError:
        raise ValueError("Could not read the {} file. Please download a "
                         "valid config file for this machine."
                         .format(filename))
    return cfg


COMMON_SETTINGS = {}

cfg = None
try:
    cfg = build_config_parser()
except ValueError as e:
    print("\nWARNING: {}".format(e))

if cfg is None:
    print("WARNING: Without a valid GradientOneAuthConfig.txt you "
          "will still be able to run commands locally, but you will not "
          "be able to make calls to the GradientOne API.\n")
else:
    try:
        COMMON_SETTINGS = cfg._sections['common']
    except KeyError as e:
        msg = ("Encountered a KeyError when reading config file.\n\n"
               "This is most likely due to missing data in the config file. "
               "Please check the config file in {} or ~/Downloads for "
               "'common' sections.\n\n ".format(SCPIDIR))
        print(msg)

if 'AUTH_TOKEN' in COMMON_SETTINGS:
    AUTH_TOKEN = COMMON_SETTINGS['AUTH_TOKEN']
else:
    AUTH_TOKEN = ''
if 'DOMAINNAME' in COMMON_SETTINGS:
    DOMAINNAME = COMMON_SETTINGS['DOMAINNAME']
else:
    DOMAINNAME = ''
if DOMAINNAME.find("localhost") == 0 or DOMAINNAME.find("127.0.0.1") == 0:
    BASE_URL = "http://" + DOMAINNAME
else:
    BASE_URL = "https://" + DOMAINNAME
