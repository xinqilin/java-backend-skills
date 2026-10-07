# Consistency Beyond One Transaction (DDIA patterns in Spring)

Ideas from *Designing Data-Intensive Applications* (Kleppmann, 1st ed.), explained in our own words and mapped to Spring Boot with MySQL or PostgreSQL. Chapter pointers are given for further reading.

## Idempotency keys (ch. 11 "Stream Processing", ch. 12 "The Future of Data Systems")

Networks retry, and clients retry on timeouts, so the same request can arrive twice. Make the effect happen at most once by recording the request's key in the **same transaction** as the effect:

```sql
CREATE TABLE idempotency_key (
    idem_key     varchar(64) PRIMARY KEY,
    request_hash varchar(64) NOT NULL,   -- reject the same key reused with a different payload
    response     text,
    created_at   timestamp   NOT NULL
);
```

```java
@Transactional
public PaymentResult pay(String idemKey, PaymentCommand cmd) {
    Optional<IdempotencyKey> seen = idempotencyRepository.findById(idemKey);
    if (seen.isPresent()) {
        return seen.get().replay(cmd); // same response; error if the payload hash differs
    }
    PaymentResult result = doPay(cmd);                              // the state change
    idempotencyRepository.save(IdempotencyKey.of(idemKey, cmd, result)); // same transaction
    return result;
}
```

- Two concurrent duplicates both pass the `findById` check. The primary key makes one of them fail at insert or commit instead of applying the effect twice; translate that failure into "replay the stored response".
- `IdempotencyKey` has an application-assigned id, so Spring Data's `save()` treats it as existing and calls `merge`, which issues an extra `SELECT`. Implement `Persistable` so `save()` persists it directly (see `java-backend:jpa-hibernate`).
- Expire old keys with a scheduled delete, outside the hot path.

## Transactional outbox (ch. 11)

Writing to the database and then publishing to a broker is a dual write, and either step can fail on its own:

- Commit succeeds but the publish fails (or the process dies): the event is lost.
- Publish succeeds but the transaction rolls back: consumers act on something that never happened.

Instead, insert the event as a row in the same transaction as the state change, and let a separate relay publish it:

```java
@Transactional
public void placeOrder(PlaceOrder cmd) {
    Order order = orderRepository.save(Order.from(cmd));
    outboxRepository.save(OutboxEvent.of("order", order.getId(), "OrderPlaced", payload(order)));
}
```

- The relay either polls (`select ... order by id limit 100 for update skip locked`, publish, then mark as sent) or uses change data capture on the outbox table.
- Delivery is at least once: the relay can publish and then crash before marking the row. Consumers must deduplicate by event id.
- `@TransactionalEventListener` runs after commit by default, but in the same process and without persistence. If the process dies between commit and publish, the event is gone. It does not replace an outbox for events other systems depend on.

## Sagas instead of distributed transactions (ch. 9 "Consistency and Consensus")

Two-phase commit across services couples their availability: a coordinator failure leaves participants holding locks. A saga runs a sequence of local transactions, each with a compensating action:

- There is no isolation between steps: other requests can see intermediate states. Model them explicitly (`PENDING`, `RESERVED`) instead of pretending they don't exist.
- Compensations are new business operations (refund, release), not rollbacks, and must themselves be idempotent and retryable.
- Drive the steps from the outbox, so a step is never lost between the database and the broker.

## Replica lag (ch. 5 "Replication")

With asynchronous replicas, a read routed to a replica can return data older than what the same user just wrote.

- **Read-your-writes**: after a user writes, serve that user's reads from the primary for a while, or for everything the user can edit.
- **Monotonic reads**: a user hopping between replicas can see time go backwards; pin a session to one replica.
- **Routing in Spring**: since Spring Framework 6.1.2, `LazyConnectionDataSourceProxy` can use a separate read-only `DataSource` during read-only transactions (`setReadOnlyDataSource`). Because the connection is fetched lazily, the transaction's read-only flag is known when the routing decision is made.
- Never route a read that feeds a write decision (stock check, balance check) to a replica.

## Hot keys and partitioning (ch. 6 "Partitioning")

- A single row updated by every request (a global counter, a campaign's remaining stock) serializes those requests on its row lock. Measure before splitting it.
- Mitigations: keep the transaction that touches the hot row tiny; split the counter into N rows and sum on read; or pre-create claimable rows (coupon codes) and claim them with `FOR UPDATE SKIP LOCKED`.
- Monotonically increasing keys concentrate inserts at one end of a B-tree index or range partition. With InnoDB, the clustered primary key makes this the table's insertion point, which is usually fine on one node but becomes a hot spot under range partitioning.

## Sources

- Kleppmann, *Designing Data-Intensive Applications* (1st ed.): ch. 5 "Replication", ch. 6 "Partitioning", ch. 7 "Transactions", ch. 9 "Consistency and Consensus", ch. 11 "Stream Processing", ch. 12 "The Future of Data Systems"
- Spring Framework Javadoc, `TransactionalEventListener` (default phase `AFTER_COMMIT`): https://docs.spring.io/spring-framework/docs/current/javadoc-api/org/springframework/transaction/event/TransactionalEventListener.html
- Spring Framework Javadoc, `LazyConnectionDataSourceProxy` (read-only DataSource since 6.1.2): https://docs.spring.io/spring-framework/docs/current/javadoc-api/org/springframework/jdbc/datasource/LazyConnectionDataSourceProxy.html
- MySQL 8.4, Locking Reads (`SKIP LOCKED`): https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html
- MySQL 8.4, Clustered and Secondary Indexes: https://dev.mysql.com/doc/refman/8.4/en/innodb-index-types.html
