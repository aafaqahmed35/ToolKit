# AWS — Chunk 1 of 6: Cloud Foundations, IAM & Your First Backend Architecture

## Learning Objectives

By the end of this chapter, you should be able to:

- Explain cloud computing and why engineering teams use it.
- Distinguish regions, Availability Zones, and edge locations.
- Understand the shared responsibility model.
- Navigate the basic AWS account and resource model.
- Explain IAM users, groups, roles, policies, and temporary credentials.
- Apply least-privilege access to a backend application.
- Design a first AWS architecture for a Java Spring Boot API.
- Reason about cloud costs, security incidents, and availability failures.

**Prerequisites:** Basic HTTP, REST APIs, Java, databases, and familiarity with deploying an application locally. No cloud experience is required.

---

# Layer 1 — Fundamentals & Mental Models

## 1. What Is Cloud Computing?

Imagine you build a Spring Boot API on your MacBook. It works locally, but your laptop is not a production hosting platform. If you close it, the API disappears from the internet. You must also manage networking, power, operating-system updates, and availability yourself.

Now imagine renting computing resources from a provider that operates large data centers and exposes them through APIs and a management console.

That is the basic idea behind cloud computing.

Cloud providers offer computing, storage, networking, databases, identity, monitoring, and other capabilities as services that you can provision when needed.

AWS stands for Amazon Web Services.

Instead of purchasing a physical server before you can deploy your application, you can provision a virtual server or a managed application service and pay according to the service's pricing model.

### The core mental model

Think of AWS as a collection of programmable infrastructure building blocks.

- **Compute** runs code.
- **Storage** keeps data or files.
- **Networking** controls how systems communicate.
- **Databases** store and retrieve structured or specialized data.
- **Identity and access management** controls who can do what.
- **Monitoring** helps you understand whether systems are working.
- **Managed services** let AWS operate some of the underlying infrastructure for you.

You choose the components, configure them, connect them, and decide how the application should behave when things fail.

## 2. Why Companies Use AWS

Cloud infrastructure is useful for several reasons.

### 2.1 Elasticity

Suppose your API normally receives 100 requests per second but experiences 2,000 requests per second during a major event.

Elastic infrastructure can add or remove capacity according to demand, provided that the application and its scaling configuration support it.

Without elasticity, you might have to purchase capacity for peak traffic and leave much of it unused during normal periods.

**Important:** Cloud elasticity is not automatic for every resource. Some services require explicit scaling policies, and databases or stateful components can have different scaling constraints.

### 2.2 Pay-as-you-go pricing

Instead of purchasing every server upfront, many cloud services charge based on consumption, allocated capacity, requests, storage, or data transfer.

This reduces some upfront investment but introduces a new engineering responsibility: controlling usage and understanding the bill.

A badly configured cloud system can cost more than an appropriately sized physical server.

### 2.3 Managed infrastructure

Compare two database approaches:

- Install PostgreSQL on a virtual machine and manage its updates, backups, recovery, and operating system.
- Use a managed database service such as Amazon RDS, where AWS operates many underlying database-management tasks.

Managed services reduce operational burden, but they do not eliminate your responsibility for schema design, access control, query performance, backup strategy, or application correctness.

### 2.4 Global reach

AWS provides infrastructure in multiple geographic regions. You can select regions appropriate for your users, compliance requirements, latency targets, and availability strategy.

A globally distributed architecture can improve user experience, but it also introduces complexity involving replication, consistency, networking, cost, and failure recovery.

## 3. Cloud Service Models: IaaS, PaaS, and SaaS

These categories describe how much of the computing stack you operate yourself.

