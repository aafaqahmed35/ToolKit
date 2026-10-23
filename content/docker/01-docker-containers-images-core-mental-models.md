# Docker — Chunk 1: Containers, Images & Core Mental Models
## Backend Engineering Tools & Infrastructure Handbook

**Phase:** II — Backend Infrastructure  
**Chunk:** 1 of 3  
**Source file:** `content/docker/01-docker-containers-images-core-mental-models.md`

---

## Learning Objectives

By the end of this chapter, you should be able to:

- Explain why Docker exists and what problem it solves.
- Distinguish images, containers, registries, volumes, and networks.
- Explain containers versus virtual machines.
- Write a Dockerfile for a backend application.
- Build, run, inspect, and debug containers.
- Recognize common container failures and explain Docker trade-offs in SDE-1 interviews.

---

# Layer 1 — Fundamentals & Mental Models

## 1. Why Docker Exists

Imagine you've built a Spring Boot application on your MacBook. It runs perfectly.

You give the project to a teammate. Their Java version differs. Their environment variables are missing. Their operating system has different dependencies. The application fails.

You deploy it to a server. It fails again.

The problem is not necessarily your code. It may be the environment surrounding your code.

Docker helps package an application with its runtime and required dependencies into a standardized image, so the application can run more consistently across supported environments.

Docker does not guarantee that every environment behaves identically. Kernel differences, CPU architecture, networking, external services, configuration, and permissions still matter.

**Mental model:** Docker standardizes the application environment; it does not eliminate every environmental difference.

## 2. Containers vs Virtual Machines

```text
+--------------------------------------------------------------------------+
|                       Virtual Machine Architecture                       |
|   +----------------------------------+  +-----------------------------+  |
|   |          Application A           |  |        Application B        |  |
|   +----------------------------------+  +-----------------------------+  |
|   |            Guest OS A            |  |          Guest OS B         |  |
|   +----------------------------------+  +-----------------------------+  |
|   |                           Hypervisor                              |  |
|   +-------------------------------------------------------------------+  |
|   |                   Host OS / Physical Hardware                     |  |
+--------------------------------------------------------------------------+
(Each VM typically runs its own dedicated guest operating system)

+--------------------------------------------------------------------------+
|                          Container Architecture                          |
|   +----------------------------------+  +-----------------------------+  |
|   |          Application A           |  |        Application B        |  |
|   +----------------------------------+  +-----------------------------+  |
|   |           Container A            |  |         Container B         |  |
|   +----------------------------------+  +-----------------------------+  |
|   |             Container Runtime (Docker Engine / containerd)        |  |
|   +-------------------------------------------------------------------+  |
|   |                     Shared Host Linux Kernel                      |  |
|   +-------------------------------------------------------------------+  |
|   |                   Host OS / Physical Hardware                     |  |
+--------------------------------------------------------------------------+
(Containers isolate user-space processes while sharing the host kernel)
```

> **Note for macOS developers:** macOS does not run a Linux kernel natively. Docker Desktop on macOS transparently provisions a lightweight Linux VM under the hood to execute Linux containers.


| Dimension | Virtual machine | Container |
|---|---|---|
| Operating system | Typically includes a guest OS | Shares the host kernel |
| Startup | Often slower | Often faster |
| Resource overhead | Usually higher | Usually lower |
| Isolation | Virtualized hardware and OS boundary | Process and namespace isolation with resource controls |
| Typical use | Full OS isolation, legacy systems | Applications, services, CI jobs |

Containers are not merely lightweight VMs. Their isolation model differs, and a container should not automatically be treated as a strong security boundary against a hostile workload.

## 3. The Five Core Docker Concepts

### 1. Image
A packaged, immutable, versioned template containing the layered filesystem, application binaries, dependencies, environment defaults, and runtime metadata needed to execute containers. An image is read-only by design; a running container instantiates its own thin writable layer on top.

