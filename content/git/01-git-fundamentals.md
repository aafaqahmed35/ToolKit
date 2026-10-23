# Git Fundamentals

Backend Engineering Tools & Infrastructure Handbook

Phase I — Developer Foundations | Chunk 1 of 2

---

## 1. What Is Git?

Git is a distributed version control system that tracks changes to files over time.

Imagine you’re building a Spring Boot backend. You add authentication, modify the database layer, and change your API validation logic. Suddenly, the application stops working.

Without version control, you might have to manually reconstruct what changed.

With Git, you can inspect previous changes, identify the problematic commit, collaborate safely, and restore a working version.

Git helps you answer four essential questions:

1. What changed?
2. When did it change?
3. Who made the change?
4. How can I recover or build upon an earlier version?

### Git versus GitHub

These are different things.

| Git | GitHub |
| :--- | :--- |
| Version control software | Online platform for hosting Git repositories |
| Runs locally | Provides remote repository hosting |
| Tracks changes and commits | Enables pull requests, code reviews, and collaboration |
| Works without an internet connection | Usually accessed over a network |

**Mental model**: Git is the version-control engine; GitHub is one place where your Git repository can live.

Other hosting platforms include GitLab and Bitbucket.

---

## 2. The Three Main Areas of Git

Understanding these three areas makes most everyday Git commands easier to understand.

Imagine modifying a Java file called `UserService.java`.

Your changes move through three conceptual areas:

```
Working Directory
       |
       | git add
       v
Staging Area
       |
       | git commit
       v
Local Repository
```

### 2.1 Working Directory

The working directory contains the files you currently see and edit.

For example:

```java
public class UserService {
    public String getStatus() {
        return "ACTIVE";
    }
}
```

You modify the method to return a different value.

The change exists in your working directory, but you have not necessarily staged or committed it.

### 2.2 Staging Area

The staging area contains the changes you intend to include in your next commit.

```bash
git add UserService.java
```

This stages the current changes to that file.

**Why have a staging area?**

Because you may modify five files but want to commit only two of them.

Staging allows you to construct a deliberate, logically grouped commit.

### 2.3 Local Repository

When you commit staged changes, Git records a new snapshot in the local repository.

```bash
git commit -m "Add user status handling"
```

A commit records information such as:

* The tracked project snapshot.
* A commit identifier.
* The author and timestamp.
* A commit message.
* References to parent commits.

Git commits are local by default. They are not automatically uploaded to GitHub.

### The Critical Distinction

* `git add` stages changes.
* `git commit` records staged changes locally.
* `git push` sends commits to a remote repository.

These commands perform different jobs.

---

## 3. Git’s Core Vocabulary

Learn these concepts before moving to advanced workflows.

| Term | Meaning |
| :--- | :--- |
| **Repository** | A project and its Git history |
| **Commit** | A recorded snapshot of project state |
| **Branch** | A movable reference to a line of development |
| **HEAD** | Usually identifies the currently checked-out commit or branch |
| **Remote** | A reference to another repository, commonly hosted online |
| **Staging area** | The changes selected for the next commit |
| **Merge** | Combines histories from different development lines |
| **Merge conflict** | A situation where Git cannot automatically reconcile competing changes |
| **.gitignore** | Specifies untracked files Git should normally ignore |
| **Working tree** | The checked-out files you work with |

### What is a branch?

A branch lets you develop a feature independently of another line of development.

For example:

```
main
 |
 A
 |
 B
 |
 C
```

Suppose you create a feature branch from commit B:

```
A --- B --- C       main
       \
        D --- E     feature/auth
```

You can develop authentication on `feature/auth` without immediately incorporating it into `main`.

A branch is not a complete independent copy of the repository’s history. It is a reference to a commit, and new commits advance that reference.

---

## 4. Configure Git

Before making commits, configure the identity recorded in your commits.

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

Replace the placeholders with your preferred commit identity.

