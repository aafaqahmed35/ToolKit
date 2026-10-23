# Linux Chunk 4 of 6 — Logs, Permissions & System Troubleshooting

Phase I · Developer Foundations  
Backend Engineering Handbook

Source file: `content/linux/04-logs-permissions-system-troubleshooting.md`

Your backend is running, but requests are failing. The log file says `Permission denied`. The server reports that it cannot write to disk. Or a service works when you launch it manually but fails when started by the system.

These are everyday engineering problems. This chunk teaches you how to read evidence, understand Linux permissions, investigate storage issues and troubleshoot systematically without making risky changes.

---

## Three Learning Layers

| Layer | Focus & Objective |
| :--- | :--- |
| **Layer 1 — Fundamentals & Mental Models** | Logs, file ownership, permission bits, users, groups, disk capacity and inodes |
| **Layer 2 — Practical Engineering & Workflows** | `tail`, `grep`, `journalctl`, `chmod`, `chown`, `df`, `du`, `stat` and diagnostic workflows |
| **Layer 3 — Production Engineering & Interview Mastery** | Investigate permission errors, full disks, missing logs, service startup failures and operational risks |

---

# 1. Layer 1 — Fundamentals & Mental Models

## 1.1 Logs are evidence, not just text

A log records events produced by an application, operating system or infrastructure component.

For a Spring Boot application, you might see:

```text
2026-10-23 08:15:04 INFO  Application started
2026-10-23 08:16:12 WARN  Database connection retry
2026-10-23 08:16:17 ERROR Failed to process order
```

A useful log entry usually provides some combination of:
- Timestamp (ISO 8601 or standard localized time)
- Severity level (`INFO`, `WARN`, `ERROR`)
- Component or logger name (e.g. `c.e.b.OrderService`)
- Message describing the event
- Request or trace identifier (`traceId`, `spanId` for distributed tracing)
- Exception details and stack trace

**Logs** answer questions about *what* happened. **Metrics** help quantify *how frequently* or *how severely* something is happening. **Traces** help connect work across components.

A production investigation often combines all three.

---

## 1.2 Understand log severity

| Level | Typical meaning | Practical Production Impact |
| :--- | :--- | :--- |
| **`TRACE`** | Very detailed diagnostic information | High volume; typically disabled in production |
| **`DEBUG`** | Information useful during development | Verbose; enabled temporarily during incident isolation |
| **`INFO`** | Normal application milestone events | Baseline operational visibility (app started, job completed) |
| **`WARN`** | Unexpected condition that may not be fatal | Potential issue; connection retry or fallback invoked |
| **`ERROR`** | A failure requiring attention | Operation failed; unhandled exception or failed transaction |

Exact semantics depend on the application and logging framework.

An `ERROR` entry does not automatically mean the entire service is down. Similarly, the absence of an error entry does not prove the service is healthy: logging may be misconfigured, incomplete, or written to an unlinked file.

---

## 1.3 Where do Linux logs live?

Common sources include:

- **Application logs**: Files configured by the application framework (e.g. `/var/log/app/app.log`), or output written to standard output and standard error.
- **System logs**: Managed through `systemd`'s journal (`systemd-journald`), accessible via `journalctl`.
- **Traditional log files**: Stored under `/var/log/`, such as `/var/log/syslog`, `/var/log/auth.log` (Debian/Ubuntu), or `/var/log/secure`, `/var/log/messages` (RHEL/CentOS).
- **Container logs**: Captured from container `stdout`/`stderr` by the container runtime (Docker, containerd) and stored as JSON or binary logs on the host.

Do not assume every Linux machine uses the same logging system or stores every log in the same location.

---

## 1.4 Linux permissions: who can do what?

Every filesystem object has an owner and a group, plus permission bits that control access.

The three common permission classes are:
- **User (`u`)** — the file's owner.
- **Group (`g`)** — members of the file's assigned group.
- **Others (`o`)** — everyone else on the system.

