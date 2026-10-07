---
name: review-pr
description: Review a GitHub pull request (by number, via gh) or a branch diff in a Java/Spring Boot repository. Use when the user asks to review a PR or compare branches before merging.
argument-hint: "[pr-number | compare-branch] [base-branch]"
allowed-tools: Read, Grep, Glob, Bash
context: fork
agent: java-backend:code-reviewer
---

# PR Review

Review pull request changes to senior-engineer standards.

Arguments: `$ARGUMENTS`

Two modes:
1. **GitHub PR mode**: a number (`123` or `#123`) → `gh pr view` + `gh pr diff`
2. **Branch comparison mode**: a branch name or nothing → `git diff`

## Parameter usage

```text
/java-backend:review-pr 123                    # GitHub PR #123
/java-backend:review-pr                        # current branch vs the default branch
/java-backend:review-pr feature-auth           # feature-auth vs the default branch
/java-backend:review-pr feature-auth develop   # feature-auth vs develop
```

**Auto-detection**: a pure number means GitHub PR mode; anything else means branch comparison mode. When no base branch is given, use the repository's default branch (`git symbolic-ref --short refs/remotes/origin/HEAD`, or `gh repo view --json defaultBranchRef`); never assume `master` or `main`.

## Workflow

### Step 1: Gather information

**GitHub PR mode**: `gh pr view <PR_NUMBER> --json number,title,body,state,author,baseRefName,headRefName,additions,deletions,changedFiles,commits` and `gh pr diff <PR_NUMBER>`.

**Branch comparison mode**: `git diff <base>...<compare> --name-status`, `git diff <base>...<compare> --stat`, `git log --oneline --no-merges <base>..<compare>`, then the full `git diff <base>...<compare>`.

### Step 2: Categorize changed files

From `--name-status`: Added (A), Modified (M), Deleted (D), Renamed (R).

Focus on `.java` files, entity and repository changes, and migration scripts. Mention configuration changes (`.yml`, `.properties`) that alter JPA, datasource, or transaction behavior.

### Step 3: Code quality review

Apply the same standards as `/java-backend:code-review`: data access and transactions, over-design, naming, method design, exception handling, Spring Boot practices, performance.

**Review the changed lines, but read enough surrounding code to judge them.**

### Step 4: PR-specific checks

#### Tests
- New features have corresponding tests
- Bug fixes have a regression test
- `OrderService.java` changed → `OrderServiceTest.java` should change too

#### Breaking changes
- Removed public methods or changed signatures
- Renamed fields in DTOs or entities, column or table renames
- Changed API endpoints or request/response formats

#### Unrelated changes
- Files that don't belong in this PR
- Formatting-only changes in unrelated files

#### Debug and TODO leftovers
```bash
git diff <base>...<compare> | grep -E "System.out.println|printStackTrace|TODO|FIXME|XXX"
```

#### Documentation
- Public API changes reflected in docs
- New dependencies explained

## Output format

Write the report in the user's language. Keep code and identifiers as-is.

```markdown
# PR Review

## Stack
Spring Boot <version> · Java <release> · <MySQL|PostgreSQL>

## Overview
- PR (gh mode): number, title, author, state, base/head branch
- Stats: files changed, +additions, -deletions, main kind of change

## Commits
Number of commits and quality of their messages.

## Code quality
Complexity, maintainability, over-design.

## Findings

### Priority 1 - Must fix
| Issue | Location | Impact | Fix |
|-------|----------|--------|-----|

### Priority 2 - Should improve
| Issue | Location | Impact | Fix |
|-------|----------|--------|-----|

## PR checks
Tests / docs / breaking changes / debug code.

## Verdict
Overall: Excellent / Good / Needs work / Do not merge
Merge when: [conditions]
```

## When to Apply

- Reviewing a GitHub PR or a branch comparison
- Quality gate before merging
- Assessing the impact of cross-file changes

## Gotchas

<!-- Keep adding mistakes Claude repeatedly makes. -->

- **Very large PRs**: `gh pr diff` output can be too large to read in one pass, or fail on huge diffs. Fetch the branch (`gh pr checkout <n>` or `git fetch origin pull/<n>/head`) and review per file with `git diff <base>...<head> -- <path>`.
- **Rename detection has a similarity threshold**: git pairs a rename only when the files are at least 50% similar by default, so a moved-and-rewritten file shows up as delete + add. Lower the threshold (`git diff -M30%`) when a PR moves and edits files.
- **Review test quality, not only test existence**: check that tests exercise real scenarios with meaningful assertions.
- **Green CI is not a quality verdict**: CI checks compilation and tests, not design, concurrency, or query behavior.
- **Don't judge critical changes from the diff alone**: read the full method or class around transactional and persistence changes before assessing impact.
