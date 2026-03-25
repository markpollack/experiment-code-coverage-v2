---
source_project: n/a
derived_from:
  - plans/inbox/testing-deep-research-results/claude/assertj-mockito-idioms.md
  - plans/inbox/testing-deep-research-results/chatgpt/patterns.md
  - plans/inbox/testing-deep-research-results/Google-Spring Testing Research Gaps.md
author: claude-code
created: 2026-03-02
last_verified: 2026-03-02
curation_status: verified
confidence: medium
task_types: [review, reference]
artifact_type: cheatsheet
subjects: [spring-testing]
related:
  see_also:
    - spring/testing/mvc-rest-testing-patterns.md
    - spring/testing/jpa-testing-cheatsheet.md
    - spring/testing/cross-cutting-testing-patterns.md
    - spring/testing/security-testing-patterns.md
    - spring/testing/webflux-testing-patterns.md
    - spring/testing/websocket-stomp-testing-patterns.md
  broader: [spring/testing/index.md]
---

# AssertJ + Mockito Idioms

Quick-reference for assertion and mocking patterns in Spring Boot tests. Prefer BDDMockito (`given/willReturn`) over classic Mockito (`when/thenReturn`).

---

## AssertJ Core

```java
import static org.assertj.core.api.Assertions.*;

// Scalar
assertThat(user.getEmail()).isEqualTo("alice@example.com");
assertThat(user.getAge()).isGreaterThan(18).isLessThan(100);
assertThat(user.getName()).startsWith("Al").endsWith("ce").hasSize(5);
assertThat(user.isActive()).isTrue();
assertThat(user.getDeletedAt()).isNull();
assertThat(optional).isPresent().hasValue("expected");
assertThat(optional).isEmpty();

// BigDecimal — use isEqualByComparingTo (not isEqualTo — scale matters)
assertThat(price).isEqualByComparingTo(BigDecimal.valueOf(9.99));
```

---

## AssertJ Collections

```java
assertThat(list).containsExactly("alpha", "beta", "gamma");           // ordered
assertThat(list).containsExactlyInAnyOrder("gamma", "alpha", "beta"); // unordered
assertThat(list).contains("alpha", "gamma");                          // subset
assertThat(list).hasSize(3);
assertThat(list).isNotEmpty();

// Filtering
assertThat(orders)
    .filteredOn(o -> o.getStatus() == OrderStatus.PENDING)
    .hasSize(2);

// Extracting single field
assertThat(users)
    .extracting(User::getEmail)
    .containsExactlyInAnyOrder("alice@example.com", "bob@example.com");

// Multi-field extraction (tuple)
assertThat(orders)
    .extracting(Order::getStatus, Order::getTotal)
    .containsExactlyInAnyOrder(
        tuple(OrderStatus.PENDING, new BigDecimal("50.00")),
        tuple(OrderStatus.SHIPPED, new BigDecimal("100.00"))
    );

// satisfies
assertThat(users).allSatisfy(user -> {
    assertThat(user.getEmail()).contains("@");
    assertThat(user.isActive()).isTrue();
});
assertThat(users).anySatisfy(user ->
    assertThat(user.getRoles()).contains("ADMIN"));
```

---

## AssertJ Exceptions

```java
// Preferred
assertThatThrownBy(() -> userService.findById(99L))
    .isInstanceOf(UserNotFoundException.class)
    .hasMessage("User not found: 99")
    .hasMessageContaining("99");

// assertThatExceptionOfType
assertThatExceptionOfType(UserNotFoundException.class)
    .isThrownBy(() -> userService.findById(99L))
    .withMessage("User not found: 99");

// catchThrowable — when you need to inspect further
Throwable thrown = catchThrowable(() -> orderService.cancel(1L));
assertThat(thrown)
    .isInstanceOf(IllegalStateException.class)
    .hasMessageContaining("already cancelled");

// assertThatNoException
assertThatNoException().isThrownBy(() -> validator.validate(validRequest));
```

---

## BDDMockito — Preferred for Spring Tests

```java
import static org.mockito.BDDMockito.*;

// given / willReturn
given(userRepository.findById(1L))
    .willReturn(Optional.of(new User(1L, "alice@example.com")));

// willThrow
given(userRepository.findById(99L))
    .willThrow(new UserNotFoundException(99L));

// willAnswer — dynamic return
given(idGenerator.nextId())
    .willAnswer(inv -> UUID.randomUUID().toString());

// Void methods
willDoNothing().given(emailService).sendWelcome(any(User.class));
willThrow(new EmailException("SMTP down")).given(emailService).sendWelcome(any(User.class));
```

---

## Argument Matchers

```java
// Exact value
given(repo.findById(1L)).willReturn(Optional.of(user));

// any() / any(Class)
given(repo.save(any(User.class))).willReturn(savedUser);

// eq() — REQUIRED when mixing matchers with literals
// If ANY argument uses a matcher, ALL must use matchers:
given(repo.findByEmailAndActive(eq("alice@example.com"), eq(true)))
    .willReturn(Optional.of(user));

// argThat — inline predicate
given(repo.save(argThat(u -> "alice@example.com".equals(u.getEmail()))))
    .willReturn(savedUser);
```

---

## ArgumentCaptor

