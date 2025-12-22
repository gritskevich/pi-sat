# Music Library Organization (Practical)

Pi‑Sat plays whatever MPD exposes. Keep MPD and Pi‑Sat pointed at the **same** music directory.

## Source of Truth

- MPD config: `~/.mpd/mpd.conf` → `music_directory "~/Music"`
- Pi‑Sat config: `config.py` → `MUSIC_LIBRARY = ~/Music` (used for defaults + docs/tests)

## Recommended Layout (KISS)

- Small kid library: **flat directory** with files named like `Artist - Title.mp3`
- Subfolders are OK (MPD will index them), but keep names short and consistent.

## Matching Tips (helps STT + fuzzy + phonetic)

- Prefer `Artist - Title` over cryptic filenames.
- Keep “feat.” style consistent (commas are fine).
- Avoid ultra-long names; avoid 3+ word “junk prefixes” (e.g. “Official Video …”).
- Accents/UTF‑8 are fine (normalization handles them).

## Operational Checklist

- After adding/removing files:
  - `mpc update`
  - `mpc stats` (song count sanity)
- If Pi‑Sat “can’t find” songs:
  - confirm MPD is pointing at the right `music_directory`
  - run `mpc outputs` (ensure an output is enabled)

## See Also

- Matching internals: `docs/PHONETIC_SEARCH_ARCHITECTURE.md`
- Playback internals: `modules/mpd_controller.py`
