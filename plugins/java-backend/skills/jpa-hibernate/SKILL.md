---
name: jpa-hibernate
description: Spring Data JPA and Hibernate 6/7 behavior that decides correctness and performance (N+1, fetch joins and pagination, persistence context, save()/merge, ID generation and batching, @Transactional semantics, OSIV). Use when reviewing or writing entities, repositories, or @Transactional services.
user-invocable: false
allowed-tools: Read, Grep, Glob
---

# JPA and Hibernate

Spring Boot 4.1 manages Hibernate ORM 7.4; Spring Boot 4.0 manages 7.2, and 3.5 manages 6.6. Several behaviors below changed between those versions, so check the project's Hibernate version before advising.

## The persistence context decides what SQL runs

- Entities loaded in a transaction are **managed**: changes are written at flush through dirty checking, with no `save()` call needed.
- Flush happens before commit and, by default, before queries that may be affected by pending changes. Bulk JPQL updates and native queries bypass managed state; see `references/persistence-context.md`.
- `@Transactional(readOnly = true)` with JPA sets Hibernate's flush mode to `MANUAL`, marks the session read-only (no dirty-checking snapshots), and calls `Connection.setReadOnly(true)`. Use it for read paths: it saves memory and CPU, but it is not a write firewall.

## Fetching

- **N+1**: a lazy association touched in a loop issues one query per row. Fix it per use case with `JOIN FETCH`, `@EntityGraph`, or batch fetching (`@BatchSize`, `hibernate.default_batch_fetch_size`). Avoid `FetchType.EAGER`: it applies to every query and cannot be turned off per query.
- `@ManyToOne` and `@OneToOne` are **eager by default** in JPA; declare `fetch = FetchType.LAZY` explicitly.
- **Fetching two `List` collections in one query** fails with `MultipleBagFetchException` ("cannot simultaneously fetch multiple bags"). Fetch one collection per query, or use batch fetching.
- **Collection fetch join + pagination**:
  - Hibernate before 7.4 (Spring Boot 3.x and 4.0) applies the limit **in memory** after loading every matching row.
  - Hibernate 7.4 (Spring Boot 4.1) applies it in the database on databases that support limits in subqueries, which includes MySQL and PostgreSQL.
  - Set `hibernate.query.fail_on_pagination_over_collection_fetch=true` to turn any remaining in-memory case into an error. For portable code, page the ids first, then fetch by id.
- **Projections** for read-only views: interface or record/DTO projections select only the needed columns and create no managed entities.

Details and examples: `references/fetching.md`.

## Writing

- `save()` calls `persist` for new entities and `merge` otherwise. An entity is "new" when its non-primitive `@Version` is `null`, or, without a version, when its id is `null`. An entity with an **application-assigned id** is therefore merged, which issues an extra `SELECT`; implement `Persistable` to control this.
- Use `getReferenceById(id)` to set a foreign key without loading the referenced row.
- **`IDENTITY` ids disable JDBC insert batching** (stated in the Hibernate user guide). MySQL `AUTO_INCREMENT` is `IDENTITY`. PostgreSQL sequences with `allocationSize` greater than 1 keep batching.
- For large inserts: `hibernate.jdbc.batch_size`, flush and clear every batch, and the driver's batch rewrite option (`rewriteBatchedStatements` for Connector/J, `reWriteBatchedInserts` for pgjdbc).

Details: `references/ids-and-batching.md`.

## Transactions

- Only calls through the Spring proxy are transactional: **self-invocation** and calls during `@PostConstruct` get no transaction.
- **Rollback rules**: only `RuntimeException` and `Error` roll back by default. A checked exception commits whatever was flushed unless `rollbackFor` says otherwise.
- **`REQUIRES_NEW`** takes a second pooled connection while the outer one stays bound, which can exhaust the pool and deadlock.
- **Open Session in View** (`spring.jpa.open-in-view`) is on by default in web applications, and Spring Boot logs a warning when you leave it unset. It hides `LazyInitializationException` by running lazy-loading queries during view rendering, outside any transaction. Set it to `false` and fetch what each endpoint needs.

Details: `references/transactional-semantics.md`. For isolation and concurrency guards, use `java-backend:transactions-consistency`.

## When to Apply

- Reviewing or writing entities, repositories, or `@Transactional` service methods
- Diagnosing N+1 queries, slow pages, `LazyInitializationException`, or memory growth in batch jobs
- Choosing ID generation, batching, or fetch strategies
- Upgrading across Hibernate 6 and 7 / Spring Boot 3 and 4

## Gotchas

<!-- Keep adding mistakes Claude repeatedly makes. -->

- **Calling `save()` on a managed entity is redundant**: dirty checking already writes the change. Adding `save()` everywhere hides the real transaction boundary.
- **"JOIN FETCH + Pageable loads everything into memory" depends on the version**: true for Hibernate before 7.4, fixed in 7.4 for MySQL and PostgreSQL. Check the version before flagging it.
- **`FetchType.EAGER` is not an N+1 fix**: it often turns into one query per row anyway, for every query that touches the entity.
- **Bulk `@Modifying` queries leave stale entities**: entities already loaded keep their old state; use `clearAutomatically = true` or reload.
- **A checked exception does not roll back**: `throws IOException` from a `@Transactional` method commits by default.
- **Switching MySQL entities from `IDENTITY` to `SEQUENCE` is not a free batching fix**: MySQL has no sequences, so Hibernate emulates them with a table. Assign ids in the application, or batch through JDBC, instead.
- **Don't add `equals`/`hashCode` to every entity by reflex**: the Hibernate guide's only absolute case is classes used as identifiers. When entities go into `Set`s across sessions, base equality on an immutable business key, or on the id with a constant `hashCode`.
- **Hibernate 6+ logs bind parameters under `org.hibernate.orm.jdbc.bind`**, not `org.hibernate.type.descriptor.sql.BasicBinder` as in Hibernate 5.

## Sources

See the Sources section at the end of each reference file.
