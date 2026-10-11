---
name: devops
use-when: the output is LIVE INFRASTRUCTURE checked against its real state — cloud or on-prem resources, IaC (Terraform/OpenTofu, Bicep, CloudFormation, Pulumi, Ansible), Kubernetes/Helm, networking, CI/CD pipelines, platform config
truth-source: the live environment (provider APIs, real network paths, the state the tooling reads back)
---

- **consumer:** the workload or operator that depends on the infrastructure: an app that needs to reach its database,
  a user hitting an endpoint, an on-call engineer running a restore.
- **the-real-thing:** the resources as they exist in the target environment after apply, read back from the provider
  (or the hosts, for on-prem). The code, the plan and the console form you filled in do not count.
- **verify:** apply to a non-production environment first, then exercise the infrastructure from the consumer's
  network position: resolve the DNS name, call the endpoint, connect to the database from the app's subnet, assume the
  role and try the denied action, fail over, restore the backup. Then re-run the plan and confirm it shows no changes
  (no drift, no perpetual diff).
- **evidence:** the reviewed plan, the apply output, a post-apply plan showing no changes, and the probe output from
  the consumer's position (`curl`, `dig`, `nc`, a CLI `describe`/`get` of the resource, a restore log). Each piece
  names the environment and account/subscription/project it came from.
- **verify anti-patterns:** "`validate`/`lint` passed"; "the plan looks right" with nothing applied; apply succeeded
  but nothing probed it; probing from inside the same host or with admin credentials, so a firewall or IAM gap stays
  hidden; a backup that exists but was never restored; verified in dev, claimed for prod; a console change that never
  made it into code.
- **pause points:** any apply, destroy, state edit (`state rm`/`mv`/`import`), or DNS/IAM/network change against a
  shared or production environment is a destructive step. Show the plan and wait for the user, even under
  standing-proceed.

> Provider and workflow facets are confirmed during adoption: which clouds/on-prem platforms, the IaC tool and where
> its state lives, the environment ladder (dev → staging → prod), how credentials are obtained, and what "non-prod"
> means in this project.

**Guides** (in `devops/` next to this file; install only the ones that match): `baseline` has the cross-cloud rules,
each paired with its live probe (IaC and state, CI/CD, secrets and identity, networking, observability, backup/DR,
cost). It always comes with this profile. Then add one provider guide per platform in use. Each maps the baseline rules
to that platform's services and CLI probes.
