"""Regression dataset: real STT outputs from live kid-driven use on 2026-04-25.

Every case asserts the *correct* outcome (decoded by hand from session logs +
parent context). This file is the ground truth — as we ship fixes, the pass
count must rise and never fall.

The fixture is `tests/fixtures/observed_failures_2026-04-25.json` and contains
both the heard transcripts and the full 95-song catalog from MPD that was live
at capture time.
"""

from __future__ import annotations

import json
import os
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List

import pytest

from modules.intent_engine import IntentEngine
from modules.music_library import MusicLibrary

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "observed_failures_2026-04-25.json"


@pytest.fixture(scope="module")
def fixture() -> Dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def engine() -> IntentEngine:
    return IntentEngine(fuzzy_threshold=50, language="fr", debug=False)


@pytest.fixture(scope="module")
def library(fixture) -> MusicLibrary:
    lib = MusicLibrary(library_path=None, fuzzy_threshold=50, debug=False)
    catalog: List[str] = []
    metadata = []
    for filename in fixture["catalog"]:
        basename = os.path.splitext(os.path.basename(filename))[0]
        variants = lib._build_searchable_variants(basename)
        catalog.append(filename)
        metadata.append((filename, variants))
    lib._catalog = catalog
    lib._catalog_metadata = metadata
    lib._search_best_cache = OrderedDict()
    if lib._phonetic_encoder:
        lib._phonetic_encoder.clear_cache()
    return lib


def _case_id(case: Dict[str, Any]) -> str:
    return f"#{case['n']:02d}-{case['cat']}"


def _load_cases() -> List[Dict[str, Any]]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["cases"]


# --- Currently-failing cases (xfail markers) -------------------------------
#
# Update these sets as fixes land. Each removed entry is a measurable win.

_INTENT_KNOWN_FAIL: set[int] = {
    # F4: article-led, no command verb. Need an "implicit play" rule.
    23,
    # F1+F3: "Me" / quoted "me" alone, then a foreign-song chunk — the
    # short prefix never reaches a play-verb match.
    18,
    # F1+F2: French homophone past the simple fold rule.
    22,
    # F5: truncated, garbled or single-word STT — best handled at the UX
    # layer ("can you say it again?"), not by stretching intent matching.
    9, 12, 28,
}

_SONG_KNOWN_FAIL: set[int] = {
    # F2: French song mangled beyond phonetic recovery
    2, 29,
    # F3: BATIDÃO cluster cases where the BATI stem is missing or the
    # query is dominated by other songs' overlap. Future work: encode
    # phonetics word-by-word so token_set_ratio works on tokens.
    17, 24, 25,
    # No intent extracted upstream → no song lookup attempted.
    18, 22, 23,
}


# --- Tests -----------------------------------------------------------------

@pytest.mark.parametrize("case", _load_cases(), ids=_case_id)
def test_intent_classification(case, engine):
    """Intent must match the decoded ground-truth (or be None for rejection cases)."""
    if case["n"] in _INTENT_KNOWN_FAIL:
        pytest.xfail(f"Known intent failure (cat={case['cat']}); see fixture")

    text = case["text"]
    expected = case["intent"]
    intent = engine.classify(text)

    if expected is None:
        assert intent is None, f"{text!r} should not match any intent, got {intent}"
    else:
        assert intent is not None, f"{text!r} produced no intent; expected {expected}"
        assert intent.intent_type == expected, (
            f"{text!r} → got {intent.intent_type}, expected {expected}"
        )


@pytest.mark.parametrize(
    "case",
    [c for c in _load_cases() if c["song"] is not None],
    ids=_case_id,
)
def test_song_resolution(case, engine, library):
    """For cases with a known target song, music search must return that file."""
    if case["n"] in _SONG_KNOWN_FAIL:
        pytest.xfail(f"Known song-resolution failure (cat={case['cat']}); see fixture")

    text = case["text"]
    expected_song = case["song"]
    intent = engine.classify(text)
    assert intent is not None, f"{text!r} produced no intent"
    query = intent.parameters.get("query", "") or text

    match = library.search_best(query)
    assert match is not None, f"{text!r} (query={query!r}) produced no match; expected {expected_song}"
    assert match[0] == expected_song, (
        f"{text!r} (query={query!r}) → {match[0]} ({match[1]:.1f}%), expected {expected_song}"
    )


def test_regression_metrics(fixture):
    """Print pass/fail counts; fails only if the known-fail sets become inaccurate.

    This guards against quietly losing a previously-passing case: if a case
    not in the known-fail set now also fails, the corresponding test above
    will fail loudly. This metric test just summarizes for humans.
    """
    cases = fixture["cases"]
    intent_targets = [c for c in cases if c["intent"] is not None or c["song"] is None]
    song_targets = [c for c in cases if c["song"] is not None]

    intent_xfailed = len(_INTENT_KNOWN_FAIL)
    song_xfailed = len(_SONG_KNOWN_FAIL)

    print(
        f"\nRegression metrics @ {fixture['captured_at']}: "
        f"intent {len(intent_targets) - intent_xfailed}/{len(intent_targets)} expected pass, "
        f"song {len(song_targets) - song_xfailed}/{len(song_targets)} expected pass"
    )
    # Sanity: known-fail sets must reference real case numbers
    case_numbers = {c["n"] for c in cases}
    assert _INTENT_KNOWN_FAIL <= case_numbers, "stale entry in _INTENT_KNOWN_FAIL"
    assert _SONG_KNOWN_FAIL <= case_numbers, "stale entry in _SONG_KNOWN_FAIL"


if __name__ == "__main__":
    import unittest
    pytest.main([__file__, "-v"])
