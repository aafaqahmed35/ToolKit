# AWS — Chunk 3 of 6: EC2, Application Load Balancers, Auto Scaling & Compute Architecture

## Backend Engineering Tools & Infrastructure Handbook · Cloud Engineering Track

**Source file:** `content/aws/03-aws-ec2-load-balancing-auto-scaling-compute-architecture.md`

---

## Learning Objectives

By the end of this chapter, you should be able to:

- Explain how EC2 runs a backend application.
- Understand AMIs, instance types, EBS volumes, launch templates, and instance metadata.
- Explain how an Application Load Balancer distributes requests.
- Configure the conceptual architecture of an Auto Scaling Group.
- Trace a request from a client to a Spring Boot application running on EC2.
- Diagnose common 502/503 errors, unhealthy targets, and failed scaling events.
- Discuss compute reliability and scaling trade-offs at an FAANG SDE-1 interview level.

---

# Layer 1 — Fundamentals & Mental Models

## 1. The Simplest Mental Model of EC2

Imagine that you have built a Spring Boot REST API on your laptop.

Your application works locally, but users on the internet cannot reliably access your laptop as a production server. You need a machine that can run continuously, accept network traffic, and provide sufficient compute resources.

**Amazon EC2 (Elastic Compute Cloud)** provides virtual machines in AWS.

Think of EC2 as renting a computer in an AWS data center. You select its operating system, CPU and memory capacity, storage configuration, and networking permissions.

You can install Java, run your Spring Boot JAR, configure a service, and expose the application through a controlled network path.

### What EC2 gives you

- **Compute:** CPU and memory to execute application code.
- **Operating system:** Linux or Windows, depending on the selected image.
- **Storage:** Attached volumes for files and application data.
- **Networking:** Private IP addresses, optional public connectivity, and security groups.
- **Identity:** An instance profile can provide AWS permissions to the application.
- **Lifecycle control:** Start, stop, reboot, terminate, or replace instances.

EC2 is infrastructure, not a complete application platform. You still manage the guest operating system, runtime, application process, deployment strategy, and much of the operational configuration.

---

## 2. The Five Concepts You Must Understand

Understanding EC2 requires mastering five distinct concepts that work together to form the compute platform:

### 1. EC2 Instance — The Running Machine
The virtual server executing your application. Its available CPU, memory, network performance, and cost depend on the instance type and configuration.

### 2. AMI — The Machine's Starting Blueprint
An **Amazon Machine Image** contains the information required to launch an instance, including its operating system and configured software or image data. AMIs help standardize server creation across your fleet.

### 3. Instance Type — The Hardware Profile
Determines the machine's resource characteristics. Different families emphasize general-purpose workloads, compute, memory, storage, or accelerated processing.

### 4. EBS — Persistent Block Storage
**Elastic Block Store** volumes can hold operating-system data, application files, and other data that should survive an instance reboot. Volume lifecycle and deletion settings matter when instances are terminated.

### 5. IAM Instance Role — The Machine's AWS Identity
An attached **instance profile** makes role credentials available to software running on the instance. Use it to grant specific AWS permissions without embedding long-lived access keys in code or configuration files.

### Summary Comparison

| Concept | What It Is | Purpose |
|---|---|---|
| **AMI** | Launch blueprint | Machine image, OS baseline, and pre-baked software |
| **Instance Type** | Hardware profile | CPU, RAM, network throughput, and I/O capacity |
| **EC2 Instance** | Virtual machine | The actively running server executing workloads |
| **EBS Volume** | Block storage | Persistent local virtual disk attached over the network |
| **Instance Role** | AWS identity | Least-privilege IAM permissions for application code |

### A useful distinction

An AMI is not the same thing as a running instance:
- **AMI:** The launch blueprint.
- **Instance type:** The compute capacity.
- **EC2 instance:** The running virtual machine.
- **EBS volume:** Attached block storage.
- **Instance role:** The AWS permissions available to the workload.

You can launch multiple instances from the same AMI and instance type, each running a separate copy of your backend.

---

## 3. EC2 Instance Families and Choosing Capacity

AWS offers instance families optimized for different workloads. Exact names, availability, and pricing vary by region and change over time.

| Workload | What matters most | Starting point | Example AWS Family |
|---|---|---|---|
| **Ordinary REST API** | Balanced CPU and memory | General-purpose instance | `t4g`, `m6i`, `m7g` |
| **CPU-heavy processing** | Sustained CPU throughput | Compute-optimized instance | `c6i`, `c7g` |
| **Large in-memory workload** | RAM capacity | Memory-optimized instance | `r6i`, `r7g` |
| **Storage-intensive processing** | Storage throughput and IOPS | Storage-optimized instance | `i3en`, `i4i` |

