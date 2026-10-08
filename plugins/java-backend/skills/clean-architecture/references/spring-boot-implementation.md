# Spring Boot Templates: Pragmatic Default and Strict Variant

Both templates compile on Spring Boot 4.1 (Hibernate 7.4, Java 21), and the ArchUnit rules in `layer-dependencies.md` pass on them. Imports are left out below.

## Pragmatic template

### Package layout

```
com.example.shop
├── order
│   ├── domain          Order, OrderLine, Money, NewLine, OrderStatus, OrderCancelled,
│   │                   OrderRepository, OrderNotFoundException, OrderStateException
│   ├── application     OrderService, PlaceOrderCommand, OrderSummary, OrderCancelledListener,
│   │                   CheckoutService, PaymentSteps, PaymentGateway (port), PaymentRequest, PaymentResult
│   └── web             OrderController, PlaceOrderRequest, OrderExceptionHandler
└── infrastructure      HttpPaymentGateway
```

Package by feature first (`order`), then by layer. A feature's classes stay together, and the layers stay visible to ArchUnit.

### Domain

```java
@Entity
@Table(name = "orders")
public class Order extends AbstractAggregateRoot<Order> {

    @Id
    private UUID id;

    @Version
    private Long version; // null until persisted, so save() persists without a SELECT

    @Column(nullable = false)
    private UUID customerId;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private OrderStatus status;

    @Embedded
    private Money total;

    private UUID paymentKey; // idempotency key sent to the payment provider

    @OneToMany(mappedBy = "order", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<OrderLine> lines = new ArrayList<>();

    protected Order() { // for JPA
    }

    public static Order place(UUID customerId, List<NewLine> newLines) {
        if (newLines.isEmpty()) {
            throw new IllegalArgumentException("an order needs at least one line");
        }
        Order order = new Order();
        order.id = UUID.randomUUID();
        order.customerId = customerId;
        order.status = OrderStatus.PENDING;
        newLines.forEach(line -> order.lines.add(new OrderLine(order, line)));
        order.total = order.lines.stream().map(OrderLine::subtotal).reduce(Money::add).orElseThrow();
        return order;
    }

    public UUID startPayment() {
        requireStatus(OrderStatus.PENDING, "pay");
        status = OrderStatus.PAYMENT_PENDING;
        paymentKey = UUID.randomUUID();
        return paymentKey;
    }

    public void completePayment(boolean succeeded) {
        requireStatus(OrderStatus.PAYMENT_PENDING, "complete payment for");
        status = succeeded ? OrderStatus.PAID : OrderStatus.PAYMENT_FAILED;
    }

    public void cancel() {
        requireStatus(OrderStatus.PENDING, "cancel");
        status = OrderStatus.CANCELLED;
        registerEvent(new OrderCancelled(id)); // published by the next repository save()
    }

    private void requireStatus(OrderStatus expected, String action) {
        if (status != expected) {
            throw new OrderStateException(id, status, action);
        }
    }

    public List<OrderLine> getLines() {
        return Collections.unmodifiableList(lines);
    }

    // getId(), getStatus(), getTotal()
}

@Entity
@Table(name = "order_lines")
public class OrderLine {

    @Id
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    private Order order;

    @Column(nullable = false, length = 40)
    private String sku;

    private int quantity;

    @Embedded
    private Money unitPrice;

    protected OrderLine() {
    }

    OrderLine(Order order, NewLine line) {
        if (line.quantity() <= 0) {
            throw new IllegalArgumentException("quantity must be positive: " + line.quantity());
        }
        this.id = UUID.randomUUID();
        this.order = order;
        this.sku = line.sku();
        this.quantity = line.quantity();
        this.unitPrice = line.unitPrice();
    }

    Money subtotal() {
        return unitPrice.times(quantity);
    }

    // getSku(), getQuantity(), getUnitPrice()
}

public interface OrderRepository extends Repository<Order, UUID> {

    Optional<Order> findById(UUID id);

    <S extends Order> S save(S order);
}
```

- `Money` is the `@Embeddable` record from `java-backend:effective-java`. It fixes the `BigDecimal` scale per currency, so equal amounts are `equals`.
- `@Version Long version` serves twice. While it is `null`, Spring Data's `save()` knows the entity is new, even with an assigned UUID, and persists it without a `SELECT`. A concurrent update fails at commit with `ObjectOptimisticLockingFailureException`, which the web layer maps to 409.
- `protected Order()` exists only for JPA. `place(...)` is the only way to create an order, and the state changes are methods that check the current status.
- `OrderRepository` extends `Repository` and declares only `findById` and `save`. These signatures match `CrudRepository`'s, so Spring Data routes them to its implementation. Use cases can't call `deleteAll` or an unpaged `findAll`.
- `registerEvent(...)` queues `OrderCancelled`. Only a repository `save` or `delete` publishes it.

### Application

