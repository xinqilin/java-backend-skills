---
name: design-solution
description: Design a Spring Boot feature or data model end to end (consistency, transactions, schema and indexes, API) and produce an actionable implementation plan. Use when the user asks for a technical design or implementation strategy.
argument-hint: "[requirement-description]"
allowed-tools: Read, Grep, Glob, Bash
---

# Design Solution

Requirement: `$ARGUMENTS`

As a senior Spring Boot engineer, analyze the requirement and produce a complete, buildable design. This skill runs in the main conversation so you can ask the user clarifying questions before committing to a design.

## Analysis workflow

### Step 0: Detect the stack
Read `pom.xml` or `build.gradle(.kts)` and `application.yml` / `application.properties`: Spring Boot version, Java release, persistence (Spring Data JPA/Hibernate), database (MySQL or PostgreSQL) and its version where visible. Design for what the project actually uses.

### Step 1: Understand the requirement
- Business goal, users, inputs and outputs
- Non-functional requirements with real numbers: peak requests per second, data volume and growth, latency targets, availability

### Step 2: Clarify ambiguities
Ask before designing:
- Edge cases and failure scenarios
- Existing code to integrate with
- Consistency expectations: what must never happen (double charge, oversell), and what may be briefly stale

### Step 3: Data and consistency analysis
Load `java-backend:transactions-consistency` and `java-backend:sql-performance` with the Skill tool when the feature writes shared state (money, inventory, quotas, counters) or has meaningful read/write volume.
- Which rows are written concurrently, and which anomaly each concurrent write path risks (lost update, write skew)
- The guard for each path: atomic conditional update, version column, lock, unique or exclusion constraint, or serializable isolation with retry
- Transaction boundaries: keep them short; no remote calls inside
- Events or messages that must stay consistent with the database (transactional outbox)
- Query patterns, and the indexes that serve them

### Step 4: Design
Architecture, data model (tables, keys, constraints, indexes), API, and key implementation details.

### Step 5: Implementation plan
An actionable todo list in phases, including the tests that prove the concurrency guards work.

## Design principles

- **Don't over-design**: solve the current problem (YAGNI); start simple and add complexity only when the numbers demand it
- **Correctness before throughput**: decide the consistency guard first, then optimize
- **Maintenance cost counts**, not only development cost
- **Spring Boot practices**: constructor injection, layered architecture, `@Transactional` on the service layer, `@RestControllerAdvice` for errors

## Output format

Write the design in the user's language. Keep code, SQL, and identifiers as-is.

```markdown
## Requirement

### Summary
[The requirement in your own words, to confirm understanding]

### Clarifying questions
1. [question]

---

## Recommendation

### Proposed approach
[The approach]

### Why this approach
- [reason]

### Alternatives considered
[Other viable options and their trade-offs]

---

## Design

### Architecture
[Components and how they interact]

### Data model
[Tables or entities with keys, constraints, and indexes]

### Consistency and concurrency
| Write path | Risk | Guard | Isolation level |
|------------|------|-------|-----------------|

### API
[Endpoints, request and response shapes, idempotency]

---

## Implementation plan

### Phase 1: Foundation
- [ ] Step 1.1: [concrete task naming the class, table, or endpoint]

### Phase 2: Core feature
- [ ] Step 2.1: [concrete task]

### Phase 3: Tests
- [ ] Step 3.1: [concrete test, including concurrency tests against the real database]

---

## Risks and edge cases

### Risks
1. [risk and mitigation]

### Edge cases
1. [edge case and handling]

### Performance
### Security

---

## Rough effort

| Phase | Relative size (S/M/L) | Notes |
|-------|-----------------------|-------|
```

## When to Apply

- A new feature needs a technical design
- Architecture or implementation strategy discussions
- Data model, consistency, or transaction-boundary decisions
- An actionable todo list is needed

## Gotchas

<!-- Keep adding mistakes Claude repeatedly makes. -->

- **Don't jump to microservices**: confirm that a modular monolith cannot meet the requirement before splitting; most new features don't need a new service.
- **Don't make every interaction event-driven**: synchronous calls are simpler and easier to debug in most cases; events add complexity that needs a reason.
- **Use real numbers for load and volume**: "large" means nothing; "about 100k requests per day, 5M rows growing 10% per month" can drive a design.
- **A cache is not a fix by default**: confirm whether the bottleneck is the database or application logic first.
- **Every todo item must be buildable**: name the class, table, or endpoint; "implement business logic" is not a task.
- **Don't invent effort estimates in days**: without team context, give relative sizes and say what drives them.

## Reference files

- **references/design-solution-example.md**: a complete worked example. Read it when you need to see the expected depth of the output.
