# Code-Level Security Design

In addition to feature-level permission limits and moderation workflows, this project includes several code-level safeguards to reduce the risk of false positives, data corruption, log growth, and uncontrolled high-risk actions.

Because local language models can consume significant system resources, resource allocation and hardware protection are also important, especially for temperature and storage control.

---

## 1. ToolRouter is decoupled from the Discord API

The project keeps most moderation logic inside `ToolRouter`.

`ToolRouter` does not directly call the Discord API. Instead, it receives plain data such as user IDs, message content, channel IDs, and case metadata. It then returns a `ToolResult`.

The Discord-facing main program decides:

* Whether to show the result to the user
* Whether to send a report to the moderation channel
* Whether to create a case thread
* Whether administrator confirmation is required
* Whether to actually perform a timeout or another action

Benefits:

* Moderation logic is not tightly coupled to Discord display behavior.
* Core logic is easier to test.
* High-risk actions can be handled as dry runs or marked as requiring administrator confirmation.
* If the project is connected to another platform later, part of the logic can be reused.

Simplified flow:

```text
Discord event
↓
Convert to plain data
↓
ToolRouter.evaluate_message(...)
↓
Return ToolResult
↓
main.py decides how to display, report, or execute
```

---

## 2. Unified ToolResult format

`ToolResult` provides a consistent result format for tool-layer operations.

It contains:

```text
ok
tool
message
data
requires_admin_confirm
dry_run
```

Meaning:

* `ok`: whether the tool processed the request successfully
* `message`: short human-readable message
* `data`: machine-readable detailed data
* `requires_admin_confirm`: whether administrator confirmation is required
* `dry_run`: whether the action was simulated and not actually executed

This allows the main program to clearly distinguish between executed actions, recommendations, confirmation-required actions, and ignored cases.

---

## 3. JSON writes use temporary-file replacement

Data is not written by directly overwriting the original JSON file.

Instead, the project first writes to a `.tmp` file, then replaces the original file after writing succeeds.

Flow:

```text
Original data file
↓
Write filename.json.tmp
↓
Replace filename.json after the write completes
```

This reduces the chance of corrupting JSON files due to interruption, write failure, or partial writes.

This is not a full database transaction system and cannot guarantee safety in every power-loss scenario. However, it is safer than directly overwriting the original file and works well for lightweight JSON storage.

---

## 4. JSON read failures fall back to defaults

When reading JSON files, the program returns a default value if the file does not exist.

If the JSON format is invalid, the program also returns default data instead of crashing the entire bot.

This helps the bot keep running during demos, testing, or manual JSON editing mistakes.

---

## 5. Lightweight data retention strategy

The project uses JSON / JSONL as lightweight storage.

To prevent files from growing without limit during long-term use, some records are capped, for example:

```text
action_log[-300:]
moderation_cases[-500:]
```

This means only recent important records are retained, which is suitable for demos and small servers.

This is not a full database design, but it is low-cost, readable, and easy to back up.

---

## 6. Log truncation and fault tolerance

Logs are written as JSONL and grouped by type, for example:

```text
logs/bot/
logs/commands/
logs/music/
logs/errors/
logs/system/
```

To prevent a single message, traceback, or large object from making logs too large, values are truncated before being written:

* Strings are length-limited.
* Lists are item-limited.
* Dictionaries are key/value-limited.
* Non-JSON-serializable values are converted to strings.

The logger is also best-effort.
If log writing fails, the logger should not crash the entire bot.

---

## 7. Temperature protection uses consecutive-hit logic

The temperature guard does not shut down the bot immediately after one high reading.

It uses:

```text
high_temp_hits
shutdown_hits_required
```

to check whether the shutdown temperature has been exceeded multiple times in a row.

This avoids shutting down the bot because of a short temperature spike, sensor glitch, or unstable reading.

Temperature protection is roughly divided into:

```text
eco_temp        → enter low-power mode
emergency_temp  → enter emergency mode
shutdown_temp   → shut down the bot after consecutive hits
```

This conservative design is more suitable for a local bot that may run for long periods.

---

## 8. Music filenames and extensions are sanitized

The music module restricts allowed audio file extensions, such as:

```text
.mp3
.wav
.flac
.ogg
.m4a
```

Filenames are also sanitized by removing characters that are unsafe or confusing in file paths, such as:

```text
\ / : * ? " < > |
```

This reduces the risk of path errors or messy file management caused by unusual uploaded filenames.

---

## 9. Administrator messages are reported but not automatically punished

When a user with administrative permissions triggers a moderation rule, the bot handles it conservatively.

Administrator messages can still be detected and reported, but automatic punishment is not applied.

This helps prevent administrators from being automatically punished when they are testing, quoting, teaching, or handling moderation cases.

---

## 10. Context is checked before automatic punishment

The bot does not punish only because a blocked term appears.

It also considers:

* Whether `safe_phrases` were matched
* Whether the message appears to be a targeted attack
* Whether other users were mentioned
* Whether the message belongs to spam or high-risk categories
* Whether the user is an administrator
* Whether the user has triggered rules multiple times in a short window

If content is suspicious but lacks a clear target or context, the bot may create a case and report it instead of automatically punishing the user.

---

## Summary

The core code-level protection design is:

```text
Separate data from platform behavior
↓
Wrap results in a unified format
↓
Use dry-run / confirmation for high-risk actions
↓
Use fault-tolerant JSON writes
↓
Truncate and classify logs
↓
Protect against high temperature
↓
Prioritize human review
```

The goal is not to completely replace moderators with automation. Instead, the project provides a safer, traceable, and human-reviewable moderation assistance workflow.

It also keeps clear boundaries between Discord events, moderation logic, and the local language model, preventing AI features from directly controlling high-risk actions.
