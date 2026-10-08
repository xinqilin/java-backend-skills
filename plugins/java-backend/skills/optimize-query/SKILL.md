---
name: optimize-query
description: Analyze slow SQL or Spring Data JPA queries on MySQL or PostgreSQL using execution plans, indexes, and fetch strategy. Use when the user asks to optimize a query, read an EXPLAIN plan, or fix a database bottleneck.
argument-hint: "[file-or-query]"
allowed-tools: Read, Grep, Glob, Bash
context: fork
agent: java-backend:data-architect
---

# Optimize Query

If the `data-architect` agent instructions (with "Step 0: Detect the stack") are not already in your context, as in Codex, where plugin agents do not load: read `../../agents/data-architect.md` (relative to this SKILL.md, not the working directory) and follow it, then read the SKILL.md of each skill in its `skills:` list (`java-backend:<skill>` is `../<skill>/SKILL.md`).

Target: `$ARGUMENTS` (a repository method, a JPQL or native query, an `EXPLAIN` output, or a file).

Find the real bottleneck, then propose the smallest change that removes it, with a way to measure the result. Use the preloaded `java-backend:sql-performance` knowledge, and load `java-backend:jpa-hibernate` when the query comes from JPA.

## Workflow

### Step 1: Establish the facts

- Database and version (Step 0 of your instructions), and whether the code is JPQL, a derived query, Criteria, or native SQL.
- The SQL actually executed: for JPA, ask for `org.hibernate.SQL` debug output or derive it from the mapping; don't assume.
- Data volume and access pattern: rows in the involved tables, how many rows the query returns, how often it runs, and its latency target. Ask when unknown; never invent numbers.
- Existing indexes: `SHOW INDEX FROM t` (MySQL), `\d t` or `pg_indexes` (PostgreSQL), and `@Table(indexes = ...)` or migration scripts.

### Step 2: Read the plan

- MySQL: `EXPLAIN ANALYZE` (or `EXPLAIN FORMAT=TREE`). PostgreSQL: `EXPLAIN (ANALYZE, BUFFERS)`, inside `BEGIN; ... ROLLBACK;` for DML.
- If the user can only run plain `EXPLAIN`, say which conclusions remain estimates.
- Compare estimated with actual rows. A large mismatch means statistics first (`ANALYZE TABLE` / `ANALYZE`).

### Step 3: Classify the problem

Check in this order; the first match usually dominates:

1. **Round trips**: N+1 from lazy associations, or one query per item in a loop → fetch join, entity graph, batch fetching, or one set-based query (`jpa-hibernate`).
2. **Rows read vs. rows returned**: a scan or a wide range for a few rows → index fit (`sql-performance` → `index-design.md`).
3. **Sort or temporary work**: `Using filesort` / `Sort` before a `LIMIT` → an index that delivers the order.
4. **Query shape**: functions on indexed columns, mismatched types, large `OFFSET`, `NOT IN` with `NULL`s (`query-patterns.md`).
5. **Too much data per row**: entities loaded for read-only views → projections.
6. **Contention, not the query**: lock waits, long transactions, or pool exhaustion → `transactions-consistency`, `connection-pool.md`.

### Step 4: Propose and verify

For each recommendation, give:

- The change: SQL or index DDL, plus the JPA change (repository method, `@Table(indexes = ...)`, or migration).
- Why it works, in terms of the plan.
- How to roll it out safely on a large table (`mysql.md` / `postgresql.md`: online DDL, `CONCURRENTLY`, `lock_timeout`).
- How to verify: the plan you expect afterwards, and what to measure before and after.

## Output format

Write the analysis in the user's language. Keep code, SQL, and identifiers as-is.

```markdown
## Stack
<MySQL|PostgreSQL> <version> · Spring Boot <version> · Hibernate <version>

## Current state
- Query (as executed):
- Plan summary: access path, rows estimated vs. actual, sorts or temporaries
- Data volume and frequency: (measured, or marked as assumed)

## Root cause
What the plan shows, and why.

## Recommendation
1. Change (SQL / DDL / JPA)
2. Expected plan after the change
3. Rollout on a live table
4. Trade-offs (write cost, storage, locking)

## Verification
Statements to run before and after, and the metric that proves the improvement.
```

## When to Apply

- Slow query analysis or EXPLAIN plan review
- Investigating N+1 queries
- SQL/JPA performance bottlenecks
- Index design or tuning

## When NOT to optimize

- The query is fast enough for its frequency and target, as measured
- The table is tiny and stays tiny
- An index would slow a write-heavy path more than it helps the reads

## Gotchas

<!-- Keep adding mistakes Claude repeatedly makes. -->

- **Plans on empty or tiny tables mislead**: statistics drive plan choice; test with production-like volume.
- **Composite index order is equality first, then range or sort**: not "most selective first".
- **The optimizer may skip your index for a reason**: understand why before forcing it with a hint; forcing can be slower.
- **Spring Data `findAll()` has no size guard**: on large tables it can exhaust memory; page or limit.
- **Collection fetch join + pagination depends on the Hibernate version**: in memory before 7.4, in the database on 7.4+ for MySQL and PostgreSQL. Check the version before flagging it.
- **Never predict exact gains**: no "3.5 s → 45 ms" without a measurement. State the expected plan change and how to measure it.
