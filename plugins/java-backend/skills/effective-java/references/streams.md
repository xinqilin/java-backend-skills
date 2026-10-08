# Streams Over Query Results

Items 45-48 of *Effective Java* (3rd ed.), applied to data that comes from a database. The examples are our own and compile on Spring Boot 4.1 (Hibernate 7.4, Java 21).

## A repository call inside a pipeline is N+1 (Item 46)

```java
// BAD: one SELECT per transfer
return transfers.stream()
        .map(t -> of(t, accounts.findById(t.accountId()).orElseThrow()))
        .toList();

// One query, then join in memory
Set<UUID> accountIds = transfers.stream().map(Transfer::accountId).collect(Collectors.toSet());
Map<UUID, Account> byId = accounts.findAllById(accountIds).stream()
        .collect(Collectors.toMap(Account::getId, Function.identity())); // ids are unique
return transfers.stream().map(t -> of(t, byId.get(t.accountId()))).toList();
```

- The stream hides the loop, so the per-element query is easy to miss in review. The fix is the same as for any N+1: one bulk query (`findAllById`, a fetch join, or a projection), then work in memory.
- Don't change managed entities inside `map` or `peek`. Dirty checking turns that into writes hidden in what reads like a query. Use a loop for elements that are changed, saved, or published.

## Collectors over rows (Item 46)

```java
// Throws IllegalStateException on a duplicate sku, NullPointerException on a null price
rows.stream().collect(Collectors.toMap(PriceRow::sku, PriceRow::price));

// Several rows per sku (one per region): say which one wins
rows.stream().collect(Collectors.toMap(PriceRow::sku, PriceRow::price, BigDecimal::min));

// A nullable column: toMap cannot hold null values, a HashMap can
Map<String, BigDecimal> bySku = new HashMap<>();
for (PriceRow row : rows) {
    bySku.put(row.sku(), row.price());
}
```

- `toMap` fails with `IllegalStateException: Duplicate key A (attempted merging values 1 and 10)` when two rows share a key. Rows from a join produce duplicates as soon as one side has several matches.
- `toMap` throws `NullPointerException` on a null value, with or without a merge function. Nullable columns produce null values.
- `groupingBy` handles one-to-many rows, but rejects a null key ("element cannot be mapped to a null key").
- List results differ:

  | Producer | Modifiable | Nulls |
  |---|---|---|
  | `Stream.toList()` | No (an unmodifiable copy) | Allowed |
  | `Collectors.toList()` | Not guaranteed (an `ArrayList` in current JDKs) | Allowed |
  | `Collectors.toUnmodifiableList()`, `List.copyOf` | No | `NullPointerException` |

## Returning streams from repositories (Item 47)

Return a collection (`List`, `Page`, `Slice`) from repositories and services, so callers don't hold a cursor open. Use `Stream<T>` for large exports and batch jobs:

```java
public interface AccountRepository extends Repository<Account, UUID> {

    @QueryHints(@QueryHint(name = HibernateHints.HINT_FETCH_SIZE, value = "500"))
    @Query("select new com.example.ej.BalanceRow(a.id, a.balance.amount) from Account a")
    Stream<BalanceRow> streamBalances();
}

@Transactional(readOnly = true) // Spring Data refuses to run a streaming query without one
public void writeTo(Writer out) {
    try (var rows = accounts.streamBalances()) { // closes the cursor and the ResultSet
        rows.forEach(row -> write(out, row.accountId() + "," + row.amount()));
    }
}
```

- Without a surrounding transaction, Spring Data JPA throws `InvalidDataAccessApiUsageException` ("You're trying to execute a streaming query method without a surrounding transaction ..."). The transaction keeps the connection and cursor open while you read.
- Close the stream as soon as you're done, with try-with-resources. Hibernate closes the `ResultSet` at the end of the transaction at the latest.
- Whether rows really stream depends on the driver:
  - **PostgreSQL (pgjdbc)** reads the whole result at once unless the connection is not in autocommit mode (it is inside a transaction), the statement is forward-only, the query is a single statement, and a fetch size is set. Otherwise it silently falls back to reading everything.
  - **MySQL Connector/J** reads the whole result into memory by default. A fetch size of `Integer.MIN_VALUE` on a forward-only, read-only statement streams row by row, and no other query can run on that connection until the stream is fully read or closed. With `useCursorFetch=true` in the JDBC URL, a positive fetch size uses a server-side cursor instead.
- Streamed entities stay managed in the persistence context, so memory still grows with every row. Stream a DTO projection, as above, or detach entities as you go.
- A long-running stream holds a connection and a transaction for its whole duration. For user-facing reads, page instead (keyset pagination: `java-backend:sql-performance`).

## Parallel streams (Item 48)

- `parallelStream()` splits the work between the calling thread and `ForkJoinPool.commonPool()`. The common pool is shared by the whole JVM, including `CompletableFuture` async methods called without an executor. Blocking JDBC calls on it starve every other user.
- Common-pool threads have no transaction and no persistence context. A Hibernate `Session` is single-threaded, so lazy loading from those threads either fails with `LazyInitializationException` (the session is closed) or uses one session from two threads at once.
- To parallelize database work, split the ids into chunks, run each chunk on a bounded executor in its own transaction, and size the executor to the connection pool (`java-backend:sql-performance`).
- CPU-bound work on data already in memory (scoring, hashing) can benefit from parallel streams. Measure before you switch.

## Readability (Item 45)

Keep pipelines short, and give intermediate results names. A loop is clearer when each element triggers several side effects (save, publish, log).

## Sources

- Joshua Bloch, *Effective Java* (3rd ed.), ch. 7 "Lambdas and Streams" (items 45-48)
- Java SE API, `Collectors` (`toMap`, `groupingBy`, `toList`, `toUnmodifiableList`): https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/stream/Collectors.html
- Java SE API, `Stream.toList`: https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/stream/Stream.html
- Java SE API, `ForkJoinPool` (common pool): https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/concurrent/ForkJoinPool.html
- Spring Data JPA reference, Streaming Query Results: https://docs.spring.io/spring-data/jpa/reference/repositories/query-methods-details.html
- Spring Data JPA 4.1.1 source, `JpaQueryExecution.StreamExecution`: https://github.com/spring-projects/spring-data-jpa/blob/4.1.1/spring-data-jpa/src/main/java/org/springframework/data/jpa/repository/query/JpaQueryExecution.java
- Hibernate ORM 7.4 User Guide (`getResultStream`, the `Session` is single-threaded): https://docs.hibernate.org/orm/7.4/userguide/html_single/
- pgJDBC, Getting results based on a cursor: https://jdbc.postgresql.org/documentation/query/
- MySQL Connector/J, JDBC API Implementation Notes (ResultSet streaming, `useCursorFetch`): https://dev.mysql.com/doc/connector-j/en/connector-j-reference-implementation-notes.html
