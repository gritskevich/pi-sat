#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1090
source "$SCRIPT_DIR/pisat-common.sh"

install() {
    log "Installing Pi-Sat..."

    sudo apt update

    if ! command -v python3 >/dev/null 2>&1; then
        error "No python3 interpreter found in PATH."
        exit 1
    fi

    PY_MAJOR_MINOR="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    if [ "$PY_MAJOR_MINOR" = "3.11" ] || [ "$PY_MAJOR_MINOR" = "3.13" ]; then
        PYTHON_BIN="python3"
    else
        log "Setting up Python 3.11 with pyenv..."
        sudo apt install -y build-essential git curl \
            libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev \
            libncursesw5-dev xz-utils tk-dev libffi-dev liblzma-dev

        PYENV_ROOT="$HOME/.pyenv"
        if [ ! -d "$PYENV_ROOT" ]; then
            curl https://pyenv.run | bash
        fi

        if ! grep -q 'PYENV_ROOT="$HOME/.pyenv"' "$HOME/.bashrc"; then
            {
                echo ''
                echo 'export PYENV_ROOT="$HOME/.pyenv"'
                echo 'export PATH="$PYENV_ROOT/bin:$PATH"'
                echo 'eval "$(pyenv init -)"'
            } >> "$HOME/.bashrc"
        fi

        export PYENV_ROOT
        export PATH="$PYENV_ROOT/bin:$PATH"

        if [ ! -x "$PYENV_ROOT/bin/pyenv" ]; then
            error "pyenv install failed."
            exit 1
        fi

        "$PYENV_ROOT/bin/pyenv" install -s 3.11.9
        "$PYENV_ROOT/bin/pyenv" local 3.11.9
        PYTHON_BIN="$PYENV_ROOT/versions/3.11.9/bin/python"
        PY_MAJOR_MINOR="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    fi

    if [ -x "$VENV_DIR/bin/python" ]; then
        VENV_PY_MAJOR_MINOR="$("$VENV_DIR/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
        if [ "$VENV_PY_MAJOR_MINOR" != "$PY_MAJOR_MINOR" ]; then
            warn "Recreating venv to match Python $PY_MAJOR_MINOR (was $VENV_PY_MAJOR_MINOR)..."
            rm -rf "$VENV_DIR"
        fi
    fi

    USE_SYS_SITE=0
    if grep -qi "raspberry pi 5" /proc/device-tree/model 2>/dev/null; then
        USE_SYS_SITE=1
    fi

    if [ -d "$VENV_DIR" ]; then
        if [ "$USE_SYS_SITE" = "1" ]; then
            if ! grep -qi '^include-system-site-packages = true' "$VENV_DIR/pyvenv.cfg" 2>/dev/null; then
                warn "Recreating venv with system site-packages to use Hailo SDK..."
                rm -rf "$VENV_DIR"
            fi
        fi
    fi

    if [ ! -d "$VENV_DIR" ]; then
        log "Creating virtual environment..."
        if [ "$USE_SYS_SITE" = "1" ]; then
            "$PYTHON_BIN" -m venv --system-site-packages "$VENV_DIR"
        else
            "$PYTHON_BIN" -m venv "$VENV_DIR"
        fi
    fi

    log "Installing system dependencies..."
    sudo apt install -y portaudio19-dev python3-pyaudio alsa-utils ffmpeg libportaudio2 sox

    if dpkg -s hailo-all >/dev/null 2>&1; then
        log "Hailo SDK already installed."
    elif ! grep -qs "hailo-ai.com/apt" /etc/apt/sources.list.d/hailo.list; then
        log "Adding Hailo APT repository..."
        sudo apt install -y gnupg
        if curl -fsSL https://hailo-ai.com/apt/hailo-repo.gpg | sudo gpg --dearmor -o /usr/share/keyrings/hailo-archive-keyring.gpg; then
            echo "deb [signed-by=/usr/share/keyrings/hailo-archive-keyring.gpg] https://hailo-ai.com/apt bookworm main" \
                | sudo tee /etc/apt/sources.list.d/hailo.list >/dev/null
            sudo apt update
        else
            warn "Failed to download Hailo repo key (offline/DNS?). Skipping hailo-all install."
        fi
    fi
    if grep -qs "hailo-ai.com/apt" /etc/apt/sources.list.d/hailo.list; then
        sudo apt install -y hailo-all
    fi

    if ! command -v piper >/dev/null 2>&1; then
        log "Installing Piper TTS..."
        tmpdir="$(mktemp -d)"
        curl -fsSL -o "$tmpdir/piper_arm64.tar.gz" \
            "https://github.com/rhasspy/piper/releases/download/v1.2.0/piper_arm64.tar.gz"
        tar xzf "$tmpdir/piper_arm64.tar.gz" -C "$tmpdir"
        sudo cp "$tmpdir/piper/piper" /usr/local/bin/
        sudo chmod +x /usr/local/bin/piper
        sudo cp "$tmpdir/piper/"*.so* /usr/local/lib/ && sudo ldconfig
        sudo cp -r "$tmpdir/piper/espeak-ng-data" /usr/local/share/
        sudo ln -sf /usr/local/share/espeak-ng-data /usr/share/espeak-ng-data
        rm -rf "$tmpdir"
    fi

    sudo apt install -y pipewire wireplumber pipewire-pulse pipewire-alsa pulseaudio-utils

    log "Configuring audio devices..."
    if pactl list sources short | grep -q "USB_Microphone"; then
        log "Setting Generalplus USB Microphone as default source..."
        pactl set-default-source alsa_input.usb-MUSIC-BOOST_USB_Microphone_MB-306-00.mono-fallback || true
    else
        warn "Generalplus USB Microphone not found. Using system default."
    fi

    sudo apt install -y mpd mpc
    if [ ! -f "$HOME/.mpd/mpd.conf" ]; then
        log "Configuring MPD..."
        mkdir -p "$HOME/Music" "$HOME/.mpd/playlists"
        cat > "$HOME/.mpd/mpd.conf" <<'EOF_MPD'
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
    type        "pulse"
    name        "Pi-Sat Pulse"
    mixer_type  "software"
}
EOF_MPD
        sed -i "s|~|$HOME|g" "$HOME/.mpd/mpd.conf"
    fi

    log "Installing Python dependencies..."
    "$PY" -m ensurepip --upgrade
    "$PY" -m pip install --upgrade pip

    HAILO_DIR="$PROJECT_ROOT/hailo_examples/speech_recognition"
    INF_REQ="$HAILO_DIR/requirements_inference.txt"
    if [ -f "$INF_REQ" ]; then
        log "Installing Hailo example requirements..."
        tmp_req="$(mktemp)"
        grep -v '^[[:space:]]*scipy==' "$INF_REQ" > "$tmp_req"
        "$PY" -m pip install -r "$tmp_req"
        rm -f "$tmp_req"
    fi

    "$PY" -m pip install -r "$PROJECT_ROOT/requirements.txt"
    "$PY" -m pip install --no-deps openwakeword>=0.6.0

    log "Installing pi-sat package in editable mode..."
    "$PY" -m pip install -e "$PROJECT_ROOT"

    if ! "$PY" -c "import hailo_platform" 2>/dev/null; then
        warn "Hailo Python bindings (hailo_platform) not found in venv."
        warn "On Raspberry Pi 5, the installer creates the venv with system site-packages."
        echo "  If you haven't installed the Hailo SDK: sudo apt install hailo-all"
        echo "  Then rerun: rm -rf '$VENV_DIR' && bash '$PROJECT_ROOT/pi-sat.sh' install"
    fi

    log "Setting up wake word models..."
    "$PY" -c "
