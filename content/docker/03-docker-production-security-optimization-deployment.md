# Docker — Chunk 3: Production Images, Security, Optimization & Deployment Workflows
## Backend Engineering Tools & Infrastructure Handbook

**Phase:** II — Backend Infrastructure  
**Chunk:** 3 of 3  
**Source file:** `content/docker/03-docker-production-security-optimization-deployment.md`

---

## Learning Objectives

By the end of this chapter, you should be able to:

- Build production-oriented images using multi-stage Dockerfiles.
- Reduce image size and improve build reproducibility.
- Apply practical container security controls.
- Understand resource limits, health checks, graceful shutdown, and restart behavior.
- Integrate Docker into a CI/CD deployment workflow.
- Diagnose production container incidents and defend engineering trade-offs in SDE-1 interviews.

---

# Layer 1 — Fundamentals & Mental Models

## 1. Development Images vs Production Images

A development environment prioritizes convenience. A production image prioritizes reliable operation, security, reproducibility, and efficient deployment.

A development image might contain:

- Source code and build tools.
- Maven and a JDK.
- Debugging utilities.
- Hot-reload tooling.
- Local configuration.

A production runtime image usually needs:

- The application artifact.
- The compatible runtime.
- Required runtime libraries and certificates.
- An explicit startup command.
- Appropriate permissions and configuration.

**Mental model:** Build the application in an environment designed for building it; run it in an environment designed for running it.

This separation reduces unnecessary software in the final image and limits the number of tools available to an attacker if the container is compromised.

## 2. Multi-Stage Builds

A multi-stage Dockerfile uses multiple `FROM` instructions. Artifacts produced in one stage can be copied into a later stage.

For a Spring Boot application:

```text
  +-------------------------------------------------------------------------+
  |                        Stage 1: Build Environment                       |
  |       JDK 21 + Maven Wrapper + POM + Complete Application Source        |
  |                `./mvnw clean package -DskipTests`                       |
  |                                   |                                     |
  |                                   v                                     |
  |                         Fat Executable JAR                              |
  +-----------------------------------+-------------------------------------+
                                      |
                                      | Copy only application JAR (--from=build)
                                      v
  +-------------------------------------------------------------------------+
  |                       Stage 2: Runtime Environment                      |
  |       Minimal JRE 21 Base Image + Hardened Non-Root System User         |
  |            Zero build tools · Minimal attack surface · Lean footprint   |
  |                                   |                                     |
  |                                   v                                     |
  |                  `java -jar /app/app.jar` (API on :8080)                |
  +-------------------------------------------------------------------------+
```

Benefits include:

- Build tools are not required in the final runtime image.
- The final image can be smaller.
- The build and runtime environments have clearer responsibilities.
- The final image contains fewer unnecessary components.

Multi-stage builds do not automatically make an image secure or reproducible. Base-image selection, dependency management, permissions, secrets, and build inputs still matter.

## 3. Image Size, Layers, and Build Cache

Docker builds images from instructions and filesystem layers. Cached layers can be reused when their relevant inputs have not changed.

Consider two approaches.

Less cache-friendly:

```dockerfile
COPY . .
RUN ./mvnw package
```

More deliberate:

```dockerfile
COPY .mvn/ .mvn/
COPY mvnw pom.xml ./
RUN chmod +x mvnw && ./mvnw -B dependency:go-offline

COPY src/ src/
RUN ./mvnw -B package
```

The second approach separates dependency inputs from frequently changing source files, so source edits may not invalidate the dependency-download layer.

This is a general pattern rather than a guarantee. Maven plugins, profiles, parent POMs, generated sources, and other build inputs may require additional files to be copied before the dependency layer.

### What makes images large?

- Unnecessary build tools and files.
- Large base images.
- Build caches copied into the runtime image.
- Logs, test output, or local development files included in the build context.
- Redundant layers and downloaded dependencies.

