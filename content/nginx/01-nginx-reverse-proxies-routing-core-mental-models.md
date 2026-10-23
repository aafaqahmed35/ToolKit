# Nginx — Chunk 1 of 2: Reverse Proxies, HTTP Routing & Core Mental Models

**Backend Engineering Tools & Infrastructure Handbook**

**Source file:** `content/nginx/01-nginx-reverse-proxies-routing-core-mental-models.md`

---

## Learning Objectives

By the end of this chapter, you should be able to:

- Explain what Nginx does and why backend systems use it.
- Distinguish a reverse proxy from a forward proxy and a load balancer.
- Trace an HTTP request from a client through Nginx to a Spring Boot application.
- Understand Nginx configuration structure, server blocks, and location matching.
- Configure Nginx to serve static files and reverse-proxy API requests.
- Forward the correct client and protocol headers to your backend.
- Diagnose common `502`, `504`, `403`, and routing failures.
- Explain Nginx's role in a production backend architecture.

This chapter focuses on fundamentals and practical workflows. Chunk 2 will deepen production operations, load balancing, TLS, reliability, security, performance, and incident mastery.

# Layer 1 — Fundamentals & Mental Models

## 1. What Is Nginx?

Nginx (pronounced *engine-x*) is a web server and reverse proxy commonly used in backend infrastructure.

It can:

- Serve static assets such as HTML, CSS, JavaScript, images, and downloads.
- Forward HTTP requests to backend applications.
- Distribute requests across multiple backend instances.
- Terminate TLS connections.
- Apply routing rules, timeouts, and request-size limits.
- Support caching and other traffic-management features.

Imagine your Spring Boot API runs on port `8080`. Instead of exposing that application port directly to every client, you place Nginx in front of it.

```text
Client → Nginx → Spring Boot API → PostgreSQL
```

Nginx becomes the public-facing entry point. Your application can concentrate on business logic while Nginx handles HTTP traffic management.

### Why not expose Spring Boot directly?

You can expose Spring Boot directly, and small applications sometimes do. Nginx becomes useful when you need a dedicated traffic layer.

| Concern | Spring Boot application | Nginx |
|---|---|---|
| Business logic | Primary responsibility | Not its role |
| Database operations | Yes | No |
| API validation | Yes | Limited request-level controls |
| Static file serving | Possible | Efficient and common |
| Reverse proxying | Usually not its main role | Core capability |
| TLS termination | Supported | Common deployment pattern |
| Traffic distribution | Possible through other components | Built-in load-balancing capabilities |

**Mental model:** Nginx manages the traffic path; your backend manages the application behavior.

## 2. Forward Proxy vs Reverse Proxy

These two proxies sit on opposite sides of a communication.

```text
Forward proxy:
Client → Forward Proxy → Internet

Reverse proxy:
Internet Client → Reverse Proxy → Backend Server
```

### Forward proxy

A forward proxy represents or mediates traffic from clients.

For example, a company may route employee web traffic through a proxy to enforce access policies or filter destinations.

The client typically knows it is using the proxy.

### Reverse proxy

A reverse proxy represents one or more backend servers.

A client requests:

`https://api.example.com/orders/123`

Nginx receives the request and forwards it to an internal application such as:

`http://127.0.0.1:8080/orders/123`

The client does not need to know the internal address or port.

### Why reverse proxies matter

1. **Hide internal topology:** clients don't need direct access to application instances.
2. **Centralize traffic handling:** routing and TLS configuration can live in one layer.
3. **Scale horizontally:** requests can be distributed across several backend instances.
4. **Separate concerns:** traffic management can change without rewriting business logic.
5. **Provide a consistent entry point:** multiple services can be exposed through one domain.

A reverse proxy is not automatically a firewall or a complete security boundary. Network rules and application-level security still matter.

## 3. Reverse Proxy vs Load Balancer

