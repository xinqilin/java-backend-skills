# Concurrency Guards and Retries in Spring Data JPA

Each guard below is shown the way it appears in a Spring Boot service. Choose the weakest one that removes the anomaly; stronger guards cost throughput.

## 1. Atomic conditional update

```java
public interface ProductRepository extends JpaRepository<Product, Long> {

    @Modifying
    @Query("update Product p set p.stock = p.stock - :qty where p.id = :id and p.stock >= :qty")
    int decrementStock(@Param("id") long id, @Param("qty") int qty);
}

@Service
class OrderService {
    @Transactional
    public void reserve(long productId, int qty) {
        if (productRepository.decrementStock(productId, qty) == 0) {
            throw new OutOfStockException(productId);
        }
        // ... insert the order line in the same transaction
    }
}
```

- The database re-checks `stock >= :qty` against the latest committed row: InnoDB because `UPDATE` reads the current version, PostgreSQL READ COMMITTED because it re-evaluates the `WHERE` clause after a concurrent writer commits.
- Under PostgreSQL REPEATABLE READ or SERIALIZABLE, the same statement can fail with 40001 and must be retried.
- Declared query methods get no transaction by default: call them inside a `@Transactional` method, or annotate the repository method.
- A bulk JPQL update bypasses the persistence context. A `Product` already loaded in this transaction keeps its old `stock`; use `@Modifying(clearAutomatically = true)` or don't load it first.

## 2. Optimistic locking

```java
@Entity
class Account {
    @Id Long id;
    @Version Long version; // a non-primitive version also tells Spring Data whether the entity is new
    BigDecimal balance;
}
```

- Hibernate adds `where id = ? and version = ?` to the `UPDATE`; when another transaction got there first, the losing writer fails and Spring throws `ObjectOptimisticLockingFailureException`, a subclass of `OptimisticLockingFailureException`.
- The failure happens at flush or commit, which is usually after the last line of the service method. Catch it at the caller, or retry there.
- Good when conflicts are rare. Under heavy contention on one row, most attempts fail and retry; prefer an atomic update or a lock.

## 3. Pessimistic locking

```java
public interface AccountRepository extends JpaRepository<Account, Long> {
    @Lock(LockModeType.PESSIMISTIC_WRITE)            // SELECT ... FOR UPDATE
    @Query("select a from Account a where a.id = :id")
    Optional<Account> findForUpdate(@Param("id") long id);
}
```

- The lock is held until the transaction ends, so keep that transaction short and free of remote calls.
- When a transaction locks several rows, always lock them in the same order (for example by ascending id). Inconsistent order is the classic deadlock.
- Waiting differs by database. MySQL waits up to `innodb_lock_wait_timeout` (default 50 s) and then fails with error 1205. PostgreSQL waits indefinitely by default (`lock_timeout = 0`) unless a lock timeout is set. Decide on a timeout explicitly.
- In PostgreSQL, `FOR UPDATE` locks only rows that exist. In MySQL REPEATABLE READ, a locking read with a range condition also locks the gaps in the scanned index range, which blocks inserts there.

## 4. Queue processing with SKIP LOCKED

```java
@Query(value = """
        select * from job
        where status = 'PENDING'
        order by id
        limit :batch
        for update skip locked
        """, nativeQuery = true)
List<Job> claimBatch(@Param("batch") int batch);
```

- Supported by MySQL 8 and PostgreSQL. Concurrent workers each claim different rows instead of blocking on each other.
- The MySQL manual warns that skipping locked rows returns an inconsistent view of the data and is meant for queue-like tables, not general transactional reads.
- `NOWAIT` instead fails immediately when a row is locked.

## 5. Constraints

```sql
-- At most one active subscription per user (PostgreSQL partial unique index)
CREATE UNIQUE INDEX uq_active_subscription ON subscription (user_id) WHERE status = 'ACTIVE';

-- No overlapping reservations for the same room (PostgreSQL)
CREATE EXTENSION btree_gist;
CREATE TABLE room_reservation (
    room   text,
    during tsrange,
    EXCLUDE USING GIST (room WITH =, during WITH &&)
);
```

- A constraint protects against rows that don't exist yet, which row locks cannot.
- Violations surface as `DataIntegrityViolationException` in Spring. PostgreSQL reports them as 23505 (`unique_violation`) or 23P01 (`exclusion_violation`).
- MySQL has no partial or exclusion constraints. Common substitutes are a generated column that is `NULL` for inactive rows plus a unique index on it, or a locking read on a parent row that represents the resource.

## 6. SERIALIZABLE with retry (PostgreSQL)

```java
@Transactional(isolation = Isolation.SERIALIZABLE)
public void goOffCall(long doctorId, long shiftId) { ... }
```

- PostgreSQL's serializable snapshot isolation aborts one of two conflicting transactions with 40001; nothing else in the code has to change.
- Every caller must be ready to retry. Keep these transactions short, since longer ones conflict more.

## Retry wiring

Retry the whole transaction: the retry must sit **outside** the transactional proxy, so each attempt opens a new transaction.

```java
@Configuration
@EnableResilientMethods // Spring Framework 7: enables @Retryable and @ConcurrencyLimit
class ResilienceConfig { }

@Service
class TransferFacade {
    private final TransferService transferService; // the @Transactional bean

    @Retryable(includes = ConcurrencyFailureException.class, maxRetries = 3)
    public void transfer(TransferCommand cmd) {
        transferService.transfer(cmd); // new transaction per attempt
    }
}
```

- `ConcurrencyFailureException` is the common parent of `OptimisticLockingFailureException` and `PessimisticLockingFailureException` in Spring's data access hierarchy. Confirm with an integration test which subclass your driver and dialect raise for 40001, 40P01, and 1213.
- By default, `@Retryable` retries any exception up to 3 times with a 1-second delay; narrow it with `includes`.
- On Spring Boot 3.x (Framework 6) there is no core `@Retryable`; use Spring Retry (Boot 4 no longer manages its version) or a hand-written loop.
- Never retry a transaction that already triggered non-idempotent side effects outside the database.

## Sources

- Spring Data JPA, Transactionality: https://docs.spring.io/spring-data/jpa/reference/jpa/transactions.html
- Spring Data JPA, Modifying queries (`clearAutomatically`): https://docs.spring.io/spring-data/jpa/reference/jpa/query-methods.html
- Spring Data JPA, Locking: https://docs.spring.io/spring-data/jpa/reference/jpa/locking.html
- Spring Framework 7, Resilience features (`@Retryable`, `@EnableResilientMethods`): https://docs.spring.io/spring-framework/reference/core/resilience.html
- Spring Framework Javadoc, `org.springframework.dao` exception hierarchy: https://docs.spring.io/spring-framework/docs/current/javadoc-api/org/springframework/dao/package-summary.html
- MySQL 8.4, Locking Reads (`NOWAIT`, `SKIP LOCKED`): https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html
- MySQL 8.4, Transaction Isolation Levels (gap and next-key locks): https://dev.mysql.com/doc/refman/8.4/en/innodb-transaction-isolation-levels.html
- PostgreSQL 18, Client Connection Defaults (`lock_timeout`): https://www.postgresql.org/docs/current/runtime-config-client.html
- PostgreSQL 18, Range Types, constraints on ranges (`btree_gist` example): https://www.postgresql.org/docs/current/rangetypes.html
- PostgreSQL 18, Serialization Failure Handling: https://www.postgresql.org/docs/current/mvcc-serialization-failure-handling.html
