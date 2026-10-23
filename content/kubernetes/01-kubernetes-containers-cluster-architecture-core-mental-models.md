# Kubernetes — Chunk 1 of 3: Containers at Scale, Cluster Architecture & Core Mental Models

**Backend Engineering Tools & Infrastructure Handbook**

**Source file:** `content/kubernetes/01-kubernetes-containers-cluster-architecture-core-mental-models.md`

---

## Learning Objectives

By the end of this chapter, you should be able to:

- Explain why Kubernetes exists and what problems it solves.
- Understand cluster architecture and the responsibilities of control-plane and worker-node components.
- Distinguish Pods, containers, Deployments, ReplicaSets, Services, and Namespaces.
- Explain how Kubernetes schedules and runs a backend application.
- Understand declarative configuration and reconciliation.
- Deploy a Spring Boot API to a local Kubernetes cluster.
- Diagnose common Pod scheduling, startup, networking, and configuration failures.
- Answer Kubernetes fundamentals questions in backend engineering interviews.

This chapter establishes the mental models and first practical workflow. Chunks 2 and 3 will build on it with networking, storage, configuration, security, production reliability, scaling, troubleshooting, and interview mastery.

# Layer 1 — Fundamentals & Mental Models

## 1. Why Kubernetes Exists

Imagine you have three backend services:

- Orders API — Spring Boot
- Payments API — Spring Boot
- Notifications worker — Java

Each runs in a container. Initially, you run them manually with Docker.

That works—until production grows.

You now need to answer:

- What happens if a container crashes?
- How do you run five copies of an API?
- How do you replace an unhealthy instance?
- How do you deploy a new version without taking down the service?
- How do containers discover one another?
- How do you allocate CPU and memory?
- How do you manage configuration across development, staging, and production?

Docker provides containerization. Kubernetes orchestrates containerized workloads across a cluster of machines.

**Mental model:** Docker packages and runs containers; Kubernetes manages the desired state and lifecycle of workloads across a cluster.

Kubernetes does not eliminate operational complexity. It gives you mechanisms for managing complexity consistently, but those mechanisms still require correct configuration, monitoring, security, and capacity planning.

## 2. What Is a Kubernetes Cluster?

A Kubernetes cluster consists of a **control plane** and one or more **worker nodes**.

### Control-Plane Components

The control plane makes global cluster decisions and maintains desired state:

| Component | Responsibility |
|---|---|
| **API Server (`kube-apiserver`)** | Entry point and primary interface for all Kubernetes API operations. Validates and configures data for Pods, Services, and Deployments. |
| **etcd** | Consistent, distributed, and highly-available key-value store holding the entire cluster state. |
| **Scheduler (`kube-scheduler`)** | Selects suitable worker nodes for newly created, unscheduled Pods based on resource constraints, affinity, and availability. |
| **Controller Manager (`kube-controller-manager`)** | Runs controller loops that continuously reconcile actual cluster state toward declared desired state. |

### Worker-Node Components

Worker nodes host and run the application container workloads:

| Component | Responsibility |
|---|---|
| **kubelet** | The primary node agent that registers the node, communicates with the control plane, and instructs the container runtime to run assigned Pods. |
| **Container runtime** | Executes containers on the node, commonly through containerd via the Container Runtime Interface (CRI). |
| **kube-proxy (or equivalent)** | Implements Service traffic routing, maintaining network rules on nodes (via iptables, IPVS, or eBPF). |
| **Pods** | The smallest deployable units containing the application containers and shared volumes. |

The exact networking implementation varies by cluster. Some environments use `kube-proxy`; others use a network implementation that replaces some or all of its functionality.

### Control-plane components detailed

**API server (`kube-apiserver`)**

The primary interface for Kubernetes API operations. Tools such as `kubectl` communicate with the API server.

**etcd**

A consistent key-value store that holds Kubernetes cluster state. It is not your application's default database.

**Scheduler (`kube-scheduler`)**

Selects a suitable node for a Pod that has not yet been assigned to a node. It considers factors such as resource requests, scheduling constraints, and node availability.

**Controller manager**

Runs controllers that observe cluster state and take action to move the system toward its desired state.

### Worker-node components detailed

**kubelet**

