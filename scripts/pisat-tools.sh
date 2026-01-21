#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1090
source "$SCRIPT_DIR/pisat-common.sh"

logs_clear() {
    log "Clearing log files..."
    set +e
    find "$PROJECT_ROOT" -type f -name "*.log" -delete 2>/dev/null
    set -e
    log "Log files cleared."
}

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

test() {
    check_venv
    log "Running tests..."

    if [ -z "$1" ]; then
        "$PY" -m pytest tests/ -q
    else
        "$PY" -m pytest tests/ -q -k "$1"
    fi
}

test_mic() {
    check_venv
    log "Testing microphone recording with debug playback..."
    "$PY" tests/test_microphone_recording.py
}

test_wake() {
    check_venv
    log "Testing wake word detection (verbose)..."
    exec "$PY" test_wake_verbose.py
}

calibrate_vad() {
    check_venv
    log "VAD Calibration Tool"
    log "Analyzes audio levels and recommends thresholds"
    exec "$PY" scripts/calibrate_vad.py
}

clean() {
    log "Cleaning up..."
    rm -rf "$VENV_DIR"
    find "$PROJECT_ROOT" -type f -name "*.pyc" -delete
    find "$PROJECT_ROOT" -type d -name "__pycache__" -delete
    log "Cleanup complete!"
}

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

case "${1:-help}" in
    logs_clear)
        logs_clear
        ;;
    hailo_check)
        hailo_check
        ;;
    test)
        test "$2"
        ;;
    test_mic)
        test_mic
        ;;
    test_wake)
        test_wake
        ;;
    calibrate_vad)
        calibrate_vad
        ;;
    clean)
        clean
        ;;
    completion)
        completion
        ;;
    *)
        error "Unknown command: $1"
        exit 1
        ;;
esac
