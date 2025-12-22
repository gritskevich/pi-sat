# Phonetic Music Search (Hybrid) — Architecture

Goal: make **FR speech → EN filenames** work reliably with a tiny library, offline, KISS.

## Canonical Code

- Matching engine: `modules/music_library.py`
- Query extraction: `modules/music_resolver.py`
- Playback + wiring: `modules/mpd_controller.py`
- Tests: `tests/test_music_library.py`, `tests/test_music_resolver.py`

## Data Flow (what happens on “play X”)

- STT text → IntentEngine extracts `play_music` intent (`modules/intent_engine.py`)
- `MusicResolver` extracts a **query** from the utterance (language-aware regex)
- `MusicLibrary.search_best(query)` returns `(file_path, confidence)`:
  - “best match” UX (threshold forced to 0)
  - confidence is still computed and logged
- MPD plays by file path (`modules/mpd_controller.py`)

## Matching Algorithm (high signal)

- **Variants per song** are derived from the filename:
  - full basename
  - split on `" - "` (artist / title / tail)
  - normalized (accents stripped + alnum only) for robustness
- **Hybrid scoring** when phonetics are available:
  - text fuzzy score (thefuzz `token_set_ratio`)
  - Beider‑Morse phonetic score (Abydos) on a restricted subset
  - combined score = `(text * (1-w)) + (phonetic * w)`, default `w=0.6`
- **Phonetic guardrails** (`_phonetic_allowed`):
  - ignore very short queries (≤4 chars), very long, or ≥3-token phrases
  - keeps phonetics fast and reduces garbage matches

## Knobs (where to tune)

- Text match threshold: `config.FUZZY_MATCH_THRESHOLD` (used by `MusicLibrary.search`)
- Hybrid weight: `phonetic_weight` (wired in `modules/mpd_controller.py`)
- Turn phonetics on/off: `phonetic_enabled` (defaults on; auto-disables if Abydos missing)

## Debug / QA

- Run library matching sanity: `python scripts/test_phonetic_search.py`
- Run unit tests: `pytest tests/test_music_library.py -q`
- Inspect logs: look for `modules.music_library: Search:` lines (query → match + confidence)
