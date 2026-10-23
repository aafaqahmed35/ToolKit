# Linux Chunk 1 of 6
# Terminal & Filesystem Mastery
### Backend Engineering Tools & Infrastructure Handbook

**Phase I — Developer Foundations**  
**Learning layers:** Fundamentals → Practical Engineering → Production Engineering & Interview Mastery

---

# 1. Why Backend Engineers Need Linux

Imagine your Spring Boot application is running on a remote server.

A user reports that the API is failing. You need to investigate.

You may need to:

- Connect to a server.
- Navigate to the application directory.
- Inspect configuration files.
- Search for error messages.
- Examine deployment artifacts.
- Identify which files have changed.
- Inspect permissions.
- Read application logs.
- Combine multiple commands to narrow down the problem.

You won't necessarily have a graphical desktop or an IDE on that server.

Instead, you'll often interact with a terminal.

Linux command-line proficiency helps you work with servers, containers, CI/CD runners, cloud virtual machines, and production environments.

The objective is not to memorize hundreds of commands.

**The objective is to understand how to inspect a system, find information, and manipulate it safely.**

---

# LAYER 1 — FUNDAMENTALS & MENTAL MODELS

# 2. What Is Linux?

Linux is an open-source operating-system kernel.

A Linux distribution combines the Linux kernel with additional software, utilities, libraries, package management, and other components to create a usable operating system.

Examples include Ubuntu, Debian, Fedora, and Red Hat Enterprise Linux.

A typical Linux environment contains:

- The kernel, which manages hardware and core system resources.
- User-space programs and libraries.
- A shell that interprets commands.
- Filesystems that organize data.
- System services and background processes.
- Administrative tools for managing the machine.

## Linux versus macOS

Your MacBook uses macOS, not Linux.

Both systems are Unix-like and share many command-line conventions, but their implementations and available utilities differ.

| Feature | Linux | macOS |
|---|---|---|
| Kernel | Linux kernel | XNU kernel |
| Common shell | Bash or Zsh | Zsh by default on modern installations |
| Package management | Depends on distribution | Commonly Homebrew for third-party packages |
| Filesystem layout | Linux filesystem hierarchy | macOS-specific layout with Unix conventions |
| System management | Distribution-specific tools | macOS-specific tools such as `launchctl` |
| Common commands | Many Unix utilities | Many shared utilities, with differences in options |

Most commands in this chunk work on both systems. Where options differ, I'll call that out.

**Practical rule:** Learn command-line concepts on your Mac, but verify Linux-specific behavior when working with Linux servers or containers.

---

# 3. The Terminal, Shell, and Command

These three terms are related but not identical.

## Terminal

The terminal is the interface through which you interact with a command-line environment.

Examples include Terminal.app on macOS and terminal emulators on Linux desktops.

## Shell

The shell interprets commands and coordinates their execution.

Examples:

- Bash
- Zsh
- Fish

## Command

A command is an instruction you ask the shell to execute.

For example:

```bash
pwd
```

The shell runs `pwd`, which prints the current working directory.

A command can also contain arguments:

```bash
ls -l /var/log
```

Here:

- `ls` is the command.
- `-l` is an option.
- `/var/log` is an argument specifying a directory.

### A useful mental model

```text
You type a command
       |
       v
Shell interprets it
       |
       v
Program executes
       |
       v
Output or error is displayed
```

The actual execution path can be more complex because shells support built-in commands, pipelines, redirection, functions, and other features. This model is sufficient for understanding everyday command-line work.

---

# 4. Understand the Linux Filesystem

Linux organizes files in a hierarchical tree.

Unlike a Windows-style interface that commonly presents drives such as `C:` and `D:`, Linux exposes a unified filesystem hierarchy rooted at `/`.

The root directory is represented by a single forward slash:

```text
/
```

It is not the same as the root user's home directory.

## 4.1 Important filesystem paths

| Path | Typical purpose |
|---|---|
| `/` | Root of the filesystem hierarchy |
| `/home` | Home directories for ordinary users on many Linux systems |
| `/root` | Home directory of the root user |
| `/etc` | System and application configuration |
| `/var` | Variable data, commonly including logs and caches |
| `/var/log` | Common location for system and service logs |
| `/tmp` | Temporary files |
| `/usr` | User-space programs, libraries, and shared resources |
| `/opt` | Common location for optional third-party software |
| `/bin` | Essential command binaries on traditional layouts; may be linked to `/usr/bin` |
| `/sbin` | System administration binaries on traditional layouts; may be linked to `/usr/sbin` |
| `/proc` | Virtual filesystem exposing process and kernel information |
| `/dev` | Device files and interfaces |
| `/mnt` | Common temporary mount point |
| `/media` | Common mount location for removable media |

