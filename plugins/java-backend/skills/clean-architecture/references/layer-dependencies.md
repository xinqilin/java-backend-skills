# Layer Dependencies Guide

## Dependency Matrix

| From \ To | Domain | Application | Infrastructure | Presentation |
|-----------|--------|-------------|----------------|--------------|
| Domain | - | NO | NO | NO |
| Application | YES | - | NO | NO |
| Infrastructure | YES | YES | - | NO |
| Presentation | YES | YES | NO | - |

## Allowed Dependencies by Layer

### Domain Layer

**Can use:**
- Java standard library
- Other domain classes

**Cannot use:**
- Spring Framework annotations
- JPA/Hibernate annotations
- External libraries (Jackson, Lombok for behavior)
- Application layer classes
- Infrastructure classes

```java
// VIOLATION: Using Spring in Domain
@Component  // NO!
public class OrderDomainService {
    @Autowired  // NO!
    private OrderRepository repo;
}

// CORRECT: Pure Java
public class OrderDomainService {
    public Money calculateDiscount(Order order, DiscountPolicy policy) {
        return policy.apply(order.getTotalAmount());
    }
}
```

### Application Layer

**Can use:**
- Domain layer
- Define interfaces (ports)
- Spring `@Service`, `@Transactional`

**Cannot use:**
- Infrastructure implementations
- Presentation DTOs
- External API clients directly

```java
// VIOLATION: Depending on infrastructure implementation
@Service
public class OrderService {
    private final JpaOrderRepository repository;  // NO! Concrete class
    private final RestTemplatePaymentClient client;  // NO!
}

// CORRECT: Depend on ports only
@Service
public class OrderService {
    private final OrderRepository repository;  // Interface (port)
    private final PaymentGateway gateway;  // Interface (port)
}
```

### Infrastructure Layer

**Can use:**
- Domain layer
- Application layer (implement ports)
- Framework-specific code (JPA, HTTP clients)
- External libraries

```java
// Infrastructure implements application ports
@Repository
public class JpaOrderRepository implements OrderRepository {
    // JPA-specific implementation
}

@Component
public class StripePaymentGateway implements PaymentGateway {
    // Stripe SDK usage
}
```

### Presentation Layer

**Can use:**
- Application layer (use cases)
- Domain layer (for response mapping)
- Spring MVC annotations

**Cannot use:**
- Infrastructure implementations
- Direct repository access

```java
// VIOLATION: Controller accessing repository directly
@RestController
public class OrderController {
    private final OrderRepository repository;  // NO!

    @GetMapping("/{id}")
    public Order get(@PathVariable Long id) {
        return repository.findById(id);  // Bypassing use case
    }
}

// CORRECT: Through use case
@RestController
public class OrderController {
    private final GetOrderUseCase getOrderUseCase;

    @GetMapping("/{id}")
    public OrderResponse get(@PathVariable Long id) {
        Order order = getOrderUseCase.execute(new GetOrderQuery(id));
        return OrderResponse.from(order);
    }
}
```

---

## Common Violations and Fixes

### 1. JPA Annotations in Domain

```java
// VIOLATION
package com.example.domain;

@Entity
@Table(name = "orders")
public class Order {
    @Id @GeneratedValue
    private Long id;

    @OneToMany(cascade = CascadeType.ALL)
    private List<OrderItem> items;
}

// FIX: Separate domain and persistence
package com.example.domain;
public class Order {
    private OrderId id;
    private List<OrderItem> items;
}

package com.example.infrastructure.persistence;
@Entity
@Table(name = "orders")
public class OrderEntity {
    @Id @GeneratedValue
    private Long id;
}
```

### 2. Service Depends on Controller DTO

```java
// VIOLATION
@Service
public class OrderService {
    public Order create(CreateOrderRequest request) {  // Controller DTO!
        // ...
    }
}

// FIX: Use application-layer command
@Service
public class OrderService {
    public Order create(CreateOrderCommand command) {
        // ...
    }
}

// Controller maps request to command
@PostMapping
public OrderResponse create(@RequestBody CreateOrderRequest request) {
    return orderService.create(request.toCommand());
}
```

### 3. Domain Calling External Service

```java
// VIOLATION
public class Order {
    public void complete(PaymentService paymentService) {
        paymentService.charge(this.total);  // Domain calling infrastructure!
        this.status = COMPLETED;
    }
}

// FIX: Domain emits events, application orchestrates
public class Order {
    public OrderCompletedEvent complete() {
        this.status = COMPLETED;
        return new OrderCompletedEvent(this.id, this.total);
    }
}

@Service
public class CompleteOrderService {
    public void execute(OrderId id) {
        Order order = repository.findById(id);
        OrderCompletedEvent event = order.complete();
        paymentGateway.charge(event.amount());
        repository.save(order);
    }
}
```

---

## Package Structure Enforcement

### Using ArchUnit for Validation

```java
@AnalyzeClasses(packages = "com.example")
public class ArchitectureTest {

    @ArchTest
    static final ArchRule domain_should_not_depend_on_infrastructure =
        noClasses()
            .that().resideInAPackage("..domain..")
            .should().dependOnClassesThat()
            .resideInAPackage("..infrastructure..");

    @ArchTest
    static final ArchRule domain_should_not_use_spring =
        noClasses()
            .that().resideInAPackage("..domain..")
            .should().dependOnClassesThat()
            .resideInAPackage("org.springframework..");

    @ArchTest
    static final ArchRule controllers_should_only_use_usecases =
        classes()
            .that().resideInAPackage("..presentation..")
            .should().onlyDependOnClassesThat()
            .resideInAnyPackage(
                "..presentation..",
                "..application.port.in..",
                "..domain.model..",
                "java..",
                "org.springframework.web.."
            );
}
```

---

## Dependency Injection Configuration

### Proper Wiring

```java
@Configuration
public class OrderConfig {

    @Bean
    public CreateOrderUseCase createOrderUseCase(
            OrderRepository orderRepository,
            CustomerRepository customerRepository) {
        return new CreateOrderService(orderRepository, customerRepository);
    }
}

@Configuration
public class PersistenceConfig {

    @Bean
    public OrderRepository orderRepository(
            OrderJpaRepository jpaRepository,
            OrderMapper mapper) {
        return new JpaOrderRepository(jpaRepository, mapper);
    }
}
```

This ensures:
- Application layer defines what it needs (ports)
- Infrastructure layer provides implementations
- Configuration wires them together
- No layer directly instantiates another layer's implementation
