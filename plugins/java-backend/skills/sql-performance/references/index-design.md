# MySQL Index Design Guide

## B+Tree Index Structure

```
                    [Root Node]
                   /     |     \
            [Branch]  [Branch]  [Branch]
           /   |   \
      [Leaf] [Leaf] [Leaf] → [Leaf] → [Leaf]  (Linked list)
       ↓       ↓       ↓
    [Data]  [Data]  [Data]  (Row pointers or data in InnoDB)
```

### Key Properties

- **Balanced**: All leaf nodes at same depth
- **Sorted**: Keys in order within nodes
- **Linked**: Leaf nodes form linked list (range scans efficient)
- **B+Tree in InnoDB**: Clustered index stores actual row data

---

## Clustered vs Secondary Index

### Clustered Index (Primary Key)

```
Primary Key Index (Clustered):
┌─────────────────────────────────────┐
│ id=1 │ customer │ total │ status │  ← Actual row data
│ id=2 │ customer │ total │ status │
│ id=3 │ customer │ total │ status │
└─────────────────────────────────────┘
```

### Secondary Index

```
Secondary Index on customer_id:
┌────────────────────────┐
│ customer_id │ id (PK)  │  ← Only index columns + PK
│ C001        │ 1        │
│ C001        │ 5        │
│ C002        │ 2        │
└────────────────────────┘
        ↓
   Lookup by PK to get full row (unless covering index)
```

---

## Composite Index Design

### The Leftmost Prefix Rule

```sql
-- Index: (a, b, c)

-- Uses index fully
WHERE a = 1 AND b = 2 AND c = 3  ✓
WHERE a = 1 AND b = 2            ✓
WHERE a = 1                      ✓

-- Uses partial index
WHERE a = 1 AND c = 3            ✓ (only 'a' used, 'c' filtered after)

-- Cannot use index
WHERE b = 2 AND c = 3            ✗ (missing leftmost 'a')
WHERE c = 3                      ✗
```

### Column Order Strategy

**1. Equality Conditions First**

```sql
-- Query
WHERE status = 'PENDING' AND customer_id = ?

-- Good: Most selective equality condition first
INDEX (customer_id, status)  -- customer_id likely more selective

-- Check selectivity
SELECT
    COUNT(DISTINCT customer_id) / COUNT(*) as cust_sel,  -- e.g., 0.9
    COUNT(DISTINCT status) / COUNT(*) as status_sel      -- e.g., 0.001
FROM orders;
```

**2. Range Conditions Last**

```sql
-- Query
WHERE customer_id = ? AND created_at > ? AND created_at < ?

-- Good: Equality before range
INDEX (customer_id, created_at)

-- Query with range on multiple columns
WHERE customer_id = ? AND price > 100 AND created_at > '2024-01-01'

-- Only one range can use index efficiently
INDEX (customer_id, price, created_at)  -- price range used, created_at filtered
-- OR
INDEX (customer_id, created_at, price)  -- created_at range used, price filtered
-- Choose based on which range is more selective
```

**3. ORDER BY / GROUP BY Consideration**

```sql
-- Query
WHERE customer_id = ? ORDER BY created_at DESC

-- Good: Index supports both filter and sort
INDEX (customer_id, created_at)  -- avoids filesort

-- Query with different sort direction
WHERE customer_id = ? ORDER BY created_at DESC, total ASC

-- Index must match sort directions
INDEX (customer_id, created_at DESC, total ASC)  -- MySQL 8.0+
```

---

## Covering Index

### What It Does

A covering index contains all columns needed by the query, eliminating the need to access the actual table rows.

```sql
-- Query
SELECT order_id, status, total
FROM orders
WHERE customer_id = ? AND created_at > ?;

-- Non-covering index
INDEX (customer_id, created_at)
-- Process: Find matching index entries → Lookup each row by PK → Return columns

-- Covering index
INDEX (customer_id, created_at, order_id, status, total)
-- Process: Find matching index entries → Return columns directly (no row lookup)
```

### EXPLAIN Output

