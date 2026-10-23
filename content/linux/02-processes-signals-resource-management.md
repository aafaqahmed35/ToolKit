# Linux Chunk 2 of 6 — Processes, Signals & Resource Management

Phase I · Developer Foundations  
Backend Engineering Handbook

Source file: `content/linux/02-processes-signals-resource-management.md`

This chunk teaches you how to understand, inspect, control, and troubleshoot running programs on Linux—the skills you need when a Spring Boot service consumes too much CPU, a process refuses to stop, or your application disappears after running out of memory.

---

## The Three-Layer Learning Framework

| Layer | Focus & Objective |
| :--- | :--- |
| **Layer 1 — Fundamentals & Mental Models** | Processes, threads, PIDs, scheduling, signals, CPU, memory and resource limits |
| **Layer 2 — Practical Engineering & Workflows** | Use `ps`, `top`, `pgrep`, `kill`, `free`, `uptime`, `nice`, `jobs`, and related commands to manage workloads |
| **Layer 3 — Production Engineering & Interview Mastery** | Diagnose CPU spikes, zombie processes, memory exhaustion, hung services and unsafe termination |

---

# LAYER 1 — FUNDAMENTALS & MENTAL MODELS

## 1.1 What is a process?

A process is a running instance of a program, together with its execution state and resources.

Think of a Java application:

```bash
java -jar app.jar
```

The JAR file is a program artifact. When you execute it, the operating system creates a process to run it.

A process has, among other things:

- A PID — process identifier.
- A virtual address space for its memory.
- One or more threads of execution.
- Open file descriptors, such as files and sockets.
- Environment variables and execution credentials.
- A current state and scheduling information.

A useful distinction:

| Term | Meaning | Example |
| :--- | :--- | :--- |
| **Program** | Code or executable artifact | `app.jar` |
| **Process** | Running instance | Java process with PID `8421` |
| **Thread** | Execution path within a process | JVM garbage-collector thread |
| **Service** | A managed application or background capability | `orders-api.service` |
| **Daemon** | A background process, commonly providing a system service | `sshd` |

A service is not a special kind of process at the operating-system level. It is a way of describing and often managing an application that performs a role.

---

## 1.2 Process versus thread

```
Java application process
PID 8421 · Own virtual address space
├── Request thread 1
├── Request thread 2
├── GC thread
└── Scheduler thread
```

Threads in one process generally share its memory and resources, while maintaining their own execution state and stack.

**Why this matters in backend engineering:** a single Spring Boot process can handle many requests using multiple threads. A thread deadlock may stall work while the process remains alive. A process crash, by contrast, terminates the entire application process.

Processes are isolated from one another through operating-system mechanisms. Threads within a process share much more state, which makes communication efficient but introduces concurrency hazards.

---

## 1.3 PIDs, PPIDs and process trees

- **PID**: the process's own identifier.
- **PPID**: the identifier of its parent process.
- **Process tree**: the parent-child relationships between processes.

Example:

```text
systemd (PID 1)
└── java -jar orders-api.jar (PID 8421, PPID 1)
    ├── JVM thread 1
    ├── JVM thread 2
    └── JVM thread 3
```

This is conceptual, not a literal display of Java threads in the normal process tree. Linux can expose threads as task IDs, too.

Inspect process relationships:

```bash
ps -ef
ps -eo pid,ppid,stat,%cpu,%mem,comm --sort=-%cpu
pstree -p
```

`pstree` may not be installed by default. On macOS, `ps` supports many similar options, but Linux-specific fields and tools can differ.

---

## 1.4 Process states: what is the operating system telling you?

Common Linux process-state codes include:

| State | Meaning | Practical interpretation |
| :---: | :--- | :--- |
| **`R`** | Running or runnable | Executing or waiting for CPU time |
| **`S`** | Interruptible sleep | Waiting for an event; often normal (e.g. waiting on network I/O) |
| **`D`** | Uninterruptible sleep | Often waiting on kernel I/O or another kernel operation |
| **`T`** | Stopped or traced | Suspended or being debugged |
| **`Z`** | Zombie | Exited, but its parent has not collected its exit status |

