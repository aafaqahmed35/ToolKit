# Git Chunk 2 of 2

Collaboration, Recovery & Production Engineering

Backend Engineering Tools & Infrastructure Handbook  
Phase I — Developer Foundations

---

## 1. The Mission: From Using Git to Engineering with Git

In Chunk 1, we established the fundamentals:

* The working directory, staging area, and repository.
* Commits, branches, and HEAD.
* Essential Git commands.
* Basic branching and merging.
* Conflict resolution.
* `restore`, `revert`, and `reset`.
* Stashing and `.gitignore`.
* Pull requests and everyday development workflows.

Now we take the next step.

Imagine you’re working on a production Spring Boot application with five other engineers.

One developer introduces a regression. Another pushes a conflicting change. You accidentally commit to the wrong branch. A deployment breaks, and the team needs to identify the responsible commit quickly.

Knowing `git add` and `git commit` isn’t enough.

You must understand how Git behaves when multiple histories interact, how to preserve work during recovery, and how to make safe decisions when a repository contains important shared history.

This chunk develops three complementary layers:

| Layer | Objective |
| :--- | :--- |
| **Layer 1 — Fundamentals & Mental Models** | Understand collaboration, history, references, and recovery |
| **Layer 2 — Practical Engineering & Workflows** | Execute branching, integration, investigation, and recovery workflows |
| **Layer 3 — Production Engineering & Interview Mastery** | Handle regressions, shared-history risks, incident investigations, and advanced interview scenarios |

By the end, you should be able to use Git as both a development tool and an engineering investigation tool.

---

# LAYER 1 — FUNDAMENTALS & MENTAL MODELS

## 2. Git Collaboration: Understand the Repository You’re Working In

### 2.1 Local branches and remote-tracking branches

Suppose your team hosts a repository on GitHub.

You clone it and begin developing locally.

You may see these references:

* `main`
* `origin/main`
* `feature/payment-validation`
* `origin/feature/payment-validation`

They represent different things:

| Reference | Meaning |
| :--- | :--- |
| `main` | Your local branch |
| `origin/main` | Your local record of the remote’s main branch |
| `feature/payment-validation` | Your local feature branch |
| `origin/feature/payment-validation` | Your local record of the remote feature branch |

The distinction is important: `origin/main` is not a live connection to GitHub. It is a remote-tracking reference updated by operations such as `git fetch`.

The remote named `origin` is simply a conventional name. A repository can have other remotes.

### 2.2 Inspect before changing anything

Use:

```bash
git status
git branch -vv
git branch -a
git remote -v
git log --oneline --graph --decorate --all
```

These commands answer important questions:

* What branch am I on?
* Do I have uncommitted work?
* Which remote branches are known locally?
* Which remote does this repository use?
* How are the commits connected?

**Engineering principle**: Never start a complex Git recovery or synchronization operation without first understanding the repository’s current state.

### 2.3 What is an upstream branch?

An upstream branch is the branch associated with your local branch for comparison and synchronization.

For example:

```
Local branch: feature/payment-validation
Upstream:     origin/feature/payment-validation
```

Inspect upstream relationships:

```bash
git branch -vv
```

When a local branch has an upstream configured, Git can generally infer the appropriate remote branch for ordinary `git pull` and `git push` commands.

The upstream relationship does not mean that your local and remote branches are always synchronized.

They can diverge.

---

## 3. Understand History Before Manipulating It

A Git commit is a snapshot of tracked project state, together with metadata and references to parent commits.

A branch is a reference to a commit.

`HEAD` identifies the currently checked-out commit or branch, depending on the repository state.

These concepts explain why many Git operations behave as they do.

Consider:

```
A --- B --- C       main
       \
        D --- E     feature
```

Here:

* `main` points to commit `C`.
* `feature` points to commit `E`.
* Both branches share history through commit `B`.
* Commits `D` and `E` are not part of the ancestry of `main`.

If you merge `feature` into `main`, Git integrates the feature history into `main`.

