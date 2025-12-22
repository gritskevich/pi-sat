# Pi‑Sat Installation (Raspberry Pi 5)

Goal: get **MPD + Piper + Hailo STT** working, then run `./pi-sat.sh run`.

## 0) Prereqs

- Raspberry Pi OS 64‑bit
- Hailo‑8L driver + SDK installed (Hailo commands work)
- USB mic + speaker

Quick Hailo check:
```bash
hailortcli fw-control identify
```

## 1) Clone + install repo dependencies

```bash
git clone https://github.com/gritskevich/pi-sat.git
cd pi-sat

./pi-sat.sh install
```

Notes:
- `./pi-sat.sh install` uses `sudo apt` and creates `./venv/`.
- It also downloads openWakeWord models and installs Hailo example deps.

## 2) Install Piper binary (once)

Pi‑Sat expects `PIPER_BINARY=/usr/local/bin/piper` (see `config.py`).

```bash
cd /tmp
wget https://github.com/rhasspy/piper/releases/download/v1.2.0/piper_arm64.tar.gz
tar xzf piper_arm64.tar.gz
cd piper
sudo cp piper /usr/local/bin/
sudo chmod +x /usr/local/bin/piper
sudo cp *.so* /usr/local/lib/ && sudo ldconfig
sudo cp -r espeak-ng-data /usr/local/share/
sudo ln -sf /usr/local/share/espeak-ng-data /usr/share/espeak-ng-data
piper --version
```

## 3) Download the default voice model

```bash
./pi-sat.sh download_voice
```

## 4) Configure MPD (required)

Pi‑Sat starts MPD automatically, but it assumes `~/.mpd/mpd.conf` exists.

```bash
mkdir -p ~/Music ~/.mpd/playlists

cat > ~/.mpd/mpd.conf <<'EOF'
music_directory     "~/Music"
playlist_directory  "~/.mpd/playlists"
db_file             "~/.mpd/database"
log_file            "~/.mpd/log"
pid_file            "~/.mpd/pid"
state_file          "~/.mpd/state"
sticker_file        "~/.mpd/sticker.sql"
bind_to_address     "localhost"
port                "6600"

audio_output {
    type        "alsa"
    name        "Pi-Sat Audio"
    device      "default"
    mixer_type  "software"
}
EOF

sed -i "s|~|$HOME|g" ~/.mpd/mpd.conf
mpd ~/.mpd/mpd.conf
mpc update
mpc status
```

If you’re not getting sound, pick the right ALSA device (see `docs/AUDIO.md`).

## 5) Run

```bash
./pi-sat.sh run
```

## 6) Local overrides (optional)

Create `.envrc.local` for machine‑specific overrides (loaded by `.envrc`):

```bash
# Language
export HAILO_STT_LANGUAGE='fr'   # or 'en'

# Output device (example)
export PIPER_OUTPUT_DEVICE='plughw:3,0'
export OUTPUT_ALSA_DEVICE='plughw:3,0'

# Ducking during listening
export VOLUME_DUCK_LEVEL=5
```

**Minimal .envrc.local:**
```bash
# Music library path (already created in Step 10)
export PISAT_MUSIC_DIR="$HOME/Music"

# MPD connection
export MPD_HOST="localhost"
export MPD_PORT="6600"

# Mic mute detection (for force listening mode)
export MIC_MUTE_ENABLED=true
export MIC_MUTE_THRESHOLD=0.01

# Debug mode (for development)
# export PISAT_DEBUG=true
```

### Step 12: Set Up direnv

```bash
# Add direnv hook to bash profile
echo 'eval "$(direnv hook bash)"' >> ~/.bashrc

# Reload bash configuration
source ~/.bashrc

# Allow direnv in pi-sat directory
cd ~/pi-sat
direnv allow

# Verify: You should see "direnv: loading" message
# and venv should be auto-activated.
# In bash, pi-sat.sh completion is also auto-enabled on repo entry.
```

### Step 13: Test Audio Devices

```bash
# Test microphone recording
arecord -D hw:2,0 -f S16_LE -r 48000 -c 1 -d 5 test.wav
aplay test.wav
rm test.wav

# List available audio devices
python -c "from modules.audio_devices import list_devices; list_devices()"

# Test wake sound
aplay resources/wakesound.wav
```

### Step 14: Run Tests

```bash
cd ~/pi-sat

# Run all tests to verify installation
./pi-sat.sh test

# Expected: All tests should pass (some may be skipped if Hailo not available)
```

### Step 15: Add Music to Library

```bash
# Copy MP3 files to music library
cp /path/to/your/music/*.mp3 ~/Music/

# Update MPD database
mpc update

# Verify music is loaded
mpc listall
```

### Step 16: Start Pi-Sat

