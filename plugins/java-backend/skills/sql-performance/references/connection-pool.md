# Connection Pool Sizing (HikariCP)

Spring Boot uses HikariCP by default. Settings live under `spring.datasource.hikari.*`.

## Smaller than you think

HikariCP's own guidance ("About Pool Sizing"): you want a small pool, saturated with threads waiting for connections. A database can only make progress on as many statements at once as its CPU and I/O allow; past that, more connections add context switching and lock contention, not throughput.

Starting point, a formula the HikariCP wiki attributes to the PostgreSQL project:

```
connections = (core_count * 2) + effective_spindle_count
```

`core_count` is the database server's cores, not the application's. Treat the result as a starting point and load-test around it. Remember that every application instance has its own pool: 10 instances × 20 connections means 200 connections on one database.

## Defaults and recommendations

| Property | Default | Recommendation |
|----------|---------|----------------|
| `maximum-pool-size` | 10 | Size it with the formula, then measure |
| `minimum-idle` | same as `maximum-pool-size` | Leave it unset: HikariCP recommends a fixed-size pool for performance and spikes |
| `connection-timeout` | 30000 ms | How long `getConnection()` blocks before throwing. Lower it if callers have tighter deadlines |
| `max-lifetime` | 1800000 ms (30 min) | Set it several seconds shorter than any database- or network-imposed connection time limit |
| `idle-timeout` | 600000 ms (10 min) | Only applies when `minimum-idle` is below `maximum-pool-size` |
| `keepalive-time` | 120000 ms (2 min) | Must be below `max-lifetime`; pings idle connections so firewalls and NATs don't drop them |
| `leak-detection-threshold` | 0 (off) | Logs connections held longer than this (minimum 2000 ms); useful in staging |

## Pool exhaustion is usually a transaction problem

When requests time out waiting for a connection (`SQLTransientConnectionException ... Connection is not available, request timed out after 30000ms`), look for these before raising the pool size:

- **Long transactions**: HTTP calls, message publishing, or slow loops inside `@Transactional`. A connection is held for the whole transaction.
- **Open Session in View**: with `spring.jpa.open-in-view=true` (the default), a connection acquired during the request can be held until the response is written.
- **`REQUIRES_NEW`**: two connections per request at once. Spring's docs warn that this can exhaust the pool and deadlock unless the pool exceeds the number of concurrent threads by at least one.
- **Leaks**: connections taken outside Spring's management and never closed. `leak-detection-threshold` finds them.

## Virtual threads

With `spring.threads.virtual.enabled=true` (Spring Boot 3.2+, Java 21+), request threads are cheap, but database connections are not. The pool becomes the throttle: thousands of virtual threads can wait for 10 connections, and `connection-timeout` then decides who fails.

- Keep `maximum-pool-size` sized for the database, not for the number of threads.
- On Java 21-23, a virtual thread that blocks inside a `synchronized` block pins its carrier thread. Whether that hurts depends on how the JDBC driver and pool synchronize internally. From Java 24 (JEP 491), `synchronized` no longer pins.

## Sources

- HikariCP README, configuration properties and defaults: https://github.com/brettwooldridge/HikariCP#gear-configuration-knobs-baby
- HikariCP wiki, About Pool Sizing: https://github.com/brettwooldridge/HikariCP/wiki/About-Pool-Sizing
- Spring Framework reference, Transaction Propagation (`REQUIRES_NEW` and pool exhaustion): https://docs.spring.io/spring-framework/reference/data-access/transaction/declarative/tx-propagation.html
- Spring Boot reference, virtual threads: https://docs.spring.io/spring-boot/reference/features/spring-application.html
- JEP 491: https://openjdk.org/jeps/491