### 2. Container
An isolated, runnable user-space instance of an image with its own independent filesystem namespace, network interface, environment variables, resource limits (cgroups), and process lifecycle.

### 3. Registry
A centralized, secure service that indexes, stores, and distributes container images. Docker Hub is the default public registry; enterprise environments commonly deploy private registries (e.g., AWS ECR, Google Artifact Registry, GitHub Container Registry, Harbor).

### 4. Volume
A persistent storage mechanism managed directly by Docker outside the container's temporary union filesystem. Volumes decouple stateful data (such as PostgreSQL database directories) from the lifecycle of ephemeral container instances.

### 5. Network
A software-defined communication boundary (such as user-defined bridge networks) that allows containers to securely discover and communicate with one another via DNS names, or access external host and internet resources under explicit routing rules.


## 4. Image vs Container: The Most Important Distinction

Think of a class and an object in Java:

- A Docker image resembles a class definition in the sense that it describes what can be instantiated.
- A container resembles a running object created from that image.

The analogy is imperfect: a container is an operating-system process environment, not a Java object.

You can create multiple containers from the same image, each with separate runtime state and configuration.

```bash
docker pull nginx:alpine

docker run -d --name web-one nginx:alpine
docker run -d --name web-two nginx:alpine

docker ps
```

Both containers use the same image but have different names and independent container identities.

The tag `alpine` identifies a particular image tag, but tags can be updated. For strict reproducibility, production systems may pin image digests.

## 5. How Docker Works

At a high level:

1. You write a `Dockerfile`.
2. Docker builds an image from instructions and files.
3. The image is stored locally or pushed to a registry.
4. Docker creates a container from the image.
5. The container's main process starts.
6. Docker reports the container's state and exposes configured networking and storage.

Docker Engine commonly includes a daemon that manages images, containers, networks, and volumes, alongside a command-line client.

Docker Desktop on macOS supplies the Linux environment needed for Linux containers, since macOS does not use the Linux kernel.

## 6. Dockerfile and Image Layers

A `Dockerfile` is a recipe for building an image.

```dockerfile
FROM eclipse-temurin:21-jre
WORKDIR /app
COPY target/app.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
```

This example:

- Starts from a Java 21 runtime image.
- Sets `/app` as the working directory.
- Copies the application JAR into the image.
- Documents that the application uses port 8080.
- Starts the Java process when a container runs.

`EXPOSE 8080` is metadata. It does not automatically publish the port to the host.

Docker image builds use layers and caching. When an earlier layer changes, later layers may need to be rebuilt. Good Dockerfiles arrange relatively stable inputs before frequently changing application code when practical.

---

# Layer 2 — Practical Engineering & Workflows

## 7. Install and Verify Docker

On your MacBook, install and start Docker Desktop, then run:

```bash
docker --version
docker info
docker run --rm hello-world
```

What these commands do:

- `docker --version`: displays the client version.
- `docker info`: displays engine details; it requires the daemon to be available.
- `docker run --rm hello-world`: downloads the image if needed, runs it, and removes the stopped container afterward.

If `docker info` reports that it cannot connect to the daemon, first check that Docker Desktop has started.

## 8. Essential Docker Commands

| Command | Purpose |
|---|---|
| `docker pull nginx:alpine` | Download an image |
| `docker images` | List local images |
| `docker build -t orders-api:1.0 .` | Build an image |
| `docker run nginx:alpine` | Start a container in the foreground |
| `docker run -d --name web nginx:alpine` | Start in detached mode |
| `docker ps` | List running containers |
| `docker ps -a` | List all containers |
| `docker logs web` | View container logs |
| `docker inspect web` | Inspect configuration and state |
| `docker exec -it web sh` | Open a shell if the image contains one |
| `docker stop web` | Stop a container |
| `docker start web` | Start a stopped container |
| `docker rm web` | Remove a stopped container |
| `docker rmi nginx:alpine` | Remove a local image when unused |

