# Terraform — Chunk 1 of 3: Infrastructure as Code, Core Concepts & Mental Models

## Backend Engineering Tools & Infrastructure Handbook

**Source file:** `content/terraform/01-terraform-infrastructure-as-code-core-mental-models.md`

**Learning objective:** Understand how Terraform manages infrastructure declaratively, how configuration becomes real infrastructure, and how to use plans and state safely in backend engineering workflows.

---

# Layer 1 — Fundamentals & Mental Models

## 1. What is Terraform?

Terraform is an Infrastructure as Code (IaC) tool. It allows engineers to describe infrastructure using configuration files and then create, update, or destroy resources to match that configuration.

Instead of manually creating infrastructure through a cloud console, you define the desired configuration in files.

For example, a backend application might need:

- A virtual machine or container platform.
- A network and firewall rules.
- A managed PostgreSQL database.
- An object storage bucket.
- Identity and access permissions.
- Monitoring and supporting resources.

Terraform lets you express these resources in configuration, review proposed changes, and apply them through a repeatable workflow.

### The core mental model

**Configuration → Plan → Apply → Real infrastructure**

Terraform compares the configuration with its understanding of the current infrastructure and calculates the changes needed to reconcile them.

```text
Terraform configuration
          |
          v
   Initialize providers
          |
          v
   Read configuration
          |
          v
  Compare with state
  and remote objects
          |
          v
       Plan
          |
          v
 Review proposed changes
          |
          v
        Apply
          |
          v
 Infrastructure changes
          |
          v
 Update Terraform state
```

The plan is a proposed set of actions, not a guarantee that every action will succeed. Permissions, quotas, concurrent changes, API failures, and provider behavior can still cause an apply to fail.

## 2. Why Infrastructure as Code matters

Manual infrastructure creation creates operational risks:

- Environments drift apart.
- Engineers forget configuration details.
- Changes are difficult to review.
- Rebuilding an environment becomes slow.
- Resource ownership becomes unclear.
- Accidental deletion becomes harder to prevent.
- Auditability suffers.

Infrastructure as Code improves repeatability, reviewability, and recovery.

Consider two environments:

- Development uses one application instance and a small database.
- Production uses multiple application instances and a highly available database.

Both can use the same underlying module design while differing through explicit configuration.

Terraform does not automatically make environments identical or safe. The quality of the configuration, module design, access controls, and review process determines how reliable the workflow becomes.

## 3. Terraform versus related tools

| Tool | Primary responsibility |
|---|---|
| Terraform | Provision and manage infrastructure resources |
| Docker | Package applications and their runtime dependencies |
| Kubernetes | Schedule and operate containerized workloads |
| Ansible | Configure systems and execute automation tasks |
| Packer | Build machine images |
| Maven | Build Java applications and manage dependencies |
| Git | Track configuration and application source changes |

These tools can complement one another.

For example:

1. Maven builds a Spring Boot application.
2. Docker packages it into an image.
3. Terraform provisions the infrastructure.
4. Kubernetes runs the application.
5. Prometheus and Grafana support monitoring.
6. Git tracks changes across the repository.

Terraform can provision a Kubernetes cluster, but Kubernetes is responsible for managing workloads inside that cluster.

## 4. Declarative versus imperative thinking

An imperative instruction describes the steps to perform.

```text
Create a server.
Install dependencies.
Configure the network.
Start the service.
```

A declarative configuration describes the intended result.

```hcl
resource "example_server" "api" {
  name = "backend-api"
  size = "small"
}
```

This is illustrative HCL, not a working provider-specific resource.

Terraform evaluates the configuration, constructs a dependency graph, and determines the actions needed to approach the desired state.

Declarative configuration does not mean Terraform can infer every operational requirement. Engineers must still define networking, security, dependencies, sizing, and lifecycle behavior correctly.

## 5. Providers and resources

A **provider** is a plugin that lets Terraform interact with an external API or platform.

Examples include providers for cloud platforms, Kubernetes, DNS services, and monitoring systems.