The three basic permission bits are:

| Bit | For Regular Files | For Directories |
| :---: | :--- | :--- |
| **`r`** (read) | Read file contents | List filenames inside the directory (`ls`) |
| **`w`** (write) | Modify or truncate file contents | Create, delete, or rename entries inside directory |
| **`x`** (execute) | Execute file as a program/script | Traverse / enter directory (`cd`) and access its files |

**Directory permissions are especially important.** Reading a file requires execute (`x`) permission on *every* parent directory in its absolute path.

Inspect permissions:

```bash
ls -l app.log
```

Example output:

```text
-rw-r----- 1 appuser appgroup 2048 Oct 23 08:15 app.log
```

Interpret it:
- `-` — regular file (first character denotes file type; `d` for directory).
- `rw-` — owner (`appuser`) can read and write.
- `r--` — group (`appgroup`) can read only.
- `---` — others have no permissions.
- `appuser` — owner user.
- `appgroup` — owner group.

---

## 1.5 Numeric permissions: why 755 and 644 exist

The standard octal representation maps bits as powers of 2:

| Permission | Bit Symbol | Octal Value |
| :--- | :---: | :---: |
| **Read** | `r` | **4** |
| **Write** | `w` | **2** |
| **Execute** | `x` | **1** |

Add the values for each permission class:
- `7` = 4 + 2 + 1 = read, write, execute (`rwx`)
- `6` = 4 + 2 + 0 = read, write (`rw-`)
- `5` = 4 + 0 + 1 = read, execute (`r-x`)
- `4` = 4 + 0 + 0 = read only (`r--`)
- `0` = 0 + 0 + 0 = no permissions (`---`)

Therefore:
- `755` = `rwxr-xr-x` (Owner: rwx; Group: r-x; Others: r-x)
- `644` = `rw-r--r--` (Owner: rw-; Group: r--; Others: r--)
- `600` = `rw-------` (Owner: rw-; Group: none; Others: none)

Typical examples:
- `755`: Standard executable directory, script, or binary.
- `644`: Standard non-sensitive configuration file or public text document.
- `600`: Sensitive private key, TLS certificate key, or database password file.

These are guidelines, not universal defaults. Sensitive files must receive only the access their specific service identity requires.

---

## 1.6 Ownership and identity

A process runs with a particular user (UID) and group (GID) identity. File access is evaluated against those credentials and the applicable permission bits.

Inspect your current identity:

```bash
whoami
id
groups
```

Inspect a file's owner and metadata:

```bash
stat app.log
ls -l app.log
```

A service might run as `appuser`, while a directory is owned by `root`. Even if the file exists and the application is running, the service will receive `Permission denied` when attempting to write.

**Key mental model:** Permissions are checked against the *process's effective credentials*, not against the person who happens to be logged into a separate terminal.

---

## 1.7 Disk space versus inodes

A server can run out of storage in two distinct ways:

1. **Disk block capacity**: The filesystem has no remaining free data blocks to store bytes.
2. **Inode exhaustion**: The filesystem has no remaining free inode entries to create new files or directories.

Every file, directory, and symlink requires one inode to store metadata (ownership, timestamps, block pointers). A directory containing millions of tiny session files or temp files can completely exhaust inodes even when hundreds of gigabytes of disk block capacity remain.

Check both:

```bash
df -h
df -i
```

- `df -h`: reports disk storage capacity in human-readable units (GB/MB).
- `df -i`: reports inode capacity, used count, and free count.

---

## 1.8 `du` versus `df`

These commands answer different questions:

```bash
df -h
du -sh /var/log
```

- `df -h` queries the filesystem superblock to report filesystem-wide used, free, and total space.
- `du -sh` traverses the directory tree recursively and sums the sizes of files it can read.