A reverse proxy receives requests and forwards them to backend servers. A load balancer distributes requests among multiple eligible backends.

These are not mutually exclusive categories: **Nginx can act as both a reverse proxy and a load balancer.**

Single backend:

```text
Client → Nginx → Spring Boot :8080
```

Multiple backends:

```text
                     ┌→ Spring Boot :8081
Client → Nginx ──────┼→ Spring Boot :8082
                     └→ Spring Boot :8083
```

With multiple backends, Nginx can use policies such as round-robin, weighted distribution, or least connections, depending on the configuration and edition.

We will configure and analyze load balancing in Chunk 2.

## 4. The HTTP Request Lifecycle

Consider a request to retrieve an order:

`GET https://api.example.com/orders/123`

A typical request path looks like this:

```text
1. Client resolves api.example.com through DNS.
2. Client establishes a TCP connection to the public endpoint.
3. TLS is negotiated if HTTPS is used.
4. Nginx receives and parses the HTTP request.
5. Nginx selects a server block and location.
6. Nginx forwards the request to the configured upstream.
7. Spring Boot processes the request.
8. Spring Boot returns an HTTP response.
9. Nginx relays the response to the client.
```

The exact path depends on the deployment. For example, TLS may terminate at a cloud load balancer before the request reaches Nginx.

### What can go wrong at each stage?

| Stage | Example failure |
|---|---|
| DNS | Domain resolves to the wrong IP |
| TCP connection | Connection refused or timeout |
| TLS | Certificate or handshake failure |
| Nginx routing | Wrong server block or location |
| Upstream connection | Spring Boot is down; often a `502` |
| Upstream response time | Backend exceeds proxy timeout; often a `504` |
| Application | Spring Boot returns `400`, `404`, or `500` |
| Response path | Connection drops or response is interrupted |

A useful debugging rule is to identify **which layer generated the failure** rather than assuming every HTTP error originates in the application.

## 5. Nginx Architecture: Master and Worker Processes

Nginx typically uses a master process and worker processes.

- **Master process:** reads configuration, manages workers, and coordinates reloads.
- **Worker processes:** handle network connections and process requests.
- **Configuration files:** define listeners, routing rules, upstreams, and other behavior.
- **Logs:** provide evidence about incoming requests and failures.

Nginx is designed around event-driven, non-blocking connection handling. A worker can manage many concurrent connections without requiring one operating-system thread per connection.

This is especially useful for high numbers of mostly I/O-bound network connections.

However, event-driven networking does not make slow upstream applications magically faster. If a backend is overloaded, proxying more requests can still increase latency and resource pressure.

### Important distinction

Nginx's worker model and your application's concurrency model are separate. A large number of client connections handled by Nginx does not imply that the Spring Boot application can process the same number of expensive operations without saturation.

## 6. Configuration File Structure

A common Linux installation uses:

- `/etc/nginx/nginx.conf` — main configuration.
- `/etc/nginx/conf.d/` — commonly used for additional configuration files.
- `/etc/nginx/sites-available/` and `/etc/nginx/sites-enabled/` — commonly used by Debian/Ubuntu packaging.
- `/var/log/nginx/access.log` — access log.
- `/var/log/nginx/error.log` — error log.

Exact paths and included files vary by operating system and installation method. Inspect the active configuration rather than assuming a directory is enabled.

### Main configuration concepts

| Directive or block | Purpose |
|---|---|
| `worker_processes` | Controls worker process count |
| `events` | Configures connection-processing behavior |
| `http` | Contains HTTP server and upstream configuration |
| `server` | Defines a virtual server, commonly selected by port and hostname |
| `listen` | Defines an address or port to listen on |
| `server_name` | Identifies hostnames handled by a server block |
| `location` | Matches request URIs |
| `proxy_pass` | Forwards requests to an upstream |
| `root` | Defines a filesystem root for static files |
| `index` | Defines default index filenames |
| `include` | Loads additional configuration files |

