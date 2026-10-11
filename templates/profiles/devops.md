---
name: devops
use-when: the output is LIVE INFRASTRUCTURE checked against its real state — cloud or on-prem resources, IaC (Terraform/OpenTofu, Bicep, CloudFormation, Pulumi, Ansible), Kubernetes/Helm, networking, CI/CD pipelines, platform config
truth-source: the live environment (provider APIs, real network paths, the state the tooling reads back)
---

- **consumer:** the workload or operator that depends on the infrastructure: an app that needs to reach its database,
  a user hitting an endpoint, an on-call engineer running a restore.
- **the-real-thing:** the resources as they exist in the target environment after apply, read back from the provider
  (or the hosts, for on-prem). The code, the plan and the console form you filled in do not count.
- **verify:** with the user's consent (see below), apply to a non-production environment first, then exercise the infrastructure from the consumer's
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
- **audit lenses:** run each as its own pass, then compare. **Wiring:** does it work from the consumer's position
  (reachable, resolvable, allowed)? **Security:** exposure, identities and least privilege, secrets. **Reliability:**
  single points of failure, backups restore-tested, failover. **Drift:** code vs state vs live resource. **Cost:**
  over-provisioned, under-provisioned, redundancy that the requirements don't need, wrong pricing model, storage
  tier, idle resources, data transfer (rules and probes in `devops/baseline.md`, Cost). Write every cost finding
  with all five parts of "Cost in every proposal": now, change, saving, performance and risk, way back. A cost cut that weakens
  reliability is a contradiction between lenses: flag it, don't pick silently.
- **pause points:** **every** change to infrastructure, in **any** environment, dev included: an apply, destroy or
  import; a state edit (`state rm`/`mv`/`push`); a CLI call that creates, updates, deletes, restarts or scales
  something; a `kubectl`/`helm` write; a playbook run; a change made over SSH. Infrastructure has no `git reset`. A
  deleted database, a replaced disk or a wrong firewall rule can't be undone by reverting code. So propose first and
  wait for a clear yes, every time, even under standing-proceed. A yes covers only the commands it was given for.

## Investigate before you change

Most infra damage comes from fixing the wrong thing fast. Before proposing any change:
- Find the actual cause with **read-only** commands: `plan`, `describe`, `show`, `get`, `list`, logs, `dig`, `curl`.
  Don't change anything "to see if it helps".
- Check the live state, not just the code. Code, state file and the real resource can disagree.
- Know what else depends on the thing you would touch: other apps, other teams, DNS, shared networks.
- If you can't find the cause, say so and list what you checked. A guess presented as a finding is worse than "I
  don't know yet".

## Propose, then ask

Before running anything that changes infrastructure, show the user this and wait for their answer:

1. **What I found:** the problem and its cause, with the command output that shows it.
2. **What I want to do:** the fix in plain words, then the exact commands or the plan output.
3. **Why it fixes it:** how this change removes the cause.
4. **What could go wrong:** what may break, go down or be deleted, for how long, and who would notice. Call out every
   destroy or replace in the plan by name.