For a small Spring Boot API, a general-purpose instance may be a sensible starting point. However, do not select production capacity based solely on a tutorial's recommendation.

Measure:

- CPU utilization and throttling where applicable (e.g., T-series burstable CPU credits).
- Heap usage and garbage-collection behavior.
- Process memory and operating-system memory pressure.
- Request rate and latency percentiles (p50, p95, p99).
- Network throughput and connection counts.
- Database connection-pool usage.

> **Interview Insight:** High CPU does not automatically mean that you need a larger instance. The bottleneck could be an inefficient query, excessive serialization, a tight retry loop, or an application bug. Diagnose before scaling vertically.

---

## 4. How Does a Client Reach an EC2 Application?

Suppose your application listens on port `8080`.

A simplified direct-access path looks like this:

```text
Client
  |
  | HTTPS request
  v
Public network
  |
  v
EC2 public IPv4 address
  |
  v
EC2 security group permits the connection
  |
  v
Operating-system firewall and network stack
  |
  v
Spring Boot process listening on port 8080
```

This architecture can work for learning, but it is usually not the preferred production entry point for a horizontally scalable API.

Problems include:

- A public instance IP can change after certain lifecycle events (e.g., stop/start).
- One instance is a single point of failure.
- Clients become tightly coupled to the instance's specific address.
- There is no managed layer distributing traffic across multiple instances.
- TLS termination, routing, and traffic-management responsibilities become harder to organize.

A more resilient architecture introduces a load balancer.

---

## 5. Application Load Balancer: The Traffic Director

An **Application Load Balancer (ALB)** distributes incoming HTTP and HTTPS requests across registered targets, such as EC2 instances.

It operates at **Layer 7** of the networking model, where it can understand HTTP-level information such as hostnames, paths, query parameters, and HTTP headers.

```text
                      +------------------------------------------+
                      |                 Clients                  |
                      | Browsers, mobile apps, backend services  |
                      +--------------------+---------------------+
                                           |
                                           v
                      +------------------------------------------+
                      |        Application Load Balancer         |
                      | HTTPS listener · host/path · target sel. |
                      +--------------------+---------------------+
                                           |
               +---------------------------+---------------------------+
               |                           |                           |
               v                           v                           v
     +-------------------+       +-------------------+       +-------------------+
     |       EC2 A       |       |       EC2 B       |       |       EC2 C       |
     |    Spring Boot    |       |    Spring Boot    |       |    Spring Boot    |
     +-------------------+       +-------------------+       +-------------------+

     (The load balancer routes requests to healthy, eligible targets according to its configuration.)
```

### Important ALB components

- **Listener:** Checks incoming connections on a configured protocol and port, such as HTTPS on port `443`.
- **Listener rule:** Determines what action to take. A rule might route `/api/orders/*` to an orders target group.
- **Target group:** Defines the destination targets and health-check configuration.
- **Target:** The actual backend receiving requests, such as an EC2 instance on port `8080`.
- **Health check:** A configured probe used to determine whether a target is healthy enough to receive traffic.

### Example routing

Imagine one domain hosts two backend services:

```text
api.example.com/orders/*   -> Orders target group
api.example.com/payments/* -> Payments target group
```

The ALB can use host-based or path-based routing to direct traffic to the appropriate target group.

This does not mean the ALB understands your business logic. Your application still validates requests, authenticates users, enforces authorization, and executes the business operation.

### ALB versus Network Load Balancer

| Feature | Application Load Balancer (ALB) | Network Load Balancer (NLB) |
|---|---|---|
| **Primary layer** | Layer 7 (Application) | Layer 4 (Transport) |
| **Traffic model** | HTTP/HTTPS and gRPC aware | TCP, TLS, UDP and supported transport protocols |
| **Routing** | Host, path, HTTP header, and query string rules | Transport-level connection distribution (IP/Port) |
| **Static IP** | Assigned DNS name (IP addresses change dynamically) | Static Elastic IP per Availability Zone |
| **Common use** | Web applications, REST APIs, microservices | Ultra-low latency, gaming, streaming, static IP whitelisting |

Choose according to the protocol and routing behavior you need, not because one product is universally better.

---

## 6. Auto Scaling Groups: Replacing Manual Server Management

Without automation, an operator might manually launch another EC2 instance whenever traffic increases.

