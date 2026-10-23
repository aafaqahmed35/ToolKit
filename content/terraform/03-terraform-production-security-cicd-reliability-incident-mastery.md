# Terraform — Chunk 3 of 3: Production Infrastructure, Security, CI/CD, Reliability & Incident Mastery

## Backend Engineering Tools & Infrastructure Handbook

**Source file:** `content/terraform/03-terraform-production-security-cicd-reliability-incident-mastery.md`

**Learning objective:** Learn to operate Terraform as a production engineering tool: secure infrastructure, manage changes through CI/CD, reduce deployment risk, control costs, and investigate incidents involving failed or dangerous infrastructure changes.

---

# Layer 1 — Fundamentals & Mental Models

## 1. Terraform in production: from configuration to controlled change

In development, Terraform helps you create infrastructure. In production, it also becomes part of your organization's change-management system.

A production infrastructure change should answer five questions:

1. What is changing?
2. Why is it changing?
3. What could break?
4. Who is authorized to approve and apply it?
5. How will we verify and recover from the change?

The production workflow is therefore more than `terraform apply`.

```text
Engineer changes configuration
            |
            v
     Pull request created
            |
            v
 Formatting and validation
            |
            v
      Plan generated
            |
            v
   Impact and risk review
            |
            v
    Authorized approval
            |
            v
     Approved plan applied
            |
            v
 Infrastructure verification
            |
            v
 Monitoring and audit trail
```

This workflow reduces the chance of an engineer accidentally deleting a database, exposing a network service, or changing the wrong environment.

Terraform supplies infrastructure-management mechanisms. Your team must provide appropriate access controls, review policies, operational procedures, and monitoring.

## 2. Understand the blast radius

The **blast radius** is the scope of damage or disruption a change can cause.

Examples:

- Changing one development resource has a relatively limited scope.
- Changing a shared network can affect multiple services.
- Changing a production database can affect business-critical data.
- Changing a widely reused module may affect many environments.

A good infrastructure design limits unnecessary blast radius through:

- Separate environment boundaries.
- Narrowly scoped identities and permissions.
- Reusable modules with controlled interfaces.
- Small, reviewable changes.
- Explicit ownership of resources.
- Carefully planned database and networking migrations.
- Tested recovery procedures.

A Terraform plan can reveal which resources may change, but it does not automatically understand every business dependency. Review the plan in the context of the actual architecture.

## 3. Pin provider dependencies and manage upgrades

Terraform configurations depend on providers, and provider versions can influence validation, planning, and resource behavior.

A typical provider requirement looks like this:

```hcl
terraform {
  required_providers {
    example = {
      source  = "example-org/example"
      version = "~> 2.4"
    }
  }
}
```

This is an illustrative provider declaration; the source and version constraint must match a real provider.

The version constraint defines which versions Terraform is allowed to select. The dependency lock file, `.terraform.lock.hcl`, records the selected provider versions and checksums for reproducibility.

### A safer upgrade workflow

1. Identify the provider upgrade and its purpose.
2. Review release notes and breaking changes.
3. Update the version constraint deliberately.
4. Run `terraform init -upgrade` in a controlled branch.
5. Review changes to `.terraform.lock.hcl`.
6. Run formatting and validation.
7. Generate plans for affected environments.
8. Test in development or staging.
9. Apply through the approved release workflow.

Avoid upgrading all providers during an unrelated production change unless there is a deliberate reason to combine those changes.

Reproducible provider selection makes reviews more meaningful because reviewers can understand which provider implementation is being used.

## 4. Production infrastructure security

Terraform can create security controls, but the configuration must express the intended policy correctly.

Consider the security of a backend application that needs to connect to PostgreSQL.

A reasonable architecture might be:

```text
Internet
   |
   v
Public entry point
   |
   v
Backend application
   |
   v
Private database network
   |
   v
PostgreSQL
```

The exact implementation depends on the hosting platform. The important principle is that the database should not be exposed publicly without a justified requirement and suitable controls.

Security responsibilities include:

- Network segmentation.
- Least-privilege identities.
- Encryption in transit and at rest where appropriate.
- Secret management.
- Auditability.
- Resource ownership.
- Secure defaults.
- Controlled infrastructure changes.

Do not confuse creating a network resource with establishing a secure network. Firewall rules, routes, identities, service exposure, and platform-specific policies must also be considered.

## 5. Secrets and identity in production workflows

Infrastructure deployments need credentials or identities to interact with their target platforms.

Safer approaches include:

- Short-lived credentials.
- Federated workload identity where supported.
- Platform-native managed identities.
- Least-privilege permissions.
- Dedicated deployment identities.
- Centralized secret-management systems.

Avoid hard-coding access keys in Terraform files or committing credentials to Git.

Example of a pattern to avoid:

```hcl
provider "example" {
  access_key = "hard-coded-secret"
}
```

The provider and attribute are illustrative. The problem is the hard-coded credential, not the specific provider syntax.

Prefer an approved identity mechanism supported by the selected provider. Environment variables can be useful for some workflows, but long-lived environment-variable credentials still need secure sourcing, restricted access, and rotation.

Marking a value as `sensitive` may redact it from certain displays. It does not guarantee that the value will never appear in state, saved plans, logs, or other artifacts.

## 6. Policy as Code and preventive guardrails

Policy as Code means expressing infrastructure rules in machine-checkable form.

Examples of policies:

- Production resources must include ownership tags.
- Public access to databases is prohibited unless explicitly approved.
- Storage resources must meet encryption requirements.
- Resources must use approved regions.
- Required monitoring settings must be present.
- Destructive changes require additional review.

Policy enforcement can be implemented using platform-native controls, CI checks, policy frameworks, or custom validation.

The purpose is to catch unacceptable changes before they reach production.

### Prevention versus detection

| Control | Example |
|---|---|
| Preventive | Reject a plan that violates an approved security policy |
| Detective | Alert when an unexpected public endpoint appears |
| Corrective | Apply a reviewed configuration change to restore the intended rule |

All three can be useful. Prevention reduces risk, detection identifies failures that escape prevention, and correction restores the intended condition.

## 7. Infrastructure reliability and availability

Terraform can provision resources that support reliability, such as:

- Multiple application instances.
- Load balancers.
- Health checks.
- Private networking.
- Database replicas.
- Backups and recovery infrastructure.
- Monitoring systems.

But provisioning a resource does not prove that the resulting system meets its reliability objectives.

A production design must consider:

- Failure domains.
- Capacity and scaling.
- Dependency limits.
- Data durability.
- Recovery time.
- Recovery point.
- Operational access.
- Monitoring and alerting.
- Application-level behavior.

For example, creating two application servers does not provide meaningful high availability if both depend on a single database with no suitable recovery plan.

Terraform manages infrastructure configuration. Application resilience and operational procedures remain essential.

## 8. Cost management and resource lifecycle

Infrastructure cost is a production concern.

Common sources of unnecessary cost include:

- Oversized compute resources.
- Forgotten development environments.
- Unused disks or snapshots.
- Excessive logging retention.
- Unnecessary public endpoints.
- Overprovisioned databases.
- Duplicate resources caused by poor state management.

Cost controls may include:

- Resource tagging.
- Budget alerts.
- Environment-specific sizing.
- Scheduled cleanup for disposable environments.
- Reviewing planned resource creation.
- Periodic utilization reviews.
- Clear ownership and expiration policies for temporary resources.

Terraform can make resource ownership and intended configuration more visible, but it cannot independently determine the optimal size or cost of every resource.

**Important:** `terraform destroy` is not a general-purpose cost optimization strategy. It can destroy data and business-critical infrastructure. Cleanup should be deliberate and scoped to disposable resources.

---

# Layer 2 — Practical Engineering & Workflows

## 9. Build a production-minded Terraform repository

A repository might use the following structure:

```text
infrastructure/
├── versions.tf
├── providers.tf
├── main.tf
├── variables.tf
├── outputs.tf
├── modules/
│   ├── network/
│   ├── application/
│   └── database/
├── environments/
│   ├── development/
│   ├── staging/
│   └── production/
├── policies/
└── README.md
```