The exact layout depends on the distribution, filesystem configuration, and whether the machine is a container.

### Backend engineering example

Suppose your application fails after deployment.

You might investigate:

- `/etc/`: service or system configuration.
- `/var/log/`: logs, if the service writes logs there.
- `/tmp/`: temporary files.
- `/opt/`: an application installed there by the deployment process.
- `/home/`: files owned by a deployment user.

Do not assume that every application stores its configuration or logs in one standard location. Modern services often use environment variables, container logging, or centralized logging systems.

---

# 5. Absolute Paths and Relative Paths

Understanding paths is essential for navigating a server.

## 5.1 Absolute path

An absolute path starts at the filesystem root.

Example:

```bash
cd /var/log
```

This takes you to `/var/log`, regardless of your current working directory.

## 5.2 Relative path

A relative path is interpreted from your current working directory.

Suppose your current directory is:

```text
/home/aafaq/projects
```

You can navigate into a child directory:

```bash
cd backend
```

The resulting location is:

```text
/home/aafaq/projects/backend
```

## 5.3 Special path symbols

| Symbol | Meaning |
|---|---|
| `.` | Current directory |
| `..` | Parent directory |
| `~` | Home directory, when interpreted by the shell |
| `/` | Filesystem root |

Examples:

```bash
cd .
cd ..
cd ~
cd ~/projects
```

`cd .` normally leaves you in the same directory.

`cd ..` moves one directory upward.

`cd ~` takes you to your home directory.

### Common mistake

This command:

```bash
cd /projects
```

means a directory named `projects` directly under `/`.

It does not mean `projects` inside your home directory.

For the latter, use:

```bash
cd ~/projects
```

---

# 6. How to Read Command Syntax

Documentation often uses notation that looks executable but contains placeholders.

For example:

```text
cp [OPTIONS] SOURCE DESTINATION
```

This describes the structure of a command.

- `OPTIONS` represents optional flags.
- `SOURCE` is the file or directory being copied.
- `DESTINATION` is where the copy should go.

Square brackets in documentation generally indicate optional elements. They are not normally typed literally.

For example:

```bash
cp report.txt backup.txt
```

This copies `report.txt` to `backup.txt` in the current directory, subject to the command's normal behavior and permissions.

### Another example

```text
grep [OPTIONS] PATTERN FILE
```

A concrete command could be:

```bash
grep "ERROR" application.log
```

This searches for lines containing `ERROR` in `application.log`.

**Habit to build:** Learn to translate command documentation into concrete commands with real arguments.

---

# LAYER 2 — PRACTICAL ENGINEERING & WORKFLOWS

# 7. Navigate the Filesystem

These are the commands you'll use constantly.

## 7.1 `pwd` — Print the current directory

```bash
pwd
```

Example output:

```text
/home/aafaq/projects/backend
```

Use it whenever you're unsure where a command will operate.

## 7.2 `ls` — List directory contents

```bash
ls
```

List detailed information:

```bash
ls -l
```

Show hidden entries:

```bash
ls -a
```

Combine the options:

```bash
ls -la
```

Human-readable file sizes are available on common GNU/Linux implementations:

```bash
ls -lh
```

On macOS, `ls -lh` is also supported.

### Hidden files

On Unix-like systems, filenames beginning with `.` are treated as hidden by common directory-listing tools.

Examples:

```text
.env
.git
.gitignore
.zshrc
```

These files may contain important project settings, shell configuration, or version-control metadata.

Hidden does not mean secure. A hidden `.env` file can still contain sensitive credentials.

## 7.3 `cd` — Change directory

```bash
cd /var/log
```

Go to your home directory:

```bash
cd ~
```

Return to the previous working directory:

```bash
cd -
```

The `cd -` command is useful when switching repeatedly between two locations.

## 7.4 `clear` — Clear the terminal display

```bash
clear
```

This clears the visible terminal screen. It does not delete files or erase command history.

## 7.5 `history` — Inspect shell command history

