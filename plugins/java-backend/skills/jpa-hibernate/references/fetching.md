# Fetching: N+1, Fetch Joins, Pagination, Projections

## Mapping defaults

```java
@Entity
public class Order {
    @ManyToOne(fetch = FetchType.LAZY)   // JPA default for @ManyToOne/@OneToOne is EAGER: override it
    private Customer customer;

    @OneToMany(mappedBy = "order")       // collections are LAZY by default
    private List<OrderItem> items;
}
```

Keep every association lazy in the mapping, then decide what to fetch per use case. `FetchType.EAGER` cannot be switched off for a query, and for JPQL queries Hibernate loads eager associations that the query didn't join with extra selects.

## N+1

```java
List<Order> orders = orderRepository.findByStatus(PENDING);  // 1 query
for (Order order : orders) {
    order.getCustomer().getName();                           // +1 query per order
}
```

Spot it by counting SQL statements per request: Hibernate statistics, or the `org.hibernate.SQL` logger in tests.

### Fix 1: fetch join

```java
@Query("select o from Order o join fetch o.customer where o.status = :status")
List<Order> findByStatusWithCustomer(@Param("status") OrderStatus status);
```

### Fix 2: entity graph

```java
@EntityGraph(attributePaths = {"customer"})
List<Order> findByStatus(OrderStatus status);
```

### Fix 3: batch fetching

```yaml
spring:
  jpa:
    properties:
      hibernate:
        default_batch_fetch_size: 50   # without it, only @BatchSize-annotated associations batch
```

Lazy associations are then loaded for up to 50 owners per query (`where id in (...)`) instead of one by one. This works without changing queries and also covers paths you didn't anticipate.

## Fetching several collections

- Fetching two `List` (bag) collections in one query fails with `MultipleBagFetchException: cannot simultaneously fetch multiple bags`.
- Turning them into `Set`s avoids the exception but multiplies rows (a Cartesian product of the two collections).
- Instead, fetch one collection per query in the same transaction (the persistence context merges the results), or rely on batch fetching:

```java
@Query("select distinct o from Order o join fetch o.items where o.id in :ids")
List<Order> fetchItems(@Param("ids") Collection<Long> ids);

@Query("select distinct o from Order o join fetch o.payments where o.id in :ids")
List<Order> fetchPayments(@Param("ids") Collection<Long> ids);
```

## Collection fetch join + pagination

| Hibernate | Spring Boot | Behavior with a collection fetch join plus `Pageable`/`setMaxResults` |
|-----------|-------------|-------------------------------------------------------------------------|
| 6.x, 7.0-7.3 | 3.x, 4.0 | Hibernate loads **all** matching rows and applies the limit in memory |
| 7.4+ | 4.1 | The limit is applied in the database on databases that support limits and offsets in subqueries (MySQL and PostgreSQL dialects do); in-memory remains only for databases that don't |

- `hibernate.query.fail_on_pagination_over_collection_fetch=true` makes Hibernate throw instead of silently paging in memory. Turn it on in every project.
- The version-independent pattern is to page ids, then fetch:

```java
@Query("select o.id from Order o where o.status = :status")
Page<Long> findIdsByStatus(@Param("status") OrderStatus status, Pageable pageable);

@Query("select distinct o from Order o join fetch o.items where o.id in :ids")
List<Order> findWithItemsByIdIn(@Param("ids") Collection<Long> ids);
```

- A `Page` return type also runs a count query; give `@Query` an explicit `countQuery` when the derived one would include the fetch join.

## Projections for read paths

```java
public interface OrderSummary {        // interface projection
    Long getId();
    OrderStatus getStatus();
    BigDecimal getTotal();
}
List<OrderSummary> findByCustomerId(Long customerId);

public record OrderRow(Long id, OrderStatus status, BigDecimal total) { }   // DTO projection
@Query("select new com.example.order.OrderRow(o.id, o.status, o.total) from Order o where o.customer.id = :id")
List<OrderRow> findRowsByCustomerId(@Param("id") Long id);
```

Projections select only the listed columns and create no managed entities, so there is no dirty checking and no lazy-loading surprise.

## Open Session in View and LazyInitializationException

- `spring.jpa.open-in-view` is enabled by default for web applications; Spring Boot registers an `OpenEntityManagerInViewInterceptor` and logs a warning at startup when the property is left unset.
- With it on, lazy associations touched while rendering the response trigger queries after the service transaction has ended, outside any transaction, and the connection is held for the whole request.
- Set it to `false`. Then a `LazyInitializationException` points to a missing fetch, which you fix with a fetch join, an entity graph, or a projection, not by re-enabling OSIV or switching to `EAGER`.

## Sources

- Hibernate ORM 7.4 User Guide (fetching, batch fetching settings, pagination with fetch joins, `fail_on_pagination_over_collection_fetch`): https://docs.hibernate.org/orm/7.4/userguide/html_single/
- Hibernate ORM 7.4.5 source, `MultipleBagFetchException`; `supportsOffsetInSubquery` in `MySQLDialect` and `PostgreSQLDialect`: https://github.com/hibernate/hibernate-orm/tree/7.4.5/hibernate-core/src/main/java/org/hibernate
- Jakarta Persistence 3.2, `ManyToOne` / `OneToOne` fetch defaults: https://jakarta.ee/specifications/persistence/3.2/apidocs/
- Spring Boot reference, Spring Data JPA and `spring.jpa.open-in-view`: https://docs.spring.io/spring-boot/reference/data/sql.html
- Spring Boot 4.1.1 source, OSIV startup warning (`JpaBaseConfiguration`): https://github.com/spring-projects/spring-boot/tree/v4.1.1/module/spring-boot-jpa
- Spring Boot dependency versions (Hibernate per Boot release): https://github.com/spring-projects/spring-boot/blob/v4.1.1/platform/spring-boot-dependencies/build.gradle
