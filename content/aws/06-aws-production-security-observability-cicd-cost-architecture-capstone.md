# AWS — Chunk 6 of 6: Production Security, Observability, CI/CD, Reliability, Cost Engineering & Final Architecture Capstone

## Backend Engineering Tools & Infrastructure Handbook · Cloud Engineering Track

**Difficulty:** Beginner-friendly foundations → production engineering → FAANG-level interview mastery  
**Prerequisites:** AWS Chunks 1–5, basic Java/Spring Boot, HTTP, PostgreSQL, Docker, Git  
**Source file:** `content/aws/06-aws-production-security-observability-cicd-cost-architecture-capstone.md`

---

# Learning Objectives

By the end of this chapter, you should be able to:

- Secure AWS workloads using IAM roles, least privilege, encryption, and managed secrets.
- Explain the responsibilities of AWS CloudTrail, CloudWatch, and AWS X-Ray.
- Design a CI/CD pipeline that builds, tests, scans, and deploys a backend application.
- Deploy safely, detect regressions, and roll back failed releases.
- Design for availability, recoverability, and measurable service objectives (SLIs, SLOs, SLAs).
- Understand AWS cost drivers and prevent accidental spending.
- Diagnose common security, performance, queueing, and availability incidents.
- Explain a complete production-minded AWS architecture in an SDE-1 or backend interview.

---

# Layer 1 — Fundamentals & Mental Models

## 1. Production Engineering: The Real Objective

Running an application in the cloud is not the same as operating it reliably.

A production system must answer five fundamental questions:

1. **Security:** Who can access this resource, and what can they do?
2. **Reliability:** What happens when a component fails?
3. **Observability:** How do we discover, trace, and diagnose problems?
4. **Delivery:** How can we release changes continuously without unnecessary risk?
5. **Cost:** Are we paying for resources that deliver genuine business value?

Imagine an Orders API built with Spring Boot. It accepts an order, writes it to PostgreSQL, stores an invoice in S3, and publishes an event to SQS.

The API might work perfectly in a local Docker container. Production introduces completely different questions:

- What if an attacker obtains an AWS credential?
- What if PostgreSQL becomes temporarily unavailable or exhausts its connection pool?
- What if SQS accumulates a million unprocessed messages?
- What if a deployment introduces a 10% error rate on checkout?
- What if an autoscaling policy creates too many instances and saturates the database?
- What if nobody notices the errors until angry customers post on social media?

Production engineering is the discipline of anticipating, detecting, and recovering from these failures.

---

## 2. AWS Security: Identity First

AWS security is built around identities, permissions, resource policies, network boundaries, and encryption.

### 2.1 IAM Users, Roles, and Policies

An **IAM policy** defines allowed or denied actions on AWS resources.

An **IAM role** is an identity that a trusted principal can assume to obtain temporary, automatically rotating credentials.

A workload should normally use a role rather than a long-lived access key stored in application configuration:
- A Spring Boot service running on EC2 obtains permissions through its attached **instance profile**.
- A service running as an ECS task uses its **Task Role** to access application resources (S3, SQS, Secrets Manager).
- A Lambda function uses its **Execution Role**.

The application does not need to know the underlying secret access key. The AWS SDK obtains temporary credentials automatically through the default credential provider chain.

### 2.2 Least Privilege

Least privilege means granting only the permissions strictly necessary for a task.

Suppose an order service must write invoice files to one S3 bucket. It does not need unrestricted access to every S3 bucket in the AWS account.

