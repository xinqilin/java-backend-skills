# Isolation Behavior: MySQL InnoDB vs PostgreSQL

The SQL standard defines isolation levels by the anomalies they forbid; each database implements them differently. This file records the behavior that matters for application code. Every statement here is backed by the vendor documentation listed under Sources.

## Defaults

| | MySQL InnoDB | PostgreSQL |
|---|---|---|
| Default level | REPEATABLE READ | READ COMMITTED |
| Plain `SELECT` | Consistent (nonlocking) read: within a transaction, every plain `SELECT` reads the snapshot established by the first read | READ COMMITTED: each statement sees a snapshot as of the moment it starts, so two `SELECT`s in one transaction can disagree |
| `UPDATE` / `DELETE` / `SELECT ... FOR UPDATE` | Lock and act on the latest committed row version. The snapshot applies to `SELECT`, "not necessarily to DML statements" | READ COMMITTED: wait for a concurrent writer, then re-evaluate the `WHERE` clause against the updated row version and continue |

## Lost update

The application reads a value, computes a new one in Java, and writes it back.

```java
@Transactional
public void withdraw(long accountId, BigDecimal amount) {
    Account a = accountRepository.findById(accountId).orElseThrow(); // plain SELECT
    a.setBalance(a.getBalance().subtract(amount));                   // computed in Java
}                                                                    // UPDATE at flush/commit
```

Timeline with two concurrent withdrawals of 10 from a balance of 100:

| Step | Transaction A | Transaction B |
|------|---------------|---------------|
| 1 | reads balance = 100 | |
| 2 | | reads balance = 100 |
| 3 | writes 90, commits | |
| 4 | | writes 90 |

- **MySQL, REPEATABLE READ**: step 4 succeeds. The `UPDATE` applies to the latest committed row, and InnoDB raises no error. The final balance is 90, so A's withdrawal is lost.
- **PostgreSQL, READ COMMITTED**: step 4 succeeds the same way, and A's withdrawal is lost.
- **PostgreSQL, REPEATABLE READ**: step 4 fails with `ERROR: could not serialize access due to concurrent update` (SQLSTATE 40001), because a repeatable-read transaction cannot modify a row that another transaction changed after it began. The application must retry the whole transaction, and the retry sees 90.

The MySQL manual itself advises against mixing locking statements (`UPDATE`, `INSERT`, `DELETE`, `SELECT ... FOR ...`) with nonlocking `SELECT`s in one REPEATABLE READ transaction. That mix is exactly the "load the entity, change it, let Hibernate flush" shape of most JPA service methods.

Fixes, in order of preference: an atomic `UPDATE ... SET balance = balance - :amount WHERE id = :id AND balance >= :amount`; a `@Version` column; `SELECT ... FOR UPDATE` before the read; PostgreSQL REPEATABLE READ or SERIALIZABLE with a retry loop.

## Write skew

Each transaction checks a condition over a set of rows, then writes a *different* row, so neither sees the other's write.

Example: at least one doctor must stay on call. Two doctors go off call at the same time.

```sql
-- both transactions, concurrently
SELECT count(*) FROM doctor WHERE shift_id = 7 AND on_call = true;  -- each sees 2
UPDATE doctor SET on_call = false WHERE id = :me AND shift_id = 7;  -- each updates its own row
COMMIT;                                                              -- result: 0 on call
```

- **MySQL, REPEATABLE READ**: allowed. Plain `SELECT`s take no locks. Making the check a locking read (`SELECT ... FOR UPDATE` on the rows checked) makes the second transaction wait.
- **MySQL, SERIALIZABLE**: InnoDB turns plain `SELECT`s into `SELECT ... FOR SHARE` when autocommit is off. Both transactions then hold shared locks and block each other's updates, so expect deadlocks; one is rolled back with error 1213.
- **PostgreSQL, READ COMMITTED and REPEATABLE READ**: allowed. REPEATABLE READ is snapshot isolation, and snapshot isolation permits write skew.
- **PostgreSQL, SERIALIZABLE**: prevented. Serializable snapshot isolation detects the read/write dependency and aborts one transaction with `could not serialize access due to read/write dependencies among transactions` (40001).

When the conflicting rows may not exist yet (double booking: "no reservation overlaps this one"), a row lock has nothing to lock in PostgreSQL. Use a constraint: an exclusion constraint for overlaps, a unique constraint for "at most one", or SERIALIZABLE.

## Phantoms

- **MySQL InnoDB**: for locking reads, `UPDATE`, and `DELETE` with a range condition at REPEATABLE READ, InnoDB locks the scanned index range with gap and next-key locks, which block concurrent inserts into that range. At READ COMMITTED, gap locking is disabled for searches and index scans.
- **PostgreSQL**: the documentation states that its REPEATABLE READ implementation does not allow phantom reads, which is stricter than the SQL standard requires.

## Errors to retry

| Database | Condition | Code |
|----------|-----------|------|
| PostgreSQL | Serialization failure (REPEATABLE READ or SERIALIZABLE) | SQLSTATE 40001 `serialization_failure` |
| PostgreSQL | Deadlock | SQLSTATE 40P01 `deadlock_detected` |
| PostgreSQL | Unique or exclusion violation, when the transaction picked a conflicting value after reading | 23505 `unique_violation`, 23P01 `exclusion_violation` |
| MySQL | Deadlock (InnoDB rolls the transaction back) | Error 1213 `ER_LOCK_DEADLOCK`, SQLSTATE 40001 |
| MySQL | Lock wait timeout (`innodb_lock_wait_timeout`, default 50 s) | Error 1205 |

PostgreSQL's documentation also advises treating data read inside a SERIALIZABLE transaction as valid only after that transaction commits.

## Sources

- MySQL 8.4 Reference Manual, Transaction Isolation Levels: https://dev.mysql.com/doc/refman/8.4/en/innodb-transaction-isolation-levels.html
- MySQL 8.4, Consistent Nonlocking Reads: https://dev.mysql.com/doc/refman/8.4/en/innodb-consistent-read.html
- MySQL 8.4, InnoDB Startup Options and System Variables (`innodb_lock_wait_timeout`): https://dev.mysql.com/doc/refman/8.4/en/innodb-parameters.html
- MySQL 8.4 Server Error Reference: https://dev.mysql.com/doc/mysql-errors/8.4/en/server-error-reference.html
- PostgreSQL 18, Transaction Isolation: https://www.postgresql.org/docs/current/transaction-iso.html
- PostgreSQL 18, Serialization Failure Handling: https://www.postgresql.org/docs/current/mvcc-serialization-failure-handling.html
- Kleppmann, *Designing Data-Intensive Applications* (1st ed.), ch. 7 "Transactions" (weak isolation levels, lost updates, write skew and phantoms)
