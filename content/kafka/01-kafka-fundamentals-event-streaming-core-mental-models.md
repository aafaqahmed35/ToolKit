# Kafka — Chunk 1: Fundamentals, Event Streaming & Core Mental Models

**Backend Engineering Tools & Infrastructure Handbook (BEH)**

**Source file:** `content/kafka/01-kafka-fundamentals-event-streaming-core-mental-models.md`

---

# 1. Learning Objectives

By the end of this chapter, you should be able to:

- Explain why Kafka exists and which problems it solves.
- Understand producers, brokers, topics, partitions, offsets, and consumers.
- Explain how Kafka differs from traditional message queues and Redis.
- Understand consumer groups and how Kafka distributes work.
- Create a local Kafka environment and perform basic operations.
- Recognize delivery semantics and common messaging mistakes.
- Explain Kafka's role in a production backend architecture.
- Answer foundational Kafka interview questions confidently.

This chapter begins the Kafka curriculum. Across all three planned Kafka chunks, we will cover fundamentals, practical engineering workflows, and production engineering mastery.

# Layer 1 — Fundamentals & Mental Models

## 2. What Is Apache Kafka?

Apache Kafka is a **distributed event-streaming platform** used to publish, store, and consume streams of events.

Imagine an e-commerce application. When a customer places an order, several things may need to happen:

1. The order must be saved.
2. Inventory must be updated.
3. A confirmation email must be sent.
4. An analytics system must record the purchase.
5. A fraud-detection system may need to evaluate the transaction.

A naive implementation calls every downstream service directly from the order API.

```text
Customer
   |
   v
Order API
   |
   +----> Inventory Service
   |
   +----> Email Service
   |
   +----> Analytics Service
   |
   +----> Fraud Service
```

This creates coupling. If the email service is slow or unavailable, it can delay the order request. Adding more downstream services also makes the order API increasingly complicated.

Kafka introduces an event stream between producers and consumers.

```text
                    +------------------+
                    |    Order API     |
                    +--------+---------+
                             |
                       Publish event
                             |
                             v
                    +------------------+
                    |      Kafka       |
                    |  orders topic    |
                    +---+----+----+----+
                        |    |    |
                 +------+    |    +---------+
                 v           v              v
          Inventory       Email          Analytics
          Consumer       Consumer         Consumer
```

The order service publishes an event such as `OrderCreated`. Independent consumers process that event for their own purposes.

Kafka does not automatically make every downstream operation succeed. It provides a durable, distributed event log that helps services communicate asynchronously and independently.

### The central mental model

**Kafka is a distributed, replayable log of events.**

This is more useful than thinking of Kafka as merely a pipe that moves messages from A to B.

A consumer can read events, track its position, and potentially read them again when it needs to recover or rebuild state, provided the events remain available under the configured retention policy.

## 3. What Is an Event?

An event records something that has happened.

Examples:

- `OrderCreated`
- `PaymentAuthorized`
- `InventoryReserved`
- `UserRegistered`
- `ShipmentDispatched`

A simplified event might look like this:

```json
{
  "eventId": "evt-1001",
  "eventType": "OrderCreated",
  "orderId": "ord-782",
  "customerId": "cust-45",
  "totalAmount": 1499.00,
  "currency": "INR",
  "occurredAt": "2026-10-23T08:30:00Z"
}
```

This is an illustrative event payload, not a Kafka-specific wire format.

Useful event-design principles:

- Give events a clear name describing something that happened.
- Include identifiers needed by consumers.
- Include an event ID when consumers need to detect duplicate processing.
- Use a consistent timestamp and schema strategy.
- Avoid putting secrets or unnecessary personal information into events.
- Consider backward compatibility when changing event schemas.

### Commands versus events

A command requests an action. An event records a fact.

| Command | Event |
|---|---|
| `CreateOrder` | `OrderCreated` |
| `ChargePayment` | `PaymentCharged` |
| `ReserveInventory` | `InventoryReserved` |

A command can be rejected. An event normally describes a fact that has already occurred.

For example, `ChargePayment` asks a payment service to charge a customer. `PaymentCharged` states that the charge succeeded.

This distinction matters when designing event-driven systems.

