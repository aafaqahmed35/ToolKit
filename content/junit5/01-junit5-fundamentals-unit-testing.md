# JUnit 5 — Chunk 1: Fundamentals & Unit Testing
## Backend Engineering Tools & Infrastructure Handbook

**Phase:** I — Developer Foundations  
**Chunk:** 1 of 2  
**Source file:** `content/junit5/01-junit5-fundamentals-unit-testing.md`

---

## Learning Objectives

By the end of this chapter, you should be able to:

- Explain unit testing and the role of JUnit 5.
- Write tests for Java classes and business logic.
- Use assertions, lifecycle methods, parameterized tests and exception testing.
- Separate unit tests from integration tests.
- Structure tests for readable, reliable feedback.
- Run and troubleshoot tests through Maven.
- Explain fundamental testing concepts in SDE-1 interviews.

---

# Layer 1 — Fundamentals & Mental Models

## 1. What is JUnit 5?

Imagine you're developing a Java backend with an order-pricing service. It calculates totals, validates quantities and applies discounts.

You could test every change manually by starting the application and submitting requests. But that becomes slow and unreliable as the project grows.

**JUnit is a testing framework for Java. JUnit 5 is the modern generation built around the JUnit Platform, JUnit Jupiter and JUnit Vintage.**

### The JUnit 5 Modular Architecture

```text
+-------------------------------------------------------------------------------+
|                                 JUnit 5                                       |
+-------------------------------------------------------------------------------+
|                                JUnit Platform                                 |
|            Foundation for launching test engines on the JVM / build tools     |
+---------------------------------------+---------------------------------------+
|             JUnit Jupiter             |             JUnit Vintage             |
|   New programming & extension model   |   Backward compatibility engine for   |
|   for writing JUnit 5 tests & runners |       running JUnit 3 & JUnit 4       |
+---------------------------------------+---------------------------------------+
```

- **JUnit Platform:** infrastructure for launching and integrating test engines with build tools (Maven Surefire, Gradle) and IDEs (IntelliJ, Eclipse, VS Code).
- **JUnit Jupiter:** the programming model and extension support for writing modern JUnit 5 tests (`org.junit.jupiter.api`).
- **JUnit Vintage:** supports running legacy JUnit 3 and JUnit 4 tests on the modern JUnit Platform.

For modern Java backends, you will primarily write tests using JUnit Jupiter.

---

## 2. What is a unit test?

A unit test checks a small piece of behavior in isolation, commonly a single method or class.

Suppose you have this Java class:

```java
package com.example.pricing;

public class PriceCalculator {

    public int total(int unitPrice, int quantity) {
        return unitPrice * quantity;
    }
}
```

A unit test checks whether it produces the expected result:

```java
package com.example.pricing;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;

class PriceCalculatorTest {

    @Test
    void calculatesTotalPrice() {
        PriceCalculator calculator = new PriceCalculator();

        int result = calculator.total(100, 3);

        assertEquals(300, result);
    }
}
```

### The AAA (Arrange–Act–Assert) Pattern

```text
                    +------------------------------------+
                    |              Arrange               |
                    | Create calculator & inputs (100, 3)|
                    +------------------------------------+
                                      │
                                      ▼
                    +------------------------------------+
                    |                Act                 |
                    | Call calculator.total(100, 3)      |
                    +------------------------------------+
                                      │
                                      ▼
                    +------------------------------------+
                    |               Assert               |
                    | Verify result == 300               |
                    +------------------------------------+
```

1. **Arrange:** set up the preconditions, instantiate objects, and prepare input fixtures.
2. **Act:** invoke the specific method or behavior under test.
3. **Assert:** verify that the observed outcome matches the expected specification.

A good test communicates the intended business behavior, not merely the mechanics of calling a method.

---

## 3. Why unit tests matter

Unit tests are fundamental to production engineering:

- **Regression safety:** catch unintended side effects immediately when code is modified.
- **Executable documentation:** serve as living, authoritative specifications of how classes are designed to behave.
- **Refactoring confidence:** allow restructuring internal algorithms without fear of breaking contracts.
- **Edge case verification:** systematically exercise nulls, negative numbers, overflow, and empty collections.
- **Fast feedback loop:** execute thousands of assertions in seconds without booting heavyweight servers or databases.
- **Automated CI quality gates:** block defective pull requests from reaching production environments.

