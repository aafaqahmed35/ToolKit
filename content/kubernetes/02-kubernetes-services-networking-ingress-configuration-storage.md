# Kubernetes — Chunk 2 of 3: Services, Networking, Ingress, Configuration, Secrets & Persistent Storage

**Backend Engineering Tools & Infrastructure Handbook**

**Source file:** `content/kubernetes/02-kubernetes-services-networking-ingress-configuration-storage.md`

---

## Learning Objectives

By the end of this chapter, you should be able to:

- Explain how Kubernetes networking connects Pods, Services, and external clients.
- Distinguish ClusterIP, NodePort, and LoadBalancer Services.
- Understand DNS-based service discovery.
- Explain Ingress and the role of an Ingress controller.
- Manage application configuration with ConfigMaps and Secrets.
- Understand PersistentVolumes, PersistentVolumeClaims, and StorageClasses.
- Deploy a multi-component backend application locally.
- Troubleshoot connectivity, configuration, and storage failures.
- Answer common Kubernetes networking and configuration interview questions.

This chapter covers all three required layers:

1. **Fundamentals & Mental Models**
2. **Practical Engineering & Workflows**
3. **Production Engineering & Interview Mastery**

# Layer 1 — Fundamentals & Mental Models

## 1. The Kubernetes Networking Problem

In a backend application, several components need to communicate:

- A client sends a request to the Orders API.
- The Orders API queries PostgreSQL.
- The API uses Redis for caching.
- An asynchronous worker processes events from Kafka.

Kubernetes Pods are replaceable. Their IP addresses can change when they are recreated. Applications therefore need a stable way to locate other components.

Kubernetes networking provides mechanisms for:

- Pod-to-Pod communication.
- Stable access to a group of Pods.
- Service discovery through DNS.
- External access to applications.
- Network isolation through supported networking policies.

**Mental model:** Pods are the changing destinations; Services provide stable access to a selected set of Pods.

## 2. How a Service Routes Traffic

```text
+-------------------------------------------------------+
|             Client or another application             |
|         (Requests a stable service address)           |
+-------------------------------------------------------+
                            |
                            v
+-------------------------------------------------------+
|                   Kubernetes Service                  |
|          (Stable virtual IP and DNS identity)         |
+-------------------------------------------------------+
                            |
       +--------------------+--------------------+
       |                    |                    |
       v                    v                    v
+--------------+     +--------------+     +--------------+
|    Pod A     |     |    Pod B     |     |    Pod C     |
|   (Ready)    |     |   (Ready)    |     |   (Ready)    |
+--------------+     +--------------+     +--------------+
```

A typical Service selects Pods using labels. Kubernetes maintains endpoint information for matching Pods, commonly through EndpointSlices.

The cluster's networking implementation handles traffic delivery. Depending on the cluster, this may involve `kube-proxy` or an alternative implementation.

A Service does not repair a broken application. It provides a stable access mechanism to eligible endpoints.

## 3. Kubernetes Service Types

| Service Type | Routing Mechanism | Typical Production Use Case |
|---|---|---|
| **ClusterIP** *(Default)* | Exposes a stable virtual IP reachable only from within the cluster. | Internal backend communication (e.g. Orders API querying PostgreSQL or Redis). |
| **NodePort** | Exposes the Service on a static high port (`30000-32767`) across every cluster node's IP. | Direct node debugging, local development clusters, or non-cloud bare-metal setups. |
| **LoadBalancer** | Provisions an external cloud load balancer (e.g. AWS NLB/ALB, GCP Cloud LB) pointing to node endpoints. | Publicly exposing critical production entrypoints when Ingress is not used. |

### Example: Internal API Service

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

Here:

- `port` is the port exposed by the Service.
- `targetPort` is the destination port on the selected Pod.
- `selector` identifies Pods using their labels.

If the application listens on port 8080, the Service can accept traffic on port 80 and forward it to port 8080.

## 4. Kubernetes DNS and Service Discovery

Kubernetes clusters commonly provide DNS-based discovery for Services.

Within the same Namespace, a client can usually connect using the Service name:

```text
http://orders-api
```

A fully qualified Service DNS name typically follows this pattern:

```text
<service>.<namespace>.svc.cluster.local
```

For example:

```text
http://orders-api.production.svc.cluster.local
```

The exact cluster domain can be configured, so `cluster.local` is common rather than universal.

### Example: Backend connection configuration

Suppose the `orders-api` application needs Redis.

