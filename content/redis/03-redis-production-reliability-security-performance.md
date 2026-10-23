# Redis — Chunk 3: Production Reliability, Security, Performance & Incident Mastery
## Backend Engineering Tools & Infrastructure Handbook

**Phase:** II — Backend Infrastructure  
**Chunk:** 3 of 3  
**Source file:** `content/redis/03-redis-production-reliability-security-performance.md`

---

## Learning Objectives

By the end of this chapter, you should be able to:

- Design a reliable Redis integration for a Spring Boot backend.
- Diagnose hot keys, slow commands, connection exhaustion, and latency spikes.
- Explain pipelining, transactions, atomic commands, and Lua scripting.
- Implement a basic Redis-backed rate limiter.
- Understand Redis replication, Sentinel, and Cluster at a conceptual level.
- Apply practical Redis security and observability controls.
- Respond systematically to Redis-related production incidents.
- Defend caching, rate limiting, and coordination trade-offs in SDE-1 interviews.

---

# Layer 1 — Fundamentals & Mental Models

## 1. Redis in a Production Architecture

In production, Redis is not just a fast key-value store. It is an infrastructure dependency that introduces its own failure modes, capacity constraints, and operational responsibilities.

Consider a Spring Boot service backed by PostgreSQL:

```text
                    Client
                      |
                      v
                  Nginx / LB
                      |
                      v
                Spring Boot API
                   /       \
                  v         v
               Redis    PostgreSQL
             cache and   source of
             counters      truth
```

Redis might support:

- Caching frequently requested product data.
- Rate limiting requests.
- Storing short-lived verification state.
- Tracking counters and selected ephemeral state.
- Coordinating certain distributed workflows.

PostgreSQL remains the authoritative source for business records in this example.

The application must still define what happens when Redis is slow, unavailable, full, or returning stale data.

### The three questions for every Redis integration

Before adding Redis to an endpoint, answer:

1. **Correctness:** What happens if the value is missing, stale, or evicted?
2. **Reliability:** What happens if Redis cannot be reached?
3. **Performance:** Does Redis reduce total request cost, or introduce another bottleneck?

If these questions have no clear answers, the integration is not production-ready.

## 2. Atomicity: Why Separate Commands Can Be Dangerous

Suppose an application implements a counter using two operations:

```redis
GET page:home:views
```

Then the application increments the result and writes it back:

```redis
SET page:home:views 101
```

Two requests can read the same old value and overwrite each other's updates.

```text
Initial value = 100

Request A reads 100
Request B reads 100

Request A writes 101
Request B writes 101

Expected: 102
Actual:   101
```

This is a lost update.

Use Redis's atomic increment operation instead:

```redis
INCR page:home:views
```

Redis executes each individual command atomically with respect to other commands on the server. That does not mean an arbitrary sequence of commands is automatically atomic.

### Key distinction

- `INCR`: one atomic increment operation.
- `GET` followed by `SET`: two separate operations with a race window.
- A Lua script: can execute a group of Redis operations atomically on the server.
- `MULTI`/`EXEC`: queues and executes a transaction's commands together, but does not provide rollback semantics like a relational database transaction.

Use the smallest mechanism that satisfies the correctness requirement.

## 3. Pipelining vs. Transactions vs. Lua

These three mechanisms solve different problems.

### Pipelining
Sends multiple commands over the network without waiting for each response before sending the next. This significantly reduces network round trips and socket I/O overhead.
- **Use when:** Commands can be issued independently and you want to reduce batch network latency.
- **Limitation:** Does not guarantee atomicity; other clients' commands can interleave between pipelined commands on the server.

### Transactions — `MULTI` / `EXEC`
Queues multiple commands on the server and executes them sequentially as a single block without other clients' commands interleaving between the queued commands during execution.
- **Use when:** Multiple commands must execute sequentially without interruption.
- **Limitation:** Does not provide relational-style rollback for runtime command errors (commands after a runtime failure will still execute).