A **resource** represents an object Terraform can create, read, update, or delete through a provider.

Conceptually:

```hcl
provider "example" {
  region = "example-region"
}

resource "example_network" "main" {
  name = "backend-network"
}
```

The provider and resource types above are placeholders. Real configuration must use resource types supported by the selected provider.

Terraform uses provider schemas to validate configuration and communicate with the relevant platform APIs.

## 6. HCL: Terraform's configuration language

Terraform configurations are commonly written in HashiCorp Configuration Language (HCL).

Basic concepts include:

- **Blocks:** Define resources, providers, variables, outputs, and other configuration objects.
- **Arguments:** Assign values to configuration properties.
- **Expressions:** Calculate or reference values.
- **Variables:** Supply configurable inputs.
- **Outputs:** Expose selected values from a configuration.
- **Data sources:** Read information about existing objects.
- **Modules:** Package reusable Terraform configurations.

Example:

```hcl
variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "development"
}

output "environment_name" {
  value = var.environment
}
```

The variable `environment` supplies an input value. The output exposes a value from the configuration.

Outputs can reveal sensitive information if configured carelessly. Marking an output as sensitive affects display behavior, but it does not automatically encrypt every stored copy of that value.

## 7. Resources, data sources, and modules

### Resources

Resources describe infrastructure Terraform manages.

Conceptual example:

```hcl
resource "example_bucket" "logs" {
  name = "backend-logs"
}
```

### Data sources

Data sources read information about existing infrastructure or other external objects.

Conceptual example:

```hcl
data "example_network" "existing" {
  name = "shared-network"
}
```

A data source does not ordinarily create the object it reads. It retrieves information for use elsewhere in the configuration.

### Modules

A module is a reusable collection of Terraform configuration.

For example, a reusable backend module might define:

- Application compute resources.
- Network attachments.
- Health-check configuration.
- Monitoring integration.
- Security settings.

A root module composes resources and child modules into a deployable configuration.

Modules improve consistency when designed well, but abstraction can also hide important details. A module should expose the configuration consumers genuinely need without making operational behavior mysterious.

## 8. Terraform state: the most important concept

Terraform state maps Terraform-managed resource addresses to the real-world objects Terraform manages.

State helps Terraform understand which resource in the configuration corresponds to which remote object.

For example:

```text
Terraform address:
example_server.api

Remote object:
server-83921
```

The address and identifier above are illustrative.

State supports:

- Tracking managed resources.
- Detecting changes.
- Determining which objects correspond to configuration.
- Calculating dependency-aware changes.
- Recording attributes returned by providers.

### State is not simply a backup

State is not equivalent to a complete infrastructure backup. It may not contain all information necessary to reconstruct every external system or its data.

It can also contain sensitive values. Treat state files as sensitive operational data.

### Local versus remote state

- **Local state:** Stored on the engineer's machine or in the working directory.
- **Remote state:** Stored in a supported remote backend.

For individual experiments, local state can be convenient. For collaborative environments, remote state generally provides a stronger foundation for shared workflows.

A production remote-state design should consider access control, encryption, locking or concurrency controls where supported, versioning or recovery options, and backup procedures.

## 9. The dependency graph

Terraform builds a dependency graph from references and explicit dependency declarations.

Suppose an application server requires a network:

```text
Network
   |
   v
Application server
   |
   v
Application configuration
```

Terraform can determine that the network must be created before resources that depend on it.

Referencing another resource's attributes normally creates an implicit dependency.

`depends_on` can declare an explicit dependency when the relationship is real but is not otherwise expressed through configuration references.

Avoid adding unnecessary dependencies. Overly restrictive dependency graphs can reduce parallelism and make configuration harder to maintain.

## 10. Desired state, drift, and reconciliation

**Drift** occurs when real infrastructure no longer matches Terraform's expected configuration and state.

Examples include:

- An engineer manually changes a firewall rule.
- A resource is deleted through a cloud console.
- An external system modifies a managed object.
- Infrastructure configuration changes without a corresponding Terraform update.

