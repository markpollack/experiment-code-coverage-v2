---
source_project: n/a
derived_from:
  - plans/inbox/testing-deep-research-results/claude/webflux-testing-patterns.md
  - plans/inbox/testing-deep-research-results/chatgpt/webflux.md
  - plans/inbox/testing-deep-research-results/chatgpt/patterns.md
  - plans/inbox/boot4/boot-4-testing.md
  - https://github.com/spring-guides/gs-reactive-rest-service
author: claude-code
created: 2026-03-02
last_verified: 2026-03-02
curation_status: verified
confidence: medium
task_types: [review, reference]
artifact_type: cheatsheet
subjects: [spring-testing, spring-webflux]
related:
  see_also:
    - spring/testing/assertj-mockito-idioms.md
    - spring/testing/security-testing-patterns.md
    - spring/testing/websocket-stomp-testing-patterns.md
    - spring/testing/cross-cutting-testing-patterns.md
  broader: [spring/testing/index.md]
---

# WebFlux / Reactive Testing Patterns

Quick-reference for testing reactive controllers with `@WebFluxTest`, `WebTestClient`, and `StepVerifier`.

**Reference**: [gs-reactive-rest-service](https://github.com/spring-guides/gs-reactive-rest-service) (not cloned locally — eval dataset item)

---

## @WebFluxTest Basics

```java
// LOADS: RouterFunctions, WebFlux controllers, WebFilter, WebFluxConfigurer,
//        Spring Security WebFlux (auto-configured), WebTestClient
// DOES NOT LOAD: @Service, @Repository, @Component — mock with @MockBean

@WebFluxTest(ProductController.class)
class ProductControllerTest {

    @Autowired WebTestClient webTestClient;
    @MockBean ProductService productService;

    @Test
    void getProduct_returnsProduct() {
        given(productService.findById(1L))
            .willReturn(Mono.just(new ProductDto(1L, "Widget", BigDecimal.TEN)));

        webTestClient.get().uri("/products/1")
            .accept(MediaType.APPLICATION_JSON)
            .exchange()
            .expectStatus().isOk()
            .expectBody()
            .jsonPath("$.id").isEqualTo(1)
            .jsonPath("$.name").isEqualTo("Widget");
    }
}
```

---

## WebTestClient — GET / POST / PUT / DELETE

```java
// GET with query param
webTestClient.get()
    .uri(uri -> uri.path("/products").queryParam("category", "ELECTRONICS").build())
    .exchange()
    .expectStatus().isOk()
    .expectBodyList(ProductDto.class)
    .hasSize(3);

// POST with JSON body
webTestClient.post().uri("/products")
    .contentType(MediaType.APPLICATION_JSON)
    .bodyValue(new ProductRequest("Gadget", BigDecimal.valueOf(29.99)))
    .exchange()
    .expectStatus().isCreated()
    .expectHeader().valueMatches("Location", ".*/products/\\d+");

// PUT
webTestClient.put().uri("/products/1")
    .contentType(MediaType.APPLICATION_JSON)
    .bodyValue(req)
    .exchange()
    .expectStatus().isOk();

// DELETE
webTestClient.delete().uri("/products/1")
    .exchange()
    .expectStatus().isNoContent();
```

---

## expectBody Assertions

```java
// Single object with AssertJ
webTestClient.get().uri("/products/1")
    .exchange()
    .expectStatus().isOk()
    .expectBody(ProductDto.class)
    .value(dto -> {
        assertThat(dto.getName()).isEqualTo("Widget");
        assertThat(dto.getPrice()).isEqualByComparingTo("9.99");
    });

// List
webTestClient.get().uri("/products")
    .exchange()
    .expectBodyList(ProductDto.class)
    .hasSize(5)
    .value(list -> assertThat(list).extracting(ProductDto::getName)
                                   .contains("Widget", "Gadget"));

// Raw jsonPath
webTestClient.get().uri("/products/1")
    .exchange()
    .expectBody()
    .jsonPath("$.tags").isArray()
    .jsonPath("$.tags[0]").isEqualTo("featured");
```

---

## StepVerifier — Core Usage

```java
import reactor.test.StepVerifier;

// Test a Flux
StepVerifier.create(Flux.just("alpha", "beta", "gamma"))
    .expectNext("alpha")
    .expectNext("beta")
    .expectNext("gamma")
    .verifyComplete();

// Shorthand
StepVerifier.create(flux)
    .expectNextCount(3)
    .verifyComplete();
```

---

## StepVerifier — Testing Mono

```java
Mono<UserDto> result = userService.findById(42L);

StepVerifier.create(result)
    .assertNext(user -> {
        assertThat(user.getId()).isEqualTo(42L);
        assertThat(user.getEmail()).isEqualTo("alice@example.com");
    })
    .verifyComplete();

// Empty Mono
StepVerifier.create(userService.findById(99L))
    .verifyComplete();   // no items, just completes
```

---

## StepVerifier — Error Signals

```java
StepVerifier.create(orderService.findById(404L))
    .expectError(OrderNotFoundException.class)
    .verify();

// With message predicate
StepVerifier.create(orderService.findById(404L))
    .expectErrorMatches(ex ->
        ex instanceof OrderNotFoundException &&
        ex.getMessage().contains("404"))
    .verify();

// Shorthand
StepVerifier.create(mono)
    .verifyError(OrderNotFoundException.class);
```

---

## StepVerifier — Flux Sequences

```java
// expectNextMatches with predicate
StepVerifier.create(productFlux)
    .expectNextMatches(p -> p.getPrice().compareTo(BigDecimal.TEN) > 0)
    .expectNextMatches(Product::isActive)
    .verifyComplete();

// consumeNextWith for multi-field assertions
StepVerifier.create(orderFlux)
    .consumeNextWith(order -> {
        assertThat(order.getStatus()).isEqualTo(OrderStatus.PENDING);
        assertThat(order.getTotal()).isPositive();
    })
    .verifyComplete();
```

---

## StepVerifier.withVirtualTime — Time-Based Operators

```java
// IMPORTANT: Flux must be created inside the supplier lambda
StepVerifier.withVirtualTime(() ->
        Flux.interval(Duration.ofSeconds(1)).take(3))
    .expectSubscription()
    .thenAwait(Duration.ofSeconds(3))
    .expectNextCount(3)
    .verifyComplete();

// Testing timeout
StepVerifier.withVirtualTime(() ->
        slowMono.timeout(Duration.ofSeconds(5)))
    .expectSubscription()
    .thenAwait(Duration.ofSeconds(6))
    .expectError(TimeoutException.class)
    .verify();
```

---

## Reactive Security with WebTestClient

```java
import static org.springframework.security.test.web.reactive.server.SecurityMockServerConfigurers.*;

// Synthetic user
webTestClient.mutateWith(mockUser("alice").roles("USER"))
    .get().uri("/profile")
    .exchange()
    .expectStatus().isOk();

// JWT
webTestClient.mutateWith(
    mockJwt().jwt(j -> j.subject("user-123").claim("scope", "orders:read")))
    .get().uri("/orders")
    .exchange()
    .expectStatus().isOk();

// OIDC login
webTestClient.mutateWith(
    mockOidcLogin().idToken(t -> t.claim("email", "alice@example.com")))
    .get().uri("/profile")
    .exchange()
    .expectStatus().isOk();

// CSRF for mutating requests
webTestClient.mutateWith(csrf())
    .mutateWith(mockUser("alice").roles("USER"))
    .post().uri("/orders")
    .contentType(MediaType.APPLICATION_JSON)
    .bodyValue(orderReq)
    .exchange()
    .expectStatus().isCreated();
```

---

## Testing SSE (Server-Sent Events)

```java
webTestClient.get().uri("/events/stream")
    .accept(MediaType.TEXT_EVENT_STREAM)
    .exchange()
    .expectStatus().isOk()
    .returnResult(ServerSentEvent.class)
    .getResponseBody()
    .as(StepVerifier::create)
    .expectNextMatches(sse -> "order-update".equals(sse.event()))
    .thenCancel()   // cancel — don't wait for infinite stream
    .verify(Duration.ofSeconds(5));
```

---

## Full Integration with WebTestClient

```java
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@AutoConfigureWebTestClient
class OrderIntegrationTest {

    @Autowired WebTestClient webTestClient;

    @Test
    void createOrder_fullStack_returns201() {
        webTestClient.post().uri("/orders")
            .contentType(MediaType.APPLICATION_JSON)
            .bodyValue(new OrderRequest("PROD-1", 2))
            .exchange()
            .expectStatus().isCreated();
    }
}
```

---

## Anti-Patterns

| Anti-Pattern | Fix | Type |
|---|---|---|
| Calling `.block()` in tests | Use `StepVerifier` or `WebTestClient` — `.block()` hides reactive errors | Principle |
| Creating Flux outside `withVirtualTime` supplier | Flux must be created inside the lambda | Principle |
| `verify()` with no timeout | Use `verify(Duration.ofSeconds(5))` or `verifyComplete()` | Principle |
| Not calling `thenCancel()` on infinite streams | Infinite `Flux.interval()` will hang the test | Principle |
| Using `MockMvc` with WebFlux | Use `WebTestClient` | Principle |
| Using `@SpringBootTest` for all WebFlux tests | Use `@WebFluxTest` for controller tests — much faster | Principle |

---

## Boot 3.x → 4.x

| Area | Boot 3.x | Boot 4.x |
|---|---|---|
| `WebTestClient` auto-config | `@WebFluxTest` auto-configures | Same |
| `@AutoConfigureWebTestClient` | Available | Same |
| Reactive security configurers | `o.s.security.test.web.reactive.server` | Same |
| Reactor Core | 3.5.x | 3.7.x+ (minor API additions) |
| `@MockBean` | `o.s.boot.test.mock.mockito` | Use `@MockitoBean` |