This is one possible structure, not a universal requirement.

Keep environment boundaries, provider configuration, modules, and operational documentation understandable. Avoid introducing abstractions that make the effective infrastructure difficult to trace.

For each environment, document:

- The infrastructure it owns.
- The backend and state boundary.
- Required identities and permissions.
- How plans are generated and reviewed.
- How changes are applied.
- How failures are recovered.
- Who owns the environment.

## 10. Validate configuration before review

A basic local validation workflow:

```bash
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
```

`terraform init -backend=false` initializes the configuration without initializing its configured backend. It can be useful for validation workflows, but provider installation and initialization requirements still apply.

For a working environment with an initialized backend, generate the plan using the team's normal backend configuration.

```bash
terraform plan -out=tfplan
terraform show tfplan
```

Review the plan before applying it.

Remember:

- Formatting checks formatting.
- Validation checks configuration consistency.
- Planning previews proposed changes.
- Applying executes changes.
- Post-deployment verification checks the real outcome.

No single step replaces all the others.

## 11. A practical CI/CD pipeline

A production pipeline can be organized into distinct stages.

### Stage A — Pull request validation

Run:

```bash
terraform fmt -check -recursive
terraform validate
```

Additional checks may include static analysis, security scanning, policy checks, and module tests.

### Stage B — Generate a plan

Initialize the correct backend and generate a plan for the intended environment.

```bash
terraform plan -out=tfplan
terraform show tfplan
```

The pipeline must use the correct environment, identity, provider dependencies, and state.

### Stage C — Review

Review:

- Resources to be created.
- Resources to be updated.
- Resources to be replaced or destroyed.
- IAM and network changes.
- Cost implications.
- Database and storage implications.
- Provider upgrades.
- State and backend changes.

### Stage D — Apply

Use an authorized workflow to apply the approved changes.

```bash
terraform apply tfplan
```

Saved plan files can contain sensitive information and should be protected. A saved plan should be applied only within the intended environment and workflow. If relevant configuration, infrastructure, or assumptions have changed, regenerate the plan rather than relying on a stale artifact.

### Stage E — Verify

Verify the resulting infrastructure using provider tooling, Terraform outputs where appropriate, application health checks, logs, and monitoring.

A successful apply confirms that Terraform completed its operation; it does not guarantee that the entire application works correctly.

## 12. Handle failed applies safely

A Terraform apply may fail partway through a multi-resource change.

For example, Terraform may create a network and application resource but fail while creating a database because of a quota or permission issue.

Do not assume that a failed apply means nothing changed.

Use this workflow:

1. Read the error and identify the failed operation.
2. Check the real infrastructure through the provider or platform.
3. Inspect Terraform state.
4. Determine which resources were successfully created or modified.
5. Correct the underlying cause.
6. Generate a fresh plan.
7. Review the new plan before retrying.

Useful commands include:

```bash
terraform state list
terraform plan
terraform show
```

The state and infrastructure may already reflect some completed operations. A fresh plan is essential for understanding what Terraform now proposes to do.

## 13. Resource lifecycle and safe deletion

Before deleting an infrastructure resource, determine whether it contains persistent data or is depended on by other systems.

Questions to ask:

- Is the resource stateful?
- Does it contain business-critical data?
- Are backups available and restorable?
- Will dependent resources fail?
- Is there a maintenance window?
- Is the deletion reversible?
- Is a migration safer than replacement?

Terraform lifecycle settings can alter how Terraform handles certain changes. For example, `prevent_destroy` can protect against some accidental destroy plans while the lifecycle rule remains applicable.

Illustrative configuration:

```hcl
resource "example_database" "orders" {
  # Provider-specific database configuration.

  lifecycle {
    prevent_destroy = true
  }
}
```

The resource type is illustrative and is not a deployable database configuration.

`prevent_destroy` is a guardrail, not a backup or recovery strategy. It does not prevent every external deletion path, and removing the resource configuration can change the situation. Review lifecycle behavior for the actual provider and resource.