That does not scale well.

An **Auto Scaling Group (ASG)** manages a group of EC2 instances according to configured capacity limits, health checks, and scaling policies.

Three values define its basic capacity boundaries:

- **Minimum capacity:** The lowest capacity the group should maintain.
- **Desired capacity:** The target number of instances the group should maintain.
- **Maximum capacity:** The upper limit it can scale to under the configured policy.

Example:

```text
Minimum: 2
Desired: 2
Maximum: 8
```

If the group has two healthy instances and traffic increases, a scaling policy may increase desired capacity to four. The ASG launches additional instances, subject to configuration, quotas, capacity availability, and other constraints.

If an instance becomes unhealthy, the group can replace it according to its health-check and replacement behavior.

### What enables repeatable instance creation?

A **launch template** defines the configuration used to launch instances, including items such as:

- AMI ID.
- Instance type.
- Instance profile (IAM role).
- Security groups.
- Storage configuration (EBS root and data volumes).
- User data (startup scripts).
- Key-pair settings, where used.

The ASG uses the launch template to create instances consistently.

### Why multi-AZ placement matters

If all application instances are concentrated in one Availability Zone, a disruption in that zone can affect the entire application tier.

A resilient design distributes instances across multiple Availability Zones within the same AWS Region. Actual availability depends on subnet selection, capacity, health checks, load-balancer configuration, and the behavior of dependent services.

Multi-AZ is not the same as multi-region. A multi-region design introduces additional DNS or traffic-routing, data replication, failover, and consistency decisions.

---

## 7. Scaling Vertically versus Horizontally

When traffic grows or resource demands increase, systems can scale along two distinct dimensions:

### Vertical Scaling — Scale Up
Move to a larger instance with more CPU or memory.
- **Characteristics:** Easy to apply without re-architecting software; useful when a single process requires large RAM or compute capacity.
- **Trade-offs:** Hard upper limits on maximum hardware size; requires instance replacement or downtime to resize; does not provide high availability or fault tolerance.

### Horizontal Scaling — Scale Out
Add more instances and distribute requests across them.
- **Characteristics:** Elastic capacity that grows and shrinks dynamically; allows replacing failed nodes with zero downtime; supports multi-AZ fault tolerance.
- **Trade-offs:** Requires an application design that tolerates multiple concurrent instances; state must be externalized; increases network and database connection management complexity.

| Dimension | Vertical Scaling (Scale Up) | Horizontal Scaling (Scale Out) |
|---|---|---|
| **Mechanism** | Resize machine to larger instance type | Add more machines to the target group / ASG |
| **Fault Tolerance** | Single point of failure remains | Redundant nodes across multiple AZs |
| **State Handling** | Monolithic state survives on single machine | Requires stateless design or external shared store |
| **Upper Limit** | Largest available cloud instance type | Virtually unlimited elasticity (within quotas) |
| **Cost Profile** | Exponential cost curve at high instance tiers | Linear pay-as-you-go cost matching demand |

Horizontal scaling is not automatic application-level scalability. Your backend must be designed to handle requests arriving at any healthy instance.

For example, if a user's session exists only in the memory of EC2 A, a subsequent request routed to EC2 B may not find that session.

Better options include stateless authentication (such as JWTs), externalized session storage (such as Redis) where needed, or another deliberate session-management design.

---

## 8. User Data and Instance Initialization

EC2 **user data** allows you to provide startup instructions when launching an instance. On common Linux configurations, it is processed through `cloud-init` or related initialization mechanisms.

A simplified educational example:

```bash
#!/bin/bash
set -euxo pipefail

dnf install -y java-21-amazon-corretto-headless

install -d -o ec2-user -g ec2-user /opt/orders-api
```

This example installs Java and prepares a directory on a compatible Amazon Linux image. It does **not** download, configure, or start your application.

A production bootstrap process may also:

1. Install or verify the runtime.
2. Retrieve a versioned application artifact from an authorized location (such as private S3).
3. Obtain runtime configuration from a secure source (such as AWS Systems Manager Parameter Store or Secrets Manager).
4. Install a system service (`systemd`) or configure a deployment agent.
5. Start the application and verify readiness.
6. Send logs and metrics to a central monitoring system (such as CloudWatch).

> [!CAUTION]
> Do not put passwords, access keys, database credentials, or other secrets directly in user data. Instance initialization logs and metadata handling can expose information to unintended readers if permissions and access are poorly designed.

User data is also not a substitute for a repeatable image-building or deployment pipeline. Repeatedly performing complex installations at boot can increase startup time and create inconsistent results.

