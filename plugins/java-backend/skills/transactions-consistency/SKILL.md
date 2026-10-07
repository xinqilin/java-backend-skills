---
name: transactions-consistency
description: Transactions, isolation anomalies (lost update, write skew, phantoms), and how MySQL InnoDB and PostgreSQL actually behave, with Spring Data JPA guards and retries; DDIA patterns (idempotency, outbox, replica lag). Use when code writes shared rows, or a design must stay consistent under concurrency.
user-invocable: false
allowed-tools: Read, Grep, Glob
---

# Transactions and Consistency

A transaction is not a concurrency guard by itself. Correctness depends on the isolation level actually in effect and on how the specific database implements it. MySQL InnoDB and PostgreSQL differ in ways that change which code is safe.

## Step 1: Establish the isolation level in effect

- Database default: **MySQL InnoDB = REPEATABLE READ**, **PostgreSQL = READ COMMITTED**
- Overrides: `@Transactional(isolation = ...)`, `spring.datasource.hikari.transaction-isolation`, server settings (`transaction_isolation` in MySQL, `default_transaction_isolation` in PostgreSQL)
- Without an explicit transaction, each statement commits on its own (autocommit), so a read and a later write are not even in the same transaction.

## Step 2: Find the anomaly each write path is exposed to

| Anomaly | Shape in application code | MySQL InnoDB, REPEATABLE READ (default) | PostgreSQL, READ COMMITTED (default) |
|---------|---------------------------|------------------------------------------|---------------------------------------|
| Lost update | Read a row, compute in Java, write the result back | **Possible.** `UPDATE` acts on the latest committed row version, not the snapshot the `SELECT` saw, and no error is raised | **Possible.** Same read-modify-write pattern; RC never aborts the second writer |
| Write skew | Check a condition over several rows, then write a different row | **Possible** with plain `SELECT` (snapshot reads take no locks) | **Possible** at RC and at REPEATABLE READ (snapshot isolation) |
| Phantom | A range check followed by an insert that would have matched it | Plain `SELECT` reads a snapshot; locking reads and DML lock the range (next-key locks) | Possible at RC; PostgreSQL's REPEATABLE READ prevents phantom reads |

PostgreSQL REPEATABLE READ *detects* the lost-update case: the second writer fails with `could not serialize access due to concurrent update` (SQLSTATE 40001), so the transaction must be retried. MySQL REPEATABLE READ has no such check. Details and timelines: `references/isolation-by-database.md`.

## Step 3: Pick the guard

Prefer the first one that fits:

1. **Atomic conditional update**: let the database do the read-modify-write in one statement and check the affected-row count.
   ```java
   @Modifying
   @Query("update Product p set p.stock = p.stock - :qty where p.id = :id and p.stock >= :qty")
   int decrementStock(@Param("id") long id, @Param("qty") int qty); // 0 rows = rejected
   ```
   Correct under both databases' defaults: InnoDB evaluates the `WHERE` against the latest committed row, and PostgreSQL READ COMMITTED re-evaluates it after a concurrent update commits. Run it inside a transaction: declared query methods get no transaction by default.
2. **Optimistic locking**: a `@Version` column; the losing writer gets `ObjectOptimisticLockingFailureException`. Best when conflicts are rare.
3. **Pessimistic locking**: `@Lock(LockModeType.PESSIMISTIC_WRITE)` issues `SELECT ... FOR UPDATE`. Keep the transaction short and lock rows in a consistent order to avoid deadlocks.
4. **Constraints**: a `UNIQUE` constraint for "at most one", a PostgreSQL `EXCLUDE USING gist` constraint for "no overlap". They also cover rows that don't exist yet, which row locks cannot.
5. **SERIALIZABLE + retry**: PostgreSQL's serializable isolation (SSI) prevents write skew in general, at the cost of retrying failed transactions. MySQL's SERIALIZABLE turns plain `SELECT`s into `SELECT ... FOR SHARE` inside transactions, which blocks and deadlocks instead.

Code for each guard, queue processing with `SKIP LOCKED`, and retry wiring: `references/guards-and-retries.md`.

## Step 4: Retry correctly

- Retry the **whole transaction**, never a statement inside it: each attempt must start a new transaction.
- Retryable failures: PostgreSQL 40001 (`serialization_failure`) and 40P01 (`deadlock_detected`); MySQL error 1213 `ER_LOCK_DEADLOCK` (SQLSTATE 40001). In Spring they surface as subclasses of `ConcurrencyFailureException`, the common parent of the optimistic and pessimistic locking failures.
- Spring Framework 7: `@Retryable(includes = ConcurrencyFailureException.class)` with `@EnableResilientMethods`, on a method **outside** the `@Transactional` boundary (for example a caller bean), so every attempt opens a new transaction.
- Make side effects idempotent: a retried transaction must not send a second email or publish a second event.

## Step 5: Keep transactions short

- No HTTP calls, message publishing, or file I/O inside a database transaction.
- Every open transaction holds a pooled connection, and row locks are held until commit.
- `REQUIRES_NEW` holds the outer connection while taking a second one; Spring's own docs warn that this can exhaust the pool and deadlock unless the pool exceeds the number of concurrent threads by at least one.

## Patterns for data across systems (DDIA)

Ideas from *Designing Data-Intensive Applications* (Kleppmann), applied to Spring:

- **Idempotency key**: store the client's key under a unique constraint in the same transaction as the effect.
- **Transactional outbox**: write the event row in the same transaction as the state change and relay it afterwards; never write to the database and a broker as two separate steps.
- **Replica lag**: reads routed to a replica can miss the user's own write (read-your-writes).
- **Hot keys**: a single counter row that every request updates serializes all of them.

Details: `references/distributed-data.md`.

## When to Apply

- Code that reads and then writes shared rows: balances, stock, quotas, counters, bookings, status transitions
- Choosing an isolation level, a lock, or a constraint
- Reviewing `@Transactional` boundaries, retries, or `REQUIRES_NEW`
- Designing idempotent APIs, event publishing, or read-replica routing

## Gotchas

<!-- Keep adding mistakes Claude repeatedly makes. -->

- **"REPEATABLE READ prevents lost updates" is false for MySQL**: InnoDB applies the `UPDATE` to the latest committed version and raises no error. Only PostgreSQL's REPEATABLE READ aborts the second writer.
- **`@Transactional` is not a lock**: two concurrent transactions running read-modify-write still lose an update under both databases' default isolation levels.
- **`synchronized` on a `@Transactional` method doesn't protect the data**: the proxy commits after the method returns and the monitor is released, so another thread can read the pre-commit state. It also does nothing across instances.
- **`@Version` conflicts surface at flush or commit**: often after the service method's last line. Handle `ObjectOptimisticLockingFailureException` where the transaction ends, not inside the method.
- **A row lock cannot protect a row that doesn't exist yet**: `FOR UPDATE` on an empty result locks nothing in PostgreSQL. Use a constraint, a lock on a parent row, or SERIALIZABLE.
- **`SKIP LOCKED` gives an inconsistent view by design**: use it for queue-like tables only, never for general reads.
- **`readOnly = true` is not a write firewall**: with JPA it sets flush mode `MANUAL`, marks the session read-only, and flags the JDBC connection read-only. Whether the database itself rejects writes depends on the driver and database.
- **PostgreSQL sequences are not transactional**: values consumed by rolled-back transactions are gone, so gaps in IDs are normal.

## Sources

See the Sources section at the end of each reference file.
