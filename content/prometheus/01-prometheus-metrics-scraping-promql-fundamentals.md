# Prometheus — Chunk 1 of 2: Metrics, Time Series & Monitoring Fundamentals

**Backend Engineering Tools & Infrastructure Handbook**

## Learning Objectives

By the end of this chapter, you should be able to:

- Explain what Prometheus does and why backend engineers use it.
- Understand metrics, labels, time series, samples, and scrape intervals.
- Distinguish counters, gauges, histograms, and summaries.
- Configure Prometheus to scrape a Spring Boot application's metrics.
- Write basic PromQL queries for request rates, errors, latency, and resource usage.
- Understand exporters, service discovery, and instrumentation.
- Debug missing targets, missing metrics, and misleading dashboards.
- Explain how metrics differ from logs and distributed traces.

Chunk 1 establishes the foundations and hands-on workflow. Chunk 2 covers production alerting, SLOs, recording rules, scaling, reliability, security, incident response, and advanced interview mastery.

# Layer 1 — Fundamentals & Mental Models

## 1. What Is Prometheus?

Prometheus is an open-source monitoring and alerting toolkit designed around numerical time-series data.

Backend engineers use it to answer questions such as:

- How many HTTP requests is my API receiving?
- What percentage of requests are failing?
- Is API latency increasing?
- Is the application running out of memory?
- Are database connections becoming saturated?
- Is a background worker falling behind?
- Did a deployment cause a performance regression?

Prometheus collects metric samples, stores them as time series, and provides a query language called PromQL.

A typical architecture looks like this:

```text
Spring Boot API ─────┐
Node Exporter ───────┼──> Prometheus ──> PromQL queries
Redis Exporter ──────┤         |
Other services ──────┘         +──> Alerting rules
                                      |
                                      v
                               Alertmanager
                                      |
                                      v
                              Notification channels
```

Grafana can query Prometheus and visualize its data. Alertmanager handles alert grouping, routing, and notification workflows when configured.

Prometheus is not a replacement for application logs, distributed tracing, or a full incident-management process. Each provides different evidence.

## 2. The Mental Model: A Time Series

A metric is a numerical measurement. A time series is a sequence of samples identified by a metric name and its label set.

Consider:

```text
http_requests_total{
  method="GET",
  route="/orders",
  status="200"
} 1250
```

This says the current recorded counter value for that particular combination of labels is `1250`.

Prometheus stores timestamped samples over time, conceptually:

| Timestamp | Value |
|---|---:|
| 10:00:00 | 1200 |
| 10:00:15 | 1215 |
| 10:00:30 | 1230 |
| 10:00:45 | 1250 |

A query can analyze this history rather than only the latest value.

### The four building blocks

- **Metric name:** what is measured, such as `http_requests_total`.
- **Labels:** dimensions describing the series, such as method or status.
- **Sample:** a numerical value with a timestamp.
- **Scrape interval:** how frequently Prometheus retrieves metrics from a target.

### Why labels matter

The following are different time series:

```text
http_requests_total{method="GET",status="200"}
http_requests_total{method="POST",status="201"}
http_requests_total{method="GET",status="500"}
```

Each distinct combination of metric name and labels identifies a separate series.

Labels enable filtering and aggregation, but too many distinct combinations create high cardinality. That can increase memory consumption, storage requirements, and query cost.

**Rule:** Use labels for bounded dimensions, not arbitrary user-specific values.

Good label candidates:

- HTTP method.
- Normalized route.
- Status class.
- Service name.
- Environment.

Dangerous label candidates:

- User ID.
- Email address.
- Request ID.
- Raw URL containing arbitrary IDs.
- Unbounded search queries.

A route label should generally use a normalized route such as `/orders/{id}`, rather than `/orders/839472`.

## 3. The Four Core Metric Types

Prometheus instrumentation commonly uses counters, gauges, histograms, and summaries.

### Counter

A cumulative value that increases over time and can reset when the process restarts.

- **Characteristics:** Monotonically increasing (can reset to 0 on application restart). Never decreases during normal operation.
- **Typical examples:** Total requests served, processed background jobs, failed payment attempts, bytes transmitted.
- **Typical PromQL query:**

```promql
rate(http_requests_total[5m])
```

---

### Gauge

A value that can arbitrarily increase or decrease over time.