- A process in `S` is not automatically unhealthy. Web servers spend plenty of time waiting for network traffic.
- A process in `D` is not necessarily doing heavy disk work, and it generally will not respond to ordinary termination signals until the uninterruptible wait ends.
- A zombie has already exited. It is not an active program consuming CPU like a running process. Its remaining process-table entry records the exit status for the parent to collect.

---

## 1.5 How Linux allocates CPU time

A CPU core executes a limited number of instruction streams at a time. Linux's scheduler selects runnable tasks and allocates CPU time according to scheduling policy, priority, and system conditions.

Important terms:

- **CPU utilization**: how much CPU processing capacity is being used.
- **Load average**: a measure of tasks that are runnable or in uninterruptible sleep, averaged over time (1, 5, and 15 minutes).
- **Context switch**: switching the CPU from one task to another.
- **Priority / nice value**: influences scheduling priority for ordinary processes.
- **I/O wait**: time CPUs are idle while the system has outstanding I/O; it is not simply a measurement of a particular process's disk activity.

On a multi-core machine, load average must be interpreted in relation to available CPU capacity. A load average of `4` means something different on a 2-core machine (saturated) than on a 16-core machine (mostly idle).

Inspect basic system pressure:

```bash
uptime
nproc
top
```

`nproc` reports the number of processing units available to the current process in many Linux environments. Container CPU limits and CPU affinity can affect what is available.

---

## 1.6 Memory: virtual, resident and shared

Processes typically use virtual memory. The operating system maps virtual addresses to physical memory or other backing storage as needed.

Key terms:

- **Virtual memory size (VSZ/VIRT)**: virtual address space associated with a process. It is not equivalent to physical RAM consumed.
- **Resident set size (RSS/RES)**: physical memory currently resident for a process, including potentially shared pages.
- **Shared memory**: pages used by more than one process.
- **Swap**: disk-backed memory used by the operating system under memory pressure.
- **Out-of-memory (OOM) event**: the system or a memory-limited environment cannot satisfy memory demands and terminates a process (via the Linux OOM Killer).

A Java process can reserve a large heap without immediately occupying that amount of physical memory. Likewise, RSS can include shared pages, so summing RSS across processes can overstate unique physical memory usage.

For JVMs, heap is only part of the story: metaspace, thread stacks, direct buffers, native libraries and other native allocations also consume memory.

---

## 1.7 Signals: messages to processes

A signal is an asynchronous notification delivered to a process or thread to request or report an event.

| Signal | Number on Linux | Typical use |
| :--- | :---: | :--- |
| `SIGTERM` | 15 | Request graceful termination; process can clean up |
| `SIGKILL` | 9 | Force termination immediately; cannot be caught, blocked, or ignored |
| `SIGINT` | 2 | Interrupt, commonly generated from `Ctrl+C` |
| `SIGHUP` | 1 | Traditionally terminal hangup; daemons commonly use it to reload config |
| `SIGSTOP` | 19 | Stop / pause execution; cannot be caught or ignored |
| `SIGCONT` | 18 | Resume a previously stopped process |

Use signal names instead of hardcoding numbers where practical, since signal numbering can vary by platform.

`SIGTERM` does not guarantee an application will exit. The process may be stuck, may delay shutdown, or may handle the signal in application-specific ways. `SIGKILL` is the final escalation, not the default first move.

---

## 1.8 The key mental model

```
Observe → Identify → Diagnose → Act → Verify
```

1. **Observe** the symptom: CPU, memory, latency or availability.
2. **Identify** the relevant PID and its ownership.
3. **Diagnose** the cause before terminating anything.
4. **Choose** the least disruptive corrective action (`SIGTERM` before `SIGKILL`).
5. **Verify** that service health and resource use recover.

This sequence is safer than seeing a process name and immediately killing it.

---

# LAYER 2 — PRACTICAL ENGINEERING & WORKFLOWS

## 2.1 Inspect running processes

Start with these commands whenever an application behaves unexpectedly.

### `ps` — take a process snapshot

```bash
ps -ef
ps aux
```

Useful for inspecting processes at a particular moment.

### `top` — monitor live resource usage

```bash
top
```

Refreshes process and system statistics. Press `q` to quit.

### `pgrep` — find processes by name

```bash
pgrep -af java
pgrep -af orders-api
```

The `-a` option displays command lines; `-f` matches against the full command line.

### `pstree` — understand parent-child relationships

```bash
pstree -p
```

