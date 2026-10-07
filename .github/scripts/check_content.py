#!/usr/bin/env python3
"""Checks the content rules from CLAUDE.md that `claude plugin validate` doesn't cover.

Run from the repository root: python3 .github/scripts/check_content.py
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "java-backend"
HAN = re.compile(r"[㐀-鿿豈-﫿]")
errors = []


def frontmatter(text):
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    fields = {}
    for line in text[4:end].splitlines():
        if line and not line.startswith((" ", "-")) and ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    return fields


def skills_list(text):
    """Return the entries of an agent's `skills:` field (YAML list or comma string)."""
    end = text.find("\n---", 4)
    lines = text[4:end].splitlines()
    for i, line in enumerate(lines):
        if line.startswith("skills:"):
            inline = line.split(":", 1)[1].strip()
            if inline:
                return [s.strip() for s in inline.split(",")]
            items = []
            for follow in lines[i + 1:]:
                if not follow.startswith("  - "):
                    break
                items.append(follow[4:].strip())
            return items
    return []


for skill_md in sorted((PLUGIN / "skills").glob("*/SKILL.md")):
    rel = skill_md.relative_to(ROOT)
    text = skill_md.read_text(encoding="utf-8")
    fm = frontmatter(text)
    if fm.get("name") != skill_md.parent.name:
        errors.append(f"{rel}: frontmatter name must equal the directory name")
    if "model" in fm:
        errors.append(f"{rel}: no `model` field (the caller's model runs everything)")
    if fm.get("context") == "fork" and not fm.get("agent", "").startswith("java-backend:"):
        errors.append(f"{rel}: fork skills need `agent: java-backend:<agent>` (a bare name falls back to general-purpose)")
    for heading in ("## When to Apply", "## Gotchas"):
        if heading not in text:
            errors.append(f"{rel}: missing `{heading}`")
    if len(text.splitlines()) > 200:
        errors.append(f"{rel}: over 200 lines; move detail to references/")

for ref in sorted((PLUGIN / "skills").glob("*/references/*.md")):
    if ref.name.endswith("-example.md"):
        continue  # worked examples illustrate format, they make no factual claims
    if "## Sources" not in ref.read_text(encoding="utf-8"):
        errors.append(f"{ref.relative_to(ROOT)}: missing `## Sources`")

for agent in sorted((PLUGIN / "agents").glob("*.md")):
    rel = agent.relative_to(ROOT)
    text = agent.read_text(encoding="utf-8")
    fm = frontmatter(text)
    for banned in ("model", "permissionMode", "memory"):
        if banned in fm:
            errors.append(f"{rel}: remove `{banned}` (see CLAUDE.md)")
    for skill in skills_list(text):
        if not skill.startswith("java-backend:"):
            errors.append(f"{rel}: preload `{skill}` as `java-backend:{skill}`")
        elif not (PLUGIN / "skills" / skill.split(":", 1)[1] / "SKILL.md").exists():
            errors.append(f"{rel}: preloaded skill `{skill}` does not exist")

for path in sorted(PLUGIN.rglob("*.md")):
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if HAN.search(line):
            errors.append(f"{path.relative_to(ROOT)}:{number}: plugin content must be English (answers follow the user's language)")
            break

docs = ROOT / "docs"
for page in sorted(docs.glob("*.html")):
    text = page.read_text(encoding="utf-8")
    for target in re.findall(r'(?:href|src)="([^"#:]+)"', text):
        if not (docs / target).exists():
            errors.append(f"{page.relative_to(ROOT)}: broken link `{target}`")

if errors:
    print("\n".join(errors))
    sys.exit(1)
print("content checks passed")
