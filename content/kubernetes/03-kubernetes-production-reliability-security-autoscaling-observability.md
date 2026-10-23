# Kubernetes — Chunk 3 of 3: Production Reliability, Security, Autoscaling, Observability & Incident Mastery

## Handbook: Backend Engineering Tools & Infrastructure

**Source file:** `content/kubernetes/03-kubernetes-production-reliability-security-autoscaling-observability.md`

**Learning objective:** Move from deploying applications on Kubernetes to operating them safely under production conditions. By the end, you should be able to reason about availability, resource pressure, autoscaling, secure workloads, deployment rollbacks, observability, and incident response.

---

# Layer 1 — Fundamentals & Mental Models

## 1. The production Kubernetes mental model

A Deployment running successfully is not the same as a production-ready service.

A production workload must handle:

- Process crashes and node failures.
- Traffic spikes and changing resource demand.
- Slow dependencies and overloaded databases.
- Bad releases and configuration mistakes.
- Unauthorized access and compromised credentials.
- Partial outages where some replicas work and others fail.
- Limited visibility into what is actually happening.

Think of Kubernetes production engineering as five connected systems:

| System | Primary question |
|---|---|
| Reliability | Can the application continue serving useful traffic? |
| Resource management | Does it have enough CPU and memory without wasting capacity? |
| Security | Who can access the workload, and what can it access? |
| Observability | Can we detect and diagnose failures? |
| Delivery | Can we release and reverse changes safely? |

Kubernetes provides mechanisms for these goals. It does not automatically guarantee that your application is reliable, secure, or observable.

## 2. Desired state, reconciliation, and recovery

Suppose a Deployment requests three replicas.

```yaml
spec:
  replicas: 3
```

Kubernetes continuously compares the desired state with the observed state.

If one Pod disappears, the Deployment's controllers work toward restoring the desired replica count.

However, there is an important distinction:

**A replacement Pod existing does not mean the service is healthy.**

The replacement may fail to start, fail its readiness probe, or be unable to reach PostgreSQL. The Pod count may eventually return to three while the application remains unusable.

Production readiness therefore requires more than replica counts. It requires meaningful health checks, correct traffic routing, suitable resources, safe deployment strategies, and observable behavior.

## 3. Requests, limits, and resource pressure

Kubernetes resource settings influence scheduling and runtime behavior.

```yaml
resources:
  requests:
    cpu: "250m"
    memory: "256Mi"
  limits:
    cpu: "1000m"
    memory: "512Mi"
```

### CPU

- **Request:** The CPU amount used when Kubernetes evaluates scheduling requirements.
- **Limit:** The CPU usage ceiling enforced by the container runtime and Linux controls.
- CPU limits can cause throttling when the container attempts to use more CPU than allowed.

A throttled application may respond slowly even when its code has not changed.

### Memory

- **Request:** Helps Kubernetes decide where the Pod can be scheduled.
- **Limit:** Establishes a memory ceiling.
- Exceeding the memory limit can cause the container to be terminated, commonly showing an `OOMKilled` reason.

Memory pressure and CPU pressure behave differently. CPU throttling often manifests as increased latency; memory exhaustion may terminate the process.

### How do you choose resource values?

Start with measurements, not guesses.

1. Measure normal CPU and memory consumption.
2. Exercise realistic request volume.
3. Observe peak usage and garbage collection behavior.
4. Set requests that reflect actual workload needs.
5. Set limits according to the workload's risk and operating requirements.
6. Reassess after load tests and production telemetry.

For Java services, include heap, native memory, thread stacks, and other process overhead when sizing a container. A JVM heap configured too close to the container memory limit can leave insufficient room for non-heap memory.

## 4. Probes: startup, readiness, and liveness

These probes answer different questions.

| Probe | Question | Failure consequence |
|---|---|---|
| Startup | Has the application finished starting? | Container may be restarted after the configured startup threshold |
| Readiness | Should this Pod receive service traffic? | Pod is removed from ready endpoints while unready |
| Liveness | Is the process sufficiently healthy to continue running? | Container may be restarted |

Example:

```yaml
startupProbe:
  httpGet:
    path: /actuator/health
    port: 8080
  periodSeconds: 5
  failureThreshold: 30

readinessProbe:
  httpGet:
    path: /actuator/health/readiness
    port: 8080
  periodSeconds: 5
  failureThreshold: 3

livenessProbe:
  httpGet:
    path: /actuator/health/liveness
    port: 8080
  periodSeconds: 10
  failureThreshold: 3
```

These endpoints must actually exist and have suitable semantics in the application. For Spring Boot, configure Actuator health probes appropriately for the deployed version and dependencies.

**Critical distinction:** Do not make liveness depend blindly on every external dependency. If PostgreSQL becomes temporarily unavailable and the liveness endpoint fails for that reason, Kubernetes may repeatedly restart otherwise functional application instances. That can amplify the outage.

Readiness is often the right mechanism to stop sending traffic to an instance that cannot serve requests. Whether a dependency failure should make an application unready depends on the API's behavior and its ability to serve degraded functionality.

## 5. Horizontal Pod Autoscaling

The Horizontal Pod Autoscaler (HPA) adjusts the number of Pod replicas based on observed metrics.

```text
Incoming traffic increases
          |
          v
Resource usage or custom metric increases
          |
          v
HPA evaluates its target
          |
          v
Desired replica count increases
          |
          v
Deployment creates more Pods
          |
          v
Scheduler places Pods on available nodes
```

Autoscaling is a control loop, not an instant reaction. Metrics must be available, the HPA must observe the threshold, Pods must start, and the cluster must have sufficient capacity.

A basic CPU-based HPA:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backend-api
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: backend-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

CPU utilization is measured relative to CPU requests. Missing or unsuitable requests can make CPU-utilization-based scaling behave unexpectedly.

HPA also requires a working metrics pipeline, commonly provided by Metrics Server for resource metrics. Metrics Server is not a replacement for a full monitoring system such as Prometheus.

### When CPU is not the right scaling signal

A backend can be overloaded without high CPU usage.

Examples:

- Requests wait on a database connection pool.
- The application spends time waiting on network calls.
- Kafka consumer lag grows while CPU remains moderate.
- The number of requests in flight increases.
- Queue depth grows faster than workers can process it.

Custom or external metrics may be more appropriate in these cases, provided they are exposed and integrated correctly.

**Autoscaling cannot solve every bottleneck.** Ten additional API Pods may worsen a database connection storm if every Pod opens too many connections.

## 6. PodDisruptionBudgets and availability

A PodDisruptionBudget (PDB) limits how many matching Pods can be voluntarily disrupted at once.

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: backend-api-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: backend-api
```

This example aims to keep at least two matching Pods available during supported voluntary disruptions, assuming enough healthy replicas exist.

PDBs can help with operations such as node maintenance and certain drain workflows. They do not guarantee availability during every failure.

A PDB does not prevent:

- A node crashing unexpectedly.
- An application bug affecting every replica.
- A bad configuration breaking all Pods.
- A database outage.
- A failed readiness configuration.

For availability, combine multiple replicas, correct readiness checks, appropriate placement, safe deployments, and resilient dependencies.

## 7. Rolling updates and rollbacks

A Deployment can replace old Pods gradually.

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 0
    maxSurge: 1
```

- `maxUnavailable: 0` aims to avoid reducing the number of available replicas during the rollout.
- `maxSurge: 1` permits one additional Pod above the desired replica count during the rollout.

This configuration requires enough cluster capacity and compatible application behavior. It cannot guarantee zero downtime if the application, database migration, or dependencies are not compatible with the transition.

Inspect rollout status:

```bash
kubectl rollout status deployment/backend-api
kubectl rollout history deployment/backend-api
kubectl describe deployment backend-api
```

Undo a rollout:

```bash
kubectl rollout undo deployment/backend-api
```

A rollback changes the Deployment's Pod template to an earlier revision. It does **not** automatically reverse database migrations, external side effects, or changes to persistent data.

### Expand-and-contract database migrations

For backward-compatible releases:

1. Add a new schema element without immediately removing the old one.
2. Deploy code that can work with both schemas.
3. Migrate or backfill data.
4. Verify that old code paths are no longer needed.
5. Remove obsolete schema elements in a later release.

This approach makes it safer to roll application code forward and backward during a deployment window.

---

# Layer 2 — Practical Engineering & Workflows

## 8. Production-minded Deployment template

