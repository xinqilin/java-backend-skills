---
name: optimize-query
description: Analyze slow SQL or Spring Data JPA queries on MySQL or PostgreSQL using execution plans, indexes, and fetch strategy. Use when the user asks to optimize a query, read an EXPLAIN plan, or fix a database bottleneck.
argument-hint: "[file-or-query]"
allowed-tools: Read, Grep, Glob, Bash
context: fork
agent: java-backend:data-architect
---

# Optimize Query

Help optimize database queries (SQL/JPA) for better performance in production environments. Focus on real-world performance bottlenecks with measurable improvements.

## Analysis Workflow

### Step 1: Understand Current Performance

Gather baseline metrics:
```sql
-- Execution time
EXPLAIN ANALYZE SELECT ...;

-- Row counts
SELECT COUNT(*) FROM orders;
SELECT COUNT(*) FROM order_items;

-- Table size
SELECT
    table_name,
    table_rows,
    data_length / 1024 / 1024 AS size_mb
FROM information_schema.tables
WHERE table_schema = 'your_database';
```

**Required Information**:
- Query execution time (ms)
- Data volume (number of rows)
- Expected QPS (queries per second)
- Current infrastructure (CPU, memory, disk)

### Step 2: Identify Performance Problems

#### Problem Pattern 1: N+1 Query Problem

**Symptom**: Multiple queries when one would suffice

```java
// Bad: N+1 Problem (1 + N queries)
List<Order> orders = orderRepository.findAll();  // 1 query
for (Order order : orders) {
    List<OrderItem> items = itemRepository.findByOrderId(order.getId());  // N queries
    order.setItems(items);
}
```

**Impact**: If you have 1000 orders, this executes 1001 queries!

**Solution**:
```java
// Good: Single query with JOIN FETCH
@Query("SELECT DISTINCT o FROM Order o LEFT JOIN FETCH o.items")
List<Order> findAllWithItems();

// Alternative: Batch loading
@EntityGraph(attributePaths = {"items"})
List<Order> findAll();
```

**Performance Gain**: 1001 queries → 1 query (99.9% reduction)

#### Problem Pattern 2: Missing Index

**Symptom**: Full table scan on WHERE clause

```sql
-- EXPLAIN output shows: type=ALL, rows=5000000
EXPLAIN SELECT * FROM orders WHERE customer_id = 12345;
```

**Solution**:
```sql
-- Create index on commonly queried column
CREATE INDEX idx_orders_customer_id ON orders(customer_id);

-- Verify index usage
EXPLAIN SELECT * FROM orders WHERE customer_id = 12345;
-- Should now show: type=ref, key=idx_orders_customer_id, rows=~50
```

**Performance Gain**: Full scan of 5M rows → Index lookup of ~50 rows

#### Problem Pattern 3: Inefficient Pagination

```java
// Bad: OFFSET grows, performance degrades linearly
@Query("SELECT o FROM Order o ORDER BY o.createdAt DESC")
Page<Order> findAll(Pageable pageable);  // OFFSET 10000 LIMIT 20
```

**Problem**: Database must scan 10,020 rows to return 20 rows.

**Solution**: Keyset pagination
```java
// Good: Use last seen ID
@Query("SELECT o FROM Order o WHERE o.id < :lastId ORDER BY o.id DESC")
List<Order> findNextPage(@Param("lastId") Long lastId, Pageable pageable);
```

#### Problem Pattern 4: SELECT * When You Need Few Columns

```java
// Bad: Fetching unnecessary data
@Query("SELECT o FROM Order o WHERE o.status = :status")
List<Order> findByStatus(String status);  // Loads all columns

// Good: Projection for specific fields
@Query("SELECT new com.example.dto.OrderSummary(o.id, o.totalAmount, o.status) " +
       "FROM Order o WHERE o.status = :status")
List<OrderSummary> findSummaryByStatus(String status);
```

#### Problem Pattern 5: Inefficient Joins

```sql
-- Bad: Cartesian product risk
SELECT *
FROM orders o
JOIN order_items oi
WHERE o.customer_id = 123;  -- Missing join condition!

-- Good: Proper join condition
SELECT o.*, oi.*
FROM orders o
JOIN order_items oi ON o.id = oi.order_id
WHERE o.customer_id = 123;
```

