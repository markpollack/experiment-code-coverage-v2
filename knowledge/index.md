# Knowledge Base — Code Coverage Agent

> **Start here.** This index routes you to the right knowledge for the code you're testing.

## Step 1: Read Coverage Mechanics (always)

These files are small and universally relevant — read them upfront before writing any tests.

| File | What it covers |
|------|---------------|
| [coverage-mechanics/coverage-fundamentals.md](coverage-mechanics/coverage-fundamentals.md) | Line/branch/method coverage, meaningful test criteria, what NOT to cover |
| [coverage-mechanics/jacoco-patterns.md](coverage-mechanics/jacoco-patterns.md) | JaCoCo Maven plugin config, report structure, common issues |
| [coverage-mechanics/common-gaps.md](coverage-mechanics/common-gaps.md) | Negative guidance: don't test records/main/config, DO test error handling |
| [coverage-mechanics/spring-test-slices.md](coverage-mechanics/spring-test-slices.md) | Quick decision tree: @WebMvcTest vs @DataJpaTest vs plain JUnit |

## Step 2: Detect Boot Version

Read `pom.xml` (or `build.gradle`) to determine the Spring Boot version from the parent. This affects which APIs and annotations are available. If Boot 4.x, each testing cheatsheet has a **Boot 3.x → 4.x** section — read it before generating tests.

## Step 3: Navigate Spring Testing Patterns (by what you're testing)

Read [spring-testing/index.md](spring-testing/index.md) for the full routing table. Quick routing:

| What are you testing? | Read |
|-----------------------|------|
| JPA repository / data layer | [spring-testing/jpa-testing-cheatsheet.md](spring-testing/jpa-testing-cheatsheet.md) (quick ref), [spring-testing/jpa-repository-testing-best-practices.md](spring-testing/jpa-repository-testing-best-practices.md) (deep dive) |
| REST controller / MVC | [spring-testing/mvc-rest-testing-patterns.md](spring-testing/mvc-rest-testing-patterns.md) |
| Secured endpoints / auth | [spring-testing/security-testing-patterns.md](spring-testing/security-testing-patterns.md) |
| WebFlux / reactive | [spring-testing/webflux-testing-patterns.md](spring-testing/webflux-testing-patterns.md) |
| WebSocket / STOMP | [spring-testing/websocket-stomp-testing-patterns.md](spring-testing/websocket-stomp-testing-patterns.md) |
| AssertJ or Mockito patterns | [spring-testing/assertj-mockito-idioms.md](spring-testing/assertj-mockito-idioms.md) |
| Test slice decision / Boot 4 changes / anti-patterns | [spring-testing/cross-cutting-testing-patterns.md](spring-testing/cross-cutting-testing-patterns.md) |

**Navigate, don't read everything.** Only read the cheatsheets relevant to the production code you're covering. The routing tables tell you exactly which file answers your question.
