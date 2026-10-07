# Concurrency Best Practices

## Item 78: Synchronize Access to Shared Mutable Data

### The Problem

```java
// BAD - Race condition
public class Counter {
    private int count = 0;

    public void increment() {
        count++;  // Not atomic! Read-modify-write
    }

    public int getCount() {
        return count;  // May see stale value
    }
}
```

### Solutions

```java
// Solution 1: synchronized
public class Counter {
    private int count = 0;

    public synchronized void increment() {
        count++;
    }

    public synchronized int getCount() {
        return count;
    }
}

// Solution 2: AtomicInteger (preferred for counters)
public class Counter {
    private final AtomicInteger count = new AtomicInteger(0);

    public void increment() {
        count.incrementAndGet();
    }

    public int getCount() {
        return count.get();
    }
}

// Solution 3: volatile (only for simple flags)
public class StopFlag {
    private volatile boolean stopped = false;

    public void stop() {
        stopped = true;
    }

    public boolean isStopped() {
        return stopped;
    }
}
```

---

## Item 79: Avoid Excessive Synchronization

### The Problem: Deadlock Risk

```java
// BAD - Calling alien method while holding lock
public class ObservableSet<E> {
    private final List<SetObserver<E>> observers = new ArrayList<>();

    public synchronized void addObserver(SetObserver<E> observer) {
        observers.add(observer);
    }

    public synchronized void notifyElementAdded(E element) {
        for (SetObserver<E> observer : observers) {
            observer.added(this, element);  // Alien method! Can cause deadlock
        }
    }
}
```

### Solution: Copy-then-iterate

```java
public class ObservableSet<E> {
    private final List<SetObserver<E>> observers = new ArrayList<>();

    public synchronized void addObserver(SetObserver<E> observer) {
        observers.add(observer);
    }

    public void notifyElementAdded(E element) {
        List<SetObserver<E>> snapshot;
        synchronized (this) {
            snapshot = new ArrayList<>(observers);  // Copy while holding lock
        }
        for (SetObserver<E> observer : snapshot) {
            observer.added(this, element);  // No lock held
        }
    }
}

// Better: Use CopyOnWriteArrayList
public class ObservableSet<E> {
    private final List<SetObserver<E>> observers = new CopyOnWriteArrayList<>();

    public void addObserver(SetObserver<E> observer) {
        observers.add(observer);
    }

    public void notifyElementAdded(E element) {
        for (SetObserver<E> observer : observers) {
            observer.added(this, element);
        }
    }
}
```

---

## Item 80: Prefer Executors, Tasks, and Streams to Threads

### ExecutorService Basics

```java
// BAD - Manual thread management
Thread thread = new Thread(() -> processOrder(order));
thread.start();

// GOOD - Use ExecutorService
ExecutorService executor = Executors.newFixedThreadPool(
    Runtime.getRuntime().availableProcessors()
);

executor.submit(() -> processOrder(order));

// Proper shutdown
executor.shutdown();
try {
    if (!executor.awaitTermination(60, TimeUnit.SECONDS)) {
        executor.shutdownNow();
    }
} catch (InterruptedException e) {
    executor.shutdownNow();
    Thread.currentThread().interrupt();
}
```

### Common Executor Types

```java
// Fixed thread pool - for CPU-bound tasks
ExecutorService cpuBound = Executors.newFixedThreadPool(
    Runtime.getRuntime().availableProcessors()
);

// Cached thread pool - for I/O-bound tasks (short-lived)
ExecutorService ioBound = Executors.newCachedThreadPool();

// Single thread - for sequential tasks
ExecutorService sequential = Executors.newSingleThreadExecutor();

// Scheduled - for periodic tasks
ScheduledExecutorService scheduled = Executors.newScheduledThreadPool(1);
scheduled.scheduleAtFixedRate(
    () -> cleanupExpired(),
    0, 1, TimeUnit.HOURS
);

// Virtual threads (Java 21+) - for massive concurrency
ExecutorService virtual = Executors.newVirtualThreadPerTaskExecutor();
```

### CompletableFuture for Async Operations

```java
public CompletableFuture<OrderResult> processOrderAsync(Order order) {
    return CompletableFuture
        .supplyAsync(() -> validateOrder(order), executor)
        .thenApplyAsync(validated -> calculateTotal(validated), executor)
        .thenApplyAsync(calculated -> saveOrder(calculated), executor)
        .exceptionally(ex -> {
            log.error("Order processing failed", ex);
            return OrderResult.failed(ex.getMessage());
        });
}

// Combining multiple futures
CompletableFuture<Void> allOrders = CompletableFuture.allOf(
    processOrderAsync(order1),
    processOrderAsync(order2),
    processOrderAsync(order3)
);

// First to complete
CompletableFuture<OrderResult> fastest = CompletableFuture.anyOf(
    processViaServiceA(order),
    processViaServiceB(order)
).thenApply(result -> (OrderResult) result);
```

---

## Item 81: Prefer Concurrency Utilities to wait and notify