The following is an illustrative Deployment template for a Spring Boot API. Replace the image reference, endpoints, and resource values with settings verified for your application.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend-api
spec:
  replicas: 3
  revisionHistoryLimit: 5
  selector:
    matchLabels:
      app: backend-api
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0
      maxSurge: 1
  template:
    metadata:
      labels:
        app: backend-api
    spec:
      automountServiceAccountToken: false
      terminationGracePeriodSeconds: 30
      securityContext:
        runAsNonRoot: true
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: api
          image: your-registry/backend-api:1.0.0
          ports:
            - name: http
              containerPort: 8080
          resources:
            requests:
              cpu: "250m"
              memory: "256Mi"
            limits:
              cpu: "1000m"
              memory: "512Mi"
          startupProbe:
            httpGet:
              path: /actuator/health
              port: http
            periodSeconds: 5
            failureThreshold: 30
          readinessProbe:
            httpGet:
              path: /actuator/health/readiness
              port: http
            periodSeconds: 5
            failureThreshold: 3
          livenessProbe:
            httpGet:
              path: /actuator/health/liveness
              port: http
            periodSeconds: 10
            failureThreshold: 3
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop:
                - ALL
```

### Important caveats

- The image must be accessible from the cluster, and the image version should be immutable or otherwise reliably traceable.
- The application must support running as a non-root user.
- A read-only root filesystem may require writable temporary or application-specific volumes.
- Spring Boot must expose the configured health endpoints.
- Requests, limits, replicas, and probe thresholds require workload-specific validation.
- `automountServiceAccountToken: false` is appropriate when the workload does not need to call the Kubernetes API using its service account.
- This manifest alone does not create a Service, HPA, PDB, NetworkPolicy, Secret, or Ingress.

Apply and verify:

```bash
kubectl apply -f deployment.yaml
kubectl rollout status deployment/backend-api
kubectl get deployment backend-api
kubectl get pods -l app=backend-api -o wide
kubectl describe deployment backend-api
```

## 9. Security: identity, permissions, and isolation

Kubernetes security should follow least privilege.

### Service accounts

A ServiceAccount gives a workload an identity when it needs to interact with the Kubernetes API or other identity-integrated systems.

Do not grant broad permissions simply because an application runs inside the cluster.

If the application does not need Kubernetes API access, consider disabling automatic service-account token mounting. If access is required, create a narrowly scoped Role or ClusterRole and bind it only to the necessary identity.

### RBAC mental model

- **Role:** Permissions within a namespace.
- **ClusterRole:** A cluster-scoped permission definition, or a reusable permission definition that can be bound at namespace scope.
- **RoleBinding:** Grants permissions in a namespace.
- **ClusterRoleBinding:** Grants permissions across the cluster.

Example: allow a dedicated service account to read Pods in one namespace.

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: diagnostics-reader
  namespace: default
automountServiceAccountToken: true
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-reader
  namespace: default
rules:
  - apiGroups: [""]
    resources: ["pods"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: diagnostics-reader-binding
  namespace: default
subjects:
  - kind: ServiceAccount
    name: diagnostics-reader
    namespace: default
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: pod-reader
```

Validate permissions before deploying:

```bash
kubectl auth can-i get pods \
  --as=system:serviceaccount:default:diagnostics-reader \
  -n default
```

Run this check with an identity that is authorized to impersonate the service account. The check does not itself grant permissions.

### NetworkPolicy

NetworkPolicy can restrict Pod ingress and egress when the cluster's networking implementation supports enforcement.

A default-deny policy can improve isolation, but it can also break DNS, API access, database connections, or monitoring if necessary traffic is not explicitly allowed.

A safe rollout sequence is:

1. Inventory legitimate network flows.
2. Identify application, DNS, database, and monitoring dependencies.
3. Apply policies in a test namespace.
4. Verify expected traffic and denied traffic.
5. Roll out gradually while monitoring errors.

Do not apply an untested cluster-wide deny-all policy to production.

### Secrets

Kubernetes Secret data is Base64-encoded in manifests; Base64 is not encryption.

Production secret management should consider:

- Encryption at rest configured for the cluster.
- RBAC restrictions on reading and modifying Secrets.
- External secret managers where appropriate.
- Secret rotation and revocation.
- Avoiding secrets in Git, container images, logs, and shell history.

