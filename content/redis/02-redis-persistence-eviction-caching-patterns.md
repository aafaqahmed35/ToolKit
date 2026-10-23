# Redis — Chunk 2: Persistence, Eviction, TTL Strategy, Caching Patterns & Consistency
## Backend Engineering Tools & Infrastructure Handbook

**Phase:** II — Backend Infrastructure  
**Chunk:** 2 of 3  
**Source file:** `content/redis/02-redis-persistence-eviction-caching-patterns.md`

---

## Learning Objectives

By the end of this chapter, you should be able to:

- Explain Redis persistence using RDB snapshots and AOF logs.
- Understand Redis memory limits and eviction policies.
- Design TTL and invalidation strategies for different workloads.
- Compare cache-aside, read-through, write-through, and write-behind.
- Reason about stale data, concurrent updates, and cache consistency.
- Diagnose common cache failures using commands and application workflows.
- Explain Redis caching trade-offs in backend interviews.

---

# Layer 1 — Fundamentals & Mental Models

## 1. Redis Is In-Memory, But Does That Mean Data Disappears on Restart?

Not necessarily.

Redis is designed for fast access to data structures held in memory, but it also supports persistence mechanisms that can write data to disk.

The important distinction is:

- **Memory:** where Redis serves its data during normal operation.
- **Persistence:** how Redis records data so it may be reconstructed after a restart.
- **Replication:** how data is copied to other Redis servers.
- **Backup:** how recoverable copies are retained outside the immediate running instance.

These are different capabilities. Enabling persistence does not automatically provide a complete backup strategy or guarantee zero data loss.

For ordinary caching, data may be reconstructible from PostgreSQL. For Redis workloads that hold important state, persistence and recovery requirements must be designed explicitly.

## 2. RDB Snapshots

RDB persistence stores point-in-time snapshots of the Redis dataset.

Conceptually:

```text
Redis dataset in memory
          |
          v
   Snapshot operation
          |
          v
       dump.rdb
```

Redis can be configured to produce snapshots according to specified save conditions, and administrators can trigger snapshots when appropriate.

### Advantages

- Compact snapshot files in many workloads.
- Convenient for restoring a dataset.
- Useful for backup and transfer workflows.

### Trade-offs

A snapshot represents the dataset at a particular point in time. Changes made after the latest successful snapshot may not be present in the recovered dataset.

Snapshot creation also consumes resources. Depending on the operation and workload, it can affect memory use, CPU use, disk I/O, and latency.

**Mental model:** RDB is like taking a photograph of the dataset periodically.

It is useful when recovering to a recent snapshot is acceptable, but the recovery-point objective must be understood.

## 3. AOF — Append-Only File

AOF persistence records write operations so Redis can reconstruct state by replaying the recorded commands.

```text
Write command
     |
     v
Redis updates data
     |
     v
AOF records write history
     |
     v
Recovery replays recorded operations
```

The exact recording and durability behavior depends on the AOF configuration and the operating system's handling of disk writes.

### Advantages

- Can reduce the amount of recent data lost compared with infrequent snapshots, depending on the configured fsync policy.
- Records a sequence of write operations.
- Supports recovery by replaying that history.

### Trade-offs

- AOF files may grow and require rewriting.
- Recovery can take time when the log is large.
- Durability depends on configuration and the storage system.
- Disk I/O and rewrite activity can affect resource consumption.

Redis supports different AOF fsync policies, including policies that sync on every write, periodically, or leave syncing to the operating system. They represent different durability/performance trade-offs.

**Mental model:** RDB is a snapshot; AOF is a record of changes.

Some deployments use both. The right choice depends on whether Redis data is disposable cache state or important application state.

## 4. Persistence vs. Replication vs. Backup

These concepts are often confused.

