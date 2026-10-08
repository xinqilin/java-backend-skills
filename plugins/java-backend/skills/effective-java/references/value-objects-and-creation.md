# Value Objects, Entity Construction, and Resources

Items 1, 2, 9, 10, 11, 15, 17, and 50 of *Effective Java* (3rd ed.), applied to JPA entities and the values they hold. The examples are our own and compile on Spring Boot 4.1 (Hibernate 7.4, Java 21).

## Money: one scale per currency

```java
@Embeddable
public record Money(@Column(precision = 19, scale = 2) BigDecimal amount, Currency currency) {

    public Money {
        Objects.requireNonNull(amount, "amount");
        Objects.requireNonNull(currency, "currency");
        try {
            // One scale per currency, so the generated equals/hashCode agree with numeric equality.
            // UNNECESSARY rejects 10.005 TWD instead of rounding it silently.
            amount = amount.setScale(currency.getDefaultFractionDigits(), RoundingMode.UNNECESSARY);
        } catch (ArithmeticException e) {
            throw new IllegalArgumentException(amount + " has more decimals than " + currency + " allows", e);
        }
    }

    public static Money zero(Currency currency) {
        return new Money(BigDecimal.ZERO, currency);
    }

    public Money add(Money other) {
        return new Money(amount.add(sameCurrency(other).amount), currency);
    }

    public Money subtract(Money other) {
        return new Money(amount.subtract(sameCurrency(other).amount), currency);
    }

    // Tax, discounts, splits: the caller decides how to round.
    public Money percent(BigDecimal rate, RoundingMode rounding) {
        BigDecimal raw = amount.multiply(rate).movePointLeft(2);
        return new Money(raw.setScale(currency.getDefaultFractionDigits(), rounding), currency);
    }

    public boolean isNegative() {
        return amount.signum() < 0;
    }

    private Money sameCurrency(Money other) {
        if (!currency.equals(other.currency)) {
            throw new IllegalArgumentException(currency + " and " + other.currency + " don't mix");
        }
        return other;
    }
}
```

Why each part is there:

- `BigDecimal.equals` and `hashCode` include the scale. `2.0` and `2.00` compare as equal (`compareTo` returns 0) but are not `equals`, and their hash codes differ. A record's generated `equals` uses its components' `equals`, so without normalization `new Money(new BigDecimal("100"), TWD)` is not equal to the `100.00` loaded from a `DECIMAL(19,2)` column. As a `HashMap` key or in a `HashSet`, the two count as different values.
- `setScale(..., RoundingMode.UNNECESSARY)` drops or pads trailing zeros and throws `ArithmeticException` when digits would be lost. The constructor rethrows it as `IllegalArgumentException`, which the web layer can map to 400.
- `Currency.getDefaultFractionDigits()` is 2 for TWD and USD, 0 for JPY, and 3 for KWD. Choose a column scale that covers every currency you accept. PostgreSQL silently rounds a value whose scale exceeds the column's.
- Hibernate 6.2 and later map a record as an `@Embeddable` and create it through its canonical constructor, so loaded values pass through the same normalization. A value stored with more digits, for example by another system, fails on load instead of being rounded.
- Rounding is a business rule (invoices, tax authorities, and payment providers differ), so `percent` takes the `RoundingMode` from its caller instead of choosing one.

When you can't normalize, for example when one type legitimately holds values with different scales, write `equals` and `hashCode` by hand, consistently:

```java
@Override
public boolean equals(Object o) {
    return o instanceof Quantity q && value.compareTo(q.value) == 0 && unit.equals(q.unit);
}

@Override
public int hashCode() {
    return Objects.hash(value.stripTrailingZeros(), unit); // 2.0 and 2.00 hash alike
}
```

## Entities: constructor, factory, behavior (Items 1, 15, 17)

```java
@Entity
public class Account {

    @Id
    private UUID id;

    @Version
    private Long version;

    @Column(nullable = false)
    private UUID ownerId;

    @Embedded
    private Money balance;

    protected Account() { // JPA only; application code goes through open()
    }

    public static Account open(UUID ownerId, Currency currency) {
        Account account = new Account();
        account.id = UUID.randomUUID();
        account.ownerId = ownerId;
        account.balance = Money.zero(currency);
        return account;
    }

    public void withdraw(Money amount) {
        Money after = balance.subtract(amount);
        if (after.isNegative()) {
            throw new InsufficientFundsException(id, amount);
        }
        balance = after;
    }

    public UUID getId() {
        return id;
    }

    public Money getBalance() {
        return balance;
    }
}
```

