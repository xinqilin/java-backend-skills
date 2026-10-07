# Object Creation Best Practices

## Item 1: Static Factory Methods

### Common Naming Conventions

| Name | Usage | Example |
|------|-------|---------|
| `of` | Aggregation factory | `List.of(1, 2, 3)` |
| `valueOf` | Type conversion | `BigInteger.valueOf(123)` |
| `from` | Type conversion | `Date.from(instant)` |
| `getInstance` | Singleton or cached | `Calendar.getInstance()` |
| `create` / `newInstance` | New instance each time | `Array.newInstance(type, length)` |
| `getType` / `newType` | Factory in different class | `Files.getFileStore(path)` |

### Implementation Patterns

```java
public class Order {
    private final OrderId id;
    private final OrderStatus status;
    private final LocalDateTime createdAt;

    private Order(OrderId id, OrderStatus status, LocalDateTime createdAt) {
        this.id = id;
        this.status = status;
        this.createdAt = createdAt;
    }

    // Factory for new orders
    public static Order create(CustomerId customerId, List<OrderItem> items) {
        return new Order(
            OrderId.generate(),
            OrderStatus.PENDING,
            LocalDateTime.now()
        );
    }

    // Factory for reconstitution (from DB)
    public static Order reconstitute(OrderId id, OrderStatus status, LocalDateTime createdAt) {
        return new Order(id, status, createdAt);
    }

    // Factory returning cached instance
    private static final Order EMPTY = new Order(OrderId.of("EMPTY"), OrderStatus.CANCELLED, LocalDateTime.MIN);
    public static Order empty() {
        return EMPTY;
    }
}
```

### Returning Subtype

```java
public interface PaymentProcessor {
    void process(Payment payment);

    static PaymentProcessor of(PaymentMethod method) {
        return switch (method) {
            case CREDIT_CARD -> new CreditCardProcessor();
            case BANK_TRANSFER -> new BankTransferProcessor();
            case PAYPAL -> new PayPalProcessor();
        };
    }
}
```

---

## Item 2: Builder Pattern

### When to Use

- More than 4 parameters
- Many optional parameters
- Immutable objects with complex construction

### Complete Builder Example

```java
public final class EmailMessage {
    private final String from;
    private final List<String> to;
    private final List<String> cc;
    private final List<String> bcc;
    private final String subject;
    private final String body;
    private final boolean html;
    private final List<Attachment> attachments;
    private final Priority priority;

    private EmailMessage(Builder builder) {
        this.from = builder.from;
        this.to = List.copyOf(builder.to);
        this.cc = List.copyOf(builder.cc);
        this.bcc = List.copyOf(builder.bcc);
        this.subject = builder.subject;
        this.body = builder.body;
        this.html = builder.html;
        this.attachments = List.copyOf(builder.attachments);
        this.priority = builder.priority;
    }

    public static Builder builder() {
        return new Builder();
    }

    public static class Builder {
        private String from;
        private final List<String> to = new ArrayList<>();
        private final List<String> cc = new ArrayList<>();
        private final List<String> bcc = new ArrayList<>();
        private String subject = "";
        private String body = "";
        private boolean html = false;
        private final List<Attachment> attachments = new ArrayList<>();
        private Priority priority = Priority.NORMAL;

        public Builder from(String from) {
            this.from = Objects.requireNonNull(from);
            return this;
        }

        public Builder to(String... recipients) {
            this.to.addAll(Arrays.asList(recipients));
            return this;
        }

        public Builder cc(String... recipients) {
            this.cc.addAll(Arrays.asList(recipients));
            return this;
        }

        public Builder subject(String subject) {
            this.subject = subject;
            return this;
        }

        public Builder body(String body) {
            this.body = body;
            return this;
        }

        public Builder htmlBody(String html) {
            this.body = html;
            this.html = true;
            return this;
        }

        public Builder attach(Attachment attachment) {
            this.attachments.add(attachment);
            return this;
        }

        public Builder priority(Priority priority) {
            this.priority = priority;
            return this;
        }

        public EmailMessage build() {
            validate();
            return new EmailMessage(this);
        }

        private void validate() {
            if (from == null || from.isBlank()) {
                throw new IllegalStateException("From address is required");
            }
            if (to.isEmpty()) {
                throw new IllegalStateException("At least one recipient is required");
            }
        }
    }
}

// Usage
EmailMessage email = EmailMessage.builder()
    .from("sender@example.com")
    .to("recipient1@example.com", "recipient2@example.com")
    .cc("manager@example.com")
    .subject("Important Update")
    .htmlBody("<h1>Hello</h1><p>This is the message.</p>")
    .priority(Priority.HIGH)
    .build();
```

### Builder with Lombok

```java
@Builder
@Getter
public class OrderRequest {
    private final String customerId;
    @Singular
    private final List<OrderItemRequest> items;
    @Builder.Default
    private final Currency currency = Currency.TWD;
}

// Usage
OrderRequest request = OrderRequest.builder()
    .customerId("C001")
    .item(new OrderItemRequest("P1", 2))
    .item(new OrderItemRequest("P2", 1))
    .build();
```

---

## Item 3: Singleton Pattern

### Enum Singleton (Recommended)

