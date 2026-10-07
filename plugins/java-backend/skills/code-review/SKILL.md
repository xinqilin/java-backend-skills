---
name: code-review
description: Review Java/Spring Boot code for correctness, JPA and database pitfalls, Clean Code, and over-design. Use when the user asks to review a Java file, class, or directory.
argument-hint: "[file-or-directory]"
allowed-tools: Read, Grep, Glob, Bash
context: fork
agent: java-backend:code-reviewer
---

# Code Review

Review `$ARGUMENTS` (or, if empty, the files changed in the working tree: `git diff --name-only HEAD`) to senior-engineer standards: correctness first, then Clean Code, without over-design.

## Core philosophy

1. **Correctness first**: concurrency anomalies, transaction boundaries, and data integrity outrank style
2. **Clean Code**: the next person should understand it quickly
3. **Never over-design**: solve the current problem; don't predict the future
4. **Pragmatic**: weigh the real maintenance cost of every suggestion

## Review focus areas

### 1. Data access and transactions (highest impact)

Load `java-backend:jpa-hibernate` and `java-backend:transactions-consistency` with the Skill tool when the code touches repositories, entities, or `@Transactional`.

- Read-modify-write on shared rows without a version column, lock, or atomic update
- `@Transactional` self-invocation (calls inside the same class bypass the proxy)
- `@Transactional` on controllers or repositories instead of the service layer
- Remote calls inside a transaction; very long transactions
- N+1 queries; collection fetch joins combined with pagination

### 2. Avoiding over-design

**Don't abstract too early** (Rule of Three):
```java
// Bad: abstraction after seeing one case
interface PaymentProcessor { ... }
class CreditCardPaymentProcessor implements PaymentProcessor { ... }
// Only credit cards are supported anyway

// Good: wait until several payment methods are actually needed
class PaymentService {
    public void processCreditCardPayment(...) { ... }
}
```

**YAGNI: no hypothetical design**:
```java
// Bad: fields for "might need later"
class Order {
    private PaymentStrategy paymentStrategy;   // might change later?
    private ShippingStrategy shippingStrategy; // might change later?
}

// Good: solve the current problem
class Order {
    private String paymentMethod; // enough for now
}
```

**Avoid single-implementation interfaces**:
```java
// Bad: UserServiceImpl is the only implementation
interface UserService { ... }
class UserServiceImpl implements UserService { ... }

// Good: extract an interface when a second implementation is real
class UserService { ... }
```

### 3. Spring Boot anti-patterns

- Field injection with `@Autowired` instead of constructor injection
- Business logic in controllers

### 4. Other quality checks

- Names express intent (no cryptic abbreviations)
- Methods are short and do one thing; nesting depth ≤ 3
- No swallowed exceptions (catch blocks without context)
- No I/O inside loops

## Review checklist

### Data access
- [ ] No unguarded read-modify-write on shared rows
- [ ] Transaction boundaries on the service layer, no remote calls inside
- [ ] No `@Transactional` self-invocation
- [ ] No N+1, no collection fetch join with pagination

### Avoiding over-design
- [ ] No premature abstraction (Rule of Three)
- [ ] No hypothetical design (YAGNI)
- [ ] No meaningless single-implementation interfaces
- [ ] Complexity matches the problem

### Naming and method design
- [ ] Names express intent; booleans use is/has/can
- [ ] Methods are short, nesting ≤ 3, parameters ≤ 4

### Exception handling
- [ ] No swallowed exceptions; messages carry context; specific exception types

### Spring Boot
- [ ] Constructor injection
- [ ] `@Transactional` on the service layer only

## Output format

Write the report in the user's language. Keep code and identifiers as-is.

```markdown
## Stack
Spring Boot <version> · Java <release> · <MySQL|PostgreSQL> (from Step 0)

## Assessment
- Complexity: Low / Medium / High
- Maintainability: 1-10
- Over-design: None / Slight / Severe

## Strengths
What the code does well.

## Issues (by priority)

### Priority 1 - Must fix
| Issue | Location | Impact | Fix |
|-------|----------|--------|-----|
| ... | File.java:42 | ... | ... |

### Priority 2 - Should improve
| Issue | Location | Impact | Fix |
|-------|----------|--------|-----|

## Refactoring suggestions
Before/after code for any larger change.

## Summary
One sentence on overall quality and the main direction for improvement.
```

## When to Apply

- Quality review of Java/Spring Boot code
- Checking JPA, transaction, and database access code for correctness and performance
- Detecting over-design and suggesting simplifications

## Gotchas

<!-- Keep adding mistakes Claude repeatedly makes. -->

- **Read the whole context before concluding**: don't call a method "too long" from a diff alone; check the class's responsibility first.
- **Confirm a second implementation exists before suggesting an interface**: a single-implementation interface is over-design, not a best practice.
- **Lombok `@Data` on entities is a bug source**: generated `equals`/`hashCode` and `toString` use every field, which breaks with Hibernate proxies and can trigger lazy loading. Use `@Getter`/`@Setter` and write identity-based `equals`/`hashCode` deliberately.
- **Beware reviewer bias**: "the way I usually write it" is not "the correct way"; state the concrete reason for every suggestion.
- **`@Transactional` self-invocation bypasses the proxy**: a call to an `@Transactional` method from inside the same class runs without the transaction semantics declared on it.
