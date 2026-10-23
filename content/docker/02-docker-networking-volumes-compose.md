# Docker — Chunk 2: Networking, Volumes & Docker Compose
## Backend Engineering Tools & Infrastructure Handbook

**Phase:** II — Backend Infrastructure  
**Chunk:** 2 of 3  
**Source file:** `content/docker/02-docker-networking-volumes-compose.md`

---

## Learning Objectives

By the end of this chapter, you should be able to:

- Explain Docker networking and container-to-container communication.
- Choose between bridge networks, published ports, and host connectivity.
- Persist database data using volumes and understand bind mounts.
- Define a multi-service backend using Docker Compose.
- Diagnose DNS, connection-refused, port-mapping, and persistence failures.
- Explain production trade-offs and common Docker networking interview questions.

---

# Layer 1 — Fundamentals & Mental Models

## 1. Networking: Containers Need Addresses and Paths

Imagine a backend system:

- Spring Boot API listens on port `8080`.
- PostgreSQL listens on port `5432`.
- Redis listens on port `6379`.

All three services run in separate containers.

The API needs to connect to PostgreSQL and Redis. But how?

Docker provides networks that let containers communicate according to their network configuration.

**Mental model:** A container is an isolated process environment. To communicate, it needs a reachable destination, the correct port, and a service that is actually listening.

### Three networking concepts

| Concept | Meaning |
|---|---|
| Container port | Port on which the application listens inside the container |
| Published port | Host port mapped to a container port |
| Docker network | Network that allows connected containers to communicate |

Suppose PostgreSQL listens on port `5432` inside its container.

If your API runs in another container on the same user-defined bridge network, it can usually connect using:

`postgres:5432`

Here, `postgres` is the service or container name resolvable on that network.

If an application runs directly on your Mac and PostgreSQL is in a container with `-p 5432:5432`, the application can typically connect using:

`localhost:5432`

The hostname changes because the API and database run in different environments.

## 2. Bridge Networking

Docker's bridge networking connects containers through a virtual network on the host.

A user-defined bridge network is especially useful for local multi-container applications because connected containers can discover one another by name.

Create a network:

```bash
docker network create backend-net
docker network ls
docker network inspect backend-net
```

Start PostgreSQL on the network:

```bash
docker run -d \
  --name postgres \
  --network backend-net \
  -e POSTGRES_USER=app \
  -e POSTGRES_PASSWORD=local-dev-only \
  -e POSTGRES_DB=orders \
  postgres:16
```

Start another container on the same network:

```bash
docker run --rm \
  --network backend-net \
  postgres:16 \
  pg_isready -h postgres -p 5432
```

This second command runs PostgreSQL's readiness utility from another container and checks whether the database is accepting connections. The database may take a short time to initialize.

Notice that we did not publish port `5432` to the host. The two containers can still communicate over their shared network.

**Production principle:** Publish a port only when a host-side client or external network path needs it. Container-to-container communication does not inherently require host port publishing.

## 3. Why `localhost` Causes So Many Bugs

`localhost` always refers to the current network environment.

> ### Where Does `localhost` Point?
>
> - **API running directly on your Mac:** `localhost:5432` points to a service published on the Mac's host port 5432.
> - **API running in a container:** `localhost:5432` points to port 5432 inside the API container itself (loopback network namespace).
> - **API container connecting to Compose PostgreSQL:** `postgres:5432` points to PostgreSQL's service name and internal container port on the shared bridge network.


If your API container tries to connect to `localhost:5432`, it will not automatically reach the PostgreSQL container.

The hostname must reflect where the destination actually runs.

## 4. Port Publishing

Consider:

```bash
docker run -d \
  --name web \
  -p 8080:80 \
  nginx:alpine
```

The mapping is:

`host port 8080 → container port 80`

The browser reaches `http://localhost:8080`, while Nginx listens on port 80 inside the container.

If the application listens on port `8080` inside a Spring Boot container, a common mapping is:

```bash
docker run -p 8080:8080 orders-api:1.0
```

For a local development service that should only be reachable through the host loopback interface, you can bind explicitly:

```bash
docker run -p 127.0.0.1:8080:8080 orders-api:1.0
```