Helpful when investigating process ownership or orphaned children.

### Sort processes by CPU usage:

```bash
ps -eo pid,ppid,stat,%cpu,%mem,etime,comm --sort=-%cpu | head -15
```

### Sort processes by resident memory (RSS):

```bash
ps -eo pid,ppid,stat,%cpu,%mem,rss,comm --sort=-rss | head -15
```

Here, `etime` is elapsed time since process start and `rss` is resident memory, typically reported in KiB on Linux.

*Important:* CPU percentages from `ps` are a snapshot or accumulated measure, depending on the field and platform. Use `top` for changing usage over time.

---

## 2.2 Inspect one specific process

Suppose your Spring Boot service is running under PID `8421`. That number is an example; use the actual PID on your machine.

```bash
ps -p 8421 -o pid,ppid,stat,%cpu,%mem,etime,args
```

On Linux, inspect its resource limits:

```bash
cat /proc/8421/limits
```

Inspect its open file descriptors:

```bash
ls -l /proc/8421/fd
```

Inspect the process's status information:

```bash
cat /proc/8421/status
```

Linux exposes process information through the `/proc` virtual filesystem. These files are generated by the kernel; they are not ordinary persistent files on disk.

On macOS, `/proc` is not available in the same Linux form. Use `ps`, `top`, `lsof` and the platform's other diagnostic tools instead.

---

## 2.3 Understand foreground and background execution

When you run:

```bash
java -jar app.jar
```

the shell normally waits for that foreground command to finish.

To run a command in the background:

```bash
java -jar app.jar &
```

The shell returns a prompt while the command continues running.

### Shell job-control commands:

| Command | Purpose |
| :--- | :--- |
| `jobs` | List jobs known to the current shell |
| `Ctrl+C` | Send an interrupt (`SIGINT`) to the foreground command |
| `Ctrl+Z` | Suspend (`SIGTSTP`) the foreground job |
| `bg` | Resume a suspended job in the background |
| `fg` | Bring a shell job into the foreground |
| `wait` | Wait for a child job or process managed by the shell |

Example:

```bash
sleep 300 &
jobs
```

You can then use `fg` to bring the job back to the foreground and press `Ctrl+C` to interrupt it.

Shell jobs are not the same as system services. If you close a terminal, the behavior of background jobs depends on terminal/session handling and shell configuration. Do not rely on `&` to deploy a production backend.

---

## 2.4 Terminate a process safely

The normal escalation sequence is:

### 1. Identify
Confirm the PID, command and owner:
```bash
ps -p PID -f
```

### 2. Request graceful shutdown
Allow the application to clean up state, flush buffers, and close connections:
```bash
kill -TERM PID
```

### 3. Verify
Check whether the process exited and service health recovered:
```bash
ps -p PID
```

### 4. Escalate only if justified
Force termination only after understanding the consequences:
```bash
kill -KILL PID
```

In a real terminal, replace `PID` with the actual numeric process ID:

```bash
kill -TERM 8421
ps -p 8421
```

If the process remains, investigate why before escalating. A process may be shutting down, blocked, or stuck in uninterruptible sleep (`D`).

`kill` sends signals; it does not necessarily terminate a process. Its name is a historical misnomer.

**Production caution:** manually killing a service managed by `systemd`, Kubernetes or another supervisor may trigger an automatic restart. Prefer the appropriate service-management command when available.

---

## 2.5 Monitor memory and CPU pressure

Run:

```bash
uptime
free -h
vmstat 1 5
```

What each tells you:

- `uptime` — uptime, load averages (1, 5, 15 min), and logged-in user count.
- `free -h` — memory and swap summary (total, used, free, shared, buff/cache, available).
- `vmstat 1 5` — five reports at one-second intervals, including runnable tasks (`r`), blocked tasks (`b`), memory, swapping (`si`/`so`), I/O (`bi`/`bo`), and CPU statistics (`us`, `sy`, `id`, `wa`, `st`).

On Linux, the `available` memory figure in `free -h` is usually more useful than simply treating all memory listed as used as unavailable. Linux uses spare RAM for caches that can readily be reclaimed when applications demand memory.

If `vmstat` shows sustained swapping alongside latency, investigate memory pressure. Swapping alone does not prove an incident.

---

## 2.6 Adjust scheduling priority with `nice`