- **Characteristics:** Snapshot of current state. Goes up or down at any time.
- **Typical examples:** Active concurrent requests, queue depth, resident memory usage, active database connections, CPU temperature.
- **Typical PromQL query:**

```promql
process_resident_memory_bytes
```

---

### Histogram

Observations are sampled into configurable, cumulative buckets. Histograms support latency distribution analysis and percentile calculations.

- **Characteristics:** Exposes `<basename>_bucket{le="..."}`, `<basename>_count`, and `<basename>_sum`. Allows aggregation across multiple target instances.
- **Typical examples:** HTTP request duration, database query execution duration, payload sizes.
- **Typical PromQL query:**

```promql
histogram_quantile(
  0.95,
  sum by (le) (
    rate(http_server_request_duration_seconds_bucket[5m])
  )
)
```

---

### Summary

Records observations and exposes direct client-calculated quantiles (such as φ=0.5, 0.9, 0.99) along with observation count and sum.

- **Characteristics:** Quantiles are computed on the client side. Unlike histograms, client-computed summary quantiles cannot be aggregated across multiple instances.
- **Typical examples:** High-accuracy percentile tracking on a single instance where bucket boundaries are unknown in advance.

---

### Counter vs gauge: the common interview trap

A counter is cumulative. A gauge is a current measurement.

Do not use a counter to represent the number of active requests because that value can decrease. Use a gauge for the current number of in-flight requests.

Likewise, don't interpret a counter's absolute value as the current request rate. Use `rate()` or `increase()` over an appropriate time range.

## 4. Pull-Based Monitoring: How Scraping Works

Prometheus commonly uses a pull model: it periodically requests metrics from configured targets.

```text
Prometheus                       Spring Boot
    |                                |
    |------ GET /actuator/prometheus->|
    |<----- metrics exposition -------|
    |                                |
    |------ wait for interval --------|
    |                                |
    |------ GET /actuator/prometheus->|
```

The endpoint returns a metrics exposition format that Prometheus can parse.

A scrape configuration might look like:

```yaml
scrape_configs:
  - job_name: "orders-api"
    metrics_path: "/actuator/prometheus"
    static_configs:
      - targets: ["localhost:8080"]
```

Here, `localhost:8080` means the address from Prometheus's network perspective. If Prometheus runs in a separate container, `localhost` usually refers to the Prometheus container itself, not the Spring Boot container.

### Why pull-based collection is useful

- Prometheus controls collection intervals.
- Targets can expose metrics without implementing a push pipeline.
- Target health is observable through scrape status.
- The same model works with applications and exporters.

### Does Prometheus always require pull?

No. Prometheus-compatible systems can integrate with push-oriented workflows through components such as the Pushgateway for certain short-lived jobs. It is not a general replacement for scraping long-running services, and it should not be used as an arbitrary event-ingestion system.

## 5. Scrape Targets, Jobs, and Instances

A **target** is an endpoint Prometheus scrapes.

A **job** groups targets of a similar role.

An **instance** normally identifies an individual target, often through its address.

Example:

```yaml
scrape_configs:
  - job_name: "orders-api"
    static_configs:
      - targets:
          - "orders-api-1:8080"
          - "orders-api-2:8080"
```

Prometheus can then distinguish the two instances while allowing queries to aggregate both.

This is useful for identifying whether:

- One instance is unhealthy.
- One replica has much higher latency.
- A particular deployment is generating errors.
- Only a subset of targets is being scraped.

## 6. Metrics, Logs, and Traces Are Different

The three pillars of observability provide complementary signals during an investigation:

| Telemetry Pillar | Concrete Example | Primary Diagnostic Role |
|---|---|---|
| **Metrics** (*Prometheus*) | *"Error rate rose to 8% at 10:05."* | **Aggregation & Trends:** Best for real-time rates, system health indicators, capacity tracking, and automated threshold alerts. |
| **Logs** | *"Order 481 failed because the database connection timed out."* | **Context & Root Cause:** Best for discrete event records, stack traces, diagnostic error messages, and payload inspection. |
| **Traces** | *"The request spent 900 ms waiting for PostgreSQL after a 20 ms proxy hop."* | **Path & Bottleneck Analysis:** Best for distributed request propagation, inter-service call graphs, and pinpointing slow hops across microservices. |

These systems complement one another.

For example, Prometheus alerts you to a latency spike. Logs help explain the affected requests, and traces can reveal which dependency consumed most of the time.

