---
name: spring-boot-baseline
description: Spring Boot 4.x vs 3.x differences (removed @MockBean, Jackson 3, modular starters, TestRestTemplate, retry, Undertow) and the library versions Boot 4.1 manages. Use when checking whether code or advice matches the project's Spring Boot version.
user-invocable: false
allowed-tools: Read, Grep, Glob
---

# Spring Boot Baseline

The plugin's baseline is Spring Boot 4.1. Always detect the project's actual version first (`pom.xml` parent or BOM import, `build.gradle(.kts)` plugin version) and give advice that compiles on that version.

## Versions managed by Spring Boot 4.1.1

| Library | Version |
|---------|---------|
| Spring Framework | 7.0.9 |
| Spring Data (release train) | 2026.0.1 |
| Hibernate ORM | 7.4.5.Final |
| HikariCP | 7.0.2 |
| Jackson | 3.1.5 (Jackson 2 support: 2.21.5, deprecated) |
| JUnit Jupiter | 6.0.3 |
| Mockito | 5.23.0 |
| AssertJ | 3.27.7 |
| Testcontainers | 2.0.5 |
| MySQL Connector/J | 9.7.0 |
| PostgreSQL JDBC | 42.7.13 |
| Flyway / Liquibase | 12.4.0 / 5.0.3 |

Spring Boot 4.x requires Java 17 or later. A project can override any of these versions, so read its build file before quoting one.

## What changed in Spring Boot 4.0

| Area | Spring Boot 3.x | Spring Boot 4.x |
|------|-----------------|-----------------|
| Mocking beans in tests | `@MockBean` / `@SpyBean` | Removed. Use Spring Framework's `@MockitoBean` / `@MockitoSpyBean` (available since Framework 6.2, i.e. Boot 3.4). They work on test-class fields, not in `@Configuration` classes |
| JSON | Jackson 2 (`com.fasterxml.jackson`) | Jackson 3 (`tools.jackson`); `jackson-annotations` keeps the `com.fasterxml.jackson.core` group ID. `@JsonComponent` became `@JacksonComponent`. `spring-boot-jackson2` (deprecated) and `spring.jackson.use-jackson2-defaults` ease migration |
| Web starter | `spring-boot-starter-web` | `spring-boot-starter-webmvc`; every starter has a test-starter companion. `spring-boot-starter-classic` / `spring-boot-starter-test-classic` restore the old broad classpath during migration |
| `TestRestTemplate` | Provided by `@SpringBootTest` | No longer provided automatically: add `@AutoConfigureTestRestTemplate`; the class moved to `org.springframework.boot.resttestclient` and needs `spring-boot-restclient` |
| Retry | Spring Retry managed by Boot | Dependency management for Spring Retry removed (declare a version if you still use it); Spring Framework 7 ships core retry support in `org.springframework.core.retry` (`RetryTemplate`, `RetryPolicy`) |
| Embedded server | Tomcat, Jetty, Undertow | Undertow dropped (Servlet 6.1 baseline) |
| Persistence | Hibernate 6.x | Hibernate 7.x (see the managed version above) |

## Still true across 3.x and 4.x

- Virtual threads: `spring.threads.virtual.enabled=true` (since Spring Boot 3.2, needs Java 21+). The Spring Boot docs strongly recommend Java 24 or later, where `synchronized` no longer pins virtual threads (JEP 491).
- `MockMvcTester` (AssertJ-style MockMvc) exists since Spring Framework 6.2 (Boot 3.4); plain `MockMvc` still works.

## When to Apply

- Step 0 found a Spring Boot version and advice depends on it
- Reviewing tests, JSON handling, starters, or retry code that may be written for the wrong Boot version
- Planning or reviewing a 3.x to 4.x upgrade

## Gotchas

<!-- Keep adding mistakes Claude repeatedly makes. -->

- **Suggesting `@MockBean` on Boot 4**: it no longer exists; use `@MockitoBean`. On Boot 3.0-3.3, `@MockitoBean` does not exist yet; use `@MockBean`.
- **Importing `com.fasterxml.jackson.databind` on Boot 4 by default**: Jackson 3 lives in `tools.jackson.*`; only the annotations keep their old package.
- **Assuming `@SpringBootTest(webEnvironment = RANDOM_PORT)` injects `TestRestTemplate` on Boot 4**: it needs `@AutoConfigureTestRestTemplate`.
- **Quoting versions from memory**: read the project's build file; the table above is only the Boot 4.1.1 default.

## Sources

- Spring Boot 4.0 Migration Guide: https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide
- Spring Boot 4.1.1 dependency management: https://github.com/spring-projects/spring-boot/blob/v4.1.1/platform/spring-boot-dependencies/build.gradle and https://github.com/spring-projects/spring-boot/blob/v4.1.1/gradle.properties
- Spring Boot 3.2 Release Notes (virtual threads): https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-3.2-Release-Notes
- Spring Boot reference, virtual threads: https://docs.spring.io/spring-boot/reference/features/spring-application.html
- `@MockitoBean` and `MockMvcTester` Javadoc (`@since 6.2`): https://docs.spring.io/spring-framework/docs/current/javadoc-api/
- JEP 491: https://openjdk.org/jeps/491
