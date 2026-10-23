# Linux Chunk 6 — Production Incident Simulation
## Backend Engineering Tools & Infrastructure Handbook

**Phase:** I — Developer Foundations  
**Chunk:** 6 of 6  
**Source file:** `content/linux/06-production-incident-simulation.md`

---

# 1. Layer 1 — Fundamentals & Mental Models

## 1.1 Think like a production engineer

Imagine your Spring Boot API suddenly stops responding. Your first instinct might be to restart it.

But what if the actual cause is:
- A disk that has run out of space?
- A database connection pool that is exhausted?
- A process consuming all available memory?
- A DNS failure?
- A service listening on the wrong port?
- A deployment that changed file permissions?

Restarting may temporarily hide the symptom while leaving the root cause untouched.

**The objective of incident response is to restore service safely, identify the cause, and prevent recurrence.**

A reliable investigation follows a consistent sequence:

1. Establish the impact.
2. Gather evidence.
3. Narrow the failure domain.
4. Test a hypothesis.
5. Mitigate the issue safely.
6. Verify recovery.
7. Document the root cause and prevention steps.

---

## 1.2 The Linux troubleshooting model

A backend request may cross several layers before reaching the application.

```text
Client
  |
  v
DNS resolution
  |
  v
Network route / firewall
  |
  v
Listening socket / reverse proxy
  |
  v
Backend process
  |
  v
Application logic
  |
  v
Database / Redis / Kafka / other dependencies
```

A failure at any layer can look like an application failure from the client's perspective.

Use the symptom to determine which layer to investigate first. For example, a DNS lookup failure is a different problem from a successful DNS lookup followed by a TCP connection refusal.

---

## 1.3 Observe before changing

Before restarting a process or editing configuration, capture the current state when it is safe and practical to do so.

Useful commands include:

```bash
date
uptime
free -h
df -h
df -i
ps aux
ss -lntp
```

These provide evidence about system load, memory, storage, processes and listening sockets.

Not every command is available or identical across every Unix-like environment. On production Linux systems, prefer the native diagnostic tools and permissions appropriate to the host.

---

## 1.4 Symptoms, causes and hypotheses

Distinguish three concepts:

- **Symptom:** what users or monitoring systems observe.
- **Hypothesis:** a possible explanation that still needs evidence.
- **Root cause:** the underlying condition established by the investigation.

Example:

- Symptom: API requests time out.
- Hypothesis: the Java process is overloaded.
- Evidence: CPU usage is high and thread dumps show substantial contention.
- Root cause: established only after correlating the evidence with the actual workload and application behavior.

A full disk, a slow database and CPU saturation can all cause request failures, but they require different mitigations.

---

## 1.5 Incident severity and communication

A useful incident response also considers user impact:

- Are all requests failing, or only a particular endpoint?
- Is the failure isolated to one instance or affecting the entire service?
- Are writes failing, or are requests merely slower?
- Is data integrity at risk?
- Is the issue getting worse?

Prioritize actions that restore safe service and protect data. Communicate observed facts separately from hypotheses.

---

# 2. Layer 2 — Practical Engineering & Workflows

## 2.1 Start with a baseline

When investigating an unfamiliar Linux server, begin with a small, repeatable diagnostic sequence:

```bash
date
hostname
uptime
free -h
df -h
df -i
ps aux --sort=-%cpu | head
ps aux --sort=-%mem | head
```

Interpret the results rather than merely collecting output.

- `uptime` provides uptime and load averages.
- `free -h` summarizes memory and swap usage.
- `df -h` reports filesystem capacity.
- `df -i` reports inode usage.
- The `ps` commands show processes sorted by CPU or memory usage on systems supporting these options.

A high load average does not automatically mean CPU saturation. Processes blocked on I/O can also contribute to load. Compare the results with CPU utilization, I/O behavior and the workload.

---

## 2.2 Incident A — The API is unreachable

**Scenario:** Users report that `orders-api` is not responding on port 8080.

### Step 1: Test the endpoint locally

```bash
curl -v --connect-timeout 3 --max-time 5 \
  http://127.0.0.1:8080/health
```

Interpretation:

- A successful HTTP response suggests the local endpoint is reachable.
- Connection refused often means no process is accepting connections at that address and port, though other configurations can affect the result.
- A timeout may indicate a hang, packet filtering or another network problem.
- An HTTP `5xx` response means an HTTP server responded but reported a server-side error.

### Step 2: Check whether a process is listening

```bash
ss -lntp
```

For a more focused view:

```bash
ss -lntp | grep ':8080'
```

If the command shows no matching listener, investigate the service process, startup logs, configured port and binding address.

If it listens only on `127.0.0.1`, remote clients cannot directly reach it through the host's external interface. This may be intentional when a reverse proxy forwards traffic locally.

### Step 3: Inspect the service

On a system using systemd:

```bash
systemctl status orders-api
journalctl -u orders-api -n 100
```

Look for startup exceptions, configuration errors, failed dependency connections or a service that repeatedly exits.

### Step 4: Verify the result

After a confirmed fix:

```bash
curl -fsS --max-time 5 \
  http://127.0.0.1:8080/health
```

Then verify through the normal client-facing route. A healthy local endpoint does not prove that DNS, TLS, the reverse proxy or the external network path is healthy.

---

## 2.3 Incident B — CPU usage is unusually high

**Scenario:** API latency has increased and the server appears overloaded.

### Gather evidence

```bash
uptime
top
ps aux --sort=-%cpu | head -n 15
```

If available, `pidstat` can provide more detailed process-level measurements:

```bash
pidstat -u 1 5
```

Questions to answer:

1. Is CPU usage high across the host or concentrated in one process?
2. Did the problem begin after a deployment?
3. Are request rates higher than normal?
4. Is the process doing useful work, retrying failures or stuck in a loop?
5. Are downstream dependencies causing repeated work?

For a Java service, a thread dump can help identify blocked or busy threads. Tools such as `jcmd` may be available when the correct JDK and permissions are present.

Do not kill the process merely because it is using CPU. First determine whether it is processing a legitimate workload or exhibiting a failure.

---

## 2.4 Incident C — The server is running out of memory

Check:

```bash
free -h
ps aux --sort=-%mem | head
```

If supported and installed:

```bash
vmstat 1 5
```

Investigate:
- Memory consumption by process.
- Swap activity and available memory.
- Recent traffic or workload changes.
- Application memory growth.
- Kernel or container memory limits.
- Out-of-memory-killer messages in the system journal.

On a system using systemd:

```bash
journalctl -k --since "30 minutes ago"
```

A memory-related failure may come from the host, a container limit or an application-level allocation problem. These are related but distinct.

For Java applications, do not assume that all memory usage equals the Java heap. Native memory, thread stacks, direct buffers and other process allocations also matter.

---

## 2.5 Incident D — Disk space is exhausted

Check:

```bash
df -h
df -i
```

Identify the affected filesystem before examining directories.

For a Linux host:

```bash
sudo du -xhd1 /var 2>/dev/null | sort -h
```

Inspect the likely cause:
- Unrotated application logs.
- Temporary files.
- Large core dumps.
- Backups stored on the wrong filesystem.
- Container image or writable-layer growth.
- Deleted files still held open by a process.

If `lsof` is installed:

```bash
sudo lsof +L1
```

Do not delete databases, container runtime directories or arbitrary files just to free space. Identify ownership, retention requirements and recovery implications first.

After remediation, verify both filesystem usage and the affected application behavior.

---

## 2.6 Incident E — A DNS or connectivity failure

Start by testing name resolution:

```bash
getent hosts api.example.com
```

If `dig` is installed:

```bash
dig api.example.com
```

Then test the connection:

```bash
curl -v --connect-timeout 3 --max-time 8 \
  https://api.example.com/health
```

For a known destination IP and permitted network access, a TCP connectivity check may help:

```bash
nc -zv api.example.com 443
```

The exact options and behavior of `nc` vary by implementation.

Interpret the evidence:

- Name resolution fails: investigate DNS configuration, records and resolver availability.
- Resolution succeeds but TCP connection fails: investigate routing, firewall rules, destination listeners and network reachability.
- TCP connects but TLS fails: inspect certificate validity, hostname matching, protocol compatibility and trust configuration.
- HTTP responds with an error: investigate the application or gateway behavior.

Avoid jumping from a single failed test to a definitive root cause.

---

## 2.7 Incident F — The service cannot write to a file

