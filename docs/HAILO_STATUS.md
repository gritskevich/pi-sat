# Hailo STT (Whisper) — Quick Status + Verification

Canonical implementation: `modules/hailo_stt.py` (singleton + retry + forced language).

## Verify Hardware

```bash
./pi-sat.sh hailo_check
hailortcli fw-control identify
```

## Verify Pi‑Sat STT

```bash
export PISAT_RUN_HAILO_TESTS=1
pytest tests/test_language_detection.py -v -s
pytest tests/test_e2e_french_true.py -v -s
```

## Common Failure Modes

- **HEF files missing**: `modules/hailo_stt.py` logs “model files not found”; fix your `hailo_examples/` install.
- **Language wrong**: set `HAILO_STT_LANGUAGE=fr` (default) or `en`; restart Pi‑Sat.
- **Tests hang after loading**: Hailo pipeline may keep background threads alive; prefer pytest timeouts for hardware suites.

## See Also

- Runtime logs: `./pi-sat.sh run_live`
- Audio sanity: `docs/AUDIO.md`