## 4. Kafka's Core Components

### Producer

A **producer** publishes records to Kafka.

A producer may be an order service, payment service, background worker, or any other application that emits events.

A Kafka record can contain:

- A key
- A value
- A timestamp
- Headers
- Other record metadata

Example:

```text
Key:   order-782
Value: OrderCreated event
Topic: orders
```

The key can influence partition selection. It is not simply decorative metadata.

### Broker

A **broker** is a Kafka server that stores and serves topic partitions.

A Kafka cluster typically contains multiple brokers. Partitions can be distributed among them so the cluster can scale and tolerate certain failures.

A broker is not the same as a topic, partition, or consumer.

### Topic

A **topic** is a named stream of records.

Examples:

```text
orders
payments
inventory-events
notifications
```

Topics organize events by domain or purpose.

A topic is divided into partitions. It is not necessarily stored entirely on one broker.

### Partition

A **partition** is an ordered, append-only log within a topic.

Imagine the `orders` topic has three partitions:

```text
orders
  |
  +-- Partition 0: [E0] [E1] [E2] [E3]
  |
  +-- Partition 1: [E0] [E1] [E2]
  |
  +-- Partition 2: [E0] [E1] [E2] [E3] [E4]
```

The offsets shown inside different partitions are local to those partitions. They do not represent one global topic-wide sequence.

Kafka guarantees ordering **within a partition**, not across all partitions of a topic.

Partitioning is a major part of Kafka's scalability model. Different partitions can be processed concurrently, subject to consumer-group assignments and other constraints.

### Offset

An **offset** is the position of a record within a partition.

For example:

```text
Partition 0:
Offset 0 -> OrderCreated
Offset 1 -> OrderCreated
Offset 2 -> OrderCancelled
Offset 3 -> OrderCreated
```

A consumer tracks its progress through a partition using offsets.

Offsets are not globally unique across an entire topic. The meaningful record location is the combination of topic, partition, and offset.

Example:

```text
orders / partition 0 / offset 42
```

A consumer can resume reading from a position after a restart if its progress has been committed and the required records remain available.

### Consumer

A **consumer** reads records from Kafka and performs application work.

Examples:

- An inventory consumer updates stock.
- An email consumer schedules a confirmation.
- An analytics consumer aggregates sales.
- A fraud consumer evaluates suspicious activity.

Kafka does not automatically execute the business logic in your consumer. Your application must process the record, handle errors, and manage progress appropriately.

### Consumer group

A **consumer group** is a set of consumers that cooperatively process a topic's partitions.

Within one consumer group, a partition is assigned to at most one consumer at a time under the normal group-assignment model.

Suppose a topic has four partitions.

```text
Topic: orders

P0 ─────> Consumer A
P1 ─────> Consumer B
P2 ─────> Consumer C
P3 ─────> Consumer D
```

If the group has only two consumers, each may receive multiple partitions.

If the group has six consumers but only four partitions, at least two consumers will have no partition assigned for that topic at that time.

**Key rule:** For a single topic, adding consumers to one group beyond the number of partitions does not increase the number of consumers that can concurrently own those partitions.

## 5. How a Kafka Record Travels

Consider a customer placing an order.

1. The Order API constructs an `OrderCreated` record.
2. The producer sends it to the `orders` topic.
3. Kafka routes it to a partition.
4. The broker appends the record to that partition's log.
5. A consumer in a subscribed group fetches the record.
6. The consumer executes its business logic.
7. The consumer commits progress according to its processing strategy.

```text
Application
    |
    v
Producer
    |
    v
Topic / Partition
    |
    v
Broker appends record
    |
    v
Consumer fetches record
    |
    v
Business processing
    |
    v
Offset progress committed
```

The last two steps are particularly important. **Reading a record and successfully completing its business operation are not the same thing.**

If a consumer commits its offset before completing the operation, a crash may cause the operation to be skipped after recovery. If it commits only after processing, a crash between the operation and the commit can cause the record to be processed again.

That is why Kafka consumers must be designed around retries, idempotency, and correct progress management.

## 6. Kafka's Ordering Model

Kafka's ordering guarantees are scoped to partitions.

Suppose order events use `orderId` as the key:

```text
Order 100 -> partition 1
Order 100 -> partition 1
Order 100 -> partition 1

Order 200 -> partition 2
Order 200 -> partition 2
```

With a stable partitioning strategy and unchanged topic partitioning assumptions, records with the same key are generally routed to the same partition. That helps preserve their relative order.

However, do not treat this as an unconditional guarantee across all configurations or future partition-count changes. Partitioning strategies, custom partitioners, and changing the number of partitions can affect placement.

### When ordering matters

Ordering is important when events describe a sequence of state transitions.

For example:

```text
AccountOpened
FundsDeposited
FundsWithdrawn
AccountClosed
```

Processing these events out of order may produce incorrect results.

For a backend system, ask:

- What entity needs ordered processing?
- What key represents that entity?
- Can two records for the same entity be processed concurrently?
- What happens when a record fails?
- Is global ordering actually necessary?

Global ordering across a highly parallel topic is expensive and should not be assumed by default.

## 7. Kafka Versus Traditional Message Queues

Kafka and traditional queues can both support asynchronous communication, but their typical models differ.

| Dimension | Kafka | Traditional work queue |
|---|---|---|
| Core model | Distributed event log | Messages delivered to workers |
| Consumption | Consumers track positions | Messages often acknowledged and removed from active delivery |
| Replay | Supported while records remain available | Depends on the queue and its configuration |
| Multiple independent consumers | Consumer groups can independently read a topic | Usually requires separate queues or fan-out configuration |
| Ordering | Per partition | Depends on queue type and delivery configuration |
| Scaling | Partitions and consumer groups | Queue and worker scaling mechanisms |

These are general patterns, not universal rules. Modern queue systems offer features that overlap with Kafka, and Kafka's behavior depends on its configuration and application design.

### Example: background email

If a user registers and the system needs to send one welcome email, a conventional task queue may be sufficient.

### Example: order events shared by multiple services

If inventory, analytics, fraud detection, and reporting all need to consume order events independently, Kafka can be a natural fit because each consumer group can track its own progress.

Choose based on the delivery and replay requirements, operational complexity, ordering needs, and throughput—not on popularity alone.

## 8. Kafka Versus Redis

Kafka and Redis solve different primary problems, even though both can appear in distributed backend architectures.

| Dimension | Kafka | Redis |
|---|---|---|
| Primary role | Distributed event streaming and durable log | In-memory data platform, often used for caching and fast data access |
| Typical data model | Ordered records within partitions | Keys, values, collections, and specialized structures |
| Common use | Event pipelines, asynchronous integration, replay | Caching, sessions, rate limiting, coordination |
| Replay | Read records again while retained | Depends on the Redis feature and data-retention design |
| Work distribution | Consumer groups and partition assignments | Depends on the mechanism used, such as Streams or other structures |
| Latency profile | Optimized for high-throughput event streaming | Often extremely low-latency access to in-memory data |

Redis also supports Streams and consumer groups. It is therefore incorrect to claim Redis cannot perform stream processing or asynchronous messaging.

The real distinction is the required system behavior. Kafka is built around a distributed event log and partitioned streaming. Redis is a broader in-memory data platform frequently used for fast access, caching, and lightweight coordination.

### Practical architecture

```text
Order API
   |
   +----> PostgreSQL: durable business state
   |
   +----> Kafka: order events for downstream consumers
   |
   +----> Redis: cache frequently accessed data
```

This is a conceptual architecture, not a complete transaction-safe implementation. Writing to PostgreSQL and publishing to Kafka introduces a dual-write problem, which we will address in later engineering work.

## 9. Retention: Why Kafka Is Not Just a Queue

Kafka commonly retains records according to a configured retention policy.

A consumer reading a record does not ordinarily delete that record for every other consumer. Multiple consumer groups can read the same retained data independently.

For example:

```text
orders topic
  |
  +----> inventory-group
  |
  +----> analytics-group
  |
  +----> fraud-group
```

All three groups can read the same stream independently and maintain their own positions.

Retention can be time-based, size-based, or configured using other topic policies. A record is not guaranteed to remain available forever. Compaction can also change which historical records are retained for compacted topics.

This gives Kafka two important characteristics:

- **Decoupling:** producers do not need to know every downstream consumer.
- **Replay:** consumers can reread retained records when appropriate.

Replay is useful for rebuilding projections, backfilling analytics, and recovering consumer state. It must be designed carefully when replayed events trigger external side effects such as sending emails or charging payments.

## 10. Delivery Semantics: The First Mental Model

Three terms appear frequently in Kafka discussions.

### At-most-once

A record may be lost from the application's processing perspective, but duplicate processing is avoided by the chosen strategy.

One way this can happen is when progress is committed before business processing. If the application crashes after committing but before completing the operation, the record may be skipped after restart.

### At-least-once

A record is processed one or more times. Duplicates are possible.

A common approach is to process the record and commit the offset after successful processing. If the operation succeeds but the application crashes before the offset commit, the record can be delivered again.

### Exactly-once

Exactly-once semantics require careful definition of what is guaranteed and within which boundary.

Kafka provides transactional and idempotent-producer capabilities for specific Kafka operations. However, exactly-once effects across Kafka, PostgreSQL, payment providers, email systems, and arbitrary external services do not arise automatically.

A common production approach is:

1. Expect duplicate delivery where appropriate.
2. Give events stable IDs.
3. Make consumer-side state changes idempotent.
4. Use database constraints or deduplication records where appropriate.
5. Commit offsets in coordination with the processing design.
6. Use Kafka transactions or an outbox/inbox pattern when the problem calls for them.

We will explore reliability and transactional boundaries in the later Kafka chunks.

# Layer 2 — Practical Engineering & Workflows

## 11. Set Up Kafka Locally

For learning, run Kafka locally using Docker. A single-node development setup is useful for experimenting, but it does not demonstrate production fault tolerance.

Use a Kafka image and configuration compatible with the official Kafka distribution you choose. The following Compose example uses a KRaft-based single-node configuration, which does not require a separate ZooKeeper service.

Create a `compose.yaml` file:

```yaml
services:
  kafka:
    image: apache/kafka:4.1.0
    hostname: kafka
    container_name: kafka
    ports:
      - "9092:9092"
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0
```

Start Kafka:

```bash
docker compose up -d
docker compose ps
docker compose logs -f kafka
```

**Important:** This configuration is for local development. It uses plaintext communication, a single broker, and replication factors of one. Do not treat it as a production security or availability configuration.

If your chosen image version or distribution uses different environment-variable conventions, follow that image's documentation rather than mixing configuration formats.

## 12. Create a Topic

Run Kafka's topic tool inside the container:

```bash
docker exec kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --create \
  --topic orders \
  --partitions 3 \
  --replication-factor 1
```

List topics:

```bash
docker exec kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --list
```

Describe the topic:

```bash
docker exec kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --describe \
  --topic orders
```

The description helps you inspect the partition count and replica assignment.

A single broker can only host one replica of each partition in this example, so a replication factor greater than one cannot be satisfied.

## 13. Produce Your First Events

Start the console producer:

```bash
docker exec -it kafka /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server localhost:9092 \
  --topic orders
```

Type a few lines:

```json
{"eventId":"evt-1","eventType":"OrderCreated","orderId":"ord-100"}
{"eventId":"evt-2","eventType":"OrderCreated","orderId":"ord-101"}
{"eventId":"evt-3","eventType":"OrderCancelled","orderId":"ord-100"}
```

Each line is a separate record value.

In this simple console example, the producer does not automatically parse the JSON into structured fields. Kafka sees the record value as bytes; JSON interpretation is the application's responsibility.

Exit the producer with `Ctrl+C`.

## 14. Consume Your Events

Run a console consumer from the beginning of the retained stream:

```bash
docker exec -it kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic orders \
  --from-beginning
```

You should see the records you produced.

Now start a second consumer in a different terminal. It can also read the retained events. This illustrates that a consumer reading records does not normally remove them from the topic.

Stop both consumers with `Ctrl+C`.

### Inspect consumer groups

Run a consumer with a group ID:

```bash
docker exec -it kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic orders \
  --group order-debug-group
```

After consuming some events, inspect the group:

```bash
docker exec kafka /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --list
```

Describe it:

```bash
docker exec kafka /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe \
  --group order-debug-group
```