Their numbers often differ because of:
- Reserved root blocks (typically 5% reserved by `ext4`).
- Mount boundaries and unmounted underlying data.
- Read permissions preventing `du` from reading certain directories.
- **Deleted files still held open by a running process.**

That last case is critical in production: a log file can be unlinked from the directory with `rm`, but its disk blocks are not freed until the process holding its open file descriptor closes it or terminates!

---

# 2. Layer 2 — Practical Engineering & Workflows

## 2.1 Read logs without opening enormous files

Never open multi-gigabyte production logs with `nano` or `vim`—doing so consumes massive memory and can crash a host. Use streaming tools:

### `tail -n 100 app.log`
Read the latest 100 lines:
```bash
tail -n 100 app.log
```

### `tail -f app.log`
Follow new log entries as they are appended in real time (`Ctrl+C` to stop):
```bash
tail -f app.log
```

### `head -n 50 app.log`
Read the first 50 lines (useful for startup banner / initialization configs):
```bash
head -n 50 app.log
```

### `less app.log`
Navigate through a file interactively without loading the entire file into RAM (`Shift+F` to follow, `/pattern` to search, `q` to quit):
```bash
less app.log
```

### `grep -n 'ERROR' app.log`
Find matching lines and display their line numbers:
```bash
grep -n 'ERROR' app.log
```

### `grep -i 'timeout' app.log`
Search case-insensitively for timeout-related messages:
```bash
grep -i 'timeout' app.log
```

### `grep -C 3 'Exception' app.log`
Show 3 lines of context before and after each match:
```bash
grep -C 3 'Exception' app.log
```

### Live filtered stream:
```bash
tail -f app.log | grep --line-buffered -i 'error'
```
*Note:* Filtering live output can hide surrounding context. Always inspect preceding lines when an error occurs.

---

## 2.2 Inspect systemd service logs

On modern Linux distributions, `journalctl` interfaces directly with `systemd-journald`:

```bash
journalctl -u orders-api
```

Useful variations:

| Command | Purpose |
| :--- | :--- |
| `journalctl -u orders-api -n 100` | Show latest 100 entries |
| `journalctl -u orders-api -f` | Follow live log stream |
| `journalctl -u orders-api --since "30 minutes ago"` | Filter entries from the last 30 minutes |
| `journalctl -u orders-api -p err` | Filter to error priority and above (`err`, `crit`, `alert`, `emerg`) |
| `journalctl -b` | Show messages from the current system boot |
| `journalctl -u orders-api --since "2026-10-23 08:00:00" --until "2026-10-23 08:30:00"` | Precise incident window slicing |

---

## 2.3 Fix permissions precisely

Suppose your application needs to read a private configuration file:

```bash
ls -l application.properties
```

If the owner should read and write, and all others have zero access:
```bash
chmod 600 application.properties
```

If a deployment script needs to be executable by its owner:
```bash
chmod u+x deploy.sh
```

If the service user should own its log directory:
```bash
sudo chown -R appuser:appgroup /var/log/orders-api
```

**Safety Rule:** Before running `chown -R`, verify the exact target path. A typo like `chown -R appuser / var/log/...` (with an accidental space) modifies root `/` and wrecks the operating system!

**Avoid `chmod -R 777`:** It grants world-writable permissions to all users, creates critical security vulnerabilities, and masks the underlying ownership issue.

---

## 2.4 Diagnose a permission error systematically

Suppose your Java service logs:
```text
java.io.FileNotFoundException: /var/log/orders-api/app.log (Permission denied)
```

Systematic diagnostic checklist:

```bash
ls -ld /var /var/log /var/log/orders-api
ls -l /var/log/orders-api
id appuser
```

