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
sox resources/beep-short.wav -t raw -r 48000 -e signed -b 16 -c 1 - repeat 2 pad 0.03 0.05 | pw-play --format s16 --rate 48000 --channels 1 --volume 1.0 -
mpc play
```

If the wake beep is silent when idle, confirm PipeWire user services are running:
```bash
systemctl --user status pipewire pipewire-pulse wireplumber
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
  - `export LANGUAGE=fr` (or `en`)
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
