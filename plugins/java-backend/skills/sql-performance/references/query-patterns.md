# MySQL Query Optimization Patterns

## EXPLAIN Analysis Deep Dive

### Full EXPLAIN Output

```sql
EXPLAIN FORMAT=JSON SELECT * FROM orders WHERE customer_id = ? AND status = ?;
```

### Key Metrics

| Column | Meaning | Target |
|--------|---------|--------|
| type | Access method | ref or better |
| possible_keys | Available indexes | Should list expected index |
| key | Actually used index | Should match expected |
| key_len | Index bytes used | Full key length |
| rows | Estimated rows scanned | As low as possible |
| filtered | % rows after filter | Close to 100% |
| Extra | Additional info | Avoid filesort, temporary |

### Type Values Explained

```sql
-- const: Primary key or unique index lookup, single row
EXPLAIN SELECT * FROM orders WHERE id = 1;
-- type: const

-- eq_ref: One row per join, unique index
EXPLAIN SELECT * FROM orders o JOIN customers c ON o.customer_id = c.id;
-- orders.type: ALL, customers.type: eq_ref

-- ref: Non-unique index lookup
EXPLAIN SELECT * FROM orders WHERE customer_id = 'C001';
-- type: ref

-- range: Index range scan
EXPLAIN SELECT * FROM orders WHERE created_at > '2024-01-01';
-- type: range

-- index: Full index scan (reads every index entry)
EXPLAIN SELECT customer_id FROM orders;
-- type: index (if customer_id is indexed)

-- ALL: Full table scan (worst)
EXPLAIN SELECT * FROM orders WHERE description LIKE '%keyword%';
-- type: ALL
```

---

## Query Anti-Patterns and Fixes

### 1. SELECT *

```sql
-- Bad: Fetches all columns
SELECT * FROM orders WHERE customer_id = ?;

-- Good: Fetch only needed columns
SELECT id, status, total FROM orders WHERE customer_id = ?;

-- Benefit: Enables covering index
CREATE INDEX idx_customer_covering ON orders (customer_id, id, status, total);
```

### 2. OR on Different Columns

```sql
-- Bad: Each OR branch scanned separately
SELECT * FROM orders WHERE customer_id = ? OR status = ?;
-- May do full table scan

-- Better: UNION (can use indexes on each)
SELECT * FROM orders WHERE customer_id = ?
UNION
SELECT * FROM orders WHERE status = ?;

-- Or restructure if possible
```

### 3. NOT IN with Subquery

```sql
-- Bad: Poor optimization
SELECT * FROM customers
WHERE id NOT IN (SELECT customer_id FROM orders);

-- Better: LEFT JOIN + IS NULL
SELECT c.* FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id
WHERE o.customer_id IS NULL;

-- Or: NOT EXISTS
SELECT * FROM customers c
WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id);
```

### 4. Correlated Subquery

```sql
-- Bad: Executes subquery for each row
SELECT *,
    (SELECT COUNT(*) FROM order_items WHERE order_id = o.id) as item_count
FROM orders o;

-- Better: JOIN with aggregation
SELECT o.*, COALESCE(oi.item_count, 0) as item_count
FROM orders o
LEFT JOIN (
    SELECT order_id, COUNT(*) as item_count
    FROM order_items
    GROUP BY order_id
) oi ON o.id = oi.order_id;
```

### 5. DISTINCT with Large Result Set

```sql
-- Expensive: Sort and dedupe large set
SELECT DISTINCT customer_id FROM orders;

-- Better if you just need existence
SELECT customer_id FROM orders GROUP BY customer_id;

-- Or use index-only scan
CREATE INDEX idx_customer ON orders (customer_id);
-- Then:
SELECT customer_id FROM orders GROUP BY customer_id;
-- EXPLAIN shows "Using index"
```

### 6. ORDER BY with LIMIT but without Index

```sql
-- Bad: Sorts entire table, then takes 10
SELECT * FROM orders ORDER BY created_at DESC LIMIT 10;
-- If no index on created_at: filesort on all rows

-- Good: Index supports sort
CREATE INDEX idx_created ON orders (created_at DESC);
SELECT * FROM orders ORDER BY created_at DESC LIMIT 10;
-- Reads only 10 rows from index
```

---

## Pagination Strategies

### Offset Pagination (Simple but Slow)

```sql
-- Page 1
SELECT * FROM orders ORDER BY id LIMIT 20 OFFSET 0;

-- Page 1000 (slow!)
SELECT * FROM orders ORDER BY id LIMIT 20 OFFSET 19980;
-- Scans 20,000 rows, returns 20
```

### Keyset Pagination (Fast)

```sql
-- First page
SELECT * FROM orders ORDER BY id LIMIT 20;

-- Subsequent pages (pass last_id from previous page)
SELECT * FROM orders WHERE id > :last_id ORDER BY id LIMIT 20;
-- Always scans only 20 rows

-- For descending order
SELECT * FROM orders WHERE id < :last_id ORDER BY id DESC LIMIT 20;
```

### Keyset with Multiple Sort Columns