### Lua Scripting
Runs procedural application logic directly on the Redis server as a single atomic operation relative to other Redis commands.
- **Use when:** Complex conditional logic, branching, or read-then-write decisions must happen atomically (e.g., checking and incrementing a rate-limit counter).
- **Limitation:** Long-running Lua scripts block the entire Redis server event loop while running.

### Example: pipelining

Suppose an application needs to read 100 independent keys.

Without pipelining, it may perform 100 request-response round trips. With pipelining, it can send commands in batches and collect their responses.

Pipelining reduces network overhead but does not make the entire batch a transaction. Other clients may execute commands between the pipelined commands.

### Example: transaction

```redis
MULTI
INCR order:9001:attempts
EXPIRE order:9001:attempts 3600
EXEC
```

The queued commands execute together when `EXEC` runs. This is useful when you need to group operations, but understand the limitations:

- Commands are queued before execution.
- Runtime errors do not automatically roll back all successful commands.
- A transaction does not create a general-purpose atomic transaction spanning Redis and PostgreSQL.

For more complicated conditional operations, Lua or a suitable optimistic-locking design may be more appropriate.

## 4. Hot Keys and Hot Partitions

A hot key is a key receiving disproportionately high traffic.

Example:

```text
product:popular-item
```

Suppose a product becomes viral and millions of requests access the same key.

Even when Redis handles the command efficiently, the concentrated request volume can cause bottlenecks in the application, network, or Redis deployment.

In a Redis Cluster, a hot key is especially important because a key maps to a single hash slot, which is served by one cluster shard at a time.

### Common mitigations

- Cache at an upstream layer where appropriate.
- Use local in-process caching for carefully selected, tolerably stale data.
- Reduce redundant reads through request coalescing.
- Avoid fetching oversized values.
- Consider distributing read load when the data model and consistency requirements permit it.
- Investigate whether a single key is being used as a global counter or coordination bottleneck.

Do not split a key into multiple independent counters without designing how to aggregate them correctly. Distribution may improve throughput but complicate reads and updates.

## 5. Connection Pools and Latency

A Redis request usually involves more than executing a command.

The application may need to:

1. Acquire a connection.
2. Send the command over the network.
3. Wait for Redis to execute it.
4. Read the response.
5. Deserialize the result.
6. Release the connection.

A slow API can therefore be caused by connection acquisition, network latency, Redis processing, or application-side work.

### Common warning signs

- Connection-pool wait time rises.
- Redis command latency remains low, but API latency is high.
- Many requests time out simultaneously.
- Client connections increase sharply.
- Large responses cause excessive processing.
- Slow database fallbacks follow cache misses.

Increasing the connection pool without investigating can make things worse. More concurrent requests may increase resource pressure on Redis and the application.

Tune pool sizes, timeouts, and concurrency using measured workload behavior.

## 6. Redis Replication, Sentinel, and Cluster

These concepts address different operational needs.

| Capability | Main purpose | Important limitation |
|---|---|---|
| Replication | Copies data from a primary to replicas | Replication is generally asynchronous and does not guarantee zero data loss |
| Sentinel | Monitors a non-clustered Redis primary/replica setup and supports automatic failover | It does not shard the dataset |
| Redis Cluster | Partitions the keyspace across shards and provides replication and failover mechanisms | Adds operational and application-design complexity |

### Replication

A primary processes writes and replicates changes to replicas. Replicas can support selected read workloads, but replication lag can make replica reads stale.

### Sentinel

Sentinel monitors Redis instances, helps detect primary failures, and coordinates failover. Clients must support the appropriate discovery and reconnection behavior.

### Cluster

Redis Cluster partitions keys into hash slots distributed across multiple primary nodes. Replicas can provide redundancy and failover.

Cluster introduces considerations such as:

- Key placement.
- Multi-key operations and hash slots.
- Client redirection.
- Resharding.
- Hot shards.
- Partial failures.

For a small backend project, a single Redis instance may be sufficient. For a production service with explicit availability or capacity requirements, choose the topology based on measured needs rather than assuming a cluster is always better.

---