If you rebase `feature` onto `main`, Git replays the feature’s commits on top of `main`, producing new commit identities.

If you cherry-pick `D` onto `main`, Git applies the changes introduced by `D` and creates a new commit on `main`.

These operations can produce similar file contents while creating different histories.

**The critical distinction**: file contents and commit history are related, but they are not the same thing.

---

## 4. Merge, Rebase, and Cherry-Pick: Three Different Decisions

### 4.1 Merge: Integrate histories

Suppose you have:

```
A --- B --- C       main
       \
        D --- E     feature
```

You run:

```bash
git switch main
git merge feature
```

If a fast-forward is not possible and Git creates a merge commit, the history may become:

```
A --- B --- C ------- M    main
       \             /
        D --- E -----
```

Merge integrates the histories while preserving the original commits.

**Advantages**:
* Preserves branch topology.
* Clearly records the integration point when a merge commit is created.
* Works well for integrating shared development histories.

**Trade-off**:
* Merge commits can make the history graph more complex.

A merge does not always create a merge commit. If the current branch can fast-forward to the other branch, Git may simply move the branch reference forward.

### 4.2 Rebase: Replay commits onto another base

Run:

```bash
git switch feature
git rebase main
```

Conceptually, the history becomes:

```
A --- B --- C              main
             \
              D' --- E'    feature
```

Git replays the feature commits on top of `main`.

The replayed commits have new identities because their parent relationships have changed.

**Advantages**:
* Can produce a more linear history.
* Makes some commit sequences easier to inspect.

**Trade-offs**:
* Rewrites the identities of replayed commits.
* May require resolving conflicts during replay.
* Can disrupt collaboration if published history is rewritten carelessly.

Rebase is often appropriate for unpublished feature work.

Avoid rewriting shared branch history unless the team explicitly agrees on the workflow.

### 4.3 Cherry-pick: Apply one specific commit

Suppose commit `D` contains a bug fix, but commit `E` contains unrelated work.

You want only the fix:

```bash
git switch main
git cherry-pick <commit-hash-of-D>
```

Git applies the changes introduced by `D` to the current branch and creates a new commit.

The original commit remains in its original history.

Cherry-picking is useful for:
* Backporting a fix to a maintenance branch.
* Applying a targeted correction to a release branch.
* Transferring an isolated change without merging an entire feature branch.

Avoid indiscriminate cherry-picking. Repeatedly copying commits across branches can complicate future integration.

### 4.4 Decision table

| Situation | Typical approach |
| :--- | :--- |
| Integrate a feature branch | Merge or the team’s approved pull-request strategy |
| Replay private feature commits onto an updated base | Rebase |
| Apply one isolated fix to another branch | Cherry-pick |
| Reverse a published problematic commit | Revert |
| Remove or reorganize unpublished local commits | Reset or rebase, with care |

No operation is universally best. The correct choice depends on the intended history, collaboration policy, and whether commits have been shared.

---

# LAYER 2 — PRACTICAL ENGINEERING & WORKFLOWS

## 5. The Professional Feature-Branch Workflow

Imagine you’re implementing payment validation in a Spring Boot application.

The team expects features to be developed on separate branches and reviewed before integration.

### Step 1: Inspect your current state

```bash
git status
git branch --show-current
git branch -vv
```

Do not switch branches or pull remote changes blindly when you have uncommitted work.

### Step 2: Update your local main branch

```bash
git switch main
git fetch origin
git pull --ff-only origin main
```

The fast-forward-only option prevents Git from automatically merging or rebasing a diverged local branch during this pull.

If the operation fails because the histories have diverged, inspect them and decide on an appropriate integration strategy.

### Step 3: Create a feature branch

```bash
git switch -c feature/payment-validation
```

### Step 4: Implement and commit the feature

```bash
git add src/
git diff --cached
git commit -m "Add payment validation"
```

Inspect the staged diff before committing. Ensure that only intended files are included.

### Step 5: Push and establish upstream tracking

