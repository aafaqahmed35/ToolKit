# Redis — Chunk 1: Caching Fundamentals, Data Structures & Core Mental Models
## Backend Engineering Tools & Infrastructure Handbook

**Phase:** II — Backend Infrastructure  
**Chunk:** 1 of 3  
**Source file:** `content/redis/01-redis-caching-fundamentals-data-structures.md`

---

## Learning Objectives

By the end of this chapter, you should be able to:

- Explain why Redis exists and when a backend should use it.
- Distinguish a cache from a primary database.
- Explain Redis's key-value model and its core data structures.
- Design cache keys and use TTLs correctly.
- Execute essential Redis commands.
- Integrate Redis into a Spring Boot backend.
- Recognize cache misses, stale data, cache stampedes, and common design mistakes.
- Defend your caching decisions in an SDE-1 interview.

---

# Layer 1 — Fundamentals & Mental Models

## 1. What Is Redis?

Redis is an in-memory data structure server that allows applications to store and retrieve data using keys.

Think of it as a very fast shared workspace for data that your application needs frequently.

Suppose you're building an e-commerce backend. A user requests product `P-1042`.

Without caching:

```text
Client
  |
  v
Spring Boot API
  |
  v
PostgreSQL
  |
  v
Return product
```

Every request that needs the product queries PostgreSQL.

With Redis caching:

```text
Client
  |
  v
Spring Boot API
  |
  v
Redis: Is product:P-1042 cached?
  |
  +---- HIT ----> Return cached product
  |
  +---- MISS ---> PostgreSQL
                    |
                    v
                 Store in Redis
                    |
                    v
                 Return product
```

Redis can reduce repeated database work and improve response latency when the workload has reusable data.

### Why not query PostgreSQL every time?

PostgreSQL is excellent at durable storage, transactions, relational queries, and consistency. However, repeated queries for the same popular data still consume database resources.

Consider a product page receiving 10,000 requests in a short period. If the product changes infrequently, querying the database for every request may be unnecessary.

A cache allows the application to reuse previously retrieved data.

**Core mental model:** PostgreSQL can remain the source of truth while Redis serves as a fast, temporary copy of selected data.

Redis can also be used for other purposes, including counters, rate limiting, queues, coordination, and ephemeral state. Those use cases require their own design considerations.

## 2. Cache vs. Database

| Property | Redis cache | PostgreSQL |
|---|---|---|
| Primary strength | Fast access to reusable data | Durable relational storage |
| Typical access | Key-based lookups and data structures | SQL queries and transactions |
| Data lifetime | Often limited by TTL or eviction | Usually persists until changed or deleted |
| Data model | Strings, hashes, lists, sets, sorted sets, streams, and more | Tables, rows, relationships |
| Source of truth | Usually not for ordinary cache entries | Often the application's source of truth |
| Failure consequence | Cache loss may increase database load | Data loss can compromise core business records |

These are common patterns, not absolute rules. Redis supports persistence, and some architectures deliberately use it as a primary data store.

For this handbook, our default architecture is:

- **PostgreSQL:** authoritative business data.
- **Redis:** cached results and selected ephemeral state.
- **Spring Boot:** application logic that coordinates both.

Never assume that data stored in Redis is automatically safe to lose or safe to reconstruct. That depends on the use case.

## 3. What Makes Redis Fast?

Redis commonly keeps active data in memory and processes commands through an efficient server architecture.

Three ideas matter:

1. **Memory access:** retrieving data from memory usually avoids the latency of a database disk-backed query path.
2. **Purpose-built data structures:** Redis provides operations for strings, sets, sorted sets, hashes, and other structures rather than requiring every operation to be implemented in application code.
3. **Low-overhead access:** a simple key lookup can be much cheaper than repeatedly executing an expensive database query.

But don't reduce Redis to “everything is O(1).” Complexity depends on the command and the data structure. For example, retrieving one hash field differs from retrieving every member of a large collection.

Redis is also not infinitely fast. Network latency, serialization, large values, memory pressure, slow commands, contention, and excessive request volume can all become bottlenecks.

## 4. The Redis Key-Value Model

Redis stores values under keys.

Conceptually:

```text
Key                         Value
-------------------------------------------------
product:1042                {"name":"Keyboard",...}
user:87:profile             {"name":"Aafaq",...}
session:abc123              session data
inventory:1042              42
```

A key should communicate the resource and purpose of its value.

Prefer:

```text
product:1042
user:87:profile
order:9001:summary
```

Avoid vague keys:

```text
data
user
result
temp
```

Good keys improve debugging, ownership, observability, and maintenance.

### Key naming conventions

A common convention is:

```text
<domain>:<identifier>:<purpose>
```

Examples:

```text
product:1042:details
product:1042:price
user:87:permissions
catalog:category:electronics
```

Choose one consistent convention across your application.

Do not put secrets, access tokens, passwords, or unnecessary personal information into key names. Keys may appear in diagnostics, monitoring, or operational tooling.

## 5. Redis Data Structures

Redis is more than a string-to-string map. Its data structures help solve different backend problems.

### 5.1 Strings

Strings store a value associated with a key. Values can represent text, serialized JSON, or numbers.

```redis
SET product:1042:name "Mechanical Keyboard"
GET product:1042:name
```

Example response:

```text
"Mechanical Keyboard"
```

A numeric counter:

```redis
SET page:home:views 0
INCR page:home:views
INCR page:home:views
GET page:home:views
```

The final value is `2`.

Redis provides atomic increment operations. This is useful when multiple requests need to update the same counter without implementing a read-modify-write sequence in application code.

**Backend use cases:**
- Cached JSON responses.
- Simple counters.
- Feature flags.
- Short-lived verification state.
- Rate-limit counters.

### 5.2 Hashes

Hashes store fields and values under a single key.

```redis
HSET user:87:profile name "Aafaq" role "developer"
HGET user:87:profile name
HGETALL user:87:profile
```

Conceptually:

```text
user:87:profile
  |
  +-- name = "Aafaq"
  +-- role = "developer"
```

Hashes are useful when a resource naturally consists of several fields.

However, don't assume a Redis hash is always superior to a serialized JSON string. Choose based on how the application accesses and updates the data, and consider schema evolution, serialization, and the number of network calls.

### 5.3 Lists

Lists hold ordered sequences of values.

```redis
LPUSH notifications:user:87 "Welcome"
LPUSH notifications:user:87 "Order shipped"

LRANGE notifications:user:87 0 -1
```

Lists support operations at their ends and can be used for simple ordered collections or queue-like patterns.

Possible use cases:
- Recent activity.
- Simple work queues.
- Ordered messages.

For robust distributed event processing, Redis Lists are not automatically a replacement for a purpose-built system such as Kafka. Delivery guarantees, consumer coordination, replay, retention, and operational requirements must be considered.

### 5.4 Sets

Sets hold unique members.

```redis
SADD user:87:roles "developer" "reviewer"
SADD user:87:roles "developer"

SMEMBERS user:87:roles
SISMEMBER user:87:roles "reviewer"
```

Adding `developer` twice does not create two distinct members.

Useful for:
- Unique membership.
- Tags.
- Feature eligibility.
- Set intersection and union operations.

For example, finding users who belong to both groups:

```redis
SINTER team:backend team:oncall
```

### 5.5 Sorted Sets

Sorted sets associate unique members with scores.

```redis
ZADD leaderboard 1200 "player:1"
ZADD leaderboard 950 "player:2"
ZADD leaderboard 1500 "player:3"

ZREVRANGE leaderboard 0 2 WITHSCORES
```

The reverse range returns the highest-scoring members first.

Useful for:
- Leaderboards.
- Rankings.
- Priority ordering.
- Time-based indexes when designed appropriately.

Sorted sets are especially helpful when the application needs ordering by a numeric score without fetching and sorting the entire dataset itself.

### 5.6 Streams

Redis Streams provide an append-oriented data structure for event records and consumer-group workflows.

They support use cases such as:
- Event ingestion.
- Consumer groups.
- Reading events from an ID.
- Tracking and acknowledging processed entries.

Streams are more capable than a simple list for event-processing workflows, but they still require careful choices about retention, consumer recovery, duplicate handling, and delivery semantics.