A Terraform plan can help identify proposed corrective actions, although the exact result depends on provider refresh behavior, state, configuration, and the resource's lifecycle semantics.

Do not automatically apply every plan. First determine whether the difference is intentional, accidental, or caused by an incomplete understanding of the infrastructure.

---

# Layer 2 — Practical Engineering & Workflows

## 11. Install and initialize Terraform

Install Terraform using the official distribution or an approved package manager for your operating system.

Verify the installation:

```bash
terraform version
```

Create a project directory:

```bash
mkdir backend-infrastructure
cd backend-infrastructure
```

Create `main.tf` and add a small local-only configuration.

```hcl
terraform {
  required_version = ">= 1.5.0"
}

resource "terraform_data" "example" {
  input = {
    application = "backend-api"
    environment = "development"
  }
}

output "example_input" {
  value = terraform_data.example.output
}
```

`terraform_data` is a built-in resource available in modern Terraform versions. It lets you practice Terraform's lifecycle without provisioning a paid cloud resource.

The example's version constraint is a minimum-version constraint, not a complete dependency-pinning strategy for every team.

Initialize:

```bash
terraform init
```

Initialization prepares the working directory, installs required providers where applicable, and initializes the configured backend.

For this local-only example, there is no external cloud provider to configure.

## 12. Format and validate configuration

Format the configuration:

```bash
terraform fmt
```

Check configuration syntax and internal consistency:

```bash
terraform validate
```

Formatting makes files consistent. Validation catches configuration problems that Terraform can identify without performing the full infrastructure change.

Neither command proves that a production deployment will succeed.

For example, a syntactically valid cloud configuration may still fail because:

- The identity lacks permissions.
- A region does not support the requested resource.
- A quota has been reached.
- A network range overlaps with an existing network.
- A provider API is unavailable.

## 13. Plan before applying

Generate a plan:

```bash
terraform plan
```

Terraform shows the proposed actions, such as creating, updating, or deleting resources.

Common plan symbols include:

- `+` — create.
- `~` — update in place.
- `-` — destroy.
- `-/+` — destroy and recreate, in configurations where replacement is required.

Always inspect the plan for destructive changes.

For a saved plan:

```bash
terraform plan -out=tfplan
terraform show tfplan
```

Apply the saved plan:

```bash
terraform apply tfplan
```

Saved plans help separate review from execution. However, they are operational artifacts that may contain sensitive data. Protect them, avoid committing them, and regenerate them if relevant infrastructure or configuration assumptions have changed.

For a disposable local exercise, a direct `terraform apply` can be convenient after reviewing the proposed changes.

## 14. Apply and inspect the result

Apply the local example:

```bash
terraform apply
```

Review the proposed changes and confirm when prompted.

Then inspect the state:

```bash
terraform state list
terraform state show terraform_data.example
```

Inspect outputs:

```bash
terraform output
```

The resource should appear in the state, and the output should expose the configured example data.

Destroy the disposable exercise when finished:

```bash
terraform destroy
```

Review the destruction plan and confirm it.

Even local exercises deserve careful cleanup habits. In cloud configurations, `destroy` can remove important resources and may cause irreversible data loss.

## 15. Variables and environment-specific configuration

As a configuration grows, hard-coded values become difficult to manage.

Create `variables.tf`:

```hcl
variable "application_name" {
  description = "Name of the application"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string

  validation {
    condition = contains(
      ["development", "staging", "production"],
      var.environment
    )
    error_message = "Choose development, staging, or production."
  }
}
```

Use the variables in `main.tf`:

```hcl
resource "terraform_data" "application" {
  input = {
    name        = var.application_name
    environment = var.environment
  }
}
```

Provide values through a `.tfvars` file:

```hcl
application_name = "orders-api"
environment      = "development"
```

For example, save the values in `development.tfvars` and run:

```bash
terraform plan -var-file="development.tfvars"
```

Use the same variable interface across environments where practical, while keeping environment-specific values explicit.