## 9. Run a Web Server

```bash
docker run -d \
  --name demo-nginx \
  -p 8080:80 \
  nginx:alpine
```

Open `http://localhost:8080`.

Understand the port mapping:

`-p 8080:80` means host port 8080 forwards to container port 80.

```text
  +-------------------------------------------------------+
  |                       Your Mac                        |
  |             Browser / curl -> localhost:8080          |
  +---------------------------+---------------------------+
                              |
                              | Published port mapping (-p 8080:80)
                              v
  +-------------------------------------------------------+
  |                     Docker Engine                     |
  |                Host 8080 -> Container 80              |
  +---------------------------+---------------------------+
                              |
                              | Virtual Bridge Network
                              v
  +-------------------------------------------------------+
  |                    Nginx Container                    |
  |             Process listens on port 80                |
  +-------------------------------------------------------+
```

Check the response:

```bash
curl -I http://localhost:8080
docker logs demo-nginx
docker inspect demo-nginx
```

Clean up:

```bash
docker stop demo-nginx
docker rm demo-nginx
```

## 10. Containerize a Spring Boot Application

Suppose you have a Spring Boot project that produces `target/app.jar`.

Build the JAR:

```bash
./mvnw clean package
```

Use this Dockerfile in the project root:

```dockerfile
FROM eclipse-temurin:21-jre
WORKDIR /app
COPY target/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
```

Build the image:

```bash
docker build -t orders-api:1.0 .
```

Run the application:

```bash
docker run --rm \
  --name orders-api \
  -p 8080:8080 \
  orders-api:1.0
```

In a second terminal:

```bash
curl -i http://localhost:8080/actuator/health
```

That endpoint exists only if Spring Boot Actuator is included and configured appropriately. Otherwise, test an endpoint your application actually exposes.

### Important configuration rule

If the application connects to PostgreSQL running directly on your Mac, `localhost` inside the container refers to the container itself, not your Mac.

With Docker Desktop, a container can often reach a host service using `host.docker.internal`, provided the service is listening on an address reachable from Docker and its network/security configuration permits access.

When the database runs in another container on the same Docker network, use the database container's service name as the hostname.

## 11. Environment Variables

Do not bake environment-specific secrets into an image.

Pass configuration at runtime:

```bash
docker run --rm \
  -p 8080:8080 \
  -e SPRING_PROFILES_ACTIVE=dev \
  -e DB_HOST=host.docker.internal \
  orders-api:1.0
```

This assumes your application is configured to read those variables. Spring Boot maps supported environment variables to configuration properties, but a custom property such as `DB_HOST` must be referenced or mapped appropriately.

For local experimentation, an environment file can help:

```bash
docker run --env-file .env orders-api:1.0
```

Keep `.env` files containing credentials out of Git. Runtime environment variables are not a complete secret-management solution: processes and privileged operators may be able to inspect them. Production deployments should use an appropriate secret-management mechanism.

## 12. Volumes and Data Persistence

A container's writable layer is not a reliable place to keep important data.

Create a named volume:

```bash
docker volume create postgres-data
docker volume ls
docker volume inspect postgres-data
```

For a local PostgreSQL container:

```bash
docker run -d \
  --name dev-postgres \
  -e POSTGRES_USER=app \
  -e POSTGRES_PASSWORD=local-dev-only \
  -e POSTGRES_DB=orders \
  -v postgres-data:/var/lib/postgresql/data \
  -p 5432:5432 \
  postgres:16
```

This example is for local development only. Do not use the example password in production or expose a production database without appropriate controls.

Stop and remove the container:

```bash
docker stop dev-postgres
docker rm dev-postgres
```

The named volume remains. Recreating the container with the same volume can preserve the database data.

**Warning:** Deleting a container and deleting its volume are different operations. `docker volume rm` can destroy persistent data. Back up valuable data before removing storage.

## 13. Inspect and Debug Containers

