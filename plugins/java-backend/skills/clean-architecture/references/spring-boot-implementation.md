# Spring Boot Clean Architecture Implementation

## Complete Project Template

```
src/
├── main/
│   ├── java/com/example/order/
│   │   ├── OrderApplication.java
│   │   ├── domain/
│   │   │   ├── model/
│   │   │   │   ├── Order.java
│   │   │   │   ├── OrderId.java
│   │   │   │   ├── OrderItem.java
│   │   │   │   ├── OrderStatus.java
│   │   │   │   ├── Money.java
│   │   │   │   └── Customer.java
│   │   │   ├── service/
│   │   │   │   └── OrderDomainService.java
│   │   │   ├── event/
│   │   │   │   └── OrderCreatedEvent.java
│   │   │   └── exception/
│   │   │       ├── OrderNotFoundException.java
│   │   │       └── InvalidOrderStateException.java
│   │   ├── application/
│   │   │   ├── port/
│   │   │   │   ├── in/
│   │   │   │   │   ├── CreateOrderUseCase.java
│   │   │   │   │   ├── GetOrderUseCase.java
│   │   │   │   │   └── CancelOrderUseCase.java
│   │   │   │   └── out/
│   │   │   │       ├── OrderRepository.java
│   │   │   │       ├── CustomerRepository.java
│   │   │   │       └── EventPublisher.java
│   │   │   ├── service/
│   │   │   │   ├── CreateOrderService.java
│   │   │   │   ├── GetOrderService.java
│   │   │   │   └── CancelOrderService.java
│   │   │   └── dto/
│   │   │       ├── CreateOrderCommand.java
│   │   │       ├── OrderResult.java
│   │   │       └── GetOrderQuery.java
│   │   ├── infrastructure/
│   │   │   ├── persistence/
│   │   │   │   ├── entity/
│   │   │   │   │   ├── OrderEntity.java
│   │   │   │   │   └── OrderItemEntity.java
│   │   │   │   ├── repository/
│   │   │   │   │   ├── OrderJpaRepository.java
│   │   │   │   │   └── JpaOrderRepositoryAdapter.java
│   │   │   │   └── mapper/
│   │   │   │       └── OrderPersistenceMapper.java
│   │   │   ├── messaging/
│   │   │   │   └── SpringEventPublisher.java
│   │   │   └── config/
│   │   │       ├── PersistenceConfig.java
│   │   │       └── ApplicationConfig.java
│   │   └── presentation/
│   │       ├── controller/
│   │       │   └── OrderController.java
│   │       ├── request/
│   │       │   └── CreateOrderRequest.java
│   │       ├── response/
│   │       │   └── OrderResponse.java
│   │       └── exception/
│   │           └── GlobalExceptionHandler.java
│   └── resources/
│       └── application.yml
└── test/
    └── java/com/example/order/
        ├── domain/
        │   └── model/OrderTest.java
        ├── application/
        │   └── service/CreateOrderServiceTest.java
        ├── infrastructure/
        │   └── persistence/JpaOrderRepositoryAdapterTest.java
        └── presentation/
            └── controller/OrderControllerTest.java
```

---

## Layer Code Templates

### Domain Layer

```java
// domain/model/Order.java
public class Order {
    private final OrderId id;
    private final CustomerId customerId;
    private final List<OrderItem> items;
    private Money totalAmount;
    private OrderStatus status;
    private final LocalDateTime createdAt;

    private Order(OrderId id, CustomerId customerId, List<OrderItem> items) {
        this.id = id;
        this.customerId = customerId;
        this.items = new ArrayList<>(items);
        this.totalAmount = calculateTotal();
        this.status = OrderStatus.PENDING;
        this.createdAt = LocalDateTime.now();
    }

    public static Order create(CustomerId customerId, List<OrderItem> items) {
        if (items.isEmpty()) {
            throw new IllegalArgumentException("Order must have at least one item");
        }
        return new Order(OrderId.generate(), customerId, items);
    }

    public void confirm() {
        if (status != OrderStatus.PENDING) {
            throw new InvalidOrderStateException("Cannot confirm non-pending order");
        }
        this.status = OrderStatus.CONFIRMED;
    }

    public void cancel() {
        if (status == OrderStatus.SHIPPED) {
            throw new InvalidOrderStateException("Cannot cancel shipped order");
        }
        this.status = OrderStatus.CANCELLED;
    }

    private Money calculateTotal() {
        return items.stream()
            .map(OrderItem::subtotal)
            .reduce(Money.ZERO, Money::add);
    }

    // Getters only - no setters
    public OrderId getId() { return id; }
    public OrderStatus getStatus() { return status; }
    public Money getTotalAmount() { return totalAmount; }
    public List<OrderItem> getItems() { return Collections.unmodifiableList(items); }
}

// domain/model/OrderId.java
public record OrderId(String value) {
    public OrderId {
        Objects.requireNonNull(value, "OrderId cannot be null");
    }

    public static OrderId generate() {
        return new OrderId(UUID.randomUUID().toString());
    }

    public static OrderId of(String value) {
        return new OrderId(value);
    }
}

// domain/model/Money.java
public record Money(BigDecimal amount, Currency currency) {
    public static final Money ZERO = new Money(BigDecimal.ZERO, Currency.getInstance("TWD"));

    public Money {
        Objects.requireNonNull(amount);
        Objects.requireNonNull(currency);
        if (amount.compareTo(BigDecimal.ZERO) < 0) {
            throw new IllegalArgumentException("Amount cannot be negative");
        }
    }

    public Money add(Money other) {
        if (!this.currency.equals(other.currency)) {
            throw new IllegalArgumentException("Cannot add different currencies");
        }
        return new Money(this.amount.add(other.amount), this.currency);
    }

    public Money multiply(int quantity) {
        return new Money(this.amount.multiply(BigDecimal.valueOf(quantity)), this.currency);
    }
}
```

