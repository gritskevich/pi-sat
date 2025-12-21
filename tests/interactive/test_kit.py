"""
Interactive Test Kit for Pi-Sat

Manual testing suite with user interaction and feedback.
Validates hardware, user experience, and end-to-end workflows.
"""

import os
import sys
import time
import subprocess
from pathlib import Path



class Colors:
    """Terminal colors for pretty output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    """Print colored header"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(70)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 70}{Colors.END}\n")


def print_test(text):
    """Print test name"""
    print(f"{Colors.BOLD}{Colors.BLUE}➤ {text}{Colors.END}")


def print_instruction(text):
    """Print user instruction"""
    print(f"{Colors.YELLOW}  ℹ {text}{Colors.END}")


def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}  ✓ {text}{Colors.END}")


def print_failure(text):
    """Print failure message"""
    print(f"{Colors.RED}  ✗ {text}{Colors.END}")


def ask_yes_no(question):
    """Ask yes/no question"""
    while True:
        answer = input(f"{Colors.YELLOW}  ? {question} (y/n): {Colors.END}").strip().lower()
        if answer in ['y', 'yes']:
            return True
        elif answer in ['n', 'no']:
            return False
        print("  Please answer 'y' or 'n'")


def ask_rating(question, scale=5):
    """Ask for rating on scale"""
    while True:
        try:
            answer = input(f"{Colors.YELLOW}  ? {question} (1-{scale}): {Colors.END}").strip()
            rating = int(answer)
            if 1 <= rating <= scale:
                return rating
            print(f"  Please enter a number between 1 and {scale}")
        except ValueError:
            print("  Please enter a valid number")