> **Production Lesson:** Tests do not prove that software is 100% defect-free. They provide verifiable evidence that the tested behavior behaves correctly for the scenarios and boundaries covered.

---

## 4. Your first JUnit 5 test

In a standard Maven project, place source and test files strictly according to convention:

```text
orders-service/
├── pom.xml
└── src/
    ├── main/
    │   └── java/
    │       └── com/example/pricing/PriceCalculator.java
    └── test/
        └── java/
            └── com/example/pricing/PriceCalculatorTest.java
```

### Maven Dependency Configuration

For Spring Boot projects, the starter test bundle imports JUnit 5 automatically:

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-test</artifactId>
    <scope>test</scope>
</dependency>
```

For plain Java applications without Spring Boot:

```xml
<dependencies>
    <dependency>
        <groupId>org.junit.jupiter</groupId>
        <artifactId>junit-jupiter</artifactId>
        <version>5.10.2</version>
        <scope>test</scope>
    </dependency>
</dependencies>
```

The fundamental annotation is:

```java
@Test
void shouldCalculateTotal() {
    // test behavior
}
```

Notice that in JUnit 5, test classes and test methods do **not** need to be declared `public`. Package-private visibility is preferred and idiomatic.

---

## 5. Assertions: how tests decide whether behavior is correct

Assertions compare actual runtime outcomes with expected values:

```java
import static org.junit.jupiter.api.Assertions.*;

assertEquals(10, actual);
assertNotEquals(0, actual);
assertTrue(actual > 0);
assertFalse(items.isEmpty());
assertNull(value);
assertNotNull(value);
assertSame(expectedRef, actualRef);
assertNotSame(obj1, obj2);
```

### Ordering Convention

Always follow the standard parameter order:

`assertEquals(expected, actual, optionalMessage);`

Reversing expected and actual produces confusing diagnostic failure messages in CI logs:

```text
// Incorrect: assertEquals(actual, 300);
// Failure message: "Expected: <300>, but was: <actual>" (misleading!)
```

### Multiple Assertions with `assertAll`

When multiple assertions are placed sequentially, the first failure immediately terminates test execution, masking subsequent failures:

```java
// If id fails, status and quantity are never evaluated!
assertEquals("order-123", order.id());
assertEquals("CREATED", order.status());
assertEquals(3, order.quantity());
```

Use `assertAll` to group assertions so that all failures are reported together:

```java
assertAll("Order attributes validation",
    () -> assertEquals("order-123", order.id(), "Incorrect order ID"),
    () -> assertEquals("CREATED", order.status(), "Incorrect status"),
    () -> assertEquals(3, order.quantity(), "Incorrect quantity")
);
```

---

## 6. Test names should describe behavior

Compare these naming styles:

| Poor Test Name | Good Behavioral Test Name | Rationale |
| :--- | :--- | :--- |
| `test1()` | `calculatesTotalForPositiveQuantity()` | Explicitly documents the scenario being validated |
| `testCalculate()` | `total_withNegativeUnitPrice_throwsIllegalArgumentException()` | Follows `method_condition_expectedResult` |
| `checkOrder()` | `createOrder_whenInventoryIsInsufficient_rejectsOrder()` | Documents business domain rule |

A standard convention:

`methodUnderScope_conditionUnderObservation_expectedOutcome`

Consistency across the engineering team matters more than any single dogmatic naming style.

---

# Layer 2 — Practical Engineering & Workflows

## 7. Build a realistic unit-tested class

Let's make the price calculator robust against invalid domain states and arithmetic errors:

```java
package com.example.pricing;

public class PriceCalculator {