Do not store credentials or production secrets in ordinary `.tfvars` files committed to Git.

## 16. Outputs and data flow

Outputs expose selected values from a module.

```hcl
output "application_name" {
  description = "Configured application name"
  value       = var.application_name
}
```

Outputs are useful when:

- A root module needs to expose a resource identifier.
- A child module returns information to its caller.
- A deployment workflow needs a value produced by Terraform.

Use outputs deliberately. Avoid exposing unnecessary internal details or sensitive values.

A downstream system should not blindly treat an output as a secret-management mechanism.

## 17. Terraform workflow in Git

A typical repository might look like this:

```text
infrastructure/
├── main.tf
├── variables.tf
├── outputs.tf
├── versions.tf
├── development.tfvars
├── staging.tfvars
└── README.md
```

A practical review workflow:

1. Create a branch for the infrastructure change.
2. Update Terraform configuration.
3. Run `terraform fmt -check`.
4. Run `terraform validate`.
5. Generate and inspect a plan.
6. Open a pull request with the purpose and impact of the change.
7. Run an approved plan workflow in CI.
8. Review the resulting plan before applying.
9. Apply through the team's authorized deployment process.
10. Verify the real infrastructure after deployment.

The plan is an important review artifact, but the final result should also be validated against the actual environment.

## 18. Common Terraform commands

| Command | Purpose |
|---|---|
| `terraform init` | Initialize the working directory and backend |
| `terraform fmt` | Format Terraform files |
| `terraform validate` | Validate configuration |
| `terraform plan` | Preview proposed changes |
| `terraform apply` | Apply infrastructure changes |
| `terraform destroy` | Destroy managed resources covered by the configuration |
| `terraform output` | Display root-module outputs |
| `terraform state list` | List resource addresses in state |
| `terraform state show` | Inspect one state resource |
| `terraform show` | Display a plan or state representation |
| `terraform providers` | Show provider requirements |
| `terraform graph` | Produce a dependency graph representation |

Some commands require initialized configuration, provider access, state, or other context. Their output is not a substitute for understanding the current environment.

---

# Layer 3 — Production Engineering & Interview Mastery

## 19. State safety and collaboration

When multiple engineers work on the same infrastructure, state management becomes a shared operational concern.

### What can go wrong?

Two engineers may attempt conflicting changes at the same time. One engineer's plan may become stale after another engineer applies a change. A local state file may diverge from the real infrastructure. A state file may be lost or exposed.

### Safer practices

- Use an appropriate remote backend for shared environments.
- Use supported state locking or concurrency controls.
- Restrict state access to authorized identities.
- Protect state backups and versions.
- Avoid manual state-file editing.
- Review plans before applying.
- Avoid concurrent applies to the same state unless the workflow explicitly supports them.
- Keep infrastructure changes auditable.

Remote state alone does not guarantee safe collaboration. Access controls, locking behavior, backup procedures, and release coordination all matter.

## 20. Drift investigation

**Scenario:** Someone manually modifies a network rule outside Terraform.

A disciplined response:

1. Confirm the affected environment and resource.
2. Inspect the current infrastructure through the appropriate provider tooling.
3. Run a fresh Terraform plan.
4. Determine whether the manual change was intentional.
5. If the configuration is authoritative, update it to represent the intended result.
6. If the manual change was unauthorized or accidental, prepare a reviewed corrective plan.
7. Apply only after verifying the impact.
8. Investigate why the out-of-band modification occurred.

Avoid immediately running `terraform apply` without reviewing the proposed changes. The plan may contain unrelated modifications or destructive replacements.

## 21. Resource replacement and lifecycle risk

Some resource changes can be performed in place. Others require destroying and recreating the resource.

A replacement can cause:

- A new resource identifier.
- Temporary downtime.
- Loss of data for disposable resources.
- Dependency changes.
- A temporary increase in infrastructure cost.
- Failed deployments if dependent systems expect the old identifier.

Before applying a replacement, ask:

1. Is the resource stateful?
2. Will data be preserved?
3. Can the service tolerate interruption?
4. Do dependent resources need updates?
5. Is a staged migration possible?
6. Is there a tested recovery path?

Terraform lifecycle configuration can influence replacement behavior, but lifecycle flags are not substitutes for an explicit migration plan.

## 22. Importing existing infrastructure

An organization may already have manually created infrastructure that should become Terraform-managed.

The general process is:

1. Write configuration that describes the existing object.
2. Identify the correct Terraform resource address.
3. Use the provider's supported import mechanism.
4. Inspect the resulting state.
5. Generate a plan.
6. Refine the configuration until the plan reflects the intended state.

Modern Terraform supports configuration-driven imports, and individual providers may have specific import requirements.

Importing is not the same as automatically generating a perfect configuration. The configuration must still describe the intended infrastructure accurately.

Never import a resource into a configuration without checking ownership and the potential for duplicate management.

## 23. Secrets and sensitive data

Terraform configurations and state may contain credentials, tokens, connection strings, or other sensitive attributes.

Safer handling includes:

- Obtain credentials through an approved identity mechanism.
- Prefer short-lived credentials where supported.
- Keep secret values out of source control.
- Restrict access to state and plan artifacts.
- Use the sensitive-value mechanisms supported by Terraform.
- Integrate with an approved secret manager when appropriate.
- Rotate credentials when exposure is suspected.

A value marked `sensitive` is primarily subject to redaction in selected output contexts. This does not automatically prevent the value from being stored in state or plan files.

Do not assume that hiding a value in terminal output makes it safe to persist.

## 24. CI/CD and controlled infrastructure changes

A production infrastructure pipeline should separate validation, review, and execution.

```text
Pull request
     |
     v
Format and validate
     |
     v
Generate plan
     |
     v
Review changes
     |
     v
Authorized approval
     |
     v
Apply approved changes
     |
     v
Verify infrastructure
```

The exact pipeline depends on the organization's deployment platform and security requirements.

Good controls include:

- Separate identities for plan and apply where appropriate.
- Least-privilege permissions.
- Protected production environments.
- Auditable approvals.
- Safe handling of saved plans.
- Drift monitoring.
- Explicit destruction safeguards.
- Recovery procedures for failed applies.

A successful Terraform apply is not the end of the workflow. Confirm that the application can actually use the provisioned infrastructure.

## 25. Production incident simulation: a plan wants to destroy a database

**Scenario:** A routine pull request produces a plan showing database replacement.

### Response

1. Stop the apply.
2. Identify the exact resource and proposed replacement reason.
3. Inspect configuration changes, provider behavior, and immutable attributes.
4. Determine whether the resource contains persistent or business-critical data.
5. Check whether a replacement is intentional.
6. If unexpected, correct the configuration or revise the migration strategy.
7. Regenerate the plan.
8. Obtain the appropriate review before applying.

Do not assume that Terraform understands the business impact of a resource replacement. It understands the provider's resource model, not the importance of the database to your customers.

## 26. Production incident simulation: state lock or concurrent apply

**Scenario:** An apply fails because state is locked, or the team suspects two workflows are changing the same environment.

### Response

1. Identify the backend and locking mechanism.
2. Find the workflow or engineer holding the lock.
3. Confirm whether an apply is still running.
4. Review recent pipeline and backend logs.
5. Allow the active operation to finish if it is healthy.
6. Remove a stale lock only after confirming it is genuinely stale and following the backend's supported procedure.
7. Re-run the plan against current state.

Never force-unlock state merely to make an error disappear. If another apply is active, removing the lock can permit conflicting operations and corrupt the team's understanding of infrastructure state.

## 27. SDE-1 interview questions and answers

**1. What is Infrastructure as Code?**

It is the practice of defining and managing infrastructure through version-controlled configuration rather than relying solely on manual actions.

**2. What does Terraform do?**

It evaluates infrastructure configuration, plans changes, and uses providers to manage supported resources.

**3. What is a Terraform provider?**

A plugin that lets Terraform interact with an external platform or API.

