# Pi-Sat Voice Assistant

A minimal voice assistant for Raspberry Pi 5 with Hailo AI accelerator integration, designed for Home Assistant control.

## Features

- 🎯 **Wake Word Detection** - Uses openWakeWord for local activation
- 🎤 **Voice Activity Detection** - Smart recording with silence detection  
- 🧠 **Hailo AI Integration** - Whisper STT with hardware acceleration
- 🏠 **Home Assistant Control** - Natural language device control
- 🔊 **Text-to-Speech** - Local response generation

## Quick Start

```bash
# 1. Setup
./setup.sh

# 2. Configure (set your Home Assistant token)
export HA_URL="http://homeassistant.local:8123"
export HA_TOKEN="your_long_lived_token_here"

# 3. Run
source venv/bin/activate
python voice_assistant.py
```

## Deployment to Raspberry Pi

```bash
# 1. Clone and setup
git clone https://github.com/your-username/pi-sat.git
cd pi-sat
./setup.sh --service

# 2. Set your Home Assistant token
export HA_TOKEN="your_long_lived_token_here"

# 3. Start the service
sudo systemctl start pi-sat.service

# View logs: sudo journalctl -u pi-sat.service -f
```

## Project Structure

```
pi-sat/
├── voice_assistant.py   # Main orchestrator
├── config.py           # Central configuration
├── modules/
│   ├── __init__.py
│   ├── wake_word.py    # openWakeWord integration
│   ├── vad.py          # WebRTC VAD + recording
│   └── hailo_stt.py    # Hailo Whisper STT
├── requirements.txt    # Python dependencies
├── setup.sh           # System setup
├── .cursorrules       # Development rules
└── README.md          # This file
```

## Development Roadmap

- [x] **Phase 1**: Wake word detection
- [ ] **Phase 2**: VAD-based command recording  
- [ ] **Phase 3**: Hailo Whisper integration
- [ ] **Phase 4**: Home Assistant API integration
- [ ] **Phase 5**: Text-to-speech responses

## Configuration

Edit `config.py` to customize:
- Audio settings (sample rate, chunk size)
- Wake word model and threshold
- Home Assistant connection details
- VAD sensitivity

## Hardware Requirements

- Raspberry Pi 5
- Hailo-8 AI accelerator
- USB microphone or audio HAT
- Speaker for audio output

## Notes

Following KISS, DRY, and minimal code principles. Each component is modular and can be extended independently. 