---

## 9. Instance Metadata and IMDSv2

The EC2 **Instance Metadata Service (IMDS)** provides information about an instance from inside its environment (`http://169.254.169.254/`). Depending on configuration and permissions, this can include instance identity information, network configuration, and temporary role credentials.

**IMDSv2** uses a token-based request flow (session-oriented PUT request to acquire a token header) that helps protect metadata access against SSRF (Server-Side Request Forgery) attacks and unintended requests.

Production basics:

- **Require IMDSv2:** Disable IMDSv1 by configuring `HttpTokens=required` in launch templates.
- **Limit metadata hop count:** Set `HttpPutResponseHopLimit=1` to prevent containers or forwarded proxies from accessing instance credentials.
- **Avoid SSRF vulnerabilities:** Avoid exposing server-side request functionality that can be abused to reach metadata.
- **Narrowly scoped instance roles:** Follow least privilege for attached IAM roles.
- **Never treat a private IP address as a security boundary by itself.**

The application should retrieve AWS credentials through the supported AWS SDK credential provider chain rather than hardcoding credentials in source code.

---

# Layer 2 — Practical Engineering & Workflows

## 10. Design a Basic Spring Boot Deployment

Suppose we are deploying an `Orders API` built with Java 21 and Spring Boot.

Its purpose is to accept HTTP requests and persist orders in PostgreSQL.

A simple learning architecture:

```text
Internet
   |
   v
Application Load Balancer
   |
   v
Target group :8080
   |
   +------> EC2 instance A: Spring Boot
   |
   +------> EC2 instance B: Spring Boot
                 |
                 v
          PostgreSQL database
          in private networking
```

For a production design, the database would typically be managed or operated as a separate stateful tier (such as Amazon RDS), with appropriate private connectivity, credentials, backup strategy, and high availability.

The application instances should not depend on a particular instance's local disk or memory for durable business data.

### Recommended application properties

```properties
server.port=8080

management.endpoints.web.exposure.include=health,info
management.endpoint.health.probes.enabled=true
```

This enables the configured management endpoints, including health and probe support. In a real application, verify the relevant Spring Boot Actuator dependency and version, and ensure management endpoints are not publicly exposed without appropriate controls.

A health endpoint can support load-balancer health checks, but it must be designed carefully:

- **Liveness** asks whether the process should be restarted.
- **Readiness** asks whether the instance is ready to serve traffic.

Do not automatically make every external dependency a liveness condition. If the database is briefly unavailable and every application instance reports itself as dead, the resulting restart loop may worsen the incident.

---

## 11. Configure the Load-Balancer Request Path

Before provisioning resources, understand the required network flow:

| Source | Destination | Port | Purpose |
|---|---|---:|---|
| **Internet clients** | ALB | 443 | Public HTTPS traffic |
| **ALB security group** | EC2 security group | 8080 | Application requests |
| **EC2 security group** | Database security group | 5432 | Application data access |

The critical rule is that the EC2 security group should generally allow inbound application traffic from the **ALB security group**, rather than allowing the entire internet to connect directly to port `8080`.

For PostgreSQL, the application tier should be authorized to connect to the database tier. The database should not be publicly exposed merely because the API is public.

These are conceptual rules. You must also configure appropriate subnets, route tables, listeners, target groups, health checks, and database connectivity.

---

## 12. Understand the Health-Check Path

Assume the ALB checks:

```text
Protocol: HTTP
Port: traffic port (8080)
Path: /actuator/health/readiness
```

The request path is:

```text
ALB health checker
      |
      v
EC2 target:8080
      |
      v
Spring Boot readiness endpoint
      |
      v
HTTP response (200 OK)
```

The target must return a response accepted by the configured success-code matcher (typically HTTP `200`).

Common problems include:

- The application listens on a different port than the target group expects.
- The health-check path is incorrect or misspelled.
- The application takes too long to start (longer than the health-check interval $\times$ threshold).
- The EC2 security group blocks ALB traffic.
- The endpoint requires authentication when the health checker cannot provide it.
- The process starts but cannot initialize its essential dependencies.

A successful TCP connection alone does not prove that the application can serve useful requests.

---

## 13. Use AWS CLI to Inspect Compute Resources

The following commands are read-only inspection commands. They assume the AWS CLI is installed, configured for an appropriate account, and operating in the intended Region.

### Verify identity and Region

```bash
aws sts get-caller-identity
aws configure list
```

These commands help verify which AWS identity and CLI configuration are active.

