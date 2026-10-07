# Lambdas and Streams Best Practices

## Item 42: Prefer Lambdas to Anonymous Classes

### Basic Syntax

```java
// Anonymous class (verbose)
Comparator<Order> byDate = new Comparator<Order>() {
    @Override
    public int compare(Order o1, Order o2) {
        return o1.getCreatedAt().compareTo(o2.getCreatedAt());
    }
};

// Lambda (concise)
Comparator<Order> byDate = (o1, o2) ->
    o1.getCreatedAt().compareTo(o2.getCreatedAt());

// Method reference (most concise)
Comparator<Order> byDate = Comparator.comparing(Order::getCreatedAt);
```

### Method Reference Types

| Type | Example | Lambda Equivalent |
|------|---------|-------------------|
| Static | `Integer::parseInt` | `s -> Integer.parseInt(s)` |
| Bound | `instant::isAfter` | `t -> instant.isAfter(t)` |
| Unbound | `String::toLowerCase` | `s -> s.toLowerCase()` |
| Constructor | `Order::new` | `() -> new Order()` |
| Array | `int[]::new` | `len -> new int[len]` |

---

## Item 43: Prefer Method References to Lambdas

```java
// Lambda
map.merge(key, 1, (count, incr) -> count + incr);

// Method reference (clearer)
map.merge(key, 1, Integer::sum);

// But sometimes lambda is clearer
service.execute(() -> action());  // Clear
service.execute(GoshThisClassNameIsHumongous::action);  // Less clear
```

---

## Item 44: Favor Standard Functional Interfaces

### Core Functional Interfaces

| Interface | Signature | Example |
|-----------|-----------|---------|
| `Supplier<T>` | `() -> T` | `() -> new Order()` |
| `Consumer<T>` | `T -> void` | `order -> save(order)` |
| `Function<T,R>` | `T -> R` | `order -> order.getTotal()` |
| `Predicate<T>` | `T -> boolean` | `order -> order.isPending()` |
| `UnaryOperator<T>` | `T -> T` | `s -> s.trim()` |
| `BinaryOperator<T>` | `(T, T) -> T` | `(a, b) -> a + b` |

### Primitive Variants (Avoid Boxing)

```java
// BAD - Boxing overhead
Function<Integer, Integer> square = x -> x * x;

// GOOD - Primitive variant
IntUnaryOperator square = x -> x * x;

// Common primitives
IntSupplier       // () -> int
LongConsumer      // long -> void
DoubleFunction<R> // double -> R
IntPredicate      // int -> boolean
ToIntFunction<T>  // T -> int
```

---

## Item 45: Use Streams Judiciously

### When Streams Excel

```java
// Filtering and mapping
List<String> customerNames = orders.stream()
    .filter(o -> o.getStatus() == OrderStatus.CONFIRMED)
    .map(Order::getCustomerId)
    .distinct()
    .sorted()
    .toList();

// Grouping
Map<OrderStatus, List<Order>> byStatus = orders.stream()
    .collect(Collectors.groupingBy(Order::getStatus));

// Aggregation
BigDecimal total = orders.stream()
    .map(Order::getTotal)
    .reduce(BigDecimal.ZERO, BigDecimal::add);

// Finding
Optional<Order> largest = orders.stream()
    .max(Comparator.comparing(Order::getTotal));
```

### When Loops Are Better

```java
// Complex state mutation - use loop
Map<CustomerId, Order> largestByCustomer = new HashMap<>();
for (Order order : orders) {
    largestByCustomer.merge(
        order.getCustomerId(),
        order,
        (existing, current) ->
            existing.getTotal().compareTo(current.getTotal()) > 0
                ? existing : current
    );
}

// Multiple operations per element
for (Order order : pendingOrders) {
    order.confirm();
    orderRepository.save(order);
    emailService.sendConfirmation(order);
    metricsService.recordConfirmation(order);
}
```

### Readability Guidelines

```java
// GOOD - Short, clear pipeline
List<String> names = users.stream()
    .filter(User::isActive)
    .map(User::getName)
    .sorted()
    .toList();

// BAD - Too complex, split it up
result = orders.stream()
    .filter(o -> o.getStatus() == PENDING)
    .collect(groupingBy(
        Order::getCustomerId,
        collectingAndThen(
            maxBy(comparing(Order::getTotal)),
            opt -> opt.map(Order::getTotal).orElse(Money.ZERO)
        )
    ))
    .entrySet().stream()
    .filter(e -> e.getValue().isGreaterThan(threshold))
    .sorted(Map.Entry.<CustomerId, Money>comparingByValue().reversed())
    .limit(10)
    .collect(toMap(Map.Entry::getKey, Map.Entry::getValue));

// GOOD - Break into steps with meaningful names
Map<CustomerId, Money> largestOrderByCustomer = orders.stream()
    .filter(o -> o.getStatus() == PENDING)
    .collect(groupingBy(
        Order::getCustomerId,
        collectingAndThen(maxBy(comparing(Order::getTotal)),
            opt -> opt.map(Order::getTotal).orElse(Money.ZERO))
    ));

List<Map.Entry<CustomerId, Money>> topSpenders = largestOrderByCustomer.entrySet().stream()
    .filter(e -> e.getValue().isGreaterThan(threshold))
    .sorted(Map.Entry.<CustomerId, Money>comparingByValue().reversed())
    .limit(10)
    .toList();
```

