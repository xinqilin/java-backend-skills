---
name: sql-performance
description: MySQL and PostgreSQL query performance for Spring Boot apps (index design, execution plans, query patterns). Use when reviewing database access code, designing indexes, or reading EXPLAIN output.
user-invocable: false
allowed-tools: Read, Grep, Glob
---

# MySQL Performance Optimization

## Index Design Principles

### Composite Index Column Order

**Rule: Equality first, Range last, ORDER BY in between**

```sql
-- Query: customer_id = equality, status = equality, created_at > = range
-- Optimal index: equality columns first, range column last
CREATE INDEX idx_orders_customer_status_created
ON orders (customer_id, status, created_at);
```

**Index stops working after range condition**: `(a, b, c, d)` with `WHERE a=1 AND b>10 AND c=5` — only a and b are used. c is skipped because b is a range.

### Covering Index

Include all SELECT columns in the index to avoid table lookup. `EXPLAIN` shows `Using index` when covering index is hit.

### Index Selectivity

High selectivity (many distinct values) = better index candidate.
```sql
SELECT COUNT(DISTINCT customer_id) / COUNT(*) AS selectivity FROM orders;
-- 0.85 = good candidate, 0.001 = poor candidate
```

---

## Query Optimization Patterns

### N+1 Problem

```java
// BAD - N+1 queries (1 + N)
List<Order> orders = orderRepository.findByCustomerId(customerId);
for (Order order : orders) {
    List<OrderItem> items = order.getItems();  // Lazy load = 1 query per order!
}
```

**Solutions:**
```java
// Solution 1: JOIN FETCH
@Query("SELECT o FROM Order o JOIN FETCH o.items WHERE o.customerId = :customerId")
List<Order> findByCustomerIdWithItems(@Param("customerId") String customerId);

// Solution 2: @EntityGraph
@EntityGraph(attributePaths = {"items", "items.product"})
List<Order> findByCustomerId(String customerId);

// Solution 3: Batch fetching (application.yml)
// spring.jpa.properties.hibernate.default_batch_fetch_size: 100
```

### Keyset Pagination (vs OFFSET)

OFFSET scans all preceding rows — becomes slow with large offsets.

```java
// BAD: OFFSET 200000 = MySQL scans 200,020 rows
Page<Order> findAll(Pageable pageable);

// GOOD: Keyset pagination - O(log n) regardless of page
@Query("SELECT o FROM Order o WHERE o.id > :lastId ORDER BY o.id LIMIT :size")
List<Order> findNextPage(@Param("lastId") Long lastId, @Param("size") int size);
```

---

## JPA/Hibernate Tuning

### Fetch Strategy

Always LAZY for collections. Consider LAZY for `@ManyToOne` to avoid joins when not needed.

```java
@Entity
public class Order {
    @ManyToOne(fetch = FetchType.LAZY)   // Single entity - LAZY to avoid unnecessary join
    private Customer customer;

    @OneToMany(fetch = FetchType.LAZY)   // Collection - ALWAYS LAZY
    private List<OrderItem> items;
}
```

### Batch Operations

Enable in `application.yml`:
```yaml
spring.jpa.properties.hibernate.jdbc.batch_size: 50
spring.jpa.properties.hibernate.order_inserts: true
spring.jpa.properties.hibernate.order_updates: true
```

See **references/jpa-hibernate-tuning.md** for batch insert code template and connection pool config.

### HikariCP Pool Size

Formula: `CPU cores * 2 + disk spindles` (e.g., 4-core server = pool size 9).

---

## EXPLAIN Analysis Quick Guide

| Column | Good | Bad |
|--------|------|-----|
| type | const, eq_ref, ref | ALL, index |
| rows | Low | High |
| Extra | Using index | Using filesort, Using temporary |

**Type values best to worst**: `const` → `eq_ref` → `ref` → `range` → `index` → `ALL`

**Red flags**: `Using filesort` (needs index for ORDER BY), `Using temporary` (GROUP BY without index)

---

## Code Review Checklist

| Issue | Detection | Solution |
|-------|-----------|----------|
| N+1 Query | Multiple SELECTs per request in logs | JOIN FETCH, @EntityGraph, batch_fetch_size |
| Full Table Scan | EXPLAIN type = ALL | Add appropriate index |
| Large OFFSET | LIMIT x OFFSET large_number | Keyset pagination |
| SELECT * | Fetching unused columns | Select only needed columns / projection |
| Missing Index | Slow query log, EXPLAIN | Analyze query pattern, add index |
| OR on different columns | Each OR = separate scan | UNION or redesign |

---

## When to Apply

- 資料庫程式碼審查（index 設計、查詢模式）
- JPA/Hibernate 效能調校
- EXPLAIN plan 分析
- 補充 /optimize-query 的領域知識

## Gotchas

<!-- 持續更新：遇到新的 Claude 常犯錯誤時加入 -->

- **JOIN FETCH + Pageable 陷阱**：Spring Data 觸發 `HHH000104` 警告，Hibernate 先載入全表再記憶體分頁。改用子查詢取 ID 清單 + JOIN FETCH，或用 `@QueryHints` + `CountQuery`
- **EXPLAIN 的 rows 是估計值**：用 `EXPLAIN ANALYZE` 看真實執行數據，兩者差距可達 10 倍
- **batch_fetch_size 設太大**：`default_batch_fetch_size: 1000` 會產生巨大 `IN(...)` clause。`max_allowed_packet` 可能不足，建議 50-200
- **MySQL 8.0 CTE 不做 materialization**：`WITH` 每次引用都重新執行（不像 PostgreSQL）。需要多次引用時改用臨時表
- **@Transactional(readOnly=true) 不只是提示**：它啟用 Hibernate flush mode MANUAL，減少 dirty checking 開銷，對讀取量大的 API 有明顯效果
- **COUNT(*) vs COUNT(1) 效能完全相同**：MySQL optimizer 都走相同路徑，不要浪費時間爭論

## Additional Resources

- **references/index-design.md** — B+Tree internals, composite index strategies, covering index design
- **references/query-patterns.md** — Common patterns, anti-patterns, schema design tips
- **references/jpa-hibernate-tuning.md** — Cache, batch insert code, connection pool tuning details