| Model | Description | AWS Examples |
|---|---|---|
| **IaaS — Infrastructure as a Service** | You provision infrastructure such as virtual machines and networking, while managing much of the operating system and application stack. | Amazon EC2, Amazon VPC, Amazon EBS |
| **PaaS — Platform as a Service** | The platform abstracts more infrastructure and operational tasks so you can focus on application delivery. AWS services offer different levels of platform abstraction; not every managed service fits neatly into a single textbook category. | AWS Elastic Beanstalk, AWS App Runner, Amazon RDS |
| **SaaS — Software as a Service** | You consume a finished application instead of provisioning the underlying infrastructure. Examples include hosted email, collaboration, and CRM applications. | Amazon WorkDocs, SaaS partner applications |

### An important interview distinction

These categories are useful mental models, not strict labels that perfectly describe every cloud product.

For example, a managed database still requires database engineering, while a container platform may abstract servers but leave networking, identity, scaling, and application reliability to you.

The practical question is:

**Which responsibilities remain yours, and which responsibilities does the provider operate?**

That question becomes especially important during incidents.

## 4. AWS Global Infrastructure

Three concepts matter early: regions, Availability Zones, and edge locations.

```text
+--------------------------------------------------------------------------+
|                        AWS Global Infrastructure                         |
+--------------------------------------------------------------------------+
|  Regions (e.g., us-east-1, eu-west-1, ap-south-1)                        |
|  +--------------------------------------------------------------------+  |
|  |  Geographic Region Boundary                                        |  |
|  |  +------------------------+  +----------------------------------+  |  |
|  |  |  Availability Zone A   |  |  Availability Zone B             |  |  |
|  |  |  (Isolated data center)|  |  (Isolated data center)          |  |  |
|  |  +------------------------+  +----------------------------------+  |  |
|  +--------------------------------------------------------------------+  |
+--------------------------------------------------------------------------+
|  Edge Locations (Global Content Delivery & Caching via Amazon CloudFront)|
+--------------------------------------------------------------------------+
```

### 4.1 Regions

A region is a separate geographic area containing AWS infrastructure.

You choose a region when creating many AWS resources.

For example, a service deployed in one region does not automatically become available in another region.

Region selection can affect:

- Latency for your users.
- Service availability.
- Data residency and compliance.
- Price.
- Disaster recovery options.
- Cross-region data-transfer costs.

### 4.2 Availability Zones

An Availability Zone, or AZ, is an isolated location within an AWS region, designed to reduce the impact of certain failures affecting other zones.

A region contains multiple Availability Zones.

For higher availability, a backend might run application instances in multiple AZs and use a load balancer to distribute requests.

However, multiple AZs do not automatically make every part of an application highly available. A single-AZ database, a single external dependency, or an application-level bottleneck can still cause an outage.

### 4.3 Edge locations

AWS operates edge infrastructure used by services such as Amazon CloudFront to deliver content closer to users.

For example, an API's static documentation or images may be delivered through a content delivery network. Dynamic API requests may still need to reach an origin or backend service.

Do not confuse edge locations with regions or Availability Zones.

### Quick comparison

| Concept | Main purpose | Example use |
|---|---|---|
| Region | Geographic deployment boundary | Host a backend near its users |
| Availability Zone | Isolation and resilience within a region | Spread application capacity across zones |
| Edge location | Deliver supported content and services near users | Cache static content through CloudFront |

### 4.4 Multi-AZ vs. Multi-Region

A multi-AZ architecture improves resilience against failures affecting an individual zone.

A multi-region architecture can help with broader regional outages and geographic distribution, but it is substantially more complex.

Multi-region designs must consider:
- How data is replicated.
- Whether writes can occur in multiple locations.
- Consistency and conflict handling.
- DNS or traffic failover.
- Recovery time and data-loss objectives.
- Cross-region transfer costs.

For a fresher's first backend deployment, a well-designed single-region architecture is a sensible starting point. Learn multi-AZ architecture next, then study multi-region recovery as an advanced design decision.

## 5. The AWS Resource Model

A useful way to understand AWS is to distinguish an account, a region, and an individual resource.

### Account

An AWS account provides an administrative and resource boundary. It is also important for billing and access control.

### Region

Many resources are created in a selected region. Some AWS capabilities are global or account-level instead, so do not assume every resource is regional.