```sql
-- Sort by created_at DESC, then id DESC
-- First page
SELECT * FROM orders ORDER BY created_at DESC, id DESC LIMIT 20;

-- Next page (pass last_created_at and last_id)
SELECT * FROM orders
WHERE (created_at, id) < (:last_created_at, :last_id)
ORDER BY created_at DESC, id DESC
LIMIT 20;

-- Index to support this
CREATE INDEX idx_created_id ON orders (created_at DESC, id DESC);
```

### Deferred Join (for offset when needed)

```sql
-- Instead of
SELECT * FROM orders ORDER BY created_at DESC LIMIT 20 OFFSET 10000;

-- Use deferred join
SELECT o.* FROM orders o
INNER JOIN (
    SELECT id FROM orders ORDER BY created_at DESC LIMIT 20 OFFSET 10000
) AS tmp ON o.id = tmp.id
ORDER BY o.created_at DESC;

-- Inner query uses covering index on (created_at, id)
-- Only 20 full rows fetched
```

---

## Aggregation Optimization

### COUNT Optimization

```sql
-- Slow: Counts all matching rows
SELECT COUNT(*) FROM orders WHERE status = 'PENDING';

-- Fast for "are there any?"
SELECT EXISTS(SELECT 1 FROM orders WHERE status = 'PENDING' LIMIT 1);

-- Fast for "more than N?"
SELECT COUNT(*) FROM (
    SELECT 1 FROM orders WHERE status = 'PENDING' LIMIT 101
) t;
-- Returns 101 if more than 100, otherwise exact count

-- Approximate count (for very large tables)
SELECT table_rows FROM information_schema.tables
WHERE table_schema = 'your_db' AND table_name = 'orders';
```

### GROUP BY Optimization

```sql
-- Ensure index supports GROUP BY
SELECT customer_id, SUM(total) as total_spent
FROM orders
WHERE created_at > '2024-01-01'
GROUP BY customer_id;

-- Index
CREATE INDEX idx_created_customer ON orders (created_at, customer_id, total);
-- Allows range on created_at, group by customer_id, covering for total
```

### HAVING vs WHERE

```sql
-- Bad: HAVING on non-aggregate
SELECT customer_id, COUNT(*) as order_count
FROM orders
GROUP BY customer_id
HAVING customer_id LIKE 'VIP%';  -- Applied after grouping

-- Good: WHERE filters first
SELECT customer_id, COUNT(*) as order_count
FROM orders
WHERE customer_id LIKE 'VIP%'  -- Applied before grouping
GROUP BY customer_id;
```

---

## JOIN Optimization

### Join Order

MySQL optimizer usually picks the best order, but you can hint:

```sql
-- Force join order
SELECT STRAIGHT_JOIN o.*, c.*
FROM orders o
JOIN customers c ON o.customer_id = c.id
WHERE c.region = 'ASIA';
```

### Join Type Selection

```sql
-- INNER JOIN: Both tables must match
SELECT o.* FROM orders o
INNER JOIN customers c ON o.customer_id = c.id;

-- LEFT JOIN: Keep all from left, match from right
SELECT c.*, o.total FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id;

-- For existence check, EXISTS is often faster than JOIN
SELECT * FROM customers c
WHERE EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id);
```

### Avoiding Implicit Type Conversion

```sql
-- Bad: customer_id is VARCHAR, comparing to INT
SELECT * FROM orders WHERE customer_id = 12345;
-- Index on customer_id may not be used

-- Good: Match types
SELECT * FROM orders WHERE customer_id = '12345';
```

---

## Subquery Optimization

### Materialization vs Correlation

```sql
-- Materialized subquery (computed once)
SELECT * FROM orders
WHERE customer_id IN (SELECT id FROM customers WHERE region = 'ASIA');
-- Subquery result cached, checked against

-- Correlated subquery (computed per row)
SELECT * FROM orders o
WHERE EXISTS (SELECT 1 FROM customers c
              WHERE c.id = o.customer_id AND c.region = 'ASIA');
-- May be faster for small outer result set
```

### Converting to JOIN

```sql
-- Subquery
SELECT * FROM orders
WHERE customer_id IN (SELECT id FROM customers WHERE vip = true);

-- Equivalent JOIN (often better optimized)
SELECT o.* FROM orders o
INNER JOIN customers c ON o.customer_id = c.id
WHERE c.vip = true;

-- For NOT IN, use LEFT JOIN + IS NULL
SELECT o.* FROM orders o
LEFT JOIN blacklist b ON o.customer_id = b.customer_id
WHERE b.customer_id IS NULL;
```

---

## Query Hints

### Force Index

```sql
SELECT * FROM orders FORCE INDEX (idx_customer)
WHERE customer_id = ? AND status = ?;
```

### Ignore Index

```sql
SELECT * FROM orders IGNORE INDEX (idx_status)
WHERE status = 'PENDING';
```

### Optimizer Hints (MySQL 8.0+)

```sql
SELECT /*+ NO_INDEX_MERGE(orders) */ *
FROM orders WHERE customer_id = ? OR status = ?;

SELECT /*+ JOIN_ORDER(c, o) */ o.*, c.*
FROM orders o JOIN customers c ON o.customer_id = c.id;
```