## 10. Graceful shutdown and termination

When a Pod is terminated, Kubernetes can remove it from service endpoints and send termination signals to the container. The precise sequence and timing depend on the workload and platform.

A well-behaved backend should:

1. Stop accepting new work when shutdown begins.
2. Become unready so new requests are no longer routed to it.
3. Allow in-flight requests to finish within a bounded period.
4. Close database and messaging connections cleanly.
5. Exit before the termination grace period expires.

For Java services, verify Spring Boot's graceful-shutdown configuration and ensure the application server's shutdown behavior matches the service's request duration.

For Kafka consumers, shutdown may also require completing or safely abandoning in-flight processing and committing offsets only when the processing semantics permit it.

A Kubernetes grace period cannot make an application graceful if the application ignores termination signals or blocks indefinitely.

## 11. Observability: metrics, logs, and traces

These three signals answer different questions.

| Signal | Best for |
|---|---|
| Metrics | Trends, alerting, saturation, error rates, latency distributions |
| Logs | Detailed events and contextual error information |
| Traces | Following a request across services and dependencies |

Useful Kubernetes-level signals include:

- Pod restart count.
- Container CPU throttling.
- Memory working set and OOM events.
- Desired versus available replicas.
- Pending Pods and scheduling failures.
- HPA current versus desired replicas.
- Node CPU, memory, and disk pressure.

Application-level signals include:

- Request rate.
- Error rate.
- Request latency percentiles.
- Database pool saturation.
- Dependency timeout rates.
- Queue depth or Kafka consumer lag.

A healthy Pod is not proof of a healthy API. Combine infrastructure and application telemetry.

### Practical investigation commands

```bash
kubectl get pods -A
kubectl get events -A --sort-by=.lastTimestamp
kubectl top nodes
kubectl top pods -n default
kubectl logs deployment/backend-api --since=15m
kubectl logs <pod-name> --previous
kubectl describe pod <pod-name>
```

`kubectl top` requires a functioning resource metrics pipeline. `--previous` is especially useful after a container has restarted because it retrieves logs from the previous container instance when available.

## 12. Autoscaling and availability configuration

Create an HPA:

```bash
kubectl autoscale deployment backend-api \
  --cpu-percent=70 \
  --min=2 \
  --max=10
```

Inspect it:

```bash
kubectl get hpa
kubectl describe hpa backend-api
kubectl top pods
```

The command creates an autoscaler targeting CPU utilization. It will not behave as intended if the metrics pipeline or resource requests are unsuitable.

Check the Deployment's available replicas:

```bash
kubectl get deployment backend-api \
  -o custom-columns=DESIRED:.spec.replicas,READY:.status.readyReplicas,AVAILABLE:.status.availableReplicas
```

Check disruption budgets:

```bash
kubectl get pdb
kubectl describe pdb backend-api-pdb
```

Check rollout health:

```bash
kubectl rollout status deployment/backend-api
kubectl rollout history deployment/backend-api
```

## 13. A disciplined release workflow

Use this sequence for a backend deployment.

### Before the release

- Verify the build and test suite.
- Use an identifiable, immutable image reference.
- Check resource requests and limits.
- Verify health probes.
- Confirm database migration compatibility.
- Review Secret and RBAC changes.
- Confirm enough cluster capacity for rollout surge.
- Check alerting and dashboards.

### During the release

- Observe rollout progress.
- Watch available replicas and Pod restarts.
- Check request error rate and latency.
- Verify dependency health.
- Stop or roll back if the release crosses agreed failure thresholds.

### After the release

- Verify API behavior using a smoke test.
- Check error and latency trends against baseline.
- Confirm consumers and background jobs are progressing.
- Record the deployed version and any deviations.
- Keep the incident timeline if anything went wrong.

A rollout reaching `successfully rolled out` is a control-plane status, not proof that business functionality is correct.

---

# Layer 3 — Production Engineering & Interview Mastery

## 14. Incident simulation: a release causes HTTP 5xx errors

**Scenario:** A new version deploys. The Pods are running, but the API's error rate increases.

### Step 1: Establish impact

Check the customer-facing symptoms, affected endpoints, and start time. Compare the start time with the release timeline.

