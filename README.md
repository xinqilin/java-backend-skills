# Bill Lin Dev Toolkit

[繁體中文](./README.zh-TW.md) | English

Enterprise-grade Java/Spring Boot development toolkit with 4 independent professional plugins.

## Quick Overview

### 4 Independent Plugins

#### 1. bill-billing-unit-test-reviewer

Focused on unit test review and best practices

- **Agent**: bill-billing-unit-test-reviewer
- **Skill**: `/review-test` - Unit test code review
- **Expertise**: TDD, test design, coverage analysis, avoiding over-engineering

#### 2. bill-code-reviewer

Code quality review and PR Review

- **Agent**: bill-code-reviewer (preloads effective-java, clean-architecture skills)
- **Skills**:
  - `/code-review` - Code quality review (Clean Code + avoiding over-engineering)
  - `/review-pr` - PR change review (branch diff or GitHub PR, runs in forked context)
- **Expertise**: Clean Code, avoiding over-engineering, architecture evaluation, PR Review

#### 3. bill-java-developer

Spring Boot development and database optimization expert

- **Agent**: bill-java-developer (preloads effective-java, clean-architecture, mysql-optimization skills)
- **Skills**:
  - `/design-solution` - Technical solution design and recommendations
  - `/optimize-query` - SQL/JPA optimization (runs in forked context)
- **Expertise**: Spring Boot, JPA, database performance, enterprise architecture

#### 4. bill-java-skills

Java development best practices knowledge base

- **Skills** (preloaded by agents, not shown in `/` menu):
  - `clean-architecture` - Clean Architecture design principles
  - `effective-java` - Effective Java best practices
  - `mysql-optimization` - MySQL performance optimization and JPA tuning

> **Difference between Skills and Agents**:
>
> - **Skills** (`/xxx`): Slash commands or auto-triggered knowledge base
> - **Agents**: Automatically start based on conversation, provide interactive assistance

### Agent Advanced Features

- **Knowledge Preloading**: bill-java-developer and bill-code-reviewer agents automatically preload relevant knowledge skills (effective-java, clean-architecture, mysql-optimization) — no manual invocation needed
- **Project Memory**: All agents support project-level memory, remembering project-specific patterns and conventions across sessions
- **Safety Restrictions**: Reviewer agents have read-only permissions and will not accidentally modify code
- **Gotchas Protection**: Every skill includes a curated Gotchas section — common pitfalls that Claude tends to fall into, ensuring higher quality output

## Installation

### Option 1: Via /plugin marketplace (recommended, no clone needed)

In Claude Code, run:
```
/plugin marketplace add xinqilin/claude-dev-toolkit-marketplace
```

### Option 2: Via install.sh (after cloning, uses symlinks — auto-updates on git pull)

```bash
git clone https://github.com/xinqilin/claude-dev-toolkit-marketplace
cd claude-dev-toolkit-marketplace
./install.sh --all
```

### Install Specific Plugins

```bash
# List available plugins
./install.sh --list

# Install only what you need
./install.sh --plugin bill-code-reviewer
./install.sh --plugin bill-java-developer
./install.sh --plugin bill-java-skills
./install.sh --plugin bill-billing-unit-test-reviewer
```

### Uninstall

```bash
./uninstall.sh
```

### Update

**install.sh users**: `git pull` — symlinks auto-update, no reinstall needed.

```bash
git pull
```

**marketplace users**: A new release reaches you only when the plugin's `version` changes, and auto-update is off by default for this marketplace. Update on demand:

```bash
claude plugin update <plugin-name>@bill-lin-dev-toolkit
```

Or turn on auto-update once: `/plugin` → **Marketplaces** → `bill-lin-dev-toolkit` → **Enable auto-update**. Updates apply in the next session or after `/reload-plugins`.

## Quick Start

### Using Slash Commands

#### Code Review

```text
/code-review src/main/java/com/example/OrderService.java
```

#### PR Review

```text
# Review GitHub PR (requires gh CLI)
/review-pr 123
/review-pr #456

# Review current branch diff against master
/review-pr

# Review feature-branch against develop
/review-pr feature-branch develop
```

**Note**: GitHub PR review requires `gh` CLI:

```bash
brew install gh
gh auth login
```

#### Spring Boot Development

```text
/design-solution
[Describe your requirements or problem]

/optimize-query
[Paste your SQL or JPA code]
```

> **Tip**: mysql-optimization knowledge is automatically preloaded into the bill-java-developer agent.

#### Unit Test Review

```text
/review-test src/test/java/com/example/OrderServiceTest.java
```

### Using Agents

Agents automatically activate based on conversation context:

- **Java Developer Agent**: "I need to design a high-concurrency order system"
- **Code Reviewer Agent**: "Please review this code's quality"
- **Unit Test Reviewer Agent**: "Please review my unit test design"

### Auto-Triggered Skills (bill-java-skills)

Knowledge skills (clean-architecture, effective-java, mysql-optimization) are preloaded into agents automatically — see [Agent Advanced Features](#agent-advanced-features) above.

## Directory Structure

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

## License

Copyright 2025-2026 Bill Lin. Licensed under the [Apache License 2.0](LICENSE).