Inside the same Namespace, its Redis URL might be:

```text
redis://redis:6379
```

If Redis is in another Namespace:

```text
redis://redis.data.svc.cluster.local:6379
```

This works only if a matching Service exists, DNS is functioning, network policies permit the connection, and the destination is reachable.

**Common mistake:** Using `localhost` to connect to another Pod.

Inside a container, `localhost` refers to that container's own network namespace. It does not automatically mean another Pod, another Service, or your laptop.

## 5. Ingress: HTTP and HTTPS Entry Routing

A Service gives you a stable endpoint. Ingress provides a declarative way to describe HTTP and HTTPS routing from outside the cluster to Services.

For example:

```text
api.example.com/orders   → orders-api Service
api.example.com/payments → payments-api Service
```

The architecture commonly looks like this:

```text
External Client
      |
      v
Ingress Controller
      |
      +------> orders-api Service ------> Orders Pods
      |
      +------> payments-api Service ----> Payments Pods
```

### Ingress versus Ingress controller

These are not the same thing.

- **Ingress resource:** Declares routing rules for HTTP and HTTPS traffic.
- **Ingress controller:** Implements those rules by configuring or operating the actual traffic-routing mechanism.

Creating an Ingress resource does not guarantee that traffic is routed. A suitable controller must be installed and configured, and the environment must provide the required network access.

Kubernetes also supports the Gateway API, which offers a richer model for traffic management. This handbook focuses on Ingress for foundational understanding.

## 6. ConfigMaps and Secrets

Applications need configuration that changes between environments.

Examples include:

- Database hostnames.
- Port numbers.
- Feature flags.
- External service URLs.
- Database credentials.
- API tokens.

Hardcoding every setting into an image makes deployments difficult to manage. Kubernetes provides ConfigMaps and Secrets to separate configuration from application images.

### ConfigMap

A ConfigMap stores non-confidential configuration.

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: orders-config
data:
  APP_ENV: "development"
  REDIS_HOST: "redis"
  REDIS_PORT: "6379"
```

A Deployment can inject these values into a container:

```yaml
envFrom:
  - configMapRef:
      name: orders-config
```

### Secret

A Secret is designed for confidential configuration, such as credentials or tokens.

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: orders-db-secret
type: Opaque
stringData:
  DB_USERNAME: app_user
  DB_PASSWORD: replace-with-a-development-only-password
```

Inject the values:

```yaml
env:
  - name: DB_USERNAME
    valueFrom:
      secretKeyRef:
        name: orders-db-secret
        key: DB_USERNAME
  - name: DB_PASSWORD
    valueFrom:
      secretKeyRef:
        name: orders-db-secret
        key: DB_PASSWORD
```

The example password is a placeholder. Do not use it as a real credential.

**Security warning:** Kubernetes Secrets are not automatically encrypted end-to-end merely because they are called Secrets. Their data may be stored in etcd, and access depends on cluster configuration and authorization. Use least-privilege RBAC, encryption at rest where supported, secure delivery workflows, and an appropriate secret-management solution.

Base64 encoding is not encryption.

## 7. Persistent Storage: Why Containers Need More Than a Filesystem

A container's writable filesystem is not an appropriate default for durable application data.

Consider a PostgreSQL Pod that stores database files only in its writable container layer. If the Pod is replaced, the database files may be lost.

Kubernetes storage abstractions separate the lifecycle of a workload from the lifecycle of its storage.

| Resource | Purpose |
|---|---|
| PersistentVolume (PV) | Represents provisioned storage available to the cluster |
| PersistentVolumeClaim (PVC) | Requests storage with particular requirements |
| StorageClass | Defines a storage provisioning class and its behavior |
| Volume mount | Makes a volume accessible inside a container |

A PVC can request storage without the application needing to know every infrastructure-specific detail.

The actual behavior depends on the cluster's storage provisioner and volume configuration.

### Mental model

- A Pod is an application execution unit.
- A PVC is a storage request.
- A PV represents storage made available to satisfy a claim.
- A StorageClass describes how storage can be provisioned.

**Important:** Persistent storage is not the same as a backup. A persistent volume may survive Pod replacement but still be lost through deletion, corruption, infrastructure failure, or an incorrect storage operation.

---

# Layer 2 — Practical Engineering & Workflows

## 8. Lab: Deploy a Multi-Service Backend

We will extend the local Kubernetes cluster from Chunk 1.

