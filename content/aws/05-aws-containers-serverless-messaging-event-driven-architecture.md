# AWS — Chunk 5 of 6: Containers, Serverless, Messaging & Event-Driven Architecture

## Backend Engineering Tools & Infrastructure Handbook · Cloud Engineering Track

**Source file:** `content/aws/05-aws-containers-serverless-messaging-event-driven-architecture.md`

---

## Learning Objectives

By the end of this chapter, you should be able to:

- Understand Amazon ECS, AWS Fargate, and AWS Lambda.
- Choose between EC2-based deployment, managed containers, and serverless functions.
- Explain SQS, SNS, and EventBridge without confusing their responsibilities.
- Design asynchronous workflows for a Spring Boot backend.
- Handle retries, duplicate messages, dead-letter queues, and idempotency.
- Understand event-driven architecture failure modes and operational trade-offs.
- Answer backend interview questions about cloud-native application architecture.

---

# Layer 1 — Fundamentals & Mental Models

## 1. Three Ways to Run Backend Code on AWS

In the previous chapters, we ran a Spring Boot API on EC2. That works, but operating virtual machines is not the only way to deploy backend software.

Consider three primary approaches:

### Option A — Amazon EC2 (Virtual Machines)
You manage virtual machines and the application runtime. You have substantial control over the guest operating system, deployment process, filesystem, and instance configuration.

### Option B — Amazon ECS with AWS Fargate (Managed Containers)
Package the application as a Docker container image and run it as a managed task. AWS manages the underlying server infrastructure for Fargate tasks, while you configure container resources, networking, task definitions, and deployment behavior.

### Option C — AWS Lambda (Serverless Functions)
Run code in response to configured events or requests without managing servers or long-running daemons. AWS manages the execution infrastructure, autoscaling, and concurrency, while you remain responsible for code, permissions, configuration, and application behavior.

---

### The Central Trade-Off

You are not choosing between a "good" architecture and a "bad" architecture. You are choosing how much infrastructure control and operational responsibility your workload requires:

| Consideration | Amazon EC2 | Amazon ECS with Fargate | AWS Lambda |
|---|---|---|---|
| **Primary abstraction** | Virtual machine | Container task or service | Function invocation |
| **OS management** | You manage guest OS & patches | AWS manages underlying Fargate OS | AWS manages execution environment |
| **Deployment unit** | Application on a machine | Container image (Docker/OCI) | Function zip package or container image |
| **Long-running service** | Yes (Daemon / Systemd) | Yes (Long-running service) | No (Max 15-minute execution limit) |
| **Request/event-driven** | Possible (always listening) | Possible (always listening) | Core native model |
| **Scaling** | Auto Scaling Groups (minutes) | ECS service autoscaling (tasks) | Concurrency scaling (milliseconds) |
| **Operational control** | High (full root / kernel) | Container-level control | Constrained runtime sandbox |
| **Typical concern** | OS patching & idle compute costs | Task sizing & networking config | Cold starts, concurrency limits, timeouts |

The appropriate choice depends on the workload, team expertise, reliability requirements, deployment constraints, and total cost.

---

## 2. Amazon ECS: Running Containers as a Service

Suppose your Orders API has a Docker image:

```text
orders-api:1.4.0
```

You want multiple copies running behind an Application Load Balancer, but you do not want to manually start each container, configure networking, and replace failed copies yourself.

**Amazon Elastic Container Service (ECS)** is a fully managed container orchestration service that manages the deployment, lifecycle, and scaling of containers according to a desired configuration.

### ECS Mental Model

```text
                      +------------------------------------------+
                      |               ECS Cluster                |
                      | Logical grouping for capacity & services |
                      +--------------------+---------------------+
                                           |
                                           v
                      +------------------------------------------+
                      |               ECS Service                |
                      | Maintains intended number of tasks       |
                      +--------------------+---------------------+
                                           |
               +---------------------------+---------------------------+
               |                                                       |
               v                                                       v
     +-------------------+                                   +-------------------+
     |      Task A       |                                   |      Task B       |
     |   Container(s)    |                                   |   Container(s)    |
     +-------------------+                                   +-------------------+

     (An ECS task runs one or more containers defined by a task definition.)
```

### Important ECS Concepts

- **Cluster:** A logical grouping of ECS workloads, tasks, and compute capacity.
- **Task definition:** A declarative JSON blueprint describing container images, CPU and memory allocation, environment variables, secrets, ports, logging, and IAM roles.
- **Task:** A running instance of a task definition (equivalent to a Kubernetes Pod).
- **Service:** Maintains a desired number of tasks, integrates with an Application Load Balancer, and manages rolling deployment and task replacement behavior.
- **Container image:** The packaged application and its runtime dependencies stored in Amazon ECR (Elastic Container Registry).
- **Task role:** IAM permissions granted to the application code executing inside the container (e.g., access to S3 or DynamoDB).
- **Task execution role:** IAM permissions granted to the ECS container agent to pull private images from ECR and stream logs to CloudWatch.

> [!IMPORTANT]
> Do not confuse the **Task Role** with the **Task Execution Role**. The Execution Role belongs to the AWS infrastructure agent (pull image, send logs); the Task Role belongs to your application code.

### ECS on EC2 versus ECS on Fargate

ECS can use two distinct compute launch types:

- **ECS on EC2:** You manage the EC2 instances providing container capacity. You handle host OS maintenance, Docker daemon updates, capacity planning, and scaling policies.
- **ECS on Fargate:** AWS manages the underlying virtual machine compute infrastructure. You simply specify CPU and memory per task (e.g., 0.5 vCPU, 1 GB RAM). Fargate eliminates server management, host patching, and cluster capacity management.

