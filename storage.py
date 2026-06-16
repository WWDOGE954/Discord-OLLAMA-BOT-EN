"""Small JSON storage helpers for the MCP-like Discord bot demo."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def read_json(filename: str, default: Any) -> Any:
    path = DATA_DIR / filename
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        # Keep the bot alive even if a demo JSON file was edited incorrectly.
        return default


def write_json(filename: str, data: Any) -> None:
    path = DATA_DIR / filename
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)
