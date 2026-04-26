"""Tests for CommandValidator's confirmation tier (NeedsConfirmation outcome).

Domain mapping:
    confidence ≥ 0.80  → ValidationResult.valid + requires_confirmation=False (Confident)
    0.65 ≤ c < 0.80    → ValidationResult.valid + requires_confirmation=False (Uncertain — hedge in TTS)
    0.50 ≤ c < 0.65    → ValidationResult.valid + requires_confirmation=True  (NeedsConfirmation)
    c < 0.50           → ValidationResult.invalid                              (Rejected)

The boundaries match modules/match_outcome.DEFAULT_*.
"""
from __future__ import annotations

import os
from collections import OrderedDict
from typing import Optional, Tuple

import pytest

from modules.command_validator import CommandValidator, ValidationResult
from modules.interfaces import Intent


class FakeLibrary:
    """Stub MusicLibrary that returns a configurable (file, confidence) for search_best."""

    def __init__(self, result: Optional[Tuple[str, float]]):
        self._result = result

    def is_empty(self) -> bool:
        return self._result is None

    def search_best(self, query: str):
        return self._result


def _make_validator(result):
    return CommandValidator(music_library=FakeLibrary(result), language="fr")


def _intent(query: str) -> Intent:
    return Intent(
        intent_type="play_music",
        confidence=1.0,
        parameters={"query": query},
        raw_text=query,
        language="fr",
    )


class TestValidatorConfirmationTier:
    def test_high_confidence_is_valid_no_confirmation(self):
        v = _make_validator(("X.mp3", 0.92))
        result = v.validate(_intent("x"))
        assert result.is_valid
        assert getattr(result, "requires_confirmation", False) is False
        assert result.validated_params["matched_file"] == "X.mp3"

    def test_uncertain_is_valid_no_confirmation_hedged_message(self):
        # 0.70 → Uncertain (hedge in TTS, but still play)
        v = _make_validator(("X.mp3", 0.70))
        result = v.validate(_intent("x"))
        assert result.is_valid
        assert result.requires_confirmation is False
        # Message should be the "playing_with_confidence" hedge (contains "crois", "pense", or similar)
        assert any(token in result.feedback_message.lower()
                   for token in ("crois", "pense", "dis-moi", "compris", "change"))

    def test_borderline_needs_confirmation_no_play(self):
        # 0.55 → NeedsConfirmation: valid (the candidate is real) but requires_confirmation
        v = _make_validator(("X.mp3", 0.55))
        result = v.validate(_intent("x"))
        assert result.is_valid is True
        assert result.requires_confirmation is True
        # Candidate is still in the params so the orchestrator can play it on "oui"
        assert result.validated_params["matched_file"] == "X.mp3"
        # Message should be a question form (contains "?" or "tu veux")
        msg = result.feedback_message.lower()
        assert "?" in result.feedback_message or "tu veux" in msg or "c'est" in msg

    def test_low_confidence_rejected(self):
        v = _make_validator(("X.mp3", 0.30))
        result = v.validate(_intent("x"))
        assert result.is_valid is False
        assert result.requires_confirmation is False

    def test_just_below_confirmation_threshold_rejected(self):
        v = _make_validator(("X.mp3", 0.49))
        result = v.validate(_intent("x"))
        assert result.is_valid is False

    def test_exactly_at_confirmation_threshold_needs_confirmation(self):
        v = _make_validator(("X.mp3", 0.50))
        result = v.validate(_intent("x"))
        assert result.is_valid
        assert result.requires_confirmation is True

    def test_exactly_at_uncertain_threshold_no_confirmation(self):
        v = _make_validator(("X.mp3", 0.65))
        result = v.validate(_intent("x"))
        assert result.is_valid
        assert result.requires_confirmation is False
