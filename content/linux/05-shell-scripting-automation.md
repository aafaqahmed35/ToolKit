# Linux Chunk 5 — Shell Scripting & Automation
## Backend Engineering Tools & Infrastructure Handbook

**Phase:** I — Developer Foundations  
**Chunk:** 5 of 6  
**Source file:** `content/linux/05-shell-scripting-automation.md`

---

# 1. Layer 1 — Fundamentals & Mental Models

## 1.1 Why shell scripting matters

Imagine repeating these tasks every day:

- Checking whether a backend process is running.
- Searching logs for errors.
- Starting a development environment.
- Running tests before committing code.
- Checking disk space.
- Verifying that a service responds to HTTP requests.
- Cleaning temporary files.

Doing these manually is repetitive and error-prone.

**Shell scripting turns repeatable operational procedures into executable instructions.**

A shell script is a file containing commands interpreted by a shell, such as Bash.

For example:

```bash
#!/usr/bin/env bash

echo "Checking backend..."
date
pwd
```

Save this as `check.sh`, make it executable, and run it:

```bash
chmod +x check.sh
./check.sh
```

The script executes its commands in sequence.

Shell scripting is especially useful for local development, CI/CD pipelines, deployment automation, diagnostics and incident response.

It is not a replacement for every programming language. Complex data processing, sophisticated application logic and large systems are often better implemented in Java, Python, Go or another suitable language.

---

## 1.2 What happens when a shell script runs?

Consider:

```bash
#!/usr/bin/env bash
echo "Hello"
```

The first line is called the **shebang**. It tells the operating system which interpreter should execute the script when it is launched as an executable.

The remaining line invokes the `echo` command.

A useful mental model:

```text
Script file
    |
    v
Shell interpreter
    |
    v
Commands and control flow
    |
    v
Processes, output and exit status
```

The shell interprets constructs such as variables, loops, conditions, functions, pipelines and redirections. Many commands are separate programs that the shell launches.

---

## 1.3 Variables and environment variables

A shell variable stores a value for use within the shell.

```bash
APP_NAME="orders-api"
PORT=8080

echo "$APP_NAME"
echo "$PORT"
```

Notice the syntax:

```bash
APP_NAME="orders-api"
```

Do not add spaces around the assignment operator.

To make a variable available to child processes, export it:

```bash
export APP_NAME="orders-api"
```

For example:

```bash
export APP_ENV=development
java -jar app.jar
```

The Java process inherits `APP_ENV` from its environment.

### Shell variable versus environment variable

- A shell variable belongs to the current shell's variable environment.
- An exported variable is included in the environment passed to child processes.

A child process cannot ordinarily modify its parent's environment. This explains why running a script as a separate process does not automatically change the environment of your interactive shell.

To execute a script in the current shell, use:

```bash
source ./setup.sh
```

or:

```bash
. ./setup.sh
```

Use this only when you intentionally want its shell-level changes to affect the current shell.

---

## 1.4 Quoting: a small detail with major consequences

Consider:

```bash
NAME="backend service"

echo $NAME
echo "$NAME"
```

Unquoted variable expansion can undergo word splitting and pathname expansion. Quoting preserves the expanded value as a single argument in the usual command context.

Prefer:

```bash
echo "$NAME"
```

The same principle applies to paths:

```bash
LOG_FILE="/tmp/application logs/app.log"

cat "$LOG_FILE"
```

Without appropriate quoting, the shell may interpret the path as multiple arguments.

**Practical rule:** quote variable expansions unless you deliberately need word splitting or pathname expansion.

---

## 1.5 Command substitution

Command substitution captures a command's standard output.

```bash
TODAY=$(date +%F)
echo "$TODAY"
```

Another example:

```bash
CURRENT_USER=$(whoami)
echo "Running as: $CURRENT_USER"
```

The command executes, its output is captured, and the result is stored in the variable.

Do not confuse standard output with a command's exit status. They represent different things.

---

## 1.6 Exit codes

A process returns an exit status when it terminates. By convention:

- `0` means success.
- A nonzero status generally indicates failure or another exceptional outcome.

The shell exposes the most recent command's exit status through `$?`.

```bash
mkdir -p test-dir
echo $?
```

Inspect a failing command:

```bash
grep "missing-pattern" app.log
echo $?
```