The node agent that communicates with the control plane and works with the container runtime to run assigned Pods.

**Container runtime**

Executes containers. Kubernetes commonly uses containerd through the Container Runtime Interface (CRI).

**Networking components**

Implement Pod networking and Service traffic routing. Their exact design depends on the cluster's networking solution.

## 3. The Declarative Model

One of Kubernetes' most important ideas is declarative configuration.

Instead of manually starting three containers and repeatedly checking whether they are alive, you declare what you want:

> Run three replicas of my Orders API using this image.

Kubernetes controllers continuously compare the declared state with the observed state and take corrective action where possible.

```text
You declare desired state
          |
          v
    Kubernetes API
          |
          v
 Controllers observe state
          |
          v
 Create / replace / reconcile resources
          |
          v
 Actual state moves toward desired state
```

Suppose you request three replicas, but only two are running.

A Deployment's controller chain works to restore the desired replica count, subject to scheduling, resource availability, image availability, and other constraints.

**Important distinction:** Kubernetes is not magic self-healing. It can replace a failed Pod, but it cannot guarantee that the application inside the replacement will work correctly.

## 4. The Kubernetes Object Hierarchy

Several objects work together to run an application.

```text
+-------------------------------------------------------+
|                      Deployment                       |
|        (Declares desired replicas & rollout strategy)  |
+-------------------------------------------------------+
                            |
                            v
+-------------------------------------------------------+
|                       ReplicaSet                      |
|        (Maintains the desired number of matching Pods)|
+-------------------------------------------------------+
                            |
       +--------------------+--------------------+
       |                    |                    |
       v                    v                    v
+--------------+     +--------------+     +--------------+
|    Pod 1     |     |    Pod 2     |     |    Pod 3     |
| (Container)  |     | (Container)  |     | (Container)  |
+--------------+     +--------------+     +--------------+
```

### Pod

A Pod is Kubernetes' smallest deployable workload unit.

A Pod contains one or more containers that share the Pod's network namespace and can share mounted volumes.

Most ordinary backend workloads use one primary application container per Pod. Multiple containers are useful when they are tightly coupled, such as an application and a supporting sidecar.

A Pod is not simply a permanent container. Pods are replaceable, and a replacement Pod can have a different identity and IP address.

### ReplicaSet

A ReplicaSet maintains the requested number of matching Pod replicas.

You will usually create a Deployment rather than manage a ReplicaSet directly.

### Deployment

A Deployment manages stateless application rollout and rollback behavior through ReplicaSets.

It provides a declarative way to update application versions and maintain a requested replica count.

### Service

Pods can be replaced, so their individual IP addresses are not a reliable long-term destination for clients.

A Service provides a stable network identity for a set of matching Pods.

We will explore Service networking and external access in Chunk 2.

### Namespace

A Namespace groups namespaced Kubernetes resources inside a cluster.

Namespaces help organize environments and teams, but they are not a complete security boundary by themselves.

## 5. Container Versus Pod

| Concept | Responsibility |
|---|---|
| Container | Runs an application process in an isolated environment |
| Pod | Provides the Kubernetes execution unit around one or more containers |
| ReplicaSet | Maintains the requested number of matching Pods |
| Deployment | Manages declarative updates and ReplicaSets |
| Service | Provides stable access to matching Pods |
| Namespace | Organizes namespaced resources |

For example, if you deploy a Spring Boot API with three replicas, you usually have three Pods, each containing one application container.

You do not normally create one giant Pod with three copies of the same application inside it. The replicas should generally be separate Pods so Kubernetes can schedule and replace them independently.

## 6. Kubernetes Scheduling: What Happens After You Apply YAML?

Consider:

```bash
kubectl apply -f deployment.yaml
```

A simplified execution sequence is:

1. `kubectl` sends the desired object to the API server.
2. The API server validates and stores the accepted object.
3. The Deployment controller creates or updates a ReplicaSet.
4. The ReplicaSet controller creates the required Pods.
5. The scheduler selects nodes for unscheduled Pods.
6. The kubelet on each selected node observes its assigned Pods.
7. The container runtime pulls images when needed and starts containers.
8. The application initializes.
9. Readiness checks, if configured, determine whether the Pod is ready to serve traffic.

