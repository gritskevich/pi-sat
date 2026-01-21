# Audio (SIMPLIFIED - Single Master Volume)

**Single source of truth** for audio routing + volume behavior.

## Philosophy (2025 Update)

Pi-Sat now uses a **SIMPLIFIED single master volume** approach:

- **ALSA PCM hardware**: Leave at current level (do NOT touch)
- **MPD software volume**: 100% (fixed at startup)
- **PulseAudio sink volume**: THE ONLY volume control (via `pactl`)

All audio (music, TTS, beep) uses the **same master volume**. No more complex layering or software volume scaling.

**IMPORTANT:** We do NOT set ALSA PCM to 100% as it would be too loud. Research shows: "Don't use amixer, it can confuse PipeWire session managers."

## Outputs (what uses what)

- **Music**: MPD → PulseAudio (`pulse`) @ 100% software volume
- **TTS**: Piper → `aplay -D default` → PulseAudio @ 100% volume
- **Wake beep**: `aplay -D default` → PulseAudio @ 100% volume

**Note (2026 update)**: Piper outputs raw PCM. When PipeWire is used directly (`pw-play`),
raw mode is required. If TTS is silent, verify `pw-play --raw` is used in the TTS path.

**Key**: MPD uses `pulse`, TTS/beep use `default` (ALSA → PulseAudio routing).

## Best Practice: Raspberry Pi 5 + PipeWire

Raspberry Pi OS Bookworm uses **PipeWire with pipewire-pulse** by default.

### Setup Checklist

✅ **Remove ALSA overrides** (avoid conflicts):
- `/etc/asound.conf` should not exist
- `~/.asoundrc` should not exist (or should not override `default`)

✅ **Set MPD to PulseAudio** in `~/.mpd/mpd.conf`:
```conf
audio_output {
    type "pulse"
    name "Pi-Sat Pulse"
    mixer_type "software"
}
```

✅ **Set Pi-Sat outputs** in `config.py`:
```python
PIPER_OUTPUT_DEVICE = 'default'  # ALSA default → PulseAudio
OUTPUT_ALSA_DEVICE = 'default'
```

✅ **Optional: Enable PipeWire noise suppression (KISS)**:
```bash
scripts/enable_noise_suppression.sh
export INPUT_DEVICE_NAME=PiSat-NS
```

✅ **Restart MPD**:
```bash
pkill mpd
mpd ~/.mpd/mpd.conf
```

## Volume Control: SIMPLIFIED

### Single Master Volume Architecture

```
┌─────────────────────────────────────────┐
│ ALSA PCM Hardware (USB speaker)         │
│ Leave at current level (do NOT touch)   │  ← NOT controlled
│                                         │
│   ↓ current level (e.g., 20-30%)        │
│                                         │
│ PulseAudio/PipeWire Sink                │
│ pactl set-sink-volume @DEFAULT_SINK@ X% │  ← THE ONLY CONTROL
│                                         │
│   ↓ X% volume (applies to ALL)          │
│                                         │
├─────────────┬──────────────┬────────────┤
│  MPD        │  TTS (Piper) │  Beep      │
│  @100%      │  @100%       │  @100%     │
└─────────────┴──────────────┴────────────┘
```

### Volume Commands

**Get current master volume:**
```bash
pactl get-sink-volume @DEFAULT_SINK@
```

**Set master volume:**
```bash
pactl set-sink-volume @DEFAULT_SINK@ 20%
```

**Verify MPD software volume is at 100%:**
```bash
mpc status  # Should show "volume:100%"
```

**Check ALSA PCM level (read-only, do NOT change):**
```bash
amixer -c 3 sget PCM  # Just for info, don't change it
```

### Troubleshooting Volume Issues

**All audio is quiet:**
1. Check PulseAudio sink volume: `pactl get-sink-volume @DEFAULT_SINK@` (should be 20-50%)
2. Check MPD software volume: `mpc status` (should be 100%)
3. Check ALSA PCM: `amixer -c 3 sget PCM` (should be 20-30%, do NOT change)

**Quick recovery (reset to known state):**
```bash
# Set MPD software volume to 100%
mpc volume 100

# Set PulseAudio sink to comfortable level (THE ONLY volume control)
pactl set-sink-volume @DEFAULT_SINK@ 20%

# DO NOT touch ALSA PCM (amixer confuses PipeWire session managers)
```

**Music volume changes unexpectedly:**
- PipeWire may store per-stream volume. Disable stream-restore module:
```bash
pactl unload-module module-stream-restore
```

## Config Reference

### STT Input Notes (2026 Update)

- Hailo Whisper uses the `whisper-base` model.
- Input is locked to the dedicated USB Microphone (Generalplus).
- Keep mic gain around 80-90%; compare near vs far without noise suppression.
- PipeWire noise suppression is experimental and can break wake word detection.

### Volume Settings (config.py)

```python
# Single master volume for ALL audio (music, TTS, beep)
MASTER_VOLUME = 15  # Default startup volume (0-100)
VOLUME_STEP = 5     # Volume up/down increment
MAX_VOLUME = 50     # Kid-safety volume limit (0-100)
```

### Audio Device Settings (config.py)

```python
# Input (Microphone)
INPUT_DEVICE_NAME = 'USB Microphone'  # Generalplus dedicated mic (better quality)
                                      # Set to None to use system default

# Output (Speaker)
OUTPUT_ALSA_DEVICE = 'default'   # Beep output (ALSA default → PulseAudio → Jieli speaker)
PIPER_OUTPUT_DEVICE = 'default'  # TTS output (ALSA default → PulseAudio → Jieli speaker)
```

