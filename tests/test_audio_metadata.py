import wave
from pathlib import Path

import pytest
from tests.utils.fixture_loader import load_fixture


PROJECT_ROOT = Path(__file__).resolve().parent.parent
METADATA_PATH = PROJECT_ROOT / "tests" / "audio_samples" / "test_metadata.json"


def _load_metadata() -> dict:
    if not METADATA_PATH.exists():
        pytest.skip(f"Missing metadata file: {METADATA_PATH}")
    return load_fixture(METADATA_PATH)


def test_audio_metadata_schema():
    metadata = _load_metadata()

    assert metadata.get("version") == "3.0"
    assert isinstance(metadata.get("suites"), dict)
    assert "e2e_french" in metadata["suites"]

    suite = metadata["suites"]["e2e_french"]
    for key in ("generator", "voice", "structure", "audio_format", "tests"):
        assert key in suite

    tests = suite["tests"]
    assert isinstance(tests.get("positive"), list)
    assert isinstance(tests.get("negative"), list)

    for group_name in ("positive", "negative"):
        seen_ids = set()
        for case in tests[group_name]:
            assert isinstance(case.get("id"), int)
            assert case["id"] not in seen_ids
            seen_ids.add(case["id"])

            assert isinstance(case.get("file"), str) and case["file"]
            assert isinstance(case.get("full_phrase"), str) and case["full_phrase"]
            assert isinstance(case.get("command"), str) and case["command"]
            assert isinstance(case.get("language"), str) and case["language"]


def test_audio_metadata_audio_files_if_present():
    metadata = _load_metadata()
    suite = metadata["suites"]["e2e_french"]

    fmt = suite["audio_format"]
    expected_rate = int(fmt["sample_rate"])
    expected_channels = int(fmt["channels"])
    expected_sampwidth = int(fmt["bit_depth"]) // 8

    all_cases = suite["tests"]["positive"] + suite["tests"]["negative"]
    existing = [c for c in all_cases if (PROJECT_ROOT / c["file"]).exists()]
    if not existing:
        pytest.skip("No generated audio found for e2e_french suite")

    for case in existing:
        wav_path = PROJECT_ROOT / case["file"]
        with wave.open(str(wav_path), "rb") as wf:
            assert wf.getframerate() == expected_rate
            assert wf.getnchannels() == expected_channels
            assert wf.getsampwidth() == expected_sampwidth
            duration_s = wf.getnframes() / float(wf.getframerate())

        # If duration is present in metadata, it should be close (rounded values ok)
        if isinstance(case.get("duration_s"), (int, float)):
            assert abs(duration_s - float(case["duration_s"])) <= 0.15

        # If command_start_s is present, it must be within file duration
        if isinstance(case.get("command_start_s"), (int, float)):
            assert 0.0 <= float(case["command_start_s"]) <= duration_s
