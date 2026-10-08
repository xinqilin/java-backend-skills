# Concurrency in Spring Beans

Items 78-84 of *Effective Java* (3rd ed.), applied to Spring Boot services that use a database. The examples are our own and compile on Spring Boot 4.1 (Java 21).

## Singleton beans share their fields (Item 78)

Spring manages one shared instance of a singleton bean (the default scope), and every request thread calls it concurrently:

```java
// BAD: one instance serves every request thread, so this field is shared mutable state.
@Service
public class InvoiceTotals {

    private BigDecimal runningTotal = BigDecimal.ZERO;

    public BigDecimal add(BigDecimal amount) {
        runningTotal = runningTotal.add(amount); // lost updates between concurrent requests
        return runningTotal;
    }
}
```

- Keep per-request state in local variables and parameters.
- For shared counters, use `AtomicLong` or `LongAdder`. For shared caches, use a bounded, expiring cache (Spring Cache with Caffeine), not a `HashMap` field.
- `WeakHashMap` is not a cache. An entry disappears once its key is no longer referenced anywhere else, which for keys built per request is almost immediately.
- State that must stay consistent across instances (balances, stock, quotas) belongs in the database. `synchronized` covers one JVM only, and on a `@Transactional` method the lock is released before the proxy commits (`java-backend:transactions-consistency`).

### ThreadLocal on pooled threads

```java
@Override
protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
        FilterChain chain) throws ServletException, IOException {
    TENANT.set(request.getHeader("X-Tenant"));
    try {
        chain.doFilter(request, response);
    } finally {
        TENANT.remove(); // request threads are pooled: the next request would inherit it
    }
}
```

Servlet containers reuse request threads, and a `ThreadLocal` lives until it is removed or its thread ends. If a tenant id that drives an `AbstractRoutingDataSource` is never removed, the next request on that thread reads another tenant's data. Set and remove the value in the same `try`/`finally`.

## Transactions are bound to the thread (Items 80, 81)

The `@Transactional` Javadoc says the annotation works with thread-bound transactions and does not propagate to threads started inside the method. The `EntityManager` and its persistence context are bound the same way. Work on another thread:

- runs without the caller's transaction. It doesn't see the caller's uncommitted writes, and it doesn't roll back with the caller.
- must not use the caller's managed entities. A Hibernate `Session` is single-threaded, and after the caller's transaction ends, lazy loading fails.
- holds its own pooled connection while it touches the database.

Hand over ids or immutable DTOs, and let the task open its own transaction through a `@Transactional` bean method.

### Start follow-up work after commit

```java
@Transactional
public UUID place(PlaceOrder command) {
    Order order = orders.save(Order.from(command));
    events.publishEvent(new OrderPlaced(order.getId())); // delivered after commit
    return order.getId();
}

@Component
class InvoiceOnOrderPlaced {

    private final InvoiceService invoices;

    InvoiceOnOrderPlaced(InvoiceService invoices) {
        this.invoices = invoices;
    }

    @Async("reportExecutor")
    @TransactionalEventListener // AFTER_COMMIT: the new transaction below can see the order
    void on(OrderPlaced event) {
        invoices.createFor(event.orderId()); // pass the id, not the entity
    }
}
```

- `@TransactionalEventListener` defaults to the `AFTER_COMMIT` phase. The task starts only if the order committed, and its own transaction can read the order.
- Without `@Async`, the listener runs on the committing thread, where the finished transaction's resources are still bound. A `@Transactional` (`REQUIRED`) call there joins that transaction, and its writes are never committed. Use `REQUIRES_NEW` there, as the Javadoc of `TransactionSynchronization.afterCommit` advises, or make the listener `@Async`.
- `@Async` and transaction events live in memory only. If the process stops between the commit and the task, the work is lost. Use an outbox for work that must happen (`java-backend:transactions-consistency`).
- `@Async`, like `@Transactional`, works through the proxy. Calling an `@Async` method from the same class runs it synchronously on the caller's thread.

## Executors (Item 80)

When no `Executor` bean exists, Spring Boot auto-configures an `AsyncTaskExecutor` named `applicationTaskExecutor`, which `@EnableAsync` uses:

| Threads | Executor | Defaults that matter |
|---|---|---|
| Platform | `ThreadPoolTaskExecutor` | 8 core threads; the queue is unbounded, so `max-size` has no effect until `queue-capacity` is set |
| Virtual (`spring.threads.virtual.enabled=true`) | `SimpleAsyncTaskExecutor` | No concurrency limit unless `spring.task.execution.simple.concurrency-limit` is set |

```yaml
spring:
  task:
    execution:
      pool:
        core-size: 8
        max-size: 16
        queue-capacity: 500 # bounded: the pool grows toward max-size only when the queue is full
```

- Every task that calls the database needs a pooled connection, so concurrency above the pool size only adds waiting (`java-backend:sql-performance`).
- A bounded `ThreadPoolTaskExecutor` rejects new tasks with `TaskRejectedException` once both its queue and its threads are full. Decide whether the caller retries, degrades, or fails.
- Give a slow workload its own executor and name it in `@Async("reportExecutor")`. Declaring any `Executor` bean makes the auto-configured one back off, and `@EnableAsync` then uses yours. Set `spring.task.execution.mode=force` to keep both.

```java
@Bean
ThreadPoolTaskExecutor reportExecutor(ThreadPoolTaskExecutorBuilder builder) {
    return builder.corePoolSize(4)
            .maxPoolSize(4)
            .queueCapacity(200) // bounded: a full queue rejects with TaskRejectedException
            .threadNamePrefix("report-")
            .build();
}
```