Example error:

```text
Permission denied: /var/log/orders-api/app.log
```

Inspect the service and the entire path:

```bash
systemctl status orders-api
systemctl cat orders-api
namei -l /var/log/orders-api/app.log
```

Check ownership and permissions:

```bash
ls -ld /var/log/orders-api
ls -l /var/log/orders-api/app.log
```

If necessary and authorized, inspect ACLs:

```bash
getfacl /var/log/orders-api
```

Identify the service user before applying a fix. Restore the intended ownership or access permissions narrowly, then verify that the service can write to the required location.

Do not use broad permissions such as `777` to make the error disappear.

---

## 2.8 Incident G — A deployment introduced the failure

When a service worked before a release and fails afterward, compare the new and previous states.

Investigate:
- Configuration changes.
- Environment variables.
- Application versions and dependencies.
- File ownership and permissions.
- Ports and network bindings.
- Database schema compatibility.
- Resource consumption and startup duration.
- Health-check behavior.

Use the deployment's known rollback procedure if it is the safest way to restore service. Verify database migration compatibility and data integrity before rolling back application code.

A rollback is a mitigation, not proof of root cause. Capture the evidence that will help explain why the release failed.

---

## 2.9 Build an incident evidence bundle

Create a directory for a local diagnostic exercise:

```bash
mkdir -p ~/incident-lab
cd ~/incident-lab
```

You can capture non-sensitive command output:

```bash
date > incident-report.txt
uptime >> incident-report.txt
free -h >> incident-report.txt
df -h >> incident-report.txt
df -i >> incident-report.txt
```

For a real incident, include relevant service status, recent logs, affected endpoints, deployment identifiers and timestamps, while following your organization's security and data-handling rules.

Never collect or share secrets, authentication tokens or unrestricted customer data in an incident report.

---

# 3. Layer 3 — Production Engineering & Interview Mastery

## 3.1 A disciplined incident-response playbook

Use this sequence when a backend service is failing.

### Phase 1: Establish impact

- Identify affected endpoints and users.
- Determine whether failures are total or partial.
- Compare against monitoring and recent changes.
- Record the start time and observed symptoms.

### Phase 2: Gather evidence

- Check process and service status.
- Inspect relevant logs.
- Check CPU, memory, storage and inode usage.
- Verify listening sockets and local health endpoints.
- Test external dependencies where appropriate.

### Phase 3: Form and test hypotheses

Write down a small number of plausible causes. Choose tests that distinguish them rather than running unrelated commands.

For example, if the API is unreachable, check the local listener before assuming the DNS system is responsible.

### Phase 4: Mitigate safely

Select the lowest-risk action likely to restore service:
- Roll back a problematic release.
- Correct an identified configuration error.
- Restore safe disk capacity.
- Reduce excessive incoming load using an approved mechanism.
- Restart a service only when evidence and the runbook justify it.

For production changes, follow authorization and change-management requirements.

### Phase 5: Verify recovery

Confirm:
- The affected endpoint responds.
- Error rates and latency return toward expected levels.
- Dependencies are functioning.
- The system is not continuing to exhaust resources.
- The mitigation did not create a new problem.

### Phase 6: Prevent recurrence

Document the root cause, contributing factors, detection gaps, corrective actions and owners. Add monitoring or automated tests where they would have detected or prevented the failure.

---

## 3.2 Common troubleshooting mistakes

**Restarting too early.** This can destroy volatile diagnostic evidence and temporarily hide a recurring failure.

**Changing several things at once.** You lose the ability to determine which change fixed the issue and may introduce additional faults.

**Treating correlation as proof.** A deployment before an incident is an important clue, not conclusive evidence.

**Ignoring resource limits.** A host may have available memory while a container is constrained by its own limit.

**Trusting one health check.** A process can exist while its dependencies are failing; a local endpoint can work while external traffic is broken.

**Collecting too much sensitive data.** Diagnostic output can contain credentials, tokens, personal data or internal infrastructure details.

---

## 3.3 Interview questions — 15 essentials

### Q1. What is your first step when a production API becomes unavailable?
**Answer**: Establish the user impact and scope, record observed symptoms and timestamps, and gather baseline state (service status, recent logs, resource saturation, and network listeners) before executing any state-changing commands.