```bash
cd ~/pi-sat

# Start the voice-controlled music player
./pi-sat.sh run

# You should see:
# - "Listening for wake word..."
# - "Wake word listener started"
```

### Step 17: Test Voice Commands

1. Say "**Alexa**" (wake word)
2. Wait for wake sound confirmation
3. Say "**Play [song name]**"
4. Music should start playing!

**Alternative**: Press the microphone mute button, then unmute to trigger force listening mode (bypasses wake word)

---

## Optional: Auto-Start on Boot

### Using systemd

```bash
# Create systemd service file
sudo nano /etc/systemd/system/pisat.service
```

**Contents:**
```ini
[Unit]
Description=Pi-Sat Voice-Controlled Music Player
After=network.target sound.target mpd.service

[Service]
Type=simple
User=dmitry
WorkingDirectory=/home/dmitry/pi-sat
Environment="PATH=/home/dmitry/pi-sat/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/dmitry/pi-sat/venv/bin/python -u /home/dmitry/pi-sat/modules/orchestrator.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start service:**
```bash
sudo systemctl enable pisat.service
sudo systemctl start pisat.service

# Check status
sudo systemctl status pisat.service

# View logs
sudo journalctl -u pisat.service -f
```

---

## Optional: Disable Auto-Suspend/Sleep

For 24/7 operation, disable all automatic suspend and screen blanking to ensure Pi-Sat stays active.

### Disable System Sleep/Suspend

```bash
# Method 1: Mask systemd sleep targets (prevents auto-suspend)
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target

# Method 2: Add explicit sleep configuration (recommended in addition to masking)
sudo mkdir -p /etc/systemd/sleep.conf.d
sudo tee /etc/systemd/sleep.conf.d/nosleep.conf > /dev/null << 'EOF'
[Sleep]
AllowSuspend=no
AllowHibernation=no
AllowHybridSleep=no
AllowSuspendThenHibernate=no
EOF

# Verify targets are masked
systemctl status sleep.target suspend.target | grep "Loaded"
```

**Expected output:** `Loaded: masked (Reason: Unit sleep.target is masked.)`

### Disable Screen Blanking (Desktop/GUI)

```bash
# Remove xscreensaver from autostart (if present)
sudo sed -i.bak '/^@xscreensaver/d' /etc/xdg/lxsession/LXDE-pi/autostart

# Add DPMS disable commands to autostart
sudo tee -a /etc/xdg/lxsession/LXDE-pi/autostart > /dev/null << 'EOF'
@xset -dpms
@xset s off
@xset s noblank
EOF

# Verify configuration
cat /etc/xdg/lxsession/LXDE-pi/autostart
```

### Disable Console Blanking (Terminal/Headless)

```bash
# Add consoleblank=0 to kernel boot parameters
sudo cp /boot/firmware/cmdline.txt /boot/firmware/cmdline.txt.backup
sudo sh -c 'printf "%s consoleblank=0\n" "$(cat /boot/firmware/cmdline.txt)" > /boot/firmware/cmdline.txt'

# Verify parameter added
cat /boot/firmware/cmdline.txt | grep consoleblank
```

**Expected output:** Should show `consoleblank=0` at the end of the line.

### Apply Changes

```bash
# Reboot to apply all changes
sudo reboot
```

### Verification After Reboot

```bash
# Check systemd sleep targets are masked
systemctl status sleep.target | grep "masked"

# Check sleep.conf.d configuration
cat /etc/systemd/sleep.conf.d/nosleep.conf

# Check cmdline.txt has consoleblank parameter
cat /boot/firmware/cmdline.txt | grep consoleblank
```

**References:**
- [Disable Sleep Mode on Raspberry Pi – RaspberryTips](https://raspberrytips.com/disable-sleep-mode-raspberry-pi/)
- [Disable Suspend/Hibernate – Ubuntu Handbook](https://ubuntuhandbook.org/index.php/2024/10/completely-disable-suspend-hibernate/)
- [Screen Blanking on RPi – FleetStack](https://fleetstack.io/blog/disable-screen-blanking-on-raspberry-pi)

---

## Optional: USB Auto-Import Setup

### Create USB Import Script

```bash
mkdir -p ~/pi-sat/scripts

cat > ~/pi-sat/scripts/usb_ingest.sh << 'EOF'
#!/bin/bash
# USB Auto-Import Script for Pi-Sat

# Configuration
MUSIC_DIR="$HOME/Music"
LOG_FILE="$HOME/pi-sat/logs/usb_import.log"

# Get USB mount point
USB_MOUNT=$(mount | grep "/media/" | head -n 1 | awk '{print $3}')

if [ -z "$USB_MOUNT" ]; then
    echo "No USB device found" >> "$LOG_FILE"
    exit 1
fi