Publishing ports can make services reachable beyond the intended audience depending on the host, firewall, Docker configuration, and network environment. Avoid exposing databases or administrative services unnecessarily.

## 5. Volumes vs Bind Mounts

Containers have writable layers, but that layer is tied to the container's lifecycle. Persistent data should live outside that layer.

Docker supports two important storage approaches.

| Property | Named volume | Bind mount |
|---|---|---|
| Source | Managed by Docker | Specific host path |
| Typical use | Database data and persistent application state | Source code, local configuration, development files |
| Host-path control | Docker manages storage location | You choose the path |
| Portability | Easier to reference by volume name | Depends on host directory layout |

Create a named volume:

```bash
docker volume create pgdata
```

Mount it into PostgreSQL:

```bash
docker run -d \
  --name postgres \
  -e POSTGRES_PASSWORD=local-dev-only \
  -v pgdata:/var/lib/postgresql/data \
  postgres:16
```

Remove and recreate the container without deleting the volume, and the database data can persist.

A bind mount is useful when you want edits on your Mac to be visible inside a development container:

```bash
docker run --rm \
  -v "$PWD:/workspace" \
  -w /workspace \
  alpine:3.20 \
  ls -la
```

This mounts the current directory at `/workspace`. Host filesystem permissions and path behavior still matter.

### Important distinction

A volume provides persistence, not a complete backup strategy.

For valuable data, plan and test backups, recovery, and retention. A volume can still be deleted, corrupted, or lost with its underlying storage.

## 6. Docker Compose: One Definition, Multiple Services

A real backend often depends on more than one process.

You might need:

- Spring Boot for HTTP requests.
- PostgreSQL for durable relational data.
- Redis for caching.
- Kafka for asynchronous events.

Starting each service manually is error-prone. Docker Compose lets you define services, networks, volumes, and configuration in a YAML file.

**Mental model:** Compose describes a multi-container application and provides commands to manage its lifecycle.

Compose is useful for local development, testing, and some deployments. It does not automatically provide every production orchestration feature.

---

# Layer 2 — Practical Engineering & Workflows

## 7. Build a Multi-Service Application with Compose

Create a project structure:

```text
orders-platform/
├── compose.yaml
├── .env
├── .gitignore
└── api/
    ├── Dockerfile
    └── ...
```

The following Compose file starts PostgreSQL and Redis:

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: orders
      POSTGRES_USER: app
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD}
    volumes:
      - postgres-data:/var/lib/postgresql/data
    ports:
      - "127.0.0.1:5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d orders"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redis-data:/data
    ports:
      - "127.0.0.1:6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

volumes:
  postgres-data:
  redis-data:
```

This example is for local development. The published ports bind to loopback, and the database password must be supplied through configuration. In production, use managed secret handling and an appropriately secured network.

The Redis append-only file setting enables Redis persistence behavior, but the durability guarantee depends on Redis configuration and the underlying storage.

Create a local `.env` file:

```dotenv
POSTGRES_PASSWORD=replace-with-a-local-development-password
```

Add `.env` to `.gitignore`:

```gitignore
.env
```

Do not commit real credentials. Compose interpolation can be used to keep values out of the YAML file, but an `.env` file is not itself a secure secret manager.

## 8. Start and Manage Services

Run these commands from the directory containing `compose.yaml`:

```bash
# Validate the resolved Compose configuration
docker compose config

# Start services in the background
docker compose up -d

# List service status
docker compose ps

# Follow logs
docker compose logs -f

# View logs for one service
docker compose logs -f postgres

# Stop and remove containers and network
docker compose down
```

The named volumes remain after a normal `docker compose down`.

Be careful with:

```bash
docker compose down -v
```

The `-v` flag removes Compose-managed named volumes declared for the project and attached anonymous volumes. That can permanently remove local database data.

## 9. Add the Spring Boot API

Assume your application image is built from the `api/` directory and listens on port `8080`.

Add this service to the same Compose file:

```yaml
  api:
    build:
      context: ./api
    ports:
      - "127.0.0.1:8080:8080"
    environment:
      SPRING_DATASOURCE_URL: jdbc:postgresql://postgres:5432/orders
      SPRING_DATASOURCE_USERNAME: app
      SPRING_DATASOURCE_PASSWORD: ${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD}
      SPRING_DATA_REDIS_HOST: redis
      SPRING_DATA_REDIS_PORT: 6379
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
```

The exact Spring configuration property names depend on your application and Spring Boot version. Confirm that the app uses the properties shown.

`depends_on` with `service_healthy` can delay startup until the configured health checks pass. It does not guarantee that every later dependency operation will succeed. Applications should still handle connection failures and reconnect where appropriate.

Start the stack:

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f api
```

