"""
Piper TTS Module - Offline Text-to-Speech using Piper

Simple wrapper around Piper TTS for generating and playing speech.
Follows KISS principle - minimal, elegant implementation.
"""

import subprocess
import os
from pathlib import Path
from modules.logging_utils import setup_logger

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

    def speak(self, text, volume=None):
        """
        Generate speech and play via ALSA.

        Args:
            text: Text to speak
            volume: Optional volume (0-100). If None and volume_manager available,
                    uses config.TTS_VOLUME. Uses volume_manager if available.

        Returns:
            bool: True if successful, False otherwise
        """
        if not text or not text.strip():
            logger.warning("Empty text provided to speak()")
            return False

        try:
            logger.debug(f"Speaking: '{text}'")
            
            # Handle volume: use provided volume, or config.TTS_VOLUME if volume_manager available
            original_volume = None
            target_volume = volume
            
            if self.volume_manager:
                if target_volume is None:
                    # Use default TTS volume from config
                    import config
                    target_volume = config.TTS_VOLUME
                
                if target_volume is not None:
                    original_volume = self.volume_manager.get_tts_volume()
                    self.volume_manager.set_tts_volume(target_volume)
            elif volume is not None:
                logger.warning("Volume specified but no volume_manager available")

            # Use shell piping for simplicity and reliability
            # echo text | piper --output-raw | aplay
            cmd = f'''echo {subprocess.list2cmdline([text])} | \
{self.piper_binary} --model {subprocess.list2cmdline([str(self.model_path)])} --output-raw | \
aplay -D {self.output_device} -r 22050 -f S16_LE -c 1 -q'''

            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                logger.error(f"Speech command failed (code {result.returncode})")
                if result.stderr:
                    logger.debug(f"Error output: {result.stderr}")
                if original_volume is not None and self.volume_manager:
                    self.volume_manager.set_tts_volume(original_volume)
                return False

            # Restore original volume if changed
            if original_volume is not None and self.volume_manager:
                self.volume_manager.set_tts_volume(original_volume)

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
        templates = {
            'playing': "Playing {song}",
            'paused': "Paused",
            'skipped': "Skipping",
            'previous': "Going back",
            'volume_up': "Volume up",
            'volume_down': "Volume down",
            'liked': "Added to favorites",
            'favorites': "Playing favorites",
            'no_match': "I don't know that song",
            'error': "Sorry, something went wrong",
            'sleep_timer': "I'll stop in {minutes} minutes",
            'stopped': "Stopped",
            'unknown': "I didn't understand that",
        }

        template = templates.get(intent, "Okay")

        try:
            return template.format(**params)
        except KeyError as e:
            logger.warning(f"Missing parameter {e} for template '{intent}'")
            return template


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
