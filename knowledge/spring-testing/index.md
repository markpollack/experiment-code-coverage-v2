---
domain: spring
scope: Spring Boot testing best practices — JPA, MVC, Security, WebFlux, WebSocket, cross-cutting
source_project: tuvium-collector
created: 2026-02-14
last_updated: 2026-03-02
---

# Spring Testing Knowledge

> **Testing best practices for Spring Boot applications (Boot 3.x / 4.x).**
> Covers JPA, MVC/REST, Security, WebFlux, WebSocket/STOMP, and assertion/mocking idioms.

## Question Routing

| Question | Read |
|----------|------|
| How do I test JPA repositories? | Start with [jpa-testing-cheatsheet.md](jpa-testing-cheatsheet.md), deep dive in [jpa-repository-testing-best-practices.md](jpa-repository-testing-best-practices.md) |
| @DataJpaTest vs @SpringBootTest? | [jpa-repository-testing-best-practices.md](jpa-repository-testing-best-practices.md) §1 |
| How do I test REST controllers? | [mvc-rest-testing-patterns.md](mvc-rest-testing-patterns.md) |
| @WebMvcTest vs @SpringBootTest? | [mvc-rest-testing-patterns.md](mvc-rest-testing-patterns.md), [cross-cutting-testing-patterns.md](cross-cutting-testing-patterns.md) |
| How do I test secured endpoints? | [security-testing-patterns.md](security-testing-patterns.md) |
| How do I test with JWT/OAuth2? | [security-testing-patterns.md](security-testing-patterns.md) §JWT, §OAuth2 |
| How do I test WebFlux controllers? | [webflux-testing-patterns.md](webflux-testing-patterns.md) |
| How do I use StepVerifier? | [webflux-testing-patterns.md](webflux-testing-patterns.md) §StepVerifier |
| How do I test WebSocket/STOMP? | [websocket-stomp-testing-patterns.md](websocket-stomp-testing-patterns.md) |
| AssertJ or Mockito pattern? | [assertj-mockito-idioms.md](assertj-mockito-idioms.md) |
| What changed in Boot 4 testing? | [cross-cutting-testing-patterns.md](cross-cutting-testing-patterns.md) §Boot 4 |
| Which test slice should I use? | [cross-cutting-testing-patterns.md](cross-cutting-testing-patterns.md) §Pyramid |
| Testcontainers setup? | [jpa-repository-testing-best-practices.md](jpa-repository-testing-best-practices.md) §2 |

## Files

| File | Artifact Type | Contains |
|------|---------------|----------|
| [jpa-repository-testing-best-practices.md](jpa-repository-testing-best-practices.md) | remediation-guide | Deep dive: @DataJpaTest vs @SpringBootTest, Testcontainers, @Transactional trap, Hibernate 6.x pitfalls, DDD aggregates, @Modifying queries |
| [jpa-testing-cheatsheet.md](jpa-testing-cheatsheet.md) | cheatsheet | Quick-ref: derived queries, pagination, projections, specs, relationships, auditing |
| [mvc-rest-testing-patterns.md](mvc-rest-testing-patterns.md) | cheatsheet | @WebMvcTest, MockMvc, jsonPath, validation, error handling, RestTestClient (Boot 4) |
| [security-testing-patterns.md](security-testing-patterns.md) | cheatsheet | @WithMockUser, CSRF, jwt(), oauth2Login(), @PreAuthorize, custom @WithSecurityContext |
| [webflux-testing-patterns.md](webflux-testing-patterns.md) | cheatsheet | @WebFluxTest, WebTestClient, StepVerifier, SSE, reactive security |
| [websocket-stomp-testing-patterns.md](websocket-stomp-testing-patterns.md) | cheatsheet | StompClient, BlockingQueue, @SendToUser, error frames, RANDOM_PORT |
| [assertj-mockito-idioms.md](assertj-mockito-idioms.md) | cheatsheet | AssertJ patterns, BDDMockito, ArgumentCaptor, @MockBean/@MockitoBean |
| [cross-cutting-testing-patterns.md](cross-cutting-testing-patterns.md) | cheatsheet | Testing pyramid, context caching, Boot 4 readiness, universal anti-patterns |

