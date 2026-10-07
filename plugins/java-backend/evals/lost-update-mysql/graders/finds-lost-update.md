---
type: llm
---

PASS if the review identifies that two concurrent withdrawals can both read the same balance and one update is lost (a lost update / race on read-modify-write), and states that @Transactional or MySQL's REPEATABLE READ default does not prevent it, and proposes at least one concrete guard: an atomic conditional UPDATE (balance = balance - amount ... WHERE balance >= amount), a @Version column (optimistic locking), or a pessimistic lock (SELECT ... FOR UPDATE / PESSIMISTIC_WRITE).
FAIL if it says the code is safe because of @Transactional or REPEATABLE READ, or does not mention the concurrency problem at all.
