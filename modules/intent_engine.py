import json
import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from thefuzz import fuzz

import config
from modules.interfaces import Intent
from modules.phonetic import PhoneticEncoder
from modules.intent_normalization import normalize_text, clean_query

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _PhraseEntry:
    intent: str
    phrase: str
    phonetic: str


class IntentEngine:
    def __init__(
        self,
        fuzzy_threshold: Optional[int] = None,
        language: Optional[str] = None,
        debug: bool = False
    ):
        self.debug = debug
        if debug:
            logger.setLevel(logging.DEBUG)

        self.fuzzy_threshold = int(
            fuzzy_threshold
            if fuzzy_threshold is not None
            else getattr(config, "INTENT_MATCH_THRESHOLD", 50)
        )

        self.language = language or getattr(config, "LANGUAGE", "fr")
        self._active_intents = set(getattr(config, "ACTIVE_INTENTS", []))
        self._dictionary_path = getattr(
            config,
            "INTENT_DICTIONARY_PATH",
            f"{config.PROJECT_ROOT}/resources/intent_dictionary.json"
        )
        self._phrases_by_language = self._load_dictionary(self._dictionary_path)
        self._phonetic_encoder = PhoneticEncoder(algorithm="fonem")
        self._phonetic_weight = float(getattr(config, "INTENT_PHONETIC_WEIGHT", 0.6))
        self._control_threshold = int(getattr(config, "INTENT_CONTROL_THRESHOLD", 75))
        self._phonetic_enabled = self._should_use_phonetic(self.language)
        self._phrase_entries = self._build_phrase_entries(self.language)

        logger.info(
            "Intent Engine initialized: "
            f"language={self.language}, threshold={self.fuzzy_threshold}, intents={len(self._active_intents)}"
        )

    def classify(self, text: str, language: Optional[str] = None) -> Optional[Intent]:
        if not text or not text.strip():
            logger.warning("Empty text provided for classification")
            return None

        raw_text = text
        normalized = normalize_text(text)
        tokens = self._tokenize(normalized)
        if not tokens:
            logger.warning(f"No tokens extracted for: '{raw_text}'")
            return None

        active_language = language or self.language
        if active_language != self.language:
            self.language = active_language
            self._phonetic_enabled = self._should_use_phonetic(active_language)
            self._phrase_entries = self._build_phrase_entries(active_language)

        best = self._find_best_match(tokens)
        if not best:
            logger.info(f"Intent answer: None")
            return None

        intent_type, score, span, matched_phrase = best
        min_score = self.fuzzy_threshold
        if intent_type in ("volume_up", "volume_down", "pause", "continue", "resume"):
            min_score = max(min_score, self._control_threshold)
        if score < min_score:
            logger.info(f"Intent answer: None")
            return None

        parameters = {}
        if intent_type == "play_music":
            query = ""
            if matched_phrase and matched_phrase in normalized:
                query_tokens = tokens[span[1]:]
                query = " ".join(query_tokens)
            else:
                query = normalized
            parameters["query"] = clean_query(query)

        intent = Intent(
            intent_type=intent_type,
            confidence=score / 100.0,
            parameters=parameters,
            raw_text=normalized,
            language=active_language
        )
        logger.info(f"Intent answer: {intent}")
        return intent

    def get_supported_intents(self) -> List[str]:
        return sorted(self._active_intents)

    def _find_best_match(self, tokens: List[str]) -> Optional[Tuple[str, float, Tuple[int, int], str]]:
        ngrams = self._generate_ngrams(tokens)
        best_score = -1.0
        best_intent = None
        best_span = None
        best_phrase = ""

        for start, end, gram in ngrams:
            if (end - start) == 1 and len(gram) <= 2:
                continue
            token_count = end - start
            phonetic_gram = ""
            if self._phonetic_enabled:
                phonetic_gram = self._phonetic_encoder.encode_query(gram) or ""
            for entry in self._phrase_entries:
                if token_count <= 2:
                    text_score = float(fuzz.ratio(gram, entry.phrase))
                else:
                    text_score = float(fuzz.WRatio(gram, entry.phrase))
                score = text_score
                if self._phonetic_enabled and phonetic_gram and entry.phonetic:
                    phonetic_score = float(fuzz.ratio(phonetic_gram, entry.phonetic))
                    score = (text_score * (1.0 - self._phonetic_weight)) + (phonetic_score * self._phonetic_weight)
                if score > best_score:
                    best_score = score
                    best_intent = entry.intent
                    best_span = (start, end)
                    best_phrase = entry.phrase
                elif score == best_score and best_span is not None:
                    if (end - start) > (best_span[1] - best_span[0]):
                        best_intent = entry.intent
                        best_span = (start, end)
                        best_phrase = entry.phrase

        if best_intent is None or best_span is None:
            return None

        if self.debug:
            logger.debug(
                f"Best intent match: intent={best_intent}, score={best_score:.1f}, span={best_span}"
            )

        return best_intent, best_score, best_span, best_phrase

    def _generate_ngrams(self, tokens: List[str]) -> List[Tuple[int, int, str]]:
        ngrams = []
        for start in range(len(tokens)):
            for end in range(start + 1, len(tokens) + 1):
                ngrams.append((start, end, " ".join(tokens[start:end])))
        return ngrams

    def _load_dictionary(self, path: str) -> Dict[str, Dict[str, List[str]]]:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict) and "languages" in data:
            data = data["languages"]

        if not isinstance(data, dict):
            raise ValueError("Intent dictionary must be a JSON object")

        return data

    def _build_phrase_entries(self, language: str) -> List[_PhraseEntry]:
        phrases_for_language = self._phrases_by_language.get(language)
        if not phrases_for_language:
            logger.warning(f"Language '{language}' not in dictionary; falling back to 'fr'")
            phrases_for_language = self._phrases_by_language.get("fr", {})

        entries: List[_PhraseEntry] = []
        for intent, phrases in phrases_for_language.items():
            if self._active_intents and intent not in self._active_intents:
                continue
            for phrase in phrases:
                normalized = normalize_text(phrase)
                if normalized:
                    phonetic = ""
                    if self._phonetic_enabled:
                        phonetic = self._phonetic_encoder.encode_pattern(normalized) or ""
                    entries.append(_PhraseEntry(intent=intent, phrase=normalized, phonetic=phonetic))

        return entries

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"[a-z0-9à-ÿ']+", text)

    def _should_use_phonetic(self, language: str) -> bool:
        if not self._phonetic_encoder.is_available():
            return False
        return language.startswith("fr")