### Application Layer

```java
// application/port/in/CreateOrderUseCase.java
public interface CreateOrderUseCase {
    OrderResult execute(CreateOrderCommand command);
}

// application/port/out/OrderRepository.java
public interface OrderRepository {
    void save(Order order);
    Optional<Order> findById(OrderId id);
    List<Order> findByCustomerId(CustomerId customerId);
}

// application/dto/CreateOrderCommand.java
public record CreateOrderCommand(
    CustomerId customerId,
    List<OrderItemCommand> items
) {
    public record OrderItemCommand(ProductId productId, int quantity, Money price) {}
}

// application/service/CreateOrderService.java
@Service
@Transactional
public class CreateOrderService implements CreateOrderUseCase {
    private final OrderRepository orderRepository;
    private final CustomerRepository customerRepository;
    private final EventPublisher eventPublisher;

    public CreateOrderService(
            OrderRepository orderRepository,
            CustomerRepository customerRepository,
            EventPublisher eventPublisher) {
        this.orderRepository = orderRepository;
        this.customerRepository = customerRepository;
        this.eventPublisher = eventPublisher;
    }

    @Override
    public OrderResult execute(CreateOrderCommand command) {
        // Validate customer exists
        customerRepository.findById(command.customerId())
            .orElseThrow(() -> new CustomerNotFoundException(command.customerId()));

        // Create domain object
        List<OrderItem> items = command.items().stream()
            .map(i -> new OrderItem(i.productId(), i.quantity(), i.price()))
            .toList();

        Order order = Order.create(command.customerId(), items);

        // Persist
        orderRepository.save(order);

        // Publish event
        eventPublisher.publish(new OrderCreatedEvent(order.getId(), order.getTotalAmount()));

        return new OrderResult(order.getId(), order.getStatus(), order.getTotalAmount());
    }
}
```

### Infrastructure Layer

```java
// infrastructure/persistence/entity/OrderEntity.java
@Entity
@Table(name = "orders")
public class OrderEntity {
    @Id
    private String id;

    @Column(name = "customer_id", nullable = false)
    private String customerId;

    @Column(name = "total_amount", nullable = false)
    private BigDecimal totalAmount;

    @Column(name = "currency", nullable = false)
    private String currency;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private OrderStatus status;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    @OneToMany(mappedBy = "order", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<OrderItemEntity> items = new ArrayList<>();

    // JPA requires default constructor
    protected OrderEntity() {}

    // Getters and setters for JPA
}

// infrastructure/persistence/repository/JpaOrderRepositoryAdapter.java
@Repository
public class JpaOrderRepositoryAdapter implements OrderRepository {
    private final OrderJpaRepository jpaRepository;
    private final OrderPersistenceMapper mapper;

    public JpaOrderRepositoryAdapter(
            OrderJpaRepository jpaRepository,
            OrderPersistenceMapper mapper) {
        this.jpaRepository = jpaRepository;
        this.mapper = mapper;
    }

    @Override
    public void save(Order order) {
        OrderEntity entity = mapper.toEntity(order);
        jpaRepository.save(entity);
    }

    @Override
    public Optional<Order> findById(OrderId id) {
        return jpaRepository.findById(id.value())
            .map(mapper::toDomain);
    }

    @Override
    public List<Order> findByCustomerId(CustomerId customerId) {
        return jpaRepository.findByCustomerId(customerId.value())
            .stream()
            .map(mapper::toDomain)
            .toList();
    }
}

// infrastructure/persistence/mapper/OrderPersistenceMapper.java
@Component
public class OrderPersistenceMapper {

    public OrderEntity toEntity(Order order) {
        OrderEntity entity = new OrderEntity();
        entity.setId(order.getId().value());
        entity.setCustomerId(order.getCustomerId().value());
        entity.setTotalAmount(order.getTotalAmount().amount());
        entity.setCurrency(order.getTotalAmount().currency().getCurrencyCode());
        entity.setStatus(order.getStatus());
        entity.setCreatedAt(order.getCreatedAt());

        List<OrderItemEntity> itemEntities = order.getItems().stream()
            .map(item -> toItemEntity(item, entity))
            .toList();
        entity.setItems(itemEntities);

        return entity;
    }

    public Order toDomain(OrderEntity entity) {
        List<OrderItem> items = entity.getItems().stream()
            .map(this::toItemDomain)
            .toList();

        return Order.reconstitute(
            OrderId.of(entity.getId()),
            CustomerId.of(entity.getCustomerId()),
            items,
            new Money(entity.getTotalAmount(), Currency.getInstance(entity.getCurrency())),
            entity.getStatus(),
            entity.getCreatedAt()
        );
    }
}
```

