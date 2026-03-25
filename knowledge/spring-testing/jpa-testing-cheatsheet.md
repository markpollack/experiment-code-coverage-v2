---
source_project: n/a
derived_from:
  - plans/inbox/testing-deep-research-results/claude/jpa-testing-patterns.md
  - plans/inbox/testing-deep-research-results/chatgpt/jpa.md
  - plans/inbox/testing-deep-research-results/chatgpt/patterns.md
  - https://github.com/spring-guides/gs-accessing-data-jpa
author: claude-code
created: 2026-03-02
last_verified: 2026-03-02
curation_status: verified
confidence: medium
task_types: [review, reference]
artifact_type: cheatsheet
subjects: [spring-testing, spring-data]
related:
  see_also:
    - spring/testing/jpa-repository-testing-best-practices.md
    - spring/testing/assertj-mockito-idioms.md
    - ddd/review-tools/ddd-jpa-review-checklist.md
    - spring/testing/cross-cutting-testing-patterns.md
  broader: [spring/testing/index.md]
---

# JPA Testing Cheatsheet

Quick-reference patterns for Spring Data JPA testing. For deep dives on @DataJpaTest vs @SpringBootTest, Testcontainers, @Transactional traps, Hibernate 6.x pitfalls, and DDD aggregate testing, see the companion [remediation guide](jpa-repository-testing-best-practices.md).

