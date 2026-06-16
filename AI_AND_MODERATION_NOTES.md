# AI and Moderation Notes

This document explains the main AI, memory, moderation, warning, case, and privacy-related behavior in this project.

This project is an archived learning project. The features described here are mainly for educational reference and self-hosted experimentation, not for production-grade moderation.

## 1. Overview

This bot combines several systems:

- Rule-based message moderation
- Warning and anger tracking
- Case reports
- Optional Discord case threads or forum posts
- Local Ollama AI replies
- Long-form AI collection mode
- Optional image-to-text analysis through a local vision model
- User profile summaries
- AI interaction insight generation
- Local JSON / JSONL runtime data storage

The bot is designed to help Discord server administrators observe, organize, and review moderation-related events. It should not be treated as a fully automatic punishment system.

## 2. Case Reports and Discussion Threads

When the bot detects a possible rule violation, it creates a moderation case and sends a report to the configured report channel.

If `CREATE_CASE_THREADS=true` is enabled, the bot can create a Discord thread or forum post for each moderation case.

A case report may include:

- Case ID
- Target user
- Channel information
- Matched rule terms
- Whether the message looks like a targeted attack
- Recent trigger count
- Original message preview
- Message link
- Suggested moderator commands

The recommended flow is:

```text
Message detected
↓
Rule match found
↓
Case created
↓
Report sent to report channel
↓
Thread or forum post created
↓
Administrators review the context
↓
Case is ignored, resolved, or handled manually
```

## 3. Anger Value

The anger value is a simple warning-state counter for each user.

It is not a psychological score, personality score, or real behavior judgment. It is only a local moderation state used by this demo project.

The value may increase when:

- A moderator manually records a warning
- The bot detects a rule violation where a penalty should be applied

The value is limited by `ANGER_LIMIT`.

Example:

```env
ANGER_LIMIT=3
```

A possible interpretation is:

```text
0 / 3 = No active warning state
1 / 3 = Warning exists
2 / 3 = Close to action threshold
3 / 3 = Action threshold reached; admin review or timeout may be suggested
```

The anger value can be reset or reduced by moderation commands such as `/calm`.

## 4. Warning Records

Warning records are stored separately from the anger value.

A warning record may include:

- Time
- User ID
- Display name
- Moderator ID or automatic detection source
- Reason
- Related case ID

Warnings are used to show user status, support moderation review, and help generate AI interaction insights.

The warning system should not be used as the only reason for punishment without human review.

## 5. Attention Level

The attention level is a manual administrator note from 0 to 5.

It is different from the anger value.

The anger value is mainly connected to warnings and rule triggers. The attention level is a manual observation level set by administrators.

Suggested meaning:

```text
0 / 5 = Normal
1 / 5 = Light watch
2 / 5 = Needs attention
3 / 5 = High attention
4 / 5 = Strict watch
5 / 5 = Priority handling
```

The attention level may be included in profile summaries and AI-generated interaction insights.

It should be used carefully and respectfully. It is not a medical, psychological, personality, or identity judgment.

## 6. AI Replies

The bot can reply using a local Ollama model.

Supported AI entry points may include:

- `/ai`
- Bot mentions
- Legacy `!ai`
- Long-form AI collection mode

In a typical self-hosted setup, the model runs locally on the deployer's own machine or server. However, actual privacy depends on the deployer's configuration.

Do not connect this bot to external AI APIs unless you understand what data may be sent outside your machine.

## 7. AI Conversation Memory

The bot may keep a small per-user AI conversation memory in runtime memory.

This memory is used to provide short context for future AI replies from the same user.

Important notes:

- This memory is stored in the running Python process.
- It is not meant to be permanent long-term memory.
- It may be cleared when the bot restarts.
- It can be manually cleared with the forget command.
- It is limited by `MAX_MEMORY_PER_USER`.

Related command:

```text
/forget
```

This memory should be understood as temporary AI context, not as a reliable database.

## 8. User Profile Summaries

The bot can create or update local user profile records.

A profile may include:

- User ID
- Display name
- Attention level
- Moderator notes
- AI interaction count
- Last seen time
- Last AI interaction time
- Last AI-generated summary

These summaries are helper notes only. They should not be used as final judgments about a person.

## 9. AI Insight Cache

AI-generated profile insights may be cached to reduce repeated AI calls.

The cache may include:

- Generated time
- Target user ID
- Display name
- Analysis range
- Summary text

This cache exists to avoid regenerating the same insight too frequently.

It should be kept private and should not be uploaded to GitHub.

## 10. Long-form AI Collection Mode

Long-form AI mode allows the user to start a collection window.

During this time, the bot collects messages or attachments from the same user in the same channel, then sends the collected content to the AI model for processing.

This can be used for:

- Summarizing long text
- Reading multiple messages
- Organizing notes
- Debugging logs
- Summarizing screenshots if vision support is enabled

## 11. Optional Image Analysis

If image analysis is enabled, the bot may send uploaded images to a local Ollama vision model.

If image analysis is disabled, the bot only records basic attachment information such as filename, content type, file size, and link.

Do not enable image analysis unless you understand what images may be processed and where they are sent.

## 12. Runtime Data and Privacy

The following folders may contain private runtime information:

```text
data/
logs/
```

These folders may include:

- User IDs
- Channel IDs
- Warning records
- Moderation cases
- AI prompts
- AI replies
- Cached AI summaries
- User profile data
- Error logs
- Uploaded file information

Do not publish these folders.

Do not commit them to GitHub.

## 13. Human Review Reminder

This bot should support moderators, not replace them.

The moderation and AI systems may produce false positives, incomplete summaries, or inaccurate suggestions.

Administrators should review context before taking serious action, especially for:

- Timeouts
- Kicks
- Bans
- Message deletion
- User profile interpretation
- AI-generated moderation advice

## 14. Archived Project Notice

This repository is mainly an archived learning project and personal portfolio record.

Unless there is a special reason, this bot may not receive major updates in the future.

Use it as a learning reference, not as a finished production moderation system.