```sql
EXPLAIN SELECT order_id, status FROM orders WHERE customer_id = ?;

-- Non-covering: Extra shows nothing or "Using where"
-- Covering: Extra shows "Using index"
```

### Trade-offs

| Pros | Cons |
|------|------|
| Eliminates row lookups | Larger index size |
| Faster SELECT | Slower INSERT/UPDATE |
| Reduces I/O | More memory for caching |

---

## Index for Common Patterns

### Pattern 1: Exact Match + Range

```sql
WHERE user_id = ? AND created_at BETWEEN ? AND ?

INDEX (user_id, created_at)
```

### Pattern 2: Multiple Equality

```sql
WHERE status = ? AND type = ? AND region = ?

-- Order by selectivity (most selective first)
INDEX (region, type, status)  -- if region is most selective
```

### Pattern 3: IN Clause

```sql
WHERE status IN ('PENDING', 'PROCESSING') AND customer_id = ?

-- IN is treated as multiple equality conditions
INDEX (status, customer_id)  -- OR
INDEX (customer_id, status)  -- depends on selectivity
```

### Pattern 4: LIKE Prefix

```sql
WHERE name LIKE 'John%'  -- Can use index
WHERE name LIKE '%John'  -- Cannot use index
WHERE name LIKE '%John%' -- Cannot use index

INDEX (name)  -- Only works for prefix LIKE
```

### Pattern 5: NULL Handling

```sql
WHERE deleted_at IS NULL  -- Can use index
WHERE deleted_at IS NOT NULL  -- Can use index

INDEX (deleted_at)
```

---

## Index Maintenance

### Finding Unused Indexes

```sql
-- MySQL 8.0+ with sys schema
SELECT *
FROM sys.schema_unused_indexes
WHERE object_schema = 'your_database';
```

### Finding Redundant Indexes

```sql
-- Index (a, b) makes (a) redundant
SELECT *
FROM sys.schema_redundant_indexes
WHERE table_schema = 'your_database';
```

### Index Statistics

```sql
-- Check index cardinality
SHOW INDEX FROM orders;

-- Update statistics
ANALYZE TABLE orders;
```

### Index Size

```sql
SELECT
    table_name,
    index_name,
    ROUND(stat_value * @@innodb_page_size / 1024 / 1024, 2) AS size_mb
FROM mysql.innodb_index_stats
WHERE stat_name = 'size'
  AND database_name = 'your_database'
ORDER BY stat_value DESC;
```

---

## Common Mistakes

### 1. Over-Indexing

```sql
-- Too many indexes slow down writes
CREATE INDEX idx1 ON orders (customer_id);
CREATE INDEX idx2 ON orders (customer_id, status);  -- idx1 is redundant!
CREATE INDEX idx3 ON orders (customer_id, status, created_at);  -- idx2 is redundant!

-- Keep only idx3
```

### 2. Low Selectivity Leading Column

```sql
-- Bad: status has only 5 distinct values
INDEX (status, customer_id)

-- Good: customer_id has high selectivity
INDEX (customer_id, status)
```

### 3. Function on Indexed Column

```sql
-- Cannot use index
WHERE YEAR(created_at) = 2024

-- Can use index
WHERE created_at >= '2024-01-01' AND created_at < '2025-01-01'

-- Cannot use index
WHERE LOWER(email) = 'test@example.com'

-- Solution: Generated column + index
ALTER TABLE users ADD email_lower VARCHAR(255) GENERATED ALWAYS AS (LOWER(email)) STORED;
CREATE INDEX idx_email_lower ON users (email_lower);
```

### 4. Type Mismatch

```sql
-- Column is VARCHAR, but comparing to INT
WHERE customer_id = 12345  -- Index may not be used

-- Match the type
WHERE customer_id = '12345'
```

---

## Index Design Checklist

1. **Identify query patterns** - Which columns in WHERE, ORDER BY, GROUP BY?
2. **Check selectivity** - High selectivity columns should lead
3. **Consider covering** - Can we include SELECT columns?
4. **Test with EXPLAIN** - Verify index is used
5. **Monitor unused indexes** - Remove if not used
6. **Balance read/write** - More indexes = slower writes
