# Bill Lin Dev Toolkit

繁體中文 | [English](./README.md)

企業級 Java/Spring Boot 開發工具包，提供 4 個獨立的專業 plugins。

## 快速概覽

### 4 個獨立 Plugins

#### 1. bill-billing-unit-test-reviewer

專注於單元測試審查與最佳實踐

- **Agent**: bill-billing-unit-test-reviewer
- **Skill**: `/review-test` - 單元測試程式碼審查
- **專長**: TDD、測試設計、覆蓋率分析、避免過度設計

#### 2. bill-code-reviewer

程式碼品質審查與 PR Review

- **Agent**: bill-code-reviewer（預載 effective-java、clean-architecture skills）
- **Skills**:
  - `/code-review` - 程式碼品質審查（Clean Code + 避免過度設計）
  - `/review-pr` - PR 變更審查（branch 差異或 GitHub PR，在 forked context 中執行）
- **專長**: Clean Code、避免過度設計、架構評估、PR Review

#### 3. bill-java-developer

Spring Boot 開發與資料庫優化專家

- **Agent**: bill-java-developer（預載 effective-java、clean-architecture、mysql-optimization skills）
- **Skills**:
  - `/design-solution` - 技術方案設計與建議
  - `/optimize-query` - SQL/JPA 優化（在 forked context 中執行）
- **專長**: Spring Boot、JPA、資料庫效能、企業架構

#### 4. bill-java-skills

Java 開發最佳實踐知識庫

- **Skills**（被 agents 預載，不出現在 `/` 選單中）:
  - `clean-architecture` - Clean Architecture 設計原則
  - `effective-java` - Effective Java 最佳實踐
  - `mysql-optimization` - MySQL 效能優化與 JPA 調校

> **Skills vs Agents 的區別**:
>
> - **Skills** (`/xxx`): Slash command 或自動觸發的知識庫
> - **Agents**: 根據對話自動啟動，提供互動式協助

### Agent 進階能力

- **知識預載**：bill-java-developer 和 bill-code-reviewer agents 會自動預載相關知識 skills（effective-java、clean-architecture、mysql-optimization），不需手動觸發
- **專案記憶**：所有 agents 支援 project-level memory，會跨 session 記住專案特有的模式和慣例
- **安全限制**：reviewer agents 僅具唯讀權限，不會意外修改程式碼
- **Gotchas 防護**：每個 skill 都包含精選的 Gotchas 區塊 — Claude 常犯的錯誤陷阱，確保更高品質的輸出

## 安裝

### 方式一：透過 /plugin marketplace（推薦，免 clone）

在 Claude Code 中執行：
```
/plugin marketplace add xinqilin/claude-dev-toolkit-marketplace
```

### 方式二：透過 install.sh（clone 後使用 symlinks，git pull 自動更新）

```bash
git clone https://github.com/xinqilin/claude-dev-toolkit-marketplace
cd claude-dev-toolkit-marketplace
./install.sh --all
```

### 安裝指定 Plugin

```bash
# 查看可用的 plugins
./install.sh --list

# 只安裝你需要的
./install.sh --plugin bill-code-reviewer
./install.sh --plugin bill-java-developer
./install.sh --plugin bill-java-skills
./install.sh --plugin bill-billing-unit-test-reviewer
```

### 卸載

```bash
./uninstall.sh
```

### 更新

**install.sh 使用者**：直接 `git pull`，symlink 自動更新，不需重新安裝。

```bash
git pull
```

**marketplace 使用者**：只有 plugin 的 `version` 變更時才會收到新版，且此 marketplace 預設不自動更新。手動更新：

```bash
claude plugin update <plugin-name>@bill-lin-dev-toolkit
```

或一次開啟自動更新：`/plugin` → **Marketplaces** → `bill-lin-dev-toolkit` → **Enable auto-update**。更新會在下個 session 或執行 `/reload-plugins` 後生效。

## 快速開始

### 使用 Slash Commands

#### 程式碼審查

```text
/code-review src/main/java/com/example/OrderService.java
```

#### PR 審查

```text
# 審查 GitHub PR（需要 gh CLI）
/review-pr 123
/review-pr #456

# 審查當前 branch 對 master 的差異
/review-pr

# 審查 feature-branch 對 develop 的差異
/review-pr feature-branch develop
```

**注意**：審查 GitHub PR 需要安裝 `gh` CLI：

```bash
brew install gh
gh auth login
```

#### Spring Boot 開發

```text
/design-solution
[描述你的需求或問題]

/optimize-query
[貼上你的 SQL 或 JPA 程式碼]
```

> **提示**：mysql-optimization 知識已自動預載到 bill-java-developer agent 中。

#### 單元測試審查

```text
/review-test src/test/java/com/example/OrderServiceTest.java
```

### 使用 Agents

Agents 根據對話內容自動啟動：

- **Java Developer Agent**: "我需要設計一個高併發訂單系統"
- **Code Reviewer Agent**: "請審查這段程式碼的品質"
- **Unit Test Reviewer Agent**: "請審查我的單元測試設計"

### 自動觸發 Skills（bill-java-skills）

知識 skills（clean-architecture、effective-java、mysql-optimization）已自動預載到 agents 中，無需手動觸發 — 詳見上方 [Agent 進階能力](#agent-進階能力)。

## 目錄結構

```plaintext
project-claude-code-plugins/
├── plugins/
│   ├── bill-billing-unit-test-reviewer/
│   │   ├── agents/
│   │   │   └── bill-billing-unit-test-reviewer.md
│   │   └── skills/
│   │       └── review-test/
│   │           └── SKILL.md
│   ├── bill-code-reviewer/
│   │   ├── agents/
│   │   │   └── bill-code-reviewer.md
│   │   └── skills/
│   │       ├── code-review/
│   │       │   └── SKILL.md
│   │       └── review-pr/
│   │           └── SKILL.md
│   ├── bill-java-developer/
│   │   ├── agents/
│   │   │   └── bill-java-developer.md
│   │   └── skills/
│   │       ├── design-solution/SKILL.md
│   │       └── optimize-query/SKILL.md
│   └── bill-java-skills/
│       └── skills/
│           ├── clean-architecture/
│           │   ├── SKILL.md
│           │   └── references/
│           ├── effective-java/
│           │   ├── SKILL.md
│           │   └── references/
│           └── mysql-optimization/
│               ├── SKILL.md
│               └── references/
├── install.sh
├── uninstall.sh
├── CLAUDE.md
└── README.md
```

## GitHub Repository

[https://github.com/xinqilin/claude-dev-toolkit-marketplace](https://github.com/xinqilin/claude-dev-toolkit-marketplace)

## 授權

Copyright 2025-2026 Bill Lin。以 [Apache License 2.0](LICENSE) 授權。
