from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import os
import re
import shutil
import uuid

from storage import DATA_DIR, read_json, write_json

MUSIC_LIBRARY_FILE = "music_library.json"
MUSIC_FILES_DIR = DATA_DIR / "music_files"
MUSIC_FILES_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a"}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_name(name: str, max_len: int = 80) -> str:
    name = name.strip()
    name = re.sub(r"[\\/:*?\"<>|\r\n\t]+", "_", name)
    name = re.sub(r"\s+", " ", name)
    return name[:max_len].strip() or "untitled"


def _safe_ext(filename: str) -> str:
    return Path(filename).suffix.lower().strip()


def _load_library() -> dict[str, Any]:
    data = read_json(MUSIC_LIBRARY_FILE, {})
    return data if isinstance(data, dict) else {}


def _save_library(data: dict[str, Any]) -> None:
    write_json(MUSIC_LIBRARY_FILE, data)


def get_user_library(user_id: str, display_name: str = "") -> dict[str, Any]:
    library = _load_library()
    entry = library.get(user_id)
    if not isinstance(entry, dict):
        entry = {"display_name": display_name or user_id, "tracks": []}
    entry.setdefault("display_name", display_name or entry.get("display_name") or user_id)
    entry.setdefault("tracks", [])
    return entry


def list_tracks(user_id: str, display_name: str = "") -> list[dict[str, Any]]:
    return list(get_user_library(user_id, display_name).get("tracks", []))


def library_summary(user_id: str, display_name: str = "") -> dict[str, Any]:
    tracks = list_tracks(user_id, display_name)
    total_bytes = 0
    for track in tracks:
        try:
            total_bytes += int(track.get("size_bytes", 0))
        except Exception:
            pass
    return {
        "display_name": display_name or get_user_library(user_id, display_name).get("display_name", user_id),
        "track_count": len(tracks),
        "total_mb": round(total_bytes / (1024 * 1024), 2),
        "tracks": tracks,
    }


def add_track(
    *,
    owner_id: str,
    owner_display_name: str,
    uploader_id: str,
    uploader_display_name: str,
    name: str,
    original_filename: str,
    source_temp_path: str,
    size_bytes: int,
    message_url: str = "",
    max_tracks_per_user: int = 20,
) -> dict[str, Any]:
    ext = _safe_ext(original_filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported audio format:{ext or 'no extension'}.Allowed:{', '.join(sorted(ALLOWED_EXTENSIONS))}")

    library = _load_library()
    entry = library.get(owner_id)
    if not isinstance(entry, dict):
        entry = {"display_name": owner_display_name or owner_id, "tracks": []}

    tracks = entry.setdefault("tracks", [])
    if len(tracks) >= max_tracks_per_user:
        raise ValueError(f"This user music library reached the limit:{max_tracks_per_user} tracks.")

    track_id = "T" + uuid.uuid4().hex[:8].upper()
    safe_title = _safe_name(name, 60)
    owner_dir = MUSIC_FILES_DIR / owner_id
    owner_dir.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{track_id}{ext}"
    stored_path = owner_dir / stored_filename

    shutil.move(source_temp_path, stored_path)

    track = {
        "track_id": track_id,
        "name": safe_title,
        "original_filename": _safe_name(original_filename, 120),
        "filename": stored_filename,
        "path": str(stored_path),
        "size_bytes": int(size_bytes),
        "owner_id": owner_id,
        "owner_display_name": owner_display_name or owner_id,
        "uploader_id": uploader_id,
        "uploader_display_name": uploader_display_name or uploader_id,
        "uploaded_at": _now(),
        "message_url": message_url,
        "play_count": 0,
    }
    tracks.append(track)
    entry["display_name"] = owner_display_name or entry.get("display_name") or owner_id
    library[owner_id] = entry
    _save_library(library)
    return track


def remove_track(owner_id: str, track_id: str) -> dict[str, Any] | None:
    track_id = track_id.strip().upper()
    library = _load_library()
    entry = library.get(owner_id)
    if not isinstance(entry, dict):
        return None

    tracks = entry.get("tracks", [])
    kept = []
    removed = None
    for track in tracks:
        if str(track.get("track_id", "")).upper() == track_id:
            removed = track
        else:
            kept.append(track)

    if removed is None:
        return None

    entry["tracks"] = kept
    library[owner_id] = entry
    _save_library(library)

    try:
        path = Path(str(removed.get("path", "")))
        if path.exists() and MUSIC_FILES_DIR in path.resolve().parents:
            path.unlink()
    except Exception:
        pass

    return removed


def get_track(owner_id: str, track_id: str) -> dict[str, Any] | None:
    track_id = track_id.strip().upper()
    for track in list_tracks(owner_id):
        if str(track.get("track_id", "")).upper() == track_id:
            return track
    return None


def increment_play_count(owner_id: str, track_id: str) -> None:
    library = _load_library()
    entry = library.get(owner_id)
    if not isinstance(entry, dict):
        return
    for track in entry.get("tracks", []):
        if str(track.get("track_id", "")).upper() == track_id.upper():
            track["play_count"] = int(track.get("play_count", 0)) + 1
            track["last_played_at"] = _now()
            break
    _save_library(library)
