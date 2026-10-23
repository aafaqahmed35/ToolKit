# Terraform — Chunk 2 of 3: State Management, Modules, Environments & Safe Infrastructure Workflows

## Backend Engineering Tools & Infrastructure Handbook

**Source file:** `content/terraform/02-terraform-state-modules-environments-safe-workflows.md`

**Learning objective:** Learn to manage Terraform state safely, structure reusable infrastructure modules, separate environments, and collaborate on infrastructure changes without creating unnecessary production risk.

---

# Layer 1 — Fundamentals & Mental Models

## 1. Why Terraform state deserves special attention

In the first chapter, we established the basic lifecycle:

**Configuration → Plan → Apply → Infrastructure**

Now we need to understand how Terraform remembers which resources it manages.

Consider a configuration that declares a database:

```hcl
resource "example_database" "orders" {
  name = "orders-db"
}
```

Terraform needs to associate the resource address `example_database.orders` with the actual database created through the provider.

That relationship is recorded in Terraform state.

State can contain resource identifiers, provider-returned attributes, dependency information, and potentially sensitive values. It is therefore a critical operational asset.

### The three things to distinguish

| Concept | Meaning |
|---|---|
| Configuration | What you declare Terraform should manage |
| State | Terraform's record of the resources it manages |
| Real infrastructure | The actual objects and their current behavior |

These are related, but they are not interchangeable.

A configuration file is not a state backup. State is not a complete backup of a database's contents. And neither one guarantees that the real infrastructure is healthy.

## 2. How Terraform uses state

Imagine this sequence:

1. You declare an application server.
2. Terraform creates it.
3. The provider returns the server's identifier and attributes.
4. Terraform records the association in state.
5. On a later plan, Terraform uses configuration, state, and provider observations to calculate proposed changes.

The state helps Terraform understand resource identity and prior management decisions.

Without the correct state, Terraform may not know that an existing object corresponds to a declared resource. Depending on the situation, this can lead to unexpected creation attempts, conflicts, or unsafe plans.

**Mental model:** State is Terraform's management ledger, not the infrastructure itself.

## 3. Local state versus remote state

### Local state

By default, a simple Terraform project may store state in a local file such as `terraform.tfstate`.

Advantages:

- Simple to understand.
- Convenient for disposable local exercises.
- No remote backend setup required.

Risks:

- Other engineers cannot automatically share the same state safely.
- A lost workstation can mean lost state.
- Local state may be accidentally committed or exposed.
- Concurrent workflows are difficult to coordinate.

### Remote state

A remote backend stores state using a supported remote storage mechanism.

Benefits can include:

- Centralized access control.
- Shared state across authorized team members.
- State locking or concurrency controls where supported.
- Versioning and recovery options when configured.
- Integration with controlled deployment pipelines.

Remote state does not automatically guarantee all these benefits. The selected backend and its configuration determine which capabilities are available.

### Choosing an approach

| Scenario | Typical choice |
|---|---|
| Disposable local learning exercise | Local state |
| Team-managed shared environment | Remote state |
| Production infrastructure | Remote state with access controls, concurrency protection, and recovery planning |

## 4. State locking and concurrent operations

Suppose two engineers try to apply changes against the same state at nearly the same time.

Engineer A plans to update a network. Engineer B plans to change the same environment before A's operation finishes.

Without suitable coordination, concurrent changes can produce conflicts or leave engineers with stale assumptions.

Where supported, state locking prevents multiple Terraform operations from simultaneously modifying the same state.

However, locking is not a substitute for change review. It coordinates state operations; it does not determine whether a proposed change is correct.

**Important:** Do not assume every backend supports locking in the same way. Check the chosen backend's documented capabilities and configuration.

## 5. Terraform modules: reusable infrastructure design

A module is a collection of Terraform configuration files that work together as a reusable unit.

Every Terraform working directory containing configuration is a root module. A root module can call child modules.

For example, an organization might define:

```text
infrastructure/
├── main.tf
├── variables.tf
├── outputs.tf
└── modules/
    ├── network/
    ├── application/
    └── database/
```

Each module has a defined responsibility.

- `network` manages networking resources.
- `application` manages application compute and related settings.
- `database` manages database infrastructure.

The directory structure is illustrative. The actual resources depend on the provider and platform.

### Why modules matter

Without modules, teams may duplicate similar configuration across multiple environments. Duplication makes it easier for security settings, tags, resource sizing, or networking rules to drift apart.

Modules allow teams to centralize common patterns and expose inputs for legitimate differences.

### The abstraction tradeoff

A module that hides every detail may become difficult to troubleshoot. A module that exposes every underlying resource property may not provide much abstraction.

