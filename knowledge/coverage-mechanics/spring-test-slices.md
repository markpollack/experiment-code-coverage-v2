# Spring Test Slices

Spring Boot provides test slice annotations that load only the relevant portion of the application context. Prefer these over `@SpringBootTest` for faster, more focused tests.

## Test Slice Decision Tree

```
Is the code a REST controller?
  → @WebMvcTest (servlet) or @WebFluxTest (reactive)

Is the code a JPA repository?
  → @DataJpaTest

Is the code a service with no Spring dependencies?
  → Plain JUnit + Mockito (no Spring context at all)

Does the test need the full application context?
  → @SpringBootTest (last resort)
```

## @WebMvcTest

Tests Spring MVC controllers without starting a server. Auto-configures MockMvc.

```java
@WebMvcTest(GreetingController.class)
class GreetingControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private GreetingService greetingService;

    @Test
    void shouldReturnGreeting() throws Exception {
        when(greetingService.greet("World"))
            .thenReturn(new Greeting(1, "Hello, World!"));

        mockMvc.perform(get("/greeting").param("name", "World"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.content").value("Hello, World!"));
    }
}
```

**Scans**: `@Controller`, `@ControllerAdvice`, `@JsonComponent`, `Filter`, `WebMvcConfigurer`
**Does NOT scan**: `@Service`, `@Repository`, `@Component`

## @WebFluxTest

Reactive equivalent of `@WebMvcTest`. Uses `WebTestClient` instead of `MockMvc`.

```java
@WebFluxTest(GreetingController.class)
class GreetingControllerTest {

    @Autowired
    private WebTestClient webTestClient;

    @MockitoBean
    private GreetingService greetingService;

    @Test
    void shouldReturnGreeting() {
        when(greetingService.greet("World"))
            .thenReturn(Mono.just(new Greeting("Hello, World!")));

        webTestClient.get().uri("/greeting?name=World")
            .exchange()
            .expectStatus().isOk()
            .expectBody(Greeting.class)
            .value(g -> assertThat(g.content()).isEqualTo("Hello, World!"));
    }
}
```

## @DataJpaTest

Tests JPA repositories with an embedded database. Transactions are rolled back after each test.

```java
@DataJpaTest
class CustomerRepositoryTest {

    @Autowired
    private TestEntityManager entityManager;

    @Autowired
    private CustomerRepository repository;

    @Test
    void shouldFindByLastName() {
        entityManager.persist(new Customer("Alice", "Smith"));
        entityManager.flush();

        List<Customer> found = repository.findByLastName("Smith");
        assertThat(found).hasSize(1);
        assertThat(found.get(0).getFirstName()).isEqualTo("Alice");
    }
}
```

**Uses**: H2/HSQLDB in-memory by default
**Configures**: `DataSource`, `JdbcTemplate`, `EntityManager`, JPA repositories

## Plain JUnit + Mockito

For service classes with no Spring-specific dependencies, skip Spring entirely:

```java
class GreetingServiceTest {

    private final GreetingService service = new GreetingService();

    @Test
    void shouldGreetWithName() {
        Greeting result = service.greet("World");
        assertThat(result.content()).contains("World");
    }
}
```

This is the **fastest** test type — no Spring context startup.

## @SpringBootTest

Full application context. Use sparingly — only when you need the complete wiring.

```java
@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT)
class IntegrationTest {

    @Autowired
    private TestRestTemplate restTemplate;

    @Test
    void shouldReturnGreetingFromServer() {
        ResponseEntity<Greeting> response =
            restTemplate.getForEntity("/greeting?name=World", Greeting.class);
        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
    }
}
```

## Annotation Quick Reference

| Annotation | What it loads | Speed | When to use |
|-----------|--------------|-------|-------------|
| (none — plain JUnit) | Nothing | Fastest | Services, utilities, POJOs |
| `@WebMvcTest` | MVC layer only | Fast | REST controllers (servlet) |
| `@WebFluxTest` | WebFlux layer only | Fast | REST controllers (reactive) |
| `@DataJpaTest` | JPA layer only | Medium | Repository queries |
| `@SpringBootTest` | Everything | Slow | Full integration tests |
