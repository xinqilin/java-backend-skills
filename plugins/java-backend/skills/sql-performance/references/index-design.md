# Index Design for MySQL (InnoDB) and PostgreSQL

## How each database stores a table

| | MySQL InnoDB | PostgreSQL |
|---|---|---|
| Table storage | The clustered index: rows stored in primary-key order | A heap: rows in no particular order |
| Secondary index entry | Index columns + **primary key** columns; lookups go through the clustered index | Index columns + a pointer to the heap row |
| Covering ("index-only") | Any secondary index already carries the PK. `EXPLAIN` shows `Using index` | Add payload columns with `INCLUDE (...)`. Also needs the visibility map (kept by `VACUUM`) to skip heap visits |
| Implication | Keep the primary key short: it is repeated in every secondary index | `UPDATE`s that change no indexed column can stay heap-only (HOT) and avoid index maintenance |

## Composite index column order

Rule: **equality columns first (any order among them), then at most one range or sort column.**

```sql
-- Query
SELECT * FROM orders
WHERE customer_id = ? AND status = ? AND created_at >= ?
ORDER BY created_at;

-- Index: two equalities, then the range/sort column
CREATE INDEX idx_orders_cust_status_created ON orders (customer_id, status, created_at);
```

- PostgreSQL documents the exact rule: equality constraints on leading columns, plus an inequality on the first column without an equality, limit the scanned part of the index. Constraints on columns to the right are checked inside the index; they save heap visits but don't shrink the scan.
- MySQL: an index on `(a, b, c)` is usable for `a`, `a, b`, and `a, b, c` (leftmost prefix). With `a = 1 AND b > 10 AND c = 5`, the range on `b` ends the usable prefix, and `c` is only filtered.
- PostgreSQL 18 adds B-tree **skip scan**: it can apply conditions on later columns even when an earlier column has no equality constraint, by generating the earlier column's values internally. It helps when that column has few distinct values. Don't design new indexes around it.

### Why "most selective first" is the wrong rule

Distinct-value counts don't decide the order: how the query constrains each column does. With `(status, customer_id)` and `(customer_id, status)`, the query `status = ? AND customer_id = ?` performs the same on both, since both are equality prefixes. What matters is which index also serves your **other** queries (leftmost prefixes) and which column carries the range or sort.

## Sorting and LIMIT through the index

```sql
-- Wants (customer_id, created_at): reads 20 index entries, no sort
SELECT * FROM orders WHERE customer_id = ? ORDER BY created_at DESC LIMIT 20;
```

- Without a usable index, both databases sort every matching row before applying `LIMIT` (MySQL shows `Using filesort`; PostgreSQL shows a `Sort` node).
- Mixed directions (`ORDER BY a ASC, b DESC`) need an index declared with matching directions. MySQL supports descending index parts (`DESC` in the key definition), and so does PostgreSQL.

## Covering indexes

```sql
-- MySQL: idx (customer_id, status) already contains the PK, so this query never reads the table
SELECT id, status FROM orders WHERE customer_id = ?;

-- PostgreSQL: carry extra columns without making them part of the key
CREATE INDEX idx_orders_customer ON orders (customer_id) INCLUDE (status, total);
```

Covering pays off for hot, narrow queries. Don't widen every index: each extra column costs space and write I/O.

## Expressions and partial indexes

```sql
-- Function on the column: index the expression instead of rewriting every query
CREATE INDEX idx_users_email_lower ON users ((lower(email)));   -- MySQL functional key part (double parentheses)
CREATE INDEX idx_users_email_lower ON users (lower(email));     -- PostgreSQL expression index

-- PostgreSQL partial index: index only the rows a hot query touches
CREATE INDEX idx_orders_pending ON orders (created_at) WHERE status = 'PENDING';
```

MySQL has no partial indexes; a generated column plus a regular index is the usual substitute.

## Low-cardinality columns

A boolean or a five-value status column alone rarely helps: the index would match a large share of the table, and the planner prefers a scan. It is fine as an equality **prefix** of a composite index, and in PostgreSQL as the predicate of a partial index.

## Write cost and index hygiene

- Every index is updated on every insert, and on updates that change its columns. Measure before adding a sixth index to a write-heavy table.
- Remove redundant indexes. An index on `(a)` is redundant next to `(a, b)` unless it is unique or used for a constraint.
- MySQL: make a candidate `INVISIBLE` first. The optimizer stops using it, but it is still maintained (a unique index still rejects duplicates), so you can make it visible again instantly if a query regresses. The primary key cannot be made invisible.
- PostgreSQL: `pg_stat_user_indexes.idx_scan` shows indexes never used since statistics were last reset.

## Sources

- MySQL 8.4, Clustered and Secondary Indexes: https://dev.mysql.com/doc/refman/8.4/en/innodb-index-types.html
- MySQL 8.4, Multiple-Column Indexes (leftmost prefix): https://dev.mysql.com/doc/refman/8.4/en/multiple-column-indexes.html
- MySQL 8.4, CREATE INDEX (functional key parts, `ASC`/`DESC`): https://dev.mysql.com/doc/refman/8.4/en/create-index.html
- MySQL 8.4, Invisible Indexes: https://dev.mysql.com/doc/refman/8.4/en/invisible-indexes.html
- PostgreSQL 18, Multicolumn Indexes (scan rule, skip scan): https://www.postgresql.org/docs/current/indexes-multicolumn.html
- PostgreSQL 18, Index-Only Scans and Covering Indexes: https://www.postgresql.org/docs/current/indexes-index-only-scans.html
- PostgreSQL 18, Partial Indexes: https://www.postgresql.org/docs/current/indexes-partial.html
- PostgreSQL 18, Indexes and ORDER BY: https://www.postgresql.org/docs/current/indexes-ordering.html
- PostgreSQL 18, Heap-Only Tuples (HOT): https://www.postgresql.org/docs/current/storage-hot.html