# Layer 2 — Practical Engineering & Workflows

## 7. Implement a Basic Redis Rate Limiter

Rate limiting controls how frequently a caller can perform an operation.

Example policy:

> Allow at most 100 requests per user per minute.

A simple fixed-window design stores a counter for each user and time window.

Key:

```text
rate:user:87:202610230930
```

The timestamp here is illustrative; the actual key should be derived from the application's chosen window boundaries.

### Basic command sequence

A naive implementation might do this:

```redis
INCR rate:user:87:window
EXPIRE rate:user:87:window 60
```

The counter increments atomically, but these two separate commands create a failure window. If the increment succeeds and the process fails before setting the expiry, the key could remain without a TTL.

A stronger implementation should ensure that the counter and its expiry are managed together.

### Lua implementation

The following script increments a counter and establishes an expiry on the first increment:

```lua
local current = redis.call("INCR", KEYS[1])

if current == 1 then
    redis.call("EXPIRE", KEYS[1], ARGV[1])
end

return current
```

Call it with:
- `KEYS[1]`: the rate-limit counter key.
- `ARGV[1]`: the window duration in seconds.

The script executes atomically relative to other Redis commands. If the first increment occurs, it sets the expiry before returning.

### Application decision

The application compares the returned count against the configured limit.

```text
count <= 100  -> Allow
count > 100   -> Reject or throttle
```

A typical API may return HTTP `429 Too Many Requests` when the limit is exceeded.

### Fixed-window trade-off

A fixed window can permit a burst near a boundary. A client might consume most of its allowance just before a window ends and then immediately consume the next window's allowance.

For stricter rate limiting, consider sliding-window or token-bucket approaches. Each has different complexity, memory, and burst-control characteristics.

**Security note:** do not trust a caller-supplied user ID as the rate-limit identity without authenticating and validating it. For unauthenticated endpoints, consider appropriate IP- or token-based controls, accounting for proxies and shared addresses.

## 8. A Spring Boot Rate-Limiter Workflow

A clean design separates Redis operations from HTTP policy.

```text
Incoming HTTP request
        |
        v
Authentication / identity resolution
        |
        v
RateLimitService
        |
        v
Atomic Redis counter
        |
        v
Compare with configured limit
        |
        +---- Within limit --> Continue
        |
        +---- Over limit ----> HTTP 429
```

A simplified service contract might look like this:

```java
public interface RateLimitService {
    long recordRequest(String subject, Duration window);
}
```

The implementation would call the Lua script using Spring Data Redis and return the count. A filter or interceptor would enforce the configured limit.

Design decisions to document:

- What identifies a caller?
- Is the limit per user, API key, tenant, or IP address?
- What is the time window?
- What happens if Redis is unavailable?
- How are limits applied consistently across multiple API instances?
- Are retry headers or reset information returned to clients?

A Redis-backed counter can coordinate rate limiting across application instances, unlike an ordinary in-memory counter in each process.

However, rate limiting is a security and availability control. If Redis fails, allowing all traffic may create an overload risk; rejecting all traffic may cause an outage. The appropriate fallback depends on the endpoint and threat model.

## 9. Diagnose Redis with CLI Commands

Start with basic health:

```bash
redis-cli PING
```

Inspect server information:

```bash
redis-cli INFO server
redis-cli INFO memory
redis-cli INFO stats
redis-cli INFO clients
redis-cli INFO persistence
```

Inspect slow commands:

```bash
redis-cli SLOWLOG GET 10
```

Inspect latency events:

```bash
redis-cli LATENCY LATEST
```

The latency-monitoring command depends on the server's configuration and permissions.

### Important diagnostic distinction

A command recorded in the Redis slow log indicates that server-side execution crossed the configured slow-log threshold. It does not capture the full end-to-end time spent waiting for a connection or traversing the network.

Therefore, compare:

- Application-side Redis latency.
- Redis server-side command latency.
- Connection-pool wait time.
- Network latency.
- API endpoint latency.

This comparison helps isolate where time is being spent.