1. **Existence**: Does the target directory actually exist?
2. **Directory Traversal**: Does `appuser` have execute (`x`) permission on `/var`, `/var/log`, and `/var/log/orders-api`?
3. **Write Permission**: Does `appuser` have write (`w`) permission in `/var/log/orders-api` to create `app.log`?
4. **Ownership**: Is an existing `app.log` owned by `root` from an accidental manual run?
5. **ACLs**: Are POSIX Access Control Lists restricting access?
   ```bash
   getfacl /var/log/orders-api
   ```

Do not alter permissions until you identify the running service's effective user identity.

---

## 2.5 Find large directories and files

When disk usage spikes:

### Step 1: Check filesystem capacity
```bash
df -h
```

### Step 2: Identify large directories on the affected filesystem
```bash
sudo du -xhd1 /var 2>/dev/null | sort -h
```
Flags:
- `-x`: stay on one filesystem (avoids crossing NFS mounts or procfs).
- `-h`: print human-readable units.
- `-d1`: summarize only one directory depth level.

### Step 3: Locate individual large files
```bash
sudo find /var -xdev -type f -size +500M -print
```
Searches `/var` for regular files exceeding 500 MB.

Finding a large file does not mean it is safe to delete. Determine which application owns it, whether it is active, and whether it is required for auditing or crash analysis.

---

## 2.6 Investigate deleted files that still occupy space

When `df -h` reports 100% full, but `du -sh` finds only a few gigabytes:

```bash
sudo lsof +L1
```

Or:

```bash
sudo lsof | grep '(deleted)'
```

This lists open files with link count `< 1`.

### The deleted file lifecycle:
1. Application writes millions of lines to `/var/log/app.log`.
2. An engineer runs `rm /var/log/app.log` to reclaim space.
3. The directory entry is deleted, so `ls` and `du` no longer see it.
4. The application process still holds the open file descriptor.
5. Disk blocks remain allocated on disk until the process closes the descriptor or terminates.

### Remediation:
- Truncate active logs instead of deleting: `> /var/log/app.log` (preserves descriptor while zeroing bytes).
- Instruct the daemon to reopen logs via `SIGHUP` or logrotate.
- Restart the service (`sudo systemctl restart orders-api`) to release the descriptor.

---

## 2.7 Inspect disk usage and mount points

```bash
df -h
df -i
findmnt
lsblk
```

- `df -h`: Capacity, used, and available space per filesystem.
- `df -i`: Inode exhaustion check.
- `findmnt`: Tree of mounted filesystems, target mountpoints, source devices, and mount options (`ro`, `rw`, `noexec`).
- `lsblk`: Physical and virtual block devices, partitions, and LVM volumes.

A filesystem can be 100% full even when an adjacent partition has hundreds of free gigabytes. Always identify the specific mount point containing the failing path.

---

## 2.8 Standard output and standard error

| Stream | File Descriptor | Purpose |
| :--- | :---: | :--- |
| **Standard Input (`stdin`)** | `0` | Program input stream |
| **Standard Output (`stdout`)** | `1` | Normal operational output |
| **Standard Error (`stderr`)** | `2` | Diagnostic and error messages |

Redirect stdout:
```bash
./run-job.sh > output.log
```

Redirect stderr:
```bash
./run-job.sh 2> error.log
```

Redirect both to the same file:
```bash
./run-job.sh > combined.log 2>&1
```

For long-running backend services, configure proper `systemd` logging or file appenders rather than ad-hoc terminal redirection.

---

## 2.9 Diagnose a service that works manually but fails under systemd

When an application runs fine as `java -jar app.jar` from your terminal but fails when started via `systemctl start orders-api`:

Inspect service definition:
```bash
systemctl status orders-api
systemctl cat orders-api
journalctl -u orders-api -n 100
```

Common root causes:
1. **User identity**: Your terminal runs as `youruser` (or `root`), while `systemd` runs as `appuser` (which lacks file permissions).
2. **Working directory**: You ran it from `/opt/app`, while `systemd` defaults to `/` if `WorkingDirectory=` is omitted.
3. **Environment variables**: Your shell loaded `.bashrc` or `.zshrc` (`JAVA_HOME`, `PATH`), which are absent in `systemd`'s clean environment.
4. **Relative paths**: Application looked for `./config/application.yml` relative to an unexpected directory.