```bash
history
```

The precise behavior depends on your shell.

Command history is useful for recalling previous commands, but do not assume it is a secure place to store secrets. Commands containing credentials may be retained in shell history.

### Navigation drill

Execute these commands and explain the result of each:

```bash
pwd
ls -la
cd /
pwd
cd ~
pwd
cd -
pwd
```

The goal is to understand how the current working directory changes.

---

# 8. Create, Copy, Move, and Remove Files

These operations are simple but can be destructive if used carelessly.

Practise them in a disposable directory.

## 8.1 Create a directory

```bash
mkdir linux-practice
```

Create nested directories:

```bash
mkdir -p linux-practice/backend/logs
```

The `-p` option creates missing parent directories and does not report an error merely because the requested directory already exists.

## 8.2 Create an empty file

```bash
touch notes.txt
```

If the file does not exist, `touch` creates an empty file.

If it already exists, `touch` normally updates its access and modification timestamps.

It does not erase the file's contents.

## 8.3 Read a small text file

```bash
cat notes.txt
```

`cat` prints file contents to standard output.

It is convenient for small files. For large files, use a pager or inspect only the relevant section.

## 8.4 Copy a file

```bash
cp notes.txt notes-backup.txt
```

This creates a copy of the file in the current directory.

Copy a file into another directory:

```bash
cp notes.txt linux-practice/
```

## 8.5 Move or rename a file

```bash
mv notes.txt notes-old.txt
```

Within the same filesystem, this commonly renames the file by changing its directory entry.

Move it into another directory:

```bash
mv notes-old.txt linux-practice/
```

The precise behavior of moves across filesystems can differ because a cross-filesystem move may require copying and removing the original.

## 8.6 Remove a file

```bash
rm notes-backup.txt
```

This removes the directory entry for the file. It does not normally move the file to a graphical trash folder.

Recovery may be difficult or impossible.

## 8.7 Remove an empty directory

```bash
rmdir empty-directory
```

This removes an empty directory.

## 8.8 Remove a directory tree

```bash
rm -r linux-practice
```

This recursively removes the directory and its contents.

**Safety rule:** Never run recursive deletion commands on an important path without first verifying the exact path and contents.

Avoid combining recursive deletion with force flags merely to make commands succeed.

Before removing anything important:

```bash
pwd
ls -la
```

If you are uncertain, stop and inspect.

---

# 9. Inspect Files Without Opening an Editor

Backend engineers frequently inspect configuration files, logs, and command output directly from the terminal.

## 9.1 `cat` — Print the entire file

```bash
cat application.yml
```

Best for small files.

## 9.2 `less` — Read large files interactively

```bash
less application.log
```

Useful keys:

| Key | Action |
|---|---|
| `Space` | Move forward one screen |
| `b` | Move backward one screen |
| `/ERROR` | Search forward for `ERROR` |
| `n` | Move to the next search match |
| `q` | Quit |

`less` is available on many Linux systems and macOS installations, though the installed version may differ.

## 9.3 `head` — Read the beginning

```bash
head application.log
```

Display the first 20 lines:

```bash
head -n 20 application.log
```

## 9.4 `tail` — Read the end

```bash
tail application.log
```

Display the last 50 lines:

```bash
tail -n 50 application.log
```

Follow a file as new lines are appended:

```bash
tail -f application.log
```

Press `Ctrl+C` to stop following the file.

On Linux, GNU `tail` also supports:

```bash
tail -F application.log
```

`-F` is useful when a file is rotated or recreated because it retries opening the file by name. Verify the implementation available on your target system before relying on this option.

### Backend example

Your application is returning HTTP 500.

Instead of dumping an enormous log file to the terminal:

```bash
tail -n 100 application.log
```

Then inspect the surrounding context using `less` or a targeted search.

**Practical lesson:** Read the smallest relevant section of a file first.

---

# 10. Search Files and Directories

Finding information is one of the most important command-line skills.

## 10.1 `grep` — Search file contents

Search for a word:

```bash
grep "ERROR" application.log
```

Ignore case:

```bash
grep -i "error" application.log
```

Include line numbers:

```bash
grep -n "ERROR" application.log
```

Search recursively through a directory:

```bash
grep -Rni "connection refused" logs/
```

Here:

- `-R` searches recursively.
- `-n` prints line numbers.
- `-i` ignores case.

