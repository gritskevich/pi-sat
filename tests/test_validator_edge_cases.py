"""Edge-case + boundary tests for CommandValidator's confirmation tier.

Covers:
  - All threshold boundaries (0.49 → Rejected, 0.50 → Confirm, 0.65 → Uncertain, 0.80 → Confident)
  - Empty queries
  - Missing library
  - Library returns None / empty catalog
  - Confidence at extremes (0.0, 1.0)
  - Special characters in query
  - Filename normalization (path separators, unusual extensions)
"""
from __future__ import annotations

from typing import Optional, Tuple

import pytest

from modules.command_validator import CommandValidator, ValidationResult
from modules.interfaces import Intent


class FakeLibrary:
    def __init__(self, result: Optional[Tuple[str, float]] = None, empty: bool = False):
        self._result = result
        self._empty = empty

    def is_empty(self) -> bool:
        return self._empty

    def search_best(self, query: str):
        return self._result


def _v(result, empty=False):
    return CommandValidator(music_library=FakeLibrary(result, empty=empty), language="fr")


def _intent(query: str) -> Intent:
    return Intent(intent_type="play_music", confidence=1.0,
                  parameters={"query": query}, raw_text=query, language="fr")


# --- Boundary matrix --------------------------------------------------------

class TestConfidenceBoundaries:
    @pytest.mark.parametrize("conf,expected_kind", [
        (0.0,  "rejected"),
        (0.30, "rejected"),
        (0.49, "rejected"),
        (0.50, "confirm"),
        (0.55, "confirm"),
        (0.64, "confirm"),
        (0.65, "uncertain"),
        (0.70, "uncertain"),
        (0.79, "uncertain"),
        (0.80, "confident"),
        (0.99, "confident"),
        (1.00, "confident"),
    ])
    def test_each_boundary(self, conf, expected_kind):
        v = _v(("X.mp3", conf))
        result = v.validate(_intent("x"))
        if expected_kind == "rejected":
            assert result.is_valid is False
            assert result.requires_confirmation is False
        elif expected_kind == "confirm":
            assert result.is_valid
            assert result.requires_confirmation is True
            assert result.validated_params["matched_file"] == "X.mp3"
        elif expected_kind == "uncertain":
            assert result.is_valid
            assert result.requires_confirmation is False
        else:  # confident
            assert result.is_valid
            assert result.requires_confirmation is False


# --- Degenerate inputs ------------------------------------------------------

class TestDegenerateInputs:
    def test_empty_query_invalid(self):
        v = _v(("X.mp3", 0.99))
        result = v.validate(_intent(""))
        assert result.is_valid is False

    def test_whitespace_query_invalid(self):
        v = _v(("X.mp3", 0.99))
        result = v.validate(_intent("   "))
        assert result.is_valid is False

    def test_empty_library_invalid(self):
        v = _v(None, empty=True)
        result = v.validate(_intent("x"))
        assert result.is_valid is False

    def test_search_returns_none_invalid(self):
        v = _v(None, empty=False)
        result = v.validate(_intent("x"))
        assert result.is_valid is False

    def test_no_library_optimistic_valid(self):
        v = CommandValidator(music_library=None, language="fr")
        result = v.validate(_intent("x"))
        # No library → can't validate, optimistic valid
        assert result.is_valid is True
        assert result.requires_confirmation is False


# --- File path edge cases ---------------------------------------------------

class TestFilePathEdgeCases:
    def test_filename_with_apostrophe(self):
        v = _v(("Mais je t'aime.mp3", 0.85))
        result = v.validate(_intent("mais"))
        assert result.is_valid
        assert "Mais je t'aime" in result.feedback_message

    def test_filename_unicode(self):
        v = _v(("NO BATIDÃO - ZXKAI.mp3", 0.92))
        result = v.validate(_intent("batidão"))
        assert result.is_valid
        assert "NO BATIDÃO" in result.feedback_message or "BATIDÃO" in result.feedback_message

    def test_filename_with_unusual_chars(self):
        # Extension stripping should still work
        v = _v(("Études: No. 6.mp3", 0.88))
        result = v.validate(_intent("etudes"))
        assert result.is_valid
        assert "Études: No. 6" in result.feedback_message


# --- Confirmation message form ---------------------------------------------

class TestConfirmationMessageForm:
    def test_confirming_message_is_a_question(self):
        v = _v(("Les dormantes.mp3", 0.55))
        result = v.validate(_intent("les dormants"))
        assert result.is_valid
        assert result.requires_confirmation is True
        # The message should clearly read as a yes/no question to the kid
        msg = result.feedback_message
        question_markers = ["?", " oui ", " non ", "tu veux", "c'est bien"]
        assert any(m.lower() in msg.lower() for m in question_markers), \
            f"Expected a yes/no question form, got: {msg!r}"

    def test_confirming_message_includes_song_name(self):
        v = _v(("Jour 1.mp3", 0.60))
        result = v.validate(_intent("jour"))
        assert "Jour 1" in result.feedback_message