### List EC2 instances

```bash
aws ec2 describe-instances \
  --query 'Reservations[].Instances[].{
    ID:InstanceId,
    State:State.Name,
    Type:InstanceType,
    AZ:Placement.AvailabilityZone,
    PrivateIP:PrivateIpAddress
  }' \
  --output table
```

This returns a compact view of instances visible to your permissions in the configured Region.

### Inspect target groups

```bash
aws elbv2 describe-target-groups \
  --query 'TargetGroups[].{
    Name:TargetGroupName,
    Port:Port,
    Protocol:Protocol,
    VPC:VpcId
  }' \
  --output table
```

### Inspect registered target health

```bash
aws elbv2 describe-target-health \
  --target-group-arn YOUR_TARGET_GROUP_ARN
```

Replace the placeholder with the actual target-group ARN. This command is particularly useful when a target is unhealthy or a deployment does not appear to receive traffic.

### Inspect Auto Scaling Groups

```bash
aws autoscaling describe-auto-scaling-groups \
  --query 'AutoScalingGroups[].{
    Name:AutoScalingGroupName,
    Desired:DesiredCapacity,
    Min:MinSize,
    Max:MaxSize,
    Instances:Instances[].InstanceId
  }' \
  --output json
```

### Inspect scaling activities

```bash
aws autoscaling describe-scaling-activities \
  --auto-scaling-group-name YOUR_ASG_NAME \
  --max-items 20
```

Scaling activity messages can explain why an instance was launched, terminated, or not launched successfully.

> [!NOTE]
> Inspection commands do not guarantee that the caller has sufficient permission to view every resource. Avoid copying state-changing examples from tutorials into a real account without reviewing their impact.

---

## 14. Build a Deployment Workflow

A reliable deployment should be repeatable and observable.

One possible workflow:

1. **Build and test** the Spring Boot application in CI.
2. **Package** a versioned JAR or container image.
3. **Publish** the artifact to an approved artifact repository (e.g., private S3 or Amazon ECR).
4. **Create or update** a launch template referencing the intended application version or image.
5. **Deploy** through a controlled rollout or instance refresh strategy.
6. **Wait** for new instances to become healthy in the target group.
7. **Verify** application-level health and business behavior.
8. **Monitor** latency, errors, saturation, and database pressure.
9. **Roll back** if defined safety conditions are violated.

A key operational principle: **an instance being `running` does not mean the application is healthy**.

The EC2 state, operating-system health, application readiness, target-group health, and end-to-end business success are different signals.

---

## 15. Graceful Shutdown and Draining

Imagine that an ASG needs to replace an EC2 instance during a deployment.

If the instance is terminated immediately while it is processing requests, users may receive errors or clients may retry operations that already partially completed.

A safer shutdown sequence is:

```text
1. Deregister target -> ALB marks target as "draining" (stops routing new requests)
2. Connection draining delay -> In-flight requests complete cleanly within timeout
3. Termination lifecycle hook -> Application process receives SIGTERM
4. Spring Boot graceful shutdown -> Active HTTP handlers finish, connection pools close
5. Instance termination -> Operating system halts and EC2 instance terminates
```

Exact behavior depends on the deployment mechanism, load-balancer deregistration settings, instance lifecycle hooks, and application shutdown configuration.

For a Spring Boot service, configure graceful shutdown and appropriate request timeouts:

```properties
server.shutdown=graceful
spring.lifecycle.timeout-per-shutdown-phase=30s
```

Make sure long-running operations have explicit cancellation or completion semantics.

---

## 16. Autoscaling Policy Design

There is no universally correct scaling metric.

| Metric | What it can tell you | Important limitation |
|---|---|---|
| **Average CPU utilization** | Compute pressure | A database-bound API may be slow with low CPU |
| **Request count per target** | Traffic volume per registered target | Request complexity can vary substantially |
| **Memory utilization** | Memory pressure, if correctly collected | Requires suitable CloudWatch agent telemetry |
| **Queue depth** | Backlog of asynchronous work | Scale-out delay and per-message processing time matter |
| **Latency or saturation signals** | User-visible pressure | Needs careful measurement and scaling-policy design |

Consider an API that receives ten times its normal traffic. CPU-based scaling may help if requests are CPU-intensive, but may be ineffective if requests are waiting for PostgreSQL connections.

Before increasing the instance count, check whether the bottleneck is:

- Application CPU.
- Heap or native memory.
- Connection-pool exhaustion.
- Database CPU or I/O.
- Network throughput.
- A hot key or lock.
- An external dependency's rate limit.