These steps are coordinated by asynchronous control loops. They do not happen as one synchronous transaction.

A successful `kubectl apply` means the configuration was accepted; it does not prove the application is healthy or reachable.

## 7. Desired State Versus Observed State

Suppose a Deployment specifies:

```yaml
spec:
  replicas: 3
```

This means the desired number of replicas is three.

You might observe:

```text
NAME                         READY   STATUS
orders-api-abc123-1           1/1     Running
orders-api-abc123-2           1/1     Running
orders-api-abc123-3           0/1     Running
```

Three Pods exist, but only two are ready.

That distinction matters:

- **Desired replicas:** how many replicas the configuration requests.
- **Existing replicas:** how many corresponding Pods exist.
- **Ready replicas:** how many satisfy readiness conditions.
- **Available replicas:** how many meet the Deployment's availability criteria.

A Pod can be running without being ready to serve traffic.

**Interview insight:** `Running` is a Pod phase, not a complete health assessment.

## 8. Kubernetes Is Not a Database or a Build Tool

Kubernetes is responsible for orchestration, not for replacing every other component in your stack.

| Tool | Main responsibility |
|---|---|
| Maven | Builds and packages the Java application |
| Docker | Builds container images and provides container tooling |
| Kubernetes | Orchestrates workloads and cluster resources |
| PostgreSQL | Stores relational application data |
| Redis | Provides in-memory data structures and caching capabilities |
| Kafka | Provides distributed event streaming |
| Prometheus | Collects and queries metrics |
| Grafana | Visualizes operational data |

Kubernetes can run PostgreSQL, Redis, and Kafka, but running a service in Kubernetes does not automatically make that service highly available, backed up, or correctly configured.

Stateful workloads need additional architectural decisions around storage, recovery, replication, and operational ownership.

---

# Layer 2 — Practical Engineering & Workflows

## 9. Set Up a Local Kubernetes Environment

For learning, use a local cluster rather than paying for a managed cloud cluster.

Common options include:

- **Kind:** runs Kubernetes nodes in Docker containers.
- **Minikube:** creates a local Kubernetes environment.
- **Docker Desktop Kubernetes:** available in supported Docker Desktop configurations.

Choose one environment and keep its setup consistent throughout the handbook.

### Example: Kind

Check prerequisites:

```bash
docker --version
kubectl version --client
kind version
```

Create a cluster:

```bash
kind create cluster --name backend-lab
kubectl cluster-info
kubectl get nodes
```

Inspect the current context:

```bash
kubectl config current-context
kubectl config get-contexts
```

A Kubernetes context identifies a cluster, a user or credentials, and optionally a default Namespace.

**Safety rule:** Before applying or deleting resources, confirm which context is active. The same command can affect a local cluster or a production cluster depending on the context.

## 10. Build a Minimal Spring Boot Image

Kubernetes runs container images; it does not compile your Java source code into a production application automatically.

From your Spring Boot project:

```bash
./mvnw clean package
```

Assuming the build produces a JAR under `target/`, a simple development Dockerfile is:

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

This is a minimal teaching example, not a hardened production Dockerfile. Production images should use controlled base-image versions, appropriate non-root execution, and a deliberate patching and scanning process.

### Make the image available to Kind

Kind nodes have their own image caches. A locally built image is not automatically available inside the cluster.

Load it:

```bash
kind load docker-image orders-api:1.0 --name backend-lab
```

This prevents Kubernetes from trying to fetch the local development image from a remote registry, provided the Pod image settings are configured appropriately.

## 11. Write a Kubernetes Deployment

Create `k8s/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orders-api
  labels:
    app: orders-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: orders-api
  template:
    metadata:
      labels:
        app: orders-api
    spec:
      containers:
        - name: orders-api
          image: orders-api:1.0
          imagePullPolicy: IfNotPresent
          ports:
            - name: http
              containerPort: 8080
          resources:
            requests:
              cpu: "100m"
              memory: "256Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
```

Understand the important fields:

- `apiVersion`: API group and version for the resource.
- `kind`: resource type.
- `metadata`: name and labels.
- `replicas`: desired Pod count.
- `selector`: determines which Pods the Deployment manages.
- `template`: defines how new Pods should be created.
- `image`: application container image.
- `containerPort`: documents the port the container is expected to use.
- `resources.requests`: resource quantities used for scheduling and related decisions.
- `resources.limits`: resource constraints applied by the node's container runtime and operating system mechanisms.