Check your configuration:

```bash
git config --global --list
```

To configure a different identity for just one repository, run these commands from that repository and omit `--global`:

```bash
git config user.name "Your Name"
git config user.email "you@example.com"
```

### What does `--global` mean?

* With `--global`, the setting applies to your user account’s Git configuration.
* Without `--global`, the setting applies to the current repository.

Git commit identity is metadata. It does not, by itself, authenticate you to GitHub.

---

## 5. Create or Obtain a Repository

There are two common ways to begin.

### 5.1 Initialize a Local Repository

If you already have a project directory and want Git to track it:

```bash
git init
```

Run this from the intended project directory.

Git creates the repository metadata needed to track the project’s history.

Check the current state:

```bash
git status
```

If appropriate, establish main as the initial branch:

```bash
git branch -M main
```

Use that command carefully if the repository already contains branches or history you need to preserve.

### 5.2 Clone an Existing Repository

If a repository already exists on a remote hosting platform:

```bash
git clone <repository-url>
```

For example:

```bash
git clone https://github.com/OWNER/REPOSITORY.git
```

Cloning normally creates a local directory, downloads the repository’s history and tracked files, and configures a remote named `origin`.

Move into the cloned directory:

```bash
cd REPOSITORY
```

Check the repository state:

```bash
git status
git remote -v
```

### Which command should you use?

* `git init`: Start tracking an existing local directory.
* `git clone`: Obtain a local copy of an existing remote repository.

Do not blindly initialize and connect an existing project without checking whether it already has Git history.

---

## 6. Your First Complete Git Workflow

Suppose you’re creating a Java backend project and adding a README.

### Step 1: Inspect the project

```bash
git status
```

This helps you understand the current working-tree state before making changes.

### Step 2: Inspect changed files

```bash
git diff
```

This shows unstaged changes to tracked files.

For a new untracked file, `git diff` will not normally show its contents. Stage it first if you want to inspect the staged diff.

### Step 3: Stage the intended changes

```bash
git add README.md
```

Stage only the file you intend to include.

You can stage multiple specific files:

```bash
git add README.md pom.xml
```

To stage all changes under the current directory, including deletions and modifications:

```bash
git add -A
```

Use broad staging commands only after inspecting the repository. Otherwise, you may accidentally stage generated files, local configuration, or secrets.

### Step 4: Inspect the staged changes

```bash
git diff --cached
```

This shows the changes currently staged for the next commit.

### Step 5: Commit

```bash
git commit -m "Add project documentation"
```

A commit records the staged changes in local history.

### Step 6: Inspect the result

```bash
git status
git log -1 --oneline
```

The first command reports the working-tree state. The second shows the latest commit in a compact format.

### Remember the workflow

```
Inspect → Edit → Review → Stage → Review Staged Changes → Commit
```

The review steps are important. They reduce accidental commits and make your history easier to understand.

---

## 7. Essential Git Commands

These are the commands you’ll use frequently as a backend engineer.

| Command | Purpose |
| :--- | :--- |
| `git status` | Inspect working-tree and staging status |
| `git init` | Initialize a repository |
| `git clone <url>` | Clone a remote repository |
| `git add <file>` | Stage a file |
| `git add -A` | Stage additions, modifications, and deletions |
| `git commit -m "message"` | Commit staged changes |
| `git log` | Inspect commit history |
| `git log --oneline` | View compact commit history |
| `git diff` | Inspect unstaged changes to tracked files |
| `git diff --cached` | Inspect staged changes |
| `git branch` | List local branches |
| `git switch <branch>` | Switch branches |
| `git switch -c <branch>` | Create and switch to a branch |
| `git merge <branch>` | Merge the specified branch into the current branch |
| `git fetch` | Download remote updates without integrating them into the current branch |
| `git pull` | Fetch and integrate remote changes |
| `git push` | Push local commits to a remote |
| `git stash` | Temporarily store changes in progress |
| `git restore <file>` | Restore file contents from a source, commonly discarding unstaged changes |
| `git revert <commit>` | Create a new commit that reverses a specified commit’s changes |
| `git reset` | Move a branch reference and, depending on options, modify the index and working tree |