### Quick data-structure selection

| Requirement | Candidate |
|---|---|
| Cache one object or response | String containing serialized data |
| Read or update individual fields | Hash |
| Maintain an ordered sequence | List |
| Store unique members | Set |
| Rank members by score | Sorted set |
| Append and consume event records | Stream |
| Maintain a numeric counter | String with `INCR`/`INCRBY` |

These are starting points, not rigid rules. Select the structure that best matches the required operations.

## 6. TTL: Time to Live

A TTL determines how long a key should remain before it expires automatically.

```redis
SET product:1042:details '{"name":"Keyboard"}' EX 300
```

The key is configured to expire after 300 seconds.

Inspect the remaining TTL:

```redis
TTL product:1042:details
```

Common outcomes:

- A positive number: remaining lifetime in seconds.
- `-1`: the key exists but has no expiration.
- `-2`: the key does not exist.

You can set an expiry separately:

```redis
EXPIRE product:1042:details 300
```

Or inspect the stored value:

```redis
GET product:1042:details
```

### Why TTL matters

Imagine that a product's price changes in PostgreSQL, but Redis keeps the old cached value forever. Customers could continue seeing stale pricing.

A TTL bounds the lifetime of that cached copy, assuming it is not refreshed or replaced.

However, TTL is **not an instantaneous consistency guarantee**. A value may remain stale until it expires, and expiry alone does not solve every race between concurrent reads and writes.

A shorter TTL generally reduces the maximum cache lifetime but increases database traffic. A longer TTL may improve cache hit rates but can prolong staleness.

TTL is a design decision, not an arbitrary number.

## 7. Cache Hits and Cache Misses

A **cache hit** occurs when the requested value is present in Redis.

A **cache miss** occurs when the value is absent, expired, or otherwise unavailable for the requested lookup.

Suppose an endpoint retrieves a product:

```text
Request 1:
Redis lookup -> MISS
PostgreSQL query -> product found
Store result in Redis
Return product

Request 2:
Redis lookup -> HIT
Return cached product
```

The first request performs the database lookup. The second can reuse the cached value.

### Cache hit ratio

A simple cache hit ratio is:

\[
\text{Hit Ratio} =
\frac{\text{Cache Hits}}
{\text{Cache Hits}+\text{Cache Misses}}
\times 100\%
\]

If 800 lookups hit the cache and 200 miss:

\[
\frac{800}{800+200}\times100=80\%
\]

An 80% hit ratio does not automatically mean the system is healthy. A cache could have a high hit ratio while returning stale data, consuming excessive memory, or causing high latency for misses.

Evaluate hit ratio alongside latency, error rates, database load, and data correctness.

---

# Layer 2 — Practical Engineering & Workflows

## 8. Start Redis Locally with Docker

If Docker is available, start a disposable Redis instance:

```bash
docker run --name redis-handbook \
  -p 127.0.0.1:6379:6379 \
  -d redis:7
```

This example pins the major Redis version rather than using an unspecified latest tag. For a real project, choose a supported version and pin an appropriate image tag or digest according to your release policy.

Check that the container is running:

```bash
docker ps
docker logs redis-handbook
```

Open a Redis CLI session:

```bash
docker exec -it redis-handbook redis-cli
```

Test connectivity:

```redis
PING
```

Expected response:

```text
PONG
```

Run a few commands:

```redis
SET greeting "Hello Redis"
GET greeting
EXPIRE greeting 60
TTL greeting
```

Clean up the container when finished:

```bash
docker rm -f redis-handbook
```

This command removes the container. Do not use this disposable setup for production data.

**Important:** this example intentionally binds Redis to loopback on the host. Do not expose an unauthenticated Redis instance directly to an untrusted network.

## 9. Essential Redis CLI Commands

Keep this command set handy.

