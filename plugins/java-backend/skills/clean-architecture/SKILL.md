---
name: clean-architecture
description: Clean Architecture layering for Spring Boot + JPA services - the dependency rule, where transactions and mapping belong, and the pragmatic (JPA on domain classes) versus strict (separate persistence model) variants. Use when reviewing package structure, layer dependencies, or ArchUnit rules.
user-invocable: false
allowed-tools: Read, Grep, Glob
---

# Clean Architecture for Spring Boot + JPA

## The dependency rule

Source code dependencies point inward. The web layer and the infrastructure (remote clients, custom persistence code) are both outer adapters, and neither depends on the other:

```
   web                                   infrastructure
   (controllers, DTOs, error mapping)    (remote clients, custom queries, outbox relay)
                     \                    /
                      v                  v
               application (use cases, @Transactional, ports)
                               |
                               v
               domain (entities, value objects, repository interfaces)
```

Both outer layers may also use domain types directly, for example to map a `Money` into a response.

## Identify the variant first

| Signal | Pragmatic (default) | Strict |
|---|---|---|
| Domain classes | `@Entity` and `@Embeddable` on the domain model | Plain classes, plus separate `*JpaEntity` classes and a mapper |
| Persistence port | A Spring Data interface next to the domain, used directly | A port interface in the application layer, implemented by an adapter around a Spring Data repository |
| Domain events | `AbstractAggregateRoot.registerEvent` | Published by the application layer |

Review a project against the variant it already uses. Don't recommend migrating from one variant to the other in a review. Raise it as a design question only when one of the costs below actually hurts.

## Layer responsibilities

| Layer | Contains | May depend on (pragmatic) | Strict variant |
|---|---|---|---|
| Domain | Entities with behavior, value objects, domain exceptions, repository interfaces | JDK, `jakarta.persistence`, Spring Data (`Repository`, `AbstractAggregateRoot`) | JDK only |
| Application | One method per use case, `@Transactional`, orchestration, ports for remote systems | Domain, Spring (`@Service`, transactions, events) | Also defines the persistence ports |
| Web | Controllers, request and response DTOs, `@RestControllerAdvice` | Application, domain types for mapping, Spring MVC | Same |
| Infrastructure | Remote clients, custom repository implementations, outbox relay, configuration | Every inner layer | Also the JPA entities, mappers, and adapters |

- Keep the port narrow. Extend `Repository<T, ID>` and declare only the methods the use cases need, instead of inheriting every `JpaRepository` method (`flush`, `deleteAllInBatch`, an unpaged `findAll`). This is a recommendation, not a violation.
- Controllers call use cases, not repositories. With Open Session in View off, the use case's transaction is the only place where lazy associations still load.

## Transactions and errors belong to the use case boundary

- The application service method that implements a use case owns `@Transactional`. Controllers and domain classes don't declare transactions.
- Don't make remote calls inside the transaction. The transaction keeps its connection and row locks while the network call waits, and the call can't be rolled back. Commit the intent, call outside, then record the result (`references/layer-dependencies.md`).
- In-process side effects run after commit (`@TransactionalEventListener`). Events other systems depend on go through an outbox (`java-backend:transactions-consistency`).
- The web layer turns domain exceptions into `ProblemDetail` responses (RFC 9457). Map `ObjectOptimisticLockingFailureException` to 409.

## What the strict variant costs with JPA

- Saving an existing aggregate maps it onto a new, detached JPA entity, so `save()` calls `merge`. `merge` `SELECT`s every row that isn't already in the persistence context, including child rows: a new line with an assigned id also looks existing.
- Optimistic locking survives only if the domain object carries the `version` and the mapper copies it back. Without it, `merge` overwrites newer data (a lost update). After a flush the domain object's version is stale, so save each aggregate once per transaction.
- The domain model can't lazy-load. The mapper reads every association it maps, on every load.
- Dirty checking doesn't see changes to plain domain objects, so every use case must call the port's `save`.
- `AbstractAggregateRoot` is a Spring Data type, so domain events need another mechanism.

These costs pay off when the domain model must stay independent of persistence, for example with several persistence models, or heavy domain logic tested without JPA. They don't pay off by default. For details on `save()`, `merge`, and `Persistable`, see `java-backend:jpa-hibernate`.

## Code Review Checklist

| Check | Correct | Violation |
|-------|---------|-----------|
| Dependency direction | Web and infrastructure → application → domain | Domain imports application, web, or infrastructure classes; application imports web DTOs |
| Framework in the domain | Pragmatic: JPA and Spring Data only. Strict: none | `@Service`, `@Transactional`, or Spring MVC types in domain classes |
| Transaction boundary | `@Transactional` on use case methods | On controllers, or around remote calls |
| Concurrent updates | `@Version` on aggregates updated concurrently; strict: `version` carried through the mapper | A strict adapter that maps without the version |
| Controllers | Map the DTO to a command, call one use case, map the result | Business rules or repository calls in the controller |
| Domain behavior | `order.cancel()` checks its own invariants | `order.setStatus(CANCELLED)` from a service |
| Bean registration | Component scan or a `@Bean` method, one per class | Both for the same class: two beans |
| Architecture tests | ArchUnit rules that pass on the current code | Rules nobody runs, or rules that already fail |

## When to Apply

- Reviewing package structure or the dependencies between the layers of a Spring Boot service
- Deciding where a transaction, a mapping, an event, or an error translation belongs
- Writing or fixing ArchUnit rules
- Splitting a service into modules

## Gotchas

<!-- Keep adding mistakes Claude repeatedly makes. -->

- **Don't take Clean Architecture to the extreme**: a small Spring Boot service is fine with three layers (controller, service, repository). Ports and adapters are a tool for large systems.
- **`@Entity` on domain classes is the pragmatic default, not a violation**: flag it only in a codebase that already follows the strict variant.
- **`AbstractAggregateRoot` events need a repository call**: only `save`, `saveAll`, `delete`, `deleteAll`, `deleteAllInBatch`, and `deleteInBatch` publish them. A use case that relies on dirty checking publishes nothing, and neither does `deleteById`. Call `save()` when the aggregate registered events, even though the update would be flushed anyway.
- **Don't recommend switching variants in a review**: the migration rewrites every repository and mapper. Name the concrete cost instead.
- **Register each bean one way**: `@Service` on a class plus a `@Bean` method that returns it creates two beans of the same type. Injection by type then fails with `NoUniqueBeanDefinitionException`, or silently picks the bean whose name matches the parameter name.
- **ArchUnit rules must match the real dependencies**: an `onlyDependOnClassesThat()` allow-list breaks on every type nobody listed (`ResponseEntity`, `jakarta.validation`, a DTO package). `layeredArchitecture().consideringOnlyDependenciesInLayers()` checks only the dependencies between your own layers.
- **A use case with more than three collaborators deserves an SRP review**: many dependencies usually mean it does too much.
- **Don't create a repository for every entity**: only aggregate roots need one. Reach other entities through their aggregate root.

## Additional Resources

- **references/layer-dependencies.md**: the dependency matrix, allowed dependencies per variant, violations and fixes (including the payment flow), and ArchUnit rules
- **references/spring-boot-implementation.md**: the pragmatic template, and the parts the strict variant changes
- Testing each layer: `java-backend:java-testing` (`references/spring-test-slices.md`)
