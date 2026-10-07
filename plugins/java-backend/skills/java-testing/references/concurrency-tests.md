# Testing Concurrency Guards Against a Real Database

A concurrency guard (`@Version`, conditional update, lock, unique constraint) is only proven when concurrent transactions actually collide in the production database engine. Unit tests and H2 can't do that.

## Rules

1. **Use `@SpringBootTest` without `@Transactional` on the test.** Spring binds the test-managed transaction to the test's thread, so worker threads would neither see uncommitted fixtures nor be rolled back.
2. **Commit fixtures and clean up explicitly**: insert through a repository (it commits), and delete in `@AfterEach`, or use unique ids per test.
3. **Start all threads at once** with a latch, so they really overlap.
4. **Propagate worker failures**: call `Future.get()`, or an exception in a worker is silently lost.
5. **Assert the invariant**, not a log line: final balance, exact count, no duplicates.

## Lost update: read-modify-write

```java
@SpringBootTest
@Testcontainers
class AccountWithdrawalConcurrencyIT {

    @Container
    @ServiceConnection
    static PostgreSQLContainer postgres = new PostgreSQLContainer("postgres:18");  // use the production engine

    @Autowired AccountService accountService;
    @Autowired AccountRepository accountRepository;

    @AfterEach
    void cleanUp() {
        accountRepository.deleteAll();
    }

    @Test
    void concurrentWithdrawalsNeverLoseAnUpdate() throws Exception {
        long id = accountRepository.save(new Account(new BigDecimal("100"))).getId();
        int threads = 10;
        ExecutorService pool = Executors.newFixedThreadPool(threads);
        CountDownLatch start = new CountDownLatch(1);
        List<Future<?>> results = new ArrayList<>();

        for (int i = 0; i < threads; i++) {
            results.add(pool.submit(() -> {
                start.await();
                accountService.withdraw(id, BigDecimal.TEN);
                return null;
            }));
        }
        start.countDown();
        for (Future<?> f : results) {
            f.get(30, TimeUnit.SECONDS);           // rethrows worker failures
        }
        pool.shutdown();

        assertThat(accountRepository.findById(id).orElseThrow().getBalance()).isEqualByComparingTo("0");
    }
}
```

- Without a guard, this test fails intermittently: the final balance stays above 0 because some withdrawals were lost. Run it several times (for example with `@RepeatedTest`) before trusting a pass.
- With `@Version`, workers fail with `ObjectOptimisticLockingFailureException`. Decide whether the service retries (then assert the balance is 0) or reports a conflict (then assert successes + conflicts = threads, and balance = 100 − 10 × successes).

## Oversell: conditional update

```java
@Test
void neverIssuesMoreThanTotal() throws Exception {
    long campaignId = campaignRepository.save(new CouponCampaign(100)).getId();   // 100 coupons
    int users = 300;
    // ... same latch-and-futures scaffolding; each worker calls redeem(campaignId, userId)
    //     and catches SoldOutException

    assertThat(redemptionRepository.countByCampaignId(campaignId)).isEqualTo(100);
    assertThat(campaignRepository.findById(campaignId).orElseThrow().getRemaining()).isZero();
}
```

## Uniqueness under concurrency

Race two requests for the same user or the same idempotency key. Assert exactly one row, and that the loser got the documented outcome (a replay or a 409), not a 500.

## What these tests don't prove

- Behavior under the other database: a test on PostgreSQL READ COMMITTED doesn't prove MySQL REPEATABLE READ behaves the same. Run against the engine you deploy.
- Throughput or hot-row contention: that needs a load test at realistic rates, not a unit test.

## Sources

- Spring Framework reference, Transaction Management in tests (transaction state bound to the current thread): https://docs.spring.io/spring-framework/reference/testing/testcontext-framework/tx.html
- Spring Boot 4.1.1 documentation, Testcontainers service connections: https://github.com/spring-projects/spring-boot/tree/v4.1.1/documentation/spring-boot-docs
- `java-backend:transactions-consistency` for the guards themselves