Fargate reduces host-management work. It does not eliminate the need to operate and monitor the application.

---

## 3. What Is AWS Lambda?

**AWS Lambda** is a serverless compute service that executes code in response to supported invocation sources without provisioning or managing servers.

For example, you might want to generate a thumbnail whenever an image is uploaded to S3:

```text
User uploads image
       |
       v
   Amazon S3
       |
       | Object-created event (s3:ObjectCreated:*)
       v
   AWS Lambda
       |
       v
Thumbnail generation
       |
       v
Save thumbnail to S3 (processed-media/)
```

The application does not need to keep a dedicated server running 24/7 solely to wait for occasional image-upload events.

### Ideal Use Cases for Lambda

- Event-driven processing (S3 uploads, DynamoDB Streams).
- Lightweight data transformations and ETL pipelines.
- Scheduled cron jobs (via EventBridge Scheduler).
- Webhooks and lightweight REST API handlers.
- Queue consumers (SQS) and stream processors (Kinesis).
- Operational automation and glue code between AWS services.

### Hard Constraints and Operational Limits

Lambda has specific service-level boundaries you must plan around:
- **Maximum execution duration:** 15 minutes per invocation (900 seconds).
- **Memory allocation:** 128 MB to 10,240 MB (CPU scales proportionally with memory).
- **Ephemeral scratch disk:** 512 MB baseline up to 10 GB (`/tmp`).
- **Cold start latency:** The time required to initialize a new execution environment (download code, boot runtime, load framework). Can be noticeable for JVM-based Spring Boot applications.
- **Concurrency limit:** Default regional account limit (e.g., 1,000 concurrent executions), expandable via service quota requests.

### Lambda versus a Continuously Running Spring Boot API

A traditional Spring Boot API is typically a continuously running process that listens on a TCP port for HTTP requests.

A Lambda function is invoked on-demand through an event bridge or API Gateway, executes within a sandbox, and suspends or tears down when idle.

While frameworks like AWS Serverless Java Container allow Spring Boot to run on Lambda, large frameworks incur substantial cold-start penalties (several seconds). For high-throughput, low-latency, complex REST APIs, running containers on ECS Fargate is generally more predictable and cost-effective than forcing Spring Boot into serverless functions.

---

## 4. SQS: A Queue That Decouples Work

Imagine that a user places an order.

The API needs to save the order in PostgreSQL, send an order confirmation email, and notify an external fulfillment warehouse.

If the API performs every operation synchronously, the client request becomes slow and fragile. If the third-party email provider experiences a 3-second delay or temporary downtime, an otherwise valid order fails or times out.

A queue lets you separate the immediate business transaction from asynchronous background work.

**Amazon Simple Queue Service (SQS)** is a fully managed, durable message queuing service:

```text
Order API
   |
   | Send message ("OrderPlaced")
   v
Amazon SQS Queue
   |
   v
Background Worker
   |
   +----> Send confirmation email
   |
   +----> Dispatch order to fulfillment partner
```

The API enqueues work and returns `202 Accepted` or `201 Created` immediately. Consumers process the backlog asynchronously at their own sustained pace.

### The Queue Mental Model

Think of SQS as a durable, distributed work inbox:

```text
1. Producer sends message -> SQS writes message redundantly across multiple AZs
2. Consumer polls queue -> Receives message via ReceiveMessage API
3. Visibility Timeout begins -> Message is hidden from other workers for N seconds
4. Consumer processes work -> Sends email, calls third-party APIs
5. Consumer deletes message -> Explicit DeleteMessage API call removes it permanently
```

If the consumer crashes or processing fails before `DeleteMessage` is invoked, the visibility timeout expires and the message reappears in the queue for another consumer to process.

> **Golden Rule of Queues:** Always design consumers to tolerate duplicate message processing!

### Standard versus FIFO Queues

| Characteristic | Standard Queue | FIFO Queue (`.fifo`) |
|---|---|---|
| **Message Ordering** | Best-effort ordering (may arrive out of order) | Strictly First-In-First-Out within Message Group ID |
| **Delivery Guarantee** | At-least-once delivery (duplicates possible) | Exactly-once processing (within 5-minute deduplication interval) |
| **Throughput** | Virtually unlimited transactions per second | 300 to 3,000 transactions per second (batching) |
| **Deduplication** | Application must implement idempotency | Content-based deduplication or deduplication ID |
| **Common Use** | Independent tasks, image resizing, emails | Financial transactions, inventory ledgers, state machines |

A FIFO queue does not automatically make an entire distributed business workflow "exactly once." If a worker updates a database, encounters a network timeout, and crashes, retries can still occur. Application idempotency remains mandatory.

---

## 5. SNS: Publish a Message to Multiple Subscribers

Suppose placing an order requires notifying several independent internal and external systems:

- Email worker (sends customer receipts).
- Fulfillment worker (generates packing slips).
- Analytics pipeline (records revenue metrics).
- Fraud detection service (runs ML scoring).

If the Order API sends an SQS message directly to each worker's individual queue, the producer becomes tightly coupled to knowing every downstream consumer.

**Amazon Simple Notification Service (SNS)** provides a managed publish-subscribe (pub/sub) fan-out model:

```text
                 Order API
                    |
                    | Publish "OrderPlaced"
                    v
             Amazon SNS Topic
                 /  |  \
                /   |   \
               v    v    v
             SQS A SQS B SQS C
               |    |    |
               v    v    v
             Email Fulfillment Analytics
             Worker   Worker    Worker
```

The publisher emits one message to the SNS topic. SNS fans out the message to all subscribed endpoints, including SQS queues, HTTP webhooks, Lambda functions, or email addresses.

### Why Combine SNS with SQS (Fan-Out Pattern)?

Publishing directly to HTTP webhooks or email endpoints lacks buffering. If an external subscriber is down, notifications are dropped or lost after retries.

By subscribing dedicated SQS queues to an SNS topic:

- **Isolated buffering:** If fulfillment takes 10 minutes to process a batch, its queue buffers messages without slowing down email or analytics.
- **Fault isolation:** An outage in the analytics service has zero impact on order fulfillment.
- **Independent retry policies:** Each queue configures its own visibility timeout, dead-letter queue, and retry limits.
- **Zero producer changes:** Adding a new fraud detection service requires only subscribing a new queue to the SNS topic; zero code changes are needed in the Order API.

---

## 6. EventBridge: Route Events Based on Their Meaning

**Amazon EventBridge** is a serverless event bus service that routes events between applications, integrated SaaS services (e.g., Zendesk, Stripe, Auth0), and AWS services using declarative rules.

Consider an e-commerce platform emitting diverse domain events:

```text
OrderPlaced
PaymentAuthorized
PaymentFailed
ShipmentDispatched
CustomerAccountLocked
```

Different consumers care about different event types and specific payload attributes.

EventBridge evaluates event patterns (JSON rules) to route matching events:

```text
Services and SaaS Event Sources
               |
               v
     Amazon EventBridge Bus
               |
      Declarative Rules & Filtering
          /      |       \
         v       v        v
      Lambda    SQS      Step Functions
      Worker   Queue     Workflow
```

### Example EventBridge Rule Pattern

Filter only orders where payment succeeded and total exceeds $500:

```json
{
  "source": ["ecommerce.orders"],
  "detail-type": ["OrderPlaced"],
  "detail": {
    "status": ["PAID"],
    "totalAmount": [{ "numeric": [">", 500] }]
  }
}
```

### SQS vs. SNS vs. EventBridge: Deciding Which to Use

| Dimension | Amazon SQS | Amazon SNS | Amazon EventBridge |
|---|---|---|---|
| **Core Abstraction** | Point-to-point work queue | Pub/sub topic fan-out | Event bus with content-based routing |
| **Delivery Model** | Consumer pulls (polls) | Push to subscribers | Push to targets |
| **Filtering** | None (consumer filters) | Basic message attributes | Deep payload JSON content filtering |
| **Latency** | Milliseconds | Sub-second | ~100–500 milliseconds |
| **SaaS Integrations** | No direct SaaS integration | No direct SaaS integration | Native partner integrations (Stripe, Datadog) |
| **Schema Registry** | No | No | Built-in schema discovery & registry |
| **Best Used For** | Work buffering, load leveling | High-throughput fan-out to queues | Cross-service enterprise event routing |

---

## 7. What Is an Event-Driven Architecture?

In a **request-driven (synchronous)** architecture, services communicate via direct blocking HTTP/REST or RPC calls:

```text
Client -> Order Service -> Inventory Service -> Payment Gateway -> Notification Service
```

- *Disadvantages:* High coupling, cascading failures (if payment is slow, the entire chain stalls), higher latency (sum of all dependencies), and fragile error handling.

In an **event-driven (asynchronous)** architecture, services communicate by producing and consuming events representing past occurrences ("facts"):

```text
Order Service -> [Emits "OrderPlaced"] -> Event Router -> Consumers react independently
```

### Event-Driven Benefits and Operational Realities

- **Benefits:** Loosely coupled services, independent scaling, resilient to temporary downstream outages, and simpler addition of new features.
- **Challenges:**
  - *Eventual consistency:* Data is not immediately synchronized across all services.
  - *At-least-once delivery:* Consumers must handle duplicate messages.
  - *Out-of-order processing:* Network delays can cause an `OrderCancelled` event to arrive before an `OrderCreated` event.
  - *Tracing & debugging:* Requires distributed tracing headers (W3C TraceContext, AWS X-Ray) to correlate asynchronous logs across independent microservices.

---

## 8. A Realistic Architecture: Order Creation and Background Processing

Consider a complete order placement workflow:

1. Client submits an order.
2. Spring Boot Order API validates input and business rules.
3. Order is written to PostgreSQL.
4. An `OrderPlaced` event is published to messaging infrastructure.
5. Fulfillment and email workers react to the event.

### The Dual-Write Problem

What happens if step 3 succeeds (order saved in PostgreSQL), but the application crashes, network fails, or broker is unreachable during step 4?

- **Outcome A:** Order exists in the database, but downstream workers never process it (customer is charged, but no goods are shipped).
- **Outcome B:** If you reverse the order (publish event first, then write DB) and the DB transaction fails, ghost events trigger fulfillment for non-existent orders.

### The Transactional Outbox Pattern

The **Transactional Outbox Pattern** solves the dual-write problem by writing both the business record and the event record into the **same relational database transaction**:

```text
+--------------------------------------------------------------+
|                Single PostgreSQL Transaction                 |
|                                                              |
|  1. INSERT INTO orders (...) VALUES (...);                   |
|  2. INSERT INTO outbox_events (event_id, payload, ...) ...;  |
+------------------------------+-------------------------------+
                               |
                               | COMMIT
                               v
                     +-------------------+
                     | Outbox Publisher  | (Scheduled Poller or Debezium CDC)
                     +---------+---------+
                               |
                               | Reliable Publish
                               v
                  Messaging Fabric (EventBridge / SNS)
```

