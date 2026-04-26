# Pi-Sat Docs

Quick reference for common tasks.

## Setup & Running

- **INSTALL.md** (root) – Hardware setup + installation
- **DEPLOYMENT.md** (root) – Production deployment checklist
- **Justfile** (root) – Main entrypoint. `just` to list, `just run` / `just install` / `just say "<text>"` / `just test` / `just daemon …`
- **scripts/pisat-install.sh** – Heavy install logic (apt + pip + models), invoked by `just install`
- **install-daemon.sh** – Systemd unit installer, invoked by `just daemon`

## Development

- **CLAUDE.md** (root) – LLM quick reference (module map, principles)
- **tests/README.md** – Test suite (unit + hardware)
- **docs/TROUBLESHOOTING.md** – Common failures

## Technical Details

- **docs/PIPELINE.md** – Complete flow diagram + config reference (incl. USB buttons)
- **docs/AUDIO.md** – Audio routing, volume architecture
- **docs/EVENTS.md** – Event contract and payloads
- **docs/WAKE_WORD_DETECTION.md** – Wake word tuning
- **docs/PHONETIC_ALGORITHM_COMPARISON.md** – FONEM vs BeiderMorse benchmarks

## Need Help?

- Check TROUBLESHOOTING.md first
- GitHub Issues: https://github.com/gritskevich/pi-sat/issues