# Count MP3 files
MP3_COUNT=$(find "$USB_MOUNT" -type f -iname "*.mp3" | wc -l)

if [ "$MP3_COUNT" -eq 0 ]; then
    echo "No MP3 files found on USB" >> "$LOG_FILE"
    exit 0
fi

# Copy files
echo "Importing $MP3_COUNT MP3 files from $USB_MOUNT" >> "$LOG_FILE"
rsync -av --include='*.mp3' --include='*.MP3' --exclude='*' "$USB_MOUNT/" "$MUSIC_DIR/"

# Normalize volume
ffmpeg-normalize "$MUSIC_DIR"/*.mp3 -o "$MUSIC_DIR/" -f

# Update MPD database
mpc update

# Announce via TTS (if Piper installed)
echo "I found $MP3_COUNT new songs" | \
    /usr/local/bin/piper --model ~/pi-sat/resources/voices/en_US-lessac-medium.onnx --output-raw | \
    aplay -D plughw:0,0 -r 22050 -f S16_LE -c 1

echo "Import completed: $MP3_COUNT files" >> "$LOG_FILE"
EOF

chmod +x ~/pi-sat/scripts/usb_ingest.sh
```

### Create udev Rule

```bash
sudo nano /etc/udev/rules.d/99-pisat-usb.rules
```

**Contents:**
```
ACTION=="add", SUBSYSTEMS=="usb", SUBSYSTEM=="block", RUN+="/home/dmitry/pi-sat/scripts/usb_ingest.sh"
```

**Reload udev rules:**
```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

---

## Troubleshooting

### Hailo Not Detected

```bash
# Check Hailo device
lspci | grep Hailo

# Check kernel module
lsmod | grep hailo

# Reinstall Hailo driver
cd ~/hailo-rpi5-driver
sudo ./uninstall.sh
sudo ./install.sh
sudo reboot
```

### MPD Not Starting

```bash
# Check MPD logs
tail -f ~/.mpd/log

# Restart MPD
mpd --kill
mpd ~/.mpd/mpd.conf

# Check MPD status
mpc status
```

### Microphone Not Working

```bash
# List audio input devices
arecord -l

# Test microphone (record 5 seconds)
arecord -D hw:2,0 -f S16_LE -r 48000 -c 1 -d 5 test.wav
aplay test.wav

# Adjust microphone in config.py
nano ~/pi-sat/config.py
# Set INPUT_DEVICE_NAME to your mic name
```

### Wake Word Not Detecting

```bash
# Test wake word detection with debug mode
cd ~/pi-sat
./pi-sat.sh run_debug

# Say "Alexa" and check console output
# Should show detection scores
```

### Python Dependencies Failed

```bash
# Reinstall with verbose output
pip install -r requirements.txt -v

# If specific package fails, install individually:
pip install python-mpd2
pip install thefuzz python-Levenshtein
```

---

## Post-Installation Checklist

- [ ] Hailo SDK installed and verified (`hailortcli fw-control identify`)
- [ ] Python virtual environment created with system site-packages
- [ ] All Python dependencies installed (`pip list`)
- [ ] Hailo Whisper models downloaded (`ls hailo_examples/speech_recognition/app/hefs/`)
- [ ] Piper TTS binary installed (`piper --version`)
- [ ] Piper voice model downloaded (`ls resources/voices/`)
- [ ] MPD configured and running (`mpc status`)
- [ ] Music library created (`ls ~/Music/`)
- [ ] direnv configured (`direnv allow`)
- [ ] Tests passing (`./pi-sat.sh test`)
- [ ] Audio devices working (mic + speaker test)
- [ ] Microphone mute button functional (if available)
- [ ] Wake word detection working
- [ ] Music playback working

---

## Next Steps

1. **Add More Music**: Copy MP3 files to `~/Music/` and run `mpc update`
2. **Test Voice Commands**: Try "Play [song]", "Pause", "Skip", "I love this"
3. **Configure Sleep Timer**: "Stop in 30 minutes"
4. **Build Favorites**: Say "I love this" while songs play
5. **Test Mic Mute Button**: Mute/unmute to trigger force listening mode
6. **Optional**: Set up auto-start on boot
7. **Optional**: Configure USB auto-import

---

## Support Resources

- **GitHub Issues**: https://github.com/gritskevich/pi-sat/issues
- **Hailo Documentation**: https://hailo.ai/developer-zone/
- **MPD Documentation**: https://www.musicpd.org/doc/
- **Piper TTS**: https://github.com/rhasspy/piper

---

## Installation Complete!

Pi-Sat is now ready to use. Say "Alexa" followed by your command to start controlling your music by voice!

Example commands:
- "Alexa, play Frozen"
- "Alexa, skip"
- "Alexa, I love this"
- "Alexa, stop in 30 minutes"

Enjoy your offline, voice-controlled music player!