```bash
git push -u origin feature/payment-validation
```

The `-u` option configures the upstream relationship if the push succeeds.

### Step 6: Open a pull request

Propose merging the feature branch into the appropriate target branch.

A strong pull request should describe:
* What changed.
* Why it changed.
* How it was tested.
* Whether database migrations are required.
* Whether configuration changes are required.
* Any deployment risks.
* Any compatibility implications.

### Step 7: Integrate the approved change

The team may use a merge commit, squash merge, or rebase-based strategy.

Follow the repository’s conventions rather than assuming all teams use the same strategy.

### Step 8: Synchronize your local main branch

After the feature has been integrated:

```bash
git switch main
git fetch origin
git pull --ff-only origin main
```

Delete obsolete branches only after confirming that their work has been preserved and integrated.

Delete a local branch:

```bash
git branch -d feature/payment-validation
```

Delete a remote branch only when appropriate:

```bash
git push origin --delete feature/payment-validation
```

**Mastery principle**: A branch is a way to organize development, not a backup. Preserve important commits and verify integration before deleting branches.

---

## 6. Scenario: Your Push Is Rejected

You run:

```bash
git push origin main
```

Git responds with a non-fast-forward rejection.

This often means the remote branch contains commits that your local branch does not have.

For example:

```
Local main:   A --- B --- C
Remote main:  A --- B --- D
```

Both histories share `A` and `B`, but they have diverged.

**Do not immediately force-push.**

### Step 1: Inspect the repository

```bash
git status
git branch -vv
```

### Step 2: Fetch remote changes

```bash
git fetch origin
```

### Step 3: Compare the histories

```bash
git log --oneline --graph --decorate main origin/main
```

See commits on the remote that are not on your local branch:

```bash
git log main..origin/main --oneline
```

See commits on your local branch that are not on the remote:

```bash
git log origin/main..main --oneline
```

These comparisons assume that both references exist locally.

### Step 4: Choose an integration strategy

If your local branch can safely fast-forward, you can use:

```bash
git pull --ff-only origin main
```

If the branches have diverged, you must decide whether to merge, rebase unpublished local commits, or use another repository-approved approach.

Before changing history, establish whether the local commits have been shared or whether other developers depend on them.

### Step 5: Push after integration

Once the histories are correctly integrated and the changes are tested:

```bash
git push origin main
```

### Why not immediately force-push?

A force-push can replace the remote branch reference with a different history, potentially making other developers’ commits inaccessible through that branch.

`--force-with-lease` offers a safety check against unexpected remote changes, but it does not eliminate the risk of rewriting shared history.

**Rule**: A rejected push is a signal to inspect the histories, not an invitation to overwrite the remote.

---

## 7. Scenario: You Committed to the Wrong Branch

You intended to commit a feature on `feature/authentication`, but you committed it to `main`.

Your latest commit contains the feature.

The correct recovery depends on whether the commit has been pushed.

### Case A: The commit is local and unpublished

First, inspect:

```bash
git status
git log --oneline -5
```

If the latest commit is the mistaken feature commit and the working tree is clean, create the intended branch at the current commit:

```bash
git branch feature/authentication
```

This preserves the commit under the new branch name.

If you have confirmed that the latest commit should be removed from the local `main` branch, you can move `main` back one commit:

```bash
git switch main
git reset --hard HEAD~1
```

*Warning*: This is destructive to uncommitted changes and moves the current branch reference. Use it only after verifying the commit, confirming the feature branch preserves the desired work, and ensuring no uncommitted changes need protection.

Then switch to the feature branch:

```bash
git switch feature/authentication
```

Verify the branch and history:

```bash
git log --oneline --graph --decorate --all
```

### Case B: The commit has already been pushed

Do not automatically reset the shared branch and force-push.

A safer general approach is to reverse the unwanted change on the shared branch:

```bash
git revert <commit-hash>
```

Then ensure the feature is available on the intended branch and follow the team’s normal review and integration workflow.

