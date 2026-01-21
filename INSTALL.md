# Pi-Sat Installation (Raspberry Pi 5 + Hailo-8L)

**KISS principle**: Minimal steps to get wake word → STT → MPD → TTS working.

---

## Prerequisites (Do Once)

### 1. System Requirements

- **Hardware**: Raspberry Pi 5 + Hailo-8L AI Kit
- **OS**: Raspberry Pi OS 64-bit (Bookworm)
- **Audio**: USB microphone + speaker/headphones

### 2. Install Hailo SDK (System-Wide)

```bash
# Add Hailo repository
wget -qO - https://hailo-ai.com/apt/hailo-repo.gpg | sudo apt-key add -
echo "deb https://hailo-ai.com/apt bookworm main" | sudo tee /etc/apt/sources.list.d/hailo.list

# Install Hailo packages
sudo apt update
sudo apt install -y hailo-all

# Verify installation
hailortcli fw-control identify
# Should show: Board Name: Hailo-8, Device Architecture: HAILO8L
```

### 3. Install Piper TTS Binary (System-Wide)

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

# Verify installation
piper --version
# Should show: 1.2.0
```

### 4. Install MPD (Music Player Daemon)

```bash
sudo apt install -y mpd mpc

# Create MPD config
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

# Fix paths
sed -i "s|~|$HOME|g" ~/.mpd/mpd.conf

# Start MPD
mpd ~/.mpd/mpd.conf
mpc update
```

---

## Pi-Sat Installation (Per Project)

### 1. Clone Repository

```bash
git clone https://github.com/gritskevich/pi-sat.git
cd pi-sat
```

### 2. Run Install Script

This handles:
- Python venv creation (with system-site-packages for Hailo SDK)
- System dependencies (portaudio, alsa, ffmpeg, sox)
- Python packages from requirements.txt
- Hailo example dependencies
- Wake word models download
- Hailo STT models download (~600MB)

```bash
./pi-sat.sh install
```

**Expected output:**
```
[Pi-Sat] Installing Pi-Sat...
[Pi-Sat] Creating virtual environment...
[Pi-Sat] Installing system dependencies...
[Pi-Sat] Installing Python dependencies...
[Pi-Sat] Installing Hailo example requirements...
[Pi-Sat] Setting up wake word models...
[Pi-Sat] Downloading Hailo models...
[Pi-Sat] ✅ Hailo models downloaded successfully
[Pi-Sat] Installation complete!
```

### 3. Download TTS Voice Model

```bash
./pi-sat.sh download_voice
```

Downloads French voice model (fr_FR-siwis-medium, ~60MB) to `resources/voices/`.

For English, set language in config (see Configuration below).

### 4. Add Music Files

```bash
# Copy your MP3 files
cp /path/to/music/*.mp3 ~/Music/

# Update MPD database
mpc update

# Verify music loaded
mpc listall | head -10
```

---

## Configuration (Optional)

Create `.envrc.local` for machine-specific settings:

```bash
# Language (default: fr)
export LANGUAGE='fr'  # or 'en'

# Audio devices (if not default)
export INPUT_DEVICE_NAME='USB Microphone'
export PIPER_OUTPUT_DEVICE='plughw:3,0'

# Wake word sensitivity (default: 0.5)
export WAKE_WORD_THRESHOLD=0.5  # Lower = more sensitive

# Debug mode
export PISAT_DEBUG=true
```

Then enable direnv:

```bash
echo 'eval "$(direnv hook bash)"' >> ~/.bashrc
source ~/.bashrc
direnv allow
```

---

## Run Pi-Sat

### Interactive Mode (Foreground)

```bash
./pi-sat.sh run
```

You should see:
```
[Pi-Sat] Starting Pi-Sat orchestrator...
Listening for wake word "Alexa"...
```

### Debug Mode (Shows Audio Levels)

```bash
./pi-sat.sh run_debug
```

Shows real-time RMS levels and wake word confidence scores.

### Test Voice Commands

1. Say **"Alexa"** (wait for beep)
2. Say **"Joue Frozen"** (or any song name)
3. Music should start playing

**Other commands:**
- "Alexa, arrête" (stop)
- "Alexa, plus fort" (volume up)
- "Alexa, moins fort" (volume down)

---

## Verification Checklist

Before running, verify:

```bash
# Hailo hardware detected
hailortcli fw-control identify

# Piper installed
piper --version

# MPD running
mpc status

# Music library populated
mpc listall | wc -l  # Should show > 0

# Python packages installed
source venv/bin/activate
python -c "import hailo_platform, openwakeword, python_mpd2, thefuzz; print('✓ All imports OK')"

# Hailo models downloaded
ls hailo_examples/speech_recognition/app/hefs/h8l/base/*.hef | wc -l  # Should show 2

# TTS voice model downloaded
ls resources/voices/*.onnx | wc -l  # Should show 1+
```

---

## Troubleshooting

### Hailo Not Detected

```bash
# Check PCI device
lspci | grep Hailo

# Reinstall driver (requires reboot)
sudo apt install --reinstall hailo-all
sudo reboot
```

### No Audio Output

```bash
# List audio devices
aplay -l

# Test speaker
aplay resources/wakesound.wav

# Adjust ALSA device in .envrc.local:
export OUTPUT_ALSA_DEVICE='plughw:X,0'  # Replace X with card number
```

### Wake Word Not Detecting

```bash
# Run in debug mode to see confidence scores
./pi-sat.sh run_debug

# Adjust sensitivity if needed
export WAKE_WORD_THRESHOLD=0.3  # Lower = more sensitive (default: 0.5)
./pi-sat.sh run
```

### MPD Connection Failed

```bash
# Check MPD status
mpc status

# Restart MPD
mpd --kill
mpd ~/.mpd/mpd.conf
```

### ImportError: hailo_platform

Your venv wasn't created with `--system-site-packages`. Recreate it:

```bash
rm -rf venv
./pi-sat.sh install
```

---

## Production Deployment (Optional)

### Auto-Start on Boot (systemd)

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

### View Logs

```bash
journalctl --user -u pi-sat -f
```

### Disable Auto-Suspend (24/7 Operation)

```bash
# Prevent system sleep
sudo systemctl mask sleep.target suspend.target hibernate.target

# Disable console blanking
sudo sh -c 'echo "consoleblank=0" >> /boot/firmware/cmdline.txt'

# Reboot to apply
sudo reboot
```

---

## Uninstall

```bash
# Remove systemd service (user)
./install-daemon.sh uninstall --user

# Remove systemd service (system)
sudo ./install-daemon.sh uninstall --system

# Remove project
cd ~
rm -rf pi-sat

# Optional: Remove system packages
sudo apt remove --purge hailo-all mpd
sudo rm /usr/local/bin/piper
```

---

## Resources

- **GitHub Issues**: https://github.com/gritskevich/pi-sat/issues
- **Hailo Developer Zone**: https://hailo.ai/developer-zone/
- **Piper TTS**: https://github.com/rhasspy/piper
- **MPD Documentation**: https://www.musicpd.org/doc/
