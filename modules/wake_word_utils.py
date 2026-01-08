import numpy as np
import config


def reset_wake_word_model(model):
    silence = np.zeros(
        config.CHUNK * config.WAKE_WORD_MODEL_RESET_SILENCE_CHUNKS,
        dtype=np.int16
    )
    for _ in range(config.WAKE_WORD_MODEL_RESET_ITERATIONS):
        model.predict(silence)