## 7. What Is an Exporter?

An exporter exposes metrics about a system through an endpoint Prometheus can scrape.

Examples include:

- Node Exporter for host-level metrics.
- Redis Exporter for Redis-related metrics.
- PostgreSQL exporters for database metrics.
- Blackbox Exporter for probing endpoints and network services.

An exporter translates system-specific information into a format Prometheus can collect.

### Application instrumentation vs exporters

**Application instrumentation** measures application behavior directly, such as request duration or business-operation counters.

**Exporters** commonly expose metrics from systems that do not natively expose the required Prometheus metrics.

You may need both. Host CPU metrics cannot, by themselves, explain why a specific API endpoint is slow.

# Layer 2 — Practical Engineering & Workflows

## 8. Run Prometheus Locally with Docker

Create a project directory:

```bash
mkdir prometheus-lab
cd prometheus-lab
```

Create a file named `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "prometheus"
    static_configs:
      - targets: ["localhost:9090"]
```

Create `compose.yaml`:

```yaml
services:
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus-lab
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    command:
      - "--config.file=/etc/prometheus/prometheus.yml"
      - "--storage.tsdb.path=/prometheus"

volumes:
  prometheus_data:
```

For a reproducible or production deployment, pin a tested image version or digest rather than relying indefinitely on `latest`.

Start it:

```bash
docker compose up -d
docker compose logs -f prometheus
```

Open the Prometheus web interface at:

`http://localhost:9090`

Check target health through **Status → Targets**.

You should see the Prometheus target become healthy if the container and configuration are correct.

### Useful operational commands

```bash
docker compose ps
docker compose logs --tail=100 prometheus
docker compose restart prometheus
```

To stop the lab:

```bash
docker compose down
```

This preserves the named data volume. To remove it too, you would need to explicitly remove the volume, which deletes stored time-series data.

## 9. Configure Spring Boot Metrics

For a Spring Boot application, Actuator and Micrometer are common ways to expose application metrics.

Add the appropriate dependencies to your Maven project:

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-actuator</artifactId>
</dependency>

<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-registry-prometheus</artifactId>
</dependency>
```

Use dependency versions managed by your Spring Boot project's dependency management unless you have a specific compatibility reason not to.

Configure the metrics endpoint in `application.yml`:

```yaml
management:
  endpoints:
    web:
      exposure:
        include: health,prometheus
  endpoint:
    health:
      show-details: never
```

This example exposes health and Prometheus endpoints through the configured management web endpoint. Review management-port, network, and authentication settings before deployment.

Start the application and test:

```bash
curl -i http://localhost:8080/actuator/health
curl -i http://localhost:8080/actuator/prometheus
```

The Prometheus endpoint should return a text exposition of the metrics available through the registry and instrumentation.

If the endpoint returns `404`, check whether the dependencies are present, the application started successfully, and the endpoint is exposed at the path you expect.

## 10. Connect Prometheus to Spring Boot

Update `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "prometheus"
    static_configs:
      - targets: ["localhost:9090"]

  - job_name: "orders-api"
    metrics_path: "/actuator/prometheus"
    static_configs:
      - targets: ["host.docker.internal:8080"]
