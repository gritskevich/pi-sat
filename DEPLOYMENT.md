# Pi-Sat Deployment Checklist

**Battle-tested, production-ready deployment guide**

---

## Pre-Deployment Checklist

### System Prerequisites

- [ ] Raspberry Pi 5 with Hailo-8L AI Kit
- [ ] Raspberry Pi OS 64-bit (Bookworm) installed
- [ ] USB microphone connected
- [ ] Audio output (speaker/headphones) connected
- [ ] Internet connection (for initial setup)

### System-Wide Dependencies

- [ ] Hailo SDK installed: `hailortcli fw-control identify`
- [ ] Piper TTS installed: `piper --version` shows 1.2.0
- [ ] MPD installed: `mpd --version`
- [ ] direnv installed (optional): `direnv --version`

---

## Installation Steps

### 1. Clone and Install

```bash
git clone https://github.com/gritskevich/pi-sat.git
cd pi-sat
./pi-sat.sh install
```

**Verify:**
- [ ] Virtual environment created: `ls venv/bin/python`
- [ ] System packages installed: `dpkg -l | grep -E "portaudio|alsa|ffmpeg"`
- [ ] Python packages installed: `venv/bin/pip list | grep -E "openwakeword|thefuzz|python-mpd2"`
- [ ] Hailo SDK accessible: `venv/bin/python -c "import hailo_platform; print('OK')"`

### 2. Download Models

```bash
# TTS voice model (~60MB)
./pi-sat.sh download_voice

# Verify Hailo models were downloaded by install script
ls hailo_examples/speech_recognition/app/hefs/h8l/base/*.hef | wc -l
# Should show: 2
```

**Verify:**
- [ ] TTS voice model downloaded: `ls resources/voices/*.onnx`
- [ ] Hailo encoder model exists: `ls hailo_examples/speech_recognition/app/hefs/h8l/base/*encoder*.hef`
- [ ] Hailo decoder model exists: `ls hailo_examples/speech_recognition/app/hefs/h8l/base/*decoder*.hef`
- [ ] Decoder assets exist: `ls hailo_examples/speech_recognition/app/decoder_assets/base/decoder_tokenization/*.npy`

### 3. Configure MPD

```bash
# MPD should already be configured (see INSTALL.md)
mpc status
mpc update
```

**Verify:**
- [ ] MPD config exists: `cat ~/.mpd/mpd.conf`
- [ ] MPD running: `pgrep mpd`
- [ ] MPD responding: `mpc status` (no errors)
- [ ] Music directory exists: `ls ~/Music/`

### 4. Add Music

```bash
# Copy MP3 files to music library
cp /path/to/music/*.mp3 ~/Music/
mpc update
mpc listall | head -10
```

**Verify:**
- [ ] Music files present: `ls ~/Music/*.mp3 | wc -l` shows > 0
- [ ] MPD database updated: `mpc stats` shows tracks > 0

---

## Functional Testing

### Test 1: Component Verification

```bash
# Hailo hardware
hailortcli fw-control identify
# Expected: Board Name: Hailo-8, Device Architecture: HAILO8L

# Piper TTS
echo "Test" | piper --model resources/voices/fr_FR-siwis-medium.onnx --output-raw | aplay -r 22050 -f S16_LE -c 1
# Expected: Hear "Test" spoken in French

# MPD playback
mpc add /
mpc play
mpc stop
# Expected: Music starts and stops without errors

# Wake sound
aplay resources/wakesound.wav
# Expected: Hear beep sound
```

**Results:**
- [ ] Hailo hardware detected
- [ ] TTS speaks French
- [ ] MPD plays music
- [ ] Wake sound plays

### Test 2: Microphone Input

```bash
# Record 5 seconds of audio
arecord -D hw:2,0 -f S16_LE -r 48000 -c 1 -d 5 test.wav
aplay test.wav
rm test.wav
```

**Results:**
- [ ] Microphone records audio
- [ ] Playback is clear (no distortion)
- [ ] Audio levels are adequate (speak normally)

### Test 3: Hailo STT Quick Test

```bash
./pi-sat.sh hailo_check
```

**Expected output:**
```
hailo_platform: 4.20.0
Imports: OK
arch=hailo8l exists=True
Pipeline init: OK
```

**Results:**
- [ ] hailo_platform imports successfully
- [ ] Hailo8L models found
- [ ] Pipeline initializes without errors

### Test 4: Wake Word Detection

```bash
# Run in debug mode
./pi-sat.sh run_debug
# Say "Alexa" multiple times
# Press Ctrl+C to exit
```

**Expected behavior:**
- Shows RMS levels updating
- When you say "Alexa", confidence score increases
- Wake word triggers command recording

**Results:**
- [ ] RMS levels show when speaking
- [ ] "Alexa" detection works (confidence > 0.5)
- [ ] False positives are rare (< 1 per minute of silence)

### Test 5: End-to-End Voice Command