## 10. Monitor Key-Level Memory and Keyspace Behavior

For a known key:

```redis
MEMORY USAGE product:1042:details
TTL product:1042:details
TYPE product:1042:details
```

These commands help answer:
- What data structure is stored?
- How much memory does this key use?
- Does it have an expiry?

Use incremental key iteration for operational exploration:

```redis
SCAN 0 MATCH product:* COUNT 100
```

`COUNT` is a work hint, not a guarantee that exactly 100 keys will be returned. Continue from the returned cursor until iteration completes.

Do not use broad key scans as a routine per-request application operation.

### Example: unexpected key growth

Suppose Redis memory rises continuously.

A useful investigation sequence:

1. Inspect memory and keyspace statistics.
2. Check whether expected TTLs are present.
3. Search for a known key family using `SCAN`.
4. Inspect representative keys with `MEMORY USAGE`.
5. Identify which application feature creates them.
6. Check whether cleanup or expiry behavior changed.
7. Correct the creation or lifecycle bug.
8. Confirm memory growth stabilizes.

Avoid deleting large groups of keys before understanding their purpose.

## 11. Redis Security: A Practical Checklist

Redis is commonly deployed as an internal service. It should not be exposed indiscriminately to the public internet.

### Network controls

- Restrict access to authorized application networks.
- Bind and firewall the service appropriately.
- Use private connectivity for managed Redis deployments.
- Use TLS when required by the deployment's security architecture.

### Authentication and authorization

- Configure authentication and ACLs where supported.
- Give each application only the permissions it needs.
- Separate application access from administrative access.
- Rotate credentials and keep them out of source control.

### Application controls

- Avoid logging credentials or sensitive cached values.
- Validate and constrain cache-key inputs.
- Use safe serialization formats and configurations.
- Set appropriate TTLs for sensitive transient data.
- Consider data residency and retention requirements.
- Avoid treating possession of a cache key as authorization to access a business resource.

A private network alone is not a complete security boundary.

## 12. Spring Boot Reliability Settings

A production Redis integration should define connection behavior explicitly.

Example configuration shape:

```yaml
spring:
  data:
    redis:
      host: ${REDIS_HOST:localhost}
      port: ${REDIS_PORT:6379}
      connect-timeout: ${REDIS_CONNECT_TIMEOUT:2s}
      timeout: ${REDIS_COMMAND_TIMEOUT:2s}
```

Verify the exact property names and supported values against the Spring Boot version in your project. The values shown are illustrative starting points, not universal production recommendations.

Consider the following when tuning:

- Connection timeout.
- Command timeout.
- Connection-pool size and acquisition behavior.
- Retry policy.
- Reconnection behavior.
- Serialization overhead.
- Application concurrency.
- The consequence of falling back to PostgreSQL.

Retries need particular care. A timed-out command may already have executed on Redis even though the client did not receive its response. Blindly retrying a non-idempotent operation can apply it twice.

For example, retrying `INCR` after an ambiguous timeout can increment the counter twice. Idempotency or operation-specific retry logic may be required.

## 13. Reliability Patterns for Redis Clients

### Bounded timeouts

A request should not wait indefinitely for Redis. Timeouts should fit within the overall API latency budget.

### Controlled retries

Use bounded retries and backoff where appropriate. Do not create retry storms during a Redis outage.

### Bulkheads and concurrency limits

Limit how many requests can concurrently depend on a failing Redis service. This can prevent resource exhaustion from spreading through the application.

### Circuit breakers

A circuit breaker can temporarily stop repeated attempts to call an unhealthy dependency. It must be configured carefully: bypassing Redis can increase database traffic, and rate limiting may have different fallback requirements from ordinary caching.

### Observability

Record failures, latency, timeout counts, and fallback activity. A degraded cache should not remain invisible until PostgreSQL becomes overloaded.

---

# Layer 3 — Production Engineering & Interview Mastery

## 14. Incident Simulation: API Latency Suddenly Increases

### Symptoms

