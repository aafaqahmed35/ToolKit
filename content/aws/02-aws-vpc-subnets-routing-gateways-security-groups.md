# AWS — Chunk 2 of 6: VPC, Subnets, Routing, Internet Gateways & Security Groups

## Backend Engineering Tools & Infrastructure Handbook · Cloud Engineering Track

**Source file:** `content/aws/02-aws-vpc-subnets-routing-gateways-security-groups.md`

In Chunk 1, we designed a Spring Boot API and PostgreSQL database. Now we'll answer the question that makes cloud deployment click:

How does an HTTP request travel from a user's browser to an application running inside AWS — and how do we stop unauthorized traffic from reaching it?

We'll build the networking concepts from scratch, then apply them to a realistic backend architecture.

---

## Learning Roadmap

1. **Fundamentals & mental models:** VPCs, CIDR ranges, subnets, public vs. private networking, routing, and network boundaries.
2. **Practical engineering:** Build a network design for a Spring Boot API, load balancer, and PostgreSQL database. Understand routes, security groups, and request flow.
3. **Production & interview mastery:** Debug unreachable services, design least-exposure networks, reason about NAT costs, and handle connectivity incidents.

---

## Learning Objectives

By the end of this chapter, you should be able to:

- Explain how an AWS Virtual Private Cloud works.
- Understand IPv4 addresses, CIDR notation, and subnet ranges.
- Distinguish public and private subnets.
- Explain route tables, the local route, Internet Gateways, and NAT Gateways.
- Understand security groups and Network ACLs.
- Design a network for a Spring Boot API and PostgreSQL database.
- Trace an incoming HTTPS request and an outgoing connection.
- Diagnose common connectivity failures using a systematic workflow.

**Prerequisites:** No prior cloud networking experience is required.

---

# Layer 1 — Fundamentals & Mental Models

## 1. What Is a VPC?

VPC stands for **Virtual Private Cloud**.

An AWS VPC is a logically isolated virtual network in which you can launch and connect supported AWS resources.

Imagine an office building:

- The **VPC** is the building's overall network boundary.
- **Subnets** are network segments within the building.
- **Route tables** are directions that tell traffic where to go.
- **Gateways** connect the network to other networks.
- **Security groups** act like stateful firewalls attached to resources.
- **Network ACLs** provide another layer of subnet-level traffic control.

This analogy is not a complete description of AWS networking, but it gives you the basic mental model.

### Why does a backend need a VPC?

Suppose you're deploying an Orders API with PostgreSQL.

You want customers to reach the API over HTTPS. However, you don't want arbitrary internet clients to connect directly to the database.

A VPC lets you organize resources into network segments and control their communication paths.

A typical architecture looks like this:

```text
                      Internet
                         |
                         v
                  Internet Gateway
                         |
+------------------------+------------------------+
| VPC                                             |
|                                                 |
|  +-------------------------------------------+  |
|  | Public subnet                             |  |
|  | Load balancer                             |  |
|  +---------------------+---------------------+  |
|                        |                        |
|                        v                        |
|  +-------------------------------------------+  |
|  | Private subnet                            |  |
|  | Spring Boot API                           |  |
|  +---------------------+---------------------+  |
|                        |                        |
|                        v                        |
|  +-------------------------------------------+  |
|  | Private subnet                            |  |
|  | PostgreSQL                                |  |
|  +-------------------------------------------+  |
+-------------------------------------------------+
```

This is a conceptual architecture. In a production design, the subnets would typically be distributed across multiple Availability Zones for resilience, and routing and security rules would be configured separately for each component.

**Core principle:** Network placement and network permissions should reflect the intended communication paths between components.

## 2. IP Addresses and CIDR Notation

Before configuring a VPC, understand how IP address ranges work.

An IPv4 address contains 32 bits and is commonly written as four decimal numbers.

Example:

```text
10.0.1.25
```

CIDR notation specifies a range of IP addresses.

Example:

```text
10.0.0.0/16
```

The `/16` indicates that the first 16 bits identify the network portion of the range. The remaining bits identify addresses within that range.

For a conventional IPv4 CIDR block:

$$\text{Address count} = 2^{32 - \text{prefix length}}$$

For `10.0.0.0/16`:

$$2^{32 - 16} = 65{,}536$$

That is the total number of addresses in the IPv4 range, not the number of addresses available to workloads in an AWS subnet.

### Common CIDR examples

| CIDR | Total IPv4 addresses | Typical interpretation |
|---|---|---|
| `10.0.0.0/16` | 65,536 | Large private network range |
| `10.0.1.0/24` | 256 | Smaller subnet range |
| `10.0.1.0/28` | 16 | Small subnet range |

AWS reserves five IPv4 addresses in each IPv4 subnet. For example, a `/24` subnet has 251 addresses available for use by resources, before accounting for any additional service-specific constraints.

### A practical subnet layout

Suppose we allocate `10.0.0.0/16` to a VPC.

We could divide it into smaller ranges:

```text
VPC: 10.0.0.0/16
|
+-- Public subnet A: 10.0.1.0/24
+-- Public subnet B: 10.0.2.0/24
|
+-- Private app A:   10.0.11.0/24
+-- Private app B:   10.0.12.0/24
|
+-- Private DB A:    10.0.21.0/24
+-- Private DB B:    10.0.22.0/24
```

These are example ranges, not a required AWS layout.

Planning address ranges matters because overlapping networks can complicate routing, particularly when connecting VPCs, corporate networks, or other environments.

**Interview insight:** CIDR planning is not merely an IP-address exercise. It affects future network connectivity and the ability to expand the architecture.

## 3. What Is a Subnet?

A subnet is a range of IP addresses within a VPC.

In AWS, each subnet is associated with one Availability Zone.

For example, a subnet might exist in Availability Zone A while another subnet exists in Availability Zone B.

You can place resources in different subnets to separate network paths and distribute infrastructure across zones.

### Why use multiple subnets?

Consider three categories:

1. Public-facing entry points.
2. Private application workloads.
3. Private data services.

Separating them helps you establish distinct routing and security policies.

However, subnet names are just labels. Naming a subnet `private-subnet` does not make it private.

Its actual behavior depends on the associated routing configuration and other networking controls.

## 4. Public vs. Private Subnets

This distinction is fundamental.

### Public subnet

A subnet is commonly described as public when its associated route table provides a route to an Internet Gateway for internet-bound IPv4 traffic.

For a resource to communicate directly with the public IPv4 internet, it also needs an appropriate public IPv4 address and suitable security rules.

A route to an Internet Gateway alone does not automatically make every resource in the subnet publicly reachable.

### Private subnet

A private subnet typically does not have a direct route to an Internet Gateway for general internet-bound IPv4 traffic.

Resources in a private subnet can still communicate with other permitted resources inside the VPC. They may also access external services through a NAT Gateway or other explicitly configured network path.

A private subnet does not mean the resources are isolated from every network. It means their routing and access paths are more restricted.

### Compare the two

| Property | Public subnet | Private subnet |
|---|---|---|
| Typical direct internet route | Via Internet Gateway | No direct general-purpose internet route |
| Public IPv4 address | May be assigned | Usually not assigned |
| Common workloads | Public load balancer | Application servers and databases |
| Internet access | Depends on routes, addressing, and security rules | May use NAT or private endpoints |
| Is it automatically secure? | No | No |

**Important:** A public subnet does not necessarily expose every resource. Exposure depends on addressing, routing, security groups, network ACLs, and service configuration.

## 5. Route Tables: Where Should Traffic Go?

A route table contains rules that determine where network traffic should be directed.

A route has a destination network and a target.

For example:

| Destination | Target |
|---|---|
| `10.0.0.0/16` | `local` |
| `0.0.0.0/0` | `Internet Gateway` |

The first route represents communication within the VPC's local IPv4 network range.

The second route sends IPv4 traffic whose destination does not match a more specific route toward the Internet Gateway.

This is a simplified example of a public subnet's route table.

### The local route

A VPC route table includes a local route that supports communication within the VPC's associated network ranges.

You do not normally add a separate Internet Gateway route for every resource in the VPC.

### The default route