---

## Item 46: Prefer Side-Effect-Free Functions in Streams

### Avoid Side Effects

```java
// BAD - forEach with side effects
Map<String, Long> freq = new HashMap<>();
words.forEach(word -> {
    freq.merge(word.toLowerCase(), 1L, Long::sum);  // Mutating external state!
});

// GOOD - Use collect
Map<String, Long> freq = words.stream()
    .collect(groupingBy(String::toLowerCase, counting()));

// BAD - Modifying stream source
List<Order> orders = new ArrayList<>(originalOrders);
orders.stream()
    .filter(Order::isPending)
    .forEach(o -> {
        o.confirm();  // Mutating elements
        orders.add(createAuditRecord(o));  // ConcurrentModificationException!
    });

// GOOD - Collect first, then modify
List<Order> pending = orders.stream()
    .filter(Order::isPending)
    .toList();

for (Order order : pending) {
    order.confirm();
    orderRepository.save(order);
}
```

### Common Collectors

```java
// toList, toSet, toMap
List<String> names = stream.collect(toList());
Set<String> uniqueNames = stream.collect(toSet());
Map<OrderId, Order> byId = stream.collect(toMap(Order::getId, identity()));

// Grouping
Map<OrderStatus, List<Order>> byStatus =
    orders.stream().collect(groupingBy(Order::getStatus));

Map<OrderStatus, Long> countByStatus =
    orders.stream().collect(groupingBy(Order::getStatus, counting()));

Map<OrderStatus, BigDecimal> totalByStatus =
    orders.stream().collect(groupingBy(
        Order::getStatus,
        reducing(BigDecimal.ZERO, Order::getTotal, BigDecimal::add)
    ));

// Partitioning (binary grouping)
Map<Boolean, List<Order>> partitioned =
    orders.stream().collect(partitioningBy(Order::isPending));

// Joining
String csv = orders.stream()
    .map(Order::getId)
    .map(OrderId::value)
    .collect(joining(", "));
```

---

## Item 47: Prefer Collection to Stream as Return Type

```java
// BAD - Returning stream limits caller options
public Stream<Order> getPendingOrders() {
    return orders.stream().filter(Order::isPending);
}

// GOOD - Return collection
public List<Order> getPendingOrders() {
    return orders.stream()
        .filter(Order::isPending)
        .toList();
}

// If collection is expensive, consider both
public class Orders {
    public List<Order> getPendingOrdersList() {
        return orders.stream().filter(Order::isPending).toList();
    }

    public Stream<Order> streamPendingOrders() {
        return orders.stream().filter(Order::isPending);
    }
}
```

---

## Item 48: Use Caution with Parallel Streams

### When NOT to Parallelize

```java
// BAD - ArrayList source, small size
List<Integer> small = List.of(1, 2, 3, 4, 5);
small.parallelStream().map(x -> x * 2);  // Overhead > benefit

// BAD - LinkedList (poor splitting)
LinkedList<Order> orders = new LinkedList<>();
orders.parallelStream().filter(Order::isPending);  // Sequential would be faster

// BAD - limit() with parallel
stream.parallel()
    .filter(predicate)
    .limit(n);  // Forces sequential-like processing

// BAD - Side effects (race conditions)
List<Order> results = new ArrayList<>();
orders.parallelStream()
    .filter(Order::isPending)
    .forEach(results::add);  // NOT THREAD-SAFE!
```

### When to Consider Parallel

```java
// GOOD - Large array, expensive computation, splittable
int[] largeArray = new int[10_000_000];
long sum = Arrays.stream(largeArray)
    .parallel()
    .mapToLong(x -> expensiveComputation(x))
    .sum();

// GOOD - Independent operations, stateless
List<Result> results = largeList.parallelStream()
    .filter(item -> expensivePredicate(item))
    .map(item -> expensiveTransform(item))
    .toList();
```

### Best Practices

1. **Measure performance** - Don't assume parallel is faster
2. **Use appropriate sources** - Arrays, ArrayLists, IntStream.range
3. **Avoid shared mutable state**
4. **Keep operations stateless**
5. **Be careful with ordering** - Use `forEachOrdered` if needed
