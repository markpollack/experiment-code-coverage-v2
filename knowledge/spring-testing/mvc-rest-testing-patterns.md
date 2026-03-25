---
source_project: n/a
derived_from:
  - plans/inbox/testing-deep-research-results/claude/spring-rest-testing.md
  - plans/inbox/testing-deep-research-results/chatgpt/mvc.md
  - plans/inbox/testing-deep-research-results/chatgpt/patterns.md
  - plans/inbox/boot4/boot-4-testing.md
  - supporting_repos/spring-testing/gs-testing-web
author: claude-code
created: 2026-03-02
last_verified: 2026-03-02
curation_status: verified
confidence: medium
task_types: [review, reference]
artifact_type: cheatsheet
subjects: [spring-testing, spring-boot]
related:
  see_also:
    - spring/testing/security-testing-patterns.md
    - spring/testing/assertj-mockito-idioms.md
    - spring/testing/cross-cutting-testing-patterns.md
  broader: [spring/testing/index.md]
---

# MVC / REST Controller Testing Patterns

Quick-reference patterns for testing Spring MVC controllers with `@WebMvcTest` and MockMvc.

**Reference repo**: `supporting_repos/spring-testing/gs-testing-web/`

---

## @WebMvcTest Basics

```java
// LOADS: Controllers, ControllerAdvice, JsonComponent, Filter, WebMvcConfigurer,
//        Spring Security filter chain (auto-configured)
// DOES NOT LOAD: @Service, @Repository, @Component — mock with @MockBean

@WebMvcTest(UserController.class)
class UserControllerTest {

    @Autowired MockMvc mockMvc;
    @MockBean UserService userService;
    @Autowired ObjectMapper objectMapper;

    @Test
    void getUser_returnsUser() throws Exception {
        given(userService.findById(1L))
            .willReturn(new UserDto(1L, "alice@example.com", "Alice"));

        mockMvc.perform(get("/users/1")
                .accept(MediaType.APPLICATION_JSON))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.id").value(1))
            .andExpect(jsonPath("$.email").value("alice@example.com"))
            .andExpect(jsonPath("$.name").value("Alice"));
    }
}
```

---

## Static Imports

```java
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import static org.springframework.test.web.servlet.result.MockMvcResultHandlers.*;
import static org.mockito.BDDMockito.*;
import static org.hamcrest.Matchers.*;
```

---

## GET / POST / PUT / DELETE

```java
// GET with path variable and query param
mockMvc.perform(get("/orders/{id}", 42L)
        .param("includeItems", "true")
        .accept(MediaType.APPLICATION_JSON))
    .andExpect(status().isOk())
    .andExpect(jsonPath("$.id").value(42));

// POST with JSON body
OrderRequest req = new OrderRequest("PROD-1", 3);
mockMvc.perform(post("/orders")
        .contentType(MediaType.APPLICATION_JSON)
        .content(objectMapper.writeValueAsString(req)))
    .andExpect(status().isCreated())
    .andExpect(header().string("Location", containsString("/orders/")));

// PUT
mockMvc.perform(put("/orders/{id}", 42L)
        .contentType(MediaType.APPLICATION_JSON)
        .content(objectMapper.writeValueAsString(req)))
    .andExpect(status().isOk());

// DELETE
mockMvc.perform(delete("/orders/{id}", 42L))
    .andExpect(status().isNoContent());
```

---

## jsonPath Assertions

```java
// Scalar values
.andExpect(jsonPath("$.name").value("Alice"))
.andExpect(jsonPath("$.active").value(true))
.andExpect(jsonPath("$.age").value(greaterThan(18)))   // Hamcrest matcher

// Arrays
.andExpect(jsonPath("$.items").isArray())
.andExpect(jsonPath("$.items", hasSize(3)))
.andExpect(jsonPath("$.items[0].sku").value("PROD-1"))

// Existence
.andExpect(jsonPath("$.id").exists())
.andExpect(jsonPath("$.internalField").doesNotExist())

// String matching
.andExpect(jsonPath("$.email").value(containsString("@example.com")))
```

---

## Request Validation — Expecting 400

```java
// Controller uses @Valid on @RequestBody

@Test
void createOrder_invalidRequest_returns400() throws Exception {
    OrderRequest invalid = new OrderRequest("", 0);

    mockMvc.perform(post("/orders")
            .contentType(MediaType.APPLICATION_JSON)
            .content(objectMapper.writeValueAsString(invalid)))
        .andExpect(status().isBadRequest());
}

// With structured error response from @RestControllerAdvice:
@Test
void createOrder_invalidRequest_returnsFieldErrors() throws Exception {
    mockMvc.perform(post("/orders")
            .contentType(MediaType.APPLICATION_JSON)
            .content("{\"sku\":\"\",\"quantity\":0}"))
        .andExpect(status().isBadRequest())
        .andExpect(jsonPath("$.errors", hasSize(greaterThanOrEqualTo(2))))
        .andExpect(jsonPath("$.errors[*].field", hasItems("sku", "quantity")));
}
```

---

## Testing @RestControllerAdvice / Exception Handlers

```java
// @WebMvcTest auto-discovers @RestControllerAdvice beans in the same package

@Test
void getUser_notFound_returns404() throws Exception {
    given(userService.findById(99L))
        .willThrow(new UserNotFoundException(99L));

    mockMvc.perform(get("/users/99"))
        .andExpect(status().isNotFound())
        .andExpect(jsonPath("$.message").value(containsString("99")));
}
// Boot 3.x: ProblemDetail (RFC 7807) returned by default with
// spring.mvc.problemdetails.enabled=true
```