`0.0.0.0/0` represents all IPv4 destinations.

A default route provides a path for destinations not matched by a more specific route.

But the target matters:

- `0.0.0.0/0 → Internet Gateway` can provide an internet route from a public subnet.
- `0.0.0.0/0 → NAT Gateway` can provide outbound internet access for workloads in a private subnet, subject to the network configuration.

AWS uses the most specific matching route when multiple routes match a destination. Route selection can also depend on the route target and route type.

### A simple example

Your API instance has an address in `10.0.11.0/24`. It wants to connect to another resource at `10.0.21.15`.

If the destination is within the VPC's local address range, the local route can direct the traffic within the VPC.

If the API instead wants to reach an external IPv4 destination, its subnet's route table needs a suitable route to an external network path.

A route table provides a path, not permission. Security groups and network ACLs may still block the connection.

## 6. Internet Gateway

An Internet Gateway is a VPC component that enables communication between the VPC and the internet when routing, addressing, and security configuration allow it.

Think of it as the connection point between a VPC and the public internet.

For a typical inbound IPv4 connection to an EC2 instance, you need:

1. An Internet Gateway attached to the VPC.
2. A suitable route to the Internet Gateway.
3. An appropriate public IPv4 address or other valid public addressing configuration.
4. Security rules that permit the intended traffic.
5. An application or service listening on the relevant port.

If any required part is missing, the connection can fail.

### What an Internet Gateway does not do

It does not:

- Automatically assign a public IP address to every instance.
- Automatically permit inbound traffic.
- Replace security groups.
- Replace application authentication.
- Guarantee that the application is listening on its intended port.

**Interview takeaway:** A network route and an access permission are different things.

## 7. NAT Gateway

A NAT Gateway can provide outbound internet connectivity for resources in private subnets without requiring those resources to have public IPv4 addresses.

Imagine a private application server that needs to download an external dependency or call a third-party API.

The application server sends traffic toward a NAT Gateway. The NAT Gateway translates the source address for eligible outbound IPv4 connections and uses its own public connectivity.

The return traffic can flow back through the NAT Gateway for established connections.

A common arrangement is:

```text
Private API instance
        |
        v
Private subnet route table
        |
        v
NAT Gateway in public subnet
        |
        v
Internet Gateway
        |
        v
External API
```

### NAT Gateway versus Internet Gateway

- An **Internet Gateway** supports internet connectivity for appropriately configured resources in a VPC.
- A **NAT Gateway** provides a controlled outbound connectivity path for private IPv4 workloads.
- A NAT Gateway does not automatically permit unsolicited inbound internet connections to the private instances using it.

### Production considerations

NAT Gateways incur charges. Costs can include gateway usage and data processing, and applicable data-transfer charges may also apply.

Availability and routing design matter too. For example, placing a single NAT Gateway in one Availability Zone can create a dependency on that zone for workloads in other zones and may result in cross-zone data-transfer charges.

For production workloads, evaluate whether per-AZ NAT Gateways or another egress architecture best meets reliability and cost requirements.

For learning, understand the design before provisioning resources.

## 8. Security Groups: Stateful Network Firewalls

A security group controls inbound and outbound traffic associated with supported AWS resources.

**Security groups are stateful.**

That means return traffic for an allowed connection is automatically permitted by the security group's state tracking; you do not need to add a separate rule solely for the return packets of that connection.

Security groups are commonly used to express which components may communicate.

### Example: Three security groups

```text
Internet
    |
    | HTTPS (port 443)
    v
[Load Balancer SG]
    |
    | Application port (port 8080)
    v
[Application SG]
    |
    | PostgreSQL port (port 5432)
    v
[Database SG]
```

The intended policy might be:

- **Load balancer security group:** allow inbound HTTPS from intended public clients.
- **Application security group:** allow inbound application traffic from the load balancer security group.
- **Database security group:** allow inbound PostgreSQL traffic from the application security group.

This expresses the architecture more safely than opening every port to every source.

### Example rules