The exact sequence depends on the branch topology and whether the feature has already been copied or integrated elsewhere.

### The lesson

Preserve the desired commit before changing a branch reference. Treat unpublished local history differently from shared history.

---

## 8. Scenario: A Commit Introduced a Regression

Your backend API worked yesterday. Today, a validation endpoint returns HTTP 500 instead of the expected response.

You suspect a recent code change.

Git provides several ways to investigate:

### 8.1 Inspect recent history

```bash
git log --oneline -10
```

### 8.2 Inspect a suspicious commit

```bash
git show <commit-hash>
```

### 8.3 Compare two revisions

```bash
git diff <known-good-commit> <failing-commit>
```

To focus on one file:

```bash
git diff <known-good-commit> <failing-commit> -- src/main/java/com/example/UserService.java
```

### 8.4 Inspect a file’s history

```bash
git log --oneline -- src/main/java/com/example/UserService.java
```

These commands help narrow down what changed, but they do not prove that a particular commit caused the failure.

You must also reproduce the failure and examine the runtime evidence.

---

## 9. Find the Problematic Commit with git bisect

When many commits exist between the last known-good revision and the failing revision, `git bisect` can systematically narrow down the regression.

Suppose:

* Commit `A` passes the test.
* Commit `H` fails the test.
* Several commits exist between them.

Git can repeatedly select an intermediate revision for testing.

### Step 1: Start bisect

```bash
git bisect start
```

### Step 2: Mark the current revision as bad

```bash
git bisect bad
```

### Step 3: Mark a known-good revision

```bash
git bisect good <known-good-commit>
```

Git checks out a revision between the good and bad points.

Run a reliable regression test.

If it fails:

```bash
git bisect bad
```

If it passes:

```bash
git bisect good
```

Repeat until Git identifies the first bad commit in the tested range, assuming the good/bad classification is consistent and the history supports the search.

### Step 4: End the session

```bash
git bisect reset
```

This returns you to the previous checkout state.

### Backend example

Suppose you have a repeatable integration test that submits an invalid request and checks the response.

If the test passes on the known-good revision but fails on the current revision, you can use it to classify revisions during bisect.

### Important limitations

Bisect is most useful when:
* The known-good and known-bad revisions are identified correctly.
* The test is repeatable.
* The environment is consistent.
* The relevant commits form a suitable history for the search.

Flaky tests, build failures unrelated to the regression, and inconsistent dependencies can make the results difficult to interpret.

---

## 10. Recovery: You Cannot Find a Commit

You reset a branch and a commit disappeared from normal history.

Before assuming the work is lost, inspect the reflog:

```bash
git reflog
```

You might see:

```
a1b2c3d HEAD@{0}: reset: moving to HEAD~1
d4e5f6a HEAD@{1}: commit: Add payment validation
```

The hashes and descriptions are illustrative.

The older entry indicates a previous `HEAD` position.

### Step 1: Inspect the candidate commit

```bash
git show d4e5f6a
```

### Step 2: Preserve it with a recovery branch

```bash
git branch recovery/payment-validation d4e5f6a
```

### Step 3: Inspect the recovered history

```bash
git log --oneline recovery/payment-validation
```

Once you have confirmed the recovered commit, determine how it should be integrated.

### Why not immediately reset the current branch again?

You may have identified the wrong commit or misunderstood the repository state.

A recovery branch preserves the candidate while you investigate.

### Reflog limitations

Reflog is a local recovery aid, not a permanent backup.

It does not guarantee recovery of uncommitted work or every unreachable object. Entries can expire, and unreachable objects can eventually be removed by repository maintenance.

If work appears lost, stop running cleanup commands and investigate before making further changes.

---

## 11. Recovery: Choosing Between Reset and Revert

Suppose commit `D` introduces a bug:

```
A --- B --- C --- D
```

The correct recovery strategy depends on whether the commit is private or shared.

### 11.1 Revert a shared commit

```bash
git revert <commit-hash>
```

Git creates a new commit that reverses the selected commit’s changes.

