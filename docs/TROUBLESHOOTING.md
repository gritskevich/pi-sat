# Troubleshooting

Short, high-signal triage for Pi‑Sat.

## Start Here

```bash
# Live pipeline logs (wake → record → STT → intent)
./pi-sat.sh run_live

# MPD basics
mpc status
mpc outputs

# Device visibility
aplay -l
arecord -l

# Hailo sanity check
./pi-sat.sh hailo_check
```

## No Sound (music / beep / TTS)

Canonical checklist: `docs/AUDIO.md`.

Quick sanity:
```bash
aplay -D default -q resources/beep-short.wav
mpc play
```

## MPD Problems

- MPD config exists: `cat ~/.mpd/mpd.conf`
- Restart:
  ```bash
  mpd --kill && mpd ~/.mpd/mpd.conf
  mpc update && mpc status
  ```
- Output enabled: `mpc outputs`

## Wake Word Problems

- Tune in `config.py`:
  - `THRESHOLD` (wake sensitivity)
  - `WAKE_WORD_COOLDOWN` (ignore activations after one fires; default is 3s)
- Feedback loop fixes:
  - Lower `VOLUME_DUCK_LEVEL` (even `0`)
  - Reduce mic gain / disable AGC (hardware dependent)
- Debug:
  - `./pi-sat.sh run_debug` (watch confidence and timing)

## STT Problems (Hailo Whisper)

- Force language:
  - `export HAILO_STT_LANGUAGE=fr` (or `en`)
- If STT returns empty:
  - increase `MAX_RECORDING_TIME`
  - tune VAD: `VAD_LEVEL`, `SILENCE_THRESHOLD`, `VAD_SPEECH_MULTIPLIER`, `VAD_SILENCE_DURATION`
- Hardware tests:
  ```bash
  export PISAT_RUN_HAILO_TESTS=1
  pytest tests/test_language_detection.py -v -s
  ```

## Clean Restart

```bash
killall python3 || true
mpd --kill || true
./pi-sat.sh logs_clear
./pi-sat.sh run
```

## See Also

- `docs/AUDIO.md`
- `tests/README.md`
- `docs/IMPLEMENTATION_PATTERNS.md`
