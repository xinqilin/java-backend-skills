---
name: effective-java
description: Core Java rules where they meet the database and Spring, in the spirit of Effective Java - value objects and BigDecimal equality, entity construction, collections, exception translation, streams over query results, and concurrency around transactions. Use when reviewing or writing Java code in a Spring Boot + JPA service.
user-invocable: false
allowed-tools: Read, Grep, Glob
---

# Effective Java for Spring Boot + JPA

Rules from *Effective Java* (3rd ed., item numbers in parentheses), restated for code that reads and writes a database. Language advice without a persistence or concurrency consequence is left to the book.

## Value objects and equality (Items 10, 11, 17)

`BigDecimal.equals` compares the scale as well as the value: `2.0` and `2.00` are not equal, and their hash codes differ. A `DECIMAL(19,2)` column reads back with scale 2, so a record that holds a raw `BigDecimal` is not equal to the same amount built in code, and it misbehaves as a map key or in a `Set`. Fix the scale in the compact constructor, so the generated `equals` and `hashCode` agree with numeric equality:

```java
@Embeddable
public record Money(@Column(precision = 19, scale = 2) BigDecimal amount, Currency currency) {
    public Money {
        Objects.requireNonNull(amount, "amount");
        Objects.requireNonNull(currency, "currency");
        // UNNECESSARY rejects 10.005 TWD instead of rounding it silently
        amount = amount.setScale(currency.getDefaultFractionDigits(), RoundingMode.UNNECESSARY);
    }
}
```

- Hibernate (6.2+) builds embeddable records through the canonical constructor, so values loaded from the database are normalized too.
- A hand-written `equals` based on `compareTo` needs a `hashCode` that ignores the scale (`amount.stripTrailingZeros().hashCode()`), never `Objects.hash(amount, ...)`.
- Arithmetic that produces extra digits (tax, discounts, splits) takes an explicit `RoundingMode` from the caller.
- Entities are not value objects: for entity `equals`/`hashCode`, follow `java-backend:jpa-hibernate`.

## Constructing entities (Items 1, 2, 15)

- JPA requires a public or protected no-arg constructor. Make it `protected`, so application code can't create a half-initialized entity.
- Create new aggregates through a static factory that takes the required arguments, assigns the id and initial state, and checks invariants (`Account.open(ownerId, currency)`).
- Change state through behavior methods (`account.withdraw(amount)`), not a setter per column. With field access (`@Id` on a field), Hibernate needs no setters.
- A builder fits commands and search criteria with many optional fields. On an entity, it lets callers skip required fields unless `build()` validates.

## Collections (Items 17, 50)

- `List.of` and `List.copyOf` reject `null` elements, which nullable columns produce. `Stream.toList()` accepts them and returns an unmodifiable copy.
- `Collections.unmodifiableList` is a view: later changes to the backing list show through.
- In an entity, return an unmodifiable view of a mapped collection and change it through the aggregate's methods. Never replace it with a copy (see Gotchas).

## Exceptions (Items 73, 76)

- Spring Data repositories throw `DataAccessException` subclasses. Translate them where the use case knows what they mean, for example a unique-key `DataIntegrityViolationException` into `AlreadyRedeemedException`, and keep the cause.
- Translate **outside** the transactional method. A constraint violation surfaces at flush, often at commit. A repository call that throws inside your transaction has already marked it rollback-only, so catching and continuing ends in `UnexpectedRollbackException`.
- Match the specific violation and rethrow the rest: a foreign-key failure is not a duplicate.

```java
public UUID redeem(UUID campaignId, UUID userId) {     // not @Transactional
    try {
        return redemptions.redeem(campaignId, userId); // @Transactional: commits before returning
    } catch (DataIntegrityViolationException e) {
        if (isUniqueViolation(e)) {
            throw new AlreadyRedeemedException(campaignId, userId, e);
        }
        throw e;
    }
}

private static boolean isUniqueViolation(Throwable e) { // getKind() needs Hibernate 6.5+
    for (Throwable t = e; t != null; t = t.getCause()) {
        if (t instanceof ConstraintViolationException violation) { // org.hibernate.exception
            return violation.getKind() == ConstraintKind.UNIQUE;
        }
    }
    return false;
}
```

- A rollback doesn't restore the in-memory state of entities, so a retry runs a new transaction that reloads them. A checked exception commits by default (`java-backend:jpa-hibernate`).

## Streams over query results (Items 45-48)

- No repository calls inside `map` or `forEach`: that is N+1 in stream form. Load in bulk (`findAllById`), then join in memory.
- `Collectors.toMap` throws `IllegalStateException` on a duplicate key and `NullPointerException` on a null value. Rows from a join and nullable columns produce both. Pass a merge function, or fill a `HashMap` in a loop.
- A repository method that returns `Stream<T>` needs a surrounding transaction and must be closed. Rows only stream from the database when the driver is set up for it.
- `parallelStream()` runs part of the work on `ForkJoinPool.commonPool()` threads, which have no transaction or persistence context. Never touch repositories, an `EntityManager`, or lazy associations inside it.

