"""Wake word detection utilities

Shared utilities for wake word detection and model management.
Following KISS and DRY principles - extracted from wake_word_listener.py and tests/test_utils.py.
"""

import numpy as np
import config


def reset_wake_word_model(model):
    """
    Reset wake word model state by feeding silence.

    Prevents state carry-over between detections by clearing internal buffers.
    Based on OpenWakeWord best practices.

    Args:
        model: OpenWakeWord model instance with predict() method

    Example:
        from openwakeword.model import Model
        model = Model(wakeword_models=["alexa_v0.1"])
        reset_wake_word_model(model)
    """
    silence = np.zeros(
        config.CHUNK * config.WAKE_WORD_MODEL_RESET_SILENCE_CHUNKS,
        dtype=np.int16
    )
    for _ in range(config.WAKE_WORD_MODEL_RESET_ITERATIONS):
        model.predict(silence)