A smaller image can reduce transfer time and storage consumption. However, aggressively minimizing an image can make troubleshooting harder or remove required runtime components.

## 4. Container Security: Defense in Depth

A container should not be treated as a security boundary that automatically makes a workload safe.

A practical security model includes several controls:

| Control | Why it matters |
|---|---|
| Minimal maintained base image | Reduces unnecessary packages and exposure |
| Non-root execution | Limits privileges available to the application process |
| No embedded secrets | Prevents credentials from persisting in image layers |
| Image scanning | Helps identify known vulnerabilities |
| Read-only filesystem where feasible | Reduces unintended filesystem modifications |
| Resource limits | Restricts resource consumption |
| Least-privilege capabilities | Limits privileged kernel operations |
| Trusted image provenance | Improves confidence in the image's origin |

No single control is sufficient. A non-root process can still exploit application vulnerabilities, leak accessible secrets, or exhaust resources within its limits.

## 5. Container Lifecycle and Health

A container has a lifecycle, and its main process is central to that lifecycle.

Important concepts:

- **Running:** The container's main process is running.
- **Exited:** The main process has stopped.
- **Restart policy:** Determines whether Docker should restart the container under configured conditions.
- **Health check:** Reports whether a configured test considers the container healthy.
- **Graceful shutdown:** Allows the application to stop accepting new work and finish or safely abandon in-flight work.

A running container is not necessarily a healthy service.

A restart policy is also not a substitute for fixing a bad deployment. An application that crashes due to invalid configuration may simply enter a repeated restart cycle.

---

# Layer 2 — Practical Engineering & Workflows

## 6. Build a Production-Oriented Spring Boot Image

Assume the repository contains a standard Maven Spring Boot application.

Use this multi-stage Dockerfile as a starting point:

```dockerfile
# syntax=docker/dockerfile:1

FROM eclipse-temurin:21-jdk AS build
WORKDIR /workspace

COPY .mvn/ .mvn/
COPY mvnw pom.xml ./
RUN chmod +x mvnw \
    && ./mvnw -B dependency:go-offline

COPY src/ src/
RUN ./mvnw -B clean package -DskipTests

FROM eclipse-temurin:21-jre
WORKDIR /app

RUN groupadd --system app \
    && useradd --system --gid app app

COPY --from=build --chown=app:app \
    /workspace/target/*.jar /app/app.jar

USER app:app
EXPOSE 8080

ENTRYPOINT ["java", "-jar", "/app/app.jar"]
```

This example assumes:

- A Linux base image with the expected user-management utilities.
- A Java 21 application.
- A Maven Wrapper and conventional source layout.
- A single runnable JAR in `target/`.
- The application listens on port 8080.

If your project has multiple JARs, generated sources, a custom Maven layout, or additional build inputs, adapt the Dockerfile accordingly.

### Important build-quality decision

The example uses `-DskipTests` in the image build stage. This can be appropriate when a separate CI stage has already run the tests and the pipeline enforces that gate.

It is **not** appropriate to use this flag as a way to bypass verification without another test stage.

A CI pipeline should run tests before publishing the image.

### More reproducible builds

For stronger reproducibility:

- Pin base images to reviewed versions or digests.
- Use the Maven Wrapper with a known Maven version.
- Keep dependencies controlled and review updates.
- Avoid downloading unreviewed artifacts during deployment.
- Record the source revision and image digest.
- Make build configuration explicit.

A versioned tag is useful, but a mutable tag can point to a different image later. A digest identifies a specific image manifest.

## 7. Create a `.dockerignore`

Example:

```dockerignore
.git
.idea
.vscode
.DS_Store

target/
build/
out/

.env
.env.*
!.env.example

*.log
coverage/
```

This reduces the build context and prevents many unnecessary local files from being sent to the builder.

Review exceptions carefully. If the build requires a generated artifact from `target/`, excluding that directory is correct only when the Dockerfile builds the artifact internally or obtains it through another explicit mechanism.

Do not include real credentials in `.env.example`.