Some commands are intentionally destructive in particular modes. We will examine recovery and safe usage in Chunk 2.

---

## 8. Branching for Backend Development

Imagine you’re building a payment API. Your `main` branch contains the current integrated application, and you want to develop a new payment-validation feature.

Create a feature branch:

```bash
git switch -c feature/payment-validation
```

Make your changes and commit them:

```bash
git add src/
git commit -m "Add payment validation"
```

Return to `main`:

```bash
git switch main
```

Merge the feature branch:

```bash
git merge feature/payment-validation
```

The merge incorporates the feature branch’s changes into the current branch, subject to the histories and any conflicts.

### Why use branches?

Branches help engineers:

* Isolate features and bug fixes.
* Work on multiple tasks without mixing their changes.
* Prepare changes for review.
* Keep the main development line more controlled.

### Important detail

Switching branches can be blocked when local changes would be overwritten. Commit, stash, or otherwise safely handle those changes before switching.

Never assume switching branches automatically saves your uncommitted work.

---

## 9. Understand fetch, pull, and push

These commands are fundamental to collaborating through a remote repository.

### `git fetch`

```bash
git fetch origin
```

Downloads updates from the remote and updates the corresponding remote-tracking references.

It does not automatically merge those changes into your current branch.

Use it when you want to inspect remote changes before integrating them.

### `git pull`

```bash
git pull
```

Fetches updates and integrates them into the current branch.

The integration behavior depends on your configuration and options. It may use a merge or a rebase.

### `git push`

```bash
git push origin main
```

Pushes local commits from `main` to the remote branch, assuming the remote and branch are configured appropriately and the operation is permitted.

### Mental model

* Remote → Local remote-tracking references: `git fetch`
* Remote → Local branch, with integration: `git pull`
* Local commits → Remote: `git push`

### Common mistake

Running `git pull` without understanding the current branch, remote configuration, or working-tree state can produce unexpected results.

Inspect first:

```bash
git status
git branch --show-current
git remote -v
```

Then choose the appropriate operation.

---

## 10. Merge Conflicts

A merge conflict occurs when Git cannot automatically reconcile changes.

For example, two developers edit the same lines in `application.yml`.

Git may mark the conflicting region like this:

```yaml
<<<<<<< HEAD
server:
  port: 8080
=======
server:
  port: 8081
>>>>>>> feature/config-update
```

The marker meanings are:

* `<<<<<<< HEAD`: The version from the current branch.
* `=======`: Separates the competing versions.
* `>>>>>>> feature/config-update`: The version from the other branch.

These markers are temporary conflict notation, not valid YAML.

### How to resolve a conflict

1. Open the conflicted file.
2. Understand what each version is trying to accomplish.
3. Decide which changes should remain.
4. Edit the file into the correct final form.
5. Remove all conflict markers.
6. Run appropriate tests or validation.
7. Stage the resolved file.
8. Complete the merge or other operation in progress.

For example:

```bash
git status
```

Inspect the reported conflict paths, edit the files, and then stage a resolved file:

```bash
git add application.yml
```

If a merge is in progress, complete it as directed by Git. For a normal merge that requires a merge commit:

```bash
git commit
```

Git may open an editor with a default merge message.

If you decide to abandon an in-progress merge, `git merge --abort` may be appropriate. Inspect your working tree first, particularly if you had uncommitted changes before starting.

### Interview insight

A conflict is not necessarily a failure of Git. It is a point where Git needs a human to decide how competing changes should be reconciled.

---

## 11. restore, revert, and reset

These commands are related to undoing work, but they do different things.

### 11.1 `git restore`

Restore a tracked file’s working-tree contents:

