# Moderation Rules

> **繁體中文版本說明**  
> 本文件使用較中性的繁體中文（zh-TW）用語整理。不同社群、地區與伺服器可能有不同規則與語境；實際部署時，請依自己的伺服器規則、Discord 平台規範與適用法律調整。

本文件說明 `moderation_rules.example.json` 的欄位用途。

此檔案是違規偵測規則範例，正式使用時可以依照自己的 Discord 伺服器規則調整。

## 檔案用途

`moderation_rules.example.json` 用來示範 Bot 的違規詞偵測規則格式。

實際執行時，Bot 可能會在 `data/` 內保存或更新規則資料，例如：

```text
data/moderation_rules.json
```

請勿將實際運行後的 `data/moderation_rules.json` 上傳到公開 GitHub，因為它可能包含伺服器內部規則、誤判案例或管理紀錄。

## 欄位說明

### `blocked_terms`

中文違規詞、辱罵詞或需要審查的關鍵字清單。

範例：

```json
"blocked_terms": [
  "測試違規",
  "違規功能測試"
]
```

如果訊息內容包含這些詞，Bot 可能會建立案件或送出管理回報；實際處理仍建議由管理員確認。

---

### `english_abuse_terms`

英文辱罵詞或需要審查的關鍵字清單。

範例：

```json
"english_abuse_terms": [
  "idiot",
  "stupid"
]
```

英文偵測會使用 Unicode NFKC 與 casefold，因此通常不分大小寫。

例如：

```text
IDIOT
Idiot
idiot
```

會被視為相近內容。

---

### `sexual_terms`

成人內容、不適合公開討論或需要管理員注意的內容關鍵字。

範例：

```json
"sexual_terms": [
  "xxx",
  "18+"
]
```

此欄位應依照伺服器規則、平台規範與適用法律自行調整。

---

### `spam_terms`

垃圾訊息、詐騙、廣告或可疑連結關鍵字。

範例：

```json
"spam_terms": [
  "free nitro",
  "click this link",
  "保證獲利"
]
```

適合放入常見詐騙、洗版、廣告或外掛下載相關詞彙。

---

### `target_patterns`

判斷訊息是否可能「針對某人」的線索。

範例：

```json
"target_patterns": [
  "你",
  "妳",
  "you",
  "your"
]
```

這些詞通常不應單獨視為違規，而是用來輔助判斷訊息是否可能是針對他人的攻擊。

例如：

```text
you are stupid
```

如果同時命中 `english_abuse_terms` 與 `target_patterns`，Bot 可能會標記為 `targeted_attack`，但仍建議由管理員確認語境。

---

### `safe_phrases`

誤判排除詞。

範例：

```json
"safe_phrases": [
  "程式碼範例",
  "引用規則說明",
  "功能測試"
]
```

如果訊息包含 `safe_phrases`，Bot 會優先降低或排除違規判定。

適合放入：

* 教學情境
* 程式碼範例
* 規則引用
* 測試訊息
* 常見誤判案例

---

### `notes`

規則說明備註。

範例：

```json
"notes": [
  "英文偵測會使用 Unicode NFKC + casefold，因此不分大小寫。"
]
```

此欄位主要給管理員或開發者閱讀，不一定會影響 Bot 判斷。

## 注意事項

請避免放入過度寬泛的詞，例如單獨的「你」、「我」、「他」作為違規詞。
這類詞適合放在 `target_patterns`，不適合放在 `blocked_terms`。

建議先用較保守的規則測試，確認不會大量誤判後，再逐步增加偵測詞。

如果某個詞經常誤判，可以加入 `safe_phrases`，或使用 Bot 的相關管理指令新增例外。

## 案件與討論串系統

當 Bot 偵測到疑似違規訊息時，會建立一筆案件紀錄，並依照 `.env` 設定將案件回報到指定頻道。

相關設定：

```env id="k9y4ar"
REPORT_CHANNEL_ID=
CREATE_CASE_THREADS=
CASE_THREAD_ARCHIVE_MINUTES=
REPORT_WEBHOOK_URL=
```

### `REPORT_CHANNEL_ID`

