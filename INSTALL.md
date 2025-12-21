# Pi-Sat Installation Guide

Complete step-by-step installation guide for Pi-Sat voice-controlled music player on Raspberry Pi 5 with Hailo-8L.

---

## Prerequisites

### Hardware Requirements

✅ **Required:**
- Raspberry Pi 5 (4GB or 8GB RAM recommended)
- Hailo-8L AI Accelerator HAT
- USB Microphone with hardware mute button (or Raspberry Pi camera with mic)
- Speaker (3.5mm jack or USB)
- MicroSD Card (32GB+ recommended, Class 10 or better)
- Official Raspberry Pi 5 Power Supply (27W USB-C)

⭐ **Optional but Recommended:**
- Enclosure/Case

### Software Requirements

- Raspberry Pi OS (64-bit, Bullseye or newer)
- Python 3.9+
- Hailo SDK (comes with Hailo-8L driver installation)

---

## Installation Steps

### Step 1: System Update

```bash
sudo apt-get update
sudo apt-get upgrade -y
sudo reboot
```

### Step 2: Install Hailo SDK

Follow Hailo's official installation guide for Raspberry Pi 5:

```bash
# Download Hailo driver package
wget https://hailo.ai/downloads/hailo-rpi5-driver.tar.gz

# Extract and install
tar xzf hailo-rpi5-driver.tar.gz
cd hailo-rpi5-driver
sudo ./install.sh

# Verify installation
hailortcli fw-control identify
```

**Expected output:** Should show Hailo-8L device information.

### Step 3: Install System Dependencies

```bash
# Update package lists first
sudo apt-get update

# Install all required packages in one command (tested and verified)
sudo apt-get install -y \
    mpd \
    mpc \
    portaudio19-dev \
    libasound2-dev \
    alsa-utils \
    ffmpeg \
    sox \
    libsox-fmt-all \
    libsndfile1 \
    python3-pip \
    python3-dev \
    python3-venv \
    direnv \
    git

# Verify installation
which mpd && which mpc && which ffmpeg && which direnv && echo "✓ All packages installed"
```

**Note:** We're not installing `ffmpeg-normalize` via apt as it's not in the default repos. We'll install it via pip if needed.

### Step 4: Download and Install Piper TTS

```bash
# Download Piper binary for ARM64
cd /tmp
wget https://github.com/rhasspy/piper/releases/download/v1.2.0/piper_arm64.tar.gz

# Extract
tar xzf piper_arm64.tar.gz
cd piper

# Install binary
sudo cp piper /usr/local/bin/
sudo chmod +x /usr/local/bin/piper

# Install shared libraries
sudo cp *.so* /usr/local/lib/
sudo ldconfig

# Install espeak-ng data
sudo cp -r espeak-ng-data /usr/local/share/

# Create symlink for espeak-ng data (Piper looks in /usr/share by default)
sudo ln -sf /usr/local/share/espeak-ng-data /usr/share/espeak-ng-data

# Verify installation
piper --version
```

**Expected output:** `1.2.0`

**Test Piper:**
```bash
echo "Hello from Piper" | piper \
    --model ~/pi-sat/resources/voices/en_US-lessac-medium.onnx \
    --output-raw > /tmp/test.raw

# Check output was generated
ls -lh /tmp/test.raw
```

**Expected:** Should generate ~60-100KB raw audio file.

### Step 5: Clone Pi-Sat Repository

```bash
cd ~
git clone https://github.com/gritskevich/pi-sat.git
cd pi-sat
```

### Step 6: Set Up Python Virtual Environment

```bash
# Create virtual environment with access to system site-packages
# (needed for Hailo SDK Python bindings)
python3 -m venv --system-site-packages venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel
```

### Step 7: Install Python Dependencies

```bash
# Install all Python packages from requirements.txt
pip install -r requirements.txt

# This will install:
# - Audio processing (pyaudio, soundfile, librosa)
# - Wake word detection (openwakeword)
# - STT (transformers, torch)
# - MPD client (python-mpd2)
# - Fuzzy matching (thefuzz, python-Levenshtein)
# - Testing (pytest)
```

**Note:** Installation may take 15-30 minutes depending on your internet speed.

### Step 8: Download Hailo Whisper Models

```bash
# Run the Hailo setup script
cd hailo_examples/speech_recognition
./download_resources.sh

# This downloads:
# - Whisper encoder/decoder HEF files for hailo8l
# - Pre-trained model weights
```

### Step 9: Download Piper Voice Model

```bash
cd ~/pi-sat

# Create voices directory
mkdir -p resources/voices

# Download Piper voice model (en_US-lessac-medium)
wget -O resources/voices/en_US-lessac-medium.onnx \
    https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx

# Download model config
wget -O resources/voices/en_US-lessac-medium.onnx.json \
    https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
```

### Step 10: Configure MPD

```bash
# Create MPD directories
mkdir -p ~/Music/pisat
mkdir -p ~/.mpd/playlists

# Copy MPD configuration template
cat > ~/.mpd/mpd.conf << 'EOF'
# Music directory
music_directory     "~/Music/pisat"

# Playlists directory
playlist_directory  "~/.mpd/playlists"

# MPD state files
db_file             "~/.mpd/database"
log_file            "~/.mpd/log"
pid_file            "~/.mpd/pid"
state_file          "~/.mpd/state"
sticker_file        "~/.mpd/sticker.sql"

# Network binding
bind_to_address     "localhost"
port                "6600"

# Audio output (ALSA)
audio_output {
    type        "alsa"
    name        "Pi-Sat Speaker"
    device      "plughw:0,0"
    mixer_type  "software"
}
EOF

# Expand ~ in config file
sed -i "s|~|$HOME|g" ~/.mpd/mpd.conf

# Start MPD
mpd ~/.mpd/mpd.conf

# Update MPD database
mpc update

# Verify MPD is running
mpc status
```

**Expected output:** Should show "volume: 100%  repeat: off  random: off  single: off  consume: off"

### Step 11: Configure Environment Variables

```bash
cd ~/pi-sat

# Copy environment template
cp .envrc.local.example .envrc.local

# Edit .envrc.local for your setup
nano .envrc.local
```

**Minimal .envrc.local:**
```bash
# Music library path (already created in Step 10)
export PISAT_MUSIC_DIR="$HOME/Music/pisat"

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
cp /path/to/your/music/*.mp3 ~/Music/pisat/

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
MUSIC_DIR="$HOME/Music/pisat"
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
- [ ] Music library created (`ls ~/Music/pisat/`)
- [ ] direnv configured (`direnv allow`)
- [ ] Tests passing (`./pi-sat.sh test`)
- [ ] Audio devices working (mic + speaker test)
- [ ] Microphone mute button functional (if available)
- [ ] Wake word detection working
- [ ] Music playback working

---

## Next Steps

1. **Add More Music**: Copy MP3 files to `~/Music/pisat/` and run `mpc update`
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
