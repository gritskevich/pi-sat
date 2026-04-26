# Pi-Sat — single entrypoint. KISS, DRY, minimal.
#
#   just                    # list recipes
#   just say "bonjour Nina"
#   just run                # start the orchestrator (daemon-equivalent)
#   just run-debug          # start with RMS + confidence stream
#   just test               # pytest -q
#   just install            # provision venv, deps, models
#
# Heavy install/daemon logic lives in scripts/pisat-install.sh and
# install-daemon.sh — those stay as shell scripts (200+ lines of bash
# each); recipes only dispatch into them.

set shell := ["bash", "-eu", "-o", "pipefail", "-c"]
set positional-arguments

root := justfile_directory()
py   := root / "venv/bin/python"

# ──────────────────────────────────────────────────────────────────────
# default
# ──────────────────────────────────────────────────────────────────────

# List recipes
default:
    @just --list --unsorted

# ──────────────────────────────────────────────────────────────────────
# install / setup
# ──────────────────────────────────────────────────────────────────────

# Install venv + Python deps + models (auto-detects 3.11/3.13)
install:
    @{{root}}/scripts/pisat-install.sh install

# Download French Piper voice model
download-voice:
    @{{root}}/scripts/pisat-install.sh download_voice

# Manage systemd daemon: just daemon install|uninstall|status [--user]
daemon *args:
    @{{root}}/install-daemon.sh "$@"

# ──────────────────────────────────────────────────────────────────────
# run
# ──────────────────────────────────────────────────────────────────────

# Start the orchestrator (production)
run: _mpd _venv
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{root}}"
    echo "[Pi-Sat] Starting orchestrator..."
    exec {{py}} modules/orchestrator.py

# Start the orchestrator with RMS + confidence debug stream
run-debug: _mpd _venv
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{root}}"
    echo "[Pi-Sat] Starting orchestrator (debug)..."
    exec {{py}} modules/orchestrator.py --debug

# Start with verbose live trace (wake + VAD + transcription)
run-live: _venv
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{root}}"
    echo "[Pi-Sat] LIVE DEBUG — say 'Coucou Eris' then your command (Ctrl+C to stop)"
    exec {{py}} - <<'PY'
    from modules.factory import create_production_orchestrator
    o = create_production_orchestrator(verbose=True, debug=True)
    o.start()
    PY

# Wake-word listener only (mic loop, no orchestrator)
listen: _venv
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{root}}"
    exec {{py}} modules/wake_word_listener.py

# ──────────────────────────────────────────────────────────────────────
# tests
# ──────────────────────────────────────────────────────────────────────

# pytest -q [filter]   e.g. just test wake_word
test filter="": _venv
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{root}}"
    if [[ -z "{{filter}}" ]]; then
        exec {{py}} -m pytest tests/ -q
    else
        exec {{py}} -m pytest tests/ -q -k "{{filter}}"
    fi

# Microphone recording test (with debug playback)
test-mic: _venv
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{root}}"
    exec {{py}} tests/test_microphone_recording.py

# Wake-word verbose test (60s, diagnostics)
test-wake: _venv
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{root}}"
    exec {{py}} test_wake_verbose.py

# ──────────────────────────────────────────────────────────────────────
# tools
# ──────────────────────────────────────────────────────────────────────

# Speak <text> in French (Piper, fr_FR-siwis-medium)
say *text: _venv
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{root}}"
    exec {{py}} scripts/speak.py "$@"

# VAD calibration: recommend thresholds from current ambient
calibrate-vad: _venv
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{root}}"
    exec {{py}} scripts/calibrate_vad.py

# Hailo diagnostic — driver, imports, HEFs, pipeline init
hailo-check: _venv
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{root}}"
    {{py}} - <<'PY'
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
    for arch in ("hailo8l", "hailo8"):
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
        HailoWhisperPipeline(enc, dec, variant=variant, multi_process_service=False)
        print("Pipeline init: OK")
    except Exception as e:
        print("Pipeline init: FAIL:", type(e).__name__, e)
        raise SystemExit(3)
    PY

# Set USB mic input volumes to 30% (run after boot or replug)
fix-mic-volume:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Setting microphone input volumes to 30%..."
    pactl set-source-volume \
        alsa_input.usb-MUSIC-BOOST_USB_Microphone_MB-306-00.mono-fallback 30% 2>/dev/null \
        && echo "✓ USB Microphone → 30%" \
        || echo "✗ USB Microphone not found"
    pactl set-source-volume \
        alsa_input.usb-Jieli_Technology_USB_Composite_Device_4250323230333208-01.mono-fallback 30% 2>/dev/null \
        && echo "✓ USB Composite Device → 30%" \
        || echo "✗ USB Composite Device not found"
    echo
    echo "Current volumes:"
    pactl list sources | grep -A 3 "Description.*USB" | grep -E "Description:|Volume:" || true

# Load PipeWire echo-cancel module on default source (sets pi_sat_ns)
enable-noise-suppression:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! command -v pactl >/dev/null 2>&1; then
        echo "pactl not found. Install PipeWire/PulseAudio tools first." >&2
        exit 1
    fi
    DEFAULT_SOURCE="$(pactl get-default-source 2>/dev/null || true)"
    if [[ -z "$DEFAULT_SOURCE" ]]; then
        DEFAULT_SOURCE="$(pactl info | awk -F': ' '/Default Source/ {print $2; exit}')"
    fi
    if [[ -z "$DEFAULT_SOURCE" ]]; then
        echo "Could not determine default source." >&2
        exit 1
    fi
    for id in $(pactl list short modules | awk '$2=="module-echo-cancel" {print $1}'); do
        pactl unload-module "$id" || true
    done
    MODULE_ID="$(pactl load-module module-echo-cancel \
        aec_method=webrtc \
        source_master="$DEFAULT_SOURCE" \
        source_name="pi_sat_ns" \
        sink_name="pi_sat_ns_out" \
        source_properties=device.description=PiSat-NS \
        sink_properties=device.description=PiSat-NS-OUT)"
    echo "Loaded noise suppression module: $MODULE_ID"
    echo "New source: pi_sat_ns (description: PiSat-NS)"
    echo "Set INPUT_DEVICE_NAME=PiSat-NS before running Pi-Sat."

# ──────────────────────────────────────────────────────────────────────
# housekeeping
# ──────────────────────────────────────────────────────────────────────

# Delete every *.log under the repo
logs-clear:
    @echo "Clearing log files..."
    @find {{root}} -type f -name "*.log" -delete 2>/dev/null || true
    @echo "Log files cleared."

# Wipe venv + bytecode caches
clean:
    @echo "Cleaning up..."
    @rm -rf {{root}}/venv
    @find {{root}} -type f -name "*.pyc" -delete
    @find {{root}} -type d -name "__pycache__" -delete
    @echo "Cleanup complete."

# ──────────────────────────────────────────────────────────────────────
# private helpers (prefix `_` keeps them out of `just --list`)
# ──────────────────────────────────────────────────────────────────────

_venv:
    @[[ -x "{{py}}" ]] || { echo "venv missing — run: just install" >&2; exit 1; }

_mpd:
    #!/usr/bin/env bash
    set -euo pipefail
    : "${XDG_RUNTIME_DIR:=/run/user/$(id -u)}"
    : "${PULSE_SERVER:=unix:${XDG_RUNTIME_DIR}/pulse/native}"
    export XDG_RUNTIME_DIR PULSE_SERVER
    if ! pgrep -x mpd >/dev/null; then
        echo "[Pi-Sat] Starting MPD..."
        mpd ~/.mpd/mpd.conf
        sleep 1
    fi
