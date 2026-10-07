# Design Solution: Worked Example

This example shows the expected depth. Real output follows the user's language.

## Input

> Flash-sale coupons: a campaign issues 1,000 coupons, each user may redeem at most one, and traffic peaks for a few minutes at the start. We must never issue more than 1,000. Mobile clients retry on timeout.
>
> Stack (from Step 0): Spring Boot 4.1, Spring Data JPA (Hibernate 7.4), PostgreSQL 18.

## Requirement

### Summary
A redemption endpoint that issues at most `total` coupons per campaign, at most one per user, and is safe under client retries and concurrent requests.

### Clarifying questions
1. Expected peak requests per second, and for how long? (drives whether the single counter row is enough)
2. Must a redemption notify other systems (wallet, push notification)? (drives whether an outbox is needed)
3. Should a user who lost the race see "sold out" or be queued?

---

## Recommendation

### Proposed approach
One database transaction per redemption: insert the redemption row (unique constraints reject duplicates), then decrement the campaign counter with a conditional `UPDATE` that refuses to go below zero. Idempotency keys make client retries replay the original response.

### Why this approach
- The conditional `UPDATE ... WHERE remaining > 0` is evaluated by the database against the latest committed row, so it cannot oversell under PostgreSQL's default READ COMMITTED (or InnoDB's default REPEATABLE READ).
- Unique constraints enforce "one per user" even for concurrent requests that both passed an application-level check.
- No distributed locks, no extra infrastructure.

### Alternatives considered
- **Pre-generated coupon rows claimed with `FOR UPDATE SKIP LOCKED`**: no single hot row, so it scales further. It costs 1,000 rows per campaign and a claim query. Switch to this if load tests show lock waits on the campaign row dominating.
- **Counter in Redis**: fast, but now two stores must agree. Rejected until the database is measured to be the bottleneck.

---

## Design

### Data model
```sql
CREATE TABLE coupon_campaign (
    id        bigint PRIMARY KEY,
    total     int NOT NULL,
    remaining int NOT NULL CHECK (remaining >= 0),
    starts_at timestamptz NOT NULL,
    ends_at   timestamptz NOT NULL
);

CREATE TABLE coupon_redemption (
    id          bigint PRIMARY KEY,                    -- sequence, allocationSize 50
    campaign_id bigint NOT NULL REFERENCES coupon_campaign (id),
    user_id     bigint NOT NULL,
    idem_key    varchar(64) NOT NULL UNIQUE,
    created_at  timestamptz NOT NULL,
    UNIQUE (campaign_id, user_id)                      -- one per user; also serves lookups by campaign
);
```

### Consistency and concurrency
| Write path | Risk | Guard | Isolation level |
|------------|------|-------|-----------------|
| Decrement `remaining` | Oversell (lost update) | `UPDATE ... SET remaining = remaining - 1 WHERE id = ? AND remaining > 0`; 0 rows → sold out | READ COMMITTED (default). At REPEATABLE READ, concurrent decrements fail with 40001 and need retries |
| One coupon per user | Double redemption from concurrent requests | `UNIQUE (campaign_id, user_id)` | Any |
| Client retry after timeout | Same effect applied twice | `UNIQUE (idem_key)`; replay the stored redemption | Any |

Order inside the transaction: insert the redemption first, so duplicates fail before touching the hot row. Decrement last, so the campaign row lock is held only until commit.

```java
@Transactional
public CouponRedemption redeem(long campaignId, long userId, String idemKey) {
    CouponRedemption r = redemptionRepository.saveAndFlush(CouponRedemption.of(campaignId, userId, idemKey));
    if (campaignRepository.decrementRemaining(campaignId) == 0) {
        throw new SoldOutException(campaignId);   // unchecked: rolls back the inserted redemption
    }
    return r;
}
```

In PostgreSQL, any error aborts the whole transaction. Handle `DataIntegrityViolationException` outside it: in the controller or a facade, look up the redemption by `idem_key` in a new transaction to replay it, or return 409 for "already redeemed".

### API
- `POST /campaigns/{id}/redemptions` with an `Idempotency-Key` header
- `201` created; `200` replay of the same key; `409` already redeemed by this user; `410` sold out or campaign ended

---

## Implementation plan

### Phase 1: Foundation
- [ ] Flyway `V1__coupon.sql`: both tables, constraints, sequence `coupon_redemption_seq INCREMENT BY 50`
- [ ] Entities `CouponCampaign`, `CouponRedemption` (sequence generator, `allocationSize = 50`)

### Phase 2: Core feature
- [ ] `CouponCampaignRepository.decrementRemaining(long id)`: `@Modifying` JPQL conditional update returning `int`
- [ ] `RedemptionService.redeem(...)`: `@Transactional`, insert then decrement as above
- [ ] `RedemptionFacade`: translates `DataIntegrityViolationException` into a replay or 409, outside the transaction
- [ ] `RedemptionController` with the `Idempotency-Key` header

### Phase 3: Tests
- [ ] `RedemptionServiceIT` with Testcontainers PostgreSQL: 50 threads × 40 users racing on a campaign of 1,000. Assert exactly 1,000 redemptions, no user twice, `remaining = 0`, and no negative values.
- [ ] Same user, two concurrent requests: one 201 and one 409 or replay
- [ ] Same idempotency key twice: the second returns the first result

---

## Risks and edge cases

### Risks
1. The campaign row is a hot spot: every redemption serializes on its lock. Load-test at the expected peak; if lock waits dominate (check `pg_stat_activity` wait events), switch to pre-generated rows with `SKIP LOCKED`.

### Edge cases
1. A request arrives after `ends_at`: reject before any write.
2. The same idempotency key with a different payload: return 422, never the stored response.

### Performance
Short transactions, two statements plus a commit; no remote calls inside.

### Security
Authenticate the user id from the token; never accept it from the request body.

---

## Rough effort

| Phase | Relative size (S/M/L) | Notes |
|-------|-----------------------|-------|
| Foundation | S | Two tables, two entities |
| Core feature | M | Facade and error translation need care |
| Tests | M | The concurrency test is the proof that the guards work |