## Version-Aware Navigation

Every cheatsheet has a **Boot 3.x → 4.x** section at the bottom. Key differences for JIT context collection:

| If target project uses... | Key difference | Where documented |
|---|---|---|
| Boot 3.x / `@MockBean` | Standard patterns — use as-is | All files (main content) |
| Boot 4.x / `@MockitoBean` | `@MockBean` → `@MockitoBean`, `@SpyBean` → `@MockitoSpyBean` | All files §Boot 3.x → 4.x |
| Boot 4.x / RestTestClient | `MockMvc` still works; `RestTestClient` is the new option | [mvc-rest-testing-patterns.md](mvc-rest-testing-patterns.md) §Boot 4.x |
| Boot 4.x / package paths | `@WebMvcTest`, `@DataJpaTest`, `TestEntityManager` moved packages | [cross-cutting-testing-patterns.md](cross-cutting-testing-patterns.md) §Package Relocations |
| Security 6 (Boot 3.x) | Lambda DSL, `.and()` deprecated | [security-testing-patterns.md](security-testing-patterns.md) §Boot 3.x → 4.x |
| Security 7 (Boot 4.x) | AuthorizationManager everywhere, component-based config | [security-testing-patterns.md](security-testing-patterns.md) §Boot 3.x → 4.x |
| Hibernate 6.x (Boot 3.x) | See pitfalls in remediation guide | [jpa-repository-testing-best-practices.md](jpa-repository-testing-best-practices.md) §5 |

**Agent rule**: Detect Boot version from `pom.xml`/`build.gradle` parent version. If Boot 4.x, read the §Boot 3.x → 4.x section of each relevant cheatsheet before generating tests.

## Forkability Guide

This KB encodes **one team's opinions**. Teams adopting it should fork and customize the idiom-level guidance while keeping universal principles intact.

| Layer | What it covers | Fork frequency | Where it lives |
|-------|---------------|----------------|----------------|
| **Principles** | Test at the narrowest slice, assert behavior not implementation, flush+clear before read | Rarely — these are universal | [cross-cutting-testing-patterns.md](cross-cutting-testing-patterns.md) §Pyramid, §Behavior > Implementation |
| **Idioms** | AssertJ over Hamcrest, BDDMockito over classic, `@WebMvcTest` scoping | Often — primary fork target | Each domain cheatsheet's Anti-Patterns table, [assertj-mockito-idioms.md](assertj-mockito-idioms.md) |
| **Config patterns** | Testcontainers setup, JaCoCo exclusions, Boot 4 package paths | Per-project | [jpa-repository-testing-best-practices.md](jpa-repository-testing-best-practices.md) §Testcontainers, [cross-cutting-testing-patterns.md](cross-cutting-testing-patterns.md) §Boot 4 |

**Agent note**: The experiment validates the *mechanism* (does KB injection produce measurable improvement?) not these specific opinions. A team swapping `idioms` (e.g., RestAssured over MockMvc, Hamcrest over AssertJ) should see the same architectural benefit.

## Supporting Repos

Reference implementations cloned at `supporting_repos/spring-testing/`:

| Repo | Contains |
|------|----------|
| `gs-testing-web/` | Spring's canonical web layer testing guide (Boot 4.x) |
| `spring-security-samples/` | 94 security test files — JWT, OAuth2, method security |

**Not cloned** (eval dataset items — avoid data leakage): gs-accessing-data-jpa, gs-reactive-rest-service, gs-rest-service, gs-securing-web, gs-messaging-stomp-websocket.

## Source

Consolidated from `tuvium-collector/plans/supporting_docs/` (JPA remediation guide) and deep research results (plans/inbox/testing-deep-research-results/).

## Not Covered

- Performance testing, load testing
- Contract testing (Spring Cloud Contract)
- End-to-end browser testing (Selenium, Playwright)
- Spring Batch job testing
- Testcontainers for non-JPA services (Redis, Kafka, etc.)
