"""Domain model for music-match outcomes.

The matching pipeline used to express results as `Optional[Tuple[file, conf]]`,
which forced every caller to re-derive what to do based on the float. This
module makes the *decisions* explicit by classifying the float into one of
four named outcomes, each carrying just the data its caller needs:

    Confident         — high score, play immediately, brief confirmation TTS
    Uncertain         — medium score, play but hedge in the TTS
    NeedsConfirmation — borderline; ask the kid before playing
    Rejected          — too low to act on; ask the kid to repeat

The thresholds are knobs, not invariants — they're tuned against the
observed-failures eval and may shift as the catalog or kid grow.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Union


# Thresholds (defaults reflect 2026-04-26 eval against 188 real cases).
DEFAULT_CONFIDENT_MIN = 0.80
DEFAULT_UNCERTAIN_MIN = 0.65
DEFAULT_CONFIRMATION_MIN = 0.50


@dataclass(frozen=True)
class SongCandidate:
    """A single result from MusicLibrary.search_best."""
    file: str
    confidence: float
    query: str


@dataclass(frozen=True)
class Confident:
    candidate: SongCandidate


@dataclass(frozen=True)
class Uncertain:
    candidate: SongCandidate


@dataclass(frozen=True)
class NeedsConfirmation:
    candidate: SongCandidate


@dataclass(frozen=True)
class Rejected:
    query: str


MatchOutcome = Union[Confident, Uncertain, NeedsConfirmation, Rejected]


def classify_match(
    *,
    file: str,
    confidence: float,
    query: str,
    confident_min: float = DEFAULT_CONFIDENT_MIN,
    uncertain_min: float = DEFAULT_UNCERTAIN_MIN,
    confirmation_min: float = DEFAULT_CONFIRMATION_MIN,
) -> MatchOutcome:
    """Classify a match into one of four domain outcomes.

    Args:
        file: matched file path
        confidence: 0.0..1.0 from MusicLibrary
        query: the query string the kid said (after intent extraction)
        confident_min: scores ≥ this → Confident
        uncertain_min: scores ≥ this → Uncertain
        confirmation_min: scores ≥ this → NeedsConfirmation, else Rejected

    Returns one of: Confident | Uncertain | NeedsConfirmation | Rejected.
    """
    if not (confirmation_min <= uncertain_min <= confident_min):
        raise ValueError(
            f"thresholds must be ordered: confirmation_min ({confirmation_min}) "
            f"<= uncertain_min ({uncertain_min}) <= confident_min ({confident_min})"
        )

    if confidence < confirmation_min:
        return Rejected(query=query)

    candidate = SongCandidate(file=file, confidence=confidence, query=query)
    if confidence >= confident_min:
        return Confident(candidate=candidate)
    if confidence >= uncertain_min:
        return Uncertain(candidate=candidate)
    return NeedsConfirmation(candidate=candidate)
