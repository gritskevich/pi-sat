"""
Intent Engine - Multi-Language Voice Command Classification

Language-aware fuzzy matching for intent classification.
Supports English and French with easy extensibility for additional languages.

Key Features:
- Multi-language support (English, French, easily extensible)
- Fuzzy matching with thefuzz library (tolerates typos)
- Language-specific parameter extraction
- Automatic language detection from config
- No translation required - direct pattern matching
- Fast, deterministic, offline classification

Architecture:
- Separate pattern dictionaries per language (INTENT_PATTERNS_EN, INTENT_PATTERNS_FR)
- Shared fuzzy matching logic (DRY)
- Language-aware regex extraction
- Auto-selects language based on config.HAILO_STT_LANGUAGE

Supported Languages:
- English (en)
- French (fr)
- Extensible: Add new language dict to LANGUAGE_PATTERNS

Supported Intents (20+):
- play_music, play_favorites, pause, resume, stop, next, previous
- volume_up, volume_down, add_favorite, sleep_timer
- repeat_song, repeat_off, shuffle_on, shuffle_off
- play_next, add_to_queue
- set_alarm, cancel_alarm
- check_bedtime, set_bedtime, check_time_limit
"""

import re
import logging
from typing import Dict, Optional, Tuple, List
from thefuzz import fuzz, process

import config
from modules.interfaces import Intent

# Logging
logger = logging.getLogger(__name__)


# ============================================================================
# ENGLISH INTENT PATTERNS
# ============================================================================