## 8. Add a Docker Health Check

A health check can detect some application failures:

```dockerfile
HEALTHCHECK --interval=30s \
            --timeout=5s \
            --start-period=40s \
            --retries=3 \
  CMD ["sh", "-c", "/* replace with a real health-check command */"]
```

The command above is a **placeholder**, not a working health check. Replace it with a command that exists in your image and actually tests the intended readiness or health condition.

For example, if the runtime image contains `curl` and the application exposes a suitable Actuator health endpoint:

```dockerfile
HEALTHCHECK --interval=30s \
            --timeout=5s \
            --start-period=40s \
            --retries=3 \
  CMD curl -fsS http://localhost:8080/actuator/health || exit 1
```

That version works only if `curl` is installed, Actuator is included, and the endpoint is accessible as configured. Minimal runtime images often omit `curl`; installing a utility solely for a health check increases the image footprint.

Docker health status does not automatically restart a container merely because it becomes unhealthy. Restart policies primarily respond to container termination, not to the health status alone. Compose, orchestrators, and monitoring systems may use health information in their own ways.

## 9. Configure Graceful Shutdown

A backend may receive a termination signal during a deployment or container stop.

The application should be prepared to:

1. Stop accepting new work.
2. Finish in-flight requests within a bounded time.
3. Close connections and release resources.
4. Exit before the termination deadline when possible.

For Spring Boot, graceful shutdown can be configured through application properties, subject to the version and server configuration:

```properties
server.shutdown=graceful
spring.lifecycle.timeout-per-shutdown-phase=20s
```

Set the Docker stop timeout to accommodate the shutdown behavior:

```bash
docker run -d \
  --name orders-api \
  --stop-timeout 30 \
  -p 8080:8080 \
  orders-api:1.0
```

The application, entrypoint, and runtime must handle termination signals correctly. A shell wrapper that fails to forward signals can interfere with graceful shutdown; exec-form `ENTRYPOINT` helps avoid this common problem.

## 10. Resource Limits

Containers can consume CPU, memory, disk, and other host resources.

For a local Docker run:

```bash
docker run -d \
  --name orders-api \
  --memory=512m \
  --cpus=1.0 \
  -p 8080:8080 \
  orders-api:1.0
```

This limits the container to a configured memory limit and CPU quota.

The appropriate values depend on the application, workload, JVM configuration, and deployment environment. A limit that is too low can cause latency spikes, memory failures, or out-of-memory termination.

Inspect usage:

```bash
docker stats
docker inspect orders-api
```

For Java applications, container-aware JVM behavior depends on the Java version and JVM flags. Measure actual usage and configure heap sizing with awareness of memory required outside the Java heap, including thread stacks, direct buffers, metaspace, and other native allocations.

## 11. Image Build and Verification Workflow

A disciplined local workflow:

```bash
# Run application tests
./mvnw clean verify

# Build the image
docker build -t orders-api:1.0 .

# Inspect image size and metadata
docker images orders-api
docker image inspect orders-api:1.0

# Start the container
docker run -d \
  --name orders-api \
  -p 8080:8080 \
  orders-api:1.0

# Inspect the runtime
docker ps
docker logs --tail 100 orders-api

# Stop and clean up the container
docker stop orders-api
docker rm orders-api
```

`verify` runs the Maven lifecycle through the verification phase, subject to the project's configured plugins and lifecycle behavior.

Do not publish the image merely because `docker build` succeeds. Build success establishes that the image could be constructed; it does not prove that the application starts, is secure, or functions correctly.

## 12. CI/CD Workflow

A practical deployment pipeline can follow this sequence:

1. Checkout a specific source revision.
2. Install or select the required JDK.
3. Run unit and integration tests.
4. Build the application artifact.
5. Build the Docker image.
6. Scan dependencies and the image.
7. Publish the image to a registry if checks pass.
8. Deploy the exact image version or digest.
9. Verify service readiness and key application behavior.
10. Monitor the rollout and roll back if required.