Test an endpoint your application actually exposes:

```bash
curl -i http://localhost:8080/actuator/health
```

This endpoint requires Spring Boot Actuator and suitable configuration. If your app does not have Actuator, use one of its actual API routes.

### Key networking insight

From the API container:

- PostgreSQL is reached through `postgres:5432`.
- Redis is reached through `redis:6379`.

These names resolve through the Compose network. You do not need to publish PostgreSQL or Redis ports merely for the API container to reach them.

## 10. Development Workflow with Bind Mounts

A development container may mount source code from the host to support rapid iteration.

For example:

```yaml
services:
  api:
    build:
      context: ./api
    volumes:
      - ./api:/workspace
    working_dir: /workspace
```

This configuration only mounts the source. It does **not** automatically compile the project, reload the JVM, or run the application from the mounted source. You must configure the container command and development tooling to achieve those behaviors.

For production images, copying a built artifact into the image is often more predictable than mounting an entire source tree.

## 11. Practical Debugging Commands

```bash
# Container and service status
docker compose ps
docker ps -a

# Logs
docker compose logs --tail 100 api
docker compose logs --tail 100 postgres

# Resolved configuration
docker compose config

# Network details
docker network ls
docker network inspect <network-name>

# Volume details
docker volume ls
docker volume inspect <volume-name>

# Resource usage
docker stats
docker system df
```

For a service that cannot connect to PostgreSQL, investigate:

1. Is PostgreSQL running?
2. Is its health check passing?
3. Is the API attached to the same Compose network?
4. Is the API using the service name `postgres`, not `localhost`?
5. Are credentials and database names correct?
6. Is PostgreSQL actually ready to accept connections?
7. What does the API log say about the failure?

---

# Layer 3 — Production Engineering & Interview Mastery

## 12. Diagnose Common Networking Failures

### Scenario A: `Connection refused`

This usually means the destination was reached but no process accepted the connection at that address and port, or a network rule actively rejected it.

Check whether the service is running, listening on the expected port, and reachable from the caller's network environment.

### Scenario B: `Could not resolve host`

The hostname could not be resolved in the caller's environment.

Check the hostname, Docker network membership, and whether the intended service name is available on that network.

### Scenario C: The API connects locally but fails in Compose

A frequent cause is a configuration value such as:

```text
SPRING_DATASOURCE_URL=jdbc:postgresql://localhost:5432/orders
```

Inside the API container, `localhost` points back to the API container. Use the Compose service name for a database container on the same network:

```text
SPRING_DATASOURCE_URL=jdbc:postgresql://postgres:5432/orders
```

### Scenario D: The database loses data after a restart

Determine whether the container was merely restarted or removed and recreated, and verify that the intended persistent volume is mounted at the database's actual data directory.

A restart and a recreation are not the same lifecycle operation.

## 13. Production Trade-offs and Security

### Network exposure

- Avoid publishing database and cache ports when only internal services require access.
- Bind development ports to loopback when appropriate.
- Use authentication and network controls for services that support them.
- Do not assume that an internal Docker network alone satisfies every production security requirement.

### Persistent storage

- Named volumes are useful for local stateful services.
- Backups must be tested independently of the volume.
- Understand the data-loss implications of volume deletion.
- For production, choose storage based on durability, availability, recovery objectives, and operational ownership.

### Configuration

- Keep environment-specific configuration outside immutable application images.
- Avoid committing credentials.
- Use a proper secret-management approach in production.
- Validate configuration at startup and make missing required settings obvious.

### Startup and resilience

- A dependency being started does not guarantee it is ready.
- Health checks help detect some readiness failures.
- Applications should tolerate transient dependency failures where appropriate.
- Avoid infinite restart loops that conceal a persistent configuration error.

### Compose versus orchestration

