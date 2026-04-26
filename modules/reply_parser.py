"""Parse a SHORT_LISTEN STT result into AFFIRM / DENY / NEW_COMMAND / UNINT / TIMEOUT.

Strictness rule: a false DENY is the worst outcome — it would discard the
kid's intended song. So when both AFFIRM and DENY tokens appear, OR when
the input is ambiguous, the parser returns UNINTELLIGIBLE.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ReplyClass(Enum):
    AFFIRM = "affirm"
    DENY = "deny"
    NEW_COMMAND = "new_command"
    UNINTELLIGIBLE = "unintelligible"
    TIMEOUT = "timeout"


# Re-export for ergonomic imports: `from modules.reply_parser import AFFIRM, ...`
AFFIRM = ReplyClass.AFFIRM
DENY = ReplyClass.DENY
NEW_COMMAND = ReplyClass.NEW_COMMAND
UNINTELLIGIBLE = ReplyClass.UNINTELLIGIBLE
TIMEOUT = ReplyClass.TIMEOUT


# Affirm/Deny tokens — match as whole words after normalization (lowercased,
# accents stripped, apostrophes preserved as separator). Each set is a list
# of normalized tokens; a hit means "this token appears as a whole word".
AFFIRM_TOKENS = {
    "oui", "ouais", "ouaip", "ouai", "ouaie", "oue",
    "ok", "okay",
    "yep", "yeah", "yes",
    "vasy", "vas y",
    "cest ca",
    "mhm",
}

DENY_TOKENS = {
    "non", "nan", "noon",
    "nope",
    "pas ca",
    "cest pas ca",
}

# A play_music verb anywhere in the reply means the kid switched intent —
# treat the whole utterance as a NEW_COMMAND, not a yes/no.
PLAY_VERBS = {"mets", "mettre", "joue", "jouer", "lance", "ecoute", "ecouter", "tu peux", "je veux"}


@dataclass(frozen=True)
class ParsedReply:
    cls: ReplyClass
    raw_text: str
    matched_token: Optional[str] = None


def _normalize(text: str) -> str:
    """Lowercase, strip accents, apostrophes, collapse whitespace.

    Keeps spaces between words so token detection is whole-word.
    """
    if not text:
        return ""
    out = unicodedata.normalize("NFKD", text.lower())
    out = "".join(ch for ch in out if not unicodedata.combining(ch))
    out = out.replace("'", "").replace("’", "")
    out = re.sub(r"[^a-z0-9\s]+", " ", out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def _has_word(haystack: str, needle: str) -> bool:
    """True if `needle` appears as a whole-word match in `haystack` (both normalized)."""
    if " " in needle:
        # Multi-token expression — match as a substring with word boundaries
        pattern = r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])"
        return bool(re.search(pattern, haystack))
    return needle in set(haystack.split())


def parse_reply(raw_text: str) -> ParsedReply:
    """Classify a STT reply during the confirmation listen window.

    Returns:
        ParsedReply with cls in {AFFIRM, DENY, NEW_COMMAND, UNINTELLIGIBLE, TIMEOUT}.
    """
    if raw_text is None:
        return ParsedReply(cls=TIMEOUT, raw_text="")
    norm = _normalize(raw_text)
    # Empty / silence / noise → TIMEOUT (the listen window registered nothing useful)
    if not norm:
        return ParsedReply(cls=TIMEOUT, raw_text=raw_text)

    # Check for play verbs first — kid issued a fresh command instead of yes/no
    new_command_match = next(
        (v for v in PLAY_VERBS if _has_word(norm, v)),
        None,
    )

    affirm_hit = next(
        (t for t in AFFIRM_TOKENS if _has_word(norm, t)),
        None,
    )
    deny_hit = next(
        (t for t in DENY_TOKENS if _has_word(norm, t)),
        None,
    )

    # NEW_COMMAND wins over a bare yes/no when both are present
    # ("oui mets autre chose" → kid wants something different)
    if new_command_match:
        return ParsedReply(cls=NEW_COMMAND, raw_text=raw_text, matched_token=new_command_match)

    # Both affirm and deny tokens → ambiguous, do NOT silently DENY
    if affirm_hit and deny_hit:
        return ParsedReply(cls=UNINTELLIGIBLE, raw_text=raw_text)

    if affirm_hit:
        return ParsedReply(cls=AFFIRM, raw_text=raw_text, matched_token=affirm_hit)
    if deny_hit:
        return ParsedReply(cls=DENY, raw_text=raw_text, matched_token=deny_hit)

    # Reply has content but no class hit
    return ParsedReply(cls=UNINTELLIGIBLE, raw_text=raw_text)
