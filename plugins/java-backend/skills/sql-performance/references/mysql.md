# MySQL (InnoDB) Specifics

Baseline: MySQL 8.4 LTS with InnoDB.

## Reading EXPLAIN

```sql
EXPLAIN SELECT ...;                 -- estimates only
EXPLAIN FORMAT=TREE SELECT ...;     -- iterator tree
EXPLAIN ANALYZE SELECT ...;         -- runs the statement: estimates vs. actual per iterator
```

`EXPLAIN ANALYZE` runs the statement and reports, per iterator, the estimated cost and rows next to the actual time to first row, total time, rows, and loops.

Classic `EXPLAIN` columns that matter most:

| Column | Look for |
|--------|----------|
| `type` | Join type, from best to worst: `system`, `const`, `eq_ref`, `ref`, `fulltext`, `ref_or_null`, `index_merge`, `unique_subquery`, `index_subquery`, `range`, `index`, `ALL`. `ALL` on a large table is a full scan; `index` is a full scan of an index |
| `key`, `key_len` | Which index is used, and how many bytes of it. A short `key_len` on a composite index means only its leftmost part is used |
| `rows`, `filtered` | Estimated rows examined, and the percentage left after the table condition |
| `Extra` | `Using index` (covering), `Using index condition` (index condition pushdown), `Using where`, `Using filesort` (sort not served by an index), `Using temporary` |

## Statistics

- `ANALYZE TABLE t;` refreshes index statistics.
- Histograms describe value distribution for columns without an index, or with skewed data: `ANALYZE TABLE t UPDATE HISTOGRAM ON col WITH 64 BUCKETS;`.

## Finding slow statements

- Slow query log, or Performance Schema statement digests (the `sys` schema's `statement_analysis` view summarizes them).
- `SHOW PROFILE` / `SHOW PROFILES` are deprecated; use Performance Schema query profiling instead.

## Index features worth knowing

- **Functional key parts**: `CREATE INDEX idx ON users ((lower(email)));` (note the double parentheses).
- **Descending key parts**: `(created_at DESC)` for mixed-direction sorts.
- **Invisible indexes**: `ALTER TABLE t ALTER INDEX idx INVISIBLE;` hides an index from the optimizer while it is still maintained, which makes dropping it reversible.
- **No partial indexes**: use a generated column and index it. A unique index allows multiple `NULL`s, so a generated column that is `NULL` for rows to ignore gives a "unique among active rows" constraint.

## Online DDL

| Operation | Instant | In place | Rebuilds table | Concurrent DML |
|-----------|---------|----------|----------------|----------------|
| Add a secondary index | No | Yes | No | Yes |
| Drop an index | No | Yes | No | Yes |
| Add a column | Yes* | Yes | No* | Yes* |
| Drop a column | Yes* | Yes | Yes | Yes |
| Change a column's data type | No | No | Yes | **No** |
| Extend a `VARCHAR` size | No | Yes | No | Yes |

`*` means conditions apply (see the MySQL manual's tables). State the algorithm and lock explicitly, so MySQL fails fast instead of silently falling back to a blocking copy:

```sql
ALTER TABLE orders ADD INDEX idx_orders_customer_created (customer_id, created_at), ALGORITHM=INPLACE, LOCK=NONE;
```

### Metadata locks: the real outage risk

Online DDL takes a shared upgradeable metadata lock, then upgrades it to an exclusive one briefly: possibly during statement preparation, and always when committing the new table definition. From the MySQL manual:

- The DDL may have to wait for concurrent transactions that hold metadata locks on the table. A long-running or idle open transaction can make it time out.
- While it waits, the **pending exclusive metadata lock blocks every subsequent transaction on that table**.
- The wait is bounded by `lock_wait_timeout`, whose default is 31,536,000 seconds (one year).

So a forgotten open transaction (a connection left in a transaction by a batch job, or a long report query) turns a "non-blocking" index creation into a full table outage. Before running DDL, check for long transactions (`information_schema.innodb_trx`) and set a short `lock_wait_timeout` for the DDL session, so the DDL gives up instead of queueing everyone behind it.

## Locking and timeouts

- `innodb_lock_wait_timeout`: default 50 seconds of waiting for a row lock before error 1205.
- Deadlocks are detected and one transaction is rolled back with error 1213 (SQLSTATE 40001). Retry the whole transaction (`java-backend:transactions-consistency`).

## Sources

- MySQL 8.4, EXPLAIN Statement (`EXPLAIN ANALYZE`): https://dev.mysql.com/doc/refman/8.4/en/explain.html
- MySQL 8.4, EXPLAIN Output Format (join types, Extra): https://dev.mysql.com/doc/refman/8.4/en/explain-output.html
- MySQL 8.4, ANALYZE TABLE (histograms): https://dev.mysql.com/doc/refman/8.4/en/analyze-table.html
- MySQL 8.4, SHOW PROFILES (deprecated): https://dev.mysql.com/doc/refman/8.4/en/show-profiles.html
- MySQL 8.4, CREATE INDEX: https://dev.mysql.com/doc/refman/8.4/en/create-index.html
- MySQL 8.4, Invisible Indexes: https://dev.mysql.com/doc/refman/8.4/en/invisible-indexes.html
- MySQL 8.4, Online DDL Operations: https://dev.mysql.com/doc/refman/8.4/en/innodb-online-ddl-operations.html
- MySQL 8.4, Online DDL Performance and Concurrency (metadata locks): https://dev.mysql.com/doc/refman/8.4/en/innodb-online-ddl-performance.html
- MySQL 8.4, InnoDB system variables: https://dev.mysql.com/doc/refman/8.4/en/innodb-parameters.html
- MySQL 8.4, Server System Variables (`lock_wait_timeout`): https://dev.mysql.com/doc/refman/8.4/en/server-system-variables.html