Because the outbox event and the order are committed atomically:
- If the transaction rolls back, neither exists.
- If the transaction commits, both exist durably.
- A background publisher polls the `outbox_events` table or uses Change Data Capture (CDC via PostgreSQL logical decoding), publishes to SNS/EventBridge, and marks the outbox record as `PUBLISHED`.
- If the publisher crashes after publishing but before marking the record, it retries upon restart. This produces duplicate events, which downstream idempotent consumers handle seamlessly.

---

# Layer 2 — Practical Engineering & Workflows

## 9. Choose a Deployment Pattern for a Backend

When architecting a Java 21 Spring Boot API on AWS, evaluate these three proven production patterns:

### Pattern A: Spring Boot on EC2 in Auto Scaling Group
- **Architecture:** `Client -> ALB -> EC2 ASG (Amazon Linux 2023) -> Spring Boot JVM`
- **Best fit:** Teams with established VM operational tooling, workloads requiring direct hardware manipulation, or legacy applications expecting local filesystems.
- **Trade-off:** High operational overhead (OS updates, AMI baking, slow ASG scale-out times of 3–5 minutes).

### Pattern B: Containerized Spring Boot on ECS Fargate
- **Architecture:** `Client -> ALB -> ECS Service -> AWS Fargate Tasks (Docker)`
- **Best fit:** Standard modern backend APIs. Zero host maintenance, containerized immutability, automated rolling updates, and predictable task sizing.
- **Trade-off:** Slightly higher compute unit cost compared to reserved EC2 instances; requires container registry (ECR) management.

### Pattern C: Event-Driven Processing with AWS Lambda
- **Architecture:** `EventBridge / S3 / SQS -> AWS Lambda Function (Java/Go/Node.js)`
- **Best fit:** Background asynchronous jobs, image processing, webhook ingestion, and bursty, infrequent event processing.
- **Trade-off:** Not recommended as the primary HTTP host for large Spring Boot monoliths due to cold starts; excellent for lightweight specialized workers.

---

## 10. Design an SQS Consumer Correctly

A robust message consumer requires an explicit, fail-safe processing lifecycle:

```text
                     +-------------------------+
                     | ReceiveMessage from SQS |
                     +------------+------------+
                                  |
                                  v
                     +-------------------------+
                     |    Validate Payload     |
                     +------------+------------+
                                  |
                                  v
                     +-------------------------+
                     |    Check Idempotency    |
                     +------------+------------+
                                  |
               +------------------+------------------+
               | (New Event)                         | (Already Processed)
               v                                     v
+-----------------------------+       +-----------------------------+
|  Execute Business Operation |       |    Log Duplicate & Skip     |
+--------------+--------------+       +--------------+--------------+
               |                                     |
               v                                     |
+-----------------------------+                      |
| Save State & Idempotency DB |                      |
+--------------+--------------+                      |
               |                                     |
               +------------------+------------------+
                                  |
                                  v
                     +-------------------------+
                     |   DeleteMessage (ACK)   |
                     +-------------------------+
```

### Configuring the Visibility Timeout

- The **Visibility Timeout** must be set to at least **6 times the expected task processing duration**, plus buffer.
- If task processing averages 10 seconds, set the visibility timeout to at least 60–90 seconds.
- If processing takes longer than anticipated, the consumer can send a heartbeat using `ChangeMessageVisibility` to extend the lease.

### Dead-Letter Queues (DLQ) and Redrive Policies

- Every production queue must have an associated **Dead-Letter Queue (DLQ)**.
- Configure `maxReceiveCount` (typically 3 to 5).
- If a message fails processing `maxReceiveCount` times, SQS automatically moves it to the DLQ.
- Prevents "poison pill" messages from perpetually blocking queue processing or wasting consumer CPU.

---

## 11. Idempotency: The Key to Safe Retries

Because standard queues guarantee at-least-once delivery, consumers must guarantee that processing a duplicate message produces no additional side effects.

### PostgreSQL Idempotency Table Schema