Look at:

- Current offset
- Log-end offset
- Consumer lag
- Partition assignment, where shown by the tool

Consumer lag is a useful signal of how far behind a consumer group is from the end of the log. It does not, by itself, prove that the application is unhealthy. Interpret it alongside incoming throughput, processing latency, error rate, and business impact.

## 15. A Backend Example: Publishing an Order Event

Suppose you have a Spring Boot order service.

A simplified design might use a producer service:

```java
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

Illustrative event type:

```java
public record OrderCreatedEvent(
        String eventId,
        String orderId,
        String customerId,
        BigDecimal totalAmount
) {}
```

Imports and configuration are omitted here. In a real Spring Boot application, configure the Kafka producer, JSON serialization, topic settings, and error handling for the versions you use.

### Why use `orderId` as the key?

```java
kafkaTemplate.send("orders", event.orderId(), event);
```

The key gives Kafka a way to choose a partition consistently under the configured partitioner. That can help preserve order for events belonging to the same order.

It does not guarantee that all orders are processed sequentially. Different orders can be processed concurrently.

### What does the future mean?

The returned future allows the application to observe the result of the send operation. A successful producer send means Kafka acknowledged the record according to the configured producer and broker settings. It does **not** mean every downstream consumer has completed its work.

Avoid swallowing send failures. Handle them according to the API's business contract and the chosen reliability design.

### The dual-write warning

Consider this implementation:

```text
1. Save order in PostgreSQL.
2. Publish OrderCreated to Kafka.
```

What if step 1 succeeds but step 2 fails?

The order exists in the database, but downstream consumers may never hear about it.

Reversing the order introduces a different inconsistency: the event could be published even if the database transaction fails.

Do not assume two independent operations become atomic merely because they occur in the same method. Later engineering work will cover the transactional outbox pattern and related approaches.

## 16. Build a Consumer Responsibly

A consumer should not simply print a message and assume processing is complete.

For an order-processing consumer, define:

- What constitutes successful processing?
- Which failures should be retried?
- Which failures are permanent?
- When is offset progress committed?
- How are duplicate events handled?
- How is processing observed?
- What happens during shutdown or a rebalance?

A conceptual processing flow:

```text
Receive record
    |
    v
Validate event
    |
    +---- Invalid permanently?
    |          |
    |          v
    |    Record failure / DLQ strategy
    |
    v
Perform idempotent business operation
    |
    +---- Temporary failure?
    |          |
    |          v
    |       Retry strategy
    |
    v
