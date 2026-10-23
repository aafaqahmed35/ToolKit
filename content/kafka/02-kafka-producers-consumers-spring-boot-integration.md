# Kafka — Chunk 2: Producers, Consumers, Delivery Semantics & Spring Boot Integration

**Backend Engineering Tools & Infrastructure Handbook (BEH)**

**Source file:** `content/kafka/02-kafka-producers-consumers-spring-boot-integration.md`

---

# 1. Learning Objectives

By the end of this chapter, you should be able to:

- Configure Kafka producers and consumers in a Spring Boot backend.
- Understand serialization, acknowledgments, retries, and idempotent producers.
- Explain consumer groups, partition assignments, and rebalancing.
- Manage offsets and understand the consequences of commit timing.
- Build practical event producers and consumers.
- Handle processing failures without creating uncontrolled retry loops.
- Design idempotent consumers and understand delivery guarantees.
- Diagnose common producer, consumer, and integration failures.

This chapter builds on Kafka's core mental models from Chunk 1. The focus is now implementation and operational behavior. The third chunk will deepen production reliability, security, performance, and incident response.

# Layer 1 — Fundamentals & Mental Models

## 2. The Producer: Sending Records Reliably

A Kafka producer sends records to a topic. Its job is more involved than simply writing a message to a server.

A typical producer flow is:

```text
Application creates event
        |
        v
Serialize key and value
        |
        v
Select partition
        |
        v
Buffer and batch records
        |
        v
Send records to broker
        |
        v
Receive acknowledgment or error
```

The producer must handle network failures, metadata updates, batching, timeouts, and potentially retriable errors.

### 2.1 Producer configuration that matters

| Setting | Purpose | Engineering consideration |
|---|---|---|
| `bootstrap.servers` | Initial broker addresses | The client discovers cluster metadata through these addresses. |
| `key.serializer` | Serializes record keys | Must match the chosen key representation. |
| `value.serializer` | Serializes record values | JSON, strings, Avro, and other formats have different tradeoffs. |
| `acks` | Controls acknowledgment requirements | Affects durability and latency. |
| `enable.idempotence` | Prevents certain duplicate writes caused by producer retries | Does not make arbitrary business operations exactly once. |
| `retries` | Controls retry attempts in applicable configurations | Retries must be considered alongside timeouts and idempotency. |
| `delivery.timeout.ms` | Bounds the overall time allowed for delivery | Application timeout expectations should account for it. |
| `request.timeout.ms` | Bounds waiting for a broker response | Must be considered with retry and delivery settings. |
| `linger.ms` | Allows additional time to accumulate batches | Can improve batching at the cost of added waiting time. |
| `batch.size` | Controls the target batch size | The effect depends on traffic patterns and record sizes. |
| `compression.type` | Compresses producer batches | Can reduce network and storage usage while consuming CPU. |

Configuration names and defaults can vary by Kafka client version. Check the documentation for the version used by your application.

### 2.2 Understanding `acks`

The `acks` setting determines what acknowledgment the producer requires before treating a send as successful.

- `acks=0`: the producer does not wait for broker acknowledgment.
- `acks=1`: the leader acknowledges the write.
- `acks=all`: the leader waits for the required in-sync replicas according to the cluster's replication configuration.

`acks=all` does not mean every configured replica must acknowledge under every configuration. The in-sync replica set and settings such as `min.insync.replicas` determine the relevant behavior.

A common reliability-oriented configuration uses:

```properties
acks=all
enable.idempotence=true
```

For stronger durability, the topic's replication configuration and broker health must also be designed appropriately. A single-broker development environment cannot demonstrate multi-broker fault tolerance.

### 2.3 Producer idempotence

Producer retries can create duplicates in some failure scenarios. Kafka's idempotent producer capability helps prevent duplicate log entries caused by supported producer retries within its protocol guarantees.

However, producer idempotence does not prevent your application from intentionally calling `send()` twice for the same business event.

For example:

```text
Request arrives
    |
    v
Application creates OrderCreated
    |
    v
Application sends it twice
    |
    v
Two logical sends may occur
```

If the application must recognize the same business event across requests or replays, use a stable event ID and appropriate business-level deduplication.