### Use Concurrent Collections

```java
// Instead of synchronized HashMap
private final Map<OrderId, Order> cache = new ConcurrentHashMap<>();

// Atomic compute operations
cache.computeIfAbsent(orderId, id -> loadOrder(id));
cache.compute(orderId, (id, existing) ->
    existing == null ? createNew(id) : update(existing)
);

// BlockingQueue for producer-consumer
BlockingQueue<Order> orderQueue = new LinkedBlockingQueue<>(100);

// Producer
orderQueue.put(order);  // Blocks if full

// Consumer
Order order = orderQueue.take();  // Blocks if empty
```

### Use Synchronizers

```java
// CountDownLatch - wait for N events
CountDownLatch latch = new CountDownLatch(3);

executor.submit(() -> { doWork1(); latch.countDown(); });
executor.submit(() -> { doWork2(); latch.countDown(); });
executor.submit(() -> { doWork3(); latch.countDown(); });

latch.await();  // Wait for all three
processResults();

// Semaphore - limit concurrent access
Semaphore permits = new Semaphore(10);  // Max 10 concurrent

public void accessResource() {
    permits.acquire();
    try {
        useResource();
    } finally {
        permits.release();
    }
}

// CyclicBarrier - synchronize threads at a point
CyclicBarrier barrier = new CyclicBarrier(3, () -> mergeResults());

// Each thread
doPartialWork();
barrier.await();  // Wait for all threads, then mergeResults() runs
```

---

## Item 82: Document Thread Safety

### Thread Safety Levels

```java
/**
 * Thread-safe order cache with atomic operations.
 *
 * <p>This class is thread-safe. All public methods can be called
 * concurrently from multiple threads without external synchronization.
 *
 * @ThreadSafe
 */
public class OrderCache {
    private final ConcurrentHashMap<OrderId, Order> cache = new ConcurrentHashMap<>();

    /**
     * Gets or loads an order.
     *
     * <p>Thread-safe: uses ConcurrentHashMap.computeIfAbsent for atomicity.
     */
    public Order get(OrderId id) {
        return cache.computeIfAbsent(id, this::loadOrder);
    }
}

/**
 * Not thread-safe. Instances should be confined to a single thread,
 * or external synchronization must be used.
 *
 * @NotThreadSafe
 */
public class OrderBuilder {
    private List<OrderItem> items = new ArrayList<>();

    public OrderBuilder addItem(OrderItem item) {
        items.add(item);
        return this;
    }
}

/**
 * Conditionally thread-safe.
 *
 * <p>Individual operations are thread-safe, but sequences of operations
 * may require external synchronization.
 */
public class ConditionallyThreadSafe {
    // ...
}
```

---

## Item 83: Use Lazy Initialization Judiciously

### Lazy Initialization Patterns

```java
// Normal initialization (preferred when possible)
private final ExpensiveObject field = new ExpensiveObject();

// Lazy initialization with synchronized accessor
private ExpensiveObject field;

public synchronized ExpensiveObject getField() {
    if (field == null) {
        field = new ExpensiveObject();
    }
    return field;
}

// Double-check idiom for instance fields
private volatile ExpensiveObject field;

public ExpensiveObject getField() {
    ExpensiveObject result = field;
    if (result == null) {
        synchronized (this) {
            if (field == null) {
                field = result = new ExpensiveObject();
            }
        }
    }
    return result;
}

// Lazy initialization holder class idiom (for static fields)
public class Singleton {
    private Singleton() {}

    private static class Holder {
        static final Singleton INSTANCE = new Singleton();
    }

    public static Singleton getInstance() {
        return Holder.INSTANCE;
    }
}
```

---

## Item 84: Don't Depend on Thread Scheduler

### Bad Practices

```java
// BAD - Busy waiting
while (!done) {
    // Wastes CPU cycles
}

// BAD - Thread.yield() for correctness
while (!condition) {
    Thread.yield();  // Unreliable, scheduler-dependent
}

// BAD - Thread.sleep() for synchronization
Thread.sleep(100);  // Hope other thread finishes
doNextStep();
```

### Good Practices

```java
// GOOD - Use proper synchronization
synchronized (lock) {
    while (!condition) {
        lock.wait();
    }
}

// GOOD - Use CountDownLatch
latch.await();
doNextStep();

// GOOD - Use CompletableFuture
future.thenAccept(result -> doNextStep(result));

// GOOD - Use BlockingQueue
Order order = queue.take();  // Blocks until available
process(order);
```

---

## Thread Safety Checklist

| Pattern | Use Case | Example |
|---------|----------|---------|
| Immutable | Value objects | `record`, final fields |
| Thread confinement | Per-request data | ThreadLocal, stack variables |
| Synchronized | Mutable shared state | synchronized blocks/methods |
| Concurrent collections | Shared collections | ConcurrentHashMap |
| Atomic variables | Counters, flags | AtomicInteger, AtomicReference |
| ExecutorService | Task execution | Thread pools |
| CompletableFuture | Async operations | Chained async tasks |
