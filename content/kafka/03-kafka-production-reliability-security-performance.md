# Kafka — Chunk 3: Production Reliability, Security, Performance & Incident Mastery

**Backend Engineering Tools & Infrastructure Handbook (BEH)**

**Source file:** `content/kafka/03-kafka-production-reliability-security-performance.md`

---

# 1. Learning Objectives

By the end of this chapter, you should be able to:

- Design partitioning strategies for backend workloads.
- Understand replication, in-sync replicas, and durability tradeoffs.
- Diagnose consumer lag and improve processing throughput.
- Configure retries, dead-letter workflows, and safe recovery procedures.
- Reason about Kafka outages, rebalances, and broker failures.
- Apply security, observability, and capacity-planning principles.
- Understand transactional processing boundaries and the outbox pattern.
- Troubleshoot production incidents systematically.
- Defend Kafka architecture decisions in SDE-1 and backend engineering interviews.

This is the final Kafka chapter. Across the three planned chunks, the Kafka curriculum covers fundamentals, practical implementation, and production engineering.

# Layer 1 — Fundamentals & Mental Models

## 2. Kafka in Production: The System, Not Just the Broker

A production Kafka deployment is more than a collection of brokers. It includes producers, consumers, topic configuration, replication, authentication, monitoring, and operational procedures.

```text
                         +--------------------+
                         |  Backend Services  |
                         +---------+----------+
                                   |
                              Producers
                                   |
                                   v
                     +-------------------------+
                     |      Kafka Cluster      |
                     |                         |
                     | Topics / Partitions      |
                     | Replication / Retention  |
                     +------------+------------+
                                  |
                         Consumer Groups
                                  |
                  +---------------+---------------+
                  |               |               |
                  v               v               v
             Inventory        Analytics         Fraud
              Service          Service          Service

              Monitoring: broker health, producer errors,
              consumer lag, throughput, latency and failures
```

The engineering objective is not simply to keep Kafka running. It is to ensure the overall event-processing system meets its required correctness, latency, availability, and recovery goals.

A healthy broker can coexist with an unhealthy application. For example, the cluster may accept records successfully while a consumer is stuck waiting for a database connection.

## 3. Partition Strategy and Parallelism

Partitions are the foundation of Kafka's parallelism.

Suppose the `orders` topic has six partitions and the `inventory-service` consumer group has three consumers.

```text
Topic: orders

P0 ─────┐
P1 ─────┴────> Consumer A

P2 ─────┐
P3 ─────┴────> Consumer B

P4 ─────┐
P5 ─────┴────> Consumer C
```

The actual assignment depends on the group assignor and current membership. The diagram illustrates one possible assignment.

### 3.1 More partitions, more potential parallelism

For a single consumer group, a partition can be assigned to at most one group member at a time under the normal group-assignment model.

If there are six partitions and three active consumers, all three consumers can process assigned partitions concurrently.

If the group grows to ten consumers, four consumers may have no partition assigned for that topic.

Adding partitions can enable more consumer parallelism, but it is not a free optimization.

Consider:

- Broker storage and metadata overhead.
- File handles and memory overhead.
- Consumer assignment and rebalancing cost.
- The ability of downstream databases to handle additional concurrency.
- Ordering requirements.
- Future workload growth.

Do not choose a partition count solely because a large number sounds scalable.

### 3.2 Choosing a partition key

For an order-processing workload, a key might be:

```text
orderId
```

For a customer-account workload, a key might be:

```text
accountId
```

The key should reflect the entity whose events need related placement or ordered processing.

A poor key can create a **hot partition**.

Imagine one customer generates 40% of all traffic. If the customer ID is the key, a disproportionate share of traffic may go to one partition.

This limits the parallelism available for that workload.

Potential responses include:

- Reconsidering the partition key.
- Separating unusually hot workloads.
- Increasing partitions where it genuinely helps.
- Optimizing consumer processing.
- Using a different data model if strict ordering is not essential.

Changing the key may change ordering guarantees. It is a business and architecture decision, not merely a tuning adjustment.

## 4. Replication, Leaders, and In-Sync Replicas

Kafka can replicate partitions across brokers.

A partition has a leader replica that handles normal reads and writes, while follower replicas replicate its log.

```text
Partition 0

Broker A: Leader
    |
    +------> Broker B: Follower
    |
    +------> Broker C: Follower
```

