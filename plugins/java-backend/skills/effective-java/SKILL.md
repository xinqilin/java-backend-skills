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

- Java 程式碼涉及物件建立模式（factory, builder）
- equals/hashCode、Optional、Stream API 使用審查
- 例外處理或泛型設計討論

## Gotchas

<!-- 持續更新：遇到新的 Claude 常犯錯誤時加入 -->

- **Record 不等於 Entity**：不要把 JPA `@Entity` 換成 record。Record 沒有無參數構造器 + 可變欄位，Hibernate proxy 無法運作
- **Stream.toList() 回傳 unmodifiable 但非真正 immutable**：原始 stream source 被修改時，list 內容會跟著變。需要真正隔離請用 `List.copyOf()`
- **Lombok @Builder 跳過 record compact constructor 驗證**：用 Lombok @Builder 搭配 record 時，要在自定義 `build()` 內做驗證，否則 compact constructor 的 validation 被繞過
- **sealed interface + pattern matching switch 忘加 default 分支**：未來新增子類型時編譯失敗，這是刻意設計的安全網，不是 bug
- **Collections.unmodifiableList() 包裝仍能被原始 list 修改**：`List.copyOf()` 才真正安全，unmodifiableList 只是視圖

---

## Additional Resources

- **references/object-creation.md** — Items 1-9 完整程式碼範例。查看特定 creation pattern 時讀取
- **references/classes-and-interfaces.md** — Items 15-25 封裝、繼承、介面設計細節
- **references/lambdas-streams.md** — Stream API 完整範例與陷阱
- **references/concurrency.md** — Thread safety patterns、Virtual Thread 用法