Linux lets you influence the scheduling priority of ordinary processes using a nice value.

- **Lower nice value**: higher scheduling priority (range: -20 to 19).
- **Higher nice value**: lower scheduling priority (range: -20 to 19).
- **Default nice value**: `0`.

Start a noncritical CPU-heavy job at lower priority:

```bash
nice -n 10 ./batch-job.sh
```

Inspect priorities:

```bash
ps -eo pid,ni,pri,comm --sort=ni | head
```

Adjust an existing process where permitted:

```bash
renice 10 -p 8421
```

Nice values do not reserve CPU, cap resource usage, or guarantee that a particular application will run faster. They are scheduling hints within the applicable scheduling policy.

Use CPU quotas (e.g. via cgroups / container limits) when hard limits are needed.

---

## 2.7 Understand environment variables and process execution

Processes inherit environment variables from the environment that launches them.

```bash
export APP_ENV=development
java -jar app.jar
```

In this example, the Java process inherits `APP_ENV`.

Inspect the current shell environment:

```bash
env
printenv APP_ENV
```

On Linux, the process environment may be inspectable through `/proc/PID/environ`, subject to permissions. Treat it as sensitive: environment variables can contain tokens, credentials or other secrets.

Avoid dumping complete environments into logs or screenshots. For production services, use deliberate secret-management practices rather than relying on an interactive shell's exported variables.

---

## 2.8 Service management: the production distinction

On many Linux distributions using `systemd`, services can be inspected with:

```bash
systemctl status orders-api
journalctl -u orders-api --since "15 minutes ago"
```

To request a managed restart:

```bash
sudo systemctl restart orders-api
```

To inspect service configuration:

```bash
systemctl cat orders-api
```

These commands apply to a Linux host with `systemd` and a service named `orders-api`. Your application may use a different service manager or run inside a container.

A managed service gives you a place to define startup behavior, restart policies, dependencies and logging integration. A raw background process gives you much less operational control.

---

## 2.9 Practical workflow: investigate a CPU spike

Imagine your API's latency suddenly increases.

Run the following sequence:

```bash
uptime
nproc
ps -eo pid,ppid,stat,%cpu,%mem,etime,args --sort=-%cpu | head -15
```

Then:

1. Determine whether the problem is system-wide or concentrated in one process.
2. Confirm the process identity and whether its CPU usage remains high.
3. Check logs and recent deployments.
4. Inspect application-level metrics, thread dumps or profiling data.
5. Correct the underlying cause and verify recovery.

For a Java process, a thread dump can help investigate lock contention, deadlocks and busy loops:

```bash
jcmd 8421 Thread.print
```

`jcmd` must be available in the relevant JDK environment, and permissions and container boundaries may affect whether the command works. Capture diagnostic data before terminating the process when doing so is safe.

---

# LAYER 3 — PRODUCTION ENGINEERING & INTERVIEW MASTERY

## 3.1 Incident simulation: CPU at 100%

### Incident A — High CPU, rising API latency

**Scenario:** A Spring Boot service is responding slowly. One CPU core is saturated, and the process appears near 100% CPU on the host.

### Your investigation plan:

1. **Confirm scope**: Check load average, CPU capacity (`nproc`), and whether other processes are affected.
2. **Identify the hot process**: Sort processes by CPU usage (`ps -eo pid,%cpu,comm --sort=-%cpu`) and confirm the service PID.
3. **Find the hot thread**: Capture a JVM thread dump or use a profiler. On Linux, a thread-level `top` view identifies the busy thread ID:
   ```bash
   top -H -p 8421
   ```
4. **Correlate with application evidence**: Check request volume, error rates, recent releases, garbage collection frequency, and dependency latency.
5. **Mitigate and verify**: Roll back a bad release, stop an offending background job, or apply a justified fix. Confirm latency and resource usage recover.

Do not assume high CPU means a memory leak. Busy loops, expensive computation, excessive request volume, JSON serialization bottlenecks, lock contention, and excessive garbage collection can all contribute.

**Production lesson:** A process is a symptom boundary, not necessarily the root cause.

---

## 3.2 Incident simulation: memory exhaustion

### Incident B — The service keeps restarting

**Scenario:** Your backend becomes unavailable and then restarts. Memory usage rises before each failure.

