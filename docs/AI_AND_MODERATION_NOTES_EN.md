# AI and Moderation Notes

This document explains the main AI, memory, moderation, warning, case, and privacy-related behavior in this project.

This project is an archived learning project. The features described here are mainly for educational reference and self-hosted experimentation, not for production-grade moderation.

## 1. Overview

This bot combines several systems:

* Rule-based message moderation
* Warning and anger tracking
* Case reports
* Optional Discord case threads or forum posts
* Local Ollama AI replies
* Long-form AI collection mode
* Optional image-to-text analysis through a local vision model
* User profile summaries
* AI interaction insight generation
* Local JSON / JSONL runtime data storage

The bot is designed to help Discord server administrators observe, organize, and review moderation-related events. It should not be treated as a fully automatic punishment system.

## 2. Case Reports and Discussion Threads

When the bot detects a possible rule violation, it creates a moderation case and sends a report to the configured report channel.

The report may include:

* Case ID
* Target user
* Channel information
* Matched rule terms
* Whether the message looks like a targeted attack
* Recent trigger count
* Original message preview
* Message link
* Suggested moderator commands

If `CREATE_CASE_THREADS=true` is enabled, the bot can create a Discord thread or forum post for each moderation case.

This allows administrators to discuss the case in one place, add evidence, review context, and decide what action should be taken.

Recommended review flow:

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

If the same user posts the same or similar violating content repeatedly within the deduplication window, the bot may merge the event into an existing pending case instead of creating many separate reports.

Related configuration:

```env
REPORT_CHANNEL_ID=
CREATE_CASE_THREADS=true
CASE_THREAD_ARCHIVE_MINUTES=1440
CASE_DEDUPE_SECONDS=60
```

## 3. Rule Matching Logic

The moderation system checks messages against several rule categories:

* `blocked_terms`
* `english_abuse_terms`
* `sexual_terms`
* `spam_terms`
* `safe_phrases`

Safe phrases are checked first. If a message matches a safe phrase, the bot skips the violation result to reduce false positives.

Rule matching uses text normalization, including case-insensitive matching and basic Unicode normalization. This helps reduce simple bypasses such as different letter casing or spacing.

The bot may also check whether a message appears to be targeted at another user. For example, mentions or target patterns such as "you" may make the case more likely to be treated as a targeted attack.

## 4. Anger Value

The anger value is a simple warning-state counter for each user.

It is not a psychological score, personality score, or real behavior judgment. It is only a local moderation state used by this demo project.

The value increases when:

* A moderator manually records a warning
* The bot detects a rule violation where a penalty should be applied

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

The anger value can be reset by moderation commands such as `/calm`.

## 5. Warning Records

Warning records are stored separately from the anger value.

A warning record may include:

* Time
* User ID
* Display name
* Moderator ID or automatic detection source
* Reason
* Related case ID

Warnings are used to show user status, support moderation review, and help generate AI interaction insights.

The warning system is meant to help administrators review patterns. It should not be used as the only reason for punishment without human review.

## 6. Recent Trigger Count and Auto-timeout Suggestion

The bot can count repeated triggers within a short time window.

Related configuration:

```env
AUTO_TIMEOUT_COUNT=3
AUTO_TIMEOUT_WINDOW_SECONDS=120
AUTO_TIMEOUT_MINUTES=1
AUTO_TIMEOUT_ENABLED=false
```

Example behavior:

```text
1st trigger = warning / case report
2nd trigger = final warning stage
3rd trigger within the time window = timeout may be suggested or applied if enabled
```

For public GitHub demos, automatic timeout should stay disabled by default:

```env
AUTO_TIMEOUT_ENABLED=false
```

This keeps the bot safer for testing and prevents accidental punishment while setting up rules.

## 7. Attention Level

The attention level is a manual administrator note from 0 to 5.

It is different from the anger value.

The anger value is mainly connected to warnings and rule triggers.
The attention level is a manual observation level set by administrators.

Suggested meaning:

```text
0 / 5 = Normal
1 / 5 = Light watch
2 / 5 = Needs attention
3 / 5 = High attention
4 / 5 = Strict watch
5 / 5 = Priority handling
```

Admins can set or clear this value with commands such as:

```text
/attention_set
/attention_clear
```

The attention level may be included in profile summaries and AI-generated interaction insights.

It should be used carefully and respectfully. It is not a medical, personality, or identity judgment.

## 8. AI Replies

The bot can reply using a local Ollama model.

Supported AI entry points may include:

* `/ai`
* `/ai_long`
* Bot mentions
* Legacy `!ai`

The bot sends the prompt to the configured Ollama endpoint.

Example configuration:

```env
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
MAX_MEMORY_PER_USER=100
```

