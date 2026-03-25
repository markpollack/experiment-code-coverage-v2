---
source_project: tuvium-collector
derived_from: []  # internally synthesized from agent experience with Spring Data JPA testing
author: claude-code
created: 2026-02-14
last_verified: 2026-02-14
curation_status: verified
confidence: high
task_types: [review, configuration]
artifact_type: remediation-guide
subjects: [spring-testing, ddd-jpa, spring-data]
related:
  see_also:
    - spring/testing/jpa-testing-cheatsheet.md
    - spring/testing/cross-cutting-testing-patterns.md
    - ddd/review-tools/ddd-jpa-review-checklist.md
    - ddd/review-tools/subagent-jpa-review.md
    - spring/boot-2-to-3/test-changes.md
  broader: [spring/testing/index.md]
---

# JPA Repository Integration Testing Best Practices

Research compiled for `tuvium-collector` — Spring Boot 3.5 + Hibernate 6.6 + PostgreSQL + DDD patterns.

**Date**: 2026-02-11

---

## Table of Contents

1. [The Great Debate: @DataJpaTest vs @SpringBootTest](#1-the-great-debate-datajpatest-vs-springboottest)
2. [Testcontainers: Shared Container Patterns for Spring Boot](#2-testcontainers-shared-container-patterns-for-spring-boot)
3. [The @Transactional-in-Tests Trap](#3-the-transactional-in-tests-trap)
4. [Test Data Setup and Cleanup](#4-test-data-setup-and-cleanup)
5. [Hibernate 6.x Migration Pitfalls for Testing](#5-hibernate-6x-migration-pitfalls-for-testing)
6. [Testing JPA Inheritance (SINGLE_TABLE)](#6-testing-jpa-inheritance-single_table)
7. [Testing DDD Aggregates with JPA](#7-testing-ddd-aggregates-with-jpa)
8. [Read-Only Repositories and @QueryHint Pitfalls](#8-read-only-repositories-and-queryhint-pitfalls)
9. [Testing @Modifying JPQL Bulk Updates](#9-testing-modifying-jpql-bulk-updates)
10. [What NOT to Test](#10-what-not-to-test)
11. [Recommendations for tuvium-collector](#11-recommendations-for-tuvium-collector)

---

## 1. The Great Debate: @DataJpaTest vs @SpringBootTest

### What @DataJpaTest Does

`@DataJpaTest` creates a "slice" of the Spring application context containing only JPA-related components: repositories, `EntityManager`, `DataSource`, `JdbcTemplate`, and `TestEntityManager`. It does **not** load `@Service`, `@Controller`, or other non-JPA beans.

Key behaviors:
- Auto-configures an embedded in-memory database (H2) by default
- Wraps every test in `@Transactional` with automatic rollback
- Provides `TestEntityManager` for test data setup
- Validates entity mappings and query syntax at startup

### What @SpringBootTest Does

`@SpringBootTest` loads the **full** application context. It does **not** add `@Transactional` by default, meaning transactions commit normally unless explicitly wrapped.

### The Case FOR @DataJpaTest

- **Faster startup**: Only JPA beans are loaded, reducing context initialization time.
- **Focused testing**: Tests only the persistence layer, isolating failures.
- **Automatic rollback**: Built-in `@Transactional` rollback keeps the database clean between tests.
- **TestEntityManager**: Provides a convenient API for test data setup independent of the repository under test.

**Recommended by**: [Arho Huttunen](https://www.arhohuttunen.com/spring-boot-datajpatest/), [Reflectoring.io](https://reflectoring.io/spring-boot-data-jpa-test/), Spring Boot official docs.

### The Case AGAINST @DataJpaTest (Vlad Mihalcea)

Vlad Mihalcea [recommends avoiding @DataJpaTest](https://vladmihalcea.com/clean-up-test-data-spring/) for several reasons:

1. **Automatic @Transactional wrapper creates unrealistic conditions**: In production, the service layer manages transactions. Wrapping tests in a test-level transaction changes flush timing, dirty-checking behavior, and lazy loading semantics.

2. **Flush behavior mismatch**: `FlushModeType.AUTO` triggers a flush before transaction commit, which does not happen at the end of a rolled-back test transaction. This means some SQL statements may never execute during the test.

3. **Masks LazyInitializationException**: The test-level transaction keeps the `EntityManager` open for the entire test, allowing lazy collections to load that would fail in production outside a transaction.

4. **Limited logging**: `spring.jpa.show-sql` (auto-enabled by `@DataJpaTest`) is limited compared to DataSource-Proxy for SQL logging.

**Source**: [Vlad Mihalcea - The best way to clean up test data with Spring and Hibernate](https://vladmihalcea.com/clean-up-test-data-spring/)

### Practical Guidance

| Scenario | Recommendation |
|----------|---------------|
| Testing custom JPQL/native queries in isolation | `@DataJpaTest` is appropriate |
| Testing repository + service transaction boundaries | `@SpringBootTest` is better |
| Testing Flyway migrations + entity mappings | `@DataJpaTest` with real DB |
| Testing DDD aggregate persistence through service layer | `@SpringBootTest` with Testcontainers |
| Project uses PostgreSQL-specific SQL | Must use Testcontainers (not H2) |

**Sources**:
- [Baeldung - @DataJpaTest and Repository Class in JUnit](https://www.baeldung.com/junit-datajpatest-repository)
- [Arho Huttunen - Testing the Persistence Layer](https://www.arhohuttunen.com/spring-boot-datajpatest/)
- [rieckpil - Spring Data JPA Persistence Layer Tests](https://rieckpil.de/test-your-spring-boot-jpa-persistence-layer-with-datajpatest/)

---

## 2. Testcontainers: Shared Container Patterns for Spring Boot

### Why Not H2

> "You should use the same database engine that you also run in production to validate the very same behavior that the users are going to experience."
> -- [Vlad Mihalcea](https://vladmihalcea.com/test-data-access-layer/)

Problems with H2:
- Cannot replicate PostgreSQL-specific features (window functions, jsonb, array types)
- SQL syntax differences may cause tests to pass on H2 but fail on PostgreSQL
- Native queries are untestable
- Flyway migrations may use PostgreSQL-specific DDL

**Sources**:
- [Vlad Mihalcea - Testcontainers Database Integration Testing](https://vladmihalcea.com/testcontainers-database-integration-testing/)
- [Testcontainers - Replace H2 with a Real Database](https://testcontainers.com/guides/replace-h2-with-real-database-for-testing/)

### Modern Spring Boot 3.1+ Pattern: @ServiceConnection

Since Spring Boot 3.1, the recommended approach uses `@TestConfiguration` with `@Bean @ServiceConnection`:

```java
@TestConfiguration(proxyBeanMethods = false)
public class TestcontainersConfiguration {

    @Bean
    @ServiceConnection
    PostgreSQLContainer<?> postgresContainer() {
        return new PostgreSQLContainer<>("postgres:16-alpine")
                .withReuse(true);
    }
}
```

Usage in tests:

```java
// For @SpringBootTest
@SpringBootTest
@Import(TestcontainersConfiguration.class)
class MyIntegrationTest { ... }

// For @DataJpaTest (requires replace=NONE)
@DataJpaTest
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import(TestcontainersConfiguration.class)
class MyRepositoryTest { ... }
```

Key points:
- `@ServiceConnection` auto-configures `spring.datasource.url`, `username`, `password` -- no `@DynamicPropertySource` needed
- `@AutoConfigureTestDatabase(replace = NONE)` is **required** with `@DataJpaTest` to prevent Spring from replacing your Testcontainers DataSource with an embedded DB
- Static containers are started once per JVM and shared across all tests in the suite
- `withReuse(true)` keeps containers alive between test runs for faster local development

**Sources**:
- [Wim Deblauwe - Combine Testcontainers and Spring Boot with Multiple Containers](https://www.wimdeblauwe.com/blog/2025/05/14/combine-testcontainers-and-spring-boot-with-multiple-containers/)
- [JetBrains Blog - Testing Spring Boot Applications Using Testcontainers](https://blog.jetbrains.com/idea/2024/12/testing-spring-boot-applications-using-testcontainers/)
- [Spring Boot Issue #35121 - Document @ServiceConnection for @DataJpaTest](https://github.com/spring-projects/spring-boot/issues/35121)
- [Spring Boot Issue #35253 - Reduce need for @AutoConfigureTestDatabase(replace=NONE)](https://github.com/spring-projects/spring-boot/issues/35253)

### Separate TestConfigurations for Slice vs Full Tests

Wim Deblauwe recommends creating separate `@TestConfiguration` classes:
- A **database-only** configuration for `@DataJpaTest` tests (starts only PostgreSQL)
- A **full** configuration for `@SpringBootTest` tests (starts PostgreSQL + any other containers)

This avoids starting unnecessary containers for slice tests.

**Source**: [Wim Deblauwe - How I Test Production-Ready Spring Boot Applications](https://www.wimdeblauwe.com/blog/2025/07/30/how-i-test-production-ready-spring-boot-applications/)

---

## 3. The @Transactional-in-Tests Trap

### The Problem

Multiple authoritative sources warn against wrapping integration tests in `@Transactional`:

1. **Lazy loading works in tests but fails in production**: The test transaction keeps the persistence context open, masking `LazyInitializationException`.

2. **Hibernate may not flush**: Since the transaction is rolled back, `FlushModeType.AUTO` may never trigger, meaning SQL statements are never sent to the database. Constraint violations, unique index violations, and other database-level errors go undetected.

3. **Auto-dirty-checking creates false positives**: Entities modified within a `@Transactional` test are automatically persisted at flush time without calling `save()`, which would not happen in production if the service layer does not explicitly save.

4. **Different transaction boundaries**: Production code commits transactions at service method boundaries. Test-level `@Transactional` merges everything into one big transaction, hiding multi-transaction bugs.

### When @Transactional IS Appropriate in Tests

- **@DataJpaTest for isolated query testing**: When you only need to test that a JPQL/SQL query returns correct results, rollback is convenient and appropriate.
- **Tests with explicit `flush()` calls**: If you `em.flush()` and `em.clear()` within the test, you force SQL execution and detect constraint violations.
- **Unit-style repository tests**: Quick verification of derived query methods where production transaction behavior is not the concern.

### When to AVOID @Transactional in Tests

- Full integration tests that verify service-layer transaction boundaries
- Tests for `@Modifying` bulk update queries
- Tests that verify lazy loading behavior
- Tests that check optimistic locking (`@Version`)
- Tests for DDD aggregate invariants that span multiple entities

**Sources**:
- [Nurkiewicz - Spring Pitfalls: Transactional Tests Considered Harmful](https://nurkiewicz.com/2011/11/spring-pitfalls-transactional-tests.html)
- [Kode Krunch - Hibernate Traps: @Transactional Integration Tests](https://www.kode-krunch.com/2021/07/hibernate-traps-transactional.html)
- [rieckpil - Spring Boot Testing Pitfall: Transaction Rollback in Tests](https://rieckpil.de/spring-boot-testing-pitfall-transaction-rollback-in-tests/)
- [Marco Behler - Should My Tests Be @Transactional?](https://www.marcobehler.com/2014/06/25/should-my-tests-be-transactional)

---

## 4. Test Data Setup and Cleanup

### Vlad Mihalcea's Approach: Truncate Before Each Test

> "Execute cleanup **before** each test, not after. Cleanup in `@AfterEach` may not run during test failures or debugging sessions."

Since Hibernate 6.2, use the `SchemaManager` API:

```java
@BeforeEach
void cleanUp() {
    entityManagerFactory
        .unwrap(SessionFactoryImplementor.class)
        .getSchemaManager()
        .truncateMappedObjects();
}
```

Benefits:
- Truncates all tables mapped to JPA entities
- Respects foreign key order automatically
- Works with any database (PostgreSQL, MySQL, Oracle)
- Runs in `@BeforeEach` to ensure a clean slate even if a previous test failed

**Source**: [Vlad Mihalcea - The best way to clean up test data with Spring and Hibernate](https://vladmihalcea.com/clean-up-test-data-spring/)

### TestEntityManager for @DataJpaTest

When using `@DataJpaTest`, Spring Boot auto-configures `TestEntityManager`:

```java
@Autowired
TestEntityManager entityManager;

@Test
void findByName_shouldReturnEntity() {
    entityManager.persistAndFlush(new User("Alice"));
    entityManager.clear(); // Prevent fetching from L1 cache

    Optional<User> found = userRepository.findByName("Alice");
    assertThat(found).isPresent();
}
```

Key practices:
- Use `persistAndFlush()` to ensure data reaches the database
- Call `clear()` to evict the L1 cache, forcing the query to hit the database
- Do NOT use the repository under test to insert test data (circular logic)

**Source**: [Arho Huttunen - Testing the Persistence Layer](https://www.arhohuttunen.com/spring-boot-datajpatest/)

### Alternative: @Sql for Complex Setup

For complex test data scenarios, use `@Sql` to load SQL scripts:

```java
@Test
@Sql("/test-data/users.sql")
void complexQuery_shouldReturnExpectedResults() { ... }
```

Caveat: SQL scripts need maintenance when schemas change.

---

## 5. Hibernate 6.x Migration Pitfalls for Testing

### 5.1 Sequence Generator Naming (6.0)

Hibernate 6 changed the default sequence naming strategy. Previously, all entities shared `hibernate_sequence`. Now, each entity gets `<table_name>_SEQ` by default.

**Impact on tests**: Test data scripts that use `nextval('hibernate_sequence')` will break. Either hardcode IDs or update sequence references.

**Source**: [Thorben Janssen - 8 Things to Know When Migrating to Hibernate 6.x](https://thorben-janssen.com/things-to-know-when-migrating-to-hibernate-6-x/)

### 5.2 Jakarta Persistence Package Migration (6.0)

All imports change from `javax.persistence.*` to `jakarta.persistence.*`. This is a global find-and-replace but affects all test code too.

### 5.3 HQL Column Names Disallowed (6.0)

Hibernate 6 only understands JPA attribute names in HQL/JPQL -- column names are no longer accepted. Tests with custom JPQL must use entity field names.

### 5.4 Instant/Duration Mapping Changes (6.0+)

`Instant` and `Duration` type mappings changed between Hibernate 5 and 6. Entities using these types may behave differently in tests if the schema was generated by an older version.

### 5.5 ClassCastException with Join Fetch and Inheritance (6.0+)

A known Hibernate 6 issue: queries using `join fetch` with entity inheritance can throw `ClassCastException` when multiple inheritance branches are fetched. This did not occur in Hibernate 5.

**Source**: [Hibernate Discourse - ClassCastException with join fetch and inheritance](https://discourse.hibernate.org/t/classcastexception-in-hibernate-6-when-join-fetch-is-used-in-a-query-with-entity-inheritance/7815)

### 5.6 @CreationTimestamp + @UuidGenerator Pitfall (6.x)

Discovered in tuvium-collector Step 3.8: `@UuidGenerator` sets the ID at persist time. Subsequent `save()` calls trigger `merge()` (not `persist()`), which can produce a spurious `UPDATE` with null `createTime` if `@CreationTimestamp` is used. **Fix**: initialize timestamp fields with `Instant.now()` in the field declaration.

### 5.7 @QueryHint readOnly String/Boolean Issue (6.6.x)

Discovered in tuvium-collector: `@QueryHint(name = HINT_READ_ONLY, value = "true")` on `findById` caused `ClassCastException` in Hibernate 6.6.x because Spring Data JPA's implementation of `findById` uses `em.find()`, which passes hints as `Map<String, Object>`. The `@QueryHints` annotation always passes values as `String`, but Hibernate 6.6 expects `Boolean` for the `org.hibernate.readOnly` hint when used with `em.find()`.

**Workaround**: Use `@Transactional(readOnly = true)` on the service method instead, which propagates read-only mode to the Hibernate Session since Spring Framework 5.1.

**Related issues**:
- [Spring Data JPA #1503 - HINT_READONLY not applied to findOne()](https://github.com/spring-projects/spring-data-jpa/issues/1503)
- [Spring Framework #21494 - Propagate read-only to Hibernate Session](https://github.com/spring-projects/spring-framework/issues/21494)

---

## 6. Testing JPA Inheritance (SINGLE_TABLE)

### How SINGLE_TABLE Works

All entities in the hierarchy are stored in one table. A discriminator column differentiates rows by subclass type.

```java
@Entity
@Inheritance(strategy = InheritanceType.SINGLE_TABLE)
@DiscriminatorColumn(name = "type")
public abstract class JobExecution { ... }

@Entity
@DiscriminatorValue("COLLECTION")
public class CollectionExecution extends JobExecution { ... }
```

### Testing Strategies

1. **Test polymorphic queries**: Verify that `findAll()` on the base repository returns both base and subclass instances.

2. **Test discriminator values**: Insert a subclass entity, query the raw table, verify the discriminator column has the expected value.

3. **Test subclass-specific fields**: Verify that subclass-specific columns are null for base class instances and populated for subclass instances.

4. **Test repository type filtering**: If you have a repository typed to a subclass (e.g., `CollectionExecutionRepository extends Repository<CollectionExecution, UUID>`), verify it only returns instances with the matching discriminator.

5. **Avoid join fetch across inheritance branches**: Hibernate 6 may throw `ClassCastException` when join-fetching multiple inheritance branches in a single query.

### Example Test Pattern

```java
@Test
void findAll_shouldReturnSubtypeInstances() {
    CollectionExecution exec = new CollectionExecution();
    exec.setStatus(BatchStatus.STARTING);
    entityManager.persistAndFlush(exec);
    entityManager.clear();

    List<JobExecution> all = jobExecutionRepository.findAll();
    assertThat(all).hasSize(1);
    assertThat(all.get(0)).isInstanceOf(CollectionExecution.class);
}
```

**Sources**:
- [Baeldung - Hibernate Inheritance Mapping](https://www.baeldung.com/hibernate-inheritance)
- [Baeldung - Query JPA Repository with Single Table Inheritance](https://www.baeldung.com/jpa-inheritance-single-table)
- [Vlad Mihalcea - The best way to map @DiscriminatorColumn](https://vladmihalcea.com/the-best-way-to-map-the-discriminatorcolumn-with-jpa-and-hibernate/)

---

## 7. Testing DDD Aggregates with JPA

### Oliver Drotbohm's Recommendations

Oliver Drotbohm (Spring Data lead) recommends:

1. **Only aggregate roots have repositories**: Non-root entities are accessed through their aggregate root, never directly persisted.

2. **Test aggregates through their public interface**: Create aggregates using factory methods or domain constructors, never by setting fields directly. This ensures the aggregate is always in a valid state.

3. **Repositories are the persistence boundary**: Test repository operations (save, find, delete) as integration tests against a real database.

4. **Domain events via `@DomainEvents`**: Spring Data publishes domain events collected by `AbstractAggregateRoot` when `save()` is called on the repository.

**Sources**:
- [Oliver Drotbohm - Implementing DDD Building Blocks in Java](http://odrotbohm.de/2020/03/Implementing-DDD-Building-Blocks-in-Java/)
- [Oliver Drotbohm - DDD and Spring](http://static.odrotbohm.de/lectures/ddd-and-spring/)

### Testing Strategy for DDD Aggregates

The aggregate is the natural unit of testing:

```
Unit Tests:
  - Test aggregate invariants (business rules)
  - Test value objects (equality, validation)
  - Test domain events are registered
  - No database needed

Integration Tests:
  - Test persistence round-trip: create -> save -> find -> verify
  - Test that aggregate state survives serialization to/from DB
  - Test optimistic locking (@Version)
  - Test cascading (CascadeType.ALL for child entities)
  - Test that domain events are published on save
```

### Key Principles

1. **Use the aggregate's public API to set up test state**: Never use reflection or set fields directly. If you cannot create a valid aggregate through its API, the API needs improvement.

2. **Test the persistence round-trip**: Save an aggregate, clear the persistence context, load it again, and verify all fields. This catches mapping errors, missing `@Column` annotations, and serialization issues.

3. **Test optimistic locking**: Save an entity, load two copies, modify both, save one, verify the second throws `OptimisticLockException`.

4. **Test cascading**: Create an aggregate with child entities, save the root, verify children are persisted. Delete the root, verify children are removed.

**Sources**:
- [Baeldung - Persisting DDD Aggregates](https://www.baeldung.com/spring-persisting-ddd-aggregates)
- [Baeldung - DDD Aggregates and @DomainEvents](https://www.baeldung.com/spring-data-ddd)
- [DDD & Testing Strategy](http://www.taimila.com/blog/ddd-and-testing-strategy/)

---

## 8. Read-Only Repositories and @QueryHint Pitfalls

### Read-Only Repository Pattern

For DDD read models, extend `Repository<T, ID>` (not `JpaRepository`) with only query methods:

```java
@NoRepositoryBean
public interface ReadOnlyRepository<T, ID> extends Repository<T, ID> {
    Optional<T> findById(ID id);
    List<T> findAll();
    long count();
}
```

This enforces the aggregate boundary at compile time -- callers cannot accidentally call `save()` or `delete()`.

**Source**: [Baeldung - Creating a Read-Only Repository with Spring Data](https://www.baeldung.com/spring-data-read-only-repository)

### @QueryHint(HINT_READ_ONLY) Behavior

The `org.hibernate.readOnly` hint disables dirty-checking for loaded entities, saving memory and CPU:

```java
@QueryHints(@QueryHint(name = org.hibernate.jpa.QueryHints.HINT_READ_ONLY, value = "true"))
List<User> findAll();
```

**Important**: The hint value is passed as `String` through the `@QueryHint` annotation, but when used programmatically with `EntityManager.find()`, the value should be `Boolean`. This type mismatch is the root cause of the ClassCastException in Hibernate 6.6.x for `findById`.

### Preferred Alternative: @Transactional(readOnly = true)

Instead of per-query hints, use service-level read-only transactions:

```java
@Service
@Transactional(readOnly = true)
public class ReadService {
    public List<User> findAll() {
        return repository.findAll();
    }
}
```

Since Spring Framework 5.1, `@Transactional(readOnly = true)` propagates the read-only flag to the Hibernate Session via `Session.setDefaultReadOnly(true)`, which:
- Disables dirty-checking for all loaded entities
- Skips hydrated state snapshots (memory savings)
- Works consistently with all query types including `em.find()`

**Sources**:
- [Vlad Mihalcea - Spring Read-Only Transaction Hibernate Optimization](https://vladmihalcea.com/spring-read-only-transaction-hibernate-optimization/)
- [Thorben Janssen - Hibernate's Read-Only Query Hint](https://thorben-janssen.com/read-only-query-hint/)
- [Thorben Janssen - 11 JPA and Hibernate Query Hints](https://thorben-janssen.com/11-jpa-hibernate-query-hints-every-developer-know/)

---

## 9. Testing @Modifying JPQL Bulk Updates

### The Pattern

```java
@Modifying
@Transactional  // REQUIRED -- not inherited from Repository interface
@Query("UPDATE User u SET u.status = :status WHERE u.id = :id")
int updateStatus(@Param("id") Long id, @Param("status") String status);
```

### Critical: @Transactional is Required

When extending `Repository` (not `JpaRepository`), `@Modifying` queries do **not** inherit `@Transactional`. You must add it explicitly. Without it, the query will throw:

```
InvalidDataAccessApiUsageException: Executing an update/delete query
```

This was discovered in tuvium-collector and is documented in `memory/hibernate-pitfalls.md`.

### Testing Bulk Updates

1. **Insert test data** (via `TestEntityManager` or separate save).
2. **Execute the bulk update** via the repository method.
3. **Clear the persistence context** (`em.clear()`) to evict stale entities.
4. **Re-read the data** and verify the update took effect.

```java
@Test
void updateStatus_shouldModifyEntity() {
    User user = entityManager.persistAndFlush(new User("Alice", "ACTIVE"));
    entityManager.clear();

    int updated = userRepository.updateStatus(user.getId(), "INACTIVE");

    assertThat(updated).isEqualTo(1);
    entityManager.clear(); // Clear stale cached state
    User reloaded = entityManager.find(User.class, user.getId());
    assertThat(reloaded.getStatus()).isEqualTo("INACTIVE");
}
```

### Use clearAutomatically for Safety

`@Modifying(clearAutomatically = true)` clears the persistence context after executing the bulk update, preventing stale data issues:

```java
@Modifying(clearAutomatically = true)
@Transactional
@Query("UPDATE StepExecution s SET s.itemCount = :count, s.version = s.version + 1 WHERE s.id = :id")
int updateItemCount(@Param("id") UUID id, @Param("count") long count);
```

### Testing Manual Version Management

For entities using `@Version` with JPQL bulk updates (which bypass Hibernate's dirty-checking), verify that the version field is incremented:

```java
@Test
void bulkUpdate_shouldIncrementVersion() {
    StepExecution step = createAndSaveStep();
    int initialVersion = step.getVersion();

    repository.updateItemCount(step.getId(), 42);
    entityManager.clear();

    StepExecution reloaded = entityManager.find(StepExecution.class, step.getId());
    assertThat(reloaded.getVersion()).isEqualTo(initialVersion + 1);
    assertThat(reloaded.getItemCount()).isEqualTo(42);
}
```

**Sources**:
- [Thorben Janssen - Implementing Bulk Updates with Spring Data JPA](https://thorben-janssen.com/implementing-bulk-updates-with-spring-data-jpa/)
- [Baeldung - Spring Data JPA @Modifying Annotation](https://www.baeldung.com/spring-data-jpa-modifying-annotation)

---

## 10. What NOT to Test

### Skip These (Framework-Validated)

- **Inherited CRUD methods** (`save()`, `findById()`, `delete()`): These are tested by the Spring Data JPA team. Testing them tests the framework, not your code.
- **Derived query methods** (`findByName()`, `findByStatusAndType()`): Spring Data validates these at application startup. If they compile and the app starts, they work.
- **Schema generation**: Use Flyway migrations instead of Hibernate auto-DDL. Test that migrations run successfully as part of the test suite startup.

### DO Test These

- **Custom @Query methods**: Both JPQL and native SQL queries need testing, especially native queries that may use PostgreSQL-specific syntax.
- **@Modifying queries**: Bulk updates bypass dirty-checking and must be verified.
- **Projection interfaces/DTOs**: Verify correct field mapping.
- **Database constraints**: Unique constraints, foreign keys, check constraints.
- **Aggregate persistence round-trips**: Save + clear + reload + verify.
- **Optimistic locking behavior**: Concurrent modification detection.
- **Inheritance discriminator values**: Correct subtype storage and retrieval.

**Sources**:
- [Arho Huttunen - Testing the Persistence Layer](https://www.arhohuttunen.com/spring-boot-datajpatest/)
- [Reflectoring.io - Testing JPA Queries with @DataJpaTest](https://reflectoring.io/spring-boot-data-jpa-test/)

---

## 11. Recommendations for tuvium-collector

Based on the research above and the project's specific patterns:

### 11.1 Use @SpringBootTest + Testcontainers for Integration Tests

Given the project already uses `@SpringBootTest @Import(TestcontainersConfiguration.class)` for integration tests, this is the correct approach. The reasons:

- PostgreSQL-specific schema (Flyway migrations)
- SINGLE_TABLE inheritance requires real discriminator column behavior
- JPQL bulk updates with manual version management need real transaction commits
- Three-phase transaction pattern (programmatic `TransactionOperations`) cannot be tested with `@DataJpaTest`'s automatic rollback

### 11.2 Consider @DataJpaTest for Focused Query Tests

If adding targeted repository query tests (not full lifecycle tests), `@DataJpaTest` with Testcontainers is appropriate:

```java
@DataJpaTest
@AutoConfigureTestDatabase(replace = Replace.NONE)
@Import(TestcontainersConfiguration.class)
class CollectionStepReadRepositoryTest {
    // Test custom finders and projections here
}
```

### 11.3 Fix the @QueryHint(HINT_READ_ONLY) Issue

Replace `@QueryHint(name = HINT_READ_ONLY, value = "true")` on individual repository methods with `@Transactional(readOnly = true)` on the service layer or a dedicated read-only service class. This avoids the String/Boolean ClassCastException and provides broader optimization.

### 11.4 Test Bulk Updates with Explicit Flush/Clear

For `StepExecutionUpdateRepository` JPQL updates:
1. Insert test data
2. Execute the `@Modifying` query
3. `em.clear()` to evict stale state
4. Reload and verify both the updated fields AND the incremented version

### 11.5 Test Inheritance Round-Trips

Write integration tests that:
- Create a `CollectionExecution` (subclass)
- Save via repository
- Clear persistence context
- Load via `JobExecution` repository (base type)
- Verify the loaded entity is `instanceof CollectionExecution`
- Verify discriminator value in the database

### 11.6 Clean Up with @BeforeEach, Not @AfterEach

If not using `@Transactional` rollback, clean up the database **before** each test using Hibernate's `SchemaManager.truncateMappedObjects()` or a custom truncation utility. This ensures a clean state even if a previous test failed or was interrupted.

### 11.7 Do NOT Use the Repository Under Test for Setup

Use `TestEntityManager` or a separate "setup" repository to insert test data. Using the same repository for both setup and assertion creates circular logic that can mask bugs.

---

## Summary of Sources

### Primary References

| Author | Article | URL |
|--------|---------|-----|
| Vlad Mihalcea | The best way to clean up test data with Spring and Hibernate | https://vladmihalcea.com/clean-up-test-data-spring/ |
| Vlad Mihalcea | Testcontainers Database Integration Testing | https://vladmihalcea.com/testcontainers-database-integration-testing/ |
| Vlad Mihalcea | The best way to test the data access layer | https://vladmihalcea.com/test-data-access-layer/ |
| Vlad Mihalcea | Spring read-only transaction Hibernate optimization | https://vladmihalcea.com/spring-read-only-transaction-hibernate-optimization/ |
| Vlad Mihalcea | JPA and Hibernate query hints | https://vladmihalcea.com/jpa-hibernate-query-hints/ |
| Vlad Mihalcea | The best way to map @DiscriminatorColumn | https://vladmihalcea.com/the-best-way-to-map-the-discriminatorcolumn-with-jpa-and-hibernate/ |
| Thorben Janssen | 8 things to know when migrating to Hibernate 6.x | https://thorben-janssen.com/things-to-know-when-migrating-to-hibernate-6-x/ |
| Thorben Janssen | Hibernate's Read-Only Query Hint | https://thorben-janssen.com/read-only-query-hint/ |
| Thorben Janssen | Implementing Bulk Updates with Spring Data JPA | https://thorben-janssen.com/implementing-bulk-updates-with-spring-data-jpa/ |
| Thorben Janssen | 11 JPA and Hibernate query hints | https://thorben-janssen.com/11-jpa-hibernate-query-hints-every-developer-know/ |
| Oliver Drotbohm | Implementing DDD Building Blocks in Java | http://odrotbohm.de/2020/03/Implementing-DDD-Building-Blocks-in-Java/ |
| Oliver Drotbohm | DDD and Spring (lecture) | http://static.odrotbohm.de/lectures/ddd-and-spring/ |
| Arho Huttunen | Testing the Persistence Layer with @DataJpaTest | https://www.arhohuttunen.com/spring-boot-datajpatest/ |
| Wim Deblauwe | Combine Testcontainers and Spring Boot with Multiple Containers | https://www.wimdeblauwe.com/blog/2025/05/14/combine-testcontainers-and-spring-boot-with-multiple-containers/ |
| rieckpil | Spring Boot Testing Pitfall: Transaction Rollback | https://rieckpil.de/spring-boot-testing-pitfall-transaction-rollback-in-tests/ |
| rieckpil | Spring Data JPA Persistence Layer Tests | https://rieckpil.de/test-your-spring-boot-jpa-persistence-layer-with-datajpatest/ |
| Nurkiewicz | Spring Pitfalls: Transactional Tests Considered Harmful | https://nurkiewicz.com/2011/11/spring-pitfalls-transactional-tests.html |

### Framework and Official Sources

| Source | URL |
|--------|-----|
| Baeldung - @DataJpaTest and Repository Class | https://www.baeldung.com/junit-datajpatest-repository |
| Baeldung - Spring Data JPA @Modifying Annotation | https://www.baeldung.com/spring-data-jpa-modifying-annotation |
| Baeldung - Hibernate Inheritance Mapping | https://www.baeldung.com/hibernate-inheritance |
| Baeldung - Persisting DDD Aggregates | https://www.baeldung.com/spring-persisting-ddd-aggregates |
| Baeldung - Creating a Read-Only Repository | https://www.baeldung.com/spring-data-read-only-repository |
| Testcontainers - Replace H2 Guide | https://testcontainers.com/guides/replace-h2-with-real-database-for-testing/ |
| Reflectoring.io - Testing JPA Queries | https://reflectoring.io/spring-boot-data-jpa-test/ |
| JetBrains Blog - Testing with Testcontainers | https://blog.jetbrains.com/idea/2024/12/testing-spring-boot-applications-using-testcontainers/ |
| Hibernate 6.0 Migration Guide | https://docs.hibernate.org/orm/6.0/migration-guide/ |
| Hibernate 6.6 Migration Guide | https://docs.jboss.org/hibernate/orm/6.6/migration-guide/migration-guide.html |
| Spring Data JPA #1503 - HINT_READONLY on findOne | https://github.com/spring-projects/spring-data-jpa/issues/1503 |
| Spring Data JPA #2423 - Support for Hibernate 6 | https://github.com/spring-projects/spring-data-jpa/issues/2423 |
| Spring Boot #35121 - @ServiceConnection for @DataJpaTest | https://github.com/spring-projects/spring-boot/issues/35121 |
| Spring Boot #35253 - Reduce @AutoConfigureTestDatabase(replace=NONE) | https://github.com/spring-projects/spring-boot/issues/35253 |
| Hibernate Discourse - ClassCastException with join fetch + inheritance | https://discourse.hibernate.org/t/classcastexception-in-hibernate-6-when-join-fetch-is-used-in-a-query-with-entity-inheritance/7815 |
