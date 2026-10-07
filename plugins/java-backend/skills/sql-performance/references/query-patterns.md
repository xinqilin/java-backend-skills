# Query Patterns and Anti-Patterns

## Keep the indexed column bare

```sql
-- Can't use an index on created_at: the function hides the column
SELECT * FROM orders WHERE YEAR(created_at) = 2024;

-- Index-friendly half-open range
SELECT * FROM orders WHERE created_at >= '2024-01-01' AND created_at < '2025-01-01';
```

If the expression is inherent to the query (`lower(email)`), index the expression: MySQL functional key parts or a PostgreSQL expression index (`index-design.md`).

## Types must match (MySQL)

```sql
-- customer_ref is VARCHAR: MySQL converts every row's string to a number, so the index is unusable
SELECT * FROM orders WHERE customer_ref = 12345;

-- Matching literal type: index usable
SELECT * FROM orders WHERE customer_ref = '12345';
```

The MySQL manual explains why: many strings convert to the number 1 (`'1'`, `' 1'`, `'1a'`), so an index on a string column can't be used to look up a numeric value. The reverse (an INT column compared with `'123'`) converts the constant once and can use the index. In JPA this shows up as an entity field typed `Long` mapped to a `VARCHAR` column, or a native query bound with the wrong type.

## Pagination

### OFFSET reads and discards

```sql
SELECT * FROM orders ORDER BY created_at DESC, id DESC LIMIT 20 OFFSET 100000; -- reads 100,020 rows
```

### Keyset (seek) pagination

```sql
-- First page
SELECT * FROM orders WHERE customer_id = ? ORDER BY created_at DESC, id DESC LIMIT 20;

-- Next page: continue after the last row seen (created_at = :ts, id = :id)
SELECT * FROM orders
WHERE customer_id = ?
  AND (created_at < :ts OR (created_at = :ts AND id < :id))
ORDER BY created_at DESC, id DESC
LIMIT 20;
-- Index: (customer_id, created_at, id)
```

- Include a unique tiebreaker (`id`) in both the sort and the predicate, or rows with equal timestamps get skipped or repeated.
- PostgreSQL handles the row-value form `(created_at, id) < (:ts, :id)` well. MySQL's manual warns that the optimizer is less likely to use an index when a row constructor doesn't cover an index prefix (as here, after the `customer_id` equality), so prefer the expanded `OR` form above for MySQL.
- Keyset can't jump to page 500. Most UIs don't need that; if one does, use a deferred join (page over ids only, then join back for the rows).
- In Spring Data, return `Slice`/`Window` or a `List` instead of `Page`, to avoid the extra count query.

## NOT IN vs NOT EXISTS

```sql
-- Wrong when blacklist.customer_id can be NULL: NOT IN then returns no rows at all
SELECT * FROM orders WHERE customer_id NOT IN (SELECT customer_id FROM blacklist);

-- Correct regardless of NULLs
SELECT * FROM orders o
WHERE NOT EXISTS (SELECT 1 FROM blacklist b WHERE b.customer_id = o.customer_id);
```

`x NOT IN (..., NULL)` evaluates to `NULL` (not true) for every `x`, so this is a correctness bug before it is a performance one.

## OR across columns

```sql
SELECT * FROM orders WHERE customer_id = ? OR status = ?;
```

- MySQL can serve this with **Index Merge**: one range scan per index, results merged (union or intersection). `EXPLAIN` shows `type: index_merge`.
- PostgreSQL can **combine indexes** with bitmap scans (`BitmapOr`).
- Rewrite into `UNION` only when the plan shows neither happening and the separate branches are each selective.

## Subqueries and joins

- `IN (subquery)` and `EXISTS` are usually optimized as semi-joins by both databases. Rewriting them as `JOIN` changes the results when the inner side can repeat values (duplicate rows), so add `DISTINCT` or keep the semi-join.
- A correlated scalar subquery in the `SELECT` list (`(SELECT count(*) FROM items WHERE order_id = o.id)`) runs per row unless the optimizer decorrelates it. Aggregate once in a derived table and join when the plan shows per-row execution.
- CTEs: MySQL materializes a CTE at most once per query, however often it is referenced. PostgreSQL inlines a non-recursive, side-effect-free CTE referenced once and materializes it otherwise; override with `MATERIALIZED` or `NOT MATERIALIZED`.

## Select only what you use

- `SELECT *` defeats covering indexes and moves more bytes. In JPA, read paths should use projections (`java-backend:jpa-hibernate`).
- Unbounded result sets (`findAll()` on a growing table) end in memory pressure. Page, stream, or aggregate in SQL.

## Counting

- InnoDB handles `COUNT(*)` and `COUNT(1)` the same way, with no performance difference.
- Neither InnoDB nor PostgreSQL keeps an exact row count per table: MVCC means different transactions can see different counts. Exact counts of large tables scan an index or the table; for "about N results", use a capped count (`SELECT count(*) FROM (SELECT 1 ... LIMIT 1001) t`) or estimates.

## Sources

- MySQL 8.4, Type Conversion in Expression Evaluation: https://dev.mysql.com/doc/refman/8.4/en/type-conversion.html
- MySQL 8.4, Row Constructor Expression Optimization: https://dev.mysql.com/doc/refman/8.4/en/row-constructor-optimization.html
- MySQL 8.4, Index Merge Optimization: https://dev.mysql.com/doc/refman/8.4/en/index-merge-optimization.html
- MySQL 8.4, Optimizing Derived Tables, View References, and Common Table Expressions: https://dev.mysql.com/doc/refman/8.4/en/derived-table-optimization.html
- MySQL 8.4, Aggregate Function Descriptions (`COUNT`): https://dev.mysql.com/doc/refman/8.4/en/aggregate-functions.html
- PostgreSQL 18, Combining Multiple Indexes: https://www.postgresql.org/docs/current/indexes-bitmap-scans.html
- PostgreSQL 18, WITH Queries (CTE inlining and `MATERIALIZED`): https://www.postgresql.org/docs/current/queries-with.html
- Spring Data JPA, Paging, scrolling and slicing (`Slice`, `Window`): https://docs.spring.io/spring-data/jpa/reference/repositories/query-methods-details.html
