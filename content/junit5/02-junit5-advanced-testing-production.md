# JUnit 5 — Chunk 2: Advanced Testing & Production Mastery

**Backend Engineering Tools & Infrastructure Handbook**

**Phase:** I — Developer Foundations  
**Chunk:** 2 of 2  
**Source file:** `content/junit5/02-junit5-advanced-testing-production.md`

---

## Learning Objectives

By the end of this chapter, you should be able to:

- Design unit, integration, and Spring Boot tests with clear boundaries.
- Choose correctly between mocks, stubs, fakes, and real dependencies.
- Test service and repository behavior without creating brittle tests.
- Diagnose flaky tests and failures in CI.
- Explain testing trade-offs in backend engineering interviews.

---

# Layer 1 — Fundamentals & Mental Models

## 1. The Testing Pyramid

Backend systems have multiple testing layers. Each answers a different question.

```text
                      / \
                     /   \
                    / E2E \           Few · Slow · Broad System Confidence
                   /-------\          (Full HTTP Request -> App -> DB -> Response)
                  / Integ-  \
                 /  ration   \        Component Interactions & Slices
                /-------------\       (Spring MVC @WebMvcTest, JPA @DataJpaTest)
               /     Unit      \
              /      Tests      \     Many · Extremely Fast · Highly Focused
             +-------------------+    (Isolated classes, domain logic, Mockito)
```

> **Architectural Principle:** The testing pyramid is a practical mental model, not a dogmatic mathematical formula. The optimal distribution depends on your application architecture, domain complexity, and failure risks.

### Unit tests
Test a small unit of behavior in isolation, usually a method or class.

*Example:* Does `OrderService` reject an order when inventory is insufficient?
- Sub-millisecond execution.
- Dependencies replaced with lightweight test doubles (mocks/stubs).
- Failures pinpoint the exact line of code.

### Integration tests
Test whether components work together correctly across architectural boundaries.

*Examples:*
- Spring Data repository queries execute against a real PostgreSQL container.
- A Spring controller correctly maps URLs, deserializes JSON, and enforces security filters.
- Transaction boundaries rollback correctly upon unhandled runtime exceptions.
- A cache service serializes keys and values correctly to Redis.

Integration tests catch wiring, serialization, dialect, and configuration defects that isolated unit tests cannot see.

### End-to-end (E2E) tests
Exercise a complete user journey through the entire application stack, from external HTTP request to database persistence and downstream events.

They provide broad confidence but are slower to execute, more complex to maintain, and produce failures that are harder to localize.

**Production Rule:** Test business algorithms primarily at the unit level, architectural boundaries with integration tests, and a small number of critical customer journeys end-to-end.

---

## 2. What Makes a Good Test?

A reliable test possesses four fundamental properties:

1. **Deterministic:** The same code and input conditions produce the exact same outcome on every run.
2. **Isolated:** Unrelated tests do not share mutable state, execute in arbitrary order, or contaminate the environment.
3. **Readable:** An engineer reading the test can immediately understand the business rule or contract being validated.
4. **Behavior-focused:** It validates observable contract specifications rather than private internal implementation details.

Consider an order service:

A **behavior-focused test** asks:
> *Given sufficient inventory, does the service create the order, decrement stock, and return the generated order identifier?*

A **brittle test** asks:
> *Did the service call private helper `doInternalCalculations()` exactly twice in sequence?*

Testing internal plumbing makes tests fragile during refactoring, even when user-facing behavior remains completely unchanged. Test observable contracts, not implementation details.

---

## 3. Test Doubles: Mock, Stub, Fake, and Spy

Gerard Meszaros defined the standard taxonomy of **Test Doubles**:

| Type | Formal Definition | Typical Production Use Case |
| :--- | :--- | :--- |
| **Dummy** | Passed around but never actually used | Supplying non-null placeholder parameters |
| **Stub** | Returns hardcoded, predetermined values to method calls | Inventory client configured to return `10` available units |
| **Mock** | Pre-programmed with expectations; verifies interactions | Verifying that an email notification service was invoked with specific payload |
| **Fake** | Simplified working implementation with shortcut logic | In-memory `ConcurrentHashMap` repository instead of PostgreSQL |
| **Spy** | Wraps a real object; delegates calls while recording interactions | Spying on a real Spring service to verify invocation metrics |

