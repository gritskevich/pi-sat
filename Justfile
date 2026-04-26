# Pi-Sat — minimalist task runner. Thin alias layer over pi-sat.sh / scripts.
# Default voice: French (fr_FR-siwis-medium) via Piper TTS.
#
# Usage:
#   just                 # list recipes
#   just say "bonjour Nina"

set shell := ["bash", "-c"]

py := justfile_directory() / "venv/bin/python"

# List recipes
default:
    @just --list --unsorted

# Say <text> aloud with the configured French Piper voice
say *text:
    @{{py}} {{justfile_directory()}}/scripts/speak.py {{text}}
