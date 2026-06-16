from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
import json
import os

from storage import DATA_DIR, read_json, write_json

USER_PROFILES_FILE = "user_profiles.json"
AI_INSIGHT_CACHE_FILE = "ai_insight_cache.json"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return utc_now().isoformat()


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def load_profiles() -> dict[str, Any]:
    return read_json(USER_PROFILES_FILE, {})


def save_profiles(data: dict[str, Any]) -> None:
    write_json(USER_PROFILES_FILE, data)


def default_profile(user_id: str, display_name: str = "") -> dict[str, Any]:
    return {
        "user_id": str(user_id),
        "display_name": display_name or str(user_id),
        "attention_score": 0,
        "notes": [],
        "ai_interaction_count": 0,
        "last_seen_at": "",
        "last_ai_at": "",
        "last_summary": "",
        "updated_at": now_iso(),
    }


def get_profile(user_id: str, display_name: str = "") -> dict[str, Any]:
    user_id = str(user_id)
    profiles = load_profiles()
    profile = profiles.get(user_id) or default_profile(user_id, display_name)
    if display_name:
        profile["display_name"] = display_name
    # shape migration
    base = default_profile(user_id, display_name)
    for key, value in base.items():
        profile.setdefault(key, value)
    profiles[user_id] = profile
    save_profiles(profiles)
    return profile


def update_profile(user_id: str, patch: dict[str, Any], display_name: str = "") -> dict[str, Any]:
    user_id = str(user_id)
    profiles = load_profiles()
    profile = profiles.get(user_id) or default_profile(user_id, display_name)
    if display_name:
        profile["display_name"] = display_name
    profile.update(patch)
    profile["updated_at"] = now_iso()
    profiles[user_id] = profile
    save_profiles(profiles)
    return profile


def set_attention(user_id: str, display_name: str, score: int, reason: str, moderator_id: str) -> dict[str, Any]:
    score = max(0, min(5, int(score)))
    profile = get_profile(user_id, display_name)
    notes = list(profile.get("notes") or [])
    if reason:
        notes.append(f"{now_iso()} | by {moderator_id} set attention level {score}:{reason}")
    notes = notes[-20:]
    return update_profile(user_id, {"attention_score": score, "notes": notes}, display_name)


def clear_attention(user_id: str, display_name: str, moderator_id: str, reason: str = "") -> dict[str, Any]:
    note = f"{now_iso()} | by {moderator_id} cleared attention level"
    if reason:
        note += f":{reason}"
    profile = get_profile(user_id, display_name)
    notes = list(profile.get("notes") or [])
    notes.append(note)
    return update_profile(user_id, {"attention_score": 0, "notes": notes[-20:]}, display_name)


def _event_log_path(dt: datetime | None = None) -> Path:
    dt = dt or utc_now()
    return DATA_DIR / f"ai_interactions_{dt.strftime('%Y-%m')}.jsonl"


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def record_ai_interaction(
    *,
    user_id: str,
    display_name: str,
    guild_id: str,
    channel_id: str,
    kind: str,
    prompt: str,
    reply: str,
) -> None:
    user_id = str(user_id)
    row = {
        "time": now_iso(),
        "user_id": user_id,
        "display_name": display_name,
        "guild_id": str(guild_id),
        "channel_id": str(channel_id),
        "kind": kind,
        "prompt": str(prompt or "")[:1500],
        "reply": str(reply or "")[:1500],
    }
    append_jsonl(_event_log_path(), row)

    profile = get_profile(user_id, display_name)
    update_profile(
        user_id,
        {
            "ai_interaction_count": int(profile.get("ai_interaction_count", 0)) + 1,
            "last_seen_at": row["time"],
            "last_ai_at": row["time"],
        },
        display_name,
    )


def _iter_recent_event_files(days: int) -> list[Path]:
    days = max(1, int(days))
    months: set[str] = set()
    today = utc_now()
    for offset in range(0, days + 35):
        dt = today - timedelta(days=offset)
        months.add(dt.strftime("%Y-%m"))
    return sorted(DATA_DIR.glob("ai_interactions_*.jsonl"), reverse=True)


def read_recent_ai_interactions(user_id: str, days: int = 7, max_events: int = 30) -> list[dict[str, Any]]:
    user_id = str(user_id)
    cutoff = utc_now() - timedelta(days=max(1, int(days)))
    events: list[dict[str, Any]] = []
    for path in _iter_recent_event_files(days):
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        row = json.loads(line)
                    except Exception:
                        continue
                    if str(row.get("user_id")) != user_id:
                        continue
                    dt = parse_time(row.get("time"))
                    if dt and dt >= cutoff:
                        events.append(row)
        except FileNotFoundError:
            continue
    events.sort(key=lambda x: str(x.get("time", "")), reverse=True)
    return events[:max_events]


def load_insight_cache() -> dict[str, Any]:
    return read_json(AI_INSIGHT_CACHE_FILE, {})


def save_insight_cache(data: dict[str, Any]) -> None:
    write_json(AI_INSIGHT_CACHE_FILE, data)