```bash
./pi-sat.sh run
# Wait for "Listening for wake word..."
# Say: "Alexa"
# Wait for beep
# Say: "Joue [song name]"
```

**Expected behavior:**
1. Wake word detected (beep plays)
2. Recording starts
3. STT transcribes command
4. Intent recognized: "play_music"
5. Music starts playing

**Results:**
- [ ] Wake word triggers reliably
- [ ] Command transcription is accurate
- [ ] Music playback starts
- [ ] Volume commands work ("plus fort", "moins fort")
- [ ] Stop command works ("arrête")

---

## Production Deployment

### Enable Auto-Start (systemd)

**Recommended (user service, keeps audio working):**

```bash
./install-daemon.sh install --user
systemctl --user status pi-sat
sudo loginctl enable-linger $USER
```

**Optional (system service, no user audio by default):**

```bash
sudo ./install-daemon.sh install --system
sudo systemctl status pi-sat
```

**Verify:**
- [ ] Service running: `systemctl --user is-active pi-sat` shows "active"
- [ ] No errors in logs: `journalctl --user -u pi-sat -n 50 --no-pager`
- [ ] Boot start enabled: `loginctl show-user $USER -p Linger` shows "Linger=yes"

### Disable Auto-Suspend (24/7 Operation)

```bash
# Mask sleep targets
sudo systemctl mask sleep.target suspend.target hibernate.target

# Disable console blanking
sudo sh -c 'echo "consoleblank=0" >> /boot/firmware/cmdline.txt'

# Reboot
sudo reboot
```

**Verify after reboot:**
- [ ] Sleep targets masked: `systemctl status sleep.target | grep masked`
- [ ] Console blanking disabled: `cat /boot/firmware/cmdline.txt | grep consoleblank=0`
- [ ] Pi-Sat auto-started: `systemctl --user is-active pi-sat` shows "active"

---

## Monitoring and Maintenance

### Daily Checks

```bash
# Check service status
sudo systemctl status pisat.service

# View recent logs
sudo journalctl -u pisat.service -n 100 --no-pager

# Check MPD status
mpc status

# Check disk space (models are ~800MB)
df -h | grep root
```

### Performance Baselines

| Metric | Expected Value |
|--------|----------------|
| Wake word latency | < 500ms |
| STT processing | 1-2 seconds |
| Intent classification | < 100ms |
| Music start latency | < 1 second |
| Total wake-to-play | 2-4 seconds |
| Memory usage (idle) | ~500MB |
| Memory usage (active) | ~1.5GB |

### Troubleshooting Commands

```bash
# Restart pi-sat service
sudo systemctl restart pisat.service

# Restart MPD
mpd --kill && mpd ~/.mpd/mpd.conf

# Clear logs
./pi-sat.sh logs_clear

# Reinstall (preserve config)
cd ~/pi-sat
git pull
./pi-sat.sh install

# Full reinstall (nuclear option)
cd ~
rm -rf pi-sat
git clone https://github.com/gritskevich/pi-sat.git
cd pi-sat
./pi-sat.sh install
./pi-sat.sh download_voice
```

---

## Security Considerations

### Network Isolation (Optional)

Pi-Sat is designed to run 100% offline:

```bash
# After initial setup, you can disable network
sudo nmcli networking off

# Or whitelist only local network
sudo ufw enable
sudo ufw allow from 192.168.1.0/24
sudo ufw deny out from any to any
```

**Verify offline capability:**
- [ ] Disconnect ethernet/WiFi
- [ ] Pi-Sat still detects wake word
- [ ] STT still transcribes (Hailo local)
- [ ] TTS still speaks (Piper local)
- [ ] Music still plays (MPD local)

### File Permissions

```bash
# Ensure config files are user-readable only
chmod 600 ~/.mpd/mpd.conf
chmod 600 .envrc.local

# Ensure scripts are not world-writable
find ~/pi-sat -type f -name "*.sh" -exec chmod 755 {} \;
```

---

## Backup and Recovery

### Backup Configuration

```bash
# Backup user config
tar czf ~/pisat-backup-$(date +%Y%m%d).tar.gz \
    ~/pi-sat/.envrc.local \
    ~/pi-sat/config.py \
    ~/.mpd/mpd.conf \
    ~/Music/

# Restore (on new system)
tar xzf ~/pisat-backup-*.tar.gz -C ~/
```

### Model Files (Do Not Backup)

Models are large and should be re-downloaded:
- Hailo models: Run `./pi-sat.sh install`
- TTS voices: Run `./pi-sat.sh download_voice`
- Wake word models: Auto-downloaded on first run

---

## Deployment Complete

Pi-Sat is now ready for production use!

**Quick health check:**
```bash
sudo systemctl status pisat.service
mpc status
df -h
```

**Live testing:**
1. Say "Alexa"
2. Say "Joue [song name]"
3. Music should play

**Support:**
- GitHub Issues: https://github.com/gritskevich/pi-sat/issues
- Documentation: See `docs/` directory
