# Troubleshooting Guide

Common issues and solutions for Pi-Sat voice assistant.

**Quick Navigation:**
- [Hailo Device Issues](#hailo-device-issues)
- [MPD Issues](#mpd-issues)
- [Wake Word Detection](#wake-word-detection)
- [Audio Device Issues](#audio-device-issues)
- [STT / Transcription Issues](#stt--transcription-issues)
- [TTS / Voice Output Issues](#tts--voice-output-issues)
- [Volume Control Issues](#volume-control-issues)
- [Network / Connectivity](#network--connectivity)

---

## Hailo Device Issues

### Hailo Not Detected
**Symptoms:** Error "HAILO_OUT_OF_PHYSICAL_DEVICES" or Hailo commands fail

**Diagnosis:**
```bash
# Check if Hailo device is detected
hailortcli fw-control identify

# Check if driver is loaded
lsmod | grep hailo

# Check for zombie processes holding the device
ps aux | grep python
```

**Solutions:**
1. **Kill zombie processes:**
   ```bash
   # Find Python processes using Hailo
   ps aux | grep python

   # Kill specific process
   kill <PID>

   # Or kill all Python processes (careful!)
   killall python3
   ```

2. **Reload Hailo driver:**
   ```bash
   sudo modprobe -r hailo_pci
   sudo modprobe hailo_pci
   ```

3. **Reboot:** If above doesn't work, reboot the Pi:
   ```bash
   sudo reboot
   ```

### Hailo Performance Issues
**Symptoms:** STT takes >5 seconds, high CPU usage

**Solutions:**
- Check no other processes using Hailo
- Verify using correct model variant (base vs tiny)
- Check system resources: `htop`

---

## MPD Issues

### MPD Not Starting
**Symptoms:** "Connection refused" errors, MPD commands fail

**Diagnosis:**
```bash
# Check MPD status
systemctl --user status mpd

# Check MPD logs
tail -f ~/.mpd/log

# Test MPD manually
mpc status
```

**Solutions:**
1. **Restart MPD:**
   ```bash
   mpd --kill && mpd ~/.mpd/mpd.conf
   ```

2. **Check configuration:**
   ```bash
   cat ~/.mpd/mpd.conf
   # Verify music_directory, db_file, log_file paths exist
   ```

3. **Update database:**
   ```bash
   mpc update
   mpc stats
   ```

### MPD Connection Drops
**Symptoms:** Intermittent "Connection lost" errors

**Solutions:**
- Check MPD logs for errors
- Verify network stability (if using network MPD)
- Increase MPD connection timeout in config
- Check system resources (low memory can cause MPD crashes)

---

## Wake Word Detection

### Wake Word Not Detecting
**Symptoms:** Saying "Alexa" doesn't trigger response

**Diagnosis:**
```bash
# Run in debug mode to see detection scores
./pi-sat.sh run_debug

# Say "Alexa" and observe console output
# Look for confidence scores near threshold (0.5)
```

**Solutions:**
1. **Adjust threshold:**
   - Edit `config.py`: `WAKE_WORD_THRESHOLD = 0.4` (lower = more sensitive)
   - Test different values: 0.3-0.6

2. **Check microphone:**
   ```bash
   # Test microphone recording
   arecord -d 3 -f cd test.wav && aplay test.wav
   ```

3. **Check audio device:**
   ```bash
   python -c "from modules.audio_devices import list_devices; list_devices()"
   ```

### False Positives
**Symptoms:** Wake word triggers on background noise or similar words

**Solutions:**
- Increase threshold: `WAKE_WORD_THRESHOLD = 0.6`
- Increase cooldown: `WAKE_WORD_COOLDOWN = 3.0`
- Use higher VAD level: `VAD_LEVEL = 3`

### Long Delay Between Wake Word and Recording
**Symptoms:**
- Several seconds pass between saying "Alexa" and hearing the "ding"
- Recording captures silence or garbage instead of actual command
- Transcriptions show random characters: "[ [ [ [", "(Morning).", etc.

**Diagnosis:**
```bash
# Test wake word → recording timing
./pi-sat.sh test_wake_stt

# Check debug audio files
ls -lh /tmp/pisat_debug_*.wav
aplay /tmp/pisat_debug_001.wav  # Listen to what was actually recorded
```

**Root Causes (Fixed in 2025-12-19):**
1. Wake sound was blocking (subprocess.run instead of Popen)
2. 2-second sleep after wake word detection
3. New audio stream creation causes buffer gap

**Solutions:**
- **Already fixed** in modules/audio_player.py and wake_word_listener.py
- Test script (test_wake_stt.py) now has zero-gap recording
- Production code still has small gap (requires architecture refactor)

**Debug saved audio:**
```bash
# Test script automatically saves recordings to /tmp/pisat_debug_NNN.wav
# Listen to verify what's being captured:
aplay /tmp/pisat_debug_001.wav

# Check if recording is silence (should be ~0 bytes if no audio):
ls -lh /tmp/pisat_debug_*.wav
```

---

## Audio Device Issues

### Microphone Not Found
**Symptoms:** "No microphone detected" errors

**Diagnosis:**
```bash
# List all audio input devices
arecord -l

# Check device in Python
python -c "from modules.audio_devices import list_devices; list_devices()"
```

**Solutions:**
1. **Set specific device:** Edit `config.py`:
   ```python
   INPUT_DEVICE_NAME = "USB Microphone"  # Match exact name from arecord -l
   ```

2. **Check USB connection:**
   - Unplug and replug USB microphone
   - Try different USB port
   - Check `dmesg | grep usb` for errors

### Speaker / TTS Not Playing
**Symptoms:** TTS generates audio but no sound output

**Diagnosis:**
```bash
# List playback devices
aplay -l

# Test speaker directly
aplay /home/dmitry/pi-sat/resources/wakesound.wav
```

**Solutions:**
1. **Set correct ALSA device:** Edit `config.py`:
   ```python
   OUTPUT_ALSA_DEVICE = "plughw:0,0"  # Adjust based on aplay -l
   PIPER_OUTPUT_DEVICE = "default"
   ```

2. **Check volume:**
   ```bash
   amixer get Master
   amixer set Master 80%
   ```

---

## STT / Transcription Issues

### Empty Transcriptions
**Symptoms:** STT returns empty string frequently

**Diagnosis:**
- Check debug logs for STT errors
- Verify audio is being recorded (check file size)
- Test with known good audio file

**Solutions:**
1. **Check language configuration:**
   ```python
   # In config.py
   HAILO_STT_LANGUAGE = "fr"  # Match your speech language
   ```

2. **Increase recording duration:**
   ```python
   MAX_RECORDING_TIME = 15.0  # Increase from 10s
   ```

3. **Adjust VAD sensitivity:**
   ```python
   VAD_LEVEL = 1  # Less aggressive (allows more speech through)
   SILENCE_THRESHOLD = 1.5  # Longer silence before cutoff
   ```

### Wrong Language Transcription
**Symptoms:** French speech transcribed as English (or vice versa)

**Solutions:**
1. **Set correct language:**
   ```bash
   export HAILO_STT_LANGUAGE='fr'  # or 'en'
   ```

2. **Test language detection:**
   ```bash
   pytest tests/test_language_detection.py -v -s
   ```

---

## TTS / Voice Output Issues

### Voice Model Not Found
**Symptoms:** "FileNotFoundError: Voice model not found"

**Solutions:**
1. **Check model path:** Edit `.envrc`:
   ```bash
   export PIPER_MODEL="$HOME/pi-sat/resources/voices/fr_FR-siwis-medium.onnx"
   ```

2. **Download missing model:**
   ```bash
   ./pi-sat.sh download_voice
   ```

### TTS Too Quiet / Too Loud
**Solutions:**
```python
# In config.py
TTS_VOLUME = 90  # Increase (0-100)
```

---

## Volume Control Issues

### Volume Commands Not Working
**Symptoms:** "Volume up" / "Volume down" commands have no effect

**Diagnosis:**
```bash
# Test volume control utilities
python scripts/test_volume.py
```

**Solutions:**
1. **Enable MPD software volume:** Edit `~/.mpd/mpd.conf`:
   ```
   mixer_type "software"
   ```

2. **Use ALSA fallback:** Volume Manager automatically falls back to ALSA
   ```bash
   amixer set Master 50%
   ```

### Volume Ducking Not Working
**Symptoms:** Music doesn't lower during voice input

**Solutions:**
- Check VolumeManager is initialized in orchestrator
- Verify `VOLUME_DUCK_LEVEL` in config.py
- Check logs for volume errors

---

## Network / Connectivity

### WiFi Drops
**Symptoms:** Intermittent disconnections affecting MPD/updates

**Solutions:**
```bash
# Monitor WiFi connection
./pi-sat/scripts/monitor_connections.sh

# Check WiFi power management
iwconfig wlan0 | grep "Power Management"

# Disable WiFi power saving
sudo iw dev wlan0 set power_save off
```

---

## General Debugging

### Enable Verbose Logging
```bash
export PISAT_DEBUG=true
export PISAT_VERBOSE=true
./pi-sat.sh run
```

### Check System Resources
```bash
# CPU, memory, processes
htop

# Disk space
df -h

# USB devices
lsusb

# System logs
journalctl -xe
```

### Clean Start
```bash
# Kill all Pi-Sat processes
killall python3

# Clear logs
./pi-sat.sh logs_clear

# Restart with debug
./pi-sat.sh run_debug
```

---

**See also:**
- [IMPLEMENTATION_PATTERNS.md](./IMPLEMENTATION_PATTERNS.md) - Understanding component behavior
- [TESTING.md](./TESTING.md) - Running diagnostics tests
- [RESEARCH.md](./RESEARCH.md) - Design decisions and trade-offs