**Note:** The Jieli USB Composite Device has both a speaker AND a built-in microphone.
We use the separate Generalplus USB Microphone for better audio quality.

### Adaptive Silence (End‑of‑Speech)

If recordings frequently hit max time, enable adaptive silence.
It tracks ambient RMS and treats low‑energy frames as silence when VAD misfires.

```bash
export ADAPTIVE_SILENCE_ENABLED=true
export ADAPTIVE_SILENCE_RATIO=1.4
export ADAPTIVE_AMBIENT_ALPHA=0.2
export ADAPTIVE_MIN_SILENCE_RMS=300
```

Calibration:
```bash
python scripts/calibrate_silence.py --seconds 3
```

Startup calibration (default on):
```bash
export STARTUP_CALIBRATION_ENABLED=true
export STARTUP_CALIBRATION_SECONDS=2
```

## Quick Checks

```bash
# 1) Is PulseAudio/PipeWire running?
pactl info

# 2) List audio sinks (speakers)
pactl list short sinks

# 3) List audio sources (microphones)
pactl list short sources
arecord -l

# 4) Is the USB speaker visible?
aplay -l

# 5) Can PulseAudio play audio?
aplay -D default -q resources/beep-short.wav

# 6) Test microphone recording
arecord -d 2 -f cd -t wav /tmp/test.wav && aplay /tmp/test.wav

# 7) Is MPD alive and playing?
mpc status
mpc outputs
mpc listall | head
```

### Set Correct Microphone

If using Generalplus USB Microphone instead of Jieli built-in mic:

```bash
# Set as default (temporary)
pactl set-default-source alsa_input.usb-MUSIC-BOOST_USB_Microphone_MB-306-00.mono-fallback

# Or configure in config.py
INPUT_DEVICE_NAME = 'USB Microphone'
```

## Choosing the right output device

If you're not using PulseAudio/PipeWire (unusual), you can point directly to ALSA:

1. Find your card/device:
   - `aplay -l`
2. Try it:
   - `aplay -D plughw:3,0 -q resources/beep-short.wav`
3. Persist it (`.envrc.local`):
   ```bash
   export PIPER_OUTPUT_DEVICE='plughw:3,0'
   export OUTPUT_ALSA_DEVICE='plughw:3,0'
   ```
4. Update `~/.mpd/mpd.conf`:
   ```conf
   audio_output {
       type "alsa"
       name "Pi-Sat Audio"
       device "plughw:3,0"
       mixer_type "software"
   }
   ```

## Common Failure Modes

- **TTS works, music is silent**
  - MPD output device mismatch in `~/.mpd/mpd.conf`
  - MPD output disabled: `mpc outputs` (must be enabled)
  - MPD software volume not at 100%: `mpc volume 100`

- **Beep missing, TTS works**
  - `OUTPUT_ALSA_DEVICE` points to wrong device
  - Test: `aplay -D pulse -q resources/beep-short.wav`

- **Double wake triggers**
  - Increase `WAKE_WORD_THRESHOLD` and/or `WAKE_WORD_COOLDOWN` in `config.py`
  - Music is now paused during voice input (eliminates feedback)
  - Reduce mic gain

- **Everything is quiet despite high volume settings**
  - Check all volume layers (see troubleshooting above)
  - Ensure PulseAudio sink is not muted: `pactl set-sink-mute @DEFAULT_SINK@ 0`
  - Ensure USB speaker is the default sink: `pactl set-default-sink alsa_output.usb-...`

## Advanced: PipeWire Configuration

To persist default sink across reboots:

`~/.config/pipewire/pipewire-pulse.conf.d/50-pisat.conf`:
```ini
pulse.properties = {
  pulse.default.sink = "alsa_output.usb-Jieli_Technology_USB_Composite_Device_..."
}
```

Restart services:
```bash
systemctl --user restart pipewire pipewire-pulse wireplumber
```

## Tools Reference

### Recommended for Raspberry Pi 5 (2025)

- **pactl**: PulseAudio command-line control (works with PipeWire via pipewire-pulse)
- **wpctl**: Native PipeWire control (alternative to pactl)
- **pavucontrol**: GUI volume control (works with PipeWire)

### NOT Recommended

- **amixer**: Can confuse PipeWire session managers. Only use for setting PCM hardware to 100%.

## Summary: What Changed from Old Approach

**Old (complex, multi-layer):**
- MPD software volume: variable (controlled by VolumeManager)
- TTS software volume: variable (sox scaling)
- Beep software volume: variable (sox scaling)
- ALSA PCM: variable or fixed via amixer
- Result: Multiple volume layers multiplying together = confusion

**New (simple, single-layer):**
- ALSA PCM hardware: **Leave at current level (do NOT touch)**
- MPD software volume: **100% (fixed at startup)**
- TTS software volume: **100% (no sox scaling)**
- Beep software volume: **100% (no sox scaling)**
- PulseAudio sink: **THE ONLY CONTROL** (via pactl)
- Result: One master volume controls everything = clarity

**Why we don't touch ALSA PCM:**
- Setting PCM to 100% makes volume too loud even at PulseAudio 20%
- Research shows: "Don't use amixer, it can confuse PipeWire session managers"
- Best practice: Let PipeWire manage hardware, only control via pactl