    public int total(int unitPrice, int quantity) {
        if (unitPrice < 0) {
            throw new IllegalArgumentException("Unit price cannot be negative");
        }

        if (quantity <= 0) {
            throw new IllegalArgumentException("Quantity must be positive");
        }

        return Math.multiplyExact(unitPrice, quantity);
    }
}
```

This class defines four explicit contracts:
1. Valid inputs produce the correct total (`unitPrice * quantity`).
2. Negative unit prices are rejected with `IllegalArgumentException`.
3. Zero or negative quantities are rejected with `IllegalArgumentException`.
4. Large values that overflow standard 32-bit integer limits throw `ArithmeticException`.

---

## 8. Test exceptions

Use `assertThrows` to verify expected exception types:

```java
package com.example.pricing;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class PriceCalculatorTest {

    private final PriceCalculator calculator = new PriceCalculator();

    @Test
    void rejectsNegativeUnitPrice() {
        var exception = assertThrows(
            IllegalArgumentException.class,
            () -> calculator.total(-100, 2)
        );

        assertEquals("Unit price cannot be negative", exception.getMessage());
    }

    @Test
    void rejectsZeroQuantity() {
        var exception = assertThrows(
            IllegalArgumentException.class,
            () -> calculator.total(100, 0)
        );

        assertEquals("Quantity must be positive", exception.getMessage());
    }

    @Test
    void throwsArithmeticExceptionOnIntegerOverflow() {
        assertThrows(
            ArithmeticException.class,
            () -> calculator.total(Integer.MAX_VALUE, 2)
        );
    }
}
```

If the code inside the lambda completes without throwing an exception, or throws an unrelated exception type, the test fails immediately.

---

## 9. Test multiple input scenarios with parameterized tests

Parameterized tests run the same test logic against a table of distinct inputs and expected outputs, eliminating repetitive boilerplate test methods.

Add the dependency (included in `spring-boot-starter-test`):

```xml
<dependency>
    <groupId>org.junit.jupiter</groupId>
    <artifactId>junit-jupiter-params</artifactId>
    <scope>test</scope>
</dependency>
```

### Parameterized Test with `@CsvSource`

```java
package com.example.pricing;

import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class PriceCalculatorParameterizedTest {

    private final PriceCalculator calculator = new PriceCalculator();

    @ParameterizedTest(name = "Price: {0}, Qty: {1} => Total: {2}")
    @CsvSource({
        "100, 1, 100",
        "100, 3, 300",
        "250, 4, 1000",
        "0,   5, 0"
    })
    void calculatesTotalAcrossValidInputs(int unitPrice, int quantity, int expected) {
        assertEquals(expected, calculator.total(unitPrice, quantity));
    }

    @ParameterizedTest
    @ValueSource(ints = {0, -1, -10, -500})
    void rejectsInvalidQuantities(int invalidQuantity) {
        assertThrows(
            IllegalArgumentException.class,
            () -> calculator.total(100, invalidQuantity)
        );
    }
}
```

---

## 10. Understand the test lifecycle

JUnit Jupiter manages the execution lifecycle of each test class:

| Annotation | Execution Timing | Default Visibility / Method Signature |
| :--- | :--- | :--- |
| **`@BeforeAll`** | Runs once before any tests in the class | Must be `static void` (unless `PER_CLASS`) |
| **`@BeforeEach`** | Runs before every individual `@Test` | `void` (runs per instance) |
| **`@Test`** | The test method execution | `void` |
| **`@AfterEach`** | Runs after every individual `@Test` | `void` (cleanup per instance) |
| **`@AfterAll`** | Runs once after all tests in the class finish | Must be `static void` (unless `PER_CLASS`) |

### Example Lifecycle Implementation

```java
package com.example.state;

import org.junit.jupiter.api.*;
import static org.junit.jupiter.api.Assertions.assertEquals;

class CounterTest {

    private Counter counter;

    @BeforeAll
    static void initGlobalFixtures() {
        // Expensive one-time initialization (e.g. static configuration)
    }

    @BeforeEach
    void setUp() {
        // Fresh instance created before each test to prevent cross-test pollution
        counter = new Counter();
    }

    @AfterEach
    void tearDown() {
        // Teardown per-test state
    }

    @Test
    void startsAtZero() {
        assertEquals(0, counter.value());
    }

    @Test
    void incrementsByOne() {
        counter.increment();
        assertEquals(1, counter.value());
    }
}
```

> **Crucial Rule:** By default, JUnit creates a **new test-class instance** for every single test method. This design guarantees test isolation by preventing field modifications in one test from leaking into another.

---

## 11. Test collections and returned data

When testing lists, maps, or sets, verify collection semantics rather than just checking if the object is non-null:

```java
List<String> items = catalog.findProductsByCategory("Electronics");