5. **How to undo it:** the way back, or a plain "this can't be undone" (deleted data, replaced resources).
6. **Where it runs:** environment and account/subscription/project.
7. **Cost:** what this changes in the monthly bill, and any cheaper option with the same performance (see "Cost in
   every proposal" below).
8. **Your call:** "Do you want me to run this?" Then stop. No yes, no change.

## Cost in every proposal

Whenever you design, change or review infrastructure, look for the same performance at a lower cost, and say what
you found even when it wasn't asked. Each cost suggestion states:
- **Now:** what it costs today, from the bill or the provider's pricing page. Say which.
- **Change:** what you would change (size, tier, pricing model, schedule, removal).
- **Saving:** the estimated monthly saving. Label it an estimate and say how you got it.
- **Performance and risk:** what happens to speed, capacity and availability. Base sizing on real usage data (14 days
  or more), not a guess.
- **Way back:** how to undo it if performance drops.
Never remove redundancy that an availability requirement depends on without asking. Under-provisioning is also a
cost (slow responses, crashes, retries, extra replicas), so a bigger size can be the cheaper fix.

## Talk plainly

Assume the user is not an infrastructure expert. Many people now build with AI and never learned the terms.
- Use short sentences and everyday words. Explain a term the first time you need it ("a security group, which is the
  firewall for this server").
- Say what will happen to their app or users, not only what happens to the resource: "the site will be down for about
  2 minutes", "this deletes the old database and its data".
- No filler and no showing off. Say the finding, the fix, the risk, and the question.
- Never hide a risk inside jargon. If something is dangerous, say so in one plain sentence.

> Provider and workflow facets are confirmed during adoption: which clouds/on-prem platforms, the IaC tool and where
> its state lives, the environment ladder (dev → staging → prod), how credentials are obtained, and what "non-prod"
> means in this project.

**Guides** (in `devops/` next to this file; install only the ones that match): `baseline` has the cross-cloud rules,
each paired with its live probe (IaC and state, CI/CD, secrets and identity, networking, observability, backup/DR,
cost). It always comes with this profile. Then add one provider guide per platform in use (each maps the baseline rules
to that platform's services and CLI probes) and one tool guide per IaC tool in use (`terraform`: safe plan and apply,
state, environments, code; `shell`: writing and running scripts safely).

## Done-gate questions

The done-gate hook asks these in place of its generic self-check when this profile is installed. Edit them freely.
`match:` lines (one regex each, any can match) list the commands that change infrastructure. The guard hook stops
each of these and asks the user first; for the done-gate, a turn that ran one (or edited files) is a **change**, any
other turn is an **investigation**. Add a line when you use a tool that isn't covered. `claims:` adds conclusion phrases that count as a "done" claim.

### gate: change
match: \b(terraform|tofu|terragrunt)\s+(.*\s)?(apply|destroy|import|taint|untaint|force-unlock|state\s+(rm|mv|push|replace-provider)|workspace\s+delete)\b
match: \b(pulumi\s+(up|destroy|refresh|import|state\s+delete)|cdk\s+(deploy|destroy))\b
match: \baws\s+\S+\s+(create|delete|update|put|modify|attach|detach|associate|disassociate|run|start|stop|terminate|reboot|restore|replace|authorize|revoke|register|deregister|enable|disable|set|tag|untag)-
match: \baws\s+(\S+\s+deploy\b|s3\s+(rm|mv|cp|sync|rb|mb)\b|s3api\s+(delete|put)-)
match: \baz\s+([\w-]+\s+)+(create|delete|update|set|add|remove|start|stop|restart|deallocate|scale|swap|import|purge|assign|deploy|apply)\b
match: \bgcloud\s+([\w-]+\s+)+(create|delete|update|deploy|start|stop|reset|resize|import|patch|apply|set-[\w-]+|add-[\w-]+|remove-[\w-]+)\b
match: \bdoctl\s+([\w-]+\s+)+(create|delete|update|apply|tag|untag|rebuild|resize|power-on|power-off|power-cycle|reboot|shutdown)\b
match: \bkubectl\s+(.*\s)?(apply|create|delete|patch|replace|scale|edit|label|annotate|taint|drain|cordon|uncordon|set|rollout\s+(restart|undo))\b
match: \bhelm\s+(install|upgrade|uninstall|rollback|delete)\b
match: \bansible-playbook\b(?!.*--check)|\bansible\s.*-m\s+(shell|command|raw|service|systemd|package|apt|yum|dnf|copy|file|user)\b
match: \b(systemctl\s+(start|stop|restart|reload|enable|disable|mask)|reboot|shutdown|iptables\s+-[ADIRF]|ufw\s+(allow|deny|delete|enable|disable))\b
- Before running it, did you show the user what you found, the fix, the risks and how to undo it, in plain words,
  and get a clear yes for these exact commands?
- Which environment and account/subscription/project did this run against? Did you check the workspace, backend and
  credentials first, or assume them?
- Did you read the whole plan? List every destroy and replace (`-/+`) and say why each is intended. A replace of a
  stateful resource (database, volume, bucket, key) is data loss.
- Was the apply run from the saved, reviewed plan file (`plan -out` then `apply <file>`), not a fresh auto-approve?
- After apply, does a new plan show no changes (`plan -detailed-exitcode` exits 0)? A diff means drift or a
  perpetual diff.
- Did you probe it from the consumer's side, as the workload identity (`dig`, `curl`, `nc`, the allowed call and one
  denied call)? Show the output.
- Any state edit, import or console change? Is it in code now, and did the user approve it?
- What is the rollback, and has it been tried?
- What does this change in the monthly bill? Is there a cheaper option with the same performance, and did you say so?
- Is your reply in plain words someone without infra experience can follow, with every risk stated plainly?

### gate: investigation
claims: root cause|the cause (is|was)|caused by|the (issue|problem) (is|was)|it'?s because|that'?s why|explains (it|the)
- What exactly is the symptom, and where was it seen: environment, account, time window, network position?
- Which statements come from output you ran in this session, and which are inference? Label each, and quote the
  command for the observed ones.
- Did you check the live state, not just the code? Code, state and the real resource can disagree (drift, console
  edits, a failed apply).
- What changed when it started? Check the deploy history, the audit log, the last applies, cert expiry and quota.
- Does the cause explain every symptom, including the timing? Which alternatives did you rule out (DNS, firewall or
  security group, IAM, routing, TLS, quota, provider incident), and how?
- Were all probes read-only? If you changed anything to test, did you revert it and say so?
- What is still unknown, and which probe would settle it?
- Did you propose the fix (what it does, why it works, what could break, how to undo it) and ask, instead of
  applying it? Is it in plain words someone without infra experience can follow?