| Command | Purpose |
|---|---|
| `PING` | Check basic server responsiveness |
| `SET key value` | Store a string |
| `GET key` | Read a string |
| `DEL key` | Delete a key |
| `EXISTS key` | Check whether a key exists |
| `EXPIRE key seconds` | Set an expiry |
| `TTL key` | Inspect remaining lifetime |
| `INCR key` | Increment a numeric string |
| `HSET key field value` | Set a hash field |
| `HGET key field` | Read a hash field |
| `SADD key member` | Add a set member |
| `SMEMBERS key` | Read set members |
| `LRANGE key start stop` | Read a list range |
| `ZADD key score member` | Add a sorted-set member |
| `ZREVRANGE key start stop WITHSCORES` | Read highest-scoring members first |
| `SCAN 0` | Begin incremental key iteration |

### Why `SCAN` instead of `KEYS *`?

`KEYS *` can traverse the entire keyspace in one command and can cause disruptive latency on a busy server.

`SCAN` supports incremental iteration, allowing clients to process batches over multiple calls. It is not a perfectly consistent snapshot, and clients must handle repeated results and cursor progression correctly.

In application code, prefer purpose-built key naming, known keys, and indexed structures over routinely searching the entire keyspace.

## 10. Design a Cache-Aside Workflow

Cache-aside is a common caching pattern:

1. Application checks Redis.
2. On a hit, return the cached value.
3. On a miss, read the source database.
4. Populate Redis with the result.
5. Return the result to the caller.

The application explicitly manages cache reads and population.

### Example: product lookup

Assume PostgreSQL is the source of truth for products.

```java
public Product getProduct(long productId) {
    String key = "product:" + productId;

    Product cached = redisCache.get(key, Product.class);

    if (cached != null) {
        return cached;
    }

    Product product = productRepository.findById(productId)
        .orElseThrow(() -> new ProductNotFoundException(productId));

    redisCache.put(key, product, Duration.ofMinutes(5));

    return product;
}
```

This example illustrates the flow; `redisCache` is an application abstraction that you would implement using Spring Data Redis or another Redis client.

The critical behavior is the ordering:

- Check Redis first.
- Query PostgreSQL on a miss.
- Populate Redis after a successful database read.

The exact treatment of missing records, serialization failures, and Redis outages depends on the endpoint's requirements.

### Why not cache every database query?

Some data is:
- Rarely accessed.
- Frequently modified.
- Expensive to serialize.
- Sensitive.
- Too large to justify retaining.
- Difficult to invalidate safely.

Cache selectively. Start with a known bottleneck or high-read workload and measure whether caching improves it.

## 11. Spring Boot Integration

For a Spring Boot application, use Spring Data Redis and a compatible Redis client.

With Maven, the Spring Boot starter is commonly declared as:

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-data-redis</artifactId>
</dependency>
```

Let your Spring Boot dependency management select a compatible version rather than hardcoding an arbitrary version.

Configure the connection using environment variables:

```yaml
spring:
  data:
    redis:
      host: ${REDIS_HOST:localhost}
      port: ${REDIS_PORT:6379}
```

The exact configuration properties can vary with Spring Boot versions and the selected Redis client. Verify them against the version used by your project.

### A small cache service

A simplified example using `StringRedisTemplate`:

```java
@Service
public class ProductCacheService {

    private final StringRedisTemplate redis;

    public ProductCacheService(StringRedisTemplate redis) {
        this.redis = redis;
    }

    public void put(String key, String value, Duration ttl) {
        redis.opsForValue().set(key, value, ttl);
    }

    public String get(String key) {
        return redis.opsForValue().get(key);
    }

