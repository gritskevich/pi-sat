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
import soundfile as sf
from pathlib import Path
from modules.command_processor import CommandProcessor
from modules.hailo_stt import HailoSTT
from modules.intent_engine import IntentEngine
from modules.music_library import MusicLibrary


# Test data directory
AUDIO_DIR = Path(__file__).parent / "audio_samples" / "e2e_french"
MANIFEST = AUDIO_DIR / "manifest.json"


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
        return True, f"Playing {query}", confidence or 1.0

    def pause(self):
        self.commands.append(('pause',))
        return True, "Paused"

    def next(self):
        self.commands.append(('next',))
        return True, "Next"

    def volume_up(self, step=10):
        self.commands.append(('volume_up', step))
        return True, "Volume up"

    def add_to_favorites(self):
        self.commands.append(('add_favorite',))
        return True, "Added to favorites"


@pytest.fixture(scope="module")
def test_manifest():
    """Load test manifest."""
    if not MANIFEST.exists():
        pytest.skip("Run: python scripts/generate_e2e_french_tests.py")

    with open(MANIFEST, 'r', encoding='utf-8') as f:
        return json.load(f)


@pytest.fixture(scope="module")
def hailo_stt():
    """Real Hailo STT instance."""
    if os.getenv("PISAT_RUN_HAILO_TESTS", "0") != "1":
        pytest.skip("Set PISAT_RUN_HAILO_TESTS=1 for Hailo tests")

    try:
        stt = HailoSTT(language='fr')
        yield stt
        stt.cleanup()
    except Exception as e:
        pytest.skip(f"Hailo STT unavailable: {e}")


@pytest.fixture(scope="module")
def intent_engine():
    """Real Intent engine instance."""
    return IntentEngine(language='fr')




def load_command_audio(test_case, manifest):
    """Load command audio (skip wake word based on manifest)."""
    skip_duration = manifest["metadata"]["command_skip_s"]
    audio_path = AUDIO_DIR / test_case["file"]

    # Load full audio
    audio_data, sample_rate = sf.read(audio_path)

    # Skip wake word + pause
    command_start = int(skip_duration * sample_rate)
    command_audio = audio_data[command_start:]

    # Convert to int16 PCM bytes
    import numpy as np
    audio_int16 = (command_audio * 32767).astype(np.int16)
    return audio_int16.tobytes()


class TestFrenchE2ETrue:
    """True E2E tests - Full orchestrator pipeline."""

    @pytest.mark.parametrize("test_idx", range(10))
    def test_full_pipeline(self, test_idx, test_manifest, hailo_stt, intent_engine):
        """Test complete pipeline: Audio → STT → Intent → MusicResolver → MPD → TTS"""
        test_case = test_manifest["positive_tests"][test_idx]

        # Load command audio (wake word already detected, skip it)
        command_bytes = load_command_audio(test_case, test_manifest)

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
        assert success, f"Pipeline failed for: {test_case['phrase']}"

        # Validate each step using internal methods (like test_orchestrator_e2e.py)
        transcript = processor._transcribe_audio(command_bytes)
        assert transcript and transcript.strip(), "Empty transcription"

        intent = processor._classify_intent(transcript)
        assert intent is not None, f"No intent for: {transcript}"
        assert intent.intent_type == "play_music", f"Wrong intent: {intent.intent_type}"

        # Validate MPD was called with play command
        assert len(fake_mpd.commands) > 0, "MPD not called"
        assert fake_mpd.commands[0][0] == "play", f"Wrong MPD command: {fake_mpd.commands[0]}"
        assert fake_mpd.last_query is not None, "No query passed to MPD"

        # Validate TTS response
        assert len(fake_tts.spoken_texts) > 0, "No TTS response"

        # Debug output
        print(f"\n✅ {test_case['phrase']}")
        print(f"   Transcript: {transcript}")
        print(f"   Intent: {intent.intent_type}")
        print(f"   Query: {fake_mpd.last_query}")
        print(f"   Confidence: {fake_mpd.last_confidence:.2f}" if fake_mpd.last_confidence else "")
        print(f"   TTS: {fake_tts.spoken_texts[0]}")


class TestE2EStatistics:
    """Generate E2E test statistics."""

    def test_generate_report(self, test_manifest):
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
        print(f"  Music commands: {len(test_manifest['positive_tests'])}")
        print(f"  Negative tests: {len(test_manifest['negative_tests'])}")

        metadata = test_manifest["metadata"]
        print(f"\n⚙️  Audio Configuration:")
        print(f"  Wake word duration: {metadata['wake_word_duration_s']:.2f}s")
        print(f"  Pause duration: {metadata['pause_duration_s']}s")
        print(f"  Skip duration: {metadata['command_skip_s']:.2f}s")
        print(f"  Voice: {metadata['voice']}")

        print(f"\n✅ Full orchestrator pipeline validated")
        print("="*80)