### A minimal configuration

```nginx
events {
    worker_connections 1024;
}

http {
    server {
        listen 8088;
        server_name localhost;

        location / {
            return 200 "Nginx is running\n";
        }
    }
}
```

This example demonstrates the hierarchy and a simple response. It is not a production deployment configuration.

### Test before applying changes

```bash
nginx -t
```

If Nginx is installed outside the standard configuration path, specify the appropriate configuration file:

```bash
nginx -t -c /path/to/nginx.conf
```

A successful configuration test means Nginx can parse the configuration and perform relevant checks. It does not prove that every upstream is reachable or that every route behaves correctly.

## 7. Server Blocks and Host-Based Routing

A server block defines how Nginx handles requests matching its listening address, port, and host-selection rules.

Example:

```nginx
server {
    listen 80;
    server_name api.example.com;

    location / {
        return 200 "API entry point\n";
    }
}

server {
    listen 80;
    server_name admin.example.com;

    location / {
        return 200 "Admin entry point\n";
    }
}
```

Both server blocks listen on port `80`, but their `server_name` values allow Nginx to route requests for different hostnames to different configurations.

This is called **name-based virtual hosting**.

### Common mistakes

- The requested hostname does not match the intended `server_name`.
- Another server block becomes the default for the listening address.
- The configuration file exists but is not included by the active configuration.
- A change was made, but Nginx was never reloaded.
- DNS points to a different machine than expected.

Inspect the complete active configuration with:

```bash
nginx -T
```

Use care when sharing this output: configuration dumps can contain internal hostnames, paths, and sensitive operational details.

## 8. Location Matching: How Nginx Chooses a Route

The `location` directive matches the request URI path.

Common forms include:

```nginx
location = /health {
    return 200 "healthy\n";
}

location /api/ {
    # API routes
}

location ^~ /assets/ {
    # Static assets
}

location ~ \.php$ {
    # Example of a case-sensitive regular-expression match
}
```

### The essential matching rules

- `location = /path` — exact match; if it matches, it wins immediately.
- `location ^~ /prefix/` — prefix match that prevents a later regular-expression match from taking precedence.
- `location ~ pattern` — case-sensitive regular expression.
- `location ~* pattern` — case-insensitive regular expression.
- `location /prefix/` — ordinary prefix match.

For ordinary prefix locations, Nginx generally remembers the longest matching prefix and then checks regular-expression locations, unless the chosen prefix uses `^~`. Regular expressions are evaluated in configuration order, and the first matching regular expression wins.

The full algorithm has nuances, so don't rely on the simplistic claim that Nginx always chooses the longest string in the file.

### Example

```nginx
server {
    listen 8088;
    server_name localhost;

    location = /health {
        return 200 "exact health match\n";
    }

    location /api/ {
        return 200 "API prefix match\n";
    }

    location / {
        return 200 "fallback match\n";
    }
}
```

Test each route:

```bash
curl -i http://localhost:8088/health
curl -i http://localhost:8088/api/orders
curl -i http://localhost:8088/about
```

Expected behavior:

- `/health` matches the exact location.
- `/api/orders` matches the `/api/` prefix.
- `/about` falls back to `/`.

### Trailing slash traps

`/api` and `/api/` are different URI paths. A location declared as `location /api/` does not directly express an exact match for `/api`.

If you want `/api` to redirect to `/api/`, you can define the behavior explicitly:

```nginx
location = /api {
    return 301 /api/;
}

location /api/ {
    # API handling
}
```

Use redirects deliberately. A redirect changes the client-visible URL and can affect HTTP methods, caching, and API consumers.

## 9. `proxy_pass`: Forwarding Requests to Spring Boot

This is one of the most important Nginx directives for backend engineers.

Assume Spring Boot listens on:

`http://127.0.0.1:8080`

You want Nginx to receive requests on port `80` and forward API traffic to the application.