INTENT_PATTERNS_EN = {
    'play_music': {
        'triggers': [
            'play',
            'play song',
            'play music',
            'put on',
            'start playing',
        ],
        'extract': r'(?:play|put on|start playing)\s+(.+)',
        'priority': 10,
    },
    'play_favorites': {
        'triggers': [
            'play my favorites',
            'play favorites',
            'play my favourite',
            'play favourite',
            'play what i like',
        ],
        'extract': None,
        'priority': 5,
    },
    'pause': {
        'triggers': [
            'pause',
            'pause music',
            'pause song',
            'pause playback',
        ],
        'extract': None,
        'priority': 10,
    },
    'resume': {
        'triggers': [
            'resume',
            'continue',
            'unpause',
            'keep playing',
            'start again',
        ],
        'extract': None,
        'priority': 10,
    },
    'stop': {
        'triggers': [
            'stop',
            'stop music',
            'stop playing',
            'turn off',
        ],
        'extract': None,
        'priority': 10,
    },
    'next': {
        'triggers': [
            'next',
            'next song',
            'next track',
            'skip',
            'skip song',
            'skip this',
        ],
        'extract': None,
        'priority': 10,
    },
    'previous': {
        'triggers': [
            'previous',
            'previous song',
            'previous track',
            'go back',
            'back',
            'last song',
        ],
        'extract': None,
        'priority': 10,
    },
    'volume_up': {
        'triggers': [
            'louder',
            'volume up',
            'turn it up',
            'increase volume',
            'raise volume',
        ],
        'extract': None,
        'priority': 10,
    },
    'volume_down': {
        'triggers': [
            'quieter',
            'volume down',
            'turn it down',
            'decrease volume',
            'lower volume',
            'lower the volume',
        ],
        'extract': None,
        'priority': 10,
    },
    'add_favorite': {
        'triggers': [
            'i love this',
            'i love this song',
            'love this',
            'like this',
            'like this song',
            'add to favorites',
            'add to favourites',
            'favorite this',
            'favourite this',
            'save this',
            'save this song',
        ],
        'extract': None,
        'priority': 10,
    },
    'sleep_timer': {
        'triggers': [
            'stop in 30 minutes',
            'stop in 15 minutes',
            'stop in 60 minutes',
            'turn off in 30 minutes',
            'sleep timer 30 minutes',
            'set sleep timer',
            'set timer',
        ],
        'extract': r'(?:stop|turn off|timer)\s+(?:in\s+)?(\d+)\s*(?:minute|min)',
        'priority': 20,
    },
    'repeat_song': {
        'triggers': [
            'repeat this',
            'repeat this song',
            'play this again',
            'play this on repeat',
            'keep repeating',
            'loop this',
            'loop this song',
        ],
        'extract': None,
        'priority': 10,
    },
    'repeat_off': {
        'triggers': [
            'stop repeating',
            'turn off repeat',
            'no more repeat',
            'repeat off',
            'stop looping',
        ],
        'extract': None,
        'priority': 10,
    },
    'shuffle_on': {
        'triggers': [
            'shuffle',
            'turn on shuffle',
            'shuffle mode',
            'play random',
            'random songs',
            'mix it up',
        ],
        'extract': None,
        'priority': 10,
    },
    'shuffle_off': {
        'triggers': [
            'stop shuffle',
            'turn off shuffle',
            'no shuffle',
            'shuffle off',
            'play in order',
        ],
        'extract': None,
        'priority': 10,
    },
    'play_next': {
        'triggers': [
            'play frozen next',
            'play beatles next',
            'next play frozen',
            'add frozen to next',
        ],
        'extract': r'(?:play|next|add)\s+(.+?)\s+(?:next|after this)',
        'priority': 15,
    },
    'add_to_queue': {
        'triggers': [
            'add frozen to queue',
            'add beatles',
            'queue frozen',
            'add to playlist',
        ],
        'extract': r'(?:add|queue)\s+(.+?)(?:\s+to\s+(?:queue|playlist))?',
        'priority': 10,
    },
    'set_alarm': {
        'triggers': [
            'wake me up at 7',
            'set alarm for 7 am',
            'wake me at 7 with frozen',
            'alarm at 7',
            'morning alarm 7 am',
        ],
        'extract': r'(?:wake|alarm)\s+(?:me\s+)?(?:up\s+)?(?:at\s+|for\s+)?(\d{1,2}(?::\d{2})?(?:\s*(?:am|pm))?)',
        'priority': 15,
    },
    'cancel_alarm': {
        'triggers': [
            'cancel alarm',
            'cancel my alarm',
            'turn off alarm',
            'no alarm',
            'delete alarm',
        ],
        'extract': None,
        'priority': 10,
    },
    'check_bedtime': {
        'triggers': [
            'what is my bedtime',
            'when is bedtime',
            'what time is bedtime',
            'when do i go to bed',
            'check bedtime',
        ],
        'extract': None,
        'priority': 10,
    },
    'check_time_limit': {
        'triggers': [
            'how much time left',
            'how much time do i have',
            'time remaining',
            'check my time',
            'how long can i listen',
        ],
        'extract': None,
        'priority': 10,
    },
    'set_bedtime': {
        'triggers': [
            'set bedtime to 9 pm',
            'change bedtime to 9',
            'bedtime at 9',
            'make bedtime 9 pm',
        ],
        'extract': r'(?:set|change|make)\s+bedtime\s+(?:to\s+|at\s+)?(\d{1,2}(?::\d{2})?(?:\s*(?:am|pm))?)',
        'priority': 15,
    },
}


# ============================================================================
# FRENCH INTENT PATTERNS
# ============================================================================

