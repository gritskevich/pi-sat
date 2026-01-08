"""
True E2E French Tests: Complete Pipeline with Orchestrator

Tests the FULL pipeline:
1. Wake word detection (pre-validated in audio)
2. VAD recording (FakeSpeechRecorder returns command audio)
3. Hailo STT transcription
4. Intent classification
5. Music library search
6. MPD command execution (mocked)
7. TTS response (mocked)

This validates the REAL orchestrator flow, not just component integration.
"""

import os
import json
import pytest
from pathlib import Path

import config
RUN_HAILO_TESTS = os.getenv("PISAT_RUN_HAILO_TESTS", "0") == "1"
RUN_HAILO_BACKEND = config.STT_BACKEND == "hailo"
from tests.test_utils import read_wav_mono_int16

pytestmark = [
    pytest.mark.skipif(not RUN_HAILO_TESTS, reason="Set PISAT_RUN_HAILO_TESTS=1 for Hailo E2E tests"),
    pytest.mark.skipif(not RUN_HAILO_BACKEND, reason="STT_BACKEND is not 'hailo'"),
]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
METADATA_PATH = PROJECT_ROOT / "tests" / "audio_samples" / "test_metadata.json"
SUITE_ID = "e2e_french"

def _load_suite_or_skip():
    if not METADATA_PATH.exists():
        pytest.skip(f"Missing: {METADATA_PATH}", allow_module_level=True)

    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    try:
        return metadata["suites"][SUITE_ID]
    except KeyError:
        pytest.skip(f"Missing suite '{SUITE_ID}' in {METADATA_PATH}", allow_module_level=True)


SUITE = _load_suite_or_skip()
POSITIVE_CASES = SUITE["tests"]["positive"]

INTENT_TO_MPD_COMMAND = {
    "play_music": "play",
    "play_favorites": "play_favorites",
    "pause": "pause",
    "resume": "resume",
    "stop": "stop",
    "next": "next",
    "previous": "previous",
    "volume_up": "volume_up",
    "volume_down": "volume_down",
    "add_favorite": "add_favorite",
}


class FakeSpeechRecorder:
    """Fake speech recorder that returns pre-recorded command audio."""
    def __init__(self, audio_bytes: bytes):
        self._audio_bytes = audio_bytes

    def record_command(self):
        return self._audio_bytes

    def record_from_stream(self, stream=None, input_rate=None, skip_initial_seconds=0.0):
        return self._audio_bytes


class FakeVolumeManager:
    """Fake volume manager for testing."""
    def duck_music_volume(self, duck_to=20):
        return True

    def restore_music_volume(self):
        return True


class FakeTTS:
    """Fake TTS for testing."""
    def __init__(self):
        self.spoken_texts = []

    def get_response_template(self, template_name: str, **kwargs):
        return template_name

    def speak(self, text: str):
        self.spoken_texts.append(text)
        return True


class FakeMPD:
    """Fake MPD for testing - tracks all commands."""
    def __init__(self):
        self.commands = []
        self.last_query = None
        self.last_confidence = None
        self._music_library = None
        self._responses = json.loads(
            Path(__file__).resolve().parent.parent.joinpath("resources/response_library.json").read_text(encoding="utf-8")
        )

    def _pick(self, key, **params):
        return self._responses.get("fr", {}).get(key, [""])[0].format(**params)

    def get_music_library(self):
        """Return music library for MusicResolver."""
        if self._music_library is None:
            from modules.music_library import MusicLibrary
            self._music_library = MusicLibrary()
        return self._music_library

    def play(self, query, confidence=None):
        self.commands.append(('play', query))
        self.last_query = query
        self.last_confidence = confidence
        return True, self._pick("playing_song", song=query), confidence or 1.0

    def pause(self):
        self.commands.append(('pause',))
        return True, self._pick("paused")

    def resume(self):
        self.commands.append(("resume",))
        return True, self._pick("resuming")

    def stop(self):
        self.commands.append(("stop",))
        return True, self._pick("stopped")

    def next(self):
        self.commands.append(('next',))
        return True, self._pick("next_song")

    def previous(self):
        self.commands.append(("previous",))
        return True, self._pick("previous_song")

    def volume_up(self, step=10):
        self.commands.append(('volume_up', step))
        return True, self._pick("volume_up")

    def volume_down(self, step=10):
        self.commands.append(("volume_down", step))
        return True, self._pick("volume_down")

    def play_favorites(self):
        self.commands.append(("play_favorites",))
        return True, self._pick("favorites")

    def add_to_favorites(self):
        self.commands.append(('add_favorite',))
        return True, self._pick("liked")


@pytest.fixture(scope="module")
def e2e_suite():
    """Suite metadata for DRY audio-driven tests."""
    # Skip early if audio isn't generated (folder is gitignored)
    sample = PROJECT_ROOT / POSITIVE_CASES[0]["file"]
    if not sample.exists():
        pytest.skip("Test audio not generated. Run: python scripts/generate_e2e_french_tests.py")

    return SUITE


