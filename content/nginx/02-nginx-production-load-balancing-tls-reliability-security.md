# Nginx — Chunk 2 of 2: Production Load Balancing, TLS, Reliability, Security & Incident Mastery

**Backend Engineering Tools & Infrastructure Handbook**

**Source file:** `content/nginx/02-nginx-production-load-balancing-tls-reliability-security.md`

---

## Learning Objectives

By the end of this chapter, you should be able to:

- Configure Nginx to distribute requests across multiple backend instances.
- Explain upstream health, failure handling, connection limits, and timeouts.
- Understand TLS termination, HTTPS redirection, and certificate renewal.
- Configure production-minded request limits, headers, and access controls.
- Diagnose latency, connection failures, unhealthy upstreams, and deployment regressions.
- Understand Nginx logs, metrics, and the limits of proxy-level observability.
- Make informed tradeoffs about caching, buffering, and connection management.
- Answer production-focused Nginx interview questions.

This completes the two-chunk Nginx curriculum. The next stage is to save and verify both source files before producing the final Nginx handbook PDF.

# Layer 1 — Fundamentals & Mental Models

## 1. From a Single Backend to a Production Traffic Layer

A single-instance deployment might look like this:

```text
Clients
   |
   v
 Nginx
   |
   v
Spring Boot :8080
   |
   v
PostgreSQL
```

This is simple, but the application is a single point of failure. If Spring Boot stops, Nginx cannot successfully serve dynamic API requests.

A horizontally scaled design introduces multiple application instances:

```text
                    +--> Spring Boot :8081
Clients --> Nginx --+--> Spring Boot :8082
                    +--> Spring Boot :8083
                              |
                              v
                          PostgreSQL
```

Nginx can distribute incoming requests among configured upstream servers.

However, multiple instances introduce new questions:

- How are requests distributed?
- What happens when one instance fails?
- How do we avoid sending traffic to a starting or unhealthy instance?
- How are application versions deployed safely?
- How do we identify whether latency comes from Nginx, the application, or a downstream dependency?

Production Nginx configuration is about answering these questions deliberately, not merely adding more servers.

## 2. Upstream Groups and Load-Balancing Algorithms

An `upstream` block defines a group of backend servers.

```nginx
http {
    upstream orders_api {
        server 127.0.0.1:8081;
        server 127.0.0.1:8082;
        server 127.0.0.1:8083;
    }

    server {
        listen 80;
        server_name api.example.com;

        location / {
            proxy_pass http://orders_api;
        }
    }
}
```

By default, Nginx distributes requests using a round-robin strategy.

### Common strategies

| Strategy | Mental model | Useful when |
|---|---|---|
| Round robin | Distribute requests in rotation | Backends have broadly similar capacity |
| Weighted round robin | Give some servers a larger share | Instances have different capacities |
| Least connections | Prefer a server with fewer active connections | Request durations vary significantly |
| IP hash | Use client IP information to influence server selection | A limited form of affinity is needed |

The available methods and behavior depend on the Nginx edition, module, and configuration.

### Weighted round robin

```nginx
upstream orders_api {
    server 127.0.0.1:8081 weight=3;
    server 127.0.0.1:8082 weight=1;
}
```

This gives the first server a larger share of traffic over time. It does not guarantee an exact percentage over every short observation window.

### Least connections

```nginx
upstream orders_api {
    least_conn;

    server 127.0.0.1:8081;
    server 127.0.0.1:8082;
    server 127.0.0.1:8083;
}
```

This can be useful when some requests remain active much longer than others. But active connection count is only a proxy for workload: it does not directly measure CPU saturation, database contention, or request complexity.

**Interview takeaway:** A load-balancing algorithm distributes traffic; it does not automatically make a backend horizontally scalable. The application and its dependencies must tolerate concurrent requests and shared state.

## 3. Health Checks and Failure Handling

A backend can fail in several ways:

- Its process is stopped.
- Its port is not listening.
- It accepts connections but responds too slowly.
- It returns application errors.
- It is alive but cannot reach PostgreSQL or another critical dependency.

These conditions are not equivalent.

### Passive failure detection

