# Changelog

## 2.0.0

A rewrite focused on depth for Spring Boot + Spring Data JPA + MySQL/PostgreSQL.

### Breaking changes

- The four plugins (`bill-billing-unit-test-reviewer`, `bill-code-reviewer`, `bill-java-developer`, `bill-java-skills`) are merged into one plugin, **`java-backend`**.
- The marketplace is renamed from `bill-lin-dev-toolkit` to **`xinqilin`**.
- Commands are namespaced: `/java-backend:code-review`, `/java-backend:review-pr`, `/java-backend:review-test`, `/java-backend:write-test`, `/java-backend:optimize-query`, `/java-backend:design-solution`.
- `install.sh` and `uninstall.sh` are removed.
- License changed from MIT to Apache-2.0.

### Upgrading from 1.x

```text
/plugin marketplace remove bill-lin-dev-toolkit
/plugin marketplace add xinqilin/claude-dev-toolkit-marketplace
/plugin install java-backend@xinqilin
```

If you used `install.sh`, remove the symlinks it created under `~/.claude/agents` and `~/.claude/skills` that point into your clone (with the 1.x `uninstall.sh`, or by hand).

### Added

- `transactions-consistency`: isolation as MySQL InnoDB and PostgreSQL actually implement it, concurrency guards in Spring Data JPA, retries, and DDIA patterns (idempotency keys, transactional outbox, sagas, replica lag, hot keys).
- `jpa-hibernate`: fetching and pagination (including the Hibernate 7.4 change), the persistence context, `save()`/merge, ID strategy vs. JDBC batching, `@Transactional` pitfalls, Open Session in View.
- `sql-performance` (formerly `mysql-optimization`): index design and query patterns for both MySQL and PostgreSQL, per-database plan reading, online schema changes, connection pool sizing.
- `java-testing` and `/java-backend:write-test`: Spring Boot 3 vs 4 test APIs, Testcontainers 2, concurrency tests against a real database.
- `spring-boot-baseline`: what changed in Spring Boot 4.0 and the versions Spring Boot 4.1 manages.
- `data-architect` agent for data-intensive design and query optimization.
- An eval suite comparing Claude with and without the plugin.
- Bilingual picture explainers in `docs/`.

### Changed

- Review and analysis commands run in read-only agents that preload the relevant knowledge; agents and skills answer in the user's language.
- Every behavioral claim was checked against vendor documentation or source code, and reference files list their sources.

### Fixed

Wrong guidance that shipped in 1.x:

- Composite index order is equality columns first and the range or sort column last, not "most selective column first".
- In MySQL, comparing a string column with a number disables its index; the reverse doesn't.
- MySQL materializes a CTE at most once per query.
- `verify(mock).method()` already means `times(1)` and fails when the method wasn't called.
- `Stream.toList()` copies its source; Lombok `@Builder` cannot bypass record validation.
- HikariCP recommends a fixed-size pool (leave `minimum-idle` unset).
- `@MockBean` no longer exists on Spring Boot 4; use `@MockitoBean`.

## 1.3.0

- Version bump so marketplace installs receive the 1.2.x content changes; README explains how marketplace updates work.

## 1.2.0

- Gotchas sections in every skill; descriptions rewritten as trigger conditions; long examples moved to `references/`.