- API p95 latency rises from 80 ms to 900 ms.
- Redis is reachable.
- PostgreSQL CPU increases.
- Cache hit ratio drops.

### Investigation

**Step 1 — Verify Redis health**

```bash
redis-cli PING
redis-cli INFO stats
redis-cli INFO memory
```

**Step 2 — Check the application's Redis metrics**

Inspect:
- Command latency.
- Connection-pool acquisition time.
- Redis timeouts.
- Cache hits and misses.

**Step 3 — Check for key changes**

A deployment may have changed the cache-key prefix or serialization format, causing misses for every request.

**Step 4 — Inspect expiry and eviction behavior**

Check whether keys expire too quickly or are being evicted under memory pressure.

**Step 5 — Protect the database**

If fallback traffic is overwhelming PostgreSQL, apply the service's approved concurrency controls, load shedding, or temporary traffic restrictions.

### Resolution criteria

Do not consider the incident resolved merely because Redis responds to `PING`.

Verify:
- Cache hit ratio recovers.
- PostgreSQL load returns toward baseline.
- API p95 latency improves.
- Error rates stabilize.
- No correctness regression was introduced by the mitigation.

## 15. Incident Simulation: Redis Is Unavailable

### Symptoms

- Connection timeouts rise.
- API requests begin failing or slowing down.
- PostgreSQL traffic may increase.

### Response

1. Determine whether the failure is limited to one application instance or affects the Redis service.
2. Check service health, network connectivity, connection limits, and recent changes.
3. Determine whether the application is falling back to PostgreSQL.
4. Protect the database if fallback traffic is excessive.
5. Restore connectivity or follow the managed service's failover procedure.
6. Verify client reconnection behavior.
7. Confirm cache recovery and normal traffic distribution.

### Design review

Before the incident, the team should have decided:

- Which endpoints may bypass the cache.
- Which operations require Redis to enforce a security or traffic policy.
- How fallback load is controlled.
- Whether the cache is rebuildable.
- How to detect a Redis outage quickly.

A cache outage and a rate-limiter outage are not necessarily equivalent. Failing open may be reasonable for a noncritical cache but unsafe for some abuse-sensitive endpoints.

## 16. Incident Simulation: A Hot Key Overloads Redis

### Symptoms

- One key receives extreme request volume.
- Application latency increases.
- Redis command processing or network utilization rises.
- Most unrelated keys may still behave normally.

### Investigation

1. Identify the popular resource or operation from application metrics.
2. Determine whether requests are concentrated on one Redis key.
3. Inspect value size and command type.
4. Check whether each request unnecessarily retrieves a large payload.
5. Determine whether upstream or local caching is safe.
6. Evaluate whether read traffic can be distributed without violating consistency requirements.

### Possible mitigations

- Reduce duplicate reads.
- Cache at a suitable upstream layer.
- Use local caching with an explicit staleness policy.
- Split independent data where the model permits it.
- Avoid using one key as a global coordination point.

The mitigation should preserve the semantics of the data. A global counter, inventory value, and public product description have very different requirements.

## 17. Incident Simulation: Rate Limiting Stops Working

### Symptoms

- Clients exceed their expected limits.
- Rate-limit counters disappear unexpectedly.
- Different application instances enforce inconsistent limits.

### Investigation

1. Verify the key format and caller identity.
2. Check counter TTLs.
3. Confirm that all application instances use the same Redis deployment and policy.
4. Check script or command failures.
5. Review retry behavior and timeout handling.
6. Determine whether counters are being evicted or reset during failover.
7. Confirm that the API enforcement code interprets the counter correctly.

### Prevention

- Test concurrent requests.
- Ensure counter creation and expiry are handled atomically.
- Monitor script failures and rate-limit decisions.
- Define behavior during Redis failover.
- Ensure user-controlled identifiers cannot bypass or poison rate-limit keys.

A rate limiter is only as correct as its identity model, counter logic, expiry policy, and failure behavior.

## 18. Redis Performance Optimization Checklist

Before making changes, establish a baseline.

### Application layer

