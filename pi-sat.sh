#!/bin/bash

# Pi-Sat Voice Assistant Runner
# KISS, DRY, Minimum elegant code

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_ROOT/venv"
PY="$VENV_DIR/bin/python"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[Pi-Sat]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Activate virtual environment helper
activate() {
    if [ ! -d "$VENV_DIR" ]; then
        error "Virtual environment not found. Run: $0 install"
        return 1
    fi

    # If the script is sourced, we can activate in current shell
    if [ "${BASH_SOURCE[0]}" != "$0" ]; then
        log "Activating virtual environment..."
        # shellcheck disable=SC1090
        source "$VENV_DIR/bin/activate"
    else
        warn "To activate in your current shell, run: source $0 activate"
        echo "Or run: source \"$VENV_DIR/bin/activate\""
    fi
}

# Clear log files across the repo
logs_clear() {
    log "Clearing log files..."
    set +e
    find . -type f -name "*.log" -delete 2>/dev/null
    set -e
    log "Log files cleared."
}

# Run wake word listener only (real mic)
listen() {
    check_venv
    log "Starting wake word listener (mic)..."
    exec "$PY" modules/wake_word_listener.py
}

# Quick Hailo diagnostic
hailo_check() {
    check_venv
    log "Running Hailo diagnostics..."
    "$PY" - <<'PY'
import os, sys
print("WD:", os.getcwd())
try:
    import hailo_platform as hp
    print("hailo_platform:", getattr(hp, "__version__", "unknown"))
except Exception as e:
    print("hailo_platform import FAIL:", e)

sys.path.insert(0, os.path.join(os.getcwd(), "hailo_examples/speech_recognition"))
try:
    from app.whisper_hef_registry import HEF_REGISTRY
    from app.hailo_whisper_pipeline import HailoWhisperPipeline
    print("Imports: OK")
except Exception as e:
    print("Imports: FAIL", e)
    raise SystemExit(1)

base = os.path.join(os.getcwd(), "hailo_examples/speech_recognition")
variant = "base"
found = []
for arch in ("hailo8l","hailo8"):
    try:
        enc = os.path.join(base, HEF_REGISTRY[variant][arch]["encoder"])
        dec = os.path.join(base, HEF_REGISTRY[variant][arch]["decoder"])
    except KeyError:
        continue
    ok = os.path.exists(enc) and os.path.exists(dec)
    print(f"arch={arch} exists={ok}\n  encoder={enc}\n  decoder={dec}")
    if ok:
        found.append((arch, enc, dec))

if not found:
    print("NO HEF FILES FOUND")
    raise SystemExit(2)

arch, enc, dec = found[0]
print("Trying pipeline init...", arch)
try:
    pipe = HailoWhisperPipeline(enc, dec, variant=variant, multi_process_service=False)
    print("Pipeline init: OK")
except Exception as e:
    print("Pipeline init: FAIL:", type(e).__name__, e)
    raise SystemExit(3)
PY
}

# Check if virtual environment exists
check_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        error "Virtual environment not found. Run: $0 install"
        exit 1
    fi
}

# Install dependencies
install() {
    log "Installing Pi-Sat..."
    
    # On Raspberry Pi 5, always include system site-packages to pick up Hailo SDK bindings
    USE_SYS_SITE=0
    if grep -qi "raspberry pi 5" /proc/device-tree/model 2>/dev/null; then
        USE_SYS_SITE=1
    fi

    # Recreate venv if it exists but lacks required system site-packages
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
            python3 -m venv --system-site-packages "$VENV_DIR"
        else
            python3 -m venv "$VENV_DIR"
        fi
    fi
    
    log "Installing system dependencies..."
    sudo apt update
    sudo apt install -y portaudio19-dev python3-pyaudio alsa-utils ffmpeg libportaudio2 sox
    
    log "Installing Python dependencies..."
    "$PY" -m pip install --upgrade pip
    "$PY" -m pip install -r "$PROJECT_ROOT/requirements.txt"
    
    log "Installing pi-sat package in editable mode..."
    "$PY" -m pip install -e "$PROJECT_ROOT"

    # Optional: Hailo example-specific Python deps (installed into the same venv)
    HAILO_DIR="$PROJECT_ROOT/hailo_examples/speech_recognition"
    INF_REQ="$HAILO_DIR/requirements_inference.txt"
    if [ -f "$INF_REQ" ]; then
        log "Installing Hailo example requirements..."
        "$PY" -m pip install -r "$INF_REQ"
    fi

    # Verify Hailo Python bindings are importable inside venv
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

# Enable bash completion
completion() {
    echo "To enable bash completion for pi-sat.sh:"
    echo ""
    echo "  source $PROJECT_ROOT/pi-sat-completion.bash"
    echo ""
    echo "If you use direnv, entering this repo will auto-enable completion in bash."
    echo ""
    echo "To make it permanent, add this line to your ~/.bashrc:"
    echo ""
    echo "  echo 'source $PROJECT_ROOT/pi-sat-completion.bash' >> ~/.bashrc"
    echo ""
}

__pisat_list_commands() {
    awk '
        function emit(cmd) {
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", cmd)
            if (cmd == "" || cmd == "*" || cmd ~ /^-/ || cmd ~ /^__/) return
            if (!seen[cmd]++) print cmd
        }
        $0 ~ /^case[[:space:]]+"[$][{]1:-help[}]"[[:space:]]+in/ { in_case = 1; next }
        in_case && $0 ~ /^esac/ { exit }
        in_case {
            if ($0 ~ /^[[:space:]]*"[^"]+"[[:space:]]*[)]/) {
                line = $0
                sub(/^[[:space:]]*"/, "", line)
                sub(/".*/, "", line)
                sub(/[)].*/, "", line)
                emit(line)
            }
        }
    ' "$0"
}

__pisat_list_test_targets() {
    awk -v needle='case "$1" in' '
        function emit(cmd) {
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", cmd)
            if (cmd == "" || cmd == "*" || cmd ~ /^-/ || cmd ~ /^__/) return
            if (!seen[cmd]++) print cmd
        }
        $0 ~ /^test[(][)][[:space:]]*[{]/ { in_test = 1; next }
        in_test && index($0, needle) { in_case = 1; next }
        in_case && $0 ~ /^[[:space:]]*esac/ { in_case = 0; next }
        in_test && $0 ~ /^[}]/ { exit }
        in_case {
            if ($0 ~ /^[[:space:]]*"[^"]+"[[:space:]]*[)]/) {
                line = $0
                sub(/^[[:space:]]*"/, "", line)
                sub(/".*/, "", line)
                sub(/[)].*/, "", line)
                emit(line)
            }
        }
    ' "$0"
}

__complete() {
    case "${1:-commands}" in
        commands)
            __pisat_list_commands
            ;;
        test_targets)
            __pisat_list_test_targets
            ;;
        *)
            return 2
            ;;
    esac
}

