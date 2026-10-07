# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Claude Code plugin marketplace for Java/Spring Boot development: 4 plugins built only from Markdown (agents, skills) and JSON manifests. No application code, no build/test pipeline.

## Architecture

```
.claude-plugin/marketplace.json    # Marketplace manifest: lists every plugin (no versions here)
plugins/<plugin-name>/
  .claude-plugin/plugin.json       # Per-plugin manifest; the plugin's `version` lives here
  agents/<name>.md                 # Agent: YAML frontmatter + system prompt
  skills/<skill-name>/SKILL.md     # Skill: slash command or knowledge base
  skills/<skill-name>/references/  # Optional detail docs, read on demand
install.sh / uninstall.sh          # Symlink installer into ~/.claude/agents, ~/.claude/skills
README.md / README.zh-TW.md        # Mirrored EN / zh-TW docs; edit both together
```

## Two install modes, different runtime behavior

| | `/plugin marketplace add xinqilin/claude-dev-toolkit-marketplace` | `./install.sh` (symlinks) |
|---|---|---|
| Plugin list comes from | `marketplace.json` + each `plugin.json` | hardcoded `PLUGINS` array; manifests ignored |
| Skill command | `/<plugin>:<skill>` (namespaced) | `/<skill>` as a personal skill; replaces a bundled command of the same name (`code-review` shadows built-in `/code-review`) |
| Agent `permissionMode` | ignored, like `hooks`, `mcpServers`, `initialPrompt` | honored (loaded as a user agent) |
| Users receive a change when | it is pushed **and** `version` in plugin.json is bumped; otherwise they keep the cached copy | they `git pull` and start a new session |

## Commands

```bash
claude plugin validate .                                            # marketplace.json only (1 known warning: no description)
for p in plugins/*/; do claude plugin validate --strict "$p"; done  # plugin.json + agent frontmatter
claude --plugin-dir ./plugins                                       # load all plugins as plugins for one session; no install, no push
claude --plugin-dir ./plugins plugin details <plugin>               # component inventory + projected token cost
./install.sh --list | --all | --plugin <name>                       # symlink install
./uninstall.sh                                                      # remove symlinks that point into this repo
ls -l ~/.claude/agents ~/.claude/skills | grep "$(pwd)"             # confirm symlinks
```

`validate` catches agent frontmatter that fails to parse (such an agent still loads, with every field dropped). It does not catch SKILL.md frontmatter errors, misspelled field names, or fields a mode ignores; check those by eye.

## Adding or renaming a plugin or skill

The plugin list is duplicated; keep all of these in sync:
1. `plugins/<name>/` with `.claude-plugin/plugin.json`
2. Its entry in `.claude-plugin/marketplace.json`
3. The `PLUGINS` array in **both** `install.sh` and `uninstall.sh`
4. `README.md`, `README.zh-TW.md`, and "Current Plugins" below

- install.sh flattens all plugins into `~/.claude/skills/<dir>` and `~/.claude/agents/<file>`, so names must be unique across plugins and avoid bundled command names. An existing symlink of the same name is silently repointed (`[update]`); a real file or dir is skipped (`[warn]`).
- Don't add `agents` or `commands` paths to plugin.json: a custom path replaces the default directory scan, so a second agent would be silently ignored. A `skills` path only adds to the default scan.

## Frontmatter and file conventions

- Agents: `name`, `description`, `tools`, `maxTurns: 30`, `color`, `memory: project`, `skills` (preload). Reviewers add `disallowedTools: Edit, Write, NotebookEdit` and `permissionMode: plan`; the developer agent uses `permissionMode: acceptEdits` (install.sh mode only). Body ends with a `## Memory Usage` section and "All output must be in Traditional Chinese".
- Skills: `name` (= the command), `description` (trigger conditions: "Use when..."), `argument-hint`, `allowed-tools`. Knowledge-base skills set `user-invocable: false` (hidden from `/`; Claude can still load them). Heavy skills set `context: fork`. Every SKILL.md has `## When to Apply` and `## Gotchas`.
- No `model` field anywhere: removed on purpose so the caller's session model runs everything.

## Orchestration Pattern

- Agent = persona + workflow + 輸出格式；Skill = 領域知識（preload 或 slash command）。
- Agent 的 `skills` frontmatter 在啟動時注入整份 skill 內容，所以 preload 的 skill 要精簡（~150–200 行），細節放 `references/`。`bill-code-reviewer`、`bill-java-developer` preload 的 skill 全在**另一個 plugin** `bill-java-skills`；沒裝它時 preload 會被靜默跳過（只記在 debug log）。
- Skill 與 agent 沒有硬連結：只靠 agent `description` 的「Use PROACTIVELY when /xxx is invoked」引導主模型委派。`context: fork` 的 skill（`review-pr`、`optimize-query`）沒設 `agent:`，實際跑在 general-purpose subagent，拿不到 agent 的 persona 與 preload skill。

## Gotchas

- `.claude-plugin/marketplace.json` 和 `plugin.json` 必須保留：`/plugin` UI 依賴這些檔案
- `version` 只寫在 plugin.json；marketplace entry 也寫的話，runtime 會靜默採用 plugin.json 的值
- `install.sh` 寫入 `~/.claude/`，在沙盒模式下需要 `dangerouslyDisableSandbox: true`

## Current Plugins

1. **bill-billing-unit-test-reviewer**: agent + `/review-test`
2. **bill-code-reviewer**: agent (preloads effective-java, clean-architecture) + `/code-review`, `/review-pr`
3. **bill-java-developer**: agent (preloads effective-java, clean-architecture, mysql-optimization) + `/design-solution`, `/optimize-query`
4. **bill-java-skills**: knowledge-base skills only: clean-architecture, effective-java, mysql-optimization
