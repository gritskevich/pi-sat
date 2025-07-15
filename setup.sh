#!/bin/bash
echo "🎤 Pi-Sat Voice Assistant Setup"
echo "==============================="

set -e

# Check if running in virtual environment
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "✅ Virtual environment detected: $VIRTUAL_ENV"
else
    echo "❌ Please run this script from within a virtual environment"
    echo "   Create one with: python3 -m venv venv && source venv/bin/activate"
    exit 1
fi

# Install system dependencies
echo "📦 Installing system dependencies..."
sudo apt update
sudo apt install -y portaudio19-dev python3-pyaudio alsa-utils ffmpeg libportaudio2

# Install Python dependencies
echo "🐍 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Download wake word models
echo "🔊 Setting up wake word models..."
python3 -c "
import openwakeword.utils
openwakeword.utils.download_models()
print('Wake word models downloaded successfully')
"

# Download Hailo Whisper models (if not already present)
echo "🤖 Checking Hailo Whisper models..."
if [ -d "speech_recognition" ]; then
    cd speech_recognition/app
    
    # Check if models already exist
    if [ -d "hefs" ] && [ -d "decoder_assets" ]; then
        echo "✅ Hailo models already exist, skipping download"
    else
        echo "📥 Downloading Hailo models..."
        chmod +x download_resources.sh
        ./download_resources.sh
        echo "✅ Hailo models downloaded successfully"
    fi
    
    cd ../..
else
    echo "⚠️  speech_recognition directory not found, skipping Hailo model download"
fi

# Optional: Install as system service
if [ "$1" = "--service" ]; then
    echo "🔌 Installing as system service..."
    sudo tee /etc/systemd/system/pi-sat.service > /dev/null << EOF
[Unit]
Description=Pi-Sat Voice Assistant
After=network.target sound.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$(pwd)
# Hailo STT always enabled
ExecStart=$(pwd)/venv/bin/python voice_assistant.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    sudo systemctl daemon-reload
    sudo systemctl enable pi-sat.service
    echo "✅ Service installed! Start with: sudo systemctl start pi-sat.service"
    echo "📋 Set your HA token: export HA_TOKEN='your_token_here'"
else
    echo "✅ Setup complete!"
    echo ""
    echo "To start the voice assistant:"
    echo "  python3 voice_assistant.py"
    echo ""
    echo "Environment variables:"
    echo "  HA_URL=http://homeassistant.local:8123"
    echo "  HA_TOKEN=your_token_here"
fi 