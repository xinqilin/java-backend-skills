---
type: llm
---

PASS if every exception scenario in the tests corresponds to behavior visible in the given code (the 404 for OrderNotFoundException), with no invented scenarios such as validation errors or 500s that the code does not show.
FAIL if it tests exceptions or error statuses the controller code does not produce.
