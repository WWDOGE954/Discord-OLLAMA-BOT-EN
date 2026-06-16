from __future__ import annotations
import asyncio
import base64
import io
import os
import platform
import random
import re
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
import shutil
import requests
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from docx import Document
from hardware_monitor import collect_system_report, format_system_report, format_detailed_system_report
from ollama_helper import ask_ollama, reset_user_memory
from tool_router import ToolRouter, ToolResult
from user_profiles import cache_is_fresh, cache_key, clear_attention, get_cached_insight, get_profile, read_recent_ai_interactions, record_ai_interaction, set_attention, set_cached_insight, update_last_summary, build_profile_prompt, format_attention
from runtime_state import load_runtime_state, save_runtime_state, set_mode, is_ai_enabled, is_doc_summary_enabled, is_full_report_enabled
from music_manager import ALLOWED_EXTENSIONS, MUSIC_FILES_DIR, add_track, increment_play_count, library_summary, list_tracks, remove_track
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = os.getenv('GUILD_ID')
USE_MESSAGE_CONTENT = os.getenv('USE_MESSAGE_CONTENT', 'false').lower() == 'true'
REPORT_WEBHOOK_URL = os.getenv('REPORT_WEBHOOK_URL', '').strip()
REPORT_CHANNEL_ID = os.getenv('REPORT_CHANNEL_ID', '').strip()
CREATE_CASE_THREADS = os.getenv('CREATE_CASE_THREADS', 'false').lower() == 'true'
CASE_THREAD_ARCHIVE_MINUTES = int(os.getenv('CASE_THREAD_ARCHIVE_MINUTES', '1440'))
ADMIN_ROLE_ID = os.getenv('ADMIN_ROLE_ID', '').strip()
WARNING_ROLE_ID = os.getenv('WARNING_ROLE_ID', '').strip()
AUTO_TIMEOUT_ENABLED = os.getenv('AUTO_TIMEOUT_ENABLED', 'false').lower() == 'true'
AUTO_TIMEOUT_MINUTES = int(os.getenv('AUTO_TIMEOUT_MINUTES', '2'))
PUBLIC_WARNING = os.getenv('PUBLIC_WARNING', 'false').lower() == 'true'
PC_STATUS_CHANNEL_ID = os.getenv('PC_STATUS_CHANNEL_ID', '').strip()
PC_STATUS_INTERVAL_MINUTES = int(os.getenv('PC_STATUS_INTERVAL_MINUTES', '30'))
PC_STATUS_ENABLED = os.getenv('PC_STATUS_ENABLED', 'false').lower() == 'true'
TEMP_AUTO_RECOVER_MARGIN = float(os.getenv('TEMP_AUTO_RECOVER_MARGIN', '8'))
FFMPEG_EXE = os.getenv('FFMPEG_EXE', '').strip()
if not FFMPEG_EXE:
    FFMPEG_EXE = shutil.which('ffmpeg') or 'ffmpeg'
print(f' FFMPEG_EXE = {FFMPEG_EXE}')
MY_PROFILE_AI_COOLDOWN_MINUTES = int(os.getenv('MY_PROFILE_AI_COOLDOWN_MINUTES', '60'))
MY_PROFILE_AI_DAYS = int(os.getenv('MY_PROFILE_AI_DAYS', '7'))
MY_PROFILE_HISTORY_PER_CHANNEL = int(os.getenv('MY_PROFILE_HISTORY_PER_CHANNEL', '100'))
MY_PROFILE_MAX_MESSAGES = int(os.getenv('MY_PROFILE_MAX_MESSAGES', '80'))
USER_INSIGHT_COOLDOWN_MINUTES = int(os.getenv('USER_INSIGHT_COOLDOWN_MINUTES', '30'))
USER_INSIGHT_PRO_HISTORY_PER_CHANNEL = int(os.getenv('USER_INSIGHT_PRO_HISTORY_PER_CHANNEL', '500'))
USER_INSIGHT_PRO_MAX_MESSAGES = int(os.getenv('USER_INSIGHT_PRO_MAX_MESSAGES', '2000'))
MUSIC_UPLOAD_CHANNEL_ID = os.getenv('MUSIC_UPLOAD_CHANNEL_ID', '').strip()
MUSIC_MAX_TRACKS_PER_USER = int(os.getenv('MUSIC_MAX_TRACKS_PER_USER', '20'))
MUSIC_MAX_FILE_MB = int(os.getenv('MUSIC_MAX_FILE_MB', '50'))
MUSIC_LEAVE_AFTER_QUEUE = os.getenv('MUSIC_LEAVE_AFTER_QUEUE', 'true').lower() == 'true'
try:
    MUSIC_DEFAULT_VOLUME = max(0.0, min(2.0, float(os.getenv('MUSIC_DEFAULT_VOLUME', '0.8'))))
except ValueError:
    MUSIC_DEFAULT_VOLUME = 0.8
if not DISCORD_TOKEN:
    raise RuntimeError('Please set DISCORD_TOKEN in Your .env file first')
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = USE_MESSAGE_CONTENT
bot = commands.Bot(command_prefix='!', intents=intents)
router = ToolRouter()
_synced = False
_pc_status_task: asyncio.Task | None = None
runtime_state = load_runtime_state()

AUTO_MOD_AWAY_ENABLED = os.getenv("AUTO_MOD_AWAY_ENABLED", "false").lower() == "true"
AUTO_MOD_AUTOCLOSE_ON_TIMEOUT = os.getenv("AUTO_MOD_AUTOCLOSE_ON_TIMEOUT", "true").lower() == "true"
AI_VISION_ENABLED = os.getenv("AI_VISION_ENABLED", "false").lower() == "true"
OLLAMA_VISION_URL = os.getenv("OLLAMA_VISION_URL", "http://localhost:11434/api/chat")
OLLAMA_VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llava:latest")
AI_VISION_MAX_IMAGE_MB = int(os.getenv("AI_VISION_MAX_IMAGE_MB", "6"))
AI_VISION_TIMEOUT_SECONDS = int(os.getenv("AI_VISION_TIMEOUT_SECONDS", "90"))

AI_COMMAND_COOLDOWN_SECONDS = int(os.getenv("AI_COMMAND_COOLDOWN_SECONDS", "60"))
AI_LONG_COMMAND_COOLDOWN_SECONDS = int(os.getenv("AI_LONG_COMMAND_COOLDOWN_SECONDS", "600"))

AI_LONG_DEFAULT_COLLECT_SECONDS = int(os.getenv("AI_LONG_DEFAULT_COLLECT_SECONDS", "60"))
AI_LONG_MAX_COLLECT_SECONDS = int(os.getenv("AI_LONG_MAX_COLLECT_SECONDS", "180"))

AI_LAST_USED: dict[str, datetime] = {}
AI_LONG_LAST_USED: dict[str, datetime] = {}


def _cooldown_text(seconds: int) -> str:
    seconds = max(0, int(seconds))
    minutes, secs = divmod(seconds, 60)
    if minutes and secs:
        return f"{minutes} min {secs} sec"
    if minutes:
        return f"{minutes} min"
    return f"{secs} sec"


def _ai_cooldown_remaining(
    user_id: str,
    cooldown_seconds: int,
    store: dict[str, datetime],
) -> int:
    if cooldown_seconds <= 0:
        return 0

    last = store.get(str(user_id))
    if not last:
        return 0

    elapsed = (datetime.now(timezone.utc) - last).total_seconds()
    remain = int(cooldown_seconds - elapsed)
    return max(0, remain)


def _mark_ai_used(
    user_id: str,
    cooldown_seconds: int,
    store: dict[str, datetime],
) -> None:
    if cooldown_seconds > 0:
        store[str(user_id)] = datetime.now(timezone.utc)


def _ai_cooldown_message(remain: int) -> str:
    return f"AI is on cooldown. Please wait {_cooldown_text(remain)} before using it again."



def _ask_ollama_vision_sync(image_bytes: bytes, filename: str, question: str = "Describe this image in English. If it is a screenshot, summarize visible text, error messages, and key points.") -> str:
    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    payload = {
        "model": OLLAMA_VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": f"{question}\nFilename:{filename}",
                "images": [image_b64],
            }
        ],
        "stream": False,
    }
    try:
        response = requests.post(OLLAMA_VISION_URL, json=payload, timeout=AI_VISION_TIMEOUT_SECONDS)
        if response.status_code != 200:
            return f"Vision model request failed: {response.status_code} {response.text[:300]}"
        data = response.json()
        if isinstance(data, dict):
            if isinstance(data.get("message"), dict):
                return str(data["message"].get("content", "")).strip() or "Vision model returned empty content."
            return str(data.get("response", "")).strip() or "Vision model returned empty content."
        return "Vision model returned an unexpected response format."
    except Exception as exc:
        return f"Vision model error: {exc}"


async def _attachment_to_ai_text(attachment: discord.Attachment) -> str:
    filename = attachment.filename or "unknown"
    content_type = attachment.content_type or "unknown"
    size = int(attachment.size or 0)
    url = attachment.url
    suffix = Path(filename).suffix.lower()

    if str(content_type).startswith("image/"):
        lines = [
            "[Image attachment]",
            f"- Filename:{filename}",
            f"- Type:{content_type}",
            f"- Size:{round(size / 1024, 1)} KB",
            f"- Link:{url}",
        ]
        if AI_VISION_ENABLED:
            max_bytes = AI_VISION_MAX_IMAGE_MB * 1024 * 1024
            if size > max_bytes:
                lines.append(f"- Image analysis skipped: image is larger than {AI_VISION_MAX_IMAGE_MB}MB.")
            else:
                try:
                    image_bytes = await attachment.read()
                    vision_text = await asyncio.to_thread(_ask_ollama_vision_sync, image_bytes, filename)
                    lines.append("- Image analysis:")
                    lines.append(vision_text[:2500])
                except Exception as exc:
                    lines.append(f"- Image analysis failed:{exc}")
        else:
            lines.append("- Image analysis is disabled. To analyze images, set AI_VISION_ENABLED=true and prepare a vision model.")
        return "\n".join(lines)

    text_suffixes = {".txt", ".md", ".py", ".json", ".csv", ".log", ".yml", ".yaml", ".ini", ".env"}
    if str(content_type).startswith("text/") or suffix in text_suffixes:
        if size <= 256 * 1024:
            try:
                data = await attachment.read()
                body = data.decode("utf-8", errors="ignore")[:6000]
                return (
                    f"[Text attachment]\n"
                    f"- Filename:{filename}\n"
                    f"- Type:{content_type}\n"
                    f"- Size:{round(size / 1024, 1)} KB\n"
                    f"- Content preview:\n{body}"
                )
            except Exception as exc:
                return f"[Attachment read failed] {filename} | {content_type} | {round(size / 1024, 1)} KB | {url} | error:{exc}"

    return f"[Attachment] {filename} | {content_type} | {round(size / 1024, 1)} KB | {url}"


async def _message_to_ai_text(msg: discord.message) -> str:
    parts: list[str] = []
    content = (msg.content or "").strip()
    if content:
        parts.append(content[:4000])
    for attachment in msg.attachments:
        parts.append(await _attachment_to_ai_text(attachment))
    if not parts:
        parts.append("[Empty message or unreadable content]")
    return f"--- message {msg.id} | {msg.created_at.isoformat()} ---\n" + "\n".join(parts)