---

# 3. Layer 3 — Production Engineering & Interview Mastery

## 3.1 Incident simulation A — The disk is full

**Incident:** API cannot write logs; database writes fail; server reports `No space left on device`.

### Investigation sequence:
1. Check filesystem capacity:
   ```bash
   df -h
   ```
2. Check inode exhaustion:
   ```bash
   df -i
   ```
3. Locate the largest directory on the full partition:
   ```bash
   sudo du -xhd1 /var/log | sort -h
   ```
4. Check for unlinked open files consuming space:
   ```bash
   sudo lsof +L1
   ```
5. Safe remediation:
   - Truncate active logs rather than deleting: `truncate -s 0 /var/log/app.log` or `> /var/log/app.log`.
   - Remove old, compressed log archives (`*.log.gz` older than 30 days).
   - Clean package manager caches (`sudo apt clean` / `sudo dnf clean all`).
6. Verification: Check `df -h` and confirm application writes resume normally.

**Mitigation principle:** Never delete active databases, core system binaries, or files without identifying their owning service.

---

## 3.2 Incident simulation B — Permission denied after deployment

**Scenario:** A deployment pipeline deploys a new JAR. The service restarts but fails with:
`java.io.FileNotFoundException: /var/log/orders-api/app.log (Permission denied)`

### Investigation workflow:
```bash
systemctl status orders-api
id appuser
namei -l /var/log/orders-api/app.log
```

`namei -l` prints the permissions and ownership of every step in the path:
```text
f: /var/log/orders-api/app.log
drwxr-xr-x root    root     /
drwxr-xr-x root    root     var
drwxr-xr-x root    root     log
drwxr-xr-x root    root     orders-api
-rw-r--r-- root    root     app.log
```
*Diagnosis:* The deployment script ran as `root`, creating `app.log` owned by `root:root`. The service runs as `appuser`, which cannot write to a root-owned file!

### Safe remediation:
```bash
sudo chown -R appuser:appgroup /var/log/orders-api
sudo systemctl restart orders-api
```

---

## 3.3 Incident simulation C — The application logs stopped appearing

A service is receiving traffic, but no new log entries appear in `/var/log/orders-api/app.log`.

### Systematic triage:
1. **Did the process restart or exit?** Check `systemctl status orders-api` and `uptime`.
2. **Did log rotation occur?** Check if `logrotate` renamed `app.log` to `app.log.1`, but the application process still has the old inode open without reopening `app.log`.
3. **Is the logger level suppressed?** Did a configuration update change logging to `ERROR` only?
4. **Did disk fill up?** Check `df -h`.
5. **Is the file unlinked?** Check `lsof -p PID | grep app.log`.

**Production lesson:** Missing logs are a diagnostic symptom. They do not prove an application is stopped.

---

## 3.4 Interview Questions — 15 Core Questions & Answers

### Q1. What is the difference between application logs and metrics?
**Answer**: Logs are discrete, structured or unstructured event records describing *what* occurred at a specific point in time (including stack traces and context). Metrics are numeric aggregations (counters, gauges, histograms) sampled over intervals that quantify *how much* or *how fast* things are happening (e.g. error rate, CPU %).

### Q2. What does `chmod 644` mean?
**Answer**: It sets permissions to `rw-r--r--`:
- Owner has Read and Write (`4 + 2 = 6`).
- Group has Read only (`4`).
- Others have Read only (`4`).
Commonly used for non-executable files, configurations, and public documents.

### Q3. What does `chmod 755` mean?
**Answer**: It sets permissions to `rwxr-xr-x`:
- Owner has Read, Write, and Execute (`4 + 2 + 1 = 7`).
- Group has Read and Execute (`4 + 1 = 5`).
- Others have Read and Execute (`4 + 1 = 5`).
Commonly used for executable binaries, scripts, and directories.

