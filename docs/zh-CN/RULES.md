# Moderation Rules

> **简体中文版本说明**  
> 本文档使用较中性的简体中文（zh-CN）术语整理。不同社群、地区与服务器可能有不同规则和语境；实际部署时，请根据自己的服务器规则、Discord 平台规范与适用法律进行调整。

本文档说明 `moderation_rules.example.json` 的字段用途。

此文件是违规检测规则示例，正式使用时可以根据自己的 Discord 服务器规则调整。

## 文件用途

`moderation_rules.example.json` 用于示范 Bot 的违规词检测规则格式。

实际运行时，Bot 可能会在 `data/` 内保存或更新规则数据，例如：

```text
data/moderation_rules.json
```

请勿将实际运行后的 `data/moderation_rules.json` 上传到公开 GitHub，因为它可能包含服务器内部规则、误判案例或管理记录。

## 字段说明

### `blocked_terms`

中文违规词、辱骂词或需要审核的关键词列表。

示例：

```json
"blocked_terms": [
  "测试违规",
  "违规功能测试"
]
```

如果消息内容包含这些词，Bot 可能会创建案件或发送管理报告；实际处理仍建议由管理员确认。

---

### `english_abuse_terms`

英文辱骂词或需要审核的关键词列表。

示例：

```json
"english_abuse_terms": [
  "idiot",
  "stupid"
]
```

英文检测会使用 Unicode NFKC 与 casefold，因此通常不分大小写。

例如：

```text
IDIOT
Idiot
idiot
```

会被视为相近内容。

---

### `sexual_terms`

成人内容、不适合公开讨论或需要管理员注意的内容关键词。

示例：

```json
"sexual_terms": [
  "xxx",
  "18+"
]
```

此字段应根据服务器规则、平台规范与适用法律自行调整。

---

### `spam_terms`

垃圾消息、诈骗、广告或可疑连结关键词。

示例：

```json
"spam_terms": [
  "free nitro",
  "click this link",
  "保证获利"
]
```

适合加入常见诈骗、洗版、广告或外挂下载相关词汇。

---

### `target_patterns`

判断消息是否可能「针对某人」的线索。

示例：

```json
"target_patterns": [
  "你",
  "you",
  "your"
]
```

这些词通常不应单独视为违规，而是用来辅助判断消息是否可能是针对他人的攻击。

例如：

```text
you are stupid
```

如果同时命中 `english_abuse_terms` 与 `target_patterns`，Bot 可能会标记为 `targeted_attack`，但仍建议由管理员确认语境。

---

### `safe_phrases`

误判排除词。

示例：

```json
"safe_phrases": [
  "代码示例",
  "引用规则说明",
  "功能测试"
]
```

如果消息包含 `safe_phrases`，Bot 会优先降低或排除违规判定。

适合加入：

* 教学场景
* 代码示例
* 规则引用
* 测试消息
* 常见误判案例

---

### `notes`

规则说明备注。

示例：

```json
"notes": [
  "英文检测会使用 Unicode NFKC + casefold，因此不分大小写。"
]
```

此字段主要给管理员或开发者閱读，不一定会影响 Bot 判断。

## 注意事项

请避免放入过于宽泛的词，例如单独的「你」、「我」、「他」作为违规词。
这类词适合放在 `target_patterns`，不适合放在 `blocked_terms`。

建议先用较保守的规则测试，确认不会大量误判后，再逐步增加检测词。

如果某个词經常误判，可以加入 `safe_phrases`，或使用 Bot 的相关管理指令新增例外。

## 案件与讨论串系统

当 Bot 检测到疑似违规消息时，会创建一筆案件记录，并按照 `.env` 设置将案件报告到指定频道。

相关设置：

```env id="k9y4ar"
REPORT_CHANNEL_ID=
CREATE_CASE_THREADS=
CASE_THREAD_ARCHIVE_MINUTES=
REPORT_WEBHOOK_URL=
```

### `REPORT_CHANNEL_ID`

