# Clean Architecture Testing Strategy

## Testing Pyramid by Layer

```
                    ┌─────────────┐
                    │   E2E Tests │  ← Few, slow, high confidence
                    ├─────────────┤
                    │ Integration │  ← Controller + Repository tests
                    ├─────────────┤
                    │  Unit Tests │  ← Domain + Application services
                    └─────────────┘
                         Many, fast
```

---

## Domain Layer Testing

**Goal:** Test business logic in isolation. No mocking frameworks needed.

```java
class OrderTest {

    @Test
    void should_create_order_with_calculated_total() {
        // Given
        List<OrderItem> items = List.of(
            new OrderItem(ProductId.of("P1"), 2, Money.of(100)),
            new OrderItem(ProductId.of("P2"), 1, Money.of(50))
        );

        // When
        Order order = Order.create(CustomerId.of("C1"), items);

        // Then
        assertThat(order.getTotalAmount()).isEqualTo(Money.of(250));
        assertThat(order.getStatus()).isEqualTo(OrderStatus.PENDING);
    }

    @Test
    void should_confirm_pending_order() {
        // Given
        Order order = createPendingOrder();

        // When
        order.confirm();

        // Then
        assertThat(order.getStatus()).isEqualTo(OrderStatus.CONFIRMED);
    }

    @Test
    void should_reject_confirming_non_pending_order() {
        // Given
        Order order = createConfirmedOrder();

        // When & Then
        assertThatThrownBy(() -> order.confirm())
            .isInstanceOf(InvalidOrderStateException.class)
            .hasMessageContaining("Cannot confirm non-pending order");
    }

    @Test
    void should_reject_empty_order() {
        assertThatThrownBy(() -> Order.create(CustomerId.of("C1"), List.of()))
            .isInstanceOf(IllegalArgumentException.class)
            .hasMessage("Order must have at least one item");
    }
}

class MoneyTest {

    @Test
    void should_add_same_currency() {
        Money m1 = Money.of(100, "TWD");
        Money m2 = Money.of(50, "TWD");

        Money result = m1.add(m2);

        assertThat(result.amount()).isEqualByComparingTo("150");
    }

    @Test
    void should_reject_adding_different_currencies() {
        Money twd = Money.of(100, "TWD");
        Money usd = Money.of(50, "USD");

        assertThatThrownBy(() -> twd.add(usd))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void should_reject_negative_amount() {
        assertThatThrownBy(() -> Money.of(-100, "TWD"))
            .isInstanceOf(IllegalArgumentException.class);
    }
}
```

---

## Application Layer Testing

**Goal:** Test use case orchestration. Mock output ports only.

```java
@ExtendWith(MockitoExtension.class)
class CreateOrderServiceTest {

    @Mock
    private OrderRepository orderRepository;

    @Mock
    private CustomerRepository customerRepository;

    @Mock
    private EventPublisher eventPublisher;

    @InjectMocks
    private CreateOrderService createOrderService;

    @Test
    void should_create_order_and_publish_event() {
        // Given
        CustomerId customerId = CustomerId.of("C1");
        CreateOrderCommand command = new CreateOrderCommand(
            customerId,
            List.of(new OrderItemCommand(ProductId.of("P1"), 2, Money.of(100)))
        );

        when(customerRepository.findById(customerId))
            .thenReturn(Optional.of(new Customer(customerId, "Test")));

        // When
        OrderResult result = createOrderService.execute(command);

        // Then
        assertThat(result.status()).isEqualTo(OrderStatus.PENDING);
        assertThat(result.totalAmount()).isEqualTo(Money.of(200));

        verify(orderRepository).save(any(Order.class));
        verify(eventPublisher).publish(any(OrderCreatedEvent.class));
    }

    @Test
    void should_fail_when_customer_not_found() {
        // Given
        CustomerId customerId = CustomerId.of("UNKNOWN");
        CreateOrderCommand command = new CreateOrderCommand(customerId, List.of());

        when(customerRepository.findById(customerId))
            .thenReturn(Optional.empty());

        // When & Then
        assertThatThrownBy(() -> createOrderService.execute(command))
            .isInstanceOf(CustomerNotFoundException.class);

        verify(orderRepository, never()).save(any());
    }
}

@ExtendWith(MockitoExtension.class)
class CancelOrderServiceTest {

    @Mock
    private OrderRepository orderRepository;

    @InjectMocks
    private CancelOrderService cancelOrderService;

    @Test
    void should_cancel_pending_order() {
        // Given
        OrderId orderId = OrderId.of("O1");
        Order order = createPendingOrder(orderId);

        when(orderRepository.findById(orderId))
            .thenReturn(Optional.of(order));

        // When
        cancelOrderService.execute(orderId);

        // Then
        assertThat(order.getStatus()).isEqualTo(OrderStatus.CANCELLED);
        verify(orderRepository).save(order);
    }

    @Test
    void should_fail_when_order_already_shipped() {
        // Given
        OrderId orderId = OrderId.of("O1");
        Order shippedOrder = createShippedOrder(orderId);

        when(orderRepository.findById(orderId))
            .thenReturn(Optional.of(shippedOrder));

        // When & Then
        assertThatThrownBy(() -> cancelOrderService.execute(orderId))
            .isInstanceOf(InvalidOrderStateException.class);
    }
}
```

---

## Infrastructure Layer Testing

**Goal:** Test integration with real dependencies (database, message queue).

