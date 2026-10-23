# AWS — Chunk 4 of 6: Storage, Managed Databases, Backups & High Availability

## Backend Engineering Tools & Infrastructure Handbook · Cloud Engineering Track

**Source file:** `content/aws/04-aws-storage-s3-ebs-efs-rds-backups-high-availability.md`

---

## Learning Objectives

By the end of this chapter, you should be able to:

- Choose between Amazon S3, EBS, and EFS based on access patterns and requirements.
- Explain why application servers should not store durable business data on their local disks.
- Understand Amazon RDS, Multi-AZ deployments, read replicas, and automated backups.
- Design a basic Spring Boot and PostgreSQL architecture on AWS.
- Explain durability, availability, consistency, RPO, and RTO.
- Diagnose common database connection, storage, and recovery failures.
- Discuss database scaling and disaster recovery in backend engineering interviews.

---

# Layer 1 — Fundamentals & Mental Models

## 1. The Three Things Your Backend Needs to Store

Imagine that you are building an e-commerce backend.

Your system stores:

- Customer orders and payment records.
- Product images and downloadable invoices.
- Temporary files and application logs.
- Database backups.
- Files shared between application instances.

These are not all the same kind of data. They have different access patterns, durability requirements, and performance characteristics.

AWS provides different storage services for different jobs:

### 1. Amazon S3 — Object Storage
Store objects such as images, PDFs, exports, log archives, and backups. Applications access objects through APIs rather than treating the bucket as an ordinary disk.

### 2. Amazon EBS — Block Storage
Attach a volume to an EC2 instance and use it like a disk. Common uses include operating-system root volumes and workloads requiring low-latency block-device semantics.

### 3. Amazon EFS — Shared File Storage
A managed network file system that multiple compatible compute clients can access concurrently over NFS. Useful when applications genuinely need shared filesystem semantics across multiple instances.

### 4. Amazon RDS — Managed Relational Databases
Run supported relational database engines, including PostgreSQL, while AWS manages many operational tasks such as infrastructure provisioning, automated patching, backups, and configured failover capabilities.

### Storage Service Mapping

| Data Type | Access Pattern | Durability Needs | Recommended AWS Service |
|---|---|---|---|
| **User avatars & invoice PDFs** | REST API / SDK / HTTP | 99.999999999% (11 9s) | Amazon S3 |
| **OS filesystem & runtime binaries** | Local block storage | Instance-bound / snapshotable | Amazon EBS |
| **Legacy CMS uploads shared by nodes** | POSIX network filesystem | Multi-AZ shared concurrent | Amazon EFS |
| **Orders, accounts, financial ledgers** | ACID SQL transactions | Managed Multi-AZ / PITR | Amazon RDS (PostgreSQL) |

The core principle is simple:

> **Core Principle:** Choose storage according to the data's access pattern and durability requirements, not merely according to which service you already know.

---

## 2. Object Storage versus Block Storage versus File Storage

A useful analogy:

- **Object storage:** A managed package-delivery system. You identify an object and retrieve or update it through an API.
- **Block storage:** A disk attached directly to a computer. The operating system and applications read and write raw blocks.
- **File storage:** A shared filing cabinet with directories and filenames that authorized clients can access through a filesystem interface.

| Property | Amazon S3 | Amazon EBS | Amazon EFS |
|---|---|---|---|
| **Storage model** | Objects (key-value + metadata) | Blocks (fixed-sized chunks) | Files and directories (POSIX) |
| **Typical access** | HTTP/REST API or AWS SDK | Attached virtual block device | Network filesystem (NFSv4) |
| **Multiple application servers** | Unlimited concurrent API access | Attached to one instance at a time (multi-attach has strict limits) | Concurrent access from thousands of instances |
| **Typical use** | Images, documents, exports, archives, data lakes | Instance OS disks, self-hosted databases | Shared application directories, CMS, batch processing |
| **Filesystem semantics** | No ordinary mounted filesystem by default | Yes, after formatting and mounting | Yes, fully POSIX compliant |
| **Common mistake** | Treating S3 like a normal POSIX disk | Assuming EBS automatically protects data from every failure | Using shared filesystem storage when object storage would be simpler |

S3 is not a drop-in replacement for a filesystem, and EFS is not automatically the best choice for every shared file.

---

## 3. Amazon S3: Store Objects, Not Server-Local Files

Suppose your Spring Boot application accepts product images.

A basic design might be:

```text
Client
  |
  v
Spring Boot API
  |
  | Upload object using an authorized AWS SDK
  v
Amazon S3 bucket
  |
  v
Object key and metadata recorded in PostgreSQL
```

Instead of storing each image inside an EC2 instance's local directory, the application uploads it to S3.

PostgreSQL stores the relevant business metadata, such as:

- Product ID.
- Object key.
- Content type (`image/webp`, `application/pdf`).
- Upload timestamp.
- Ownership or access-control information.

The actual image bytes live durably in S3.

### What is a bucket?

A bucket is an S3 container for objects. Each object has a **key**, which identifies it within that bucket.

For example:

```text
Bucket: shop-product-media
Object key: products/1042/front.webp
Object key: products/1042/side.webp
Object key: invoices/2026/order-8931.pdf
```

The slash-separated names are conventions for organizing object keys. They do not imply that S3 is an ordinary hierarchical filesystem.

### What does S3 provide?

S3 offers object storage with durability and availability characteristics that depend on the service and storage class. Common capabilities include:

- **Object versioning:** Protects against accidental overwrites and deletions.
- **Lifecycle rules:** Automatically transitions older objects to cheaper tiers (e.g., S3 Standard $\to$ S3 Glacier) or expires them.
- **Encryption:** Server-side encryption with AWS managed keys (SSE-S3) or customer KMS keys (SSE-KMS).
- **Access policies:** Bucket policies and IAM policies for fine-grained authorization.
- **Event notifications:** Trigger AWS Lambda functions or SQS messages on object creation.
- **Retention controls:** S3 Object Lock for WORM (Write Once, Read Many) compliance.
- **Storage classes:** S3 Standard, S3 Intelligent-Tiering, S3 Standard-IA, S3 Glacier Instant Retrieval, S3 Glacier Flexible, and S3 Glacier Deep Archive.

These features solve different problems. Versioning can help recover overwritten objects, while lifecycle policies can transition or expire eligible objects according to configured rules.

### S3 security basics

A production bucket should not be made public just because the application needs to upload files.

Use:

- **Block Public Access:** Keep all four Block Public Access settings enabled unless direct public website hosting is strictly required.
- **IAM roles:** Use instance profiles and narrowly scoped IAM permissions.
- **Bucket policies:** Enforce TLS-only transport (`aws:SecureTransport: "true"`).
- **Encryption:** Encrypt at rest and enforce HTTPS in transit.
- **Appropriate retention:** Apply lifecycle and versioning policies.
- **Logging and monitoring:** Enable S3 server access logging and AWS CloudTrail data events for sensitive workloads.

Avoid embedding long-lived AWS access keys in source code.

### Direct uploads: a better scaling pattern

For large uploads, routing every byte through your Spring Boot API may waste application bandwidth, memory, and compute resources.

A common alternative is a **presigned S3 URL**:

```text
1. Client asks API to start an upload (provides filename, content type, size).
2. API validates the request and authorizes the user.
3. API creates a short-lived presigned URL (e.g., valid for 15 minutes).
4. Client uploads bytes directly to S3 via HTTP PUT.
5. API verifies the resulting object and records metadata in PostgreSQL.
```

A presigned URL grants time-limited access to a specific operation under the permissions of the signer. Treat it as a bearer credential while it is valid.

The backend should still enforce ownership, allowed content types and sizes, expected object keys, and any required scanning or validation. A successful upload does not automatically mean the file is safe.

---

## 4. EBS: Persistent Block Storage for EC2

Consider an EC2 instance running a Linux operating system. Its root filesystem commonly resides on an EBS volume.

You can also attach additional EBS volumes for application data or supported workloads.

Important concepts:

- **Volume:** The network-attached block-storage resource (e.g., `gp3`, `io2`).
- **Snapshot:** A point-in-time, incremental backup of an EBS volume stored durably in S3.
- **Attachment:** The association between a volume and a supported instance in the same Availability Zone.
- **IOPS and throughput:** Performance characteristics that influence storage behavior (e.g., `gp3` baseline of 3,000 IOPS and 125 MB/s).
- **Encryption:** Transparent protection of volume data and subsequent snapshots using AWS KMS.

### Why EBS is not the same as an instance

An instance and its storage have separate lifecycle considerations.

For example, an instance may be terminated while a separately configured data volume is retained. Conversely, a root volume may be deleted when the instance is terminated if its configuration specifies that behavior (`DeleteOnTermination = true`).

Never assume that terminating an instance either always deletes all attached storage or always preserves it. Inspect the actual configuration.

### EBS snapshots

Snapshots can support recovery and creation of new volumes. They are not a complete backup strategy for every application.

For a database, a storage snapshot alone may not provide the required application-consistent recovery point unless the database and snapshot process are coordinated appropriately (e.g., freezing writes or flushing write buffers).

Database-native backups, transaction-log recovery, and tested restoration procedures may be necessary to satisfy business recovery requirements.

---

## 5. EFS: When Multiple Servers Need Shared Files

Suppose you have three EC2 instances behind an ALB.

A user uploads a file to a directory on EC2 A. A later request is routed to EC2 B, which does not have that local file.

This is a classic distributed-application problem.

**Amazon EFS** provides shared network filesystem access to compatible clients:

```text
EC2 A ----\
           \
EC2 B -------> Shared Amazon EFS Filesystem (NFSv4)
           /
EC2 C ----/
```

All authorized clients can access files concurrently through standard POSIX file operations.

However, shared files introduce operational questions:

- Who can read or modify each file? (POSIX UID/GID ownership and permissions)
- What happens when two instances update the same file? (File locking and race conditions)
- Is the application's filesystem access pattern compatible with network storage latency?
- What are the latency and throughput implications?
- Does the workload actually require shared filesystem semantics?