    public void evict(String key) {
        redis.delete(key);
    }
}
```

This example stores strings. A production application that caches Java objects must choose a serialization format and configure it consistently.

Prefer explicit, understandable serialization. Avoid unsafe polymorphic deserialization configurations, and treat cached data as untrusted input if its source or integrity is not guaranteed.

### Test the integration

1. Start Redis locally.
2. Start the Spring Boot application.
3. Store a value with a short TTL.
4. Read it and confirm the value matches.
5. Wait for expiration and confirm it is absent.
6. Stop Redis and observe the application's behavior.
7. Restart Redis and verify that the application can reconnect according to its configuration.

This last pair of tests is important: successful integration does not mean the system behaves correctly when Redis becomes unavailable.

## 12. Cache Keys and Expiration in a Backend API

Suppose you have these endpoints:

```text
GET /api/products/1042
GET /api/products/1043
GET /api/users/87/profile
```

Use distinct keys:

```text
product:1042:details
product:1043:details
user:87:profile
```

A product lookup should not accidentally reuse another product's cached value. A user-specific response should not be shared across users just because the URL or key was designed poorly.

For cache keys, consider:

- Resource identity.
- Tenant or organization identity where applicable.
- Locale or representation version when the response differs by locale or schema.
- Relevant query parameters for list endpoints.
- Authorization boundaries.
- Schema changes and cache-key versioning.

For example:

```text
v1:tenant:42:product:1042:details
```

A versioned prefix can make a schema transition easier to manage, although it may temporarily leave old entries in Redis until they expire or are removed.

### Cache negative results carefully

If a product does not exist, repeated requests can still generate database load. Some applications cache a “not found” result briefly to reduce repeated lookups.

But negative caching requires care:

- Use a short, deliberate TTL.
- Distinguish a cached negative result from a cache miss.
- Invalidate the negative result when the resource is created.
- Avoid turning temporary database failures into cached “not found” responses.

A database timeout does not mean that a product does not exist.

## 13. Hands-On Lab: Build a Mini Product Cache

Complete the lab in Redis CLI.

### Task A — Cache a product

```redis
SET product:1042:details '{"id":1042,"name":"Keyboard","price":2499}' EX 120
GET product:1042:details
TTL product:1042:details
```

Verify that the value exists and has a positive TTL.

### Task B — Update the cached value

```redis
SET product:1042:details '{"id":1042,"name":"Keyboard","price":2299}' EX 120
GET product:1042:details
```

Observe that `SET` replaces the previous value and, with `EX 120`, establishes a new expiry.

### Task C — Build a counter

```redis
SET product:1042:view-count 0
INCR product:1042:view-count
INCR product:1042:view-count
GET product:1042:view-count
```

Expected final value:

```text
2
```

### Task D — Inspect expiration

```redis
SET demo:short-lived "temporary" EX 5
TTL demo:short-lived
```

Wait several seconds, then run:

```redis
GET demo:short-lived
```

Expected result after expiration: a nil response.

### Task E — Think like an engineer

Answer these questions:

1. Which component owns the authoritative product price?
2. What happens if PostgreSQL updates the price but Redis retains the previous value?
3. How would you invalidate the cached product after an update?
4. What should the API do if Redis is unavailable?
5. What happens when 1,000 concurrent requests miss the same popular key?

The final question leads directly to the production concerns explored in later chapters.

---

# Layer 3 — Production Engineering & Interview Mastery

## 14. The Cache-Aside Pattern Is Not a Consistency Guarantee

Cache-aside is easy to understand, but concurrency creates edge cases.

Imagine:

```text
Request A                  Request B
---------                  ---------
Read old product from DB
                           Update product in DB
                           Delete Redis key
Write old product to Redis
```

The final Redis entry can contain stale data even though Request B invalidated the key.

This is a race condition. Simple “update database, then delete cache” logic does not eliminate every possible stale-write scenario.

For many read-heavy endpoints, a short TTL and cache invalidation may be an acceptable trade-off. For stricter requirements, the design may need versioned entries, coordinated updates, or a different consistency strategy.

Do not promise strong consistency simply because your application deletes a key after a database update.

## 15. Common Production Failure Modes

### Failure 1 — Cache stampede

A popular key expires, and many requests simultaneously query the database to refill it.

```text
1,000 requests
      |
      v
Same cache miss
      |
      v
