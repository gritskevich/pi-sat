# Package Structure (Why + How)

Pi‑Sat is a normal Python package (no `sys.path` hacks).

## Source of Truth

- Packaging: `setup.py`
- Install flow: `./pi-sat.sh install` (creates venv, installs deps, `pip install -e .`)

## Sanity

```bash
python -c "from modules.orchestrator import Orchestrator; print('OK')"
pytest tests/test_package_structure.py -q
```