A good module offers:

- A clear purpose.
- Explicit inputs.
- Useful outputs.
- Sensible defaults.
- Documented security and lifecycle behavior.
- A manageable interface.

## 6. Module inputs and outputs

A module can accept inputs through variables and return selected information through outputs.

Conceptual root-module configuration:

```hcl
module "application" {
  source = "./modules/application"

  application_name = "orders-api"
  environment      = "development"
}
```

The child module might define:

```hcl
variable "application_name" {
  type = string
}

variable "environment" {
  type = string
}

output "application_name" {
  value = var.application_name
}
```

These snippets illustrate the module interface; a real module must also define the resources it manages.

Module outputs can be referenced by the root module:

```hcl
output "deployed_application_name" {
  value = module.application.application_name
}
```

Keep outputs intentional. Do not expose credentials or unnecessary internal details merely because a child module can return them.

## 7. Separate environments without losing consistency

A backend project may have development, staging, and production environments.

They often share architectural patterns but differ in:

- Resource size.
- Replica count.
- Network boundaries.
- Access permissions.
- Availability requirements.
- Data classification.
- Backup and recovery settings.
- Cost constraints.

The goal is **consistent design with explicit environment-specific configuration**.

### Common approaches

**Separate directories or root modules**

```text
environments/
├── development/
├── staging/
└── production/
```

Each environment can have its own configuration and state boundary.

**Reusable modules with separate root configurations**

Each environment calls the same modules but supplies different values.

**Terraform workspaces**

Workspaces provide separate state instances associated with a configuration and backend. They can be useful for certain workflows, but they do not automatically provide strong security or organizational isolation.

For critical environments, separate configurations, backend state boundaries, permissions, and deployment controls may be more appropriate than relying on workspace names alone.

## 8. Terraform workspaces: what they do and do not do

Terraform workspaces allow multiple state instances to be associated with the same configuration.

Conceptually:

```text
Same configuration
       |
       +---- development state
       |
       +---- staging state
       |
       +---- production state
```

The exact behavior depends on the backend and workspace configuration.

Workspaces do not automatically create:

- Separate cloud accounts.
- Different IAM permissions.
- Network isolation.
- Independent deployment approval policies.
- Separate credentials.
- Protection against applying to the wrong environment.

A workspace is a state-management mechanism, not a complete environment-security boundary.

Before using workspaces for production, determine whether they fit the organization's access-control, isolation, and recovery requirements.

## 9. Dependencies and module composition

A root module can connect child modules through their inputs and outputs.

For example:

```text
Network module
      |
      v
Database module

Network module
      |
      v
Application module
      |
      v
Application endpoint output
```

When a module input references another module's output, Terraform can establish an implicit dependency.

Avoid hard-coding identifiers that should be supplied by the infrastructure graph. Explicit references make relationships easier to understand and reduce accidental coupling to a particular environment.

Do not add `depends_on` mechanically. Use it when a genuine dependency exists but is not already represented through expressions.

---

# Layer 2 — Practical Engineering & Workflows

## 10. Configure a remote backend safely

Terraform supports multiple backends, each with its own requirements and capabilities.

A remote backend configuration may look conceptually like this:

```hcl
terraform {
  backend "example" {
    # Backend-specific configuration goes here.
  }
}
```

`example` is a placeholder, not a real backend type. Replace it with a supported backend and its documented settings.

Backend configuration is special: Terraform must initialize the backend before normal planning and applying.

A safe setup sequence is:

1. Choose the backend.
2. Create its storage and access controls through an approved process.
3. Configure locking or concurrency protection if supported.
4. Configure encryption and recovery options where available.
5. Add the backend block to the Terraform configuration.
6. Run `terraform init`.
7. Review any state migration prompts carefully.
8. Verify that the intended state is available.
9. Test the normal plan workflow before making infrastructure changes.

Never delete a local state file just because a remote backend has been configured. First verify that the state migration or initialization completed correctly and that the remote state contains the expected resource mappings.

## 11. Inspect state safely

Useful commands include:

```bash
terraform state list
terraform state show <resource-address>
terraform show
```

For example:

```bash
terraform state list
terraform state show terraform_data.application
```

These commands help inspect what Terraform currently tracks.

State inspection can reveal sensitive values. Be careful when sharing terminal output in issue trackers, pull requests, chat, or screenshots.

### Do not edit state files manually

Terraform provides specific state commands for supported management tasks. Directly editing a state file can corrupt resource mappings or introduce inconsistencies.

If state must be repaired, investigate the supported operation for the situation and take a recovery backup where appropriate.

