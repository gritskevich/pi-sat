"""
Language-dependent intent patterns (data only).

Kept separate from `modules/intent_engine.py` so the engine logic stays DRY and
language packs can evolve without touching classification code.

KISS: Only active intents are defined. Add more when needed.
"""

# ============================================================================
# ENGLISH INTENT PATTERNS
# ============================================================================

INTENT_PATTERNS_EN = {
    'play_music': {
        'triggers': [
            'play',
            'play song',
            'play music',
            'can you play',
            'could you play',
            'put on',
            'start playing',
            'i want to listen',
            'i want to hear',
        ],
        'extract': r'(?:play|put on|start playing|can you play|could you play|i want to (?:listen|hear)(?: to)?)\s+(?:to\s+)?(.+)',
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
            'tu peux jouer',
            'tu peux mettre',
            'peux tu jouer',
            'peux tu mettre',
            'peux jouer',
            'peux mettre',
            'mets la chanson',
            'je veux écouter',
            'je veux ecouter',
            'je veux entendre',
            'je voudrais écouter',
            'je voudrais ecouter',
            "j'aimerais ecouter",
            "j'aimerais écouter",
            "j'aimerais entendre",
            'je vais écouter',
        ],
        'extract': (
            r'(?:'
            r'joue|mets|mettre|lance|'
            r'fais\s+(?:moi\s+)?(?:jouer|écouter|ecouter)|'
            r'est\s+ce\s+que\s+tu\s+peux\s+(?:jouer|mettre)|'
            r'(?:pourrais\s+tu|tu\s+pourrais)\s+(?:jouer|mettre)|'
            r'tu\s+veux\s+bien\s+(?:jouer|mettre)|'
            r'je\s+veux\s+que\s+tu\s+(?:joues|mettes)|'
            r"j(?:'| )ai\s+envie\s+d(?:'|e)\s*(?:écouter|ecouter|entendre)|"
            r'tu\s+peux\s+(?:jouer|mettre)|'
            r'peux\s+(?:tu\s+)?(?:jouer|mettre)|'
            r'je\s+(?:veux|voudrais|vais)\s+(?:écouter|ecouter|entendre)|'
            r"j'aimerais\s+(?:écouter|ecouter|entendre)"
            r')\s+(?:moi\s+)?(.+)'
        ),
        'priority': 10,
    },
    'volume_up': {
        'triggers': [
            'plus fort',
            'monte le volume',
            'monte volume',
            'augmente',
            'augmente le volume',
            'augmente le son',
            'augmente volume',
            'plus de volume',
            'monte',
            'monte le son',
            'plus haut',
            'plus de son',
            'un peu plus fort',
            'encore plus fort',
            'plus',
            "j'entends pas",
            "j entends pas",
            "j'entends mal",
            "j entends mal",
            'on entend rien',
            'trop bas',
            'pousse',
            'pousse le son',
            'pousse le volume',
        ],
        'extract': None,
        'priority': 10,
    },
    'volume_down': {
        'triggers': [
            'moins fort',
            'baisse le volume',
            'baisse volume',
            'diminue',
            'diminue le volume',
            'diminue le son',
            'diminue volume',
            'moins de volume',
            'baisse',
            'baisse le son',
            'plus bas',
            'moins de son',
            'un peu moins fort',
            'encore moins fort',
            'moins',
            'trop fort',
            'c\'est trop fort',
            'c est trop fort',
            'mes oreilles',
            'doucement',
            'plus doucement',
            'chut',
            'chuchote',
        ],
        'extract': None,
        'priority': 10,
    },
    'stop': {
        'triggers': [
            'arrête',
            'arrete',
            'arrêter',
            'arreter',
            'stop',
            'arrête la musique',
            'arrete la musique',
            'arrête de jouer',
            'arrete de jouer',
            'arrête tout',
            'arrete tout',
            'éteins',
            'eteins',
            'éteins la musique',
            'eteins la musique',
            'éteins tout',
            'eteins tout',
            'coupe',
            'coupe la musique',
            'termine',
            'fini',
            'finis',
            'silence',
            'tais-toi',
            'tais toi',
        ],
        'extract': None,
        'priority': 10,
    },
}


# ============================================================================
# LANGUAGE REGISTRY
# ============================================================================

LANGUAGE_PATTERNS = {
    'en': INTENT_PATTERNS_EN,
    'fr': INTENT_PATTERNS_FR,
}

# Production intent scope: Essential commands for kids
# Only 4 core intents are active. Add more to this set as needed.
ACTIVE_INTENTS = {
    'play_music',    # Play any music by name
    'volume_up',     # Increase volume
    'volume_down',   # Decrease volume
    'stop',          # Stop playback
}
