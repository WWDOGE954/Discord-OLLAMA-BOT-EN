"""Ollama helper with per-user in-memory context."""
from __future__ import annotations

import os
import re
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-coder:6.7b")
MAX_MEMORY_PER_USER = int(os.getenv("MAX_MEMORY_PER_USER", "20"))

user_memory: dict[str, list[dict[str, str]]] = {}
user_names: dict[str, str] = {}

SYSTEM_PROMPT = (
    "You are a Discord server moderation assistant."
    "You can help summarize incidents, suggest moderation actions, organize rules, and answer technical questions."
    "For high-risk actions such as timeout, kick, delete message, or ban, only make suggestions and never pretend the action has been executed."
    "Reply in English and keep it concise."
)


def reset_user_memory(user_id: str | None = None) -> None:
    if user_id is None or user_id == "ALL":
        user_memory.clear()
        user_names.clear()
        return
    user_memory.pop(str(user_id), None)
    user_names.pop(str(user_id), None)


def _ensure_user(user_id: str, display_name: str = "") -> None:
    if display_name:
        user_names[user_id] = display_name
    if user_id not in user_memory:
        user_memory[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]


def _strip_think(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return text.replace("<think>", "").replace("</think>", "").strip()


def ask_ollama(prompt: str, user_id: str, display_name: str = "") -> str:
    user_id = str(user_id)
    _ensure_user(user_id, display_name)

    name = user_names.get(user_id) or display_name or f"user {user_id}"
    user_memory[user_id].append({"role": "user", "content": f"{name}:{prompt}"})

    # Ollama /api/generate is plain prompt-based, so we flatten the small memory.
    full_prompt = "\n".join(msg["content"] for msg in user_memory[user_id])

    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": full_prompt, "stream": False},
            timeout=60,
        )
        if response.status_code != 200:
            return f"⚠️ Ollama request failed:{response.status_code}\n{response.text[:500]}"

        data: dict[str, Any] = response.json()
        reply = _strip_think(str(data.get("response", "⚠️ Local model did not respond")))
        if not reply:
            reply = "⚠️ Local model returned an empty response."

        user_memory[user_id].append({"role": "assistant", "content": reply})
        user_memory[user_id] = user_memory[user_id][:1] + user_memory[user_id][-MAX_MEMORY_PER_USER:]
        return reply
    except Exception as exc:
        return f"❌ Local model error:{exc}"
