---
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Agent]
tags: [transactions, postgresql]
---

We have a rule: every shift must keep at least one doctor on call. This endpoint lets a doctor go off call. Stack: Spring Boot 4.1, Spring Data JPA, PostgreSQL 18. We set `@Transactional(isolation = Isolation.REPEATABLE_READ)` to be safe. Is this correct when two doctors of the same shift press the button at the same time?

```java
@Transactional(isolation = Isolation.REPEATABLE_READ)
public void goOffCall(long doctorId, long shiftId) {
    long onCall = doctorRepository.countByShiftIdAndOnCallTrue(shiftId);
    if (onCall < 2) {
        throw new LastDoctorOnCallException(shiftId);
    }
    Doctor me = doctorRepository.findById(doctorId).orElseThrow();
    me.setOnCall(false);
}
```
