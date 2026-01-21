import ctypes
import os
from contextlib import contextmanager

_ALSA_ERROR_HANDLER = None


def suppress_alsa_errors() -> bool:
    """
    Disable ALSA library error logging to stderr.

    Returns:
        True if the handler was installed, False otherwise.
    """
    global _ALSA_ERROR_HANDLER
    try:
        asound = ctypes.cdll.LoadLibrary("libasound.so.2")
    except OSError:
        return False

    ERROR_HANDLER = ctypes.CFUNCTYPE(
        None, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p
    )

    def _no_op_handler(filename, line, function, err, fmt):
        return

    _ALSA_ERROR_HANDLER = ERROR_HANDLER(_no_op_handler)
    asound.snd_lib_error_set_handler(_ALSA_ERROR_HANDLER)
    return True


def suppress_jack_autostart() -> None:
    os.environ.setdefault("JACK_NO_START_SERVER", "1")
    os.environ.setdefault("JACK_START_SERVER", "0")


@contextmanager
def suppress_stderr():
    fd = None
    devnull = None
    try:
        fd = os.dup(2)
        devnull = open(os.devnull, "w")
        os.dup2(devnull.fileno(), 2)
        yield
    finally:
        if fd is not None:
            os.dup2(fd, 2)
            os.close(fd)
        if devnull:
            devnull.close()