When a container fails, use a structured workflow.

```bash
docker ps -a
docker logs --tail 100 orders-api
docker inspect orders-api
docker stats
```

Ask these questions in order:

1. Was the container created successfully?
2. Is it running, exited, or restarting?
3. What does its exit status and log output show?
4. Are required environment variables present?
5. Does the process listen on the expected port?
6. Is the port published correctly?
7. Can the container resolve and reach its dependencies?
8. Are storage mounts and permissions correct?

A container can be running while its application is unhealthy. A running state alone does not prove the service is ready to accept requests.

## 14. Docker Cleanup

Useful commands:

```bash
docker container prune
docker image prune
docker system df
```

Be careful with broad cleanup commands. Pruning removes unused resources, and the exact set depends on the command and its flags. Inspect what is using disk space before removing resources.

Avoid treating `docker system prune -a --volumes` as routine cleanup on a machine containing important local data.

---

# Layer 3 — Production Engineering & Interview Mastery

## 15. Common Failure Modes

### Failure A: Container exits immediately

**Possible causes:** The main process completed, the application crashed, or the startup command was incorrect.

**Investigate:**

```bash
docker ps -a
docker logs <container>
docker inspect <container>
```

Containers typically live as long as their primary process runs. A background daemon started incorrectly may exit when the foreground process ends.

### Failure B: Application starts but cannot reach PostgreSQL

**Possible causes:** Wrong hostname, incorrect credentials, a database that is not ready, incompatible network configuration, or firewall restrictions.

**Investigate:** Check application logs, database readiness, connection settings, and Docker network membership. Do not assume that `localhost` identifies another container.

### Failure C: Port is already allocated

Another process or container is using the host port.

```bash
docker ps
lsof -i :8080
```

Choose another available host port or stop the conflicting service if appropriate.

### Failure D: Image builds but the application crashes

An image build does not prove the application starts correctly.

Possible causes include a missing JAR, incorrect Java version, missing runtime configuration, invalid entrypoint, or an architecture mismatch.

Check the logs and inspect the image's build inputs and runtime configuration.

### Failure E: Database data disappears

The database stored data in the container's writable layer and the container was replaced, or a volume was not mounted at the intended data path.

Use persistent storage, verify the mount, and test recovery procedures.

## 16. Production Image Best Practices

- Use a supported, maintained base image.
- Prefer a runtime-only image when compilation is complete outside the final image.
- Pin versions deliberately and consider image digests for reproducible deployments.
- Exclude unnecessary files using `.dockerignore`.
- Avoid copying credentials into the image.
- Run as a non-root user when practical and supported by the image.
- Keep images small enough for efficient distribution, without sacrificing required runtime dependencies.
- Scan images and keep dependencies patched.
- Use explicit health checks or orchestrator probes where appropriate.
- Send logs to standard output/error so the container platform can collect them.
- Set CPU and memory constraints at the deployment level where appropriate.
- Test graceful shutdown and signal handling.

A container image is not automatically secure just because it is small.

## 17. Dockerfile vs Docker Compose vs Kubernetes

| Tool | Primary responsibility |
|---|---|
| Dockerfile | Defines how to build an image |
| Docker CLI / Engine | Builds and runs containers |
| Docker Compose | Defines and runs a multi-container application |
| Kubernetes | Orchestrates containerized workloads across a cluster |

For example, a backend project may contain:

- A Spring Boot API.
- PostgreSQL for persistence.
- Redis for caching.
- Kafka for asynchronous events.

Compose can run these components together for local development. Kubernetes addresses a different set of deployment and orchestration requirements; it is not a mandatory next step for every application.

## 18. Fifteen Interview Questions

**Q1. What problem does Docker solve?**  
It standardizes packaging and execution environments, improving portability and consistency across development, CI, and deployment.

**Q2. What is the difference between an image and a container?**  
An image is the packaged template; a container is an instance created from it with runtime state.