```java
@Captor ArgumentCaptor<EmailNotification> captor;

@Test
void registerUser_sendsWelcomeEmail() {
    userService.register(new RegisterRequest("alice@example.com", "Alice"));

    then(emailService).should().send(captor.capture());

    EmailNotification notification = captor.getValue();
    assertThat(notification.getTo()).isEqualTo("alice@example.com");
    assertThat(notification.getSubject()).contains("Welcome");
}

// Multiple invocations
then(auditLog).should(times(2)).record(captor.capture());
List<AuditEvent> events = captor.getAllValues();
assertThat(events).extracting(AuditEvent::getAction)
    .containsExactly("USER_CREATED", "EMAIL_SENT");
```

---

## BDDMockito Verification

```java
then(emailService).should().sendWelcome(any(User.class));       // once
then(retryService).should(times(3)).attempt(any());             // N times
then(emailService).should(never()).sendAlert(any());            // never
then(cache).should(atLeastOnce()).evict(anyString());           // at least once
then(emailService).shouldHaveNoMoreInteractions();              // no more (use sparingly)
```

---

## @MockBean vs @SpyBean

```java
// @MockBean — full mock, all methods return defaults unless stubbed
@MockBean OrderService orderService;

// @SpyBean — wraps real bean, all methods call real implementation unless overridden
@SpyBean AuditService auditService;
willDoNothing().given(auditService).record(any(AuditEvent.class));

// WARNING: @SpyBean requires the real bean to be loadable in the slice context.
// In @WebMvcTest, only web-layer beans load — @SpyBean on a service will fail
// unless all dependencies are satisfied.
```

---

## Strict Stubbing and UnnecessaryStubbingException

```java
// Mockito strict stubbing (default): throws if a stub is never called

// Fix A: Remove the unneeded stub
// Fix B: Use lenient() for shared stubs
lenient().when(userRepository.findById(anyLong())).thenReturn(Optional.of(user));

// Fix C: Relax at class level (avoid where possible)
@MockitoSettings(strictness = Strictness.LENIENT)
class MyServiceTest { }

// Best practice: move stubs into the tests that actually need them
```

---

## MockMvc + Hamcrest vs AssertJ

```java
// MockMvc uses Hamcrest matchers in ResultMatchers — not AssertJ
import static org.hamcrest.Matchers.*;

.andExpect(jsonPath("$.items", hasSize(3)))
.andExpect(jsonPath("$.name", containsString("Widget")))
.andExpect(jsonPath("$.price", greaterThan(0.0)))
.andExpect(jsonPath("$.tags", hasItem("featured")))
.andExpect(jsonPath("$.ids", containsInAnyOrder(1, 2, 3)))

// For complex body assertions: extract body and assert with AssertJ
String json = mockMvc.perform(get("/orders/1"))
    .andExpect(status().isOk())
    .andReturn().getResponse().getContentAsString();
OrderDto order = objectMapper.readValue(json, OrderDto.class);
assertThat(order.getItems()).hasSize(3);
```

---

## Common Mistakes

```java
// MISTAKE 1: Stubbing after the act                              [Principle]
orderService.processOrder(request);       // act
given(repo.findById(1L)).willReturn(...); // WRONG — too late

// MISTAKE 2: Mixing matchers with literals                       [Principle]
given(repo.find(eq("alice"), true)).willReturn(...);  // ERROR — mixed
given(repo.find(eq("alice"), eq(true))).willReturn(...); // RIGHT

// MISTAKE 3: Over-verifying                                      [Principle]
verify(repo).findById(1L);
verify(mapper).toDto(any());          // noise — verify observable side effects only
then(emailService).should().sendConfirmation(any(Order.class)); // RIGHT

// MISTAKE 4: Mocking value objects                               [Principle]
// Don't mock DTOs or domain objects — use real instances

// MISTAKE 5: Unused stubs in @BeforeEach                         [Idiom]
// Move stubs into the tests that need them
```

---

## Quick Reference

| Need | Use |
|---|---|
| Stub a method call | `given(mock.method(args)).willReturn(value)` |
| Stub void method | `willDoNothing().given(mock).method(args)` |
| Stub to throw | `given(mock.method(args)).willThrow(ex)` |
| Verify call happened | `then(mock).should().method(args)` |
| Verify never called | `then(mock).should(never()).method(any())` |
| Capture argument | `then(mock).should().method(captor.capture()); captor.getValue()` |
| Assert exception | `assertThatThrownBy(() -> ...).isInstanceOf(X.class)` |
| Assert collection fields | `assertThat(list).extracting(X::getField).contains(...)` |
| Assert BigDecimal | `assertThat(val).isEqualByComparingTo(BigDecimal.valueOf(x))` |
| Hamcrest in jsonPath | `jsonPath("$.field", is("value"))` |

---

## Boot 3.x → 4.x

| Area | Boot 3.x | Boot 4.x |
|---|---|---|
| Mockito version | 5.x | 5.x+ |
| `@MockBean` | `o.s.boot.test.mock.mockito` | Deprecated; use `@MockitoBean` from `o.s.test.context.bean.override.mockito` |
| `@SpyBean` | `o.s.boot.test.mock.mockito` | Deprecated; use `@MockitoSpyBean` |
| AssertJ version | 3.24.x | 3.26.x+ |
| Strict stubbing | Default via `MockitoExtension` | Same |