The learning architecture:

```text
Local Client
    |
    | port-forward
    v
orders-api Service
    |
    v
Orders API Pods
    |
    +------> redis Service
```

This lab focuses on Service discovery, configuration, and connectivity. It does not attempt to create a production-grade Redis deployment.

### Step 1 — Verify the cluster

```bash
kubectl config current-context
kubectl get nodes
kubectl get deployments
kubectl get pods -o wide
```

Confirm that the active context is your local learning cluster before continuing.

### Step 2 — Deploy Redis for the lab

Create `k8s/redis.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - name: redis
          image: redis:7
          ports:
            - name: redis
              containerPort: 6379
```

Create its Service:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: redis
spec:
  type: ClusterIP
  selector:
    app: redis
  ports:
    - name: redis
      port: 6379
      targetPort: 6379
```

Save these resources in a single `redis.yaml` file separated by `---`, or use separate files.

Apply the resources:

```bash
kubectl apply -f k8s/redis.yaml
kubectl get deployment redis
kubectl get service redis
kubectl get pods -l app=redis
```

This Redis configuration is intentionally minimal. It has no durable storage, authentication, or production hardening. Do not use it for important data.

### Step 3 — Configure the Orders API

Create `k8s/orders-config.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: orders-config
data:
  APP_ENV: "development"
  REDIS_HOST: "redis"
  REDIS_PORT: "6379"
```

Apply it:

```bash
kubectl apply -f k8s/orders-config.yaml
```

Update the Orders API Deployment to consume it:

```yaml
envFrom:
  - configMapRef:
      name: orders-config
```

Place `envFrom` under the application container definition, at the same level as `image`, `ports`, and `resources`.

Your Spring Boot application must actually read `REDIS_HOST` and `REDIS_PORT` for this configuration to affect its Redis connection.

### Step 4 — Verify Service discovery

Inspect the Service and endpoints:

```bash
kubectl get service redis
kubectl get endpointslice
kubectl get pods -l app=redis --show-labels
```

If you have a suitable debugging container in the cluster, test DNS resolution and TCP connectivity from it.

For example, a temporary diagnostic Pod could use a networking utility image approved for your environment. Keep diagnostic images controlled and remove temporary resources afterward.

Inside a Pod in the same Namespace, DNS resolution should normally resolve `redis` to the Service's cluster address.

If resolution fails, inspect DNS configuration, Namespace, Service existence, and cluster DNS health.

### Step 5 — Test the API

Use the Service from the local host through port forwarding:

```bash
kubectl port-forward service/orders-api 8080:80
```

In a separate terminal, test a real application route:

```bash
curl -i http://localhost:8080/actuator/health
```

This assumes Spring Boot Actuator is installed and the health endpoint is enabled and exposed. Otherwise, use an endpoint that exists in your application.

A successful health response does not necessarily prove Redis operations work. Test the API path that actually exercises Redis if Redis integration is part of the application.

## 9. Lab: Configure a Secret Safely

For a local exercise, you can create a Secret interactively rather than committing credentials to YAML.

```bash
kubectl create secret generic orders-db-secret \
  --from-literal=DB_USERNAME=app_user \
  --from-literal=DB_PASSWORD='local-only-test-password'
```

The example is for a disposable local environment only.

Reference the Secret in the Deployment using `secretKeyRef`, as shown earlier.

Verify the Secret exists:

```bash
kubectl get secret orders-db-secret
kubectl describe secret orders-db-secret
```

Avoid printing secret values to terminal logs or copying them into tickets.

For production, prefer an approved secret-management workflow and avoid passing real credentials through shell history or process arguments.

## 10. Lab: Add Persistent Storage

For a local cluster with a working dynamic storage provisioner, create a PVC:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: app-data
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
```

Apply and inspect it:

```bash
kubectl apply -f k8s/app-data-pvc.yaml
kubectl get pvc
kubectl describe pvc app-data
```

The claim may remain `Pending` if the cluster lacks a suitable StorageClass or provisioner. That is a storage-provisioning problem, not necessarily an application problem.

To use the claim, mount it into a Pod:

```yaml
volumeMounts:
  - name: app-data
    mountPath: /var/lib/app-data

volumes:
  - name: app-data
    persistentVolumeClaim:
      claimName: app-data
```

The `volumeMounts` field belongs inside the container specification; `volumes` belongs inside the Pod specification.

Use a path appropriate for your application. Do not mount an arbitrary volume over application files or database directories without understanding the implications.