async def _run_ai_long_mode(
    interaction: discord.Interaction,
    *,
    question: str,
    collect_seconds: int,
    public: bool,
) -> None:
    if not interaction.channel or not hasattr(interaction.channel, "id"):
        await interaction.response.send_message(" This feature must be used in a text channel.", ephemeral=not public)
        return

    collect_seconds = max(10, min(int(collect_seconds), AI_LONG_MAX_COLLECT_SECONDS))
    await interaction.response.send_message(
        f" **AI long-form collection mode started**\n"
        f"Please send the long text, additional messages, or image attachments in this channel within the next **{collect_seconds} sec**.\n"
        f"When finished, send `done`, `end`, or `finish` to end collection early.",
        ephemeral=not public,
    )

    channel_id = interaction.channel.id
    user_id = interaction.user.id
    collected: list[discord.message] = []
    done_words = {"done", "done", "end", "end", "END", "Done", "DONE"}
    deadline = datetime.now(timezone.utc) + timedelta(seconds=collect_seconds)

    def check(msg: discord.message) -> bool:
        return (
            not msg.author.bot
            and msg.author.id == user_id
            and getattr(msg.channel, "id", None) == channel_id
            and msg.created_at >= interaction.created_at
        )

    while True:
        remain = (deadline - datetime.now(timezone.utc)).total_seconds()
        if remain <= 0:
            break
        try:
            msg = await bot.wait_for("message", timeout=remain, check=check)
        except asyncio.TimeoutError:
            break
        if (msg.content or "").strip() in done_words and not msg.attachments:
            break
        collected.append(msg)

    if not collected:
        await interaction.followup.send(" No long text or attachment was received.", ephemeral=not public)
        return

    thinking = await interaction.followup.send(
        f" Received {len(collected)} messages. Processing and replying...",
        ephemeral=not public,
        wait=True,
    )

    blocks = []
    for msg in collected:
        blocks.append(await _message_to_ai_text(msg))

    full_prompt = (
        "You are reading long-form content posted by a Discord user. Answer the user based on the collected content.\n"
        "If an image cannot be interpreted directly, clearly state that only its filename, type, and link are available.\n\n"
        f"user question / task:{question}\n\n"
        "Collected content:\n"
        + "\n\n".join(blocks)
    )[:18000]

    reply = await asyncio.to_thread(ask_ollama, full_prompt, str(interaction.user.id), interaction.user.display_name)
    try:
        await thinking.edit(content=reply[:1900])
    except Exception:
        await interaction.followup.send(reply[:1900], ephemeral=not public)

    try:
        record_ai_interaction(
            user_id=str(interaction.user.id),
            display_name=interaction.user.display_name,
            guild_id=str(interaction.guild.id) if interaction.guild else "DM",
            channel_id=str(interaction.channel.id) if interaction.channel else "DM",
            kind="slash_ai_long",
            prompt=full_prompt[:1500],
            reply=reply,
        )
    except Exception as exc:
        print(f" Failed to save AI long-form interaction log:{exc}")

PUBLIC_COMMANDS = {'ai', 'status', 'my_warnings', 'my_profile', 'music_add', 'music_list', 'music_remove', 'go_music', 'music_queue', 'music_skip', 'music_stop', 'music_pause', 'music_resume', 'music_now', 'music_volume', 'music_loop', 'music_clear', 'music_sync'}

def extract_temp_c(text: str) -> float | None:
    match = re.search('(-?\\d+(?:\\.\\d+)?)\\s*°C', text or '')
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None

def warning_reminder_text(data: dict) -> str:
    anger = int(data.get('anger', 0))
    limit = int(data.get('anger_limit', 3))
    warning_count = int(data.get('warning_count', 0))
    pending = len(data.get('pending_cases', []))
    remain = max(0, limit - anger)
    if warning_count <= 0 and anger <= 0:
        level = ' No warnings recorded.'
    elif remain >= 2:
        level = ' Warnings exist. Please be careful with future messages.'
    elif remain == 1:
        level = ' Close to the action threshold. Another trigger may be reviewed by moderators or cause a short timeout.'
    else:
        level = ' Action threshold reached. Please wait for moderator review or improve future messages.'
    return f'Warnings:{warning_count}\nAnger:{anger}/{limit}\nPending cases:{pending}\nReminder:{level}'

def profile_basic_text(status_data: dict, profile: dict) -> str:
    last_summary = str(profile.get('last_summary') or 'No AI insight has been generated yet.')
    notes = profile.get('notes') or []
    last_note = str(notes[-1]) if notes else 'Failed'
    return f"Warnings:{status_data.get('warning_count', 0)}\nAnger:{status_data.get('anger', 0)}/{status_data.get('anger_limit', 0)}\ncases:{status_data.get('case_count', 0)}\nPending cases:{len(status_data.get('pending_cases', []))}\nAttention level:{format_attention(profile.get('attention_score', 0))}\nAI interactions:{profile.get('ai_interaction_count', 0)}\nLatest moderator note:{last_note[:300]}\nLast AI insight:{last_summary[:600]}"

async def collect_user_discord_history(guild: discord.Guild | None, target_user_id: int, *, days: int=7, per_channel_limit: int=100, max_messages: int=80) -> tuple[list[dict], dict]:
    """Scan text channels visible to the bot and collect recent messages from the target user."""
    if guild is None:
        return ([], {'scanned_channels': 0, 'skipped_channels': 0, 'matched_messages': 0})
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, int(days)))
    bot_member = guild.me
    messages: list[dict] = []
    scanned = 0
    skipped = 0
    for channel in guild.text_channels:
        if len(messages) >= max_messages:
            break
        try:
            perms = channel.permissions_for(bot_member) if bot_member else None
            if perms and (not perms.view_channel or not perms.read_message_history):
                skipped += 1
                continue
            scanned += 1
            async for msg in channel.history(limit=max(1, int(per_channel_limit)), after=cutoff, oldest_first=False):
                if msg.author.bot:
                    continue
                if int(msg.author.id) != int(target_user_id):
                    continue
                content = (msg.content or '').strip()
                if not content:
                    continue
                messages.append({'time': msg.created_at.isoformat(), 'guild_id': str(guild.id), 'channel_id': str(channel.id), 'channel_name': channel.name, 'message_id': str(msg.id), 'jump_url': msg.jump_url, 'content': content[:900]})
                if len(messages) >= max_messages:
                    break
            await asyncio.sleep(0)
        except Exception:
            skipped += 1
            continue
    messages.sort(key=lambda x: str(x.get('time', '')), reverse=True)
    meta = {'scanned_channels': scanned, 'skipped_channels': skipped, 'matched_messages': len(messages)}
    return (messages[:max_messages], meta)

def insight_cooldown_text(remain_minutes: int) -> str:
    if remain_minutes <= 0:
        return ''
    if remain_minutes < 60:
        return f'About {remain_minutes} min until regeneration is available.'
    hours, minutes = divmod(remain_minutes, 60)
    return f'About {hours} h {minutes} min until regeneration is available.'

async def generate_user_insight(*, interaction: discord.Interaction, target: discord.Member | discord.user, days: int, is_self: bool, pro: bool, use_history: bool, refresh: bool, cooldown_minutes: int, per_channel_limit: int, max_messages: int) -> tuple[str, bool]:
    """Return (message, used_cache)."""
    guild_id = str(interaction.guild.id) if interaction.guild else 'DM'
    target_id = str(target.id)
    display_name = getattr(target, 'display_name', str(target))
    key = cache_key('my' if is_self else 'user', guild_id, target_id, int(days), pro=pro)
    cached = get_cached_insight(key)
    fresh, remain = cache_is_fresh(cached, cooldown_minutes)
    if fresh and (not refresh or not require_manage_messages(interaction)):
        summary = str(cached.get('summary', '')) if cached else ''
        generated_at = str(cached.get('generated_at', 'Unknown')) if cached else 'Unknown'
        return (f' Still on cooldown. Showing the last AI insight instead.\nGenerated at:{generated_at}\nNext regeneration:{insight_cooldown_text(remain)}\n\n{summary[:1700]}', True)
    if not is_ai_enabled(runtime_state):
        if cached and cached.get('summary'):
            return (f" Bot is currently in `{runtime_state.mode}`` mode. AI analysis is paused. Showing the last cache:\n\n{str(cached.get('summary'))[:1700]}", True)
        return (f' Bot is currently in `{runtime_state.mode}`` mode. AI analysis is paused and no cache is available.', True)
    status = router.get_user_status(target_id, display_name).data
    profile = get_profile(target_id, display_name)
    ai_events = read_recent_ai_interactions(target_id, days=days, max_events=40 if pro else 20)
    discord_messages: list[dict] = []
    meta = {'scanned_channels': 0, 'skipped_channels': 0, 'matched_messages': 0}
    if use_history:
        discord_messages, meta = await collect_user_discord_history(interaction.guild, int(target.id), days=days, per_channel_limit=per_channel_limit, max_messages=max_messages)
    prompt = build_profile_prompt(target_name=display_name, days=days, status_data=status, profile=profile, ai_events=ai_events, discord_messages=discord_messages, is_self=is_self, pro=pro)
    memory_key = f"INSIGHT_{guild_id}_{target_id}_{('self' if is_self else 'admin')}"
    reset_user_memory(memory_key)
    reply = await asyncio.to_thread(ask_ollama, prompt, memory_key, 'Insight Analyzer')
    reset_user_memory(memory_key)
    payload = {'generated_at': datetime.now(timezone.utc).isoformat(), 'target_user_id': target_id, 'display_name': display_name, 'days': int(days), 'pro': bool(pro), 'used_history': bool(use_history), 'history_meta': meta, 'summary': reply[:3500]}
    set_cached_insight(key, payload)
    update_last_summary(target_id, display_name, reply)
    source = f"Source: data records + Discord history scan across {meta['scanned_channels']} channels, found {meta['matched_messages']} messages." if use_history else 'Source: data records for warnings, cases, and AI interactions.'
    return (f' **AI interaction insight**\n{source}\n\n{reply[:1700]}', False)

def _to_int_or_none(value: str) -> int | None:
    value = (value or '').strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None

def require_manage_messages(interaction: discord.Interaction) -> bool:
    perms = getattr(interaction.user, 'guild_permissions', None)
    if perms and (perms.manage_messages or perms.administrator):
        return True
    role_id = _to_int_or_none(ADMIN_ROLE_ID)
    if role_id and isinstance(interaction.user, discord.Member):
        return any((role.id == role_id for role in interaction.user.roles))
    return False

def is_admin_member(member: discord.Member | discord.user) -> bool:
    perms = getattr(member, 'guild_permissions', None)
    if perms and (perms.manage_messages or perms.administrator):
        return True
    role_id = _to_int_or_none(ADMIN_ROLE_ID)
    if role_id and isinstance(member, discord.Member):
        return any((role.id == role_id for role in member.roles))
    return False

def format_tool_result(result: ToolResult) -> str:
    lines = [f'**{result.tool}**', result.message]
    if result.requires_admin_confirm:
        lines.append(' This is a high-risk action suggestion and requires admin confirmation.')
    if result.dry_run:
        lines.append(' dry-run: no real action has been executed.')
    return '\n'.join(lines)

def format_case_summary(data: dict) -> str:
    matches = data.get('matches', [])
    match_text = ', '.join((f"{m.get('category')}:{m.get('term')}" for m in matches)) or 'Failed'
    return f"case:{data.get('case_id')}\nuser:{data.get('display_name')} ({data.get('user_id')})\nmatches:{match_text}\nTargeted attack:{('is' if data.get('targeted_attack') else 'No')}\nRecent triggers:{data.get('recent_count')}/{data.get('auto_timeout_count')}\nStatus:{data.get('status')}"

async def sync_commands_once() -> None:
    global _synced
    if _synced:
        return
    if GUILD_ID:
        guild = discord.Object(id=int(GUILD_ID))
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        print(f' Slash commands synced to guild {GUILD_ID}')
    else:
        await bot.tree.sync()
        print(' Slash commands synced globally')
    _synced = True

async def add_warning_role(member: discord.Member) -> str:
    role_id = _to_int_or_none(WARNING_ROLE_ID)
    if not role_id:
        return 'WARNING_ROLE_ID is not set; skipped adding the warning role.'
    role = member.guild.get_role(role_id)
    if not role:
        return 'Could not find the role for WARNING_ROLE_ID.'
    if role in member.roles:
        return 'user already has the warning role.'
    try:
        await member.add_roles(role, reason='Automatic moderation detection')
        return f'Added {role.name} role.'
    except Exception as exc:
        return f'Failed to add warning role:{exc}'

async def remove_warning_role(member: discord.Member) -> str:
    role_id = _to_int_or_none(WARNING_ROLE_ID)
    if not role_id:
        return 'WARNING_ROLE_ID is not set.'
    role = member.guild.get_role(role_id)
    if not role:
        return 'Could not find the role for WARNING_ROLE_ID.'
    if role not in member.roles:
        return 'user does not have the warning role.'
    try:
        await member.remove_roles(role, reason='Moderator removed warning role')
        return f'Removed {role.name} role.'
    except Exception as exc:
        return f'Failed to remove warning role:{exc}'

async def _get_channel_by_id(channel_id: str):
    cid = _to_int_or_none(channel_id)
    if not cid:
        return None
    channel = bot.get_channel(cid)
    if channel is None:
        try:
            channel = await bot.fetch_channel(cid)
        except Exception:
            channel = None
    return channel

async def _send_report_by_webhook(content: str, embed: discord.Embed) -> None:
    if not REPORT_WEBHOOK_URL:
        return
    async with aiohttp.ClientSession() as session:
        webhook = discord.Webhook.from_url(REPORT_WEBHOOK_URL, session=session)
        await webhook.send(content=content, embed=embed, username='DC Moderation Report', allowed_mentions=discord.AllowedMentions(roles=True, users=False, everyone=False))

