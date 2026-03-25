---
source_project: n/a
derived_from:
  - plans/inbox/testing-deep-research-results/chatgpt/patterns.md
  - plans/inbox/testing-deep-research-results/Google-Spring Testing Research Gaps.md
  - plans/inbox/boot4/boot-4-testing.md
  - supporting_repos/spring-testing/andy-wilkinson-testing-springone-2019.txt
author: claude-code
created: 2026-03-02
last_verified: 2026-03-02
curation_status: verified
confidence: medium
task_types: [review, architecture-design]
artifact_type: cheatsheet
subjects: [spring-testing, spring-boot]
related:
  see_also:
    - spring/testing/mvc-rest-testing-patterns.md
    - spring/testing/jpa-testing-cheatsheet.md
    - spring/testing/security-testing-patterns.md
    - spring/testing/webflux-testing-patterns.md
    - spring/testing/assertj-mockito-idioms.md
    - spring/testing/jpa-repository-testing-best-practices.md
  broader: [spring/testing/index.md]
---

# Cross-Cutting Testing Patterns

Strategic guidance that applies across all Spring testing domains: test slice selection, context caching, the testing pyramid, Boot 4 readiness, and universal anti-patterns.

Source: Andy Wilkinson's "Testing Spring Boot Applications" (SpringOne 2019), Google deep research report, Boot 4 analysis.

---

## Testing Pyramid — Slice Preference Order

| Priority | Annotation | Scope | Speed |
|---|---|---|---|
| 1 | `@WebMvcTest` | MVC controllers only | ~1-3s |
| 2 | `@DataJpaTest` | JPA entities + repos only | ~2-5s |
| 3 | `@WebFluxTest` | Reactive controllers only | ~1-3s |
| 4 | `@SpringBootTest` | Full context | ~5-30s |
| 5 | `@SpringBootTest(RANDOM_PORT)` | Full context + real server | ~10-30s+ |

**Rule**: Use the narrowest slice that covers your test objective. Only escalate to `@SpringBootTest` when testing cross-cutting concerns (security + service + persistence together).

---

## Context Caching — The #1 Performance Pitfall

Spring Test caches ApplicationContexts across test classes. The cache is keyed by the **exact** combination of configuration — any difference creates a new context.

**Context cache killers**:
- Each unique `@MockBean` / `@MockitoBean` combination creates a new context
- `@DirtiesContext` evicts the context after the test
- Different `@ActiveProfiles` create separate contexts
- Different `@Import` or `@TestConfiguration` create separate contexts

**Best practice**: Standardize mock sets. If 10 test classes all mock `UserService`, make them mock the *same set* of beans so they share a context.

```java
// BAD: Each class has a different @MockBean set → N contexts
@WebMvcTest(UserController.class)
class UserControllerTest {
    @MockBean UserService userService;    // context A
}

@WebMvcTest(OrderController.class)
class OrderControllerTest {
    @MockBean OrderService orderService;  // context B
    @MockBean UserService userService;    // context C (different combo!)
}
```

Default cache limit is 32 contexts. Beyond that, eviction + recreation causes catastrophic slowdown.

---

## Behavior > Implementation

Across all domains, assert **observable outcomes**, not implementation details.

| Domain | Assert This | Not This |
|---|---|---|
| MVC | HTTP status + response body | `verify(service).findById(1L)` |
| JPA | Re-fetched entity state after flush+clear | In-memory entity state before flush |
| Security | 401/403 status codes | Internal filter chain calls |
| WebFlux | StepVerifier signals | `.block()` result |
| WebSocket | Message received in BlockingQueue | Internal broker routing |

---

## Universal Anti-Patterns

| Anti-Pattern | Why It's Bad | Fix | Type |
|---|---|---|---|
| `@SpringBootTest` for everything | Slow, hides what you're testing | Use narrowest slice | Principle |
| Verifying mocks instead of behavior | Brittle, couples to implementation | Assert observable outcomes | Principle |
| String-matching JSON responses | Breaks on field order, whitespace | Use `jsonPath()` | Principle |
| Disabling security in tests | False confidence | Test security explicitly | Principle |
| Using H2 for dialect-sensitive queries | Production mismatch | Use Testcontainers | Config |
| `.block()` in reactive tests | Hides errors, breaks semantics | Use `StepVerifier` | Principle |
| `Thread.sleep()` in async tests | Flaky, non-deterministic | Use Awaitility or BlockingQueue | Principle |
| Over-mocking (DTOs, value objects) | Maintenance burden, no value | Use real instances | Principle |

---

## Boot 4 Readiness Checklist

For a code coverage agent targeting Boot 4 / Framework 7 applications:

### Stack Awareness
- Java 21+
- Jakarta namespaces only
- No deprecated Boot 2/3 APIs

### Annotation Changes
| Boot 3.x | Boot 4.x |
|---|---|
| `@MockBean` | `@MockitoBean` (`o.s.test.context.bean.override.mockito`) |
| `@SpyBean` | `@MockitoSpyBean` |
| `MockMvc` (primary) | `RestTestClient` via `@AutoConfigureRestTestClient` (new option) |

### Package Relocations
| Boot 3.x | Boot 4.x |
|---|---|
| `o.s.boot.test.autoconfigure.web.servlet.WebMvcTest` | `o.s.boot.webmvc.test.autoconfigure.WebMvcTest` |
| `o.s.boot.test.autoconfigure.orm.jpa.DataJpaTest` | `o.s.boot.data.jpa.test.autoconfigure.DataJpaTest` |
| `o.s.boot.test.autoconfigure.orm.jpa.TestEntityManager` | `o.s.boot.jpa.test.autoconfigure.TestEntityManager` |

### AOT Safety Rules
- Prefer constructor injection
- Prefer explicit bean wiring
- Prefer framework-provided test annotations
- Avoid reflection-based test hacks or classloader manipulation

### Observability Testing (Future-Proof)
```java
// If actuator present, optionally validate metrics
assertThat(meterRegistry.find("http.server.requests")).isNotNull();
```

---

## Supporting Repos On Disk

These repos are cloned at `supporting_repos/spring-testing/` for reference:

| Repo | Contains | Boot Version |
|---|---|---|
| `gs-testing-web/` | @WebMvcTest, RestTestClient, @MockitoBean | Boot 4.x |
| `spring-security-samples/` | JWT, OAuth2, @WithMockUser, @PreAuthorize | Boot 4.x |

Eval dataset repos (gs-accessing-data-jpa, gs-reactive-rest-service, etc.) are intentionally NOT cloned here to avoid data leakage.

**Transcript**: `supporting_repos/spring-testing/andy-wilkinson-testing-springone-2019.txt` — Andy Wilkinson's "Testing Spring Boot Applications" (SpringOne 2019). Covers testing pyramid, context caching, slice testing philosophy.