import openwakeword.utils
openwakeword.utils.download_models()
print('Wake word models downloaded successfully')
"

    log "Setting up Hailo examples..."
    if [ -d "hailo_examples/speech_recognition" ]; then
        cd hailo_examples/speech_recognition/app

        if [ -d "hefs" ] && [ -d "decoder_assets" ]; then
            log "✅ Hailo models already exist, skipping download"
        else
            log "📥 Downloading Hailo models..."
            chmod +x download_resources.sh
            ./download_resources.sh
            log "✅ Hailo models downloaded successfully"
        fi

        cd ../../..
    else
        warn "⚠️  hailo_examples/speech_recognition directory not found"
        warn "   Hailo STT will not be available"
    fi

    log "Installation complete!"
}

download_voice() {
    log "Downloading Piper voice model..."
    mkdir -p "$PROJECT_ROOT/resources/voices"

    VOICE_MODEL="fr_FR-siwis-medium"
    VOICES_DIR="$PROJECT_ROOT/resources/voices"

    log "Downloading French voice model: $VOICE_MODEL"
    wget -O "$VOICES_DIR/$VOICE_MODEL.onnx" \
        "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/fr/fr_FR/siwis/medium/$VOICE_MODEL.onnx"

    wget -O "$VOICES_DIR/$VOICE_MODEL.onnx.json" \
        "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/fr/fr_FR/siwis/medium/$VOICE_MODEL.onnx.json"

    log "✓ Voice model downloaded: $VOICE_MODEL"
}

case "${1:-help}" in
    install)
        install
        ;;
    download_voice)
        download_voice
        ;;
    *)
        error "Unknown command: $1"
        exit 1
        ;;
esac
