---
name: sql-performance
description: MySQL and PostgreSQL query performance for Spring Boot apps (index design, execution plans, query patterns, online schema changes, connection pool sizing). Use when reviewing database access code, designing indexes, or reading EXPLAIN output.
user-invocable: false
allowed-tools: Read, Grep, Glob
---

# SQL Performance for MySQL and PostgreSQL

Measure first, then fix in this order: round trips (N+1), index fit, query shape, and only then the data model. Identify the database and version first: InnoDB and PostgreSQL store tables differently, so index advice that is right for one can be wrong for the other.

## Step 1: Find the expensive statements

- **MySQL**: the slow query log, or the Performance Schema statement digests (`sys.statement_analysis`). `SHOW PROFILE` / `SHOW PROFILES` are deprecated in favor of the Performance Schema.
- **PostgreSQL**: the `pg_stat_statements` extension. It must be loaded through `shared_preload_libraries`, which needs a server restart.
- **Application side**: count the statements per request in tests (`org.hibernate.SQL` logging or Hibernate statistics). Many small queries usually mean N+1 (`java-backend:jpa-hibernate`), not a missing index.

## Step 2: Read the real plan

- **MySQL**: `EXPLAIN` gives estimates; `EXPLAIN ANALYZE` runs the statement and adds actual timing and row counts per iterator; `EXPLAIN FORMAT=TREE` shows the iterator tree.
- **PostgreSQL**: `EXPLAIN (ANALYZE, BUFFERS)` runs the statement and shows actual rows, time, and buffer hits and reads per node. For DML, wrap it in `BEGIN; ... ROLLBACK;`, because `ANALYZE` really executes the statement.
- Compare estimated with actual rows. A large mismatch points to stale or missing statistics (`ANALYZE TABLE` in MySQL, `ANALYZE` in PostgreSQL) before it points to a missing index.

Reading plans per database: `references/mysql.md`, `references/postgresql.md`.

## Step 3: Make the index fit the query

Both databases use B-tree indexes by default, and the same rules apply:

1. **Equality columns first, then one range or sort column.** In PostgreSQL's words, equality constraints on the leading columns plus an inequality on the first column without an equality limit the scanned part of the index; constraints on columns further right are only checked inside it.
2. **Leftmost prefix**: an index on `(a, b, c)` serves `a`, `a, b`, and `a, b, c`, but not `b` alone. PostgreSQL 18's B-tree skip scan can sometimes use later columns without a condition on `a`.
3. **Sort through the index**: `WHERE customer_id = ? ORDER BY created_at DESC LIMIT 20` wants `(customer_id, created_at)`. The database then reads 20 index entries instead of sorting every match.
4. **Covering**: when the index holds every column the query needs, the table isn't read. In InnoDB, every secondary index already contains the primary key. In PostgreSQL, use `INCLUDE (...)`; index-only scans also depend on the visibility map, which `VACUUM` maintains.
5. **Selectivity is not the ordering rule.** Order columns by how the query constrains them (equality before range), not by distinct-value counts. A low-cardinality column alone rarely makes a useful index, but it is fine as an equality prefix. In PostgreSQL, a partial index (`WHERE status = 'PENDING'`) is often better.
6. **Every index costs writes and memory.** Remove unused and redundant indexes. In MySQL, make an index `INVISIBLE` first to test dropping it safely.

Details: `references/index-design.md`.

## Step 4: Fix the query shape

- No functions or arithmetic on the indexed column (`YEAR(created_at) = 2024`): rewrite as a range, or index the expression (MySQL functional key parts, PostgreSQL expression indexes).
- Match types: in MySQL, comparing a **string column with a number** (`WHERE varchar_col = 123`) cannot use the index on that column.
- Use keyset pagination (`WHERE (created_at, id) < (?, ?) ORDER BY created_at DESC, id DESC LIMIT 20`) instead of large `OFFSET`s.
- `NOT IN (subquery)` returns no rows when the subquery yields a `NULL`; use `NOT EXISTS`.
- `OR` across different columns isn't automatically bad: MySQL can use Index Merge and PostgreSQL can combine indexes with bitmap scans. Check the plan before rewriting it into `UNION`.

Details: `references/query-patterns.md`.

## Step 5: Change schemas without outages

- **MySQL**: adding a secondary index is in-place and permits concurrent DML. Many column changes are `INSTANT`, but changing a column's data type copies the table and blocks DML. Every online DDL still needs a brief exclusive **metadata lock**: a long-running transaction on the table blocks the DDL, and the waiting DDL then blocks every later query on that table.
- **PostgreSQL**: plain `CREATE INDEX` blocks writes until it finishes. `CREATE INDEX CONCURRENTLY` doesn't, but it can't run inside a transaction block, and a failed build leaves an `INVALID` index behind that must be dropped. `ADD COLUMN` with a non-volatile default doesn't rewrite the table. Set `lock_timeout` for migrations.
- Flyway runs each migration in a transaction by default (`spring.flyway.execute-in-transaction=true`) and uses a transactional advisory lock on PostgreSQL. For a script containing `CREATE INDEX CONCURRENTLY`, set `executeInTransaction=false` in that script's configuration file, and if the lock gets in the way, set `spring.flyway.postgresql.transactional-lock=false`.

## Step 6: Size the connection pool

A small pool with threads waiting for it beats a large pool that overloads the database. HikariCP's default is 10 connections; start from `(core_count * 2) + effective_spindle_count` and measure. Details, including virtual threads: `references/connection-pool.md`.

## When to Apply

- Reviewing repository methods, native queries, entity indexes, or migrations
- A slow endpoint, a slow query log entry, or a plan to read
- Designing indexes for new access patterns
- Planning schema changes on large tables
- Connection pool timeouts or pool sizing

## Gotchas

<!-- Keep adding mistakes Claude repeatedly makes. -->

- **"Most selective column first" is a myth for composite indexes**: put equality columns first and the range or sort column last.
- **The type-conversion trap runs one way in MySQL**: `varchar_col = 123` can't use the index, while `int_col = '123'` can, because MySQL converts the constant.
- **MySQL materializes a CTE once per query**: even when the query references it several times. PostgreSQL inlines a non-recursive, side-effect-free CTE that is referenced once, and materializes it otherwise (override with `MATERIALIZED` / `NOT MATERIALIZED`).
- **`COUNT(*)` vs `COUNT(1)`**: no difference in InnoDB; don't spend review comments on it.
- **`EXPLAIN` row counts are estimates**: confirm with `EXPLAIN ANALYZE` before concluding.
- **Index advice from MySQL doesn't transfer verbatim**: the clustered primary key, the implicit primary key in every secondary index, and `Using index` are InnoDB concepts. PostgreSQL tables are heaps, and covering needs `INCLUDE` plus a well-vacuumed visibility map.
- **Never `CREATE INDEX` on a busy PostgreSQL table without `CONCURRENTLY`**: it blocks all writes until it finishes.
- **Don't invent numbers**: never predict "98% faster" or "10% slower writes"; state what to measure and how.

## Sources

See the Sources section at the end of each reference file.
