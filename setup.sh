#!/bin/bash
echo "🎤 Pi-Sat Setup"

# Install system dependencies
sudo apt update
sudo apt install -y portaudio19-dev python3-pyaudio alsa-utils ffmpeg

# Setup Python environment
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

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
Environment=HAILO_STT_USE_HAILO=true
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
    echo "🔧 For development: source venv/bin/activate && python voice_assistant.py"
    echo "🤖 For Pi service: ./setup.sh --service"
fi 