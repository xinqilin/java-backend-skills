# Layer Dependencies

The rules below and the ArchUnit tests at the end compile on Spring Boot 4.1 (Java 21). The tests were run with ArchUnit 1.5.1 on JUnit 6. They pass on the templates in `spring-boot-implementation.md` and fail on deliberate violations.

## Dependency matrix

| From \ To | Domain | Application | Web | Infrastructure |
|-----------|--------|-------------|-----|----------------|
| Domain | - | No | No | No |
| Application | Yes | - | No | No |
| Web | Yes | Yes | - | No |
| Infrastructure | Yes | Yes | No | - |

Web and infrastructure are both outer adapters: they depend inward and never on each other. Spring does the wiring. The application layer declares an interface (`PaymentGateway`), infrastructure implements it, and component scanning connects the two.

## Allowed framework dependencies

| Layer | Pragmatic (default) | Strict |
|---|---|---|
| Domain | `jakarta.persistence`; `org.springframework.data` (repository interfaces, `AbstractAggregateRoot`, `Pageable`) | JDK only |
| Application | Spring stereotypes, `@Transactional`, `ApplicationEventPublisher`; no web or JDBC types | Same |
| Web | Spring MVC, `jakarta.validation`, `ProblemDetail`, Spring's data-access exceptions for error mapping | Same |
| Infrastructure | Anything: HTTP clients, JDBC, JPA, messaging | Same, plus the JPA entities and mappers |

Lombok is a compile-time tool and fits any layer, but keep `@Data` and `@EqualsAndHashCode` off entities (`java-backend:jpa-hibernate`).

## Violations and fixes

### 1. A use case that takes a web DTO

```java
// VIOLATION: the application layer depends on the web layer
@Transactional
public UUID place(PlaceOrderRequest request) { ... }
```

The controller maps the request to an application command, and the use case takes the command:

```java
@PostMapping
ResponseEntity<Void> place(@Valid @RequestBody PlaceOrderRequest request) {
    UUID id = orders.place(request.toCommand());
    return ResponseEntity.created(URI.create("/orders/" + id)).build();
}
```

### 2. A controller that reads through a repository

```java
// VIOLATION: no transaction around the mapping, so lazy lines fail when open-in-view is off
@GetMapping("/{id}")
OrderSummary get(@PathVariable UUID id) {
    return OrderSummary.from(orderRepository.findById(id).orElseThrow());
}
```

A read-only use case loads and maps the aggregate inside its own transaction:

```java
@Transactional(readOnly = true)
public OrderSummary get(UUID orderId) {
    return OrderSummary.from(load(orderId)); // lines are read inside the transaction
}
```

### 3. A payment inside the order transaction

```java
// VIOLATION: the domain calls a remote service
public void pay(PaymentClient client) {
    client.charge(total);
    status = OrderStatus.PAID;
}
```

Moving the call into a `@Transactional` application service ("charge, then save") is no fix. It is a dual write. If the commit fails after the charge succeeded, the customer has paid for an order the database doesn't know is paid. Meanwhile, the remote call holds the transaction's connection and row locks while it waits.

Split it into two short transactions around a call made with an idempotency key:

```java
@Service
public class CheckoutService {

    // Not @Transactional: the remote call must not hold a database transaction open.
    public void checkout(UUID orderId) {
        PaymentRequest request = steps.start(orderId);                                    // transaction 1
        PaymentResult result = gateway.charge(request.idempotencyKey(), request.amount()); // no transaction
        steps.finish(orderId, result);                                                    // transaction 2
    }
}

@Service
public class PaymentSteps {

    @Transactional
    public PaymentRequest start(UUID orderId) {
        Order order = load(orderId);
        UUID key = order.startPayment(); // PAYMENT_PENDING and the key are committed before the call
        return new PaymentRequest(key, order.getTotal());
    }

    @Transactional
    public void finish(UUID orderId, PaymentResult result) {
        load(orderId).completePayment(result.succeeded());
    }
}
```

- Transaction 1 commits `PAYMENT_PENDING` and the idempotency key before any money moves.
- The charge runs outside any transaction. Send the key through the provider's idempotency mechanism, often an `Idempotency-Key` header, so a retry with the same key can't charge twice.
- Transaction 2 records the result.
- If the process dies between the call and transaction 2, or the call times out, the order stays `PAYMENT_PENDING`. A scheduled job retries those orders with the stored key, then records the result.
- `checkout()` lives on a different bean than the two `@Transactional` methods, so each call goes through the transaction proxy. A self-invocation would run both steps without transactions.
- For idempotency keys and the outbox in depth, see `java-backend:transactions-consistency` (`references/distributed-data.md`).

### 4. A strict-variant adapter that drops the version

```java
// VIOLATION: a JPA entity without @Version, rebuilt from the domain object on every save.
// merge copies its state over whatever is in the database: a concurrent update is lost.
jpa.save(OrderJpaEntity.from(order));
```

