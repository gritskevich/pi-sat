#!/usr/bin/env bash
# Bash completion for pi-sat.sh
# Source this file or add to ~/.bashrc

_pisat_root() {
    if [ -n "${PROJECT_ROOT:-}" ] && [ -d "${PROJECT_ROOT:-}" ]; then
        printf '%s\n' "$PROJECT_ROOT"
        return 0
    fi

    local src="${BASH_SOURCE[0]}"
    while [ -h "$src" ]; do
        local dir
        dir="$(cd -P "$(dirname "$src")" && pwd)"
        src="$(readlink "$src")"
        [[ "$src" != /* ]] && src="$dir/$src"
    done
    printf '%s\n' "$(cd -P "$(dirname "$src")" && pwd)"
}

_pisat_cmdlist() {
    local root
    root="$(_pisat_root)"

    if [ -x "$root/pi-sat.sh" ]; then
        "$root/pi-sat.sh" __complete commands 2>/dev/null && return 0
    fi

    printf '%s\n' \
        install activate test run run_debug run_live test_synthetic test_wake_stt \
        test_wake_stt_debug calibrate_vad benchmark_stt listen test_mic logs_clear \
        hailo_check download_voice completion clean help
}

_pisat_test_targets() {
    local root
    root="$(_pisat_root)"

    if [ -x "$root/pi-sat.sh" ]; then
        "$root/pi-sat.sh" __complete test_targets 2>/dev/null && return 0
    fi

    printf '%s\n' wake_word listener orchestrator integration microphone stt stt_integration e2e
}

_pisat_completions() {
    local cur prev cmd
    cur="${COMP_WORDS[COMP_CWORD]:-}"
    prev="${COMP_WORDS[COMP_CWORD-1]:-}"
    cmd="${COMP_WORDS[1]:-}"

    if [ "$COMP_CWORD" -le 1 ]; then
        COMPREPLY=($(compgen -W "$(_pisat_cmdlist)" -- "$cur"))
        return 0
    fi

    case "$cmd" in
        test)
            if [ "$COMP_CWORD" -eq 2 ]; then
                COMPREPLY=($(compgen -W "$(_pisat_test_targets)" -- "$cur"))
                return 0
            fi
            ;;
        benchmark_stt)
            COMPREPLY=($(compgen -W "--quick" -- "$cur"))
            return 0
            ;;
    esac

    COMPREPLY=()
}

# Register completion for both ./pi-sat.sh and pi-sat.sh
complete -F _pisat_completions ./pi-sat.sh
complete -F _pisat_completions pi-sat.sh