This is an illustrative replica arrangement. Real assignments depend on cluster metadata and configuration.

### 4.1 Why replication matters

If a broker fails, the cluster may be able to elect a new leader from an eligible replica. That is how replication supports availability and recovery.

Replication does not guarantee that every failure is harmless. The outcome depends on:

- Which replicas are available.
- Whether replicas are in sync.
- The producer's acknowledgment requirements.
- The topic's replication factor.
- The minimum in-sync replica configuration.
- Cluster health and controller behavior.

### 4.2 `acks=all` and `min.insync.replicas`

These settings work together.

- `acks=all` asks the leader to wait for the required in-sync replica acknowledgments.
- `min.insync.replicas` establishes a minimum in-sync replica count required for writes under the relevant acknowledgment behavior.

For example, a topic with replication factor three and a minimum in-sync replica count of two can reject writes requiring all acknowledgments when fewer than two eligible in-sync replicas remain.

That rejection is intentional: it can prevent accepting writes under conditions that violate the desired durability policy.

The correct configuration depends on the application's tolerance for data loss and temporary write unavailability.

### 4.3 Replication is not a backup

Replication helps with broker failure, but it does not protect against every logical error.

If an application writes incorrect data, that data may be replicated too. Retention or deletion mistakes can also affect the records you need.

A robust data-protection strategy considers backups, recovery procedures, replication, and application-level safeguards separately.

## 5. Retention, Compaction, and Storage

Kafka stores records according to topic-level policies.

Two important retention concepts are:

**Time/size-based retention:** Records become eligible for deletion according to the configured retention policy.

**Log compaction:** Kafka retains the latest value for each key in a compacted log, subject to compaction behavior and configuration. Compaction is useful when consumers need the latest known state for keys rather than every historical transition.

Example state stream:

```text
customer-1 -> Bronze
customer-1 -> Silver
customer-1 -> Gold
```

A compacted topic can eventually retain the latest value for `customer-1`, rather than preserving every superseded value indefinitely.

This is not the same as a complete event-history log.

Choose retention based on replay requirements, storage costs, compliance obligations, and the downstream systems' recovery needs.

## 6. Consumer Lag: The Core Operational Signal

Consumer lag indicates how far a consumer group is behind the end of the partition log, according to the offsets used by the monitoring tool.

Conceptually:

```text
Lag ≈ Log-End Position - Consumer Progress
```

The exact numeric calculation can differ according to offset conventions and tooling.

Lag is not automatically a failure. A short-lived spike during a traffic burst may be expected. A steadily growing backlog that misses business deadlines is more concerning.

### Understand lag alongside throughput

Suppose an application receives 2,000 records per second but processes only 1,500 records per second.

Its backlog grows by approximately 500 records per second, assuming a sustained period and comparable units.

Adding consumers may help if the workload can be parallelized and the downstream dependencies have capacity. It will not fix a database that is already saturated.

## 7. Delivery Guarantees and Transaction Boundaries

Kafka's reliability mechanisms operate within defined boundaries.

### Producer reliability

Producer idempotence helps prevent certain duplicate writes caused by retries.

### Kafka transactions

Transactions can coordinate supported Kafka writes and offsets. They are particularly useful when one Kafka processing stage consumes records and publishes derived records.

### External side effects

PostgreSQL transactions, HTTP calls, email delivery, and payment-provider operations are not automatically part of a Kafka transaction.

For these systems, use application-level patterns such as:

- Idempotent operations.
- Database uniqueness constraints.
- Transactional outbox.
- Inbox or deduplication tables.
- Explicit retry and reconciliation workflows.

A production architecture should state its guarantee precisely rather than simply claiming “exactly once.”

# Layer 2 — Practical Engineering & Workflows

## 8. Diagnose Consumer Lag Systematically

When lag grows, investigate before scaling.

### Step 1: Inspect the consumer group

```bash
kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe \
  --group inventory-service
```

Review the lag per partition, current consumer progress, and assignment information provided by the tool.

### Step 2: Compare incoming and processing throughput

Measure:

- Records produced per second.
- Records processed per second.
- Average and tail processing latency.
- Error and retry rates.
- Lag growth over time.

### Step 3: Inspect the downstream dependency

If each event triggers a database update, inspect:

- Database query latency.
- Connection-pool saturation.
- Lock contention.
- Database CPU and I/O.
- Transaction retries.
- Timeouts.