## 11. Troubleshooting Service Connectivity

Use this sequence when one Pod cannot reach another application.

### A. Confirm the destination Service exists

```bash
kubectl get services
kubectl describe service redis
```

### B. Confirm the selector matches Pod labels

```bash
kubectl get pods --show-labels
kubectl get service redis -o yaml
```

A selector mismatch can result in no matching endpoints.

### C. Inspect EndpointSlices

```bash
kubectl get endpointslice
```

Confirm that the Service has the expected endpoint addresses and ports.

### D. Check DNS from the client Pod

Use a diagnostic container to resolve the Service name.

If DNS fails, check the name, Namespace, cluster DNS, and network configuration.

### E. Check the application listener

Confirm the destination application is actually listening on the expected port. A Pod's `containerPort` declaration does not force an application to bind to that port.

### F. Check network policies

If the cluster uses NetworkPolicies, confirm that the policies permit the required ingress and egress traffic and that the networking implementation enforces them.

### G. Inspect logs and events

```bash
kubectl describe pod <pod-name>
kubectl logs <pod-name>
kubectl get events --sort-by=.metadata.creationTimestamp
```

**Debugging principle:** Follow the request path one boundary at a time: DNS, Service, endpoints, network path, listening socket, and application behavior.

## 12. Troubleshooting Configuration and Storage

### ConfigMap changes do not appear in the application

Possible explanations:

- The Pod uses environment variables populated at startup.
- The Deployment has not recreated the Pod.
- The application reads a different variable name.
- The application caches configuration.
- The ConfigMap is mounted as a file and the application does not reload it.

Changing a ConfigMap does not guarantee that an application automatically reloads its settings. Confirm the configuration delivery method and restart or reload the application as required.

### Secret reference fails

Check:

- Secret name and Namespace.
- Key name spelling.
- Pod specification.
- Service account permissions and relevant policy.
- Application variable names.
- Whether the secret exists before the Pod starts.

Do not dump secret values into logs as a debugging shortcut.

### PVC remains pending

Check:

```bash
kubectl get pvc
kubectl describe pvc app-data
kubectl get storageclass
kubectl get events --sort-by=.metadata.creationTimestamp
```

Potential causes include missing StorageClasses, unsupported access modes, capacity constraints, and provisioner failures.

### Pod starts but cannot write to its volume

Investigate volume mounts, filesystem permissions, security context, ownership, access mode, and the application's write path.

A bound PVC alone does not guarantee that the process has permission to write to the mounted directory.

---

# Layer 3 — Production Engineering & Interview Mastery

## 13. Networking Reliability

Production networking requires more than creating a Service.

Consider:

- Is the Service selecting the intended Pods?
- Are only appropriate Pods considered ready endpoints?
- Does DNS resolve consistently?
- Are ports aligned across the application, container, and Service?
- Do network policies permit the expected traffic?
- Can the destination handle connection volume?
- Are connection timeouts and retry behavior appropriate?
- Is external traffic protected by the intended TLS and access-control design?

### Readiness versus liveness

These probes have different jobs:

- **Readiness probe:** Determines whether the container should be considered ready to serve traffic.
- **Liveness probe:** Determines whether the container should be restarted because it is unhealthy in a way that warrants restart.
- **Startup probe:** Gives a slow-starting application time to initialize before liveness and readiness checks take effect in the usual configured pattern.

An overly aggressive liveness probe can repeatedly restart a slow but recoverable application. A readiness probe that is too permissive can route traffic to an application that cannot serve requests.

Probe design is an application-reliability decision, not merely YAML configuration.

## 14. Ingress and TLS Considerations

In production, HTTP routing and TLS termination need a deliberate design.

A typical request path may be:

```text
Client
  |
  | HTTPS
  v
External Load Balancer
  |
  v
Ingress Controller
  |
  v
Service
  |
  v
Application Pod
```

The exact path depends on the environment. TLS can terminate at different points, and the security of traffic between components must be considered separately.

Operational requirements include:

- A supported Ingress controller.
- Correct host and path rules.
- Valid certificates and renewal procedures.
- Correct backend Service ports.
- Appropriate request-size and timeout policies.
- Safe external exposure.
- Observability for routing failures.

A `404` from the Ingress layer, a `502` from a proxy, and a connection timeout can indicate different failure points. Identify which component generated the response before changing configuration.

## 15. Secrets and Access Control in Production

