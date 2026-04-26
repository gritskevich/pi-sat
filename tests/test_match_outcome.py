"""Domain tests for match_outcome — the four-tier classification of music search results.

Domain language (DDD):
    The matching pipeline returns one of four outcomes for a play_music query:
    - Confident:        we are sure, play immediately
    - Uncertain:        we'll play, but TTS hedges ("Je crois que tu veux X")
    - NeedsConfirmation: we are not sure, ask the kid first
    - Rejected:         we cannot match, ask the kid to repeat

The thresholds are configurable per-deployment; defaults reflect what we
saw on the kid-eval (4 months / 188 cases).
"""
from __future__ import annotations

import pytest

from modules.match_outcome import (
    Confident,
    NeedsConfirmation,
    Rejected,
    SongCandidate,
    Uncertain,
    classify_match,
)


class TestClassifyMatch:
    def test_high_confidence_is_confident(self):
        outcome = classify_match(file="X.mp3", confidence=0.92, query="x")
        assert isinstance(outcome, Confident)
        assert outcome.candidate.file == "X.mp3"
        assert outcome.candidate.confidence == 0.92
        assert outcome.candidate.query == "x"

    def test_medium_high_is_uncertain(self):
        outcome = classify_match(file="X.mp3", confidence=0.72, query="x")
        assert isinstance(outcome, Uncertain)

    def test_medium_low_needs_confirmation(self):
        outcome = classify_match(file="X.mp3", confidence=0.55, query="x")
        assert isinstance(outcome, NeedsConfirmation)
        assert outcome.candidate.file == "X.mp3"

    def test_very_low_is_rejected(self):
        outcome = classify_match(file="X.mp3", confidence=0.30, query="x")
        assert isinstance(outcome, Rejected)
        assert outcome.query == "x"

    def test_boundary_confident(self):
        # Exactly at confident threshold → Confident (inclusive lower bound)
        outcome = classify_match(file="X.mp3", confidence=0.80, query="x")
        assert isinstance(outcome, Confident)

    def test_boundary_uncertain(self):
        outcome = classify_match(file="X.mp3", confidence=0.65, query="x")
        assert isinstance(outcome, Uncertain)

    def test_boundary_confirmation(self):
        outcome = classify_match(file="X.mp3", confidence=0.50, query="x")
        assert isinstance(outcome, NeedsConfirmation)

    def test_boundary_rejected(self):
        outcome = classify_match(file="X.mp3", confidence=0.49, query="x")
        assert isinstance(outcome, Rejected)

    def test_overridable_thresholds(self):
        # If the deployment wants to be stricter, raise confirmation threshold
        outcome = classify_match(
            file="X.mp3",
            confidence=0.78,
            query="x",
            confident_min=0.85,
            uncertain_min=0.70,
            confirmation_min=0.55,
        )
        # 0.78 < 0.85 (confident) and >= 0.70 (uncertain min) → Uncertain
        assert isinstance(outcome, Uncertain)

    def test_thresholds_must_be_ordered(self):
        with pytest.raises(ValueError):
            classify_match(
                file="X.mp3", confidence=0.5, query="x",
                confident_min=0.5, uncertain_min=0.6,  # uncertain > confident
                confirmation_min=0.4,
            )


class TestSongCandidate:
    def test_immutable(self):
        c = SongCandidate(file="X.mp3", confidence=0.9, query="x")
        with pytest.raises((AttributeError, Exception)):
            c.file = "Y.mp3"  # frozen dataclass

    def test_equality_by_value(self):
        a = SongCandidate(file="X.mp3", confidence=0.9, query="x")
        b = SongCandidate(file="X.mp3", confidence=0.9, query="x")
        assert a == b


class TestOutcomeAccessors:
    """Each non-Rejected outcome carries the candidate; helpers should expose it uniformly."""

    def test_candidate_attr_on_nonrejected(self):
        for ConcreteOutcome in (Confident, Uncertain, NeedsConfirmation):
            candidate = SongCandidate(file="X.mp3", confidence=0.7, query="x")
            o = ConcreteOutcome(candidate=candidate)
            assert o.candidate is candidate

    def test_rejected_has_query_only(self):
        r = Rejected(query="le bâtiment")
        assert r.query == "le bâtiment"
        assert not hasattr(r, "candidate")