- `CompletableFuture.supplyAsync(task)` without an executor runs on `ForkJoinPool.commonPool()`, which parallel streams share. Pass a Spring-managed executor instead:

```java
public CompletableFuture<BigDecimal> quote(UUID productId) {
    return CompletableFuture.supplyAsync(() -> lookUp(productId), executor); // the reportExecutor bean
}
```

- Avoid `Executors.newCachedThreadPool()`: it starts a new thread whenever no idle one is available, with no upper bound. An executor you create yourself is also yours to shut down. A Spring bean is shut down when the context closes.

## Concurrent collections (Item 81)

```java
private final ConcurrentHashMap<String, TaxRule> byRegion = new ConcurrentHashMap<>();

TaxRule ruleFor(String region) {
    // Runs the loader at most once per absent key, but blocks other updates to the same bin meanwhile.
    return byRegion.computeIfAbsent(region, loader);
}
```

`ConcurrentHashMap.computeIfAbsent` runs the mapping function at most once per absent key, atomically. Its Javadoc also says the computation should be short and simple, because other threads' updates may block while it runs, and that the function must not modify the map:

- A database call inside it holds up writers to the same bin for the length of the query.
- A nested `computeIfAbsent` on the same map throws `IllegalStateException: Recursive update`.
- The map never evicts. When keys come from user input, or the data changes, use a bounded cache with expiry.

Prefer `java.util.concurrent` (executors, latches, semaphores, blocking queues) to `wait` and `notify`.

## Lazy initialization (Item 83)

In a Spring application, let the container own the lifecycle. A singleton bean created at startup (or marked `@Lazy`) is initialized once, safely. In code that isn't a bean:

```java
private volatile TaxTable table;

TaxTable table() {
    TaxTable local = table;
    if (local != null) {
        return local; // fast path: one volatile read
    }
    synchronized (this) {
        if (table == null) {
            table = TaxTable.load();
        }
        return table; // read under the lock, so never null
    }
}

// Static field: the class initializer already runs once, lazily, and safely.
private static final class Holder {
    static final TaxTable SHARED = TaxTable.load();
}

static TaxTable shared() {
    return Holder.SHARED;
}
```

- The double-check idiom needs a `volatile` field, and it must return the value read **inside** the lock. A common broken variant keeps the local variable from the first read and returns it after the lock. When another thread initializes the field in between, the second check skips the assignment, and the method returns `null`.
- For a static field, the holder class is simpler. The JVM initializes a class once, on first use, with the required locking.

## Don't depend on timing (Item 84)

- Using `Thread.sleep` to wait for async work, in code or in tests, is a race. Wait on a `CompletableFuture`, a latch, or a condition. For concurrency tests, see `java-backend:java-testing`.
- Thread priorities and `Thread.yield()` are not correctness tools.

## Virtual threads

See `java-backend:spring-boot-baseline` (enabling them, which Java version) and `java-backend:sql-performance` (`references/connection-pool.md`: the pool becomes the throttle; pinning on Java 21-23).

## Sources

- Joshua Bloch, *Effective Java* (3rd ed.), ch. 11 "Concurrency" (items 78-84)
- Spring Framework reference, Bean Scopes (the singleton scope): https://docs.spring.io/spring-framework/reference/core/beans/factory-scopes.html
- Spring Framework Javadoc, `Transactional` (thread-bound, not propagated to new threads): https://docs.spring.io/spring-framework/docs/current/javadoc-api/org/springframework/transaction/annotation/Transactional.html
- Spring Framework Javadoc, `TransactionSynchronization.afterCommit` (use `REQUIRES_NEW`): https://docs.spring.io/spring-framework/docs/current/javadoc-api/org/springframework/transaction/support/TransactionSynchronization.html
- Spring Framework Javadoc, `TransactionalEventListener` (default phase `AFTER_COMMIT`): https://docs.spring.io/spring-framework/docs/current/javadoc-api/org/springframework/transaction/event/TransactionalEventListener.html
- Spring Framework Javadoc, `EnableAsync` (proxy mode intercepts calls through the proxy only): https://docs.spring.io/spring-framework/docs/current/javadoc-api/org/springframework/scheduling/annotation/EnableAsync.html
- Spring Boot reference, Task Execution and Scheduling: https://docs.spring.io/spring-boot/reference/features/task-execution-and-scheduling.html
- Spring Boot application properties (`spring.task.execution.*`): https://docs.spring.io/spring-boot/appendix/application-properties/index.html
- Spring Boot 4.1.1 source, `TaskExecutionProperties` (pool defaults): https://github.com/spring-projects/spring-boot/blob/v4.1.1/core/spring-boot-autoconfigure/src/main/java/org/springframework/boot/autoconfigure/task/TaskExecutionProperties.java
- Hibernate ORM 7.4 User Guide (the `Session` is single-threaded): https://docs.hibernate.org/orm/7.4/userguide/html_single/
- Java SE API, `ConcurrentHashMap.computeIfAbsent`: https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/concurrent/ConcurrentHashMap.html
- Java SE API, `CompletableFuture` (default executor): https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/concurrent/CompletableFuture.html
- Java SE API, `WeakHashMap`: https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/WeakHashMap.html
- Java Language Specification, 12.4.2 "Detailed Initialization Procedure": https://docs.oracle.com/javase/specs/jls/se25/html/jls-12.html#jls-12.4.2
