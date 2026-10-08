---
name: effective-java
description: Core Java rules where they meet the database and Spring (Effective Java) - BigDecimal equality, entity construction, exception translation, streams over query results, and concurrency around transactions. Use when reviewing or writing Java in a Spring Boot + JPA service.
user-invocable: false
allowed-tools: Read, Grep, Glob
---

# Effective Java for Spring Boot + JPA

Rules from *Effective Java* (3rd ed., item numbers in parentheses), restated for code that reads and writes a database.

## Value objects (Items 10, 11, 17)

- `BigDecimal.equals` compares the scale: `2.0` and `2.00` are not equal, and their hash codes differ. A `DECIMAL(19,2)` column reads back with scale 2, so a record holding a raw `BigDecimal` is not equal to the same amount built in code.
- Fix the scale in the compact constructor: `amount = amount.setScale(currency.getDefaultFractionDigits(), RoundingMode.UNNECESSARY)`. `UNNECESSARY` rejects 10.005 TWD instead of rounding it. Hibernate 6.2+ builds embeddable records through the canonical constructor, so loaded values are normalized too.
- A hand-written `equals` based on `compareTo` needs a `hashCode` over `amount.stripTrailingZeros()`, never `Objects.hash(amount, ...)`.
- Arithmetic that adds digits (tax, discounts, splits) takes a `RoundingMode` from the caller. For entity equality, see `java-backend:jpa-hibernate`.

## Entities (Items 1, 2, 15)

- Give entities a `protected` no-arg constructor (JPA requires public or protected), a static factory with the required arguments (`Account.open(ownerId, currency)`), and behavior methods instead of a setter per column. Field access needs no setters.
- A builder fits commands and search criteria. On an entity, it lets callers skip required fields.

## Collections (Items 17, 50)

- `List.of` and `List.copyOf` reject `null` elements, which nullable columns produce. `Stream.toList()` accepts them and returns an unmodifiable copy. `Collections.unmodifiableList` is a view.
- Return an unmodifiable view of a mapped collection, and change it through the aggregate. Never replace it (see Gotchas).

## Exceptions (Items 73, 76)

- Translate a `DataAccessException` where the use case knows what it means, for example a unique-key `DataIntegrityViolationException` into `AlreadyRedeemedException`. Keep the cause, and rethrow other violations: a foreign-key failure is not a duplicate.
- Translate **outside** the transactional method. Violations surface at flush, often at commit, and a repository call that throws inside your transaction has already marked it rollback-only, so the commit fails with `UnexpectedRollbackException`.
- A rollback doesn't restore entities in memory, so a retry reloads them in a new transaction. A checked exception commits by default (`java-backend:jpa-hibernate`).

## Streams over query results (Items 45-48)

- No repository calls inside `map` or `forEach`: that is N+1 in stream form. Load in bulk, then join in memory.
- `Collectors.toMap` throws `IllegalStateException` on a duplicate key and `NullPointerException` on a null value. Rows from joins and nullable columns produce both.
- A repository method that returns `Stream<T>` needs a surrounding transaction and must be closed. Rows only stream when the driver is configured for it.
- `parallelStream()` runs part of the work on `ForkJoinPool.commonPool()`, which has no transaction or persistence context. Never touch repositories, an `EntityManager`, or lazy associations there.

## Concurrency (Items 78-84)

- A `@Service` is a singleton shared by all request threads, so a mutable field is a data race.
- Transactions and persistence contexts are bound to the thread. `@Async`, `CompletableFuture`, and executors run outside the caller's transaction: they don't see its uncommitted writes or roll back with it. Pass ids, not managed entities, and open a new transaction in the task.
- Work started inside a transaction can run before the commit. Start it after commit with `@TransactionalEventListener`, or use an outbox when it must not be lost (`java-backend:transactions-consistency`).
- Use bounded, Spring-managed executors. Avoid `Executors.newCachedThreadPool()`, and don't call `supplyAsync` without an executor. Each task that touches the database holds a pooled connection.
- JVM locks guard one instance, and on a `@Transactional` method they are released before the commit. Guard shared data in the database. For virtual threads, see `java-backend:spring-boot-baseline` and `java-backend:sql-performance`.

## Also

- `Optional` (Item 55) is for return values, not fields or parameters.
- Prefer composition (Item 18): decorate an interface instead of extending a concrete class you don't own.

## When to Apply

- Reviewing or writing value objects, entities, or exception handling around repositories
- Streams and collectors over query results
- `@Async`, executors, `CompletableFuture`, caches, or other shared state in Spring beans

## Gotchas

<!-- Keep adding mistakes Claude repeatedly makes. -->

- **A record is not an entity**: don't turn a JPA `@Entity` into a record. Records are final and immutable with no no-arg constructor, so Hibernate cannot proxy or populate them. Use records for DTOs, projections, and embeddable values.
- **Replacing a mapped collection breaks orphan removal**: assigning a new list to a loaded entity with `orphanRemoval = true` fails at flush with "A collection with orphan deletion was no longer referenced by the owning entity instance". Change the existing collection.
- **`Stream.toList()` returns an unmodifiable list**: unlike the result of `collect(Collectors.toList())`, which callers often mutate, any mutator throws `UnsupportedOperationException`. It is a copy, so later changes to the source don't leak in, but the copy is shallow: the elements themselves can still change.
- **`Collections.unmodifiableList()` is a view**: changes to the wrapped list still show through. Use `List.copyOf()` for a real snapshot.
- **Record validation can't be bypassed**: every record constructor must end up in the canonical one, so checks in a compact constructor also run for builders, including Lombok's `@Builder`.
- **Don't add `default` to an exhaustive switch over a sealed type**: without it, adding a new permitted subtype breaks compilation at every switch that doesn't handle it. That is the intended safety net.
- **The common double-checked locking bug**: returning the local variable read before the lock returns `null` when another thread initializes the field in between. Return the field read inside the lock.

## Additional Resources

- **references/value-objects-and-creation.md**: the full `Money`, entity construction, builders, and JDBC resources inside a transaction
- **references/exceptions.md**: translating constraint violations outside the transaction
- **references/streams.md**: collectors over rows, repository streams and driver fetch sizes, parallel streams
- **references/concurrency.md**: shared state in beans, thread-bound transactions, after-commit work, executors, caches, lazy initialization