In common Nginx Open Source configurations, upstream failure handling is primarily passive: Nginx observes failures while attempting real requests and can temporarily mark an upstream server unavailable according to configured parameters.

```nginx
upstream orders_api {
    server 127.0.0.1:8081 max_fails=3 fail_timeout=10s;
    server 127.0.0.1:8082 max_fails=3 fail_timeout=10s;
}
```

Here, `max_fails` and `fail_timeout` influence when an upstream server is considered temporarily unavailable under the applicable conditions.

These settings are not a universal active-health-check system. Exact behavior depends on the upstream configuration and Nginx edition.

### Active health checks

Active health checks periodically probe a backend independently of normal user traffic. These capabilities depend on the Nginx edition or an additional health-check mechanism.

A Spring Boot health endpoint might be:

```text
/actuator/health
```

The endpoint must be enabled and safely exposed. A basic process-health check is not necessarily proof that every dependency or business operation is healthy.

### Health-check design

A useful health strategy distinguishes:

- **Liveness:** is the application process functioning?
- **Readiness:** should this instance receive new traffic?
- **Dependency health:** can it access the resources needed to serve requests?

Avoid turning every transient downstream issue into an automatic restart loop. Health semantics should reflect the recovery behavior of the application and its platform.

## 4. Timeouts: Three Different Clocks

A proxy timeout is not the same as an application execution deadline.

Three important Nginx directives are:

```nginx
proxy_connect_timeout 3s;
proxy_send_timeout    30s;
proxy_read_timeout    30s;
```

- `proxy_connect_timeout`: time allowed to establish an upstream connection.
- `proxy_send_timeout`: timeout between successive writes while sending a request to the upstream.
- `proxy_read_timeout`: timeout between successive reads from the upstream.

A critical nuance: `proxy_read_timeout` generally measures inactivity between read operations, not the total wall-clock duration of the entire response.

For example, a streaming response that sends data periodically can remain active longer than the configured read timeout, while a backend that sends nothing for too long can trigger a timeout.

### Why blindly increasing timeouts is dangerous

Suppose an endpoint is slow because it performs a poorly indexed database query.

Increasing the proxy timeout might stop clients from receiving errors immediately, but it may also keep connections occupied longer and increase pressure during overload.

A better sequence is:

1. Measure request latency.
2. Check application and database traces or logs.
3. Identify whether the delay is expected or pathological.
4. Set timeouts consistent with the API's latency budget.
5. Apply concurrency controls and overload protection where appropriate.

## 5. TLS Termination and HTTPS

TLS protects data in transit between two endpoints.

A common deployment terminates public HTTPS at Nginx:

```text
Client
  |
  | HTTPS
  v
Nginx :443
  |
  | HTTP on a restricted internal network
  v
Spring Boot :8080
```

TLS termination lets Nginx handle the public certificate and encrypted client connection.

Whether the internal hop should also use TLS depends on the network trust boundary and security requirements. In untrusted or regulated environments, encrypting internal traffic may be necessary.

### Example HTTPS server block

```nginx
server {
    listen 443 ssl;
    server_name api.example.com;

    ssl_certificate     /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8080;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

The certificate paths are examples. They must exist and contain a valid certificate and private key for the deployed hostname.

### Redirect HTTP to HTTPS

```nginx
server {
    listen 80;
    server_name api.example.com;

    return 301 https://$host$request_uri;
}
```

This sends clients to the HTTPS URL while preserving the requested path and query string.

Before enabling a redirect, ensure HTTPS is configured and working. Otherwise, clients may be redirected to an unusable endpoint.

### Certificate operations

A production certificate lifecycle includes:

1. Issuing the certificate for the correct hostname.
2. Protecting the private key.
3. Installing the certificate chain and key.
4. Testing the Nginx configuration.
5. Reloading Nginx after renewal.
6. Monitoring expiration and renewal failures.

A certificate that was valid when first installed can still expire later. Renewal monitoring is therefore part of operations, not merely setup.

## 6. Connection Reuse and Upstream Keepalive

Repeatedly establishing upstream connections can add overhead.

Nginx can reuse upstream connections when the configuration, HTTP protocol, and upstream application support it.

Example pattern:

```nginx
upstream orders_api {
    server 127.0.0.1:8081;
    server 127.0.0.1:8082;

    keepalive 32;
}