```sql
CREATE TABLE processed_events (
    event_id UUID PRIMARY KEY,
    event_type VARCHAR(64) NOT NULL,
    order_id VARCHAR(64) NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### Atomic Deduplication Workflow in Spring Boot

```java
@Transactional
public void processOrderEvent(OrderPlacedEvent event) {
    // 1. Attempt atomic insert into processed_events table
    try {
        jdbcTemplate.update(
            "INSERT INTO processed_events (event_id, event_type, order_id) VALUES (?, ?, ?)",
            event.getEventId(), event.getEventType(), event.getOrderId()
        );
    } catch (DuplicateKeyException e) {
        log.warn("Duplicate event detected: {}. Skipping business logic.", event.getEventId());
        return; // Idempotent exit; message will be acknowledged and deleted from queue
    }

    // 2. Perform business logic in the same transaction
    inventoryService.reserveStock(event.getOrderId(), event.getItems());
    orderRepository.markStatus(event.getOrderId(), OrderStatus.PROCESSING);
}
```

If the transaction succeeds, both the business modification and the idempotency record commit atomically. If the message is redelivered, the duplicate key exception safely aborts execution before external side effects occur.

---

## 12. Retries, Backoff, and Poison Messages

Not all errors are equal. A production consumer must categorize failures:

### Transient Failures (Retryable)
- Network socket timeout to database.
- Downstream HTTP 429 (Too Many Requests / Throttling) or 503 (Service Unavailable).
- Deadlock detected during concurrent database transactions.
- **Handling:** Retry with exponential backoff and full jitter:
  $$t_{\text{sleep}} = \text{random}(0, \min(M, B \times 2^{\text{attempt}}))$$

### Permanent Failures (Non-Retryable)
- JSON deserialization error (malformed syntax).
- Missing required fields (e.g., missing `orderId`).
- Business rule validation failure (e.g., negative payment amount).
- Unknown event version.
- **Handling:** Do **not** retry! Immediately route to DLQ or log as fatal error and acknowledge to purge from main queue. Retrying a malformed JSON payload 5 times wastes compute and delays other messages.

---

## 13. Lambda and SQS: Asynchronous Event Processing

When AWS Lambda consumes from SQS via an **Event Source Mapping (ESM)**:

- Lambda service internally polls SQS and invokes your function synchronously with batches of messages (e.g., batch size 10).
- If your function completes without exceptions, the Lambda service automatically deletes the batch from SQS.

```text
Producer -> SQS -> Lambda Event Source Mapping (ESM) -> Lambda Handler -> Database
```

### Preventing Whole-Batch Retries: Partial Batch Responses

By default, if 1 message in a batch of 10 throws an exception, Lambda considers the entire batch failed. All 10 messages become visible again and are reprocessed, causing 9 duplicates!

**Solution:** Enable **Report Batch Item Failures** in the ESM and return individual failed IDs:

```java
public class SqsBatchHandler implements RequestHandler<SQSEvent, SQSBatchResponse> {
    @Override
    public SQSBatchResponse handleRequest(SQSEvent event, Context context) {
        List<SQSBatchResponse.BatchItemFailure> failures = new ArrayList<>();

        for (SQSEvent.SQSMessage msg : event.getRecords()) {
            try {
                processSingleMessage(msg);
            } catch (Exception e) {
                // Record only the specific message that failed
                failures.add(new SQSBatchResponse.BatchItemFailure(msg.getMessageId()));
            }
        }
        return new SQSBatchResponse(failures);
    }
}
```

Lambda deletes all successfully processed messages from SQS and leaves only the failing messages to retry according to the redrive policy.

---

## 14. ECS Task Roles and Least Privilege

In an ECS-based asynchronous backend, enforce strict role separation:

```text
+------------------------------------------------------------------------+
|                            ECS Task Sandbox                            |
|                                                                        |
|  +------------------------------------------------------------------+  |
|  | Task Execution Role (Infrastructure Level)                       |  |
|  | - ecr:GetAuthorizationToken                                       |  |
|  | - ecr:BatchGetImage                                               |  |
|  | - logs:CreateLogStream, logs:PutLogEvents                         |  |
|  | - ssm:GetParameters / secretsmanager:GetSecretValue (Environment) |  |
|  +------------------------------------------------------------------+  |
|                                                                        |
|  +------------------------------------------------------------------+  |
|  | Task Role (Application Logic Level)                              |  |
|  | - sqs:ReceiveMessage, sqs:DeleteMessage (on orders-queue only)   |  |
|  | - s3:PutObject (on orders-bucket/invoices/* only)                |  |
|  | - kms:Decrypt (on application KMS key only)                      |  |
|  +------------------------------------------------------------------+  |
+------------------------------------------------------------------------+
```

Never grant ECS tasks broad permissions like `sqs:*` or `s3:*`. Restrict ARNs to specific queue names and bucket prefixes.

---

## 15. Practical Design Exercise: Order Notifications Architecture

Let us construct a production-grade asynchronous order processing architecture:

```text
                     +-----------------------------------+
                     |     Spring Boot Order Service     |
                     |         (ECS Fargate Task)        |
                     +-----------------+-----------------+
                                       |
                   1. Commit Order + Outbox Record
                                       v
                     +-----------------------------------+
                     |       Amazon RDS PostgreSQL       |
                     |  orders table + outbox table      |
                     +-----------------+-----------------+
                                       |
                   2. CDC / Scheduled Outbox Poller
                                       v
                     +-----------------------------------+
                     |        Amazon EventBridge         |
                     |         Domain Event Bus          |
                     +-----------------+-----------------+
                                       |
                     3. Event Rule Filter ("OrderPlaced")
                                       v
                     +-----------------------------------+
                     |          Amazon SNS Topic         |
                     |         "orders.placed"           |
                     +--------+-----------------+--------+
                              |                 |
                   Fan-Out    |                 | Fan-Out
                              v                 v
            +-------------------+             +-------------------+
            |  SQS Email Queue  |             |  SQS Analytics Q  |
            +---------+---------+             +---------+---------+
                      |                                 |
                      v                                 v
            +-------------------+             +-------------------+
            |   Email Worker    |             | Analytics Worker  |
            |   (ECS Fargate)   |             |   (AWS Lambda)    |
            +-------------------+             +-------------------+
```

### Architectural Resilience Properties

1. **Email worker outage:** If the email worker process crashes, messages safely buffer in the SQS Email Queue for up to 14 days without dropping notifications or affecting the API.
2. **Analytics failure isolation:** If the analytics worker encounters a bug, it retries and eventually shunts failed records to its DLQ. The email worker and core order flow continue uninterrupted.
3. **Database safety:** Downstream consumers interact only with SQS, protecting PostgreSQL from sudden burst traffic spikes.

---

## 16. Hands-On Lab Without Provisioning AWS Resources

### Task A: Define the Domain Event
Draft a canonical, versioned JSON domain event payload:

```json
{
  "specversion": "1.0",
  "id": "f20e9e7c-2c8d-4c1b-a6bd-21f0f1b2a100",
  "source": "https://api.orders.example.com",
  "type": "com.example.orders.OrderPlaced",
  "datacontenttype": "application/json",
  "time": "2026-10-23T08:00:00Z",
  "data": {
    "orderId": "order-8931",
    "customerId": "cust-5021",
    "currency": "USD",
    "totalAmount": 149.99,
    "items": [
      { "sku": "SKU-PRO-01", "quantity": 1, "unitPrice": 149.99 }
    ]
  }
}
```

*Design rationale:* Stable event UUID (`id`) guarantees consumer deduplication; explicit `type` enables EventBridge rule routing; schema follows CloudEvents open standards.

### Task B: Consumer Logic Pseudocode
```python
def handle_sqs_message(record):
    event = json.loads(record.body)
    event_id = event["id"]

    with db.transaction():
        # Check idempotency
        if db.query("SELECT 1 FROM processed_events WHERE id = %s", event_id):
            logger.info(f"Event {event_id} already processed. Skipping.")
            return

        # Perform business operation
        send_order_email(event["data"])

        # Persist idempotency record
        db.execute("INSERT INTO processed_events (id) VALUES (%s)", event_id)

    sqs.delete_message(ReceiptHandle=record.receipt_handle)
```

### Task C: Crash Simulation
If the worker crashes after `send_order_email()` but before `sqs.delete_message()`:
1. SQS visibility timeout expires.
2. Message is redelivered to another worker.
3. The new worker checks `processed_events`.
4. *Correction note:* If the email provider is external, the email might be sent twice unless an external idempotency key is passed to the email API! Always forward the `event_id` as the email provider's `Idempotency-Key` header.

### Task D: DLQ & Redrive Plan
- Set `maxReceiveCount = 3`.
- Set `VisibilityTimeout = 120s`.
- Configure CloudWatch alarm on `ApproximateNumberOfMessagesVisible` on DLQ $> 0$.
- Diagnostic runbook: inspect DLQ message attributes, fix parsing bug in codebase, deploy patch, and initiate redrive via SQS StartMessageMoveTask API.

### Task E: AWS Service Selection
1. **Buffer image-processing jobs:** Amazon SQS Standard Queue.
2. **Notify multiple independent systems of published events:** Amazon SNS Topic fanning out to multiple SQS queues.
3. **Route events based on payload metadata:** Amazon EventBridge.
4. **Execute lightweight code on S3 file upload:** AWS Lambda.
5. **Run a high-throughput, continuously listening Spring Boot REST API:** Amazon ECS with AWS Fargate.

---

# Layer 3 — Production Engineering & Interview Mastery

## 17. Production Incident Simulations

### Incident A: Queue Depth Grows Continuously

**Symptoms:** CloudWatch metric `ApproximateNumberOfMessagesVisible` on the orders queue rises steadily from 50 to 100,000 messages.

- **Investigation:**
  1. Inspect consumer task count: Are ECS worker tasks running and healthy?
  2. Inspect consumer logs: Are tasks crashing or encountering database connection timeouts?
  3. Inspect consumer CPU and memory: Are workers CPU-throttled?
  4. Inspect visibility timeout: Is the timeout too short, causing tasks to time out and re-enqueue messages in a loop?
  5. Check downstream database: Is PostgreSQL saturated with lock contention?
- **Resolution:**
  - If workers are healthy but overwhelmed, scale out ECS task count.
  - If downstream database is saturated, throttle consumer concurrency and optimize queries.
  - Fix any recurring transient exception that is resetting the visibility timeout.

---

### Incident B: Customer Receives Duplicate Order Confirmation Emails

**Symptoms:** Multiple customer support tickets report receiving 3 to 5 identical order confirmation emails for a single checkout.

- **Root Cause:**
  1. The worker process sends the email via external API (takes 2,500 ms).
  2. SQS visibility timeout was misconfigured to 2,000 ms.
  3. SQS marks the message visible while the first worker is still finalizing the network call.
  4. Worker 2 receives the message and sends another email.
- **Resolution:**
  1. Increase SQS queue `VisibilityTimeout` to 30 seconds.
  2. Pass `orderId` or `eventId` as the idempotency key to the email provider API.
  3. Record the idempotency entry in PostgreSQL before or during the send operation.

---

### Incident C: Lambda Invocations Fail Under Spike, Crashing Database

**Symptoms:** Marketing sends a push notification. SQS receives 50,000 messages in 10 seconds. Lambda scales to 1,000 concurrent executions. RDS PostgreSQL crashes with `FATAL: remaining connection slots are reserved for non-replication superuser connections`.

- **Root Cause:** SQS triggered Lambda without concurrency throttling. 1,000 concurrent Lambda instances opened 1,000 simultaneous connections to RDS, completely exhausting PostgreSQL `max_connections` (150).
- **Resolution:**
  1. Set **Reserved Concurrency** on the Lambda function to 20 to limit simultaneous database connections.
  2. Implement **Amazon RDS Proxy** between Lambda and PostgreSQL to pool and reuse connections.
  3. Configure SQS ESM maximum concurrency controls.

---

### Incident D: ECS Deployment Replaces Tasks, Causing Total API Outage

**Symptoms:** ECS service initiates a rolling update (`orders-api:2.0.0`). Within 2 minutes, the ALB returns HTTP 503 Service Unavailable for 100% of incoming traffic.

- **Root Cause:** The new task definition specified an environment variable that failed decryption, causing Spring Boot to terminate immediately on startup (`CrashLoopBackOff`). The ECS service had `minimumHealthyPercent` configured to `0`, allowing ECS to terminate all running 1.0.0 tasks before verifying that 2.0.0 tasks were healthy.
- **Resolution:**
  1. Set `minimumHealthyPercent: 100` and `maximumPercent: 200` to guarantee that existing capacity remains active until new tasks pass ALB target health checks.
  2. Roll back immediately to task definition revision `orders-api:1.4.0`.
  3. Fix the missing KMS decryption permission on the Task Role.

---

### Incident E: A Poison-Pill Message Blocks Queue Processing

**Symptoms:** SQS message throughput drops to near-zero. CPU on worker tasks is 100%.

- **Root Cause:** A client sent an order containing an unexpected null character that causes an unhandled `NullPointerException` in the JSON parser. The queue had no DLQ configured (`maxReceiveCount` was disabled), so the message was retried infinitely every time the visibility timeout expired.
- **Resolution:**
  1. Attach a Dead-Letter Queue with `maxReceiveCount = 3`.
  2. Add robust input validation and wrap message parsing in a `try-catch` block that discards or dead-letters malformed payloads.

---

### Incident F: Database Commits Order, but Downstream Consumers Never Hear About It

**Symptoms:** Orders are stored in PostgreSQL, but warehouse fulfillment is never triggered.

- **Root Cause:** Dual-write bug. The application executed `orderRepository.save(order)` and then attempted `snsClient.publish(...)`. During a network blip to AWS, the SNS call threw an exception. The DB transaction was already committed, leaving the order orphaned without an event.
- **Resolution:**
  1. Implement the **Transactional Outbox Pattern**: write the event to an `outbox` table in the same DB transaction.
  2. Run a resilient CDC or poller service that guarantees at-least-once publication to SNS/EventBridge.

---

## 18. Seven Production Engineering Principles

1. **Design for At-Least-Once Delivery:** Always assume messages can be duplicated, delayed, or reordered. Idempotency is non-negotiable.
2. **Never Perform Dual Writes Directly:** Never update a database and publish to a network broker as two independent, uncoordinated steps. Use the Transactional Outbox pattern.
3. **Queue Age Is More Important Than Queue Depth:** A queue with 1,000 messages processing in 500 ms is healthy; a queue with 10 messages that have been stuck for 4 hours is an active production incident. Monitor CloudWatch `ApproximateAgeOfOldestMessage`.
4. **Isolate Workloads with Fan-Out:** Never let slow or non-critical consumers (e.g., analytics) share a queue with mission-critical consumers (e.g., payment/fulfillment).
5. **Enforce Backpressure and Concurrency Limits:** Protect stateful databases from serverless compute spikes using connection pools, RDS Proxy, and concurrency caps.
6. **Treat Event Contracts as APIs:** Events are public schemas. Version event payloads (`v1`, `v2`) and ensure backward compatibility before modifying fields.
7. **Make Dead-Letter Queues Actionable:** Never let DLQs become data graveyards. Configure automated alarms, build replay tooling (`aws sqs start-message-move-task`), and inspect failure headers.

---

## 19. FAANG-Style Interview Questions and Answers

### Q1. What is Amazon ECS?
Amazon Elastic Container Service is a fully managed container orchestration service that executes, scales, and manages Docker/OCI containers across EC2 instances or AWS Fargate.

### Q2. What is the difference between ECS on EC2 and ECS on Fargate?
With ECS on EC2, you manage the underlying virtual machines, host OS, and cluster capacity. With AWS Fargate, AWS provisions and manages the serverless compute infrastructure, allowing you to pay strictly for the CPU and memory allocated per task.

### Q3. What is an ECS task definition?
A declarative JSON blueprint defining one or more containers, their Docker image repositories, CPU/memory limits, port mappings, environment variables, storage mounts, and IAM roles.

### Q4. What is the difference between an ECS Task Role and an Task Execution Role?
The Task Role provides AWS credentials to the application container code (e.g., S3/DynamoDB access). The Task Execution Role is used by the ECS container agent to perform infrastructure tasks like pulling private ECR images and writing logs to CloudWatch.

### Q5. What is AWS Lambda?
A serverless event-driven compute platform that executes stateless code in response to events, automatically managing server provisioning, OS patching, and concurrency scaling.

### Q6. When would you choose ECS Fargate over AWS Lambda?
Choose ECS Fargate for long-running processes, complex Spring Boot monoliths with heavy startup times, consistent high-throughput traffic, or services requiring raw TCP listening sockets.

### Q7. What is Amazon SQS?
A distributed, fully managed message queuing service designed to decouple and scale microservices, distributed systems, and serverless applications via asynchronous message buffering.

### Q8. What is the difference between SQS Standard and SQS FIFO queues?
Standard queues provide best-effort ordering and at-least-once delivery with nearly unlimited throughput. FIFO queues preserve strict order within message groups, guarantee deduplication, but have lower default throughput limits.

### Q9. What is an SQS Visibility Timeout?
The duration during which a message is hidden from other workers after being retrieved by a consumer. If the consumer fails to delete the message before the timeout expires, it becomes visible again for other consumers to process.

### Q10. What is a Dead-Letter Queue (DLQ)?
A secondary queue attached to a source queue or Lambda function that isolates messages that repeatedly fail processing after a configured number of retries (`maxReceiveCount`).

### Q11. What is Amazon SNS?
A fully managed pub/sub messaging service that coordinates the delivery of messages from publishers to multiple subscribing endpoints (fan-out).

### Q12. What is Amazon EventBridge?
A serverless event bus service that ingests events from applications, SaaS integrations, and AWS services, routing them to targets based on content-matching rules.

### Q13. When should you use SQS instead of SNS?
Use SQS when a single consumer needs to pull and buffer work to process at its own pace. Use SNS when a publisher needs to broadcast an event immediately to multiple independent subscribers.

### Q14. What is the difference between Amazon SNS and Amazon EventBridge?
SNS is optimized for high-throughput, low-latency pub/sub fan-out (primarily to SQS or webhooks). EventBridge is an enterprise event bus supporting complex JSON content filtering, schema registries, and native SaaS integrations.

### Q15. What is the dual-write problem?
The architectural hazard where an application attempts to write to a local database and publish to a message broker without distributed transaction coordination, leading to data inconsistency if one operation fails.

### Q16. How does the Transactional Outbox pattern prevent lost events?
By writing the business entity and an outbox event record within the same ACID database transaction. A separate, resilient process reads the outbox table and publishes events to the broker with guaranteed delivery.

### Q17. Does the Transactional Outbox pattern guarantee exactly-once message delivery?
No. If the outbox publisher crashes after publishing but before updating the outbox table, it will publish the message again upon restart. It guarantees at-least-once delivery; consumers must be idempotent.

### Q18. How do you implement idempotency in a distributed consumer?
By storing unique event IDs in a relational database table with a unique primary key constraint inside the same database transaction that updates business state. If a duplicate arrives, the unique constraint violation safely skips processing.

### Q19. Why can scaling consumer concurrency degrade overall system throughput?
Excessive concurrency can overwhelm downstream shared dependencies (such as PostgreSQL connection limits or third-party API rate limits), causing timeouts, retry storms, and connection exhaustion.

### Q20. How would you design a scalable, fault-tolerant order notification system?
Use Spring Boot with the Transactional Outbox pattern on Amazon RDS PostgreSQL; emit events to Amazon EventBridge; fan out via Amazon SNS to dedicated SQS queues for Email, Fulfillment, and Analytics; and process queues with idempotent workers running on ECS Fargate with DLQs and CloudWatch alarms.

---

## 20. Mastery Challenge

Design an asynchronous order-processing system with these requirements:

- Orders are stored in PostgreSQL.
- Email and fulfillment process independently.
- A temporary downstream outage must not immediately fail order creation.
- Duplicate event delivery must not create duplicate fulfillment.
- Failed messages must be diagnosable and recoverable.
- The system must expose processing delay and failure metrics.

Complete these tasks:

1. **Architecture diagram:** Client $\to$ ALB $\to$ ECS Orders API $\to$ PostgreSQL (Orders + Outbox tables) $\to$ Outbox Poller $\to$ EventBridge $\to$ SNS Topic $\to$ SQS Queues (Email & Fulfillment) $\to$ Workers.
2. **Compute choice for workers:** ECS Fargate for high-throughput fulfillment; Lambda for bursty email notifications.
3. **Messaging workflow:** EventBridge for domain event routing; SNS for fan-out; SQS for consumer isolation and buffering.
4. **Preventing lost publication:** Transactional Outbox commits order and outbox record atomically in PostgreSQL.
5. **Enforcing idempotency:** Workers insert event UUID into `processed_events` table before executing side effects; skip on duplicate key violation.
6. **Retry & DLQ parameters:** `VisibilityTimeout = 90s`, `maxReceiveCount = 4`, with dedicated DLQ and alarm.
7. **Crash recovery scenario:** If worker crashes post-side-effect, idempotency check prevents duplicate fulfillment on redelivery; external API calls must pass idempotency keys.
8. **Replaying DLQ messages:** Fix bug, verify schema, initiate SQS message move task back to primary queue.
9. **Backlog metrics:** CloudWatch `ApproximateAgeOfOldestMessage` (latency signal) and `ApproximateNumberOfMessagesVisible` (queue depth).
10. **Protecting PostgreSQL from traffic surges:** Use RDS Proxy, set maximum task counts on ECS consumer services, and tune HikariCP connection pool limits.

### Self-assessment

Score each item from 0 to 2:

| Skill | Score |
|---|---:|
| ECS, Fargate, and Lambda distinctions | /2 |
| SQS, SNS, and EventBridge separation | /2 |
| Queue delivery and visibility timeout | /2 |
| Idempotency and safe retries | /2 |
| Transactional outbox pattern | /2 |
| Dead-letter handling and redrive | /2 |
| IAM task roles and least privilege | /2 |
| Production troubleshooting & backpressure | /2 |

**Target:** At least 13/16, with no zero in idempotency, retries, or the transactional outbox.

---

## Chapter Completion Protocol

**Chapter:** AWS Chunk 5 of 6

**Save as:** `content/aws/05-aws-containers-serverless-messaging-event-driven-architecture.md`

Do not generate a PDF yet. After all six AWS chapters are saved and verified, generate one complete AWS handbook:

`docs/aws/BEH_AWS_COMPLETE_HANDBOOK.pdf`

After verifying all source chapters and the final PDF, use the intended Git commit message:

`AWS done`

**Next chapter:** AWS Chunk 6 of 6 — Production Security, Observability, CI/CD, Reliability, Cost Engineering & Final Architecture Capstone.
