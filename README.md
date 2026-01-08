# Pi‑Sat

Offline, local‑first voice‑controlled music player for kids (Raspberry Pi 5 + Hailo‑8L).

## What it does

- Wake word: **“Alexa”** (openWakeWord)
- Record command (VAD) → STT (Hailo Whisper) → deterministic intent (fuzzy) → MPD playback
- Offline TTS feedback (Piper)
- Continuous shuffle by default (MPD random + repeat playlist). Override with `DEFAULT_SHUFFLE_MODE=false` or `DEFAULT_REPEAT_MODE=off`.

## Quick start

```bash
./pi-sat.sh install
./pi-sat.sh download_voice

# MPD needs a config at ~/.mpd/mpd.conf (see INSTALL.md), then:
mpc update

./pi-sat.sh run
```

## Voice commands (active intents)

French (default, `LANGUAGE=fr`):
- Play: `joue <titre/artiste>`
- Stop: `arrête` / `stop`
- Volume up: `plus fort` / `monte le volume`
- Volume down: `moins fort` / `baisse le volume`

English (optional, `LANGUAGE=en`):
- `play <song>`, `stop`, `louder`, `quieter`

To enable more intents, edit `ACTIVE_INTENTS` in `modules/intent_engine.py`.

## Docs

- `INSTALL.md` – setup on Raspberry Pi 5
- `AGENTS.md` / `CLAUDE.md` – AI/dev quick reference
- `docs/README.md` – doc map
- `tests/README.md` – tests

For issues, questions, or feature requests:
- GitHub Issues: https://github.com/gritskevich/pi-sat/issues
- Discussions: https://github.com/gritskevich/pi-sat/discussions