### Q2. What is the difference between a connection refusal and a timeout?
**Answer**: A connection refusal (`RST` packet) means the host was reached but actively rejected the packet because no process is listening on that port or a firewall blocked it. A timeout means packets were sent but no response or acknowledgment was received within the deadline, typically indicating routing failure, drop-by-firewall, or complete process hang.

### Q3. How do you investigate high CPU usage?
**Answer**: Use `top` or `ps aux --sort=-%cpu` to identify whether CPU is consumed in user space, system/kernel space, or I/O wait. Drill down to specific threads using `pidstat -u` or `top -H -p <PID>`, and capture JVM thread dumps via `jcmd <PID> Thread.print` or stack profiles to pinpoint spinning threads or contention.

### Q4. How do you diagnose memory pressure?
**Answer**: Check host memory with `free -h` and `vmstat 1 5` to inspect available memory and swap activity. Inspect process memory consumption with `ps aux --sort=-%mem`. For containerized apps, inspect cgroup limits (`memory.current`, `memory.max`). Check system logs (`journalctl -k` or `dmesg -T`) for kernel Out-Of-Memory (OOM) killer events.

### Q5. Why check both `df -h` and `df -i`?
**Answer**: `df -h` measures storage volume in data blocks (bytes). `df -i` measures inode table utilization. An application generating millions of tiny files can completely exhaust the filesystem's inodes, preventing any new file creation even when hundreds of gigabytes of disk block capacity remain free.

### Q6. Why might a process exist even though its API is unavailable?
**Answer**: The process may be stuck in a deadlock, trapped in garbage collection (stop-the-world pause), blocked on an unresponsive upstream database/socket, bound strictly to `127.0.0.1` rather than `0.0.0.0`, or running behind a reverse proxy/firewall that cannot route to it.

### Q7. How do you troubleshoot DNS versus TCP connectivity?
**Answer**: Decouple the resolution and transport layers. First test hostname resolution in isolation with `getent hosts <domain>` or `dig <domain>`. If resolution succeeds, test transport connectivity to the returned IP and target port with `nc -zv <IP> <port>` or `curl -v`.

### Q8. What is the purpose of `ss -lntp`?
**Answer**: It displays all listening (`-l`) TCP (`-t`) sockets with numeric IP and port addresses (`-n`) along with the process ID and program name (`-p`) responsible for holding the socket open.

### Q9. Why is restarting not always the best first action?
**Answer**: Restarting wipes out volatile forensic evidence (open file descriptors, thread states, JVM heap contents, temporary connection metrics), drops in-flight transactions, and if the root cause is external (e.g. exhausted DB pool or full disk), the service will immediately fail or crash again.

### Q10. What should be included in an incident report?
**Answer**: Impact statement, detailed timeline, observed symptoms, technical evidence, identified root cause, contributing factors, mitigation applied, recovery verification steps, and prioritized preventive action items (with assigned owners).

### Q11. What is the difference between mitigation and root-cause resolution?
**Answer**: Mitigation is a rapid, temporary stabilization action taken during an incident to restore service availability (e.g. rolling back, shedding load, expanding disk). Root-cause resolution fixes the underlying bug, design flaw, or infrastructure defect to permanently eliminate recurrence.

### Q12. How do you investigate a service that fails only after deployment?
**Answer**: Diff the configuration and code changes between the old and new release artifacts. Verify environment variables, file ownership/permissions in the new directory, database schema migration backward compatibility, and port/dependency bindings. If unhealthy and unresolved rapidly, trigger the automated rollback plan.

### Q13. What makes a good health check?
**Answer**: It distinguishes liveness (is the process alive and responsive without deadlock?) from readiness (are required local caches or critical connections established so it can safely handle user traffic?). It must execute with strict, short timeouts and avoid expensive cascading queries against shared external databases.

### Q14. Why are retries potentially dangerous during an outage?
**Answer**: Unsynchronized retries multiply request volume geometrically against degraded downstream components, turning minor brownouts into catastrophic complete outages (thundering herd problem). Robust retries must employ exponential backoff, randomized jitter, and circuit breakers.

### Q15. How do you know an incident is resolved?
**Answer**: You confirm through telemetry that customer-facing error rates, response latencies, and throughput have returned to nominal SLO/SLA thresholds, synthetic health checks pass consistently, queue backlogs are draining, and resource utilization (CPU, memory, disk, connections) has stabilized.

