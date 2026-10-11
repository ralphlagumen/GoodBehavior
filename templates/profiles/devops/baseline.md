---
name: devops/baseline
use-when: any devops project, whatever the provider; the provider guides next to this file map each rule to services and CLI probes
---

# DevOps baseline: cross-cloud rules, each with its live probe

Every rule here is paired with a **probe**: the check that shows the rule holds in the live environment. A rule with
no probe result is unverified, however good the code looks. Provider guides (`aws.md`, `azure.md`, …) give the
concrete service names and CLI commands for each rule.

How to run probes:
- **Read-only by default.** A probe reads state; it does not change it. A probe that changes anything (failover,
  restore, rotation, a deliberate denied write) is marked **(pause point)**: propose it and get the user's yes first,
  in every environment, per `devops.md`. Prefer non-prod; prod only as a planned, user-approved exercise.
- **From the consumer's position.** Run reachability and access probes as the workload identity and from the
  workload's network, not from your admin login on your laptop. An admin probe passes where the workload fails.
- **Name where it ran.** Every probe result records the environment and the account/subscription/project.

## IaC and state

- **rule:** All infrastructure is defined in code in version control. Nothing is created or changed by hand in the
  console, except break-glass, which is then written back into code.
  **probe:** run the plan against the live environment; it shows no changes (`terraform plan -detailed-exitcode`
  exits 0, or your tool's equivalent). A diff means drift or an unrecorded console change.
- **rule:** State is remote, encrypted, versioned and locked, never a local file or committed to git.
  **probe:** read the backend config, then list the state bucket/container and confirm versioning and encryption are
  on. Start two plans at once and confirm the second waits on, or fails on, the lock.
- **rule:** Each environment has its own state and its own credentials, so a dev apply cannot touch prod.
  **probe:** with dev credentials, run a read against a prod resource and confirm it is denied.
- **rule:** Modules and providers are pinned to exact versions.
  **probe:** grep the version constraints and the lock file; no unpinned or open-ended `>=` without an upper bound.

## CI/CD

- **rule:** Every change reaches an environment through the pipeline: plan on pull request, a reviewed apply on merge.
  **probe:** open a test PR and confirm the plan is posted to it. Check the deploy history: every prod apply maps to a
  merged commit.
- **rule:** The pipeline authenticates with short-lived federated credentials (OIDC), not long-lived keys stored as
  secrets.
  **probe:** list the CI secrets: no static cloud keys. Read the cloud's trust policy and confirm it is scoped to this
  repo and branch/environment.
- **rule:** Prod deploys need an approval gate and run only from the protected branch.
  **probe:** read the branch protection and environment rules. Confirm a run from a non-protected branch cannot reach
  prod credentials.
- **rule:** A deploy can be rolled back, and the rollback path has been used.
  **probe:** **(pause point)** in non-prod, deploy the previous version through the pipeline and confirm the health
  check passes.

## Secrets and identity

- **rule:** Secrets live in a secret manager, never in code, images, state outputs or CI logs.
  **probe:** run a secret scanner over the repo and its history (e.g. `gitleaks detect`). Grep state for known secret
  names. Read a recent CI log for leaked values.
- **rule:** Workloads use managed or workload identities, not embedded keys.
  **probe:** from inside the workload, ask the platform who it is (the provider's identity call) and confirm it is the
  expected role, not a user or a long-lived key.
- **rule:** Least privilege: each identity can do its job and nothing more.
  **probe:** **(pause point)** as the workload identity, try one action it must not do (read another app's secret,
  write outside its bucket) and confirm it is denied. Use a harmless target.
- **rule:** Humans use SSO with MFA. Root or owner accounts are locked away with no access keys.
  **probe:** list the root/owner credentials: no access keys, MFA on. List users with console passwords but no MFA:
  none.
- **rule:** Secrets rotate, and the workload survives rotation.
  **probe:** read the rotation config and last-rotated date. **(pause point)** in non-prod, rotate once and confirm the
  workload keeps working.

## Networking

- **rule:** Nothing is public unless it is meant to be. Databases, caches and admin ports are reachable only from
  their consumers.
  **probe:** from outside the network, `nc -zv <host> <port>` on the database and admin ports times out or is
  refused. From the app's subnet, the same call connects.
- **rule:** Ingress is limited to what is needed. No `0.0.0.0/0` on SSH, RDP or database ports.
  **probe:** list the firewall/security-group rules and grep for open-world sources on non-HTTP ports.
- **rule:** Public endpoints serve valid TLS, renewed automatically.
  **probe:** `openssl s_client -connect <host>:443 -servername <host>` shows a trusted chain and an expiry date more
  than 14 days away. Confirm the renewal job or managed certificate exists.
- **rule:** DNS records are in code and resolve as intended from each side (public and private).
  **probe:** `dig +short <name>` from outside and from inside the network; each returns the expected address.
- **rule:** Outbound traffic goes through a known path (NAT, proxy or egress firewall).
  **probe:** from the workload, call an external echo service (e.g. `curl -s https://ifconfig.me`) and confirm the
  source address is the expected NAT/egress IP.

## Observability

- **rule:** Logs from every workload and the control plane (audit log) are kept centrally, with a set retention.
  **probe:** trigger a known event (a request, a denied action) and find it in the central log within minutes. Read
  the retention setting.
- **rule:** Key signals have alerts that reach a human: availability, error rate, saturation, cost spikes.
  **probe:** **(pause point)** fire a test alert (or breach a threshold in non-prod) and confirm it reaches the
  on-call channel.
- **rule:** Each public service has a health check or uptime probe from outside.
  **probe:** read the uptime check's last results. **(pause point)** Take a non-prod instance down and confirm the check fails.
- **rule:** The cloud audit log is on in every account/region and stored where workloads cannot delete it.
  **probe:** confirm the audit trail is enabled and logging, then try to delete it as a workload identity: denied.

## Backup and DR

- **rule:** Every stateful store (databases, volumes, buckets, state files) has automated backups with a known
  retention.
  **probe:** list the backup jobs/snapshots for each store and confirm the latest is inside the expected window.
- **rule:** Backups are restore-tested. A backup that was never restored does not count.
  **probe:** **(pause point)** restore the latest backup into a scratch target, never over the source. Run a data
  check (row counts, a known record, the app's health check against it) and keep the restore log with timings.
- **rule:** RPO and RTO are written down, and the restore test meets them.
  **probe:** compare the backup age (RPO) and the restore duration from the log (RTO) to the written targets.
- **rule:** Backups are protected from the account that made them: a separate account/vault, immutability or
  object lock.
  **probe:** as the workload or deploy identity, try to delete a backup: denied. Read the lock or immutability setting.
- **rule:** Failover across zones or regions works, where the design claims it.
  **probe:** **(pause point)** in non-prod, or as a scheduled prod exercise, fail over and measure recovery against
  the RTO.

## Cost

- **rule:** Every resource carries owner, environment and cost-center tags, enforced by policy.
  **probe:** query the provider for resources missing the required tags; the list is empty. Try creating an untagged
  resource in non-prod (**pause point**); the policy blocks it.
- **rule:** Budgets with alerts exist per account/project and environment.
  **probe:** list the budgets and their alert recipients, and confirm the thresholds fire before the money is spent.
- **rule:** No idle spend: unattached disks, idle IPs, stopped-but-billed instances, old snapshots outside retention.
  **probe:** list unattached volumes, unassociated IPs and snapshots older than retention; each has an owner or goes.
- **rule:** Non-prod is sized down and scheduled off when unused.
  **probe:** read the schedules and instance sizes for non-prod; compare against prod.
- **rule:** Not over-provisioned: sizes match real use. Low average and p95 use over 14+ days (for example CPU under
  20% and memory under 40%) means a smaller size, a burstable type or autoscaling.
  **probe:** pull 14–30 days of CPU, memory, disk and network use (average and p95) for each instance, database and
  node pool, and compare with its size. Memory often needs the provider's agent; say if it's missing.
- **rule:** Not under-provisioned: running hot costs money too (slow responses, crashes, retries, extra replicas
  added to compensate). Sometimes one bigger size is cheaper than several small ones.
  **probe:** look for p95 CPU over 80%, out-of-memory kills, exhausted burst credits, throttled disk or API calls,
  long queues, and autoscaling stuck at its maximum.
- **rule:** Redundancy matches the written availability target. Prod keeps what the target needs. Dev and test don't
  run multi-zone databases, a NAT gateway per zone or spare replicas unless there's a reason. No two resources doing
  the same job (unused load balancers, duplicate log pipelines, forgotten replicas).
  **probe:** list multi-zone, replicated and duplicated resources per environment and match each to the availability
  target. Anything that backs the target stays unless the user decides otherwise.
- **rule:** The pricing model fits the usage: commitments (reserved capacity, savings plans, committed use) for
  steady 24/7 load; spot or preemptible for work that can be interrupted; serverless or autoscaling for spiky load.
  Newer instance generations and ARM types often give the same performance for less.
  **probe:** read the commitment coverage and utilization reports, and list instance families and generations in
  use against what is current.
- **rule:** Storage sits in the right tier: lifecycle rules move or expire old objects, logs have a retention, disk
  types match the IOPS really used.
  **probe:** list buckets without lifecycle rules, log groups without retention, and disks with provisioned IOPS far
  above measured use.
- **rule:** Data transfer is known and kept low: cross-zone, cross-region and NAT traffic are billed. Use private or
  gateway endpoints for the provider's storage and APIs; keep chatty services in the same zone.
  **probe:** break the bill down by usage type and check NAT bytes processed and inter-zone/region transfer.
