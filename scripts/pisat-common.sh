#!/bin/bash

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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

check_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        error "Virtual environment not found. Run: $PROJECT_ROOT/pi-sat.sh install"
        exit 1
    fi
}
