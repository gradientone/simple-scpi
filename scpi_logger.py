import datetime
import logging
import os


ALLOWED_FILESIZE = 2000000
HOME = os.path.expanduser("~")
SCPIDIR = os.path.join(HOME, 'scpi')
if not os.path.exists(SCPIDIR):
    try:
        os.makedirs(SCPIDIR)
    except OSError as e:
        print("OSError creating log directory, e: {}".format(e))
        raise
    except Exception as e:
        print("Exception creating log directory, e: {}".format(e))
        raise


def purge_logfile(file):
    if not os.path.isfile(file):
        return
    try:
        os.remove(file)
    except OSError as e:
        print("OSError in purge_logfile. Err: {}".format(e))
        raise
    except Exception as e:
        print("Unexpected purge logfile exception! {}".format(e))
        raise


def rotate_logfiles(original_file, max_num_files=10):
    """Creates a new logfile if needed. Purges old ones if needed.

    Returns the new log file.
    """
    for i in range(max_num_files):
        file_num = i + 1
        nextlogfile = original_file + "." + str(file_num)
        if not os.path.isfile(nextlogfile):
            break
        if os.stat(nextlogfile).st_size < int(ALLOWED_FILESIZE):
            # purge the oldest file so that it's ready next rotate
            if file_num < int(max_num_files):
                file_num += 1
                purge_logfile(original_file + "." + str(file_num))
            # break to return nextlogfile
            break
        # if all allowed files are full, purge and original
        if file_num == int(max_num_files):
            purge_logfile(original_file)
            nextlogfile = original_file
    return nextlogfile


def get_logger(file_lvl=logging.DEBUG,
               loggername='scpi_runner.log',
               console_lvl=logging.INFO,
               verbose=True,):
    """Returns the logger for client logs

    If verbose is True, the console will print debug level
    """
    _logger = logging.getLogger(loggername)

    # check if the logger already exists (avoids duplicate logs)
    if len(_logger.handlers) > 0:
        return _logger

    _logger.setLevel(logging.DEBUG)
    _logger.propagate = False
    logger_file = os.path.join(SCPIDIR, loggername)

    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    initmsg = now + " :: [ INIT ] Initializing {}\n".format(loggername)
    # check if file exists
    if not os.path.isfile(logger_file):
        with open(logger_file, 'w') as f:
            f.write(initmsg)

    # check logfile size and rotate if needed
    if os.stat(logger_file).st_size > int(ALLOWED_FILESIZE):
        logger_file = rotate_logfiles(logger_file)

    # create file handler
    console_handler = logging.StreamHandler()  # by default, sys.stderr
    file_handler = logging.FileHandler(logger_file)

    # set logging levels
    console_handler.setLevel(console_lvl)
    file_handler.setLevel(file_lvl)

    # create logging format
    formatter = logging.Formatter(
        '%(asctime)s :: [ %(levelname)s ] %(message)s',
        '%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    # Note verbose flag will set the console_lvl to the debug
    if verbose:
        console_handler.setLevel(logging.DEBUG)

    _logger.addHandler(console_handler)
    _logger.addHandler(file_handler)

    return _logger
