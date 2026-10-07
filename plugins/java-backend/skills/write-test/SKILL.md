---
name: write-test
description: Write JUnit tests for a Spring Boot class (service, controller, or repository) that follow the project's conventions, cover the code's real branches and exceptions, and pass when run. Use when the user asks to write, add, or generate tests.
argument-hint: "[class-or-file]"
allowed-tools: Read Grep Glob Bash(./mvnw test *) Bash(./gradlew test *) Bash(mvn test *) Bash(gradle test *)
---

# Write Tests

Target: `$ARGUMENTS`

This skill runs in the main conversation, so the user sees and can steer every file change. Only the test commands below are pre-approved; file edits go through the normal permission flow. Apply the `java-backend:java-testing` knowledge throughout.

## Step 0: Detect the stack and conventions

1. Build file (`pom.xml` or `build.gradle(.kts)`): Spring Boot version, Java release, JUnit, Mockito, AssertJ, Testcontainers, the JDBC driver, and test starters (`spring-boot-starter-webmvc-test`, `spring-boot-starter-data-jpa-test` on Boot 4).
2. Two or three existing tests near the target: naming, `@DisplayName` language and pattern, `@Nested` use, assertion style, fixture style, and any shared Testcontainers setup to reuse.
3. Choose imports for the detected Spring Boot version (`java-testing` → version table). Never mix Boot 3 and Boot 4 test APIs.

## Step 1: Read the code under test

- List every public behavior: branches, guard clauses, and **exceptions actually thrown**, each with its `file:line`.
- Note collaborators: which to mock (ports to the outside), and which to use as real objects (domain types).
- Note persistence behavior that needs a real database: custom queries, constraints, locking, `@Version`, transaction boundaries.

## Step 2: Choose the test type

| Target | Test |
|--------|------|
| Service or domain logic | Plain unit test with `MockitoExtension` |
| Controller | `@WebMvcTest` + `MockMvcTester` + `@MockitoBean` |
| Repository, query, constraint | `@DataJpaTest` + Testcontainers (production engine) |
| Concurrency guard or transaction behavior | `@SpringBootTest` without a test transaction, real threads (`java-testing` → `concurrency-tests.md`) |

If a needed dependency is missing (for example Testcontainers), stop and tell the user what to add instead of silently falling back to H2 or mocks.

## Step 3: Write the tests

- One behavior per test; Arrange-Act-Assert; `@Nested` per method or scenario; `@ParameterizedTest` for equivalence classes.
- One test per real exception, citing the throwing line in a comment if the project's style allows comments.
- Assert state, not interactions, unless the behavior is the interaction (a message published, an email sent).
- Construct objects inline; no helper hierarchies.
- Match the project's conventions found in Step 0, even where they differ from this skill.

## Step 4: Run the narrowest command and fix until green

```bash
./mvnw test -Dtest=OrderServiceTest                      # Maven (single class)
./gradlew test --tests 'com.example.order.OrderServiceTest'   # Gradle
```

- Use the wrapper (`mvnw` / `gradlew`) when the project has one.
- When a test fails, decide whether **the test** is wrong (fix it) or **the code** is wrong (stop and report the bug with evidence; never weaken an assertion to make a real bug pass).
- Testcontainers needs a running Docker daemon; if it isn't available, say so instead of skipping those tests.

## Step 5: Report

- The tests added, by behavior covered
- Behaviors deliberately not tested, and why
- Any bug found in the code under test, with the failing test as evidence
- The command you ran and its result

Write the report in the user's language. Keep code and identifiers as-is.

## When to Apply

- "Write tests for X", "add a test for this bug", "cover this class"
- After implementing a feature, to add the tests that prove it
- Reproducing a bug as a failing test before fixing it

## Gotchas

<!-- Keep adding mistakes Claude repeatedly makes. -->

- **Inventing exceptions or branches**: every exception test must point to a real `throw` in the code under test.
- **Boot 3 imports in a Boot 4 project (or the reverse)**: test slice annotations moved packages in 4.0, and `@MockBean` no longer exists there.
- **H2 as a silent fallback**: it hides dialect, constraint, and locking behavior; use the production engine through Testcontainers.
- **Concurrency tests inside `@DataJpaTest`'s transaction**: worker threads can't see the fixtures, so the test proves nothing.
- **Weakening assertions to get green**: a failing test that exposes a real bug is the most valuable output; report it.
- **Running the whole suite to check one test**: use the narrowest selector so the feedback loop stays short.