```java
@Service
public class OrderService {

    private final OrderRepository orders;

    public OrderService(OrderRepository orders) {
        this.orders = orders;
    }

    @Transactional
    public UUID place(PlaceOrderCommand command) {
        Order order = Order.place(command.customerId(), command.lines());
        return orders.save(order).getId();
    }

    @Transactional
    public void cancel(UUID orderId) {
        Order order = load(orderId);
        order.cancel();
        orders.save(order); // dirty checking writes the change anyway; save() publishes OrderCancelled
    }

    @Transactional(readOnly = true)
    public OrderSummary get(UUID orderId) {
        return OrderSummary.from(load(orderId)); // lines are read inside the transaction
    }

    private Order load(UUID orderId) {
        return orders.findById(orderId).orElseThrow(() -> new OrderNotFoundException(orderId));
    }
}

public record PlaceOrderCommand(UUID customerId, List<NewLine> lines) {
}

public record OrderSummary(UUID id, OrderStatus status, Money total, List<String> skus) {

    static OrderSummary from(Order order) {
        return new OrderSummary(order.getId(), order.getStatus(), order.getTotal(),
                order.getLines().stream().map(OrderLine::getSku).toList());
    }
}

@Component
class OrderCancelledListener {

    @TransactionalEventListener // AFTER_COMMIT by default: runs only if the cancellation committed
    void on(OrderCancelled event) {
        log.info("order {} cancelled", event.orderId()); // in-process only; other systems need an outbox
    }
}
```

- Each use case method declares its own transaction. `readOnly = true` on reads switches Hibernate to manual flush and skips dirty-checking snapshots (`java-backend:jpa-hibernate`).
- `get()` maps the aggregate inside the transaction, so it works with `spring.jpa.open-in-view=false`.
- The checkout flow (`CheckoutService`, `PaymentSteps`, and the `PaymentGateway` port) is in `layer-dependencies.md`, section 3.

### Web

```java
@RestController
@RequestMapping("/orders")
class OrderController {

    private final OrderService orders;
    private final CheckoutService checkout;

    OrderController(OrderService orders, CheckoutService checkout) {
        this.orders = orders;
        this.checkout = checkout;
    }

    @PostMapping
    ResponseEntity<Void> place(@Valid @RequestBody PlaceOrderRequest request) {
        UUID id = orders.place(request.toCommand());
        return ResponseEntity.created(URI.create("/orders/" + id)).build();
    }

    @GetMapping("/{id}")
    OrderSummary get(@PathVariable UUID id) {
        return orders.get(id);
    }

    @PostMapping("/{id}/cancel")
    ResponseEntity<Void> cancel(@PathVariable UUID id) {
        orders.cancel(id);
        return ResponseEntity.noContent().build();
    }

    @PostMapping("/{id}/checkout")
    ResponseEntity<Void> checkout(@PathVariable UUID id) {
        checkout.checkout(id);
        return ResponseEntity.noContent().build();
    }
}

record PlaceOrderRequest(
        @NotNull UUID customerId,
        @NotBlank @Size(min = 3, max = 3) String currency,
        @NotEmpty List<@Valid Line> lines) {

    record Line(@NotBlank String sku, @Positive int quantity, @NotNull @Positive BigDecimal unitPrice) {
    }

    PlaceOrderCommand toCommand() {
        Currency orderCurrency = Currency.getInstance(currency);
        return new PlaceOrderCommand(customerId, lines.stream()
                .map(line -> new NewLine(line.sku(), line.quantity(), new Money(line.unitPrice(), orderCurrency)))
                .toList());
    }
}

@RestControllerAdvice
class OrderExceptionHandler {

    @ExceptionHandler(OrderNotFoundException.class)
    ProblemDetail notFound(OrderNotFoundException e) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.NOT_FOUND, e.getMessage());
    }

    @ExceptionHandler(OrderStateException.class)
    ProblemDetail invalidState(OrderStateException e) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT, e.getMessage());
    }

    @ExceptionHandler(ObjectOptimisticLockingFailureException.class)
    ProblemDetail concurrentUpdate(ObjectOptimisticLockingFailureException e) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT,
                "the order was changed by another request; reload it and retry");
    }

    @ExceptionHandler(IllegalArgumentException.class)
    ProblemDetail invalidInput(IllegalArgumentException e) {
        return ProblemDetail.forStatusAndDetail(HttpStatus.BAD_REQUEST, e.getMessage());
    }
}
```

- An `@ExceptionHandler` that returns `ProblemDetail` renders an RFC 9457 body (`application/problem+json`). Set `spring.mvc.problemdetails.enabled=true` so that Spring MVC's own exceptions, such as validation failures, use the same format. The property defaults to `false`.
- `@Valid` checks the request's shape. The domain checks its invariants: `Money` rejects more decimals than the currency allows, and a line rejects a non-positive quantity.
- Mapping `IllegalArgumentException` to 400 assumes that domain code throws it only for invalid input. If the codebase also throws it for bugs, introduce a dedicated exception instead.
- The `ObjectOptimisticLockingFailureException` handler works because the commit happens inside the `orders.cancel(id)` call, in the service's transaction proxy.

## Strict variant: what changes

Only persistence changes. Controllers look the same, and use cases call a port instead of a Spring Data repository, and must always save.

### A domain without JPA

