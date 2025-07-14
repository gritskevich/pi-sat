import logging
import time
import numpy as np
from openwakeword.model import Model
import openwakeword.utils
import config

logger = logging.getLogger(__name__)

class WakeWordDetector:
    def __init__(self):
        self.model = None
        self.last_detection_time = time.time() - config.WAKE_WORD_COOLDOWN
        
    def _ensure_model_loaded(self):
        if self.model is None:
            logger.info("Loading wake word model...")
            openwakeword.utils.download_models()
            self.model = Model(
                wakeword_models=config.WAKE_WORD_MODELS if config.WAKE_WORD_MODELS else None,
                inference_framework='tflite'
            )
    
    def detect(self, audio_frame):
        self._ensure_model_loaded()
        prediction = self.model.predict(audio_frame)
        
        for wake_word, confidence in prediction.items():
            if confidence > config.WAKE_WORD_THRESHOLD:
                if time.time() - self.last_detection_time >= config.WAKE_WORD_COOLDOWN:
                    self.last_detection_time = time.time()
                    logger.info(f"Wake word detected! (confidence: {confidence:.2f})")
                    return True
        return False
    
    def reset_after_command(self):
        """Reset detector state after command processing"""
        self.last_detection_time = time.time()
        
        if self.model:
            # Flush model state with silence
            silence_chunk = np.zeros(320, dtype=np.int16)
            for _ in range(25):  # 500ms of silence to flush state
                self.model.predict(silence_chunk) 