## 3. Serialization: What Actually Goes Over the Network?

Kafka records contain byte-oriented keys and values. Producers serialize application objects before transmission, and consumers deserialize them after fetching records.

For a Java application:

```text
OrderCreatedEvent object
        |
        v
JSON serializer
        |
        v
Kafka record bytes
        |
        v
JSON deserializer
        |
        v
OrderCreatedEvent object
```

Serialization is a contract between producers and consumers.

Common options include:

- Plain strings for simple events.
- JSON for approachable service integration.
- Avro or Protobuf when schema management and compact, typed data are important.

### Schema evolution

Suppose a producer adds a new field:

```json
{
  "eventId": "evt-123",
  "orderId": "ord-456",
  "currency": "INR"
}
```

Consumers must be able to interpret the event safely.

Good practices include:

- Prefer compatible schema changes.
- Define sensible behavior for missing optional fields.
- Avoid silently changing the meaning of an existing field.
- Test producer and consumer versions together.
- Use a schema registry when the architecture benefits from centrally governed schemas.

A schema registry is an additional component, not an inherent requirement for every Kafka deployment.

## 4. The Consumer: Fetching Is Not Processing

A consumer fetches records from partitions and executes application code.

Consider this sequence:

```text
1. Fetch record at offset 25.
2. Update inventory in PostgreSQL.
3. Commit progress for the partition.
```

If the process crashes after step 2 but before step 3, the record may be processed again.

If the order is reversed:

```text
1. Fetch record at offset 25.
2. Commit progress.
3. Update inventory in PostgreSQL.
```

A crash after step 2 but before step 3's business equivalent—the database update—can cause the operation to be skipped when the consumer resumes.

The core problem is that a Kafka offset commit and a PostgreSQL transaction are normally separate operations.

**The solution is not simply to memorize a commit order. It is to design processing so retries and crashes are safe.**

## 5. Offset Management

An offset records a consumer group's progress within a partition. The committed offset is used as a recovery position.

Important concepts:

- **Current position:** where the consumer is currently reading.
- **Committed offset:** the progress saved for recovery.
- **Log-end offset:** the end position of the partition log.
- **Consumer lag:** the gap between a consumer's progress and the log end, interpreted according to the monitoring tool's offset conventions.

### Automatic versus manual commits

With automatic commits, the client periodically commits offsets according to configuration. This is convenient but can be unsafe if your processing takes longer than expected or if the commit timing does not match your business-processing requirements.

With manual commits, the application chooses when to commit. This provides more control but makes correct offset management the application's responsibility.

For business-critical processing, define the relationship between processing success and offset commits explicitly.

### Example failure

```text
Offset 25 fetched
       |
       v
Database update succeeds
       |
       v
Process crashes before offset commit
       |
       v
Offset 25 may be delivered again
```

This is a normal recovery scenario for an at-least-once processing design. Your application should be prepared for it.

## 6. Delivery Semantics in Practice

### At-most-once

Progress may be committed before processing is complete. A crash can cause an event to be skipped from the application's perspective.

Use only when losing an event is acceptable under the system's requirements.

### At-least-once

The application processes a record and commits progress after successful processing. A crash before the commit may cause duplicate processing.

This is a common approach for backend event processing when consumer operations are idempotent.

### Exactly-once processing

Kafka transactions can coordinate certain Kafka reads, writes, and offsets. They are useful for pipelines in which consuming records and producing derived Kafka records must be handled transactionally.

They do not automatically include arbitrary database writes, HTTP calls, email sends, or payment-provider operations.

For external effects, design idempotency or a suitable cross-system consistency pattern.

# Layer 2 — Practical Engineering & Workflows

## 7. Spring Boot Kafka Dependencies

For a Maven-based Spring Boot application, use Spring Kafka through the Spring Boot dependency-management system.

Example dependency:

```xml
<dependency>
    <groupId>org.springframework.kafka</groupId>
    <artifactId>spring-kafka</artifactId>
</dependency>
```

Use a Spring Boot-managed version unless you have a deliberate reason to override it. Keep Spring Boot, Spring Kafka, and the Kafka client versions compatible.

## 8. Configure the Application

A development configuration might look like this:

```yaml
spring:
  kafka:
    bootstrap-servers: localhost:9092
    producer:
      key-serializer: org.apache.kafka.common.serialization.StringSerializer
      value-serializer: org.springframework.kafka.support.serializer.JsonSerializer
    consumer:
      group-id: inventory-service
      auto-offset-reset: earliest
      key-deserializer: org.apache.kafka.common.serialization.StringDeserializer
      value-deserializer: org.springframework.kafka.support.serializer.JsonDeserializer
      properties:
        "[spring.json.trusted.packages]": "com.example.events"
```

This example assumes your event class is in `com.example.events` and that your Spring Kafka version supports these property names and behaviors. Confirm the trusted-package and deserialization configuration against your selected version.

For production:

- Store credentials outside source control.
- Configure authentication and encryption where required.
- Review serializer/deserializer security behavior.
- Define consumer commit and error-handling policies.
- Set resource and timeout limits based on actual workload.

`auto-offset-reset: earliest` applies when a group has no valid committed offset or its committed offset is no longer available. It does not mean the consumer always starts from the beginning.

## 9. Define the Event Type

```java
package com.example.events;

import java.math.BigDecimal;

public record OrderCreatedEvent(
        String eventId,
        String orderId,
        String customerId,
        BigDecimal totalAmount
) {}
```

The event contains a stable identifier and business identifiers. A production event contract may also include a schema version, occurrence timestamp, trace context, and other fields required by the architecture.

Avoid placing internal secrets or unnecessary customer information in the event payload.

## 10. Implement a Producer

```java
package com.example.orders;

import com.example.events.OrderCreatedEvent;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;
import org.springframework.stereotype.Service;

import java.util.concurrent.CompletableFuture;

@Service
public class OrderEventPublisher {

    private final KafkaTemplate<String, OrderCreatedEvent> kafkaTemplate;

    public OrderEventPublisher(
            KafkaTemplate<String, OrderCreatedEvent> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    public CompletableFuture<SendResult<String, OrderCreatedEvent>> publish(
            OrderCreatedEvent event) {

        return kafkaTemplate.send(
                "orders",
                event.orderId(),
                event
        );
    }
}
```

### Why use `orderId` as the key?

Related events for the same order can be routed to the same partition under the configured partitioning strategy, helping preserve their relative order.

### What should the caller do?

The application must define how it reacts when publication fails.

For example, if the API responds with success after saving an order but event publication later fails, downstream systems may not learn about the order. If the API waits for publication, it still needs a clear failure policy and a solution for database/event consistency.

Do not hide publication failures with an empty exception handler.

## 11. Implement a Consumer

```java
package com.example.inventory;

import com.example.events.OrderCreatedEvent;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

@Component
public class InventoryConsumer {

    @KafkaListener(
            topics = "orders",
            groupId = "inventory-service"
    )
    public void handle(OrderCreatedEvent event) {
        System.out.println(
                "Received order: " + event.orderId()
        );

        // Production code should invoke an idempotent
        // inventory-processing service here.
    }
}
```

This is a learning example. Printing an event is not the same as successfully updating inventory.

A real consumer should delegate to a business service that validates the event, performs an appropriate transaction, records idempotency state where necessary, and handles failures.

### Consumer group design

Use a stable group ID for each logically independent processing application.

For example:

```text
inventory-service  -> updates stock
analytics-service  -> records metrics
email-service      -> schedules notifications
```

If three replicas belong to `inventory-service`, they can share work through one group. The analytics service should generally have its own group if it needs to process every retained event independently.

## 12. Make the Consumer Idempotent

Suppose an inventory consumer receives the same `OrderCreated` event twice. A naive implementation might reserve stock twice.

One strategy is to record processed event IDs in the same database transaction as the business update.

Illustrative relational design:

```sql
CREATE TABLE processed_events (
    event_id VARCHAR(100) PRIMARY KEY,
    processed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

Conceptual transaction:

```text
BEGIN DATABASE TRANSACTION

Attempt to insert eventId into processed_events.

If eventId already exists:
    Treat this event as already processed.
Else:
    Apply inventory change.

