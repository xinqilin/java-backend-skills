---
max_turns: 20
timeout_seconds: 600
allowed_tools: [Read, Glob, Grep, Skill, Agent]
tags: [testing, spring-boot-4]
---

Write a @WebMvcTest for this controller. Our project uses Spring Boot 4.1.1 (spring-boot-starter-parent 4.1.1, spring-boot-starter-webmvc-test). Reply with the complete test class including imports; don't create files.

```java
@RestController
@RequestMapping("/api/v1/orders")
public class OrderController {
    private final OrderService orderService;

    public OrderController(OrderService orderService) {
        this.orderService = orderService;
    }

    @GetMapping("/{id}")
    public OrderResponse get(@PathVariable long id) {
        return orderService.find(id);                 // throws OrderNotFoundException (mapped to 404 by @ResponseStatus)
    }
}
```