- [ ] Measure cache hit and miss ratios.
- [ ] Measure connection acquisition and command latency.
- [ ] Avoid unnecessary round trips.
- [ ] Avoid fetching large payloads when only a small field is required.
- [ ] Check serialization and deserialization cost.
- [ ] Use pipelining when commands are independent and batching is beneficial.
- [ ] Apply concurrency limits when needed.

### Redis layer

- [ ] Inspect memory usage and eviction statistics.
- [ ] Check slow-log entries and latency events.
- [ ] Investigate hot keys and oversized values.
- [ ] Review persistence overhead if persistence is enabled.
- [ ] Verify that commands are appropriate for the data structure.
- [ ] Avoid expensive full-keyspace operations in latency-sensitive paths.

### System layer

- [ ] Measure network latency between application and Redis.
- [ ] Verify that the deployment has adequate CPU and memory.
- [ ] Inspect connection counts and resource limits.
- [ ] Review failover and reconnect behavior.
- [ ] Load-test both warm-cache and cold-cache scenarios.

Optimize the bottleneck demonstrated by measurements, not the component that seems most interesting.

## 19. Redis and Kafka Are Not Interchangeable

Both systems can participate in distributed backend architectures, but their primary roles differ.

| Redis | Kafka |
|---|---|
| In-memory data structures and low-latency access | Durable event streaming and event-log workflows |
| Frequently used for caching and counters | Frequently used for event distribution and replay |
| Supports keys, TTLs, sets, hashes, sorted sets, and streams | Organizes records into topics and partitions |
| Cache eviction can remove entries | Retention policies govern stored event records |
| Redis Streams support consumer groups | Kafka provides consumer groups and partition-based processing |

Redis Streams can support event-processing workloads, and Kafka can be used in low-latency pipelines. The decision depends on retention, replay, throughput, durability, operational requirements, and the surrounding architecture.

Do not select Redis merely because the system needs asynchronous processing. Choose the technology that matches the required delivery and recovery model.

## 20. Production Readiness Checklist

Before considering a Redis integration production-ready:

- [ ] The Redis use case and authoritative data source are documented.
- [ ] Every key family has a naming and expiry policy.
- [ ] Memory limits and eviction behavior are understood.
- [ ] Connection and command timeouts are bounded.
- [ ] Retry behavior accounts for ambiguous command outcomes.
- [ ] Hot-key and cache-stampede risks have been considered.
- [ ] The application handles cache misses correctly.
- [ ] Redis outages have a tested degradation strategy.
- [ ] Database fallback capacity has been evaluated.
- [ ] Rate limiting has correct identity and concurrency semantics.
- [ ] Credentials, network access, and permissions are controlled.
- [ ] Relevant latency, memory, hit-rate, and error metrics are monitored.
- [ ] Persistence and recovery are configured if required by the workload.
- [ ] Failover and restart behavior have been tested.
- [ ] Runbooks describe the first steps for common incidents.

## 21. SDE-1 Interview Questions & Answers

### Q1. What is the difference between atomicity and pipelining?

Atomicity concerns whether operations execute as an indivisible unit relative to other commands. Pipelining reduces network round trips by sending multiple commands without waiting for every response. Pipelining alone does not make a batch atomic.

### Q2. Does Redis `MULTI`/`EXEC` provide rollback like PostgreSQL?

No. Redis transactions group queued commands for execution, but runtime command errors do not automatically roll back other successful commands.

### Q3. When should you use Lua scripting?

When multiple Redis operations must execute atomically, particularly when the operation requires a conditional decision based on Redis state.

### Q4. What is a hot key?

A key that receives disproportionately high traffic and becomes a potential bottleneck.

### Q5. Why can increasing the connection pool make performance worse?

It can increase concurrency and resource pressure on Redis and the application, worsening contention or overload instead of fixing the underlying bottleneck.

### Q6. What is the difference between Redis Sentinel and Redis Cluster?

Sentinel provides monitoring and failover coordination for a primary/replica deployment. Redis Cluster partitions the keyspace across shards and supports replication and failover mechanisms.

