import logging
import sys

_configured = False


def get_logger(name: str = "twin_mind") -> logging.Logger:
    global _configured
    if not _configured:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
            stream=sys.stderr,
        )
        _configured = True
    return logging.getLogger(name)