INTENT_PATTERNS_FR = {
    'play_music': {
        'triggers': [
            'joue',
            'joue chanson',
            'joue musique',
            'mets',
            'mettre',
            'lance',
            'joue moi',
            'mets moi',
            'mets-moi',
            'fais jouer',
            'fais moi écouter',
            'fais-moi écouter',
            'tu peux jouer',
            'tu peux mettre',
            'peux tu jouer',
            'peux tu mettre',
            'peux jouer',
            'peux mettre',
            'mets la chanson',
            'je veux écouter',
            'je veux entendre',
            'je voudrais écouter',
            'j\'aimerais écouter',
            'j\'aimerais entendre',
            'je vais écouter',
        ],
        'extract': r'(?:joue|mets|lance|peux\s+(?:tu\s+)?jouer|tu\s+peux\s+jouer)\s+(?:moi\s+)?(.+)',
        'priority': 10,
    },
    'play_favorites': {
        'triggers': [
            'joue mes favoris',
            'joue mes préférés',
            'joue ce que j\'aime',
            'joue favoris',
            'mes favoris',
            'mes préférés',
        ],
        'extract': None,
        'priority': 5,
    },
    'pause': {
        'triggers': [
            'pause',
            'mets en pause',
            'pause la musique',
            'pause chanson',
        ],
        'extract': None,
        'priority': 10,
    },
    'resume': {
        'triggers': [
            'reprends',
            'continue',
            'relance',
            'enlève la pause',
            'redémarre',
        ],
        'extract': None,
        'priority': 10,
    },
    'stop': {
        'triggers': [
            'arrête',
            'stop',
            'arrête la musique',
            'arrête de jouer',
            'éteins',
        ],
        'extract': None,
        'priority': 10,
    },
    'next': {
        'triggers': [
            'suivant',
            'suivante',
            'chanson suivante',
            'piste suivante',
            'passe',
            'skip',
            'saute',
        ],
        'extract': None,
        'priority': 10,
    },
    'previous': {
        'triggers': [
            'précédent',
            'précédente',
            'chanson précédente',
            'piste précédente',
            'retour',
            'avant',
            'dernière chanson',
        ],
        'extract': None,
        'priority': 10,
    },
    'volume_up': {
        'triggers': [
            'plus fort',
            'monte le volume',
            'augmente',
            'plus de volume',
            'monte',
            'plus haut',
        ],
        'extract': None,
        'priority': 10,
    },
    'volume_down': {
        'triggers': [
            'moins fort',
            'baisse le volume',
            'diminue',
            'moins de volume',
            'baisse',
            'plus bas',
        ],
        'extract': None,
        'priority': 10,
    },
    'add_favorite': {
        'triggers': [
            'j\'adore',
            'j\'adore ça',
            'j\'aime',
            'j\'aime cette chanson',
            'j\'aime ça',
            'ajoute aux favoris',
            'ajoute aux préférés',
            'favori',
            'sauvegarde',
            'garde ça',
        ],
        'extract': None,
        'priority': 10,
    },
    'sleep_timer': {
        'triggers': [
            'arrête dans 30 minutes',
            'arrête dans 15 minutes',
            'arrête dans 60 minutes',
            'arrête dans une demi-heure',
            'éteins dans 30 minutes',
            'éteins dans 5 minutes',
            'stop dans 20 minutes',
            'stop dans 30 minutes',
            'minuterie 30 minutes',
            'mets une minuterie',
            'minuterie de sommeil',
        ],
        'extract': r'(?:arrête|arrete|éteins|eteins|stop|minuterie)\s+(?:dans\s+|de\s+)?(\d+|une\s+demi-heure|demi-heure|demie\s+heure)\s*(?:minute|min)?',
        'priority': 20,
    },
    'repeat_song': {
        'triggers': [
            'répète',
            'répète ça',
            'répète cette chanson',
            'rejoue',
            'rejoue ça',
            'mets en boucle',
            'en boucle',
        ],
        'extract': None,
        'priority': 10,
    },
    'repeat_off': {
        'triggers': [
            'arrête de répéter',
            'enlève la répétition',
            'plus de répétition',
            'répétition off',
            'enlève la boucle',
        ],
        'extract': None,
        'priority': 10,
    },
    'shuffle_on': {
        'triggers': [
            'mélange',
            'melange',
            'aléatoire',
            'mode aléatoire',
            'joue au hasard',
            'au hasard',
            'mixe',
        ],
        'extract': None,
        'priority': 10,
    },
    'shuffle_off': {
        'triggers': [
            'arrête de mélanger',
            'plus d\'aléatoire',
            'aléatoire off',
            'en ordre',
            'dans l\'ordre',
        ],
        'extract': None,
        'priority': 10,
    },
    'play_next': {
        'triggers': [
            'joue frozen ensuite',
            'joue beatles après',
            'suivant frozen',
            'après joue frozen',
            'mets frozen après',
        ],
        'extract': r'(?:joue|mets|suivant)\s+(.+?)\s+(?:ensuite|après)',
        'priority': 15,
    },
    'add_to_queue': {
        'triggers': [
            'ajoute frozen',
            'ajoute beatles',
            'ajoute à la file',
            'file d\'attente frozen',
            'ajoute à la playlist',
        ],
        'extract': r'(?:ajoute|file)\s+(?:d\'attente\s+)?(.+?)(?:\s+(?:à la file|à la playlist))?',
        'priority': 10,
    },
    'set_alarm': {
        'triggers': [
            'réveille-moi à 7',
            'réveille moi à 7',
            'alarme à 7 heures',
            'mets une alarme',
            'alarme pour 7',
            'réveille-moi à 7 avec frozen',
        ],
        'extract': r'(?:réveille|alarme)\s+(?:moi\s+)?(?:à\s+|pour\s+)?(\d{1,2}(?::\d{2})?(?:\s*(?:h|heures?))?)',
        'priority': 15,
    },
    'cancel_alarm': {
        'triggers': [
            'annule l\'alarme',
            'annule alarme',
            'enlève l\'alarme',
            'pas d\'alarme',
            'supprime alarme',
        ],
        'extract': None,
        'priority': 10,
    },
    'check_bedtime': {
        'triggers': [
            'c\'est quand l\'heure du coucher',
            'quelle est mon heure de coucher',
            'quand je vais au lit',
            'c\'est quand mon coucher',
            'heure de coucher',
        ],
        'extract': None,
        'priority': 10,
    },
    'check_time_limit': {
        'triggers': [
            'combien de temps il reste',
            'combien de temps j\'ai',
            'temps restant',
            'mon temps restant',
            'combien je peux écouter',
        ],
        'extract': None,
        'priority': 10,
    },
    'set_bedtime': {
        'triggers': [
            'mets l\'heure du coucher à 21',
            'change l\'heure du coucher',
            'coucher à 21 heures',
            'heure de coucher 21',
        ],
        'extract': r'(?:mets|change)\s+(?:l\')?heure\s+(?:du\s+)?coucher\s+(?:à\s+)?(\d{1,2}(?::\d{2})?(?:\s*(?:h|heures?))?)',
        'priority': 15,
    },
}