### Resource

A resource is an individual cloud object, such as an EC2 instance, an S3 bucket, or an RDS database.

A simplified mental model:

```text
AWS organization
└── AWS account
    ├── Region A
    │   ├── Virtual network
    │   ├── Application compute
    │   └── Database
    └── Region B
        └── Disaster-recovery resources
```

This is illustrative, not a mandatory architecture.

In a larger company, separate accounts may be used for development, staging, production, security, or shared infrastructure. AWS Organizations can help manage multiple accounts.

### Resource names and identifiers

Cloud resources may have names, identifiers, and Amazon Resource Names (ARNs).

An ARN identifies an AWS resource in a structured form. The exact format depends on the service.

For example, IAM policies may use ARNs to specify which resources an action applies to.

Do not assume every resource supports the same naming rules or global uniqueness requirements.

## 6. The Shared Responsibility Model

One of the most important cloud concepts is the division of responsibility between the provider and the customer.

AWS is responsible for the security of the cloud, including the underlying infrastructure it operates. Customers are responsible for security in the cloud, with the precise boundary depending on the service.

### Example: EC2

When you run an application on an EC2 virtual machine, you generally have responsibilities for:
- Operating-system configuration and updates.
- Application security.
- Application dependencies.
- Access control.
- Network rules you configure.
- Protecting credentials and data.

AWS operates the underlying physical infrastructure and virtualization layer.

### Example: Managed database

With a managed database, AWS handles more of the underlying infrastructure and operational work, but you still need to consider:
- Database permissions.
- Network access.
- Encryption configuration.
- Data classification.
- Query performance.
- Backup retention and recovery requirements.
- Application-level data correctness.

**Interview takeaway:** Moving a workload to the cloud changes the operational boundary; it does not remove security and reliability responsibilities.

## 7. What Is IAM?

IAM means Identity and Access Management.

IAM controls which identities can perform which actions on which AWS resources.

Imagine your Spring Boot API needs to upload an invoice to an S3 bucket. The application should be allowed to upload to the intended bucket, but it should not automatically receive permission to delete every bucket in your AWS account.

IAM expresses those permissions.

The key concepts are:

- **Principal:** An identity that makes a request.
- **Authentication:** Establishing which identity is making the request.
- **Authorization:** Determining whether that identity may perform the requested action.
- **Policy:** A document describing allowed or denied actions and their scope.
- **Role:** An identity that can be assumed to obtain a set of permissions, often through temporary credentials.

Authentication and authorization are separate. A user can authenticate successfully but still lack permission to perform an operation.

## 8. IAM Users, Groups, Roles, and Policies

### IAM user

An IAM user is an identity within an AWS account. It can have credentials and permissions assigned directly or through group membership.

Long-lived IAM user access keys require careful management. Avoid creating permanent access keys for applications when a role-based credential mechanism is available.

### IAM group

An IAM group helps organize IAM users and attach shared permissions to them.

Groups are useful for organizing human access, but they are not a general mechanism for assigning application workloads their own identity.

### IAM role

An IAM role has permissions that an authorized principal can assume. It provides temporary credentials when assumed.

Roles are central to AWS workload identity, cross-account access, and temporary elevated access.

For example:
- An EC2 instance can use an instance profile to obtain credentials associated with an IAM role.
- A supported container workload can obtain credentials through its configured task or pod identity mechanism.
- A CI/CD system can assume a role to deploy a service.

### IAM policy