| Capability | Primary purpose | What it does not automatically guarantee |
|---|---|---|
| RDB | Recover from a snapshot | Zero data loss after the snapshot |
| AOF | Reconstruct state from recorded writes | No loss under every failure scenario |
| Replication | Copy data to replicas | A replica is not necessarily an independent backup |
| Backup retention | Preserve recoverable copies | Successful restoration unless tested |

A replica may receive an accidental deletion or corrupted logical state. If that change propagates, the replica does not necessarily preserve the old correct data.

A robust recovery plan defines:

- Recovery Point Objective (RPO): how much data loss is acceptable.
- Recovery Time Objective (RTO): how quickly service must be restored.
- Backup retention and isolation.
- Restoration procedures and testing.
- Monitoring for failed backups and replication problems.

For a disposable product cache, rebuilding from PostgreSQL may be sufficient. For state that cannot be reconstructed, the recovery design must be much more rigorous.

## 5. Redis Memory Is a Finite Resource

Redis performance depends partly on whether the working dataset fits comfortably within the available memory budget.

Suppose the host has 8 GB of RAM. That does not mean the Redis process can safely use all 8 GB.

You must account for:

- Redis dataset memory.
- Per-key and per-value overhead.
- Client connections and buffers.
- Replication buffers.
- Persistence-related memory requirements.
- Operating system and other services.
- A safety margin for workload spikes.

Large numbers of tiny keys can still consume substantial memory because keys and data structures have overhead.

### Inspect memory usage

```redis
INFO memory
```

Useful fields include:

- `used_memory`
- `used_memory_human`
- `used_memory_peak_human`
- `maxmemory`
- `maxmemory_policy`

Inspect key-level information:

```redis
MEMORY USAGE product:1042:details
```

This helps estimate the memory attributable to a particular key, but it is not a complete capacity-planning method.

### Key lesson

Memory planning should be based on representative workloads and measured data, not just the raw size of serialized values.

## 6. What Happens When Redis Runs Out of Memory?

Redis can be configured with a `maxmemory` limit and an eviction policy.

Conceptually:

```text
New write arrives
       |
       v
Would memory exceed the configured limit?
       |
       +---- No ----> Process write
       |
       +---- Yes ---> Apply configured policy
                         |
                         +--> Evict eligible keys
                         |
                         +--> Reject write
```

The exact behavior depends on the policy, the command, and whether keys are eligible for eviction.

A cache workload often needs a policy that allows Redis to remove cached entries under memory pressure. Other workloads may need a policy that preserves existing data and rejects writes instead.

## 7. Redis Eviction Policies

Redis supports multiple eviction policies. The following are the major concepts to understand.

| Policy | Behavior |
|---|---|
| `noeviction` | Does not evict keys; writes that need additional memory may fail |
| `allkeys-lru` | Evicts keys selected by an approximate least-recently-used policy across keys |
| `allkeys-lfu` | Evicts keys selected by an approximate least-frequently-used policy across keys |
| `volatile-lru` | Applies approximate LRU eviction to keys with an expiry |
| `volatile-lfu` | Applies approximate LFU eviction to keys with an expiry |
| `allkeys-random` | Evicts randomly selected keys from the keyspace |
| `volatile-random` | Evicts randomly selected keys that have an expiry |
| `volatile-ttl` | Prefers keys with shorter remaining TTLs among eligible keys |

LRU approximates recency: which data has been used recently?

LFU approximates frequency: which data has been accessed frequently?

Neither policy perfectly predicts future access. Their suitability depends on workload patterns.

### Example: a product catalog

Suppose 20% of products account for 80% of requests. An LFU-like strategy may retain frequently accessed products, while less popular entries become candidates for eviction.

But if a campaign suddenly makes a previously unpopular product extremely popular, historical access patterns may not immediately reflect the new workload.

### A subtle but important point

`volatile-*` policies consider only keys that have an expiration set. If the workload has no eligible keys, the system may not be able to evict a key under those policies, and writes requiring memory can fail.

Do not choose an eviction policy without understanding which keys have TTLs and whether eviction is allowed for the workload.

