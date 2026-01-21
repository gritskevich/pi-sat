import re


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = text.replace("-", " ")
    text = re.sub(r"\balexa\b", "", text)
    text = re.sub(r"\bmontant\b", "monte", text)
    text = re.sub(r"[^a-z0-9à-ÿ'\s]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_query(query: str) -> str:
    query = query.strip()
    if not query:
        return ""
    query = re.sub(
        r"\b(?:s[' ]?il\s+te\s+pla[iî]t|stp|svp|merci)\b",
        "",
        query,
        flags=re.IGNORECASE
    )
    query = re.sub(r"\s+", " ", query).strip()
    tokens = query.split()
    if len(tokens) >= 3 and tokens[0] in ("tu", "je", "j", "on", "nous", "vous"):
        tokens = tokens[1:]
    if len(tokens) >= 3 and tokens[0] in ("peux", "veux", "voudrais", "aimerais"):
        tokens = tokens[1:]
    return " ".join(tokens).strip()