For images, PDFs, and static downloadable content, S3 is often the more natural and cost-effective option. EFS is valuable when the application specifically needs a POSIX shared filesystem.

---

## 6. Amazon RDS: Managed Relational Databases

Now consider the Orders API.

The application needs transactions, relational constraints, joins, indexes, and SQL queries. PostgreSQL is a reasonable database choice.

You could install PostgreSQL directly on an EC2 instance, but then your team is responsible for many operational tasks:

- Database installation, configuration, and upgrades.
- Operating-system patching and security maintenance.
- Backup scheduling, verification, and retention.
- Storage provisioning, auto-scaling, and monitoring.
- Replication setup and failover automation.
- Disaster recovery testing.
- Database process crashes and host hardware failures.

**Amazon RDS (Relational Database Service)** manages much of the underlying database infrastructure and supports managed relational database engines, including PostgreSQL.

You remain responsible for database schema design, query performance, access control, application connection behavior, and selecting appropriate availability and recovery settings.

### A basic architecture

```text
Clients
   |
   v
Application Load Balancer (Public Subnets)
   |
   v
Spring Boot on EC2 instances (Private Application Subnets)
   |
   | Private database connection (Port 5432)
   v
Amazon RDS for PostgreSQL (Private Database Subnets)
```

The application instances should normally reach the database over private networking, with security-group rules that allow the required database traffic.

For PostgreSQL, the default port is `5432`, unless the database is configured differently.

### RDS does not eliminate database engineering

Managed infrastructure does not automatically solve:

- Missing indexes or poor query planning.
- Slow queries consuming all CPU.
- Lock contention and deadlocks.
- Connection-pool exhaustion.
- Bad transaction boundaries and long-running transactions.
- Incorrect isolation level assumptions.
- Schema migration failures.
- Application-level data corruption.

RDS reduces some infrastructure-management work. It does not replace understanding PostgreSQL.

---

## 7. Multi-AZ Deployments versus Read Replicas

These concepts are easy to confuse in interviews and architecture discussions.

### Multi-AZ: Availability and Failover

A Multi-AZ RDS deployment is designed to improve availability by maintaining a synchronous standby replica in a different Availability Zone.

- **Primary Goal:** High availability and automatic disaster recovery.
- **Replication:** Synchronous replication from primary to standby.
- **Traffic:** The standby does **not** serve ordinary read traffic; it is strictly a failover target.
- **Failover:** Automatic failover typically completes in 60–120 seconds. DNS endpoint updates automatically to point to the new primary.
- **Impact on writes:** Minor latency overhead on commits due to synchronous cross-AZ replication.

### Read Replica: Read Scaling

A read replica is an asynchronous copy of the primary database designed to offload read-heavy query traffic.

- **Primary Goal:** Horizontal read scalability and performance.
- **Replication:** Asynchronous replication from primary to replica.
- **Traffic:** Replicas actively serve read-only queries (`SELECT`).
- **Failover:** Not automatically a synchronous failover standby; can be manually promoted to a standalone database if needed.
- **Replication lag:** Asynchronous replication means replicas can lag behind the primary, resulting in stale reads.

> [!IMPORTANT]
> **Remember This Distinction:**
> - **Multi-AZ:** Primary goal is to improve database availability and automatic failover behavior (synchronous replication to standby; standby does not serve reads).
> - **Read Replica:** Primary goal is to serve additional read traffic horizontally or support a planned cross-region replication/recovery strategy (asynchronous replication; serves active read queries).

### Feature Comparison Matrix

| Property | Multi-AZ Standby | Read Replica |
|---|---|---|
| **Primary Goal** | High availability & fault tolerance | Read scalability & reporting |
| **Replication Type** | Synchronous | Asynchronous |
| **Serves Read Traffic?** | No | Yes (Read-Only) |
| **Failover Behavior** | Automatic failover to standby | Manual promotion (or Aurora auto-failover) |
| **Number of Copies** | 1 standby in another AZ | Up to 15 (RDS PostgreSQL) |
| **Cross-Region Support** | No (within same Region) | Yes (Cross-Region Read Replicas) |
| **Performance Impact** | Small write latency overhead | None on primary writes |

Neither feature eliminates the need for regular backups.

---

## 8. Automated Backups and Point-in-Time Recovery

Imagine that a faulty deployment runs a SQL statement that accidentally deletes or truncates important tables.

High availability (Multi-AZ) keeps the database reachable, but it does **not** restore the deleted data—the destructive SQL query synchronously replicates to the standby immediately!

This is why **availability and recoverability are completely different properties**.

RDS automated backups support recovery within the configured backup retention period (1 to 35 days).

### Point-in-Time Recovery (PITR)
RDS continuously archives database transaction logs (WAL in PostgreSQL) to S3 every 5 minutes. Using automated daily snapshots plus transaction logs, you can restore your database to any specific second within your retention window, up to the last 5 minutes.

A complete recovery strategy should consider:

- Automated backup retention periods.
- Manual snapshots for long-term archiving before major releases.
- Transaction-log and point-in-time recovery capabilities.
- Cross-Region backup replication for disaster recovery.
- KMS encryption-key access across regions/accounts.
- Restore duration and recovery validation procedures.
- Protection against accidental deletion (enable Deletion Protection on RDS).

> [!TIP]
> A backup that has never been tested in a restoration drill is an unverified recovery assumption.

---

## 9. Durability, Availability, RPO, and RTO

These four concepts appear frequently in production engineering and system-design interviews:

### Definitions

- **Durability:** The probability that stored data survives without loss or corruption over time (e.g., S3's 99.999999999% durability).
- **Availability:** The percentage of time a system is operational and able to respond successfully to requests (e.g., 99.95% uptime).
- **Recovery Point Objective (RPO):** The maximum acceptable amount of data loss measured in time (e.g., "we can tolerate losing at most 5 minutes of data").
- **Recovery Time Objective (RTO):** The maximum acceptable duration of downtime before service is restored (e.g., "the database must be back online within 30 minutes").

### Target Scenario

Suppose a business requires:
- **RPO:** 5 minutes.
- **RTO:** 30 minutes.

Your recovery strategy must aim to lose no more than five minutes of data and restore the service within thirty minutes under the agreed scenario.

These are targets, not guarantees that every AWS recovery operation will finish within the specified time. The architecture and recovery procedures must be tested against realistic failures.

### Why availability does not equal durability

- **High Availability, Low Durability:** A database cluster is online and reachable, but an application bug executes `UPDATE orders SET status = 'CANCELLED'`. The database is 100% available, but data integrity is destroyed.
- **Low Availability, High Durability:** An earthquake disrupts power to an entire data center. The database is completely offline for 2 hours (0% availability), but every committed transaction is preserved on durable storage with 0 data loss once power returns.

Production systems must be designed for both.

---

# Layer 2 — Practical Engineering & Workflows

## 10. A Sensible Storage Architecture for the Orders API

Use the following separation of responsibilities:

| Data Element | Suggested AWS Service | Architecture Rationale |
|---|---|---|
| **Orders, customers, inventory** | RDS for PostgreSQL | Relational transactions, foreign keys, and ACID guarantees |
| **Product images & avatars** | Amazon S3 | Highly durable object storage, direct CDN integration |
| **Generated invoice PDFs** | Amazon S3 | Immutable document storage with presigned URL access |
| **EC2 OS root disk** | Amazon EBS (`gp3`) | Low-latency local block storage for OS and JVM binaries |
| **Shared filesystem (legacy)** | Amazon EFS (if required) | POSIX-compliant multi-instance shared directory |
| **Database recovery points** | RDS Backups & Snapshots | PITR point-in-time recovery and snapshot archiving |

Do not put every kind of data into one service simply to reduce the number of services in your architecture.

Likewise, do not introduce EFS if S3 already satisfies the application's file-storage requirements.

---

## 11. Spring Boot Database Configuration

A Spring Boot application commonly receives its database configuration through environment variables or AWS Systems Manager Parameter Store:

```yaml
spring:
  datasource:
    url: ${DB_URL}
    username: ${DB_USERNAME}
    password: ${DB_PASSWORD}
    hikari:
      maximum-pool-size: 10
      minimum-idle: 5
      connection-timeout: 3000
      idle-timeout: 600000
      max-lifetime: 1800000
```

The example uses Spring Boot's default HikariCP connection pool settings.

The pool size is illustrative, not a universal production recommendation. Tune it using database capacity, instance count, request concurrency, transaction duration, and measured behavior.

A production configuration should also consider TLS requirements (`sslmode=verify-full`), credential rotation, secret retrieval via AWS Secrets Manager, connection validation, transaction timeouts, and database failover behavior.

### Why the connection pool matters

Suppose:
- 4 EC2 instances run the application.
- Each instance allows up to 10 database connections.

The application tier could request up to:

$$4 \times 10 = 40 \text{ connections}$$

If the Auto Scaling Group scales out to 12 instances during a traffic surge, the theoretical pool maximum becomes:

$$12 \times 10 = 120 \text{ connections}$$

This does not mean every connection is always open. It means the potential database connection demand increases as the application tier scales.

The database's own capacity (`max_connections` parameter in PostgreSQL) and any connections used by administrative jobs, migration tools, or background workers must also be considered. If total pool demand exceeds `max_connections`, connections are refused and the API returns 500 errors.

---

## 12. Use the AWS SDK for Java to Upload to S3

A simplified example using AWS SDK for Java v2:

```java
package com.example.orders.storage;

import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;

import java.nio.file.Path;

public class ObjectStorageService {
    private final S3Client s3;

    public ObjectStorageService(S3Client s3) {
        this.s3 = s3;
    }

    public void upload(String bucket, String key, Path file) {
        PutObjectRequest request = PutObjectRequest.builder()
                .bucket(bucket)
                .key(key)
                .contentType("image/webp")
                .build();

        s3.putObject(request, RequestBody.fromFile(file));
    }
}
```

This illustrates the upload operation. A production implementation should also address:

- Bucket and key authorization.
- Input validation and file size limits.
- Error handling and bounded retries with exponential backoff.
- Upload timeouts and cancellation.
- Content type and required metadata tags.
- Server-side encryption headers (`ServerSideEncryption.AWS_KMS`).
- Safe handling of partial or duplicate application workflows.
- Multipart-upload behavior for files larger than 100 MB.

Configure the SDK to use its default credential provider chain (`DefaultCredentialsProvider.create()`). In AWS, an IAM instance profile or container task role is strongly preferred over credentials embedded in code.

---

## 13. AWS CLI: Inspect Storage and Database Resources

These commands are read-only inspection commands. They assume that you have the AWS CLI configured for the intended account and Region and that your identity has the required permissions.

### List S3 buckets

```bash
aws s3api list-buckets \
  --query 'Buckets[].Name' \
  --output table
```

### Inspect objects in a specific bucket

```bash
aws s3api list-objects-v2 \
  --bucket YOUR_BUCKET_NAME \
  --max-items 20
```

### List RDS instances

```bash
aws rds describe-db-instances \
  --query 'DBInstances[].{
    Identifier:DBInstanceIdentifier,
    Engine:Engine,
    Status:DBInstanceStatus,
    MultiAZ:MultiAZ,
    Storage:AllocatedStorage,
    Endpoint:Endpoint.Address
  }' \
  --output table
```

### Inspect automated backups

```bash
aws rds describe-db-instances \
  --query 'DBInstances[].{
    Identifier:DBInstanceIdentifier,
    BackupRetentionDays:BackupRetentionPeriod,
    BackupWindow:PreferredBackupWindow
  }' \
  --output table
```

### Inspect RDS snapshots

```bash
aws rds describe-db-snapshots \
  --query 'DBSnapshots[].{
    Snapshot:DBSnapshotIdentifier,
    Status:Status,
    Created:SnapshotCreateTime,
    Source:DBInstanceIdentifier
  }' \
  --output table
```

### Inspect EBS volumes

```bash
aws ec2 describe-volumes \
  --query 'Volumes[].{
    ID:VolumeId,
    State:State,
    SizeGiB:Size,
    Encrypted:Encrypted,
    AZ:AvailabilityZone
  }' \
  --output table
```

These commands inspect resources. They do not create, modify, delete, or restore infrastructure.

---

## 14. How to Reason About an S3 Upload Failure

Suppose users cannot upload product images.

Work through the request path systematically:

1. **Verify API receipt:** Confirm that the API received the upload request and logged the entry point.
2. **Inspect SDK exception:** Check application logs for the specific AWS SDK exception class (`S3Exception`, `SdkClientException`).
3. **Verify bucket & Region:** Confirm the bucket name exists and the client is querying the correct AWS Region.
4. **Confirm IAM identity:** Confirm the active workload identity is the expected IAM instance role via STS (`aws sts get-caller-identity`).
5. **Review permissions & policies:** Verify the IAM policy allows `s3:PutObject` on `arn:aws:s3:::bucket-name/*`. Check if bucket policies contain explicit `Deny` statements.
6. **Check KMS key permissions:** If using SSE-KMS, ensure the instance role has `kms:GenerateDataKey` and `kms:Decrypt` permissions on the KMS key.
7. **Check network & routing:** If running in a private subnet, ensure there is an active S3 Gateway VPC Endpoint or NAT Gateway route.
8. **Verify idempotency & retries:** Ensure partial uploads do not leave broken database records.

A `403 Forbidden` response indicates access restrictions, but the exact cause depends on IAM, bucket policies, KMS keys, or organization SCPs (Service Control Policies).

---

## 15. How to Reason About a Database Connection Failure

Suppose the API starts returning database connection errors (`Connection refused`, `Connection timeout`).

Check in this order:

1. **Database status:** Is the RDS instance in the `available` state, or is it modifying, rebooting, or failing over?
2. **Configuration accuracy:** Is the application using the correct RDS DNS endpoint, port (5432), database name, and credentials?
3. **Security groups:** Does the RDS security group contain an inbound rule allowing TCP 5432 from the EC2 security group ID?
4. **Subnet & routing:** Are application and database subnets within the same VPC, and do route tables allow local communication?
5. **Connection pool exhaustion:** Has HikariCP exhausted its maximum pool size? Check `ActiveConnections` vs. `max_connections` in RDS metrics.
6. **Database CPU & memory:** Is the database thrashing due to memory exhaustion (OOM killer) or CPU saturation?
7. **Failover recovery:** Did a Multi-AZ failover recently occur? Were stale connection pool sockets purged?
8. **Timeouts:** Are acquisition and query timeouts configured reasonably?

Separate a network failure (timeout) from an authentication failure (`FATAL: password authentication failed`) and from pool exhaustion (`Connection is not available, request timed out`).

---

## 16. A Database Failover Workflow

Imagine the primary database experiences a failure in a configured Multi-AZ RDS deployment.

The application will experience connection errors while failover takes place (typically 60–120 seconds).

A resilient application should:

```text
1. Detect broken connections -> HikariCP marks connection as invalid and evicts from pool
2. Bounded backoff retry -> Application pauses brief intervals before attempting new connections
3. DNS resolution refresh -> Java/JVM DNS cache respects low TTL (<= 5 seconds) to resolve new primary IP
4. Reconnection handshake -> New TCP connection established to promoted primary standby
5. Idempotent retry logic -> Safely retry read queries or idempotent writes with idempotency keys
6. Resume normal traffic -> Alert operators and monitor error rates until steady state is restored
```

A database failover does not guarantee that an in-flight transaction completed. For a payment or order-creation request, the client may not know whether the transaction committed before the connection failed.

This is an application-level correctness problem, not just a networking problem.

An **idempotency key** or deduplication table can help prevent a client retry from creating duplicate orders or double payments.

---

## 17. Backup Restoration Lab

Do not perform a restore against production just to learn the workflow.

Use a disposable test environment or a documented tabletop exercise.

### Exercise Scenario
Your database contains order records. A deployment script accidentally deletes orders created during the previous hour.

Define:

1. **Available recovery mechanisms:** Automated daily snapshots + continuous WAL transaction logs (PITR).
2. **Business RPO target:** Maximum 5 minutes of data loss.
3. **Business RTO target:** Maximum 30 minutes of downtime.
4. **Restoration procedure:** Restore the snapshot to a **separate, new database instance** (`orders-db-restored`) at the exact minute prior to the deletion script execution.
5. **Data validation:** Connect to `orders-db-restored`, verify table row counts and schema integrity, and export the deleted rows.
6. **Approval & reconciliation:** Obtain authorization from the lead architect/DBA. Re-insert the missing rows into the live production database (`orders-db-prod`) without overwriting new transactions created in the interim.
7. **Teardown:** Terminate `orders-db-restored` once validation and reconciliation are complete to avoid ongoing infrastructure costs.

> [!WARNING]
> Never assume that restoring a snapshot is equivalent to replacing a live database. In a live production system, simply swapping endpoints causes all writes that occurred between the incident and the restore time to be lost forever!

---

# Layer 3 — Production Engineering & Interview Mastery

## 18. Production Incident Simulations

### Incident A: Product images disappear after an EC2 deployment

**Symptoms:** Images uploaded yesterday return 404 errors after the Auto Scaling Group replaces instances during an application update.

- **Root Cause:** The application was configured to write uploaded files to a local directory (e.g., `/var/app/uploads/`) on the instance's ephemeral or EBS root disk. When instances were replaced, the local disks were destroyed.
- **Resolution:**
  1. Refactor the application service to upload files to an S3 bucket using the AWS SDK.
  2. Store only the S3 bucket name and object key in PostgreSQL.
  3. Update existing records and verify all active instances read from S3.
  4. Enable S3 Versioning and Default Encryption on the bucket.

---

### Incident B: Database connections are exhausted

**Symptoms:** During a flash sale, API response times spike to 30 seconds and the application logs display:
`java.sql.SQLTransientConnectionException: HikariPool-1 - Connection is not available, request timed out after 3000ms.`

- **Root Cause:** The Auto Scaling Group scaled from 2 to 10 instances. Each instance had `maximum-pool-size: 30`, creating up to 300 concurrent connection requests. RDS PostgreSQL instance type was `db.t4g.small` with `max_connections = 150`.
- **Resolution:**
  1. Immediately reduce `maximum-pool-size` to 10 per instance in configuration.
  2. Implement **Amazon RDS Proxy** between the application instances and RDS to pool and multiplex database connections efficiently.
  3. Add CloudWatch alarms on RDS `DatabaseConnections` metric at 80% of `max_connections`.
  4. Evaluate resizing the RDS instance class if CPU or query load warrants it.

---

### Incident C: Multi-AZ failover causes a persistent API outage

**Symptoms:** RDS completed automatic Multi-AZ failover within 90 seconds, but the Spring Boot application continues to throw connection exceptions for over 30 minutes.

- **Root Cause:** The JVM permanently cached the DNS resolution of the RDS endpoint to the old primary IP address (`networkaddress.cache.ttl` was set to `-1` or default infinite).
- **Resolution:**
  1. Configure the JVM DNS cache TTL to a low value (e.g., 5 to 10 seconds):
     `-Dnetworkaddress.cache.ttl=10`
  2. Configure HikariCP `maxLifetime: 1800000` (30 minutes) and `connectionTimeout: 3000`.
  3. Restart application instances to purge stale JVM DNS cache.

---

### Incident D: A backup exists, but recovery fails

**Symptoms:** During a disaster recovery drill, the team attempts to restore a snapshot to a new region, but the operation fails.

- **Root Cause:** The snapshot was encrypted using the default AWS managed KMS key (`aws/rds`), which cannot be shared or used directly across regions.
- **Resolution:**
  1. Re-encrypt snapshots using a Customer Managed Key (CMK) configured for multi-region replication.
  2. Rehearse the snapshot copy and restore process monthly in automated testing.
  3. Verify that IAM restore permissions include the necessary KMS decrypt and create-grant rights.

---

### Incident E: A database is available but important data is missing

**Symptoms:** The API responds with HTTP 200, but orders created by users 30 minutes ago are missing from database tables.

- **Root Cause:** An engineer erroneously restored a snapshot directly over the production database or promoted an outdated read replica that had 30 minutes of replication lag.
- **Resolution:**
  1. Lock down destructive RDS actions using IAM Service Control Policies (SCPs) and require dual-operator approval.
  2. Enable Point-in-Time Recovery to recover lost transactions from transaction logs.
  3. Always restore to a temporary validation instance first, extract the delta, and merge.

---

## 19. Advanced Design Trade-Offs

### Should the application store files in PostgreSQL or S3?

For large files and user-generated media, S3 separates object storage from transactional metadata and prevents bloat in database backups, buffers, and replication streams.

PostgreSQL can still be appropriate for small binary data in some applications. The decision depends on transaction requirements, file size, query patterns, backup strategy, and operational complexity.

A common design stores file metadata and references in PostgreSQL while storing the bytes in S3.

This creates a **cross-service consistency problem**: the database transaction and S3 upload do not form one atomic distributed transaction. Your workflow must handle partial failures:
- *Failure mode:* S3 upload succeeds, but database transaction rolls back $\to$ Orphaned S3 object. Clean up via scheduled garbage-collection or S3 lifecycle rules.
- *Failure mode:* Database record written before upload, upload fails $\to$ Database points to non-existent object. Solved by uploading to S3 first with a temporary status, and confirming in DB only upon upload success.

### Should we use RDS or run PostgreSQL on EC2?

- **RDS is preferred** when the team values automated backups, automated multi-AZ failover, push-button scaling, managed security patching, and reduced operational overhead.
- **Self-managed PostgreSQL on EC2** is appropriate only when the workload requires unsupported operating-system access, custom PostgreSQL extensions not approved by AWS, specialized hardware, or when an organization already employs a dedicated, specialized DBA team.

### Should we add a read replica?

A read replica helps when read-heavy queries saturate database CPU and the application can tolerate **eventual consistency** (replication lag).

It will **not** improve write throughput. It also introduces the risk of stale reads: if a user submits an order and immediately redirects to an order confirmation page querying a lagging read replica, the user may see an empty page.

### Is Multi-AZ enough for disaster recovery?

No. Multi-AZ protects against a single Availability Zone failure within a single AWS Region. It does **not** protect against:
- Catastrophic regional AWS outages.
- Accidental table truncation or malicious SQL injection.
- Application-level bugs that corrupt data.

Comprehensive disaster recovery requires automated backups, point-in-time recovery, cross-region snapshot replication, and documented, tested runbooks with explicit RPO and RTO metrics.

---

## 20. FAANG-Style Interview Questions and Answers

### Q1. What is the difference between S3, EBS, and EFS?
S3 is object storage accessed via HTTP APIs for files, media, and backups. EBS is block storage attached directly to an EC2 instance as a virtual hard disk. EFS is an elastic, shared network file system accessible concurrently by multiple EC2 instances via NFS.

### Q2. Why should application instances avoid storing durable uploads locally?
EC2 instances in an Auto Scaling Group are ephemeral. If an instance terminates or scales in, local storage is destroyed. Externalizing state to S3 ensures persistence and makes instances fully interchangeable.

### Q3. What is an S3 bucket?
A globally unique container for storing objects in Amazon S3. Objects are identified within the bucket by unique alphanumeric keys and optional version IDs.

### Q4. What is a presigned URL?
A cryptographically signed URL generated by an authorized entity that allows temporary, direct upload or download access to an S3 object without exposing AWS credentials to the client.

### Q5. What is EBS used for?
EBS provides low-latency block storage volumes for EC2 instances, typically used for operating system filesystems, application runtimes, and local scratch space.

### Q6. When would you choose EFS over S3?
When legacy applications or multi-instance workloads strictly require standard POSIX filesystem semantics, directory traversal, file locking, and immediate consistency across multiple running servers.

### Q7. What does Amazon RDS manage?
RDS manages OS and database installation, automated minor version patching, automated backups, point-in-time recovery, disk auto-scaling, and synchronous Multi-AZ failover.

### Q8. What is Multi-AZ RDS?
A high-availability feature where RDS synchronously replicates database writes to an active standby instance in a different Availability Zone. If the primary fails, RDS automatically fails over to the standby.

### Q9. How does a read replica differ from a Multi-AZ standby?
A Multi-AZ standby is synchronous, does not serve read traffic, and is used strictly for automatic failover. A read replica is asynchronous, actively serves read traffic to scale queries, and does not provide automatic synchronous failover.

### Q10. Why do read replicas introduce consistency concerns?
Because replication is asynchronous, replicas may lag behind the primary by milliseconds or seconds, leading to stale reads (reading uncommitted or delayed data).

### Q11. What is point-in-time recovery?
An RDS feature that combines daily storage snapshots and 5-minute transaction log (WAL) backups to restore a database instance to any specific second within the backup retention period.

### Q12. What is the difference between availability and durability?
Availability measures the percentage of time a service is reachable and responsive to requests. Durability measures the probability that stored data is preserved without corruption or loss over time.

### Q13. What is RPO?
Recovery Point Objective: the maximum acceptable amount of data loss measured in time between the last recovery point and a disaster event.

### Q14. What is RTO?
Recovery Time Objective: the maximum acceptable duration of clock time to restore a system and resume operations after an outage.

### Q15. Why are backups necessary if the database has Multi-AZ enabled?
Multi-AZ replicates errors, corruption, and accidental deletions synchronously to the standby. Backups are required to recover historical states before the damaging operation took place.

### Q16. Why can a database failover break application requests?
Existing TCP sockets are abruptly severed during failover. Applications must have robust connection pool eviction, bounded retries, low JVM DNS TTL, and idempotent request handling to recover gracefully.

### Q17. How can scaling EC2 instances overload RDS?
Each new EC2 instance creates its own pool of open database connections. If the aggregate connections from all instances exceed `max_connections`, the database refuses new connections, crashing the API.

### Q18. What is the risk of storing file metadata in PostgreSQL and bytes in S3?
There is no two-phase commit across S3 and RDS. If an S3 upload succeeds but the subsequent database commit fails, an orphaned S3 object is created. Systems must implement compensation logic or reconciliation jobs.

### Q19. How would you test a database recovery strategy?
Perform a non-disruptive disaster recovery drill: restore a production snapshot to a test database instance, run validation queries to verify schema and record integrity, measure the elapsed time against RTO, and calculate data delta against RPO.

### Q20. How would you design storage for an e-commerce backend?
Store transactional order records in Amazon RDS PostgreSQL (Multi-AZ enabled with automated backups); store product images, videos, and generated invoice PDFs in Amazon S3; use CloudFront CDN for caching static assets; and attach EBS `gp3` volumes for instance operating systems.

---

## 21. Mastery Challenge

Design the data layer for an e-commerce API with these requirements:

- Orders and inventory must use transactional relational storage.
- Customers upload product images.
- The application runs across multiple EC2 instances in an Auto Scaling Group.
- Database availability is critical.
- Accidental deletion must be recoverable.
- Database connections must remain within a safe budget.
- Recovery targets are RPO 5 minutes and RTO 30 minutes.

Complete these tasks:

1. **Storage service for product images:** Choose Amazon S3 with SSE-S3 encryption and private bucket access.
2. **Database service and engine:** Choose Amazon RDS for PostgreSQL (Multi-AZ deployment).
3. **Why EC2-local files fail for shared uploads:** EC2 instances are ephemeral and dynamically scaled; local disks are destroyed on termination and cannot be shared across multiple instances.
4. **Roles of Multi-AZ and backups:** Multi-AZ provides automatic failover for high availability during hardware/AZ failures. Automated backups and PITR provide recovery from data corruption, accidental deletion, and disaster recovery.
5. **Failover effect on pooled connections:** Existing pool connections break with socket errors. The pool must evict broken connections and reconnect to the new primary using the updated DNS record.
6. **Connection pool calculation:** 6 instances $\times$ pool size 12 = **72 potential connections**. Must ensure `max_connections` on RDS exceeds 72 plus administrative headroom.
7. **Presigned upload URLs:** The backend issues a short-lived presigned PUT URL. The backend must enforce authentication, validate file size/type constraints, and verify upload completion before persisting the reference.
8. **Restoring a backup safely:** Restore to a separate new RDS instance, run validation queries, extract missing data, and merge into production.
9. **Achieving RPO 5m and RTO 30m:** Requires enabling automated continuous transaction log archiving (WAL to S3), testing automated restore scripts, and practicing runbook execution.
10. **Handling partial S3/DB failures:** Implement a two-step commit pattern: upload to S3 first with a `PENDING` metadata state, commit to PostgreSQL, and finalize or purge unreferenced S3 objects via an automated cleanup worker.

### Self-assessment

Score each item from 0 to 2:

| Skill | Score |
|---|---:|
| S3, EBS, and EFS distinctions | /2 |
| RDS fundamentals and connectivity | /2 |
| Multi-AZ versus read replicas | /2 |
| Backups and point-in-time recovery | /2 |
| RPO and RTO | /2 |
| Connection-pool capacity | /2 |
| Storage and IAM security | /2 |
| Incident diagnosis and recovery | /2 |

**Target:** At least 13/16, with no zero in backups, database connectivity, or recovery planning.

---

## Chapter Completion Protocol

**Chapter:** AWS Chunk 4 of 6

**Save as:** `content/aws/04-aws-storage-s3-ebs-efs-rds-backups-high-availability.md`

Do not generate a PDF yet. Once all six AWS chapters have been saved and verified, generate the single final AWS handbook:

`docs/aws/BEH_AWS_COMPLETE_HANDBOOK.pdf`

After the full source set and final PDF are verified, the intended Git commit message is:

`AWS done`

**Next chapter:** AWS Chunk 5 of 6 — Containers, Serverless, Messaging & Event-Driven Architecture. We will compare ECS/Fargate, Lambda, SQS, SNS, and EventBridge, with practical backend examples and production trade-offs.