### Step 4: Inspect partition distribution

A single partition may be lagging because one key dominates traffic or because a specific partition's processing is blocked.

### Step 5: Choose the intervention

| Finding | Potential intervention |
|---|---|
| Consumer logic is CPU-bound | Profile and optimize processing |
| Database calls are slow | Optimize SQL, indexes, batching, or pool usage |
| Too few partitions for useful parallelism | Evaluate a partition expansion or topic redesign |
| One hot key dominates | Revisit key strategy or isolate the workload |
| Poison messages cause repeated failure | Introduce bounded retries and a dead-letter strategy |
| Consumers repeatedly restart | Investigate crashes, memory pressure, timeouts, or deployment instability |

Do not increase concurrency blindly. More consumers can overwhelm downstream services and make the incident worse.

## 9. Throughput Tuning

Kafka throughput depends on the entire pipeline: producer batching, network, broker resources, replication, partition count, consumer processing, and downstream dependencies.

### 9.1 Producer batching

Relevant settings include:

```properties
linger.ms=5
batch.size=32768
compression.type=snappy
```

These values are examples, not universal recommendations.

- `linger.ms` can allow additional records to accumulate into a batch.
- `batch.size` influences the producer's target batch size.
- Compression can reduce network and storage usage at the cost of CPU.

Benchmark with realistic payload sizes and traffic patterns.

### 9.2 Consumer processing

A consumer's throughput can be limited by:

- CPU-intensive processing.
- Synchronous network calls.
- Database transactions.
- Serialization overhead.
- Excessive logging.
- Retry delays.
- Too much contention between worker threads.

Measure the slowest part of the pipeline instead of assuming Kafka itself is the bottleneck.

### 9.3 Batching database writes

If the business logic permits it, batching multiple records into a database operation can improve throughput.

But batching introduces tradeoffs:

- Higher latency before a batch is complete.
- More complex error handling for partially invalid data.
- Larger transaction scope.
- More complicated offset-commit decisions.

The batch's business operations and offset progress must be coordinated so that failed work is not silently skipped.

## 10. Retries and Dead-Letter Workflows

Not every error should be retried indefinitely.

A practical classification is:

```text
Record fails
    |
    v
Is the failure transient?
    |
    +---- Yes ---> Bounded retry with backoff
    |                    |
    |                    v
    |             Retry succeeds?
    |                /       \
    |              Yes       No
    |               |         |
    |               v         v
    |            Continue   Escalate or isolate
    |
    +---- No ----> Record failure details
                       |
                       v
                Dead-letter workflow
```

A dead-letter topic can preserve a record that could not be processed by the normal workflow.

Useful diagnostic information can include:

- Original topic, partition, and offset.
- Event ID.
- Failure category.
- Timestamp and retry count.
- A sanitized error description.
- Trace or correlation ID.

Do not blindly copy secrets or sensitive payload fields into diagnostic records.

### Ordering tradeoff

Moving a failed event to a dead-letter topic and continuing with later records can change the effective order in which business effects occur.

If order matters, define whether later records must wait, whether the entity can be quarantined, or whether the failure can be resolved and replayed safely.

## 11. Safe Replay and Recovery

Kafka allows consumers to reread retained records by changing the group's starting position or using a separate consumer group.

Replay is useful for:

- Rebuilding derived state.
- Reprocessing after a fixed bug.
- Backfilling analytics.
- Recovering a consumer's application state.

But replaying events can repeat external side effects.

Before replaying production data:

1. Identify the exact topic, partitions, and offset range.
2. Confirm retention still includes the required records.
3. Determine whether the operation is idempotent.
4. Decide whether to reuse the existing group or create a separate recovery group.
5. Estimate replay volume and downstream load.
6. Define a stop condition and rollback or reconciliation plan.
7. Monitor lag, processing errors, and business-level outcomes.

Avoid changing production offsets casually. A mistaken offset reset can cause missed processing or large-scale duplication.

## 12. Security and Access Control

A production Kafka deployment should apply defense in depth.

### Authentication

Verify the identity of clients using the chosen mechanism, such as SASL-based authentication or another supported enterprise configuration.

### Encryption

Use TLS where required to protect traffic in transit.

### Authorization

Restrict access to topics, consumer groups, and administrative operations.

For example, an analytics consumer may need permission to read the `orders` topic but should not automatically receive permission to delete topics or modify cluster-wide settings.

