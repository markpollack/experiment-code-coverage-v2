# Common Coverage Gaps (Negative Guidance)

## What NOT to Test

These items are commonly targeted by naive coverage agents but provide low value:

### 1. Record Classes
Java records generate constructors, accessors, equals(), hashCode(), and toString() at compile time. Testing these verifies the compiler, not your code.

```java
// DON'T test this
public record Greeting(long id, String content) {}

// This test adds coverage but zero value:
@Test
void shouldCreateGreeting() {
    Greeting g = new Greeting(1, "hi");
    assertThat(g.id()).isEqualTo(1);       // Tests compiler-generated accessor
    assertThat(g.content()).isEqualTo("hi"); // Tests compiler-generated accessor
}
```

### 2. Application Main Methods
`SpringApplication.run()` is tested by `@SpringBootTest`. A separate test for `main()` is redundant.

```java
// DON'T write this
@Test
void contextLoads() {
    Application.main(new String[]{}); // Pointless — covered by @SpringBootTest
}
```

### 3. Framework Configuration
`@Configuration` classes with `@Bean` methods are wired by Spring. Testing them directly tests Spring, not your code.

### 4. Generated Code
- JPA metamodel classes (`*_` suffix)
- MapStruct mappers
- Lombok-generated methods
- Swagger/OpenAPI generated DTOs

## What TO Test (Common Real Gaps)

### 1. Error Handling Paths
The most common meaningful gap. Controllers and services often have catch blocks or error responses that aren't tested:

```java
// This error path is commonly uncovered:
@ExceptionHandler(CustomerNotFoundException.class)
public ResponseEntity<String> handleNotFound(CustomerNotFoundException ex) {
    return ResponseEntity.notFound().build();
}
```

### 2. Validation Logic
Input validation in controllers or services:

```java
// Test the validation branch:
@Test
void shouldRejectEmptyName() throws Exception {
    mockMvc.perform(post("/greeting").param("name", ""))
        .andExpect(status().isBadRequest());
}
```

### 3. Conditional Business Logic
If/else branches in service methods — test both paths:

```java
// Service method with branch:
public String formatGreeting(String name, boolean formal) {
    if (formal) {
        return "Dear " + name;        // ← Branch 1
    }
    return "Hey " + name + "!";       // ← Branch 2
}

// Test BOTH branches:
@Test void formalGreeting() { ... }
@Test void casualGreeting() { ... }
```

### 4. Edge Cases in Data Processing
Null handling, empty collections, boundary values:

```java
@Test
void shouldHandleNullName() {
    Greeting result = service.greet(null);
    assertThat(result.content()).isEqualTo("Hello, Stranger!");
}
```

## Coverage Improvement Priority

When looking at uncovered code, prioritize in this order:

1. **Error handling paths** — highest behavioral significance
2. **Conditional branches** — test both/all paths
3. **Input validation** — boundary and negative cases
4. **Integration points** — HTTP endpoints, repository queries
5. **Utility methods** — if they contain logic (not just delegation)

Skip: records, main(), configuration, generated code.