Example shell sequence for a pipeline that already has registry authentication configured:

```bash
set -euo pipefail

./mvnw -B clean verify

docker build \
  -t registry.example.com/orders-api:"$GIT_COMMIT" \
  .

docker push \
  registry.example.com/orders-api:"$GIT_COMMIT"
```

This is an illustrative sequence. A real CI environment must define `GIT_COMMIT`, configure the registry, protect credentials, and enforce the necessary checks.

Avoid deploying an image solely by a mutable tag such as `latest`. Record which immutable image digest is deployed so you can identify and reproduce the exact version.

---

# Layer 3 — Production Engineering & Interview Mastery

## 13. Production Incident Scenarios

### Incident A: The new image is much larger than expected

**Possible causes:**

- The build stage was accidentally used as the final stage.
- Local files or generated artifacts entered the build context.
- The runtime image contains unnecessary packages.
- Build caches or dependency directories were copied into the final image.

**Response:**

1. Compare the previous and current image sizes.
2. Inspect the Dockerfile stages.
3. Review `.dockerignore`.
4. Inspect image layers and their sizes.
5. Verify that the final stage copies only required runtime artifacts.

### Incident B: Container memory usage rises until the service crashes

**Possible causes:**

- Increased request concurrency or workload.
- A memory leak or unbounded cache.
- Oversized payloads or queues.
- JVM heap settings that leave too little room for native memory.
- An overly restrictive container limit.

**Response:**

1. Confirm whether the container was terminated and inspect its state.
2. Review application logs and memory metrics.
3. Compare heap and total container memory.
4. Inspect workload and traffic changes.
5. Adjust limits or application behavior based on evidence.
6. Load-test the revised configuration.

Do not assume every memory-related restart is a Java heap leak.

### Incident C: Deployment succeeds but the service is unavailable

**Possible causes:**

- Incorrect runtime environment variables.
- A container that is running but not ready.
- A port or network configuration mismatch.
- A database migration or dependency failure.
- A failed health check.
- A broken image entrypoint.

**Response:**

- Inspect container state and logs.
- Verify the deployed image digest.
- Check the actual listening port and published mapping.
- Test dependency connectivity.
- Verify readiness and application-level health.
- Roll back if the deployment violates the service's recovery criteria.

### Incident D: A container restarts repeatedly

**Possible causes:**

- Invalid configuration.
- Application startup exception.
- Missing credentials.
- Failed dependency initialization.
- Memory pressure or an explicit process exit.

**Response:**

```bash
docker ps -a
docker logs --tail 200 <container>
docker inspect <container>
docker events
```

Identify the initial failure before changing restart settings. Repeated restarts can increase load on dependencies and make diagnosis more difficult.

## 14. Production Readiness Checklist

Before shipping an image, verify:

- [ ] The base image is maintained and its version is controlled.
- [ ] The build uses explicit, reviewed dependencies.
- [ ] The final image excludes unnecessary build tooling.
- [ ] The application runs with minimal practical privileges.
- [ ] Secrets are not embedded in image layers.
- [ ] The image has been scanned according to the project's security policy.
- [ ] Configuration is supplied explicitly at runtime.
- [ ] Health checks reflect the intended health condition.
- [ ] Graceful shutdown behavior is tested.
- [ ] Resource limits are appropriate for expected workload.
- [ ] Logs are available through the container platform.
- [ ] The image version or digest is recorded.
- [ ] CI tests pass before publication.
- [ ] Rollback and incident diagnosis procedures are understood.

## 15. Fifteen Interview Questions

**Q1. Why use a multi-stage Docker build?**  
To separate the build environment from the runtime image and copy only required artifacts into the final stage.

**Q2. What is the difference between a JDK and a JRE?**  
A JDK includes development tools such as a compiler. A runtime environment provides what is needed to execute Java applications. Modern Java distributions and packaging can differ, so select a compatible supported image.

