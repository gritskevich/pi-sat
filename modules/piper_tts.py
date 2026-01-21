"""
Piper TTS Module - Offline Text-to-Speech using Piper

Simple wrapper around Piper TTS for generating and playing speech.
Follows KISS principle - minimal, elegant implementation.
"""

import subprocess
import os
import shutil
from pathlib import Path
from modules.logging_utils import setup_logger
from modules.response_library import ResponseLibrary

logger = setup_logger(__name__)


class PiperTTS:
    """Wrapper for Piper TTS - offline text-to-speech generation"""

    def __init__(self, model_path=None, voice_model=None, output_device='default', volume_manager=None):
        """
        Initialize Piper TTS.

        Args:
            model_path: Path to .onnx voice model (overrides config)
            voice_model: Voice model name (e.g., 'en_US-lessac-medium')
            output_device: ALSA device for audio output
            volume_manager: Optional VolumeManager instance for volume control
        """
        self.output_device = output_device
        self.volume_manager = volume_manager

        # Determine model path
        if model_path:
            self.model_path = Path(model_path)
        elif voice_model:
            project_root = Path(__file__).parent.parent
            self.model_path = project_root / 'resources' / 'voices' / f'{voice_model}.onnx'
        else:
            # Use default from config
            import config
            self.model_path = Path(config.PIPER_MODEL_PATH)

        # Get Piper binary path
        import config
        self.piper_binary = config.PIPER_BINARY_PATH
        self._responses = ResponseLibrary(language=getattr(config, 'LANGUAGE', 'en'))

        # Validate setup
        self._validate()

        logger.info(f"Initialized Piper TTS with model: {self.model_path.name}")

    def _validate(self):
        """Validate Piper binary, voice model, and audio device exist"""
        if not os.path.exists(self.piper_binary):
            raise FileNotFoundError(
                f"Piper binary not found at {self.piper_binary}. "
                "Run installation: wget piper_arm64.tar.gz and install to /usr/local/bin/"
            )

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Voice model not found at {self.model_path}. "
                f"Download from: https://huggingface.co/rhasspy/piper-voices"
            )
        
        # Validate audio output device
        from modules.audio_devices import validate_alsa_device
        if not validate_alsa_device(self.output_device):
            logger.warning(
                f"ALSA device '{self.output_device}' may not be available. "
                "TTS playback may fail. Use 'aplay -l' to list available devices."
            )

    def _preprocess_text(self, text):
        """
        Preprocess text for more natural TTS.

        Args:
            text: Input text

        Returns:
            str: Preprocessed text with pauses
        """
        # Add a short leading pause for clearer starts.
        text = text.strip()
        if text and not text.startswith(","):
            text = f", {text}"

        # Replace " - " (hyphen with spaces) with ", " for natural pause
        # Example: "Louane - maman" → "Louane, maman"
        text = text.replace(" - ", ", ")

        # Add a pause before common tails to separate song name from the rest.
        text = text.replace(" pour toi", "... pour toi")
        text = text.replace(" pour vous", "... pour vous")

        # Replace standalone hyphens (less common)
        text = text.replace("-", ", ")

        return text

    def speak(self, text, volume=None):
        """
        Generate speech and play via ALSA/PulseAudio.

        SIMPLIFIED: Volume controlled by PulseAudio sink (pactl), not sox.
        All audio plays at 100% software volume; master volume controls everything.

        Args:
            text: Text to speak
            volume: DEPRECATED - ignored. Use VolumeManager for volume control.

        Returns:
            bool: True if successful, False otherwise
        """
        if not text or not text.strip():
            logger.warning("Empty text provided to speak()")
            return False

        # Preprocess text for better TTS
        text = self._preprocess_text(text)

        try:
            logger.debug(f"Speaking: '{text}'")

            # Generate raw PCM from Piper (avoid shell/echo to preserve UTF-8 accents).
            piper_proc = subprocess.run(
                [self.piper_binary, "--model", str(self.model_path), "--output-raw"],
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=30
            )

            if piper_proc.returncode != 0:
                logger.error(f"Speech command failed (code {piper_proc.returncode})")
                if piper_proc.stderr:
                    logger.debug(f"Error output: {piper_proc.stderr.decode('utf-8', errors='replace')}")
                return False

            raw_audio = piper_proc.stdout

            # Pulse/pipewire: feed raw PCM directly to pw-play (NO volume scaling)
            # ALSA: convert to WAV + resample via sox (NO volume scaling), then aplay
            if self.output_device in ("pulse", "pipewire") and shutil.which("pw-play"):
                play_proc = subprocess.run(
                    ["pw-play", "--raw", "--format", "s16", "--rate", "22050", "--channels", "1", "--volume", "1.0", "-"],
                    input=raw_audio,
                    capture_output=True,
                    timeout=30
                )
                if play_proc.returncode != 0:
                    logger.error(f"Speech playback failed (code {play_proc.returncode})")
                    if play_proc.stderr:
                        logger.debug(f"Error output: {play_proc.stderr.decode('utf-8', errors='replace')}")
                    return False
            else:
                sox_proc = subprocess.run(
                    ["sox", "-t", "raw", "-r", "22050", "-e", "signed", "-b", "16", "-c", "1", "-", "-t", "wav", "-r", "48000", "-c", "2", "-"],
                    input=raw_audio,
                    capture_output=True,
                    timeout=30
                )
                if sox_proc.returncode != 0:
                    logger.error(f"Speech conversion failed (code {sox_proc.returncode})")
                    if sox_proc.stderr:
                        logger.debug(f"Error output: {sox_proc.stderr.decode('utf-8', errors='replace')}")
                    return False

                aplay_device = "default" if self.output_device in ("pipewire", "pulse") else self.output_device
                play_proc = subprocess.run(
                    ["aplay", "-D", aplay_device, "-q"],
                    input=sox_proc.stdout,
                    capture_output=True,
                    timeout=30
                )
                if play_proc.returncode != 0:
                    logger.error(f"Speech playback failed (code {play_proc.returncode})")
                    if play_proc.stderr:
                        logger.debug(f"Error output: {play_proc.stderr.decode('utf-8', errors='replace')}")
                    return False

            logger.debug("Speech playback completed successfully")
            return True

        except subprocess.TimeoutExpired:
            logger.error("Speech timeout (>30s)")
            return False
        except Exception as e:
            logger.error(f"Error during speech: {e}")
            return False

    def generate_audio(self, text, output_path=None):
        """
        Generate speech audio to file or return raw bytes.

        Args:
            text: Text to generate speech for
            output_path: Optional path to save WAV file

        Returns:
            bytes: Raw PCM audio data if output_path is None
            bool: True if file saved successfully (when output_path provided)
        """
        if not text or not text.strip():
            logger.warning("Empty text provided to generate_audio()")
            return None if output_path is None else False

        try:
            cmd = [
                self.piper_binary,
                '--model', str(self.model_path),
                '--output-raw'
            ]

            result = subprocess.run(
                cmd,
                input=text,
                capture_output=True,
                text=False,  # Binary mode for audio
                check=True
            )

            raw_audio = result.stdout

            if output_path:
                # Convert raw PCM to WAV using sox
                wav_cmd = [
                    'sox',
                    '-r', '22050',
                    '-e', 'signed-integer',
                    '-b', '16',
                    '-c', '1',
                    '-t', 'raw',
                    '-',  # stdin
                    output_path
                ]

                subprocess.run(
                    wav_cmd,
                    input=raw_audio,
                    check=True,
                    capture_output=True
                )

                logger.debug(f"Saved audio to {output_path}")
                return True
            else:
                return raw_audio

        except subprocess.CalledProcessError as e:
            logger.error(f"Error generating audio: {e}")
            return None if output_path is None else False
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None if output_path is None else False

    def get_response_template(self, intent, **params):
        """
        Get pre-defined response for common intents.

        Args:
            intent: Intent name (e.g., 'playing', 'paused')
            **params: Parameters to format into response

        Returns:
            str: Formatted response text
        """
        response = self._responses.get(intent, fallback_key="unknown", **params)
        if response:
            return response
        logger.warning(f"Missing response template for '{intent}'")
        return ""


# Convenience function for quick speech
def speak(text, output_device='default'):
    """
    Quick speak function without creating PiperTTS instance.

    Args:
        text: Text to speak
        output_device: ALSA output device

    Returns:
        bool: True if successful
    """
    try:
        tts = PiperTTS(output_device=output_device)
        return tts.speak(text)
    except Exception as e:
        logger.error(f"Quick speak failed: {e}")
        return False


if __name__ == '__main__':
    # Test module
    import sys

    if len(sys.argv) > 1:
        test_text = ' '.join(sys.argv[1:])
    else:
        test_text = "Hello! I am Pi-Sat, your offline voice-controlled music player."

    print(f"Testing Piper TTS with: '{test_text}'")

    try:
        tts = PiperTTS()
        print(f"Using voice model: {tts.model_path}")

        success = tts.speak(test_text)

        if success:
            print("✓ Speech test successful")
            sys.exit(0)
        else:
            print("✗ Speech test failed")
            sys.exit(1)

    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