```bash
git restore UserService.java
```

By default, this discards the file’s unstaged modifications by restoring from the index.

To unstage a file without discarding its working-tree changes:

```bash
git restore --staged UserService.java
```

The second command removes the file from the staging area but leaves the working-tree changes in place.

**Caution**: restoring a file can discard work. Review the diff before using it.

### 11.2 `git revert`

```bash
git revert <commit-hash>
```

Creates a new commit that reverses the changes introduced by the specified commit.

This is commonly useful when a problematic change has already been shared with other developers.

It preserves the existing history and records the reversal.

### 11.3 `git reset`

```bash
git reset --soft HEAD~1
```

Moves the current branch reference back one commit while keeping the changes from that commit staged.

Other modes have different effects:

* `--soft`: Keeps changes staged.
* `--mixed`: Resets the index while keeping working-tree changes; this is the default mode.
* `--hard`: Resets the index and working tree, potentially discarding uncommitted changes.

**Never use `git reset --hard` casually.** It can permanently discard work that is not otherwise recoverable.

### Which should you choose?

| Situation | Typical choice |
| :--- | :--- |
| Discard unstaged edits to a file | `git restore <file>` |
| Unstage a file but keep its edits | `git restore --staged <file>` |
| Reverse a commit while preserving shared history | `git revert <commit>` |
| Undo a recent local commit while keeping its changes staged | `git reset --soft HEAD~1` |
| Discard local changes intentionally | A destructive operation only after careful verification |

More complex recovery scenarios, including reflog and recovering lost commits, belong in Chunk 2.

---

## 12. Temporarily Store Work with git stash

Suppose you’re halfway through implementing a feature, but you need to switch to another branch to fix an urgent bug.

You do not want to create a premature commit.

You can temporarily stash tracked changes:

```bash
git stash push -m "Work in progress: payment validation"
```

Inspect the stash list:

```bash
git stash list
```

Reapply the latest stash while keeping it in the stash list:

```bash
git stash apply
```

Apply the latest stash and remove it from the stash list if successful:

```bash
git stash pop
```

Stash application can produce conflicts.

Also, untracked files are not included by default. To include them:

```bash
git stash push -u -m "Include untracked files"
```

### When should you stash?

Use it for short-lived context switching, not as a replacement for meaningful commits or a long-term backup.

---

## 13. .gitignore and Secret Protection

A `.gitignore` file specifies patterns for files that Git should normally ignore when they are untracked.

A Java/Spring Boot project might use rules such as:

```gitignore
# Build output
target/
# IDE configuration
.idea/
.vscode/
# Environment files
.env
.env.*
# Logs
*.log
# Operating-system metadata
.DS_Store
```

Adjust these patterns to your project. For example, if you need to commit a safe example environment file, you can deliberately allow a specific template while keeping real secrets excluded.

### Why this matters

Backend projects often contain:

* Database credentials.
* API keys.
* JWT signing secrets.
* Cloud access keys.
* Local environment configuration.
* Generated build output.

**Do not commit real secrets.**

### Important limitation

Adding a file to `.gitignore` does not automatically stop tracking a file that Git already tracks.

If a file has already been committed, removing it from tracking requires a separate operation. Even then, previously committed secrets may remain in repository history or other clones.

If a real credential is exposed, revoke or rotate it immediately. Deleting the file from the latest commit is not sufficient protection.

---

## 14. Pull Requests and Code Review

A pull request is a platform feature, commonly provided by GitHub, that lets developers propose changes for review before those changes are integrated.

A typical workflow looks like this:

```
main
  |
  +---- feature/payment-validation
                |
                | commits
                v
          Push feature branch
                |
                v
          Open pull request
                |
                v
          Review and tests
                |
                v
          Merge approved changes
```

A useful pull request should explain:

* What changed?
* Why was the change needed?
* How was it tested?
* Are there relevant screenshots, logs, or API examples?
* Are there risks or deployment considerations?

