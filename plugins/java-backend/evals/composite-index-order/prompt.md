---
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Agent]
tags: [sql, index]
---

This query runs very often on a 40M-row table and is slow. Stack: MySQL 8.4, Spring Boot 4.1.

```sql
SELECT id, total, created_at
FROM orders
WHERE status = ? AND customer_id = ? AND created_at >= ?
ORDER BY created_at
LIMIT 50;
```

Existing index: `idx_orders_created_customer (created_at, customer_id)`. EXPLAIN shows `type: range` on that index with about 2,000,000 rows examined. Which index should we create? Give the exact CREATE INDEX statement.