### The Critical Architectural Trade-Off

Mocks are invaluable when a collaborator is slow, expensive, nondeterministic, or out-of-process (e.g. third-party Stripe API, SMS gateway).

However, **over-mocking creates a false sense of security**:
- Mocking a database repository does not prove your JPQL or native SQL query syntax is valid.
- Mocking an HTTP client does not prove Jackson can deserialize the real third-party JSON payload.

**Interview Principle:** Use test doubles to isolate unit business logic, but use real implementations (via Testcontainers or test slices) where integration correctness is what must be verified.

---

## 4. Spring Boot Testing Annotations

Spring Boot provides specialized **Test Slices** that configure only the specific subset of beans needed for a test, dramatically improving speed.

| Annotation | Loaded Context Scope | Typical Target Layer |
| :--- | :--- | :--- |
| **`@ExtendWith(MockitoExtension.class)`** | No Spring context; pure JUnit 5 + Mockito | Pure service/domain business unit tests |
| **`@SpringBootTest`** | Full Spring application context with all beans | Full integration tests and end-to-end flows |
| **`@WebMvcTest`** | Spring MVC layer only (Controllers, Filters, Formatters) | HTTP routes, status codes, JSON validation |
| **`@DataJpaTest`** | JPA repositories, entities, EntityManager | Database queries, mappings, transaction rollbacks |
| **`@ActiveProfiles("test")`** | Activates `application-test.yml` | Overriding database URLs, secrets, or ports |

### Anti-Patterns to Avoid:
1. **Using `@SpringBootTest` everywhere:** Boots the entire application context (databases, caches, security, scheduled jobs), slowing the test suite down to minutes.
2. **Assuming `@WebMvcTest` boots services:** It only instantiates controllers. Service collaborators must be explicitly provided as mocks (`@MockBean` or `@MockitoBean`).

---

# Layer 2 — Practical Engineering & Workflows

## 5. Unit-Test a Spring Service with Mockito

Consider an order placement workflow:

### Production Interfaces & Service

```java
package com.example.orders;

public interface InventoryClient {
    int availableUnits(String productId);
}
```

```java
package com.example.orders;

public interface OrderRepository {
    Order save(Order order);
}
```

```java
package com.example.orders;

public record Order(String productId, int quantity) {}
```

```java
package com.example.orders;

public class OrderService {
    private final InventoryClient inventory;
    private final OrderRepository orders;

    public OrderService(InventoryClient inventory, OrderRepository orders) {
        this.inventory = inventory;
        this.orders = orders;
    }

    public Order placeOrder(String productId, int quantity) {
        if (quantity <= 0) {
            throw new IllegalArgumentException("Quantity must be positive");
        }

        if (inventory.availableUnits(productId) < quantity) {
            throw new IllegalStateException("Insufficient inventory");
        }

        return orders.save(new Order(productId, quantity));
    }
}
```

### Complete Unit Test with Mockito

```java
package com.example.orders;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class OrderServiceTest {

    @Mock
    InventoryClient inventory;

    @Mock
    OrderRepository orders;

    OrderService service;

    @BeforeEach
    void setUp() {
        service = new OrderService(inventory, orders);
    }

    @Test
    void placesOrderWhenInventoryIsSufficient() {
        // Arrange
        when(inventory.availableUnits("P-101")).thenReturn(10);
        Order expected = new Order("P-101", 2);
        when(orders.save(any(Order.class))).thenReturn(expected);

        // Act
        Order result = service.placeOrder("P-101", 2);

        // Assert
        assertEquals(expected, result);
        verify(orders).save(new Order("P-101", 2));
    }

    @Test
    void rejectsOrderWhenInventoryIsInsufficient() {
        // Arrange
        when(inventory.availableUnits("P-101")).thenReturn(1);

        // Act & Assert
        assertThrows(
            IllegalStateException.class,
            () -> service.placeOrder("P-101", 2)
        );

        verify(orders, never()).save(any());
    }

    @Test
    void rejectsNonPositiveQuantityBeforeCheckingInventory() {
        // Act & Assert
        assertThrows(
            IllegalArgumentException.class,
            () -> service.placeOrder("P-101", 0)
        );

        // Verify fail-fast behavior: inventory is never contacted
        verifyNoInteractions(inventory, orders);
    }
}
```