1,000 database queries
```

Potential mitigations include:

- Request coalescing or single-flight loading.
- A short randomized TTL variation to avoid synchronized expirations.
- Background refresh for suitable data.
- Carefully designed locking when its overhead and failure modes are understood.
- Database capacity controls.

The right solution depends on the workload. A distributed lock is not automatically the best first choice.

### Failure 2 — Stale cached data

The source database changes, but the cache is not updated or invalidated correctly.

Mitigations:
- Define invalidation behavior for every relevant write path.
- Choose TTLs based on freshness requirements.
- Test concurrent reads and writes.
- Monitor stale-data symptoms where measurable.

### Failure 3 — Redis outage

The application cannot read or write cached values.

A common strategy is to fall back to PostgreSQL for cache reads, provided the database has enough capacity. Cache writes may be skipped temporarily when they are not required for correctness.

But consider the consequences: if all requests suddenly hit PostgreSQL, a Redis outage can overload the database.

Mitigations:
- Bound Redis connection and command timeouts.
- Use connection pooling appropriately.
- Apply database-side concurrency limits and application load shedding where necessary.
- Monitor database saturation during cache degradation.
- Decide whether each endpoint should fail open or fail closed.

“Fail open” means continuing without the cache where safe. It does not mean bypassing authentication, authorization, or other essential controls.

### Failure 4 — Memory pressure

Redis memory is finite. If the workload exceeds available memory, performance or write behavior depends on configuration and the selected eviction policy.

Possible causes:
- Unbounded keys.
- Missing TTLs.
- Oversized cached values.
- Excessive duplication.
- A workload whose working set no longer fits.

Later Redis chapters will cover eviction policies, memory accounting, persistence, and deeper operational diagnostics.

### Failure 5 — Cache key collision or tenant leakage

A key does not include enough context to distinguish two resources or authorization boundaries.

For example, caching a response under:

```text
profile:current
```

is dangerous if that key is shared across different users.

Prefer identity-aware keys and ensure cached responses respect authorization. A cache hit must never bypass the checks required to decide whether a caller may access a resource.

### Failure 6 — Cache miss treated as a database failure

A missing cache entry is normally an expected condition, not an application error.

Correct logic:

```text
Redis key absent
      |
      v
Read from PostgreSQL
```

Incorrect logic:

```text
Redis key absent
      |
      v