Commit progress according to the chosen strategy
```

This is a design outline, not a complete consumer implementation. Retrying synchronously can block a partition; retry topics, dead-letter topics, and pause/resume mechanisms have different ordering and operational tradeoffs.

## 17. Common Kafka Mistakes

### Mistake 1: Treating offsets as global

Offset 10 in partition 0 is not the same record position as offset 10 in partition 1.

### Mistake 2: Adding consumers without checking partition count

More consumers in one group do not guarantee more parallelism when the number of partitions is fixed.

### Mistake 3: Assuming successful publication means successful processing

A producer acknowledgment and a consumer's business completion are different events.

### Mistake 4: Assuming records disappear after consumption

Kafka generally retains records according to topic policy, not according to whether a particular consumer has read them.

### Mistake 5: Assuming exactly-once behavior across every system

Kafka's transactional capabilities do not automatically make an external PostgreSQL transaction or payment request part of the same atomic operation.

### Mistake 6: Using the wrong event key

If related events need ordering, an unsuitable key or partitioning strategy can undermine the intended processing model.

### Mistake 7: Using a single local broker to claim high availability

A one-broker development setup cannot demonstrate broker redundancy or tolerate the loss of that broker.

# Layer 3 — Production Engineering & Interview Mastery

## 18. Production Mental Models

Before operating Kafka in production, understand these relationships:

**Throughput versus ordering:** More partitions can enable more parallelism, but partition design and ordering requirements must be considered together.

**Durability versus latency:** Producer acknowledgments, replication, and in-sync replica settings affect the durability and availability tradeoffs. The word “Kafka” alone does not guarantee a particular durability level.

**Delivery versus business effects:** Kafka can redeliver records. Consumer operations must handle duplicates when the chosen processing model permits them.

**Retention versus replay:** Replay is possible only while the needed records remain available and compatible with the consumer's logic.

**Consumer lag versus business health:** Lag can indicate insufficient processing capacity, a stalled consumer, or a sudden increase in input volume. The number alone does not identify the root cause.

## 19. Foundational Incident Scenarios

### Scenario A: Consumer lag keeps increasing

Potential causes:

- Incoming records are arriving faster than the consumer can process them.
- A consumer is stuck on slow database calls.
- The group has fewer effective consumers than expected.
- Errors or retries are consuming processing time.
- A partition is disproportionately hot.

Initial investigation:

1. Inspect consumer-group lag and per-partition distribution.
2. Compare input throughput with processing throughput.
3. Check application errors and processing latency.
4. Inspect downstream dependencies such as PostgreSQL or HTTP APIs.
5. Check partition assignments and recent rebalances.
6. Scale or optimize only after identifying the bottleneck.

Adding consumers may not help if the topic has too few partitions or the downstream database is already saturated.

### Scenario B: Duplicate order processing

Potential causes:

- A consumer processed a record but crashed before committing its offset.
- The producer emitted the same logical event more than once.
- The application retried an operation after an ambiguous timeout.
- A replay intentionally reprocessed retained events.

Response:

1. Identify the stable event or business-operation ID.
2. Inspect the consumer's offset-commit strategy.
3. Make the business operation idempotent.
4. Consider database uniqueness constraints or an inbox/deduplication table.
5. Test crashes between business processing and offset commits.

Do not treat every duplicate as a Kafka defect. Duplicates can arise from normal retry and recovery behavior.

### Scenario C: Events arrive in an unexpected order

Investigate:

- Whether the records use the intended key.
- Whether the relevant records are in the same partition.
- Whether the application processes records concurrently.
- Whether retry or dead-letter workflows reorder the effective business operations.
- Whether partition-count or partitioner changes affected placement.

Kafka's per-partition order cannot repair application-level reordering that occurs after records have been fetched.

### Scenario D: Producer sends fail

Investigate:

- Broker connectivity and advertised listener configuration.
- Authentication and authorization, if enabled.
- Topic existence and metadata.
- Broker health and resource saturation.
- Serialization errors.
- Request timeouts and retry configuration.
- Replication and acknowledgment requirements.

A connection failure in a local Docker setup may be caused by using `localhost` from inside another container. Container-to-container clients typically need the Kafka service's network hostname and an advertised listener appropriate to that network.

## 20. Kafka Interview Questions and Answers

### Q1. What is Kafka?

Kafka is a distributed event-streaming platform that stores records in partitioned logs and allows independent consumers to process those records.

### Q2. What is a topic?

A named stream of records divided into partitions.

### Q3. What is a partition?

An ordered log within a topic. Partitions allow data distribution and parallel processing.

### Q4. What is an offset?

A record's position within a particular partition. It is not globally unique across a topic.

### Q5. What is a broker?

A Kafka server that stores and serves partitions.

### Q6. What is a consumer group?

A group of consumers that cooperatively process assigned partitions. Different groups can independently consume the same topic.

### Q7. Can two consumers in the same group process the same partition simultaneously?

Under the normal consumer-group assignment model, a partition is assigned to at most one group member at a time. Application-level concurrency can still affect the ordering of completed work.

### Q8. What happens when a group has more consumers than partitions?

Some consumers remain without an assignment for that topic until assignments or membership change.

### Q9. Does Kafka guarantee ordering?

Ordering is guaranteed within a partition, not globally across all partitions.

### Q10. Why use a record key?

A key can influence partition selection and help keep related records in the same partition for ordered processing.

### Q11. What is consumer lag?

A measure of how far a consumer group is behind the end of the log. Its exact interpretation depends on offsets and the monitoring method.

### Q12. Does consuming a Kafka record delete it?

No, not ordinarily. Kafka retains records according to topic policies, independently of a particular consumer reading them.

### Q13. What is the difference between Kafka and Redis?

Kafka focuses on distributed event streaming and partitioned logs. Redis is an in-memory data platform used for caching, fast data access, and other structures, including Streams. The right choice depends on the workload and required guarantees.

### Q14. What is at-least-once processing?

A processing model in which a record may be processed more than once, so duplicates must be handled where they matter.

### Q15. Does Kafka automatically guarantee exactly-once business operations?

No. Kafka offers transactional and idempotent features within specific boundaries, but external side effects require their own transactional or idempotency design.

### Q16. Why can consumer lag increase?

Processing throughput may be lower than incoming throughput, a consumer may be stalled, retries may be excessive, or workload may be unevenly distributed.

### Q17. What happens if a consumer crashes?

The group can reassign its partitions to remaining or replacement consumers. Records may be processed again depending on the committed offsets and processing strategy.

### Q18. Why is a single-broker local setup insufficient for high availability?

There is no redundant broker to take over the lost broker's partition replicas. A local setup is useful for learning, not proof of production resilience.

### Q19. Why is writing to a database and publishing to Kafka tricky?

The operations are usually not one atomic transaction. One can succeed while the other fails. Patterns such as transactional outbox and inbox/deduplication address different sides of this problem.

### Q20. When should you not introduce Kafka?

Avoid it when the problem does not justify the operational and architectural complexity. A direct call, a database-backed job table, or a simpler queue may be more appropriate for a small workload or straightforward background task.

## 21. Hands-On Mastery Lab

Complete these tasks against your local Kafka environment.

- [ ] Start Kafka and verify the container is healthy.
- [ ] Create an `orders` topic with three partitions.
- [ ] Describe the topic and identify its partitions.
- [ ] Produce at least five sample order events.
- [ ] Consume the events from the beginning.
- [ ] Start a second independent consumer without sharing the same group ID.
- [ ] Run a consumer using a named group.
- [ ] Inspect the consumer group's offsets and lag.
- [ ] Explain why offset 2 in one partition is unrelated to offset 2 in another partition.
- [ ] Explain what happens when you add more consumers than the topic has partitions.
- [ ] Explain how using `orderId` as a key helps with ordering.
- [ ] Describe how a consumer crash could cause duplicate processing.
- [ ] Explain why a successful producer acknowledgment does not prove the inventory update succeeded.
- [ ] Identify one case where Redis would be a better fit and one case where Kafka would be a better fit.

### Mastery challenge

Design a simple order-event architecture with:

- An Order API
- PostgreSQL
- A Kafka `orders` topic
- An inventory consumer
- An analytics consumer
- A Redis cache

Write down:

1. Which component owns the authoritative order state.
2. Which event is published when an order is created.
3. Which key should be used if order-level ordering is required.
4. How each consumer tracks progress.
5. What happens if the inventory consumer crashes after updating the database but before committing its offset.
6. How duplicate inventory updates can be prevented.
7. What the system should do if PostgreSQL saves the order but event publication fails.

Do not skip the final two questions. They are the bridge from Kafka fundamentals to real production engineering.

## 22. Chunk Completion Checklist

You have completed Kafka Chunk 1 when you can explain the following without memorizing definitions:

- [ ] Kafka as a distributed event log.
- [ ] Producer, broker, topic, partition, offset, and consumer.
- [ ] Consumer groups and partition assignment.
- [ ] Per-partition ordering.
- [ ] Retention and replay.
- [ ] Kafka versus traditional queues and Redis.
- [ ] At-most-once, at-least-once, and the boundaries of exactly-once processing.
- [ ] Basic local topic, producer, consumer, and consumer-group workflows.
- [ ] Why idempotency matters.
- [ ] Why database-plus-Kafka dual writes are difficult.
- [ ] How to start investigating consumer lag and duplicate processing.

---

## Next: Kafka Chunk 2 — Producers, Consumers, Delivery Semantics & Spring Boot Integration

The next chapter will move from the mental model to implementation: producer configuration, consumer configuration, serialization, acknowledgment behavior, retries, offset commits, consumer groups, Spring Boot integration, and hands-on backend workflows.

**Repository rule:** Save this chapter as `content/kafka/01-kafka-fundamentals-event-streaming-core-mental-models.md`. Do not generate a chunk PDF. The final Kafka PDF is created only after all three Kafka chunks have been saved and verified.