**Reference**: [gs-accessing-data-jpa](https://github.com/spring-guides/gs-accessing-data-jpa) (not cloned locally — eval dataset item)

---

## @DataJpaTest + TestEntityManager

```java
@DataJpaTest
class OrderRepositoryTest {

    @Autowired TestEntityManager em;
    @Autowired OrderRepository orderRepository;

    @Test
    void findByCustomerId_returnsMatchingOrders() {
        Customer customer = em.persist(new Customer("alice@example.com"));
        em.persist(new Order(customer, OrderStatus.PENDING));
        em.persist(new Order(customer, OrderStatus.SHIPPED));
        em.flush();
        em.clear();     // CRITICAL: evicts L1 cache so repo reads from DB

        List<Order> orders = orderRepository.findByCustomerId(customer.getId());

        assertThat(orders).hasSize(2);
    }
}
```

---

## Testing Derived Query Methods

```java
@Test
void findByEmailAndActiveTrue_returnsOnlyActiveUsers() {
    em.persist(new User("bob@example.com", true));
    em.persist(new User("bob@example.com", false));
    em.flush();
    em.clear();

    List<User> results = userRepository.findByEmailAndActiveTrue("bob@example.com");

    assertThat(results).hasSize(1);
    assertThat(results.get(0).isActive()).isTrue();
}

@Test
void findTop3ByOrderByCreatedAtDesc_returnsLatestThree() {
    for (int i = 0; i < 5; i++) {
        em.persist(new Product("P" + i, BigDecimal.TEN));
    }
    em.flush();
    em.clear();

    List<Product> top3 = productRepository.findTop3ByOrderByCreatedAtDesc();
    assertThat(top3).hasSize(3);
}
```

---

## Testing Custom @Query Methods

```java
// Repository:
// @Query("SELECT o FROM Order o WHERE o.status = :status AND o.total >= :minTotal")
// List<Order> findByStatusAndMinTotal(@Param("status") OrderStatus status,
//                                     @Param("minTotal") BigDecimal minTotal);

@Test
void findByStatusAndMinTotal_filtersCorrectly() {
    Customer c = em.persist(new Customer("alice@example.com"));
    em.persist(orderWith(c, OrderStatus.PENDING, new BigDecimal("50.00")));
    em.persist(orderWith(c, OrderStatus.PENDING, new BigDecimal("150.00")));
    em.persist(orderWith(c, OrderStatus.SHIPPED, new BigDecimal("200.00")));
    em.flush();
    em.clear();

    List<Order> results = orderRepository
        .findByStatusAndMinTotal(OrderStatus.PENDING, new BigDecimal("100.00"));

    assertThat(results).hasSize(1);
    assertThat(results.get(0).getTotal()).isEqualByComparingTo("150.00");
}
```

---

## Testing Pagination

```java
@Test
void findAll_paginated_returnsCorrectPage() {
    for (int i = 0; i < 10; i++) {
        em.persist(new Product("P" + i, BigDecimal.TEN));
    }
    em.flush();
    em.clear();

    Pageable pageable = PageRequest.of(0, 3, Sort.by("name").ascending());
    Page<Product> page = productRepository.findAll(pageable);

    assertThat(page.getContent()).hasSize(3);
    assertThat(page.getTotalElements()).isEqualTo(10);
    assertThat(page.getTotalPages()).isEqualTo(4);
    assertThat(page.getContent().get(0).getName()).isEqualTo("P0");
}
```

---

## Testing Specifications

```java
@Test
void spec_filtersByCategory() {
    em.persist(new Product("Widget", "ELECTRONICS", BigDecimal.TEN));
    em.persist(new Product("Screw", "HARDWARE", BigDecimal.ONE));
    em.flush();
    em.clear();

    List<Product> results = productRepository
        .findAll(ProductSpecs.hasCategory("ELECTRONICS"));

    assertThat(results).hasSize(1);
    assertThat(results.get(0).getName()).isEqualTo("Widget");
}
```

---

## Testing Interface Projections

```java
// interface UserSummary { String getEmail(); String getDisplayName(); }
// List<UserSummary> findByActiveTrue();

@Test
void findByActiveTrue_returnsProjection() {
    em.persist(new User("alice@example.com", "Alice Smith", true));
    em.persist(new User("bob@example.com", "Bob Jones", false));
    em.flush();
    em.clear();

    List<UserSummary> summaries = userRepository.findByActiveTrue();

    assertThat(summaries).hasSize(1);
    assertThat(summaries.get(0).getEmail()).isEqualTo("alice@example.com");
    assertThat(summaries.get(0).getDisplayName()).isEqualTo("Alice Smith");
}
```

---

## Testing Entity Relationships

```java
@Test
void findOrderWithItems_lazyLoadingInTransaction() {
    Customer customer = em.persist(new Customer("alice@example.com"));
    Order order = em.persist(new Order(customer));
    em.persist(new OrderItem(order, "PROD-1", 2));
    em.persist(new OrderItem(order, "PROD-2", 1));
    em.flush();
    em.clear();

    Order loaded = orderRepository.findById(order.getId()).orElseThrow();

    // CAUTION: @OneToMany(fetch=LAZY) works here because @DataJpaTest wraps
    // test in @Transactional. In production without a transaction this would
    // throw LazyInitializationException.
    assertThat(loaded.getItems()).hasSize(2);
}
```

---

## Testing Entity Auditing

```java
@DataJpaTest
@Import(AuditingConfig.class)
class AuditedEntityTest {

    @TestConfiguration
    @EnableJpaAuditing
    static class AuditingConfig {}

    @Autowired TestEntityManager em;
    @Autowired ProductRepository productRepository;

    @Test
    void save_populatesAuditDates() {
        Product p = productRepository.save(new Product("Widget", BigDecimal.TEN));
        em.flush();
        em.clear();

        Product loaded = productRepository.findById(p.getId()).orElseThrow();
        assertThat(loaded.getCreatedAt()).isNotNull();
        assertThat(loaded.getUpdatedAt()).isNotNull();
    }
}
```

---

## Transaction Rollback Control

```java
// @DataJpaTest wraps each test in @Transactional → rollback after each test.
// Override when needed:

@Test
@Commit   // override rollback — use sparingly, clean up manually
void saveOrder_commitsSuccessfully() { /* ... */ }

// Or disable wrapping transaction entirely:
@DataJpaTest
@Transactional(propagation = Propagation.NOT_SUPPORTED)
class OrderRepositoryCommitTest {
    // must clean up test data manually (@BeforeEach)
}
```

---

## Constraint Violation Testing

```java
@Test
void save_duplicateEmail_throwsConstraintViolation() {
    em.persist(new User("alice@example.com"));
    em.flush();

    assertThatThrownBy(() -> {
        em.persist(new User("alice@example.com"));
        em.flush();
    }).isInstanceOf(DataIntegrityViolationException.class);
}
```

---

## Anti-Patterns

| Anti-Pattern | Fix | Type |
|---|---|---|
| `save()` then `findById()` without `flush()+clear()` | Always flush+clear before read assertions | Principle |
| Testing `save()` and `findById()` only | Test YOUR query methods, not Spring Data plumbing | Principle |
| Loading `@SpringBootTest` for repository tests | Use `@DataJpaTest` — 90% less infrastructure | Principle |
| Using H2 for native queries with PostgreSQL syntax | Use Testcontainers with production DB image | Config |
| Assuming lazy collections work like production | They work in test transactions — document the difference | Principle |

---

## Boot 3.x → 4.x

| Area | Boot 3.x | Boot 4.x |
|---|---|---|
| `@DataJpaTest` import | `o.s.boot.test.autoconfigure.orm.jpa` | `o.s.boot.data.jpa.test.autoconfigure` |
| `TestEntityManager` import | `o.s.boot.test.autoconfigure.orm.jpa` | `o.s.boot.jpa.test.autoconfigure` |
| `@MockBean` | `o.s.boot.test.mock.mockito` | Use `@MockitoBean` from `o.s.test.context.bean.override.mockito` |
| Hibernate | 6.x | 7.x (minor behavioral changes) |