> [!WARNING]
> Adding application instances can actually increase database load by creating more concurrent connections.

---

## 17. A Safe Hands-On Lab

This lab is designed to be completed without creating billable AWS resources. You can inspect existing resources if you already have authorized access, or draw and reason about the architecture locally.

### Task A: Draw the architecture
Draw the path from client to ALB, from ALB to two EC2 targets, and from the application tier to a private PostgreSQL database. Mark each security-group relationship and port.

### Task B: Define the launch template
Write down the following intended values:
- A supported Linux AMI (e.g., Amazon Linux 2023).
- A suitable instance type (e.g., `t4g.small` or `m7g.large`).
- An instance role with minimum required permissions.
- A security group that permits app traffic only from the ALB.
- Storage appropriate for the workload.
- A repeatable startup or deployment mechanism.

Do not launch the instance merely to complete the exercise.

### Task C: Design target health checks
Specify a readiness endpoint and explain:
- What constitutes a healthy response?
- How long should startup be allowed to take?
- What happens if the database is temporarily unavailable?
- How will you distinguish a failed application from a failed health-check configuration?

### Task D: Plan scaling
Assume the group has minimum capacity 2, desired capacity 2, and maximum capacity 8. Write down what should happen when:
1. One instance fails its health checks.
2. CPU rises steadily.
3. Request traffic spikes for two minutes.
4. PostgreSQL becomes saturated.
5. The selected instance type is temporarily unavailable in one AZ.

For each situation, identify the signal you would inspect before changing capacity.

---

# Layer 3 — Production Engineering & Interview Mastery

## 18. Production Incident Simulations

### Incident A: The ALB returns HTTP 502

**Symptoms:** Clients receive 502 responses, although EC2 instances appear to be running.

Investigate in this order:

1. Inspect ALB access logs or metrics where available (`HTTPCode_ELB_502_Count`).
2. Check target-group health and the exact health-check reason.
3. Confirm that Spring Boot is listening on the expected port (`ss -lntp`).
4. Check whether the application process has crashed or is restarting.
5. Verify ALB-to-instance security-group rules (ALB egress and EC2 ingress).
6. Review application logs, startup errors, and connection behavior.
7. Check whether the application closes connections unexpectedly or returns malformed upstream responses.

A 502 generally indicates a problem with the upstream response or connection path, but the precise cause depends on the architecture and protocol.

Do not conclude that the instance is healthy simply because EC2 reports it as `running`.

---

### Incident B: The ALB returns HTTP 503

**Symptoms:** Requests receive 503 responses during deployment.

Possible causes include:

- No healthy registered targets in the target group.
- All targets temporarily unavailable.
- Incorrect listener or target-group configuration.
- A deployment that removed old targets before new targets became healthy.
- An application startup failure affecting every target.

Check target health, listener rules, deployment events, and application readiness. Restore healthy capacity and roll back if required by your incident procedure.

---

### Incident C: Auto Scaling does not add instances

**Symptoms:** CPU is high, but the group remains at two instances.

Investigate:

1. Is the scaling policy enabled and receiving its metric?
2. Is desired capacity already at the maximum?
3. Are account or service quotas being reached (vCPU limits)?
4. Is the launch template valid?
5. Can the selected instance type be launched in the configured subnets and Availability Zones?
6. Are subnet IP addresses available?
7. Does the instance have required launch permissions and configuration?
8. Are cooldowns, warm-up periods, or policy evaluation delays affecting the response?

Inspect ASG scaling activities (`aws autoscaling describe-scaling-activities`) instead of guessing.

---

### Incident D: New instances launch but never become healthy

Likely causes:

- The wrong AMI was selected.
- User data failed during execution.
- The JAR or application artifact could not be downloaded (e.g., S3 permission error).
- The instance role lacks required permissions.
- The application is bound to localhost (`127.0.0.1`) rather than `0.0.0.0`.
- The security group blocks the health checker.
- The configured readiness endpoint returns an unexpected status (e.g., 503 due to uninitialized datasource).
- Startup takes longer than the configured health-check expectations.

**Engineering lesson:** Launch success and application readiness are separate milestones.

---

### Incident E: Scaling out makes the database slower

Suppose each application instance creates a connection pool of up to 40 database connections.

At two instances, the application tier can potentially request 80 connections. At eight instances, that upper bound becomes 320.

This is a simplified upper-bound calculation; actual open connections depend on pool configuration and runtime behavior.

If PostgreSQL cannot handle the additional concurrency, scaling the application tier may increase database latency and connection contention.