**Q3. Why are containers generally lighter than VMs?**  
Containers share the host kernel rather than each requiring a separate guest OS.

**Q4. Does `EXPOSE 8080` publish a port?**  
No. It documents container port metadata. Port publishing is configured at runtime, for example with `-p 8080:8080`.

**Q5. Why does a container exit when its main process exits?**  
The container's lifecycle is tied to its primary process. When that process finishes, the container stops.

**Q6. What is a Docker volume?**  
A persistent storage mechanism managed by Docker that can outlive individual containers.

**Q7. What is the difference between `docker stop` and `docker kill`?**  
`stop` requests graceful termination and then forcefully terminates after its timeout if necessary. `kill` sends a signal directly, using SIGKILL by default unless configured otherwise.

**Q8. Why does `localhost` fail when one container connects to another?**  
Inside a container, `localhost` refers to that same container's network namespace, not another service.

**Q9. What is a Docker registry?**  
A service for storing and distributing container images.

**Q10. Why use `.dockerignore`?**  
It prevents unnecessary files from entering the build context, which can improve build efficiency and reduce accidental inclusion of sensitive or irrelevant files.

**Q11. What is image-layer caching?**  
Docker can reuse unchanged build layers, making subsequent builds faster when earlier inputs remain the same.

**Q12. Why should secrets not be baked into an image?**  
Images can be copied, cached, pushed, and inspected. Credentials embedded in them may persist and be exposed beyond their intended scope.

**Q13. Does a running container guarantee a healthy application?**  
No. Its main process can remain alive while the service is unable to handle requests. Health checks and application-level monitoring help detect this.

**Q14. When would you choose Compose over Kubernetes?**  
Compose is often sufficient for local multi-container development and simpler environments. Kubernetes is intended for orchestration requirements that justify its additional complexity.

**Q15. How would you debug a container that works locally but fails in deployment?**  
Compare image versions, runtime configuration, architecture, network and port settings, resource constraints, filesystem permissions, and logs. Reproduce the deployed configuration where possible.

---

## 19. Hands-On Lab: Containerize and Diagnose

Complete these exercises on your local machine:

- [ ] Run `hello-world` successfully.
- [ ] Run Nginx and access it through a published port.
- [ ] Build a Docker image for a Spring Boot JAR.
- [ ] Pass runtime configuration through environment variables.
- [ ] Run PostgreSQL with a named volume.
- [ ] Remove and recreate the PostgreSQL container, then verify the volume's persistence.
- [ ] Intentionally use a wrong port and diagnose the failure.
- [ ] Intentionally configure an invalid database hostname and identify the connection failure.
- [ ] Inspect logs, container state, and configuration.
- [ ] Stop and remove the lab resources without accidentally deleting valuable data.

---

## 20. Mastery Checklist

- [ ] Explain the container versus VM distinction.
- [ ] Explain images, containers, registries, volumes, and networks.
- [ ] Build and run a Spring Boot image.
- [ ] Explain image layers and build caching.
- [ ] Distinguish container ports from published host ports.
- [ ] Diagnose process exits, port conflicts, and network failures.
- [ ] Explain why containers should not be the only persistence layer.
- [ ] Identify basic image-security and configuration risks.
- [ ] Explain Dockerfile, Compose, and Kubernetes responsibilities.

---

## Final Completion Protocol

After all three Docker chunks are saved and verified:

1. Verify all three authoritative Markdown files under `content/docker/`.
2. Review the complete tool content against all three learning layers.
3. Generate one final PDF: `docs/docker/BEH_DOCKER_COMPLETE_HANDBOOK.pdf`.
4. Verify the PDF includes all three chunks, code samples, diagrams, and readable formatting.
5. Update README status based on actual verification.
6. Commit with the exact message: `Docker done`.

Do not create chunk-level PDFs. Proceed next to **Docker — Chunk 2 of 3: Networking, Volumes & Docker Compose**.