案件回報頻道 ID。

當 Bot 偵測到違規訊息時，會將案件摘要送到這個頻道。
回報內容通常包含：

* 案件 ID
* 使用者資訊
* 觸發的規則分類與詞彙
* 原始訊息內容
* 訊息連結
* 是否為針對性攻擊
* 是否達到自動禁言建議
* Bot 已採取或建議的處理動作

建議建立一個只有管理員可見的頻道，例如：

```text id="lp4t91"
#mod-reports
#管理紀錄
#bot-cases
```

請不要把案件回報頻道設為公開頻道，避免公開使用者紀錄、誤判內容或管理討論。

---

### `CREATE_CASE_THREADS`

是否為每個案件建立 Discord 討論串。

```env id="j1hbtb"
CREATE_CASE_THREADS=true
```

啟用後，每當 Bot 在回報頻道送出案件訊息時，會嘗試在該訊息下建立一個討論串。

討論串名稱大致會像：

```text id="qc3ahr"
警告案件 C0001 - 使用者名稱
```

討論串用途：

* 集中討論同一個案件
* 補充上下文或證據
* 判斷是否誤判
* 記錄管理員處理結果
* 使用 `/case_ignore`、`/case_resolve`、`/punish` 等指令處理案件

如果不想讓每個案件都產生討論串，可以設定：

```env id="gdn2b8"
CREATE_CASE_THREADS=false
```

這樣 Bot 只會在回報頻道送出案件訊息，不會另外建立討論串。

---

### `CASE_THREAD_ARCHIVE_MINUTES`

案件討論串自動封存時間，單位是分鐘。

範例：

```env id="eb7pj6"
CASE_THREAD_ARCHIVE_MINUTES=1440
```

代表討論串在一段時間沒有活動後會自動封存。

常見設定：

```text id="5lh98x"
60     = 1 小時
1440   = 1 天
4320   = 3 天
10080  = 7 天
```

實際可用時間可能會受到 Discord 伺服器設定或權限限制影響。

---

### `REPORT_WEBHOOK_URL`

Webhook 回報 URL。

如果沒有設定 `REPORT_CHANNEL_ID`，或 Bot 無法正常取得回報頻道，程式可以改用 Webhook 發送案件回報。

```env id="l23zxb"
REPORT_WEBHOOK_URL=
```

注意：

* Webhook URL 屬於敏感資料，請不要上傳到 GitHub。
* 如果 Webhook URL 曾經公開，請立即刪除舊 Webhook 並重新建立。
* 使用 Webhook 回報時，不一定會有案件討論串功能；建議優先使用 `REPORT_CHANNEL_ID`。

---

## 案件處理流程

一般流程如下：

```text id="q891f7"
使用者發送訊息
↓
Bot 偵測違規詞 / spam / 針對性攻擊
↓
建立案件 ID
↓
送出案件回報到 REPORT_CHANNEL_ID
↓
若 CREATE_CASE_THREADS=true，建立案件討論串
↓
管理員在討論串中確認情境
↓
管理員使用指令處理案件
```

常用處理指令：

```text id="u9jg8t"
/case_ignore case_id:C0001 reason:誤判 add_safe_phrase:可選
/case_resolve case_id:C0001 action:warn reason:已處理
/punish user:@對象 minutes:5 reason:原因 confirm:true
/safe_add phrase:例外詞 reason:原因
```

---

## 誤判處理建議

如果案件是誤判，可以使用：

```text id="etzpbt"
/case_ignore case_id:C0001 reason:教學情境 add_safe_phrase:程式碼範例
```

這會將案件標記為忽略，並可選擇加入 `safe_phrases`，降低之後相同情境再次誤判的機率。

如果案件確認為違規，可以使用：

```text id="js9zrs"
/case_resolve case_id:C0001 action:warn reason:已人工確認
```

如果需要實際處罰，可以使用：

```text id="lx3j7b"
/punish user:@對象 minutes:5 reason:多次違規 confirm:true
```

建議高風險操作，例如禁言、踢出、封鎖、刪除訊息，都由管理員人工確認後再執行。