## 8. Cache Expiration Is Different From Eviction

These two concepts are related but distinct.

**Expiration:** a key's configured lifetime has elapsed.

**Eviction:** Redis removes a key to manage memory pressure according to its configured policy.

A key may disappear because its TTL expired even when memory is plentiful. A key may also be evicted before its TTL expires when memory pressure and the configured policy allow it.

This means that a TTL is not a promise that the key will remain present for its entire configured lifetime.

Applications must treat cached entries as optional and handle missing values correctly.

## 9. Cache Invalidation: The Hard Part

Imagine an application updates a product's price in PostgreSQL.

The Redis cache still contains the old price.

There are several common strategies.

### Strategy A — Delete the cache key after a database update

```text
Update PostgreSQL
       |
       v
Commit transaction
       |
       v
Delete Redis key
```

A later read misses the cache and reloads the current database value.

This is a common starting point, but it is not perfectly race-free. A concurrent reader could fetch an old value before the update commits and write it into Redis after the invalidation.

### Strategy B — Update the cache after the database update

```text
Update PostgreSQL
       |
       v
Commit transaction
       |
       v
Update Redis value
```

This may reduce the time a cache remains stale, but failure between the database commit and the cache update can leave the cache inconsistent.

### Strategy C — TTL-based eventual freshness

Allow the entry to expire and be reloaded later.

This is simple but permits stale values during the TTL window. It is unsuitable when the business requires stronger freshness guarantees.

### Strategy D — Versioned cache entries

Associate cached data with a version or generation identifier.

Versioning can help avoid some stale-write races, but it requires careful handling of version ownership, atomicity, and old-entry cleanup.

No invalidation strategy is universally correct. Pick one that matches the business requirements and document its failure behavior.

## 10. Cache-Aside, Read-Through, Write-Through and Write-Behind

These patterns describe how application reads and writes interact with a cache.

### Cache-aside

The application manages cache lookups and population.

```text
Read:
Cache -> miss -> Database -> Populate cache

Write:
Database update -> Invalidate or update cache
```

**Advantages:** simple, flexible, widely used.

**Trade-offs:** application code must handle misses, invalidation, and concurrency.

### Read-through

The application reads through a cache abstraction, and the cache-loading layer retrieves data from the backing store on a miss.

```text
Application -> Cache layer -> Database on miss
```

**Advantages:** centralizes loading behavior.

**Trade-offs:** requires a suitable cache abstraction and does not remove the need to reason about invalidation and consistency.

### Write-through

A write is applied to the cache and backing store through a coordinated write path.

```text
Application
     |
     v
Coordinated cache/write layer
     |
     +----> Cache
     |
     +----> Database
```

The ordering and failure semantics depend on the implementation. A diagram alone does not make two independent stores transactionally atomic.

**Advantages:** can keep cache updates close to write operations.

**Trade-offs:** extra write latency and cross-store failure handling.

### Write-behind (write-back)

The cache accepts a write first, and the backing store is updated asynchronously later.

```text
Application
     |
     v
Cache / pending write state
     |
     v
Asynchronous persistence
     |
     v
Database
```

**Advantages:** can reduce synchronous write latency and batch downstream writes.

**Trade-offs:** increased complexity, delayed durability, potential data loss, ordering problems, and recovery requirements.

Do not use write-behind for critical business records merely because it appears faster. It needs a reliable mechanism for tracking, retrying, and recovering pending writes.

## 11. The Database-Cache Dual-Write Problem

A common backend bug occurs when one operation must update two independent systems.

For example:

```text
1. Update product in PostgreSQL
2. Update Redis
```

What if step 1 succeeds and step 2 fails?

Or what if Redis is updated first and PostgreSQL fails?

Without a coordinated consistency strategy, the two systems can disagree.

For ordinary caches, deleting the cache after a successful database commit is often a practical baseline. If invalidation fails, the system may need retries, monitoring, and TTL-based recovery.