For backend work, reviewers may examine:

* API behavior.
* Database queries and migrations.
* Error handling.
* Authentication and authorization.
* Logging and sensitive-data exposure.
* Test coverage.
* Performance implications.
* Compatibility with existing clients.

### Interview insight

A pull request is not just a way to merge code. It is a collaboration and quality-control mechanism.

---

## 15. Common Git Mistakes

### Mistake 1: Forgetting to inspect staged changes
* **Problem**: Unrelated or sensitive files are included in a commit.
* **Prevention**:
  ```bash
  git status
  git diff --cached
  ```

### Mistake 2: Assuming a commit uploads code
* **Problem**: Changes exist locally but not on the remote.
* **Correction**: Push when appropriate, then verify the remote branch.

### Mistake 3: Committing secrets
* **Problem**: Credentials may be exposed in repository history.
* **Prevention**: Review staged files and maintain a suitable `.gitignore`. Rotate any exposed credentials.

### Mistake 4: Using vague commit messages
* **Weak**:
  ```bash
  git commit -m "changes"
  ```
* **Better**:
  ```bash
  git commit -m "Add payment validation"
  ```
* A useful message describes the intent of the change.

### Mistake 5: Using destructive commands without understanding them
* **Problem**: Uncommitted work can be lost.
* **Prevention**: Inspect `git status`, review diffs, and understand the command’s effect before executing it.

### Mistake 6: Treating Git and GitHub as the same thing
* **Problem**: Confusion about local commits, remote branches, authentication, and pushing.
* **Correction**: Understand which operations are local and which interact with a remote.

### Mistake 7: Using `git add .` without reviewing the project
* **Problem**: Generated files, temporary files, or secrets may be staged.
* **Correction**: Inspect the repository and use targeted staging where appropriate.

---

## 16. Practical Lab — Create a Clean Git Repository

Complete this exercise in a disposable practice directory or a new project directory that does not contain valuable work.

Do not experiment with destructive commands in an important existing repository.

### Task A: Initialize

```bash
mkdir git-practice
cd git-practice
git init
git branch -M main
```

If Git reports that a repository already exists, stop and inspect rather than assuming the directory is empty.

### Task B: Configure your identity if needed

```bash
git config user.name "Your Name"
git config user.email "you@example.com"
```

These repository-local settings are appropriate for the disposable exercise.

### Task C: Create a README

```bash
echo "# Git Practice" > README.md
```

Inspect the status:

```bash
git status
```

### Task D: Stage and review

```bash
git add README.md
git diff --cached
```

### Task E: Commit

```bash
git commit -m "Add initial README"
```

### Task F: Modify and inspect

```bash
echo "Learning Git fundamentals" >> README.md
git diff
```

Stage and commit the new change:

```bash
git add README.md
git diff --cached
git commit -m "Document Git learning goals"
```

### Task G: Inspect history

```bash
git log --oneline
```

You should see two commits.

### Task H: Create a branch

```bash
git switch -c feature/add-notes
```

Add a file:

```bash
echo "Branching practice" > notes.txt
git add notes.txt
git commit -m "Add branching practice notes"
```

Return to main:

```bash
git switch main
```

Inspect the directory and history. Notice that the branch-specific commit is not part of `main` yet.

This is the core value of branching: you can develop separately and integrate changes deliberately.

### Lab completion criteria

You should be able to explain:

* Why the first commit was local.
* What the staging area did.
* Why the second branch has its own commit.
* What would happen if you merged the feature branch into `main`.
* Why you should inspect changes before committing.

---

## 17. Git Interview Questions and Answers

### Q1. What is Git?
**Answer**: Git is a distributed version control system that tracks changes to files and allows developers to maintain history, create branches, and collaborate.

### Q2. What is the difference between Git and GitHub?
**Answer**: Git is the version-control system. GitHub is an online platform that hosts Git repositories and adds collaboration features such as pull requests and code reviews.