class InteractiveTestKit:
    """Interactive test suite for Pi-Sat"""

    def __init__(self):
        self.results = {
            'passed': 0,
            'failed': 0,
            'skipped': 0,
        }

    def run_all_tests(self):
        """Run complete interactive test suite"""
        print_header("Pi-Sat Interactive Test Kit")

        print("This test suite will validate:")
        print("  • Audio hardware (microphone, speaker)")
        print("  • Text-to-speech (Piper TTS)")
        print("  • Wake word detection")
        print("  • Full voice command pipeline")
        print("  • MPD music playback (if configured)")
        print()

        if not ask_yes_no("Ready to begin testing?"):
            print("\nTest suite cancelled by user.")
            return

        # Run tests
        self.test_speaker()
        self.test_microphone()
        self.test_tts()
        self.test_wake_word()
        self.test_stt()
        self.test_full_command()
        self.test_mpd_playback()

        # Summary
        self.print_summary()

    def test_speaker(self):
        """Test speaker output"""
        print_header("Test 1: Speaker Output")

        print_test("Testing speaker with test tone")
        print_instruction("You should hear a 1-second tone")

        try:
            # Generate 1-second 440Hz tone
            subprocess.run([
                'speaker-test',
                '-t', 'sine',
                '-f', '440',
                '-l', '1'
            ], check=True, capture_output=True)

            if ask_yes_no("Did you hear the tone?"):
                print_success("Speaker test passed")
                self.results['passed'] += 1
            else:
                print_failure("Speaker test failed - no audio heard")
                self.results['failed'] += 1

        except subprocess.CalledProcessError:
            print_failure("Speaker test failed - command error")
            self.results['failed'] += 1
        except FileNotFoundError:
            print_instruction("speaker-test not found, using aplay instead")

            try:
                # Fallback: use aplay with generated tone
                subprocess.run([
                    'sh', '-c',
                    'ffmpeg -f lavfi -i "sine=frequency=440:duration=1" -f wav - 2>/dev/null | aplay -q'
                ], shell=False, check=True)

                if ask_yes_no("Did you hear the tone?"):
                    print_success("Speaker test passed")
                    self.results['passed'] += 1
                else:
                    print_failure("Speaker test failed - no audio heard")
                    self.results['failed'] += 1

            except Exception as e:
                print_failure(f"Speaker test failed: {e}")
                self.results['failed'] += 1

    def test_microphone(self):
        """Test microphone recording and playback"""
        print_header("Test 2: Microphone Input")

        print_test("Testing microphone recording")
        print_instruction("Recording 3 seconds of audio...")
        print_instruction("Please say: 'Testing microphone one two three'")

        temp_file = '/tmp/pisat_mic_test.wav'

        try:
            time.sleep(1)  # Brief pause
            print_instruction("Recording NOW...")

            # Record 3 seconds
            subprocess.run([
                'arecord',
                '-d', '3',
                '-f', 'cd',
                '-t', 'wav',
                temp_file
            ], check=True)

            print_success("Recording completed")
            print_instruction("Playing back recording...")

            # Playback
            subprocess.run(['aplay', temp_file], check=True)

            # User feedback
            if ask_yes_no("Did you hear your voice clearly?"):
                quality = ask_rating("Rate audio quality", scale=5)
                if quality >= 3:
                    print_success(f"Microphone test passed (quality: {quality}/5)")
                    self.results['passed'] += 1
                else:
                    print_failure(f"Microphone quality low ({quality}/5)")
                    self.results['failed'] += 1
            else:
                print_failure("Microphone test failed - no audio heard")
                self.results['failed'] += 1

        except Exception as e:
            print_failure(f"Microphone test failed: {e}")
            self.results['failed'] += 1

        finally:
            # Cleanup
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def test_tts(self):
        """Test text-to-speech"""
        print_header("Test 3: Text-to-Speech (Piper)")

        print_test("Testing Piper TTS")

        test_phrases = [
            "Hello! I am Pi-Sat, your voice-controlled music player.",
            "The quick brown fox jumps over the lazy dog.",
            "Testing numbers: one, two, three, four, five.",
        ]

        total_tests = len(test_phrases)
        passed = 0

        for i, phrase in enumerate(test_phrases, 1):
            print_instruction(f"Test phrase {i}/{total_tests}: '{phrase}'")
            print_instruction("Generating speech...")

            try:
                # Use Piper TTS module
                from modules.piper_tts import speak

                success = speak(phrase)

                if success:
                    if ask_yes_no("Was the speech clear and intelligible?"):
                        passed += 1
                    else:
                        print_failure("Speech quality issue")
                else:
                    print_failure("TTS generation failed")

            except Exception as e:
                print_failure(f"TTS error: {e}")

        if passed == total_tests:
            print_success(f"TTS test passed ({passed}/{total_tests} phrases)")
            self.results['passed'] += 1
        elif passed > 0:
            print_failure(f"TTS test partial ({passed}/{total_tests} phrases)")
            self.results['failed'] += 1
        else:
            print_failure("TTS test failed completely")
            self.results['failed'] += 1

    def test_wake_word(self):
        """Test wake word detection"""
        print_header("Test 4: Wake Word Detection")

        print_test("Testing wake word: 'Alexa'")
        print_instruction("This will start the wake word listener for 10 seconds")
        print_instruction("Say 'Alexa' when you're ready")

        if not ask_yes_no("Start wake word test?"):
            print_instruction("Test skipped")
            self.results['skipped'] += 1
            return

        try:
            # Import wake word listener
            from modules.wake_word_listener import WakeWordListener

            detected = []

            def on_detection():
                detected.append(time.time())
                print_success("Wake word detected!")

            listener = WakeWordListener(verbose=False)
            listener._notify_orchestrator = on_detection

            print_instruction("Listening for wake word (say 'Alexa')...")

            # Listen for 10 seconds
            listener.start_listening(duration=10)

            if detected:
                print_success(f"Wake word detected {len(detected)} time(s)")

                if len(detected) == 1:
                    print_success("Wake word test passed")
                    self.results['passed'] += 1
                else:
                    print_instruction(f"Multiple detections: {len(detected)}")
                    if ask_yes_no("Were all detections correct?"):
                        print_success("Wake word test passed")
                        self.results['passed'] += 1
                    else:
                        print_failure("False positive detections")
                        self.results['failed'] += 1
            else:
                print_failure("Wake word not detected")
                if ask_yes_no("Did you say 'Alexa' clearly?"):
                    print_failure("Wake word detection failed")
                    self.results['failed'] += 1
                else:
                    print_instruction("Test inconclusive - user did not speak")
                    self.results['skipped'] += 1

        except Exception as e:
            print_failure(f"Wake word test error: {e}")
            self.results['failed'] += 1

    def test_stt(self):
        """Test speech-to-text"""
        print_header("Test 5: Speech-to-Text (Hailo Whisper)")

        print_test("Testing speech-to-text transcription")

        if not ask_yes_no("Do you want to test STT?"):
            print_instruction("Test skipped")
            self.results['skipped'] += 1
            return

        test_phrases = [
            "Play maman",
            "Volume up",
            "I love this song",
        ]

        print_instruction(f"You will speak {len(test_phrases)} phrases")

        try:
            from modules.speech_recorder import SpeechRecorder
            from modules.hailo_stt import HailoSTT

            recorder = SpeechRecorder(debug=False)
            stt = HailoSTT(debug=False)

            if not stt.is_available():
                print_failure("STT not available (Hailo not loaded)")
                self.results['skipped'] += 1
                return

            correct = 0

            for i, expected in enumerate(test_phrases, 1):
                print_instruction(f"\nPhrase {i}/{len(test_phrases)}: Say '{expected}'")
                time.sleep(1)
                print_instruction("Recording...")

                audio_data = recorder.record_command()

                print_instruction("Transcribing...")
                transcribed = stt.transcribe(audio_data)

                print(f"  Transcribed: '{transcribed}'")

                if ask_yes_no("Is this correct?"):
                    correct += 1

            if correct == len(test_phrases):
                print_success(f"STT test passed ({correct}/{len(test_phrases)})")
                self.results['passed'] += 1
            elif correct > 0:
                print_failure(f"STT partial ({correct}/{len(test_phrases)})")
                self.results['failed'] += 1
            else:
                print_failure("STT test failed")
                self.results['failed'] += 1

        except Exception as e:
            print_failure(f"STT test error: {e}")
            self.results['failed'] += 1

    def test_full_command(self):
        """Test full voice command pipeline"""
        print_header("Test 6: Full Voice Command Pipeline")

        print_test("Testing complete workflow")
        print_instruction("This tests: Wake word → Recording → STT → Response")

        if not ask_yes_no("Run full command test?"):
            print_instruction("Test skipped")
            self.results['skipped'] += 1
            return

        print_instruction("Implementation coming soon...")
        print_instruction("This will test the complete orchestrator flow")
        self.results['skipped'] += 1

    def test_mpd_playback(self):
        """Test MPD music playback"""
        print_header("Test 7: MPD Music Playback")

        print_test("Testing MPD music control")

        # Check if MPD is running
        try:
            result = subprocess.run(['mpc', 'status'], capture_output=True, check=True)
            print_success("MPD is running")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print_failure("MPD is not running or not installed")
            self.results['skipped'] += 1
            return

        if not ask_yes_no("Test MPD playback?"):
            print_instruction("Test skipped")
            self.results['skipped'] += 1
            return

        print_instruction("Implementation coming soon...")
        print_instruction("This will test MPD play/pause/skip controls")
        self.results['skipped'] += 1

    def print_summary(self):
        """Print test summary"""
        print_header("Test Summary")

        total = self.results['passed'] + self.results['failed'] + self.results['skipped']

        print(f"Total Tests:   {total}")
        print(f"{Colors.GREEN}Passed:        {self.results['passed']}{Colors.END}")
        print(f"{Colors.RED}Failed:        {self.results['failed']}{Colors.END}")
        print(f"{Colors.YELLOW}Skipped:       {self.results['skipped']}{Colors.END}")

        if self.results['failed'] == 0 and self.results['passed'] > 0:
            print(f"\n{Colors.GREEN}{Colors.BOLD}✓ All tests passed!{Colors.END}")
        elif self.results['failed'] > 0:
            print(f"\n{Colors.RED}{Colors.BOLD}✗ Some tests failed{Colors.END}")
        else:
            print(f"\n{Colors.YELLOW}⊘ No tests completed{Colors.END}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Pi-Sat Interactive Test Kit')
    parser.add_argument(
        '--test',
        choices=['speaker', 'microphone', 'tts', 'wake_word', 'stt', 'full', 'mpd'],
        help='Run specific test only'
    )

    args = parser.parse_args()

    kit = InteractiveTestKit()

    if args.test:
        # Run specific test
        test_method = getattr(kit, f'test_{args.test}')
        test_method()
        kit.print_summary()
    else:
        # Run all tests
        kit.run_all_tests()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Test interrupted by user{Colors.END}")
        sys.exit(1)
