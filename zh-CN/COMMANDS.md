# 命令摘要

本文件提供各语言版本的简要命令介绍。完整命令与实际行为仍以主文件 `docs/COMMANDS.md` 和实际代码为准。

## 普通用户命令

- `/status`：查看 Bot 基本状态。
- `/ai`：向本地 Ollama AI 发送问题。
- `@bot 消息`：通过提及方式让 Bot 回复。
- `/my_warnings`：查看自己的警告记录。
- `/my_profile`：查看自己的互动摘要或基本 profile。

## 管理与违规处理

- `/warn`：为用户添加警告记录。
- `/anger`：查看或确认用户当前的怒气值状态。
- `/calm`：降低或重置用户的怒气值。
- `/punish`：由管理员判断并执行处理动作。
- `/mod_suggest`：生成管理建议，辅助管理员判断。
- `/remove_warning`：移除指定警告记录。

## 规则与安全词

- `/banword_add`：新增违规词。
- `/banword_remove`：移除违规词。
- `/banword_list`：查看违规词列表。
- `/safe_add`：新增安全词或白名单用语。
- `/safe_remove`：移除安全词。
- `/safe_list`：查看安全词列表。

## 案件与自动管理

- `/case_ignore`：忽略指定案件。
- `/case_resolve`：将案件标记为已处理。
- `/auto_mod`：切换或设置自动管理功能。
- `/auto_mod_status`：查看自动管理状态。

## 系统与电脑状态

- `/pc_status`：查看主机 CPU、RAM、磁盘、网络或 GPU 状态。
- `/pc_monitor_start`：启动状态监控。
- `/pc_monitor_stop`：停止状态监控。
- `/pc_action`：执行预设系统动作。
- `/bot_mode`：切换 Bot 模式，例如 normal、eco、emergency。
- `/bot_mode_status`：查看当前 Bot 模式。
- `/bot_guard_set`：设置高温保护或安全模式相关参数。

## 音乐功能

- `/music_add`：加入音乐文件或音乐项目。
- `/music_list`：查看音乐库。
- `/music_remove`：移除音乐项目。
- `/go_music`：加入语音频道并开始播放。
- `/music_queue`：查看播放队列。
- `/music_now`：查看当前播放项目。
- `/music_pause`：暂停。
- `/music_resume`：继续播放。
- `/music_skip`：跳过当前项目。
- `/music_stop`：停止播放并清空队列。
- `/music_volume`：调整音量。
- `/music_loop`：切换循环播放。

## 使用提醒

部分命令需要管理员身份组、指定频道或 Discord Bot 权限。实际可用性会受到 `.env` 设置、服务器权限与 Discord Developer Portal 权限影响。