```nginx
server {
    listen 80;
    server_name api.example.com;

    location /api/ {
        proxy_pass http://127.0.0.1:8080;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

With this configuration, a request for:

`http://api.example.com/api/orders/123`

is forwarded upstream with the URI path preserved as:

`/api/orders/123`

This matters because your Spring Boot controller must expect the path that actually reaches the application.

### Why forward these headers?

| Header | Why it matters |
|---|---|
| `Host` | Preserves the original host information |
| `X-Real-IP` | Passes a client-address value |
| `X-Forwarded-For` | Carries a chain of proxy/client addresses |
| `X-Forwarded-Proto` | Indicates the original request scheme, such as HTTP or HTTPS |

These headers are only trustworthy if your proxy chain is configured correctly. A backend directly exposed to untrusted clients must not blindly trust client-supplied forwarding headers. Configure trusted proxies and the framework's forwarded-header behavior deliberately.

### Important: `proxy_pass` trailing-slash behavior

These configurations can forward different URI paths.

**Configuration A — no URI component:**

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8080;
}
```

A request to `/api/orders` is normally forwarded as `/api/orders`.

**Configuration B — URI component `/`:**

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8080/;
}
```

For a straightforward prefix location, the matched `/api/` prefix is replaced by `/`, so `/api/orders` is forwarded as `/orders`.

This is a frequent source of backend `404` errors. If Spring Boot expects `/api/orders`, removing `/api/` upstream may break the route. Conversely, if the application expects `/orders`, stripping the prefix may be intentional.

**Rule:** Test the actual upstream URI. Never add or remove a trailing slash based on appearance alone.

## 10. Serving Static Files

Nginx can serve files directly without involving Spring Boot.

Example directory:

```text
/var/www/myapp/
├── index.html
├── assets/
│   ├── app.js
│   └── app.css
└── images/
    └── logo.png
```

Configuration:

```nginx
server {
    listen 8088;
    server_name localhost;

    root /var/www/myapp;
    index index.html;

    location / {
        try_files $uri $uri/ =404;
    }
}
```

`try_files` checks candidate filesystem paths and returns `404` if none exists in this example.

### `root` vs `alias`

These directives are related but not identical.

- `root` appends the request URI to the configured root path.
- `alias` replaces the matched location prefix with a specified filesystem path.

Example using `alias`:

```nginx
location /downloads/ {
    alias /srv/app-downloads/;
}
```

A request for `/downloads/report.pdf` maps to `/srv/app-downloads/report.pdf`.

Be careful with path mapping and trailing slashes. Incorrect filesystem mapping can cause missing-file errors or unintentionally expose files.

## 11. Local Lab: Put Nginx in Front of a Backend

You can perform this lab on your development machine. The examples assume Nginx and a backend are reachable from the same host. Containerized deployments need appropriate service names and networking instead of blindly using `127.0.0.1`.

### Step 1 — Start a test backend

If you already have a Spring Boot API listening on port `8080`, use it. Otherwise, create a temporary HTTP service for testing:

```bash
python3 -m http.server 8080
```

This is a simple static-file server, not a Spring Boot API. Keep it running in one terminal.

Verify the backend:

```bash
curl -i http://127.0.0.1:8080/
```

### Step 2 — Configure Nginx

Create a server block in a configuration file included by your Nginx installation:

```nginx
server {
    listen 8088;
    server_name localhost;

    location / {
        proxy_pass http://127.0.0.1:8080;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Ensure the file is included by the active `http` configuration. Avoid overwriting the main configuration blindly.

### Step 3 — Validate and reload

```bash
nginx -t
```

After a successful test, reload using the service manager or installation-specific command. For a typical Linux systemd installation:

```bash
sudo systemctl reload nginx
```

Check service status:

```bash
sudo systemctl status nginx
```

On macOS or a containerized setup, the service commands and paths may differ.

### Step 4 — Test through Nginx

```bash
curl -i http://127.0.0.1:8088/
```

Compare the response from port `8088` with the direct backend response from port `8080`.

### Step 5 — Inspect logs

```bash
sudo tail -f /var/log/nginx/access.log
```

In another terminal:

```bash
sudo tail -f /var/log/nginx/error.log
```

Generate a request and observe which log entries appear. Your installation may use different paths or permissions.

### Step 6 — Deliberately create a failure

Stop the test backend, then run:

```bash
curl -i http://127.0.0.1:8088/
```

Nginx will generally return `502 Bad Gateway` when it cannot connect to the configured upstream. Inspect the error log, restart the backend, and repeat the request.

**Lab result:** You have demonstrated the difference between the public-facing proxy and the upstream application, plus the role of logs in diagnosing an upstream failure.

## 12. Common Nginx Errors and First Checks

| Symptom | Likely areas to inspect | First action |
|---|---|---|
| `502 Bad Gateway` | Backend down, wrong upstream host/port, refused connection | `curl` the upstream directly |
| `504 Gateway Timeout` | Upstream too slow or unreachable, network delay | Check backend latency and Nginx error log |
| `403 Forbidden` | Filesystem permissions, access rules, directory traversal rules | Inspect the path and Nginx worker permissions |
| `404 Not Found` | Wrong location, URI rewrite, missing file, backend route | Compare requested and upstream paths |
| `413 Content Too Large` | Request-body size limit | Inspect `client_max_body_size` and application requirements |
| `400 Bad Request` | Malformed request, host or protocol mismatch, application validation | Determine which layer generated the response |
| `504` only under load | Saturated backend, slow dependency, too-short timeout | Measure latency and resource saturation before changing timeouts |

These are diagnostic starting points, not definitive mappings. An application can itself return a `502` or `504`, and a proxy can return a `404` based on its own configuration.

## 13. Security Fundamentals

Even a basic reverse proxy configuration needs sound security practices.

1. **Don't expose unnecessary ports.** Clients should reach the intended public entry point; internal backend ports should be restricted by network controls.
2. **Protect secrets.** Don't commit credentials, private keys, or sensitive environment values to Git.
3. **Validate forwarding headers.** Trust them only from known proxy infrastructure.
4. **Limit request sizes appropriately.** An oversized upload should not consume unlimited resources.
5. **Keep software patched.** Use a supported Nginx release and maintain the underlying operating system or container image.
6. **Protect logs.** Access logs may contain identifiers, query strings, or other sensitive data.
7. **Use TLS for public production traffic.** TLS termination and certificate operations are covered in Chunk 2.
8. **Avoid reflexive timeout increases.** A longer timeout can keep resources occupied while an unhealthy backend remains slow.

Nginx is one layer of defense, not a replacement for authentication, authorization, input validation, safe database access, or application security.

# Layer 2 — Practical Engineering & Workflows

## 14. The Backend Engineer's Nginx Debugging Workflow

When an API endpoint fails, proceed from the application outward rather than changing several settings at once.

### Step A — Test the application directly

```bash
curl -i http://127.0.0.1:8080/actuator/health
```

Use a real endpoint appropriate for your application. The Spring Boot Actuator health endpoint is available only if Actuator is installed and the endpoint is enabled and accessible.

If this fails, investigate the application, port, and dependencies before blaming Nginx.

### Step B — Verify Nginx configuration

```bash
sudo nginx -t
sudo nginx -T
```

Check server names, listeners, included files, locations, upstream addresses, and `proxy_pass` paths.

### Step C — Verify the listening ports

On Linux:

```bash
sudo ss -ltnp
```

Confirm that Nginx and the backend are listening on the intended addresses and ports.

### Step D — Inspect logs

```bash
sudo tail -n 100 /var/log/nginx/error.log
sudo tail -n 100 /var/log/nginx/access.log
```

Look for the timestamp of the failing request, the upstream address, connection errors, and response status.

### Step E — Reproduce through the proxy

```bash
curl -i \
  -H 'Host: api.example.com' \
  http://127.0.0.1/api/orders