Possible responses:

- Establish a safe total connection budget.
- Tune pool size and acquisition timeouts.
- Improve query efficiency and transaction duration.
- Apply admission control or backpressure.
- Introduce connection pooling middleware (such as AWS RDS Proxy).
- Scale or optimize the database tier when evidence supports it.
- Avoid retry storms that amplify overload.

Horizontal scaling moves bottlenecks; it does not eliminate them.

---

### Incident F: Deployment creates a traffic outage

A new launch-template version is deployed, but the new instances fail their health checks.

A robust deployment should limit blast radius:

- Maintain sufficient healthy capacity during rollout (e.g., minimum healthy percentage = 100%).
- Wait for readiness before sending production traffic.
- Monitor error rate and latency during the rollout.
- Stop or reverse the rollout when safety conditions fail.
- Keep a known-good version available.
- Verify the rollback actually restores healthy service.

The best rollback plan is one you have tested.

---

## 19. Security and Reliability Checklist

Before considering an EC2-based backend production-ready, verify the following.

### Identity and access
- [ ] Use an instance role rather than embedded long-lived credentials.
- [ ] Grant only required AWS permissions (least privilege).
- [ ] Protect metadata access and require IMDSv2 where appropriate.
- [ ] Keep secrets in an appropriate secrets-management service.
- [ ] Restrict administrative access (use AWS Systems Manager Session Manager instead of open SSH ports) and audit it.

### Network boundaries
- [ ] Place application instances in private subnets.
- [ ] Expose the ALB in public subnets rather than exposing application instances directly.
- [ ] Permit inbound application traffic only from the ALB security group.
- [ ] Keep the database private in dedicated database subnets.
- [ ] Restrict outbound traffic where practical (using NAT Gateways or VPC Endpoints).
- [ ] Separate administrative access from public application traffic.

### Availability
- [ ] Use multiple Availability Zones when the availability requirement justifies it.
- [ ] Maintain sufficient minimum capacity across AZs.
- [ ] Configure target health checks appropriately.
- [ ] Ensure instances can be replaced safely (stateless application design).
- [ ] Design the application to tolerate instance replacement.
- [ ] Verify database failover and recovery separately.

### Observability
Monitor at least:
- [ ] Request count and HTTP error rates (4xx, 5xx).
- [ ] Latency percentiles, such as p95 and p99.
- [ ] CPU and memory pressure.
- [ ] Healthy and unhealthy target counts.
- [ ] Desired versus actual ASG capacity.
- [ ] Instance launch and termination failures.
- [ ] Database connections and query latency.
- [ ] Application startup and readiness failures.

### Cost
- [ ] Select instance types based on measured workload needs.
- [ ] Review utilization and idle capacity.
- [ ] Understand the billing implications of load balancers, storage, data transfer, and other associated services.
- [ ] Use scaling bounds to prevent uncontrolled capacity growth.
- [ ] Test cost-impacting changes before applying them.

---

## 20. FAANG-Style Interview Questions and Answers

### Q1. What is Amazon EC2?
EC2 is an AWS service that provides configurable virtual machines for running workloads. Users choose the operating system image, instance type, storage, networking, and associated permissions.

### Q2. What is the difference between an AMI and an instance?
An AMI is a machine image used to launch instances. An instance is the running virtual machine created from that image and its launch configuration.

### Q3. What is the difference between an instance type and an AMI?
An AMI defines the machine image and software baseline. An instance type defines the compute resource profile, including CPU, memory, and networking characteristics.

### Q4. What is EBS?
Elastic Block Store provides persistent network-attached block storage volumes that can be mounted to supported EC2 instances. Data durability and deletion behavior depend on the volume and instance configuration.

### Q5. What does an Application Load Balancer do?
An ALB distributes HTTP/HTTPS requests across registered targets and supports Layer 7 routing based on configured rules (paths, hosts, headers).

### Q6. What is a target group?
A target group defines a set of destinations, their traffic configuration, and associated health checks. An ALB listener routes requests to target groups based on listener rules.

### Q7. What is the difference between an ALB and an NLB?
An ALB focuses on HTTP-level routing at Layer 7. An NLB distributes traffic at the transport/network level (Layer 4) for high throughput, low latency, and static IP requirements.

### Q8. What is an Auto Scaling Group?
An ASG maintains a group of EC2 instances within configured capacity limits and can automatically launch or replace instances based on health checks and scaling policies.