```

`host.docker.internal` is commonly available in Docker Desktop environments to reach the host from a container. The appropriate address differs by operating system and deployment setup. In Docker Compose, using the backend's service name on a shared network is often cleaner.

Reload or restart Prometheus after updating the file, depending on its reload configuration:

```bash
docker compose restart prometheus
```

Then inspect **Status → Targets**. The `orders-api` target should show as `UP` when the endpoint is reachable and the scrape succeeds.

### What if the target is `DOWN`?

Check in this order:

1. Does the Spring Boot application run?
2. Does the metrics endpoint respond directly?
3. Can the Prometheus container resolve and reach the target address?
4. Is the port correct?
5. Does the application expose the metrics endpoint at the configured path?
6. Does the Prometheus log explain a connection, parsing, or HTTP error?

Avoid changing multiple settings simultaneously. Verify each layer separately.

## 11. Your First PromQL Queries

PromQL is Prometheus's query language.

Open the Prometheus expression browser and try the following queries.

### Query 1 — Is the target scrape healthy?

```promql
up
```

Prometheus usually exposes `up` for configured scrape targets:

- `1` means the last scrape succeeded.
- `0` means the last scrape failed.

Filter to one job:

```promql
up{job="orders-api"}
```

### Query 2 — Inspect available metrics

```promql
{job="orders-api"}
```

This selector is useful for exploring series belonging to the job, although a metric-name selector is more precise once you know what to inspect.

For a specific metric, try:

```promql
process_resident_memory_bytes
```

Metric availability depends on the application's dependencies, instrumentation, and configuration.

### Query 3 — Request rate

For an HTTP request counter:

```promql
rate(http_server_requests_seconds_count[5m])
```

This is a common metric pattern in Micrometer-based Spring applications. Exact names and labels depend on the Spring Boot and Micrometer versions and the instrumentation being used.

The query estimates the per-second rate of increase over a five-minute window.

### Query 4 — Request volume over a window

```promql
increase(http_server_requests_seconds_count[1h])
```

This estimates the counter increase over the selected one-hour window. It can produce fractional estimates because Prometheus extrapolates counter behavior at the window boundaries.

### Query 5 — Filter by status

Metric names and label names must match the actual exposed series. A common Micrometer HTTP metric includes a `status` label:

```promql
sum by (status) (
  rate(http_server_requests_seconds_count[5m])
)
```

This aggregates the observed request rate by status code.

If your instrumentation uses a different metric or label, inspect the available series and adapt the query.

### Query 6 — Approximate 5xx error ratio

```promql
sum(
  rate(http_server_requests_seconds_count{status=~"5.."}[5m])
)
/
sum(
  rate(http_server_requests_seconds_count[5m])
)
```

This computes the share of requests represented by matching 5xx series, assuming the metric and label conventions match the query.

Handle the no-traffic case deliberately: the denominator may be zero or no series may be returned. Also ensure the numerator and denominator cover the same intended population of requests.

## 12. Understand Histograms and Percentiles

Latency averages can hide slow requests.

Imagine 100 requests:

- 95 complete in 50 ms.
- 5 complete in 2 seconds.

The average alone may not convey how bad the slowest requests feel to users.

Percentiles help describe a distribution:

- **p50:** median latency.
- **p95:** 95% of observations are at or below this value, according to the distribution estimate.
- **p99:** 99% are at or below this value.

If your application exposes classic Prometheus histogram buckets, a p95 query can look like:

```promql
histogram_quantile(
  0.95,
  sum by (le) (
    rate(http_server_requests_seconds_bucket[5m])
  )
)
```

`le` identifies the upper bound of each classic histogram bucket.

The query aggregates bucket rates across instances before estimating the percentile. This is important: calculating each instance's percentile and then averaging the percentiles is generally not equivalent to calculating a fleet-wide percentile.

### Histogram caveats

- Bucket boundaries determine the quality of the estimate.
- A percentile is an estimate, not necessarily an exact observed duration.
- A metric may use a native histogram or a different instrumentation convention.
- The exact metric name depends on the library and version.
- Sparse traffic can make short-window percentiles unstable.

**Engineering takeaway:** Choose histogram boundaries and observation windows based on actual latency objectives and traffic volume.

## 13. Scrape Interval and Retention

The scrape interval determines how frequently Prometheus collects samples from targets.

```yaml
global:
  scrape_interval: 15s
```

A shorter interval gives finer temporal resolution but increases collection overhead and the number of samples stored.

A longer interval reduces collection volume but can miss short-lived spikes and delays detection.

Retention controls how long historical data is kept. It depends on configuration, storage capacity, and operational requirements.

A simple storage intuition:

```text
More targets
  × more time series per target
  × more samples per series
  × longer retention
  = more storage and processing demand