Use least privilege.

- Give workloads only the permissions they need.
- Avoid giving application Pods broad Kubernetes API permissions.
- Restrict who can read Secrets.
- Enable and verify encryption at rest where supported.
- Rotate credentials and revoke compromised values.
- Avoid putting credentials into container images or Git.
- Prefer a managed secret store or approved secret operator where appropriate.
- Audit access to sensitive resources.

Kubernetes RBAC controls API permissions; it does not automatically restrict every possible route to sensitive data. For example, access to create a Pod in a Namespace may, depending on permissions and configuration, create indirect ways to access mounted Secrets.

Security reviews should consider the effective permissions and workload capabilities, not only whether a user has direct permission to read a Secret.

## 16. Stateful Workloads and Persistent Storage

For databases and other stateful systems, the following questions matter:

- What happens when a Pod is recreated?
- Does storage survive Pod replacement?
- Is the storage replicated?
- What is the backup strategy?
- Can the application recover after corruption?
- How does volume attachment behave during rescheduling?
- What are the storage performance characteristics?
- Is recovery tested?

A PVC provides a storage abstraction, not a complete data-protection strategy.

StatefulSets can help manage stable identities and storage associations for stateful workloads, but they do not automatically make a database cluster highly available or consistent.

For production databases, choose the operational model deliberately: a managed database, a well-operated stateful deployment, or another architecture appropriate to the team's capabilities.

## 17. Production Incident Simulations

### Incident A — Orders API cannot connect to Redis

**Symptoms:** API requests fail when accessing cached data.

Investigate:

1. Confirm the Redis Service exists.
2. Verify Service selectors and EndpointSlices.
3. Confirm the Redis Pod is ready.
4. Resolve the Service DNS name from the API Pod.
5. Test TCP connectivity to the expected port.
6. Inspect NetworkPolicies.
7. Check the application connection URL and credentials.
8. Review Redis logs and API exception details.

**Likely causes:** Incorrect hostname, wrong Namespace, missing endpoints, incorrect port, network policy restrictions, authentication failure, or a Redis process that is not ready.

**Lesson:** A successful DNS lookup proves only name resolution, not that the destination accepts connections.

### Incident B — Deployment is healthy, but external users receive 502 responses

Investigate:

1. Confirm the external load balancer and Ingress controller are healthy.
2. Inspect the Ingress resource and controller events.
3. Check the backend Service name and port.
4. Inspect EndpointSlices.
5. Verify application listening ports.
6. Check readiness and startup behavior.
7. Inspect proxy logs and application logs.
8. Test connectivity at each layer.

**Likely causes:** Wrong backend port, missing endpoints, unhealthy Pods, proxy timeouts, or incorrect routing configuration.

**Lesson:** Start at the layer where the failure appears and trace the request inward.

### Incident C — Application configuration does not change after a ConfigMap update

Investigate:

1. Verify the ConfigMap's current content.
2. Check whether values are injected as environment variables or mounted files.
3. Determine whether the Pod must be recreated.
4. Confirm the application uses the expected variable or file.
5. Check whether the application caches configuration.
6. Verify the running Pod's effective configuration without exposing secrets.

**Likely cause:** Environment variables are populated when the container starts, so existing processes may continue using their old values.

**Lesson:** Configuration storage and configuration activation are different operations.

### Incident D — Database Pod is recreated and data disappears

Investigate:

1. Determine where the database wrote its data.
2. Inspect the Pod's volume mounts.
3. Check whether a PVC was used.
4. Inspect the PVC and PV lifecycle.
5. Check whether the database data directory was mounted correctly.
6. Determine whether data was deleted or merely became inaccessible.
7. Inspect backup and restore procedures.

**Likely cause:** Data was stored only in ephemeral container storage, or the persistent volume was incorrectly configured.

**Lesson:** Storage persistence, replication, and backup are separate requirements.

## 18. Twenty Interview Questions and Answers

**1. What is a Kubernetes Service?**

A stable network abstraction that exposes a set of matching Pods through a virtual address and, commonly, DNS.

**2. What is the difference between ClusterIP and NodePort?**

ClusterIP provides internal cluster access. NodePort exposes a Service through a port on cluster nodes, subject to the networking environment.

**3. What does a LoadBalancer Service do?**

It requests a load-balancing implementation from the underlying environment, when supported, to expose the Service externally.

**4. What is the difference between `port` and `targetPort`?**

