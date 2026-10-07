---
name: effective-java
description: Java language best practices (object creation, equals/hashCode, generics, Optional, streams, exceptions, concurrency) in the spirit of Effective Java. Use when reviewing or writing core Java code.
user-invocable: false
allowed-tools: Read, Grep, Glob
---

# Effective Java Best Practices

## Creating Objects

### Item 1: Static Factory Methods over Constructors

Prefer static factories over constructors: descriptive names (`createEmpty`, `of`, `from`), can return cached instances, can return subtypes.

```java
// Descriptive naming conveys intent
public static Order createPending(CustomerId customerId, List<OrderItem> items) {
    return new Order(OrderId.generate(), customerId, items, OrderStatus.PENDING);
}
public static Order reconstitute(OrderId id, CustomerId customerId,
        List<OrderItem> items, OrderStatus status) {
    return new Order(id, customerId, items, status);
}
```

### Item 2: Builder Pattern for Many Parameters

Use Builder when a class has 4+ parameters, especially optional ones. The Builder copies fields in the constructor to ensure immutability (`Map.copyOf`).

### Item 17: Minimize Mutability

```java
// Compact constructor validates in record
public record Money(BigDecimal amount, Currency currency) {
    public Money {
        Objects.requireNonNull(amount);
        Objects.requireNonNull(currency);
        if (amount.compareTo(BigDecimal.ZERO) < 0) {
            throw new IllegalArgumentException("Amount cannot be negative");
        }
    }

    public Money add(Money other) {
        validateSameCurrency(other);
        return new Money(this.amount.add(other.amount), this.currency);
    }
}
```

### Item 18: Favor Composition over Inheritance

The critical non-obvious trap: `addAll` calls `add` internally in HashSet.

```java
// BAD - Inheritance breaks encapsulation
public class InstrumentedHashSet<E> extends HashSet<E> {
    private int addCount = 0;

    @Override
    public boolean addAll(Collection<? extends E> c) {
        addCount += c.size();
        return super.addAll(c);  // BUG: addAll calls add(), double counting!
    }
}

// GOOD - Composition (Wrapper/Decorator)
public class InstrumentedSet<E> implements Set<E> {
    private final Set<E> delegate;
    private int addCount = 0;

    @Override
    public boolean addAll(Collection<? extends E> c) {
        addCount += c.size();
        return delegate.addAll(c);  // Correct: no double counting
    }
}
```

---

## Generics

### Item 31: Use Bounded Wildcards (PECS)

**Producer Extends, Consumer Super** — non-obvious rule that enables maximum flexibility.

```java
// Producer - reads from collection, use extends
public void processOrders(List<? extends Order> orders) {
    for (Order order : orders) { process(order); }
}

// Consumer - writes to collection, use super
public void addOrders(List<? super Order> destination) {
    destination.add(new Order());
}

// Copy: src is producer (extends), dest is consumer (super)
public static <T> void copy(List<? extends T> src, List<? super T> dest) {
    for (T item : src) { dest.add(item); }
}
```

---

## Lambdas and Streams

### Item 45: Use Streams Judiciously

Use loop when it's clearer than a stream chain. Multi-level nested collectors hurt readability — prefer a loop with `Map.merge`.

### Item 46: Prefer Side-Effect-Free Functions

```java
// BAD - Side effects in stream (mutation + I/O inside forEach)
orders.stream()
    .filter(Order::isPending)
    .forEach(o -> {
        o.confirm();               // Mutating!
        orderRepository.save(o);   // Side effect!
    });

// GOOD - Collect, then process
List<Order> pendingOrders = orders.stream()
    .filter(Order::isPending)
    .toList();

for (Order order : pendingOrders) {
    order.confirm();
    orderRepository.save(order);
}
```

---

## Exceptions

### Item 73: Throw Appropriate to Abstraction

```java
// BAD - Low-level exception leaks implementation detail
public Order findOrder(OrderId id) {
    try {
        return jdbcTemplate.queryForObject(...);
    } catch (EmptyResultDataAccessException e) {
        throw e;  // Caller shouldn't know about JDBC!
    }
}

// GOOD - Translate to domain exception
public Order findOrder(OrderId id) {
    try {
        return jdbcTemplate.queryForObject(...);
    } catch (EmptyResultDataAccessException e) {
        throw new OrderNotFoundException(id, e);
    }
}
```

---

## Code Review Checklist

| Check | Good | Bad |
|-------|------|-----|
| Object creation | Static factory / Builder | Telescoping constructors |
| Value objects | `record` or immutable class | Mutable with setters |
| Collections | `List.of()`, `Map.of()`, `unmodifiableList` | Exposed mutable collections |
| Optional | `orElseThrow()`, `map()`, `filter()` | `get()` without `isPresent()` |
| Streams | Reasonable pipeline, side-effect free | Nested collectors, mutations |
| Exceptions | Domain-specific, standard exceptions | Generic Exception, flow control |
| Generics | Bounded wildcards (PECS) | Raw types |

---

## When to Apply

- Java code that creates objects (static factories, builders)
- Reviewing equals/hashCode, Optional, or Stream API usage
- Exception handling or generics design discussions

## Gotchas

<!-- Keep adding mistakes Claude repeatedly makes. -->

- **A record is not an entity**: don't turn a JPA `@Entity` into a record. Records are final and immutable with no no-arg constructor, so Hibernate cannot proxy or populate them. Use records for DTOs and query projections.
- **`Stream.toList()` returns an unmodifiable list**: unlike the result of `collect(Collectors.toList())`, which callers often mutate, any mutator throws `UnsupportedOperationException`. It is a copy, so later changes to the source don't leak in, but the copy is shallow: the elements themselves can still change.
- **Record validation can't be bypassed**: every record constructor must end up in the canonical one, so checks in a compact constructor also run for builders, including Lombok's `@Builder`.
- **Don't add `default` to an exhaustive switch over a sealed type**: without it, adding a new permitted subtype breaks compilation at every switch that doesn't handle it. That is the intended safety net.
- **`Collections.unmodifiableList()` is a view**: changes to the wrapped list still show through. Use `List.copyOf()` for a real snapshot.

---

## Additional Resources

- **references/object-creation.md**: full examples for object creation (items 1-9). Read when checking a specific creation pattern.
- **references/classes-and-interfaces.md**: encapsulation, inheritance, and interface design (items 15-25)
- **references/lambdas-streams.md**: Stream API examples and pitfalls
- **references/concurrency.md**: thread-safety patterns and virtual threads