```

This tests the selected host-based routing rule on a local Nginx listener. Adapt the port and path to your environment.

### Step F — Change one thing and retest

After making a targeted change:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

This is a common Linux systemd workflow. It does not apply unchanged to every installation.

Re-run the same request and compare the result. A successful reload is not proof that the application behavior is correct.

## 15. Backend Deployment Architecture

A common architecture is:

```text
Client
  |
  | HTTPS
  v
Nginx
  |
  | HTTP over a restricted internal network
  v
Spring Boot API
  |
  +------> PostgreSQL
  |
  +------> Redis
  |
  +------> Kafka
```

The components have distinct responsibilities:

- **Nginx:** public HTTP entry point, routing, and potentially TLS termination.
- **Spring Boot:** API behavior and business rules.
- **PostgreSQL:** durable relational data.
- **Redis:** caching or other suitable low-latency data operations.
- **Kafka:** asynchronous event streaming when the architecture requires it.

Nginx does not replace the database, message broker, or application. It provides a traffic-management layer in front of services.

In a Docker Compose environment, `127.0.0.1` inside the Nginx container refers to that Nginx container itself. To reach a backend in another Compose service, use the service name on the shared network, such as `http://api:8080`, provided the service is actually named `api`.

This localhost distinction is one of the most common deployment mistakes.

# Layer 3 — Production Engineering & Interview Mastery

## 16. Interview Questions and Answers

### Q1. What is Nginx?

Nginx is a web server and reverse proxy that can serve static content, route requests, forward traffic to backends, and distribute requests across upstream servers.

### Q2. What is the difference between a forward proxy and a reverse proxy?

A forward proxy mediates client traffic to destinations. A reverse proxy receives client requests on behalf of backend servers and forwards them to those servers.

### Q3. Is Nginx a load balancer?

It can be. Nginx supports reverse proxying to one backend or distributing requests across multiple upstream servers.

### Q4. What happens when Nginx returns `502 Bad Gateway`?

It often means Nginx could not obtain a valid response from the upstream. Check backend health, connection refusal, address/port correctness, networking, and the error log.

### Q5. How does `502` differ from `504`?

A `502` commonly indicates an invalid or unavailable upstream response. A `504` indicates that a gateway or proxy did not receive a timely upstream response. The exact cause must be established from logs and request behavior.

### Q6. What does `proxy_pass` do?

It forwards a request to a configured upstream. Its URI component and interaction with the matched location affect the path that reaches the backend.

### Q7. Why set `X-Forwarded-For`?

It can carry client and proxy address information through the proxy chain. It must be interpreted using a trusted-proxy policy because request headers can be spoofed by untrusted clients.

### Q8. What is a server block?

A server block defines request-handling rules for a listening address and host configuration, including server names, locations, and upstream behavior.

### Q9. What is the difference between `root` and `alias`?

`root` combines the configured root with the request URI. `alias` maps a matched location to a specified filesystem path by replacing the matched location prefix.

### Q10. How do you validate an Nginx configuration?

Run `nginx -t` with the appropriate configuration path. Inspect the complete active configuration with `nginx -T` when needed.

### Q11. Why might a correct-looking `proxy_pass` produce a backend `404`?

The URI may be rewritten differently than expected, the wrong location may match, or the backend route may not exist. Compare the incoming URI with the URI forwarded upstream.

### Q12. What is the difference between a reverse proxy and an API gateway?

A reverse proxy focuses on forwarding and traffic management. An API gateway may additionally provide API-oriented policies such as authentication integration, quotas, transformations, and centralized API lifecycle controls. Products can overlap, so compare actual capabilities rather than relying only on labels.

### Q13. Why is Nginx often used for static files?

It can serve files directly without consuming application-server resources for every static asset request.