### Step 2: Inspect the rollout

```bash
kubectl rollout status deployment/backend-api
kubectl rollout history deployment/backend-api
kubectl get replicasets
kubectl get pods -l app=backend-api
```

### Step 3: Inspect new Pods

```bash
kubectl describe pod <new-pod-name>
kubectl logs <new-pod-name> --since=10m
```

Look for startup failures, connection errors, missing configuration, and dependency timeouts.

### Step 4: Separate application failure from routing failure

Check whether Pods are ready and whether the Service has healthy endpoints.

```bash
kubectl get service
kubectl get endpointslice \
  -l kubernetes.io/service-name=backend-api
```

If no endpoints are ready, investigate readiness probes and Pod state. If endpoints exist, continue into application logs, dependencies, and request traces.

### Step 5: Mitigate

If the release is the likely cause and rollback is safe:

```bash
kubectl rollout undo deployment/backend-api
kubectl rollout status deployment/backend-api
```

Then verify the error rate and user-facing behavior.

### Step 6: Learn

Determine whether the failure came from code, configuration, migration incompatibility, resource settings, or an overlooked dependency. Add a test, release guard, or alert that would catch the failure earlier.

**Interview signal:** You establish impact, inspect evidence, mitigate, and verify recovery instead of randomly restarting Pods.

## 15. Incident simulation: Pods are repeatedly OOMKilled

**Scenario:** A Spring Boot service restarts under load.

Inspect:

```bash
kubectl describe pod <pod-name>
kubectl get pod <pod-name> -o yaml
kubectl top pod <pod-name>
kubectl logs <pod-name> --previous
```

Investigate:

- Container memory limit.
- JVM heap and non-heap memory.
- Memory growth over time.
- Traffic or workload changes.
- Large payloads and unbounded caches.
- Thread stacks, direct buffers, and native allocations.
- Whether the Pod is on a memory-pressured node.

Possible responses:

- Correct an unrealistically low memory limit when evidence supports it.
- Reduce excessive memory use in the application.
- Tune the JVM with container-aware memory sizing.
- Bound caches and queues.
- Add load testing and memory monitoring.

Simply increasing the memory limit may postpone the incident without fixing a leak.

## 16. Incident simulation: HPA does not scale

**Scenario:** Traffic rises, but the replica count remains unchanged.

Check:

```bash
kubectl get hpa
kubectl describe hpa backend-api
kubectl top pods
kubectl get deployment backend-api
kubectl get events --sort-by=.lastTimestamp
```

Look for:

- Missing metrics.
- Missing CPU requests.
- Current utilization below the configured target.
- An HPA at its maximum replica count.
- Unschedulable Pods due to insufficient node capacity.
- Startup time too long for the traffic spike.
- The real bottleneck being a database, queue, or external dependency.

Distinguish **scaling not triggered** from **scaling triggered but Pods cannot be scheduled**. They require different fixes.

## 17. Incident simulation: rolling deployment stalls

**Scenario:** New Pods never become available.

Inspect:

```bash
kubectl rollout status deployment/backend-api
kubectl describe deployment backend-api
kubectl get pods -l app=backend-api
kubectl describe pod <new-pod-name>
kubectl get events --sort-by=.lastTimestamp
```

Common causes:

- Image cannot be pulled.
- Startup or readiness probe is incorrect.
- Resource requests cannot fit on available nodes.
- Application configuration is missing.
- Dependency initialization blocks startup.
- The new version is incompatible with the existing database schema.
- Security settings prevent the process from starting.

Do not assume the correct fix is to increase rollout timeouts. Identify the actual blocker first.

## 18. Reliability engineering: error budgets and SLOs

An **SLO** is a target for a service-level indicator over a defined time window.

For example:

- Availability SLI: successful eligible requests divided by total eligible requests.
- Latency SLI: fraction of eligible requests completed below a latency threshold.
- SLO: 99.9% of eligible requests succeed over a rolling 30-day window.

An error budget is the permitted unreliability implied by the SLO.

For a 99.9% availability target, the theoretical error budget is 0.1% of eligible requests over the selected window. That is not automatically a fixed number of minutes: the conversion depends on how availability is measured and the window used.

