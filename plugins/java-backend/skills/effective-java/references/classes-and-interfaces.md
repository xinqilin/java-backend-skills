# Classes and Interfaces Design

## Item 15: Minimize Accessibility

### Access Level Hierarchy

| Modifier | Class | Package | Subclass | World |
|----------|-------|---------|----------|-------|
| private | Yes | No | No | No |
| (default) | Yes | Yes | No | No |
| protected | Yes | Yes | Yes | No |
| public | Yes | Yes | Yes | Yes |

### Guidelines

```java
// BAD - Everything public
public class Order {
    public String id;
    public List<OrderItem> items;
    public BigDecimal total;

    public void recalculateTotal() { /* ... */ }
    public void validateItems() { /* ... */ }
    public void notifyCustomer() { /* ... */ }
}

// GOOD - Minimal exposure
public class Order {
    private final OrderId id;
    private final List<OrderItem> items;
    private Money total;

    // Only expose necessary methods
    public OrderId getId() { return id; }

    public List<OrderItem> getItems() {
        return Collections.unmodifiableList(items);
    }

    public Money getTotal() { return total; }

    // Internal methods are private
    private void recalculateTotal() { /* ... */ }
}
```

---

## Item 16: Use Accessor Methods in Public Classes

```java
// BAD - Public fields (okay for private nested classes)
public class Point {
    public double x;
    public double y;
}

// GOOD - Encapsulated with accessors
public class Point {
    private double x;
    private double y;

    public Point(double x, double y) {
        this.x = x;
        this.y = y;
    }

    public double getX() { return x; }
    public double getY() { return y; }

    // Can add validation later
    public void setX(double x) {
        if (Double.isNaN(x)) throw new IllegalArgumentException();
        this.x = x;
    }
}

// Or use immutable record
public record Point(double x, double y) {
    public Point {
        if (Double.isNaN(x) || Double.isNaN(y)) {
            throw new IllegalArgumentException("Coordinates cannot be NaN");
        }
    }
}
```

---

## Item 17: Minimize Mutability

### Immutable Class Rules

1. Don't provide mutators (setters)
2. Ensure class can't be extended (final class or private constructor)
3. Make all fields final
4. Make all fields private
5. Ensure exclusive access to mutable components

```java
// Immutable Money class
public final class Money {
    private final BigDecimal amount;
    private final Currency currency;

    public Money(BigDecimal amount, Currency currency) {
        this.amount = Objects.requireNonNull(amount);
        this.currency = Objects.requireNonNull(currency);
        if (amount.compareTo(BigDecimal.ZERO) < 0) {
            throw new IllegalArgumentException("Amount cannot be negative");
        }
    }

    public BigDecimal getAmount() { return amount; }
    public Currency getCurrency() { return currency; }

    // Operations return new instances
    public Money add(Money other) {
        validateSameCurrency(other);
        return new Money(this.amount.add(other.amount), this.currency);
    }

    public Money multiply(int quantity) {
        return new Money(this.amount.multiply(BigDecimal.valueOf(quantity)), this.currency);
    }

    private void validateSameCurrency(Money other) {
        if (!this.currency.equals(other.currency)) {
            throw new IllegalArgumentException("Cannot operate on different currencies");
        }
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof Money money)) return false;
        return amount.compareTo(money.amount) == 0 &&
               currency.equals(money.currency);
    }

    @Override
    public int hashCode() {
        return Objects.hash(amount, currency);
    }
}
```

### Defensive Copying

```java
public final class Period {
    private final Date start;
    private final Date end;

    public Period(Date start, Date end) {
        // Defensive copy on construction
        this.start = new Date(start.getTime());
        this.end = new Date(end.getTime());

        if (this.start.after(this.end)) {
            throw new IllegalArgumentException("Start after end");
        }
    }

    public Date getStart() {
        // Defensive copy on access
        return new Date(start.getTime());
    }

    public Date getEnd() {
        return new Date(end.getTime());
    }
}

// Better: Use immutable types
public record Period(LocalDate start, LocalDate end) {
    public Period {
        if (start.isAfter(end)) {
            throw new IllegalArgumentException("Start after end");
        }
    }
}
```

---

## Item 18: Favor Composition over Inheritance

### Inheritance Problem: Breaking Encapsulation

```java
// Fragile base class problem
public class InstrumentedHashSet<E> extends HashSet<E> {
    private int addCount = 0;

    @Override
    public boolean add(E e) {
        addCount++;
        return super.add(e);
    }

    @Override
    public boolean addAll(Collection<? extends E> c) {
        addCount += c.size();
        return super.addAll(c);  // BUG: Calls add() internally!
    }

    public int getAddCount() { return addCount; }
}

// addAll(Arrays.asList(1, 2, 3)) results in addCount = 6, not 3!
```