| Security group | Inbound source | Port | Purpose |
|---|---|---|---|
| Load balancer SG | Intended public clients | 443 | HTTPS |
| Application SG | Load balancer SG | 8080 | Spring Boot API |
| Database SG | Application SG | 5432 | PostgreSQL |

The table describes the intended access rules, not a complete deployable configuration.

The application port could differ depending on the load balancer's target configuration and the application's actual listener.

### Why reference another security group?

Instead of allowing all IPv4 addresses to connect to PostgreSQL, a database security group can permit the application security group as the source.

This makes the permission express a relationship between components.

It is generally easier to reason about and maintain than a broad source range.

### Security group rules are not application authentication

A security group can permit a TCP connection to the API. It does not prove that the requester is an authorized application user.

You still need application-level authentication and authorization.

Network access control, IAM, database permissions, and application authentication solve different problems.

## 9. Network ACLs

A Network Access Control List, or NACL, is associated with a subnet and controls inbound and outbound traffic at that subnet boundary.

**Unlike security groups, network ACLs are stateless.**

For a connection to succeed, both the forward and return traffic must be permitted by the relevant NACL rules.

NACL rules are evaluated in rule-number order, and the first matching rule determines the outcome.

A NACL can provide an additional network-control layer, but it also introduces another place where connectivity can be blocked.

### Security groups vs. NACLs

| Property | Security group | Network ACL |
|---|---|---|
| Scope | Associated with network interfaces/resources | Associated with subnets |
| Stateful? | Yes | No |
| Rules | Allow rules | Allow and deny rules |
| Rule evaluation | Matching allowed traffic is permitted unless other controls block it | Rules evaluated in order |
| Common use | Restrict communication between components | Additional subnet-level traffic filtering |

For most beginner backend designs, learn to express the main component access relationships through security groups first. Introduce NACLs when a specific subnet-level control requirement justifies them.

## 10. The Full Request Path

Let's trace a user request to a Spring Boot API.

Assume the architecture has a public Application Load Balancer and private application instances.

```text
1. Client resolves the API hostname
        |
        v
2. Client opens HTTPS connection
        |
        v
3. Public load balancer receives traffic
        |
        v
4. Load balancer forwards to a healthy API target
        |
        v
5. Spring Boot processes the request
        |
        v
6. API connects to PostgreSQL
        |
        v
7. Database returns the result
        |
        v
8. API returns the HTTP response
```

Each step has different possible failure points:

- DNS resolution may fail.
- TLS negotiation may fail.
- The load balancer may have no healthy targets.
- Security rules may block the load balancer-to-application connection.
- The application may not be listening on the expected port.
- The database route or security group may block the connection.
- The application may be healthy at the network layer but fail during request processing.

**The debugging lesson:** Do not treat every timeout as an application bug. Trace the request path and identify the first failing boundary.

---

# Layer 2 — Practical Engineering & Workflows

## 11. Design a Network for the Orders API

Let's design a network before deploying anything.

### Requirements

- Customers need HTTPS access.
- The application should not require a public IP address on each application instance.
- PostgreSQL should not be directly exposed to the public internet.
- Application instances should connect to PostgreSQL.
- The architecture should be able to expand across Availability Zones.

### Step 1 — Choose a VPC range

For this example:

$$\text{VPC CIDR: } 10.0.0.0/16$$

### Step 2 — Create subnet ranges

Example layout:

| Subnet | CIDR | Intended role |
|---|---|---|
| Public A | 10.0.1.0/24 | Load balancer |
| Public B | 10.0.2.0/24 | Load balancer |
| App A | 10.0.11.0/24 | Application workloads |
| App B | 10.0.12.0/24 | Application workloads |
| DB A | 10.0.21.0/24 | Database subnet group |
| DB B | 10.0.22.0/24 | Database subnet group |

The subnets should be placed in suitable Availability Zones. For managed databases, the subnet group and service-specific availability requirements also need to be considered.

### Step 3 — Plan routing

A simplified routing plan:

| Subnet category | Typical route |
|---|---|
| Public | VPC local route plus an internet route through the Internet Gateway |
| Private application | VPC local route plus NAT or other required egress routes |
| Private database | VPC local route and only the additional routes actually required |