async def send_report(message: discord.message, result: ToolResult, action_notes: list[str]) -> None:
    data = result.data
    embed = discord.Embed(title=' Potential rule violation detected', description=result.message, color=15844367)
    embed.add_field(name='case ID', value=str(data.get('case_id', 'Unknown')), inline=True)
    embed.add_field(name='user', value=f'{message.author.mention}\n{message.author} / {message.author.id}', inline=True)
    embed.add_field(name='Channel', value=message.channel.mention if hasattr(message.channel, 'mention') else str(message.channel), inline=True)

    matches = data.get('matches', [])
    match_text = '\n'.join((f"- {m.get('category')}:`{m.get('term')}`" for m in matches)) or 'Failed'
    embed.add_field(name='Matched rules', value=match_text[:1000], inline=False)
    embed.add_field(name='Targeted attack', value='is' if data.get('targeted_attack') else 'No', inline=True)
    embed.add_field(name='Action applied', value='is' if data.get('penalty_applied') else 'No, report only', inline=True)
    embed.add_field(name='Recent triggers', value=f"{data.get('recent_count', 0)}/{data.get('auto_timeout_count', 0)}", inline=True)
    embed.add_field(name='Auto-timeout suggestion', value='is' if data.get('should_auto_timeout') else 'No', inline=True)
    embed.add_field(name='Admin / exempt', value='is' if data.get('is_admin') else 'No', inline=True)

    content = data.get('content', '')
    if content:
        embed.add_field(name='Original message', value=content[:1000], inline=False)
    if message.jump_url:
        embed.add_field(name='message link', value=message.jump_url, inline=False)
    if action_notes:
        embed.add_field(name='Bot action / suggestion', value='\n'.join((f'- {note}' for note in action_notes))[:1000], inline=False)

    commands_hint = (
        f"Suggested commands:\n"
        f"`/case_ignore case_id:{data.get('case_id')} reason:false positive add_safe_phrase:optional`\n"
        f"`/case_resolve case_id:{data.get('case_id')} action:warn reason:resolved`\n"
        f"`/punish user:@target minutes:5 reason:reason confirm:true`\n"
        f"`/safe_add phrase:safe phrase reason:reason`"
    )
    mention = ''
    admin_role_id = _to_int_or_none(ADMIN_ROLE_ID)
    if admin_role_id:
        mention = f'<@&{admin_role_id}> '
    report_content = mention + commands_hint

    report_channel = await _get_channel_by_id(REPORT_CHANNEL_ID)
    print(f"REPORT_CHANNEL_ID={REPORT_CHANNEL_ID}")
    print(f"report_channel={report_channel} type={type(report_channel)}")
    print(f"CREATE_CASE_THREADS={CREATE_CASE_THREADS}")

    if data.get("deduplicated"):
        thread_id = str(data.get("thread_id") or "")
        if thread_id:
            thread = await _get_channel_by_id(thread_id)
            if thread and hasattr(thread, "send"):
                current_url = data.get("current_message_url") or data.get("last_message_url") or data.get("message_url") or ""
                duplicate_count = int(data.get("duplicate_count", 0) or 0)
                recent_count = int(data.get("recent_count", 0) or 0)
                auto_count = int(data.get("auto_timeout_count", 0) or 0)
                note = (
                    f"Duplicate trigger merged into case `{data.get('case_id')}`.\n"
                    f"Duplicate count:{duplicate_count}\n"
                    f"Recent triggers:{recent_count}/{auto_count}\n"
                )
                if current_url:
                    note += f"Latest message:{current_url}\n"
                if data.get("should_auto_timeout"):
                    note += "Status:Auto-timeout threshold reached."
                elif data.get("final_warning"):
                    note += "Status:Final warning stage."
                await thread.send(note[:1900])
                return

    # ForumChannel: create a forum post directly; the post itself is the case thread.
    if isinstance(report_channel, discord.ForumChannel):
        try:
            print('Creating Forum case post...')
            name = f"Moderation case {data.get('case_id')} - {data.get('display_name', 'user')}"
            created = await report_channel.create_thread(
                name=name[:90],
                content=report_content,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(roles=True, users=False, everyone=False),
                auto_archive_duration=CASE_THREAD_ARCHIVE_MINUTES,
            )
            thread = getattr(created, 'thread', created)
            thread_url = f"https://discord.com/channels/{message.guild.id}/{thread.id}"
            print(f"Created Forum case post:{thread.name} / {thread.id} / {thread_url}")
            await thread.send('Use this thread to discuss the case, add evidence, or process it with `/case_ignore`, `/case_resolve`, or `/punish`.')
            router.case_set_thread(str(data.get('case_id')), str(thread.id), thread_url)
            return
        except Exception as exc:
            print(f' Failed to create Forum case post:{exc}')
            return

    # Normal text channel: send the report first, then create a thread under it.
    if report_channel and hasattr(report_channel, 'send'):
        try:
            report_msg = await report_channel.send(
                content=report_content,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(roles=True, users=False, everyone=False),
            )
        except Exception as exc:
            print(f' Failed to send moderation report:{exc}')
            return

        if CREATE_CASE_THREADS and hasattr(report_msg, 'create_thread'):
            try:
                print('Creating case thread...')
                name = f"Moderation case {data.get('case_id')} - {data.get('display_name', 'user')}"
                thread = await report_msg.create_thread(name=name[:90], auto_archive_duration=CASE_THREAD_ARCHIVE_MINUTES)
                thread_url = f"https://discord.com/channels/{message.guild.id}/{thread.id}"
                print(f"Created case thread:{thread.name} / {thread.id} / {thread_url}")
                await thread.send('Use this thread to discuss the case, add evidence, or process it with `/case_ignore`, `/case_resolve`, or `/punish`.')
                router.case_set_thread(str(data.get('case_id')), str(thread.id), thread_url)
            except Exception as exc:
                print(f' Failed to create case thread:{exc}')
        return

    if REPORT_WEBHOOK_URL:
        await _send_report_by_webhook(report_content, embed)
        return

    print(' REPORT_CHANNEL_ID or REPORT_WEBHOOK_URL is not set; cannot send moderation report.')


async def apply_temperature_guard(channel=None) -> tuple[str | None, bool]:
    """Check CPU temp and automatically reduce bot workload.

    Returns: (notice_message, should_shutdown_bot)
    """
    global runtime_state
    if not runtime_state.auto_guard_enabled:
        return (None, False)
    sys_report = await asyncio.to_thread(collect_system_report)
    cpu_temp = extract_temp_c(sys_report.cpu_temp)
    if cpu_temp is None:
        return (None, False)
    notice = None
    should_shutdown = False
    if cpu_temp >= runtime_state.shutdown_temp:
        runtime_state.high_temp_hits += 1
        runtime_state.mode = 'emergency'
        runtime_state.reason = f'CPU temperature {cpu_temp:.1f}°C exceeded shutdown threshold'
        save_runtime_state(runtime_state)
        notice = f' **Emergency temperature guard**\nCPU temperature:{cpu_temp:.1f}°C\nSwitched to emergency mode.'
        if runtime_state.high_temp_hits >= runtime_state.shutdown_hits_required:
            notice += f'\nConsecutive high-temperature count:{runtime_state.high_temp_hits}/{runtime_state.shutdown_hits_required}, The bot will shut itself down.'
            should_shutdown = True
        else:
            notice += f'\nConsecutive high-temperature count:{runtime_state.high_temp_hits}/{runtime_state.shutdown_hits_required}.'
    elif cpu_temp >= runtime_state.emergency_temp:
        runtime_state.mode = 'emergency'
        runtime_state.high_temp_hits = 0
        runtime_state.reason = f'CPU temperature {cpu_temp:.1f}°C exceeded emergency threshold'
        save_runtime_state(runtime_state)
        notice = f' CPU temperature {cpu_temp:.1f}°C, automatically switched to emergency mode.'
    elif cpu_temp >= runtime_state.eco_temp and runtime_state.mode == 'normal':
        runtime_state.mode = 'eco'
        runtime_state.high_temp_hits = 0
        runtime_state.reason = f'CPU temperature {cpu_temp:.1f}°C exceeded eco threshold'
        save_runtime_state(runtime_state)
        notice = f' CPU temperature {cpu_temp:.1f}°C, automatically switched to eco mode.'
    elif cpu_temp < runtime_state.eco_temp - TEMP_AUTO_RECOVER_MARGIN and runtime_state.mode in {'eco', 'emergency'}:
        runtime_state.high_temp_hits = 0
        current_reason = str(getattr(runtime_state, 'reason', '') or '')
        was_auto_temperature_mode = (
            'CPU temperature' in current_reason
            or 'high temperature' in current_reason
            or 'exceeded eco' in current_reason
            or 'exceeded emergency' in current_reason
            or 'exceeded shutdown' in current_reason
        )

        if was_auto_temperature_mode:
            old_mode = runtime_state.mode
            runtime_state.mode = 'normal'
            runtime_state.reason = f'CPU temperature {cpu_temp:.1f}°C fell below the recovery threshold; automatically restored normal mode'
            save_runtime_state(runtime_state)
            notice = f' CPU temperature {cpu_temp:.1f}°C has decreased; restored from {old_mode} to normal mode.'
        else:
            # If manually switched to eco/emergency, do not override the admin-selected mode.
            save_runtime_state(runtime_state)
    if notice and channel and hasattr(channel, 'send'):
        await channel.send(notice[:1900])
    return (notice, should_shutdown)

async def pc_status_loop() -> None:
    await bot.wait_until_ready()
    global PC_STATUS_ENABLED
    while not bot.is_closed():
        try:
            channel = await _get_channel_by_id(PC_STATUS_CHANNEL_ID) if _to_int_or_none(PC_STATUS_CHANNEL_ID) else None
            if PC_STATUS_ENABLED and channel and hasattr(channel, 'send'):
                _, should_shutdown = await apply_temperature_guard(channel)
                if should_shutdown:
                    await bot.close()
                    return
                report = await asyncio.to_thread(format_system_report)
                await channel.send(report[:1900])
            elif runtime_state.auto_guard_enabled:
                _, should_shutdown = await apply_temperature_guard(None)
                if should_shutdown:
                    await bot.close()
                    return
        except Exception as exc:
            print(f' Scheduled PC status report failed:{exc}')
        await asyncio.sleep(max(60, PC_STATUS_INTERVAL_MINUTES * 60))

def ensure_pc_status_task() -> None:
    global _pc_status_task
    if _pc_status_task is None or _pc_status_task.done():
        _pc_status_task = bot.loop.create_task(pc_status_loop())

@bot.event
async def on_ready() -> None:
    await sync_commands_once()
    ensure_pc_status_task()
    print(f' Bot online:{bot.user}')
    if USE_MESSAGE_CONTENT:
        print(' USE_MESSAGE_CONTENT=true:normal-message moderation is enabled.')
    else:
        print('ℹ USE_MESSAGE_CONTENT=false:slash commands only; normal-message moderation is disabled.')
    if PC_STATUS_ENABLED:
        print(f' PC_STATUS_ENABLED=true:every {PC_STATUS_INTERVAL_MINUTES} minreportPCStatus.')

