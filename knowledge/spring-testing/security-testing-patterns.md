---
source_project: n/a
derived_from:
  - plans/inbox/testing-deep-research-results/claude/security-testing-patterns.md
  - plans/inbox/testing-deep-research-results/chatgpt/security.md
  - plans/inbox/testing-deep-research-results/chatgpt/patterns.md
  - plans/inbox/boot4/boot-4-testing.md
  - supporting_repos/spring-testing/spring-security-samples
author: claude-code
created: 2026-03-02
last_verified: 2026-03-02
curation_status: verified
confidence: medium
task_types: [review, reference]
artifact_type: cheatsheet
subjects: [spring-testing, spring-security]
related:
  see_also:
    - spring/testing/mvc-rest-testing-patterns.md
    - spring/testing/webflux-testing-patterns.md
    - spring/testing/assertj-mockito-idioms.md
    - spring/testing/cross-cutting-testing-patterns.md
  broader: [spring/testing/index.md]
---

# Spring Security Testing Patterns

Quick-reference for testing secured endpoints. Spring Security is auto-configured in `@WebMvcTest` — you do not need `@SpringBootTest` to test security.

**Reference repo**: `supporting_repos/spring-testing/spring-security-samples/`

---

## @WithMockUser

```java
@WebMvcTest(OrderController.class)
class OrderControllerSecurityTest {

    @Autowired MockMvc mockMvc;
    @MockBean OrderService orderService;

    @Test
    @WithMockUser(username = "alice", roles = "USER")
    void getOrder_asUser_returns200() throws Exception {
        given(orderService.findById(1L)).willReturn(anOrder());
        mockMvc.perform(get("/orders/1"))
            .andExpect(status().isOk());
    }

    @Test
    void getOrder_noAuth_returns401() throws Exception {
        mockMvc.perform(get("/orders/1"))
            .andExpect(status().isUnauthorized());
    }

    @Test
    @WithMockUser(roles = "USER")   // not ADMIN
    void deleteOrder_asUser_returns403() throws Exception {
        mockMvc.perform(delete("/orders/1"))
            .andExpect(status().isForbidden());
    }
}
```

---

## roles vs authorities — The ROLE_ Prefix

```java
// roles = "ADMIN"       -> authority = "ROLE_ADMIN"   (prefix added automatically)
// authorities = "ADMIN" -> authority = "ADMIN"         (no prefix)

// Use `roles` when config uses hasRole("ADMIN")
// Use `authorities` when config uses hasAuthority("products:read")

@WithMockUser(authorities = {"products:read", "products:write"})
```

---

## @WithUserDetails

```java
// Loads principal from a real UserDetailsService bean
@WebMvcTest(ProfileController.class)
@Import(TestSecurityConfig.class)
class ProfileControllerTest {

    @Test
    @WithUserDetails(value = "alice@example.com",
                     userDetailsServiceBeanName = "userDetailsService")
    void getProfile_returnsAuthenticatedUsersProfile() throws Exception {
        mockMvc.perform(get("/profile"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.email").value("alice@example.com"));
    }
}

@TestConfiguration
class TestSecurityConfig {
    @Bean
    UserDetailsService userDetailsService() {
        UserDetails alice = User.withUsername("alice@example.com")
            .password("{noop}password").roles("USER").build();
        return new InMemoryUserDetailsManager(alice);
    }
}
```

---

## SecurityMockMvcRequestPostProcessors (Per-Request Auth)

```java
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.*;

// Synthetic user
mockMvc.perform(get("/orders").with(user("alice").roles("USER")))
    .andExpect(status().isOk());

// HTTP Basic
mockMvc.perform(get("/admin").with(httpBasic("admin", "secret")))
    .andExpect(status().isOk());

// Anonymous
mockMvc.perform(get("/public").with(anonymous()))
    .andExpect(status().isOk());
```

---

## CSRF — Required for Mutating Requests

```java
// Spring Security enables CSRF by default for session-based apps
// Without csrf() on POST/PUT/DELETE → 403 Forbidden

mockMvc.perform(post("/orders")
        .with(csrf())
        .with(user("alice").roles("USER"))
        .contentType(APPLICATION_JSON)
        .content(orderJson))
    .andExpect(status().isCreated());

// For stateless/JWT apps, disable CSRF in test security config:
@TestConfiguration
static class DisableCsrfConfig {
    @Bean
    SecurityFilterChain testChain(HttpSecurity http) throws Exception {
        http.csrf(csrf -> csrf.disable())
            .authorizeHttpRequests(a -> a.anyRequest().authenticated());
        return http.build();
    }
}
```

---

## JWT Testing with jwt() Post-Processor

