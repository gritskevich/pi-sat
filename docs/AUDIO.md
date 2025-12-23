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
- **TTS**: Piper → `aplay -D pulse` (or `pw-play`) @ 100% volume
- **Wake beep**: `aplay -D pulse` @ 100% volume

**Key**: `config.py` defaults `PIPER_OUTPUT_DEVICE` and `OUTPUT_ALSA_DEVICE` to `pulse`.

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

✅ **Set Pi-Sat outputs to pulse** in `config.py`:
```python
PIPER_OUTPUT_DEVICE = 'pulse'
OUTPUT_ALSA_DEVICE = 'pulse'
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

## Ducking (music during voice input)

- `VOLUME_DUCK_LEVEL` in `config.py` sets the master volume during recording
  - Default: **5%** (quiet but not silent)
  - If you get feedback/false wake triggers: set to **0%** (mute)

```bash
# Temporary override
export VOLUME_DUCK_LEVEL=0
./pi-sat.sh run
```

## Config Reference

### Volume Settings (config.py)

```python
# Single master volume for ALL audio (music, TTS, beep)
MASTER_VOLUME = 20  # Default startup volume (0-100)
VOLUME_STEP = 10    # Volume up/down increment
VOLUME_DUCK_LEVEL = 5  # Volume during voice recording (0-100)
MAX_VOLUME = 50     # Kid-safety volume limit (0-100)
```

### Audio Device Settings (config.py)

```python
OUTPUT_ALSA_DEVICE = 'pulse'  # Beep output
PIPER_OUTPUT_DEVICE = 'pulse'  # TTS output
```

## Quick Checks

```bash
# 1) Is PulseAudio/PipeWire running?
pactl info

# 2) List audio sinks
pactl list short sinks

# 3) Is the USB speaker visible?
aplay -l

# 4) Can PulseAudio play audio?
aplay -D pulse -q resources/beep-short.wav

# 5) Is MPD alive and playing?
mpc status
mpc outputs
mpc listall | head
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
  - Increase `THRESHOLD` and/or `WAKE_WORD_COOLDOWN` in `config.py`
  - Lower `VOLUME_DUCK_LEVEL` (reduce music feedback into mic)
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