### Secret management

- Keep passwords, tokens, and private keys out of source control.
- Use a secret manager or controlled deployment configuration.
- Rotate credentials.
- Audit access.
- Restrict administrative access.
- Avoid exposing event payloads in logs unnecessarily.

Security configuration depends on the Kafka distribution, deployment model, and selected authentication and authorization mechanisms.

## 13. Observability: What Should You Monitor?

Monitor both Kafka infrastructure and application behavior across four essential dimensions:

| Monitoring Area | Focus Metrics & Operational Signals |
|---|---|
| **Broker health** | Broker availability, request latency, resource pressure, under-replicated partitions, and offline partitions. |
| **Producer health** | Send failures, retries, request latency, throughput, and serialization errors. |
| **Consumer health** | Lag, processing throughput, processing latency, failed records, retries, and rebalances. |
| **Business outcomes** | Orders processed, inventory updates completed, duplicate-event detections, and end-to-end processing delay. |

Infrastructure metrics tell you whether Kafka is functioning. Business metrics tell you whether the system is accomplishing its purpose.

For example, a low consumer lag is not enough if the consumer acknowledges records but fails to update inventory correctly.

## 14. End-to-End Tracing

Distributed event processing can cross multiple services and execute long after the original HTTP request ends.

Use correlation identifiers and distributed tracing to connect:

```text
HTTP request
    |
    v
Order API
    |
    v
Kafka publish
    |
    v
Inventory consumer
    |
    v
PostgreSQL transaction
```

Where supported, propagate trace context through Kafka headers and instrument producer and consumer operations.

A trace ID is useful for investigation, but it should not be treated as a unique business-event identifier. Use a separate stable event ID for deduplication.

## 15. Production Readiness Checklist

Before deploying an event-driven service, review the following.

- [ ] Topic replication and minimum in-sync replica settings match durability requirements.
- [ ] Producer acknowledgment, retry, and idempotence settings have been reviewed.
- [ ] Consumer offset-commit behavior is explicit.
- [ ] Business operations are safe under duplicate delivery.
- [ ] Schema evolution is tested.
- [ ] Retry and dead-letter behavior is defined.
- [ ] Consumer lag and processing latency are monitored.
- [ ] Broker and consumer failure alerts are actionable.
- [ ] Authentication, encryption, and authorization are configured as required.
- [ ] Secrets are managed outside source control.
- [ ] Replay and offset-reset procedures are documented.
- [ ] Downstream database capacity has been tested.
- [ ] Graceful shutdown and rebalance behavior have been tested.
- [ ] Disaster recovery and data-protection requirements are documented.
- [ ] Production load testing uses realistic event sizes and arrival rates.

# Layer 3 — Production Engineering & Interview Mastery

## 16. Incident Simulation 1: Consumer Lag Explosion

**Situation:** The `orders` topic is receiving traffic normally, but inventory consumer lag has grown rapidly.

### Investigation

1. Check the lag by partition.
2. Compare incoming rate with processing rate.
3. Check recent deployments and error-rate changes.
4. Inspect database latency and connection-pool saturation.
5. Look for repeated retries or a poison event.
6. Determine whether one partition is disproportionately affected.

### Decision

If processing is slow because database queries are inefficient, optimize the database path first.

If processing is healthy but there are too few partitions for the required concurrency, evaluate partition scaling.

If a poison event is blocking progress, resolve or isolate it according to the ordering requirements.

### Verification

Confirm that lag is decreasing, error rates are stable, downstream services remain healthy, and the business processing delay is returning to its target.

Do not declare recovery merely because consumer processes are running.

## 17. Incident Simulation 2: Duplicate Inventory Reservations

**Situation:** A customer places one order, but inventory appears to have been reserved twice.

### Possible causes

- The consumer updated the database and crashed before committing its offset.
- The producer emitted duplicate logical events.
- An upstream request was retried.
- A replay operation repeated the same event.
- The consumer's deduplication logic is incorrect.

### Investigation

1. Compare the event IDs and order IDs.
2. Inspect consumer restart and offset-commit timing.
3. Check application retry logs.
4. Examine the inventory transaction history.
5. Verify whether event deduplication and the business update share a transaction.

### Resolution

Implement or repair idempotent processing, reconcile incorrect inventory state, and add a regression test for the crash window.

A robust test should simulate failure after the database transaction commits but before Kafka progress is committed.

