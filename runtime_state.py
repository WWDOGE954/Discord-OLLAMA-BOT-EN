from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from storage import read_json, write_json

RUNTIME_FILE = "runtime_state.json"
VALID_MODES = {"normal", "eco", "emergency"}


@dataclass
class RuntimeState:
    mode: str = "normal"
    eco_temp: float = 80.0
    emergency_temp: float = 90.0
    shutdown_temp: float = 95.0
    auto_guard_enabled: bool = True
    high_temp_hits: int = 0
    shutdown_hits_required: int = 2
    reason: str = "Initial state"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_runtime_state() -> RuntimeState:
    data = read_json(RUNTIME_FILE, {})
    return RuntimeState(
        mode=str(data.get("mode", "normal")) if str(data.get("mode", "normal")) in VALID_MODES else "normal",
        eco_temp=float(data.get("eco_temp", 80.0)),
        emergency_temp=float(data.get("emergency_temp", 90.0)),
        shutdown_temp=float(data.get("shutdown_temp", 95.0)),
        auto_guard_enabled=bool(data.get("auto_guard_enabled", True)),
        high_temp_hits=int(data.get("high_temp_hits", 0)),
        shutdown_hits_required=int(data.get("shutdown_hits_required", 2)),
        reason=str(data.get("reason", "Initial state")),
    )


def save_runtime_state(state: RuntimeState) -> None:
    write_json(RUNTIME_FILE, state.to_dict())


def set_mode(state: RuntimeState, mode: str, reason: str = "") -> RuntimeState:
    mode = mode.strip().lower()
    if mode not in VALID_MODES:
        raise ValueError("mode must be normal / eco / emergency")
    state.mode = mode
    state.reason = reason or f"Manually switched to {mode}"
    if mode != "emergency":
        state.high_temp_hits = 0
    save_runtime_state(state)
    return state


def is_ai_enabled(state: RuntimeState) -> bool:
    return state.mode == "normal"


def is_doc_summary_enabled(state: RuntimeState) -> bool:
    return state.mode == "normal"


def is_full_report_enabled(state: RuntimeState) -> bool:
    # Full report reads more sensors; keep summary only in emergency mode.
    return state.mode in {"normal", "eco"}


def should_only_basic_moderation(state: RuntimeState) -> bool:
    return state.mode in {"eco", "emergency"}
