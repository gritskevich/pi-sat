"""Reply parser: classify a SHORT_LISTEN STT result into AFFIRM/DENY/NEW/UNINT.

The parser is the *strictness boundary* of the confirmation loop. A false
DENY is much worse than a re-prompt — it would discard the kid's intended
song. So the rule is: ambiguous input → UNINTELLIGIBLE, not DENY.
"""
from __future__ import annotations

import pytest

from modules.reply_parser import (
    AFFIRM,
    DENY,
    NEW_COMMAND,
    UNINTELLIGIBLE,
    TIMEOUT,
    ParsedReply,
    parse_reply,
)


class TestAffirm:
    @pytest.mark.parametrize("text", [
        "oui", "Oui", "OUI", " oui ", "ouais", "ouaip", "yep",
        "ok", "okay", "OK", "vas-y", "vas y", "c'est ça", "c'est ca",
        "yeah", "ouè",
    ])
    def test_simple_affirm_words(self, text):
        r = parse_reply(text)
        assert r.cls is AFFIRM, f"{text!r} should be AFFIRM, got {r.cls}"

    def test_affirm_with_trailing_punct(self):
        assert parse_reply("Oui!").cls is AFFIRM
        assert parse_reply("oui.").cls is AFFIRM
        assert parse_reply("ok ?").cls is AFFIRM

    def test_affirm_with_word_after(self):
        # "oui s'il te plait" — still AFFIRM
        assert parse_reply("oui s'il te plaît").cls is AFFIRM


class TestDeny:
    @pytest.mark.parametrize("text", [
        "non", "Non", "NON", " non ", "nan", "nope",
        "pas ça", "pas ca", "c'est pas ça", "c'est pas ca",
        "non non", "noon",
    ])
    def test_simple_deny_words(self, text):
        r = parse_reply(text)
        assert r.cls is DENY, f"{text!r} should be DENY, got {r.cls}"


class TestStrictnessGuards:
    """Ambiguous input must be UNINTELLIGIBLE, never DENY (false-DENY is worst case)."""

    def test_oui_then_non_is_unintelligible(self):
        # The kid said two contradictory things
        r = parse_reply("oui non")
        assert r.cls is UNINTELLIGIBLE

    def test_non_then_oui_is_unintelligible(self):
        r = parse_reply("non oui")
        assert r.cls is UNINTELLIGIBLE

    def test_ouais_nan_attends_is_unintelligible(self):
        # The example from /challenge — must not silently DENY
        r = parse_reply("ouais nan attends")
        assert r.cls is UNINTELLIGIBLE

    def test_random_french_is_unintelligible(self):
        r = parse_reply("Je voudrais peut-être quelque chose")
        # Has neither affirm nor deny stems, no play verb → UNINTELLIGIBLE
        assert r.cls is UNINTELLIGIBLE


class TestNewCommand:
    """Reply containing a play verb is treated as a fresh command, not yes/no."""

    def test_kid_says_a_new_song_with_play_verb(self):
        r = parse_reply("mets les dormantes")
        assert r.cls is NEW_COMMAND

    def test_tu_peux_mettre(self):
        r = parse_reply("tu peux mettre Jour 1")
        assert r.cls is NEW_COMMAND

    def test_joue_moi(self):
        r = parse_reply("joue moi NO BATIDÃO")
        assert r.cls is NEW_COMMAND

    def test_oui_followed_by_new_command_prefers_new_command(self):
        # If both are present, prefer the more specific signal
        r = parse_reply("oui mets autre chose")
        assert r.cls is NEW_COMMAND

    def test_song_name_alone_is_NOT_new_command(self):
        # Kid just says "Les dormantes" — no play verb. Treat as UNINTELLIGIBLE
        # (we can't be sure she meant "play that"). Wake-word loop handles this.
        r = parse_reply("les dormantes")
        assert r.cls is UNINTELLIGIBLE


class TestEdgeCases:
    def test_empty_string_is_timeout(self):
        # Empty STT result = nothing was said in the listen window
        assert parse_reply("").cls is TIMEOUT

    def test_whitespace_only_is_timeout(self):
        assert parse_reply("   ").cls is TIMEOUT
        assert parse_reply("\t\n").cls is TIMEOUT

    def test_punctuation_only_is_timeout(self):
        # STT often returns just "." for silent / very short captures
        assert parse_reply(".").cls is TIMEOUT
        assert parse_reply("...").cls is TIMEOUT
        assert parse_reply("?").cls is TIMEOUT

    def test_long_text_unintelligible(self):
        # Random long string that doesn't match anything
        r = parse_reply("blabla blabla blabla zzzzz xyz")
        assert r.cls is UNINTELLIGIBLE


class TestPreservesRawText:
    def test_raw_text_kept_for_logging(self):
        r = parse_reply("Oui!")
        assert r.raw_text == "Oui!"

    def test_matched_token_set_for_affirm(self):
        r = parse_reply("oui s'il te plaît")
        assert r.cls is AFFIRM
        assert r.matched_token in {"oui", "ouais", "yes"}  # whatever rule fired

    def test_matched_token_set_for_deny(self):
        r = parse_reply("non merci")
        assert r.cls is DENY
        assert r.matched_token is not None
