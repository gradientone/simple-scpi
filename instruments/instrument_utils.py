# helpers for instrument related behavior

class InstrumentConnectionError(Exception):
    def __init__(self, *args):
        super(InstrumentConnectionError, self).__init__(*args)
