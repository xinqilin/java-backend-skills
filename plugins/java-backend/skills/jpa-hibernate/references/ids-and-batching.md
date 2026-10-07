# ID Generation and Batch Writes

## Why the id strategy decides batching

The Hibernate user guide: "Hibernate disables insert batching at the JDBC level transparently if you use an identity identifier generator." With `IDENTITY`, Hibernate must execute each `INSERT` immediately to learn the generated key.

| Strategy | MySQL | PostgreSQL | JDBC insert batching |
|----------|-------|------------|----------------------|
| `GenerationType.IDENTITY` | `AUTO_INCREMENT`, the usual choice | `identity` / `serial` columns | **Disabled** |
| `GenerationType.SEQUENCE` | No sequences: Hibernate's `SequenceStyleGenerator` transparently falls back to a table | Native sequences | Enabled |
| Application-assigned (UUID, TSID) | Any | Any | Enabled, but see `Persistable` below |

## PostgreSQL: sequences with pooling

```java
@Id
@GeneratedValue(strategy = GenerationType.SEQUENCE, generator = "order_seq")
@SequenceGenerator(name = "order_seq", sequenceName = "order_seq", allocationSize = 50)
private Long id;
```

```sql
CREATE SEQUENCE order_seq INCREMENT BY 50;  -- must match allocationSize
```

- `allocationSize` defaults to 50 in Jakarta Persistence. With a value greater than 1, Hibernate uses a pooled optimizer: one sequence call reserves a block of ids.
- The sequence's `INCREMENT BY` must match `allocationSize`. Hibernate checks this at startup and by default throws (`hibernate.id.sequence.increment_size_mismatch_strategy = EXCEPTION`).
- Ids have gaps and are not in commit order. Never derive business meaning from them.

## MySQL: options when you need batched inserts

`AUTO_INCREMENT` (`IDENTITY`) disables Hibernate's insert batching, and the table-backed sequence emulation adds a round trip and a contended row. Options:

1. **Keep `IDENTITY`** when insert volume is modest. Most OLTP writes are one row per request anyway.
2. **Assign ids in the application** with time-ordered values (UUIDv7, TSID) so Hibernate can batch. InnoDB stores rows in primary-key order (the clustered index) and every secondary index stores the primary key, so prefer time-ordered over random values, and compact keys over long ones.
3. **Bypass the ORM for bulk loads**: `JdbcTemplate.batchUpdate` with the Connector/J property `rewriteBatchedStatements=true`, which rewrites a prepared `INSERT` batch into multi-row `INSERT` statements.

## Settings for batched writes

```yaml
spring:
  jpa:
    properties:
      hibernate:
        jdbc:
          batch_size: 50        # the user guide suggests a value between 10 and 50
        order_inserts: true     # group inserts by entity so batches aren't broken up
        order_updates: true
  datasource:
    url: jdbc:postgresql://db/app?reWriteBatchedInserts=true   # pgjdbc: multi-row INSERT
    # MySQL: jdbc:mysql://db/app?rewriteBatchedStatements=true
```

- `reWriteBatchedInserts` (pgjdbc) and `rewriteBatchedStatements` (Connector/J) are off by default.
- Connector/J warns that `rewriteBatchedStatements` may allow SQL injection when used with plain (non-prepared) statements built from unsanitized input. Use it only with prepared statements.
- Flush and clear the persistence context every `batch_size` entities (`persistence-context.md`).

## Application-assigned ids and `save()`

An entity whose id is set before saving is "not new" to Spring Data, so `save()` merges it (a `SELECT` plus an `INSERT`). Make `save()` persist directly:

```java
@Entity
public class Event implements Persistable<UUID> {
    @Id private UUID id;
    @Transient private boolean isNew = true;

    @Override public UUID getId() { return id; }
    @Override public boolean isNew() { return isNew; }

    @PostPersist @PostLoad
    void markNotNew() { this.isNew = false; }
}
```

## Sources

- Hibernate ORM 7.4 User Guide, Batching ("disables insert batching ... identity identifier generator"), identifier generators, `SequenceStyleGenerator`, settings `hibernate.jdbc.batch_size` and `hibernate.id.sequence.increment_size_mismatch_strategy`: https://docs.hibernate.org/orm/7.4/userguide/html_single/
- Hibernate ORM 7.4.5 source, `MySQLDialect.getSequenceSupport()` returns `NoSequenceSupport`: https://github.com/hibernate/hibernate-orm/blob/7.4.5/hibernate-core/src/main/java/org/hibernate/dialect/MySQLDialect.java
- Jakarta Persistence 3.2, `SequenceGenerator.allocationSize` (default 50): https://jakarta.ee/specifications/persistence/3.2/apidocs/
- Spring Data JPA, entity state detection and `Persistable`: https://docs.spring.io/spring-data/jpa/reference/jpa/entity-persistence.html
- MySQL Connector/J, Performance Extensions (`rewriteBatchedStatements`): https://dev.mysql.com/doc/connector-j/en/connector-j-connp-props-performance-extensions.html
- PostgreSQL JDBC driver, connection parameters (`reWriteBatchedInserts`): https://jdbc.postgresql.org/documentation/use/
- MySQL 8.4, Clustered and Secondary Indexes: https://dev.mysql.com/doc/refman/8.4/en/innodb-index-types.html