## 14. Drift detection workflow

Suppose an engineer manually changes a security rule outside Terraform.

Start with:

```bash
terraform plan
```

Then:

1. Identify the exact resource and attribute.
2. Confirm the actual platform configuration.
3. Determine why the manual change occurred.
4. Decide whether the intended configuration should change or the external modification should be reversed.
5. Generate a new plan after resolving the discrepancy.
6. Apply through the approved workflow.
7. Consider automated drift detection for important environments.

A plan is useful for identifying differences, but not every external change is necessarily represented identically by every provider or resource. Understand the resource's behavior before relying on drift detection as a complete security control.

## 15. Logging and auditing infrastructure changes

When an infrastructure incident occurs, the team should be able to answer:

- Who requested the change?
- Who approved it?
- Which plan was reviewed?
- Which identity applied it?
- Which provider and configuration versions were used?
- What changed in the target platform?
- Was the application healthy afterward?

Keep useful evidence such as:

- Pull request references.
- CI/CD execution identifiers.
- Plan review records.
- Terraform logs where appropriate.
- Platform audit events.
- Post-deployment verification results.

Do not publish secrets or sensitive state contents in logs. Operational evidence should be accessible to authorized responders without unnecessarily exposing credentials.

## 16. Module testing and reusable infrastructure

Reusable modules need validation just like application libraries.

Useful checks include:

- Formatting and validation.
- Reviewing required and optional inputs.
- Verifying outputs.
- Checking default values.
- Testing expected resource relationships.
- Generating plans for representative configurations.
- Testing security policy requirements.
- Reviewing upgrades against all relevant environments.

Where practical, use automated infrastructure tests in disposable environments. Avoid running destructive tests against shared or production infrastructure.

A module change that works in development can still behave differently in production because of quotas, network boundaries, provider differences, or environment-specific inputs.

---

# Layer 3 — Production Engineering & Interview Mastery

## 17. Incident simulation: a Terraform apply fails halfway through

**Scenario:** A deployment creates some resources, then fails while creating the database.

### Step 1 — Stop and assess

Do not immediately rerun the pipeline repeatedly. Determine whether the failed operation left infrastructure behind.

### Step 2 — Inspect the error

Check for:

- Permission failures.
- Resource quotas.
- Invalid arguments.
- Network conflicts.
- API rate limits.
- Provider errors.
- Dependency failures.

### Step 3 — Inspect state and actual infrastructure

```bash
terraform state list
terraform plan
```

Check the platform itself to confirm which objects exist and whether they are healthy.

### Step 4 — Correct the cause

Fix the configuration, permissions, quota, or environmental issue. Do not remove state entries merely to make the next plan appear clean.

### Step 5 — Plan again

Generate a fresh plan and review it for unexpected creation, replacement, or destruction.

### Step 6 — Apply and verify

Use the approved deployment process and verify the resulting infrastructure and application behavior.

**Interview principle:** A failed apply is a partially completed operation until evidence proves otherwise.

## 18. Incident simulation: a Terraform change exposes a database

**Scenario:** A pull request changes network rules, and the resulting database becomes publicly reachable.

### Immediate response

1. Establish the exposure and affected resource.
2. Restrict public access using an approved emergency procedure.
3. Confirm that authorized application traffic still works.
4. Review platform audit events and the Terraform change.
5. Determine whether credentials or data may have been exposed.
6. Rotate credentials if exposure warrants it.
7. Restore the intended network configuration through a reviewed change.
8. Add a preventive policy and a regression check.

Do not wait for a normal release window if there is an active security exposure and an authorized emergency mitigation is available.

The corrective Terraform configuration should reflect the intended security posture so that a later apply does not reintroduce the exposure.

## 19. Incident simulation: a provider upgrade changes resource behavior

**Scenario:** A provider upgrade produces an unexpected replacement in a production plan.

### Response

- Stop the production apply.
- Inspect the provider version and lock-file change.
- Identify the resource attribute causing replacement.
- Review the provider's upgrade notes.
- Compare plans under the previous and proposed versions where safely possible.
- Test in a non-production environment.
- Decide whether to modify the configuration, defer the upgrade, or follow a migration procedure.
- Apply only after the replacement risk is understood and approved.