Do not assume the database needs general-purpose internet access. Design the required paths explicitly.

### Step 4 — Define security group relationships

```text
Internet clients
       |
       | TCP 443
       v
Load balancer SG
       |
       | TCP 8080
       v
Application SG
       |
       | TCP 5432
       v
Database SG
```

The arrows describe intended connection directions.

Security group rules must match the actual listener ports and traffic path. The load balancer may terminate TLS and use HTTP or HTTPS to reach its targets, depending on your configuration.

### Step 5 — Validate the design

Ask these questions:

1. Does the load balancer have the routing and addressing it needs?
2. Are the application targets reachable from the load balancer?
3. Can the application reach PostgreSQL on its configured port?
4. Does the database accept traffic only from approved sources?
5. Are routes and network controls correct in every Availability Zone?
6. Can the design tolerate the loss of one zone?
7. Is outbound connectivity restricted to what the workload needs?

This is the beginning of cloud network design: describe the intended traffic first, then implement the smallest set of routes and rules that supports it.

## 12. Learn to Inspect AWS Networking

You do not need to create paid resources to begin learning how to inspect the environment.

If you have an AWS identity with the required read permissions, the AWS CLI can query VPC resources.

### List VPCs

```bash
aws ec2 describe-vpcs \
  --query 'Vpcs[*].[VpcId,CidrBlock,State]' \
  --output table
```

### List subnets

```bash
aws ec2 describe-subnets \
  --query 'Subnets[*].[SubnetId,VpcId,AvailabilityZone,CidrBlock]' \
  --output table
```

### List route tables

```bash
aws ec2 describe-route-tables \
  --query 'RouteTables[*].[RouteTableId,VpcId]' \
  --output table
```

### List Internet Gateways

```bash
aws ec2 describe-internet-gateways \
  --query 'InternetGateways[*].[InternetGatewayId,Attachments]' \
  --output table
```

### List security groups

```bash
aws ec2 describe-security-groups \
  --query 'SecurityGroups[*].[GroupId,GroupName,VpcId]' \
  --output table
```

These are read-only inspection commands. They do not create or modify network resources.

The CLI identity needs the relevant describe permissions. An empty result may simply mean that the selected account or region has no matching resources.

Always verify the account and region before interpreting the output.

## 13. Troubleshooting: API Is Unreachable

Suppose your load balancer returns an error or the API request times out.

Use this workflow rather than randomly opening ports.

### Step 1 — Check DNS

Verify that the API hostname resolves to the expected destination.

If DNS resolves incorrectly, investigate the DNS records and configuration before changing security groups.

### Step 2 — Check the load balancer

Inspect:

- Listener configuration.
- Listener rules.
- Target group configuration.
- Target health.
- Health-check path and port.

An unhealthy target can result from an incorrect health-check path, an application startup problem, a port mismatch, or a network restriction.

### Step 3 — Check the application security group

Verify that the application accepts the expected port from the intended load balancer security group.

Avoid opening the application port to all public addresses merely to test connectivity.

### Step 4 — Check the application listener

Confirm that the application is actually listening on the expected port and interface.

For a Linux-based host, useful diagnostic commands can include:

```bash
ss -lntp
curl -v http://127.0.0.1:8080/actuator/health
```

These commands are examples for an environment where the corresponding tools and endpoint exist. A local health endpoint can succeed even when the load balancer cannot reach the instance, so this is only one diagnostic step.

### Step 5 — Check routing and network controls

Verify:

- The relevant subnet route tables.
- Security group rules.
- NACL inbound and outbound rules.
- The route and target configuration for the traffic direction.
- Any required return path.

### Step 6 — Check application and infrastructure logs

Use the evidence from load balancer health checks, application logs, and available network telemetry to identify the failing boundary.

Do not assume the application is at fault until the network path has been checked.

## 14. Troubleshooting: Application Cannot Reach PostgreSQL

Assume the API runs but database connections time out.

Investigate in this order:

1. Confirm the database hostname and port in application configuration.
2. Verify that the database is available and accepting connections.
3. Confirm that the database security group permits the application source on the database port.
4. Inspect the application's subnet route table and the database network path.
5. Review NACL rules, including return traffic.
6. Check DNS resolution and database endpoint configuration.
7. Review connection-pool exhaustion, database connection limits, and application logs.