@bot.event
async def on_message(message: discord.message) -> None:
    if message.author.bot:
        return
    if message.content.startswith('!'):
        await bot.process_commands(message)
        return
    if not USE_MESSAGE_CONTENT or not message.guild or (not message.content.strip()):
        return
    admin = isinstance(message.author, discord.Member) and is_admin_member(message.author)
    mentioned_users = [u for u in message.mentions if not getattr(u, 'bot', False)]
    result = router.evaluate_message(user_id=str(message.author.id), display_name=getattr(message.author, 'display_name', str(message.author)), content=message.content, channel_id=str(message.channel.id), message_id=str(message.id), message_url=message.jump_url, guild_id=str(message.guild.id), is_admin=admin, apply_penalty=not admin, mentioned_user_count=len(mentioned_users), mentioned_user_ids=[str(u.id) for u in mentioned_users])
    if result.ok:
        action_notes: list[str] = []
        penalty_applied = bool(result.data.get('penalty_applied'))
        if admin:
            action_notes.append('Admin/moderator message: report only; do not add warning role or timeout.')
        elif not penalty_applied:
            action_notes.append('This case is report-only: no warning role or timeout was automatically applied.')
        elif isinstance(message.author, discord.Member):
            role_note = await add_warning_role(message.author)
            action_notes.append(role_note)
            if result.data.get('should_auto_timeout'):
                if AUTO_TIMEOUT_ENABLED:
                    try:
                        await message.author.timeout(timedelta(minutes=AUTO_TIMEOUT_MINUTES), reason=f"Repeated moderation triggers in a short window:{result.data.get('case_id')}")
                        router.record_action('auto_timeout_user', 'BOT', str(message.author.id), f"case={result.data.get('case_id')}; minutes={AUTO_TIMEOUT_MINUTES}", dry_run=False)
                        action_notes.append(f'Automatically timed out for {AUTO_TIMEOUT_MINUTES} min.')
                        if AUTO_MOD_AWAY_ENABLED and AUTO_MOD_AUTOCLOSE_ON_TIMEOUT:
                            resolved = router.case_resolve(str(result.data.get('case_id')), 'AUTO_MOD_AWAY', f'auto_timeout_{AUTO_TIMEOUT_MINUTES}m', 'Away mode: auto-closed after automatic short timeout')
                            if resolved.ok:
                                result.data.update(resolved.data.get('case', {}))
                                action_notes.append('Away mode automatically closed the case.')
                    except Exception as exc:
                        action_notes.append(f'Auto-timeout attempt failed:{exc}')
                else:
                    action_notes.append('AUTO_TIMEOUT_ENABLED=false:Repeated-trigger threshold reached, but report-only because auto-timeout is disabled.')
        try:
            await send_report(message, result, action_notes)
        except Exception as exc:
            print(f' Report failed:{exc}')
        if PUBLIC_WARNING and (not admin) and result.ok:
            recent_count = int(result.data.get('recent_count', 0) or 0)
            auto_count = int(result.data.get('auto_timeout_count', 0) or 0)
            should_timeout = bool(result.data.get('should_auto_timeout'))

            if should_timeout and AUTO_TIMEOUT_ENABLED:
                public_msg = (
                    f'{message.author.mention}  was timed out due to repeated moderation triggers in a short window,'
                    f'timed out for {AUTO_TIMEOUT_MINUTES} min.'
                )
            elif bool(result.data.get('final_warning')) and AUTO_TIMEOUT_ENABLED:
                public_msg = (
                    f'{message.author.mention} Final warning: please stop this behavior;'
                    f'another trigger may result in a short timeout {AUTO_TIMEOUT_MINUTES} min.'
                )
            elif penalty_applied and AUTO_TIMEOUT_ENABLED and auto_count > 1:
                remain_hits = max(1, auto_count - recent_count)
                public_msg = (
                    f'{message.author.mention} please watch Your language;'
                    f'another {remain_hits} trigger(s) may result in a short timeout of {AUTO_TIMEOUT_MINUTES} min.'
                )
            else:
                public_msg = f'{message.author.mention} please watch Your language;the event has been sent for moderator review.'

            await message.channel.send(public_msg[:1900], delete_after=10)
        return
    if bot.user and bot.user in message.mentions:
        if not is_ai_enabled(runtime_state):
            await message.reply(f' Bot is currently in `{runtime_state.mode}` mode, AI replies and memory are paused; only warning and report features remain.', delete_after=10)
            return
        prompt = message.content
        prompt = prompt.replace(f'<@{bot.user.id}>', '')
        prompt = prompt.replace(f'<@!{bot.user.id}>', '')
        prompt = prompt.strip()
        if not prompt:
            await message.reply('You can ask me directly or use `/ai`.')
            return
        remain = _ai_cooldown_remaining(
            str(message.author.id),
            AI_COMMAND_COOLDOWN_SECONDS,
            AI_LAST_USED,
        )
        if remain > 0:
            await message.reply(_ai_cooldown_message(remain), delete_after=10)
            return
        _mark_ai_used(
            str(message.author.id),
            AI_COMMAND_COOLDOWN_SECONDS,
            AI_LAST_USED,
        )
        thinking = await message.reply(' Thinking...')
        reply = await asyncio.to_thread(ask_ollama, prompt, str(message.author.id), message.author.display_name)
        await thinking.edit(content=reply[:1900])
        try:
            record_ai_interaction(user_id=str(message.author.id), display_name=message.author.display_name, guild_id=str(message.guild.id), channel_id=str(message.channel.id), kind='mention_ai', prompt=prompt, reply=reply)
        except Exception as exc:
            print(f' Failed to save AI interaction record:{exc}')
        return
MUSIC_RUNTIME: dict[int, dict] = {}

def _music_state(guild_id: int) -> dict:
    state = MUSIC_RUNTIME.setdefault(guild_id, {'queue': [], 'current': None, 'text_channel_id': None, 'starter_id': None, 'owner_id': None, 'volume': MUSIC_DEFAULT_VOLUME, 'loop_mode': 'none', 'last_queue': [], '_skip_requested': False, '_stop_requested': False})
    state.setdefault('volume', MUSIC_DEFAULT_VOLUME)
    state.setdefault('loop_mode', 'none')
    state.setdefault('last_queue', [])
    state.setdefault('_skip_requested', False)
    state.setdefault('_stop_requested', False)
    return state

def _music_upload_channel_ok(interaction: discord.Interaction) -> bool:
    channel_id = _to_int_or_none(MUSIC_UPLOAD_CHANNEL_ID)
    if not channel_id:
        return True
    return bool(interaction.channel and interaction.channel.id == channel_id)

def _format_track_line(track: dict, index: int | None=None) -> str:
    prefix = f'{index}. ' if index is not None else ''
    size_mb = int(track.get('size_bytes', 0)) / (1024 * 1024)
    return f"{prefix}`{track.get('track_id')}` | {track.get('name')} | {size_mb:.1f}MB | plays {track.get('play_count', 0)} times"

def _music_voice_status(guild: discord.Guild) -> str:
    vc = guild.voice_client
    if not vc or not vc.is_connected():
        return 'Not connected'
    if vc.is_paused():
        return 'Paused'
    if vc.is_playing():
        return 'Playing'
    return 'Connected but not playing'

def _music_current_line(guild_id: int) -> str:
    state = _music_state(guild_id)
    current = state.get('current')
    if not current:
        return 'Current track: none'
    return 'Current track:' + _format_track_line(current)

def _music_volume_percent(guild_id: int) -> int:
    state = _music_state(guild_id)
    try:
        return int(round(float(state.get('volume', MUSIC_DEFAULT_VOLUME)) * 100))
    except Exception:
        return int(round(MUSIC_DEFAULT_VOLUME * 100))

def _music_loop_mode(guild_id: int) -> str:
    state = _music_state(guild_id)
    mode = str(state.get('loop_mode', 'none')).lower()
    return mode if mode in {'none', 'single', 'queue'} else 'none'

def _music_apply_live_volume(guild: discord.Guild, volume: float) -> bool:
    vc = guild.voice_client
    if not vc or not vc.source:
        return False
    if isinstance(vc.source, discord.PCMVolumeTransformer):
        vc.source.volume = volume
        return True
    return False

def _music_is_admin_or_starter(interaction: discord.Interaction) -> bool:
    if require_manage_messages(interaction):
        return True
    if not interaction.guild:
        return False
    state = _music_state(interaction.guild.id)
    return str(interaction.user.id) == str(state.get('starter_id', ''))

async def _music_send_to_text(guild_id: int, content: str) -> None:
    state = _music_state(guild_id)
    channel_id = state.get('text_channel_id')
    if not channel_id:
        return
    channel = bot.get_channel(int(channel_id))
    if channel and hasattr(channel, 'send'):
        try:
            await channel.send(content[:1900])
        except Exception:
            pass

async def _music_play_next(guild_id: int, error: Exception | None=None) -> None:
    state = _music_state(guild_id)
    guild = bot.get_guild(guild_id)
    if guild is None:
        return
    if error:
        await _music_send_to_text(guild_id, f' Playback error:{error}')
    voice_client = guild.voice_client
    if voice_client is None or not voice_client.is_connected():
        state['current'] = None
        return
    if state.get('_stop_requested'):
        state['_stop_requested'] = False
        state['_skip_requested'] = False
        state['queue'] = []
        state['current'] = None
        return
    queue: list[dict] = state.get('queue', [])
    loop_mode = _music_loop_mode(guild_id)
    current = state.get('current')
    skip_requested = bool(state.get('_skip_requested'))
    if skip_requested:
        state['_skip_requested'] = False
    elif loop_mode == 'single' and current:
        queue.insert(0, current)
    if not queue and loop_mode == 'queue':
        last_queue = [dict(t) for t in state.get('last_queue', []) if Path(str(t.get('path', ''))).exists()]
        if last_queue:
            queue.extend(last_queue)
    if not queue:
        state['current'] = None
        await _music_send_to_text(guild_id, ' Queue finished.')
        if MUSIC_LEAVE_AFTER_QUEUE:
            try:
                await voice_client.disconnect(force=False)
            except Exception:
                pass
        return
    track = queue.pop(0)
    state['current'] = track
    path = Path(str(track.get('path', '')))
    if not path.exists():
        await _music_send_to_text(guild_id, f" Track file not found; skipped:{track.get('name')}")
        await _music_play_next(guild_id)
        return
    try:
        raw_source = discord.FFmpegPCMAudio(str(path), executable=FFMPEG_EXE, before_options='-nostdin', options='-vn -loglevel warning')
        source = discord.PCMVolumeTransformer(raw_source, volume=float(state.get('volume', MUSIC_DEFAULT_VOLUME)))
    except Exception as exc:
        await _music_send_to_text(guild_id, f' Could not create playback source; please confirm ffmpeg is installed:{exc}')
        await _music_play_next(guild_id)
        return
    try:
        voice_client.play(source, after=lambda exc: bot.loop.call_soon_threadsafe(asyncio.create_task, _music_play_next(guild_id, exc)))
        increment_play_count(str(track.get('owner_id')), str(track.get('track_id')))
        await _music_send_to_text(guild_id, f" Now playing:`{track.get('track_id')}` | **{track.get('name')}**\nOwner:{track.get('owner_display_name', track.get('owner_id'))}\nVolume:{_music_volume_percent(guild_id)}% | Loop:{_music_loop_mode(guild_id)}")
    except Exception as exc:
        await _music_send_to_text(guild_id, f' Playback failed; skipped:{exc}')
        await _music_play_next(guild_id)

async def _connect_to_member_voice(interaction: discord.Interaction) -> discord.VoiceClient | None:
    if not isinstance(interaction.user, discord.Member):
        await interaction.followup.send(' This command can only be used inside a server.', ephemeral=True)
        return None
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.followup.send(' You need to join a voice channel first.', ephemeral=True)
        return None
    voice_channel = interaction.user.voice.channel
    voice_client = interaction.guild.voice_client if interaction.guild else None
    try:
        if voice_client and voice_client.is_connected():
            if voice_client.channel.id != voice_channel.id:
                await voice_client.move_to(voice_channel)
        else:
            voice_client = await voice_channel.connect(self_deaf=True)
        return voice_client
    except Exception as exc:
        await interaction.followup.send(f' Could not join voice channel:{exc}\nPlease make sure the bot has Connect / Speak permissions and PyNaCl is installed.', ephemeral=True)
        return None

@bot.tree.command(name='music_add', description='Add an audio file to Your personal music library')
@app_commands.describe(name='Song name', file='Audio attachment: mp3 / wav / flac / ogg / m4a', confirm='Confirm that this audio is Yours, licensed, or legal to play', owner='Admins can specify the owner; members can only add to their own library')
async def music_add(interaction: discord.Interaction, name: str, file: discord.Attachment, confirm: bool=True, owner: discord.Member | None=None, public: bool=False) -> None:
    if runtime_state.mode == 'emergency':
        await interaction.response.send_message('The bot is currently in emergency mode. Adding music is paused.', ephemeral=not public)
        return
    if not _music_upload_channel_ok(interaction) and (not require_manage_messages(interaction)):
        await interaction.response.send_message(' Please use this command in the configured music upload channel.', ephemeral=not public)
        return
    if not confirm:
        await interaction.response.send_message('dry-run: not added to the library. To add it, use `confirm:true` to confirm the audio is legal to play on this server.', ephemeral=not public)
        return
    target = owner or interaction.user
    if owner and owner.id != interaction.user.id and (not require_manage_messages(interaction)):
        await interaction.response.send_message(' Only admins can add music for another user.', ephemeral=not public)
        return
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        await interaction.response.send_message(f" Unsupported format:`{ext or 'no extension'}`.Allowed:{', '.join(sorted(ALLOWED_EXTENSIONS))}", ephemeral=not public)
        return
    max_bytes = MUSIC_MAX_FILE_MB * 1024 * 1024
    if file.size and file.size > max_bytes:
        await interaction.response.send_message(f' File is too large. Limit: {MUSIC_MAX_FILE_MB}MB.', ephemeral=not public)
        return
    await interaction.response.defer(ephemeral=not public)
    tmp_dir = MUSIC_FILES_DIR / '_tmp'
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f'upload_{interaction.id}{ext}'
    try:
        await file.save(tmp_path)
        track = add_track(owner_id=str(target.id), owner_display_name=getattr(target, 'display_name', str(target)), uploader_id=str(interaction.user.id), uploader_display_name=getattr(interaction.user, 'display_name', str(interaction.user)), name=name, original_filename=file.filename, source_temp_path=str(tmp_path), size_bytes=int(file.size or tmp_path.stat().st_size), message_url='', max_tracks_per_user=MUSIC_MAX_TRACKS_PER_USER)
    except Exception as exc:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass
        await interaction.followup.send(f' Failed to add to library:{exc}', ephemeral=not public)
        return
    await interaction.followup.send(f" Added to library:`{track['track_id']}` | **{track['name']}**\nOwner:{getattr(target, 'display_name', target)}\nReminder:Uploader must confirm the audio is original, licensed, or legally playable publicly.", ephemeral=not public)

