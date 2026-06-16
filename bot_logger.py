from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_GROUPS = {"bot", "server", "commands", "music", "errors", "system"}

for group in LOG_GROUPS:
    (LOG_DIR / group).mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(group: str) -> Path:
    group = group if group in LOG_GROUPS else "bot"
    date = datetime.now().strftime("%Y-%m-%d")
    return LOG_DIR / group / f"{group}_{date}.jsonl"


def _truncate(value: Any, limit: int = 300) -> Any:
    if isinstance(value, str):
        return value[:limit]
    if isinstance(value, list):
        return [_truncate(v, limit) for v in value[:25]]
    if isinstance(value, dict):
        return {str(k)[:80]: _truncate(v, limit) for k, v in list(value.items())[:60]}
    return value


def _safe(value: Any) -> Any:
    value = _truncate(value)
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except Exception:
        return str(value)


def log_event(group: str, event: str, data: dict[str, Any] | None = None) -> None:
    row = {"time": _now(), "event": str(event), "data": _safe(data or {})}
    try:
        path = _path(group)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        # Logger should never crash the bot.
        pass


def log_command(*, name: str, user_id: str, display_name: str, guild_id: str, channel_id: str, options: Any = None) -> None:
    log_event("commands", "slash_command", {
        "name": name,
        "user_id": user_id,
        "display_name": display_name,
        "guild_id": guild_id,
        "channel_id": channel_id,
        "options": options or [],
    })


def log_error(event: str, error: BaseException, data: dict[str, Any] | None = None) -> None:
    payload = dict(data or {})
    payload.update({
        "error_type": type(error).__name__,
        "error": str(error),
        "traceback": traceback.format_exc(),
    })
    log_event("errors", event, payload)