Conceptually:

```
A --- B --- C --- D --- E
                         ^
                   Reversal of D
```

The original history remains visible.

This is generally suitable for correcting published changes without rewriting the shared branch history.

### 11.2 Reset an unpublished commit

If the latest commit is local, unpublished, and you want to keep its changes staged:

```bash
git reset --soft HEAD~1
```

If you want to keep its changes in the working tree but unstage them:

```bash
git reset HEAD~1
```

The default reset mode is `--mixed`.

To remove the latest commit and discard changes in the index and working tree:

```bash
git reset --hard HEAD~1
```

Do not run the hard reset unless you have verified the exact target and protected any work you need.

### Decision table

| Situation | Typical approach |
| :--- | :--- |
| Latest unpublished commit needs editing | `git reset --soft HEAD~1` |
| Latest unpublished commit should be undone but its changes retained unstaged | `git reset HEAD~1` |
| A published commit must be reversed | `git revert <commit>` |
| A commit appears to have disappeared | Inspect `git reflog` |
| A particular commit is needed on another branch | `git cherry-pick <commit>` |

---

# LAYER 3 — PRODUCTION ENGINEERING & INTERVIEW MASTERY

## 12. Production Incident: A Bad Configuration Reaches Production

Your Spring Boot application deploys a new release.

Immediately afterward:
* Database connections fail.
* Some API endpoints return HTTP 500.
* The deployment health check fails.
* The team suspects a recent configuration change.

Git can help identify the change, but it cannot independently establish the root cause.

Use a disciplined investigation:

### Step 1: Identify the deployed revision

Determine which commit was deployed using release metadata, build information, deployment logs, or the platform’s release history.

Do not assume that the latest commit on `main` is the deployed commit.

### Step 2: Inspect the relevant change

```bash
git show <deployed-commit>
```

Compare the deployed revision with the last known-good revision:

```bash
git diff <known-good-commit> <deployed-commit> -- application.yml
```

Adapt the path to the actual configuration file.

### Step 3: Gather runtime evidence

Inspect:
* Application logs.
* Deployment logs.
* Database connectivity.
* Environment-variable configuration.
* Health-check responses.
* Recent infrastructure changes.

Avoid printing secrets into logs or incident reports.

### Step 4: Decide whether the commit is responsible

Look for evidence connecting the change to the failure.

A recent commit is a candidate, not proof of causation.

### Step 5: Restore service

Depending on the deployment system and incident, you may:
* Revert the offending commit and deploy the correction.
* Apply a forward fix.
* Roll back to a known-good release.

Follow the team’s release and incident procedures.

### Step 6: Verify recovery

Confirm that:
* The application starts correctly.
* Database connections succeed.
* Health checks pass.
* The affected API behavior is restored.
* Relevant error rates return to acceptable levels.

### Step 7: Preserve the learning

Create a focused fix, add regression tests, and document the incident according to team policy.

### Production takeaway

Git provides the history of intended code changes. Logs, metrics, deployment metadata, and runtime tests provide the evidence needed to understand actual system behavior.

---

## 13. Git Safety Rules for Production Teams

### Rule 1: Inspect before changing history
Before `reset`, `rebase`, `cherry-pick`, or recovery operations:
```bash
git status
git log --oneline --graph --decorate --all
git branch -vv
```
These commands do not guarantee safety, but they give you the context needed to make a reasoned decision.

### Rule 2: Preserve valuable commits before recovery
If you are uncertain whether a commit is needed, create a branch at that commit after verifying it:
```bash
git branch recovery/important-work <commit-hash>
```
A branch reference can preserve access to a commit while you investigate.

### Rule 3: Treat shared history carefully
Rewriting unpublished local history is different from rewriting a branch used by other developers. Coordinate before rewriting shared history.

### Rule 4: Do not treat Git as a backup system
A repository can be damaged, local commits can become unreachable, and uncommitted changes may never enter Git history. Use appropriate remote backups and preserve important work.