For more demanding workflows, teams may use an outbox pattern, versioning, event-driven invalidation, or another carefully designed reconciliation mechanism.

Remember: a cache is an optimization. Its failure should not silently corrupt the authoritative business record.

---

# Layer 2 — Practical Engineering & Workflows

## 12. Inspect Persistence and Memory Configuration

Start by examining the running server.

```redis
INFO persistence
INFO memory
CONFIG GET maxmemory
CONFIG GET maxmemory-policy
```

Configuration commands may be restricted by server policy or managed-service permissions.

Inspect the results before making changes. Do not blindly apply production settings to a local or managed instance.

### Inspect key TTLs

```redis
TTL product:1042:details
PTTL product:1042:details
```

`PTTL` reports remaining lifetime in milliseconds.

### Inspect the keyspace

```redis
INFO keyspace
```

This provides a high-level view of database key counts and expiration statistics. It does not replace workload-specific monitoring.

## 13. Configure a Local Redis Experiment

For a disposable local instance, you can inspect or configure memory behavior for a controlled experiment.

First inspect the current settings:

```redis
CONFIG GET maxmemory
CONFIG GET maxmemory-policy
```

If your local server permits runtime configuration changes, you can set a small memory limit and an eviction policy for experimentation. Choose values that are appropriate for your environment and reset them after the lab if necessary.

For example, on a disposable instance:

```redis
CONFIG SET maxmemory 50mb
CONFIG SET maxmemory-policy allkeys-lru
```

This is a lab example, not a recommended universal production configuration. A small memory limit may cause immediate eviction or rejected writes depending on the dataset and policy.

Observe:

```redis
INFO memory
INFO stats
```

Then populate test keys and examine how the dataset behaves as memory pressure increases.

**Safety:** don't experiment with memory limits or eviction settings on a shared or production Redis instance without an approved change procedure.

## 14. Build a Reliable Cache-Aside Write Workflow

A simple product-update workflow should define what happens if cache invalidation fails.

Pseudocode:

```java
@Transactional
public Product updateProduct(long id, ProductUpdate update) {
    Product product = productRepository.findById(id)
        .orElseThrow(() -> new ProductNotFoundException(id));

    product.apply(update);

    return productRepository.save(product);
}
```

After the database transaction commits, an application service can attempt to invalidate the corresponding cache key.

Conceptually:

```text
Database transaction commits
            |
            v
Invalidate product:<id>
            |
            +---- Success --> Normal operation
            |
            +---- Failure --> Record failure and recover
```

A production design must consider transaction boundaries. Calling Redis inside a database transaction does not make the two operations part of one atomic transaction.

Possible recovery mechanisms include:
- Logging and alerting on invalidation failures.
- Retrying failed invalidations.
- A durable outbox event for important invalidation workflows.
- Short TTLs as a secondary bound on stale data.
- Reconciliation or versioning where requirements justify it.

Do not swallow every Redis exception silently. Decide whether the endpoint can safely succeed when the cache update fails and make that decision observable.

## 15. TTL Strategy in Application Code

Use a TTL that reflects the freshness requirements and expected workload.

Example:

```java
Duration productDetailsTtl = Duration.ofMinutes(5);
```

When many keys are populated at the same time, identical TTLs can cause synchronized expiration patterns.

A common mitigation is to add a small randomized variation to expiration times, often called TTL jitter.

Conceptually:

```text
Base TTL: 300 seconds
Random variation: 0–30 seconds

Actual TTL: 300–330 seconds
```

The exact range should be selected for the workload. Jitter reduces synchronized expiration risk; it does not prevent all cache stampedes.

### Avoid these TTL mistakes

- Creating cache entries with no expiry unintentionally.
- Applying one TTL to every kind of data.
- Using TTL as the only correctness mechanism for critical records.
- Assuming that an expired key will never be read by an already-running request.
- Forgetting to refresh or invalidate cached data after a write.
- Setting extremely short TTLs that make the cache ineffective.