### Separate the possible causes:

- JVM heap exhaustion (e.g. `java.lang.OutOfMemoryError: Java heap space`).
- Native memory exhaustion (thread stacks, direct byte buffers, Metaspace, JNI).
- Host-level memory pressure resulting in a kernel OOM kill.
- Container memory-limit enforcement (cgroup OOM killer in Docker/Kubernetes).
- A supervisor (`systemd`/Kubernetes) restarting a process after a failed health/liveness probe.

Start with host-level evidence:

```bash
free -h
ps -eo pid,%mem,rss,vsz,comm --sort=-rss | head -15
```

Check kernel logs if permissions and distribution allow:

```bash
sudo journalctl -k --since "30 minutes ago"
```

Search logs for OOM-killer events:

```bash
sudo dmesg -T | grep -i -E "oom|out of memory|killed process"
```

Do not assume that a missing log entry proves no OOM occurred; access restrictions, log retention, and container isolation can hide kernel logs. For a JVM, inspect heap and GC logs.

**Production lesson:** Distinguish application-level heap exhaustion from operating-system or container-level memory exhaustion before choosing a fix.

---

## 3.3 Incident simulation: zombie processes

A zombie (`Z`) is a process that has already exited but whose parent has not yet collected its exit status.

Inspect process states:

```bash
ps -eo pid,ppid,stat,comm | awk '$3 ~ /Z/'
```

Investigate a zombie's parent:

```bash
ps -o pid,ppid,stat,comm -p 8421
ps -o pid,ppid,stat,comm -p 8100
```

Here, `8421` represents the zombie PID and `8100` its hypothetical parent PID.

### What should you do?

1. Identify the parent process (`PPID`).
2. Determine why the parent is not reaping child processes (missing `wait()` / `waitpid()` calls).
3. Investigate the parent's behavior and application logs.
4. Correct the parent application's child-process handling where possible.

**Why `kill -9` fails on zombies:** Sending `SIGKILL` to a zombie will not remove it because it has already exited and has no code running. The parent must collect its exit status; if the parent terminates, the zombie is reparented to PID 1 (`init` / `systemd`), which automatically reaps it.

A few zombies are not necessarily a major incident. A growing number indicates an application process-management bug.

---

## 3.4 Incident simulation: a process refuses to terminate

Suppose you run:

```bash
kill -TERM 8421
```

but the process remains active.

### Diagnostic Decision Tree:

```
Process remains after SIGTERM
       |
       +---> State 'S' or 'R': Investigate shutdown handling, blocked threads, 
       |                       stuck shutdown hooks, or active network socket flushes.
       |
       +---> State 'D': Process is in Uninterruptible Sleep waiting on kernel I/O 
       |                (e.g., hung NFS mount or failing disk). Signals cannot be delivered.
       |
       +---> State 'Z': Process is a Zombie (already exited). The parent must reap it.
       |
       +---> PID gone: Process successfully exited. Verify before assuming a reused PID.
```

This is why repeatedly sending `SIGKILL` is not a universal solution. The right response depends on the process state and underlying cause.

---

## 3.5 Production safety rules

1. **Inspect before acting**: Confirm the PID, executable, owner, and service role before sending signals.
2. **Prefer graceful shutdown**: Give applications a chance to flush data, close connections, and complete in-flight transactions with `SIGTERM`.
3. **Preserve evidence**: Capture logs, metrics, thread dumps, and heap snapshots before restarting when safe to do so.
4. **Respect orchestration**: Use the service manager (`systemctl`) or orchestrator (`kubectl`) lifecycle controls rather than raw `kill` commands.
5. **Verify the outcome**: Check application health and user-facing behavior, not just whether a PID disappeared from `ps`.

---

# 4. Interview Mastery — 15 Core Questions & Answers

### Q1. What is the difference between a program and a process?
**Answer**: A program is a passive executable file or artifact stored on disk (e.g., `app.jar` or a binary). A process is an active, running instance of that program loaded into memory with its own PID, virtual address space, open file descriptors, security context, and execution threads.

### Q2. What is a PID?
**Answer**: A PID (Process Identifier) is a unique integer assigned by the operating system kernel to track and manage each active process in the system process table.

