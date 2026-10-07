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

<!-- 持續更新：遇到新的 Claude 常犯錯誤時加入 -->

- **不要把 Clean Architecture 套到極致**：Spring Boot 小專案用 3 層（Controller / Service / Repository）就夠，ports/adapters 是大型系統的工具
- **@Entity 放 domain layer 是務實選擇**：嚴格派要求 JPA entity 在 infrastructure，但這需要額外 mapper。若專案規模小，允許 domain 依賴 JPA annotations 是合理的 trade-off
- **Domain Event 不要用 Spring ApplicationEvent**：這讓 domain 依賴 Spring framework，違反 Dependency Rule
- **UseCase 超過 3 個依賴就該審查 SRP**：依賴太多通常意味著 use case 做了太多事
- **不要為每個 Entity 都建 Repository interface**：只有 Aggregate Root 需要 Repository，其他 Entity 透過 Aggregate Root 存取

## Additional Resources

- **references/layer-dependencies.md** — Dependency rules and violation examples
- **references/spring-boot-implementation.md** — Complete project templates for all layers
- **references/testing-strategy.md** — Testing each layer in isolation
