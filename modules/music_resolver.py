"""
Music Resolver - Query Extraction + Catalog Resolution

Keeps IntentEngine music-agnostic by extracting song queries here.
KISS: one small service that turns an utterance into a catalog match.
"""

from dataclasses import dataclass
import re
from typing import Optional

from modules.music_library import MusicLibrary
from modules.intent_normalization import normalize_text


@dataclass
class MusicResolution:
    query: str
    matched_file: Optional[str]
    confidence: Optional[float]


class MusicResolver:
    def __init__(self, library: MusicLibrary):
        self.library = library

    def resolve(self, text: str, language: str = "fr", explicit_query: Optional[str] = None) -> MusicResolution:
        query = explicit_query or self.extract_query(text, language)
        if not query:
            query = text.strip()

        match = self.library.search_best(query) if query else None
        if not match:
            return MusicResolution(query=query, matched_file=None, confidence=None)

        file_path, confidence = match
        return MusicResolution(query=query, matched_file=file_path, confidence=confidence)

    @staticmethod
    def extract_query(text: str, language: str = "fr") -> str:
        text = normalize_text(text)
        if not text:
            return ""

        if language == "fr":
            pattern = (
                r"(?:joue|mets|mets-moi|mettre|lance|fais\s+jouer|"
                r"fais(?:\s+|-)?moi\s+écouter|peux\s+(?:tu\s+)?(?:jouer|mettre)|"
                r"tu\s+peux\s+(?:jouer|mettre)|je\s+veux\s+(?:écouter|entendre)|"
                r"je\s+voudrais\s+écouter|j'aimerais\s+(?:écouter|entendre))\s+"
                r"(?:moi\s+)?(?:la\s+chanson\s+)?(.+)"
            )
        else:
            pattern = r"(?:play|put on|start playing|listen to|hear)\s+(.+)"

        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return MusicResolver._clean_query(match.group(1).strip(), language)

        return MusicResolver._fallback_query(text, language)

    @staticmethod
    def _clean_query(query: str, language: str) -> str:
        query = query.strip().strip(".,!?;:")
        query = re.sub(r"\s+", " ", query)

        if language == "fr":
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

        return query

    @staticmethod
    def _fallback_query(text: str, language: str) -> str:
        text = normalize_text(text)
        if not text:
            return ""

        if language == "fr":
            verb_pattern = r"\b(joue|jouer|mets|mettre|met|lance|écoute|ecoute|écouter|ecouter|entendre|jouez|mettez)\b"
        else:
            verb_pattern = r"\b(play|put on|start playing|listen to|hear)\b"

        last_match = None
        for match in re.finditer(verb_pattern, text, re.IGNORECASE):
            last_match = match

        if not last_match:
            soft_trimmed = MusicResolver._soft_trim_leading(text, language)
            return soft_trimmed

        tail = text[last_match.end():].strip()
        if not tail:
            return ""

        tail = tail.lstrip(".,!?;:\"' ")
        if "," in tail:
            head = tail.split(",", 1)[0].strip()
            if len(head.split()) >= 2:
                tail = head

        tail = tail.replace(",", " ")
        tail = tail.strip().strip(".,!?;:\"'")
        tail = re.sub(r"\s+", " ", tail)

        filler_patterns = [
            r"^(?:moi|nous|vous)\s+",
            r"^(?:de|du|des|d')\s+la\s+musique\s+",
            r"^la\s+musique\s+",
            r"^une\s+chanson\s+",
            r"^un\s+truc\s+",
            r"^des\s+chansons\s+",
        ]
        for pattern in filler_patterns:
            tail = re.sub(pattern, "", tail, flags=re.IGNORECASE).strip()

        return tail

    @staticmethod
    def _soft_trim_leading(text: str, language: str) -> str:
        if language != "fr":
            return ""
        tokens = [t for t in normalize_text(text).split() if t]
        if len(tokens) < 3:
            return ""
        if tokens[0] in ("tu", "je", "j", "j'", "j'ai", "j’ai", "jai"):
            remainder = " ".join(tokens[2:]).strip()
            return remainder
        return ""
