---
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Agent]
tags: [jpa, hibernate]
---

This endpoint got slow and memory usage spikes when the orders table grew to a few million rows. Stack: Spring Boot 3.5 (Hibernate 6.6), MySQL 8.4. What is wrong and how do we fix it?

```java
public interface OrderRepository extends JpaRepository<Order, Long> {
    @Query("select o from Order o join fetch o.items where o.status = :status")
    Page<Order> findByStatusWithItems(@Param("status") OrderStatus status, Pageable pageable);
}
```

`Order.items` is a `@OneToMany List<OrderItem>`. The controller calls it with `PageRequest.of(page, 20)`.