```java
public class Order {

    private final UUID id;
    private final Long version; // null for a new order; carried so the adapter keeps optimistic locking
    private final UUID customerId;
    private final List<OrderLine> lines;
    private OrderStatus status;

    public static Order place(UUID customerId, List<OrderLine> lines) {
        if (lines.isEmpty()) {
            throw new IllegalArgumentException("an order needs at least one line");
        }
        return new Order(UUID.randomUUID(), null, customerId, OrderStatus.PENDING, lines);
    }

    // Only for the persistence adapter: rebuilds an order that already exists.
    public static Order reconstitute(UUID id, Long version, UUID customerId, OrderStatus status,
            List<OrderLine> lines) {
        return new Order(id, version, customerId, status, lines);
    }

    // private constructor, cancel(), total(), and accessors id(), version(), customerId(), status(), lines()
}

public record OrderLine(UUID id, String sku, int quantity, Money unitPrice) {
}
```

### Port and use case

```java
public interface OrderStore {

    Optional<Order> find(UUID id);

    void save(Order order);
}

@Transactional
public void cancel(UUID orderId) {
    Order order = store.find(orderId).orElseThrow(() -> new OrderNotFoundException(orderId));
    order.cancel();
    store.save(order); // required: nothing tracks changes on a plain domain object
}
```

### Adapter and JPA entity

```java
@Entity
@Table(name = "orders")
class OrderJpaEntity {

    @Id
    private UUID id;

    @Version
    private Long version;

    // customerId, status, and @OneToMany(mappedBy = "order", cascade = ALL, orphanRemoval = true) lines

    static OrderJpaEntity from(Order order) {
        OrderJpaEntity entity = new OrderJpaEntity();
        entity.id = order.id();
        entity.version = order.version(); // null: persist; otherwise merge checks it against the database
        entity.customerId = order.customerId();
        entity.status = order.status();
        order.lines().forEach(line -> entity.lines.add(OrderLineJpaEntity.from(line, entity)));
        return entity;
    }

    Order toDomain() {
        return Order.reconstitute(id, version, customerId, status,
                lines.stream().map(OrderLineJpaEntity::toDomain).toList()); // always loads the lines
    }
}

@Component
class JpaOrderStore implements OrderStore {

    private final OrderJpaRepository jpa; // extends JpaRepository<OrderJpaEntity, UUID>

    @Override
    public Optional<Order> find(UUID id) {
        return jpa.findById(id).map(OrderJpaEntity::toDomain);
    }

    @Override
    public void save(Order order) {
        // A new order (version null) is persisted. An existing one is merged: Hibernate throws
        // StaleObjectStateException, translated to ObjectOptimisticLockingFailureException,
        // when the carried version no longer matches.
        jpa.save(OrderJpaEntity.from(order));
    }
}
```

What this costs compared with the pragmatic template:

- In `cancel()`, `find()` already loaded the order and its lines into the persistence context, so `merge` copies onto those managed instances. A line added in the use case costs a `SELECT` before its `INSERT`, because its assigned id looks existing.
- `toDomain()` reads the lines on every load, whether the use case needs them or not.
- After a flush, the domain object's version is stale. Saving it a second time in the same transaction fails with an optimistic-locking error, so save each aggregate once, at the end of the use case.
- The domain can't extend `AbstractAggregateRoot`, so the use case publishes events itself (`ApplicationEventPublisher`).

## Bean registration

Both templates use component scanning only: `@Service`, `@Component`, and `@RestController` on the classes, and no `@Bean` methods that create the same classes again (`layer-dependencies.md`, section 5).

## Testing

- Domain rules (`Order.place`, `cancel`, `Money`): plain unit tests without Spring.
- Repositories and use cases against the real database engine: `java-backend:java-testing`.
- Layering: the ArchUnit rules in `layer-dependencies.md`.

## Sources

- Robert C. Martin, *Clean Architecture* (2017), ch. 22 "The Clean Architecture"
- Spring Data JPA reference, Fine-tuning Repository Definition (selectively exposing CRUD methods): https://docs.spring.io/spring-data/jpa/reference/repositories/definition.html
- Spring Data reference, Publishing Events from Aggregate Roots: https://docs.spring.io/spring-data/jpa/reference/repositories/core-domain-events.html
- Spring Data Commons Javadoc, `AbstractAggregateRoot`: https://docs.spring.io/spring-data/commons/docs/current/api/org/springframework/data/domain/AbstractAggregateRoot.html
- Spring Data JPA, Persisting Entities (entity state detection): https://docs.spring.io/spring-data/jpa/reference/jpa/entity-persistence.html
- Spring Framework reference, Error Responses (`ProblemDetail`, RFC 9457): https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-ann-rest-exceptions.html
- Spring Boot application properties (`spring.mvc.problemdetails.enabled`): https://docs.spring.io/spring-boot/appendix/application-properties/index.html
- Spring Boot reference, Structuring Your Code: https://docs.spring.io/spring-boot/reference/using/structuring-your-code.html
- Hibernate ORM 7.4.5 source, `DefaultMergeEventListener` (version check on merge): https://github.com/hibernate/hibernate-orm/blob/7.4.5/hibernate-core/src/main/java/org/hibernate/event/internal/DefaultMergeEventListener.java