The Deployment selector must match the labels on its Pod template.

### Apply the Deployment

```bash
kubectl apply -f k8s/deployment.yaml
kubectl get deployments
kubectl get replicasets
kubectl get pods -o wide
```

Watch rollout progress:

```bash
kubectl rollout status deployment/orders-api
```

Inspect the Deployment:

```bash
kubectl describe deployment orders-api
```

If it does not become ready, inspect the Pods and their events rather than repeatedly reapplying the same manifest.

## 12. Expose the Application Locally

Create `k8s/service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: orders-api
spec:
  type: ClusterIP
  selector:
    app: orders-api
  ports:
    - name: http
      port: 80
      targetPort: 8080
```

Apply it:

```bash
kubectl apply -f k8s/service.yaml
kubectl get service orders-api
```

`ClusterIP` creates a Service reachable from within the cluster. It does not automatically expose the API to your host machine.

For a local test, use port forwarding:

```bash
kubectl port-forward service/orders-api 8080:80
```

Then, in another terminal:

```bash
curl -i http://localhost:8080/
```

Replace `/` with an endpoint that actually exists in your Spring Boot application. A `404` from an undefined route does not necessarily indicate a Kubernetes networking failure.

Port forwarding is a convenient development technique, not a general production exposure strategy.

## 13. The Most Useful Initial Commands

The essential command field guide for cluster inspection and workload debugging:

| Category | Primary Commands | Operational Purpose |
|---|---|---|
| **Cluster** | `kubectl cluster-info`<br>`kubectl get nodes` | Check cluster access, control-plane reachability, and node availability. |
| **Workloads** | `kubectl get deployments`<br>`kubectl get replicasets`<br>`kubectl get pods -o wide` | Compare desired replicas with actual running Pods and inspect their IP and node placement. |
| **Details** | `kubectl describe pod <pod-name>` | Inspect detailed conditions, scheduling decisions, probes, lifecycle events, and container exit codes. |
| **Logs** | `kubectl logs <pod-name>`<br>`kubectl logs <pod-name> --previous` | Stream current application output or examine logs from a previously crashed container instance. |
| **Events** | `kubectl get events --sort-by=.metadata.creationTimestamp` | Review cluster-wide scheduling, scaling, and failure events in chronological order. |
| **Rollout** | `kubectl rollout status deployment/orders-api`<br>`kubectl rollout history deployment/orders-api` | Monitor rollout transitions and inspect previous revision histories. |

## 14. Common Failure Modes

### `ImagePullBackOff`

**Meaning:** Kubernetes cannot successfully obtain the requested image.

Check:

```bash
kubectl describe pod <pod-name>
```

Look for events indicating:

- Image not found.
- Registry authentication failure.
- Network or DNS failure.
- Incorrect tag.
- Local image not loaded into the cluster.

For Kind, verify that the local image was loaded into the correct cluster.

### `CrashLoopBackOff`

**Meaning:** The container repeatedly terminates and Kubernetes backs off before restarting it.

Investigate:

```bash
kubectl logs <pod-name>
kubectl logs <pod-name> --previous
kubectl describe pod <pod-name>
```

Possible causes include invalid configuration, missing environment variables, failed startup dependencies, application exceptions, or resource constraints.

The status describes a restart pattern, not the root cause.

### `Pending`

A Pod may remain pending because:

- No node has sufficient requested resources.
- Scheduling constraints cannot be satisfied.
- A required volume cannot be attached or provisioned.
- A scheduling policy prevents placement.

Inspect the Pod's events and scheduling conditions.

### `Running` but not `Ready`

The container may be running while the application is still initializing, failing readiness checks, or unable to serve traffic correctly.

Check Pod conditions, container logs, probe configuration, and application health.

### Service has no working endpoints

Check that the Service selector matches the Pod labels:

```bash
kubectl get service orders-api -o yaml
kubectl get pods --show-labels
kubectl get endpointslice
```

A Service can exist even when no ready Pods match its selector.

---

# Layer 3 — Production Engineering & Interview Mastery

