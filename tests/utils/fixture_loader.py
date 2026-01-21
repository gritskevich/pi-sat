import json
from pathlib import Path
from typing import Callable, Optional


def load_fixture(path: Path, validator: Optional[Callable[[dict], None]] = None) -> dict:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if validator:
        validator(data)
    return data
