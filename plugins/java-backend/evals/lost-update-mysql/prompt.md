---
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Agent]
tags: [transactions, mysql]
---

Please review this service method for correctness before we ship it. Stack: Spring Boot 4.1, Spring Data JPA, MySQL 8.4 with the default isolation level. Withdrawals for the same account can arrive concurrently.

```java
@Service
public class AccountService {
    private final AccountRepository accountRepository;

    public AccountService(AccountRepository accountRepository) {
        this.accountRepository = accountRepository;
    }

    @Transactional
    public void withdraw(long accountId, BigDecimal amount) {
        Account account = accountRepository.findById(accountId).orElseThrow();
        if (account.getBalance().compareTo(amount) < 0) {
            throw new InsufficientFundsException(accountId);
        }
        account.setBalance(account.getBalance().subtract(amount));
    }
}
```

`Account` is a plain JPA entity with `id` and `balance` (no version column).