### Key Engineering Practices:
- **Constructor Injection:** Allows direct instantiation with mock doubles without booting a Spring container.
- **Fail-Fast Verification (`verifyNoInteractions`):** Proves that invalid inputs are rejected before triggering expensive remote inventory calls.
- **`never().save(any())`:** Confirms database writes are prevented when business validations fail.

---

## 6. Test a Spring MVC Controller with `@WebMvcTest`

Test HTTP routing, JSON serialization, and error handling without starting a live web server:

```java
package com.example.orders;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.test.context.bean.override.mockito.MockitoBean; // Spring Boot 3.4+
import org.springframework.test.web.servlet.MockMvc;

import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(OrderController.class)
class OrderControllerTest {

    @Autowired
    MockMvc mockMvc;

    @MockitoBean // Or @MockBean in earlier Spring Boot versions
    OrderService orderService;

    @Test
    void returnsOrderAsJson() throws Exception {
        when(orderService.findById("O-101"))
            .thenReturn(new OrderResponse("O-101", "P-101"));

        mockMvc.perform(get("/orders/O-101"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.id").value("O-101"))
            .andExpect(jsonPath("$.productId").value("P-101"));
    }
}
```

### What this test verifies:
- HTTP GET mapping `/orders/{id}` routes to the controller method.
- Spring MVC serializes Java records/DTOs into JSON format.
- HTTP status code returns `200 OK`.
- Mockito mock isolates the controller from service and repository logic.

---

## 7. Test a Repository Against a Database with `@DataJpaTest`

Verify custom queries, JPA object-relational mappings, and unique constraints:

```java
package com.example.orders;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;

import static org.junit.jupiter.api.Assertions.assertEquals;

@DataJpaTest
class OrderEntityRepositoryTest {

    @Autowired
    TestEntityManager entityManager;

    @Autowired
    OrderEntityRepository repository;

    @Test
    void savesAndFindsOrderById() {
        OrderEntity entity = new OrderEntity();
        entity.setProductId("P-101");
        entity.setQuantity(2);

        OrderEntity saved = repository.save(entity);

        // Force SQL INSERT execution to database
        entityManager.flush();
        // Detach entities so subsequent findById queries actual database table
        entityManager.clear();

        OrderEntity found = repository.findById(saved.getId())
            .orElseThrow();

        assertEquals("P-101", found.getProductId());
        assertEquals(2, found.getQuantity());
    }
}
```

> **Why `flush()` and `clear()` Matter:** By default, JPA caches entity instances in the first-level persistence context. Without `clear()`, calling `findById()` simply returns the cached object in RAM without executing any SQL SELECT against the database!

### Database Dialect Reality: Embedded H2 vs. Real PostgreSQL
Embedded databases (H2) often accept invalid SQL queries, ignore PostgreSQL JSONB operators, or have different case-sensitivity rules. If your production database is PostgreSQL, configure integration tests using **Testcontainers**.

---

## 8. Test Configuration and External Dependencies

```java
@SpringBootTest
@Testcontainers
class OrderServicePostgresIT {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine");

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
    }

    @Test
    void verifiesRealPostgresPersistence() {
        // Runs against genuine disposable Dockerized PostgreSQL
    }
}
```

### Production Rules:
1. **Never point tests at production or staging databases:** Tests modify, truncate, and corrupt state.
2. **Use `@DynamicPropertySource`:** Binds random dynamic container ports to Spring properties seamlessly.
3. **Isolate Test Profiles:** Store non-production defaults in `src/test/resources/application-test.yml`.