def cache_key(scope: str, guild_id: str, user_id: str, days: int, pro: bool = False) -> str:
    return f"{scope}:{guild_id}:{user_id}:days={int(days)}:pro={int(bool(pro))}"


def get_cached_insight(key: str) -> dict[str, Any] | None:
    return load_insight_cache().get(key)


def cache_is_fresh(cache: dict[str, Any] | None, cooldown_minutes: int) -> tuple[bool, int]:
    if not cache:
        return False, 0
    dt = parse_time(cache.get("generated_at"))
    if not dt:
        return False, 0
    next_time = dt + timedelta(minutes=max(1, int(cooldown_minutes)))
    remain = int((next_time - utc_now()).total_seconds() // 60)
    return utc_now() < next_time, max(0, remain)


def set_cached_insight(key: str, payload: dict[str, Any]) -> None:
    data = load_insight_cache()
    data[key] = payload
    # keep cache bounded
    if len(data) > 300:
        items = sorted(data.items(), key=lambda kv: str(kv[1].get("generated_at", "")), reverse=True)
        data = dict(items[:300])
    save_insight_cache(data)


def update_last_summary(user_id: str, display_name: str, summary: str) -> None:
    update_profile(user_id, {"last_summary": summary[:1200]}, display_name)


def format_attention(score: int | str | None) -> str:
    try:
        score_i = int(score or 0)
    except Exception:
        score_i = 0
    labels = {
        0: "0/5 Normal",
        1: "1/5 Light watch",
        2: "2/5 Needs attention",
        3: "3/5 High attention",
        4: "4/5 Strict watch",
        5: "5/5 Priority handling",
    }
    return labels.get(score_i, f"{score_i}/5")


def compact_events_for_prompt(events: list[dict[str, Any]], max_chars: int = 4000) -> str:
    lines: list[str] = []
    total = 0
    for row in events:
        time = str(row.get("time", ""))[:19]
        kind = row.get("kind", "event")
        prompt = str(row.get("prompt", "")).replace("\n", " ")[:260]
        reply = str(row.get("reply", "")).replace("\n", " ")[:180]
        line = f"- {time} [{kind}] user:{prompt} | Bot:{reply}"
        total += len(line)
        if total > max_chars:
            break
        lines.append(line)
    return "\n".join(lines) if lines else " (No recent AI interaction records)"


def compact_discord_messages_for_prompt(messages: list[dict[str, Any]], max_chars: int = 5000) -> str:
    lines: list[str] = []
    total = 0
    for row in messages:
        time = str(row.get("time", ""))[:19]
        channel = row.get("channel_name", row.get("channel_id", ""))
        content = str(row.get("content", "")).replace("\n", " ")[:320]
        if not content:
            continue
        line = f"- {time} #{channel}:{content}"
        total += len(line)
        if total > max_chars:
            break
        lines.append(line)
    return "\n".join(lines) if lines else " (No recent Discord messages captured)"


def build_profile_prompt(
    *,
    target_name: str,
    days: int,
    status_data: dict[str, Any],
    profile: dict[str, Any],
    ai_events: list[dict[str, Any]],
    discord_messages: list[dict[str, Any]],
    is_self: bool,
    pro: bool,
) -> str:
    recent_warnings = status_data.get("recent_warnings", [])
    pending_cases = status_data.get("pending_cases", [])
    notes = profile.get("notes", [])[-8:]

    scope = "user is viewing their own interaction summary" if is_self else "Admin is viewing a selected user interaction observation"
    if pro:
        scope += " (Pro:includes Discord history scan)"

    return f"""
You are a Discord server moderation assistant.summarize interaction insight based on the data; do not fabricate unsupported claims.
Use English. The tone may be friendly, but do not insult or label people. Avoid medical/personality diagnosis and political/religious/sensitive identity guesses.
If the user is viewing their own summary, use second person with reminders and encouragement. If an admin is viewing it, use a moderation-advice tone.

Query type:{scope}
target:{target_name}
Range: last {days} days

Basic status:
- Warnings:{status_data.get('warning_count', 0)}
- Anger:{status_data.get('anger', 0)}/{status_data.get('anger_limit', 0)}
- cases:{status_data.get('case_count', 0)}
- Pending cases:{len(pending_cases)}
- Attention level:{format_attention(profile.get('attention_score', 0))}
- AI interactions:{profile.get('ai_interaction_count', 0)}

Recent warnings:
{json.dumps(recent_warnings, ensure_ascii=False)[:2000]}

Pending cases:
{json.dumps(pending_cases, ensure_ascii=False)[:2000]}

Moderator notes:
{json.dumps(notes, ensure_ascii=False)[:1200]}

Recent AI interactions:
{compact_events_for_prompt(ai_events)}

Recent Discord message excerpts:
{compact_discord_messages_for_prompt(discord_messages)}

Please output:
1. Overall interaction insight (3-5 sentences)
2. Current status reminder
3. Suggested attention level (0～5)and reason
4. If self-query, provide a friendly reminder; if admin-query, provide moderation advice
""".strip()
