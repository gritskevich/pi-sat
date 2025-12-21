"""
French E2E Tests: Wake Word → STT → Intent (Music Commands Only)

Validates complete pipeline with realistic French audio from ElevenLabs.
Tests 10 music commands with "Alexa" wake word.
"""

import json
import pytest
import soundfile as sf
from pathlib import Path
from modules.wake_word_listener import WakeWordListener
from modules.hailo_stt import HailoSTT
from modules.intent_engine import IntentEngine
import config

# Test data directory
AUDIO_DIR = Path(__file__).parent / "audio_samples" / "e2e_french"
MANIFEST = AUDIO_DIR / "manifest.json"


@pytest.fixture(scope="module")
def test_manifest():
    """Load test manifest with skip duration."""
    if not MANIFEST.exists():
        pytest.skip(f"Test audio not generated. Run: python scripts/generate_e2e_french_tests.py")

    with open(MANIFEST, 'r', encoding='utf-8') as f:
        return json.load(f)


@pytest.fixture(scope="module")
def wake_word_listener():
    """Wake word listener instance."""
    listener = WakeWordListener()
    yield listener
    # Cleanup handled by listener itself


@pytest.fixture(scope="module")
def hailo_stt():
    """Hailo STT instance (French)."""
    try:
        stt = HailoSTT(language='fr')
        yield stt
        stt.cleanup()
    except Exception as e:
        pytest.skip(f"Hailo STT not available: {e}")


@pytest.fixture(scope="module")
def intent_engine():
    """Intent engine instance (French)."""
    return IntentEngine(language='fr')


class TestFrenchE2EMusic:
    """E2E tests - Wake word + STT + Intent (music commands only)."""

    @pytest.mark.parametrize("test_idx", range(10))
    def test_music_command(self, test_idx, test_manifest, wake_word_listener, hailo_stt, intent_engine):
        """Test: 'Alexa [pause] [music command]' → play_music intent."""
        test_case = test_manifest["positive_tests"][test_idx]
        skip_duration = test_manifest["metadata"]["command_skip_s"]

        # Load audio
        audio_path = AUDIO_DIR / test_case["file"]
        audio_data, sample_rate = sf.read(audio_path)

        # 1. Wake word detection
        detected = wake_word_listener.detect_wake_word(audio_data)
        assert detected, f"Wake word not detected: {test_case['phrase']}"

        # 2. Extract command (skip wake word + pause)
        command_start = int(skip_duration * sample_rate)
        command_audio = audio_data[command_start:]

        # 3. STT transcription
        transcript = hailo_stt.transcribe(command_audio)
        assert transcript, "Empty transcript"
        print(f"\n  Expected: {test_case['command']}")
        print(f"  Got:      {transcript}")

        # 4. Intent classification
        intent = intent_engine.classify(transcript)
        assert intent is not None, f"No intent: {transcript}"
        assert intent.intent_type == "play_music", f"Wrong intent: {intent.intent_type}"


class TestFrenchE2ENegative:
    """Negative tests - should NOT trigger (no wake word)."""

    def test_no_wake_01_joue_musique(self, test_manifest, wake_word_listener):
        """Test: 'Joue de la musique.' → should NOT detect wake word."""
        test_case = test_manifest["negative_tests"][0]
        audio_path = AUDIO_DIR / test_case["file"]
        audio_data, _ = sf.read(audio_path)

        detected = wake_word_listener.detect_wake_word(audio_data)
        assert not detected, f"False positive: detected wake word in: {test_case['phrase']}"

    def test_no_wake_02_peux_tu_frozen(self, test_manifest, wake_word_listener):
        """Test: 'Peux-tu mettre Frozen?' → should NOT detect wake word."""
        test_case = test_manifest["negative_tests"][1]
        audio_path = AUDIO_DIR / test_case["file"]
        audio_data, _ = sf.read(audio_path)

        detected = wake_word_listener.detect_wake_word(audio_data)
        assert not detected

    def test_no_wake_03_monte_volume(self, test_manifest, wake_word_listener):
        """Test: 'Monte le volume s'il te plaît.' → should NOT detect wake word."""
        test_case = test_manifest["negative_tests"][2]
        audio_path = AUDIO_DIR / test_case["file"]
        audio_data, _ = sf.read(audio_path)

        detected = wake_word_listener.detect_wake_word(audio_data)
        assert not detected


class TestE2EStatistics:
    """Generate test statistics and report."""

    def test_generate_report(self, test_manifest, hailo_stt, intent_engine):
        """Generate comprehensive test report."""
        print("\n" + "="*80)
        print("FRENCH E2E TEST REPORT")
        print("="*80)

        print(f"\n📊 Test Suite:")
        print(f"  Positive tests: {len(test_manifest['positive_tests'])}")
        print(f"  Negative tests: {len(test_manifest['negative_tests'])}")
        print(f"  Total: {len(test_manifest['positive_tests']) + len(test_manifest['negative_tests'])}")

        print(f"\n🎯 Intent Coverage:")
        intents = set(t["intent"] for t in test_manifest["positive_tests"])
        for intent in sorted(intents):
            count = sum(1 for t in test_manifest["positive_tests"] if t["intent"] == intent)
            print(f"  {intent}: {count} test(s)")

        print(f"\n✅ All tests should pass for production readiness")
        print("="*80)