## 18. Incident Simulation 3: Producer Errors After a Broker Failure

**Situation:** A broker fails and order-event publication begins returning errors.

### Investigation

1. Confirm the failed broker and affected partitions.
2. Inspect leader elections and replica health.
3. Check the in-sync replica count.
4. Verify producer error and retry metrics.
5. Confirm that clients can reach the advertised broker addresses.
6. Determine whether writes are being rejected because durability requirements cannot be met.

### Resolution principles

- Preserve the intended durability policy.
- Restore broker and replica health.
- Allow safe retries according to producer configuration.
- Avoid disabling acknowledgment requirements merely to hide errors.
- Verify event completeness and business reconciliation after recovery.

The correct response depends on the cluster topology and configured guarantees. A single-broker local environment cannot simulate a genuine replicated-cluster failover.

## 19. Incident Simulation 4: Poison Event Blocks Business Progress

**Situation:** One malformed event repeatedly fails and later records in the partition are not being processed.

### Investigation

- Identify the record's topic, partition, offset, and event ID.
- Determine whether the failure is transient or permanent.
- Check whether the consumer retries indefinitely.
- Establish whether subsequent events depend on the failed event.

### Resolution

Use a bounded retry strategy and an appropriate isolation workflow.

If later records are allowed to proceed, ensure that skipping or delaying the failed event does not violate business invariants. Preserve enough diagnostic information to repair and replay the event if necessary.

## 20. Advanced Interview Questions

### Q1. How would you choose the number of partitions?

Estimate required throughput and parallelism, consider consumer count and key distribution, test realistic workloads, and account for operational overhead and ordering requirements. Avoid choosing an arbitrary large number.

### Q2. What happens when a broker fails?

The cluster may elect a new leader from an eligible replica. The outcome depends on replica availability, in-sync status, cluster metadata, and durability configuration.

### Q3. Does replication prevent data loss?

It reduces exposure to certain broker failures but does not eliminate every data-loss scenario. Producer acknowledgment policy, replica health, retention, and logical errors all matter.

### Q4. Why can `acks=all` still fail to protect a write?

It depends on the configured in-sync replica set and cluster state. If the required acknowledgment conditions cannot be met, the write may fail. The setting does not replace appropriate replication and recovery design.

### Q5. Why does consumer lag increase even though Kafka brokers are healthy?

Consumers may be slower than incoming traffic, blocked by downstream dependencies, retrying failed records, or processing unevenly distributed partitions.

### Q6. How would you scale a slow consumer?

Identify the bottleneck first. Then consider optimizing processing, batching, increasing consumer concurrency within partition limits, or changing partition strategy. Check downstream capacity before scaling.

### Q7. What is a hot partition?

A partition receiving a disproportionate share of traffic or expensive work, often because of key distribution or workload characteristics.

### Q8. Why is changing a partition key dangerous?

It can change record placement and the ordering relationships the application relies on. Existing and future events may no longer share the same partitioning behavior.

### Q9. What is the difference between retention and compaction?

Retention removes records according to configured policies. Compaction retains the latest known values for keys over time, subject to its configuration and processing behavior.

### Q10. How does a dead-letter topic help?

It isolates records that cannot be processed normally, enabling investigation and recovery without necessarily allowing one poison record to block all further processing.

### Q11. What is the downside of dead-lettering a failed record?

Continuing with later records can change effective business order. The workflow must account for dependencies and define how failed records are recovered.

### Q12. How do you safely replay production events?

Define the topic and offset range, check retention, assess side effects and idempotency, control replay rate, monitor downstream load, and define reconciliation and stop conditions.

### Q13. What is the difference between an event ID and a trace ID?

An event ID identifies a logical event for deduplication and business tracking. A trace ID links operations across a distributed execution. One event may be processed across multiple spans, and tracing identifiers should not replace business identity.

### Q14. What should you monitor beyond consumer lag?

Processing latency, throughput, error and retry rates, broker health, replication status, producer failures, downstream latency, and business completion metrics.

### Q15. Why is a Kafka transaction not a global transaction?

Kafka transactions coordinate supported Kafka operations. They do not automatically include arbitrary databases or external HTTP services.

### Q16. What problem does the transactional outbox solve?

It coordinates the durable creation of business state and an event record in the same database transaction, reducing the risk of a committed business change with no corresponding event record.

