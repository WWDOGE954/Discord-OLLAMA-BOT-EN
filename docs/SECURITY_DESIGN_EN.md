# Security Design

This document explains the security design, risk-reduction measures, and known limitations of the Discord OLLAMA Bot.

This project includes Discord moderation assistance, rule-based violation detection, case reporting, local AI, music playback, and PC status reporting. Because it may process server management data and user-related records, deployers should understand how data is stored and what the security limits are before using it in a real server.

---

## 1. Sensitive data is not hard-coded

This project uses `.env` to manage sensitive configuration, such as:

* Discord Bot Token
* Webhook URL
* Channel IDs
* Role IDs
* Ollama API URL
* Music and PC status settings

For production use, create your own `.env` file and do not upload it to GitHub or any public location.

A public repository should only provide:

```text
.env.example
```

This file should demonstrate the configuration format, not store real tokens or private data.

---

## 2. Runtime data is separated from source code

During execution, the project may generate:

```text
data/
logs/
```

These folders may contain:

* User IDs
* Server IDs
* Channel IDs
* Warning records
* Moderation case records
* AI interaction records
* Music library data
* Error logs

These files are useful for debugging and maintenance, but they should not be committed to a public repository.

---

## 3. Moderation rules are categorized

Moderation rules are divided into several categories, such as:

* `blocked_terms`
* `english_abuse_terms`
* `sexual_terms`
* `spam_terms`
* `target_patterns`
* `safe_phrases`

This reduces the risk of relying on one overly broad blacklist.

`target_patterns` helps the bot determine whether a message may be directed at another person.

`safe_phrases` is used to exclude contexts such as teaching, quoting, code examples, feature tests, or other low-risk cases. This helps reduce false positives.

---

## 4. False-positive reduction

The bot supports a safe phrase mechanism.

When an administrator confirms that a piece of content was a false positive, they can add it as an exception phrase so future similar contexts are treated with lower severity.

Good safe phrase candidates include:

* Code examples
* Educational content
* Quoted rules
* Test messages
* Filenames or command parameters
* Non-targeted discussion

---

## 5. Case system and human review

When the bot detects potentially problematic content, it creates a moderation case and sends it to the report channel.

If this setting is enabled:

```env
CREATE_CASE_THREADS=true
```

The bot creates a Discord thread or forum post for each case, so administrators can discuss the context in one place.

Recommended flow:

```text
Potential violation detected
↓
Create a case
↓
Send it to the moderation report channel
↓
Create a thread or forum post
↓
Administrators review the context
↓
Handle it with /case_ignore, /case_resolve, /punish, or related commands
```

This prevents the bot from applying excessive punishment based only on a single text match.

---

## 6. High-risk actions require administrator confirmation

High-risk operations should be confirmed by an administrator, including:

* Timeout
* Kick
* Ban
* Message deletion
* Remote PC actions
* Bot shutdown

Some commands require `confirm:true` before they actually run.
If `confirm:false`, the command usually performs a dry run or only shows a recommendation.

---

## 7. Member and administrator permissions are separated

This project separates normal member commands from administrator commands.

Normal members can use:

* `/status`
* `/ai`
* `/my_warnings`
* `/my_profile`
* Music-related commands

Administrators can use:

* Warning and punishment commands
* Case handling commands
* Rule management commands
* PC status and remote action commands
* Bot mode and temperature guard settings

Administrator access can be determined by Discord permissions or the `ADMIN_ROLE_ID` value in `.env`.

---

## 8. Public / private response control

Some slash commands support a `public` parameter.

```text
public:false
```

Only the command user can see the response.

```text
public:true
```

The response is shown publicly in the current channel.

This helps avoid exposing warning records, AI summaries, user status, or moderation information unnecessarily.

---

## 9. Log truncation and error protection

The bot records commands, errors, and system events. Log entries are truncated before writing, so a single large message or object does not cause uncontrolled log growth.

The logger is also best-effort.
If log writing fails, it should not crash the entire bot.

---

## 10. AI feature limitations and isolation

AI features use local Ollama.

Important notes:

* AI responses are only suggestions.
* AI judgment should not be the only basis for moderation decisions.
* High-risk actions still require administrator confirmation.
* User interaction summaries may contain personal data and should not be shown publicly unless necessary.

The bot also supports different runtime modes:

```text
normal
eco
emergency
```

In `eco` or `emergency` mode, AI and heavy tasks can be reduced or disabled while basic moderation and reporting remain available.

---

## 11. Music file limits

The music feature limits allowed audio extensions, such as:

```text
.mp3
.wav
.flac
.ogg
.m4a
```

The following `.env` settings can also limit user libraries and upload sizes:

```env
MUSIC_MAX_TRACKS_PER_USER=20
MUSIC_MAX_FILE_MB=50
```

Uploaders are responsible for the source, license, and usage rights of the audio files they upload.

The bot only provides queueing and playback. It does not mean the server, administrators, or bot owner owns, reviews, or licenses the uploaded audio content.

---

## 12. PC status and temperature guard

The PC status feature can report:

* CPU usage
* RAM usage
* Disk usage
* Network traffic
* GPU status
* CPU temperature

CPU temperature reading can be used with LibreHardwareMonitor.

The bot can use temperature thresholds such as:

```text
eco_temp
emergency_temp
shutdown_temp
```

When temperatures are too high, the bot can switch to low-power mode, emergency mode, or shut itself down if needed.

---

## 13. Known limitations

This project still has limitations:

* Rule-based moderation can produce false positives.
* AI summaries can be incomplete or inaccurate.
* Incorrect Discord permission settings may break commands.
* If a webhook URL or bot token is leaked, it must be rotated immediately.
* Real security depends on the deployer's `.env`, Discord permissions, and server configuration.

---

## 14. Recommended deployment practices

Before production deployment:

1. Test in a private repository first.
2. Confirm that `.env` has not been committed.
3. Confirm that `data/` and `logs/` are not uploaded.
4. Test all features in a test Discord server.
5. Enable only the permissions the bot actually needs.
6. Restrict administrator commands to trusted roles.
7. Review logs and moderation cases regularly.
8. Before publishing the project, remove all private settings and local machine paths.

---

## 15. Summary

The security focus of this project is not fully automated punishment, but:

```text
Detect → Report → Discuss → Human review → Execute
```

Through the case system, discussion threads, safe phrases, permission separation, private responses, log truncation, and `.env` separation, the project reduces the risk of false positives, data leakage, and excessive punishment.