### Q14. Why should you avoid blindly increasing proxy timeouts?

Longer timeouts can tie up connections and resources while an unhealthy backend remains slow. First determine whether the problem is legitimate workload, saturation, dependency latency, or a connectivity issue.

### Q15. Does Nginx automatically make a backend secure?

No. It can contribute to security through TLS, routing, and request controls, but the system still needs secure application logic, authentication, authorization, network controls, secret management, and appropriate trust boundaries.

## 17. Production Scenario: API Returns `404` Only Through Nginx

**Scenario:** Calling the Spring Boot service directly works, but calling the public API through Nginx returns `404`.

Investigate in this order:

1. Reproduce the same HTTP method and URI against the direct backend.
2. Inspect the active `server_name` and determine which server block handles the request.
3. Identify the matching `location`.
4. Inspect the `proxy_pass` directive, especially whether it includes a trailing slash or URI component.
5. Compare the original request URI with the upstream URI.
6. Check Nginx access/error logs and application logs at the same timestamp.
7. Change only the incorrect routing or path-mapping rule and retest.

**Key lesson:** If direct backend access works but proxy access fails, the proxy's routing or URI transformation becomes a high-value investigation target.

## 18. Practical Mastery Assessment

Review your understanding of key Nginx concepts:

1. **Which component normally owns business rules?**
   - *Options:* Nginx, Spring Boot, DNS
   - *Correct Answer:* Spring Boot
   - *Why:* Nginx manages traffic; the application implements business behavior.

2. **What should you run before reloading an edited Nginx configuration?**
   - *Options:* `nginx -t`, `git reset --hard`, `redis-cli FLUSHALL`
   - *Correct Answer:* `nginx -t`
   - *Why:* It checks configuration syntax and related validity before applying changes.

3. **Nginx cannot connect to a stopped upstream. Which response is common?**
   - *Options:* `502 Bad Gateway`, `201 Created`, `301 Moved Permanently`
   - *Correct Answer:* `502 Bad Gateway`
   - *Why:* An unavailable upstream connection commonly produces a `502`.

4. **What does `127.0.0.1` mean inside an Nginx container?**
   - *Options:* The host in all cases, The Nginx container itself, The public DNS server
   - *Correct Answer:* The Nginx container itself
   - *Why:* Loopback refers to the current network namespace, not automatically another container.

5. **Which location is an exact match for `/health`?**
   - *Options:* `location / { }`, `location = /health { }`, `location ~* .css { }`
   - *Correct Answer:* `location = /health { }`
   - *Why:* The equals modifier selects an exact URI match.

## 19. Hands-On Completion Checklist

- [ ] Explain forward proxy, reverse proxy, and load balancing without memorized definitions.
- [ ] Draw the request path from client to Nginx to Spring Boot.
- [ ] Identify the main Nginx configuration blocks and inspect the active configuration.
- [ ] Configure a server block with an exact-match health route and an API prefix.
- [ ] Reverse-proxy a local backend and verify the request with curl.
- [ ] Explain how `proxy_pass` trailing-slash behavior can change an upstream URI.
- [ ] Diagnose a deliberately stopped upstream using curl and the error log.
- [ ] Explain why localhost behaves differently inside a container.
- [ ] Describe the trust and security implications of forwarded headers.

## 20. Chunk 1 Summary

You should now understand Nginx as a traffic-management layer that can serve static files, select routes, and proxy requests to backend applications. You have practiced the configuration hierarchy, server blocks, location matching, `proxy_pass`, forwarded headers, and a structured debugging workflow.

**Next: Nginx — Chunk 2 of 2: Production Load Balancing, TLS, Reliability, Security & Incident Mastery.**

That final chunk will complete the Nginx curriculum and cover production-grade upstream configuration, health and failure behavior, TLS termination, operational observability, performance tradeoffs, incident simulations, and advanced interview preparation.