### Step 3: Index Strategy

#### When to Create Index

Create index when:
- Column is frequently used in WHERE clause
- Column is used in JOIN conditions
- Column is used in ORDER BY
- Query selectivity is high (index returns < 15% of rows)

```sql
-- High selectivity: Good candidate
SELECT * FROM users WHERE email = 'user@example.com';  -- Returns 1 row

-- Low selectivity: Poor candidate
SELECT * FROM users WHERE is_active = true;  -- Returns 90% of rows
```

#### Composite Index Column Order

**Rule**: Most selective column first, then by query frequency

```sql
-- Query pattern
WHERE status = 'PENDING' AND customer_id = 123 AND created_at > '2024-01-01'

-- Analyze selectivity
SELECT
    COUNT(DISTINCT status) as status_values,  -- Result: 5
    COUNT(DISTINCT customer_id) as customers, -- Result: 50000
    COUNT(DISTINCT DATE(created_at)) as dates -- Result: 365
FROM orders;

-- Optimal index: customer_id (most selective) first
CREATE INDEX idx_orders_lookup ON orders(customer_id, status, created_at);
```

#### Covering Index

Index contains all columns needed by query:
```sql
-- Query needs: id, customer_id, total_amount
SELECT id, total_amount
FROM orders
WHERE customer_id = 123;

-- Covering index (no table access needed)
CREATE INDEX idx_orders_covering ON orders(customer_id, id, total_amount);
```

**Benefit**: Index-only scan - no table access needed

### Step 4: JPA-Specific Optimizations

#### FetchType Strategy

```java
// Default LAZY loading causes N+1
@Entity
public class Order {
    @OneToMany(mappedBy = "order")  // Default: LAZY
    private List<OrderItem> items;
}

// Solution 1: EAGER (use cautiously)
@OneToMany(mappedBy = "order", fetch = FetchType.EAGER)
private List<OrderItem> items;

// Solution 2: Query-specific fetch (preferred)
@Query("SELECT o FROM Order o LEFT JOIN FETCH o.items WHERE o.id = :id")
Optional<Order> findByIdWithItems(@Param("id") Long id);

// Solution 3: EntityGraph
@EntityGraph(attributePaths = {"items", "customer"})
Optional<Order> findById(Long id);
```

#### Batch Fetching

```java
// Configure in application.properties
spring.jpa.properties.hibernate.default_batch_fetch_size=10

// Or per-entity
@Entity
@BatchSize(size = 10)
public class Order {
    @OneToMany
    @BatchSize(size = 10)
    private List<OrderItem> items;
}
```

**Impact**: Fetches associations in batches instead of one-by-one

#### Query Hints

```java
// Read-only query optimization
@QueryHints(@QueryHint(name = "org.hibernate.readOnly", value = "true"))
List<Order> findByStatus(String status);

// Cache query results
@QueryHints(@QueryHint(name = "org.hibernate.cacheable", value = "true"))
List<Product> findAllProducts();
```

### Step 5: Advanced Optimization Techniques

#### Denormalization for Read-Heavy Workloads

```java
// Before: Join on every query
SELECT o.id, c.name, c.email
FROM orders o
JOIN customers c ON o.customer_id = c.id;

// After: Denormalize frequently accessed data
@Entity
public class Order {
    private Long customerId;
    private String customerName;  // Denormalized
    private String customerEmail; // Denormalized
}
```

**Trade-off**: Faster reads, slower writes, data duplication

## Output Format

Write the analysis in the user's language. Keep code, SQL, and identifiers as-is.

For each optimization, provide:

### 1. Current State Assessment
```
Execution Time: 3.5 seconds
Rows Examined: 5,000,000
Rows Returned: 150
Index Used: NONE
Problem: Full table scan on orders table
```

### 2. Root Cause Analysis
```
The query uses WHERE customer_id = 123 but there's no index
on customer_id column. MySQL performs a full table scan,
examining all 5M rows to find matching records.

EXPLAIN output:
type: ALL
rows: 5000000
Extra: Using where
```

### 3. Optimization Solution

**SQL Changes**:
```sql
CREATE INDEX idx_orders_customer_id ON orders(customer_id);
```