@bot.tree.command(name='music_list', description='View Your personal music library')
@app_commands.describe(user='Admins can view another user; members can only view themselves')
async def music_list(interaction: discord.Interaction, user: discord.Member | None=None, public: bool=False) -> None:
    target = user or interaction.user
    if user and user.id != interaction.user.id and (not require_manage_messages(interaction)):
        await interaction.response.send_message(' Only admins can view another user library.', ephemeral=not public)
        return
    summary = library_summary(str(target.id), getattr(target, 'display_name', str(target)))
    tracks = summary['tracks']
    if not tracks:
        await interaction.response.send_message(f" {getattr(target, 'display_name', target)} library has no music yet.", ephemeral=not public)
        return
    lines = [f" **{getattr(target, 'display_name', target)} personal music library**", f"Count:{summary['track_count']}/{MUSIC_MAX_TRACKS_PER_USER} | Size: about {summary['total_mb']}MB", '']
    for i, track in enumerate(tracks[:25], start=1):
        lines.append(_format_track_line(track, i))
    await interaction.response.send_message('\n'.join(lines)[:1900], ephemeral=not public)

@bot.tree.command(name='music_remove', description='Remove a track from Your personal music library')
@app_commands.describe(track_id='Track ID, for example T1234ABCD', owner='Admins can specify owner; members can only remove their own tracks')
async def music_remove(interaction: discord.Interaction, track_id: str, owner: discord.Member | None=None, public: bool=False) -> None:
    target = owner or interaction.user
    if owner and owner.id != interaction.user.id and (not require_manage_messages(interaction)):
        await interaction.response.send_message(' Only admins can delete another user tracks.', ephemeral=not public)
        return
    removed = remove_track(str(target.id), track_id)
    if not removed:
        await interaction.response.send_message(' Track not found.', ephemeral=not public)
        return
    await interaction.response.send_message(f" Removed:`{removed.get('track_id')}` | **{removed.get('name')}**", ephemeral=not public)

@bot.tree.command(name='go_music', description='Make the bot join Your voice channel and play a personal library')
@app_commands.describe(owner='Admins can play a specified user library; members can only play their own', mode='sequential / shuffle')
async def go_music(interaction: discord.Interaction, owner: discord.Member | None=None, mode: str='sequential', public: bool=False) -> None:
    try:
        await interaction.response.defer(ephemeral=not public, thinking=True)
    except discord.NotFound:
        print('/go_music interaction expired; could not defer.')
        return
    if runtime_state.mode != 'normal':
        await interaction.followup.send(f' Bot is currently in `{runtime_state.mode}` mode, new music playback is paused.', ephemeral=not public)
        return
    if not interaction.guild:
        await interaction.followup.send(' This command can only be used inside a server.', ephemeral=not public)
        return
    target = owner or interaction.user
    if owner and owner.id != interaction.user.id and (not require_manage_messages(interaction)):
        await interaction.followup.send(' Only admins can play another user library.', ephemeral=not public)
        return
    state = _music_state(interaction.guild.id)
    voice_client = interaction.guild.voice_client
    if voice_client and (voice_client.is_playing() or voice_client.is_paused()) and (not _music_is_admin_or_starter(interaction)):
        await interaction.followup.send(' A queue is already playing. Only the starter or admins can switch queues.', ephemeral=not public)
        return
    tracks = list_tracks(str(target.id), getattr(target, 'display_name', str(target)))
    tracks = [t for t in tracks if Path(str(t.get('path', ''))).exists()]
    if not tracks:
        await interaction.followup.send(' This library has no playable music.', ephemeral=not public)
        return
    mode_key = mode.strip().lower()
    if mode_key in {'shuffle', 'random', 'shuffle'}:
        random.shuffle(tracks)
        mode_label = 'shuffle'
    else:
        mode_label = 'sequential'
    voice_client = await _connect_to_member_voice(interaction)
    if voice_client is None:
        return
    state['queue'] = [dict(t) for t in tracks]
    state['last_queue'] = [dict(t) for t in tracks]
    state['current'] = None
    state['text_channel_id'] = interaction.channel.id if interaction.channel else None
    state['starter_id'] = str(interaction.user.id)
    state['owner_id'] = str(target.id)
    state['_skip_requested'] = False
    state['_stop_requested'] = False
    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()
    await interaction.followup.send(f" Loaded **{getattr(target, 'display_name', target)}** library, total {len(tracks)} tracks , mode: {mode_label}.", ephemeral=not public)
    if not voice_client.is_playing():
        await _music_play_next(interaction.guild.id)

@bot.tree.command(name='music_queue', description='View the current playback queue')
async def music_queue(interaction: discord.Interaction, public: bool=False) -> None:
    if not interaction.guild:
        await interaction.response.send_message(' This command can only be used inside a server.', ephemeral=not public)
        return
    state = _music_state(interaction.guild.id)
    current = state.get('current')
    queue = state.get('queue', [])
    lines = [' **Current music queue**']
    lines.append(f'Voice status:{_music_voice_status(interaction.guild)}')
    lines.append(f'Volume:{_music_volume_percent(interaction.guild.id)}% | Loop:{_music_loop_mode(interaction.guild.id)}')
    if current:
        lines.append('Now playing:' + _format_track_line(current))
    else:
        lines.append('Now playing: none')
    if queue:
        lines.append('\nUp next:')
        for i, track in enumerate(queue[:10], start=1):
            lines.append(_format_track_line(track, i))
        if len(queue) > 10:
            lines.append(f'...more {len(queue) - 10} tracks')
    else:
        lines.append('\nQueue: empty')
    await interaction.response.send_message('\n'.join(lines)[:1900], ephemeral=not public)

@bot.tree.command(name='music_skip', description='Skip the current track; available to starter or admins')
async def music_skip(interaction: discord.Interaction, public: bool=False) -> None:
    if not interaction.guild:
        await interaction.response.send_message(' This command can only be used inside a server.', ephemeral=not public)
        return
    if not _music_is_admin_or_starter(interaction):
        await interaction.response.send_message(' Only the current starter or admins can skip tracks.', ephemeral=not public)
        return
    voice_client = interaction.guild.voice_client
    if not voice_client or not voice_client.is_connected():
        await interaction.response.send_message(' Bot is not connected to a voice channel.', ephemeral=not public)
        return
    if not (voice_client.is_playing() or voice_client.is_paused()):
        state = _music_state(interaction.guild.id)
        state['current'] = None
        await interaction.response.send_message(' No music is currently playing; current track state has been cleared.', ephemeral=not public)
        return
    state = _music_state(interaction.guild.id)
    state['_skip_requested'] = True
    voice_client.stop()
    await interaction.response.send_message('⏭ Skipped the current track.', ephemeral=not public)

@bot.tree.command(name='music_stop', description='Stop music and clear the queue; available to starter or admins')
async def music_stop(interaction: discord.Interaction, public: bool=False) -> None:
    if not interaction.guild:
        await interaction.response.send_message(' This command can only be used inside a server.', ephemeral=not public)
        return
    if not _music_is_admin_or_starter(interaction):
        await interaction.response.send_message(' Only the current starter or admins can stop music.', ephemeral=not public)
        return
    state = _music_state(interaction.guild.id)
    state['queue'] = []
    state['current'] = None
    state['_stop_requested'] = True
    state['_skip_requested'] = False
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_connected():
        try:
            if voice_client.is_playing() or voice_client.is_paused():
                voice_client.stop()
            await voice_client.disconnect(force=False)
        except Exception:
            pass
    await interaction.response.send_message('⏹ Stopped music and cleared the queue.', ephemeral=not public)

@bot.tree.command(name='music_pause', description='Pause current music; available to starter or admins')
async def music_pause(interaction: discord.Interaction, public: bool=False) -> None:
    if not interaction.guild:
        await interaction.response.send_message(' This command can only be used inside a server.', ephemeral=not public)
        return
    if not _music_is_admin_or_starter(interaction):
        await interaction.response.send_message(' Only the current starter or admins can pause music.', ephemeral=not public)
        return
    vc = interaction.guild.voice_client
    state = _music_state(interaction.guild.id)
    current = state.get('current')
    if not vc or not vc.is_connected():
        state['current'] = None
        await interaction.response.send_message(' Bot is not connected to a voice channel.', ephemeral=not public)
        return
    if vc.is_paused():
        await interaction.response.send_message('⏸ Music is already paused.', ephemeral=not public)
        return
    if vc.is_playing():
        vc.pause()
        await interaction.response.send_message(f'⏸ Music paused.\n{_music_current_line(interaction.guild.id)}', ephemeral=not public)
        return
    if current:
        await interaction.response.send_message('Bot has a current track recorded, but Discord voice is not playing. Use `/music_sync`, `/music_skip`, or `/music_stop` to reset state.', ephemeral=not public)
        return
    await interaction.response.send_message(' No music is currently playing.', ephemeral=not public)

@bot.tree.command(name='music_resume', description='Resume paused music; available to starter or admins')
async def music_resume(interaction: discord.Interaction, public: bool=False) -> None:
    if not interaction.guild:
        await interaction.response.send_message(' This command can only be used inside a server.', ephemeral=not public)
        return
    if not _music_is_admin_or_starter(interaction):
        await interaction.response.send_message(' Only the current starter or admins can resume music.', ephemeral=not public)
        return
    vc = interaction.guild.voice_client
    if not vc or not vc.is_connected():
        await interaction.response.send_message(' Bot is not connected to a voice channel.', ephemeral=not public)
        return
    if vc.is_paused():
        vc.resume()
        await interaction.response.send_message(f'▶ Playback resumed.\n{_music_current_line(interaction.guild.id)}', ephemeral=not public)
        return
    if vc.is_playing():
        await interaction.response.send_message('▶ Music is already playing.', ephemeral=not public)
        return
    await interaction.response.send_message(' There is no paused music to resume.', ephemeral=not public)

@bot.tree.command(name='music_now', description='Show the current track')
async def music_now(interaction: discord.Interaction, public: bool=False) -> None:
    if not interaction.guild:
        await interaction.response.send_message(' This command can only be used inside a server.', ephemeral=not public)
        return
    state = _music_state(interaction.guild.id)
    queue = state.get('queue', [])
    lines = [' **Current playback status**', f'Voice status:{_music_voice_status(interaction.guild)}', _music_current_line(interaction.guild.id), f'Queue remaining:{len(queue)} tracks', f'Volume:{_music_volume_percent(interaction.guild.id)}%', f'Loop:{_music_loop_mode(interaction.guild.id)}']
    await interaction.response.send_message('\n'.join(lines)[:1900], ephemeral=not public)

@bot.tree.command(name='music_volume', description='Set music volume 0-200; starter or admins only')
@app_commands.describe(volume='Volume percentage, recommended 30-100, range 0-200')
async def music_volume(interaction: discord.Interaction, volume: app_commands.Range[int, 0, 200], public: bool=False) -> None:
    if not interaction.guild:
        await interaction.response.send_message(' This command can only be used inside a server.', ephemeral=not public)
        return
    if not _music_is_admin_or_starter(interaction):
        await interaction.response.send_message(' Only the current starter or admins can change volume.', ephemeral=not public)
        return
    state = _music_state(interaction.guild.id)
    state['volume'] = float(volume) / 100.0
    live = _music_apply_live_volume(interaction.guild, state['volume'])
    note = 'Applied to current playback.' if live else 'No active source to apply now; it will apply to the next track.'
    await interaction.response.send_message(f' Volumeset to {volume}%.{note}', ephemeral=not public)