### Distinguish network failure from authentication failure

A **connection timeout** often suggests a network path or availability issue, although timeouts can have several causes.

An **explicit authentication error** means the connection reached a point where the database rejected the supplied credentials or authentication method.

These symptoms call for different investigations.

Do not respond to a database authentication failure by opening more network ports. Similarly, do not rotate database passwords at random when the connection cannot reach the database at all.

## 15. Common Networking Mistakes

| Mistake | Why it fails | Better approach |
|---|---|---|
| Assuming a public subnet makes every resource reachable | Public reachability depends on several controls | Check routes, addressing, and security rules |
| Assuming a private subnet has no outbound connectivity | Private resources may use NAT or other paths | Inspect the actual route table |
| Opening SSH or database ports to all IPv4 addresses | Unnecessarily expands exposure | Restrict access to approved sources |
| Assuming a security group creates a route | Security groups control traffic; they do not establish a network path | Check routing separately |
| Forgetting NACL return rules | NACLs are stateless | Validate both traffic directions |
| Using one NAT Gateway without considering zone failures | Other zones may depend on that gateway | Evaluate availability and cost trade-offs |
| Treating a healthy local endpoint as proof of external reachability | The load balancer path may still be broken | Test each network boundary |
| Overlapping VPC CIDR ranges | Can complicate connectivity and routing | Plan address ranges before deployment |

---

# Layer 3 — Production Engineering & Interview Mastery

## 16. Production Network Design Principles

### 16.1 Minimize public exposure

Only components that require direct public reachability should have it.

A common backend architecture exposes a load balancer publicly while keeping application instances and databases in private subnets.

This reduces the number of public entry points and makes access relationships easier to reason about.

### 16.2 Design explicit communication paths

For each component, define:

- Which systems can initiate connections to it.
- Which ports are needed.
- Whether the connection is inbound or outbound.
- Whether the traffic needs to leave the VPC.
- Which security groups and routes support the connection.

This creates a network design that can be reviewed, tested, and debugged.

### 16.3 Plan for multiple Availability Zones

For production systems that require high availability, distribute appropriate resources across Availability Zones.

Do not assume that placing the API in two zones is enough. Check the availability of the load balancer, database, networking dependencies, and capacity in the surviving zone.

### 16.4 Control outbound traffic

Private workloads often need to call external APIs, download dependencies, or reach AWS services.

Do not automatically give every workload unrestricted internet access.

Consider:

- NAT-based egress.
- Private connectivity to supported AWS services.
- VPC endpoints where appropriate.
- Application-level destination controls.
- Monitoring for unexpected outbound traffic.

The right choice depends on which services the application needs and how tightly its network access must be restricted.

### 16.5 Use logs and network telemetry

When ordinary application logs cannot explain a connection failure, additional network telemetry can help.

Relevant AWS capabilities include:

- **VPC Flow Logs** for information about IP traffic to and from network interfaces and supported network resources.
- **Load balancer access logs** where supported and configured.
- **CloudTrail** for recording supported AWS API activity.
- **Application logs and metrics** for request-level behavior.

VPC Flow Logs provide useful network evidence, but they do not capture every detail of an application's request or prove that the application successfully processed a request.

## 17. Production Incident Simulation: Database Exposed to the Internet

**Scenario:** A security review discovers that a database may be reachable from public networks.

### Investigation

1. Confirm the database's public-access configuration.
2. Inspect its subnet group and network placement.
3. Review the relevant route tables.
4. Inspect database security groups and any other applicable network controls.
5. Review database authentication, permissions, and encryption.
6. Examine available audit and access logs for evidence of unauthorized activity.

### Remediation

1. Remove unnecessary public access.
2. Restrict database ingress to the intended application network identity or source.
3. Verify the application can still connect.
4. Review credentials and rotate them if compromise is suspected.
5. Investigate whether data or credentials were exposed.
6. Document the incident and add a preventive configuration check.

