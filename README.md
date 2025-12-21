# Pi-Sat: Voice-Controlled Music Player for Kids

**100% offline, local-first voice-controlled music player for Raspberry Pi 5 + Hailo-8L**

Perfect for kids who want to control their music collection by voice without any cloud services, subscriptions, or internet dependency.

---

## Features

- **Wake Word Detection**: Say "Alexa" to activate (runs locally with openWakeWord)
- **Voice Commands**: "Play Frozen!", "Skip", "I love this!", "Stop in 30 minutes"
- **Fuzzy Search**: Handles pronunciation errors ("frozzen" finds "Frozen")
- **Smart Favorites**: Build playlists by saying "I love this"
- **Mic Mute Button**: Analog volume-level detection (no GPIO) - unmute to force listening mode
- **Auto USB Import**: Plug in a USB stick with MP3s, say "update your music library" to import
- **Sleep Timer**: "Stop in 30 minutes" with smooth fade-out
- **Volume Ducking**: Music auto-lowers when wake word detected
- **100% Offline**: Zero cloud dependencies, works without internet

---

## Quick Start

### Prerequisites

- Raspberry Pi 5 (4GB+ recommended)
- Hailo-8L AI accelerator HAT
- USB microphone or Raspberry Pi official camera with mic (with hardware mute button)
- Speaker (3.5mm jack or USB)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/gritskevich/pi-sat.git
cd pi-sat

# 2. Install dependencies and setup
./pi-sat.sh install
./pi-sat.sh setup_mpd
./pi-sat.sh download_voice

# 3. Add music to your library
mkdir -p ~/Music/pisat
cp /path/to/your/music/*.mp3 ~/Music/pisat/
./pi-sat.sh mpd_update

# 4. Run
./pi-sat.sh run
```

**Full installation guide:** [INSTALL.md](INSTALL.md)

---

## Usage

Say "**Alexa**" followed by your command:

### Music Control
- French (default): "Joue Frozen", "Pause", "Suivant", "Précédent", "Joue mes favoris"
- English (optional): "Play Frozen", "Pause", "Next", "Previous", "Play my favorites"

### Volume Control
- French: "Plus fort" / "Moins fort"
- English: "Louder" / "Quieter"

### Favorites
- French: "J'adore ça" / "Ajoute aux favoris"
- English: "I love this" / "Add to favorites"

### Sleep Timer
- French: "Arrête dans 30 minutes"
- English: "Stop in 30 minutes"

### Library Management
- "Update your music library"

### Mic Mute Button

The system monitors microphone audio levels to detect mute button state:
- **Muted**: Audio level drops to near-zero (hardware mute button pressed)
- **Unmuted**: Audio level returns (hardware mute button released)
- **Force Listening**: Unmuting the mic triggers force listening mode (bypasses wake word)

---

## Documentation

- **[INSTALL.md](INSTALL.md)** - Complete installation guide
- **[CLAUDE.md](CLAUDE.md)** - Developer guide (for AI development)
- **[docs/MUSIC_LIBRARY_ORGANIZATION.md](docs/MUSIC_LIBRARY_ORGANIZATION.md)** - Music library organization patterns
- **[docs/HAILO_STATUS.md](docs/HAILO_STATUS.md)** - Hailo STT hardware status and debugging
- **[tests/README.md](tests/README.md)** - Test suite documentation

---

## Architecture

```
Wake Word ("Alexa") → Volume Duck → Voice Recording →
Hailo Whisper STT → Intent Engine (Fuzzy Match) → MPD Music Player →
Piper TTS Response
```

**Alternative**: Mic mute button (analog volume-level detection) for force listening mode

### Components

1. **Wake Word Listener** - Detects "Alexa" using openWakeWord (optionally Hailo-accelerated)
2. **Speech Recorder** - Records voice commands using WebRTC VAD with smart silence detection
3. **Hailo STT** - Hailo-8L accelerated Whisper transcription (~1-2s latency)
4. **Intent Engine** - Fuzzy-match command classifier (no LLM needed)
5. **MPD Controller** - Controls Music Player Daemon for playback
6. **Piper TTS** - Offline text-to-speech responses
7. **Mic Mute Detector** - Analog audio level monitoring for mute button detection

---

## Development

### Running

```bash
./pi-sat.sh run              # Normal mode
./pi-sat.sh run_debug        # Debug with audio playback
./pi-sat.sh run_live         # Live debug output
```

### Testing

```bash
./pi-sat.sh test             # Run all tests
./pi-sat.sh test wake_word   # Test wake word detection
./pi-sat.sh test stt         # Test speech-to-text
./pi-sat.sh test intent      # Test intent classification
./pi-sat.sh test mpd         # Test music control
```

### MPD Management

```bash
./pi-sat.sh mpd_start        # Start MPD daemon
./pi-sat.sh mpd_update       # Update music library
./pi-sat.sh mpd_status       # Show MPD status
```

---

## Hardware Shopping List

**Required:**
- Raspberry Pi 5 (4GB or 8GB): ~$60-80
- Hailo-8L AI HAT: ~$70
- USB Microphone with hardware mute button: ~$15-25
- Speaker (3.5mm or USB): ~$10-30
- MicroSD Card (32GB+): ~$10
- Power Supply (27W USB-C): ~$12

**Optional:**
- Enclosure/Case: ~$10-20

**Total**: ~$175-250

---

## Architecture Decisions

### Why No LLM for Intent?
- **Fast**: Fuzzy matching is instant (<1ms)
- **Deterministic**: No hallucinations or unpredictable behavior
- **Resource-efficient**: No GPU needed beyond STT
- **Kid-friendly**: Simple commands work better than natural language

### Why MPD?
- **Rock-solid**: Industry-standard music daemon
- **Low resource**: Minimal CPU/RAM usage
- **Headless**: No X server needed
- **Playlist support**: M3U, favorites, queues

### Why Piper TTS?
- **Best offline TTS**: Human-sounding voices
- **Fast**: Real-time generation on Pi 5
- **Multiple voices**: Easy to swap models
- **Active development**: rhasspy project

---

## Contributing

Contributions welcome! Please:

1. Follow the KISS principle
2. Add tests for new features
3. Keep dependencies minimal
4. Document voice commands
5. Test on actual Raspberry Pi 5 hardware

---

## License

MIT License - see LICENSE file

---

## Credits

- **openWakeWord**: Wake word detection
- **Hailo**: AI accelerator SDK
- **MPD**: Music Player Daemon
- **Piper TTS**: Offline text-to-speech
- **thefuzz**: Fuzzy string matching

---

## Support

For issues, questions, or feature requests:
- GitHub Issues: https://github.com/gritskevich/pi-sat/issues
- Discussions: https://github.com/gritskevich/pi-sat/discussions
