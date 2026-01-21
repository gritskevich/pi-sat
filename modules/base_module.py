from modules.logging_utils import setup_logger


class BaseModule:
    """Tiny base class for shared logger/debug wiring."""

    def __init__(self, name: str, debug: bool = False, verbose: bool = True, event_bus=None):
        self.debug = debug
        self.verbose = verbose
        self.event_bus = event_bus
        self.logger = setup_logger(name, debug=debug, verbose=verbose)