@bot.tree.command(name='music_loop', description='Set loop mode: none / single / queue')
@app_commands.describe(mode='none / single / queue')
async def music_loop(interaction: discord.Interaction, mode: str='none', public: bool=False) -> None:
    if not interaction.guild:
        await interaction.response.send_message(' This command can only be used inside a server.', ephemeral=not public)
        return
    if not _music_is_admin_or_starter(interaction):
        await interaction.response.send_message(' Only the current starter or admins can set loop mode.', ephemeral=not public)
        return
    mode_key = mode.strip().lower()
    aliases = {'off': 'none', 'off': 'none', 'none': 'none', 'single': 'single', 'single': 'single', 'queue': 'queue', 'queue': 'queue'}
    mode_key = aliases.get(mode_key, mode_key)
    if mode_key not in {'none', 'single', 'queue'}:
        await interaction.response.send_message(' Loop mode must be `none`、`single`、`queue`.', ephemeral=not public)
        return
    state = _music_state(interaction.guild.id)
    state['loop_mode'] = mode_key
    await interaction.response.send_message(f' Loopmodeset to `{mode_key}`.', ephemeral=not public)

@bot.tree.command(name='music_clear', description='Clear music queue; admin only; does not stop current track')
@app_commands.default_permissions(manage_messages=True)
async def music_clear(interaction: discord.Interaction, public: bool=False) -> None:
    if not interaction.guild:
        await interaction.response.send_message(' This command can only be used inside a server.', ephemeral=not public)
        return
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.', ephemeral=not public)
        return
    state = _music_state(interaction.guild.id)
    removed = len(state.get('queue', []))
    state['queue'] = []
    await interaction.response.send_message(f' Queue cleared; removed {removed} tracks; current track will not be stopped.', ephemeral=not public)

@bot.tree.command(name='music_sync', description='Sync music playback state; starter or admins only')
async def music_sync(interaction: discord.Interaction, public: bool=False) -> None:
    if not interaction.guild:
        await interaction.response.send_message(' This command can only be used inside a server.', ephemeral=not public)
        return
    if not _music_is_admin_or_starter(interaction):
        await interaction.response.send_message(' Only the current starter or admins can sync music state.', ephemeral=not public)
        return
    state = _music_state(interaction.guild.id)
    vc = interaction.guild.voice_client
    if not vc or not vc.is_connected():
        state['current'] = None
        state['queue'] = []
        await interaction.response.send_message(' Bot is not connected; cleared playback state.', ephemeral=not public)
        return
    if vc.is_playing() or vc.is_paused():
        await interaction.response.send_message(f' Discord voice playback state is normal:{_music_voice_status(interaction.guild)}', ephemeral=not public)
        return
    current = state.get('current')
    if current:
        state['current'] = None
        await interaction.response.send_message(f" Detected out-of-sync state; cleared current track:`{current.get('track_id')}` | {current.get('name')}", ephemeral=not public)
        return
    await interaction.response.send_message(' No playback state needs syncing.', ephemeral=not public)