**4. What is a resource?**

A Terraform-managed object such as a server, network, database, or supported platform object.

**5. What is a data source?**

A configuration object used to read information about existing infrastructure or other external data.

**6. What is Terraform state?**

A record that maps Terraform resource addresses to real-world objects and stores attributes needed for Terraform's management workflow.

**7. Why is state important?**

It helps Terraform identify managed resources and calculate changes. Losing or mishandling state can make infrastructure management unsafe.

**8. What is the difference between `plan` and `apply`?**

`plan` previews proposed actions. `apply` executes the selected changes.

**9. What is infrastructure drift?**

A difference between the actual infrastructure and the intended or tracked configuration.

**10. What is a Terraform module?**

A reusable collection of Terraform configuration that packages infrastructure logic behind an interface.

**11. Why use variables?**

Variables make configuration reusable and allow values to be supplied for different environments without duplicating entire configurations.

**12. Why use remote state?**

It supports a shared state workflow and can provide centralized access control, recovery, and locking or concurrency controls when supported.

**13. Why should state files be treated as sensitive?**

They may contain sensitive infrastructure attributes or secret values, depending on the resources and configuration.

**14. Does `terraform validate` prove an infrastructure deployment will succeed?**

No. It validates configuration properties that Terraform can check locally. Permissions, quotas, API failures, and environment-specific issues can still prevent deployment.

**15. What is a dangerous Terraform plan?**

A plan containing unexpected destructive actions, replacements, security changes, or modifications with unacceptable operational impact.

**16. What happens when a resource requires replacement?**

Terraform may need to destroy and recreate it. This can change identifiers, interrupt service, or risk data loss.

**17. What does `terraform init` do?**

It initializes the working directory, installs required providers, and prepares the configured backend.

**18. How do you safely adopt manually created infrastructure?**

Write matching configuration, import the object through supported mechanisms, inspect state, and review plans until Terraform's proposed actions match the intended result.

**19. Is marking a variable sensitive enough to secure a secret?**

No. It can redact selected output, but state and plan artifacts may still contain the value. Access control and appropriate secret management are also required.

**20. How would you respond to a plan that unexpectedly destroys a production database?**

Stop, investigate the replacement reason and configuration, assess data and availability risk, correct the design, regenerate the plan, and require an appropriate review before applying.

---

## 28. Hands-on mastery assessment

Complete this exercise using the local `terraform_data` resource before provisioning any cloud infrastructure.

- [ ] Create a Terraform project.
- [ ] Initialize the working directory.
- [ ] Define typed input variables.
- [ ] Add validation to at least one variable.
- [ ] Create a resource that uses the variables.
- [ ] Add an output.
- [ ] Run formatting and validation.
- [ ] Generate and review a plan.
- [ ] Apply the plan.
- [ ] Inspect the resulting state.
- [ ] Change a variable and review the next plan.
- [ ] Destroy the disposable resource after reviewing the plan.
- [ ] Explain why remote state and state access controls matter.
- [ ] Explain how you would respond to an unexpected destructive plan.

### Mastery standard

You should be able to explain Terraform's lifecycle without memorizing commands, identify state as a critical operational asset, recognize destructive changes, and describe how to move from local practice to a reviewed production workflow.

---

# Terraform Chunk 1 completion protocol

Save this chapter as:

`content/terraform/01-terraform-infrastructure-as-code-core-mental-models.md`

Terraform has **three planned content chunks**. Do not generate a PDF yet.

The completed Terraform handbook must combine all three chapters into exactly one final PDF:

`docs/terraform/BEH_TERRAFORM_COMPLETE_HANDBOOK.pdf`

After all three Terraform chapters are saved and verified:

1. Generate the complete Terraform handbook PDF.
2. Verify content order, code blocks, tables, and page rendering.
3. Update the README with verified progress.
4. Commit the completed Terraform sources and verified PDF using the exact commit message:

`Terraform done`

Do not create a PDF for this chunk alone. The full repository still requires all 13 individual tool handbooks and one master handbook.