```

This is not a precise storage formula, because compression, churn, and other factors matter. It captures the variables you need to reason about.

## 14. Common Prometheus Problems

### Problem A — Target is `DOWN`

Likely causes:

- Wrong host or port.
- Application is stopped.
- Metrics endpoint is not exposed.
- Container networking is incorrect.
- Authentication or TLS requirements are missing.
- The target returns an error or invalid exposition.

Start with `up`, the Targets page, and Prometheus logs.

### Problem B — The metric doesn't exist

Possible causes:

- The relevant instrumentation is not installed.
- No request or operation has triggered the metric yet.
- The metric name differs from your assumption.
- The metric is not exposed by the registry.
- The metric changed across library versions.

Use the endpoint itself to inspect available metrics, then query the exact name.

### Problem C — Dashboard values look wrong

Check:

- Units: seconds vs milliseconds, bytes vs megabytes.
- Counter vs gauge semantics.
- Whether the query uses `rate()` for a counter.
- Whether aggregation groups the correct labels.
- Whether the dashboard window matches the incident.
- Whether the metric includes every relevant instance.
- Whether missing series or no traffic is handled correctly.

A dashboard can be visually attractive and still be operationally misleading.

# Layer 3 — Production Engineering & Interview Mastery

## 15. Production Scenario: Error Rate Rises After a Deployment

**Scenario:** Your Spring Boot API's 5xx error ratio rises immediately after a deployment.

### Step 1 — Confirm the symptom

Query the error rate:

```promql
sum(
  rate(http_server_requests_seconds_count{status=~"5.."}[5m])
)
```

Compare it with total request rate:

```promql
sum(
  rate(http_server_requests_seconds_count[5m])
)
```

### Step 2 — Compare the baseline

Inspect the same time window before and after deployment. Look at the affected routes, instances, and status codes where those dimensions are available.

### Step 3 — Correlate with other signals

- Application logs: stack traces and exception messages.
- Traces: slow or failing downstream calls.
- Database metrics: connection-pool saturation and query latency.
- Infrastructure metrics: CPU, memory, and restarts.
- Deployment records: version and configuration changes.

### Step 4 — Choose a mitigation

If evidence strongly connects the issue to the release, a controlled rollback may be safer than trying to repair production configuration through multiple unverified edits.

### Step 5 — Verify recovery

Confirm that the error ratio returns toward baseline, latency stabilizes, and the intended version is running.

**Lesson:** Prometheus detects and quantifies a symptom. Root-cause analysis requires correlated evidence.

## 16. Production Scenario: Memory Is Increasing

**Scenario:** The process's resident memory rises over several hours.

Inspect the metric:

```promql
process_resident_memory_bytes
```

For a particular job:

```promql
process_resident_memory_bytes{job="orders-api"}
```

Then investigate:

1. Is memory rising across every instance or only one?
2. Did traffic volume increase?
3. Is the growth correlated with a particular workload?
4. Are containers approaching their memory limits?
5. Are garbage collection and heap metrics available?
6. Does the process stabilize or continue growing after traffic drops?
7. Do logs or heap diagnostics suggest retained objects or a leak?

Do not conclude that every rise is a memory leak. Caches, warm-up, workload, and normal memory-management behavior can all affect usage.

## 17. Production Scenario: Metrics Disappear

**Scenario:** A Grafana panel shows gaps even though the API appears healthy.

Investigate:

- Target scrape status.
- Prometheus restarts and logs.
- Application endpoint availability.
- Changes to metric names or labels after deployment.
- Prometheus configuration changes.
- Time-range and query-window selection.
- Resource pressure and scrape duration.
- Whether the metric series is created only after a relevant event.

A missing series is not always the same as a numerical zero. Dashboard and alert logic must account for missing data explicitly.

## 18. Cardinality and Cost Control

Cardinality is the number of distinct time series.

Consider:

```text
http_requests_total{route="/orders/{id}",status="200"}
```

This uses a bounded route label.

By contrast:

```text
http_requests_total{path="/orders/847239"}
```

If every request has a different path value, Prometheus may create a very large number of series.

High cardinality can lead to:

- Increased memory consumption.
- Higher storage usage.
- Slower queries.
- Increased ingestion overhead.
- Greater operational complexity.

### Practical controls

1. Normalize route labels.
2. Avoid user IDs, raw URLs, request IDs, and arbitrary strings as labels.
3. Review newly introduced labels before deployment.
4. Track active series and cardinality growth.
5. Use logs or traces for high-cardinality event-level context.
6. Keep metric dimensions aligned with real operational questions.

**Interview takeaway:** Labels are dimensions, not a place to store arbitrary event data.

## 19. Monitoring Is Not the Same as Observability

Monitoring commonly asks whether a system is operating within expected bounds.

Observability uses available telemetry to help explain unfamiliar internal behavior.

Prometheus supports both, especially through metrics and derived indicators, but metrics alone may not identify the precise cause of a novel incident.

A mature backend setup combines:

- Metrics for trends, rates, and alerting.
- Logs for event-level details.
- Traces for request-path analysis.
- Deployment metadata for change correlation.
- Runbooks and operational procedures for response.

## 20. Interview Questions and Answers

### Q1. What is Prometheus?

An open-source monitoring and alerting toolkit that collects, stores, and queries time-series metrics.

### Q2. What is a time series?

A sequence of timestamped samples identified by a metric name and label set.

### Q3. What is a scrape?

Prometheus's process of fetching metrics from a configured target endpoint.

### Q4. What does `up` mean?

It is a target-health metric: `1` generally indicates the last scrape succeeded; `0` indicates failure.

### Q5. Why use `rate()` on a counter?

It estimates the average per-second increase over a selected window and accounts for counter resets.

### Q6. What is the difference between a counter and a gauge?

A counter accumulates increases and may reset. A gauge represents a value that can rise or fall.

### Q7. What is a histogram?

A metric type that groups observations into buckets and records counts and sums, allowing distribution analysis and percentile estimation.

### Q8. Why can averaging p95 values be misleading?

Percentiles are not generally additive or linearly composable. Aggregate histogram buckets first, then calculate the desired percentile for a fleet-wide estimate.

### Q9. What is cardinality?

The number of distinct time series. High cardinality can increase memory, storage, and query costs.

### Q10. Why avoid user IDs as metric labels?

They can create an unbounded number of time series. High-cardinality event details belong in other telemetry systems.

### Q11. What is an exporter?

A component that exposes metrics from a system in a format Prometheus can scrape.

### Q12. What is the difference between metrics and logs?

Metrics summarize numerical behavior over time. Logs capture individual events and their contextual details.

### Q13. Why might a Prometheus target be down even though the service is healthy?

The scrape endpoint may be unreachable, incorrectly configured, inaccessible from the Prometheus network, or returning an error.

### Q14. What does a shorter scrape interval change?

It improves temporal resolution and may reduce detection delay, but increases collection and storage overhead.

### Q15. What is the role of Grafana?

Grafana queries data sources such as Prometheus and visualizes metrics through dashboards and related workflows.

### Q16. Does Prometheus automatically know every metric in your application?

No. Metrics must be exposed through supported instrumentation or exporters and collected by configured targets.

### Q17. What is the Pushgateway for?

It supports selected short-lived or batch jobs that cannot be scraped reliably during their lifetime. It is not a general-purpose replacement for scraping long-running services.

### Q18. Why can a missing metric be different from zero?

A series may not exist because the event has never occurred, instrumentation is missing, or collection failed. Zero is an actual value; absence requires separate interpretation.

### Q19. How would you investigate a latency spike?

Use PromQL to establish timing and scope, then correlate with application metrics, logs, traces, infrastructure, and deployment history.

### Q20. Does a successful scrape prove the application is healthy?

No. It proves that the metrics endpoint was scraped successfully. The application can still return errors, be slow, or fail important business operations.

## 21. Hands-On Mastery Assessment

Complete this checklist to verify your foundational Prometheus competency:

- [ ] Run Prometheus locally and inspect its scrape target.
- [ ] Expose Spring Boot metrics through Actuator and Micrometer.
- [ ] Configure Prometheus to scrape the application.
- [ ] Explain the difference between a counter and a gauge.
- [ ] Use `up` to verify scrape health.
- [ ] Query a request counter with `rate()`.
- [ ] Calculate a 5xx ratio using the actual metric names and labels.
- [ ] Explain how histogram buckets support percentile estimation.
- [ ] Find and fix a deliberately incorrect target address.
- [ ] Explain why high-cardinality labels can destabilize monitoring.
- [ ] Distinguish metrics, logs, and traces in an incident.
- [ ] Document the first checks for a missing metric or target.

## 22. Chunk 1 Summary

You now have the foundations of Prometheus monitoring:

- Metrics and time series.
- Counters, gauges, histograms, and summaries.
- Pull-based scraping, targets, jobs, and exporters.
- Spring Boot Actuator and Micrometer integration.
- Core PromQL patterns for health, request rates, errors, and latency.
- Cardinality risks and practical debugging workflows.
- The relationship between metrics, logs, and traces.

**Next: Prometheus — Chunk 2 of 2: Alerting, SLOs, Recording Rules, Production Reliability & Incident Mastery.**

That chapter will complete the fixed two-chunk Prometheus curriculum, including alert rules, Alertmanager, actionable alert design, production scaling, security, and advanced incident scenarios.