---

## Full Context REST Test

```java
@SpringBootTest
@AutoConfigureMockMvc
class UserIntegrationTest {

    @Autowired MockMvc mockMvc;

    @Test
    @WithMockUser(roles = "ADMIN")
    void listUsers_asAdmin_returnsAll() throws Exception {
        mockMvc.perform(get("/users"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$", hasSize(greaterThan(0))));
    }
}
```

---

## Response Headers

```java
mockMvc.perform(post("/orders")
        .contentType(MediaType.APPLICATION_JSON)
        .content(objectMapper.writeValueAsString(req)))
    .andExpect(status().isCreated())
    .andExpect(header().exists("Location"))
    .andExpect(header().string("Location", matchesPattern(".*/orders/\\d+")));
```

---

## Multipart File Upload

```java
@Test
void uploadAvatar_returns200() throws Exception {
    MockMultipartFile file = new MockMultipartFile(
        "file", "avatar.png", MediaType.IMAGE_PNG_VALUE, "fake-image-bytes".getBytes());

    mockMvc.perform(multipart("/users/1/avatar").file(file))
        .andExpect(status().isOk());
}
```

---

## Debugging

```java
mockMvc.perform(get("/users/1"))
    .andDo(print())    // prints full request/response to stdout
    .andExpect(status().isOk());
```

---

## Anti-Patterns

| Anti-Pattern | Fix | Type |
|---|---|---|
| Using `@SpringBootTest` for every controller test | Use `@WebMvcTest` — 10x faster | Principle |
| Not scoping `@WebMvcTest(controllers=…)` | Always scope to avoid loading all controllers | Principle |
| Asserting exact JSON string with `content().string(…)` | Use `jsonPath()` — resilient to field ordering | Principle |
| Forgetting `contentType(APPLICATION_JSON)` on POST | MockMvc returns 415 without it | Principle |
| Expecting `status().isOk()` without checking body | Check both status and key response fields | Principle |
| Verifying mock calls instead of HTTP behavior | Controller tests verify HTTP contract, not implementation | Principle |

---

## Boot 3.x → 4.x

| Area | Boot 3.x | Boot 4.x |
|---|---|---|
| `@WebMvcTest` import | `o.s.boot.test.autoconfigure.web.servlet` | `o.s.boot.webmvc.test.autoconfigure` |
| `@MockBean` | `o.s.boot.test.mock.mockito` | Use `@MockitoBean` from `o.s.test.context.bean.override.mockito` |
| Test client (MVC) | `MockMvc` | `MockMvc` (still valid) **or** `MockMvcTester` (preferred — AssertJ-based, no checked exceptions) |
| Test client (REST) | `MockMvc` | `RestTestClient` via `@AutoConfigureRestTestClient` (WebTestClient-style) |
| ProblemDetail | Opt-in | Default for standard exceptions |
| Servlet imports | `jakarta.servlet.*` | Same |

### Boot 4.x MockMvcTester Pattern (preferred for MVC/Thymeleaf apps)

`MockMvcTester` is auto-configured by `@WebMvcTest` in Boot 4.x. No extra annotation needed.
Import: `org.springframework.test.web.servlet.assertj.MockMvcTester`

```java
@WebMvcTest(VetController.class)
class VetControllerTest {

    @Autowired
    private MockMvcTester mvc;

    @MockitoBean
    private VetRepository vetRepository;

    @Test
    void showVetList_returnsHtmlView() {
        given(vetRepository.findAll(any(Pageable.class))).willReturn(new PageImpl<>(buildVetList()));

        assertThat(mvc.get().uri("/vets.html")).hasStatusOk().hasViewName("vets/vetList");
    }

    @Test
    void showVetList_hasPaginationAttributes() {
        given(vetRepository.findAll(any(Pageable.class))).willReturn(new PageImpl<>(buildVetList()));

        assertThat(mvc.get().uri("/vets.html")).hasStatusOk()
            .model()
            .containsKey("currentPage")
            .containsKey("totalPages")
            .containsKey("listVets");
    }
}
```

Key `MockMvcTester` assertions:
- `.hasStatusOk()`, `.hasStatus(HttpStatus.CREATED)`, `.hasStatus4xxClientError()`
- `.hasViewName("view/name")` — for Thymeleaf/MVC view name assertions
- `.model().containsKey("attr")`, `.model().attribute("attr", value)`
- `.hasBodyTextEqualTo("...")`, `.bodyJson().extractingPath("$.field").isEqualTo("value")`

### Boot 4.x RestTestClient Pattern (for JSON REST APIs)

```java
// Use RestTestClient when the project already uses WebTestClient (WebFlux parity)
@WebMvcTest(GreetingController.class)
@AutoConfigureRestTestClient
class GreetingControllerTest {

    @Autowired RestTestClient restTestClient;
    @MockitoBean GreetingService service;

    @Test
    void greetingShouldReturnMessageFromService() {
        when(service.greet()).thenReturn("Hello, Mock");
        restTestClient.get().uri("/greeting")
            .exchange()
            .expectBody(String.class)
            .isEqualTo("Hello, Mock");
    }
}
```

See `supporting_repos/spring-testing/gs-testing-web/complete/` for live Boot 4.x examples.