# Download Piper voice model
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

# Run tests
test() {
    check_venv
    log "Running tests..."
    
    if [ -z "$1" ]; then
        # Run all tests
        "$PY" -m unittest discover tests -v
    else
        # Run specific test
        case "$1" in
            "wake_word")
                "$PY" tests/test_wake_word.py
                ;;
            "listener")
                "$PY" tests/test_wake_word_listener.py
                ;;
            "orchestrator")
                "$PY" tests/test_orchestrator.py
                ;;
            "integration")
                "$PY" tests/test_orchestrator_integration.py
                ;;
            "microphone")
                "$PY" tests/test_microphone_recording.py
                ;;
            "stt")
                "$PY" tests/run_tests.py --test stt
                ;;
            "stt_integration")
                "$PY" tests/run_tests.py --test stt_integration
                ;;
            "e2e")
                "$PY" tests/run_tests.py --test e2e
                ;;
            *)
                error "Unknown test: $1"
                echo "Available tests: wake_word, listener, orchestrator, integration, microphone, stt, stt_integration, e2e"
                echo "Run 'python tests/run_tests.py --list' for detailed test descriptions"
                exit 1
                ;;
        esac
    fi
}

# Run the orchestrator
run() {
    check_venv

    # Ensure MPD is running
    if ! pgrep -x mpd > /dev/null; then
        log "Starting MPD..."
        mpd ~/.mpd/mpd.conf
        sleep 1
    fi

    log "Starting Pi-Sat orchestrator..."
    exec "$PY" modules/orchestrator.py
}

# Run the orchestrator in debug mode
run_debug() {
    check_venv

    # Ensure MPD is running
    if ! pgrep -x mpd > /dev/null; then
        log "Starting MPD..."
        mpd ~/.mpd/mpd.conf
        sleep 1
    fi

    log "Starting Pi-Sat orchestrator in debug mode..."
    exec "$PY" modules/orchestrator.py --debug
}

# Run the orchestrator in live debug mode
run_live() {
    check_venv
    log "Starting Pi-Sat orchestrator in LIVE DEBUG mode..."
    log "🔔 Wake word detection, 🎤 VAD recording, 📝 Text output"
    exec "$PY" -c "
from modules.factory import create_production_orchestrator

orchestrator = create_production_orchestrator(verbose=True, debug=True)
print('🎯 Pi-Sat LIVE DEBUG MODE')
print('🔔 Say \"Alexa\" to trigger wake word detection')
print('🎤 Speak your command after wake word')
print('📝 See real-time transcription and processing')
print('⏹️  Press Ctrl+C to stop')
print('=' * 50)
orchestrator.start()
"
}

# Synthetic test - full pipeline (wake word → record → STT → TTS)
test_synthetic() {
    check_venv
    log "Starting synthetic pipeline test..."
    log "🔔 Wake word → 🎤 Record → 🔊 STT → 💬 TTS"
    log "Say 'Alexa' to test full pipeline"
    log "Press Ctrl-C to exit"
    exec "$PY" scripts/test_synthetic.py "$@"
}

# Test microphone recording
test_mic() {
    check_venv
    log "Testing microphone recording with debug playback..."
    "$PY" tests/test_microphone_recording.py
}