---

## 9. Maven Testing Workflow

Execute targeted testing workflows from the repository root:

```bash
# Run all unit tests
./mvnw test

# Clean target/ and run tests
./mvnw clean test

# Package artifact, including all verification phases
./mvnw package

# Run a specific test class
./mvnw -Dtest=OrderServiceTest test

# Run a specific test method
./mvnw -Dtest=OrderServiceTest#placesOrderWhenInventoryIsSufficient test

# Run integration tests bound to the verify phase (via maven-failsafe-plugin)
./mvnw verify
```

### Triage Sequence for Failed Tests:
1. Read the **first assertion failure** message (downstream failures are frequently cascading side effects).
2. Distinguish compilation errors (`javac`) from runtime assertion errors (`AssertionFailedError`).
3. Inspect Surefire XML reports in `target/surefire-reports/`.
4. Run the failing test in isolation to rule out execution-order coupling.

---

# Layer 3 — Production Engineering & Interview Mastery

## 10. Flaky Tests and CI Reliability

A **flaky test** exhibits non-deterministic behavior—passing and failing intermittently on the same code revision.

### Top Causes of Test Flakiness:
1. **Arbitrary Sleeps (`Thread.sleep(1000)`):** Loaded CI runners with fewer vCPUs execute slower than developer MacBooks, triggering spurious timeouts.  
   *Fix:* Use **Awaitility** for bounded polling:
   ```java
   await().atMost(5, SECONDS).until(() -> worker.isFinished());
   ```
2. **System Clock Reliance (`LocalDateTime.now()`):** Assertions fail when executed across midnight or in different server timezones (UTC vs. local).  
   *Fix:* Inject a fixed `Clock` instance:
   ```java
   Clock fixedClock = Clock.fixed(Instant.parse("2026-10-23T08:00:00Z"), ZoneOffset.UTC);
   ```
3. **Shared Mutable State:** Static variables or shared database tables not cleared between tests.  
   *Fix:* Use `@BeforeEach` resets or `@DirtiesContext`.
4. **Order Dependency:** Test B only passes if Test A executed first to seed data.  
   *Fix:* Make every test self-sufficient and seed its own prerequisites.

---

## 11. Common Production Testing Failures

### Scenario A — Works locally, fails in CI
- **Root Causes**: Different JDK versions, missing CI environment variables, case-sensitive Linux filesystem (APFS on macOS is case-insensitive), or timezone assumptions.
- **Action**: Inspect CI logs, verify `mvn -version`, enforce the Maven Wrapper (`./mvnw`), and run tests in Docker locally to reproduce.

### Scenario B — Unit tests pass, API fails in production
- **Root Causes**: Incorrect Spring auto-configuration, JSON serialization/naming mismatch (`snake_case` vs `camelCase`), missing security filters, or database constraint violations.
- **Action**: Add a focused `@WebMvcTest` or Testcontainers integration test; do not turn every unit test into a full application test.

### Scenario C — Tests pass individually, fail as a full suite
- **Root Causes**: Static state leakage, database records persisting across test classes, port collisions during parallel test execution.
- **Action**: Ensure test isolation; clean up resources in `@AfterEach`; verify `@DirtiesContext` usage for contaminated Spring contexts.

### Scenario D — Test suite is painfully slow
- **Root Causes**: Booting multiple separate Spring contexts, excessive integration tests, or unnecessary real network latency.
- **Action**: Group tests under unified test configurations to allow Spring context caching, and shift business validation logic to pure Mockito unit tests.

---

## 12. Testing Security and Failure Paths

Robust production systems test error paths with the same rigor as happy paths:

- **Input Validation**: Assert `400 Bad Request` on malformed, boundary, or missing fields.
- **Authentication**: Assert `401 Unauthorized` when tokens are missing, expired, or tampered.
- **Authorization & RBAC**: Assert `403 Forbidden` when a standard user accesses an administrative route.
- **Resource Not Found**: Assert `404 Not Found` when requesting non-existent resource IDs.
- **Concurrency & Idempotency**: Assert that duplicate POST requests with the same idempotency key reject duplicate charges.
- **Information Leakage Prevention**: Verify that error payloads conform to RFC 7807 Problem Details and **never leak internal database stack traces or secrets**.

