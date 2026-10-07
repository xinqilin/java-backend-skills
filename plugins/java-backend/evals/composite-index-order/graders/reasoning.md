---
type: llm
---

PASS if the recommended index puts the two equality columns (status and customer_id, in either order) before the range/sort column created_at, explains that the range column must come last so the equality prefix narrows the scan and the index can deliver ORDER BY created_at, and does not justify the column order solely by "most selective column first".
FAIL if created_at is not the last of those three columns, or the order is justified only by selectivity.