### Rule 5: Protect secrets immediately
If a credential is committed:
1. Revoke or rotate it.
2. Identify potentially exposed copies.
3. Assess whether history cleanup is necessary.
4. Coordinate any history rewrite.
5. Prevent the secret from being committed again.

Removing the secret from the latest commit does not invalidate copies of the old credential.

### Rule 6: Keep commits understandable
Prefer focused commits with meaningful messages.

Examples:
* `Add payment validation`
* `Fix database connection configuration`
* `Handle duplicate event delivery`
* `Add retry handling to payment consumer`

Good commit messages help code review, regression investigation, and incident analysis.

---

## 14. Practical Engineering Lab

Complete the following exercises in a disposable repository.

Do not perform destructive experiments in a project containing valuable work.

### Lab A: Create and push a feature branch
1. Initialize or clone a practice repository.
2. Create `feature/api-validation`.
3. Make a change.
4. Commit it.
5. Push with upstream tracking.
6. Inspect the local and remote-tracking references.

Commands to practise:
```bash
git switch -c feature/api-validation
git add .
git diff --cached
git commit -m "Add API validation"
git push -u origin feature/api-validation
git branch -vv
```

### Lab B: Cherry-pick an isolated fix
1. Create a feature branch.
2. Add and commit a single isolated change.
3. Switch to another branch.
4. Cherry-pick the commit.
5. Compare the resulting histories.

Explain why the cherry-picked commit has a different identity.

### Lab C: Recover a commit
1. Create a commit in a disposable repository.
2. Record its hash.
3. Move the branch reference backward.
4. Inspect `git reflog`.
5. Create a recovery branch at the intended commit.
6. Verify that the expected content is present.

Do not proceed with further cleanup until the recovery has been verified.

### Lab D: Investigate a regression
1. Create several commits.
2. Introduce a deliberate bug in one commit.
3. Add a repeatable test that exposes it.
4. Identify known-good and known-bad revisions.
5. Use `git bisect` to locate the problematic commit.
6. End the session with `git bisect reset`.

### Lab E: Handle a rejected push
Using a remote practice repository and two separate working copies:
1. Commit a change in the first copy.
2. Independently commit another change in the second copy.
3. Push from one copy.
4. Attempt to push the other copy.
5. Inspect the rejection.
6. Fetch and compare histories.
7. Integrate the remote changes using an appropriate strategy.
8. Verify the final history and push successfully.

This exercise demonstrates why a rejected push should trigger investigation rather than an immediate force-push.

---

## 15. Advanced Interview Questions

### Q1. What is the difference between `origin/main` and `main`?
**Answer**: `main` is a local branch. `origin/main` is a remote-tracking reference representing the local repository’s view of the remote branch.

### Q2. Why does cherry-picking create a new commit?
**Answer**: Cherry-pick applies the changes from an existing commit to the current branch. The resulting commit has a different parent relationship and therefore a different commit identity.

### Q3. How can you recover a commit after an accidental reset?
**Answer**: Inspect `git reflog`, identify the intended commit, verify it with `git show`, and preserve it using a recovery branch before deciding how to integrate it.

### Q4. Why is reflog not a backup?
**Answer**: It is local, time-limited by repository configuration and maintenance, and cannot guarantee recovery of uncommitted changes or every unreachable object.

### Q5. When would you choose revert over reset?
**Answer**: Revert is generally preferred for reversing changes in shared history because it adds a new commit instead of moving the shared branch backward.

### Q6. How do you diagnose a non-fast-forward push rejection?
**Answer**: Inspect the working tree and branch relationships, fetch the remote, compare local and remote histories, integrate the changes using an appropriate strategy, test, and push again.

### Q7. What is the danger of rebasing a shared branch?
**Answer**: Rebase creates new commit identities. Rewriting published history can cause divergence and force collaborators to reconcile their local histories.

### Q8. What is `git bisect`?
**Answer**: A regression-isolation tool that uses known-good and known-bad revisions to narrow down the commit that introduced a problem.