---

## 13. Fifteen Advanced Interview Questions

### Q1. What is the difference between a unit test and an integration test?
**Answer**: A **unit test** isolates a small unit of behavior (a class or method), replacing all external dependencies with test doubles, running in milliseconds. An **integration test** verifies that multiple collaborating components (e.g. Spring controllers, repositories, databases, message brokers) work together correctly across architectural boundaries.

### Q2. Why should you avoid using `@SpringBootTest` for every test?
**Answer**: `@SpringBootTest` boots the full Spring application context, instantiating all beans, configurations, and connections. Doing this for every test drastically inflates test execution time from seconds to minutes. Use focused unit tests or test slices (`@WebMvcTest`, `@DataJpaTest`) instead.

### Q3. What is the difference between a mock and a stub?
**Answer**: A **stub** is an indirect input double that returns predetermined, hardcoded responses to method calls. A **mock** is an indirect output double that records incoming method invocations and allows the test to verify that specific interactions occurred.

### Q4. What is the Arrange–Act–Assert (AAA) pattern?
**Answer**: A standard structural pattern for test readability:
1. **Arrange**: Set up fixtures, inputs, and stub expectations.
2. **Act**: Invoke the target method.
3. **Assert**: Verify return values, state mutations, and required interactions.

### Q5. What does `assertThrows` do in JUnit 5?
**Answer**: It asserts that executing a supplied lambda throws a specific exception class (or subclass), failing the test if no exception or an incorrect exception is thrown, and returning the thrown exception instance for further assertions.

### Q6. Why is mocking a repository insufficient to test a database query?
**Answer**: Mocking a repository stubs the Java interface without executing any SQL against a database engine. It cannot catch invalid SQL syntax, broken JPQL mappings, constraint violations, or database dialect differences.

### Q7. What is a flaky test and why is it dangerous?
**Answer**: A flaky test passes and fails intermittently on identical code revisions due to timing, order dependence, or environmental factors. It erodes developer trust in CI pipelines, causing teams to ignore genuine regression failures.

### Q8. How do you test asynchronous code reliably without `Thread.sleep`?
**Answer**: Use synchronization primitives (`CountDownLatch`, `CompletableFuture.join()`) or bounded polling libraries like **Awaitility** (`await().atMost(...).until(...)`) to await the actual completion condition.

### Q9. What is `@DataJpaTest` used for?
**Answer**: It is a Spring Boot test slice that configures only JPA entities, Spring Data repositories, and an `EntityManager`, running each test in a transaction that is rolled back by default at test completion.

### Q10. What is `@WebMvcTest` used for?
**Answer**: It is a Spring Boot test slice that configures only the presentation layer (Spring MVC controllers, filters, JSON serialization), allowing fast testing of HTTP status codes, routing, and payloads via `MockMvc` without starting an embedded servlet container.

### Q11. Why can an embedded in-memory database (H2) hide production bugs?
**Answer**: H2 differs from production databases (like PostgreSQL) in supported SQL dialect, data types (JSONB, UUID), lock escalation models, constraint enforcement, and case sensitivity, allowing tests to pass that fail when deployed to production.

### Q12. What is the purpose of Testcontainers?
**Answer**: Testcontainers provides lightweight, disposable Docker containers for integration tests, allowing tests to execute against genuine production-identical databases (PostgreSQL, MySQL), caches (Redis), and message brokers (Kafka).

### Q13. Should a test verify every internal method invocation with `verify()`?
**Answer**: No. Overusing `verify()` couples tests to internal private implementation details rather than observable business contracts, creating brittle tests that break during harmless refactoring.

### Q14. How do you systematically debug a test that passes locally but fails in CI?
**Answer**: Inspect CI console logs for the root cause; verify JDK vendor/version alignment; check for case-sensitive file path lookups; eliminate timezone/locale dependencies; and run tests in a clean Docker container matching the CI environment.