`grep` returns `0` when it finds a match, `1` when it finds no match, and another nonzero status for an error. Thus, not every nonzero status means a program crashed.

A critical distinction:

```bash
some_command
echo "$?"
```

The `echo` command has its own exit status. If you need the original command's status, capture it first:

```bash
some_command
status=$?

echo "Command status: $status"
```

---

## 1.7 Conditions

Shell conditions let a script make decisions.

```bash
if [[ -f "app.log" ]]; then
    echo "Log file exists"
else
    echo "Log file does not exist"
fi
```

Common tests:

| Expression | Meaning |
|---|---|
| `-f FILE` | File exists and is a regular file |
| `-d DIR` | Directory exists |
| `-e PATH` | Path exists |
| `-r FILE` | File is readable |
| `-w FILE` | File is writable |
| `-x FILE` | File is executable or searchable, depending on the path type |
| `-z "$VALUE"` | String is empty |
| `-n "$VALUE"` | String is nonempty |

Use `[[ ... ]]` when writing Bash-specific scripts. It supports convenient conditional expressions and avoids some pitfalls of the older `[ ... ]` syntax.

---

## 1.8 Loops

Loops repeat a task.

```bash
for service in orders-api payment-api inventory-api; do
    echo "Checking $service"
done
```

A `while` loop continues while its condition succeeds:

```bash
COUNT=1

while [[ "$COUNT" -le 3 ]]; do
    echo "Attempt $COUNT"
    COUNT=$((COUNT + 1))
done
```

Loops are useful for checking multiple services, processing lists of files and repeating bounded diagnostic attempts.

Avoid unbounded loops that continuously retry a failing service without delay, limits or useful logging.

---

## 1.9 Functions

Functions group reusable commands.

```bash
log_info() {
    echo "[INFO] $*"
}

log_info "Starting diagnostic script"
```

Functions help scripts stay readable and consistent.

For production scripts, define clear inputs, return meaningful exit statuses and send diagnostic messages to the appropriate output stream.

---

## 1.10 Standard streams and pipelines

Processes commonly use three standard streams:

- Standard input: file descriptor `0`.
- Standard output: file descriptor `1`.
- Standard error: file descriptor `2`.

Example:

```bash
grep -i "error" app.log > errors.log
```

The `>` operator redirects standard output to a file, replacing its previous contents.

Append instead:

```bash
grep -i "error" app.log >> errors.log
```

Redirect standard error:

```bash
some_command 2> command-errors.log
```

Combine standard output and standard error:

```bash
some_command > command.log 2>&1
```

A pipeline passes one command's standard output to another command's standard input:

```bash
ps -ef | grep '[j]ava'
```

In Bash, a pipeline normally returns the status of its last command unless `pipefail` is enabled. That behavior matters when a script must detect failures in earlier pipeline stages.

---

## 1.11 Defensive scripting

Operational scripts can damage systems when assumptions are wrong.

Good scripts should:

1. Validate required inputs.
2. Quote variable expansions.
3. Fail clearly when prerequisites are missing.
4. Avoid destructive actions by default.
5. Log what they do.
6. Return meaningful exit statuses.
7. Handle expected errors.
8. Avoid exposing secrets.
9. Be tested on disposable data before production use.

For Bash scripts, a common starting point is:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
```

This enables several useful failure-handling behaviors:

- `-e`: exits on many unhandled command failures.
- `-u`: treats certain unset-variable expansions as errors.
- `-o pipefail`: makes a pipeline fail if a command within it fails, rather than only considering the final command.

These options are useful but not a complete error-handling strategy. `set -e` has context-dependent behavior, especially in conditionals, functions and compound commands. Explicit checks remain important.

---

# 2. Layer 2 — Practical Engineering & Workflows

## 2.1 Build a reusable diagnostic script

Create a file named `backend-diagnostics.sh`:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="${APP_NAME:-orders-api}"
APP_PORT="${APP_PORT:-8080}"

log_info() {
    printf '[INFO] %s\n' "$*"
}

log_error() {
    printf '[ERROR] %s\n' "$*" >&2
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

main() {
    log_info "Starting diagnostics"
    log_info "Application: $APP_NAME"
    log_info "Expected port: $APP_PORT"

    log_info "Current user: $(whoami)"
    log_info "Current directory: $PWD"

    if command_exists uptime; then
        uptime
    else
        log_error "uptime command is unavailable"
    fi

    if command_exists df; then
        df -h
    else
        log_error "df command is unavailable"
    fi

    if command_exists pgrep; then
        if pgrep -af "$APP_NAME"; then
            log_info "Matching process found"
        else
            log_error "No matching process found"
        fi
    else
        log_error "pgrep command is unavailable"
    fi

    log_info "Diagnostics completed"
}

main "$@"
```

