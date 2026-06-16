## Translation Notice

All English translations in this repository were assisted by AI. Some wording may be imperfect or slightly different from the original intent.

# Discord OLLAMA Bot

A Discord moderation assistant that combines rule-based moderation, case tracking, local Ollama AI, PC status monitoring, temperature-protection modes, and a personal music library.

This project is designed for Discord server administrators who want a self-hosted helper bot for daily moderation, warning workflows, local AI summaries, user interaction insights, and basic server utilities.

## Project Note

This repository is an organized English version of a project I developed during high school.

It was prepared as part of my personal portfolio and learning record. Since this is one of my first repositories uploaded to GitHub, there may still be issues in the repository structure, documentation, wording, or setup instructions.

Unless there is a special reason, this bot will probably not receive major updates in the future. The repository is mainly kept for documentation, learning, educational reference, and portfolio purposes.

If you find any problems or have suggestions, feel free to contact me, open an issue, or use the discussion area.

## Features

* Rule-based message moderation
* Report and case workflow with Discord text channels or forum posts
* Case deduplication to avoid repeated spam reports
* Warning, final warning, and optional short timeout flow
* Admin-only case tools such as `/case_list`, `/case_clear`, and `/case_clear_test`
* Away mode for limited automatic moderation handling when admins are unavailable
* Local Ollama AI replies with `/ai`, mentions, and legacy `!ai`
* Long-form AI collection mode with optional image-to-text analysis through a vision model
* User profile summaries and AI interaction insights
* PC status reports through psutil, NVIDIA `nvidia-smi`, and LibreHardwareMonitor
* Temperature guard modes: normal, eco, and emergency
* Personal music library and Discord voice playback
* Public/private slash command response control
* JSON data storage and JSONL logs

## Documentation

See [`docs/README.md`](./docs/README.md) for documentation, command guides, security notes, and supplementary multilingual documents.

## Safety Notice

Never commit the following files or data:

* `.env`
* Discord bot token
* Webhook URLs
* API keys or passwords
* `data/`
* `logs/`
* Uploaded music files
* Real moderation cases
* Real AI conversation records
* User profile data or cached insights

Use `.env.example` as a safe public template. Copy it to `.env` locally and fill in your private values.

If a Discord token, webhook URL, API key, or password is ever exposed, revoke or regenerate it immediately.

## Requirements

* Python 3.10+
* Discord bot token
* `discord.py`
* `python-dotenv`
* `requests`
* `aiohttp`
* `psutil`
* Optional: Ollama for local AI
* Optional: FFmpeg for music playback
* Optional: LibreHardwareMonitor for CPU temperature readings on Windows
* Optional: NVIDIA driver tools for GPU status through `nvidia-smi`

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

## Configuration

Copy the public template:

```bash
cp .env.example .env
```

Then fill in your real values:

```env
DISCORD_TOKEN=
GUILD_ID=
REPORT_CHANNEL_ID=
ADMIN_ROLE_ID=
WARNING_ROLE_ID=
```

For moderation testing, keep automatic timeout disabled at first:

```env
AUTO_TIMEOUT_ENABLED=false
PUBLIC_WARNING=true
```

After confirming the rules work correctly, you can enable short timeout:

```env
AUTO_TIMEOUT_ENABLED=true
AUTO_TIMEOUT_MINUTES=1
AUTO_TIMEOUT_COUNT=3
AUTO_TIMEOUT_WINDOW_SECONDS=120
```

## Running the Bot

```bash
python main.py
```

For development guild sync, set `GUILD_ID` in `.env` so slash commands appear faster.

## Important Commands

Member commands:

* `/status`
* `/my_warnings`
* `/my_profile`
* `/ai`
* `@bot message`

Moderation commands:

* `/banword_add`
* `/banword_remove`
* `/banword_list`
* `/safe_add`
* `/safe_remove`
* `/case_list`
* `/case_resolve`
* `/case_ignore`
* `/case_clear`
* `/case_clear_test`
* `/punish`
* `/auto_mod`
* `/auto_mod_status`

System commands:

* `/pc_status`
* `/pc_monitor_start`
* `/pc_monitor_stop`
* `/bot_mode`
* `/bot_mode_status`
* `/bot_guard_set`

Music commands:

* `/music_add`
* `/music_list`
* `/go_music`
* `/music_queue`
* `/music_pause`
* `/music_resume`
* `/music_skip`
* `/music_stop`
* `/music_volume`
* `/music_loop`

See `docs/COMMANDS.md` for a fuller command guide.

## Data Files

Runtime files are created under `data/` and `logs/`.

These folders may contain user IDs, channel IDs, moderation cases, AI prompts, cached summaries, uploaded music information, and error traces. They are excluded by `.gitignore` and should not be committed.

## License

This repository uses a custom educational and non-commercial license.

Learning, teaching, classroom use, and academic reference are welcome. Commercial use, redistribution without permission, misuse of user data, and unauthorized use of copyrighted music are prohibited.

See `LICENSE` for details.

Third-party packages keep their own licenses.