COMMIT DATABASE TRANSACTION
```

The uniqueness constraint prevents two concurrent attempts from both successfully claiming the same event ID.

The deduplication record and business change must be coordinated in the same database transaction. If they are committed independently, a crash can still produce inconsistent outcomes.

This example also needs suitable handling for uniqueness violations, transaction retries, retention of deduplication records, and the specific business semantics of inventory reservation.

## 13. Handle Failures Deliberately

A consumer can fail for several reasons:

- Invalid event schema.
- Temporary database outage.
- Permanent business validation failure.
- Downstream timeout.
- Unexpected application exception.

These failures should not all be handled identically.

| Failure | Possible strategy |
|---|---|
| Temporary dependency outage | Bounded retry with backoff |
| Invalid, unrecoverable payload | Record the failure and route to a dead-letter workflow |
| Duplicate event | Recognize it using idempotency state |
| Unexpected application bug | Preserve diagnostic context, alert, and avoid an infinite retry loop |
| Poison message | Isolate it so it does not indefinitely block useful progress |

A retry strategy must account for partition ordering. Blocking a partition while retrying one record can delay later records in that partition. Moving failed records to another topic may improve progress but can alter the effective processing order.

Spring Kafka provides listener error-handling mechanisms, including error handlers and dead-letter publishing facilities. Configure them according to your version and ordering requirements rather than copying an unverified configuration blindly.

## 14. Local Integration Workflow

Use the local Kafka environment from Chunk 1.

1. Start Kafka using Docker Compose.
2. Create the `orders` topic.
3. Configure Spring Boot to connect to `localhost:9092`.
4. Start the application.
5. Publish an `OrderCreatedEvent`.
6. Verify the consumer receives the event.
7. Stop and restart the consumer.
8. Inspect the consumer group's offsets.
9. Simulate a temporary processing failure.
10. Verify that the event is retried or handled according to your configured policy.
11. Send the same event ID twice.
12. Verify that your idempotency mechanism prevents duplicate business effects.

For a multi-container setup, `localhost` inside the Spring Boot container refers to that container itself. Use the Kafka service hostname and the correct internal listener when the application also runs inside Docker Compose.

## 15. Debugging Checklist

When the producer appears to send but the consumer receives nothing, inspect the system systematically.

**Producer**

- Can it reach a bootstrap broker?
- Are advertised broker addresses reachable from the application?
- Is serialization succeeding?
- Are sends failing, timing out, or being retried?
- Is the target topic correct?

**Topic and cluster**

- Does the topic exist?
- Are the partitions available?
- Is the broker healthy?
- Are the topic's replication and in-sync replica settings compatible with the acknowledgment requirement?

**Consumer**

- Is it subscribed to the correct topic?
- Is the expected consumer group being used?
- Are committed offsets already at the end of the log?
- Is the deserializer failing?
- Is the consumer repeatedly failing while processing a record?
- Is the listener running and assigned partitions?

**Networking**

- Is the bootstrap address reachable?
- Are all advertised broker addresses reachable from the consumer?
- Is the client using the correct listener for its network location?
- Are authentication and TLS settings aligned?

---

# Layer 3 — Production Engineering & Interview Mastery

## 16. Producer Reliability Tradeoffs

A producer configuration should match the business requirement.

For an important order event, a team may choose idempotent production, stronger acknowledgments, retries, and a carefully designed replication policy.

But configuration alone is not enough.

The application must also define what happens when:

- The send times out but the broker may have accepted the record.
- The application receives the same HTTP request twice.
- PostgreSQL commits but Kafka publication fails.
- Kafka publication succeeds but the HTTP response is lost.
- The caller retries after an ambiguous outcome.

These are distributed-systems failure modes, not merely Kafka configuration issues.

## 17. The Database–Kafka Dual-Write Problem

Consider:

```text
BEGIN
  Insert order into PostgreSQL
COMMIT

Publish OrderCreated to Kafka
```

If the database commit succeeds but Kafka publication fails, the database and event stream disagree.

Now reverse the order:

```text
Publish OrderCreated to Kafka