### Q3. What is the staging area?
**Answer**: It is the intermediate area where you select changes to include in the next commit.

### Q4. What is the difference between `git add` and `git commit`?
**Answer**: `git add` stages changes. `git commit` records the staged changes in the local repository.

### Q5. What is a branch?
**Answer**: A branch is a movable reference to a commit, allowing a line of development to progress independently.

### Q6. What is HEAD?
**Answer**: HEAD usually identifies the currently checked-out commit or branch. In a normal attached state, HEAD points to the current branch, which in turn identifies a commit.

### Q7. What is the difference between `git fetch` and `git pull`?
**Answer**: `git fetch` downloads remote updates without integrating them into the current branch. `git pull` fetches updates and then integrates them according to the configured or selected strategy.

### Q8. What is the difference between `git merge` and `git rebase`?
**Answer**: Merge integrates histories and may create a merge commit. Rebase replays commits onto another base, creating new commit identities for the replayed commits. Rebase can produce a more linear history, but rewriting published history can disrupt collaboration.

### Q9. What is a merge conflict?
**Answer**: It occurs when Git cannot automatically reconcile competing changes. A developer must inspect the conflict, decide the correct result, and complete the operation.

### Q10. What is the difference between `git revert` and `git reset`?
**Answer**: `git revert` creates a new commit that reverses another commit’s changes. `git reset` moves a branch reference and can also alter the index and working tree, depending on its mode.

### Q11. What is `.gitignore`?
**Answer**: It specifies patterns for files Git should normally ignore when they are untracked. It does not automatically untrack files already committed.

### Q12. Why are small, meaningful commits useful?
**Answer**: They make changes easier to review, debug, revert, and understand.

### Q13. What does `git stash` do?
**Answer**: It temporarily stores changes so you can switch context without immediately committing those changes.

### Q14. Does `git commit` push code to GitHub?
**Answer**: No. A commit records changes in the local repository. Pushing transfers commits to a remote repository.

### Q15. What should you check before committing?
**Answer**: Inspect the working-tree status, review the intended changes, check staged files with `git diff --cached`, and confirm that no secrets or unrelated files are included.

---

## 18. Mastery Checklist

Before proceeding to Chunk 2, verify that you can:

* [ ] Explain Git versus GitHub.
* [ ] Explain the working directory, staging area, and local repository.
* [ ] Initialize or clone a repository appropriately.
* [ ] Configure Git identity.
* [ ] Inspect repository status.
* [ ] Stage selected files.
* [ ] Review staged and unstaged changes.
* [ ] Create meaningful commits.
* [ ] Inspect commit history.
* [ ] Create and switch branches.
* [ ] Explain fetch, pull, and push.
* [ ] Merge a feature branch.
* [ ] Explain how merge conflicts are resolved.
* [ ] Distinguish restore, revert, and reset.
* [ ] Stash and reapply changes.
* [ ] Configure a useful `.gitignore`.
* [ ] Explain why `.gitignore` does not remove previously committed secrets.
* [ ] Describe a pull request and its purpose.

---

## 19. What Comes Next?

**Git Chunk 2 of 2 — Collaboration, Recovery, Advanced Workflows & Interview Scenarios**

The next chunk will build upon these foundations and cover:

* Remote branches and upstream tracking.
* More deliberate collaboration workflows.
* Cherry-picking commits.
* Reflog and recovery techniques.
* Diagnosing and recovering from common Git mistakes.
* Safe history management.
* Practical scenarios involving feature branches and shared repositories.
* Advanced Git interview questions.
* A final Git mastery assessment.

Once both chunks are complete, we will assemble and verify the single complete Git handbook PDF:

`BEH_GIT_COMPLETE_HANDBOOK.pdf`

Only after that PDF is verified will we create the Git completion commit:

```
Git done
```

*No separate chunk PDFs will be created.*