On GNU/Linux, `grep` commonly supports `-R` as recursive traversal that follows symbolic links. Behavior can differ between implementations, so use `-r` when you want the more conventional recursive search that does not follow symbolic links by default on GNU grep.

## 10.2 `find` — Search by filesystem properties

Find files by name:

```bash
find . -name "*.log"
```

Find YAML files:

```bash
find . -name "*.yml"
```

Find files with a particular name, case-insensitively:

```bash
find . -iname "application.yml"
```

Find directories:

```bash
find . -type d
```

Find regular files:

```bash
find . -type f
```

### Search by file size

On GNU/Linux:

```bash
find . -type f -size +100M
```

This finds regular files larger than 100 MiB according to GNU `find`'s size interpretation.

File-size predicates have implementation-specific details, so check the local manual if exact size boundaries matter.

## 10.3 `grep` versus `find`

| Tool | Primary purpose |
|---|---|
| `find` | Locate filesystem entries by properties such as name, type, and size |
| `grep` | Search text inside files |

A useful combination is:

```bash
find . -type f -name "*.log"
```

This locates log files.

Then:

```bash
grep -n "ERROR" application.log
```

This searches within a particular log file.

### Avoid accidental overload

Searching every file on a large server can be slow and noisy.

Start from a relevant directory, narrow the filename pattern, and exclude unnecessary locations when appropriate.

---

# 11. Understand Standard Input, Output, and Error

This is the foundation of command composition.

Many command-line programs interact with three standard streams.

| Stream | File descriptor | Purpose |
|---|---:|---|
| Standard input | `0` | Input received by a program |
| Standard output | `1` | Normal output |
| Standard error | `2` | Diagnostic output and errors |

For example:

```bash
ls
```

Normally writes its listing to standard output.

If it encounters an error, it may write a diagnostic to standard error.

Understanding the difference allows you to redirect output, preserve error messages, and combine commands.

---

# 12. Redirection: Control Where Output Goes

## 12.1 `>` — Replace a file's contents

```bash
echo "Backend practice" > notes.txt
```

This creates `notes.txt` if necessary and replaces its existing contents.

**Warning:** `>` can destroy previously stored text in the destination file.

## 12.2 `>>` — Append output

```bash
echo "Learning Linux" >> notes.txt
```

This appends output to the end of the file rather than replacing its contents.

## 12.3 `<` — Read input from a file

```bash
sort < names.txt
```

This supplies the contents of `names.txt` as standard input to `sort`.

## 12.4 `2>` — Redirect standard error

On a Unix-like shell:

```bash
some-command 2> errors.txt
```

This redirects standard error to `errors.txt`.

## 12.5 `>` and `2>` together

```bash
some-command > output.txt 2> errors.txt
```

This sends normal output and error output to separate files.

## 12.6 `2>&1` — Send standard error to standard output's destination

```bash
some-command > combined.txt 2>&1
```

The command's standard output is redirected to `combined.txt`, and standard error is then redirected to the same destination.

Order matters.

For example:

```bash
some-command > combined.txt 2>&1
```

is not generally equivalent to:

```bash
some-command 2>&1 > combined.txt
```

In the second command, standard error is first connected to the original standard-output destination, and standard output is redirected afterward.

### Engineering use case

During a long-running local test:

```bash
./run-tests.sh > test-output.log 2>&1
```

This captures both standard output and standard error in one file.

The example assumes a compatible shell and an executable script at that path.

---

# 13. Pipes: Connect Commands Together

A pipe (`|`) sends one command's standard output to another command's standard input.

For example:

```bash
cat application.log | grep "ERROR"
```

This prints lines containing `ERROR`.

However, `cat` is unnecessary in this example.

A simpler command is:

```bash
grep "ERROR" application.log
```

Prefer direct commands when they are clearer.

## 13.1 A useful pipeline

```bash
grep "ERROR" application.log | head -n 20
```

This searches for `ERROR` and displays the first 20 matching lines.

## 13.2 Count matching lines

```bash
grep -c "ERROR" application.log
```

This prints the number of matching lines.

Be aware that `grep -c` counts matching lines, not necessarily the number of occurrences of the text within each line.

## 13.3 Sort and deduplicate

```bash
sort names.txt | uniq
```

`uniq` removes adjacent duplicate lines, so sorting first groups identical lines together.