A policy specifies permissions. A simplified identity-based policy might look like this:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::my-invoices-bucket/invoices/*"
    }
  ]
}
```

This illustrates permission to upload objects to a particular object path. It is not a complete policy for every S3 operation or application.

The bucket name and path must be replaced with real, intended values.

### How to read the policy

- `Effect`: whether the statement allows or denies an operation.
- `Action`: which API actions it matches.
- `Resource`: which resources the statement applies to.

Other policy elements can include conditions and principal-related information, depending on the policy type.

**Important:** AWS authorization can involve multiple policy types. An explicit deny overrides an applicable allow. The final decision depends on the complete authorization context, including resource policies, permissions boundaries, session policies, and organization-level controls where applicable.

## 9. Least Privilege

Least privilege means granting only the permissions needed for a task, at the narrowest practical scope.

Consider two policies for an API that uploads invoices.

**Overly broad example:**

```json
{
  "Effect": "Allow",
  "Action": "s3:*",
  "Resource": "*"
}
```

**Narrower example:**

```json
{
  "Effect": "Allow",
  "Action": "s3:PutObject",
  "Resource": "arn:aws:s3:::my-invoices-bucket/invoices/*"
}
```

The second policy is narrower, assuming the application needs only that operation and object path.

Real applications may also need additional permissions for encryption, reading objects, or multipart uploads. Add permissions based on actual requirements, not by default.

### Why this matters

If an application credential is compromised, the permissions attached to that identity influence what an attacker can do.

Least privilege limits the potential blast radius.

It is not enough to protect the credential itself; the credential must also have appropriately restricted permissions.

---

# Layer 2 — Practical Engineering & Workflows

## 10. Your First AWS Backend Architecture

Suppose we want to deploy a Spring Boot Orders API backed by PostgreSQL.

The architecture could evolve like this:

```text
                    Internet
                       |
                       v
                Public HTTPS entry
                       |
                       v
                  Load Balancer
                       |
             ---------------------
             |                   |
             v                   v
         API instance        API instance
             |                   |
             ---------+-----------
                      |
                      v
               Managed PostgreSQL
```

This is a conceptual design. A real deployment needs VPC networking, subnet placement, security groups, application identity, secrets management, database configuration, logging, monitoring, and a deployment workflow.

For the first lesson, focus on the responsibilities of the components.

### Component responsibilities

**Load balancer:** Distributes incoming requests across healthy targets when correctly configured.

**Application instances:** Run the Spring Boot application.

**Database:** Stores durable application state.

**IAM role:** Grants the application or deployment workflow only the AWS permissions it needs.

**Monitoring:** Collects signals needed to understand application and infrastructure behavior.

**Network controls:** Restrict which components can communicate.

### A critical design rule

Your application should not need unrestricted database access from the public internet.

A common design places the database in private subnets and restricts database access to the intended application security group or other narrowly scoped network path.

Network isolation and IAM permissions are separate controls. A correct IAM policy does not replace network restrictions, and a private subnet does not replace database authentication.

## 11. Create an AWS Learning Environment Safely

You can learn the concepts before deploying paid infrastructure.

### Step 1 — Secure your account

If you create an AWS account:

1. Enable multi-factor authentication for the root user.
2. Do not use the root user for routine engineering tasks.
3. Use an appropriately secured identity for administration.
4. Create only the permissions needed for your labs.
5. Enable suitable billing visibility and budget notifications.
6. Review the current AWS Free Tier and pricing conditions before creating resources.

A budget notification is useful, but it should not be treated as a guaranteed hard spending cap. Some costs can be incurred before an alert is delivered.

### Step 2 — Choose a region deliberately

For learning, select a region that makes sense for your location, service availability, and cost. Use the same region consistently unless a lab specifically teaches regional differences.

### Step 3 — Install the AWS CLI

The AWS Command Line Interface lets you manage supported AWS services from your terminal.

Check whether it is installed:

```bash
aws --version
```

If it is missing, install AWS CLI v2 using the official AWS installation instructions for your operating system.

### Step 4 — Configure credentials securely

For human access, prefer an AWS-supported identity and credential flow appropriate to your environment, such as IAM Identity Center or another approved role-based setup.

Then inspect the active identity:

```bash
aws sts get-caller-identity
```

This command reports the AWS account and identity associated with the credentials being used.

Avoid pasting access keys into source files, shell scripts, chat messages, or Git commits.

### Step 5 — Understand profiles and regions

You may use named CLI profiles to separate identities and environments.

For example:

```bash
aws configure list-profiles
```

A named profile can be used with commands through `--profile`, provided that the profile has been configured.

Always verify the active account and region before running commands that create, modify, or delete resources.

## 12. First Practical Lab: Inspect AWS Identity

This lab is intentionally read-only.

Run:

```bash
aws sts get-caller-identity
```

Inspect the output:
- Which AWS account is active?
- Which principal is making the request?
- Are you using the intended learning or development identity?

Then run:

```bash
aws configure list
```

This helps inspect which configuration and credential sources the CLI is using. Sensitive values may be masked, but never share credential output publicly.

### Troubleshooting

**Error: Unable to locate credentials**

Possible causes:
- No supported credential source is configured.
- The selected profile is missing.
- The environment is not configured for role-based credentials.

**Error: AccessDenied**

Possible causes:
- The identity lacks the required permission.
- A permission boundary or organization-level policy restricts the operation.
- A role trust policy or session policy prevents the requested access.

**Error: ExpiredToken**

Possible causes:
- Temporary credentials expired.
- The credential session needs to be refreshed.
- The application or CLI is using stale credentials.

The right fix depends on the identity flow. Do not solve credential problems by granting administrator access indiscriminately.

## 13. Application Credentials: The Correct Pattern

Suppose your API needs to upload an invoice to S3.

Avoid hardcoding credentials:

```java
// Never embed real AWS credentials in application source code.
String accessKey = "AKIA...";
String secretKey = "secret...";
```

Instead, use the AWS SDK's supported credential provider chain or a specifically configured workload identity mechanism.

For example, with the AWS SDK for Java v2, the default credentials provider can resolve credentials from supported sources:

```java
import software.amazon.awssdk.auth.credentials.DefaultCredentialsProvider;
import software.amazon.awssdk.services.s3.S3Client;

public class S3ClientFactory {

    public static S3Client create() {
        return S3Client.builder()
                .credentialsProvider(
                    DefaultCredentialsProvider.create()
                )
                .build();
    }
}
```

This is a basic illustration. The SDK dependency and region configuration must also be supplied by your project.

For production, configure the workload's identity using an appropriate AWS-supported mechanism, such as an EC2 instance profile or an ECS task role, depending on where the application runs.

The exact credential source depends on the runtime environment.

### Why temporary credentials are preferable

Temporary credentials:
- Expire automatically.
- Can be refreshed by supported credential providers.
- Reduce reliance on long-lived access keys.
- Allow permissions to be tied to a workload identity.

They still need appropriate permissions and secure delivery. Temporary credentials are not inherently safe if an attacker can retrieve them from a compromised workload.

## 14. Your First IAM Design Exercise

Imagine an Orders API with two responsibilities:

1. Read a configuration object from a designated S3 path.
2. Upload invoice files to a designated S3 path.

Before writing a policy, answer:

- Which bucket does the API need?
- Which object prefixes does it need?
- Does it need to list the bucket?
- Does it need to read existing objects?
- Does it need to delete objects?
- Is access to other buckets necessary?

Build the policy from these requirements.

Do not begin with `s3:*` and attempt to remove permissions later. Begin with the smallest permission set and add permissions only when a verified requirement demands them.

### Human access versus workload access

Separate the permissions of the engineer deploying the application from the permissions of the running application.

A deployment identity might need permission to update a service. The application identity might need permission to upload invoices. Those responsibilities should not automatically share one unrestricted credential.

This separation makes incidents easier to contain and permissions easier to review.

---

# Layer 3 — Production Engineering & Interview Mastery

## 15. Production Security Principles

### 15.1 Protect the root user

The root user has broad account-level capabilities and should not be used for ordinary development tasks.

Protect it with MFA and reserve it for operations that specifically require root-user access.

### 15.2 Avoid long-lived access keys where possible

Prefer short-lived, role-based credentials for supported human and workload environments.

If long-lived keys are genuinely required, establish a secure storage, rotation, monitoring, and revocation process.

Never commit credentials to Git.

### 15.3 Restrict network exposure

A security group is a virtual firewall controlling traffic to and from associated resources.

For a typical API architecture:
- Public ingress should expose only the intended entry point.
- Application instances should accept traffic only from intended sources.
- Database access should be restricted to the application or other approved clients.
- Administrative access should use a controlled management path.

Security groups are stateful. Network ACLs are a separate network control with different behavior. Both should be understood before designing complex network rules.

### 15.4 Use encryption thoughtfully

Consider encryption:
- In transit, using TLS where appropriate.
- At rest, using supported encryption mechanisms for storage and databases.
- For secrets, using a dedicated secrets-management approach.
- For backups, ensuring that the protection and access policies match the sensitivity of the data.

Encryption does not replace access control, monitoring, or key-management practices.

## 16. Availability and Failure Reasoning

Cloud architecture is not just about selecting services. It is about understanding which failures a design can tolerate.

### Scenario A — An application instance fails

If the application runs on a single instance, a failure may make the API unavailable.

A multi-instance design behind a correctly configured load balancer can continue serving traffic if enough healthy capacity remains.

But this requires:
- More than one healthy instance.
- Appropriate health checks.
- Capacity to handle remaining traffic.
- A deployment and recovery process.
- No single shared dependency that defeats the design.

### Scenario B — The database becomes unavailable

Two healthy API instances cannot solve a database outage if both depend on the same unavailable database.

The application may need:
- Sensible connection timeouts.
- Bounded retries with backoff.
- Connection-pool limits.
- Graceful degradation where appropriate.
- A recovery and backup strategy.
- Clear observability for database errors and latency.

Do not blindly retry writes. A request may have committed before the connection failed, leaving the client uncertain about the outcome. Idempotency and reconciliation may be necessary.

### Scenario C — An entire Availability Zone fails

A multi-AZ application design may continue operating if application capacity and required dependencies are available in surviving zones.

However, failover behavior depends on the architecture and service configuration. A zonal dependency, insufficient remaining capacity, or a failed network path may still cause an outage.

### Scenario D — An AWS region becomes unavailable

A single-region application may be unavailable during a severe regional failure.

Multi-region recovery can reduce that risk, but requires explicit design for data replication, routing, failover, consistency, and recovery procedures.

For most early projects, understand the trade-off before implementing a multi-region architecture. Complexity has a cost.

## 17. Cost Engineering for Beginners

Cloud costs are an engineering concern, not merely a finance concern.

Potential cost sources include:
- Running compute resources.
- Allocated database capacity.
- Storage.
- Requests and data processing.
- Data transfer.
- Load balancers and other supporting services.
- Monitoring, logs, and retained data.

### Cost controls for learning

1. Create a budget and configure alerts.
2. Choose the smallest suitable resources for a lab.
3. Check whether services have hourly or usage-based charges.
4. Review the cost of public IPv4 addresses, networking, and data transfer where applicable.
5. Stop or delete resources when no longer needed.
6. Verify what remains after cleanup, including storage, snapshots, addresses, and other persistent resources.

**Important:** Stopping an instance does not necessarily stop all related charges. For example, attached storage can continue to incur costs. Some services have additional charges even when they are not receiving requests.

Free-tier eligibility and limits change over time. Check the current terms rather than assuming a service is free.

## 18. Incident Simulation: The API Suddenly Returns AccessDenied

**Situation:** Your Spring Boot API previously uploaded invoices successfully. After a deployment, uploads start failing with an AWS authorization error.

### Step 1 — Establish the impact

Determine:
- Which endpoint fails?
- Does every request fail, or only uploads?
- Did the issue begin after a deployment or configuration change?
- Are reads and writes affected differently?

### Step 2 — Verify the active identity

Confirm which role or credential source the application is actually using.

A common mistake is assuming the deployed workload uses the same credentials as a developer's laptop.

### Step 3 — Inspect the permission scope

Check:
- The action requested.
- The bucket and object path.
- The role's identity-based policies.
- Applicable bucket policies.
- Permissions boundaries or organization-level restrictions.
- Relevant encryption-key permissions, if the operation uses a customer-managed key.

### Step 4 — Inspect recent changes

Compare:
- Role assignments.
- Policy changes.
- Bucket or key policies.
- Environment configuration.
- Deployment identity and runtime environment.

### Step 5 — Remediate safely

Restore only the required permission or correct the identity configuration.

Avoid granting unrestricted access to make the error disappear.

### Step 6 — Prevent recurrence

Add deployment checks, permission tests where feasible, clear application error logging, and documented ownership of the IAM role.

The goal is not just to restore service. It is to preserve least privilege while preventing the same incident.

## 19. Incident Simulation: Unexpected Cloud Spending

**Situation:** Your learning project has generated a much larger bill than expected.

Investigate:
1. Which account and region incurred the charges?
2. Which services and resources contributed to the cost?
3. Were resources left running after a lab?
4. Did data transfer, storage, or request volume exceed expectations?
5. Were credentials compromised or used unexpectedly?
6. Are cost and usage reports available for the relevant period?

If compromise is suspected, follow the organization's security process to contain the incident, investigate access, and rotate or revoke credentials where necessary.

Prevent recurrence with budgets, cost visibility, resource ownership tags where appropriate, cleanup procedures, and carefully scoped access.

Do not rely on budget notifications alone as a security or hard-spending control.

## 20. FAANG-Style Interview Questions

### Q1. What is AWS?

AWS is a cloud platform providing computing, storage, networking, databases, identity, monitoring, and other services that can be provisioned and managed programmatically.

### Q2. Why might a company choose cloud infrastructure over purchasing physical servers?

Cloud can reduce upfront infrastructure investment, provide managed services, and enable elastic provisioning. It also introduces usage-based costs and requires cloud-specific security and operational practices.

### Q3. What is the difference between a region and an Availability Zone?

A region is a geographic deployment area. An Availability Zone is an isolated location within a region. Multi-AZ designs can improve resilience against certain zonal failures.

### Q4. Does deploying in multiple Availability Zones guarantee high availability?

No. Availability depends on the full architecture, including application capacity, health checks, data stores, network paths, and shared dependencies.

### Q5. What is the shared responsibility model?

AWS operates and secures the underlying cloud infrastructure, while customers retain responsibilities for security in the cloud. The exact division depends on the service.

### Q6. What is IAM?

Identity and Access Management controls which identities can perform which actions on which AWS resources.

### Q7. What is the difference between authentication and authorization?

Authentication establishes identity. Authorization determines which operations that identity is permitted to perform.

### Q8. What is an IAM role?

An IAM role is an identity with associated permissions that an authorized principal can assume, typically receiving temporary credentials.

### Q9. Why use IAM roles for applications instead of embedding access keys?

Role-based credential mechanisms can provide temporary, renewable credentials and avoid hardcoding long-lived secrets in application source code.

### Q10. What is least privilege?

Granting only the permissions necessary for a task, scoped as narrowly as practical.

### Q11. What is an explicit deny?

An applicable explicit deny in AWS authorization policy evaluation overrides an applicable allow.

### Q12. Why is a public database dangerous?

It increases the database's exposure to network attacks and unauthorized access attempts. Restricting network access, using strong authentication, and applying least privilege reduces risk.

### Q13. Does a private subnet automatically secure a database?

No. Network placement is one control. Security groups, routing, database authentication, authorization, encryption, and monitoring also matter.

### Q14. What happens if an EC2 instance fails?

The instance stops serving requests. Recovery or replacement depends on the configured deployment and orchestration approach. A load balancer can route traffic to healthy targets if sufficient capacity remains.

### Q15. Why might two healthy application instances still fail?

They may depend on a common failed database, shared network path, external service, or other single point of failure.

### Q16. What is elasticity?

The ability to adjust resources to match demand. It requires appropriate service capabilities and configuration; it is not automatic for every workload.

### Q17. What is the difference between a managed database and a database on EC2?

A managed database service operates more of the underlying database infrastructure and maintenance. A database on EC2 gives you more direct control but also more operational responsibility.

### Q18. Why is multi-region deployment harder than multi-AZ deployment?

Multi-region designs introduce additional challenges involving data replication, consistency, routing, failover, recovery, and cross-region costs.

### Q19. Why can cloud costs increase unexpectedly?

Unneeded resources, overprovisioning, data transfer, retained storage, high request volume, and unexpected usage can all increase costs.

### Q20. How would you deploy a secure Spring Boot API on AWS?

Choose an appropriate compute and networking design, expose only the required entry point, restrict database access, use workload roles and least privilege, store secrets appropriately, enable monitoring, plan recovery, and track costs.

---

# Capstone — Design Your First AWS Backend

## Scenario

You are deploying an Orders API built with Spring Boot and PostgreSQL.

The API must:
- Accept HTTPS requests.
- Store order data durably.
- Upload invoices to S3.
- Avoid embedding AWS credentials in code.
- Limit database network exposure.
- Provide useful logs and metrics.
- Remain recoverable after a component failure.

### Task 1 — Draw the architecture

Include:
- A public entry point.
- Application compute.
- PostgreSQL.
- An S3 bucket.
- An application IAM role.
- Network boundaries.
- Monitoring and logging.

### Task 2 — Define access

Write down:
- What the engineer deploying the API needs to do.
- What the running API needs to do.
- What the database needs to accept.
- Which permissions should not be granted.

### Task 3 — Analyze failures

Explain what happens when:
- An application instance fails.
- PostgreSQL becomes unavailable.
- S3 permissions are removed.
- An Availability Zone becomes unavailable.
- The AWS region becomes unavailable.

### Task 4 — Estimate operational responsibilities

For each component, list:
- What AWS operates.
- What your team configures.
- What your team must monitor.
- What your team must recover.

### Task 5 — Define the minimum viable production baseline

Write a checklist for identity, network access, secrets, logs, metrics, backups, and cost controls.

No paid deployment is required to complete the design exercise.

## Mastery Assessment

Before moving to Chunk 2, answer these questions in your own words:

1. Why does cloud computing not eliminate infrastructure engineering?
2. Why is a multi-AZ design usually a different first step from a multi-region design?
3. What is the difference between an IAM user and an IAM role?
4. Why should an API not receive `s3:*` permissions by default?
5. Why are application identity and network isolation separate security controls?
6. What can still fail when two application instances are healthy?
7. Why is a cloud budget notification not a guaranteed spending cap?
8. How would you investigate an `AccessDenied` error without granting administrator access?

## Completion Checklist

- [ ] I can explain cloud computing and its trade-offs.
- [ ] I understand regions, Availability Zones, and edge locations.
- [ ] I can explain the shared responsibility model.
- [ ] I understand AWS accounts and resources.
- [ ] I can distinguish IAM users, groups, roles, and policies.
- [ ] I understand least privilege and temporary credentials.
- [ ] I can sketch a basic AWS backend architecture.
- [ ] I can explain basic availability and cost risks.
- [ ] I can reason through an authorization incident.

## Handbook Completion Protocol

Save this chapter as:

`content/aws/01-aws-cloud-foundations-iam-backend-architecture.md`

This is **Chunk 1 of 6**, not a standalone final handbook. Preserve the source as Markdown and do not generate a chunk PDF.

After all six AWS chapters are saved and verified, combine them into one complete AWS handbook:

`docs/aws/BEH_AWS_COMPLETE_HANDBOOK.pdf`

Update the main README only after verifying the source and final PDF. Commit only when the complete AWS source content and final PDF are verified, using the required commit message:

`AWS done`

No repository operation, PDF generation, or Git commit is implied by this chapter.