```java
public enum DatabaseConnection {
    INSTANCE;

    private final DataSource dataSource;

    DatabaseConnection() {
        this.dataSource = createDataSource();
    }

    public Connection getConnection() throws SQLException {
        return dataSource.getConnection();
    }

    private DataSource createDataSource() {
        HikariConfig config = new HikariConfig();
        config.setJdbcUrl("jdbc:mysql://localhost/db");
        return new HikariDataSource(config);
    }
}

// Usage
Connection conn = DatabaseConnection.INSTANCE.getConnection();
```

### Static Factory Singleton (Flexible)

```java
public class ConfigurationManager {
    private static final ConfigurationManager INSTANCE = new ConfigurationManager();

    private final Map<String, String> properties;

    private ConfigurationManager() {
        this.properties = loadProperties();
    }

    public static ConfigurationManager getInstance() {
        return INSTANCE;
    }

    public String get(String key) {
        return properties.get(key);
    }
}
```

---

## Item 5: Dependency Injection over Hardwired Resources

```java
// BAD - Hardwired dependency
public class OrderService {
    private final OrderRepository repository = new JpaOrderRepository();  // Hardwired!

    public Order findById(OrderId id) {
        return repository.findById(id);
    }
}

// GOOD - Dependency injection
public class OrderService {
    private final OrderRepository repository;

    public OrderService(OrderRepository repository) {
        this.repository = Objects.requireNonNull(repository);
    }

    public Order findById(OrderId id) {
        return repository.findById(id);
    }
}

// With Spring
@Service
public class OrderService {
    private final OrderRepository repository;

    public OrderService(OrderRepository repository) {
        this.repository = repository;
    }
}
```

---

## Item 6: Avoid Unnecessary Object Creation

### Pattern Compilation

```java
// BAD - Compiles pattern on every call
public boolean isValid(String input) {
    return input.matches("[A-Z]{2}\\d{6}");  // Creates Pattern internally
}

// GOOD - Compile once
private static final Pattern PATTERN = Pattern.compile("[A-Z]{2}\\d{6}");

public boolean isValid(String input) {
    return PATTERN.matcher(input).matches();
}
```

### Autoboxing

```java
// BAD - Creates many Long objects
public long sum() {
    Long sum = 0L;
    for (long i = 0; i < Integer.MAX_VALUE; i++) {
        sum += i;  // Autoboxing on every iteration
    }
    return sum;
}

// GOOD - Use primitive
public long sum() {
    long sum = 0L;
    for (long i = 0; i < Integer.MAX_VALUE; i++) {
        sum += i;
    }
    return sum;
}
```

### Date Formatting

```java
// BAD - Creates new formatter each time
public String formatDate(LocalDate date) {
    return DateTimeFormatter.ofPattern("yyyy-MM-dd").format(date);
}

// GOOD - Reuse formatter (DateTimeFormatter is immutable and thread-safe)
private static final DateTimeFormatter DATE_FORMATTER =
    DateTimeFormatter.ofPattern("yyyy-MM-dd");

public String formatDate(LocalDate date) {
    return DATE_FORMATTER.format(date);
}
```

---

## Item 7: Eliminate Obsolete Object References

```java
public class Stack {
    private Object[] elements;
    private int size = 0;

    public Object pop() {
        if (size == 0) throw new EmptyStackException();
        Object result = elements[--size];
        elements[size] = null;  // Eliminate obsolete reference!
        return result;
    }
}
```

### Common Memory Leak Sources

1. **Collections** - Clear when no longer needed
2. **Caches** - Use `WeakHashMap` or bounded cache
3. **Listeners/Callbacks** - Unregister when done
4. **ThreadLocal** - Remove after use

```java
// Cache with weak references
private final Map<Key, WeakReference<Value>> cache = new WeakHashMap<>();

// Bounded cache
private final Map<Key, Value> cache = new LinkedHashMap<>(100, 0.75f, true) {
    @Override
    protected boolean removeEldestEntry(Map.Entry<Key, Value> eldest) {
        return size() > MAX_ENTRIES;
    }
};

// ThreadLocal cleanup
private static final ThreadLocal<Context> CONTEXT = new ThreadLocal<>();

public void process() {
    try {
        CONTEXT.set(new Context());
        doWork();
    } finally {
        CONTEXT.remove();  // Always clean up!
    }
}
```

---

## Item 9: Prefer try-with-resources

```java
// BAD - Verbose, error-prone
InputStream in = null;
OutputStream out = null;
try {
    in = new FileInputStream(src);
    out = new FileOutputStream(dst);
    byte[] buf = new byte[1024];
    int n;
    while ((n = in.read(buf)) >= 0) {
        out.write(buf, 0, n);
    }
} finally {
    if (in != null) {
        try { in.close(); } catch (IOException e) { /* ignored */ }
    }
    if (out != null) {
        try { out.close(); } catch (IOException e) { /* ignored */ }
    }
}

// GOOD - try-with-resources
try (InputStream in = new FileInputStream(src);
     OutputStream out = new FileOutputStream(dst)) {
    byte[] buf = new byte[1024];
    int n;
    while ((n = in.read(buf)) >= 0) {
        out.write(buf, 0, n);
    }
}

// Even better with Files utility
Files.copy(src.toPath(), dst.toPath(), StandardCopyOption.REPLACE_EXISTING);
```
