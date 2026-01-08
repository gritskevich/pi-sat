import re
import logging
from typing import Dict, Optional, Tuple, List
from thefuzz import fuzz

import config
from modules.interfaces import Intent
from modules.intent_patterns import ACTIVE_INTENTS, LANGUAGE_PATTERNS
from modules.intent_matchers import build_intent_matcher_stack

# Logging
logger = logging.getLogger(__name__)

_FAST_INTENT_REGEX = {
    'en': {
        'stop': re.compile(r'\b(stop|turn\s+off)\b', re.IGNORECASE),
        'volume_up': re.compile(
            r'\b(louder|volume\s+up|turn\s+(?:it\s+)?up|increase\s+volume|raise\s+volume)\b',
            re.IGNORECASE
        ),
        'volume_down': re.compile(
            r'\b(quieter|volume\s+down|turn\s+(?:it\s+)?down|decrease\s+volume|lower\s+(?:the\s+)?volume)\b',
            re.IGNORECASE
        ),
    },
    'fr': {
        'stop': re.compile(r'\b(arr[êe]t(?:e|er)|stop|éteins|eteins)\b', re.IGNORECASE),
        'volume_up': re.compile(r'\b(plus\s+fort|plus\s+haut|monte(?:r)?|augmente(?:r)?)\b', re.IGNORECASE),
        'volume_down': re.compile(r'\b(moins\s+fort|plus\s+bas|baisse(?:r)?|diminue(?:r)?)\b', re.IGNORECASE),
    },
}


# ============================================================================
# INTENT ENGINE (Language-Aware)
# ============================================================================

