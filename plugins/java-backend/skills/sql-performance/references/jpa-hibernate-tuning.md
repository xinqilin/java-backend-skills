# JPA/Hibernate Performance Tuning

## Fetch Strategy

### LAZY vs EAGER

```java
@Entity
public class Order {
    // Single entity relationships
    @ManyToOne(fetch = FetchType.LAZY)  // LAZY recommended
    private Customer customer;

    // Collections - ALWAYS LAZY
    @OneToMany(fetch = FetchType.LAZY, mappedBy = "order")
    private List<OrderItem> items;
}
```

### N+1 Problem Solutions

**Problem:**
```java
List<Order> orders = orderRepository.findAll();  // 1 query
for (Order order : orders) {
    order.getCustomer().getName();  // N queries!
}
```

**Solution 1: JOIN FETCH**

```java
@Query("SELECT o FROM Order o JOIN FETCH o.customer")
List<Order> findAllWithCustomer();

// Multiple collections? Multiple queries (due to Cartesian product)
@Query("SELECT o FROM Order o JOIN FETCH o.customer")
List<Order> findAllWithCustomer();

@Query("SELECT o FROM Order o JOIN FETCH o.items WHERE o IN :orders")
List<Order> fetchItems(@Param("orders") List<Order> orders);
```

**Solution 2: @EntityGraph**

```java
@EntityGraph(attributePaths = {"customer", "items"})
List<Order> findByStatus(OrderStatus status);

// Named entity graph
@NamedEntityGraph(
    name = "Order.withDetails",
    attributeNodes = {
        @NamedAttributeNode("customer"),
        @NamedAttributeNode(value = "items", subgraph = "items.product")
    },
    subgraphs = @NamedSubgraph(name = "items.product", attributeNodes = @NamedAttributeNode("product"))
)
@Entity
public class Order { }

@EntityGraph("Order.withDetails")
List<Order> findByCustomerId(String customerId);
```

**Solution 3: Batch Fetching**

```yaml
spring:
  jpa:
    properties:
      hibernate:
        default_batch_fetch_size: 100
```

```java
// Now when accessing lazy collections, Hibernate fetches in batches
List<Order> orders = orderRepository.findAll();  // 1 query
for (Order order : orders) {
    order.getItems().size();  // 1 query per 100 orders (instead of N)
}
```

**Solution 4: @BatchSize on Entity**

```java
@Entity
@BatchSize(size = 50)
public class OrderItem { }

// Or on collection
@OneToMany(mappedBy = "order")
@BatchSize(size = 50)
private List<OrderItem> items;
```

---

## Batch Operations

### Batch Insert Configuration

```yaml
spring:
  jpa:
    properties:
      hibernate:
        jdbc:
          batch_size: 50
          batch_versioned_data: true
        order_inserts: true
        order_updates: true
        generate_statistics: true  # For monitoring
```

### Batch Insert Code

```java
@Service
@Transactional
public class OrderService {

    @PersistenceContext
    private EntityManager entityManager;

    public void saveAll(List<Order> orders) {
        int batchSize = 50;

        for (int i = 0; i < orders.size(); i++) {
            entityManager.persist(orders.get(i));

            if (i > 0 && i % batchSize == 0) {
                entityManager.flush();
                entityManager.clear();  // Release memory
            }
        }

        entityManager.flush();
        entityManager.clear();
    }
}
```

### Bulk Update/Delete (JPQL)

```java
// Much faster than loading + modifying + saving
@Modifying
@Query("UPDATE Order o SET o.status = :newStatus WHERE o.status = :oldStatus")
int updateStatus(@Param("oldStatus") OrderStatus oldStatus,
                 @Param("newStatus") OrderStatus newStatus);

@Modifying
@Query("DELETE FROM Order o WHERE o.createdAt < :date")
int deleteOldOrders(@Param("date") LocalDateTime date);
```

**Caution:** Bulk operations bypass entity cache!

```java
@Transactional
public void processOrders() {
    Order order = orderRepository.findById(1L);  // Cached in persistence context

    orderRepository.updateAllStatus(...);  // Bypasses cache!

    order.getStatus();  // Returns stale value from cache!

    entityManager.refresh(order);  // Or clear cache first
}
```

---

## Caching

### First-Level Cache (Session Cache)

Built-in, per-transaction. No configuration needed.

```java
@Transactional
public void process() {
    Order order1 = orderRepository.findById(1L);  // DB query
    Order order2 = orderRepository.findById(1L);  // From cache (same object)
    assert order1 == order2;  // true
}
```

### Second-Level Cache

```yaml
spring:
  jpa:
    properties:
      hibernate:
        cache:
          use_second_level_cache: true
          region.factory_class: org.hibernate.cache.jcache.JCacheRegionFactory
        javax:
          cache:
            provider: org.ehcache.jsr107.EhcacheCachingProvider

# pom.xml dependencies
# - org.hibernate:hibernate-jcache
# - org.ehcache:ehcache
```

