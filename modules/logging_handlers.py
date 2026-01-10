import logging
import sys
from typing import List

import config


def build_handlers(verbose: bool = True) -> List[logging.Handler]:
    if not verbose:
        return []

    outputs = getattr(config, "LOG_OUTPUTS", "stdout")
    parts = [part.strip().lower() for part in outputs.split(",") if part.strip()]
    handlers: List[logging.Handler] = []

    for part in parts:
        if part == "stdout":
            handlers.append(logging.StreamHandler(sys.stdout))
        elif part == "stderr":
            handlers.append(logging.StreamHandler(sys.stderr))
        elif part == "file":
            handlers.append(logging.FileHandler(getattr(config, "LOG_FILE_PATH", "pisat.log")))

    if not handlers:
        handlers.append(logging.StreamHandler(sys.stdout))

    return handlers