class IntentEngine:
    REQUIRED_PARAMS_INTENTS = {
        'play_next',
        'add_to_queue',
        'sleep_timer',
        'set_alarm',
        'set_bedtime',
        'set_volume',
    }

    def __init__(
        self,
        fuzzy_threshold: int = 50,
        language: Optional[str] = None,
        debug: bool = False
    ):
        """
        Initialize Intent Engine.

        Args:
            fuzzy_threshold: Minimum fuzzy match score (0-100) to consider a match
            language: Language code ('en', 'fr', etc.). Auto-detected from config if None
            debug: Enable debug logging
        """
        self.fuzzy_threshold = fuzzy_threshold
        self.debug = debug
        self._sorted_patterns_cache: Dict[str, List[Tuple[str, Dict]]] = {}
        matcher_names = getattr(config, "INTENT_MATCHERS", None)
        if isinstance(matcher_names, str):
            matcher_names = [name.strip() for name in matcher_names.split(",") if name.strip()]
        if not matcher_names:
            matcher_names = ["text", "phonetic"]
        self._matcher_stack = build_intent_matcher_stack(
            matcher_names=matcher_names,
            phonetic_weight=getattr(config, "PHONETIC_WEIGHT", 0.6)
        )

        # Auto-detect language from config if not specified
        if language is None:
            language = getattr(config, 'LANGUAGE', 'fr')  # Default: French

        # Validate language
        if language not in LANGUAGE_PATTERNS:
            logger.warning(
                f"Language '{language}' not supported. Available: {list(LANGUAGE_PATTERNS.keys())}. "
                f"Falling back to 'fr' (default)"
            )
            language = 'fr'  # Default: French

        self.language = language
        self.intent_patterns = LANGUAGE_PATTERNS[language]
        self._sorted_patterns_cache[language] = self._sort_patterns(self.intent_patterns)

        if debug:
            logger.setLevel(logging.DEBUG)

        logger.info(
            f"Intent Engine initialized: "
            f"language={self.language}, "
            f"threshold={fuzzy_threshold}, "
            f"intents={len(self.intent_patterns)}"
        )

    def _score_trigger(self, text: str, trigger: str) -> Tuple[int, int, float]:
        breakdown = self._matcher_stack.score(text, trigger)
        text_score = int(breakdown.scores.get("text", 0))
        phonetic_score = int(breakdown.scores.get("phonetic", 0))
        return text_score, phonetic_score, float(breakdown.combined)

    def _best_trigger_match(self, text: str, triggers: List[str]) -> Tuple[str, float, int, int]:
        best_phrase = None
        best_score = 0.0
        best_text = 0
        best_phonetic = 0
        for trigger in triggers:
            text_score, phonetic_score, combined = self._score_trigger(text, trigger)
            if combined > best_score:
                best_score = combined
                best_phrase = trigger
                best_text = text_score
                best_phonetic = phonetic_score
        return best_phrase, best_score, best_text, best_phonetic

    def _sort_patterns(self, patterns: Dict[str, Dict]) -> List[Tuple[str, Dict]]:
        return sorted(
            patterns.items(),
            key=lambda x: x[1]['priority'],
            reverse=True
        )

    def _get_sorted_patterns(self, language: str, patterns: Dict[str, Dict]) -> List[Tuple[str, Dict]]:
        cached = self._sorted_patterns_cache.get(language)
        if cached is not None:
            return cached
        sorted_patterns = self._sort_patterns(patterns)
        self._sorted_patterns_cache[language] = sorted_patterns
        return sorted_patterns

    def _fast_classify(self, text: str, language: str) -> Optional[Intent]:
        """
        Fast-path classification for high-signal intents (stop/volume).

        Goal: avoid collisions where play triggers overlap with polite phrasing.
        """
        regex = _FAST_INTENT_REGEX.get(language)
        if not regex:
            return None

        if 'stop' in ACTIVE_INTENTS and regex['stop'].search(text):
            return Intent(intent_type='stop', confidence=1.0, parameters={}, raw_text=text, language=language)

        volume_up_match = 'volume_up' in ACTIVE_INTENTS and regex['volume_up'].search(text)
        volume_down_match = 'volume_down' in ACTIVE_INTENTS and regex['volume_down'].search(text)
        if volume_up_match and not volume_down_match:
            return Intent(intent_type='volume_up', confidence=1.0, parameters={}, raw_text=text, language=language)
        if volume_down_match and not volume_up_match:
            return Intent(intent_type='volume_down', confidence=1.0, parameters={}, raw_text=text, language=language)

        return None

    def classify(self, text: str, language: Optional[str] = None) -> Optional[Intent]:
        """
        Classify voice command into structured intent.

        Args:
            text: Transcribed voice command text
            language: Override language for this classification (optional)

        Returns:
            Intent object with classification and parameters, or None if no match
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for classification")
            return None

        raw_text = text
        text = text.strip().lower()
        text = (
            text.replace("peux-tu", "peux tu")
            .replace("pourrais-tu", "pourrais tu")
            .replace("est-ce", "est ce")
            .replace("mets-moi", "mets moi")
            .replace("mets-nous", "mets nous")
            .replace("fais-moi", "fais moi")
            .replace("fais-nous", "fais nous")
            .replace("balance-moi", "balance moi")
            .replace("envoie-moi", "envoie moi")
            .replace("vas-y", "vas y")
        )
        text = re.sub(r'^(?:ok|hey|salut)\s+alexa[\s,]+', '', text)
        text = re.sub(r'^alexa[\s,]+', '', text)
        logger.info(f"Intent request: raw='{raw_text}' cleaned='{text}'")

        # Use override language if specified
        if language and language in LANGUAGE_PATTERNS:
            patterns = LANGUAGE_PATTERNS[language]
            active_language = language
        else:
            patterns = self.intent_patterns
            active_language = self.language

        if self.debug:
            logger.debug(f"Classifying: '{text}' (language={active_language})")

        fast_intent = self._fast_classify(text, active_language)
        if fast_intent:
            logger.info(f"Intent answer: {fast_intent}")
            return fast_intent

        # Try each intent pattern, sorted by priority (cached)
        best_match = None
        best_score = 0

        for intent_type, pattern in self._get_sorted_patterns(active_language, patterns):
            if intent_type not in ACTIVE_INTENTS:
                continue
            if intent_type == 'play_music':
                if active_language == 'fr':
                    if not re.search(r'\b(joue|jouer|mets|mettre|lance|lancer|balance|envoie|écoute|ecoute|écouter|ecouter|entends|entendre|veux|voudrais|aimerais|pourrais|peux|fais|allez|vas)\b', text):
                        continue
                else:
                    if not re.search(r'(?:\bplay\b|\bput on\b|\bstart playing\b|\bi want to listen\b|\bi want to hear\b)', text):
                        continue
            if intent_type == 'pause':
                if active_language == 'fr':
                    if re.search(r'\b(joue|mets|lance)\b', text):
                        continue
                else:
                    if re.search(r'(?:\bplay\b|\bput on\b|\bstart playing\b)', text):
                        continue
            # Fuzzy match against all trigger phrases
            # Use token_set_ratio for better handling of extra words
            phrase, score, text_score, phonetic_score = self._best_trigger_match(text, pattern['triggers'])

            if phrase:
                if self.debug:
                    score_detail = f"text={text_score}"
                    if phonetic_score:
                        score_detail += f", phonetic={phonetic_score}"
                    logger.debug(f"  {intent_type}: {score:.1f} ({score_detail}) ('{phrase}')")

                if intent_type == 'stop':
                    if not re.search(r'\b(arrête|arrete|stop|coupe|éteins|eteins|suffit|assez|fini|silence)\b', text) and score < 80:
                        continue
                if intent_type == 'volume_up':
                    if not re.search(r'\b(plus fort|monte|augmente|plus haut)\b', text) and score < 80:
                        continue
                if intent_type == 'volume_down':
                    if not re.search(r'\b(moins fort|baisse|diminue|plus bas)\b', text) and score < 80:
                        continue

                # Check if score exceeds threshold and is better than previous best
                if score >= self.fuzzy_threshold and score > best_score:
                    extracted_params = None
                    if pattern['extract'] and intent_type in self.REQUIRED_PARAMS_INTENTS:
                        extracted_params = self._extract_parameters(
                            text,
                            pattern['extract'],
                            intent_type,
                            active_language
                        )
                        if not extracted_params:
                            continue
                    best_score = score
                    best_match = (intent_type, pattern, phrase, score, extracted_params)

        # If no match found
        if not best_match:
            logger.warning(f"No intent matched for: '{text}'")
            logger.info("Intent answer: None")
            return None

        intent_type, pattern, matched_phrase, score, extracted_params = best_match

        # Extract parameters if pattern has extraction regex
        parameters = {}
        if pattern['extract']:
            if extracted_params is not None:
                parameters = extracted_params
            else:
                parameters = self._extract_parameters(
                    text,
                    pattern['extract'],
                    intent_type,
                    active_language
                )

        # Convert score to 0.0-1.0 confidence
        confidence = score / 100.0

        intent = Intent(
            intent_type=intent_type,
            confidence=confidence,
            parameters=parameters,
            raw_text=text,
            language=active_language
        )

        logger.info(f"Intent answer: {intent}")
        return intent

    def _extract_parameters(
        self,
        text: str,
        regex_pattern: str,
        intent_type: str,
        language: str
    ) -> Dict:
        """
        Extract parameters from text using regex pattern.

        Args:
            text: Input text
            regex_pattern: Regex pattern with capture groups
            intent_type: Type of intent (for context-aware extraction)
            language: Language code for language-specific parsing

        Returns:
            Dict of extracted parameters
        """
        match = re.search(regex_pattern, text, re.IGNORECASE)

        if not match:
            return {}

        groups = match.groups()
        if not groups:
            return {}

        # For play_music/play_next/add_to_queue: extract song/artist name
        if intent_type in ('play_music', 'play_next', 'add_to_queue'):
            query = self._clean_play_query(groups[0].strip(), language)
            if intent_type == 'play_music' and language == 'fr':
                tokens = query.split()
                if len(tokens) >= 5:
                    sep_indices = [i for i, token in enumerate(tokens) if token in ("de", "par")]
                    sep_index = -1
                    for idx in reversed(sep_indices):
                        if len(tokens[idx + 1:]) >= 2:
                            sep_index = idx
                            break
                    if sep_index == -1 and sep_indices:
                        last_idx = sep_indices[-1]
                        if len(tokens) - last_idx - 1 >= 1 and last_idx >= 3:
                            sep_index = last_idx
                    if sep_index >= 2 and sep_index < len(tokens) - 1:
                        left_phrase = " ".join(tokens[:sep_index])
                        if left_phrase not in ("la musique", "musique", "la chanson", "chanson"):
                            song = " ".join(tokens[:sep_index]).strip()
                            artist = " ".join(tokens[sep_index + 1:]).strip()
                            if song and artist:
                                query = f"{song} {artist}"
            return {'query': query}

        # For sleep_timer: extract duration in minutes
        if intent_type == 'sleep_timer':
            try:
                raw_value = groups[0].strip().lower()
                if 'demi' in raw_value:
                    duration = 30
                else:
                    duration = int(raw_value)
                return {'duration_minutes': duration}
            except ValueError:
                logger.warning(f"Failed to parse duration: {groups[0]}")
                return {}

        # For set_alarm/set_bedtime: extract time
        if intent_type in ('set_alarm', 'set_bedtime'):
            time_str = groups[0].strip()

            # Normalize time format (language-aware)
            normalized_time = self._normalize_time(time_str, language)

            # Extract music query if present (for alarms with music)
            params = {'time': normalized_time}

            if intent_type == 'set_alarm':
                # Try to extract music query
                # English: "wake me at 7 with frozen"
                # French: "réveille-moi à 7 avec frozen"
                music_patterns = {
                    'en': r'(?:with|play)\s+(.+?)(?:\s+at\s+\d|$)',
                    'fr': r'(?:avec)\s+(.+?)(?:\s+à\s+\d|$)',
                }

                music_pattern = music_patterns.get(language, music_patterns['en'])
                music_match = re.search(music_pattern, text, re.IGNORECASE)

                if music_match:
                    params['music_query'] = music_match.group(1).strip()

            return params

        # For set_volume: extract volume level (0-100)
        if intent_type == 'set_volume':
            try:
                raw_value = groups[0].strip().lower()

                # French number words to integers
                french_numbers = {
                    'cinquante': 50,
                    'soixante': 60,
                    'soixante-dix': 70,
                    'soixante dix': 70,
                    'quatre-vingts': 80,
                    'quatre vingts': 80,
                    'cent': 100,
                }

                # Check if it's a French number word
                if raw_value in french_numbers:
                    volume = french_numbers[raw_value]
                else:
                    # Parse as integer
                    volume = int(raw_value)

                # Clamp to 0-100 range
                volume = max(0, min(100, volume))

                return {'volume': volume}
            except ValueError:
                logger.warning(f"Failed to parse volume level: {groups[0]}")
                return {}

        return {}

    def _clean_play_query(self, query: str, language: str) -> str:
        query = query.strip().strip(".,!?;:")
        query = re.sub(r'\s+', ' ', query)

        if language == 'fr':
            prefixes = [
                'tu peux jouer',
                'tu peux mettre',
                'est ce que tu peux jouer',
                'est ce que tu peux mettre',
                'pourrais tu jouer',
                'pourrais tu mettre',
                'tu pourrais jouer',
                'tu pourrais mettre',
                'tu veux bien jouer',
                'tu veux bien mettre',
                'je veux que tu joues',
                'je veux que tu mettes',
                "j'ai envie d'écouter",
                "j'ai envie d'entendre",
                'je veux écouter',
                'je veux ecouter',
                'je veux entendre',
                'je voudrais écouter',
                'je voudrais ecouter',
                "j'aimerais ecouter",
                'j\'aimerais écouter',
                'joue',
                'mets',
                'lance',
                'fais jouer',
                'fais moi écouter',
                'fais-moi écouter',
            ]
        else:
            prefixes = [
                'play',
                'put on',
                'start playing',
                'i want to hear',
                'i want to listen',
            ]

        lower_query = query.lower()
        for prefix in prefixes:
            if lower_query.startswith(prefix):
                query = query[len(prefix):].strip()
                break

        lower_query = query.lower()
        if language == 'fr':
            for filler in ("la chanson", "chanson"):
                if lower_query.startswith(f"{filler} "):
                    query = query[len(filler):].strip()
                    break

        query = query.strip().strip(".,!?;:")
        query = re.sub(r'\s+', ' ', query)

        if language != 'fr':
            query = re.sub(r'\bplease\b$', '', query, flags=re.IGNORECASE).strip()
            query = query.strip().strip(".,!?;:")
            query = re.sub(r'\s+', ' ', query)

        return query


    def _normalize_time(self, time_str: str, language: str) -> str:
        """
        Normalize time string to HH:MM 24-hour format.

        Args:
            time_str: Time like "7", "7am", "7:30", "7:30 pm", "21h", "21 heures"
            language: Language code for language-specific parsing

        Returns:
            Normalized time in HH:MM format
        """
        time_str = time_str.lower().strip()

        # Language-specific parsing
        if language == 'fr':
            # French: "7h", "21 heures", "7h30"
            time_str = time_str.replace('h', ':').replace('heures', ':').replace('heure', ':')
            # Remove trailing colons
            time_str = time_str.rstrip(':')

        # Extract AM/PM if present (English)
        is_pm = 'pm' in time_str
        is_am = 'am' in time_str

        # Remove am/pm markers
        time_str = time_str.replace('am', '').replace('pm', '').strip()

        # Split hour and minute
        if ':' in time_str:
            parts = time_str.split(':')
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 and parts[1] else 0
        else:
            hour = int(time_str)
            minute = 0

        # Convert to 24-hour format (English AM/PM)
        if is_pm and hour < 12:
            hour += 12
        elif is_am and hour == 12:
            hour = 0

        return f"{hour:02d}:{minute:02d}"

    def get_supported_intents(self) -> List[str]:
        """Get list of supported intent types"""
        return list(self.intent_patterns.keys())

    def get_supported_languages(self) -> List[str]:
        """Get list of supported languages"""
        return list(LANGUAGE_PATTERNS.keys())

    def set_language(self, language: str) -> bool:
        """
        Change the active language.

        Args:
            language: Language code ('en', 'fr', etc.)

        Returns:
            True if language changed successfully
        """
        if language not in LANGUAGE_PATTERNS:
            logger.error(
                f"Language '{language}' not supported. "
                f"Available: {list(LANGUAGE_PATTERNS.keys())}"
            )
            return False

        self.language = language
        self.intent_patterns = LANGUAGE_PATTERNS[language]
        logger.info(f"Language changed to: {language}")
        return True

