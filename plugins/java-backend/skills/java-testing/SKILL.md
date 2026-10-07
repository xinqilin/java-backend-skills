---
name: java-testing
description: How to write and judge JUnit tests for Spring Boot 3.x/4.x services on Spring Data JPA with MySQL or PostgreSQL (real-behavior tests, test slices, @MockitoBean, MockMvcTester, Testcontainers, concurrency tests). Use when writing or reviewing tests.
user-invocable: false
allowed-tools: Read, Grep, Glob
---

# Testing Spring Boot Services

## Principles

1. **Test real behavior only**: read the code under test first. Test the branches that exist and the exceptions that are actually thrown; never invent scenarios.
2. **One behavior per test**, structured Arrange-Act-Assert, grouped with `@Nested`. Collapse equivalence classes into one `@ParameterizedTest`.
3. **Prefer state over interactions**: assert results and persisted state; use `verify()` only for effects you cannot observe otherwise (an email sent, a message published).
4. **Follow the project's conventions**: naming, `@DisplayName` language and pattern, assertion library, fixtures. Consistency beats this skill's preferences.
5. **No over-engineering**: no base-class hierarchies or helper factories for a handful of fields; construct objects inline.
6. **Test against the real database** for anything that depends on SQL, constraints, locking, or isolation. An embedded H2 doesn't behave like MySQL or PostgreSQL.

## Choose the smallest test that proves the behavior

| What you're testing | Test type | Setup |
|---------------------|-----------|-------|
| Domain logic, pure services | Plain unit test | `@ExtendWith(MockitoExtension.class)`, `@Mock`, no Spring context |
| Controller: HTTP status, JSON, validation | `@WebMvcTest(XController.class)` | `MockMvcTester`, `@MockitoBean` for collaborators |
| Repository queries, mappings, constraints | `@DataJpaTest` | Testcontainers with the production database |
| Transactions, locking, concurrency | `@SpringBootTest` (no test-managed transaction) | Testcontainers; threads; explicit cleanup |
| Full flow through HTTP | `@SpringBootTest(webEnvironment = RANDOM_PORT)` | Testcontainers; a real HTTP client |

## Spring Boot 4 vs 3: imports and annotations

Detect the version first (`java-backend:spring-boot-baseline`). Generated code must compile on that version.

| Concern | Spring Boot 4.x | Spring Boot 3.x |
|---------|-----------------|-----------------|
| `@WebMvcTest` | `org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest` (`spring-boot-starter-webmvc-test`) | `org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest` |
| `@DataJpaTest` | `org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest` (`spring-boot-starter-data-jpa-test`) | `org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest` |
| `TestEntityManager` | `org.springframework.boot.jpa.test.autoconfigure.TestEntityManager` | `org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager` |
| `@AutoConfigureTestDatabase` | `org.springframework.boot.jdbc.test.autoconfigure.AutoConfigureTestDatabase` | `org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase` |
| Mock a bean | `@MockitoBean` (`org.springframework.test.context.bean.override.mockito`) | `@MockitoBean` on 3.4+, `@MockBean` before |
| MockMvc with AssertJ | `MockMvcTester` (`org.springframework.test.web.servlet.assertj`) | Same on 3.4+ (Framework 6.2); `MockMvc` before |
| Testcontainers | 2.x: `org.testcontainers.postgresql.PostgreSQLContainer`, `org.testcontainers.mysql.MySQLContainer` (not generic) | 1.x: `org.testcontainers.containers.PostgreSQLContainer<?>` |
| `TestRestTemplate` | `org.springframework.boot.resttestclient.TestRestTemplate` (`spring-boot-resttestclient`), enabled with `@AutoConfigureTestRestTemplate` (`...resttestclient.autoconfigure`) | Injected by `@SpringBootTest(webEnvironment = RANDOM_PORT)` |
| JUnit | Jupiter 6 (same `org.junit.jupiter.api` packages) | Jupiter 5 |

## Testcontainers and the test database

