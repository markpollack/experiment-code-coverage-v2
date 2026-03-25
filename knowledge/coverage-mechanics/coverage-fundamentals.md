# Coverage Fundamentals

## Coverage Types

### Line Coverage
Percentage of executable lines reached during test execution. The primary metric for this experiment. Target: 80%.

### Branch Coverage
Percentage of decision branches (if/else, switch, ternary) exercised. More meaningful than line coverage for complex logic. Typical gap: 10-20% below line coverage.

### Method Coverage
Percentage of methods invoked. Usually the easiest to achieve but least informative — a method can be "covered" while its edge cases remain untested.

## Meaningful vs. Vanity Coverage

**Meaningful coverage** verifies behavior:
```java
@Test
void shouldReturnGreetingWithName() {
    Greeting greeting = service.greet("World");
    assertThat(greeting.content()).isEqualTo("Hello, World!");
}
```

**Vanity coverage** just exercises lines:
```java
@Test
void shouldCreateGreeting() {
    new Greeting(1, "test"); // no assertions
}
```

## What NOT to Cover

These are excluded from meaningful coverage targets:
- **Record classes**: Constructors, accessors, equals/hashCode/toString are compiler-generated
- **main() methods**: Application entry points — integration-tested, not unit-tested
- **Framework-generated code**: Spring proxies, JPA metamodel classes
- **Trivial getters/setters**: No logic to test
- **Configuration classes**: @Configuration/@Bean methods — tested via integration

## Coverage Arithmetic

If a class has 100 executable lines and tests cover 60:
- Line coverage = 60%
- To reach 80%, need 20 more covered lines
- Focus on the 40 uncovered lines — which have the most behavioral significance?

## JaCoCo Report Navigation

After `mvn test jacoco:report`, the report is at `target/site/jacoco/index.html`.

- **Red bars** = uncovered lines (priority targets)
- **Yellow bars** = partially covered branches (if/else where only one path tested)
- **Green bars** = fully covered

Navigate: package → class → source view for line-by-line analysis.
