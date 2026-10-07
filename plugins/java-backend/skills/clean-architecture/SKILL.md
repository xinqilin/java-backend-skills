---
name: clean-architecture
description: Layering and dependency rules for Spring Boot projects in the spirit of Clean Architecture. Use when reviewing architecture, layer separation, or project structure.
user-invocable: false
allowed-tools: Read, Grep, Glob
---

# Clean Architecture for Spring Boot

## Core Principle: The Dependency Rule

**Dependencies point inward only.** Inner layers know nothing about outer layers.

```
┌─────────────────────────────────────────────┐
│              Presentation                    │  ← Controllers, DTOs
│   ┌─────────────────────────────────────┐   │
│   │          Infrastructure              │   │  ← Repositories Impl, External APIs
│   │   ┌─────────────────────────────┐   │   │
│   │   │        Application           │   │   │  ← Use Cases, Ports
│   │   │   ┌─────────────────────┐   │   │   │
│   │   │   │      Domain          │   │   │   │  ← Entities, Value Objects
│   │   │   └─────────────────────┘   │   │   │
│   │   └─────────────────────────────┘   │   │
│   └─────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

---

## Layer Responsibilities

| Layer | Contains | Framework Dependencies |
|-------|----------|----------------------|
| Domain | Entity, Value Object, Domain Exception | None |
| Application | UseCase, Port (interface), Command/Query | None |
| Infrastructure | Repository impl, External API adapters, Config | Spring, JPA, etc. |
| Presentation | Controller, Request/Response DTO | Spring MVC |

### Domain Layer: Key Pattern

```java
// Entity - business identity + behavior
public class Order {
    private OrderId id;
    private OrderStatus status;

    public void confirm() {
        if (this.status != OrderStatus.PENDING) {
            throw new IllegalOrderStateException("Only pending orders can be confirmed");
        }
        this.status = OrderStatus.CONFIRMED;
    }
}

// Value Object - immutable, equality by value
public record Money(BigDecimal amount, Currency currency) {
    public Money {
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

### Application Layer Pattern

Input Port (UseCase interface) + Output Port (Repository interface) + Service implementation.
See **references/spring-boot-implementation.md** for complete template.

### Infrastructure + Presentation

`JpaOrderRepository implements OrderRepository` — adapters implement ports.
`OrderController` only calls UseCase, no business logic.
See **references/spring-boot-implementation.md** for complete template.

---

## Spring Boot Project Structure

```
src/main/java/com/example/order/
├── domain/
│   ├── model/          Order.java, OrderId.java, Money.java
│   ├── service/        OrderDomainService.java
│   └── exception/      IllegalOrderStateException.java
├── application/
│   ├── port/in/        CreateOrderUseCase.java
│   ├── port/out/       OrderRepository.java
│   ├── service/        CreateOrderService.java
│   └── dto/            CreateOrderCommand.java
├── infrastructure/
│   ├── persistence/    OrderEntity.java, JpaOrderRepository.java, OrderMapper.java
│   └── config/         PersistenceConfig.java
└── presentation/
    ├── controller/     OrderController.java
    ├── request/        CreateOrderRequest.java
    └── response/       OrderResponse.java
```

---

## Code Review Checklist

| Check | Correct | Violation |
|-------|---------|-----------|
| Domain has no Spring annotations | `public class Order` | `@Entity public class Order` |
| Controller has no business logic | Delegates to UseCase | Contains validation/calculation |
| UseCase depends on ports only | `OrderRepository` (interface) | `JpaOrderRepository` (impl) |
| DTOs don't leak to domain | Maps to Command/Entity | Passes DTO to UseCase |
| Entities have behavior | `order.confirm()` | Anemic model with only getters |

---

## Common Anti-Patterns

1. **Framework Coupling in Domain** — `@Entity` in domain layer. Pragmatic resolution: allow JPA annotations in domain if the project is small; strict projects keep JPA entities in infrastructure with a mapper
2. **Fat Controllers** — business logic in `@PostMapping` methods; delegate to UseCase instead
3. **Anemic Domain Model** — `order.setStatus(CONFIRMED)` from a service; behavior belongs to the entity

---

## When to Apply

- New feature development requiring clear boundaries
- Refactoring legacy code with tangled dependencies
- Designing microservice boundaries

## Gotchas

<!-- Keep adding mistakes Claude repeatedly makes. -->

- **Don't take Clean Architecture to the extreme**: a small Spring Boot project is fine with three layers (controller / service / repository); ports and adapters are a tool for large systems.
- **`@Entity` in the domain layer is a pragmatic choice**: the strict view puts JPA entities in infrastructure, which costs an extra mapping layer. For small projects, letting the domain depend on JPA annotations is a reasonable trade-off.
- **Don't model domain events as Spring `ApplicationEvent`s**: it makes the domain depend on the Spring framework, against the dependency rule.
- **A use case with more than three dependencies deserves an SRP review**: many dependencies usually mean it does too much.
- **Don't create a repository for every entity**: only aggregate roots need one; reach other entities through their aggregate root.

## Additional Resources

- **references/layer-dependencies.md** — Dependency rules and violation examples
- **references/spring-boot-implementation.md** — Complete project templates for all layers
- **references/testing-strategy.md** — Testing each layer in isolation