### Q17. Does an outbox eliminate duplicate publication?

No. A publisher may send an event and crash before recording publication success. Consumers still need idempotency or an equivalent deduplication strategy.

### Q18. What is the role of consumer-group rebalancing?

It redistributes partition ownership as membership or assignment requirements change. Poor processing and shutdown behavior can make rebalances disruptive.

### Q19. Why is blindly increasing retries dangerous?

It can increase latency, consume resources, block progress, and repeatedly hit a dependency that is already failing. Retries should be bounded and appropriate to the failure type.

### Q20. When is Kafka unnecessary?

When the workload is simple, throughput and replay requirements are modest, and a direct call, database-backed job, or simpler queue satisfies the reliability requirements with less operational complexity.

## 21. Final Hands-On Capstone

Build an event-driven order-processing prototype using Spring Boot, PostgreSQL, Kafka, and Redis.

### Architecture

```text
Client
  |
  v
Order API
  |
  +------> PostgreSQL
  |          |
  |          +----> Orders table
  |          |
  |          +----> Outbox table
  |
  v
Outbox Publisher
  |
  v
Kafka: orders topic
  |
  +------> Inventory Consumer
  |
  +------> Analytics Consumer

Redis: cache frequently accessed order summaries
```

This is a reference architecture. Redis is optional and should be included only if the caching requirement justifies it.

### Implementation milestones

**Milestone 1 — Produce events**

- Create an order through a REST endpoint.
- Persist the order in PostgreSQL.
- Define an `OrderCreated` event.
- Publish through Kafka.

**Milestone 2 — Process events**

- Build an inventory consumer.
- Build an independent analytics consumer.
- Use separate consumer groups.
- Add stable event IDs and structured logging.

**Milestone 3 — Reliability**

- Add a PostgreSQL-backed idempotency mechanism.
- Implement an outbox if order persistence and event publication must be reliably coordinated.
- Add bounded retries and a dead-letter workflow.
- Define how failed events are recovered.

**Milestone 4 — Observability**

- Measure producer send errors and latency.
- Monitor consumer lag and processing time.
- Log event IDs and correlation IDs.
- Track business-level completion counts.

**Milestone 5 — Failure testing**

Simulate:

- A consumer restart after processing but before committing progress.
- A duplicate event.
- A database outage.
- A malformed event.
- A slow consumer and growing lag.
- A publication failure.
- A replay of retained events.

For each scenario, document expected behavior, observed behavior, recovery procedure, and the test proving recovery.

## 22. Final Kafka Mastery Assessment

Review and validate the following Kafka readiness checklist before production deployment:

- [ ] Explain topics, partitions, offsets, brokers, producers, and consumer groups.
- [ ] Design a key strategy that supports the required ordering guarantees.
- [ ] Explain producer acknowledgments, idempotence, and replication.
- [ ] Configure a Spring Boot producer and consumer.
- [ ] Explain offset commits and duplicate-processing failure windows.
- [ ] Implement an idempotent consumer backed by PostgreSQL.
- [ ] Explain the transactional outbox and its remaining duplicate-publication risk.
- [ ] Diagnose lag using throughput, latency, partition distribution, and downstream health.
- [ ] Design bounded retries and dead-letter recovery.
- [ ] Explain retention, compaction, and safe replay.
- [ ] Identify Kafka security and observability requirements.
- [ ] Defend a Kafka architecture using concrete reliability and operational tradeoffs.

> **Mastery Validation:** Validate all checklist items through hands-on testing, the capstone architecture, and failure simulations before considering the material fully mastered.

## 23. Kafka Curriculum Completion

The three planned Kafka chapters are now authored in this conversation:

1. Fundamentals, Event Streaming & Core Mental Models
2. Producers, Consumers, Delivery Semantics & Spring Boot Integration
3. Production Reliability, Security, Performance & Incident Mastery

**Repository completion is a separate step.** Save all three Markdown sources under `content/kafka/`, review the examples against the Kafka and Spring Kafka versions you use, and verify the files before generating the single final PDF:

`docs/kafka/BEH_KAFKA_COMPLETE_HANDBOOK.pdf`

Do not create PDFs per chunk. Once the complete Kafka handbook PDF is generated and verified, use the required Git commit message:

`Kafka done`

The next tool in the locked curriculum is **Nginx — Chunk 1 of 2: Reverse Proxies, HTTP Routing & Core Mental Models**.
