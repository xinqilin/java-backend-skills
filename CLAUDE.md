# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Claude Code plugin marketplace (`xinqilin`) that ships one plugin, `java-backend`: deep expertise for Spring Boot + Spring Data JPA/Hibernate + MySQL/PostgreSQL (transactions and isolation, JPA performance, indexing, code/PR/test review, test generation). The plugin is Markdown (agents, skills) plus JSON manifests; there is no application code and no build. Depth over breadth: anything outside that stack (MyBatis, other databases, observability, GC tuning) is out of scope.

## Architecture

```
.claude-plugin/marketplace.json    # Marketplace "xinqilin": one entry + renames map from the four v1 plugin names
plugins/java-backend/
  .claude-plugin/plugin.json       # name, version, Apache-2.0
  agents/*.md                      # Read-only subagents: code-reviewer, test-reviewer, data-architect
  skills/<name>/SKILL.md           # Workflow skills (slash commands) and knowledge skills (user-invocable: false)
  skills/<name>/references/*.md    # Detail loaded on demand; each file ends with a Sources list
  evals/                           # claude plugin eval cases
docs/                              # GitHub Pages: bilingual ELI5 explainers; not shipped with the plugin
```

How the pieces connect (verified in a live session on Claude Code 2.1.292):

- Review and analysis skills run with `context: fork` and `agent: java-backend:<agent>`. The value must be the scoped `plugin:agent` name: a bare name silently falls back to the general-purpose agent, which has Edit/Write.
- Agents preload knowledge skills with `skills:` entries written as `java-backend:<skill>`. Bare names also resolve, but scoped names cannot collide with a user's personal skill. A missing skill is skipped with only a debug-log warning.
- Agents are read-only (`disallowedTools: Edit, Write, NotebookEdit`) and do not set `memory`: with Edit/Write disallowed they cannot write memory, and the field only creates empty `.claude/agent-memory/` directories in the user's project.
- Skills that edit files or ask the user questions (`write-test`, `design-solution`) run in the main conversation, not in a fork.
- Plugin agents ignore `permissionMode`, `hooks`, `mcpServers`, and `initialPrompt`.
- Every component is namespaced: users run `/java-backend:<skill>`.

## Commands

```bash
claude plugin validate --strict .                     # marketplace.json, including the renames chain
claude plugin validate --strict plugins/java-backend  # plugin.json and agent frontmatter
claude --plugin-dir ./plugins/java-backend            # load the plugin from source for one session
claude --plugin-dir ./plugins/java-backend plugin details java-backend   # inventory and always-on token cost
claude plugin marketplace add ./                      # local marketplace; loads source files in place each session
claude plugin eval plugins/java-backend --runs 3 --max-cost-usd <cap> --no-publish   # evals vs. a no-plugin baseline; bills your plan
```

`validate` catches agent frontmatter that fails to parse, but not SKILL.md YAML errors, misspelled field names, or fields the plugin ignores.

## Content rules

- Baseline: Spring Boot 4.1 / Spring Framework 7, MySQL 8.4, current PostgreSQL. Note Spring Boot 3.x differences inline rather than forking content.
- Check every behavioral claim about MySQL, PostgreSQL, Hibernate, or Spring against official documentation (context7 or the vendor manual) before writing it; reference files end with a Sources list.
- Explain DDIA concepts in our own words with chapter pointers; never copy its text or figures.
- Write skills and agents in English and tell Claude to answer in the user's language; never hard-code an output language.
- Every SKILL.md has `## When to Apply` and `## Gotchas` (mistakes Claude actually makes). Keep SKILL.md under ~200 lines and move detail to `references/`.
- Keep descriptions short with trigger words first: descriptions are truncated when a user has many skills installed.
- No `model` field in agents or skills: the caller's session model runs everything.

## Releasing

- Bump `version` in `plugins/java-backend/.claude-plugin/plugin.json` on every release; marketplace users keep their cached copy until it changes. Don't also set a version in marketplace.json.
- Renaming the plugin breaks installs unless the old name is added to `renames` (append-only history).
- README.md and README.zh-TW.md mirror each other; edit both. Each docs/ page carries both languages.

## Gotchas

- In Claude Code's macOS sandbox, `gh` fails TLS verification (x509 OSStatus -26276). Use `curl` against api.github.com for reads, or run `gh` outside the sandbox with the user's consent.