- Jakarta Persistence requires a public or protected no-arg constructor, a non-final class, and non-final persistent fields and methods. `protected` keeps the constructor out of application code.
- `open(...)` is the only way to create an account. It assigns the id and the initial state. Name factories after what they do (`open`, `place`, `of`, `parse`).
- Hibernate rebuilds loaded entities through the no-arg constructor and field access, so no second factory is needed. A `reconstitute(...)` factory only exists where a mapper builds domain objects from a separate persistence model (the strict variant in `java-backend:clean-architecture`).
- `@Version Long version` stays `null` until the first persist. That also tells Spring Data's `save()` that an entity with an assigned id is new, so it persists without a `SELECT` (`java-backend:jpa-hibernate`).
- `withdraw` checks the invariant in memory. Two concurrent withdrawals still need a guard in the database, here the `@Version` column (`java-backend:transactions-consistency`).

### Mapped collections (Item 50)

```java
@OneToMany(mappedBy = "order", cascade = CascadeType.ALL, orphanRemoval = true)
private List<OrderLine> lines = new ArrayList<>();

public List<OrderLine> getLines() {
    return Collections.unmodifiableList(lines); // read-only view; changes go through the aggregate
}
```

- Hand out a read-only view, and change the list only through the aggregate's methods, so the aggregate can keep its invariants (the order total, line limits).
- Don't copy defensively into the field (`this.lines = List.copyOf(newLines)`) on a loaded entity. Hibernate tracks the collection instance it put there. With `orphanRemoval = true`, the replaced collection fails at flush with "A collection with orphan deletion was no longer referenced by the owning entity instance". Clear and refill the existing collection instead.

## Builders (Item 2)

A builder pays off for commands and search criteria with many optional fields. With Lombok's `@Builder` on a record, the generated builder calls the canonical constructor, so the compact constructor's defaults and checks still run:

```java
@Builder
public record OrderSearch(String status, UUID customerId, Instant placedAfter, Integer limit) {

    public OrderSearch {
        limit = limit == null ? 50 : limit; // records have no field initializers, so defaults go here
        if (limit < 1 || limit > 500) {
            throw new IllegalArgumentException("limit must be between 1 and 500: " + limit);
        }
    }
}

OrderSearch pending = OrderSearch.builder().status("PENDING").build(); // limit = 50
```

On an entity, `@Builder` generates an all-arguments constructor and lets callers leave out required fields. Prefer a factory method with the required parameters.

## JDBC resources inside a transaction (Item 9)

- `JpaTransactionManager` lets plain JDBC code join the JPA transaction, as long as it obtains its connection through `DataSourceUtils.getConnection(dataSource)` or a `TransactionAwareDataSourceProxy`. `JdbcTemplate` and `JdbcClient` already do this.
- `dataSource.getConnection()` takes a second pooled connection outside the transaction. That connection doesn't see the transaction's uncommitted writes, doesn't roll back with it, and can block on row locks the transaction itself holds.
- When you hold a raw `PreparedStatement` or `ResultSet`, close it with try-with-resources. Release a connection obtained through `DataSourceUtils` with `DataSourceUtils.releaseConnection`, not `close()`.

## Sources

- Joshua Bloch, *Effective Java* (3rd ed.): ch. 2 "Creating and Destroying Objects" (items 1, 2, 9), ch. 3 "Methods Common to All Objects" (items 10, 11), ch. 4 "Classes and Interfaces" (items 15, 17), ch. 8 "Methods" (item 50)
- Java SE API, `BigDecimal` (`equals`, `hashCode`, `setScale`, `stripTrailingZeros`): https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/math/BigDecimal.html
- Java SE API, `Currency.getDefaultFractionDigits`: https://docs.oracle.com/en/java/javase/25/docs/api/java.base/java/util/Currency.html
- Jakarta Persistence 3.2, section 2.1 "The Entity Class": https://jakarta.ee/specifications/persistence/3.2/jakarta-persistence-spec-3.2
- Hibernate ORM 6.2 release (Java records): https://hibernate.org/orm/releases/6.2/
- Hibernate ORM 7.4.5 source, `EmbeddableInstantiatorRecordStandard` (canonical constructor) and `engine/internal/Collections` (orphan deletion error): https://github.com/hibernate/hibernate-orm/tree/7.4.5/hibernate-core/src/main/java/org/hibernate
- PostgreSQL 18, Numeric Types (rounding to the declared scale): https://www.postgresql.org/docs/18/datatype-numeric.html
- Spring Framework Javadoc, `JpaTransactionManager` (plain JDBC access within a transaction): https://docs.spring.io/spring-framework/docs/current/javadoc-api/org/springframework/orm/jpa/JpaTransactionManager.html
- Project Lombok, `@Builder`: https://projectlombok.org/features/Builder