## 15. Resource Requests and Limits

Kubernetes resource configuration influences both scheduling and runtime behavior.

### Requests

A resource request describes the amount of a resource the scheduler should account for when placing the Pod.

For example:

```yaml
resources:
  requests:
    cpu: "250m"
    memory: "256Mi"
```

`250m` CPU means one quarter of a CPU core.

### Limits

A resource limit constrains resource usage.

```yaml
resources:
  limits:
    cpu: "1"
    memory: "512Mi"
```

CPU limits can cause throttling when the container attempts to exceed its permitted CPU usage. Memory-limit violations can result in an out-of-memory termination.

A Pod that requests too much memory may remain unschedulable. A Pod with a memory limit that is too low may repeatedly restart under load.

Resource values should be based on observed application behavior, workload testing, and capacity planning rather than arbitrary numbers.

## 16. Why Multiple Replicas Matter

Three replicas can improve availability and throughput, but only if the surrounding architecture supports them.

Ask:

- Can requests reach all replicas?
- Can replicas run on different nodes?
- Does the application rely on local in-memory state?
- Can the database handle concurrent connections from every replica?
- Do all replicas use compatible configuration?
- Can a rolling deployment maintain enough available replicas?
- Does the service remain healthy if one node fails?

**Important:** Three replicas on the same worker node do not provide the same node-failure protection as replicas distributed across independent nodes.

Replication of application Pods also does not automatically replicate database state or make a stateful dependency highly available.

## 17. What Kubernetes Does Not Guarantee

Kubernetes can help maintain declared workload state, but it does not automatically guarantee:

- Zero downtime for every deployment.
- Correct application logic.
- Database consistency.
- Durable storage.
- Safe secret management.
- Cross-node fault tolerance.
- Sufficient cluster capacity.
- Correct health checks.
- Secure network access.
- Reliable backups and recovery.

These outcomes depend on the application's design, Kubernetes configuration, cluster infrastructure, and operational practices.

## 18. Production Incident: The Deployment Never Becomes Ready

Imagine that you deploy version `1.1` of your Orders API.

The Deployment exists, but the rollout stalls.

Use a disciplined workflow:

1. Check rollout status.
2. Inspect Deployment and ReplicaSet events.
3. Inspect the Pods created by the new ReplicaSet.
4. Check container logs.
5. Check the image reference and image availability.
6. Review environment variables and external dependencies.
7. Review resource requests, limits, and scheduling constraints.
8. Check readiness probes if configured.
9. Compare the new version with the previous healthy revision.
10. Roll back if the new version is causing an active production incident and rollback is safe.

Useful commands:

```bash
kubectl rollout status deployment/orders-api
kubectl get replicasets
kubectl get pods -o wide
kubectl describe deployment orders-api
kubectl describe pod <pod-name>
kubectl logs <pod-name> --previous
```

If you decide to roll back:

```bash
kubectl rollout undo deployment/orders-api
kubectl rollout status deployment/orders-api
```

Verify the application and its dependencies after the rollback. A successful rollout command does not prove that every user-facing operation is functioning correctly.

## 19. Kubernetes Interview Questions

**1. What is Kubernetes?**

A container-orchestration platform that manages workloads and cluster resources through declarative APIs and controllers.

**2. What is a cluster?**

A Kubernetes environment consisting of a control plane and worker nodes.

**3. What does the API server do?**

It exposes the Kubernetes API and serves as the main interface for cluster operations.

**4. What is etcd?**

The consistent key-value store used to persist Kubernetes cluster state.

**5. What does the scheduler do?**

It selects an appropriate node for Pods that have not yet been scheduled.

**6. What is a Pod?**

The smallest deployable Kubernetes workload unit, containing one or more closely related containers.

**7. Why use a Deployment instead of creating Pods manually?**

A Deployment provides declarative replica management, rollout behavior, and revision history through ReplicaSets.

**8. What is a ReplicaSet?**

A controller-managed resource that maintains the desired number of matching Pods.

**9. Why do Services exist?**

They provide a stable network identity for accessing a changing set of matching Pods.

**10. What is a Namespace?**

A mechanism for organizing namespaced resources within a cluster. It is not, by itself, a complete security boundary.