Provider upgrades should be treated as infrastructure changes, not as harmless dependency maintenance.

## 20. Incident simulation: unexpected infrastructure cost

**Scenario:** The cloud bill increases after a Terraform deployment.

Investigate:

1. Identify which resources changed during the release.
2. Compare planned and actual resource configurations.
3. Inspect utilization, capacity, and scaling behavior.
4. Check for duplicate resources, unused disks, or unexpected replicas.
5. Confirm whether a module default or provider behavior changed.
6. Identify whether the increase is expected, temporary, or erroneous.
7. Propose a reviewed correction.

Do not automatically destroy resources just because they appear expensive. Confirm ownership, dependencies, data retention, and recovery implications before making changes.

## 21. Production readiness checklist

### Configuration and dependencies

- [ ] Terraform and provider requirements are explicit.
- [ ] Provider lock-file changes are reviewed.
- [ ] Configuration is formatted and validated.
- [ ] Reusable modules have documented inputs and outputs.
- [ ] Resource dependencies are clear.
- [ ] Destructive changes are reviewed carefully.

### State and recovery

- [ ] Shared environments use an appropriate remote-state design.
- [ ] State access is restricted.
- [ ] Locking or concurrency behavior is understood.
- [ ] State recovery options are documented and tested where feasible.
- [ ] State and plan artifacts are protected.
- [ ] State migration and recovery procedures are documented.

### Security

- [ ] Credentials are not hard-coded.
- [ ] Deployment identities follow least privilege.
- [ ] Network exposure is intentional.
- [ ] Database access is appropriately restricted.
- [ ] Required encryption controls are configured.
- [ ] Secret rotation procedures exist.
- [ ] Policy checks catch important prohibited configurations.

### Delivery and operations

- [ ] Plans are reviewed before production apply.
- [ ] Production deployment permissions are restricted.
- [ ] Failed applies are handled through a documented process.
- [ ] Post-deployment checks verify actual infrastructure.
- [ ] Drift detection is appropriate for the environment.
- [ ] Audit evidence is retained securely.
- [ ] Cost and resource ownership are visible.
- [ ] Incident response and recovery procedures are understood.

---

## 22. SDE-1 interview questions and answers

**1. Why should production infrastructure changes go through code review?**

Review makes the proposed changes visible before execution and helps identify destructive, insecure, or unexpectedly expensive operations.

**2. What is the blast radius of an infrastructure change?**

The scope of systems and users that could be affected if the change fails or behaves unexpectedly.

**3. Why pin provider dependencies?**

Explicit version constraints and a committed lock file help make provider selection reproducible and upgrades deliberate.

**4. Does a successful Terraform apply prove the application is healthy?**

No. It shows that Terraform completed its planned operations. Application behavior, dependencies, networking, and monitoring must still be verified.

**5. What should you do if an apply fails halfway through?**

Inspect the error, state, and real infrastructure; correct the cause; generate a fresh plan; review it; and apply through the approved workflow.

**6. Why is a saved plan sensitive?**

It may contain infrastructure details and sensitive values. Protect it from unauthorized access and avoid committing it.

**7. What is Policy as Code?**

The practice of expressing infrastructure rules in machine-checkable form so violations can be detected or prevented automatically.

**8. What is the difference between preventive and detective controls?**

Preventive controls stop prohibited changes before they happen. Detective controls identify conditions that already exist or have occurred.

**9. How does Terraform relate to infrastructure security?**

It can manage security-relevant infrastructure configuration, but safe outcomes require correct policies, identities, network rules, secret handling, and review processes.

**10. Why is `prevent_destroy` not a backup strategy?**

It is a configuration-level guardrail against certain Terraform destroy operations. It does not preserve data or prevent all external deletion paths.

**11. What should you do if a provider upgrade introduces unexpected resource replacement?**

Stop the risky apply, inspect the version and plan, review provider changes, test in a safe environment, and proceed only after the replacement implications are understood.

