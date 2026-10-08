# java-backend for Claude Code and Codex

[![Validate](https://github.com/xinqilin/java-backend-skills/actions/workflows/validate.yml/badge.svg)](https://github.com/xinqilin/java-backend-skills/actions/workflows/validate.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)

[繁體中文](./README.zh-TW.md) | English

**A Claude Code and Codex plugin that reviews, tests, and designs Spring Boot services the way a senior backend engineer does: by knowing exactly how Spring Data JPA, Hibernate, MySQL, and PostgreSQL behave under concurrency and load.**

## Deep, not broad

The plugin covers one stack and goes deep on it: Spring Boot 4.1 (with 3.x differences noted), Spring Data JPA / Hibernate 7, MySQL 8.4, and PostgreSQL 18. Every behavioral claim in it was checked against vendor documentation or source code, and each reference file lists its sources.

What it catches that a generic review usually misses:

- **Lost updates in "correct-looking" code**: a `@Transactional` read-modify-write still loses money under MySQL's REPEATABLE READ. PostgreSQL's REPEATABLE READ raises 40001 instead. The plugin knows which database you run.
- **Write skew**: two requests each pass a check and break an invariant together. It names the guard that fixes it: SERIALIZABLE with retry, a lock, or a constraint.
- **Version-dependent JPA behavior**: a collection fetch join with `Pageable` pages in memory before Hibernate 7.4 and in the database from 7.4 on (MySQL, PostgreSQL). `IDENTITY` ids silently disable batch inserts.
- **Index design**: equality columns first and the range or sort column last, not "most selective first". It also knows the MySQL type-conversion trap and online DDL metadata locks.
- **Spring Boot 4 tests**: `@MockitoBean` instead of the removed `@MockBean`, moved test-slice packages, Testcontainers 2, and concurrency tests that actually prove something.

## Install

In Claude Code:

```text
/plugin marketplace add xinqilin/java-backend-skills
/plugin install java-backend@xinqilin
```

Updates arrive when the plugin's `version` changes. Run `claude plugin update java-backend@xinqilin`, or turn on auto-update under `/plugin` → **Marketplaces** → `xinqilin`.

Recommended companion: the official Java language server plugin, so Claude sees compile errors right after editing:

```text
/plugin install jdtls-lsp@claude-plugins-official
```

It needs `jdtls` on your `PATH`.

### Codex

Codex reads the same marketplace (tested with codex-cli 0.160.1):

```bash
codex plugin marketplace add xinqilin/java-backend-skills
codex plugin add java-backend@xinqilin
```

Call a skill by name, for example `$java-backend:code-review src/main/java/com/example/OrderService.java`. Differences from Claude Code:

- Codex does not load plugin agents, so the review commands run in your conversation instead of a read-only helper. Each one reads its agent's instructions and knowledge files itself; your Codex sandbox setting decides whether it may edit files.
- Knowledge may not load on its own when you just ask a question; name the skill to be sure.
- The evals below run on Claude Code only.

## Commands

| Command | What it does | Runs in |
|---------|--------------|---------|
| `/java-backend:code-review [path]` | Reviews Java code: data access and transactions first, then Clean Code and over-design | `code-reviewer` (read-only) |
| `/java-backend:review-pr [pr \| branch] [base]` | Reviews a GitHub PR (via `gh`) or a branch diff | `code-reviewer` (read-only) |
| `/java-backend:review-test [path]` | Reviews tests for real-behavior coverage and Spring test pitfalls | `test-reviewer` (read-only) |
| `/java-backend:write-test [class]` | Writes tests following your project's conventions, then runs them until green | your conversation |
| `/java-backend:optimize-query [query \| file]` | Finds the real bottleneck from the execution plan and proposes a measured fix | `data-architect` (read-only) |
| `/java-backend:design-solution [requirement]` | Designs a feature with explicit consistency guards and a buildable plan | your conversation |

You can also just ask ("review this service", "why is this query slow?"); the knowledge loads when it's relevant.

## How it works

Each review command runs in a read-only helper agent that starts with the relevant knowledge already loaded: transactions and isolation, JPA/Hibernate, SQL performance, testing, and Spring Boot version differences. Before giving advice, it reads your `pom.xml` or `build.gradle` and `application.yml`, so the advice matches your Spring Boot, Hibernate, and database versions.

Picture explainers of the core ideas, in English and Traditional Chinese: **https://xinqilin.github.io/java-backend-skills/**

## Evals

`plugins/java-backend/evals/` contains six cases (lost update on MySQL, write skew on PostgreSQL, fetch join pagination, IDENTITY batching, composite index order, Spring Boot 4 tests). Each runs with the plugin and against a no-plugin baseline:

```bash
claude plugin eval plugins/java-backend --runs 3 --model sonnet --judge-model haiku --max-cost-usd 15 --no-publish
```

Results will be published here after the first full run.

## FAQ

**How is this different from Claude Code's built-in `/code-review`?**
The built-in review looks for correctness bugs in a diff, in any language. `java-backend` adds stack knowledge it doesn't have: per-database isolation semantics, Hibernate version behaviors, and Spring Boot 3 vs 4 APIs. Use both.

**Which language does it answer in?**
Yours. The plugin's files are in English, and every command answers in the language you write in.

**Does it change my code?**
The review and analysis commands are read-only. `/java-backend:write-test` and `/java-backend:design-solution` run in your conversation, so you see and approve each edit.

**Upgrading from 1.x (`bill-*` plugins)?**
See [CHANGELOG.md](CHANGELOG.md#upgrading-from-1x).

## Contributing

Corrections with an official source are the most valuable contribution. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Copyright 2025-2026 Bill Lin. Licensed under the [Apache License 2.0](LICENSE).