Insert order into PostgreSQL
```

If publication succeeds but the database transaction fails, consumers can observe an order that does not exist in the database.

### Transactional outbox: the next architectural step

A common solution is the transactional outbox:

1. Save the business record in PostgreSQL.
2. Save an outbox event in the same database transaction.
3. A separate publisher reads unpublished outbox records.
4. The publisher sends events to Kafka.
5. Published records are marked or tracked for recovery.

Because the business record and outbox entry are written in one database transaction, the application avoids the original atomicity gap between those two writes.

The publisher can still send an event more than once if it crashes after publication but before recording success. Consumers must remain idempotent, or the publisher and downstream workflow must use an appropriate transactional design.

The outbox solves an important dual-write problem; it does not magically provide one global transaction across all services.

## 18. Consumer Rebalancing

A consumer group may rebalance when:

- A consumer joins.
- A consumer leaves or crashes.
- Subscription changes.
- Partition assignments need to be recalculated.

During a rebalance, partition ownership changes. Applications should handle revoked and assigned partitions correctly and avoid assuming that a consumer owns a partition forever.

Production implications:

- Long-running processing can delay progress.
- Poor shutdown handling can increase recovery time.
- Incorrect offset management can cause duplicate or skipped processing.
- Excessive membership changes can create repeated rebalances.

Useful operational signals include group membership changes, assignment changes, processing latency, lag, and repeated failures.

## 19. Security and Configuration Hygiene

For production deployments:

- Enable appropriate TLS and authentication.
- Use Kafka ACLs or equivalent authorization controls.
- Give applications only the permissions they need.
- Avoid committing credentials to source control.
- Restrict access to topics containing sensitive data.
- Review deserialization behavior and schema evolution.
- Monitor rejected requests and authentication failures.
- Separate development and production credentials and environments.

JSON deserialization of untrusted data should be configured carefully. Trusted-package settings are not a replacement for schema validation or authorization.

## 20. Production Incident Scenarios

### Incident A: Producer latency increases

Investigate:

1. Producer send latency and error rate.
2. Broker request latency and resource saturation.
3. Network connectivity and DNS.
4. Batch size, compression, and `linger.ms`.
5. Retry rates and timeout configuration.
6. Replication health and in-sync replicas.

Do not immediately increase timeouts without determining why requests are slow.

### Incident B: Consumer duplicates business operations

Investigate:

1. Whether duplicate event IDs are present.
2. Whether the consumer crashed after the business transaction but before offset commit.
3. Whether upstream producers intentionally or accidentally emitted duplicate logical events.
4. Whether retry behavior replays an operation.
5. Whether the business operation and deduplication record share a transaction.

Then fix the idempotency boundary and test the crash window.

### Incident C: Consumer appears healthy but lag grows

Investigate:

- Incoming record rate versus processing rate.
- Processing time per event.
- Slow SQL or remote calls.
- Partition imbalance.
- Retry frequency.
- Consumer-group membership and assignments.

A running process is not proof that the consumer is making useful progress.

### Incident D: One event blocks a partition

Investigate whether a poison message repeatedly fails. Determine whether it can be retried safely, isolated, or moved through a dead-letter workflow. Preserve the original payload, event identifiers, failure reason, and diagnostic context while avoiding sensitive-data exposure.

If strict per-key ordering matters, define how processing resumes after the failed event. Skipping it may violate business invariants.

## 21. Interview Questions and Answers

### Q1. What does `acks=all` mean?

The leader waits for acknowledgment from the required in-sync replicas according to the cluster configuration. It does not universally mean every configured replica must acknowledge.

### Q2. What is producer idempotence?

A Kafka producer feature that prevents certain duplicate writes caused by producer retries within its protocol guarantees. It does not prevent all duplicate business events.

### Q3. What does a serializer do?

It converts an application's key or value into bytes for Kafka. A deserializer converts bytes back into application data.

### Q4. Why is schema compatibility important?

Producers and consumers can be deployed independently. Incompatible changes can cause old consumers or new consumers to fail when reading events.

### Q5. What is the difference between current position and committed offset?

The current position reflects where the consumer is reading. The committed offset is saved progress used for recovery.

### Q6. Why can a consumer process a record twice?

It may finish the business operation and crash before committing progress. The record can then be delivered again.

### Q7. Why is committing before processing risky?

A crash after the commit but before the business operation completes can cause the operation to be skipped on recovery.

### Q8. Does manual offset committing guarantee exactly-once processing?

No. Manual commits provide control over progress timing, but external side effects can still be repeated or skipped unless the design handles failure windows.

### Q9. How do you prevent duplicate database updates?

Use idempotent business logic and an appropriate deduplication mechanism, often enforced by a database uniqueness constraint in the same transaction as the business update.

### Q10. What is a poison message?

A record that repeatedly fails processing, potentially preventing progress on its partition unless the application handles it.

### Q11. What is a dead-letter topic?

A topic used to retain records that cannot be processed through the normal workflow, together with useful diagnostic context where appropriate.

### Q12. What is a consumer rebalance?

A reassignment of topic partitions among members of a consumer group.

### Q13. What does `auto-offset-reset=earliest` do?

It defines where to begin when the group has no valid committed offset. It does not override an existing valid committed offset.

### Q14. What is the transactional outbox pattern?

A pattern in which the application writes business state and an outbox event in the same database transaction, then publishes the outbox event asynchronously.

### Q15. Does a transactional outbox eliminate duplicates?

No. Publication can be repeated after a crash. Consumers should be idempotent or use an appropriate deduplication strategy.

### Q16. Why might producer sends time out even if the record reached Kafka?

A response can be lost or delayed after the broker accepts a record. The producer may not know whether the write succeeded, which is why retry behavior and idempotence matter.

### Q17. What is the difference between producer idempotence and a consumer inbox?

Producer idempotence addresses certain duplicate writes from producer retries. A consumer inbox or deduplication table records processed business event IDs to prevent repeated business effects.

### Q18. How do you troubleshoot a consumer receiving no records?

Check connectivity, advertised listeners, topic subscription, group offsets, partition assignment, deserialization failures, and whether records are actually being produced.

### Q19. Why can adding consumers fail to reduce lag?

The topic may not have enough partitions, the workload may be uneven, or a downstream dependency may be the bottleneck.

### Q20. What does Kafka exactly-once semantics not automatically solve?

It does not automatically make arbitrary external database transactions, HTTP requests, payments, or emails exactly once.

## 22. Hands-On Assessment

Complete the following against your local Spring Boot project:

- [ ] Configure `KafkaTemplate` with a JSON serializer.
- [ ] Publish an `OrderCreatedEvent` using `orderId` as the key.
- [ ] Create a consumer using `@KafkaListener`.
- [ ] Run two instances in the same consumer group and observe partition assignment.
- [ ] Explain what happens when the group has fewer consumers than partitions.
- [ ] Explain what happens when the group has more consumers than partitions.
- [ ] Simulate a consumer crash before offset commit.
- [ ] Simulate a duplicate event ID.
- [ ] Implement an idempotency mechanism backed by PostgreSQL.
- [ ] Explain the difference between a producer acknowledgment and successful downstream processing.
- [ ] Draw the failure window between committing an order and publishing its event.
- [ ] Explain how a transactional outbox closes that particular dual-write gap.
- [ ] Explain why the outbox publisher and consumers must still account for retries.

## 23. Chunk Completion Checklist

You have mastered Chunk 2 when you can:

- [ ] Explain producer acknowledgment and idempotence.
- [ ] Choose appropriate serialization and schema-evolution practices.
- [ ] Configure a basic Spring Boot producer and consumer.
- [ ] Explain current position, committed offset, and lag.
- [ ] Reason about crashes before and after offset commits.
- [ ] Build an idempotent consumer.
- [ ] Explain consumer-group rebalancing.
- [ ] Design bounded retries and dead-letter handling.
- [ ] Diagnose common producer and consumer failures.
- [ ] Explain why the transactional outbox is useful.
- [ ] Distinguish Kafka-level guarantees from business-level guarantees.

---

## Next: Kafka Chunk 3 — Production Reliability, Security, Performance & Incident Mastery

The final Kafka chapter will cover deeper production architecture, partition strategy, replication and durability, throughput tuning, lag diagnosis, consumer scaling, retries and dead-letter workflows, observability, security, failure simulations, and advanced interview scenarios.

**Repository rule:** Save this chapter as `content/kafka/02-kafka-producers-consumers-spring-boot-integration.md`. Do not generate a chunk PDF. The final Kafka PDF is created only after all three Kafka chapters have been saved and verified.