**12. How do you detect infrastructure drift?**

Generate plans and use suitable platform monitoring or drift-detection workflows to compare actual resources with the intended configuration.

**13. Why should infrastructure changes be small and reviewable?**

Smaller changes are easier to understand, test, attribute, and recover from, reducing uncertainty and blast radius.

**14. How would you respond to a publicly exposed database?**

Restrict access through an authorized mitigation, establish impact, review audit evidence, rotate credentials if warranted, restore the intended configuration, and add preventive controls.

**15. How should infrastructure credentials be provided to CI/CD?**

Prefer short-lived or federated identities where supported, with least-privilege permissions and secure credential handling.

**16. Why is state not a complete infrastructure backup?**

It tracks Terraform-managed resource mappings and attributes; it does not necessarily preserve resource contents or provide everything needed to recover the full system.

**17. What should you verify after an infrastructure deployment?**

Confirm the resulting resources, network access, application health, dependency connectivity, monitoring signals, and any expected changes in cost or capacity.

**18. How would you investigate an unexpected cost increase?**

Correlate the increase with deployment changes, inspect resource sizing and utilization, identify unexpected resources, and implement a reviewed correction.

**19. Why can a shared module change be risky?**

Many environments may inherit the same change. A default or resource change can affect multiple services and increase the blast radius.

**20. What does production readiness mean for Terraform?**

The configuration, state management, security, deployment controls, observability, and recovery procedures are designed and tested well enough to manage infrastructure safely.

---

## 23. Final Terraform capstone

### Scenario

You are responsible for infrastructure supporting a Spring Boot Orders API backed by PostgreSQL.

Design a Terraform workflow that provisions the required infrastructure and supports safe future changes.

Your solution should include:

1. A reusable network module.
2. An application infrastructure module.
3. A database infrastructure module.
4. Separate environment configurations or state boundaries appropriate to the deployment model.
5. A documented backend and state-recovery approach.
6. Explicit provider version requirements.
7. A secure deployment identity.
8. Restricted database access.
9. A reviewed CI/CD plan-and-apply workflow.
10. A post-deployment verification checklist.
11. Drift detection and incident-response procedures.
12. A strategy for handling database replacement and schema migration risk.

### Required failure drills

Perform these only in a disposable test environment.

- Introduce a configuration validation error and verify that the pipeline stops.
- Change a harmless resource input and review the plan.
- Simulate an unexpected replacement and practice stopping the deployment.
- Introduce an intentional drift in a disposable resource and inspect the plan.
- Test a failed apply and document how you determine which resources exist.
- Verify that unauthorized identities cannot apply production changes.
- Document how to recover if the state backend becomes unavailable.

### Final mastery standard

You should be able to explain not only how Terraform creates infrastructure, but how an engineering team can manage that infrastructure securely and reliably throughout its lifecycle.

---

# Terraform completion protocol

This is the **third and final planned Terraform content chunk**.

Save this chapter as:

`content/terraform/03-terraform-production-security-cicd-reliability-incident-mastery.md`

After all three Terraform source chapters have been saved and verified:

1. Confirm that all three Markdown files contain their complete chapters.
2. Build one complete Terraform handbook PDF from all three chapters in curriculum order.
3. Save it as `docs/terraform/BEH_TERRAFORM_COMPLETE_HANDBOOK.pdf`.
4. Verify chapter order, code blocks, tables, links, and page rendering.
5. Update the README with verified source and PDF status.
6. Commit the complete Terraform source chapters and verified PDF using the exact commit message:

`Terraform done`

**Do not generate a PDF for this chapter alone.**

## Handbook project milestone

The planned curriculum is now complete at the *content-authoring level in this conversation* for Terraform. This does not confirm that the chapters have been saved to the repository, that any PDF has been generated, or that any Git commit has been made.

The overall project still requires all 13 individual tool PDFs and the final master handbook:

`docs/BEH_MASTER_BACKEND_ENGINEERING_HANDBOOK.pdf`

The master must contain all 13 complete tool handbooks, the end-to-end integration lesson, and the final readiness checklist.
