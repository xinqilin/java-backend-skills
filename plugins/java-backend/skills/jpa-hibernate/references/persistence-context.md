# Persistence Context: Dirty Checking, Flush, save(), Bulk Updates

## Managed entities are written automatically

```java
@Transactional
public void rename(long id, String name) {
    Customer c = customerRepository.findById(id).orElseThrow();
    c.setName(name);          // no save(): dirty checking writes it at flush
}
```

- Within one persistence context, Hibernate guarantees one Java instance per database row, so two lookups of the same id return the same object.
- Dirty checking compares each managed entity with a snapshot taken at load time. Loading thousands of entities costs memory and CPU even if nothing changes, which is why read paths should use `readOnly = true` or projections.

## What `@Transactional(readOnly = true)` actually does with JPA

Read from Spring Framework 7.0.9's `HibernateJpaDialect` and `DataSourceUtils`:

1. The Hibernate flush mode is set to `MANUAL`, so pending changes are not flushed.
2. For the usual transaction-scoped `EntityManager`, the session is set to default read-only, so loaded entities keep no dirty-checking snapshots.
3. The JDBC connection gets `setReadOnly(true)` and is reset afterwards. Spring's `HibernateJpaVendorAdapter` switches Hibernate to the `DELAYED_ACQUISITION_AND_HOLD` connection mode so this connection preparation can happen.

Whether the database rejects writes on such a connection depends on the JDBC driver and database. Treat `readOnly` as an optimization and a routing signal, not as a security boundary.

## `save()` is persist-or-merge

Spring Data JPA's `save()` calls `persist` for a new entity and `merge` otherwise. "New" is decided by:

1. A non-primitive `@Version` attribute: `null` means new. A primitive `long version` cannot be used for this, because JPA treats 0 as the first version.
2. Otherwise the id: `null` means new.
3. Or your own logic, by implementing `Persistable<ID>.isNew()`.

Consequences:

- An entity with an **application-assigned id** (UUID, natural key) looks "not new", so `save()` calls `merge`, which `SELECT`s the row before inserting it. Implement `Persistable` (for example with a transient `isNew` flag set in the constructor and cleared in `@PostPersist` / `@PostLoad`), or call `persist` through a custom repository.
- `merge` returns a **different instance**; keep using the returned object, not the one you passed in.

## References without a query

```java
OrderLine line = new OrderLine(orderRepository.getReferenceById(orderId), sku, qty);
```

`getReferenceById` returns a proxy without hitting the database, which is enough to set a foreign key. Touching any other attribute initializes it, and a missing row fails at that point (typically `EntityNotFoundException`).

## Bulk updates bypass the persistence context

```java
@Modifying(clearAutomatically = true)
@Query("update Order o set o.status = :to where o.status = :from")
int bulkUpdateStatus(@Param("from") OrderStatus from, @Param("to") OrderStatus to);
```

- JPQL bulk updates and native statements write directly to the database. Entities already loaded in the same transaction keep their old state.
- `clearAutomatically = true` clears the persistence context afterwards, discarding unflushed changes too. `flushAutomatically = true` flushes pending changes before the bulk statement runs.
- A bulk update does not touch the `@Version` column, so it doesn't participate in optimistic locking. Hibernate's HQL-only `update versioned ...` increments it; plain JPQL cannot.

## Large batch jobs

```java
@Transactional
public void importAll(List<CustomerRow> rows) {
    int batchSize = 50; // match hibernate.jdbc.batch_size
    for (int i = 0; i < rows.size(); i++) {
        entityManager.persist(Customer.from(rows.get(i)));
        if ((i + 1) % batchSize == 0) {
            entityManager.flush();
            entityManager.clear(); // keeps the persistence context from growing without bound
        }
    }
}
```

After `clear()`, entities loaded earlier are detached; don't keep using them. For millions of rows, split the work into several transactions so a failure doesn't roll back everything and locks aren't held for the whole run.

## equals and hashCode

The Hibernate user guide names one absolute case: a class used as an identifier (a composite key) must implement `equals`/`hashCode` from its id values. Beyond that, it suggests considering not implementing them at all. When entities must work in `Set`s across sessions:

- Prefer an immutable business key (for example `@NaturalId`).
- If you use the generated id, the id is `null` before persist, so return a constant `hashCode()` and compare ids only when both are non-null.
- Never include lazy associations or mutable fields, and never use Lombok `@Data` or `@EqualsAndHashCode` on entities.

## Observing what Hibernate does

```yaml
logging:
  level:
    org.hibernate.SQL: debug              # statements
    org.hibernate.orm.jdbc.bind: trace    # bind parameters (Hibernate 6+)
spring:
  jpa:
    properties:
      hibernate:
        generate_statistics: true         # statement and cache counts per session
```

Use these in tests, for example to assert the number of statements an endpoint issues. Keep them off in production; bind logging prints parameter values.

## Sources

- Spring Data JPA, Persisting Entities (entity state detection): https://docs.spring.io/spring-data/jpa/reference/jpa/entity-persistence.html
- Spring Data JPA, Modifying queries: https://docs.spring.io/spring-data/jpa/reference/jpa/query-methods.html
- Spring Framework 7.0.9 source, `HibernateJpaDialect`, `HibernateJpaVendorAdapter`, `DataSourceUtils`: https://github.com/spring-projects/spring-framework/tree/v7.0.9
- Hibernate ORM 7.4 User Guide (persistence context, batching, "Implementing equals() and hashCode()"): https://docs.hibernate.org/orm/7.4/userguide/html_single/
- Hibernate ORM 7.4.5 source, `JdbcBindingLogging` (`org.hibernate.orm.jdbc.bind`): https://github.com/hibernate/hibernate-orm/blob/7.4.5/hibernate-core/src/main/java/org/hibernate/type/descriptor/JdbcBindingLogging.java
