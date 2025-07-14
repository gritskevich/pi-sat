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

# Setup Hailo examples
echo "🤖 Setting up Hailo examples..."
HAILO_DIR="lib/hailo-examples"

if [ ! -d "$HAILO_DIR" ]; then
    echo "📥 Cloning Hailo Application Code Examples..."
    mkdir -p lib
    git clone https://github.com/hailo-ai/Hailo-Application-Code-Examples.git "$HAILO_DIR"
else
    echo "✅ Hailo examples already cloned"
fi

# Setup Hailo speech recognition environment
HAILO_STT_DIR="$HAILO_DIR/runtime/hailo-8/python/speech_recognition"
echo "🔧 Setting up Hailo STT environment..."

if [ -d "$HAILO_STT_DIR" ]; then
    cd "$HAILO_STT_DIR"
    if [ ! -d "whisper_env" ]; then
        echo "📦 Installing Hailo STT dependencies..."
        python3 setup.py
    else
        echo "✅ Hailo STT environment already exists"
    fi
    cd - > /dev/null
else
    echo "❌ Hailo STT directory not found: $HAILO_STT_DIR"
    exit 1
fi

# Download wake word models
echo "🔊 Setting up wake word models..."
python3 -c "
import openwakeword.utils
openwakeword.utils.download_models()
print('Wake word models downloaded successfully')
"

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