## Concurrency (Items 78-84)

- A `@Service` is a singleton shared by every request thread, so a mutable instance field is a data race. Keep services stateless.
- Transactions and persistence contexts are bound to the thread. Work handed to `@Async`, `CompletableFuture`, or an executor runs outside the caller's transaction. It doesn't roll back with the caller, and a managed entity passed to it is unsafe. Pass ids, and let the task open its own transaction.
- Work started inside a transaction can run before the commit and miss its writes. Start it after commit with `@TransactionalEventListener`, or use an outbox when it must not be lost (`java-backend:transactions-consistency`).
- Use Spring-managed executors with bounded queues. Avoid `Executors.newCachedThreadPool()`, and don't call `supplyAsync` without an executor (it falls back to the common pool). Every task that touches the database also holds a pooled connection.
- JVM locks guard one instance only. On a `@Transactional` method they are released before the commit. Guard shared data in the database (`java-backend:transactions-consistency`).
- Virtual threads: see `java-backend:spring-boot-baseline` and `java-backend:sql-performance`.

## Code Review Checklist

| Check | Good | Bad |
|-------|------|-----|
| Money and quantities | Record with a fixed `BigDecimal` scale | `equals` on raw `BigDecimal`; `hashCode` that disagrees with `equals` |
| Entities | `protected` no-arg constructor, factory, behavior methods | A public setter per column; a `final` class or a record as `@Entity` |
| Collections | Unmodifiable view of a mapped collection; `List.copyOf` for snapshots | Exposing or replacing a mapped collection |
| Exceptions | Translated where the transaction ends, cause kept | Catch-and-continue inside the transaction; every `DataIntegrityViolationException` treated as a duplicate |
| Streams | Bulk load, then map; `toMap` with a merge function | A repository call per element; `parallelStream()` touching entities |
| Concurrency | Stateless singletons; ids across threads; bounded executors | Mutable fields in a `@Service`; entities passed to `@Async`; `synchronized` as a data guard |
| Optional (Item 55) | Return type of finders | Fields and parameters; `get()` without a check |
| Inheritance (Item 18) | Composition, for example a decorator around an interface | Extending a concrete class you don't own to override one method |

## When to Apply

- Reviewing or writing value objects, entities, or exception handling around repositories
- Streams and collectors over query results
- `@Async`, executors, `CompletableFuture`, caches, or other shared state in Spring beans

## Gotchas

<!-- Keep adding mistakes Claude repeatedly makes. -->

- **A record is not an entity**: don't turn a JPA `@Entity` into a record. Records are final and immutable with no no-arg constructor, so Hibernate cannot proxy or populate them. Use records for DTOs, projections, and embeddable values.
- **`BigDecimal` equality includes the scale**: `new BigDecimal("2.0").equals(new BigDecimal("2.00"))` is `false`. Compare amounts with `compareTo`, or normalize the scale.
- **Replacing a mapped collection breaks orphan removal**: assigning a new list to a loaded entity with `orphanRemoval = true` fails at flush with "A collection with orphan deletion was no longer referenced by the owning entity instance". Change the existing collection.
- **`Stream.toList()` returns an unmodifiable list**: unlike the result of `collect(Collectors.toList())`, which callers often mutate, any mutator throws `UnsupportedOperationException`. It is a copy, so later changes to the source don't leak in, but the copy is shallow: the elements themselves can still change.
- **`Collections.unmodifiableList()` is a view**: changes to the wrapped list still show through. Use `List.copyOf()` for a real snapshot.
- **Record validation can't be bypassed**: every record constructor must end up in the canonical one, so checks in a compact constructor also run for builders, including Lombok's `@Builder`.
- **Don't add `default` to an exhaustive switch over a sealed type**: without it, adding a new permitted subtype breaks compilation at every switch that doesn't handle it. That is the intended safety net.
- **A singleton's mutable field is shared by all requests**: a "running total" or "current user" field in a `@Service` mixes data across concurrent requests.
- **The common double-checked locking bug**: returning the local variable read before the lock returns `null` when another thread initializes the field in between. Return the field read inside the lock.
- **`@Async` and `CompletableFuture` leave the transaction**: the task neither sees the caller's uncommitted writes nor rolls back with it.

## Additional Resources

- **references/value-objects-and-creation.md**: the full `Money`, entity construction, builders, and JDBC resources inside a transaction
- **references/streams.md**: collectors over rows, repository streams and driver fetch sizes, parallel streams
- **references/concurrency.md**: shared state in beans, thread-bound transactions, after-commit work, executors, caches, lazy initialization