### Q3. What is the difference between a process and a thread?
**Answer**: A process is an isolated execution environment with its own dedicated memory space. Threads exist within a process and share its heap, open files, and address space, but each thread maintains its own program counter, registers, and execution stack.

### Q4. What is a zombie process?
**Answer**: A zombie process (State `Z`) is a process that has completed execution and exited, but whose entry remains in the process table because its parent process has not yet read its exit status via the `wait()` or `waitpid()` system call.

### Q5. Can you kill a zombie process?
**Answer**: No. A zombie process is already dead—it executes no instructions and occupies no physical RAM. Because it cannot process signals, `kill -9` has no effect. It can only be cleared when its parent reaps it, or when its parent is terminated and PID 1 (`systemd`/`init`) inherits and reaps it.

### Q6. What is the difference between `SIGTERM` and `SIGKILL`?
**Answer**: `SIGTERM` (signal 15) is a cooperative request asking a process to terminate; the process can catch, handle, or block it to perform graceful cleanup. `SIGKILL` (signal 9) is handled directly by the kernel and cannot be caught, blocked, or ignored, terminating the process immediately.

### Q7. Why should `SIGKILL` not be your first choice?
**Answer**: `SIGKILL` aborts the process immediately without running shutdown hooks. This can leave transactions in-flight, corrupt files, abandon database connections without clean closure, and prevent flushing of buffered data to disk.

### Q8. What is load average?
**Answer**: Load average measures the average number of processes in the system that are either running, runnable (waiting for CPU), or in uninterruptible sleep (state `D`, waiting on I/O) over 1, 5, and 15-minute windows. It must be compared against the number of available CPU cores (`nproc`).

### Q9. Does high memory usage always indicate a memory leak?
**Answer**: No. Linux aggressively uses free RAM for buffer and page caches to accelerate I/O, which it reclaims automatically when applications demand memory. Additionally, JVM applications often pre-allocate their heap up to `-Xmx` even when the live set of objects is small.

### Q10. What is RSS?
**Answer**: RSS (Resident Set Size) is the amount of physical RAM currently allocated to and held by a process in memory, including shared library pages currently resident.

### Q11. What is virtual memory?
**Answer**: Virtual memory is an operating-system abstraction that maps each process's virtual address space (VSZ) to physical RAM or secondary storage (swap), providing process isolation and enabling programs to address more memory than physical RAM.

### Q12. What does `nice` do?
**Answer**: `nice` sets or modifies the scheduling priority of a process in the Linux scheduler. Nice values range from -20 (highest priority) to 19 (lowest priority, "nicest" to other processes). Ordinary users can only lower their priority (increase nice value).

### Q13. What is the difference between a service and a process?
**Answer**: A process is the low-level operating-system execution entity. A service is a higher-level system abstraction (typically managed by a daemon like `systemd`) that configures startup dependencies, automatic restarts, resource limits, logging, and lifecycle commands.

### Q14. How would you investigate a CPU spike?
**Answer**: 
1. Check `uptime` and `nproc` to assess system-wide CPU saturation.
2. Run `top` or `ps -eo pid,%cpu,comm --sort=-%cpu` to identify the culprit PID.
3. For Java applications, run `top -H -p PID` to identify the specific burning thread, convert the thread PID to hex, and locate it in a JVM thread dump (`jcmd PID Thread.print`).
4. Review application logs and APM metrics for concurrency bottlenecks, GC spikes, or infinite loops.

### Q15. Why might a process remain after `SIGTERM`?
**Answer**: 
1. It is still executing graceful shutdown routines or flushing buffers.
2. It has blocked or ignored `SIGTERM`.
3. It is stuck in an uninterruptible sleep state (`D`), waiting for an unresponsive kernel I/O call (e.g., a stalled NFS share).
4. It is deadlocked within a shutdown hook.

---

# 5. Hands-On Lab — Process Detective

Complete this lab in a terminal. The commands are designed for a local development environment; avoid experimenting with termination commands against production processes.

### Lab A — Create and inspect a process

Start a harmless process:

```bash
sleep 300 &
```

Then run:

```bash
jobs
pgrep -af 'sleep 300'
ps -ef | grep '[s]leep 300'
```

Record its PID and inspect it:

```bash
ps -p YOUR_PID -o pid,ppid,stat,%cpu,%mem,etime,args
```