### Q4. What does `chown` do?
**Answer**: `chown` (change owner) changes the user ownership and/or group ownership of filesystem objects (e.g. `chown user:group file.txt`).

### Q5. Why is `chmod 777` usually a bad fix?
**Answer**: It grants unrestricted read, write, and execute permissions to all users on the system. This creates severe security risks (any compromised local user can overwrite code or inject malware) and masks the true underlying user/group misconfiguration.

### Q6. Why do directory execute (`x`) permissions matter?
**Answer**: For directories, the execute bit (`x`) controls search and traversal access. Without `x` permission on a directory, a user cannot `cd` into it, open files inside it, or traverse through it, even if the user has read permissions on individual files within that directory.

### Q7. What is the difference between `df` and `du`?
**Answer**: `df` (disk free) queries the filesystem superblock to report total, used, and available capacity across mounted filesystems. `du` (disk usage) traverses specific directories and files to calculate the space consumed by those accessible objects.

### Q8. What are inodes?
**Answer**: Inodes (index nodes) are kernel data structures that store all metadata about a filesystem object (file size, permissions, owner, timestamps, data block pointers), excluding its filename and file content. Filesystems have a finite number of inodes; exhausting them prevents file creation even if disk blocks are free.

### Q9. How do you follow a log in real time?
**Answer**: Use `tail -f /path/to/logfile.log`, or for `systemd` services, use `journalctl -u service-name -f`.

### Q10. What does `journalctl -u` do?
**Answer**: The `-u` flag filters journal logs to a specific `systemd` unit or service (e.g. `journalctl -u orders-api`).

### Q11. Why can deleting a log file fail to free disk space?
**Answer**: When a file is deleted with `rm`, its directory link is removed, but its data blocks remain allocated if a running process still holds an open file descriptor to it. Space is only freed when the process closes the file descriptor or terminates.

### Q12. Why might a service work manually but fail under systemd?
**Answer**: 
1. `systemd` runs the service under a restricted user/group with fewer permissions.
2. The working directory is different.
3. Interactive shell environment variables (`PATH`, `JAVA_HOME`, secrets) are not present in `systemd`'s environment.

### Q13. What is standard error (`stderr`)?
**Answer**: Standard error is a distinct I/O stream (file descriptor `2`) reserved for diagnostic and error messages, allowing errors to be captured or redirected separately from normal program output (`stdout`, file descriptor `1`).

### Q14. How do you investigate a full disk?
**Answer**:
1. Run `df -h` to identify the full filesystem.
2. Run `df -i` to verify whether disk space or inode exhaustion is responsible.
3. Run `du -xhd1 /mountpoint | sort -h` to drill into large directories.
4. Run `lsof +L1` to check for deleted files held open by processes.

### Q15. How do you investigate a permission error?
**Answer**:
1. Check the identity of the failing process (`whoami` or service definition `User=`).
2. Run `namei -l /path/to/file` or `ls -ld` on each parent directory to verify traversal (`x`) permissions.
3. Run `ls -l` on the target file to check owner, group, and `r`/`w` bits.
4. Check for POSIX ACLs (`getfacl`) or SELinux/AppArmor security contexts.

---

# 4. Hands-On Lab — The Operations Investigator

Complete the following on your Linux development environment. You can perform these exercises in a temporary directory without touching system files.

### Lab A — Create and inspect a log
```bash
mkdir -p ~/linux-lab
cd ~/linux-lab

printf 'INFO application started\n' > app.log
printf 'ERROR database connection failed\n' >> app.log
printf 'WARN retrying connection\n' >> app.log

cat app.log
grep -n 'ERROR' app.log
tail -n 2 app.log
```
*Takeaway:* Notice how `>` truncates and overwrites, while `>>` safely appends new entries.

