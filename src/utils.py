from threading import Thread
import logging
import sys
from typing import Union

_logger: logging.Logger = None


def run_thread(function: callable, *args) -> None:
    Thread(target=function, args=args, daemon=True).start()


def get_logger() -> logging.Logger:
    global _logger
    if _logger is None:
        logging.basicConfig(
            level=logging.DEBUG,
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        # Setup logging
        _logger = logging.getLogger('asac')
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        _logger.addHandler(handler)

        # Without this, python does some stupid magic double logging...
        _logger.propagate = False

    return _logger


def constrain(value: Union[int, float], min: Union[int, float], max: Union[int, float]) -> Union[int, float]:
    if value < min:
        return min
    if value > max:
        return max
    return value
