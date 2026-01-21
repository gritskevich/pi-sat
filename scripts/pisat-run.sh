#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1090
source "$SCRIPT_DIR/pisat-common.sh"

ensure_mpd() {
    if [ -z "${XDG_RUNTIME_DIR:-}" ]; then
        export XDG_RUNTIME_DIR="/run/user/$(id -u)"
    fi
    if [ -z "${PULSE_SERVER:-}" ]; then
        export PULSE_SERVER="unix:${XDG_RUNTIME_DIR}/pulse/native"
    fi
    if ! pgrep -x mpd > /dev/null; then
        log "Starting MPD..."
        mpd ~/.mpd/mpd.conf
        sleep 1
    fi
}

run() {
    check_venv
    ensure_mpd

    log "Starting Pi-Sat orchestrator..."
    exec "$PY" modules/orchestrator.py
}

run_debug() {
    check_venv
    ensure_mpd

    log "Starting Pi-Sat orchestrator in debug mode..."
    exec "$PY" modules/orchestrator.py --debug
}

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

listen() {
    check_venv
    log "Starting wake word listener (mic)..."
    exec "$PY" modules/wake_word_listener.py
}

case "${1:-help}" in
    run)
        run
        ;;
    run_debug)
        run_debug
        ;;
    run_live)
        run_live
        ;;
    listen)
        listen
        ;;
    *)
        error "Unknown command: $1"
        exit 1
        ;;
esac