### Q7. Why can retrying a timed-out `INCR` be dangerous?

The original increment may have executed even though its response was lost. Retrying can increment the counter a second time.

### Q8. How would you implement a basic distributed rate limiter?

Use a shared Redis counter keyed by caller identity and time window. Increment it atomically, ensure its expiry is set safely, and compare the result against the configured limit.

### Q9. What is the main limitation of a fixed-window rate limiter?

It can allow bursts around window boundaries, since a caller may consume the allowance in adjacent windows close together.

### Q10. Why is `PING` insufficient for diagnosing a slow API?

It verifies basic responsiveness but does not measure application connection waits, cache hit rate, serialization, database fallback, or end-to-end request latency.

### Q11. How do you distinguish Redis server latency from client-side latency?

Compare Redis-side slow-log and latency information with application-side timings, connection-pool wait time, network measurements, and total endpoint latency.

### Q12. How would you respond to a Redis outage?

Confirm the scope, inspect service and network health, assess fallback load, protect downstream systems, restore or fail over Redis, and verify recovery through application metrics.

### Q13. Why might rate limiting need a different outage policy from caching?

Bypassing an ordinary cache may only increase database work. Bypassing a rate limiter can remove an abuse or overload control, so its failure policy must account for security and availability.

### Q14. What is a hot partition in Redis Cluster?

A shard may receive disproportionate traffic because its assigned keys or slots are unusually popular. This can create a bottleneck even if other shards are underutilized.

### Q15. How do you prove a Redis optimization worked?

Use a controlled workload and compare latency percentiles, request throughput, error rates, Redis resource usage, database load, and correctness before and after the change.

---

## 22. Final Mastery Assessment

Try these without looking at the answers above.

1. A Redis command times out after incrementing a counter. How would you avoid accidentally incrementing it twice?
2. Explain why pipelining improves throughput without guaranteeing atomicity.
3. A popular product key overwhelms one Redis Cluster shard. Propose two mitigations and explain their trade-offs.
4. Redis is healthy, but API latency is high. What metrics would help separate connection, network, server, and application bottlenecks?
5. Your distributed rate limiter must enforce 100 requests per minute. Why should counter increment and initial expiry be handled atomically?
6. What could happen if Redis fails and every application instance falls back to PostgreSQL?
7. Why might a circuit breaker help during an outage, and why can bypassing Redis still be dangerous?
8. What is the difference between Redis replication, Sentinel, and Cluster?
9. When would you prefer Redis caching over repeatedly querying PostgreSQL, and when might caching be the wrong choice?
10. Design an incident response for a sudden drop in cache hit ratio following a deployment.

## 23. Redis Handbook Completion

The Redis curriculum is now complete across three planned chunks:

| Chunk | Content | Source |
|---|---|---|
| 1 | Caching fundamentals, data structures, mental models | `content/redis/01-redis-caching-fundamentals-data-structures.md` |
| 2 | Persistence, eviction, TTL strategy, caching patterns, consistency | `content/redis/02-redis-persistence-eviction-caching-patterns.md` |
| 3 | Production reliability, security, performance, incident mastery | `content/redis/03-redis-production-reliability-security-performance.md` |

### Finalization protocol

1. Save all three Markdown sources in the repository.
2. Verify that each file contains the complete chapter.
3. Review command examples, configuration, formatting, and cross-references.
4. Assemble the three chapters into one complete Redis handbook.
5. Generate and inspect `docs/redis/BEH_REDIS_COMPLETE_HANDBOOK.pdf`.
6. Update the README only after source and PDF verification.
7. Commit the verified Redis deliverables with the exact commit message:

`Redis done`

Do not create individual PDFs for the three chunks.

---

## Next Tool: Kafka — Chunk 1 of 3

The next handbook begins **Kafka Fundamentals, Event Streaming & Core Mental Models**. It will cover event-driven architecture, producers, consumers, topics, partitions, offsets, brokers, and how Kafka differs from Redis and ordinary message queues.