@pytest.fixture(scope="module")
def hailo_stt():
    """Real Hailo STT instance."""
    from modules.hailo_stt import HailoSTT

    stt = HailoSTT(language="fr")
    if not stt.is_available():
        pytest.skip("Hailo STT not available (model/pipeline not loaded)")

    yield stt
    stt.cleanup()


@pytest.fixture(scope="module")
def intent_engine():
    """Real Intent engine instance."""
    from modules.intent_engine import IntentEngine
    return IntentEngine(language="fr")




def load_command_audio(test_case, suite):
    """Load command audio (skip wake word based on metadata)."""
    command_start_s = test_case.get("command_start_s", suite["structure"]["command_start_s"])
    audio_path = PROJECT_ROOT / test_case["file"]

    # Load full audio
    audio_data, sample_rate = read_wav_mono_int16(str(audio_path))

    # Skip wake word + pause
    command_start = int(command_start_s * sample_rate)
    command_audio = audio_data[command_start:]

    # Convert to int16 PCM bytes
    return command_audio.tobytes()


class TestFrenchE2ETrue:
    """True E2E tests - Full orchestrator pipeline."""

    @pytest.mark.parametrize("test_case", POSITIVE_CASES, ids=lambda c: f"{c['id']:02d}_{c['intent']}")
    def test_full_pipeline(self, test_case, e2e_suite, hailo_stt, intent_engine):
        """Test complete pipeline: Audio → STT → Intent → MusicResolver → MPD → TTS"""
        from modules.command_processor import CommandProcessor

        # Load command audio (wake word already detected, skip it)
        command_bytes = load_command_audio(test_case, e2e_suite)

        # Create fake dependencies
        fake_recorder = FakeSpeechRecorder(command_bytes)
        fake_volume = FakeVolumeManager()
        fake_tts = FakeTTS()
        fake_mpd = FakeMPD()

        # Create CommandProcessor with real STT/Intent/MusicLibrary + fakes
        processor = CommandProcessor(
            speech_recorder=fake_recorder,
            stt_engine=hailo_stt,
            intent_engine=intent_engine,
            mpd_controller=fake_mpd,
            tts_engine=fake_tts,
            volume_manager=fake_volume,
            debug=True,
            verbose=False
        )

        # EXECUTE FULL PIPELINE
        success = processor.process_command()

        # Validate pipeline executed
        assert success, f"Pipeline failed for: {test_case['full_phrase']}"

        # Validate each step using internal methods (like test_orchestrator_e2e.py)
        transcript = processor._transcribe_audio(command_bytes)
        assert transcript and transcript.strip(), "Empty transcription"

        intent = processor._classify_intent(transcript)
        assert intent is not None, f"No intent for: {transcript}"
        assert intent.intent_type == test_case["intent"], f"Wrong intent: {intent.intent_type}"

        # Validate MPD was called with play command
        assert len(fake_mpd.commands) > 0, "MPD not called"
        expected_command = INTENT_TO_MPD_COMMAND.get(test_case["intent"])
        if expected_command is not None:
            assert fake_mpd.commands[0][0] == expected_command, f"Wrong MPD command: {fake_mpd.commands[0]}"
        if expected_command == "play":
            assert fake_mpd.last_query is not None, "No query passed to MPD"

        # Validate TTS response
        assert len(fake_tts.spoken_texts) > 0, "No TTS response"

        # Debug output
        print(f"\n✅ {test_case['full_phrase']}")
        print(f"   Transcript: {transcript}")
        print(f"   Intent: {intent.intent_type}")
        print(f"   Query: {fake_mpd.last_query}")
        print(f"   Confidence: {fake_mpd.last_confidence:.2f}" if fake_mpd.last_confidence else "")
        print(f"   TTS: {fake_tts.spoken_texts[0]}")


class TestE2EStatistics:
    """Generate E2E test statistics."""

    def test_generate_report(self, e2e_suite):
        """Print test suite statistics."""
        print("\n" + "="*80)
        print("TRUE E2E TEST REPORT")
        print("="*80)

        print(f"\n📊 Pipeline Tested:")
        print(f"  1. Wake word detection (pre-validated)")
        print(f"  2. Command audio extraction")
        print(f"  3. Hailo STT transcription (REAL)")
        print(f"  4. Intent classification (REAL)")
        print(f"  5. Music library search (REAL)")
        print(f"  6. MPD command execution (MOCKED)")
        print(f"  7. TTS response (MOCKED)")

        print(f"\n🎯 Test Coverage:")
        print(f"  Music commands: {len(e2e_suite['tests']['positive'])}")
        print(f"  Negative tests: {len(e2e_suite['tests']['negative'])}")

        structure = e2e_suite["structure"]
        voice = e2e_suite["voice"]
        print(f"\n⚙️  Audio Configuration:")
        print(f"  Wake word duration: {structure['wake_word_duration_s']:.2f}s")
        print(f"  Pause duration: {structure['pause_duration_s']}s")
        print(f"  Command start: {structure['command_start_s']:.2f}s")
        print(f"  Voice: {voice['voice_name']} ({voice['provider']})")

        print(f"\n✅ Full orchestrator pipeline validated")
        print("="*80)