```java
@Entity
@Cacheable
@org.hibernate.annotations.Cache(usage = CacheConcurrencyStrategy.READ_WRITE)
public class Product {
    // Rarely changing, frequently read data
}

// Collection caching
@OneToMany(mappedBy = "category")
@org.hibernate.annotations.Cache(usage = CacheConcurrencyStrategy.READ_WRITE)
private List<Product> products;
```

### Query Cache

```yaml
spring:
  jpa:
    properties:
      hibernate:
        cache:
          use_query_cache: true
```

```java
@QueryHints(@QueryHint(name = "org.hibernate.cacheable", value = "true"))
List<Product> findByCategory(String category);
```

**When to use query cache:**
- Same query executed frequently
- Underlying data changes rarely
- Query parameters are repeated

---

## Connection Pool (HikariCP)

### Sizing

```
pool_size = (core_count * 2) + effective_spindle_count
```

For SSD: `effective_spindle_count` ≈ 1-2

```yaml
spring:
  datasource:
    hikari:
      maximum-pool-size: 10
      minimum-idle: 5
      idle-timeout: 300000      # 5 minutes
      max-lifetime: 1800000     # 30 minutes
      connection-timeout: 30000 # 30 seconds
      leak-detection-threshold: 60000  # 1 minute
```

### Monitoring

```java
@Component
public class HikariMetrics {

    @Autowired
    private DataSource dataSource;

    @Scheduled(fixedRate = 60000)
    public void logPoolStats() {
        if (dataSource instanceof HikariDataSource hikari) {
            HikariPoolMXBean pool = hikari.getHikariPoolMXBean();
            log.info("Pool stats - Active: {}, Idle: {}, Waiting: {}",
                pool.getActiveConnections(),
                pool.getIdleConnections(),
                pool.getThreadsAwaitingConnection());
        }
    }
}
```

---

## Read-Only Optimization

### Read-Only Transactions

```java
@Transactional(readOnly = true)
public List<Order> findOrders() {
    return orderRepository.findAll();
}
```

Benefits:
- Hibernate skips dirty checking
- No flush at end of transaction
- Database can optimize (e.g., use read replica)

### Read-Only Query Hints

```java
@QueryHints({
    @QueryHint(name = "org.hibernate.readOnly", value = "true"),
    @QueryHint(name = "org.hibernate.fetchSize", value = "50")
})
List<Order> findByStatus(OrderStatus status);
```

---

## Projection for Read-Only

### DTO Projection

```java
// Instead of loading full entity
public interface OrderSummary {
    String getId();
    String getStatus();
    BigDecimal getTotal();
}

List<OrderSummary> findByCustomerId(String customerId);

// Or with constructor expression
@Query("SELECT new com.example.OrderDTO(o.id, o.status, o.total) FROM Order o WHERE o.customerId = :id")
List<OrderDTO> findDtoByCustomerId(@Param("id") String customerId);
```

### Tuple Projection

```java
@Query("SELECT o.id as id, o.status as status, o.total as total FROM Order o")
List<Tuple> findAllTuples();

// Usage
for (Tuple t : tuples) {
    String id = t.get("id", String.class);
    OrderStatus status = t.get("status", OrderStatus.class);
}
```

---

## Statistics and Monitoring

### Enable Statistics

```yaml
spring:
  jpa:
    properties:
      hibernate:
        generate_statistics: true
```

### Log Statistics

```java
@Component
public class HibernateStatsLogger {

    @Autowired
    private EntityManagerFactory emf;

    @Scheduled(fixedRate = 60000)
    public void logStats() {
        Statistics stats = emf.unwrap(SessionFactory.class).getStatistics();
        log.info("Hibernate Stats: " +
            "Queries: {}, Cache hits: {}, Cache misses: {}, " +
            "Entity loads: {}, Entity fetches: {}",
            stats.getQueryExecutionCount(),
            stats.getSecondLevelCacheHitCount(),
            stats.getSecondLevelCacheMissCount(),
            stats.getEntityLoadCount(),
            stats.getEntityFetchCount());
    }
}
```

### SQL Logging

```yaml
# Development only!
spring:
  jpa:
    show-sql: true
    properties:
      hibernate:
        format_sql: true

logging:
  level:
    org.hibernate.SQL: DEBUG
    org.hibernate.type.descriptor.sql.BasicBinder: TRACE  # Show parameters
```

---

## Common Performance Issues Checklist

| Issue | Symptom | Solution |
|-------|---------|----------|
| N+1 Queries | Many small queries in logs | JOIN FETCH, @EntityGraph, batch_fetch_size |
| Large Result Sets | OOM, slow response | Pagination, streaming, projections |
| Eager Loading | Slow queries loading unused data | Change to LAZY, use EntityGraph when needed |
| No Batch Insert | Many individual INSERTs | Configure batch_size, use bulk operations |
| Dirty Checking Overhead | Slow transactions with many entities | Read-only transactions, clear() |
| Connection Pool Exhaustion | Timeouts, connection errors | Increase pool size, check for leaks |
| Missing Indexes | Slow queries | Analyze EXPLAIN, add appropriate indexes |