案件报告频道 ID。

当 Bot 检测到违规消息时，会将案件摘要送到这个频道。
报告内容通常包含：

* 案件 ID
* 用户资讯
* 触发的规则分类与词汇
* 原始消息内容
* 消息连结
* 是否为针对性攻击
* 是否達到自动禁言建议
* Bot 已採取或建议的处理动作

建议创建一个只有管理员可见的频道，例如：

```text id="lp4t91"
#mod-reports
#管理记录
#bot-cases
```

请不要把案件报告频道设为公开频道，避免公开用户记录、误判内容或管理讨论。

---

### `CREATE_CASE_THREADS`

是否为每个案件创建 Discord 讨论串。

```env id="j1hbtb"
CREATE_CASE_THREADS=true
```

启用后，每当 Bot 在报告频道送出案件消息时，会嘗試在该消息下创建一个讨论串。

讨论串名称大致会像：

```text id="qc3ahr"
警告案件 C0001 - 用户名称
```

讨论串用途：

* 集中讨论同一个案件
* 补充上下文或证据
* 判断是否误判
* 记录管理员处理结果
* 使用 `/case_ignore`、`/case_resolve`、`/punish` 等指令处理案件

如果不想让每个案件都产生讨论串，可以设置：

```env id="gdn2b8"
CREATE_CASE_THREADS=false
```

这样 Bot 只会在报告频道送出案件消息，不会另外创建讨论串。

---

### `CASE_THREAD_ARCHIVE_MINUTES`

案件讨论串自动归档时間，单位是分钟。

示例：

```env id="eb7pj6"
CASE_THREAD_ARCHIVE_MINUTES=1440
```

代表讨论串在一段时間沒有活动后会自动归档。

常见设置：

```text id="5lh98x"
60     = 1 小时
1440   = 1 天
4320   = 3 天
10080  = 7 天
```

实际可用时間可能会受到 Discord 服务器设置或权限限制影响。

---

### `REPORT_WEBHOOK_URL`

Webhook 报告 URL。

如果沒有设置 `REPORT_CHANNEL_ID`，或 Bot 無法正常取得报告频道，程序可以改用 Webhook 发送案件报告。

```env id="l23zxb"
REPORT_WEBHOOK_URL=
```

注意：

* Webhook URL 属于敏感数据，请不要上传到 GitHub。
* 如果 Webhook URL 曾經公开，请立即删除舊 Webhook 并重新创建。
* 使用 Webhook 报告时，不一定会有案件讨论串功能；建议優先使用 `REPORT_CHANNEL_ID`。

---

## 案件处理流程

一般流程如下：

```text id="q891f7"
用户发送消息
↓
Bot 检测违规词 / spam / 针对性攻击
↓
创建案件 ID
↓
送出案件报告到 REPORT_CHANNEL_ID
↓
若 CREATE_CASE_THREADS=true，创建案件讨论串
↓
管理员在讨论串中确认场景
↓
管理员使用指令处理案件
```

常用处理指令：

```text id="u9jg8t"
/case_ignore case_id:C0001 reason:误判 add_safe_phrase:可选
/case_resolve case_id:C0001 action:warn reason:已处理
/punish user:@对象 minutes:5 reason:原因 confirm:true
/safe_add phrase:例外词 reason:原因
```

---

## 误判处理建议

如果案件属于误判，可以使用：

```text id="etzpbt"
/case_ignore case_id:C0001 reason:教学场景 add_safe_phrase:代码示例
```

这会将案件标记为忽略，并可选择加入 `safe_phrases`，降低之后相同场景再次误判的机率。

如果案件确认为违规，可以使用：

```text id="js9zrs"
/case_resolve case_id:C0001 action:warn reason:已人工确认
```

如果需要实际处罚，可以使用：

```text id="lx3j7b"
/punish user:@对象 minutes:5 reason:多次违规 confirm:true
```

建议高风险操作，例如禁言、踢出、封禁、删除消息，都由管理员人工确认后再运行。
