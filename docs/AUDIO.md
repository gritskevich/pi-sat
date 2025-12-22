# Audio (MPD + TTS + Beep)

Single source of truth for **audio routing + volume behavior**.

## Outputs (what uses what)

- **Music**: MPD → ALSA device from `~/.mpd/mpd.conf` (recommended: `mixer_type "software"`).
- **TTS**: Piper → `aplay -D $PIPER_OUTPUT_DEVICE` (software volume via `sox`).
- **Wake beep**: `modules/audio_player.py` → `aplay -D $OUTPUT_ALSA_DEVICE` (software volume via `sox`).

`config.py` defaults both `PIPER_OUTPUT_DEVICE` and `OUTPUT_ALSA_DEVICE` to `default`.

## Quick checks

```bash
# 1) Is the speaker visible?
aplay -l

# 2) Can ALSA play anything?
aplay -D default -q resources/beep-short.wav

# 3) Is MPD alive and playing?
mpc status
mpc outputs
mpc listall | head
```

## Recommended baseline (stable + kid-safe)

- Keep **ALSA Master** at a fixed value (example):
  - `amixer set Master 40%`
- Use **MPD software volume** for music (`mpc volume 40`, bounded by `MAX_VOLUME` in `config.py`).
- Use **TTS_VOLUME/BEEP_VOLUME** for speech/beep (software scaling via `sox`, no Master changes).

## Ducking (music during voice input)

- `VOLUME_DUCK_LEVEL` is the MPD/ALSA **music volume target** during recording.
  - Default is **5** (quiet but not fully silent).
  - If you get feedback / false wake triggers: set to **0** (mute while listening).

```bash
# Temporary override (current shell)
export VOLUME_DUCK_LEVEL=0
./pi-sat.sh run
```

## Choosing the right output device

If `default` isn’t your USB speaker:

1. Find your card/device:
   - `aplay -l`
2. Try it:
   - `aplay -D plughw:3,0 -q resources/beep-short.wav`
3. Persist it (recommended: `.envrc.local`):
   ```bash
   export PIPER_OUTPUT_DEVICE='plughw:3,0'
   export OUTPUT_ALSA_DEVICE='plughw:3,0'
   ```
4. Ensure MPD uses the same device in `~/.mpd/mpd.conf`:
   ```conf
   audio_output {
       type "alsa"
       name "Pi-Sat Audio"
       device "plughw:3,0"
       mixer_type "software"
   }
   ```

## Common failure modes

- **TTS works, music is silent**
  - MPD output device mismatch (`~/.mpd/mpd.conf` points to a different ALSA device than `aplay`).
  - MPD output disabled: `mpc outputs` (must be enabled).
- **Beep missing, TTS works**
  - `OUTPUT_ALSA_DEVICE` points to a bad device; test with `aplay -D ... resources/beep-short.wav`.
- **Double wake triggers**
  - Increase `THRESHOLD` and/or `WAKE_WORD_COOLDOWN`; reduce `VOLUME_DUCK_LEVEL`; lower mic gain.

