# Tests per Layer (Spring Boot 4.1)

Examples use Spring Boot 4.1 imports; see the version table in `SKILL.md` for 3.x equivalents. Adapt names, assertion style, and `@DisplayName` conventions to the project.

## Domain and application services: plain unit tests

```java
@ExtendWith(MockitoExtension.class)
class OrderServiceTest {

    @Mock OrderRepository orderRepository;
    @Mock PaymentGateway paymentGateway;
    @InjectMocks OrderService orderService;

    @Nested
    class Cancel {

        @Test
        void cancelsPendingOrder() {
            Order order = Order.pending(42L);
            given(orderRepository.findById(42L)).willReturn(Optional.of(order));

            orderService.cancel(42L);

            assertThat(order.getStatus()).isEqualTo(OrderStatus.CANCELLED);   // state, not interactions
        }

        @Test
        void rejectsShippedOrder() {                                      // OrderService.java:57 throws this
            given(orderRepository.findById(42L)).willReturn(Optional.of(Order.shipped(42L)));

            assertThatThrownBy(() -> orderService.cancel(42L))
                .isInstanceOf(InvalidOrderStateException.class);
        }
    }
}
```

No Spring context: these run in milliseconds. Mock only ports to the outside (repositories, gateways); construct domain objects directly.

## Controllers: `@WebMvcTest` + `MockMvcTester`

```java
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.assertj.MockMvcTester;

@WebMvcTest(OrderController.class)
class OrderControllerTest {

    @Autowired MockMvcTester mvc;
    @MockitoBean OrderService orderService;

    @Test
    void returns404ForUnknownOrder() {
        given(orderService.find(99L)).willThrow(new OrderNotFoundException(99L));

        assertThat(mvc.get().uri("/api/v1/orders/99")).hasStatus(HttpStatus.NOT_FOUND);
    }

    @Test
    void rejectsInvalidRequestBody() {
        assertThat(mvc.post().uri("/api/v1/orders")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                        {"items": []}
                        """))
            .hasStatus(HttpStatus.BAD_REQUEST);
    }
}
```

- `@WebMvcTest` loads only the web layer; every collaborator of the controller must be a `@MockitoBean`.
- Test HTTP concerns here: status codes, JSON shape, validation wiring, error mapping. Business rules belong in service tests.

## Repositories: `@DataJpaTest` against the real database

```java
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.boot.jpa.test.autoconfigure.TestEntityManager;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.postgresql.PostgreSQLContainer;

@DataJpaTest
@Testcontainers
class OrderRepositoryTest {

    @Container
    @ServiceConnection
    static PostgreSQLContainer postgres = new PostgreSQLContainer("postgres:18");

    @Autowired TestEntityManager em;
    @Autowired OrderRepository orderRepository;

    @Test
    void findsPendingOrdersOfCustomer() {
        em.persist(Order.pending(customerId(1)));
        em.persist(Order.shipped(customerId(1)));
        em.flush();
        em.clear();                       // read from the database, not the persistence context

        assertThat(orderRepository.findByCustomerIdAndStatus(1L, PENDING)).hasSize(1);
    }

    @Test
    void rejectsSecondActiveSubscription() {
        em.persistAndFlush(Subscription.active(7L));

        assertThatThrownBy(() -> em.persistAndFlush(Subscription.active(7L)))
            .isInstanceOf(ConstraintViolationException.class);   // Hibernate's; flush makes the INSERT run now
    }
}
```

- Each test runs in a transaction that rolls back. Flush explicitly, or constraint violations and generated SQL never reach the database.
- `em.clear()` before asserting, so the assertion reads what the database returns rather than cached entities.
- Since Spring Boot 3.4, `@ServiceConnection` containers are kept by `@AutoConfigureTestDatabase`'s default; on 3.3 and earlier add `@AutoConfigureTestDatabase(replace = Replace.NONE)`.

## End to end: `@SpringBootTest` over HTTP

```java
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@AutoConfigureTestRestTemplate     // Spring Boot 4: TestRestTemplate is no longer injected by default
@Testcontainers
class OrderFlowIT {

    @Container
    @ServiceConnection
    static MySQLContainer mysql = new MySQLContainer("mysql:8.4");

    @Autowired TestRestTemplate rest;

    @Test
    void createsAndReadsOrder() {
        ResponseEntity<OrderResponse> created = rest.postForEntity("/api/v1/orders", newOrderRequest(), OrderResponse.class);
        assertThat(created.getStatusCode()).isEqualTo(HttpStatus.CREATED);

        ResponseEntity<OrderResponse> read = rest.getForEntity("/api/v1/orders/" + created.getBody().id(), OrderResponse.class);
        assertThat(read.getBody().status()).isEqualTo("PENDING");
    }
}
```

Keep these few: one per critical flow. They are slow and fail for many reasons at once.

## Responsibility split

| Layer | Tests | Doesn't test |
|-------|-------|--------------|
| Domain / service | Business rules, state changes, real exceptions | HTTP, SQL |
| Controller | Status codes, JSON, validation wiring, error mapping | Business rules |
| Repository | Queries, mappings, constraints, against the real database | Business rules |
| Integration | Transactions, concurrency, critical end-to-end flows | Every edge case again |

## Sources

- Spring Boot 4.1.1 documentation examples (`MyControllerTests`, `MyRepositoryTests`, `MyIntegrationTests`): https://github.com/spring-projects/spring-boot/tree/v4.1.1/documentation/spring-boot-docs/src/main/java/org/springframework/boot/docs/testing
- Spring Boot 4.0 Migration Guide (`@AutoConfigureTestRestTemplate`, `@MockitoBean`): https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-4.0-Migration-Guide
- Testcontainers 2.0.5 database modules: https://github.com/testcontainers/testcontainers-java/tree/2.0.5/modules