For a count of repeated lines:

```bash
sort names.txt | uniq -c
```

## 13.4 Count files matching a pattern

On common Unix-like systems:

```bash
find . -type f -name "*.java" | wc -l
```

This counts the output lines from `find`.

For ordinary filenames this is useful, but newline-containing filenames can make line-based counting unreliable. For robust processing of arbitrary filenames, use null-delimited output and tools that understand null delimiters.

### Mental model

```text
Command A
   |
   | standard output
   v
  Pipe
   |
   v
Command B
```

The commands are connected through streams, not by automatically sharing files.

---

# 14. Command Chaining: `&&`, `||`, and `;`

These operators control how commands execute in sequence.

## 14.1 `&&` — Run the next command only if the previous succeeds

```bash
mkdir practice && cd practice
```

The second command runs only if `mkdir practice` returns a successful exit status.

This is useful when later operations depend on earlier ones.

## 14.2 `||` — Run the next command if the previous fails

```bash
cd /missing-directory || echo "Could not enter directory"
```

If `cd` fails, the fallback message is printed.

## 14.3 `;` — Run commands sequentially regardless of success

```bash
pwd; ls
```

The shell runs `ls` after `pwd` even if `pwd` fails.

## 14.4 Exit status

Most Unix commands communicate success or failure through an exit status.

By convention:

- `0` means success.
- A nonzero status indicates failure or another condition defined by the command.

Inspect the last command's status in Bash or Zsh:

```bash
echo $?
```

Run this immediately after the command you want to inspect. The `echo` command itself changes the most recent exit status.

### Why this matters in automation

Consider:

```bash
mkdir build && cd build && echo "Ready"
```

If creating the directory fails, the remaining commands will not run.

This is safer than blindly executing dependent commands in sequence.

---

# 15. Command Substitution

Command substitution captures a command's output and uses it within another command.

For example:

```bash
current_dir=$(pwd)
echo "$current_dir"
```

The shell runs `pwd`, stores its output in the variable, and then prints the variable's value.

Another example:

```bash
today=$(date +%F)
echo "$today"
```

The output format depends on the `date` implementation and the supplied format string. `%F` is supported by common GNU/Linux and macOS versions.

### Why quote variables?

Prefer:

```bash
echo "$current_dir"
```

over:

```bash
echo $current_dir
```

Quoting prevents the shell from performing unintended word splitting and pathname expansion on the variable's value.

This is especially important in shell scripts.

---

# 16. A Complete Terminal Workflow

Let's put the commands together.

You have a backend project containing application logs. You need to locate the log files and identify recent errors.

## Step 1: Confirm your location

```bash
pwd
```

## Step 2: Inspect the project directory

```bash
ls -la
```

## Step 3: Locate log files

```bash
find . -type f -name "*.log"
```

## Step 4: Search a known log file

```bash
grep -ni "error" application.log
```

## Step 5: Inspect recent lines

```bash
tail -n 100 application.log
```

## Step 6: Narrow the output

```bash
grep -ni "error" application.log | tail -n 20
```

## Step 7: Preserve investigation output

```bash
grep -ni "error" application.log > error-investigation.txt
```

Review the resulting file before sharing it.

Logs may contain tokens, email addresses, database connection strings, and other sensitive information. Redact sensitive material before posting or sharing logs.

### What did you learn?

You used:

- Navigation to establish context.
- Filesystem inspection to understand the directory.
- `find` to locate files.
- `grep` to search contents.
- `tail` to limit output.
- Pipes to compose commands.
- Redirection to save results.

This is the core of practical terminal work.

---

# LAYER 3 — PRODUCTION ENGINEERING & INTERVIEW MASTERY

# 17. Production Scenario: A Configuration File Is Missing

Your Spring Boot service fails to start after deployment.

The error message suggests that a configuration file cannot be found.

Do not immediately change permissions or create a replacement file.

Investigate methodically.

## Step 1: Inspect the current directory

```bash
pwd
```

A relative path may be resolving from an unexpected working directory.

## Step 2: Inspect the directory contents

```bash
ls -la
```

Check for hidden configuration files and unexpected filenames.

## Step 3: Search for the expected file

```bash
find . -type f -name "application.yml"
```

If the search starts from the wrong directory, it may miss the file.

Broaden the search only when necessary and appropriate.

## Step 4: Inspect the launch configuration

