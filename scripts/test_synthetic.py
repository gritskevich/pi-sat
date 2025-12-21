#!/usr/bin/env python3
"""
Synthetic Test - End-to-End Pipeline Test

Tests the complete voice pipeline:
1. Listen for wake word ("Alexa")
2. Play wake sound ("ding")
3. Record command (<5s or until pause)
4. Transcribe with Hailo STT
5. Speak back with Piper TTS

Runs in loop until Ctrl-C. Minimalist implementation for real hardware testing.

TROUBLESHOOTING:
- If you get HAILO_OUT_OF_PHYSICAL_DEVICES error:
  1. Check no other processes using Hailo: ps aux | grep python
  2. Kill any orphaned processes: killall python3
  3. Check Hailo device: hailortcli fw-control identify
  4. Reboot if needed
"""

import sys
import os
import signal
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.wake_word_listener import WakeWordListener
from modules.speech_recorder import SpeechRecorder
from modules.hailo_stt import HailoSTT
from modules.piper_tts import PiperTTS
import modules.audio_player as audio_player
import config


class SyntheticTest:
    """Minimalist end-to-end pipeline test"""

    def __init__(self, debug=False):
        self.debug = debug
        self.running = True

        print("=" * 60)
        print("Pi-Sat Synthetic Test - End-to-End Pipeline")
        print("=" * 60)
        print()

        # Initialize components
        print("Initializing components...")

        # Check if Hailo device is available
        print("  Checking Hailo device...")
        try:
            import subprocess
            result = subprocess.run(
                ['hailortcli', 'fw-control', 'identify'],
                capture_output=True,
                timeout=2
            )
            if result.returncode == 0:
                print("  ✓ Hailo device detected")
            else:
                print("  ⚠️  Hailo device not responding - continuing anyway")
        except Exception as e:
            print(f"  ⚠️  Could not check Hailo device: {e}")

        try:
            self.wake_word = WakeWordListener(debug=debug)
            print("  ✓ Wake word listener ready")
        except Exception as e:
            print(f"  ✗ Wake word error: {e}")
            raise

        try:
            self.recorder = SpeechRecorder(debug=False)  # No playback in test
            print("  ✓ Speech recorder ready")
        except Exception as e:
            print(f"  ✗ Recorder error: {e}")
            raise

        try:
            self.stt = HailoSTT(debug=debug)
            if not self.stt.is_available():
                print(f"  ⚠️  Hailo STT not available - attempting reload...")
                self.stt.reload()
                if not self.stt.is_available():
                    raise RuntimeError("Hailo STT unavailable after reload")
            print("  ✓ Hailo STT ready")
        except Exception as e:
            print(f"  ✗ STT error: {e}")
            raise

        try:
            # Use full model path from config
            self.tts = PiperTTS(
                model_path=config.PIPER_MODEL_PATH,
                output_device=config.PIPER_OUTPUT_DEVICE
            )
            print("  ✓ Piper TTS ready")
        except Exception as e:
            print(f"  ✗ TTS error: {e}")
            raise

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        print()
        print("=" * 60)
        print("Ready! Say 'Alexa' to test the pipeline")
        print("Press Ctrl-C to exit")
        print("=" * 60)
        print()

    def _signal_handler(self, signum, frame):
        """Handle Ctrl-C gracefully"""
        print("\n\nShutting down...")
        self.running = False
        self.cleanup()
        sys.exit(0)

    def run(self):
        """Run the test loop"""
        # Connect wake word callback
        self.wake_word._notify_orchestrator = self._on_wake_word

        try:
            # Start listening
            self.wake_word.start_listening()
        except KeyboardInterrupt:
            print("\n\nKeyboard interrupt")
            self.cleanup()
        except Exception as e:
            print(f"\n\nError: {e}")
            self.cleanup()

    def _on_wake_word(self):
        """Handle wake word detection"""
        print("\n" + "=" * 60)
        print("🔔 WAKE WORD DETECTED!")
        print("=" * 60)

        # Play wake sound
        try:
            audio_player.play_wake_sound()
            print("  ✓ Played wake sound")
        except Exception as e:
            print(f"  ⚠️  Wake sound error: {e}")

        # Record command
        print("  🎤 Recording command (max 5 seconds or until pause)...")
        try:
            # Override max recording time for this test
            original_max = config.MAX_RECORDING_TIME
            config.MAX_RECORDING_TIME = 5.0

            audio_data = self.recorder.record_command()

            # Restore original
            config.MAX_RECORDING_TIME = original_max

            if not audio_data or len(audio_data) == 0:
                print("  ✗ No audio recorded")
                return

            print(f"  ✓ Recorded {len(audio_data)} bytes")

        except Exception as e:
            print(f"  ✗ Recording error: {e}")
            return

        # Transcribe with Hailo STT
        print("  🔊 Transcribing with Hailo STT...")
        try:
            text = self.stt.transcribe(audio_data)

            if not text or not text.strip():
                print("  ✗ No text transcribed")
                # Speak error
                try:
                    self.tts.speak("Sorry, I didn't understand that")
                except:
                    pass
                return

            print(f"  ✓ Transcribed: '{text}'")

        except Exception as e:
            print(f"  ✗ STT error: {e}")
            return

        # Speak back with Piper TTS
        print("  💬 Speaking with Piper TTS...")
        try:
            response = f"You said: {text}"
            success = self.tts.speak(response)

            if success:
                print(f"  ✓ Spoke: '{response}'")
            else:
                print(f"  ✗ TTS failed")

        except Exception as e:
            print(f"  ✗ TTS error: {e}")

        print("=" * 60)
        print("✅ Pipeline complete! Ready for next wake word...")
        print()

    def cleanup(self):
        """Clean up resources"""
        print("Cleaning up...")

        try:
            if hasattr(self, 'wake_word') and self.wake_word:
                self.wake_word.stop_listening()
                print("  ✓ Wake word listener stopped")
        except Exception as e:
            print(f"  ⚠️  Wake word cleanup error: {e}")

        try:
            if hasattr(self, 'stt') and self.stt:
                self.stt.cleanup()
                print("  ✓ STT cleaned up")
        except Exception as e:
            print(f"  ⚠️  STT cleanup error: {e}")

        print("Goodbye!")


def main():
    """Main entry point"""
    debug = "--debug" in sys.argv or "-d" in sys.argv

    try:
        test = SyntheticTest(debug=debug)
        test.run()
    except KeyboardInterrupt:
        print("\n\nInterrupted")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
