import logging
import os
import sys
from typing import List

import config


def build_handlers(verbose: bool = True, debug: bool = False) -> List[logging.Handler]:
    if not verbose:
        return []

    if debug:
        outputs = getattr(config, "DEBUG_LOG_OUTPUTS", getattr(config, "LOG_OUTPUTS", "stdout"))
        log_file_path = getattr(config, "DEBUG_LOG_FILE_PATH", getattr(config, "LOG_FILE_PATH", "pisat.log"))
    else:
        outputs = getattr(config, "LOG_OUTPUTS", "stdout")
        log_file_path = getattr(config, "LOG_FILE_PATH", "pisat.log")
    parts = [part.strip().lower() for part in outputs.split(",") if part.strip()]
    handlers: List[logging.Handler] = []

    for part in parts:
        if part == "stdout":
            handlers.append(logging.StreamHandler(sys.stdout))
        elif part == "stderr":
            handlers.append(logging.StreamHandler(sys.stderr))
        elif part == "file":
            log_dir = os.path.dirname(log_file_path)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            handlers.append(logging.FileHandler(log_file_path))

    if not handlers:
        handlers.append(logging.StreamHandler(sys.stdout))

    return handlers
