---
name: review-test
description: Review JUnit test code in a Spring Boot project for real-behavior coverage, over-design, and Spring test pitfalls. Use when the user asks to review tests, test design, or coverage.
argument-hint: "[test-file-or-directory]"
allowed-tools: Read, Grep, Glob
context: fork
agent: java-backend:test-reviewer
---

# Review Unit Tests

Review `$ARGUMENTS` (or the test files changed in the working tree when empty) to senior-engineer standards, applying the preloaded `java-backend:java-testing` knowledge (test types, Spring Boot 3 vs 4 APIs, Testcontainers, concurrency tests).

## Core principle

**Most important**: every test scenario must come from real system behavior. Never fabricate hypothetical scenarios.

## Review focus areas

### 1. Reality check

- Is the tested exception actually thrown by the code?
- Does the tested branch actually exist?
- Are there hypothetical "what-if" scenarios?

```java
// Bad: assumes an exception without checking the source
@Test
void shouldThrowIllegalArgumentException() {
    assertThrows(IllegalArgumentException.class, () -> facade.process(null));
}

// Good: verified that OrderFacade.java:45 actually throws InvalidTokenException
@Test
@DisplayName("throws InvalidTokenException when the token is invalid")
void shouldThrowInvalidTokenExceptionWhenTokenIsInvalid() {
    assertThrows(InvalidTokenException.class, () -> facade.process(invalidToken));
}
```

### 2. Over-design check

- **Over-abstracted helpers**: `createTestOrder(DEFAULT_USER, DEFAULT_ITEMS, DEFAULT_AMOUNT)` where `new Order(userId, items, amount)` inline is clearer
- **Unnecessary base classes**: `extends AbstractServiceTest<Order, OrderRepository>` where a plain `class OrderServiceTest` would do
- **Excessive mock setup in `@BeforeEach`**: stub only what each test needs

### 3. Test responsibility separation

| Layer | Should test | Should NOT test |
|-------|-------------|-----------------|
| Model | Bean Validation (@NotBlank, @Size, ...) | — |
| Controller | HTTP behavior, status codes, JSON serialization | Validation rules already covered by Model tests |
| Service | Business logic, state changes | Database operation details |

### 4. Naming and structure

- `@DisplayName`: follow the convention the project already uses, including its language; if there is none, suggest one consistent pattern
- Use `@Nested` for logical grouping
- Method names describe behavior, e.g. `shouldRejectOrderWhenAmountExceedsLimit()`

### 5. Verification strategy

**Prefer state verification over interaction verification**:
```java
// Good: state verification
assertThat(order.getStatus()).isEqualTo(OrderStatus.PENDING);

// Interaction verification only when state cannot be asserted
verify(emailService).sendOrderCompletionEmail(orderId);
```

## Review checklist

### Reality
- [ ] Every tested exception is actually thrown by the code
- [ ] Every scenario reflects real system behavior

### Simplicity
- [ ] No over-abstracted helpers or unnecessary base classes
- [ ] Mock setup is minimal and per test

### Responsibility separation
- [ ] Model tests focus on validation, controller tests on HTTP behavior
- [ ] No duplicate testing across layers

### Code quality
- [ ] Arrange-Act-Assert
- [ ] `@DisplayName` follows the project's convention
- [ ] `@Nested` used for organization
- [ ] State verification preferred

## Output format

Write the report in the user's language. Keep code and identifiers as-is.

```markdown
## Stack
Spring Boot <version> · JUnit <version> · Mockito/AssertJ/Testcontainers as detected

## Analysis
- Coverage: what is covered, what is missing
- Reality check: any fabricated scenarios

## Issues
For each: issue / evidence (file:line) / impact / fix

## Recommendations
- Tests to add (with reasons)
- Tests to delete (with reasons)
- Tests to refactor (with before/after)
```

## When to Apply

- Reviewing unit or integration test quality
- Discussing test design or coverage
- Checking tests for over-design

## Gotchas

<!-- Keep adding mistakes Claude repeatedly makes. -->

- **Stubbing void methods**: `when(service.voidMethod())` does not compile. Void methods already do nothing by default; use `doThrow(...).when(service).voidMethod()` or `doAnswer(...)` when the test needs behavior.
- **Overusing `@SpringBootTest`**: most unit tests only need `@ExtendWith(MockitoExtension.class)`; `@SpringBootTest` loads the whole application context and is slow.
- **`verify(mock).method()` already means `times(1)`**: it fails when the method was never called, so `times(1)` is redundant. Use `never()`, `times(n)`, or `atLeastOnce()` when you mean something else.
- **Bean overrides fragment the context cache**: `@MockitoBean` / `@MockitoSpyBean` (and `@MockBean` / `@SpyBean` before Spring Boot 3.4) are part of the test context cache key, so every distinct combination starts a new `ApplicationContext` and slows the suite.
- **Prefer AssertJ's collection assertions**: `assertThat(list).containsExactly(...)` reports which element differs, unlike `assertEquals` on whole lists.