### Q15. How do you balance test suite execution speed with production confidence?
**Answer**: Follow the testing pyramid: maintain a wide foundation of fast, deterministic unit tests for complex business rules; a focused set of slice/integration tests for database and API boundaries; and a minimal set of end-to-end smoke tests for critical user workflows.

---

## 14. Hands-On Capstone

Build an order processing service with three explicit requirements:
1. Reject non-positive quantities (`quantity <= 0`) with `IllegalArgumentException`.
2. Reject orders when inventory is insufficient with `IllegalStateException`.
3. Save valid orders and return the persisted result.

### Implementation Checklist
- [ ] Write three isolated unit tests using JUnit 5 and Mockito (`@ExtendWith(MockitoExtension.class)`).
- [ ] Add a controller test with `@WebMvcTest` asserting HTTP `200 OK` and JSON response fields.
- [ ] Add a controller test asserting HTTP `400 Bad Request` on invalid input payloads.
- [ ] Add a repository integration test using `@DataJpaTest` with `TestEntityManager.flush()` and `clear()`.
- [ ] Run the complete test suite using `./mvnw clean test`.
- [ ] Confirm all tests pass independently and as a full suite.
- [ ] Introduce an intentional boundary error (e.g. change `<` to `<=`) and verify tests fail.
- [ ] Verify test configuration cannot target production databases.
- [ ] Document which requirements are covered at unit vs. integration levels.

### Quick Mastery Check

1. **A repository query must be verified against PostgreSQL. Which test is most appropriate?**
   - *Option A*: A unit test with a mocked repository.
   - *Option B (Correct)*: An integration test using PostgreSQL (e.g. via Testcontainers).
   - *Option C*: A test that only checks HTTP status.
   - *Rationale*: A real database engine is required to validate SQL dialect, type mappings, and constraint enforcement.

2. **A test passes alone but fails when executed in the full test suite. What should you investigate first?**
   - *Option A*: Increase timeouts.
   - *Option B*: Delete the failing assertion.
   - *Option C (Correct)*: Shared mutable static state, execution order dependence, or uncleaned database records.
   - *Rationale*: Suite-only failures point to contamination or side effects leaking across test boundaries.

3. **What is the primary benefit of a narrow Spring test slice like `@WebMvcTest`?**
   - *Option A*: It eliminates the need for assertions.
   - *Option B (Correct)*: It instantiates only the presentation layer, keeping tests fast and focused.
   - *Option C*: It proves every backend database query works.
   - *Rationale*: Slices provide fast feedback on HTTP contracts without booting unneeded database beans.

---

## 15. JUnit 5 Completion Checklist

- [ ] Explain the JUnit Platform, Jupiter, and Vintage architecture.
- [ ] Write readable tests using the Arrange–Act–Assert pattern.
- [ ] Use assertions, parameterized tests, and lifecycle callbacks appropriately.
- [ ] Isolate service behavior with Mockito mocks and stubs.
- [ ] Choose the correct Spring testing scope (`@WebMvcTest`, `@DataJpaTest`, `@SpringBootTest`).
- [ ] Test persistence behavior using real database semantics (`flush()` and `clear()`).
- [ ] Diagnose flaky and environment-dependent CI failures.
- [ ] Explain the testing pyramid and its architectural trade-offs.
- [ ] Run and debug tests reliably through Maven (`./mvnw test`).
- [ ] Articulate testing trade-offs in backend engineering interviews.

---

## Final Completion Protocol

1. Authoritative source files:
   - `content/junit5/01-junit5-fundamentals-unit-testing.md`
   - `content/junit5/02-junit5-advanced-testing-production.md`
2. Both chunks verified for all three learning layers.
3. Single final handbook PDF: `docs/junit5/BEH_JUNIT5_COMPLETE_HANDBOOK.pdf`.
4. Update `README.md` progress tracker.
5. Commit with exact message: `JUnit 5 done`.
