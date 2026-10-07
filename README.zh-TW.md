# java-backend for Claude Code

[![Validate](https://github.com/xinqilin/claude-dev-toolkit-marketplace/actions/workflows/validate.yml/badge.svg)](https://github.com/xinqilin/claude-dev-toolkit-marketplace/actions/workflows/validate.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

繁體中文 | [English](./README.md)

**一個 Claude Code plugin，用資深後端工程師的方式審查、測試、設計 Spring Boot 服務：清楚知道 Spring Data JPA、Hibernate、MySQL、PostgreSQL 在並行和高負載下的實際行為。**

## 做深，不做廣

這個 plugin 只涵蓋一個技術組合，但做得很深：Spring Boot 4.1（並註明 3.x 的差異）、Spring Data JPA / Hibernate 7、MySQL 8.4、PostgreSQL 18。裡面每一句關於行為的描述，都對照過原廠文件或原始碼，每份 reference 檔都列出來源。

一般審查常漏掉、它能抓到的問題：

- **看起來正確的 lost update**：包在 `@Transactional` 裡的「讀出、修改、寫回」，在 MySQL 的 REPEATABLE READ 下照樣會少算錢；PostgreSQL 的 REPEATABLE READ 則會丟出 40001。plugin 會看你用的是哪一個資料庫。
- **Write skew**：兩個請求各自通過檢查，合起來卻破壞了規則。plugin 會指出該用哪一種防護：SERIALIZABLE 搭配重試、加鎖，或 constraint。
- **和版本有關的 JPA 行為**：collection fetch join 搭配 `Pageable`，在 Hibernate 7.4 之前會在記憶體裡分頁，7.4 起改在資料庫端分頁（MySQL、PostgreSQL）。`IDENTITY` 主鍵會悄悄讓批次 INSERT 失效。
- **Index 設計**：等值欄位在前、範圍或排序欄位在後，而不是「選擇性最高的欄位放最前面」。也清楚 MySQL 隱式型別轉換的陷阱，以及 online DDL 的 metadata lock。
- **Spring Boot 4 的測試**：用 `@MockitoBean` 取代已移除的 `@MockBean`、知道 test slice 搬過 package、會用 Testcontainers 2，並寫出真正證明得了東西的並行測試。

## 安裝

在 Claude Code 裡執行：

```text
/plugin marketplace add xinqilin/claude-dev-toolkit-marketplace
/plugin install java-backend@xinqilin
```

plugin 的 `version` 變更時才會收到新版。可以執行 `claude plugin update java-backend@xinqilin`，或在 `/plugin` → **Marketplaces** → `xinqilin` 開啟自動更新。

建議搭配官方的 Java language server plugin，讓 Claude 改完程式碼就能看到編譯錯誤：

```text
/plugin install jdtls-lsp@claude-plugins-official
```

需要先把 `jdtls` 裝在 `PATH` 上。

## 指令

| 指令 | 做什麼 | 在哪裡執行 |
|------|--------|-----------|
| `/java-backend:code-review [path]` | 審查 Java 程式碼：先看資料存取和交易，再看 Clean Code 和過度設計 | `code-reviewer`（唯讀） |
| `/java-backend:review-pr [pr \| branch] [base]` | 審查 GitHub PR（透過 `gh`）或 branch 差異 | `code-reviewer`（唯讀） |
| `/java-backend:review-test [path]` | 審查測試是否涵蓋真實行為，以及 Spring 測試的陷阱 | `test-reviewer`（唯讀） |
| `/java-backend:write-test [class]` | 依專案慣例寫測試，並執行到全部通過 | 你的對話 |
| `/java-backend:optimize-query [query \| file]` | 從執行計畫找出真正的瓶頸，提出可量測的改善 | `data-architect`（唯讀） |
| `/java-backend:design-solution [requirement]` | 設計功能，明確寫出一致性防護和可執行的計畫 | 你的對話 |

也可以直接問（「幫我 review 這個 service」、「這個查詢為什麼慢？」），相關知識會在需要時自動載入。

## 運作方式

每個審查指令都在一個唯讀的小幫手 agent 裡執行，開工前就已載入相關知識：交易與隔離等級、JPA/Hibernate、SQL 效能、測試，以及 Spring Boot 的版本差異。給建議之前，它會先讀你的 `pom.xml` 或 `build.gradle` 和 `application.yml`，讓建議符合你的 Spring Boot、Hibernate 和資料庫版本。

核心觀念的圖解說明（中英雙語）：**https://xinqilin.github.io/claude-dev-toolkit-marketplace/**

## Eval

`plugins/java-backend/evals/` 有 6 個 case（MySQL 的 lost update、PostgreSQL 的 write skew、fetch join 分頁、IDENTITY 批次寫入、複合 index 順序、Spring Boot 4 測試）。每個 case 都會和「沒裝 plugin」的對照組比較：

```bash
claude plugin eval plugins/java-backend --runs 3 --model sonnet --judge-model haiku --max-cost-usd 15 --no-publish
```

第一次完整跑完後，結果會公布在這裡。

## 常見問題

**和 Claude Code 內建的 `/code-review` 有什麼不同？**
內建的審查會找出 diff 裡的正確性 bug，適用任何語言。`java-backend` 補上它沒有的技術知識：各資料庫的隔離語意、Hibernate 各版本的行為、Spring Boot 3 和 4 的 API 差異。兩者可以一起用。

**它用什麼語言回答？**
跟你一樣。plugin 的檔案是英文寫的，但每個指令都會用你提問的語言回答。

**它會改我的程式碼嗎？**
審查和分析類的指令都是唯讀的。`/java-backend:write-test` 和 `/java-backend:design-solution` 在你的對話裡執行，每次修改你都看得到，也要經過你同意。

**從 1.x（`bill-*` plugin）升級？**
請看 [CHANGELOG.md](CHANGELOG.md#upgrading-from-1x)。

## 貢獻

附上官方來源的修正，是最有價值的貢獻。請看 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 授權

Copyright 2025-2026 Bill Lin。以 [Apache License 2.0](LICENSE) 授權。
