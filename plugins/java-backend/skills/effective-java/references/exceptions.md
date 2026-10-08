# Exceptions Around Repositories

Items 73 and 76 of *Effective Java* (3rd ed.), applied to Spring Data JPA. The example is our own and compiles on Spring Boot 4.1 (Hibernate 7.4, Java 21).

## Translate a constraint violation where the transaction ends (Item 73)

```java
public UUID redeem(UUID campaignId, UUID userId) {     // not @Transactional
    try {
        return redemptions.redeem(campaignId, userId); // @Transactional: commits before returning
    } catch (DataIntegrityViolationException e) {
        if (isUniqueViolation(e)) {
            throw new AlreadyRedeemedException(campaignId, userId, e);
        }
        throw e;
    }
}

private static boolean isUniqueViolation(Throwable e) { // getKind() needs Hibernate 6.5+
    for (Throwable t = e; t != null; t = t.getCause()) {
        if (t instanceof ConstraintViolationException violation) { // org.hibernate.exception
            return violation.getKind() == ConstraintKind.UNIQUE;
        }
    }
    return false;
}
```

- Hibernate writes the `INSERT` at flush, which usually happens at commit, after the service method's last line. A `try` around `save()` inside the transaction doesn't see the violation.
- Catching it inside the transaction doesn't help either. The exception passed through the repository's own transactional proxy, which marked the shared transaction rollback-only, so the commit fails with `UnexpectedRollbackException` (`java-backend:jpa-hibernate`, `references/transactional-semantics.md`). On PostgreSQL, the failed statement has also aborted the transaction.
- Translate only the violation you expect. A foreign-key or `NOT NULL` violation is a bug, so rethrow it. Hibernate 6.5 and later expose the violation's kind (`ConstraintKind.UNIQUE`) and, when the dialect can extract it, the constraint name (`getConstraintName()`). On older versions, match the constraint name.
- Keep the cause (`new AlreadyRedeemedException(..., e)`), so the log still shows the SQL and the constraint.
- For the full redemption design (unique keys, idempotency, the replayed response), see `java-backend:design-solution` (`references/design-solution-example.md`).

## Failure atomicity after a rollback (Item 76)

- A rollback undoes the database changes, not the Java objects. Managed entities keep the values the failed transaction gave them, and the Hibernate session is unusable after the exception.
- A retry therefore runs a whole new transaction that reloads its entities. It never reuses entities, or the `EntityManager`, from the failed attempt (`java-backend:transactions-consistency` for retry rules).

## Sources

- Joshua Bloch, *Effective Java* (3rd ed.), ch. 10 "Exceptions" (items 73, 76)
- Spring Framework reference, Transaction Propagation (rollback-only and `UnexpectedRollbackException`): https://docs.spring.io/spring-framework/reference/data-access/transaction/declarative/tx-propagation.html
- Hibernate ORM 7.4 User Guide, exception handling (a rollback doesn't restore business objects; Hibernate exceptions are not recoverable): https://docs.hibernate.org/orm/7.4/userguide/html_single/
- Hibernate ORM source, `ConstraintViolationException` (`getKind()` since 6.5): https://github.com/hibernate/hibernate-orm/blob/7.4.5/hibernate-core/src/main/java/org/hibernate/exception/ConstraintViolationException.java