Do not assume that a public route alone proves the database was accessed. Establish the actual exposure path and investigate the evidence.

## 18. Production Incident Simulation: One Availability Zone Fails

**Scenario:** Application instances in one Availability Zone become unhealthy.

### Questions to investigate

- Are healthy application targets available in another zone?
- Does the load balancer have healthy targets to serve?
- Can surviving instances handle the increased traffic?
- Is the database available?
- Does the remaining network path depend on a failed-zone resource?
- Are there NAT or egress dependencies that affect surviving instances?

### Engineering response

1. Establish the scope of the failure.
2. Verify service health from the load balancer and application metrics.
3. Confirm that the remaining capacity can handle demand.
4. Restore or replace failed resources according to the recovery design.
5. Check whether any zonal dependency undermined resilience.
6. Update the architecture and runbook based on the findings.

**Key lesson:** Availability is a property of the complete system, not a checkbox on an individual AWS service.

## 19. Production Incident Simulation: Private API Cannot Reach an External Service

**Scenario:** A Spring Boot application runs in a private subnet but cannot reach a third-party API.

### Possible causes

- No suitable route to an egress path.
- NAT Gateway configuration or availability issue.
- Security group outbound rules.
- NACL rules blocking traffic or return packets.
- DNS resolution failure.
- TLS or application-level failure.
- The external service is unavailable.

### Investigation sequence

1. Confirm the destination hostname resolves.
2. Inspect the subnet route table.
3. Verify the intended egress mechanism.
4. Check security group and NACL behavior.
5. Test TCP connectivity where permitted.
6. Inspect TLS errors and application logs.
7. Confirm whether the external service is responding.

Avoid changing multiple network controls at once. Change one justified setting, validate it, and record the result.

## 20. Interview Questions and Answers

### Q1. What is a VPC?

A logically isolated virtual network in AWS where supported resources can communicate through configured routing and network controls.

### Q2. What is a subnet?

A range of IP addresses within a VPC associated with a single Availability Zone.

### Q3. What is CIDR notation?

A way to express an IP address range using a prefix length, such as `10.0.0.0/16`.

### Q4. What makes an AWS subnet public?

Typically, its route table provides an internet route through an Internet Gateway. Direct public IPv4 reachability also depends on addressing and applicable security controls.

### Q5. What is the difference between an Internet Gateway and a NAT Gateway?

An Internet Gateway provides the VPC's internet connectivity path for appropriately configured resources. A NAT Gateway provides outbound internet connectivity for private IPv4 workloads without requiring public IPv4 addresses on those workloads.

### Q6. Does a private subnet guarantee that resources cannot access the internet?

No. Private resources may have outbound internet connectivity through a NAT Gateway or another configured egress path.

### Q7. What does 0.0.0.0/0 mean?

It represents all IPv4 destinations. In a route table, it is commonly used as a default route.

### Q8. What is a security group?

A stateful virtual firewall associated with supported resources or network interfaces, used to control inbound and outbound traffic.

### Q9. Why are security groups stateful?

They track permitted connections, so return traffic for an allowed connection is automatically permitted by the security group's state tracking.

### Q10. What is a Network ACL?

A subnet-associated network access control list that filters traffic using ordered allow and deny rules. It is stateless.

### Q11. What is the difference between a security group and a NACL?

Security groups are stateful and commonly define resource-level communication permissions. NACLs are stateless, subnet-level controls with ordered allow and deny rules.

### Q12. Why might an EC2 instance in a public subnet still be unreachable?

It may lack a public IP address, have incorrect routing, be blocked by security groups or NACLs, or have no service listening on the intended port.

### Q13. Why can an application reach the database locally but fail in AWS?

The AWS route, security group, NACL, DNS, database endpoint, or authentication configuration may be incorrect. A local test does not validate the cloud network path.

### Q14. How would you secure PostgreSQL for a backend API?

Keep it off unnecessary public paths, restrict inbound access to approved application sources, enforce database authentication and least privilege, and configure appropriate encryption, backups, and monitoring.

### Q15. What is a route table?

A collection of routes that determines where network traffic should be directed based on its destination.