### Presentation Layer

```java
// presentation/controller/OrderController.java
@RestController
@RequestMapping("/api/v1/orders")
public class OrderController {
    private final CreateOrderUseCase createOrderUseCase;
    private final GetOrderUseCase getOrderUseCase;
    private final CancelOrderUseCase cancelOrderUseCase;

    public OrderController(
            CreateOrderUseCase createOrderUseCase,
            GetOrderUseCase getOrderUseCase,
            CancelOrderUseCase cancelOrderUseCase) {
        this.createOrderUseCase = createOrderUseCase;
        this.getOrderUseCase = getOrderUseCase;
        this.cancelOrderUseCase = cancelOrderUseCase;
    }

    @PostMapping
    public ResponseEntity<OrderResponse> createOrder(
            @Valid @RequestBody CreateOrderRequest request) {
        CreateOrderCommand command = request.toCommand();
        OrderResult result = createOrderUseCase.execute(command);
        return ResponseEntity
            .created(URI.create("/api/v1/orders/" + result.orderId().value()))
            .body(OrderResponse.from(result));
    }

    @GetMapping("/{orderId}")
    public ResponseEntity<OrderResponse> getOrder(@PathVariable String orderId) {
        OrderResult result = getOrderUseCase.execute(new GetOrderQuery(OrderId.of(orderId)));
        return ResponseEntity.ok(OrderResponse.from(result));
    }

    @DeleteMapping("/{orderId}")
    public ResponseEntity<Void> cancelOrder(@PathVariable String orderId) {
        cancelOrderUseCase.execute(OrderId.of(orderId));
        return ResponseEntity.noContent().build();
    }
}

// presentation/request/CreateOrderRequest.java
public record CreateOrderRequest(
    @NotBlank String customerId,
    @NotEmpty List<OrderItemRequest> items
) {
    public record OrderItemRequest(
        @NotBlank String productId,
        @Min(1) int quantity,
        @NotNull BigDecimal price
    ) {}

    public CreateOrderCommand toCommand() {
        List<CreateOrderCommand.OrderItemCommand> itemCommands = items.stream()
            .map(i -> new CreateOrderCommand.OrderItemCommand(
                ProductId.of(i.productId()),
                i.quantity(),
                new Money(i.price(), Currency.getInstance("TWD"))
            ))
            .toList();

        return new CreateOrderCommand(CustomerId.of(customerId), itemCommands);
    }
}

// presentation/response/OrderResponse.java
public record OrderResponse(
    String orderId,
    String status,
    BigDecimal totalAmount,
    String currency
) {
    public static OrderResponse from(OrderResult result) {
        return new OrderResponse(
            result.orderId().value(),
            result.status().name(),
            result.totalAmount().amount(),
            result.totalAmount().currency().getCurrencyCode()
        );
    }
}

// presentation/exception/GlobalExceptionHandler.java
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(OrderNotFoundException.class)
    public ResponseEntity<ErrorResponse> handleOrderNotFound(OrderNotFoundException ex) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
            .body(new ErrorResponse("ORDER_NOT_FOUND", ex.getMessage()));
    }

    @ExceptionHandler(InvalidOrderStateException.class)
    public ResponseEntity<ErrorResponse> handleInvalidState(InvalidOrderStateException ex) {
        return ResponseEntity.status(HttpStatus.CONFLICT)
            .body(new ErrorResponse("INVALID_ORDER_STATE", ex.getMessage()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ErrorResponse> handleValidation(MethodArgumentNotValidException ex) {
        String message = ex.getBindingResult().getFieldErrors().stream()
            .map(e -> e.getField() + ": " + e.getDefaultMessage())
            .collect(Collectors.joining(", "));
        return ResponseEntity.badRequest()
            .body(new ErrorResponse("VALIDATION_ERROR", message));
    }
}
```

### Configuration

```java
// infrastructure/config/ApplicationConfig.java
@Configuration
public class ApplicationConfig {

    @Bean
    public CreateOrderUseCase createOrderUseCase(
            OrderRepository orderRepository,
            CustomerRepository customerRepository,
            EventPublisher eventPublisher) {
        return new CreateOrderService(orderRepository, customerRepository, eventPublisher);
    }

    @Bean
    public GetOrderUseCase getOrderUseCase(OrderRepository orderRepository) {
        return new GetOrderService(orderRepository);
    }

    @Bean
    public CancelOrderUseCase cancelOrderUseCase(OrderRepository orderRepository) {
        return new CancelOrderService(orderRepository);
    }
}
```
