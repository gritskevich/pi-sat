"""
French E2E Tests: Wake Word → STT → Intent (Music Commands Only)

Validates complete pipeline with realistic French audio from ElevenLabs.
Tests 10 music commands with "Alexa" wake word.
"""

import os
import pytest
from pathlib import Path

import config
RUN_HAILO_TESTS = os.getenv("PISAT_RUN_HAILO_TESTS", "0") == "1"
RUN_HAILO_BACKEND = config.STT_BACKEND == "hailo"
from tests.test_utils import read_wav_mono_int16
from tests.utils.fixture_loader import load_fixture

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

    metadata = load_fixture(METADATA_PATH)

    try:
        return metadata["suites"][SUITE_ID]
    except KeyError:
        pytest.skip(f"Missing suite '{SUITE_ID}' in {METADATA_PATH}", allow_module_level=True)


SUITE = _load_suite_or_skip()
POSITIVE_CASES = SUITE["tests"]["positive"]
NEGATIVE_CASES = SUITE["tests"]["negative"]


@pytest.fixture(scope="module")
def e2e_suite():
    """Suite metadata for DRY audio-driven tests."""
    # Skip early if audio isn't generated (folder is gitignored)
    sample = PROJECT_ROOT / POSITIVE_CASES[0]["file"]
    if not sample.exists():
        pytest.skip("Test audio not generated. Run: python scripts/generate_e2e_french_tests.py")
    return SUITE


@pytest.fixture(scope="module")
def wake_word_listener():
    """Wake word listener instance."""
    try:
        from modules.wake_word_listener import WakeWordListener
        listener = WakeWordListener()
    except Exception as e:
        pytest.skip(f"Wake word not available: {e}")

    yield listener


@pytest.fixture(scope="module")
def hailo_stt():
    """Hailo STT instance (French)."""
    from modules.hailo_stt import HailoSTT

    stt = HailoSTT(language="fr")
    if not stt.is_available():
        pytest.skip("Hailo STT not available (model/pipeline not loaded)")

    yield stt
    stt.cleanup()


@pytest.fixture(scope="module")
def intent_engine():
    """Intent engine instance (French)."""
    from modules.intent_engine import IntentEngine
    return IntentEngine(language="fr")


class TestFrenchE2EMusic:
    """E2E tests - Wake word + STT + Intent (music commands only)."""

    @pytest.mark.parametrize("test_case", POSITIVE_CASES, ids=lambda c: f"{c['id']:02d}_{c['intent']}")
    def test_music_command(self, test_case, e2e_suite, wake_word_listener, hailo_stt, intent_engine):
        """Test: 'Alexa [pause] [music command]' → play_music intent."""
        # Load audio (paths are relative to repo root)
        audio_path = PROJECT_ROOT / test_case["file"]
        audio_data, sample_rate = read_wav_mono_int16(str(audio_path))

        # 1. Wake word detection
        detected = wake_word_listener.detect_wake_word(audio_data)
        assert detected, f"Wake word not detected: {test_case['full_phrase']}"

        # 2. Extract command (skip wake word + pause)
        command_start_s = test_case.get("command_start_s", e2e_suite["structure"]["command_start_s"])
        command_start = int(command_start_s * sample_rate)
        command_audio = audio_data[command_start:]

        # 3. STT transcription
        transcript = hailo_stt.transcribe(command_audio)
        assert transcript, "Empty transcript"
        print(f"\n  Expected: {test_case['command']}")
        print(f"  Got:      {transcript}")

        # 4. Intent classification
        intent = intent_engine.classify(transcript)
        assert intent is not None, f"No intent: {transcript}"
        assert intent.intent_type == test_case["intent"], f"Wrong intent: {intent.intent_type}"


class TestFrenchE2ENegative:
    """Negative tests - should NOT trigger (no wake word)."""

    @pytest.mark.parametrize("test_case", NEGATIVE_CASES, ids=lambda c: f"{c['id']:02d}_no_wake")
    def test_no_wake_word(self, test_case, e2e_suite, wake_word_listener):
        """No wake word → should NOT detect wake word."""
        audio_path = PROJECT_ROOT / test_case["file"]
        audio_data, _ = read_wav_mono_int16(str(audio_path))

        detected = wake_word_listener.detect_wake_word(audio_data)
        assert not detected, f"False positive: detected wake word in: {test_case['full_phrase']}"


class TestE2EStatistics:
    """Generate test statistics and report."""

    def test_generate_report(self, e2e_suite, hailo_stt, intent_engine):
        """Generate comprehensive test report."""
        print("\n" + "="*80)
        print("FRENCH E2E TEST REPORT")
        print("="*80)

        print(f"\n📊 Test Suite:")
        positive = e2e_suite["tests"]["positive"]
        negative = e2e_suite["tests"]["negative"]
        print(f"  Positive tests: {len(positive)}")
        print(f"  Negative tests: {len(negative)}")
        print(f"  Total: {len(positive) + len(negative)}")

        print(f"\n🎯 Intent Coverage:")
        intents = set(t["intent"] for t in positive)
        for intent in sorted(intents):
            count = sum(1 for t in positive if t["intent"] == intent)
            print(f"  {intent}: {count} test(s)")

        print(f"\n✅ All tests should pass for production readiness")
        print("="*80)