In a typical self-hosted setup, the model runs locally on the deployer's own machine or server. However, actual privacy depends on the deployer's configuration.

Do not connect this bot to external AI APIs unless you understand what data may be sent outside your machine.

## 9. AI Conversation Memory

The bot keeps a small per-user AI conversation memory in runtime memory.

This memory is used to provide short context for future AI replies from the same user.

Important notes:

* This memory is stored in the running Python process.
* It is not meant to be permanent long-term memory.
* It may be cleared when the bot restarts.
* It can be manually cleared with the forget command.
* It is limited by `MAX_MEMORY_PER_USER`.

Related command:

```text
/forget
```

Related configuration:

```env
MAX_MEMORY_PER_USER=100
```

This memory should be understood as temporary AI context, not as a reliable database.

## 10. AI Interaction Records

Some AI interactions may be recorded locally for later profile summaries or AI insight generation.

A record may include:

* Time
* User ID
* Display name
* Guild ID
* Channel ID
* Interaction type
* Prompt preview
* Reply preview

These records are stored locally and should not be committed to GitHub.

They may contain private or sensitive content depending on how the bot is used.

## 11. User Profile Summaries

The bot can create or update a local user profile record.

A profile may include:

* User ID
* Display name
* Attention level
* Moderator notes
* AI interaction count
* Last seen time
* Last AI interaction time
* Last AI-generated summary

The profile system is designed for moderation review and self-summary features such as:

```text
/my_profile
/user_profile
```

These summaries should be treated as helper notes only. They should not be used as final judgments about a person.

## 12. AI Insight Cache

AI-generated profile insights may be cached to reduce repeated AI calls.

The cache may include:

* Generated time
* Target user ID
* Display name
* Analysis range
* Whether Discord history was scanned
* Summary text

This cache exists to avoid regenerating the same insight too frequently.

It should be kept private and should not be uploaded to GitHub.

## 13. Discord History Scan

Some profile insight features may scan recent messages from text channels that the bot can access.

The scan may collect message excerpts from a target user for AI summarization.

This depends on:

* Bot permissions
* Channel visibility
* Message history permission
* Command settings
* Whether history scan is enabled for that command

Server owners should inform members if AI logging, profile summaries, or message history analysis are enabled.

## 14. Long-form AI Collection Mode

Long-form AI mode allows the user to start a collection window.

During this time, the bot collects messages or attachments from the same user in the same channel, then sends the collected content to the AI model for processing.

This can be used for:

* Summarizing long text
* Reading multiple messages
* Organizing notes
* Debugging logs
* Summarizing screenshots if vision support is enabled

Related configuration:

```env
AI_LONG_DEFAULT_COLLECT_SECONDS=60
AI_LONG_MAX_COLLECT_SECONDS=180
AI_LONG_COMMAND_COOLDOWN_SECONDS=600
```

## 15. Optional Image Analysis

If image analysis is enabled, the bot may send uploaded images to a local Ollama vision model.

Related configuration:

```env
AI_VISION_ENABLED=false
OLLAMA_VISION_URL=http://localhost:11434/api/chat
OLLAMA_VISION_MODEL=llava:latest
AI_VISION_MAX_IMAGE_MB=6
AI_VISION_TIMEOUT_SECONDS=90
```

If image analysis is disabled, the bot only records basic attachment information such as filename, content type, file size, and link.

Do not enable image analysis unless you understand what images may be processed and where they are sent.

## 16. Runtime Data and Privacy

The following folders may contain private runtime information:

```text
data/
logs/
```

These folders may include:

* User IDs
* Channel IDs
* Warning records
* Moderation cases
* AI prompts
* AI replies
* Cached AI summaries
* User profile data
* Error logs
* Uploaded file information

Do not publish these folders.

Do not commit them to GitHub.

They are excluded by `.gitignore`, but deployers are still responsible for checking their files before publishing.

## 17. Data Safety Reminders

Never publish:

* `.env` files
* Discord bot tokens
* Webhook URLs
* API keys
* Passwords
* Runtime data
* Logs
* AI conversation records
* User profile data
* Cached AI summaries
* Uploaded files or music files
* Real moderation cases

If a token, webhook URL, API key, or password is exposed, revoke or regenerate it immediately.

## 18. Human Review Reminder

This bot should support moderators, not replace them.

The moderation and AI systems may produce false positives, incomplete summaries, or inaccurate suggestions.

Administrators should review context before taking serious action, especially for:

* Timeouts
* Kicks
* Bans
* Message deletion
* User profile interpretation
* AI-generated moderation advice

## 19. Archived Project Notice

This repository is mainly an archived learning project and personal portfolio record.

Unless there is a special reason, this bot may not receive major updates in the future.

Use it as a learning reference, not as a finished production moderation system.