# Test wake word + STT only (user feedback loop)
test_wake_stt() {
    check_venv
    log "Testing wake word → STT (user feedback loop)..."
    log "Say 'Alexa' then speak your command"
    log "Press Ctrl-C to exit"
    exec "$PY" scripts/test_wake_stt.py
}

# Test wake word → STT with debug audio saving
test_wake_stt_debug() {
    check_venv
    log "Testing wake word → STT (DEBUG MODE - saving audio files)..."
    log "Audio files will be saved to debug_audio/"
    log "Say 'Alexa' then speak your command"
    log "Press Ctrl-C to exit"
    exec "$PY" scripts/test_wake_stt.py --save-audio
}

# Test STT → Intent pipeline with French audio samples
test_stt_intent() {
    check_venv
    log "Testing STT → Intent pipeline with French audio samples..."
    exec "$PY" scripts/test_stt_intent.py "$@"
}

# Test STT → Intent pipeline (failures only)
test_stt_intent_failures() {
    check_venv
    log "Testing STT → Intent pipeline (failures only)..."
    exec "$PY" scripts/test_stt_intent.py --failures-only
}

# Calibrate VAD and analyze audio levels
calibrate_vad() {
    check_venv
    log "VAD Calibration Tool"
    log "Analyzes audio levels and recommends thresholds"
    exec "$PY" scripts/calibrate_vad.py
}

# Benchmark STT engines (Native vs Hailo)
benchmark_stt() {
    check_venv
    log "STT Performance Benchmark"
    log "Comparing Native Whisper vs Hailo acceleration"
    exec "$PY" scripts/benchmark_stt.py "$@"
}

# Clean up
clean() {
    log "Cleaning up..."
    rm -rf "$VENV_DIR"
    find . -type f -name "*.pyc" -delete
    find . -type d -name "__pycache__" -delete
    log "Cleanup complete!"
}

# Show help
help() {
    echo "Pi-Sat Voice Assistant Runner"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  install                    Install dependencies"
    echo "  activate                   Activate venv (source this script: 'source $0 activate')"
    echo "  test [test_name]          Run tests (all or specific)"
    echo "  run                       Start the orchestrator"
    echo "  run_debug                 Start the orchestrator in debug mode"
    echo "  run_live                  Start with LIVE DEBUG (wake word + VAD + text)"
    echo "  test_synthetic            Synthetic test: wake word → record → STT → TTS"
    echo "  test_wake_stt             Test wake word → STT only (user feedback loop)"
    echo "  test_wake_stt_debug       Test wake word → STT with audio file saving (DEBUG)"
    echo "  test_stt_intent           Test STT → Intent pipeline (100 French samples)"
    echo "  test_stt_intent_failures  Test STT → Intent (show failures only)"
    echo "  calibrate_vad             Calibrate VAD and analyze audio levels"
    echo "  benchmark_stt [--lang fr|en] [--audio-dir DIR]   Benchmark STT (default: Hailo+FR; use --quick for fast test)"
    echo "  listen                    Run wake word listener only (mic)"
    echo "  test_mic                  Test microphone recording with debug playback"
    echo "  logs_clear                Delete all *.log files in the repo"
    echo "  hailo_check               Run a quick Hailo diagnostic"
    echo "  download_voice            Download French Piper voice model"
    echo "  completion                Show how to enable bash completion"
    echo "  clean                     Clean up environment"
    echo "  help                      Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 install                Install everything"
    echo "  $0 test                   Run all tests"
    echo "  $0 test wake_word         Run specific test"
    echo "  $0 test stt               Run STT tests"
    echo "  $0 test microphone        Test microphone recording"
    echo "  $0 run                    Start voice assistant"
    echo "  $0 run_debug              Start with audio playback"
    echo "  $0 run_live               Start with LIVE DEBUG mode"
    echo "  $0 test_wake_stt          Test wake word + STT feedback loop"
    echo "  $0 test_mic               Test microphone recording"
}

# Main command dispatcher
case "${1:-help}" in
    "__complete")
        shift
        __complete "$@"
        ;;
    "install")
        install
        ;;
    "activate")
        activate
        ;;
    "test")
        test "$2"
        ;;
    "run")
        run
        ;;
    "run_debug")
        run_debug
        ;;
    "run_live")
        run_live
        ;;
    "test_synthetic")
        test_synthetic "$@"
        ;;
    "test_wake_stt")
        test_wake_stt
        ;;
    "test_wake_stt_debug")
        test_wake_stt_debug
        ;;
    "test_stt_intent")
        shift
        test_stt_intent "$@"
        ;;
    "test_stt_intent_failures")
        test_stt_intent_failures
        ;;
    "calibrate_vad")
        calibrate_vad
        ;;
    "benchmark_stt")
        shift
        benchmark_stt "$@"
        ;;
    "listen")
        listen
        ;;
    "test_mic")
        test_mic
        ;;
    "logs_clear")
        logs_clear
        ;;
    "hailo_check")
        hailo_check
        ;;
    "download_voice")
        download_voice
        ;;
    "completion")
        completion
        ;;
    "clean")
        clean
        ;;
    "help"|"--help"|"-h")
        help
        ;;
    *)
        error "Unknown command: $1"
        help
        exit 1
        ;;
esac 