server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_http_version 1.1;
        proxy_set_header Connection "";

        proxy_pass http://orders_api;
    }
}
```

This configures a per-worker cache of idle upstream keepalive connections. It does **not** impose a global maximum of 32 connections across all workers, nor does it mean every request will reuse a connection.

Keepalive can reduce connection-establishment overhead, but it must be configured in the context of backend connection limits, proxy concurrency, and the actual traffic pattern.

## 7. Buffering and Streaming

Nginx can buffer proxied responses and requests.

### Response buffering

With response buffering enabled, Nginx can read data from an upstream and buffer it before delivering all of it to the client. This can help protect the application from slow clients and decouple upstream response progress from downstream consumption.

However, large responses can consume memory or use temporary files.

### Streaming

For streaming APIs, server-sent events, or other responses that must reach clients incrementally, buffering behavior needs deliberate configuration.

Example:

```nginx
location /events/ {
    proxy_pass http://events_api;
    proxy_buffering off;
}
```

Whether this is appropriate depends on the application protocol. Disabling buffering indiscriminately can reduce efficiency or expose upstreams to slow-client pressure.

**Rule:** Choose buffering settings based on measured behavior and protocol requirements, not by copying a generic configuration.

# Layer 2 — Practical Engineering & Workflows

## 8. Build a Local Load-Balancing Lab

This lab demonstrates request distribution without requiring paid cloud infrastructure.

### Step 1 — Start two backend instances

If you have a Spring Boot application that supports a configurable port, start two instances using different ports. For example:

```bash
SERVER_PORT=8081 java -jar target/app.jar
```

In another terminal:

```bash
SERVER_PORT=8082 java -jar target/app.jar
```

These commands assume the application honors `SERVER_PORT` and that the built JAR exists. Use your project's actual JAR path and configuration.

For an observable test, expose a harmless diagnostic endpoint that identifies the instance. Do not expose sensitive environment information.

### Step 2 — Configure an upstream group

```nginx
upstream demo_api {
    server 127.0.0.1:8081;
    server 127.0.0.1:8082;
}