---

# 4. Capstone Lab — Investigate a Simulated Outage

You are the on-call engineer for a Spring Boot service named `orders-api`.

Users report that order requests are failing. The deployment was updated recently, and the service's logs have become incomplete.

Your task is to investigate systematically. Use a local lab or an authorized development environment; do not intentionally disrupt a production service.

## Stage 1: Establish the facts

Record:
- The affected endpoint (`http://localhost:8080/api/v1/orders`).
- The approximate start time.
- Whether the problem affects all requests or only write/POST operations.
- The latest deployment identifier (e.g. commit hash or container tag).
- Whether the failure is reproducible locally.

## Stage 2: Collect evidence

Run the appropriate commands for your environment:

```bash
date
uptime
free -h
df -h
df -i
ps aux --sort=-%cpu | head
ss -lntp
```

Inspect service state and logs if the service uses systemd:

```bash
systemctl status orders-api
journalctl -u orders-api --since "30 minutes ago"
```

Test the local endpoint:

```bash
curl -v --connect-timeout 3 --max-time 5 \
  http://127.0.0.1:8080/health
```

## Stage 3: Choose a hypothesis

Pick the hypothesis best supported by your evidence:

1. The application is not listening on port 8080.
2. The process is overloaded.
3. The filesystem cannot accept new log writes (`Permission denied` or `No space left on device`).
4. The service user lacks permission to access a required file.
5. A downstream dependency is unavailable.

Write down the evidence that supports or weakens your hypothesis.

## Stage 4: Mitigate and verify

Describe the smallest safe corrective action. Then define how you would prove that the original problem is resolved.

## Stage 5: Write the post-incident report

Use this structure:

```text
Incident: orders-api Degradation and Failure
Impact: 100% of order placement requests failing with 500 Internal Server Error for 14 minutes.
Start time: 2026-10-23 07:45 UTC
Detection: Synthetic alert triggered on 5xx error rate > 1%.
Symptoms: API unreachable on write routes; log appending failed.
Evidence: 
  - `df -h` showed /var partition at 100% block capacity.
  - `lsof +L1` revealed 4.2 GB unlinked rolling log held by process 1421.
Root cause: Log rotation unlinked previous day's log without signaling application logger to reopen file descriptor.
Contributing factors: Missing copytruncate in logrotate config; lack of disk threshold alerting.
Mitigation: Truncated the file descriptor via /proc/1421/fd/1 and signaled process with SIGHUP.
Recovery verification: `df -h` confirmed 42% free space; synthetic POST /api/v1/orders returned 201 Created.
Preventive actions: Updated logrotate configuration with copytruncate; added PagerDuty alert at 85% disk utilization.
```

The goal is not to guess the intended answer. It is to demonstrate a repeatable, evidence-driven investigation.

---

# 5. Linux Mastery Assessment

You have now covered the six Linux chunks in the curriculum. Use this final assessment to determine whether you can apply the concepts rather than merely recall commands.

- [ ] Navigate the filesystem and inspect files safely.
- [ ] Inspect processes, signals, CPU usage and memory.
- [ ] Diagnose basic network and connectivity failures.
- [ ] Read system logs and application logs.
- [ ] Understand ownership, permissions, disk capacity and inodes.
- [ ] Write defensive shell scripts with meaningful exit statuses.
- [ ] Use a systematic incident-response workflow.
- [ ] Explain how you would troubleshoot an unavailable backend service.
- [ ] Complete the capstone and write a post-incident report.

---

## Completion Protocol

1. Save this complete source as `content/linux/06-production-incident-simulation.md`.
2. Preserve all six Linux source chunks in `content/linux/`.
3. Verify that all six chunks collectively cover Fundamentals & Mental Models, Practical Engineering & Workflows, and Production Engineering & Interview Mastery.
4. Do not create PDFs for individual chunks.
5. Only after all six chunks are saved and verified, generate the single final Linux handbook: `docs/linux/BEH_LINUX_COMPLETE_HANDBOOK.pdf`.
6. Update the README using verified progress and complete the Linux work only after the final PDF is generated and checked.

**Linux curriculum complete — 6 of 6 educational chunks authored.**
