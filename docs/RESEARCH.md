# Research / Decisions (Condensed)

This is a short “why we did it this way” note. Prefer code + tests for implementation details.

## Core Decisions

- **No LLM for intent**: `modules/intent_engine.py` is deterministic, fast (<1ms), no hallucinations.
- **MPD for playback**: stable daemon, low resources, simple control surface (`mpc` for debugging).
- **Hailo Whisper for STT**: `whisper-base` on-device, forced language via `config.HAILO_STT_LANGUAGE`.
- **Hybrid phonetic search**: improves FR speech → EN filenames; see `docs/PHONETIC_SEARCH_ARCHITECTURE.md`.
- **Volume isolation**: music via MPD volume; TTS/beep via per-stream scaling (sox) — see `docs/AUDIO.md`.

## Benchmarks / Tools

- STT benchmarks: `python scripts/benchmark_stt.py`
- E2E diagnostic (timing WAVs + JSON): `python scripts/test_e2e_diagnostic.py`
- Phonetic search sanity: `python scripts/test_phonetic_search.py`

## When to Revisit

- Library grows large (≫1k tracks): consider faster fuzzy backend (RapidFuzz) and/or indexed search.
- Multi-room / UI needs: consider MPD event/idle usage (not needed today).
- Latency regressions: profile the pipeline; keep “wake → music” within kid patience window.