Determine how the application is started.

The application may use:

- An absolute configuration path.
- A relative configuration path.
- Environment variables.
- A mounted configuration file.
- A container-specific working directory.

Do not assume that the application's current directory is the same as the directory from which you usually run it locally.

## Step 5: Check file readability

```bash
ls -l application.yml
```

This displays the file's permission bits and ownership information.

If the file exists but cannot be read, investigate the process identity and permissions.

Do not make it world-readable or world-writable as a quick fix.

## Step 6: Verify the correction

After correcting the actual cause, restart or redeploy according to the service's operational procedure.

Check the logs and application health.

**Production lesson:** Missing-file errors can result from incorrect paths, missing mounts, deployment packaging, or permissions. Diagnose the cause before modifying the system.

---

# 18. Production Scenario: Logs Are Growing Too Large

Your application writes logs to a local file.

Disk usage is increasing, and the server may eventually run out of space.

This chunk provides the filesystem and inspection tools needed to begin investigating.

## Step 1: Inspect the relevant directory

```bash
ls -lh /var/log
```

The location is illustrative. Your application may store logs elsewhere or write them to standard output.

## Step 2: Locate large files

On GNU/Linux:

```bash
find /var/log -type f -size +100M
```

Use a directory appropriate to the investigation and your permissions.

## Step 3: Inspect the relevant file

```bash
tail -n 100 /path/to/application.log
```

Determine whether the log is growing because of repeated errors, verbose logging, or another behavior.

## Step 4: Identify the logging mechanism

Check whether the application uses:

- A file-based logging framework.
- System logging.
- Container standard output and standard error.
- A centralized logging service.
- A configured log-rotation mechanism.

## Step 5: Apply the appropriate operational fix

Possible responses include:

- Correcting an error loop that generates excessive logs.
- Adjusting appropriate log levels.
- Configuring log rotation.
- Correcting log retention.
- Moving to a centralized logging solution.

**Do not casually delete active production logs.** You may lose evidence needed for incident investigation, and deleting a file may not immediately free space if a process still has it open.

The actual remediation depends on the logging architecture.

---

# 19. Production Safety: Commands That Deserve Extra Attention

Some commands are easy to type and expensive to misuse.

| Command | Risk |
|---|---|
| `rm -r <path>` | Recursively deletes directory contents |
| `rm -f <path>` | Suppresses certain removal errors and removes files without prompting |
| `rm -rf <path>` | Combines recursive deletion with forced removal |
| `>` | Replaces the destination file's contents |
| `chmod -R` | Recursively changes permissions |
| `chown -R` | Recursively changes ownership on supported systems |
| `sudo <command>` | Runs a command with elevated privileges when permitted |

Before executing a potentially destructive command:

1. Confirm the current directory.
2. Inspect the exact target path.
3. Understand which files or directories will be affected.
4. Check whether the operation can be tested safely.
5. Use the least privilege necessary.
6. Verify the result.

For example:

```bash
pwd
ls -la /path/to/target
```

These commands help you establish context, but they do not replace understanding the operation itself.

Never copy a destructive command from an online answer without verifying its arguments.

---

# 20. Essential Linux Interview Questions

## Q1. What is the difference between a terminal and a shell?

A terminal provides the interface for interacting with a command-line environment. A shell interprets commands and coordinates their execution.

## Q2. What is the difference between an absolute path and a relative path?

An absolute path starts from the filesystem root. A relative path is interpreted from the current working directory.

## Q3. What does `pwd` do?

It prints the current working directory.

## Q4. What is the difference between `ls -l` and `ls -a`?

`ls -l` requests a detailed listing. `ls -a` includes hidden entries, including `.` and `..`.

## Q5. What is the difference between `cat`, `less`, `head`, and `tail`?

- `cat` prints file contents.
- `less` provides interactive viewing.
- `head` displays the beginning.
- `tail` displays the end.

## Q6. What is the difference between `find` and `grep`?

`find` locates filesystem entries by properties. `grep` searches text within input.

## Q7. What is a pipe?

A pipe connects one command's standard output to another command's standard input.

## Q8. What is the difference between `>` and `>>`?

`>` redirects output and replaces the destination's contents. `>>` appends output.

## Q9. What is standard error?

Standard error is a separate output stream commonly used for diagnostics. Its file descriptor is `2`.

## Q10. What does `2>&1` mean?