`port` is the Service's exposed port; `targetPort` is the destination port on the selected Pod.

**5. How does Kubernetes DNS work for Services?**

Cluster DNS resolves Service names to Service addresses. Fully qualified names include the Service, Namespace, and cluster DNS domain.

**6. Why should an application avoid using another Pod's IP directly?**

Pods can be replaced and receive new IPs. A Service provides a more stable destination.

**7. What is Ingress?**

A Kubernetes API resource for declaring HTTP and HTTPS routing rules to Services.

**8. What is an Ingress controller?**

The component that implements Ingress rules. An Ingress resource alone does not provide traffic routing.

**9. What is a ConfigMap?**

A Kubernetes object for storing non-confidential configuration data.

**10. What is a Secret?**

A Kubernetes object intended for sensitive configuration, such as credentials. Proper access control and storage protections are still necessary.

**11. Is Base64 encryption?**

No. Base64 is an encoding format, not encryption.

**12. What is a PersistentVolume?**

A cluster storage resource representing provisioned storage.

**13. What is a PersistentVolumeClaim?**

A request for storage with specified requirements.

**14. What is a StorageClass?**

A resource describing a class of storage and its provisioning behavior.

**15. Does a PVC guarantee backups?**

No. Persistence and backup/recovery are different requirements.

**16. Why might a Service have no endpoints?**

Its selector may not match any Pods, or matching Pods may not be eligible endpoints because of their state or readiness.

**17. Why does `localhost` fail when connecting to another Pod?**

`localhost` refers to the current network namespace, not the other Pod.

**18. What is the difference between readiness and liveness probes?**

Readiness controls whether a container should receive traffic; liveness helps determine whether a container should be restarted.

**19. Why might a ConfigMap update not change the running application?**

The application may use environment variables populated at startup, cache configuration, or lack file-reload behavior.

**20. How would you debug an API-to-database connection failure?**

Verify the Service, selector, endpoints, DNS, network policies, port, process listener, credentials, and application logs in sequence.

## 19. Hands-On Capstone

Extend the Orders API deployment to include service discovery and external access planning.

### Required tasks

- [ ] Create an internal Redis Service.
- [ ] Configure the Orders API using a ConfigMap.
- [ ] Create a development-only Secret using a safe local workflow.
- [ ] Confirm that the API can resolve the Redis Service name.
- [ ] Inspect Service EndpointSlices.
- [ ] Test a real API endpoint using port forwarding.
- [ ] Create a PVC and inspect its binding status.
- [ ] Explain what happens when the Pod is recreated.
- [ ] Design an Ingress rule and identify the controller required to implement it.
- [ ] Diagnose a deliberate Service selector mismatch.
- [ ] Explain why a Secret is not automatically secure merely because it is a Secret.
- [ ] Write a short incident report for a connectivity or storage failure.

### Completion standard

You can trace traffic from a client to a Pod, explain how applications find each other, manage configuration separately from application images, and distinguish persistent storage from a complete backup strategy.

---

# Final Mastery Checklist

- [ ] Explain Service networking and stable Pod access.
- [ ] Distinguish ClusterIP, NodePort, and LoadBalancer.
- [ ] Explain Kubernetes Service DNS.
- [ ] Distinguish Ingress resources from Ingress controllers.
- [ ] Configure and troubleshoot ConfigMaps.
- [ ] Use Secrets with least-privilege access.
- [ ] Explain PVs, PVCs, and StorageClasses.
- [ ] Understand why persistence is not backup.
- [ ] Troubleshoot selector mismatches and missing endpoints.
- [ ] Explain readiness, liveness, and startup probes.
- [ ] Diagnose connectivity and configuration incidents.
- [ ] Complete the hands-on capstone.

## Kubernetes Handbook Progress

This is **Chunk 2 of 3**.

The remaining planned chapter is:

**Chunk 3 — Production Reliability, Security, Autoscaling, Observability, Incident Mastery & Interview Preparation**

Save this chapter as:

`content/kubernetes/02-kubernetes-services-networking-ingress-configuration-storage.md`

Do not generate the Kubernetes PDF yet. Save and verify all three planned chapters first, then generate the single complete handbook at:

`docs/kubernetes/BEH_KUBERNETES_COMPLETE_HANDBOOK.pdf`

After all three source chapters and the final PDF are saved and verified, commit with the exact message:

`Kubernetes done`

Do not claim repository changes, PDF generation, or Git commits until they have actually been performed and verified.