### Solution: Composition (Wrapper Pattern)

```java
// Forwarding class
public class ForwardingSet<E> implements Set<E> {
    private final Set<E> delegate;

    public ForwardingSet(Set<E> delegate) {
        this.delegate = delegate;
    }

    @Override public int size() { return delegate.size(); }
    @Override public boolean isEmpty() { return delegate.isEmpty(); }
    @Override public boolean contains(Object o) { return delegate.contains(o); }
    @Override public Iterator<E> iterator() { return delegate.iterator(); }
    @Override public boolean add(E e) { return delegate.add(e); }
    @Override public boolean remove(Object o) { return delegate.remove(o); }
    @Override public boolean addAll(Collection<? extends E> c) { return delegate.addAll(c); }
    // ... other Set methods
}

// Instrumented wrapper
public class InstrumentedSet<E> extends ForwardingSet<E> {
    private int addCount = 0;

    public InstrumentedSet(Set<E> delegate) {
        super(delegate);
    }

    @Override
    public boolean add(E e) {
        addCount++;
        return super.add(e);
    }

    @Override
    public boolean addAll(Collection<? extends E> c) {
        addCount += c.size();
        return super.addAll(c);  // Correct: doesn't call our add()
    }

    public int getAddCount() { return addCount; }
}
```

---

## Item 19: Design for Inheritance or Prohibit It

```java
// If you allow inheritance, document self-use
public abstract class AbstractOrderProcessor {

    /**
     * Processes the order.
     *
     * @implSpec This implementation calls {@link #validate(Order)} first,
     * then {@link #execute(Order)}. Subclasses may override either method.
     */
    public final void process(Order order) {
        validate(order);
        execute(order);
        notifyComplete(order);
    }

    /**
     * Validates the order. Can be overridden.
     * @implSpec Default implementation checks order is not null and has items.
     */
    protected void validate(Order order) {
        Objects.requireNonNull(order);
        if (order.getItems().isEmpty()) {
            throw new IllegalArgumentException("Order has no items");
        }
    }

    protected abstract void execute(Order order);

    // Private, cannot be overridden
    private void notifyComplete(Order order) {
        // ...
    }
}

// If inheritance not needed, prohibit it
public final class OrderValidator {
    // Cannot be subclassed
}
```

---

## Item 20: Prefer Interfaces to Abstract Classes

```java
// Interface for flexibility
public interface PaymentProcessor {
    PaymentResult process(Payment payment);

    default boolean supports(PaymentMethod method) {
        return true;  // Default implementation
    }
}

// Skeletal implementation for convenience
public abstract class AbstractPaymentProcessor implements PaymentProcessor {

    @Override
    public final PaymentResult process(Payment payment) {
        validate(payment);
        PaymentResult result = doProcess(payment);
        audit(payment, result);
        return result;
    }

    protected void validate(Payment payment) {
        Objects.requireNonNull(payment);
    }

    protected abstract PaymentResult doProcess(Payment payment);

    protected void audit(Payment payment, PaymentResult result) {
        // Default auditing
    }
}

// Concrete implementation
public class CreditCardProcessor extends AbstractPaymentProcessor {

    @Override
    protected PaymentResult doProcess(Payment payment) {
        // Credit card specific logic
        return new PaymentResult(/* ... */);
    }

    @Override
    public boolean supports(PaymentMethod method) {
        return method == PaymentMethod.CREDIT_CARD;
    }
}
```

---

## Item 22: Use Interfaces Only to Define Types

```java
// BAD - Constant interface antipattern
public interface PhysicalConstants {
    double AVOGADROS_NUMBER = 6.022e23;
    double BOLTZMANN_CONSTANT = 1.38e-23;
}

// GOOD - Utility class or enum for constants
public final class PhysicalConstants {
    private PhysicalConstants() {}  // Prevent instantiation

    public static final double AVOGADROS_NUMBER = 6.022e23;
    public static final double BOLTZMANN_CONSTANT = 1.38e-23;
}

// Or enum for related constants
public enum OrderStatus {
    PENDING("待處理"),
    CONFIRMED("已確認"),
    SHIPPED("已出貨"),
    DELIVERED("已送達"),
    CANCELLED("已取消");

    private final String displayName;

    OrderStatus(String displayName) {
        this.displayName = displayName;
    }

    public String getDisplayName() { return displayName; }
}
```

---

## Item 25: Limit Source Files to a Single Top-Level Class

```java
// BAD - Multiple top-level classes in one file
// Order.java
class Order { }
class OrderItem { }  // Should be in separate file

// GOOD - One top-level class per file
// Order.java
public class Order {
    // Nested class is fine
    public static class Builder { }
}

// OrderItem.java
public class OrderItem { }
```
