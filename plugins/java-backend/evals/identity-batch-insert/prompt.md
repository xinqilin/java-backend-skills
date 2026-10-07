---
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Agent]
tags: [jpa, mysql]
---

Our nightly import saves about 200,000 rows with `repository.saveAll(batch)` in chunks of 1,000, inside one transaction per chunk. We set `spring.jpa.properties.hibernate.jdbc.batch_size=50`, but the SQL log still shows one INSERT round trip per row. Stack: Spring Boot 4.1, Hibernate 7.4, MySQL 8.4.

```java
@Entity
public class ImportedRecord {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String externalId;
    private String payload;
}
```

Why isn't batching working, and what should we do?