## 16. Production Debugging Commands

When Redis behavior looks wrong, collect evidence before changing configuration.

```redis
PING
INFO memory
INFO stats
INFO persistence
INFO clients
INFO keyspace
SLOWLOG GET 10
LATENCY LATEST
```

Availability of diagnostic commands and their output depend on the Redis version and deployment permissions.

Useful questions:

1. Is Redis reachable?
2. Is memory usage close to the configured limit?
3. Are evictions increasing?
4. Are rejected writes increasing?
5. Are persistence operations causing resource pressure?
6. Are slow commands appearing?
7. Are client connections or buffers growing unexpectedly?
8. Is the cache hit ratio falling?
9. Is PostgreSQL receiving more requests than normal?
10. Did a recent deployment change cache keys, TTLs, or serialization?

### Example incident: sudden increase in database load

Symptoms:
- PostgreSQL CPU rises.
- API latency increases.
- Redis remains reachable.
- Cache hit ratio falls sharply.

Investigation:
1. Check whether a deployment changed key names.
2. Confirm that the expected keys are being populated.
3. Inspect TTLs and eviction statistics.
4. Examine whether a popular key expired or stopped being cached.
5. Compare application and database request metrics.
6. Fix the root cause and verify the hit ratio and database load recover.

Do not immediately increase Redis memory. A broken cache-key convention can cause a miss storm even when memory is plentiful.

## 17. Hands-On Lab: Eviction and Expiration

Use a disposable Redis instance.

### Task A — Compare TTL and eviction

1. Create a key with an expiry.
2. Create another key without an expiry.
3. Inspect both using `TTL`.
4. Configure a small memory limit and an appropriate policy in the disposable environment.
5. Generate enough test data to create memory pressure.
6. Observe which keys remain.
7. Restore the normal configuration after the experiment.

### Task B — Persistence investigation

Inspect:

```redis
INFO persistence
```

Identify:
- Whether RDB or AOF is enabled.
- When the most recent successful snapshot occurred, where applicable.
- Whether background persistence is active.
- Whether persistence errors are reported.

Do not infer that data is fully protected just because persistence is enabled.

### Task C — Cache invalidation design

Write a short design for this sequence:

```text
Client updates product price
PostgreSQL commits the update
Redis invalidation fails
Another client requests the product
```

Your design should state:
- Which system is authoritative.
- Whether the update endpoint succeeds.
- How the invalidation failure is recorded.
- How stale data is bounded or prevented.
- How the system recovers.

### Task D — Capacity review

For a cache with a configured memory limit, document:
- Expected number of keys.
- Approximate value sizes.
- Key and object overhead assumptions.
- Expected TTL distribution.
- Eviction policy.
- Peak workload.
- Alert thresholds and response steps.

The objective is not to calculate a perfect number from assumptions. It is to build a capacity model that can be validated using measurements.

---

# Layer 3 — Production Engineering & Interview Mastery

## 18. Production Scenario: Redis Restarts and the Cache Is Empty

### Symptoms

- Redis restarts.
- Cache hit ratio drops.
- PostgreSQL traffic spikes.
- API latency increases.

### Likely explanation

The application relied on cached values that were lost or not restored after the restart.

For an ordinary cache, this can be an expected recovery scenario. The real issue may be that the application was not prepared for the sudden increase in database traffic.

### Response

1. Confirm Redis health and restart status.
2. Inspect persistence and recovery logs if the workload requires persistence.
3. Measure cache misses and PostgreSQL load.
4. Protect PostgreSQL with appropriate concurrency limits or load shedding if needed.
5. Allow the cache to warm gradually or repopulate it safely.
6. Verify that the system recovers without creating another overload.

### Prevention

- Load-test cold-cache behavior.
- Set realistic database capacity assumptions.
- Design gradual cache warming where useful.
- Monitor hit ratio, database load, and API latency together.
- Decide whether persistence is required for the actual Redis workload.