Compose is excellent for local environments and integration testing. For larger production environments, teams may need orchestration, rolling deployment controls, service discovery, resource policies, and automated recovery. Kubernetes can address many of these needs, but its operational complexity should be justified by the requirements.

## 14. Fifteen Interview Questions

**Q1. What is a Docker bridge network?**  
A virtual network that connects containers. User-defined bridge networks support service-name-based communication between connected containers.

**Q2. Why should a containerized API not normally use `localhost` for another container?**  
Because `localhost` refers to the API container itself, not the other service.

**Q3. What does `-p 8080:80` mean?**  
It maps host port `8080` to container port `80`.

**Q4. Do two containers need published ports to communicate?**  
No. Containers on a suitable shared Docker network can communicate through their internal ports.

**Q5. What is the difference between a volume and a bind mount?**  
A volume is managed by Docker; a bind mount maps a specific host path into a container.

**Q6. Why use named volumes for databases?**  
They allow data to persist independently of an individual container's writable layer and make storage references easier to manage.

**Q7. Does a named volume guarantee backups?**  
No. It provides persistence, not a backup and recovery strategy.

**Q8. What does Docker Compose solve?**  
It defines and manages a multi-service application, including services, networks, volumes, and configuration.

**Q9. What is the role of `depends_on`?**  
It expresses service dependencies and can control startup ordering. With supported health-check conditions, it can wait for a dependency to become healthy, but it does not eliminate runtime failures.

**Q10. What does a health check establish?**  
It runs a configured test and reports health status according to its result. A poorly designed health check may still miss important application failures.

**Q11. Why can a database work from the host but not from an API container?**  
The hostname, port mapping, network membership, credentials, or service readiness may differ between those environments.

**Q12. What does `docker compose down -v` do?**  
It removes the Compose project's containers and network and removes declared named volumes and attached anonymous volumes. Persistent data may be lost.

**Q13. When should you publish a container port?**  
When a client outside the container's internal network needs to reach that service through the host's published port.

**Q14. Why is an `.env` file not sufficient production secret management?**  
It is a configuration convenience, not a complete access-control, auditing, rotation, or secret-distribution system.

**Q15. How would you debug an API-to-database connectivity incident?**  
Inspect service health and logs, verify hostname and port, check network membership, validate credentials and configuration, and test connectivity from the caller's environment.

---

## 15. Hands-On Capstone

Build a local backend environment with:

- Spring Boot API
- PostgreSQL
- Redis
- Docker Compose
- Persistent named volumes
- Health checks for dependencies

Complete the following:

- [ ] Create `compose.yaml`.
- [ ] Configure a local `.env` file and ignore it in Git.
- [ ] Start PostgreSQL and Redis.
- [ ] Verify both health checks.
- [ ] Add the Spring Boot API service.
- [ ] Configure internal service-name-based connections.
- [ ] Verify the API can reach its dependencies.
- [ ] Stop and recreate the database container and verify data persistence.
- [ ] Break the database hostname intentionally and diagnose the failure.
- [ ] Remove the lab resources carefully without deleting data unintentionally.

---

## 16. Mastery Checklist

- [ ] Explain container ports versus published host ports.
- [ ] Explain bridge networks and container DNS.
- [ ] Distinguish named volumes from bind mounts.
- [ ] Explain why `localhost` behaves differently inside a container.
- [ ] Write a Compose file for a backend and its dependencies.
- [ ] Use health checks and understand their limitations.
- [ ] Debug DNS, refused connections, and dependency startup failures.
- [ ] Explain persistent storage and backup trade-offs.
- [ ] Secure ports, configuration, and credentials appropriately.

---

## Final Completion Protocol

After all three Docker chunks are saved and verified:

1. Verify all three source files under `content/docker/`.
2. Review the complete content against the three learning layers.
3. Generate one final PDF at `docs/docker/BEH_DOCKER_COMPLETE_HANDBOOK.pdf`.
4. Verify the PDF contains all three chunks, commands, diagrams, and readable formatting.
5. Update README status using verified progress.
6. Commit with the exact message:

`Docker done`

**Do not generate a separate PDF for this chunk.**

Next: **Docker — Chunk 3 of 3: Production Images, Security, Optimization & Deployment Workflows**.