@bot.tree.command(name='tool_list', description='List current MCP-like tools')
@app_commands.default_permissions(manage_messages=True)
async def tool_list(interaction: discord.Interaction, public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.', ephemeral=not public)
        return
    result = router.list_tools()
    await interaction.response.send_message(format_tool_result(result) + '\n```' + '\n'.join(result.data['tools']) + '```', ephemeral=not public)

@bot.tree.command(name='status', description='View bot and server status')
async def status(interaction: discord.Interaction, public: bool=False) -> None:
    guild = interaction.guild
    result = router.server_status(guild_name=guild.name if guild else 'DM', member_count=guild.member_count if guild else None, bot_name=str(bot.user))
    data = result.data
    msg = f"{format_tool_result(result)}\nServer:{data['guild_name']}\nMembers:{data['member_count']}\nTracked users:{data['tracked_users']}\nAction logs:{data['logged_actions']}\nPending cases:{data['pending_cases']}\nSafe phrases:{data['safe_phrases']}\nRule terms:{data['rule_terms']}\nBot mode:{runtime_state.mode}"
    await interaction.response.send_message(msg, ephemeral=not public)

@bot.tree.command(name='my_warnings', description='View Your warning count and penalty reminder')
async def my_warnings(interaction: discord.Interaction, public: bool=False) -> None:
    result = router.get_user_status(str(interaction.user.id), interaction.user.display_name)
    data = result.data
    await interaction.response.send_message(f'**My warning status**\n{warning_reminder_text(data)}', ephemeral=not public)

@bot.tree.command(name='my_profile', description='View Your interaction summary; set ai=true to generate AI insight')
@app_commands.describe(ai='Whether to generate AI interaction insight; per-user cooldown applies', days='Analyze the last N days, default 7', include_history='Whether to read a small number of recent Discord messages')
async def my_profile(interaction: discord.Interaction, ai: bool=False, days: app_commands.Range[int, 1, 14]=MY_PROFILE_AI_DAYS, include_history: bool=True, public: bool=False) -> None:
    target = interaction.user
    status = router.get_user_status(str(target.id), target.display_name).data
    profile = get_profile(str(target.id), target.display_name)
    if not ai:
        await interaction.response.send_message(f'**My interaction summary**\n{profile_basic_text(status, profile)}\n\nUse `/my_profile ai:true` to generate an AI insight.', ephemeral=not public)
        return
    await interaction.response.defer(ephemeral=not public, thinking=True)
    text, _ = await generate_user_insight(interaction=interaction, target=target, days=int(days), is_self=True, pro=False, use_history=bool(include_history), refresh=False, cooldown_minutes=MY_PROFILE_AI_COOLDOWN_MINUTES, per_channel_limit=MY_PROFILE_HISTORY_PER_CHANNEL, max_messages=MY_PROFILE_MAX_MESSAGES)
    await interaction.followup.send(text[:1900], ephemeral=not public)

@bot.tree.command(name='user_profile', description='Admin: view a user moderation summary without AI')
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(user='user to view')
async def user_profile(interaction: discord.Interaction, user: discord.Member, public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.', ephemeral=not public)
        return
    status = router.get_user_status(str(user.id), user.display_name).data
    profile = get_profile(str(user.id), user.display_name)
    await interaction.response.send_message(f'**User moderation summary:{user.mention}**\n{profile_basic_text(status, profile)}', ephemeral=not public)

@bot.tree.command(name='user_insight', description='Admin: generate AI insight for a user; pro can scan Discord history')
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(user='user to analyze', days='Analyze the last N days, max 30', pro='Enable Pro scan: read recent messages from bot-visible channels', confirm='When pro=true, confirm=true is required to scan Discord history', refresh='Ignore cache and regenerate; admin only')
async def user_insight(interaction: discord.Interaction, user: discord.Member, days: app_commands.Range[int, 1, 30]=7, pro: bool=False, confirm: bool=False, refresh: bool=False, public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.', ephemeral=not public)
        return
    if pro and (not confirm):
        await interaction.response.send_message('dry-run: Pro mode scans text channels visible to the bot, filters recent messages from the target user, then sends them to AI for summary. To execute, use `confirm:true`.', ephemeral=not public)
        return
    await interaction.response.defer(ephemeral=not public, thinking=True)
    text, _ = await generate_user_insight(interaction=interaction, target=user, days=int(days), is_self=False, pro=bool(pro), use_history=bool(pro), refresh=bool(refresh), cooldown_minutes=USER_INSIGHT_COOLDOWN_MINUTES, per_channel_limit=USER_INSIGHT_PRO_HISTORY_PER_CHANNEL if pro else MY_PROFILE_HISTORY_PER_CHANNEL, max_messages=USER_INSIGHT_PRO_MAX_MESSAGES if pro else MY_PROFILE_MAX_MESSAGES)
    await interaction.followup.send(f'target:{user.mention}\n' + text[:1850], ephemeral=not public)

@bot.tree.command(name='attention_set', description='Admin: set user attention level 0-5')
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(user='Target user', score='Attention level 0～5', reason='Reason')
async def attention_set_command(interaction: discord.Interaction, user: discord.Member, score: app_commands.Range[int, 0, 5], reason: str='', public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.', ephemeral=not public)
        return
    profile = set_attention(str(user.id), user.display_name, int(score), reason, str(interaction.user.id))
    await interaction.response.send_message(f" Set {user.mention} attention level:{format_attention(profile.get('attention_score', 0))}\nreason:{reason or 'No reason provided'}", ephemeral=not public)

@bot.tree.command(name='attention_clear', description='Admin: clear user attention level')
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(user='Target user', reason='Clear reason')
async def attention_clear_command(interaction: discord.Interaction, user: discord.Member, reason: str='', public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.', ephemeral=not public)
        return
    profile = clear_attention(str(user.id), user.display_name, str(interaction.user.id), reason)
    await interaction.response.send_message(f" Cleared {user.mention} attention level:{format_attention(profile.get('attention_score', 0))}", ephemeral=not public)

@bot.tree.command(name='anger', description='Query user status and warning records')
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(user='user to query; leave empty for Yourself')
async def anger(interaction: discord.Interaction, user: discord.Member | None=None, public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.Members should use `/my_warnings`.', ephemeral=not public)
        return
    target = user or interaction.user
    result = router.get_user_status(str(target.id), target.display_name)
    data = result.data
    msg = f"{format_tool_result(result)}\nanger:{data['anger']}/{data['anger_limit']}\nWarnings:{data['warning_count']}\ncases:{data['case_count']}\npending:{len(data['pending_cases'])}"
    await interaction.response.send_message(msg, ephemeral=not public)

@bot.tree.command(name='warn', description='Record a warning; increases state value but does not timeout')
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(user='Warned user', reason='Warning reason')
async def warn(interaction: discord.Interaction, user: discord.Member, reason: str, public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.', ephemeral=not public)
        return
    result = router.add_warning(str(user.id), user.display_name, str(interaction.user.id), reason)
    role_note = await add_warning_role(user)
    data = result.data
    msg = f"{format_tool_result(result)}\ntarget:{user.mention}\nreason:{reason}\nrole:{role_note}\nCurrent anger:{data['anger']}\nWarnings:{data['warning_count']}"
    await interaction.response.send_message(msg, ephemeral=not public)

@bot.tree.command(name='calm', description='Reset a user state')
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(user='user to reset; leave empty for Yourself')
async def calm(interaction: discord.Interaction, user: discord.Member | None=None, public: bool=False) -> None:
    target = user or interaction.user
    if target.id != interaction.user.id and (not require_manage_messages(interaction)):
        await interaction.response.send_message(' You can only reset Yourself; resetting another user requires Manage messages permission.', ephemeral=not public)
        return
    result = router.reset_user_state(str(target.id), target.display_name)
    reset_user_memory(str(target.id))
    role_note = ''
    if isinstance(target, discord.Member) and require_manage_messages(interaction):
        role_note = '\n' + await remove_warning_role(target)
    await interaction.response.send_message(format_tool_result(result) + role_note, ephemeral=not public)

@bot.tree.command(name='mod_suggest', description='Generate moderation suggestion based on state and reason; does not execute actions')
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(user='Target user', reason='Incident reason or message content')
async def mod_suggest(interaction: discord.Interaction, user: discord.Member, reason: str, public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.', ephemeral=not public)
        return
    await interaction.response.defer(ephemeral=not public)
    result = router.suggest_moderation_action(str(user.id), user.display_name, reason)
    llm_prompt = f'Summarize the following Discord moderation tool result as a short interview/demo suggestion. Do not pretend actions were executed; only provide suggestions.\nTool result:{result.to_dict()}'
    llm_reply = await asyncio.to_thread(ask_ollama, llm_prompt, str(interaction.user.id), interaction.user.display_name)
    if llm_reply.startswith('') or llm_reply.startswith(''):
        llm_reply = result.message
    msg = f"{format_tool_result(result)}\ntarget:{user.mention}\nreason:{reason}\nSuggested action:{result.data['suggested_action']}\nSuggested timeout duration:{result.data['suggested_timeout_minutes']} min\n\nAI summary:\n{llm_reply[:1200]}"
    await interaction.followup.send(msg, ephemeral=not public)

@bot.tree.command(name='punish', description='Admin-confirmed punishment; confirm=false is dry-run only')
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(user='Target user', minutes='Timeout minutes', reason='reason', confirm='Whether to execute for real')
async def punish(interaction: discord.Interaction, user: discord.Member, minutes: app_commands.Range[int, 1, 60], reason: str, confirm: bool=False, public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.', ephemeral=not public)
        return
    if not confirm:
        result = router.record_action('timeout_user', str(interaction.user.id), str(user.id), reason, dry_run=True)
        await interaction.response.send_message(f'{format_tool_result(result)}\ntarget:{user.mention}\nPlanned timeout:{minutes} min\nreason:{reason}', ephemeral=not public)
        return
    try:
        await user.timeout(timedelta(minutes=minutes), reason=reason)
        result = router.record_action('timeout_user', str(interaction.user.id), str(user.id), reason, dry_run=False)
        await interaction.response.send_message(f'{format_tool_result(result)}\nTimed out {user.mention} {minutes} min.reason:{reason}', ephemeral=not public)
    except Exception as exc:
        await interaction.response.send_message(f' Failed to timeout:{exc}', ephemeral=not public)

@bot.tree.command(name='safe_add', description='Add a safe phrase; the same phrase will not be treated as violation later')
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(phrase='Safe phrase', reason='Add reason')
async def safe_add(interaction: discord.Interaction, phrase: str, reason: str='', public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.', ephemeral=not public)
        return
    result = router.safe_add(phrase, str(interaction.user.id), reason)
    await interaction.response.send_message(format_tool_result(result), ephemeral=not public)

@bot.tree.command(name='safe_remove', description='Remove a safe phrase')
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(phrase='Safe phrase to remove')
async def safe_remove(interaction: discord.Interaction, phrase: str, public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.', ephemeral=not public)
        return
    result = router.safe_remove(phrase, str(interaction.user.id))
    await interaction.response.send_message(format_tool_result(result), ephemeral=not public)

@bot.tree.command(name='safe_list', description='View current safe phrases')
@app_commands.default_permissions(manage_messages=True)
async def safe_list(interaction: discord.Interaction, public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.', ephemeral=not public)
        return
    result = router.safe_list()
    phrases = result.data.get('safe_phrases', [])
    text = '\n'.join((f'- {p}' for p in phrases)) or 'No safe phrases currently.'
    await interaction.response.send_message(format_tool_result(result) + '\n' + text[:1500], ephemeral=not public)

@bot.tree.command(name='banword_add', description='Add a blocked term to rules; English matching is case-insensitive')
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(category='Category: blocked_terms / english_abuse_terms / sexual_terms / spam_terms', term='Term to add')
async def banword_add(interaction: discord.Interaction, category: str, term: str, public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.', ephemeral=not public)
        return
    result = router.rule_add(category, term, str(interaction.user.id))
    await interaction.response.send_message(format_tool_result(result), ephemeral=not public)

@bot.tree.command(name='banword_remove', description='Remove blocked term')
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(category='Category: blocked_terms / english_abuse_terms / sexual_terms / spam_terms', term='Term to remove')
async def banword_remove(interaction: discord.Interaction, category: str, term: str, public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.', ephemeral=not public)
        return
    result = router.rule_remove(category, term, str(interaction.user.id))
    await interaction.response.send_message(format_tool_result(result), ephemeral=not public)

@bot.tree.command(name='banword_list', description='View blocked-term rules')
@app_commands.default_permissions(manage_messages=True)
async def banword_list(interaction: discord.Interaction, public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.', ephemeral=not public)
        return
    result = router.rule_list()
    rules = result.data.get('rules', {})
    lines = []
    for category in ['blocked_terms', 'english_abuse_terms', 'sexual_terms', 'spam_terms', 'safe_phrases']:
        terms = rules.get(category, [])
        preview = ', '.join((str(t) for t in terms[:20])) or 'Failed'
        lines.append(f'**{category}**:{preview}')
    await interaction.response.send_message(format_tool_result(result) + '\n\n' + '\n'.join(lines)[:1800], ephemeral=not public)


@bot.tree.command(name='case_list', description='List cases; default is pending cases')
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(status='pending / resolved / ignored / all', limit='Maximum number of cases to list, 1 to 50')
async def case_list(interaction: discord.Interaction, status: str='pending', limit: app_commands.Range[int, 1, 50]=10, public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message('You need Manage messages permission to use this.', ephemeral=not public)
        return
    result = router.case_list(status=status, limit=int(limit))
    if not result.ok:
        await interaction.response.send_message(result.message, ephemeral=not public)
        return
    cases = result.data.get('cases', [])
    if not cases:
        await interaction.response.send_message(f'No `{status}` case.', ephemeral=not public)
        return
    lines = [f'case list:{status}']
    for case in cases:
        matches = ', '.join(f"{m.get('category')}:{m.get('term')}" for m in case.get('matches', [])[:3]) or 'Failed'
        dup = int(case.get('duplicate_count', 0) or 0)
        dup_text = f'; duplicate {dup} times' if dup else ''
        lines.append(
            f"`{case.get('case_id')}` | {case.get('display_name')} | {case.get('status')} | {matches}{dup_text}\n"
            f"message:{case.get('message_url') or case.get('last_message_url') or 'FailedLink'}"
        )
    await interaction.response.send_message('\n'.join(lines)[:1900], ephemeral=not public)


@bot.tree.command(name='case_clear', description='Clear case records; default only clears resolved cases')
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(status='pending / resolved / ignored / all', test_only='Only clear test cases', confirm='Must be true to really clear')
async def case_clear(interaction: discord.Interaction, status: str='resolved', test_only: bool=False, confirm: bool=False, public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message('You need Manage messages permission to use this.', ephemeral=not public)
        return
    if not confirm:
        await interaction.response.send_message(f'dry-run:Will clear status=`{status}` test_only={test_only} case(s).Set confirm:true to confirm..', ephemeral=not public)
        return
    result = router.case_clear(status, str(interaction.user.id), test_only=bool(test_only))
    await interaction.response.send_message(f"{result.message}\ncase ID:{', '.join(result.data.get('removed_case_ids', [])[:30]) or 'Failed'}", ephemeral=not public)


@bot.tree.command(name='case_clear_test', description='Clear test cases without affecting formal cases')
@app_commands.default_permissions(manage_messages=True)
async def case_clear_test(interaction: discord.Interaction, confirm: bool=False, public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message('You need Manage messages permission to use this.', ephemeral=not public)
        return
    if not confirm:
        await interaction.response.send_message('dry-run:Will clear test cases.Set confirm:true to confirm..', ephemeral=not public)
        return
    result = router.case_clear_test(str(interaction.user.id))
    await interaction.response.send_message(f"{result.message}\ncase ID:{', '.join(result.data.get('removed_case_ids', [])[:30]) or 'Failed'}", ephemeral=not public)


@bot.tree.command(name='case_ignore', description='Mark a case as false positive; optionally add safe phrase')
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(case_id='case ID, for example C0001', reason='Ignore reason', add_safe_phrase='Optional safe phrase to add')
async def case_ignore(interaction: discord.Interaction, case_id: str, reason: str, add_safe_phrase: str='', public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.', ephemeral=not public)
        return
    result = router.case_ignore(case_id, str(interaction.user.id), reason, add_safe_phrase)
    await interaction.response.send_message(format_tool_result(result), ephemeral=not public)

@bot.tree.command(name='case_resolve', description='Mark a case as resolved')
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(case_id='case ID, for example C0001', action='Action, for example warn / timeout / no_action', reason='reason')
async def case_resolve(interaction: discord.Interaction, case_id: str, action: str, reason: str='', public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.', ephemeral=not public)
        return
    result = router.case_resolve(case_id, str(interaction.user.id), action, reason)
    await interaction.response.send_message(format_tool_result(result), ephemeral=not public)

@bot.tree.command(name='remove_warning', description='Remove warning role and reset state')
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(user='Target user')
async def remove_warning(interaction: discord.Interaction, user: discord.Member, public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.', ephemeral=not public)
        return
    result = router.reset_user_state(str(user.id), user.display_name)
    role_note = await remove_warning_role(user)
    await interaction.response.send_message(f'{format_tool_result(result)}\n{role_note}', ephemeral=not public)

@bot.tree.command(name='pc_status', description='View PC status for the machine running the bot')
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(public='Whether to post publicly in the current channel', detail='summary / full')
async def pc_status(interaction: discord.Interaction, public: bool=False, detail: str='summary') -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.', ephemeral=not public)
        return
    await interaction.response.defer(ephemeral=not public)
    if detail.strip().lower() == 'full':
        if not is_full_report_enabled(runtime_state):
            await interaction.followup.send(f' Bot is currently in `{runtime_state.mode}` mode, detailed sensor reports are paused; only summary is available.', ephemeral=not public)
            report = await asyncio.to_thread(format_system_report)
        else:
            report = await asyncio.to_thread(format_detailed_system_report)
    else:
        report = await asyncio.to_thread(format_system_report)
    await interaction.followup.send(report[:1900], ephemeral=not public)

@bot.tree.command(name='pc_monitor_start', description='Start scheduled PC status reports')
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(channel='Report channel; leave empty to use the current channel', interval_minutes='Interval in minutes, recommended 10 or more')
async def pc_monitor_start(interaction: discord.Interaction, channel: discord.TextChannel | None=None, interval_minutes: app_commands.Range[int, 1, 1440]=30, public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.', ephemeral=not public)
        return
    global PC_STATUS_ENABLED, PC_STATUS_CHANNEL_ID, PC_STATUS_INTERVAL_MINUTES
    target = channel or interaction.channel
    PC_STATUS_CHANNEL_ID = str(target.id)
    PC_STATUS_INTERVAL_MINUTES = int(interval_minutes)
    PC_STATUS_ENABLED = True
    ensure_pc_status_task()
    await interaction.response.send_message(f" Started scheduled PC status reports:{(target.mention if hasattr(target, 'mention') else target)}, every {interval_minutes} min.\nNote:This isruntime-only setting; update `.env` as well to make it permanent.", ephemeral=not public)

@bot.tree.command(name='pc_monitor_stop', description='Stop scheduled PC status reports')
@app_commands.default_permissions(manage_messages=True)
async def pc_monitor_stop(interaction: discord.Interaction, public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.', ephemeral=not public)
        return
    global PC_STATUS_ENABLED
    PC_STATUS_ENABLED = False
    await interaction.response.send_message(' Stopped scheduled PC status reports for this runtime.', ephemeral=not public)

@bot.tree.command(name='pc_action', description='Remote PC action; confirm=false is dry-run only')
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(action='lock / sleep / shutdown_60 / shutdown_cancel', confirm='Whether to execute for real')
async def pc_action(interaction: discord.Interaction, action: str, confirm: bool=False, public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.', ephemeral=not public)
        return
    action = action.strip().lower()
    allowed = {'lock', 'sleep', 'shutdown_60', 'shutdown_cancel'}
    if action not in allowed:
        await interaction.response.send_message(f" Unsupported action.Allowed:{', '.join(sorted(allowed))}", ephemeral=not public)
        return
    if not confirm:
        await interaction.response.send_message(f' dry-run:Will execute `{action}`.Set confirm to true to execute.', ephemeral=not public)
        return
    try:
        if platform.system() != 'Windows':
            raise RuntimeError('Only Windows commands are built in.')
        if action == 'lock':
            subprocess.Popen(['rundll32.exe', 'user32.dll,LockWorkStation'])
        elif action == 'sleep':
            subprocess.Popen(['rundll32.exe', 'powrprof.dll,SetSuspendState', '0,1,0'])
        elif action == 'shutdown_60':
            subprocess.Popen(['shutdown', '/s', '/t', '60', '/c', 'Requested by Discord bot remote command shutdown in 60 sec'])
        elif action == 'shutdown_cancel':
            subprocess.Popen(['shutdown', '/a'])
        router.record_action('pc_action', str(interaction.user.id), 'LOCAL_PC', action, dry_run=False)
        await interaction.response.send_message(f' Executed `{action}`.', ephemeral=not public)
    except Exception as exc:
        await interaction.response.send_message(f' Execution failed:{exc}', ephemeral=not public)

@bot.tree.command(name='bot_mode', description='Switch bot workload mode')
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(mode='normal / eco / emergency / shutdown', confirm='Must be true for shutdown')
async def bot_mode(interaction: discord.Interaction, mode: str, confirm: bool=False, public: bool=False) -> None:
    global runtime_state
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.', ephemeral=not public)
        return
    mode = mode.strip().lower()
    if mode == 'shutdown':
        if not confirm:
            await interaction.response.send_message(' dry-run:Preparing to shut down the bot itself.To really shut it down, use `confirm:true`.', ephemeral=not public)
            return
        runtime_state.mode = 'emergency'
        runtime_state.reason = f'by {interaction.user} manually shut down bot'
        save_runtime_state(runtime_state)
        await interaction.response.send_message(' The bot is going to shut itself down.', ephemeral=not public)
        await bot.close()
        return
    try:
        runtime_state = set_mode(runtime_state, mode, reason=f'by {interaction.user} manually switched')
    except ValueError:
        await interaction.response.send_message(' mode must be `normal`、`eco`、`emergency`、`shutdown`.', ephemeral=not public)
        return
    await interaction.response.send_message(f' Bot mode switched to `{runtime_state.mode}`.\nreason:{runtime_state.reason}', ephemeral=not public)

@bot.tree.command(name='bot_mode_status', description='View bot workload mode')
@app_commands.default_permissions(manage_messages=True)
async def bot_mode_status(interaction: discord.Interaction, public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.', ephemeral=not public)
        return
    await interaction.response.send_message(f'**Bot Mode**\nCurrent mode:`{runtime_state.mode}`\nAuto guard:{runtime_state.auto_guard_enabled}\neco Temperature:{runtime_state.eco_temp}°C\nemergency Temperature:{runtime_state.emergency_temp}°C\nshutdown Temperature:{runtime_state.shutdown_temp}°C\nhigh-temperature hits:{runtime_state.high_temp_hits}/{runtime_state.shutdown_hits_required}\nreason:{runtime_state.reason}', ephemeral=not public)


@bot.tree.command(name='auto_mod', description='Away mode: automatically process timeout cases and optionally close them when admins are unavailable')
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(enabled='Enable away mode', autoclose_on_timeout='Auto-close after successful auto-timeout')
async def auto_mod(interaction: discord.Interaction, enabled: bool, autoclose_on_timeout: bool=True, public: bool=False) -> None:
    global AUTO_MOD_AWAY_ENABLED, AUTO_MOD_AUTOCLOSE_ON_TIMEOUT
    if not require_manage_messages(interaction):
        await interaction.response.send_message('You need Manage messages permission to use this.', ephemeral=not public)
        return
    AUTO_MOD_AWAY_ENABLED = bool(enabled)
    AUTO_MOD_AUTOCLOSE_ON_TIMEOUT = bool(autoclose_on_timeout)
    state = 'on' if AUTO_MOD_AWAY_ENABLED else 'off'
    await interaction.response.send_message(
        f'Away mode:{state}\nAuto-close after auto-timeout:{AUTO_MOD_AUTOCLOSE_ON_TIMEOUT}\nNote:This isruntime-only setting; update .env as well to make it permanent.',
        ephemeral=not public,
    )


@bot.tree.command(name='auto_mod_status', description='View away mode status')
@app_commands.default_permissions(manage_messages=True)
async def auto_mod_status(interaction: discord.Interaction, public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message('You need Manage messages permission to use this.', ephemeral=not public)
        return
    await interaction.response.send_message(
        f'Away mode:{AUTO_MOD_AWAY_ENABLED}\nAuto-close after auto-timeout:{AUTO_MOD_AUTOCLOSE_ON_TIMEOUT}\nAUTO_TIMEOUT_ENABLED:{AUTO_TIMEOUT_ENABLED}\nAUTO_TIMEOUT_MINUTES:{AUTO_TIMEOUT_MINUTES}',
        ephemeral=not public,
    )


@bot.tree.command(name='bot_guard_set', description='Set bot temperature guard thresholds')
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(eco_temp='CPU temperature to enter eco mode', emergency_temp='CPU temperature to enter emergency mode', shutdown_temp='CPU temperature to shut down bot', enabled='Enable automatic guard', shutdown_hits_required='Consecutive shutdown-threshold hits before closing bot')
async def bot_guard_set(interaction: discord.Interaction, eco_temp: float=80.0, emergency_temp: float=90.0, shutdown_temp: float=95.0, enabled: bool=True, shutdown_hits_required: app_commands.Range[int, 1, 10]=2, public: bool=False) -> None:
    global runtime_state
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.', ephemeral=not public)
        return
    if not 40 <= eco_temp < emergency_temp < shutdown_temp <= 110:
        await interaction.response.send_message(' Temperature values must satisfy:40 <= eco < emergency < shutdown <= 110', ephemeral=not public)
        return
    runtime_state.eco_temp = float(eco_temp)
    runtime_state.emergency_temp = float(emergency_temp)
    runtime_state.shutdown_temp = float(shutdown_temp)
    runtime_state.auto_guard_enabled = bool(enabled)
    runtime_state.shutdown_hits_required = int(shutdown_hits_required)
    runtime_state.high_temp_hits = 0
    runtime_state.reason = f'by {interaction.user} updated temperature guard settings'
    save_runtime_state(runtime_state)
    await interaction.response.send_message(f' Updated temperature guard:\neco:{eco_temp}°C\nemergency:{emergency_temp}°C\nshutdown:{shutdown_temp}°C\nenabled:{enabled}\nshutdown_hits_required:{shutdown_hits_required}', ephemeral=not public)

@bot.tree.command(name='ai', description='Ask the local Ollama model')
@app_commands.describe(
    prompt='AI prompt; when long_mode=true, enter the question or summary request here',
    long_mode='Long mode: collects text and attachments You send next',
    collect_seconds='Long-mode collection seconds, default 60, max 180',
    public='Whether to reply publicly; false means only You can see it',
)
async def ai(
    interaction: discord.Interaction,
    prompt: str,
    long_mode: bool=False,
    collect_seconds: app_commands.Range[int, 10, 180]=AI_LONG_DEFAULT_COLLECT_SECONDS,
    public: bool=False,
) -> None:
    if not is_ai_enabled(runtime_state):
        await interaction.response.send_message(f' Bot is currently in `{runtime_state.mode}` mode, AI and memory features are paused.', ephemeral=not public)
        return

    cooldown_seconds = AI_LONG_COMMAND_COOLDOWN_SECONDS if long_mode else AI_COMMAND_COOLDOWN_SECONDS
    cooldown_store = AI_LONG_LAST_USED if long_mode else AI_LAST_USED

    remain = _ai_cooldown_remaining(
        str(interaction.user.id),
        cooldown_seconds,
        cooldown_store,
    )

    if remain > 0:
        await interaction.response.send_message(_ai_cooldown_message(remain), ephemeral=True)
        return

    _mark_ai_used(
        str(interaction.user.id),
        cooldown_seconds,
        cooldown_store,
    )

    if long_mode:
        await _run_ai_long_mode(interaction, question=prompt, collect_seconds=int(collect_seconds), public=public)
        return

    await interaction.response.defer(ephemeral=not public)
    reply = await asyncio.to_thread(ask_ollama, prompt, str(interaction.user.id), interaction.user.display_name)
    await interaction.followup.send(reply[:1900], ephemeral=not public)
    try:
        record_ai_interaction(user_id=str(interaction.user.id), display_name=interaction.user.display_name, guild_id=str(interaction.guild.id) if interaction.guild else 'DM', channel_id=str(interaction.channel.id) if interaction.channel else 'DM', kind='slash_ai', prompt=prompt, reply=reply)
    except Exception as exc:
        print(f' Failed to save AI interaction record:{exc}')


@bot.tree.command(name='ai_long', description='AI long mode: collects upcoming text, attachments, and image info before replying')
@app_commands.describe(
    question='What You want AI to do with the upcoming content, such as summarize, organize, debug, or answer questions',
    collect_seconds='Collection seconds, default 60, max 180',
    public='Whether to reply publicly; false means only You can see it',
)
async def ai_long(
    interaction: discord.Interaction,
    question: str='Please read, summarize the key points, and point out issues or suggestions if needed.',
    collect_seconds: app_commands.Range[int, 10, 180]=AI_LONG_DEFAULT_COLLECT_SECONDS,
    public: bool=False,
) -> None:
    if not is_ai_enabled(runtime_state):
        await interaction.response.send_message(f' Bot is currently in `{runtime_state.mode}` mode, AI and memory features are paused.', ephemeral=not public)
        return

    remain = _ai_cooldown_remaining(
        str(interaction.user.id),
        AI_LONG_COMMAND_COOLDOWN_SECONDS,
        AI_LONG_LAST_USED,
    )

    if remain > 0:
        await interaction.response.send_message(_ai_cooldown_message(remain), ephemeral=True)
        return

    _mark_ai_used(
        str(interaction.user.id),
        AI_LONG_COMMAND_COOLDOWN_SECONDS,
        AI_LONG_LAST_USED,
    )

    await _run_ai_long_mode(interaction, question=question, collect_seconds=int(collect_seconds), public=public)


@bot.tree.command(name='forget', description='Clear Your AI conversation memory')
@app_commands.default_permissions(manage_messages=True)
async def forget(interaction: discord.Interaction, public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.', ephemeral=not public)
        return
    reset_user_memory(str(interaction.user.id))
    await interaction.response.send_message(' Your AI conversation memory has been cleared.', ephemeral=not public)

@bot.tree.command(name='summarize_docx', description='Upload a Word document and ask the local model to summarize it')
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(file='.docx file')
async def summarize_docx(interaction: discord.Interaction, file: discord.Attachment, public: bool=False) -> None:
    if not require_manage_messages(interaction):
        await interaction.response.send_message(' You need Manage messages permission to use this.', ephemeral=not public)
        return
    if not is_doc_summary_enabled(runtime_state):
        await interaction.response.send_message(f' Bot is currently in `{runtime_state.mode}` mode, document summary is paused.', ephemeral=not public)
        return
    if not file.filename.lower().endswith('.docx'):
        await interaction.response.send_message(' Only .docx files are supported.', ephemeral=not public)
        return
    await interaction.response.defer(ephemeral=not public)
    data = await file.read()
    try:
        doc = Document(io.BytesIO(data))
        text = '\n'.join((p.text for p in doc.paragraphs if p.text.strip()))
    except Exception as exc:
        await interaction.followup.send(f' Failed to read document:{exc}', ephemeral=not public)
        return
    prompt = f'Summarize the following Word document and list key points:\n\n{text[:6000]}'
    reply = await asyncio.to_thread(ask_ollama, prompt, str(interaction.user.id), interaction.user.display_name)
    await interaction.followup.send(reply[:1900], ephemeral=not public)

@bot.command(name='anger')
async def legacy_anger(ctx: commands.Context) -> None:
    if isinstance(ctx.author, discord.Member) and (not is_admin_member(ctx.author)):
        await ctx.reply(' This legacy command is admin-only; members should use `/my_warnings`.')
        return
    result = router.get_user_status(str(ctx.author.id), ctx.author.display_name)
    data = result.data
    await ctx.reply(f"anger:{data['anger']}/{data['anger_limit']} | warnings:{data['warning_count']} | case:{data['case_count']}")

@bot.command(name='calm')
async def legacy_calm(ctx: commands.Context) -> None:
    if isinstance(ctx.author, discord.Member) and (not is_admin_member(ctx.author)):
        await ctx.reply(' You need moderation permissions to use this.')
        return
    router.reset_user_state(str(ctx.author.id), ctx.author.display_name)
    reset_user_memory(str(ctx.author.id))
    await ctx.reply(' Your status has been reset.')

@bot.command(name='forget')
async def legacy_forget(ctx: commands.Context) -> None:
    if isinstance(ctx.author, discord.Member) and (not is_admin_member(ctx.author)):
        await ctx.reply(' You need moderation permissions to use this.')
        return
    reset_user_memory(str(ctx.author.id))
    await ctx.reply(' Your AI conversation memory has been cleared.')

@bot.command(name='ai')
async def legacy_ai(ctx: commands.Context, *, prompt: str) -> None:
    if not is_ai_enabled(runtime_state):
        await ctx.reply(f' Bot is currently in `{runtime_state.mode}` mode, AI and memory features are paused.')
        return

    remain = _ai_cooldown_remaining(
        str(ctx.author.id),
        AI_COMMAND_COOLDOWN_SECONDS,
        AI_LAST_USED,
    )
    if remain > 0:
        await ctx.reply(_ai_cooldown_message(remain), delete_after=10)
        return

    _mark_ai_used(
        str(ctx.author.id),
        AI_COMMAND_COOLDOWN_SECONDS,
        AI_LAST_USED,
    )

    thinking = await ctx.reply(' Thinking...')
    reply = await asyncio.to_thread(ask_ollama, prompt, str(ctx.author.id), ctx.author.display_name)
    await thinking.edit(content=reply[:1900])
    try:
        record_ai_interaction(
            user_id=str(ctx.author.id),
            display_name=ctx.author.display_name,
            guild_id=str(ctx.guild.id) if ctx.guild else 'DM',
            channel_id=str(ctx.channel.id),
            kind='legacy_ai',
            prompt=prompt,
            reply=reply,
        )
    except Exception as exc:
        print(f' Failed to save AI interaction record:{exc}')

if __name__ == '__main__':
    bot.run(DISCORD_TOKEN)