## 12. Recovering from state problems

State problems can arise from:

- Accidental deletion.
- Incorrect backend configuration.
- Failed state migration.
- Resource changes made outside Terraform.
- A resource imported incorrectly.
- An operation interrupted during a critical transition.

A disciplined recovery workflow:

1. Stop concurrent applies.
2. Identify the correct environment and backend.
3. Inspect available state versions or backups.
4. Determine whether real infrastructure is still present.
5. Preserve the current evidence before attempting repair.
6. Follow the backend's recovery procedure.
7. Run a fresh plan.
8. Review all proposed changes before applying.

Do not blindly copy an old state file over the current state. The infrastructure may have changed since the backup was created.

## 13. Build a reusable application module

Create a module directory:

```bash
mkdir -p modules/application
```

Create `modules/application/variables.tf`:

```hcl
variable "application_name" {
  description = "Application identifier"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}
```

Create `modules/application/main.tf`:

```hcl
resource "terraform_data" "application" {
  input = {
    application_name = var.application_name
    environment      = var.environment
  }
}
```

Create `modules/application/outputs.tf`:

```hcl
output "application_name" {
  value = var.application_name
}

output "environment" {
  value = var.environment
}
```

Now configure the root module in `main.tf`:

```hcl
module "application" {
  source = "./modules/application"

  application_name = "orders-api"
  environment      = "development"
}

output "application_name" {
  value = module.application.application_name
}
```

This local exercise does not create cloud infrastructure. It teaches module boundaries, inputs, outputs, and composition using Terraform's built-in `terraform_data` resource.

Initialize and validate:

```bash
terraform init
terraform fmt -recursive
terraform validate
terraform plan
terraform apply
```

Review the plan before confirming the apply.

## 14. Use environment-specific values

You can reuse the same root configuration with different variable files.

For example, define variables in `variables.tf`:

```hcl
variable "application_name" {
  type = string
}

variable "environment" {
  type = string
}
```

Create `development.tfvars`:

```hcl
application_name = "orders-api"
environment      = "development"
```

Create `staging.tfvars`:

```hcl
application_name = "orders-api"
environment      = "staging"
```

Generate environment-specific plans:

```bash
terraform plan -var-file="development.tfvars"
terraform plan -var-file="staging.tfvars"
```

These commands use the same root configuration. They do not, by themselves, guarantee separate state.

If these environments represent separate infrastructure, ensure the backend and state arrangement correctly separates them. Different variable files with the same state can cause Terraform to propose changes to the same managed resources.

## 15. Review module changes carefully

Suppose a module's default database size changes.

That change might affect every environment using the module, including production.

Before merging a module change:

1. Identify every environment that uses the module.
2. Determine whether the changed default affects existing callers.
3. Generate plans for affected environments.
4. Inspect replacements and destructive actions.
5. Verify security and availability implications.
6. Review the change with the appropriate owners.
7. Roll out according to the team's deployment policy.

A reusable module increases consistency, but a poorly reviewed module change can also increase the blast radius of a mistake.

## 16. State commands and resource addresses

Terraform identifies resources through addresses.

For example:

```text
terraform_data.application
module.application.terraform_data.application
```

These addresses are different because one resource is declared in the root module and the other inside a child module.

A refactor that moves a resource into a module can change its Terraform address even when the intended real infrastructure remains the same.

Terraform supports state-management operations to handle certain refactors and address changes. For supported configurations, `moved` blocks can document resource address changes.

Conceptual example:

```hcl
moved {
  from = terraform_data.application
  to   = module.application.terraform_data.application
}
```

The destination must correspond to the resource's actual new address.

Review the plan after a refactor. The goal is to avoid accidentally destroying and recreating a resource merely because its configuration location changed.

## 17. Git practices for Terraform repositories

Infrastructure code deserves the same disciplined review as application code.

A repository might contain:

```text
infrastructure/
├── main.tf
├── variables.tf
├── outputs.tf
├── versions.tf
├── modules/
├── environments/
└── README.md
```

Use `.gitignore` to exclude local artifacts such as:

```gitignore
.terraform/
*.tfstate
*.tfstate.*
*.tfplan
crash.log
```

Review these exclusions against your team's actual workflow. Do not blindly ignore files that the repository intentionally tracks, and never commit state or plan files without a deliberate, approved reason.

Terraform lock files are different: the provider dependency lock file, commonly `.terraform.lock.hcl`, is generally committed so teams can reproduce provider selections.

A useful pull request should explain:

- What infrastructure is changing.
- Which environments are affected.
- Whether resources are created, updated, or replaced.
- Any cost or availability implications.
- Security changes.
- Recovery or rollback considerations.

