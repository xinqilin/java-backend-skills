# Contributing

Thanks for helping. This plugin aims for depth over breadth: Spring Boot, Spring Data JPA/Hibernate, and MySQL/PostgreSQL. Contributions outside that stack are likely to be declined; corrections inside it are the most valuable thing you can send.

## The one rule: every claim has a source

Each statement about how MySQL, PostgreSQL, Hibernate, Spring, or a library behaves must be checked against official documentation or source code before it is written, and the reference file must list that source under `## Sources`. If you can't find a source, leave the claim out. Opinions (design advice) are fine when they are clearly phrased as advice.

## Develop locally

```bash
claude --plugin-dir ./plugins/java-backend      # load the plugin from source for one session
claude plugin marketplace add ./                # or: a local marketplace that reads source files in place
claude --plugin-dir ./plugins/java-backend plugin details java-backend   # inventory and token cost
```

## Before opening a pull request

```bash
claude plugin validate --strict .
claude plugin validate --strict plugins/java-backend
python3 .github/scripts/check_content.py
```

CI runs the same three commands. The content check enforces the conventions below.

## Conventions

- **Skills** (`plugins/java-backend/skills/<name>/SKILL.md`): `name` equals the directory name; the description starts with what the skill covers and when to use it; the file has `## When to Apply` and `## Gotchas` and stays under 200 lines. Detail goes into `references/*.md`, each ending with `## Sources`.
- **Gotchas** list mistakes Claude actually makes, not general advice. One bullet each: the wrong belief in bold, then the correct behavior.
- **Agents** (`plugins/java-backend/agents/*.md`) are read-only reviewers. They don't set `model`, `permissionMode`, or `memory`, and they preload skills by scoped name (`java-backend:<skill>`).
- **Fork skills** (`context: fork`) name their agent with the scoped form, `agent: java-backend:<agent>`; a bare name silently falls back to the general-purpose agent.
- **Language**: plugin files are written in English and tell Claude to answer in the user's language. `README.md` and `README.zh-TW.md` mirror each other; `docs/` pages carry both languages.
- **Versions**: write for Spring Boot 4.1 and note Spring Boot 3.x differences inline.

## Evals

`plugins/java-backend/evals/` holds cases that compare Claude with and without the plugin. Running them calls models on your own account:

```bash
claude plugin eval plugins/java-backend --runs 1 --model sonnet --judge-model haiku --max-cost-usd 3 --no-publish
```

When you add knowledge for a pitfall, consider adding a case that the plugin should pass and plain Claude might not.

## Releasing (maintainers)

Bump `version` in `plugins/java-backend/.claude-plugin/plugin.json` and add a `CHANGELOG.md` entry; marketplace users only receive changes when the version changes.
