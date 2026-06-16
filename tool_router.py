"""MCP-like tool layer for Discord moderation + rule management demo.

This layer intentionally does not call the Discord API directly.
The Discord bot receives an event, calls a tool here, and then decides
how to display/report/execute the result.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
import os
import re
import unicodedata
from typing import Any

from storage import read_json, write_json

ANGER_FILE = "anger_memory.json"
WARNINGS_FILE = "warnings.json"
ACTION_LOG_FILE = "action_log.json"
MODERATION_CASES_FILE = "moderation_cases.json"
RECENT_EVENTS_FILE = "recent_events.json"
MODERATION_RULES_FILE = "moderation_rules.json"

ANGER_LIMIT = int(os.getenv("ANGER_LIMIT", "3"))
AUTO_TIMEOUT_COUNT = int(os.getenv("AUTO_TIMEOUT_COUNT", "3"))
AUTO_TIMEOUT_WINDOW_SECONDS = int(os.getenv("AUTO_TIMEOUT_WINDOW_SECONDS", "60"))
CASE_DEDUPE_SECONDS = int(os.getenv("CASE_DEDUPE_SECONDS", "60"))

RULE_CATEGORIES = {
    "blocked_terms",
    "english_abuse_terms",
    "sexual_terms",
    "spam_terms",
    "safe_phrases",
}

DEFAULT_RULES: dict[str, Any] = {
    "blocked_terms": [],
    "english_abuse_terms": [
        "idiot",
        "stupid",
        "shut up",
        "loser",
        "trash",
        "noob",
        "dumb",
    ],
    "sexual_terms": [],
    "spam_terms": [
        "free nitro",
        "click this link",
        "download cheat",
        "guaranteed profit",
    ],
    "target_patterns": [
        "You",
        "u",
        "ur",
        "Your",
        "You are",
        "You're",
    ],
    "safe_phrases": [
        "code example",
        "rule explanation",
        "feature test",
        "moderation test",
    ],
    "notes": [
        "blocked_terms / english_abuse_terms / sexual_terms / spam_terms can be managed with /banword_add.",
        "English detection uses Unicode NFKC normalization and casefolding, so matching is case-insensitive.",
        "safe_phrases are checked first and are useful for false-positive exceptions.",
        "If abuse terms are detected with @user, You/u, or similar target clues, the case may be marked as targeted_attack.",
    ],
}


@dataclass
class ToolResult:
    ok: bool
    tool: str
    message: str
    data: dict[str, Any]
    requires_admin_confirm: bool = False
    dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return datetime.now(timezone.utc)


def _clean_term(term: str) -> str:
    return str(term).strip()


# Common Chinese variant normalization.
# Only low-risk clearly equivalent characters are listed to avoid false positives.
_CHINESE_VARIANTS = str.maketrans({
    "You": "You",
    "You": "You",
    "You": "You",
    "mom": "mom",
    "mom": "mom",
    "mother": "mother",
})


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(text or "")).casefold()
    normalized = normalized.translate(_CHINESE_VARIANTS)
    # Remove spaces and zero-width characters to avoid bypasses such as"y o u"split-character bypass.
    normalized = re.sub(r"[\s\u200b\u200c\u200d\ufeff]+", "", normalized)
    return normalized


def _contains_term(content_norm: str, term: str) -> bool:
    cleaned = _normalize_text(_clean_term(term))
    if not cleaned:
        return False
    return cleaned in content_norm


def _target_pattern_hit(content_norm: str, target_patterns: list[str]) -> list[str]:
    hits: list[str] = []
    for pattern in target_patterns:
        cleaned = _normalize_text(_clean_term(pattern))
        if not cleaned:
            continue
        # English short words use word boundaries to reduce false positives.
        if re.fullmatch(r"[a-z0-9']+", cleaned):
            if re.search(rf"\b{re.escape(cleaned)}\b", content_norm):
                hits.append(pattern)
        elif cleaned in content_norm:
            hits.append(pattern)
    return hits


class ToolRouter:
    """A simple MCP-like router: named tools + JSON persistence."""

    def __init__(self) -> None:
        self.anger: dict[str, int] = read_json(ANGER_FILE, {})
        self.warnings: dict[str, list[dict[str, Any]]] = read_json(WARNINGS_FILE, {})
        self.action_log: list[dict[str, Any]] = read_json(ACTION_LOG_FILE, [])
        self.cases: list[dict[str, Any]] = read_json(MODERATION_CASES_FILE, [])
        self.recent_events: dict[str, list[dict[str, Any]]] = read_json(RECENT_EVENTS_FILE, {})
        self.rules: dict[str, Any] = read_json(MODERATION_RULES_FILE, DEFAULT_RULES)
        self._ensure_rules_shape()
        self.save_rules()

    def _ensure_rules_shape(self) -> None:
        for key, value in DEFAULT_RULES.items():
            if key not in self.rules:
                self.rules[key] = value
            elif isinstance(value, list) and not isinstance(self.rules.get(key), list):
                self.rules[key] = value

    def save_all(self) -> None:
        write_json(ANGER_FILE, self.anger)
        write_json(WARNINGS_FILE, self.warnings)
        write_json(ACTION_LOG_FILE, self.action_log[-300:])
        write_json(MODERATION_CASES_FILE, self.cases[-500:])
        write_json(RECENT_EVENTS_FILE, self.recent_events)
        self.save_rules()

    def save_rules(self) -> None:
        write_json(MODERATION_RULES_FILE, self.rules)

    def list_tools(self) -> ToolResult:
        tools = [
            "server_status",
            "get_user_status",
            "add_warning",
            "reset_user_state",
            "reset_all_state",
            "suggest_moderation_action",
            "record_action",
            "evaluate_message",
            "safe_add",
            "safe_remove",
            "safe_list",
            "rule_add",
            "rule_remove",
            "rule_list",
            "case_ignore",
            "case_resolve",
            "case_set_thread",
            "case_get",
            "case_list",
            "case_clear",
            "case_clear_test",
        ]
        return ToolResult(True, "list_tools", "Available tools listed.", {"tools": tools})

    def server_status(self, guild_name: str, member_count: int | None, bot_name: str) -> ToolResult:
        pending_cases = len([c for c in self.cases if c.get("status") == "pending"])
        return ToolResult(
            True,
            "server_status",
            "Discord moderation bot is running.",
            {
                "guild_name": guild_name,
                "member_count": member_count,
                "bot_name": bot_name,
                "tracked_users": len(set(self.anger) | set(self.warnings)),
                "logged_actions": len(self.action_log),
                "pending_cases": pending_cases,
                "safe_phrases": len(self.rules.get("safe_phrases", [])),
                "rule_terms": sum(len(self.rules.get(k, [])) for k in RULE_CATEGORIES if isinstance(self.rules.get(k), list)),
            },
        )

    def get_user_status(self, user_id: str, display_name: str = "") -> ToolResult:
        user_id = str(user_id)
        warnings = self.warnings.get(user_id, [])
        anger = int(self.anger.get(user_id, 0))
        user_cases = [c for c in self.cases if str(c.get("user_id")) == user_id]
        return ToolResult(
            True,
            "get_user_status",
            f"{display_name or user_id} status has been loaded.",
            {
                "user_id": user_id,
                "display_name": display_name,
                "anger": anger,
                "anger_limit": ANGER_LIMIT,
                "warning_count": len(warnings),
                "recent_warnings": warnings[-5:],
                "case_count": len(user_cases),
                "pending_cases": [c for c in user_cases[-10:] if c.get("status") == "pending"],
            },
        )

    def add_warning(self, user_id: str, display_name: str, moderator_id: str, reason: str) -> ToolResult:
        user_id = str(user_id)
        warning = {
            "time": _now(),
            "user_id": user_id,
            "display_name": display_name,
            "moderator_id": str(moderator_id),
            "reason": reason.strip() or "No reason provided",
        }
        self.warnings.setdefault(user_id, []).append(warning)
        self.anger[user_id] = min(int(self.anger.get(user_id, 0)) + 1, ANGER_LIMIT)
        self.record_action("warn_user", moderator_id, user_id, reason, dry_run=False, save=False)
        self.save_all()
        return ToolResult(
            True,
            "add_warning",
            f"Recorded {display_name} warning.",
            {
                "warning": warning,
                "anger": self.anger[user_id],
                "warning_count": len(self.warnings[user_id]),
            },
        )

    def reset_user_state(self, user_id: str, display_name: str = "") -> ToolResult:
        user_id = str(user_id)
        self.anger[user_id] = 0
        self.warnings[user_id] = []
        self.recent_events[user_id] = []
        self.save_all()
        return ToolResult(True, "reset_user_state", f"Reset {display_name or user_id} state.", {"user_id": user_id})

    def reset_all_state(self) -> ToolResult:
        self.anger.clear()
        self.warnings.clear()
        self.recent_events.clear()
        self.save_all()
        return ToolResult(True, "reset_all_state", "Reset all user states.", {})

    def suggest_moderation_action(self, user_id: str, display_name: str, reason: str) -> ToolResult:
        status = self.get_user_status(user_id, display_name).data
        anger = status["anger"]
        warning_count = status["warning_count"]

        if warning_count >= 2 or anger >= ANGER_LIMIT:
            action = "timeout_user"
            minutes = 5
            explanation = "Multiple records exist. A short timeout is suggested but still requires admin confirmation."
        elif warning_count == 1 or anger == ANGER_LIMIT - 1:
            action = "warn_user"
            minutes = 0
            explanation = "One record exists. Suggest warning again and observing."
        else:
            action = "soft_reminder"
            minutes = 0
            explanation = "Current record is low. Suggest reminder first, no direct punishment."

        return ToolResult(
            True,
            "suggest_moderation_action",
            explanation,
            {
                "target_user_id": str(user_id),
                "display_name": display_name,
                "reason": reason,
                "suggested_action": action,
                "suggested_timeout_minutes": minutes,
                "current_status": status,
            },
            requires_admin_confirm=action == "timeout_user",
            dry_run=True,
        )

    def record_action(
        self,
        action: str,
        moderator_id: str,
        target_user_id: str,
        reason: str,
        dry_run: bool = True,
        save: bool = True,
    ) -> ToolResult:
        row = {
            "time": _now(),
            "action": action,
            "moderator_id": str(moderator_id),
            "target_user_id": str(target_user_id),
            "reason": reason.strip() or "No reason provided",
            "dry_run": dry_run,
        }
        self.action_log.append(row)
        if save:
            self.save_all()
        return ToolResult(True, "record_action", "Action log saved.", row, dry_run=dry_run)

    def _find_rule_matches(self, content: str, mentioned_user_count: int = 0) -> dict[str, Any]:
        original = content or ""
        norm = _normalize_text(original)

        safe_matches = [p for p in self.rules.get("safe_phrases", []) if _contains_term(norm, p)]
        if safe_matches:
            return {"violation": False, "safe": True, "safe_matches": safe_matches, "matches": []}

        matches: list[dict[str, str]] = []
        for category in ["blocked_terms", "english_abuse_terms", "sexual_terms", "spam_terms"]:
            for term in self.rules.get(category, []):
                cleaned = _clean_term(term)
                if _contains_term(norm, cleaned):
                    matches.append({"category": category, "term": cleaned})

        target_hits = _target_pattern_hit(norm, list(self.rules.get("target_patterns", [])))
        targeted_attack = mentioned_user_count > 0 or bool(target_hits)
        abuse_hit = any(m["category"] in {"english_abuse_terms", "blocked_terms"} for m in matches)

        return {
            "violation": bool(matches),
            "safe": False,
            "safe_matches": [],
            "matches": matches,
            "target_hits": target_hits,
            "targeted_attack": bool(abuse_hit and targeted_attack),
        }

    def evaluate_message(
        self,
        *,
        user_id: str,
        display_name: str,
        content: str,
        channel_id: str = "",
        message_id: str = "",
        message_url: str = "",
        guild_id: str = "",
        is_admin: bool = False,
        apply_penalty: bool = True,
        mentioned_user_count: int = 0,
        mentioned_user_ids: list[str] | None = None,
    ) -> ToolResult:
        """Evaluate a message and optionally record warning/anger.

        Duplicate handling:
        - If the same user posts the same normalized content or matching rule set in
          the same guild/channel within CASE_DEDUPE_SECONDS, the event is merged into
          the existing pending case instead of creating a new Forum post.
        - The repeated event still updates recent_events, so timeout logic still works.
        """
        rule_result = self._find_rule_matches(content, mentioned_user_count=mentioned_user_count)
        if not rule_result["violation"]:
            if rule_result["safe"]:
                return ToolResult(False, "evaluate_message", "message matched a safe phrase and was skipped.", {"safe_matches": rule_result["safe_matches"]})
            return ToolResult(False, "evaluate_message", "No violation detected.", {})

        user_id = str(user_id)
        now = _now()
        matches = rule_result["matches"]
        targeted_attack = bool(rule_result.get("targeted_attack"))
        content_signature = _normalize_text(content)[:500]
        match_signature = ",".join(sorted(f"{m.get('category')}:{_normalize_text(m.get('term', ''))}" for m in matches))

        duplicate_case: dict[str, Any] | None = None
        if CASE_DEDUPE_SECONDS > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=CASE_DEDUPE_SECONDS)
            for old in reversed(self.cases):
                try:
                    if str(old.get("status", "pending")) != "pending":
                        continue
                    if str(old.get("user_id")) != user_id:
                        continue
                    if str(old.get("guild_id", "")) != str(guild_id):
                        continue
                    if str(old.get("channel_id", "")) != str(channel_id):
                        continue
                    if _parse_time(str(old.get("last_duplicate_at") or old.get("time") or "")) < cutoff:
                        continue
                    same_content = str(old.get("content_signature", "")) == content_signature
                    same_matches = str(old.get("match_signature", "")) == match_signature
                    if same_content or same_matches:
                        duplicate_case = old
                        break
                except Exception:
                    continue

        case_id = str(duplicate_case.get("case_id")) if duplicate_case else f"C{len(self.cases) + 1:04d}"

        high_category = any(m["category"] in {"sexual_terms", "spam_terms"} for m in matches)
        blocked_hit = any(m["category"] == "blocked_terms" for m in matches)
        penalty_applied = bool(apply_penalty and not is_admin and (targeted_attack or high_category or blocked_hit))

        recent_count = 0
        should_auto_timeout = False
        final_warning = False
        if penalty_applied:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=AUTO_TIMEOUT_WINDOW_SECONDS)
            recent = [item for item in self.recent_events.get(user_id, []) if _parse_time(str(item.get("time", ""))) >= cutoff]
            recent.append({"time": now, "case_id": case_id, "matches": matches, "deduplicated": bool(duplicate_case)})
            self.recent_events[user_id] = recent[-20:]
            recent_count = len(recent)
            should_auto_timeout = recent_count >= AUTO_TIMEOUT_COUNT
            final_warning = recent_count >= max(1, AUTO_TIMEOUT_COUNT - 1) and not should_auto_timeout

            self.anger[user_id] = min(int(self.anger.get(user_id, 0)) + 1, ANGER_LIMIT)
            self.warnings.setdefault(user_id, []).append({
                "time": now,
                "user_id": user_id,
                "display_name": display_name,
                "moderator_id": "AUTO_DETECT",
                "reason": f"Auto detection:{', '.join(m['term'] for m in matches)}",
                "case_id": case_id,
                "targeted_attack": targeted_attack,
                "deduplicated": bool(duplicate_case),
            })

        if duplicate_case is not None:
            case = duplicate_case
            case["duplicate_count"] = int(case.get("duplicate_count", 0)) + 1
            case["last_duplicate_at"] = now
            case["last_message_id"] = str(message_id)
            case["last_message_url"] = message_url
            ids = list(case.get("duplicate_message_ids") or [])
            if message_id:
                ids.append(str(message_id))
            case["duplicate_message_ids"] = ids[-30:]
            case["recent_count"] = recent_count
            case["auto_timeout_count"] = AUTO_TIMEOUT_COUNT
            case["window_seconds"] = AUTO_TIMEOUT_WINDOW_SECONDS
            case["should_auto_timeout"] = should_auto_timeout
            case["final_warning"] = final_warning
            case["penalty_applied"] = penalty_applied
            case["deduplicated"] = True
            case["current_message_id"] = str(message_id)
            case["current_message_url"] = message_url
            case["current_content"] = content[:1500]
        else:
            case = {
                "case_id": case_id,
                "time": now,
                "status": "pending",
                "user_id": user_id,
                "display_name": display_name,
                "guild_id": str(guild_id),
                "channel_id": str(channel_id),
                "message_id": str(message_id),
                "message_url": message_url,
                "content": content[:1500],
                "content_signature": content_signature,
                "match_signature": match_signature,
                "matches": matches,
                "targeted_attack": targeted_attack,
                "target_hits": rule_result.get("target_hits", []),
                "mentioned_user_count": mentioned_user_count,
                "mentioned_user_ids": mentioned_user_ids or [],
                "is_admin": is_admin,
                "apply_penalty": apply_penalty,
                "penalty_applied": penalty_applied,
                "recent_count": recent_count,
                "auto_timeout_count": AUTO_TIMEOUT_COUNT,
                "window_seconds": AUTO_TIMEOUT_WINDOW_SECONDS,
                "should_auto_timeout": should_auto_timeout,
                "final_warning": final_warning,
                "deduplicated": False,
                "duplicate_count": 0,
                "last_duplicate_at": now,
                "thread_id": "",
                "thread_url": "",
            }
            self.cases.append(case)

        self.record_action(
            "auto_detect_duplicate" if duplicate_case is not None else "auto_detect_violation",
            "BOT",
            user_id,
            f"case={case_id}; matches={matches}; targeted={targeted_attack}; penalty={penalty_applied}; duplicate={bool(duplicate_case)}",
            dry_run=not penalty_applied,
            save=False,
        )
        self.save_all()

        if is_admin:
            message = "Admin message matched rules: report only, no automatic penalty."
        elif should_auto_timeout:
            message = "Rules triggered repeatedly in a short period. Short timeout or admin review suggested."
        elif final_warning:
            message = "Rules triggered again within a short period; final warning stage reached."
        elif duplicate_case is not None:
            message = f"Duplicate violation detected and merged into existing case {case_id}."
        elif not penalty_applied:
            message = "Potential inappropriate content detected, but no clear target: create case and report only."
        else:
            message = "Potential rule violation detected; pending case created."

        return ToolResult(
            True,
            "evaluate_message",
            message,
            dict(case),
            requires_admin_confirm=should_auto_timeout or not penalty_applied,
            dry_run=not penalty_applied,
        )

    def safe_add(self, phrase: str, moderator_id: str, reason: str = "") -> ToolResult:
        phrase = _clean_term(phrase)
        if not phrase:
            return ToolResult(False, "safe_add", "Safe phrase cannot be empty.", {})
        safe_phrases = self.rules.setdefault("safe_phrases", [])
        exists = {_normalize_text(x) for x in safe_phrases}
        if _normalize_text(phrase) not in exists:
            safe_phrases.append(phrase)
        self.record_action("safe_add", moderator_id, "RULES", f"{phrase} | {reason}", dry_run=False, save=False)
        self.save_all()
        return ToolResult(True, "safe_add", f"Added safe phrase:{phrase}", {"phrase": phrase, "reason": reason})

    def safe_remove(self, phrase: str, moderator_id: str) -> ToolResult:
        return self.rule_remove("safe_phrases", phrase, moderator_id)

    def safe_list(self) -> ToolResult:
        phrases = list(self.rules.get("safe_phrases", []))
        return ToolResult(True, "safe_list", "Safe phrases listed.", {"safe_phrases": phrases})

    def rule_add(self, category: str, term: str, moderator_id: str) -> ToolResult:
        category = _clean_term(category)
        term = _clean_term(term)
        if category not in RULE_CATEGORIES:
            return ToolResult(False, "rule_add", f"Unknown category:{category}", {"allowed_categories": sorted(RULE_CATEGORIES)})
        if not term:
            return ToolResult(False, "rule_add", "Term / safe phrase cannot be empty.", {})
        bucket = self.rules.setdefault(category, [])
        exists = {_normalize_text(x) for x in bucket}
        added = False
        if _normalize_text(term) not in exists:
            bucket.append(term)
            added = True
        self.record_action("rule_add", moderator_id, "RULES", f"{category}:{term}", dry_run=False, save=False)
        self.save_all()
        msg = f"Added {category}:{term}" if added else f"{category} already exists:{term}"
        return ToolResult(True, "rule_add", msg, {"category": category, "term": term, "added": added})

    def rule_remove(self, category: str, term: str, moderator_id: str) -> ToolResult:
        category = _clean_term(category)
        term = _clean_term(term)
        if category not in RULE_CATEGORIES:
            return ToolResult(False, "rule_remove", f"Unknown category:{category}", {"allowed_categories": sorted(RULE_CATEGORIES)})
        old = list(self.rules.get(category, []))
        term_norm = _normalize_text(term)
        new = [x for x in old if _normalize_text(x) != term_norm]
        self.rules[category] = new
        removed = len(old) - len(new)
        self.record_action("rule_remove", moderator_id, "RULES", f"{category}:{term}", dry_run=False, save=False)
        self.save_all()
        return ToolResult(bool(removed), "rule_remove", f"Removed {category}:{term}" if removed else "Term not found.", {"category": category, "term": term, "removed": removed})

    def rule_list(self) -> ToolResult:
        return ToolResult(True, "rule_list", "Current rules loaded.", {"rules": self.rules, "allowed_categories": sorted(RULE_CATEGORIES)})

    def case_get(self, case_id: str) -> ToolResult:
        for case in self.cases:
            if str(case.get("case_id")) == str(case_id):
                return ToolResult(True, "case_get", f"Loaded {case_id}.", {"case": case})
        return ToolResult(False, "case_get", "case not found.", {"case_id": case_id})

    def case_set_thread(self, case_id: str, thread_id: str, thread_url: str = "") -> ToolResult:
        for case in self.cases:
            if str(case.get("case_id")) == str(case_id):
                case["thread_id"] = str(thread_id)
                case["thread_url"] = str(thread_url)
                self.save_all()
                return ToolResult(True, "case_set_thread", f"Recorded {case_id} thread.", {"case_id": case_id, "thread_id": str(thread_id), "thread_url": thread_url})
        return ToolResult(False, "case_set_thread", "case not found.", {"case_id": case_id})

    def case_list(self, status: str = "pending", user_id: str = "", limit: int = 10) -> ToolResult:
        status = (status or "pending").strip().lower()
        limit = max(1, min(int(limit or 10), 50))
        cases = list(self.cases)
        if status not in {"all", "pending", "resolved", "ignored"}:
            return ToolResult(False, "case_list", "status must be all / pending / resolved / ignored.", {"allowed_status": ["all", "pending", "resolved", "ignored"]})
        if status != "all":
            cases = [c for c in cases if str(c.get("status", "pending")) == status]
        if user_id:
            cases = [c for c in cases if str(c.get("user_id")) == str(user_id)]
        cases = list(reversed(cases))[:limit]
        return ToolResult(True, "case_list", f"Listed {len(cases)} cases.", {"cases": cases, "status": status, "limit": limit})

    def _is_test_case(self, case: dict[str, Any]) -> bool:
        text = _normalize_text(str(case.get("content", "")) + " " + str(case.get("current_content", "")))
        if any(k in text for k in ["test violation", "moderation feature test", "moderation detection test", "testviolation"]):
            return True
        for match in case.get("matches", []) or []:
            term = _normalize_text(str(match.get("term", "")))
            if term in {"test violation", "moderation feature test", "moderation detection test"}:
                return True
        return False

    def case_clear(self, status: str, moderator_id: str, *, test_only: bool = False) -> ToolResult:
        status = (status or "resolved").strip().lower()
        if status not in {"pending", "resolved", "ignored", "all"}:
            return ToolResult(False, "case_clear", "status must be pending / resolved / ignored / all.", {"allowed_status": ["pending", "resolved", "ignored", "all"]})

        old_cases = list(self.cases)
        kept: list[dict[str, Any]] = []
        removed: list[dict[str, Any]] = []
        for case in old_cases:
            status_match = status == "all" or str(case.get("status", "pending")) == status
            test_match = self._is_test_case(case) if test_only else True
            if status_match and test_match:
                removed.append(case)
            else:
                kept.append(case)
        self.cases = kept
        self.record_action("case_clear_test" if test_only else "case_clear", moderator_id, "CASES", f"status={status}; removed={len(removed)}", dry_run=False, save=False)
        self.save_all()
        return ToolResult(True, "case_clear", f"Cleared {len(removed)} cases.", {"removed_count": len(removed), "status": status, "test_only": test_only, "removed_case_ids": [str(c.get("case_id")) for c in removed]})

    def case_clear_test(self, moderator_id: str) -> ToolResult:
        return self.case_clear("all", moderator_id, test_only=True)

    def case_ignore(self, case_id: str, moderator_id: str, reason: str = "", add_safe_phrase: str = "") -> ToolResult:
        target = None
        for case in self.cases:
            if str(case.get("case_id")) == str(case_id):
                target = case
                break
        if not target:
            return ToolResult(False, "case_ignore", "case not found.", {"case_id": case_id})

        target["status"] = "ignored"
        target["ignore_reason"] = reason
        target["ignored_by"] = str(moderator_id)
        target["ignored_at"] = _now()

        if add_safe_phrase.strip():
            self.safe_add(add_safe_phrase, moderator_id, f"by {case_id} added as false positive:{reason}")
        else:
            self.record_action("case_ignore", moderator_id, str(target.get("user_id")), f"{case_id} | {reason}", dry_run=False, save=False)
            self.save_all()

        return ToolResult(True, "case_ignore", f"Marked {case_id} as false positive / ignored.", {"case": target})

    def case_resolve(self, case_id: str, moderator_id: str, action: str, reason: str = "") -> ToolResult:
        target = None
        for case in self.cases:
            if str(case.get("case_id")) == str(case_id):
                target = case
                break
        if not target:
            return ToolResult(False, "case_resolve", "case not found.", {"case_id": case_id})
        target["status"] = "resolved"
        target["resolved_action"] = action
        target["resolved_reason"] = reason
        target["resolved_by"] = str(moderator_id)
        target["resolved_at"] = _now()
        self.record_action("case_resolve", moderator_id, str(target.get("user_id")), f"{case_id} | {action} | {reason}", dry_run=False, save=False)
        self.save_all()
        return ToolResult(True, "case_resolve", f"Resolved case {case_id}.", {"case": target})