SLOs help teams make release and reliability tradeoffs. They do not replace diagnosing incidents or selecting useful alerts.

### Alert on symptoms, investigate causes

A high-value alert often identifies user-visible impact, such as sustained elevated error rates or latency. CPU usage, restart count, and disk pressure are useful diagnostic signals, but not every elevated resource metric represents a customer-impacting incident.

Avoid alerting on every brief fluctuation. Define the symptom, threshold, duration, ownership, and required response.

## 19. Production readiness checklist

Use this before calling a workload production-ready.

### Availability and delivery

- [ ] Multiple replicas where required.
- [ ] Readiness, liveness, and startup probes have appropriate semantics.
- [ ] Rolling updates have suitable surge and unavailability settings.
- [ ] Rollback has been tested.
- [ ] Database migrations support the intended release sequence.
- [ ] Pod placement and cluster capacity match availability goals.
- [ ] PDB settings reflect actual disruption requirements.

### Resources and scaling

- [ ] CPU and memory requests are evidence-based.
- [ ] Limits are appropriate for the workload.
- [ ] JVM and container memory are sized together.
- [ ] HPA metrics are available and validated.
- [ ] Scaling behavior has been load-tested.
- [ ] Database and other dependency capacity are considered.

### Security

- [ ] Containers run as non-root when feasible.
- [ ] Privilege escalation is disabled unless explicitly needed.
- [ ] Linux capabilities are minimized.
- [ ] Service account permissions follow least privilege.
- [ ] Unneeded service-account token mounting is disabled.
- [ ] Secrets are not committed to source control.
- [ ] Network policies are tested and enforced by the cluster's network implementation.
- [ ] Image provenance, patching, and vulnerability scanning have appropriate controls.

### Observability and incident response

- [ ] Request rate, error rate, and latency are visible.
- [ ] Restarts, OOM events, CPU throttling, and pending Pods are observable.
- [ ] Logs provide enough context to diagnose failures.
- [ ] Distributed tracing is available where useful.
- [ ] Alerts have clear ownership and actionable runbooks.
- [ ] Rollback and recovery procedures are documented.
- [ ] A failure simulation has been completed.

---

## 20. SDE-1 interview questions and answers

### Fundamentals

**1. Does Kubernetes automatically make an application highly available?**

No. Kubernetes provides mechanisms such as replicas, rescheduling, probes, and rolling updates. Availability still depends on application design, placement, dependencies, capacity, and configuration.

**2. What is the difference between a readiness probe and a liveness probe?**

Readiness determines whether a Pod should receive traffic. Liveness determines whether Kubernetes should restart a container because it is considered unhealthy.

**3. Why are startup probes useful?**

They allow slow-starting applications time to initialize before liveness checks begin enforcing failure thresholds.

**4. What is the difference between a CPU request and a CPU limit?**

A request informs scheduling and contributes to utilization calculations. A limit caps CPU consumption and may cause throttling.

**5. What happens when a container exceeds its memory limit?**

It may be terminated by the kernel, often resulting in an `OOMKilled` status. Inspect Pod details and previous logs to confirm the failure.

### Autoscaling and availability

**6. How does an HPA work?**

It periodically compares observed metrics with configured targets and adjusts the desired replica count within configured bounds.

**7. Why might an HPA fail to scale a Deployment?**

Metrics may be unavailable, requests may be missing, utilization may be below the target, the maximum replica count may have been reached, or new Pods may be unschedulable.

**8. Does a PodDisruptionBudget prevent a node failure?**

No. It constrains supported voluntary disruptions, not arbitrary involuntary failures.

**9. How do you reduce downtime during rolling updates?**

Use suitable readiness probes, enough replicas and capacity, compatible application and database changes, and an appropriate rollout strategy. Validate real behavior during the release.

**10. Why is rollback not always sufficient?**

The previous application version may be incompatible with a database migration, persistent data change, or irreversible external side effect.

### Security and networking

**11. What is RBAC?**

Role-Based Access Control governs which identities can perform which operations on Kubernetes resources.

**12. Why should applications avoid broad cluster-admin access?**

Excessive privileges increase the impact of a compromised workload or application vulnerability.

**13. Is Base64-encoded Kubernetes Secret data encrypted?**

No. Base64 is encoding, not encryption. Access control and suitable encryption-at-rest configuration are important.

