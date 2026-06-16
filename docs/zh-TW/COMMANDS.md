# 指令摘要

本文件提供各語系的簡要指令介紹。完整指令與行為仍以主文件 `docs/COMMANDS.md` 與實際程式為準。

## 一般使用者指令

- `/status`：查看 Bot 基本狀態。
- `/ai`：向本地 Ollama AI 發送問題。
- `@bot 訊息`：用提及方式請 Bot 回覆。
- `/my_warnings`：查看自己的警告紀錄。
- `/my_profile`：查看自己的互動摘要或基本 profile。

## 管理與違規處理

- `/warn`：對使用者加入警告紀錄。
- `/anger`：查看或確認使用者目前的怒氣值狀態。
- `/calm`：降低或重置使用者的怒氣值。
- `/punish`：依管理員判斷執行處理動作。
- `/mod_suggest`：產生管理建議，協助管理員判斷。
- `/remove_warning`：移除特定警告紀錄。

## 規則與安全詞

- `/banword_add`：新增違規詞。
- `/banword_remove`：移除違規詞。
- `/banword_list`：查看違規詞清單。
- `/safe_add`：新增安全詞或白名單用語。
- `/safe_remove`：移除安全詞。
- `/safe_list`：查看安全詞清單。

## 案件與自動管理

- `/case_ignore`：忽略指定案件。
- `/case_resolve`：將案件標記為已處理。
- `/auto_mod`：切換或設定自動管理功能。
- `/auto_mod_status`：查看自動管理狀態。

## 系統與電腦狀態

- `/pc_status`：查看主機 CPU、RAM、磁碟、網路或 GPU 狀態。
- `/pc_monitor_start`：啟動狀態監控。
- `/pc_monitor_stop`：停止狀態監控。
- `/pc_action`：執行預設系統動作。
- `/bot_mode`：切換 Bot 模式，例如 normal、eco、emergency。
- `/bot_mode_status`：查看目前 Bot 模式。
- `/bot_guard_set`：設定高溫保護或安全模式相關參數。

## 音樂功能

- `/music_add`：加入音樂檔案或音樂項目。
- `/music_list`：查看音樂庫。
- `/music_remove`：移除音樂項目。
- `/go_music`：加入語音頻道並開始播放。
- `/music_queue`：查看播放佇列。
- `/music_now`：查看目前播放項目。
- `/music_pause`：暫停。
- `/music_resume`：繼續播放。
- `/music_skip`：跳過目前項目。
- `/music_stop`：停止播放並清空佇列。
- `/music_volume`：調整音量。
- `/music_loop`：切換循環播放。

## 使用提醒

部分指令需要管理員身分組、指定頻道或 Discord Bot 權限。實際可用性會受到 `.env` 設定、伺服器權限與 Discord Developer Portal 權限影響。