### Q16. Why can CIDR overlap be a problem?

Overlapping IP ranges can create ambiguous or incompatible routing when connecting networks, such as VPCs or corporate networks.

### Q17. Why might a NAT Gateway become a reliability bottleneck?

If workloads depend on a single NAT Gateway, a failure or connectivity problem affecting its Availability Zone can disrupt their outbound access. Cross-zone routing can also affect costs and availability.

### Q18. How would you investigate an unreachable API?

Trace the path from DNS through the load balancer, target health, application listener, routes, security groups, NACLs, and application logs. Find the first failing boundary before making changes.

### Q19. Why does opening a port not always fix connectivity?

The route may be missing, the destination may be unreachable, the application may not be listening, or another network control may still block traffic.

### Q20. How would you design a highly available AWS network for a backend API?

Use an appropriate VPC address plan, distribute suitable resources across Availability Zones, expose only the required entry point, keep internal workloads on restricted network paths, design database connectivity deliberately, and test failure behavior.

---

# Capstone Lab — Draw and Debug the Orders API Network

## Objective

Create a network design for a Spring Boot API and PostgreSQL database. You do not need to provision paid resources.

### Task 1 — Draw the VPC

Include:

- One VPC CIDR.
- Two public subnet ranges.
- Two private application subnet ranges.
- Two private database subnet ranges.
- Availability Zone placement.

### Task 2 — Design the routes

Write the intended route table for each subnet category. Identify which routes are required for local communication, internet-facing traffic, and outbound application connectivity.

### Task 3 — Define security group rules

Document the intended traffic:

- Public client to load balancer.
- Load balancer to application.
- Application to database.
- Application to approved external destinations.

Specify the port and source for each required connection.

### Task 4 — Simulate failures

Explain how you would investigate:

- The load balancer has no healthy targets.
- The application cannot connect to PostgreSQL.
- The application cannot reach an external API.
- A security group was changed accidentally.
- One Availability Zone becomes unavailable.

### Task 5 — Review the security posture

Identify:

- Which components need public reachability.
- Which components should remain private.
- Which permissions are unnecessary.
- Which network paths are single points of failure.
- Which costs need consideration.

## Mastery Assessment

Answer these without looking at the chapter:

1. Why is a public subnet not sufficient to make an EC2 instance publicly reachable?
2. How are a route table and a security group different?
3. Why are security groups stateful but NACLs stateless?
4. How does a private subnet reach an external IPv4 API through a NAT Gateway?
5. Why can an application and database be in the same VPC yet fail to communicate?
6. What would you inspect if a load balancer reports unhealthy targets?
7. Why should PostgreSQL usually not be exposed directly to public clients?
8. How would you design for an Availability Zone failure without making every component public?

## Completion Checklist

- [ ] I understand VPCs and subnets.
- [ ] I can read common CIDR ranges.
- [ ] I understand public and private subnet routing.
- [ ] I can explain Internet Gateways and NAT Gateways.
- [ ] I understand security groups and NACLs.
- [ ] I can trace an HTTPS request to a backend.
- [ ] I can diagnose basic AWS network failures.
- [ ] I can design a network for a Spring Boot API and PostgreSQL.
- [ ] I can explain the cost and availability trade-offs of network choices.

---

# Handbook Completion Protocol

Save this chapter as:

`content/aws/02-aws-vpc-subnets-routing-gateways-security-groups.md`

This is **Chunk 2 of 6**. Preserve it as Markdown. Do not generate a separate chunk PDF.

After all six AWS chapters have been saved and verified, create the complete handbook:

`docs/aws/BEH_AWS_COMPLETE_HANDBOOK.pdf`

Update the README only after verifying the source chapters and final PDF. Commit only after the complete AWS source content and final PDF have been verified.

Required commit message: `AWS done`

This chapter does not imply that any repository operation, PDF generation, or Git commit has already occurred.

### Up next

**AWS Chunk 3 of 6 — EC2, Application Load Balancers, Auto Scaling & Compute Architecture.**

We'll move from networking into running the actual backend: what a virtual server is, how load balancing works, how instances scale, and why a running instance is not the same as a reliable service.
