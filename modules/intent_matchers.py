from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List

from thefuzz import fuzz
from modules.phonetic import PhoneticEncoder


@dataclass(frozen=True)
class MatchBreakdown:
    combined: float
    scores: Dict[str, float]


class TextMatcher:
    name = "text"

    def score(self, text: str, trigger: str) -> float:
        return float(fuzz.token_set_ratio(text, trigger))

    def available(self) -> bool:
        return True


class PhoneticMatcher:
    """
    Phonetic matcher using FONEM algorithm (French-specific).

    Faster and more accurate than BeiderMorse for French:
    - Speed: 75x faster (0.1ms vs 5ms per encoding)
    - Accuracy: 78.6% vs 71.4% on French STT errors
    """
    name = "phonetic"

    def __init__(self, algorithm: str = "fonem"):
        """
        Initialize phonetic matcher.

        Args:
            algorithm: Phonetic algorithm ("fonem" or "beidermorse")
        """
        self._encoder = PhoneticEncoder(algorithm=algorithm)

    def available(self) -> bool:
        return self._encoder.is_available()

    def score(self, text: str, trigger: str) -> float:
        if not self.available():
            return 0.0

        # Don't cache user queries (unbounded, causes memory leaks)
        query_phonetic = self._encoder.encode_query(text)

        # Cache trigger patterns (limited set, ~20 intents)
        trigger_phonetic = self._encoder.encode_pattern(trigger)

        if not query_phonetic or not trigger_phonetic:
            return 0.0

        return float(fuzz.token_set_ratio(query_phonetic, trigger_phonetic))


class MatcherStack:
    def __init__(self, matchers: Iterable, weights: Dict[str, float]):
        self.matchers = list(matchers)
        self.weights = weights

    def score(self, text: str, trigger: str) -> MatchBreakdown:
        scores: Dict[str, float] = {}
        total = 0.0
        weight_sum = 0.0
        for matcher in self.matchers:
            if hasattr(matcher, "available") and not matcher.available():
                continue
            score = float(matcher.score(text, trigger))
            scores[matcher.name] = score
            weight = float(self.weights.get(matcher.name, 1.0))
            if weight > 0:
                total += score * weight
                weight_sum += weight
        combined = total / weight_sum if weight_sum else 0.0
        return MatchBreakdown(combined=combined, scores=scores)


MATCHER_REGISTRY: Dict[str, Callable[[], object]] = {
    "text": TextMatcher,
    "phonetic": PhoneticMatcher,
}


def register_matcher(name: str, factory: Callable[[], object]) -> None:
    MATCHER_REGISTRY[name] = factory


def build_intent_matcher_stack(
    matcher_names: Iterable[str],
    phonetic_weight: float
) -> MatcherStack:
    names = [name for name in matcher_names if name in MATCHER_REGISTRY]
    matchers: List[object] = [MATCHER_REGISTRY[name]() for name in names]
    text_weight = max(0.0, 1.0 - phonetic_weight)
    weights = {"text": text_weight, "phonetic": max(0.0, phonetic_weight)}
    return MatcherStack(matchers=matchers, weights=weights)
