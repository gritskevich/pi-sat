#!/bin/bash

# Pi-Sat Voice Assistant Runner
# KISS, DRY, Minimum elegant code

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1090
source "$PROJECT_ROOT/scripts/pisat-common.sh"

__pisat_list_commands() {
    cat <<'EOF_CMDS'
install
activate
daemon
test
run
run_debug
run_live
calibrate_vad
listen
test_mic
test_wake
logs_clear
hailo_check
download_voice
completion
clean
help
EOF_CMDS
}

__pisat_list_test_targets() {
    cat <<'EOF_TESTS'
wake_word
orchestrator
e2e
mpd
intent
music
tts
volume
EOF_TESTS
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

daemon() {
    if [ "$EUID" -ne 0 ]; then
        error "Daemon commands require sudo"
        echo "Usage: sudo $0 daemon [install|uninstall|status]"
        exit 1
    fi
    exec "$PROJECT_ROOT/install-daemon.sh" "$@"
}

activate() {
    if [ ! -d "$VENV_DIR" ]; then
        error "Virtual environment not found. Run: $0 install"
        return 1
    fi

    if [ "${BASH_SOURCE[0]}" != "$0" ]; then
        log "Activating virtual environment..."
        # shellcheck disable=SC1090
        source "$VENV_DIR/bin/activate"
    else
        warn "To activate in your current shell, run: source $0 activate"
        echo "Or run: source \"$VENV_DIR/bin/activate\""
    fi
}

help() {
    echo "Pi-Sat Voice Assistant Runner"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  install                    Install dependencies"
    echo "  activate                   Activate venv (source this script: 'source $0 activate')"
    echo "  daemon [install|uninstall|status]  Manage systemd daemon (requires sudo)"
    echo "  test [test_name]          Run tests (all or specific)"
    echo "  run                       Start the orchestrator"
    echo "  run_debug                 Start the orchestrator in debug mode"
    echo "  run_live                  Start with LIVE DEBUG (wake word + VAD + text)"
    echo "  calibrate_vad             Calibrate VAD and analyze audio levels"
    echo "  listen                    Run wake word listener only (mic)"
    echo "  test_mic                  Test microphone recording with debug playback"
    echo "  test_wake                 Test wake word detection (verbose)"
    echo "  logs_clear                Delete all *.log files in the repo"
    echo "  hailo_check               Run a quick Hailo diagnostic"
    echo "  download_voice            Download French Piper voice model"
    echo "  completion                Show how to enable bash completion"
    echo "  clean                     Clean up environment"
    echo "  help                      Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 install                Install everything"
    echo "  sudo $0 daemon install    Install as system service (auto-start on boot)"
    echo "  $0 test                   Run all tests"
    echo "  $0 test wake_word         Run specific test"
    echo "  $0 run                    Start voice assistant (interactive)"
    echo "  $0 run_debug              Start with audio playback"
    echo ""
    echo "Daemon Mode (Production):"
    echo "  sudo $0 daemon install           Install as system service"
    echo "  sudo systemctl status pi-sat     Check daemon status"
    echo "  sudo journalctl -u pi-sat -f     View live logs"
    echo "  See DEPLOYMENT.md for complete guide"
}

case "${1:-help}" in
    "__complete")
        shift
        __complete "$@"
        ;;
    "install")
        exec "$PROJECT_ROOT/scripts/pisat-install.sh" install
        ;;
    "download_voice")
        exec "$PROJECT_ROOT/scripts/pisat-install.sh" download_voice
        ;;
    "activate")
        activate
        ;;
    "daemon")
        shift
        daemon "$@"
        ;;
    "test")
        exec "$PROJECT_ROOT/scripts/pisat-tools.sh" test "$2"
        ;;
    "run")
        exec "$PROJECT_ROOT/scripts/pisat-run.sh" run
        ;;
    "run_debug")
        exec "$PROJECT_ROOT/scripts/pisat-run.sh" run_debug
        ;;
    "run_live")
        exec "$PROJECT_ROOT/scripts/pisat-run.sh" run_live
        ;;
    "calibrate_vad")
        exec "$PROJECT_ROOT/scripts/pisat-tools.sh" calibrate_vad
        ;;
    "listen")
        exec "$PROJECT_ROOT/scripts/pisat-run.sh" listen
        ;;
    "test_mic")
        exec "$PROJECT_ROOT/scripts/pisat-tools.sh" test_mic
        ;;
    "test_wake")
        exec "$PROJECT_ROOT/scripts/pisat-tools.sh" test_wake
        ;;
    "logs_clear")
        exec "$PROJECT_ROOT/scripts/pisat-tools.sh" logs_clear
        ;;
    "hailo_check")
        exec "$PROJECT_ROOT/scripts/pisat-tools.sh" hailo_check
        ;;
    "completion")
        exec "$PROJECT_ROOT/scripts/pisat-tools.sh" completion
        ;;
    "clean")
        exec "$PROJECT_ROOT/scripts/pisat-tools.sh" clean
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