### Lab B — Inspect permissions
```bash
ls -l app.log
stat app.log
chmod 600 app.log
ls -l app.log
```

Questions:
- Who can read the file after `chmod 600`? *(Only the owner).*
- Why would another user or service account be unable to read it? *(Read bit is stripped from group and others).*
- Why should you not apply `chmod 600` indiscriminately? *(Shared services or log collectors running as separate users will fail to read).*

### Lab C — Inspect disk usage
```bash
df -h .
df -i .
du -sh ~/linux-lab
```
*Takeaway:* Observe how `df` reports partition-level superblock metrics, while `du` sums the space of the specified directory.

### Lab D — Write a short incident report
Choose one scenario:
- The service cannot write a log file (`Permission denied`).
- The filesystem is 100% full (`No space left on device`).
- The service starts manually in shell but fails under `systemd`.

Write a brief report with:
1. Reported symptom.
2. Three diagnostic commands run.
3. Collected evidence.
4. Root cause hypothesis.
5. Safe remediation and verification step.

---

# 5. Mastery Checklist

### Layer 1 — Fundamentals & Mental Models
- [ ] Explain log severity levels (`TRACE`, `DEBUG`, `INFO`, `WARN`, `ERROR`) and log sources.
- [ ] Interpret Linux owner (`u`), group (`g`), and other (`o`) permissions.
- [ ] Calculate and explain octal permission numbers (`755`, `644`, `600`).
- [ ] Differentiate file permissions from directory traversal (`x`) permissions.
- [ ] Explain disk block storage capacity versus inode capacity (`df -h` vs `df -i`).
- [ ] Explain why `df` and `du` report different disk usage metrics.

### Layer 2 — Practical Engineering & Workflows
- [ ] Stream and inspect logs safely using `tail -f`, `tail -n`, `less`, and `grep -C`.
- [ ] Query and filter `systemd` service logs using `journalctl` (`-u`, `-f`, `-n`, `--since`, `-p`).
- [ ] Modify permissions and ownership safely using `chmod` and `chown`.
- [ ] Diagnose `Permission denied` systematically using `ls -ld`, `namei -l`, and `id`.
- [ ] Drill down into disk usage with `du -xhd1` and `find -size`.
- [ ] Detect deleted open files consuming disk space using `lsof +L1`.
- [ ] Separate and redirect `stdout` and `stderr` (`>`, `2>`, `2>&1`).

### Layer 3 — Production Engineering & Interview Mastery
- [ ] Execute an incident investigation for full filesystems and inode exhaustion.
- [ ] Resolve post-deployment permission failures without granting world-writable access (`chmod 777`).
- [ ] Investigate silent or missing application logs.
- [ ] Troubleshoot services that run manually but fail under `systemd`.
- [ ] Answer all 15 interview questions with production-grade engineering explanations.
- [ ] Complete the hands-on operations investigator lab.

---

## Chunk Completion Protocol
- Authoritative source file: `content/linux/04-logs-permissions-system-troubleshooting.md`.
- No chunk-level PDF generated.
- Complete Linux handbook PDF (`BEH_LINUX_COMPLETE_HANDBOOK.pdf`) is compiled only after all six Linux chunks are complete and verified.

---

## What Comes Next?

**Linux Chunk 5 of 6 — Shell Scripting & Automation**

We will cover:
- Bash scripting foundations: shebang (`#!/usr/bin/env bash`), strict mode (`set -euo pipefail`).
- Variables, positional parameters, and command-line arguments.
- Conditional logic (`if`, `test`, `[[ ... ]]`), string/file/numeric comparisons.
- Loops (`for`, `while`) and stream processing.
- Exit codes, error trapping (`trap`), and defensive scripting.
- Functions, return values, and modular script design.
- Production automation scripts: log archivers, health checkers, deployment helpers.
- Practical lab and interview questions.