**14. What is the purpose of a NetworkPolicy?**

It specifies allowed Pod network traffic. Enforcement depends on the cluster networking implementation.

**15. Why might a container run as non-root?**

It reduces the privileges available to a compromised process and supports defense in depth.

### Operations and debugging

**16. A Pod is Running but not Ready. What do you inspect?**

Inspect the readiness probe, Pod events, container logs, application health endpoint, configuration, and dependencies required for serving requests.

**17. What does CrashLoopBackOff mean?**

The container repeatedly exits and Kubernetes backs off before attempting another restart. It is a symptom; inspect exit status, events, and logs to find the cause.

**18. How do you inspect logs from a crashed container?**

Use `kubectl logs <pod-name> --previous` when the previous container's logs are available.

**19. How do metrics, logs, and traces complement one another?**

Metrics identify patterns and symptoms, logs provide detailed event context, and traces show the path and timing of requests across components.

**20. What is your first response to a production deployment failure?**

Establish user impact, correlate it with the release, inspect rollout status and evidence, mitigate safely, verify recovery, and then conduct a root-cause analysis.

---

## 21. Capstone: operate a Spring Boot API under failure

### Objective

Deploy and operate a backend API locally on a Kubernetes development cluster, such as Kind or Minikube. No paid cloud account is required.

### Stage A — Prepare

1. Build and test the Spring Boot application.
2. Build a container image and make it accessible to the local cluster.
3. Deploy at least two replicas.
4. Create a ClusterIP Service.
5. Configure startup, readiness, and liveness probes.
6. Set CPU and memory requests.

### Stage B — Introduce operational controls

1. Configure a rolling update strategy.
2. Create a PDB appropriate to the replica count.
3. Configure an HPA if the cluster has the required metrics support.
4. Run a least-privilege RBAC check.
5. Test shutdown and restart behavior.
6. Add metrics and structured application logs.

### Stage C — Run failure drills

Perform these drills only in your local development environment.

- Deploy an image tag that does not exist, then diagnose `ImagePullBackOff`.
- Configure a deliberately incorrect readiness path and observe the effect on endpoints.
- Set a low memory limit in a test environment and observe the resulting termination behavior under a controlled workload.
- Deploy a deliberately broken application version and practice a rollback.
- Remove a required environment variable and diagnose startup failure.
- Generate test traffic and observe whether HPA metrics and scaling behave as expected.

Do not use destructive drills on a production cluster.

### Stage D — Write a short incident report

For each drill, record:

- Impact and symptoms.
- Detection method.
- Commands and evidence collected.
- Root cause.
- Mitigation and verification.
- Preventive change.
- What you would explain in an interview.

### Stage E — Mastery test

You have completed this chapter when you can explain and demonstrate:

- Why a Running Pod can still be unhealthy.
- How readiness differs from liveness.
- Why CPU throttling and memory exhaustion have different symptoms.
- What an HPA needs in order to scale.
- What a PDB does and does not guarantee.
- How to roll back a bad release safely.
- Why Kubernetes Secrets need additional security controls.
- How to narrow down a failed rollout using evidence.
- How metrics, logs, and traces work together.
- How to explain the incident clearly to an interviewer.

---

# Kubernetes completion protocol

This is the final planned Kubernetes content chunk.

1. Save this chapter as `content/kubernetes/03-kubernetes-production-reliability-security-autoscaling-observability.md`.
2. Verify that all three planned Kubernetes Markdown chapters exist and contain their complete content.
3. Build **one complete Kubernetes handbook PDF** from all three chapters in curriculum order.
4. Save the PDF as `docs/kubernetes/BEH_KUBERNETES_COMPLETE_HANDBOOK.pdf`.
5. Verify the PDF's chapter order, headings, code blocks, tables, and page rendering.
6. Update the README only with progress that has actually been verified.
7. Commit the completed Kubernetes source chapters and verified PDF with the exact commit message:

`Kubernetes done`

**Do not generate a PDF for this chunk alone.** The three source chapters and the single final Kubernetes PDF form the complete handbook deliverable.

After this is saved and verified, the next planned tool in the curriculum is Terraform, with three chunks. The overall project remains incomplete until all 13 individual handbooks and the final master handbook are complete.