---

# Layer 3 — Production Engineering & Interview Mastery

## 18. State migration: local to remote

**Scenario:** A prototype begins as a local Terraform project. The team now needs a shared workflow.

A safe migration requires more than adding a backend block.

### Recommended process

1. Stop other Terraform operations for the environment.
2. Back up the existing state securely.
3. Configure the intended remote backend.
4. Run `terraform init` and carefully review migration prompts.
5. Confirm the migration completed.
6. Verify expected resources with `terraform state list`.
7. Generate a fresh plan.
8. Investigate any unexpected create, delete, or replacement actions.
9. Resume the approved workflow only after verification.

If the plan proposes recreating resources that should already be managed, stop and investigate the state association before applying.

## 19. Production incident: Terraform wants to recreate existing resources

**Scenario:** After a module refactor, Terraform proposes replacing an application resource.

Possible causes include:

- A resource address changed.
- A provider attribute requires replacement.
- The resource was removed from state.
- The configuration now points at a different environment.
- A module input changed.
- Provider behavior or versions changed.

### Investigation

```bash
terraform state list
terraform plan
terraform providers
```

Inspect the proposed actions and relevant resource configuration. If necessary, review provider documentation for attributes that force replacement.

Do not automatically use `terraform state rm` to silence the difference. Removing a resource from state changes Terraform's tracking; it does not delete the actual object, and the next plan may attempt to create another one.

Use a supported state move or migration strategy when the issue is a legitimate address refactor.

## 20. Production incident: state lock cannot be acquired

**Scenario:** A pipeline fails because another operation appears to hold the state lock.

Possible explanations:

- Another apply is running.
- A previous operation did not release its lock.
- A pipeline was interrupted.
- The backend reports a stale lock.

### Response

1. Identify the backend and the reported lock.
2. Check the deployment pipeline and team activity.
3. Verify whether any Terraform operation is still active.
4. Follow the backend's documented stale-lock recovery procedure.
5. Use force-unlock only when you have verified that the lock belongs to an operation that is no longer active and you understand the consequences.
6. Re-run the plan against current state.

Never use force-unlock as a routine retry button.

## 21. Production incident: an engineer applied to the wrong environment

**Scenario:** A developer intended to update staging but selected production configuration.

Prevention controls include:

- Separate environment directories and state boundaries where appropriate.
- Explicit environment naming in plans and pipeline output.
- Protected production apply workflows.
- Least-privilege credentials.
- Required review and approval.
- Automated checks for the expected workspace or backend.
- Clear ownership and deployment procedures.

If the wrong change was applied:

1. Establish the actual change and impact.
2. Stop additional changes.
3. Determine whether a corrective change or rollback is safe.
4. Preserve the relevant plan, logs, and audit evidence.
5. Restore the intended configuration through a reviewed workflow.
6. Verify real infrastructure and application behavior.
7. Add a guardrail to prevent recurrence.

Do not assume that reverting a Git commit automatically reverses an infrastructure change.

## 22. Production incident: sensitive data appears in state

**Scenario:** A state artifact containing credentials is accidentally shared.

Treat this as a potential secret exposure.

1. Restrict further access to the artifact.
2. Determine which values were exposed and who could access them.
3. Rotate or revoke credentials where appropriate.
4. Review relevant access logs.
5. Secure state and plan storage.
6. Remove unintended copies where possible, while following retention and incident-response requirements.
7. Prevent recurrence through secret-management improvements and access controls.

Removing a value from the current configuration may not remove every historical copy from state versions, backups, plans, or logs.

## 23. Production architecture exercise: development, staging, and production

Design an infrastructure repository for a Spring Boot backend backed by PostgreSQL.

Your design should address:

- A reusable application module.
- A reusable database module.
- Shared networking patterns.
- Explicit environment-specific variables.
- Separate state arrangements appropriate to each environment.
- Least-privilege access.
- A reviewed plan before applying.
- Safe handling of credentials.
- A recovery strategy for state.
- A migration strategy for changes that require resource replacement.

### Questions to answer

1. Which values should be module inputs?
2. Which values should be outputs?
3. Which resources should be shared, and which should be isolated?
4. How will you prevent a staging plan from targeting production?
5. What happens if an engineer loses local state?
6. How will you review a change that replaces a database?
7. How will you detect manual changes to managed infrastructure?

There is no universal folder layout or backend choice. The design should match the platform, team's access model, and operational requirements.

## 24. SDE-1 interview questions and answers

**1. Why does Terraform need state?**

State maps Terraform resource addresses to real objects and records information needed to manage those objects across operations.