**Q3. Why should containers run as non-root?**  
It reduces the privileges available to a compromised application process, limiting some potential damage.

**Q4. What is `.dockerignore`?**  
A file that excludes specified paths from the Docker build context.

**Q5. What is Docker layer caching?**  
Docker reuses unchanged build layers where possible, reducing repeated build work.

**Q6. Does a smaller image automatically mean a safer image?**  
No. Security also depends on vulnerabilities, configuration, permissions, provenance, and runtime exposure.

**Q7. What is the difference between a container's running state and its health status?**  
Running describes the main process state; health status reflects the result of a configured health check.

**Q8. Does Docker automatically restart an unhealthy container?**  
Not merely because it is unhealthy. Restart policies primarily act when the container terminates. Additional orchestration or monitoring behavior may be needed.

**Q9. Why use exec-form `ENTRYPOINT`?**  
It starts the application as the main process rather than placing it behind a shell wrapper that may interfere with signal handling.

**Q10. Why configure a stop timeout?**  
To give the application time to shut down gracefully before forced termination.

**Q11. Why can Java memory usage exceed the heap limit you expected?**  
The container's memory usage includes native allocations, thread stacks, direct buffers, metaspace, and other processes or overhead—not just the Java heap.

**Q12. Why deploy by image digest?**  
A digest identifies a specific image manifest and avoids ambiguity from mutable tags.

**Q13. What should a container health check test?**  
A condition that meaningfully reflects the intended health or readiness state, without being so broad or fragile that it creates misleading results.

**Q14. How should CI handle image publication?**  
Run required tests and security checks first, authenticate safely to the registry, publish a versioned image, and record the resulting artifact identity.

**Q15. How do you troubleshoot a failed production container deployment?**  
Inspect the deployed image, container state, logs, environment configuration, networking, resource limits, and health status. Compare against the last known-good release and roll back when required.

---

## 16. Hands-On Capstone: Ship a Spring Boot Container

Use a small Spring Boot API and complete the following:

- [ ] Create a multi-stage Dockerfile.
- [ ] Add a `.dockerignore`.
- [ ] Build and test the application.
- [ ] Run the application as a non-root user.
- [ ] Configure environment-specific values outside the image.
- [ ] Add a meaningful health check if supported by the image.
- [ ] Test graceful shutdown.
- [ ] Apply a memory limit and observe resource usage.
- [ ] Inspect the image metadata and size.
- [ ] Run a simulated failure and diagnose it from logs and container state.
- [ ] Document the image tag or digest used for the test.
- [ ] Sketch a CI pipeline that tests, builds, scans, publishes, and deploys the image.

---

## 17. Docker Mastery Checklist

- [ ] Explain multi-stage builds and layer caching.
- [ ] Build a production-oriented Spring Boot image.
- [ ] Exclude unnecessary build-context files.
- [ ] Explain image security and non-root execution.
- [ ] Understand health checks and restart-policy limitations.
- [ ] Configure resource limits and graceful shutdown.
- [ ] Design a basic CI/CD workflow for container images.
- [ ] Debug startup, memory, and deployment incidents.
- [ ] Explain image tags versus digests.
- [ ] Defend Docker deployment choices in a backend interview.

---

## Final Completion Protocol

Docker's three-chunk curriculum is now authored in this conversation. Once all three source files are saved and verified in the repository:

1. Confirm all three files exist under `content/docker/`.
2. Verify that all three learning layers are covered across the complete handbook.
3. Generate **one final Docker PDF only** at `docs/docker/BEH_DOCKER_COMPLETE_HANDBOOK.pdf`.
4. Verify the PDF's code, diagrams, headings, and page layout.
5. Update README progress using verified status.
6. Commit the completed source and PDF with the exact message:

`Docker done`

Do not generate separate chunk PDFs.

**Next tool:** Redis — Chunk 1 of 3: Caching Fundamentals, Data Structures & Core Mental Models.
