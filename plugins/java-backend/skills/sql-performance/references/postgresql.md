# PostgreSQL Specifics

Baseline: PostgreSQL 18 (the current release as of this writing).

## Reading EXPLAIN

```sql
EXPLAIN SELECT ...;                         -- estimates only
EXPLAIN (ANALYZE, BUFFERS) SELECT ...;      -- runs it: actual rows, time, and buffer hits/reads per node

BEGIN;
EXPLAIN (ANALYZE, BUFFERS) UPDATE ...;      -- ANALYZE really executes DML
ROLLBACK;
```

- Compare `rows=` (estimated) with `actual ... rows=`. Large gaps point to stale statistics; run `ANALYZE table_name`.
- `loops=` multiplies a node's per-loop time and rows; a cheap node executed 10,000 times inside a nested loop is often the real cost.
- `Buffers: shared hit=... read=...`: `read` means blocks fetched from outside PostgreSQL's buffer cache.
- Common nodes: `Seq Scan`; `Index Scan` (index, then heap); `Index Only Scan` (heap skipped when the visibility map allows); `Bitmap Index Scan` + `Bitmap Heap Scan` (many matches, or several indexes combined with `BitmapAnd`/`BitmapOr`); `Sort`; `Hash Join`; `Nested Loop`.

## Finding slow statements

`pg_stat_statements` tracks planning and execution statistics for every statement. It must be added to `shared_preload_libraries` (server restart), then `CREATE EXTENSION pg_stat_statements;` in the database.

## MVCC, VACUUM, and bloat

- An `UPDATE` writes a new row version, and the old one stays until `VACUUM` removes it once no transaction can see it. Long-running transactions hold back that cleanup.
- **HOT updates** (heap-only tuples) avoid creating new index entries when the update changes no indexed column (BRIN, a summarizing index, excepted) and the page has free space for the new version. Lowering a table's `fillfactor` leaves room for HOT updates on update-heavy tables. `pg_stat_all_tables` reports HOT vs. non-HOT updates.
- Implication for design: indexing a frequently updated column (`updated_at`, `status`) disables HOT for those updates, so every update also writes index entries.

## Index types

| Type | Use for |
|------|---------|
| B-tree (default) | Equality, ranges, sorting, `LIKE 'prefix%'` (with the right collation or operator class) |
| GIN | `jsonb` containment, arrays, full-text search |
| GiST | Ranges, geometry, exclusion constraints (with `btree_gist` for scalar equality) |
| BRIN | Very large tables whose values correlate with physical order (append-only timestamps) |

Expression indexes (`lower(email)`), partial indexes (`WHERE status = 'PENDING'`), and `INCLUDE` columns for index-only scans are the most useful B-tree features beyond the basics. See `index-design.md`.

## Schema changes on live tables

```sql
SET lock_timeout = '3s';                                 -- default 0 = wait forever
CREATE INDEX CONCURRENTLY idx_orders_customer ON orders (customer_id);
```

- A plain `CREATE INDEX` blocks writes, but not reads, until it finishes. `CONCURRENTLY` avoids that, at the cost of a slower build.
- `CREATE INDEX CONCURRENTLY` cannot run inside a transaction block. With Flyway, mark that script non-transactional (`executeInTransaction=false` in its script configuration).
- If a concurrent build fails (a deadlock, or a uniqueness violation), it leaves an `INVALID` index behind. That index is ignored by queries but still slows writes. Drop it and retry.
- `ALTER TABLE ... ADD COLUMN` with a non-volatile `DEFAULT` stores the default in the catalog and doesn't rewrite the table, even on large tables.
- `lock_timeout` aborts any statement that waits longer than the limit for a lock, and applies to each lock acquisition separately. Set it for migrations, so DDL stuck behind a long-running transaction fails fast and can be retried, instead of waiting indefinitely while holding its place in line.

## Sources

- PostgreSQL 18, Using EXPLAIN: https://www.postgresql.org/docs/current/using-explain.html
- PostgreSQL 18, EXPLAIN (DML with `BEGIN`/`ROLLBACK`): https://www.postgresql.org/docs/current/sql-explain.html
- PostgreSQL 18, pg_stat_statements: https://www.postgresql.org/docs/current/pgstatstatements.html
- PostgreSQL 18, Heap-Only Tuples (HOT): https://www.postgresql.org/docs/current/storage-hot.html
- PostgreSQL 18, Combining Multiple Indexes: https://www.postgresql.org/docs/current/indexes-bitmap-scans.html
- PostgreSQL 18, Index-Only Scans and Covering Indexes: https://www.postgresql.org/docs/current/indexes-index-only-scans.html
- PostgreSQL 18, CREATE INDEX (`CONCURRENTLY`, invalid indexes): https://www.postgresql.org/docs/current/sql-createindex.html
- PostgreSQL 18, ALTER TABLE (`ADD COLUMN` with defaults): https://www.postgresql.org/docs/current/sql-altertable.html
- PostgreSQL 18, Client Connection Defaults (`lock_timeout`): https://www.postgresql.org/docs/current/runtime-config-client.html
- PostgreSQL 18, Range Types (exclusion constraints with `btree_gist`): https://www.postgresql.org/docs/current/rangetypes.html
- Flyway, `executeInTransaction` and PostgreSQL lock settings: https://github.com/flyway/flyway/tree/main/documentation/Reference