A simplified illustrative identity policy looks like this:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::example-invoice-bucket/invoices/*"
    }
  ]
}
```

This example allows object uploads strictly to the specified bucket and key prefix.

> [!IMPORTANT]
> **Authorization Precedence:** An IAM allow statement does not automatically guarantee access. Explicit denies, permissions boundaries, Service Control Policies (SCPs), resource policies, and session policies all take precedence. Any explicit `Deny` unconditionally blocks access.

### 2.3 Temporary Credentials versus Static Credentials

**Always Prefer:**
- IAM roles for EC2 workloads via instance profiles.
- ECS task roles for container application code.
- Lambda execution roles for serverless functions.
- Federated, short-lived OIDC credentials for CI/CD (GitHub Actions $\to$ AWS via OIDC).
- AWS IAM Identity Center (formerly AWS SSO) for human engineers.

**Strictly Avoid:**
- Hardcoding access keys (`AKIA...`) in Java or configuration source code.
- Committing AWS credentials to Git repositories.
- Permanent administrator keys for deployment pipelines.
- Passing credentials through Docker build arguments, which bakes them into image layers.

If a credential leaks, simply removing it from the latest Git commit is useless (it remains in Git history). Treat it as compromised: deactivate it immediately, audit CloudTrail for unauthorized API calls, and rotate affected credentials.

---

## 3. Encryption and Key Management

Encryption protects data in two major states:

| State | Concrete Example | Common AWS Capability |
|---|---|---|
| **At Rest** | PostgreSQL storage, S3 objects, EBS volumes | AWS KMS (SSE-S3, SSE-KMS, EBS Encryption) |
| **In Transit** | REST API calls, database connections | TLS 1.3, ACM (AWS Certificate Manager) |

**AWS Key Management Service (KMS)** manages cryptographic keys and controls their use through permissions and policies:
- **AWS Managed Keys:** Managed automatically by AWS (e.g., `aws/s3`, `aws/rds`). Free to use, but key policies cannot be modified.
- **Customer Managed Keys (CMKs):** Created and controlled by your organization. Allows fine-grained key policies, cross-account sharing, and automatic annual rotation.

Encryption is not a substitute for authorization. An encrypted S3 object can still be read if an overly permissive IAM policy grants both `s3:GetObject` and `kms:Decrypt` to an unauthorized principal.

---

## 4. Secrets Manager versus Systems Manager Parameter Store

Applications need database passwords, API tokens, and other sensitive configuration:

### AWS Secrets Manager
- Specifically designed for confidential credentials (passwords, OAuth tokens).
- Built-in automatic rotation integrations for Amazon RDS, Aurora, and DocumentDB.
- Generates random credentials and updates database and application secrets simultaneously.
- Cost: ~$0.40 per secret per month + API request costs.

### AWS Systems Manager Parameter Store
- Stores hierarchical configuration parameters (`/orders-api/prod/db-url`).
- Supports plain text (`String`, `StringList`) and encrypted values (`SecureString` backed by KMS).
- Cost: Standard parameters are free; Advanced parameters incur small costs.

| Dimension | AWS Secrets Manager | SSM Parameter Store |
|---|---|---|
| **Primary Use** | Database passwords, API keys, credentials | App configuration, flags, license keys |
| **Automatic Rotation** | Native built-in Lambda rotation | Manual or custom Lambda rotation |
| **Cross-Account Access**| Native resource policies on secrets | More complex cross-account setup |
| **Pricing** | $0.40 / secret / month | Free (Standard tier) |

Neither service eliminates the need for least privilege. A workload should be allowed to retrieve only the specific secrets it requires.

---

## 5. Observability: Metrics, Logs, and Traces

Observability is the ability to understand the internal health and behavior of a system from the external signals it produces:

### 1. Metrics — What is happening?
Numerical measurements aggregated over time intervals: request rate, 5xx error rate, p95/p99 latency, CPU utilization, heap memory usage, active database connections, and SQS queue depth.

### 2. Logs — What happened?
Structured event records detailing specific occurrences: an order failed schema validation, a database connection acquisition timed out, or a deployment initiated.

### 3. Traces — Where did the request spend its time?
A distributed request timeline following a transaction across microservices, database queries, SQS queues, and external third-party HTTP calls.

```text
Request Timeline (Total: 2,050 ms)
+-------------------------------------------------------------+
| ALB Routing (20 ms)                                         |
+--+----------------------------------------------------------+
   | Spring Boot Handler (30 ms)                              |
   +----+-----------------------------------------------------+
        | PostgreSQL: INSERT INTO orders (1,850 ms) <-- BOTTLENECK!
        +----+------------------------------------------------+
             | SQS: SendMessage (150 ms)                      |
             +------------------------------------------------+
```

### 5.1 Amazon CloudWatch
Central hub for operational monitoring:
- **CloudWatch Metrics:** Ingests infrastructure and custom application metrics (via Micrometer in Spring Boot).
- **CloudWatch Logs:** Collects structured application logs into Log Groups and Log Streams.
- **CloudWatch Alarms:** Triggers automated remediation or pager alerts when metrics cross thresholds.
- **CloudWatch Dashboards:** Real-time visual monitoring for engineering teams.

### 5.2 AWS CloudTrail
CloudTrail records **management and API activity** across your AWS account:
- Records *who* made *what* API call, *when*, from *which IP*, on *which resource*.
- Essential for security auditing, compliance, and investigating configuration drift.
- **Rule of thumb:** CloudWatch monitors application & system performance; CloudTrail audits AWS API interactions.

### 5.3 AWS X-Ray and OpenTelemetry
- **OpenTelemetry (OTel):** The vendor-neutral industry standard for instrumenting metrics, logs, and distributed traces.
- **AWS X-Ray:** Ingests distributed traces, generates service maps, and highlights latency bottlenecks across microservices.

---

## 6. CI/CD: From a Commit to Production

Continuous Integration and Continuous Delivery (CI/CD) automates the path from code check-in to verified production execution:

```text
Developer pushes commit to main
        |
        v
[CI Stage: Quality & Safety Checks]
  - Compile Java 21 bytecode
  - Execute JUnit 5 unit tests
  - Execute integration tests (Testcontainers)
  - Static code analysis & linting
  - Dependency vulnerability scan (Trivy / Snyk)
        |
        v
[Build & Package Stage]
  - Build immutable Docker image
  - Scan image layers for CVEs
  - Tag with Git commit SHA: orders-api:7f8a12c
  - Push image to Amazon ECR
        |
        v
[Deployment Stage: Staging]
  - Update ECS task definition or Helm release
  - Execute automated smoke tests
  - Verify database migrations (Flyway / Liquibase)
        |
        v
[Production Rollout: Controlled Deployment]
  - Rolling update or Canary deployment (10% -> 50% -> 100%)
  - Continuous health check evaluation
  - Automated rollback on alarm trigger
```

> [!TIP]
> Never deploy a mutable tag like `:latest` to production. Always use immutable identifiers such as the short Git commit SHA (`:7f8a12c`) to guarantee traceability and reproducible rollbacks.

---

## 7. Reliability: Design for Failure

A production-grade cloud backend assumes that every server, disk, network link, and dependency will eventually fail:

- **Redundancy:** Multi-AZ deployment across at least two Availability Zones.
- **Health Checks:** Separate liveness (is JVM hung?) from readiness (is DB pool initialized?).
- **Timeouts:** Enforce strict client and server timeouts on every network call.
- **Bounded Retries with Jitter:** Prevent retry storms by combining exponential backoff with full jitter:
  $$t = \text{random}(0, \min(M, B \times 2^{\text{attempt}}))$$
- **Circuit Breakers:** Cut off calls to struggling downstream services (using Resilience4j) to prevent cascading failures.
- **Bulkheads:** Isolate resource pools (separate thread pools for payment vs. recommendation APIs).
- **Graceful Shutdown:** Complete in-flight requests cleanly within a draining window before termination.

---

## 8. SLI, SLO, and SLA

Engineering teams use three distinct terms to define and measure service reliability:

- **SLI (Service Level Indicator):** A quantifiable metric measuring real-time performance.
  $$\text{SLI} = \frac{\text{Count of Successful Requests (HTTP status } < 500 \text{ and latency } < 500\text{ms})}{\text{Total Valid Requests}} \times 100$$
- **SLO (Service Level Objective):** The internal target reliability agreed upon by the engineering team (e.g., 99.9% successful requests over any rolling 30-day window).
- **SLA (Service Level Agreement):** The legal or commercial commitment to customers, which carries financial or contractual penalties if breached (e.g., 99.5% uptime).
- **Error Budget:** The allowed margin of unreliability:
  $$\text{Error Budget} = 100\% - \text{SLO} = 100\% - 99.9\% = 0.1\%$$
  Over 1,000,000 requests, the error budget allows at most 1,000 failed requests before halting non-critical releases.

---

## 9. Cost Engineering: Understand the Bill

AWS costs are driven by:

- **Compute:** Running EC2 instances, Fargate vCPU/RAM per second, Lambda invocation count and duration.
- **Storage:** S3 GB-months, EBS provisioned volume size and IOPS (`gp3`), EFS storage.
- **Networking & Data Transfer:** NAT Gateway data processing fees ($0.045/GB), cross-AZ traffic, egress to the internet.
- **Databases:** RDS instance hours, provisioned storage, Multi-AZ licensing, backup retention beyond free limits.
- **Observability:** CloudWatch log ingestion ($0.50/GB), custom metrics, and metric alarms.

Cost engineering means making spending visible through cost-allocation tags, configuring AWS Budgets, eliminating orphaned EBS volumes or idle NAT Gateways, and right-sizing workloads based on utilization telemetry.

---

# Layer 2 — Practical Engineering & Workflows

## 10. Workload Identity in Practice

### 10.1 Local Development
Use AWS CLI profiles or temporary SSO session tokens:

```bash
aws configure list
aws sts get-caller-identity
```

### 10.2 Production Workload
Configure the Spring Boot application to use the AWS SDK default credential provider chain:
- On EC2: Automatically retrieves credentials from the EC2 instance profile (`http://169.254.169.254/latest/meta-data/iam/security-credentials/`).
- On ECS: Automatically retrieves credentials from the ECS Task Role (`AWS_CONTAINER_CREDENTIALS_RELATIVE_URI`).
- On Lambda: Uses the Lambda execution role environment variables.

---

## 11. Retrieving Secrets Safely in Spring Boot

In `application.yml`, reference environment variables injected by the container runtime:

```yaml
spring:
  datasource:
    url: ${DB_URL}
    username: ${DB_USERNAME}
    password: ${DB_PASSWORD}
    hikari:
      maximum-pool-size: 15
      connection-timeout: 3000
```

On ECS Fargate, inject secrets directly from AWS Secrets Manager in the task definition:

```json
{
  "name": "DB_PASSWORD",
  "valueFrom": "arn:aws:secretsmanager:ap-south-1:123456789012:secret:prod/orders/db-xyz:password::"
}
```

The ECS agent securely resolves the secret at container launch and sets it as an environment variable without writing it to disk or committing it to source control.

---

## 12. CloudWatch: Inspect and Monitor a Workload

### 12.1 Inspect Log Groups via AWS CLI

```bash
aws logs describe-log-groups \
  --region ap-south-1
```

```bash
aws logs describe-log-streams \
  --log-group-name "/aws/ecs/orders-api-prod" \
  --order-by LastEventTime \
  --descending \
  --limit 5 \
  --region ap-south-1
```

### 12.2 Practical Golden Signals Monitoring Set

| Golden Signal | Metric Name | Recommended Alarm Threshold |
|---|---|---|
| **Latency** | `TargetResponseTime` (ALB) | p95 > 500 ms for 3 consecutive 1-minute evaluation periods |
| **Traffic** | `RequestCount` (ALB) | Anomaly detection: $\pm 3\sigma$ deviation from historical trend |
| **Errors** | `HTTPCode_Target_5XX_Count` | 5xx error rate > 1% of total requests over 5 minutes |
| **Saturation** | `CPUUtilization` (ECS / RDS) | Sustained CPU > 80% for 10 minutes |
| **Queue Backlog** | `ApproximateAgeOfOldestMessage` | Age > 300 seconds (5 minutes) |
| **Database Pool** | `DatabaseConnections` (RDS) | Active connections > 80% of `max_connections` |

### 12.3 Structured JSON Logging Example

```json
{
  "timestamp": "2026-10-23T10:30:00Z",
  "level": "ERROR",
  "service": "orders-api",
  "environment": "production",
  "traceId": "1-6718d8f0-1a2b3c4d5e6f7a8b9c0d1e2f",
  "requestId": "req-98234-a1b2",
  "event": "order_persistence_failed",
  "errorType": "DatabaseTimeoutException",
  "message": "Connection to PostgreSQL primary timed out after 3000ms"
}
```

---

## 13. CloudTrail: Investigate an Unauthorized Configuration Change

When a critical security group rule or IAM policy changes unexpectedly:

```bash
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=AuthorizeSecurityGroupIngress \
  --max-results 10 \
  --region ap-south-1
```

Examine the returned CloudTrail record:
- `userIdentity`: Identify the IAM user, assumed role, or access key used.
- `sourceIPAddress`: Check if the call originated from corporate VPN or an unknown IP.
- `requestParameters`: Determine exact ports and CIDRs opened (e.g., `0.0.0.0/0` on port 5432).
- `responseElements`: Verify whether the API call succeeded.

---

## 14. CI/CD Pipeline Implementation (GitHub Actions Example)

```yaml
name: Deploy Orders API to ECS Fargate

on:
  push:
    branches: [ main ]

permissions:
  id-token: write   # Required for AWS OIDC federation
  contents: read

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Source Code
        uses: actions/checkout@v4

      - name: Set up JDK 21
        uses: actions/setup-java@v4
        with:
          java-version: '21'
          distribution: 'corretto'

      - name: Build & Test with Gradle/Maven
        run: ./mvnw clean verify

      - name: Configure AWS Credentials via OIDC
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/github-actions-deploy-role
          aws-region: ap-south-1

      - name: Log in to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build, Tag, and Push Docker Image
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/orders-api:$IMAGE_TAG .
          docker push $ECR_REGISTRY/orders-api:$IMAGE_TAG

      - name: Deploy to ECS Fargate
        run: |
          aws ecs update-service \
            --cluster prod-cluster \
            --service orders-service \
            --force-new-deployment \
            --region ap-south-1
```

---

## 15. Infrastructure as Code: Terraform Hygiene

Maintain strict IaC discipline:

```bash
terraform fmt -check
terraform validate
terraform plan -out=tfplan.binary
```

Before applying:
- Review the plan output: verify zero unintended resource destructions.
- Enforce remote state locking using an S3 bucket with Amazon DynamoDB state locking.
- Maintain strict environment separation: isolate `prod` and `staging` state files in separate buckets and accounts.

---

## 16. Budgets, Billing Visibility, and Cleanup

- **AWS Budgets:** Configure automated alarms when forecasted monthly spending exceeds target budgets.
- **Cost Allocation Tags:** Tag all resources with `Environment` (`prod`/`staging`), `Service` (`orders-api`), and `Owner` (`backend-team`).
- **Clean Up Non-Production Resources:**
  - Terminate unused EC2 instances and idle NAT Gateways.
  - Delete unattached EBS volumes (`aws ec2 describe-volumes --filters Name=status,Values=available`).
  - Delete obsolete manual RDS snapshots.
  - Set S3 Lifecycle rules to expire temporary staging artifacts after 7 days.

---

## 17. Pre-Production Release Readiness Checklist

Before approving any backend service for production release, verify every item:

### Security
- [ ] Workload uses IAM roles (instance profile / task role) rather than static access keys.
- [ ] IAM permissions strictly adhere to least privilege (specific resource ARNs and actions).
- [ ] Secrets are retrieved dynamically via Secrets Manager / SSM; none are committed to Git.
- [ ] Security groups restrict traffic to known sources (no open 0.0.0.0/0 on databases or SSH).
- [ ] S3 buckets have Block Public Access enabled; data is encrypted at rest and in transit (TLS 1.3).

### Reliability
- [ ] Health checks correctly separate liveness probes from readiness probes.
- [ ] Network timeouts and bounded retries with jitter are configured on all dependencies.
- [ ] Multi-AZ redundancy is enabled for compute (ASG/ECS across 2+ AZs) and database (RDS Multi-AZ).
- [ ] Automated daily database backups and continuous point-in-time recovery (PITR) are active.
- [ ] Tested rollback and graceful shutdown procedures are documented in runbooks.

### Observability
- [ ] Logs are output in structured JSON format with distributed correlation IDs (`traceId`).
- [ ] Golden signals (Latency, Traffic, Errors, Saturation) are tracked in CloudWatch.
- [ ] CloudWatch alarms are configured with actionable thresholds and PagerDuty/SNS alerts.
- [ ] Application deployment version is recorded alongside metrics and logs.

### Delivery and Cost
- [ ] CI/CD pipeline enforces unit tests, integration tests, and container vulnerability scanning.
- [ ] Container images use immutable tags (Git commit SHA); `:latest` is prohibited.
- [ ] Infrastructure changes are reviewed via `terraform plan` before application.
- [ ] Cost allocation tags are applied to all resources; AWS Budget alerts are active.

---

# Layer 3 — Production Engineering & Interview Mastery

## 18. Production Architecture Capstone

Below is the comprehensive, end-to-end production architecture for the e-commerce Orders API, integrating all 6 chunks of the handbook:

```text
========================================================================================
                                 PUBLIC INTERNET
========================================================================================
                                        |
                          HTTPS (TLS 1.3 / Port 443)
                                        v
+--------------------------------------------------------------------------------------+
| AWS REGION (e.g., ap-south-1)                                                        |
|                                                                                      |
|  +--------------------------------------------------------------------------------+  |
|  | VPC (CIDR: 10.0.0.0/16)                                                        |  |
|  |                                                                                |  |
|  |  +--------------------------------------------------------------------------+  |  |
|  |  | PUBLIC SUBNETS (AZ-a: 10.0.1.0/24 | AZ-b: 10.0.2.0/24)                    |  |  |
|  |  |                                                                          |  |  |
|  |  |             +-----------------------------------------+                  |  |  |
|  |  |             |        Application Load Balancer        |                  |  |  |
|  |  |             | (HTTPS Listener · ACM TLS Cert · WAF)   |                  |  |  |
|  |  |             +--------------------+--------------------+                  |  |  |
|  |  |                                  |                                       |  |  |
|  |  |           +----------------------+----------------------+                |  |  |
|  |  |           | (Egress via NAT)                            | (Egress via NAT)|  |  |
|  |  |           v                                             v                |  |  |
|  |  |   [NAT Gateway AZ-a]                            [NAT Gateway AZ-b]       |  |  |
|  |  +-----------+---------------------------------------------+----------------+  |  |
|  |              |                                             |                   |  |
|  |  +-----------+---------------------------------------------+----------------+  |  |
|  |  | PRIVATE APPLICATION SUBNETS (AZ-a: 10.0.11.0/24 | AZ-b: 10.0.12.0/24)    |  |  |
|  |  |                                                                          |  |  |
|  |  |   +-------------------------------+   +-------------------------------+  |  |  |
|  |  |   | ECS Task: Orders API (AZ-a)   |   | ECS Task: Orders API (AZ-b)   |  |  |  |
|  |  |   | Spring Boot 3 · Java 21       |   | Spring Boot 3 · Java 21       |  |  |  |
|  |  |   | (Port 8080 · IAM Task Role)   |   | (Port 8080 · IAM Task Role)   |  |  |  |
|  |  |   +---------------+---------------+   +---------------+---------------+  |  |  |
|  |  +-------------------|-----------------------------------|------------------+  |  |
|  |                      |                                   |                     |  |
|  |  +-------------------|-----------------------------------|------------------+  |  |
|  |  | PRIVATE DATABASE SUBNETS (AZ-a: 10.0.21.0/24 | AZ-b: 10.0.22.0/24)       |  |  |
|  |  |                   |                                   |                     |  |
|  |  |                   +-----------------+-----------------+                     |  |
|  |  |                                     | TCP 5432                              |  |
|  |  |                                     v                                       |  |
|  |  |                 +---------------------------------------+                   |  |
|  |  |                 |    Amazon RDS PostgreSQL (Multi-AZ)   |                   |  |
|  |  |                 | Primary (AZ-a) <---sync---> Standby   |                   |  |
|  |  |                 | (orders table + outbox_events table)  |                   |  |
|  |  |                 +-------------------+-------------------+                   |  |
|  |  +-------------------------------------|------------------------------------+  |  |
|  +----------------------------------------|---------------------------------------+  |
|                                           |                                          |
|                          Transactional Outbox Publisher                              |
|                                           |                                          |
|                                           v                                          |
|                        +-------------------------------------+                       |
|                        |      Amazon EventBridge Event Bus   |                       |
|                        |        (Rule: "OrderPlaced")        |                       |
|                        +------------------+------------------+                       |
|                                           |                                          |
|                        +------------------+------------------+                       |
|                        |                                     |                       |
|                        v                                     v                       |
|            +-----------------------+             +-----------------------+           |
|            | SQS: Order Fulfillment|             | SQS: Customer Email   |           |
|            | (Visibility: 90s, DLQ)|             | (Visibility: 60s, DLQ)|           |
|            +-----------+-----------+             +-----------+-----------+           |
|                        |                                     |                       |
|                        v                                     v                       |
|            +-----------------------+             +-----------------------+           |
|            | Fulfillment Worker    |             | Email Notification    |           |
|            | (ECS Fargate Task)    |             | (AWS Lambda Function) |           |
|            +-----------+-----------+             +-----------------------+           |
|                        |                                                             |
|                        | Upload PDF Invoices (SSE-KMS)                               |
|                        v                                                             |
|            +-----------------------+                                                 |
|            | Amazon S3 Bucket      |                                                 |
|            | (Invoices & Media)    |                                                 |
|            +-----------------------+                                                 |
|                                                                                      |
|  +--------------------------------------------------------------------------------+  |
|  | CROSS-CUTTING PLATFORM SERVICES                                                |  |
|  |                                                                                |  |
|  |  - AWS Secrets Manager: DB passwords and third-party API keys                  |  |
|  |  - AWS KMS: Customer Managed Keys (CMK) for EBS, S3, RDS, Secrets              |  |
|  |  - Amazon CloudWatch: Container Insights, Metrics, Alarms, Logs                |  |
|  |  - AWS CloudTrail: Regional management event auditing                          |  |
|  |  - AWS X-Ray: Distributed tracing and dependency map                           |  |
|  +--------------------------------------------------------------------------------+  |
+--------------------------------------------------------------------------------------+
```

---

## 19. Five Production Incident Simulations

### Incident A — Leaked AWS IAM Credentials
- **Detection:** An alert triggers from AWS GuardDuty: `UnauthorizedAccess:IAMUser/InstanceCredentialExfiltration.OutsideAWS`. Unfamiliar EC2 instances spin up in an unapproved region (`us-west-2`).
- **Response:**
  1. Immediately deactivate or delete the compromised access key via AWS CLI:
     `aws iam update-access-key --access-key-id AKIA... --status Inactive`
  2. Query CloudTrail to identify all API actions performed by the compromised key in the last 24 hours.
  3. Terminate all unauthorized instances, security groups, and IAM roles created by the attacker.
  4. Force password reset and MFA re-enrollment for the affected IAM user.
  5. Audit source repositories using GitGuardian/TruffleHog to locate how the credential leaked.

### Incident B — S3 Bucket Public Exposure
- **Detection:** Security review finds an S3 bucket policy containing `"Principal": "*"` and `"Action": "s3:GetObject"`.
- **Response:**
  1. Immediately apply S3 Block Public Access at the account and bucket level:
     `aws s3api put-public-access-block --bucket invoice-bucket --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"`
  2. Query CloudTrail S3 Data Events to audit all IP addresses that accessed objects during the exposure window.
  3. Validate if any personally identifiable information (PII) was exfiltrated; report according to GDPR/data breach protocols.
  4. Implement an AWS Config rule (`s3-bucket-public-read-prohibited`) to automatically remediate future policy misconfigurations.

### Incident C — Post-Deployment 5xx Spike
- **Detection:** ALB 5xx rate jumps from 0.01% to 14% immediately after an ECS deployment.
- **Response:**
  1. Check CloudWatch deployment metrics and correlate with the exact time of the ECS service update.
  2. Inspect target group health: 50% of targets are unhealthy due to failing `/actuator/health` checks.
  3. Immediately roll back to the previous stable task definition:
     `aws ecs update-service --cluster prod --service orders --task-definition orders-api:42`
  4. Once healthy capacity is restored, examine container logs from the failed tasks: discover that a required environment variable (`SPRING_PROFILES_ACTIVE`) was omitted in the new revision.

### Incident D — SQS Backlog Growth and Consumer Starvation
- **Detection:** PagerDuty alert: `ApproximateAgeOfOldestMessage` on `orders-fulfillment-queue` exceeds 15 minutes.
- **Response:**
  1. Check consumer task metrics: ECS fulfillment workers are running at 100% CPU.
  2. Check worker logs: workers are executing slow, unindexed database queries on each message.
  3. Add the missing database index in PostgreSQL (`CREATE INDEX CONCURRENTLY idx_orders_customer...`).
  4. Scale out ECS fulfillment worker task count from 2 to 10 to drain the 50,000 message backlog.
  5. Once the backlog is drained, scale back to baseline task count and verify DLQ message count is 0.

### Incident E — Unexpected AWS Bill Spike ($10,000 Jump)
- **Detection:** AWS Budgets email alert: forecasted monthly spending exceeds target budget by 300%.
- **Response:**
  1. Open AWS Cost Explorer and group costs by Service and Usage Type.
  2. Identify the culprit: **NAT Gateway Data Processing fees** in `ap-south-1` accounted for $8,500.
  3. Root cause: An ECS worker was downloading 50 GB of machine learning models from an S3 bucket every 10 minutes over the public internet through the NAT Gateway.
  4. Fix: Create a **Gateway VPC Endpoint for S3** in the VPC. Traffic to S3 now routes privately over AWS internal networking at **$0.00 data transfer fee**, completely eliminating the NAT Gateway charge.

---

# 20. FAANG-Level Interview Questions & Answers

### 1. Why should an application use an IAM role instead of hardcoded access keys?
IAM roles eliminate long-lived credentials from source code and configuration files. AWS automatically provisions, distributes, and rotates temporary credentials (valid for 1–6 hours) via the instance profile or container metadata service, dramatically reducing the blast radius of credential leaks.

### 2. What is the difference between authentication and authorization?
Authentication (AuthN) verifies the identity of a principal ("who are you?"). Authorization (AuthZ) verifies what actions that authenticated principal is permitted to execute on a target resource ("what are you allowed to do?").

### 3. What is least privilege?
The foundational security principle of granting an identity strictly the minimum set of permissions required to complete its intended tasks, scoped to specific resource ARNs, actions, and conditions, and nothing more.

### 4. What is the difference between Secrets Manager and SSM Parameter Store?
Secrets Manager is tailored for sensitive credentials with built-in automatic rotation for databases, cross-account sharing, and per-secret monthly pricing. SSM Parameter Store is a general-purpose configuration store supporting free plain text strings and KMS-encrypted `SecureString` parameters.

### 5. What does AWS KMS provide?
AWS KMS provides centralized, hardware security module (HSM)-backed management and generation of cryptographic keys, controlling encryption and decryption operations across AWS services with audit logging in CloudTrail.

### 6. Does encryption at rest eliminate the need for authorization?
No. Encryption protects data confidentiality if underlying storage media is stolen or accessed out-of-band. However, if an unauthorized principal has IAM permissions that permit `kms:Decrypt` and `s3:GetObject`, the system will happily decrypt and return the data. Authorization controls access; encryption enforces confidentiality.

### 7. What is the difference between CloudWatch and CloudTrail?
CloudWatch collects, visualizes, and alerts on operational telemetry (metrics, logs, traces, system performance). CloudTrail audits management and API operations across the AWS account (who called which API, when, and from where).

### 8. Metrics versus logs versus traces: how do they differ?
Metrics show aggregate numerical trends over time (what is happening). Logs provide detailed, timestamped event records of specific occurrences (what happened). Traces map the end-to-end journey of a single request across multiple distributed services and databases (where time was spent).

### 9. Why monitor p95 and p99 latency instead of average latency?
Averages hide severe tail latency issues. If 95% of users experience 50 ms latency, but 5% experience 10 seconds, the average might look acceptable (500 ms), but 1 in 20 customers experiences a broken, frustrating checkout.

### 10. What is an SLO and how is it used?
A Service Level Objective is an agreed-upon internal target for an indicator (e.g., "99.9% of order requests return HTTP 200 in $< 500$ ms"). It establishes an Error Budget that guides engineering trade-offs between rapid feature deployment and reliability investments.

### 11. Why can aggressive retries worsen a database outage?
When a database is struggling under high load, thousands of client instances retrying immediately create a "thundering herd" or retry storm. This multiplies incoming traffic exponentially, driving database CPU to 100% and preventing it from recovering. Retries must be bounded, with exponential backoff, jitter, and circuit breakers.

### 12. What is graceful shutdown?
A process termination sequence where an application stops accepting new requests from the load balancer, allows currently in-flight requests to complete cleanly within a timeout window, flushes buffers, closes database connection pools, and exits cleanly with return code 0.

### 13. Why must CI/CD pipelines deploy immutable artifacts?
Deploying an immutable container image tagged with a Git commit SHA ensures that the exact binary that passed automated unit, integration, and security tests in staging is what runs in production. It eliminates configuration drift and guarantees reproducible rollbacks.

### 14. What is the difference between blue-green and canary deployments?
Blue-green maintains two identical production environments (Blue and Green), routing 100% of traffic from one to the other via a load balancer switch. Canary deployment gradually routes a small percentage of real user traffic (e.g., 5%, then 25%, then 100%) to the new version while actively monitoring error rates.

### 15. What is the Transactional Outbox pattern?
An architectural pattern that resolves the dual-write problem by saving a business entity (e.g., order) and an event record (e.g., `OrderPlaced`) into the same database transaction. A separate publisher reads committed outbox events and publishes them to the message broker, ensuring reliable event publication without data loss.

### 16. Why is consumer idempotency mandatory in SQS architectures?
Amazon SQS Standard queues guarantee at-least-once delivery, meaning network retries or expired visibility timeouts can cause the same message to be delivered multiple times. Idempotent consumers guarantee that processing duplicate messages produces no duplicate side effects.

### 17. Multi-AZ versus Multi-Region: what are the operational trade-offs?
Multi-AZ provides high availability and automatic failover within a single geographic region with sub-millisecond synchronous replication. Multi-Region provides disaster recovery against regional catastrophic failure, but requires complex asynchronous data replication, handling of eventual consistency, split-brain mitigation, and significantly higher networking costs.

### 18. How do you reduce AWS costs without impacting reliability?
1. Replace NAT Gateway S3/DynamoDB traffic with free Gateway VPC Endpoints.
2. Right-size over-provisioned EC2/RDS instances using CloudWatch telemetry.
3. Purchase Savings Plans or Reserved Instances for predictable baseline compute.
4. Set S3 Lifecycle rules to transition objects to Glacier and expire old logs.
5. Delete unattached EBS volumes, obsolete snapshots, and unused load balancers.

### 19. How would you design an AWS backend to handle a 10x traffic spike?
1. Front the architecture with an Application Load Balancer and CloudFront CDN for static caching.
2. Deploy containerized stateless Spring Boot tasks on ECS Fargate with target tracking autoscaling based on ALB request count.
3. Protect the database using Amazon RDS Proxy to pool and multiplex database connections.
4. Offload heavy processing (invoices, emails, analytics) asynchronously via SQS queues and background workers.
5. Implement Redis (ElastiCache) caching for read-heavy database queries.

### 20. How would you investigate a suspected unauthorized AWS API change?
1. Open AWS CloudTrail Event History and search by resource name or suspicious event name.
2. Identify the calling IAM ARN, source IP, user agent, and timestamp.
3. Check AWS GuardDuty and VPC Flow Logs for associated network anomalies.
4. Immediately revoke permissions or quarantine the compromised IAM identity.
5. Revert unauthorized infrastructure modifications using Terraform.

---

# 21. Final Hands-On Capstone

To achieve complete mastery, implement the following local-first architecture on your workstation:

- **Phase 1 — Application Core:** Implement a Spring Boot 3 REST API in Java 21 with `/api/v1/orders`. Configure PostgreSQL with Flyway migrations. Implement the Transactional Outbox pattern: write to `orders` and `outbox_events` atomically.
- **Phase 2 — Asynchronous Processing:** Implement a background poller or worker that reads `outbox_events`, simulates dispatching to SQS, and writes to a local `processed_events` idempotency table.
- **Phase 3 — Observability:** Add Spring Boot Actuator with Micrometer. Export structured JSON logs containing `traceId`, `orderId`, and `timestamp`. Configure health probes on `/actuator/health/readiness` and `/actuator/health/liveness`.
- **Phase 4 — Containerization & CI/CD:** Write a multi-stage Dockerfile using Eclipse Temurin 21. Create a GitHub Actions workflow that compiles code, executes tests, builds the container image, and tags it with `${{ github.sha }}`.
- **Phase 5 — Production Readiness Review:** Complete the 20-point pre-production readiness checklist and document the failure modes for database connection loss, queue consumer crashes, and rolling updates.

---

# 22. AWS Final Readiness Assessment

Test your understanding with these core architectural scenarios:

#### Question 1
A production Spring Boot API running on ECS needs to upload invoice PDFs to Amazon S3. How should credentials be supplied?
- (A) Hardcode an IAM User access key in `application.yml`.
- **(B) Attach an IAM Task Role to the ECS task definition with a policy allowing `s3:PutObject` on the specific invoice bucket.** *(Correct)*
- (C) Use the root account credentials stored in an environment variable.
- (D) Assign the permission to the underlying EC2 host's instance profile.
*Explanation:* Workloads should use IAM Task Roles to obtain temporary credentials scoped to the specific container task, adhering to least privilege.

#### Question 2
Which AWS service is specifically designed for auditing management API calls, such as who modified a security group or deleted an RDS instance?
- **(A) AWS CloudTrail** *(Correct)*
- (B) Amazon CloudWatch Metrics
- (C) AWS X-Ray
- (D) Amazon GuardDuty
*Explanation:* CloudTrail records AWS account activity and API calls for governance and compliance. CloudWatch monitors application and infrastructure operational telemetry.

#### Question 3
An SQS consumer queue depth is climbing rapidly. What is the first operational step?
- (A) Immediately increase consumer worker count to 100 tasks.
- (B) Delete all messages in the queue to clear the backlog.
- **(C) Inspect CloudWatch metrics for message age, consumer error logs, processing duration, and downstream database saturation.** *(Correct)*
- (D) Reduce the SQS visibility timeout to 1 second.
*Explanation:* You must identify the root bottleneck first. If the downstream database is saturated, adding more consumers will cause total database failure.

#### Question 4
A rolling deployment is initiated. Immediately, ALB returns HTTP 500 errors on 15% of requests. What is the safest immediate action?
- **(A) Stop the deployment and trigger an immediate automated rollback to the previous known-good task revision.** *(Correct)*
- (B) SSH into the running containers and inspect heap dumps.
- (C) Increase the request timeout on the Application Load Balancer to 60 seconds.
- (D) Wait 2 hours to see if errors clear on their own.
*Explanation:* Contain customer impact immediately by rolling back to the known-good version, then investigate logs and root causes safely in a staging environment.

#### Question 5
Why is an AWS Budget alert not a guarantee against unexpected cloud charges?
- (A) AWS Budgets only tracks compute instances, not storage.
- **(B) Budgets are passive monitoring and notification tools; they do not automatically terminate running resources or stop network transfers, and billing telemetry has a propagation delay.** *(Correct)*
- (C) Budgets only trigger after an invoice is officially billed at the end of the month.
- (D) Budgets require manual approval before sending emails.
*Explanation:* Budgets send notifications when thresholds are crossed; they do not enforce a hard spending cap or automatically shut down infrastructure unless configured with custom automation scripts.

#### Question 6
Why is the Transactional Outbox pattern preferred over publishing directly to SNS/SQS from the API handler?
- (A) It allows SQS to execute SQL queries directly.
- (B) It makes SQS messages strictly FIFO.
- **(C) It guarantees atomic consistency between the database update and event publication, eliminating the dual-write problem where database commits succeed but network message publishing fails.** *(Correct)*
- (D) It eliminates the need for message consumers to be idempotent.
*Explanation:* The outbox pattern commits the entity and event within the same ACID database transaction, ensuring no events are lost if the application crashes before publishing.

---

## Final Mastery Checklist

You have mastered the AWS Cloud Engineering track when you can:

- [ ] Explain workload IAM roles (Instance Profiles, ECS Task Roles, Lambda Execution Roles) and least privilege.
- [ ] Design secure secret retrieval and rotation using Secrets Manager and SSM Parameter Store.
- [ ] Distinguish CloudWatch, CloudTrail, and AWS X-Ray responsibilities and use cases.
- [ ] Define actionable monitoring alarms using Golden Signals (Latency, Traffic, Errors, Saturation).
- [ ] Design an automated, secure CI/CD pipeline using GitHub Actions, OIDC, and Amazon ECR.
- [ ] Implement bounded retries with jitter, circuit breakers, and graceful shutdown.
- [ ] Calculate and defend SLIs, SLOs, and Error Budgets for production APIs.
- [ ] Diagnose and resolve SQS queue backlogs without overloading downstream databases.
- [ ] Architect resilient Multi-AZ systems with automated failover and verified point-in-time recovery.
- [ ] Analyze AWS billing drivers and optimize costs using Gateway VPC Endpoints and right-sizing.
- [ ] Articulate and defend a complete, production-grade cloud backend architecture in a technical interview.

---

# Handbook Completion Protocol

1. Save this chapter as `content/aws/06-aws-production-security-observability-cicd-cost-architecture-capstone.md`.
2. Verify that all six AWS source files exist and that the earlier chapters are preserved.
3. Check that the chapters collectively cover fundamentals, practical workflows, and production engineering/interview mastery.
4. Generate **one complete AWS handbook PDF only after all six source files have been saved and verified**:
   `docs/aws/BEH_AWS_COMPLETE_HANDBOOK.pdf`
5. Verify that the PDF includes all six chapters in order, with readable code blocks, tables, diagrams, and page breaks.
6. Verify the README progress and final PDF path.
7. Commit the verified AWS sources and final PDF using the exact commit message:

   `AWS done`
