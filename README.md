# Pi-Sat Voice Assistant

Minimal voice assistant for Raspberry Pi 5 with Hailo AI accelerator. Local wake word detection, Hailo-accelerated Whisper STT, and Home Assistant control.

## Setup

```bash
# Clone repository
git clone https://github.com/your-username/pi-sat.git
cd pi-sat

# Development mode
./setup.sh
export HA_URL="http://homeassistant.local:8123"
export HA_TOKEN="your_token_here"
source venv/bin/activate
python voice_assistant.py

# Production service (Raspberry Pi)
./setup.sh --service
export HA_TOKEN="your_token_here"
sudo systemctl start pi-sat.service
sudo journalctl -u pi-sat.service -f  # View logs
```

## Configuration

Environment variables override `config.py` defaults:
- `HA_URL` - Home Assistant URL  
- `HA_TOKEN` - Long-lived access token

## Hardware

- **Raspberry Pi 5** + Hailo-8 AI accelerator  
- **Microphone** (USB or HAT)  
- **Speaker** for responses

## STT Integration

The system uses Hailo-accelerated Whisper models for real-time speech recognition:
- **Base model**: 5-second chunks, higher accuracy
- **Tiny model**: 10-second chunks, faster inference
- **Hardware**: Hailo-8L accelerator for optimal performance
- **Preprocessing**: VAD, audio enhancement, mel spectrogram generation
- **Postprocessing**: Repetition penalty, transcription cleaning 