assertAll("Product list validations",
    () -> assertNotNull(items),
    () -> assertEquals(2, items.size(), "Unexpected element count"),
    () -> assertTrue(items.contains("Laptop")),
    () -> assertTrue(items.contains("Mouse")),
    () -> assertFalse(items.contains("Apple"))
);
```

Ensure you verify:
- Expected size and presence of key items.
- Correct ordering when sorting is guaranteed by the API contract.
- Empty collection handling (`assertTrue(list.isEmpty())`).
- Avoid fragile assertions that fail merely if elements appear in an unspecified order.

---

## 12. Mocking: isolate the unit under test

A pure unit test tests one class in complete isolation from external databases, networks, and services.

Consider `OrderService`:

```java
package com.example.orders;

import java.util.Optional;

public class OrderService {

    private final OrderRepository repository;

    public OrderService(OrderRepository repository) {
        this.repository = repository;
    }

    public Order findById(String id) {
        return repository.findById(id)
            .orElseThrow(() -> new IllegalArgumentException("Order not found: " + id));
    }
}
```

Using Mockito, we mock `OrderRepository` so no actual database or connection pool is involved:

```java
package com.example.orders;

import org.junit.jupiter.api.Test;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.*;

class OrderServiceTest {

    @Test
    void returnsOrderWhenPresentInRepository() {
        // 1. Arrange: Create mock collaborator and stub behavior
        OrderRepository repository = mock(OrderRepository.class);
        Order expectedOrder = new Order("ord-101", "PAID");

        when(repository.findById("ord-101"))
            .thenReturn(Optional.of(expectedOrder));

        OrderService service = new OrderService(repository);

        // 2. Act
        Order actualOrder = service.findById("ord-101");

        // 3. Assert: Verify returned entity and interaction
        assertEquals(expectedOrder, actualOrder);
        verify(repository, times(1)).findById("ord-101");
    }