### Q9. What are minimum, desired, and maximum capacity?
Minimum is the lower capacity boundary, desired is the target instance count the group currently maintains, and maximum is the upper boundary for scaling out.

### Q10. Why use a launch template?
It standardizes instance creation by defining the AMI, instance type, security groups, storage, instance profile, user data, and other launch settings in a versioned template.

### Q11. What is the difference between vertical and horizontal scaling?
Vertical scaling increases the capacity of an individual machine (larger instance type). Horizontal scaling adds more machines and distributes work among them.

### Q12. Why should application instances be stateless?
Stateless instances are easier to replace and scale because requests do not depend on local in-memory session state or durable local files. Shared or durable state belongs in suitable external systems like Redis or databases.

### Q13. What does a target health check tell you?
It indicates whether a target satisfies the configured health-check criteria (e.g., returning HTTP 200 on `/actuator/health/readiness`). It does not prove every business operation or downstream dependency is functioning correctly.

### Q14. Why can an EC2 instance be running but the API be unavailable?
The operating system may be running while the application is crashed, starting, listening on the wrong port, blocked by network rules, or unable to serve requests.

### Q15. How would you debug an ALB 502?
Check target health, application logs, listening ports, security-group rules, startup status, and the upstream connection path. Use ALB access logs and metrics where available to narrow the failure.

### Q16. Why might an ALB return 503?
The load balancer may have no healthy eligible targets or may be unable to route requests under the configured conditions. Inspect target health, listener configuration, and deployment events.

### Q17. Why might Auto Scaling fail to launch an instance?
Potential causes include reaching maximum capacity, invalid launch configuration, unavailable capacity in the AZ, exhausted subnet IPs, quotas, permissions, or service constraints.

### Q18. Why can adding EC2 instances make an application slower?
More instances can increase database connections, downstream traffic, lock contention, and request concurrency. If a shared dependency is saturated, scaling out the application tier may worsen the bottleneck.

### Q19. What is the purpose of graceful shutdown?
It reduces interrupted requests and inconsistent behavior by allowing traffic draining, in-flight work completion, and orderly resource cleanup before termination.

### Q20. Why is multi-AZ deployment not the same as multi-region deployment?
Multi-AZ distributes resources across Availability Zones within a single Region. Multi-region uses separate Regions and requires additional decisions about traffic failover, data replication, consistency, and disaster recovery.

---

## 21. Mastery Challenge

You are designing a production Orders API with these requirements:

- Two or more application instances during normal operation.
- HTTPS for public requests.
- No direct public access to the application instances.
- Automatic replacement of unhealthy instances.
- Scale-out when traffic rises.
- A private PostgreSQL database.
- Safe deployments and a rollback path.

Complete the following tasks before moving to Chunk 4:

1. Draw the request path from client to database.
2. Identify the roles of the ALB, target group, launch template, and ASG.
3. Define the security-group relationships.
4. Choose a readiness endpoint and explain its behavior.
5. Explain how a failed instance is replaced.
6. Explain how the design behaves when database capacity is exhausted.
7. List five metrics you would watch during deployment.
8. Describe how you would investigate an ALB 502.
9. Explain how you would prevent a faulty rollout from removing all healthy capacity.
10. Identify which parts of the design create costs even when traffic is low.

### Self-assessment

Rate each skill from 0 to 2:
- **0:** Cannot explain it yet.
- **1:** Can explain it but need help applying it.
- **2:** Can explain it and solve a practical scenario.

| Skill | Score |
|---|---:|
| EC2, AMIs, instance types, and EBS | /2 |
| ALB, listeners, and target groups | /2 |
| ASG capacity and scaling | /2 |
| Health checks and readiness | /2 |
| Network and identity security | /2 |
| Incident diagnosis | /2 |
| Deployment and rollback | /2 |
| Cost and bottleneck reasoning | /2 |

**Target:** At least 13/16, with no zero in health checks, security, or incident diagnosis. Review weak areas before advancing.

---

## Chapter Completion Protocol

**Chapter:** AWS Chunk 3 of 6

**Save as:** `content/aws/03-aws-ec2-load-balancing-auto-scaling-compute-architecture.md`

**Do not generate a PDF yet.** Save all six AWS chapters first, verify the complete source content, then generate one final AWS handbook:

`docs/aws/BEH_AWS_COMPLETE_HANDBOOK.pdf`

After the source chapters and final PDF have been verified, the intended Git commit message is:

`AWS done`

This chapter completes the core compute foundation. The next AWS chapter will cover **storage and managed databases**, including S3, EBS/EFS, RDS, backups, and high availability.