**11. What is declarative configuration?**

Describing the desired state and allowing Kubernetes controllers to reconcile observed state toward it.

**12. Does `kubectl apply` mean the application is healthy?**

No. It means the configuration was accepted or updated. Workloads may still be unscheduled, starting, crashing, or not ready.

**13. What is the difference between `Running` and `Ready`?**

`Running` describes the Pod phase. `Ready` indicates whether the Pod currently satisfies the conditions for being considered ready to serve traffic.

**14. What is `CrashLoopBackOff`?**

A restart-backoff condition seen when a container repeatedly terminates and Kubernetes delays subsequent restart attempts.

**15. What causes `ImagePullBackOff`?**

Failures obtaining an image, such as an invalid image reference, unavailable registry, authentication problem, or missing local image.

**16. What is the purpose of resource requests?**

They inform scheduling decisions and describe the resources the workload requests.

**17. What can happen when a container exceeds its memory limit?**

It may be terminated due to an out-of-memory condition.

**18. Does Kubernetes automatically make an application highly available?**

No. Kubernetes provides orchestration mechanisms, but availability also depends on replica placement, dependencies, health checks, capacity, and application design.

**19. Why is a local image sometimes unavailable to a local Kubernetes cluster?**

The cluster's nodes may have separate image caches from the host's Docker daemon. The image must be loaded into the cluster or made available from a registry.

**20. How do you investigate a failed rollout?**

Inspect rollout status, ReplicaSets, Pod events, image availability, application logs, configuration, resources, and readiness behavior. Roll back if needed and safe.

## 20. Hands-On Capstone

Deploy a Spring Boot Orders API to your local Kubernetes cluster.

### Tasks

- [ ] Create a local cluster.
- [ ] Build the application JAR.
- [ ] Build a container image.
- [ ] Load the image into the local cluster or publish it to a registry.
- [ ] Create a Deployment with three replicas.
- [ ] Configure resource requests and limits.
- [ ] Create a ClusterIP Service.
- [ ] Verify that the Pods become ready.
- [ ] Use port forwarding to test a real API endpoint.
- [ ] Intentionally use an incorrect image tag and diagnose the failure.
- [ ] Inspect logs for a container that exits.
- [ ] Explain the difference between desired, existing, ready, and available replicas.
- [ ] Roll back a test Deployment revision.
- [ ] Document the troubleshooting sequence and evidence.

### Mastery standard

You should be able to explain how a declarative Deployment becomes running Pods, trace the responsibilities of the control plane and worker nodes, and diagnose the first layer of Kubernetes workload failures without guessing.

---

# Final Mastery Checklist

- [ ] Explain Kubernetes' role relative to Docker.
- [ ] Describe the control plane and worker-node components.
- [ ] Explain the API server, etcd, scheduler, controllers, and kubelet.
- [ ] Distinguish Pods, ReplicaSets, Deployments, Services, and Namespaces.
- [ ] Explain desired state and reconciliation.
- [ ] Deploy a Spring Boot API locally.
- [ ] Explain requests versus limits.
- [ ] Diagnose `Pending`, `CrashLoopBackOff`, and `ImagePullBackOff`.
- [ ] Understand why `Running` does not necessarily mean `Ready`.
- [ ] Explain why replicas alone do not guarantee high availability.
- [ ] Perform a controlled rollback.
- [ ] Complete the hands-on capstone.

## Kubernetes Handbook Progress

This is **Chunk 1 of 3**. The remaining planned chunks are:

- **Chunk 2:** Services, Networking, Ingress, Configuration, Secrets & Persistent Storage.
- **Chunk 3:** Production Reliability, Security, Autoscaling, Observability, Incident Mastery & Interview Preparation.

Save this chapter to:

`content/kubernetes/01-kubernetes-containers-cluster-architecture-core-mental-models.md`

Do not generate the Kubernetes PDF yet. Save and verify all three planned chapters first, then generate the single complete handbook at:

`docs/kubernetes/BEH_KUBERNETES_COMPLETE_HANDBOOK.pdf`

After all three source chapters and the final PDF are saved and verified, commit using the exact message:

`Kubernetes done`

Do not claim repository changes, PDF generation, or Git commits until they have actually been performed and verified.
