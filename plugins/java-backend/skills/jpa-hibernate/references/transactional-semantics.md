# @Transactional Semantics That Cause Production Bugs

## Only proxied calls are transactional

In proxy mode (the default), only external calls coming in through the Spring proxy are intercepted.

```java
@Service
class OrderService {
    public void placeAll(List<Order> orders) {
        orders.forEach(this::place);        // self-invocation: no transaction per order
    }

    @Transactional
    public void place(Order order) { ... }
}
```

- Fix: move `place` to another bean, call it through an injected self-proxy, or use `TransactionTemplate` for the inner unit.
- Don't rely on transactions in initialization code such as `@PostConstruct`: the proxy may not be fully initialized yet.
- Visibility: since Spring Framework 6.0, protected and package-visible methods can be transactional with class-based proxies (the Spring Boot default). With interface-based proxies, transactional methods must be public and declared in the interface.

## Rollback rules

- By default, Spring rolls back only on `RuntimeException` and `Error`.
- A **checked exception commits** everything flushed so far:

```java
@Transactional                                   // commits on IOException
public void importFile(Path file) throws IOException { ... }

@Transactional(rollbackFor = Exception.class)    // rolls back on checked exceptions too
public void importFile(Path file) throws IOException { ... }
```

- Catching an exception inside the transactional method and continuing doesn't undo a rollback-only mark set by an inner `REQUIRED` participant: the outer commit then fails with `UnexpectedRollbackException`.

## Propagation

| Propagation | Physical transactions | Typical trap |
|-------------|-----------------------|--------------|
| `REQUIRED` (default) | Joins the caller's transaction | An inner failure marks the whole transaction rollback-only |
| `REQUIRES_NEW` | Suspends the caller's transaction and starts an independent one, on a second connection | Holds two pooled connections per request |
| `NESTED` | One physical transaction with savepoints | `JpaTransactionManager` disables it by default (`nestedTransactionAllowed = false`): savepoints roll back the JDBC connection, not the `EntityManager`'s cached entities |

The Spring reference documentation warns about `REQUIRES_NEW`: the outer transaction's connection stays bound while the inner one acquires another. Several threads in that state can exhaust the pool and deadlock waiting for connections. Only use it when the pool exceeds the number of concurrent threads by at least one. Typical legitimate use: an audit record that must survive the business transaction's rollback.

## readOnly

See `persistence-context.md`. In short: flush mode `MANUAL`, read-only session, and `Connection.setReadOnly(true)`. It does not guarantee that the database rejects writes.

## Keep transactions short

- Load, decide, write, commit. Do HTTP calls, message publishing, and file I/O before the transaction starts or after it commits.
- Every open transaction holds a pooled connection, plus row locks taken by writes or locking reads until commit.
- Publish follow-up work after commit with `@TransactionalEventListener` (default phase `AFTER_COMMIT`); for events other systems depend on, use an outbox (`java-backend:transactions-consistency`).

## Programmatic transactions

```java
private final TransactionTemplate tx;

public void reprocess(List<Long> ids) {
    for (Long id : ids) {
        tx.executeWithoutResult(status -> reprocessOne(id)); // one transaction per item
    }
}
```

Use `TransactionTemplate` when one method needs several separate transactions, or when the boundary depends on runtime conditions.

## Sources

- Spring Framework reference, Using `@Transactional` (proxy mode, self-invocation, method visibility, initialization code): https://docs.spring.io/spring-framework/reference/data-access/transaction/declarative/annotations.html
- Spring Framework reference, Rolling Back a Declarative Transaction: https://docs.spring.io/spring-framework/reference/data-access/transaction/declarative/rolling-back.html
- Spring Framework reference, Transaction Propagation (`REQUIRES_NEW` pool exhaustion, `NESTED` savepoints, `UnexpectedRollbackException`): https://docs.spring.io/spring-framework/reference/data-access/transaction/declarative/tx-propagation.html
- Spring Framework Javadoc, `TransactionalEventListener`: https://docs.spring.io/spring-framework/docs/current/javadoc-api/org/springframework/transaction/event/TransactionalEventListener.html
- Spring Framework Javadoc, `JpaTransactionManager` (nested transactions via savepoints): https://docs.spring.io/spring-framework/docs/current/javadoc-api/org/springframework/orm/jpa/JpaTransactionManager.html