## 19. Production Scenario: Writes Start Failing

### Symptoms

- Redis write commands return errors.
- The application logs indicate memory-related failures.
- Reads may continue to work.

### Investigation

1. Inspect `INFO memory`.
2. Check `maxmemory` and `maxmemory-policy`.
3. Inspect eviction and rejected-command statistics.
4. Check whether the dataset has grown unexpectedly.
5. Identify keys that are unexpectedly large or lack expiry.
6. Verify that the chosen policy is appropriate for the workload.

### Corrective options

Depending on the findings:
- Remove unintended unbounded data.
- Add suitable TTLs to disposable entries.
- Reduce value sizes or duplicate caching.
- Adjust the memory budget after reviewing host capacity.
- Change the eviction policy if the current policy does not match the intended workload.
- Split unrelated workloads where their memory and reliability requirements conflict.

Do not automatically delete arbitrary keys to restore service. First determine whether the data is disposable cache state or important application state.

## 20. Production Scenario: Stale Product Prices

### Symptoms

Customers report old prices even after a successful product update.

### Investigation

1. Verify the authoritative value in PostgreSQL.
2. Read the corresponding Redis key.
3. Check the TTL and key naming.
4. Inspect all write paths that can modify the product.
5. Look for failed invalidations or a race between cache population and deletion.
6. Check whether multiple application versions use different key formats.

### Remediation

Choose an approach based on the required consistency:
- Correct the invalidation logic.
- Retry failed invalidations reliably.
- Introduce versioning where appropriate.
- Reduce TTL if the acceptable stale window is too large.
- Bypass the cache for operations that require authoritative reads.

The fix must address the underlying inconsistency rather than merely deleting the currently stale key.

## 21. Production Scenario: Redis Looks Healthy, but the API Is Slow

Redis may be healthy at the server level while the application remains slow.

Possible causes:
- High cache-miss rates.
- Slow serialization and deserialization.
- Large cached payloads.
- Network latency between the application and Redis.
- Excessive round trips caused by fetching fields one at a time.
- Slow database queries on cache misses.
- Connection-pool saturation.
- A hot key or contention around application-level coordination.

Investigate end-to-end latency rather than relying on a single Redis health check.

Measure the complete request path:

```text
API request
   |
   +--> Redis lookup latency
   |
   +--> Database fallback latency
   |
   +--> Serialization / application processing
   |
   +--> Response latency
```

Optimize the actual bottleneck. A cache that saves 2 ms but introduces a complex failure mode may not be worth using for every endpoint.

## 22. Production Readiness Checklist

Before deploying Redis caching:

- [ ] The source of truth is explicitly documented.
- [ ] Every cached resource has a key-naming convention.
- [ ] TTLs reflect data freshness requirements.
- [ ] Cache invalidation is defined for every relevant write path.
- [ ] Missing cache entries are handled correctly.
- [ ] Serialization is consistent and safe.
- [ ] Memory limits and eviction policy match the workload.
- [ ] Redis outages have a documented degradation strategy.
- [ ] Database capacity has been evaluated for cold-cache conditions.
- [ ] Hit ratio, latency, memory, evictions, and errors are monitored.
- [ ] Credentials and network access are protected.
- [ ] Persistence and backups are configured if the workload requires them.
- [ ] Recovery procedures have been tested.
- [ ] Load tests include cold-cache and cache-degradation scenarios.
- [ ] Failure paths are covered by automated tests.

## 23. Advanced SDE-1 Interview Questions

### Q1. What is the difference between RDB and AOF?

RDB stores point-in-time snapshots. AOF records write operations for recovery through replay. Their recovery-point, recovery-time, and resource trade-offs differ.

### Q2. Does Redis persistence guarantee zero data loss?

No. The outcome depends on persistence configuration, when data was successfully written, the storage system, and the failure scenario.

### Q3. What is a Redis eviction policy?

