import re
import unicodedata
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List

from thefuzz import fuzz

try:
    from abydos.phonetic import BeiderMorse
    PHONETIC_AVAILABLE = True
except ImportError:
    PHONETIC_AVAILABLE = False
    BeiderMorse = None


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
    name = "phonetic"

    def __init__(self):
        self._enabled = PHONETIC_AVAILABLE
        self._matcher = None
        self._cache: Dict[str, str] = {}
        self._query_cache: Dict[str, str] = {}
        if self._enabled:
            try:
                self._matcher = BeiderMorse(language_arg=0, name_mode='gen', match_mode='approx')
            except Exception:
                self._enabled = False
                self._matcher = None

    def available(self) -> bool:
        return self._enabled and self._matcher is not None

    def score(self, text: str, trigger: str) -> float:
        if not self.available():
            return 0.0
        query_phonetic = self._encode(text, self._query_cache)
        trigger_phonetic = self._encode(trigger, self._cache)
        if not query_phonetic or not trigger_phonetic:
            return 0.0
        return float(fuzz.token_set_ratio(query_phonetic, trigger_phonetic))

    def _encode(self, text: str, cache: Dict[str, str]) -> str:
        if not text or not self._allowed(text):
            return ""
        normalized = unicodedata.normalize('NFKD', text.lower())
        normalized = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
        normalized = re.sub(r'[^a-z0-9]+', '', normalized).strip()
        cached = cache.get(normalized)
        if cached is not None:
            return cached
        try:
            encoded = self._matcher.encode(normalized or text)
            phonetic_str = '|'.join(sorted(encoded)) if isinstance(encoded, tuple) else str(encoded)
        except Exception:
            phonetic_str = ""
        cache[normalized] = phonetic_str
        return phonetic_str

    def _allowed(self, text: str) -> bool:
        normalized = unicodedata.normalize('NFKD', text.lower())
        normalized = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
        normalized = re.sub(r'[^a-z0-9]+', '', normalized).strip()
        return len(normalized) >= 3


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