Return HTTP 500
```

A cache miss should trigger the normal loading path unless the application's design explicitly defines otherwise.

## 16. Choosing a Cache TTL

There is no universally correct TTL.

| Data | Possible starting approach | Important consideration |
|---|---|---|
| Product details | Minutes | How quickly must catalog changes appear? |
| Public configuration | Minutes or longer | How are configuration updates propagated? |
| User profile | Short TTL or explicit invalidation | How sensitive is profile freshness? |
| Real-time inventory | Very short TTL or no cache for critical reads | Can stale stock cause overselling? |
| Search results | Short TTL | Query diversity and invalidation complexity |
| Authentication or authorization state | Carefully designed, if cached at all | Revocation and security requirements |

These are illustrative strategies, not universal production defaults.

For business-critical values such as inventory or prices, decide which operations require authoritative reads or stronger consistency. Do not rely on TTL alone when stale data could cause unacceptable business outcomes.

## 17. Measure Whether Caching Helps

A cache should improve a measurable outcome.

Track relevant metrics such as:

- Cache hit and miss counts.
- Hit ratio.
- Redis command latency.
- Redis errors and connection failures.
- Redis memory usage.
- Key expirations and evictions.
- PostgreSQL query latency and connection utilization.
- API p50, p95, and p99 latency.
- Request volume during cache degradation.

For example, compare the same endpoint before and after introducing Redis:

| Measurement | Before cache | After cache |
|---|---:|---:|
| API p95 latency | Measure | Measure |
| Database queries per second | Measure | Measure |
| Cache hit ratio | N/A | Measure |
| Error rate | Measure | Measure |

Do not invent benchmark improvements. Run a controlled test with a representative workload, comparable data, and clearly defined measurement conditions.

A high hit ratio is useful only if it translates into meaningful improvements without unacceptable correctness or operational costs.

## 18. Security Basics

Treat Redis as an internal infrastructure service, not a public API.

Baseline precautions:

- Keep Redis on a private network.
- Require authentication and use ACLs where appropriate.
- Use TLS when required by your network and security architecture.
- Restrict network access to authorized application services.
- Avoid placing credentials in source code or committed configuration.
- Protect sensitive cached values and minimize unnecessary retention.
- Avoid untrusted serialized object deserialization.
- Use separate credentials or access policies when applications have different trust boundaries.
- Keep Redis and its client libraries updated.

Redis's availability on an internal network does not make every command safe for every caller. Apply least privilege and limit operational access.

## 19. SDE-1 Interview Questions & Answers

### Q1. What is Redis?

Redis is an in-memory data structure server commonly used for caching, counters, ephemeral state, coordination, and selected data-processing workloads.

### Q2. Why is Redis commonly used as a cache?

It can serve frequently accessed data quickly and reduce repeated work on the primary database.

### Q3. What is a cache hit?

The requested value is present in the cache and can be served from it.

### Q4. What is a cache miss?

The requested value is absent or unavailable, so the application generally follows a fallback path such as querying the database.

### Q5. What is TTL?

Time to live is the configured lifetime of a key before it expires.

### Q6. What is cache-aside?

The application checks the cache first, loads missing data from the source database, and populates the cache.

### Q7. Redis vs. PostgreSQL?

Redis provides fast access to in-memory data structures and is often used as a cache. PostgreSQL provides relational storage, SQL queries, and transactional guarantees. They solve different problems.

### Q8. When would you use a Redis hash?

When a resource is naturally represented as fields under one key and those fields need to be accessed or updated individually.

### Q9. When would you use a sorted set?

When members need to be ranked or ordered by scores, such as in a leaderboard.

### Q10. What is a cache stampede?

Many requests attempt to reload the same missing or expired key concurrently, potentially overwhelming the backing database.

### Q11. Does a high cache hit ratio guarantee good performance?

No. Latency, error rates, memory pressure, stale data, and database load also matter.

### Q12. What happens if Redis goes down?

Cache reads and writes may fail. The application needs a deliberate degradation strategy that accounts for database capacity and endpoint correctness.

### Q13. Why should cache keys follow a naming convention?

Consistent names improve isolation, troubleshooting, observability, and maintainability.

### Q14. Why can `KEYS *` be dangerous?

It may traverse a large keyspace in one operation and introduce disruptive latency. Incremental iteration with `SCAN` is generally more suitable for operational inspection.

### Q15. Is Redis always the source of truth?

No. In many backend systems, a relational database remains authoritative while Redis stores a rebuildable copy. Redis can serve as primary storage in other architectures, depending on the durability and consistency requirements.

---

## 20. Mastery Assessment

Try these before moving to Chunk 2.

**1. Design:** Your product endpoint receives 5,000 reads per minute for the same product. Would you consider Redis? What would you measure before and after?

**2. Debugging:** Redis returns a value, but the value is older than PostgreSQL. Name two plausible causes and explain how you would investigate.

**3. Reliability:** Redis becomes unavailable during peak traffic. What happens to PostgreSQL load if every API request falls back to the database?

**4. Data structures:** Choose an appropriate Redis structure for each:
- A page-view counter.
- A leaderboard.
- Unique members of a group.
- A user's individual profile fields.
- An ordered event-consumption workflow.

**5. Design trade-off:** Why might a two-minute TTL be reasonable for product descriptions but inappropriate for certain inventory checks?

**6. Code review:** Identify the risk in a cache key that omits a tenant ID when multiple tenants can have resources with the same local identifier.

### Completion checklist

- [ ] I can explain Redis without describing it merely as a database replacement.
- [ ] I can distinguish a cache hit from a cache miss.
- [ ] I can explain cache-aside and TTL.
- [ ] I can choose between strings, hashes, lists, sets, sorted sets, and streams.
- [ ] I can execute the core Redis CLI commands.
- [ ] I can integrate a basic Redis cache into Spring Boot.
- [ ] I understand why stale data and cache stampedes occur.
- [ ] I can explain how a Redis outage can increase database load.
- [ ] I can identify key-naming and authorization risks.
- [ ] I can describe what to measure to prove caching is beneficial.

---

## What Comes Next?

**Redis — Chunk 2 of 3: Persistence, Eviction, TTL Strategy, Caching Patterns & Consistency**

The next chapter moves beyond basic caching into memory management, eviction policies, persistence trade-offs, cache invalidation, write-through versus write-behind approaches, and consistency under concurrent updates.

**Repository workflow:** Save this chapter as `content/redis/01-redis-caching-fundamentals-data-structures.md`. Do not generate a PDF yet. The complete Redis PDF should be generated only after all three Redis chapters have been saved and verified.