# ============================================================================
# LANGUAGE REGISTRY
# ============================================================================

LANGUAGE_PATTERNS = {
    'en': INTENT_PATTERNS_EN,
    'fr': INTENT_PATTERNS_FR,
}

# Production intent scope: Only essential commands for kids
# Keep it simple: play, stop, volume control
ACTIVE_INTENTS = {
    'play_music',
    'stop',
    'volume_up',
    'volume_down',
}


# ============================================================================
# INTENT ENGINE (Language-Aware)
# ============================================================================

class IntentEngine:
    """
    Multi-language fuzzy command classification engine.

    Maps voice commands to structured intents using language-aware fuzzy matching.
    No machine learning, no translation, no LLM required.
    """

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

        # Auto-detect language from config if not specified
        if language is None:
            language = getattr(config, 'HAILO_STT_LANGUAGE', 'fr')  # Default: French

        # Validate language
        if language not in LANGUAGE_PATTERNS:
            logger.warning(
                f"Language '{language}' not supported. Available: {list(LANGUAGE_PATTERNS.keys())}. "
                f"Falling back to 'fr' (default)"
            )
            language = 'fr'  # Default: French

        self.language = language
        self.intent_patterns = LANGUAGE_PATTERNS[language]

        if debug:
            logger.setLevel(logging.DEBUG)

        logger.info(
            f"Intent Engine initialized: "
            f"language={self.language}, "
            f"threshold={fuzzy_threshold}, "
            f"intents={len(self.intent_patterns)}"
        )

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
        text = text.replace("peux-tu", "peux tu").replace("peux-tu", "peux tu")
        text = text.replace("mets-moi", "mets moi").replace("fais-moi", "fais moi")
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

        # Try each intent pattern, sorted by priority
        best_match = None
        best_score = 0
        required_params_intents = {
            'play_next',
            'add_to_queue',
            'sleep_timer',
            'set_alarm',
            'set_bedtime',
        }

        for intent_type, pattern in sorted(
            patterns.items(),
            key=lambda x: x[1]['priority'],
            reverse=True
        ):
            if intent_type not in ACTIVE_INTENTS:
                continue
            if intent_type == 'play_music':
                if not re.search(r'\b(joue|mets|mettre|lance|écoute|écouter|entendre|veux|voudrais|aimerais|peux|fais)\b', text):
                    continue
            if intent_type == 'pause':
                if re.search(r'\b(joue|mets|lance)\b', text):
                    continue
            # Fuzzy match against all trigger phrases
            # Use token_set_ratio for better handling of extra words
            match_result = process.extractOne(
                text,
                pattern['triggers'],
                scorer=fuzz.token_set_ratio
            )

            if match_result:
                phrase, score = match_result[0], match_result[1]

                if self.debug:
                    logger.debug(f"  {intent_type}: {score} ('{phrase}')")

                if intent_type == 'stop':
                    if not re.search(r'\b(arrête|arrete|stop)\b', text) and score < 80:
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
                    if pattern['extract'] and intent_type in required_params_intents:
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

        return {}

    def _clean_play_query(self, query: str, language: str) -> str:
        query = query.strip().strip(".,!?;:")
        query = re.sub(r'\s+', ' ', query)

        if language == 'fr':
            prefixes = [
                'tu peux jouer',
                'tu peux mettre',
                'je veux écouter',
                'je veux ecouter',
                'je veux entendre',
                'je voudrais écouter',
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

    def search_music(self, query: str, music_library: List[str]) -> Optional[Tuple[str, float]]:
        """
        Fuzzy search music library for best match.

        Handles typos and partial matches (e.g., "frozzen" → "Frozen").

        Args:
            query: Search query (song name, artist, etc.)
            music_library: List of available songs/artists

        Returns:
            Tuple of (matched_item, confidence) or None if no match
        """
        if not query or not music_library:
            return None

        query = query.strip().lower()

        # Use fuzzy matching to find best match
        # token_set_ratio handles partial matches better
        match_result = process.extractOne(
            query,
            music_library,
            scorer=fuzz.token_set_ratio
        )

        if not match_result:
            return None

        matched_item, score = match_result[0], match_result[1]

        # Convert score to confidence
        confidence = score / 100.0

        if score < self.fuzzy_threshold:
            logger.warning(f"Music search '{query}' below threshold: {score}")
            return None

        logger.info(f"Music search: '{query}' → '{matched_item}' ({confidence:.2f})")
        return (matched_item, confidence)

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


def main():
    """Test multi-language intent classification"""
    import logging
    logging.basicConfig(level=logging.INFO)

    print("Multi-Language Intent Classification Test\n")
    print("=" * 80)

    # Test English
    print("\n" + "=" * 80)
    print("ENGLISH TESTS")
    print("=" * 80)

    engine_en = IntentEngine(language='en', debug=True)

    test_commands_en = [
        "Play Frozen",
        "Play the Beatles",
        "Pause",
        "Volume up",
        "I love this song",
        "Stop in 30 minutes",
        "Repeat this song",
        "Shuffle",
        "Play Frozen next",
        "Wake me up at 7 AM",
        "What's my bedtime?",
    ]

    for cmd in test_commands_en:
        print(f"\nCommand: '{cmd}'")
        intent = engine_en.classify(cmd)

        if intent:
            print(f"  ✓ Intent: {intent.intent_type}")
            print(f"  ✓ Confidence: {intent.confidence:.2%}")
            if intent.parameters:
                print(f"  ✓ Parameters: {intent.parameters}")
        else:
            print("  ✗ No match")

    # Test French
    print("\n" + "=" * 80)
    print("FRENCH TESTS")
    print("=" * 80)

    engine_fr = IntentEngine(language='fr', debug=True)

    test_commands_fr = [
        "Joue Frozen",
        "Joue les Beatles",
        "Pause",
        "Plus fort",
        "J'adore cette chanson",
        "Arrête dans 30 minutes",
        "Répète cette chanson",
        "Mélange",
        "Joue Frozen ensuite",
        "Réveille-moi à 7 heures",
        "C'est quand mon heure de coucher?",
    ]

    for cmd in test_commands_fr:
        print(f"\nCommande: '{cmd}'")
        intent = engine_fr.classify(cmd)

        if intent:
            print(f"  ✓ Intent: {intent.intent_type}")
            print(f"  ✓ Confidence: {intent.confidence:.2%}")
            if intent.parameters:
                print(f"  ✓ Paramètres: {intent.parameters}")
        else:
            print("  ✗ Pas de correspondance")

    # Test language auto-detection from config
    print("\n" + "=" * 80)
    print("AUTO-DETECTION TEST (from config)")
    print("=" * 80)

    engine_auto = IntentEngine(debug=True)
    print(f"\nAuto-detected language: {engine_auto.language}")
    print(f"Supported languages: {engine_auto.get_supported_languages()}")
    print(f"Supported intents: {len(engine_auto.get_supported_intents())}")


if __name__ == '__main__':
    main()