Give the JPA entity a `@Version Long version`, carry it in the domain object, and copy it in the mapper. A `null` version makes `save()` persist a new order without a `SELECT`. A stale version makes `merge` throw `StaleObjectStateException`, which Spring translates to `ObjectOptimisticLockingFailureException`. See `spring-boot-implementation.md`.

### 5. One class registered as two beans

```java
@Service
public class CreateOrderService implements CreateOrderUseCase { ... }

@Configuration
class ApplicationConfig {

    @Bean
    CreateOrderUseCase createOrderUseCase(OrderStore store) {
        return new CreateOrderService(store); // a second bean of the same type
    }
}
```

There are now two beans, `createOrderService` and `createOrderUseCase`. Injecting `CreateOrderUseCase` by type fails with `NoUniqueBeanDefinitionException`, unless a parameter name matches one of the bean names. In that case Spring silently picks that bean, and the other instance sits unused. Register each class one way: component scanning (the default here), or `@Bean` methods for an application layer kept free of Spring annotations.

## ArchUnit rules

On Spring Boot 4 (JUnit 6), add `com.tngtech.archunit:archunit-junit6` (ArchUnit 1.5+) with test scope. On Spring Boot 3 (JUnit 5), add `archunit-junit5`. The annotations and rules are the same.

Pragmatic variant:

```java
@AnalyzeClasses(packages = "com.example.shop", importOptions = ImportOption.DoNotIncludeTests.class)
public class ArchitectureTest {

    @ArchTest
    public static final ArchRule layers = layeredArchitecture()
            .consideringOnlyDependenciesInLayers() // ResponseEntity, jakarta.validation etc. are not layers
            .layer("Web").definedBy("..web..")
            .layer("Application").definedBy("..application..")
            .layer("Domain").definedBy("..domain..")
            .layer("Infrastructure").definedBy("..infrastructure..")
            .whereLayer("Web").mayNotBeAccessedByAnyLayer()
            .whereLayer("Infrastructure").mayNotBeAccessedByAnyLayer()
            .whereLayer("Application").mayOnlyBeAccessedByLayers("Web", "Infrastructure");

    @ArchTest
    public static final ArchRule domainUsesNoSpringOutsideSpringData = noClasses()
            .that().resideInAPackage("..domain..")
            .should().dependOnClassesThat(resideInAPackage("org.springframework..")
                    .and(not(resideInAPackage("org.springframework.data.."))));

    @ArchTest
    public static final ArchRule webDoesNotUseRepositories = noClasses()
            .that().resideInAPackage("..web..")
            .should().dependOnClassesThat().areAssignableTo(Repository.class);
}
```

Strict variant: the same `layers` rule, plus a plain-Java domain:

```java
@ArchTest
public static final ArchRule domainIsPlainJava = noClasses()
        .that().resideInAPackage("..domain..")
        .should().dependOnClassesThat()
        .resideInAnyPackage("org.springframework..", "jakarta.persistence..", "org.hibernate..");
```

- The static imports are `ArchRuleDefinition.noClasses`, `Architectures.layeredArchitecture`, `DescribedPredicate.not`, and `JavaClass.Predicates.resideInAPackage`. `Repository` is `org.springframework.data.repository.Repository`.
- `consideringOnlyDependenciesInLayers()` ignores dependencies whose origin or target lies outside every layer: JDK types, Spring MVC, validation, Jackson. `consideringAllDependencies()` only works when every target package belongs to a layer.
- There is no `whereLayer("Domain")` constraint. Every layer may use the domain, and the constraints on `Web`, `Application`, and `Infrastructure` already stop the domain from depending outward.
- By default, ArchUnit fails a rule whose `that()` clause matches no classes (`archRule.failOnEmptyShould`), so a renamed package can't silently switch a rule off.
- Running the strict rule against the pragmatic template fails, as it should: `@Entity`, `@Embeddable`, and `AbstractAggregateRoot` sit in the domain.

## Sources

- Robert C. Martin, *Clean Architecture* (2017), ch. 22 "The Clean Architecture" (the Dependency Rule)
- ArchUnit User Guide (layer checks, "Fail Rules on Empty Should"): https://www.archunit.org/userguide/html/000_Index.html
- ArchUnit 1.5.0 release notes (`archunit-junit6`): https://github.com/TNG/ArchUnit/releases/tag/v1.5.0
- ArchUnit source, `Architectures.java` (`consideringOnlyDependenciesInLayers`): https://github.com/TNG/ArchUnit/blob/main/archunit/src/main/java/com/tngtech/archunit/library/Architectures.java
- Spring Framework reference, Fine-tuning Annotation-based Autowiring with Qualifiers (fallback to the injection point name): https://docs.spring.io/spring-framework/reference/core/beans/annotation-config/autowired-qualifiers.html
- Hibernate ORM 7.4.5 source, `DefaultMergeEventListener` (stale version on merge): https://github.com/hibernate/hibernate-orm/blob/7.4.5/hibernate-core/src/main/java/org/hibernate/event/internal/DefaultMergeEventListener.java