server {
    listen 8088;
    server_name localhost;

    location / {
        proxy_pass http://demo_api;

        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Ensure this configuration is included in the active Nginx `http` context.

### Step 3 — Test and reload

```bash
nginx -t
```

Then reload Nginx using the appropriate service command for your installation.

### Step 4 — Send repeated requests

```bash
for i in $(seq 1 10); do
    curl -s http://127.0.0.1:8088/instance
    echo
done
```

Replace `/instance` with your diagnostic endpoint.

Observe which instances handle the requests. Do not expect exact alternation in every setup if other configuration, connection behavior, or traffic is involved.

### Step 5 — Stop one backend

Stop the instance on port `8081` and repeat the test.

Observe the failure behavior and inspect the error log. Passive failure handling may temporarily avoid an upstream after enough qualifying failures, but the behavior depends on the configured failure conditions.

### Step 6 — Restore and document

Restart the stopped backend, repeat the test, and record:

- Whether both instances received traffic.
- How quickly a failed instance was avoided, if applicable.
- What errors appeared during failure.
- Whether recovery was automatic.
- What would need to change for explicit readiness-based health checks.

This lab teaches more than syntax: it demonstrates why failover behavior must be tested rather than assumed.

## 9. Production-Minded Configuration Example

The following example combines upstream routing, request limits, and conservative proxy timeouts. Adapt it to your environment rather than treating it as a universal production template.

```nginx
upstream orders_api {
    least_conn;

    server 127.0.0.1:8081 max_fails=3 fail_timeout=10s;
    server 127.0.0.1:8082 max_fails=3 fail_timeout=10s;

    keepalive 32;
}

server {
    listen 443 ssl;
    server_name api.example.com;

    ssl_certificate     /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;

    client_max_body_size 10m;

    location /api/ {
        proxy_pass http://orders_api;

        proxy_http_version 1.1;
        proxy_set_header Connection "";

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 3s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }
}
```

Before deploying it, verify:

- The certificate and key exist.
- The upstream instances are reachable from Nginx.
- The URI behavior matches the API's route design.
- The body-size limit fits legitimate uploads.
- The timeout values fit the API's latency budget.
- Forwarded headers are trusted only through the intended proxy chain.
- Logs, monitoring, and certificate renewal are configured.
- The configuration is compatible with the installed Nginx version.

## 10. Access Controls and Request Limits

### Restrict access to an internal endpoint

```nginx
location /internal/ {
    allow 10.0.0.0/8;
    deny all;

    proxy_pass http://internal_api;
}
```

This example permits the specified private address range and denies other addresses based on the client address Nginx sees.

If Nginx is behind another proxy or load balancer, that address may be the upstream proxy rather than the original client. Configure real-client-IP handling only with trusted proxy addresses and a deliberate trust policy.

IP-based restrictions are not a replacement for authentication and authorization.

### Request-body limits

```nginx
client_max_body_size 10m;
```

A limit that is too small may reject legitimate requests with `413 Content Too Large`. A limit that is too large can allow unnecessarily expensive uploads.

Choose limits based on the API contract and application constraints.

### Rate limiting

Nginx can apply request-rate controls using its request-limiting modules.

```nginx
http {
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

    server {
        listen 8088;

        location /api/ {
            limit_req zone=api_limit burst=20 nodelay;
            proxy_pass http://127.0.0.1:8080;
        }
    }
}
```

This is a basic example of per-client-address rate limiting. Its behavior depends on the configured zone, burst handling, and client identity.

Important production considerations:

- A single client IP may represent many users behind a NAT.
- An untrusted forwarding header should not be used as an identity key.
- Multiple Nginx instances do not automatically share local rate-limit counters.
- Distributed rate limits may require application-level or shared-state coordination.
- Legitimate bursts and retry storms should be considered.

## 11. Observability: Logs, Metrics, and Traces

Nginx provides valuable evidence about traffic, but it does not explain every application failure by itself.

### Access logs

Access logs can capture fields such as:

- Request method and URI.
- HTTP status code.
- Response size.
- Request processing time.
- Upstream response time.
- Upstream address.

A custom log format can help distinguish proxy overhead from upstream latency:

```nginx
http {
    log_format upstream_timing
        '$remote_addr "$request" status=$status '
        'request_time=$request_time '
        'upstream_time=$upstream_response_time '
        'upstream_addr=$upstream_addr';

    access_log /var/log/nginx/access.log upstream_timing;
}
```

Field availability and values depend on request flow and whether an upstream was contacted.

### How to interpret the timings

- `request_time` describes elapsed time processing the request from Nginx's perspective.
- `upstream_response_time` records upstream response timing information.
- A high upstream time suggests investigating the backend or its dependencies.
- A low upstream time with a slow overall request may indicate downstream transfer delays, buffering behavior, or other proxy/client-side factors.

These are clues, not conclusive root-cause proof. Correlate them with application metrics, database telemetry, and distributed traces.

### Metrics

Production monitoring may include:

- Request rate.
- Status-code distribution.
- Request latency percentiles.
- Active connections.
- Upstream failures.
- Backend saturation.
- TLS and certificate status.

Some metrics require an Nginx status endpoint, an exporter, or other instrumentation. Protect status endpoints so they do not unintentionally reveal operational details to the public.

### Tracing

Nginx access logs and metrics can help locate a slow hop, while distributed tracing can follow a request through the application and its dependencies.

Use a consistent request or trace identifier across the proxy and backend where supported. Do not trust arbitrary client-supplied identifiers for security decisions.

## 12. Graceful Reloads and Deployment Safety

A configuration change should not be deployed blindly.

Typical workflow:

```bash
nginx -t &&
sudo systemctl reload nginx
```

On systems using systemd, the reload command asks the service to apply configuration changes without treating it as a full stop-and-start operation. Exact behavior depends on the package and service configuration.

A safer deployment sequence is:

1. Validate configuration syntax.
2. Review the diff.
3. Confirm referenced files, certificates, and upstreams.
4. Reload the service.
5. Run a synthetic request through the public route.
6. Inspect status codes, latency, and logs.
7. Roll back the change if the regression is confirmed.

A reload command returning successfully does not establish that the new routing works for every hostname or API path.

# Layer 3 — Production Engineering & Interview Mastery

## 13. Incident Simulation A — All API Requests Return `502`

**Symptoms:** The Nginx endpoint is reachable, but requests to the API return `502 Bad Gateway`.

### Investigation

1. Confirm the response is generated by Nginx rather than the application.
2. Check whether the backend process is running.
3. Verify the actual listening address and port.
4. Test the upstream directly from the Nginx host or container.
5. Inspect Nginx error logs for connection refusal, resolution failures, or other upstream errors.
6. Verify container networking and whether `localhost` points to the intended service.
7. Restore connectivity and retest the public endpoint.

### Example commands

```bash
curl -i http://127.0.0.1:8081/actuator/health
sudo ss -ltnp
sudo tail -n 100 /var/log/nginx/error.log
```

Adapt commands to the environment and the application's enabled endpoints.

**Common root causes:** backend not started, incorrect port, incorrect container hostname, network restrictions, or an upstream service that is unavailable.

## 14. Incident Simulation B — Latency Spikes, but Nginx Is Healthy

**Symptoms:** The proxy responds, but API latency increases dramatically.

### Investigation

1. Compare overall request time with upstream response time.
2. Check Spring Boot request latency, thread pools, CPU, and memory.
3. Inspect database query latency and connection-pool saturation.
4. Check Redis, Kafka, and other dependencies if the affected request relies on them.
5. Compare latency by endpoint, status code, and time window.
6. Determine whether the incident affects one backend instance or all instances.
7. Apply a targeted mitigation and confirm recovery through measured latency.

Do not assume Nginx is responsible merely because the error appears at the public endpoint. The proxy may simply be revealing a slow upstream.

## 15. Incident Simulation C — One Backend Instance Is Unhealthy

**Symptoms:** Some requests fail while others succeed.

Potential causes include:

- One application instance is down.
- One instance has a configuration mismatch.
- One instance cannot reach the database.
- One instance is overloaded.
- The load-balancing policy is not behaving as expected.

### Response

1. Identify which upstream address correlates with failures.
2. Test each backend directly.
3. Compare application versions and configuration.
4. Review upstream failure logs and configured passive-failure parameters.
5. Remove or isolate the unhealthy instance using the approved operational process.
6. Verify that remaining capacity can handle the traffic.
7. Restore the instance only after it passes the appropriate readiness checks.

Avoid repeatedly reintroducing an unhealthy instance without understanding why it fails.

## 16. Incident Simulation D — HTTPS Works, but Redirected Requests Fail

**Symptoms:** HTTP requests redirect to HTTPS, but the destination returns a certificate warning or an error.

Investigate:

1. Does the HTTPS listener exist?
2. Is the certificate valid for the requested hostname?
3. Is the certificate chain configured correctly?
4. Does the private key match the certificate?
5. Is the certificate expired or not yet valid?
6. Is Nginx serving the intended virtual host?
7. Is the HTTPS upstream routing correct after TLS terminates?
8. Does the application incorrectly generate HTTP redirects because it does not correctly understand trusted forwarded-protocol information?

Fix the underlying certificate or proxy/application configuration. Disabling certificate verification is not a sound production fix.

## 17. Incident Simulation E — Requests Fail After an Nginx Configuration Change

**Symptoms:** An API route previously worked but now returns `404`, `403`, `413`, or `502`.

### Response checklist

- Compare the deployed configuration with the last known-good version.
- Run `nginx -T` and identify the active server block and location.
- Check whether the `proxy_pass` URI changed.
- Verify upstream hostnames and ports.
- Check request-size and access-control directives.
- Validate the configuration with `nginx -t`.
- Roll back the specific regression if needed.
- Re-run smoke tests for critical routes.
- Record the root cause and add a regression test or deployment check.

The fastest recovery is often a controlled rollback, not a sequence of unverified configuration edits.

## 18. Reliability and Capacity Tradeoffs

### One Nginx instance is still a single point of failure

Multiple application instances behind one Nginx process do not remove the proxy itself as a failure point.

Production systems may place multiple Nginx instances behind a cloud load balancer, virtual IP, or another supported entry-point mechanism.

### Proxy capacity is not backend capacity

Nginx may handle many open network connections, while the backend is limited by CPU, thread pools, database connections, or other dependencies.

Monitor both layers.

### Retries can amplify incidents

Retrying failed requests may improve resilience for certain transient failures, but retries can also amplify load during an outage.

Consider:

- Which methods and operations are safe to retry.
- Whether a request may have completed before a connection failed.
- Idempotency keys and duplicate side effects.
- Retry limits and backoff.
- The combined retry behavior of clients, proxies, and application code.

Never assume that a failed response means the backend performed no work.

### Sticky sessions have costs

Client affinity may help legacy stateful applications, but it can reduce flexibility in distributing load and complicate failover. Prefer shared or externalized session state when appropriate, while considering the added dependency and its failure modes.

## 19. Advanced Interview Questions

### Q1. How does Nginx choose an upstream server?

It uses the configured upstream group and load-balancing method. Round robin is the default for a standard upstream group; methods such as least connections and IP hash can be configured when suitable.

### Q2. What is the difference between passive and active health checks?

Passive checks infer failure from real traffic and upstream errors. Active checks independently probe backend health at intervals. Active-check support depends on the edition or additional modules used.

### Q3. Does `max_fails` guarantee that Nginx will detect every unhealthy backend?

No. It influences passive failure handling under the applicable conditions. It is not a complete application-readiness check and does not guarantee detection of every logical failure.

### Q4. What is the difference between `proxy_connect_timeout` and `proxy_read_timeout`?

The connection timeout controls establishing the upstream connection. The read timeout controls the allowed inactivity between upstream read operations.

### Q5. Why can a backend return `404` only when accessed through Nginx?

The proxy may select the wrong location, alter the URI through `proxy_pass`, or route to a different upstream. Compare direct and proxied requests and inspect the active configuration.

### Q6. What is TLS termination?

It is the point at which an endpoint accepts the encrypted TLS connection and handles decryption. Nginx can terminate client TLS and forward the request to an internal HTTP or HTTPS upstream.

### Q7. Is internal HTTP always safe after TLS termination?

No. Its suitability depends on the network trust boundary, infrastructure controls, and compliance requirements. Internal TLS may still be required.

### Q8. What is the purpose of upstream keepalive?

It can reuse idle upstream connections and reduce connection-establishment overhead. It must be configured with the relevant HTTP and upstream behavior in mind.

### Q9. What do `request_time` and `upstream_response_time` tell you?

They provide different views of request and upstream timing from Nginx's perspective. Comparing them helps narrow down where latency may be introduced, but neither replaces application-level telemetry.

### Q10. How would you protect an internal API route?

Use appropriate network restrictions, authentication and authorization, and careful proxy trust configuration. IP allowlists can be useful but should not be the only security mechanism.

### Q11. Why can a timeout increase worsen an outage?

Longer timeouts may keep more requests and connections occupied during backend overload, increasing resource pressure and delaying failure detection.

### Q12. How do retries interact with idempotency?

A retry may repeat an operation that already completed despite the client not receiving its response. Non-idempotent operations require safeguards such as idempotency keys or deduplication to prevent duplicate effects.

### Q13. Does round robin guarantee equal CPU usage across instances?

No. It distributes requests according to the configured policy, not according to actual CPU cost. Requests may have different execution times and resource requirements.

### Q14. How would you investigate intermittent upstream errors?

Correlate errors by upstream address, request time, status code, and application logs. Test instances individually and look for differences in configuration, resource saturation, network behavior, and dependency health.

### Q15. What is the relationship between Nginx and Kubernetes Ingress?

Nginx can be used as an ingress controller or as a proxy outside Kubernetes. Kubernetes Ingress is an API abstraction; an ingress controller implements the routing behavior. The specific Nginx integration and its capabilities depend on the controller and version.

### Q16. Why should status endpoints be protected?

They may reveal traffic levels, connection counts, and internal operational details. Expose only the information needed and restrict access appropriately.

### Q17. When is caching at Nginx appropriate?

It can help when responses are safely cacheable and invalidation semantics are understood. Personalized, authorization-sensitive, or rapidly changing responses need careful cache-key and policy design.

### Q18. What would you monitor for a public API proxy?

Request rate, status-code distribution, latency percentiles, upstream errors, active connections, backend saturation, certificate expiration, and relevant application/dependency metrics.

### Q19. Does multiple upstream configuration automatically provide high availability?

No. It helps distribute requests and can tolerate some instance failures, but only if failure behavior, remaining capacity, shared dependencies, network paths, and the proxy entry point itself are addressed.

### Q20. How do you deploy an Nginx change safely?

Review the diff, test configuration, verify referenced resources, reload using the appropriate service mechanism, run synthetic smoke tests, inspect logs and latency, and roll back if necessary.

## 20. Capstone: Put a Spring Boot API Behind Nginx

Build a local setup with:

- One Nginx reverse proxy.
- Two Spring Boot instances.
- A PostgreSQL dependency.
- A health endpoint suitable for operational checks.
- Access logs containing upstream timing.
- A small smoke-test script.
- A documented recovery procedure.

### Required exercises

1. Route requests to both backend instances.
2. Confirm the upstream URI matches the controller mapping.
3. Stop one backend and observe failure behavior.
4. Restore the instance and verify recovery.
5. Introduce a controlled slow endpoint and compare request timing with upstream timing.
6. Configure a local HTTPS test setup if you have suitable development certificates.
7. Apply a request-size limit and verify the expected response to an oversized request.
8. Document how you would secure an internal endpoint.
9. Record the steps required to roll back a faulty proxy configuration.
10. Explain which problems belong to Nginx, Spring Boot, PostgreSQL, or the deployment network.

Do not expose diagnostic endpoints or development credentials publicly. Use synthetic data for the lab.

## 21. Final Nginx Mastery Checklist

- [ ] I can explain reverse proxying and load balancing.
- [ ] I can write and validate a basic upstream configuration.
- [ ] I understand round robin, weighted distribution, least connections, and IP hash.
- [ ] I understand passive failure handling and its limitations.
- [ ] I can distinguish connection, send, and read timeouts.
- [ ] I can explain TLS termination and certificate renewal.
- [ ] I understand the role of upstream keepalive.
- [ ] I can reason about buffering and streaming.
- [ ] I can apply request-size and rate limits appropriately.
- [ ] I can interpret Nginx access logs and upstream timing.
- [ ] I can investigate `502`, `504`, routing, TLS, and configuration incidents.
- [ ] I understand why proxy health does not prove application health.
- [ ] I can describe a safe configuration deployment and rollback.
- [ ] I can explain the tradeoffs of retries, affinity, and caching.

## 22. Nginx Curriculum Completion Protocol

**Nginx content is complete across its two planned chunks.**

Expected authoritative Markdown files:

```text
content/nginx/
├── 01-nginx-reverse-proxies-routing-core-mental-models.md
└── 02-nginx-production-load-balancing-tls-reliability-security.md
```

After both files are saved and verified:

1. Review both chapters for continuity, examples, and technical consistency.
2. Confirm all three learning layers are covered across the two chunks.
3. Generate the **single final Nginx handbook PDF**, not PDFs per chunk.
4. Save it as:

```text
docs/nginx/BEH_NGINX_COMPLETE_HANDBOOK.pdf
```

5. Verify the PDF includes both complete chapters, code blocks, tables, and interview questions.
6. Update the README using verified completion status.
7. Commit the completed Nginx source and final PDF with the exact commit message:

```text
Nginx done
```

Do not mark the source, PDF, or Git commit complete until the corresponding work has actually been saved and verified.

---

**Nginx is now complete at the curriculum-content level.** The next tool in the locked sequence is **Prometheus — Chunk 1 of 2: Metrics, Time Series & Monitoring Fundamentals**.