    @Test
    void throwsExceptionWhenOrderNotFound() {
        OrderRepository repository = mock(OrderRepository.class);

        when(repository.findById("missing-id"))
            .thenReturn(Optional.empty());

        OrderService service = new OrderService(repository);

        assertThrows(
            IllegalArgumentException.class,
            () -> service.findById("missing-id")
        );
    }
}
```

### When to Mock vs. When Not to Mock:
- **Mock**: Database repositories, third-party payment gateways, SMS/email senders, external microservice clients.
- **Do Not Mock**: Pure domain entities, value objects, simple DTOs, standard Java collections (`List`, `Map`), or the class under test itself.

---

## 13. Run tests with Maven

Execute the test phase via the Maven Wrapper:

```bash
./mvnw test
```

Run a specific test class:

```bash
./mvnw test -Dtest=PriceCalculatorTest
```

Run a single test method:

```bash
./mvnw test -Dtest=PriceCalculatorTest#calculatesTotalPrice
```

Execute full verification (compilation, unit tests, packaging, integration tests):

```bash
./mvnw clean verify
```

If tests fail, inspect the console error trace or view the detailed Surefire XML and text reports under:

```text
target/surefire-reports/
```

---

## 14. Exercise: test the calculator

Verify your understanding by implementing the complete matrix of calculator test cases:

| Case | Inputs | Expected Outcome |
| :--- | :--- | :--- |
| Normal calculation | `unitPrice=100`, `quantity=2` | Returns `200` |
| Identity quantity | `unitPrice=100`, `quantity=1` | Returns `100` |
| Zero unit price | `unitPrice=0`, `quantity=5` | Returns `0` |
| Negative unit price | `unitPrice=-10`, `quantity=2` | Throws `IllegalArgumentException` |
| Zero quantity | `unitPrice=100`, `quantity=0` | Throws `IllegalArgumentException` |
| Negative quantity | `unitPrice=100`, `quantity=-3` | Throws `IllegalArgumentException` |
| Multiplication overflow | `unitPrice=Integer.MAX_VALUE`, `quantity=2` | Throws `ArithmeticException` |

---

# Layer 3 — Production Engineering & Interview Mastery

## 15. What makes a unit test reliable?

A production-grade unit test adheres to the **F.I.R.S.T.** principles:

- **Fast:** Executes in milliseconds. If unit tests take minutes, engineers stop running them locally.
- **Isolated / Independent:** Tests never depend on execution order or side effects from prior tests.
- **Repeatable / Deterministic:** Returns identical results regardless of whether executed on macOS, Linux CI, or at midnight on New Year's Eve.
- **Self-Validating:** Evaluates to a boolean pass or fail; no manual log inspection required.
- **Timely / Thorough:** Written concurrently with production code, covering happy paths, edge boundaries, and exception branches.

Avoid anti-patterns:
- Flaky tests caused by `Thread.sleep()`.
- Tests that depend on current machine timezone or default locale.
- Tests that access external network URLs.

---

## 16. Unit tests versus integration tests

| Dimension | Unit Tests | Integration Tests |
| :--- | :--- | :--- |
| **Scope** | Single class or isolated method | Multiple collaborating components |
| **Dependencies** | Mocks or stubs for all external I/O | Real databases (PostgreSQL/H2), Spring context |
| **Speed** | 1–5 milliseconds per test | 500ms to several seconds per test |
| **Failure Isolation** | Pinpoints the exact line in a class | Failure could be in DB, query, mapping, or network |
| **Maven Plugin** | `maven-surefire-plugin` (`mvn test`) | `maven-failsafe-plugin` (`mvn verify`) |
| **Naming Convention** | `*Test.java` | `*IT.java` or `*IntegrationTest.java` |

A resilient backend uses both: high volumes of fast unit tests for complex business algorithms, supplemented by targeted integration tests verifying persistence and HTTP wiring.

---

## 17. Test behavior, not implementation details

Avoid **overspecified tests** that assert every internal private helper call or intermediate variable:

```java
// Fragile / Brittle: Couples test to internal private method names
verify(service, times(1)).doInternalHelperStepA();
verify(service, times(1)).doInternalHelperStepB();
```

If you refactor internal algorithms without changing the external business contract, existing unit tests should continue passing without modification. Test inputs and observable outputs, not private implementation plumbing.

---

## 18. Common failure scenarios

### Scenario A: Tests pass individually but fail when run together
- **Root Cause**: Leaked static state or shared mutable singleton modified during one test, contaminating downstream tests.
- **Remediation**: Avoid static mutable variables; reset shared state in `@BeforeEach` / `@AfterEach`.

### Scenario B: Tests pass locally but fail in CI
- **Root Cause**: Discrepancies in JDK versions, APFS (case-insensitive) vs. Linux ext4 (case-sensitive) file lookups, or unconfigured locale/timezone differences.
- **Remediation**: Run tests in Docker with identical Linux JDK configurations; isolate date logic with fixed `Clock` instances (`Clock.fixed()`).

### Scenario C: A unit test takes several seconds to execute
- **Root Cause**: Accidentally booting the full Spring application context (`@SpringBootTest`) instead of running a pure Mockito unit test (`@ExtendWith(MockitoExtension.class)`).
- **Remediation**: Strip Spring annotations from business unit tests.

### Scenario D: High test coverage but production bugs escape
- **Root Cause**: Shallow assertion syndrome—tests exercise code paths to increase metrics but perform no assertions or assert only non-nullness (`assertNotNull(res)`).
- **Remediation**: Enforce strict assertion reviews and mutation testing (e.g. PIT).

---

## 19. Interview questions — 15 essentials

### Q1. What is JUnit 5 and how is it architected?
**Answer**: JUnit 5 is the modern generation of the Java testing framework. It is decoupled into three distinct sub-projects: **JUnit Platform** (runtime foundation for launching test engines), **JUnit Jupiter** (the programming model and extension API for writing JUnit 5 tests), and **JUnit Vintage** (backward compatibility engine for running JUnit 3/4 tests).

### Q2. What does the `@Test` annotation signify in JUnit 5?
**Answer**: It marks a method as a test method to be discovered and executed by the JUnit Jupiter engine. In JUnit 5, test methods and classes do not need to be `public`; package-private visibility is preferred.

### Q3. Explain the Arrange–Act–Assert (AAA) pattern.
**Answer**: A standard structural pattern for unit tests:
1. **Arrange**: Set up fixtures, inputs, and mock collaborator responses.
2. **Act**: Invoke the method under test with the prepared inputs.
3. **Assert**: Verify that the return value, exception, or state mutation matches the expected specification.

### Q4. What is the difference between `assertEquals` and `assertSame`?
**Answer**: `assertEquals` verifies logical equality using the target object's `equals(Object)` method. `assertSame` checks memory reference equality using the `==` operator to confirm both references point to the exact same heap instance.

### Q5. How do you test that a method throws an expected exception in JUnit 5?
**Answer**: Use `assertThrows(ExpectedException.class, () -> methodCall())`. It returns the thrown exception instance, allowing further assertions on the error message or custom exception fields.

### Q6. What is the difference between `@BeforeEach` and `@BeforeAll`?
**Answer**: `@BeforeEach` executes before every individual `@Test` method in the class, operating on that test's fresh instance. `@BeforeAll` executes once before all test methods in the class begin; it must be declared `static` under the default test lifecycle.

### Q7. What are parameterized tests and why are they valuable?
**Answer**: Tests annotated with `@ParameterizedTest` that execute the same test logic repeatedly across multiple arguments supplied by sources like `@ValueSource`, `@CsvSource`, or `@MethodSource`. They eliminate duplicated test boilerplate and simplify boundary-value analysis.

### Q8. What is mocking and why is it used in unit testing?
**Answer**: Mocking is the practice of replacing real external collaborators (databases, third-party HTTP clients, messaging brokers) with simulated test doubles that return controlled stub responses and record method invocations, enabling fast, isolated verification of business logic.

### Q9. When should you use a mock versus a real object?
**Answer**: Use mocks for slow, non-deterministic, or out-of-process collaborators (databases, network APIs, disk I/O, email servers). Use real objects for domain entities, value objects, mathematical utilities, and pure data structures.

### Q10. What is the fundamental difference between a unit test and an integration test?
**Answer**: A **unit test** validates a single class or method in complete isolation without external I/O or frameworks, running in milliseconds. An **integration test** verifies the interaction and wiring across multiple layers (e.g. Spring controllers, database repositories, JPA mappings) against real or containerized infrastructure.

### Q11. What causes flaky tests and how do you prevent them?
**Answer**: Flaky tests are caused by non-deterministic factors: reliance on real system clocks, `Thread.sleep()`, race conditions in concurrent code, dependency on test execution order, unseeded random number generators, or network latency. Prevent them by using deterministic clocks (`Clock.fixed()`), dependency injection, and clean state resets.

### Q12. Why does JUnit create a new instance of the test class for each test method?
**Answer**: To enforce test isolation. By instantiating a fresh class instance for every `@Test`, instance variables modified in one test cannot pollute or influence subsequent test outcomes.

### Q13. How are JUnit 5 tests executed in a Maven build?
**Answer**: Maven Surefire Plugin discovers and runs test classes ending in `*Test`, `Test*`, or `*TestCase` during the `test` phase (`mvn test`), reporting results in `target/surefire-reports/`.

### Q14. What is the benefit of `assertAll` over multiple sequential assertions?
**Answer**: Sequential assertions fail-fast on the first mismatch, hiding information about whether remaining assertions would have passed or failed. `assertAll` evaluates every supplied assertion independently and reports all failures together in a unified error summary.

### Q15. Does 100% code coverage mean software is bug-free?
**Answer**: No. Code coverage only measures which lines of bytecode were executed during testing. It does not prove that assertions were meaningful, that boundary edge cases were evaluated, or that specifications were correct.

---

# 20. Hands-on mastery checklist

- [ ] Create a Maven project with JUnit Jupiter configured.
- [ ] Write a passing unit test using `@Test` and `assertEquals`.
- [ ] Test invalid input and boundary exceptions using `assertThrows`.
- [ ] Create a parameterized test with `@CsvSource` and `@ValueSource`.
- [ ] Use `@BeforeEach` to initialize clean test state.
- [ ] Mock a repository and test service behavior using Mockito (`when`, `thenReturn`, `verify`).
- [ ] Run tests through Maven (`./mvnw test`) and inspect Surefire reports.
- [ ] Explain the difference between unit and integration tests.
- [ ] Identify one possible cause of a flaky test and write a deterministic fix.
- [ ] Add tests for boundaries, arithmetic overflow, and failure scenarios.

---

## Completion Protocol

1. Authoritative source file: `content/junit5/01-junit5-fundamentals-unit-testing.md`.
2. Coverage of all three layers: Fundamentals & Mental Models, Practical Engineering & Workflows, and Production Engineering & Interview Mastery.
3. No chunk-level PDF generated.
4. Next chunk: `content/junit5/02-junit5-advanced-testing-production.md`.
5. Compile `docs/junit5/BEH_JUNIT5_COMPLETE_HANDBOOK.pdf` only after Chunk 2 is complete.
6. Commit with exact message `JUnit 5 done` only upon complete tool verification.

**JUnit 5 progress: 1 of 2 educational chunks authored.**