```java
@DataJpaTest
@Testcontainers
class OrderRepositoryTest {
    @Container
    @ServiceConnection                                    // Spring Boot 3.1+
    static PostgreSQLContainer postgres = new PostgreSQLContainer("postgres:18");
    ...
}
```

- `@ServiceConnection` wires the container's URL and credentials; no `@DynamicPropertySource` needed.
- `@AutoConfigureTestDatabase` defaults to `Replace.NON_TEST` since Spring Boot 3.4: it keeps `@ServiceConnection` containers, `@DynamicPropertySource` URLs, and Testcontainers JDBC URLs. On 3.3 and earlier the default `ANY` replaced them with an embedded database, so add `@AutoConfigureTestDatabase(replace = Replace.NONE)` there.
- Use the production image and major version (`mysql:8.4`, `postgres:18`).

Details for each slice: `references/spring-test-slices.md`.

## Concurrency and transaction tests

- Spring binds the test-managed transaction to the test's thread. Work done in other threads runs outside it: it can't see the test's uncommitted fixtures and isn't rolled back. So concurrency tests use `@SpringBootTest` without `@Transactional`, commit their fixtures, and clean up explicitly.
- Prove the guard, not the happy path: race N threads on the same row and assert the invariant (balance never negative, exactly `total` coupons issued, no duplicate rows).

Patterns: `references/concurrency-tests.md`.

## When to Apply

- Writing new tests (`/java-backend:write-test`) or reviewing existing ones (`/java-backend:review-test`)
- Choosing between unit, slice, and integration tests
- Testing repositories, constraints, locking, or isolation against a real database
- Migrating tests from Spring Boot 3 to 4

## Gotchas

<!-- Keep adding mistakes Claude repeatedly makes. -->

- **Fabricated exceptions**: never write `assertThrows(IllegalArgumentException.class, ...)` without finding the `throw` in the code under test.
- **Spring Boot 3 imports in a Boot 4 project**: slice annotations moved packages in 4.0, and `@MockBean` no longer exists.
- **H2 hides real bugs**: dialect-specific SQL, constraint behavior, locking, and isolation differ from MySQL and PostgreSQL.
- **`@DataJpaTest` rolls back each test**: inserts may never flush, so constraint violations go unnoticed. Call `flush()` (or `saveAndFlush`) before asserting on database-level behavior.
- **Concurrency tests inside a test-managed transaction prove nothing**: the other threads can't see the fixtures.
- **`when(mock.voidMethod())` doesn't compile**: use `doThrow(...).when(mock).voidMethod()` when the test needs behavior.
- **`verify(mock).method()` already means `times(1)`**: it fails when the method was never called.
- **Every distinct `@MockitoBean` set creates a new application context**: keep mocked beans consistent across a suite, or the context cache misses.

## Sources

- Spring Boot 4.1.1 reference and examples, testing (slices, `MockMvcTester`, `@MockitoBean`, Testcontainers): https://github.com/spring-projects/spring-boot/tree/v4.1.1/documentation/spring-boot-docs
- Spring Boot source, `AutoConfigureTestDatabase` defaults (`NON_TEST` since 3.4.0, `ANY` in 3.3): https://github.com/spring-projects/spring-boot
- Spring Boot 4.0 Migration Guide: https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide
- Spring Framework reference, Transaction Management in tests (thread-bound test transactions): https://docs.spring.io/spring-framework/reference/testing/testcontext-framework/tx.html
- Spring Framework reference, Context Caching (bean overrides in the cache key): https://docs.spring.io/spring-framework/reference/testing/testcontext-framework/ctx-management/caching.html
- Testcontainers 2.0.5 source, `org.testcontainers.postgresql.PostgreSQLContainer` and `org.testcontainers.mysql.MySQLContainer`: https://github.com/testcontainers/testcontainers-java/tree/2.0.5/modules
- Mockito, `verify` defaults to `times(1)`: https://github.com/mockito/mockito