*Replace `YOUR_PID` with the actual number.* Notice that the process is in state `S` (interruptible sleep) and consumes virtually zero CPU.

### Lab B — Observe resource usage

Run:

```bash
uptime
free -h
ps -eo pid,stat,%cpu,%mem,rss,comm --sort=-%cpu | head -10
```

Answer these questions:
- What is your current load average?
- How many processing units are available?
- Which process appears to be consuming the most CPU?
- Why might `free -h` show memory as used even when the machine feels idle?

### Lab C — Terminate cleanly

Send a termination request to the PID created by your own `sleep` command:

```bash
kill -TERM YOUR_PID
```

Verify:

```bash
ps -p YOUR_PID
```

The process should exit cleanly. If it has already exited, that is the expected outcome.

### Lab D — Investigate a simulated backend incident

Imagine your backend has the following symptoms:
- API latency has increased.
- One process consumes a large amount of CPU.
- Memory usage has remained relatively stable.
- The problem began immediately after a deployment.

Write a short incident note containing:
1. Three commands you would run first (e.g. `uptime`, `ps -eo pid,%cpu,comm --sort=-%cpu`, `jcmd PID Thread.print`).
2. Two likely causes (e.g. infinite loop / algorithmic regression, lock contention / busy wait).
3. The evidence you would collect before restarting (thread dumps, recent commit diff, application error logs).
4. One mitigation (immediate rollback to previous release artifact).
5. The metrics you would monitor to verify recovery (P99 API response latency, CPU utilization %, load average).

---

# 6. Chunk 2 Mastery Checklist

### Layer 1 — Fundamentals & Mental Models
- [ ] Explain processes, threads, PIDs, PPIDs and process states (`R`, `S`, `D`, `T`, `Z`).
- [ ] Distinguish load average from CPU utilization.
- [ ] Explain virtual memory (VSZ), resident set size (RSS), swap and OOM events.
- [ ] Explain `SIGTERM`, `SIGKILL`, `SIGINT`, `SIGHUP` and signal delivery semantics.
- [ ] Explain why zombie processes cannot be killed with `SIGKILL`.

### Layer 2 — Practical Engineering & Workflows
- [ ] Inspect processes using `ps`, `top`, and `pgrep`.
- [ ] Inspect process details, limits, and file descriptors via `/proc/PID/`.
- [ ] Use shell job-control commands (`&`, `jobs`, `fg`, `bg`, `Ctrl+Z`, `Ctrl+C`).
- [ ] Execute the 4-step safe termination sequence (`ps` → `kill -TERM` → verify → escalate).
- [ ] Inspect memory and swap with `free -h` and `vmstat 1 5`.
- [ ] Adjust process scheduling priority using `nice` and `renice`.
- [ ] Manage and inspect background services via `systemctl` and `journalctl`.

### Layer 3 — Production Engineering & Interview Mastery
- [ ] Execute a methodical CPU spike investigation (load average → hot PID → hot thread → thread dump).
- [ ] Distinguish JVM heap exhaustion from OS kernel / container cgroup OOM kills.
- [ ] Troubleshoot zombie processes by diagnosing and remedying parent process reaping.
- [ ] Apply the decision tree for processes that refuse to terminate upon `SIGTERM`.
- [ ] Answer all 15 interview questions with production-tested technical explanations.
- [ ] Complete the hands-on process detective lab.

---

## Chunk Completion Protocol
- Authoritative source file: `content/linux/02-processes-signals-resource-management.md`.
- No chunk-level PDF generated.
- Complete Linux handbook PDF (`BEH_LINUX_COMPLETE_HANDBOOK.pdf`) is compiled only after all six Linux chunks are complete and verified.

---

## What Comes Next?

**Linux Chunk 3 of 6 — Networking & Connectivity Debugging**

We will cover:
- TCP/IP model, IP addressing, DNS resolution (`/etc/resolv.conf`, `dig`, `nslookup`).
- Listening ports, established connections, and socket states (`ss`, `netstat`, `lsof -i`).
- Connectivity debugging (`ping`, `traceroute`, `curl -v`, `nc`/`ncat`, `telnet`).
- Diagnosing connection timeouts, "connection refused", and DNS lookup failures.
- Production incident simulations: downstream service unreachable, port conflicts, connection pool leaks.
- Practical networking lab and interview questions.