**JPA Changes**:
```java
@Entity
@Table(name = "orders", indexes = {
    @Index(name = "idx_orders_customer_id", columnList = "customer_id")
})
public class Order {
    // entity fields
}
```

### 4. Expected Improvement
```
Execution Time: 3.5s → 45ms (98.7% faster)
Rows Examined: 5,000,000 → 150 (99.997% reduction)
Index Used: idx_orders_customer_id
```

### 5. Verification Steps
```sql
-- Test query performance
SET profiling = 1;
SELECT * FROM orders WHERE customer_id = 123;
SHOW PROFILES;

-- Verify index usage
EXPLAIN SELECT * FROM orders WHERE customer_id = 123;

-- Check index statistics
SHOW INDEX FROM orders;
```

### 6. Trade-offs and Warnings

**Index Overhead**:
- Additional disk space: ~50MB for this index
- INSERT/UPDATE performance: ~10% slower (extra index maintenance)
- Worth it if reads >> writes (typical OLTP pattern)

## Common Query Anti-Patterns

### 1. Using Functions in WHERE Clause
```sql
-- Bad: Prevents index usage
SELECT * FROM orders WHERE YEAR(created_at) = 2024;

-- Good: Index-friendly
SELECT * FROM orders
WHERE created_at >= '2024-01-01' AND created_at < '2025-01-01';
```

### 2. OR Conditions Spanning Multiple Columns
```sql
-- Bad: Can't use composite index efficiently
SELECT * FROM orders WHERE customer_id = 123 OR status = 'PENDING';

-- Good: Use UNION
SELECT * FROM orders WHERE customer_id = 123
UNION
SELECT * FROM orders WHERE status = 'PENDING';
```

### 3. Implicit Type Conversion
```sql
-- Bad: customer_id is INT, but querying with STRING
SELECT * FROM orders WHERE customer_id = '123';  -- Index not used!

-- Good: Match column type
SELECT * FROM orders WHERE customer_id = 123;
```

## Optimization Checklist

Before optimizing:
- [ ] Measure baseline performance (execution time, rows examined)
- [ ] Identify exact bottleneck (EXPLAIN ANALYZE)
- [ ] Check existing indexes (SHOW INDEX)
- [ ] Understand data volume and growth rate
- [ ] Know read/write ratio

After optimizing:
- [ ] Verify performance improvement (before/after metrics)
- [ ] Check EXPLAIN output (index usage confirmed)
- [ ] Test with realistic data volume
- [ ] Monitor for 24-48 hours (catch edge cases)
- [ ] Document the change (comments in code, migration scripts)

## Performance Tuning Priorities

1. **Eliminate N+1 Queries** (highest impact, usually easy fix)
2. **Add Missing Indexes** (high impact on large tables)
3. **Optimize JOIN Operations** (especially multi-table joins)
4. **Implement Pagination** (for large result sets)
5. **Use Projections** (select only needed columns)
6. **Consider Caching** (for rarely changing, frequently read data)
7. **Database Connection Pooling** (prevent connection overhead)

## When to Apply

- Slow query analysis or EXPLAIN plan review
- Investigating N+1 queries
- SQL/JPA performance bottlenecks
- Index design or tuning

## When NOT to Optimize

- Table has < 1000 rows (overhead > benefit)
- Query runs < 100ms and isn't frequent
- Write-heavy workload where index overhead hurts more
- Development/testing environment (optimize for production data)

## Gotchas

<!-- Keep adding mistakes Claude repeatedly makes. -->

- **EXPLAIN on empty or tiny tables misleads**: plans depend on statistics; test with production-like data volume.
- **Check selectivity before adding an index**: `SELECT COUNT(DISTINCT col) / COUNT(*) FROM t`; a low-cardinality column alone (such as a status with 5 values) rarely makes a useful index.
- **The optimizer may skip your index for a reason**: understand why before forcing it with an index hint; forcing can be slower.
- **Spring Data JPA `findAll()` has no size guard**: on large tables it can exhaust memory; use paging or limits.
- **Collection fetch join + pagination**: Hibernate applies the limit in memory after loading every matching row; paginate IDs first, then fetch.