### Q9. How can Git help with a production incident?
**Answer**: It identifies the code history associated with a deployed revision, enables comparisons with known-good versions, and helps locate candidate changes. Runtime evidence is still necessary to establish causation.

### Q10. Why is a clean working tree important before recovery?
**Answer**: Uncommitted changes can be overwritten or complicated by operations that switch branches, reset files, or rewrite history. A clean tree makes the starting state easier to reason about, although it does not by itself guarantee safety.

### Q11. How should a team handle a commit that accidentally reached a shared production branch?
**Answer**: Assess the impact, follow the team’s incident process, and usually create a corrective commit or revert the change. Avoid rewriting shared history without explicit coordination.

### Q12. When should you use cherry-pick instead of merge?
**Answer**: When you need a specific isolated change from another branch and do not want to integrate the entire branch history.

### Q13. Why is `git reset --hard` dangerous?
**Answer**: It moves the branch reference and resets the index and working tree, potentially discarding uncommitted changes. Its use requires careful verification.

### Q14. What is the difference between a code rollback and a Git revert?
**Answer**: A Git revert creates a commit that reverses changes in repository history. A deployment rollback restores a previously released version of a running system. They are related but not identical operations.

### Q15. Can the latest commit always be assumed to be the version running in production?
**Answer**: No. The deployed revision must be established using release metadata, build identifiers, or deployment records.

---

## 16. Git Mastery Assessment

Before considering Git complete, you should be able to demonstrate all three layers:

### Layer 1 — Fundamentals & Mental Models
* [ ] Explain local branches versus remote-tracking branches.
* [ ] Explain upstream tracking.
* [ ] Describe the differences between merge, rebase, and cherry-pick.
* [ ] Explain why rebased and cherry-picked commits have different identities.
* [ ] Explain reflog and its limitations.

### Layer 2 — Practical Engineering & Workflows
* [ ] Execute a feature-branch workflow.
* [ ] Push a branch with upstream tracking.
* [ ] Investigate a rejected push.
* [ ] Cherry-pick an isolated commit.
* [ ] Recover a commit with reflog.
* [ ] Use `git bisect` to locate a regression.
* [ ] Resolve conflicts during integration.
* [ ] Inspect branch differences and commit history.

### Layer 3 — Production Engineering & Interview Mastery
* [ ] Distinguish local recovery from shared-history recovery.
* [ ] Explain when revert is safer than reset.
* [ ] Investigate a production regression using deployed revision information.
* [ ] Explain why force-pushing shared branches is risky.
* [ ] Explain why Git is not a backup system.
* [ ] Describe how to handle a committed secret.
* [ ] Distinguish a Git revert from a deployment rollback.
* [ ] Explain how code history and runtime evidence work together during an incident.

---

## 17. Git Handbook Completion Protocol

Git Chunk 2 of 2 is complete.

The Git curriculum remains unchanged: two chunks total.

The authoritative source files should be:

```
content/git/
├── 01-git-fundamentals.md
└── 02-git-collaboration-recovery-advanced-workflows.md
```

The completed Git handbook must combine both chunks in order and retain the full educational content.

Final PDF:
```
BEH_GIT_COMPLETE_HANDBOOK.pdf
```

Before marking Git complete:

1. Verify both source files are present and complete.
2. Confirm all three learning layers are represented.
3. Assemble the complete handbook without summarizing or deleting sections.
4. Generate and inspect the PDF.
5. Check code examples, headings, page breaks, and missing content.
6. Update the README only after verification.
7. Commit the completed Git source, PDF, and relevant progress updates using:
   ```
   Git done
   ```
8. Verify the commit.
9. Push only if the remote is correctly configured and the push succeeds.

*No separate chunk PDFs will be created.*

---

## Next in the Curriculum

**Linux Chunk 1 of 6 — Terminal & Filesystem Mastery**

The total curriculum remains locked at 32 chunks across 13 tools. We are strengthening the structure and quality of the existing chunks, not increasing the number of chunks.
