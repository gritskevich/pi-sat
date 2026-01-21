from pathlib import Path

from tests.utils.fixture_loader import load_fixture


FIXTURES_DIR = Path(__file__).parent / "fixtures"
METADATA_PATH = Path(__file__).resolve().parent.parent / "tests" / "audio_samples" / "test_metadata.json"


def _require_keys(data: dict, keys: list[str]) -> None:
    for key in keys:
        assert key in data, f"Missing key: {key}"


def _validate_intent_music_cases(data: dict) -> None:
    _require_keys(data, ["catalog", "play_cases", "control_cases"])
    assert isinstance(data["catalog"], list)
    for item in data["catalog"]:
        _require_keys(item, ["id", "file", "title", "artist"])
    for case in data["play_cases"]:
        _require_keys(case, ["text", "expect_id"])
    for case in data["control_cases"]:
        _require_keys(case, ["text", "expect_intent"])


def _validate_intent_smoke_en(data: dict) -> None:
    _require_keys(data, ["play_music", "pause", "volume_up", "volume_down", "no_match", "fuzzy_typos"])
    for case in data["play_music"]:
        _require_keys(case, ["text", "query"])


def _validate_intent_smoke_fr(data: dict) -> None:
    _require_keys(data, ["play_music", "volume", "pause"])
    for case in data["play_music"]:
        _require_keys(case, ["text", "query"])
    for case in data["volume"]:
        _require_keys(case, ["text", "intent"])
    for case in data["pause"]:
        _require_keys(case, ["text", "intent"])


def _validate_intent_continue_fr(data: dict) -> None:
    _require_keys(data, ["continue"])
    for case in data["continue"]:
        _require_keys(case, ["text"])


def _validate_music_library_cases(data: dict) -> None:
    _require_keys(data, ["songs", "search_exact", "search_partial", "search_typo", "search_artist", "no_match"])
    assert isinstance(data["songs"], list)


def _validate_music_resolver_cases(data: dict) -> None:
    _require_keys(data, ["extract_fr", "extract_en", "clean_queries"])
    assert isinstance(data["extract_fr"], list)
    assert isinstance(data["extract_en"], list)


def _validate_music_false_positive_cases(data: dict) -> None:
    _require_keys(data, ["songs", "unrelated_queries", "music_queries", "stt_errors"])
    for case in data["music_queries"]:
        _require_keys(case, ["query", "expect_contains"])
    for case in data["stt_errors"]:
        _require_keys(case, ["query", "expect_contains"])


def _validate_music_library_stt_cases(data: dict) -> None:
    _require_keys(data, ["catalog", "cases"])
    assert isinstance(data["catalog"], list)
    assert isinstance(data["cases"], list)
    for case in data["cases"]:
        _require_keys(case, ["query", "expect_file"])


def _validate_command_validator_fr(data: dict) -> None:
    _require_keys(data, ["simple_controls", "volume_controls"])
    for case in data["simple_controls"]:
        _require_keys(case, ["intent", "raw_text", "response_key"])
    for case in data["volume_controls"]:
        _require_keys(case, ["intent", "raw_text", "response_key"])


def _validate_audio_metadata(data: dict) -> None:
    _require_keys(data, ["version", "suites", "usage"])
    suites = data["suites"]
    assert "e2e_french" in suites
    suite = suites["e2e_french"]
    _require_keys(suite, ["generator", "voice", "structure", "audio_format", "tests"])
    tests = suite["tests"]
    _require_keys(tests, ["positive", "negative"])
    for group in ("positive", "negative"):
        for case in tests[group]:
            _require_keys(case, ["id", "file", "full_phrase", "command", "language"])


def test_fixture_schemas():
    load_fixture(FIXTURES_DIR / "intent_music_cases_fr.json", _validate_intent_music_cases)
    load_fixture(FIXTURES_DIR / "intent_smoke_cases_en.json", _validate_intent_smoke_en)
    load_fixture(FIXTURES_DIR / "intent_smoke_cases_fr.json", _validate_intent_smoke_fr)
    load_fixture(FIXTURES_DIR / "intent_continue_cases_fr.json", _validate_intent_continue_fr)
    load_fixture(FIXTURES_DIR / "music_library_cases.json", _validate_music_library_cases)
    load_fixture(FIXTURES_DIR / "music_library_stt_cases_fr.json", _validate_music_library_stt_cases)
    load_fixture(FIXTURES_DIR / "music_resolver_cases.json", _validate_music_resolver_cases)
    load_fixture(FIXTURES_DIR / "music_false_positive_cases.json", _validate_music_false_positive_cases)
    load_fixture(FIXTURES_DIR / "command_validator_fr.json", _validate_command_validator_fr)
    load_fixture(METADATA_PATH, _validate_audio_metadata)
