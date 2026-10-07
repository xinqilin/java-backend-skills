---
type: llm
---

PASS if the answer explains that both transactions can see two doctors on call, each update its own (different) row, and both commit, leaving zero doctors on call (write skew), and that PostgreSQL's REPEATABLE READ (snapshot isolation) does not prevent this, and proposes a working fix such as SERIALIZABLE isolation with retry on serialization failures, locking the rows that were read or a parent row (SELECT ... FOR UPDATE), or a database constraint/materialized conflict.
FAIL if it claims REPEATABLE READ prevents the problem, or only suggests application-level synchronization (synchronized / locks in Java) as the fix.