```java
// From spring-security-samples — the canonical pattern

@WebMvcTest(OAuth2ResourceServerController.class)
@Import(OAuth2ResourceServerSecurityConfiguration.class)
class OAuth2ResourceServerControllerTests {

    @Autowired MockMvc mockMvc;

    @Test
    void indexGreetsAuthenticatedUser() throws Exception {
        mockMvc.perform(get("/").with(jwt().jwt(j -> j.subject("ch4mpy"))))
            .andExpect(content().string(is("Hello, ch4mpy!")));
    }

    @Test
    void messageRequiresScopeReadAuthority() throws Exception {
        // Via scope claim (Jwt extracts to SCOPE_* authorities)
        mockMvc.perform(get("/message")
                .with(jwt().jwt(j -> j.claim("scope", "message:read"))))
            .andExpect(content().string(is("secret message")));

        // Or via explicit authorities
        mockMvc.perform(get("/message")
                .with(jwt().authorities(new SimpleGrantedAuthority("SCOPE_message:read"))))
            .andExpect(content().string(is("secret message")));
    }

    @Test
    void messageWithoutScope_returns403() throws Exception {
        mockMvc.perform(get("/message").with(jwt()))
            .andExpect(status().isForbidden());
    }
}
```

---

## OAuth2 Login Testing

```java
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.*;

// oauth2Login()
mockMvc.perform(get("/profile")
        .with(oauth2Login()
            .attributes(attrs -> attrs.put("email", "alice@example.com"))))
    .andExpect(status().isOk());

// mockOidcLogin() — OIDC with ID token
mockMvc.perform(get("/profile")
        .with(mockOidcLogin()
            .idToken(t -> t.subject("user-123").claim("email", "alice@example.com"))))
    .andExpect(status().isOk());
```

---

## Custom @WithSecurityContext for JWT

```java
// Step 1: Create annotation
@Retention(RetentionPolicy.RUNTIME)
@WithSecurityContext(factory = JwtFactory.class)
@interface WithMockJwt {
    String value();             // classpath resource with JWT claims
    String[] authorities() default {};
}

// Step 2: Implement factory
class JwtFactory implements WithSecurityContextFactory<WithMockJwt> {
    @Override
    public SecurityContext createSecurityContext(WithMockJwt annotation) {
        // Load claims from JSON file, build Jwt, create JwtAuthenticationToken
        Jwt jwt = Jwt.withTokenValue("token")
            .header("alg", "none")
            .claims(c -> c.putAll(loadClaims(annotation.value())))
            .build();
        Collection<GrantedAuthority> authorities = Stream.of(annotation.authorities())
            .map(SimpleGrantedAuthority::new).collect(Collectors.toList());
        return new SecurityContextImpl(new JwtAuthenticationToken(jwt, authorities));
    }
}

// Step 3: Use in tests
@Test
@WithMockJwt(value = "classpath:validjwt.json", authorities = "SCOPE_message:read")
void messageCanBeRead() throws Exception {
    mockMvc.perform(get("/message")).andExpect(status().isOk());
}
```

See `supporting_repos/spring-testing/spring-security-samples/servlet/spring-boot/java/oauth2/resource-server/hello-security/` for the complete implementation.

---

## Testing Method Security (@PreAuthorize)

```java
// Method security is NOT active in @WebMvcTest by default
// Use @SpringBootTest or load method security config explicitly

@SpringBootTest(classes = {OrderService.class, MethodSecurityConfig.class})
class OrderServiceMethodSecurityTest {

    @Autowired OrderService orderService;
    @MockBean OrderRepository orderRepository;

    @Test
    @WithMockUser(roles = "USER")
    void cancelOrder_asUser_throwsAccessDenied() {
        assertThatThrownBy(() -> orderService.cancelOrder(1L))
            .isInstanceOf(AccessDeniedException.class);
    }

    @Test
    @WithMockUser(roles = "ADMIN")
    void cancelOrder_asAdmin_succeeds() {
        given(orderRepository.findById(1L)).willReturn(Optional.of(anOrder()));
        assertThatNoException().isThrownBy(() -> orderService.cancelOrder(1L));
    }
}
```

---

## SecurityMockMvcResultMatchers

```java
import static org.springframework.security.test.web.servlet.response.SecurityMockMvcResultMatchers.*;

mockMvc.perform(get("/profile").with(user("alice")))
    .andExpect(authenticated().withUsername("alice"))
    .andExpect(authenticated().withRoles("USER"));

mockMvc.perform(get("/public"))
    .andExpect(unauthenticated());
```

---

## Anti-Patterns

| Anti-Pattern | Fix | Type |
|---|---|---|
| Using `@SpringBootTest` for all security tests | `@WebMvcTest` loads security filter chain — use it | Principle |
| Not testing 401 / 403 paths | Always add unauthenticated + wrong-role tests | Principle |
| `roles = "ROLE_ADMIN"` with `@WithMockUser` | Use `roles = "ADMIN"` — prefix is added automatically | Principle |
| Forgetting `.with(csrf())` on POST | Add csrf() or disable CSRF in test security config | Principle |
| Disabling security in tests (`addFilters = false`) | You are not testing security — false confidence | Principle |
| Manually setting `SecurityContextHolder` | Use test annotations or post-processors | Idiom |

---

## Boot 3.x → 4.x

| Area | Boot 3.x | Boot 4.x |
|---|---|---|
| Security DSL | Lambda DSL (`.and()` deprecated) | Lambda DSL only, AuthorizationManager everywhere |
| `WebSecurityConfigurerAdapter` | Removed in Security 6 | Same — use component-based config |
| `jwt()` post-processor | `spring-security-test` 6.x | `spring-security-test` 7.x (same API) |
| `@MockBean` | `o.s.boot.test.mock.mockito` | Use `@MockitoBean` |
