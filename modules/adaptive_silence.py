from dataclasses import dataclass
from typing import Optional


@dataclass
class AdaptiveSilenceConfig:
    ambient_alpha: float = 0.2
    silence_ratio: float = 1.4
    min_silence_rms: float = 300.0


class AdaptiveSilenceDetector:
    """
    Adaptive silence detector for end-of-speech detection.

    Uses ambient RMS tracking to treat low-energy frames as silence,
    even if VAD misclassifies them as speech.
    """

    def __init__(self, config: AdaptiveSilenceConfig):
        self.config = config
        self._ambient_rms: Optional[float] = None

    def update(self, rms: float, vad_is_speech: bool) -> tuple[bool, float]:
        """
        Update ambient estimate and return effective speech decision.

        Returns:
            (effective_is_speech, silence_threshold)
        """
        if not vad_is_speech:
            if self._ambient_rms is None:
                self._ambient_rms = rms
            else:
                alpha = self.config.ambient_alpha
                self._ambient_rms = (1 - alpha) * self._ambient_rms + alpha * rms

        ambient = self._ambient_rms or 0.0
        threshold = max(self.config.min_silence_rms, ambient * self.config.silence_ratio)
        if vad_is_speech and rms < threshold:
            return False, threshold
        return vad_is_speech, threshold

    def set_ambient(self, rms: float) -> None:
        if rms <= 0:
            return
        self._ambient_rms = rms