It determines how Redis selects keys for removal when memory pressure requires eviction and the configured policy allows it.

### Q4. What is the difference between LRU and LFU?

LRU focuses on recency of access. LFU focuses on frequency of access. Both are approximations and perform differently under different workloads.

### Q5. Can a key be evicted before its TTL expires?

Yes. If memory pressure and the configured eviction policy permit it, a key can be removed before its expiration time.

### Q6. What happens when `noeviction` is configured and memory is exhausted?

Redis does not evict keys under that policy. Commands requiring additional memory may fail.

### Q7. Why is cache invalidation difficult?

Because the database and cache are separate systems, and concurrent reads, writes, and failures can leave them inconsistent.

### Q8. What is the dual-write problem?

An application updates two separate systems, and one operation may succeed while the other fails. Without coordination or recovery, their states can diverge.

### Q9. What is write-behind caching?

The cache accepts updates and the backing store is updated asynchronously later. It can improve write latency but introduces durability and recovery risks.

### Q10. How would you prevent a cache stampede?

Consider request coalescing, TTL jitter, background refresh, or carefully designed coordination. Select based on workload and failure behavior.

### Q11. Is a replica a backup?

Not necessarily. Replication improves availability and may aid recovery, but destructive or incorrect changes can propagate. Independent backups and tested restoration are still important.

### Q12. Why might a cache hit ratio fall suddenly?

Potential causes include mass expiration, eviction, a deployment changing key names, cache population failures, a workload shift, or a cold-cache restart.

### Q13. Why should cache memory be budgeted below host memory?

Redis needs overhead for connections, buffers, persistence, replication, and other processes. Operating at the host's full memory limit risks resource exhaustion.

### Q14. When is a cache inappropriate?

When the overhead, invalidation complexity, stale-data risk, or operational burden outweighs the benefit, or when the operation requires authoritative data and cannot tolerate the cache's consistency model.

### Q15. How would you prove that Redis improved performance?

Compare equivalent workloads before and after deployment, measuring API latency percentiles, database load, cache hit ratio, Redis latency, error rates, and correctness.

---

## 24. Mastery Assessment

Answer these in your own words:

1. Why can Redis lose recent writes despite persistence being enabled?
2. Why is `volatile-lru` potentially unsuitable when most keys have no TTL?
3. How could a cache invalidation failure create stale data?
4. What is the difference between an eviction and an expiration?
5. Why does a cache restart sometimes overload PostgreSQL?
6. When would you choose cache-aside over write-behind?
7. What would you investigate if Redis memory is stable but cache hit ratio collapses?
8. What is the difference between replication and a backup?
9. How can TTL jitter help, and what does it fail to guarantee?
10. Why is updating PostgreSQL and Redis not automatically an atomic operation?

## Completion Checklist

- [ ] I can explain RDB and AOF.
- [ ] I can distinguish persistence, replication, and backups.
- [ ] I can inspect memory and persistence statistics.
- [ ] I understand `maxmemory` and major eviction policies.
- [ ] I can distinguish expiration from eviction.
- [ ] I can explain cache invalidation and the dual-write problem.
- [ ] I can compare cache-aside, read-through, write-through, and write-behind.
- [ ] I can diagnose a cold-cache database overload.
- [ ] I can reason about memory pressure and rejected writes.
- [ ] I can design a measured, recoverable caching strategy.

---

## What Comes Next?

**Redis — Chunk 3 of 3: Production Reliability, Security, Performance & Incident Mastery**

The final Redis chapter will bring the pieces together: operational design, connection handling, hot keys, pipelining, transactions and atomicity, rate limiting, distributed coordination, observability, security, incident simulations, and final interview mastery.

**Repository workflow:** Save this chapter as `content/redis/02-redis-persistence-eviction-caching-patterns.md`. Do not generate a PDF yet. Generate `docs/redis/BEH_REDIS_COMPLETE_HANDBOOK.pdf` only after all three Redis chapters have been saved and verified.