**2. What is remote state?**

State stored using a configured remote backend rather than only in a local state file.

**3. Does remote state always provide locking?**

No. Locking and concurrency behavior depend on the backend and its configuration.

**4. What is a Terraform module?**

A reusable collection of Terraform configuration with inputs and outputs.

**5. What is the difference between a root module and a child module?**

The root module is the configuration in the working directory used for a Terraform operation. A child module is called by another module.

**6. Are Terraform workspaces a complete production isolation mechanism?**

No. They separate state instances, but do not automatically separate credentials, accounts, permissions, or deployment approval policies.

**7. Why can moving a resource into a module cause a problem?**

Its Terraform address may change. Without a supported migration or move strategy, Terraform may propose creating or destroying resources unnecessarily.

**8. What is a `moved` block used for?**

It records a supported resource address migration so Terraform can recognize that a resource's address changed without treating it as an unrelated object.

**9. What should you do when a plan unexpectedly replaces a database?**

Stop, identify why replacement is required, evaluate data and availability risks, correct the configuration or migration strategy, and review a new plan before applying.

**10. Why should state not be edited manually?**

Direct edits can corrupt resource mappings and create inconsistencies. Use supported state-management operations and recovery procedures.

**11. What is state locking?**

A coordination mechanism that helps prevent conflicting operations against the same state when supported by the backend.

**12. Why is `terraform state rm` potentially dangerous?**

It removes a resource from Terraform's state tracking without deleting the real object. A subsequent plan may propose creating another resource or otherwise produce unexpected changes.

**13. What is infrastructure drift?**

A difference between real infrastructure and the configuration or state Terraform expects.

**14. Should development and production share the same state?**

Usually they should have separate state boundaries when they represent independently managed environments. The exact arrangement depends on architecture and access requirements.

**15. What is the purpose of `.terraform.lock.hcl`?**

It records provider dependency selections and checksums to support more reproducible provider installation. It is generally committed to version control.

**16. Why can a module default change be risky?**

Every caller that inherits the default may be affected, potentially changing resource sizes, security settings, or lifecycle behavior across environments.

**17. How should secrets be handled in Terraform?**

Use approved identity and secret-management mechanisms, restrict state and plan access, and avoid committing secret values. Sensitive marking alone does not prevent persistence.

**18. Does reverting a Terraform configuration commit reverse infrastructure changes?**

No. It changes source control. A new plan and apply may be required to reconcile infrastructure, and the correction must account for irreversible changes and data compatibility.

**19. How would you migrate local state to a remote backend?**

Stop concurrent operations, back up state, configure the backend, initialize and review migration, verify state contents, and inspect a fresh plan before resuming changes.

**20. How do you prevent applying to the wrong environment?**

Use clear environment boundaries, protected deployment workflows, least-privilege credentials, explicit plan review, and automated environment verification.

---

## 25. Hands-on mastery assessment

Use the local Terraform exercise from Chunk 1 and extend it.

- [ ] Create an `application` child module.
- [ ] Define module inputs and outputs.
- [ ] Call the module from a root configuration.
- [ ] Create separate development and staging variable files.
- [ ] Explain why separate variable files do not automatically imply separate state.
- [ ] Inspect state with `terraform state list`.
- [ ] Explain why state and plan files must be protected.
- [ ] Add a resource address migration using a suitable `moved` block in a controlled example.
- [ ] Run `terraform fmt -recursive`.
- [ ] Run `terraform validate`.
- [ ] Generate and review a plan.
- [ ] Describe a safe local-to-remote state migration.
- [ ] Explain how to investigate an unexpected database replacement.
- [ ] Describe how to recover from a stale lock safely.

### Mastery standard

You should be able to design a reusable module interface, explain the difference between state and real infrastructure, separate environments safely, diagnose state-related failures, and defend an infrastructure change during a code review.

---

# Terraform Chunk 2 completion protocol

Save this chapter as:

`content/terraform/02-terraform-state-modules-environments-safe-workflows.md`

Terraform has three planned content chunks. Do not generate a PDF yet.

The final Terraform handbook must combine all three complete chapters into one PDF:

`docs/terraform/BEH_TERRAFORM_COMPLETE_HANDBOOK.pdf`

After all three chapters are saved and verified:

1. Build the complete Terraform handbook PDF.
2. Verify chapter order, code blocks, tables, and page rendering.
3. Update the README with verified progress.
4. Commit the completed Terraform sources and verified PDF with the exact commit message:

`Terraform done`

**Do not create a PDF for this chapter alone.** The repository's final deliverable remains 13 individual tool handbooks and one complete master handbook.