Run it:

```bash
chmod +x backend-diagnostics.sh
./backend-diagnostics.sh
```

Override the defaults:

```bash
APP_NAME=payment-api APP_PORT=8081 ./backend-diagnostics.sh
```

The script provides a reusable starting point. A process-name match does not prove that the correct service is healthy, and this example intentionally does not terminate any process.

---

## 2.2 Write a service health-check script

For an HTTP service, a meaningful health check should test the service's actual HTTP endpoint.

Create `health-check.sh`:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

URL="${1:-http://127.0.0.1:8080/health}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"
DELAY_SECONDS="${DELAY_SECONDS:-2}"

if ! command -v curl >/dev/null 2>&1; then
    echo "ERROR: curl is required" >&2
    exit 2
fi

if ! [[ "$MAX_ATTEMPTS" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR: MAX_ATTEMPTS must be a positive integer" >&2
    exit 2
fi

if ! [[ "$DELAY_SECONDS" =~ ^[0-9]+$ ]]; then
    echo "ERROR: DELAY_SECONDS must be a nonnegative integer" >&2
    exit 2
fi

for ((attempt = 1; attempt <= MAX_ATTEMPTS; attempt++)); do
    if curl --fail --silent --show-error \
        --connect-timeout 2 --max-time 5 \
        "$URL" >/dev/null; then
        echo "OK: $URL responded successfully"
        exit 0
    fi

    echo "Attempt $attempt/$MAX_ATTEMPTS failed" >&2

    if (( attempt < MAX_ATTEMPTS )); then
        sleep "$DELAY_SECONDS"
    fi
done

echo "ERROR: Health check failed after $MAX_ATTEMPTS attempts" >&2
exit 1
```

Run:

```bash
chmod +x health-check.sh
./health-check.sh
```

Specify another endpoint:

```bash
./health-check.sh http://127.0.0.1:8080/actuator/health
```

This script expects a successful HTTP status in the `2xx` or `3xx` range as interpreted by curl's `--fail` behavior. Your application's health contract may require stricter validation.

**Engineering distinction:** a process check tells you that a matching process exists. An HTTP health check tells you that a particular endpoint responded. Neither automatically proves every dependency is healthy.

---

## 2.3 Automate log inspection

Create `find-errors.sh`:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

LOG_FILE="${1:-app.log}"

if [[ ! -f "$LOG_FILE" ]]; then
    printf 'ERROR: Log file not found: %s\n' "$LOG_FILE" >&2
    exit 2
fi

if [[ ! -r "$LOG_FILE" ]]; then
    printf 'ERROR: Log file is not readable: %s\n' "$LOG_FILE" >&2
    exit 2
fi

printf 'Searching for error entries in %s\n' "$LOG_FILE"

if grep -niE 'error|exception|fatal' "$LOG_FILE"; then
    exit 0
else
    status=$?

    if [[ "$status" -eq 1 ]]; then
        echo "No matching error entries found"
        exit 0
    fi

    echo "ERROR: grep encountered a problem" >&2
    exit "$status"
fi
```

Run:

```bash
chmod +x find-errors.sh
./find-errors.sh app.log
```

This example handles the distinction between no matches and a `grep` error.

In production, logs may contain sensitive information. Limit access, redact credentials and avoid forwarding raw logs to unauthorized destinations.

---

## 2.4 Understand command-line arguments

Shell scripts receive positional arguments:

```bash
#!/usr/bin/env bash

echo "Script: $0"
echo "First argument: ${1:-}"
echo "Argument count: $#"
```

Useful special parameters:

| Parameter | Meaning |
|---|---|
| `$0` | Script name or invocation path |
| `$1`, `$2`, etc. | Positional arguments |
| `$#` | Number of positional arguments |
| `"$@"` | All arguments, preserved as separate arguments |
| `"$*"` | Arguments expanded as a combined string in many common contexts |
| `$?` | Previous command's exit status |

For forwarding arguments to another command, prefer:

```bash
some_command "$@"
```

This preserves argument boundaries.

Avoid using unquoted `$@` when passing arbitrary arguments because word splitting and pathname expansion can alter them.

---

## 2.5 Schedule recurring jobs with cron

Cron runs scheduled commands on systems configured to use it.

Open your user crontab:

```bash
crontab -e
```

A cron entry has five time fields followed by a command:

```text
minute hour day-of-month month day-of-week command
```

Example: run a diagnostic script every day at 2:30 AM.

```cron
30 2 * * * /home/appuser/scripts/backend-diagnostics.sh >> /home/appuser/logs/diagnostics.log 2>&1
```

Important considerations:

- Use absolute paths.
- Do not assume the interactive shell's `PATH`.
- Use the correct user and permissions.
- Capture output and errors.
- Understand the server's timezone.
- Avoid overlapping jobs if an earlier run may still be active.
- Do not place passwords or tokens directly in crontab entries.

The directories in this example must exist, and the executing user must have appropriate access.

Cron is not available or configured identically on every Linux system. Some environments use systemd timers or external schedulers.

---

## 2.6 Prevent overlapping executions

If a scheduled job takes longer than its interval, multiple instances can overlap.

On systems with `flock`, you can use a lock:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

LOCK_FILE="/tmp/backend-maintenance.lock"

exec 9>"$LOCK_FILE"

if ! flock -n 9; then
    echo "Another instance is already running"
    exit 0
fi

echo "Running maintenance task"
# Insert safe, tested maintenance commands here.
```

The file descriptor holds the lock while the script runs. When the process releases the lock, another invocation can acquire it.

Locking behavior depends on the filesystem and environment. A lock file alone does not prevent overlap; the lock operation is what matters.

---

## 2.7 Automate project workflows

A developer may repeatedly need to:

1. Compile the project.
2. Run tests.
3. Package the application.
4. Build a container image.

A simple Maven wrapper script could be:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

if [[ ! -x "./mvnw" ]]; then
    echo "ERROR: Maven wrapper ./mvnw is unavailable" >&2
    exit 2
fi

./mvnw clean verify

echo "Build and verification succeeded"
```

Save it as `verify-project.sh`.

Run:

```bash
chmod +x verify-project.sh
./verify-project.sh
```

Using the Maven wrapper helps the project select its configured Maven version without requiring a separately installed Maven version, though a compatible JDK and other prerequisites are still needed.

Do not automatically deploy to production merely because a local build succeeds. Deployment should follow the project's required review, test and release controls.

---

## 2.8 Handle configuration safely

Use environment variables for configuration when appropriate:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

APP_ENV="${APP_ENV:-development}"
APP_PORT="${APP_PORT:-8080}"

printf 'Environment: %s\n' "$APP_ENV"
printf 'Port: %s\n' "$APP_PORT"
```

The `${VARIABLE:-default}` form uses a default when the variable is unset or empty.

For a required value, use:

```bash
: "${DATABASE_URL:?DATABASE_URL must be configured}"
```

This stops execution with an explanatory error if the value is unset or empty.

Do not print `DATABASE_URL` if it contains credentials. Configuration validation should not expose secrets.

---

# 3. Layer 3 — Production Engineering & Interview Mastery

## 3.1 Incident scenario: a script reports success after failure

Consider:

```bash
./mvnw clean verify
echo "Build succeeded"
```

The message may appear even if the build failed, because the shell proceeds to the next command.

A safer version is:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

./mvnw clean verify

echo "Build succeeded"
```

Or check explicitly:

```bash
if ./mvnw clean verify; then
    echo "Build succeeded"
else
    echo "Build failed" >&2
    exit 1
fi
```

**Production lesson:** scripts must propagate failures to the caller. Otherwise, CI/CD systems may treat a failed build or deployment step as successful.

---

## 3.2 Incident scenario: a script works manually but fails in cron

Possible causes:

- The job runs as a different user.
- Its `PATH` is different.
- It runs from a different working directory.
- Required environment variables are absent.
- The script or an input file lacks permissions.
- Output is not captured.
- The expected network or mounted filesystem is unavailable at execution time.

Investigate by using absolute paths, recording non-sensitive diagnostic information and testing the job under the same identity and environment as the scheduled task.

A useful debugging technique is to record:

```bash
date
whoami
pwd
printf 'PATH=%s\n' "$PATH"
```

Do not log complete environments if they may contain secrets.

---

## 3.3 Incident scenario: a cleanup script deletes the wrong files

Dangerous scripts often combine variables and recursive deletion:

```bash
rm -rf "$TARGET"/*
```

If `TARGET` is empty, incorrect or unexpected, the script may affect unintended files.

Before any destructive operation:

1. Validate the target variable.
2. Require an expected directory.
3. Confirm the directory is within the intended root.
4. Inspect the exact paths to be affected.
5. Add a dry-run mode.
6. Test against disposable data.
7. Require explicit confirmation for high-impact operations.

For example, a safer starting point is:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

TARGET="${1:-}"

if [[ -z "$TARGET" ]]; then
    echo "Usage: $0 TARGET_DIRECTORY" >&2
    exit 2
fi

if [[ ! -d "$TARGET" ]]; then
    echo "ERROR: Target must be an existing directory" >&2
    exit 2
fi

printf 'Would inspect this directory: %s\n' "$TARGET"
find "$TARGET" -maxdepth 1 -type f -print
```

This example only lists files. It does not delete anything.

Even with validation, paths can change between checking and acting. High-impact automation requires careful path handling, appropriate permissions and a threat model suited to the environment.

---

## 3.4 Retries, backoff and timeouts

A production script that repeatedly retries a failing endpoint can worsen an outage.

A robust retry design should consider:

- Maximum attempt count.
- Connection and total-operation timeouts.
- Delay between attempts.
- Exponential backoff for transient failures.
- Jitter when many clients may retry simultaneously.
- Which errors are actually retryable.
- A final nonzero exit status when the operation fails.

A retry is not a substitute for diagnosing the underlying problem. Avoid infinite retries and unbounded waits.

For high-impact operations, also consider idempotency: if a command is retried after an uncertain outcome, can it safely run again without duplicating side effects?

---

## 3.5 Production script review checklist

Before running a script against an important environment, review:

- Inputs and defaults are validated.
- Variables and file paths are quoted appropriately.
- Commands have clear failure behavior.
- Exit statuses are meaningful.
- Secrets are not printed.
- Logging is useful but does not expose sensitive data.
- Destructive operations are guarded.
- Retries are bounded and have timeouts.
- Permissions are minimal.
- The script has been tested in a safe environment.
- The operator knows how to stop it and recover from partial execution.

---

# 4. Interview Mastery — 15 Questions

### Q1. What is a shell script?
**Answer**: A file containing a sequence of commands and shell-language constructs (variables, conditionals, loops, functions) that an interpreter executes to automate operational tasks.

### Q2. What does the shebang do?
**Answer**: It specifies the absolute path to the interpreter used when the script is launched as an executable program directly from the kernel (e.g. `#!/usr/bin/env bash`).

### Q3. What is the difference between a shell variable and an environment variable?
**Answer**: A shell variable exists only within the current shell instance. An exported variable is added to the environment list and inherited by child processes spawned by that shell.

### Q4. Why should shell variables usually be quoted?
**Answer**: Double-quoting variables (e.g. `"$VAR"`) prevents the shell from performing word splitting on whitespace and pathname expansion (globbing) on wildcards contained within the variable value.

### Q5. What does `$?` represent?
**Answer**: The exit status (numeric return code between 0 and 255) of the most recently executed command, foreground pipeline, or function.

### Q6. What does `set -e` do?
**Answer**: Instructs the shell to exit immediately if any simple command returns a nonzero exit status, subject to certain shell exceptions (such as commands executed as part of an `if` test or `while` condition).

### Q7. Why use `set -o pipefail`?
**Answer**: By default, a pipeline returns the exit status of its last command. `set -o pipefail` ensures that if any command in the pipeline fails with a nonzero exit code, the entire pipeline returns that failure code.

### Q8. What is the difference between `>` and `>>`?
**Answer**: `>` redirects output to a file and truncates (overwrites) its previous contents. `>>` appends redirected output to the end of the file.

### Q9. What is the difference between `$@` and `$*`?
**Answer**: When quoted, `"$@"` expands to separate strings for each positional parameter (`"$1"` `"$2"` ...), preserving original argument boundaries. `"$*"` combines all positional parameters into a single string separated by the first character of `IFS` (typically a space).

### Q10. What is command substitution?
**Answer**: The syntax `$(command)` (or legacy backticks `` `command` ``) that executes a command in a subshell and replaces the construct with its standard output.

### Q11. Why might a script work interactively but fail in cron?
**Answer**: Cron executes in a minimal, non-interactive environment with a restricted `PATH` (typically `/usr/bin:/bin`), a different working directory (home directory), different user permissions, and without user shell profile variables loaded.

### Q12. What is cron?
**Answer**: A time-based background daemon in Unix-like operating systems that executes scheduled jobs (crontabs) at specified times and dates.

### Q13. How can you prevent two instances of a scheduled script from overlapping?
**Answer**: Use an advisory file lock mechanism such as `flock` (e.g. `flock -n 9`) around the execution block, binding the lock to an open file descriptor for the lifetime of the process.

### Q14. Why is retrying every failure dangerous?
**Answer**: Unbounded or aggressive retries can create a "retry storm" (thundering herd), amplifying load on an already struggling downstream dependency and prolonging the outage. Retries should use exponential backoff, jitter, and strict attempt limits.

### Q15. How do you make an operational script production-safe?
**Answer**: Use defensive Bash options (`set -Eeuo pipefail`), validate all inputs and environment variables, quote expansions, avoid unvalidated recursive file operations, implement timeouts, prevent secret leakage in logs, and make actions idempotent.

---

# 5. Hands-on Lab — Build a Mini Operations Toolkit

Use a local development directory.

## Lab A — Build a script that checks prerequisites

Create `prerequisites.sh`:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

for command_name in bash curl grep df; do
    if command -v "$command_name" >/dev/null 2>&1; then
        printf '[OK] %s is available\n' "$command_name"
    else
        printf '[MISSING] %s is unavailable\n' "$command_name" >&2
        exit 1
    fi
done
```

Run it and explain why `command -v` is useful.

---

## Lab B — Add an HTTP health check

Adapt the health-check script from Section 2 to test your own local Spring Boot endpoint.

Verify that:
- A healthy endpoint returns exit status `0`.
- An unavailable endpoint produces a nonzero status.
- The script does not retry forever.
- Its output does not contain credentials.

---

## Lab C — Test exit-code handling

Run:

```bash
grep "NOT_A_REAL_PATTERN" app.log
echo "$?"
```

Then compare it with:

```bash
if grep -q "NOT_A_REAL_PATTERN" app.log; then
    echo "Pattern found"
else
    echo "Pattern not found or grep failed"
fi
```

Improve the second version so that it distinguishes “no match” from a genuine `grep` error.

---

## Lab D — Review a scheduled job

Design a cron entry that runs a diagnostic script daily.

Document:
- The schedule.
- The execution user.
- Absolute script and log paths.
- Output and error handling.
- How overlapping executions are prevented.
- How you would verify a run succeeded.

Do not schedule destructive maintenance on a production machine as part of this exercise.

---

# 6. Mastery Checklist

- [ ] Explain how shell scripts are interpreted and executed.
- [ ] Distinguish shell variables from exported environment variables.
- [ ] Use quoting, command substitution and positional arguments correctly.
- [ ] Understand exit codes and pipeline failure handling.
- [ ] Write conditions, loops and reusable functions.
- [ ] Redirect output and errors appropriately.
- [ ] Build a bounded HTTP health-check script.
- [ ] Automate recurring tasks with cron or an appropriate scheduler.
- [ ] Explain locking, retries, timeouts and idempotency.
- [ ] Review scripts for destructive behavior and secret exposure.
- [ ] Complete the hands-on lab and document the resulting workflow.

---

## Completion Protocol

1. Save the complete source as `content/linux/05-shell-scripting-automation.md`.
2. Preserve the full Markdown content.
3. Do not generate a PDF for this individual chunk.
4. The final Linux PDF must wait until all six Linux chunks are complete and verified.

**Next:** Linux Chunk 6 of 6 — **Production Incident Simulation**. We will combine Linux fundamentals, processes, networking, logs, permissions and scripting into realistic backend troubleshooting scenarios. That completes the six-chunk Linux curriculum.