It redirects standard error to the current destination of standard output. The order of redirections matters.

## Q11. What is the difference between `&&` and `;`?

`&&` runs the next command only if the previous command succeeds. `;` runs the next command regardless of the previous command's exit status.

## Q12. What does `cd ..` do?

It changes the working directory to the parent directory.

## Q13. Why can `rm -rf` be dangerous?

It recursively removes directory contents without the normal interactive protections that might otherwise help prevent accidental deletion.

## Q14. Does macOS run Linux?

No. macOS and Linux are different operating systems with different kernels, although they share many Unix-like conventions and command-line tools.

## Q15. Why should you inspect the current directory before a destructive operation?

Because relative paths are resolved from the current working directory, and an unexpected location can cause the command to affect the wrong files.

---

# 21. Practical Mastery Lab

Create a disposable workspace.

```bash
mkdir -p linux-lab/backend/logs
cd linux-lab
```

## Exercise A: Create files

```bash
touch README.md
touch backend/application.yml
touch backend/logs/application.log
```

## Exercise B: Add sample content

```bash
echo "# Linux Lab" > README.md
echo "server.port: 8080" > backend/application.yml
echo "INFO Application started" > backend/logs/application.log
echo "ERROR Database connection failed" >> backend/logs/application.log
echo "INFO Retry scheduled" >> backend/logs/application.log
```

## Exercise C: Inspect the directory

```bash
pwd
ls -la
find . -type f
```

## Exercise D: Search the log

```bash
grep -ni "error" backend/logs/application.log
```

## Exercise E: Inspect recent entries

```bash
tail -n 2 backend/logs/application.log
```

## Exercise F: Save matching lines

```bash
grep -ni "error" backend/logs/application.log > errors.txt
```

Inspect the result:

```bash
cat errors.txt
```

## Exercise G: Practise command composition

```bash
find . -type f -name "*.log" | wc -l
```

Explain what each part does.

## Exercise H: Inspect your working-tree location

```bash
cd backend
pwd
cd ..
pwd
```

### Mastery requirement

Do not merely execute these commands.

For each one, explain:

1. What it does.
2. Which directory or file it affects.
3. Whether it changes data.
4. What could go wrong if used with the wrong path.

That final question is what turns command familiarity into engineering judgment.

---

# 22. Chunk 1 Mastery Checklist

## Layer 1 — Fundamentals & Mental Models

- [ ] Explain Linux versus macOS.
- [ ] Distinguish terminal, shell, and command.
- [ ] Explain the filesystem root.
- [ ] Recognize important Linux directories.
- [ ] Distinguish absolute and relative paths.
- [ ] Explain standard input, output, and error.
- [ ] Explain pipes, redirection, and command chaining.

## Layer 2 — Practical Engineering & Workflows

- [ ] Navigate directories with `pwd`, `ls`, and `cd`.
- [ ] Create and inspect files and directories.
- [ ] Copy, move, and remove files safely.
- [ ] Read large files with `less`.
- [ ] Inspect recent log entries with `tail`.
- [ ] Search contents with `grep`.
- [ ] Locate files with `find`.
- [ ] Combine commands using pipes.
- [ ] Redirect output to files.
- [ ] Use `&&`, `||`, and `;` correctly.
- [ ] Explain command exit statuses.

## Layer 3 — Production Engineering & Interview Mastery

- [ ] Investigate a missing configuration file.
- [ ] Locate relevant log files.
- [ ] Explain why deleting active logs can be dangerous.
- [ ] Identify potentially destructive commands.
- [ ] Explain why the working directory matters.
- [ ] Diagnose a simple terminal-based backend issue.
- [ ] Answer the 15 interview questions.
- [ ] Complete the practical lab independently.

---

# 23. What Comes Next?

**Linux Chunk 2 of 6 — Processes, Signals & Resource Management**

We will cover:

- Processes and process IDs.
- Parent and child processes.
- Foreground and background execution.
- `ps`, `top`, and process inspection.
- Signals and graceful shutdown.
- `kill` and `kill -9`, including when not to use them.
- CPU and memory investigation.
- Resource exhaustion.
- Linux process troubleshooting.
- Practical backend incident scenarios and interview questions.

The three-layer structure remains mandatory, and the curriculum remains unchanged at **six Linux chunks and 32 total chunks across all 13 tools**.