```java
@DataJpaTest
@Import({JpaOrderRepositoryAdapter.class, OrderPersistenceMapper.class})
class JpaOrderRepositoryAdapterTest {

    @Autowired
    private JpaOrderRepositoryAdapter repository;

    @Autowired
    private TestEntityManager entityManager;

    @Test
    void should_save_and_retrieve_order() {
        // Given
        Order order = Order.create(
            CustomerId.of("C1"),
            List.of(new OrderItem(ProductId.of("P1"), 2, Money.of(100)))
        );

        // When
        repository.save(order);
        entityManager.flush();
        entityManager.clear();

        Optional<Order> found = repository.findById(order.getId());

        // Then
        assertThat(found).isPresent();
        assertThat(found.get().getTotalAmount()).isEqualTo(order.getTotalAmount());
        assertThat(found.get().getStatus()).isEqualTo(OrderStatus.PENDING);
    }

    @Test
    void should_return_empty_when_not_found() {
        Optional<Order> found = repository.findById(OrderId.of("UNKNOWN"));

        assertThat(found).isEmpty();
    }

    @Test
    void should_find_orders_by_customer() {
        // Given
        CustomerId customerId = CustomerId.of("C1");
        Order order1 = createOrder(customerId);
        Order order2 = createOrder(customerId);
        Order otherCustomerOrder = createOrder(CustomerId.of("C2"));

        repository.save(order1);
        repository.save(order2);
        repository.save(otherCustomerOrder);
        entityManager.flush();

        // When
        List<Order> orders = repository.findByCustomerId(customerId);

        // Then
        assertThat(orders).hasSize(2);
    }
}
```

---

## Presentation Layer Testing

**Goal:** Test HTTP interface and request/response mapping.

```java
@WebMvcTest(OrderController.class)
class OrderControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private CreateOrderUseCase createOrderUseCase;

    @MockBean
    private GetOrderUseCase getOrderUseCase;

    @MockBean
    private CancelOrderUseCase cancelOrderUseCase;

    @Autowired
    private ObjectMapper objectMapper;

    @Test
    void should_create_order() throws Exception {
        // Given
        CreateOrderRequest request = new CreateOrderRequest(
            "C1",
            List.of(new OrderItemRequest("P1", 2, new BigDecimal("100")))
        );

        when(createOrderUseCase.execute(any()))
            .thenReturn(new OrderResult(
                OrderId.of("O1"),
                OrderStatus.PENDING,
                Money.of(200)
            ));

        // When & Then
        mockMvc.perform(post("/api/v1/orders")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
            .andExpect(status().isCreated())
            .andExpect(header().string("Location", "/api/v1/orders/O1"))
            .andExpect(jsonPath("$.orderId").value("O1"))
            .andExpect(jsonPath("$.status").value("PENDING"))
            .andExpect(jsonPath("$.totalAmount").value(200));
    }

    @Test
    void should_return_400_for_invalid_request() throws Exception {
        CreateOrderRequest invalidRequest = new CreateOrderRequest("", List.of());

        mockMvc.perform(post("/api/v1/orders")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(invalidRequest)))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.code").value("VALIDATION_ERROR"));
    }

    @Test
    void should_return_404_when_order_not_found() throws Exception {
        when(getOrderUseCase.execute(any()))
            .thenThrow(new OrderNotFoundException(OrderId.of("UNKNOWN")));

        mockMvc.perform(get("/api/v1/orders/UNKNOWN"))
            .andExpect(status().isNotFound())
            .andExpect(jsonPath("$.code").value("ORDER_NOT_FOUND"));
    }

    @Test
    void should_return_409_for_invalid_state_transition() throws Exception {
        doThrow(new InvalidOrderStateException("Cannot cancel shipped order"))
            .when(cancelOrderUseCase).execute(any());

        mockMvc.perform(delete("/api/v1/orders/O1"))
            .andExpect(status().isConflict())
            .andExpect(jsonPath("$.code").value("INVALID_ORDER_STATE"));
    }
}
```

---

## End-to-End Testing

**Goal:** Test complete flow with real application context.

```java
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Testcontainers
class OrderE2ETest {

    @Container
    static MySQLContainer<?> mysql = new MySQLContainer<>("mysql:8.0")
        .withDatabaseName("orders")
        .withUsername("test")
        .withPassword("test");

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", mysql::getJdbcUrl);
        registry.add("spring.datasource.username", mysql::getUsername);
        registry.add("spring.datasource.password", mysql::getPassword);
    }

    @Autowired
    private TestRestTemplate restTemplate;

    @Autowired
    private CustomerRepository customerRepository;

    @BeforeEach
    void setUp() {
        customerRepository.save(new Customer(CustomerId.of("C1"), "Test Customer"));
    }

    @Test
    void should_create_and_retrieve_order() {
        // Create order
        CreateOrderRequest createRequest = new CreateOrderRequest(
            "C1",
            List.of(new OrderItemRequest("P1", 2, new BigDecimal("100")))
        );

        ResponseEntity<OrderResponse> createResponse = restTemplate.postForEntity(
            "/api/v1/orders",
            createRequest,
            OrderResponse.class
        );

        assertThat(createResponse.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        String orderId = createResponse.getBody().orderId();

        // Retrieve order
        ResponseEntity<OrderResponse> getResponse = restTemplate.getForEntity(
            "/api/v1/orders/" + orderId,
            OrderResponse.class
        );

        assertThat(getResponse.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(getResponse.getBody().status()).isEqualTo("PENDING");
        assertThat(getResponse.getBody().totalAmount()).isEqualByComparingTo("200");
    }
}
```

---

## Test Organization Summary

| Layer | Test Type | Dependencies | Speed |
|-------|-----------|--------------|-------|
| Domain | Unit | None | Fast |
| Application | Unit | Mocked ports | Fast |
| Infrastructure | Integration | Real DB (@DataJpaTest) | Medium |
| Presentation | Integration | Mocked services (@WebMvcTest) | Medium |
| Full | E2E | Full context + Testcontainers | Slow |
