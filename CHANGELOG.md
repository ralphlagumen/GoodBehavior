# Changelog

Every entry here is a unit a downstream project will 3-way-merge via `/update-goodbehavior` — write entries so an
adopter skimming before an update knows what's coming and why.

## 2026-10-12 — devops guard.py: default-deny parsing, looser default (ask), secrets denied

The red-team audit found the text-matching guard bypassable (29 confirmed routes) and failing open. This replaces it
for devops projects with `templates/profiles/devops/guard.py`, adapted from a hand-built default-deny guard an adopter
wrote after unasked applies. Same parser and default (a command runs only when every part is shown to be read-only
or local), softer outcome: anything else **asks** instead of being denied, so investigation isn't blocked.

- **Runs:** cloud reads (aws/az/gcloud/doctl/kubectl/helm), plan/test/validate, scanners, local git commits, local
  docker, SSM port-forward tunnels, `ssh -N -L` tunnels, ssh with the user's own config, and ssh commands whose every
  part reads (pipes included). Reads `make` recipes (prerequisites, variables, `.env` includes, recursive make,
  `$(shell)`), scripts and what they source, package scripts and inline Python before deciding. Tracks `cd` and
  simple variables (`X=literal`, `X=$(mktemp -d)`) across a command line.
- **Asks** (right away, saying what it found): infrastructure writes, remote changes over ssh, unknown programs,
  `eval`, arithmetic tricks, unparseable lines, edits to `.claude/`, `.mcp.json`, git hooks/config, the lock file,
  `.terraform/`, scanner config.
- **Denies:** anything that would show a secret — credential files (symlinks and globs resolved), `.env`/`.secret`,
  recursive greps that would reach them (`grep -R`/`rg -L` follow symlinks; `grep -r`/`rg` don't), secret-manager and
  token commands (aws/az/gcloud/doctl, vault, op, sops, gh), `terraform output -json|-raw|<name>`, `state pull`,
  `docker inspect` without `--format`, `docker exec … env`. Also denies on any crash (fail closed), and turns every
  ask into a deny when permissions are bypassed.
- **Logs** every ask and deny to `.claude/goodbehavior/guard.log` (permission mode included; no secret values).
- `done-gate.py` hands PreToolUse to an installed `profiles/**/guard.py`; a guard that fails to load denies. Without
  one, the old text-matching guard still applies. `install.py` wires PreToolUse on `*` (so `Monitor` and MCP tools
  reach it) and accepts `devops/guard.py` as a profile entry; `adopt` adds it with the devops profile.
- Tests: `tests/test_guard.py` (517 decisions: 396 identity-stripped cases from the adopter's bypass suite with the
  intended loosenings, the red-team routes, make/scripts/package scripts, Terraform escape hatches, tools, bypass
  mode, fail-closed, the log). Live with `claude -p` in bypass and acceptEdits modes: `make infra_plan` ran, `make
  infra_apply` stopped with the hidden line named, `Read .env` denied, an ssh read passed the guard; four log lines,
  no secret in them.

## 2026-10-11 — guard: protects itself, docker over ssh, deny when permissions are bypassed

- **Self-protection:** a new `### gate: protect` section lists files whose edits always ask: `.claude/settings*.json`,
  `.claude/hooks/`, `.claude/goodbehavior/profiles/`. Covers the Edit/Write tools and shell writes (redirects,
  `cp`/`mv`/`rm`/`tee`, `sed -i`, inline code). Reading them is fine.
- **Docker over SSH:** `docker`/`docker compose` writes (`down`, `up`, `restart`, `rm`, `exec`, ...) run on another
  host through `ssh` or `docker -H ssh://` ask. Local docker is not matched.
- **Bypass mode:** observed live, Claude Code skipped a hook's "ask" for Edit under `--dangerously-skip-permissions`
  (Bash asks held). Hooks receive `permission_mode`, so under `bypassPermissions` every "ask" becomes "deny", with a
  note telling Claude to explain the step to the user instead.
- `install.py` wires the guard on `Bash|Read|Grep|Edit|Write|MultiEdit|NotebookEdit`. **Existing adopters:** widen
  the PreToolUse matcher for `done-gate.py` in `settings.json` by hand.
- `devops.md` **suggests** (does not require) keeping `AWS_PROFILE`, region, subscription and project settings in the
  project's `.env`, so commands don't need prefixes and a one-off override stands out.
- Tested: 20 more guard cases (docker over ssh vs local, self-protection by every write route, bypass-mode denies);
  real `claude -p` with permissions skipped: editing the hook was blocked and the file left unchanged, `make
  infra_apply` blocked, a harmless command ran.

## 2026-10-11 — devops: guard sees inside make/scripts, protects secrets; security in every audit

- **Guard** (`done-gate.py`, PreToolUse): follows `make` targets (prerequisites, variables, includes, recursive
  `$(MAKE)` calls), scripts (shell, Python, Node, Ruby, Perl), scripts they call and inline code, up to 3 levels. A
  harmless run (nothing that changes infrastructure or touches secrets) just runs; a risky one asks and names the
  line it found (for example `Makefile:infra_apply: terraform apply tfplan`).
- **Secrets:** new `### gate: secrets` section in the profile. `files:` lists secret files (`.secret`, `.env` but not
  `.env.example`, cloud CLI credential caches, kube config, SSH keys, `*.tfstate`); `match:` lists commands that
  print secrets (secret-manager reads, token printers, `terraform output -json` unless piped to a filter, `printenv`).
  Reading a secret file (Read, Grep, or `cat`/`grep`/`tail`/... in Bash) or running such a command is **denied**.
  Writing without reading (`>> .env`, `sed -i`) is allowed. `devops.md` adds the `.secret` file convention.
- **Change detection** also catches cloud SDK write calls in code (`.terminate_instances(`, `begin_delete(`) and
  signed raw API calls (`curl --aws-sigv4`).
- `install.py` wires the guard on `Bash|Read|Grep` (was `Bash`). **Existing adopters:** change the PreToolUse
  matcher for `done-gate.py` in `settings.json` by hand; `/update-goodbehavior` doesn't touch settings.
- **Security in audits:** the security lens now covers the attack surface against automated attacks (DDoS, bots,
  injection, exposure, patching, detection). Each finding states risk, how likely, impact, fix and evidence, in plain
  words. New baseline section "Security and attack surface" (11 rule/probe pairs) and a matching section in every
  provider guide (AWS WAF/Shield/GuardDuty/Inspector/Security Hub; Azure WAF/DDoS/Defender; GCP Cloud Armor/SSL
  policies/SCC; DigitalOcean: external WAF + firewall; on-prem: ModSecurity, fail2ban/CrowdSec, patching, lynis).
- Fixed a probe that would have passed every server: `openssl s_client -tls1_1` fails on the client side under
  OpenSSL 3+; the probe now adds `-cipher 'DEFAULT@SECLEVEL=0'` (tested: example.com does accept TLS 1.1).
- `shell.md`: assess a script's risk first; run it if harmless, otherwise explain why it needs to run, what could
  go wrong and what it fixes, then ask.
- `update.py`/`install.py` expand `~` in the source path; `install.py` keeps `updatedAt` when adding files.
- Tested: 40 new guard cases (make, scripts, inline code, secrets) plus the 280 command cases; all CLI commands in
  the guides parse (232); on-prem security tools run in Debian 12; real `claude -p` runs with permissions skipped:
  `make infra_apply` stopped with the hidden line named, `Read .secret` blocked (canary never printed), a harmless
  script ran.

## 2026-10-11 — devops: guide commands checked in the self-test; on-prem Linux probes run

- `tests/test_guide_cli.py`: every `aws`, `az`, `gcloud` and `doctl` command in the devops guides is parsed by the
  real CLI with no credentials and no provider reach (fake keys, empty configs, a dead local endpoint for aws). A
  command passes when it gets past parsing and stops at the missing login. CLIs that aren't installed are skipped.
  Known non-commands are listed with a reason. Takes about 15 seconds; a broken command name or a missing required
  argument fails it.
- `devops/onprem.md`: the Linux-only probes were run in a Debian 12 container (`ss`, `nft`, `iptables`, `ufw`,
  `sshd -T`, `sudo -l`, `journalctl`, `smartctl`, `chronyc`, `sar`, `logger`, `virsh`, `upsc`, `certbot`, and a
  real `restic`/`borg` backup, check and restore, diffed identical); `govc` checked against govc 0.56. Two notes
  added: stock Debian fails the SSH rule until hardened, and `sar` history needs sysstat collection enabled.
  Proxmox `qm`/`pct`/`ha-manager` were reviewed, not run.

## 2026-10-11 — devops: provider guides (AWS, Azure, GCP, DigitalOcean, on-prem)

- `templates/profiles/devops/{aws,azure,gcp,digitalocean,onprem}.md`: each maps every baseline area (IaC and state,
  CI/CD, secrets and identity, networking, observability, backup/DR, cost) to that platform's services and CLI
  probes. Each names the platform's own traps: Azure "stopped" VMs still billed until deallocated; DigitalOcean
  databases with no trusted sources accept connections from anywhere, powered-off droplets are billed in full, and
  there is no OIDC or audit-log API; GCP default compute service account; AWS Cost Explorer calls are billed.
- Every CLI command was checked offline against the installed CLI (AWS CLI 2.36, Azure CLI 2.89, Google Cloud SDK
  588, doctl 1.166) with no credentials and no network reach to the provider: command names, flags, required
  arguments and (AWS, Azure) `--query` syntax. That caught 3 Azure commands that need `-g` and a GA-missing
  `gcloud monitoring channels`. On-prem probes that run on macOS were run (SSH certificate window, TLS expiry,
  `dig`, `nc`, Ansible check mode showing drift without changing anything); Linux-only ones (`ss`, `nft`,
  `systemctl`, `journalctl`, `smartctl`) were reviewed but not run.
- Guard: `match:` lines now cover on-prem changes (`qm`, `pct`, `govc`, `virsh`, `ha-manager`, `restic`/`borg`
  forget/prune/restore) and more cloud verbs (rotate, restore, failover, clone, fork, `set-*`). Verbs match whole
  words only, so `az sql failover-group list` no longer asks.
- `test_hook.py`: every CLI command in the guides is checked against the guard: the 12 after a pause-point marker
  must ask, the 200+ read-only probes must not (280 commands in all). `test_lint.py` checks all 8 guides pair every
  rule with a probe.

## 2026-10-11 — devops: cost in every audit and proposal

- `devops.md`: new **audit lenses** slot (wiring, security, reliability, drift, cost). The cost lens looks for
  over-provisioning, under-provisioning, redundancy the requirements don't need, the wrong pricing model, storage
  tier, idle resources and data transfer. Every cost finding states now / change / saving (labeled an estimate) /
  performance and risk / way back. A cost cut that weakens reliability is flagged as a lens conflict.
- New "Cost in every proposal" section: look for the same performance at lower cost on every design, change or
  review, size from 14+ days of real usage, never drop redundancy an availability target needs without asking.
  Propose-then-ask gains a cost line; the change gate asks about bill impact.
- `devops/baseline.md` Cost: six new rule/probe pairs (over- and under-provisioning, redundancy vs target, pricing
  model, storage tier, data transfer).
- `audit-goodbehavior`: one line pointing devops audits at the profile's lenses.
- Tested: a real `/audit-goodbehavior` run on a scratch over-provisioned Terraform project produced cost findings in
  the five-part format, flagged the cost-vs-backup conflict, and changed no files under `infra/`.
- `devops/shell.md`: shellcheck probes now tested (SC2086, SC3010, SC3030; the template passes clean).

## 2026-10-11 — devops: shell script guide

- `templates/profiles/devops/shell.md`: rules for writing and running shell scripts, from Cycle.io's "Shell Scripting
  Best Practices", each with a probe: read a script before running it and ask if it changes anything; strict mode;
  dry run by default with `--apply`; input checks; quoting and `--`; `mktemp -d` + `trap` cleanup; no `eval` or
  secrets; descriptive names; `printf`; POSIX vs bash shebang; `bash -n`/`shellcheck`. Ends with a tested template.
- Corrections to the article, tested with bash 5.3: `set -e` alone let a failed pipeline continue and turned a
  variable typo into `/old`; `set -euo pipefail` stops both, but failures inside functions called from `if` are
  still ignored. The article's `rm -rf /tmp/*` cleanup deletes other programs' files; use `mktemp -d` + `trap`.
- The guard hook can't see inside a script, so the guide makes reading it first a rule.

## 2026-10-11 — devops: Terraform guide

- `templates/profiles/devops/terraform.md`: rules for a safe Terraform/OpenTofu apply, from Paweł Piwosz's "10
  Terraform best practices that actually matter", each with a probe run against Terraform 1.15: saved plan only, list
  every delete/replace from `show -json` before asking, `plan -detailed-exitcode` after apply, remote locked state,
  split state, one directory per environment, validated variables, pinned versions, `templatefile()`, module READMEs.
- Corrections to the article: S3 locking uses `use_lockfile = true` (Terraform 1.15 deprecates `dynamodb_table`);
  `most_recent` image lookups can force a replace; added `prevent_destroy` on stateful resources and a
  user-approved `force-unlock`.
- `devops.md` and `adopt-goodbehavior` offer tool guides next to provider guides. Lint checks the new guide.

## 2026-10-11 — devops: ask before every infra change

Infrastructure has no `git reset`: a deleted database or a wrong firewall rule can't be reverted. So:

- **Guard hook.** `done-gate.py` also runs as a PreToolUse hook on Bash. A command that matches a profile's change
  `match:` lines (terraform/tofu apply, destroy, import, state edits; cloud CLI create/update/delete calls for AWS,
  Azure, GCP and DigitalOcean; kubectl/helm writes; playbook runs; service restarts, reboots, firewall edits) returns
  `ask`, so the user must approve it. Read-only commands (`plan`, `describe`, `list`, `get`, logs) pass. Tested live:
  under `claude -p`, a matched command was blocked even with permissions skipped; a read-only one ran.
- **`devops.md`:** pause points now cover every change in every environment, dev included. New sections:
  investigate before you change (read-only first, live state, dependents, say "I don't know yet"), propose then ask
  (found / fix / why it works / what could break / how to undo / where / "do you want me to run this?"), and talk
  plainly (assume the user is not an infra expert; no filler; state risks in one plain sentence).
- `install.py` wires the guard (`PreToolUse`, matcher `Bash`) alongside the Stop hook. **Existing adopters:**
  `/update-goodbehavior` updates the hook file but not `settings.json`; re-run the install plan (it skips existing
  files) or add the PreToolUse entry by hand.
- Tests: 50 commands checked for the right ask/pass decision; install wires the guard once.

## 2026-10-11 — done-gate: profile questions (devops first)

- `done-gate.py`: an installed profile can carry `### gate: change` and `### gate: investigation` sections. When
  present, their questions replace the generic self-check. A turn is a **change** if it edited files or ran a command
  matching the profile's `match:` regex; otherwise it is an **investigation**. `claims:` adds conclusion phrases
  ("root cause", "caused by") that count as a done-claim. No sections → the generic messages, unchanged. A bad regex is
  ignored, never breaks the session.
- `devops.md`: change questions (target environment, every destroy/replace in the plan, apply from the saved plan,
  no-change re-plan, probe as the workload identity, state edits, prod approval and rollback) and investigation
  questions (symptom and where, observed vs inferred, live state vs code, what changed, alternatives ruled out,
  read-only probes, what's still unknown; propose the fix, don't apply it). Edit them in the profile.
- `test_hook.py`: 7 devops cases; runs hermetic (sets `CLAUDE_PROJECT_DIR`).

## 2026-10-11 — devops baseline guide

- `templates/profiles/devops/baseline.md`: cross-cloud DevOps rules in seven areas (IaC and state, CI/CD, secrets and
  identity, networking, observability, backup/DR, cost). Every rule is paired with a live probe. Probes are read-only
  by default; ones that change state (restore, failover, rotation, a deliberate denied write) are marked pause points.
  Backups count only once restored into a scratch target.
- `devops.md` lists its guides. `adopt-goodbehavior` asks which platforms are in use and installs the matched guides as
  `<profile>/<guide>` entries (e.g. `devops/baseline`). `install.py` already handled the nested path; no code change.
- `test_lint.py`: every guide rule must carry a probe; the invariant layer must not name a cloud provider.
  `test_install.py`: a nested guide installs byte-identical and the manifest records its source path.

## 2026-10-11 — devops profile

- `templates/profiles/devops.md`: a fifth core profile for infrastructure work, cloud or on-prem (IaC, Kubernetes,
  networking, CI/CD). The real thing is the live environment read back from the provider; verify is apply to non-prod,
  probe from the consumer's network position, then re-plan for no changes; evidence names the environment it came
  from. Adds a **pause points** slot: applies, destroys, state edits and DNS/IAM/network changes to shared or prod
  environments wait for the user, even under standing-proceed.
- `INDEX.md`, `adopt-goodbehavior`, `install.py`, `test_lint.py`, README: count and list five cores.

## 2026-07-13 — chat-agents: attach-file + inline-prompt deployment

Some assistants (Copilot observed) **ignore custom instructions**, so standing instructions alone aren't enough. The
`chat-agents/` folder now supports the robust belt-and-suspenders pattern and is single-sourced:
- `chat-agents/goodbehavior.md`: **the** method (attach it, or paste it as instructions) — one source of truth.
- `chat-agents/PROMPT-TEMPLATE.md`: a blank, domain-neutral per-task scaffold that re-states the gate + ✔/⚠ evidence
  rules *inside the task prompt*, where a forgetful agent can't drop them.
- `chat-agents/EXAMPLE.md`: the template filled for one task — domain nouns isolated here so the base stays neutral.
- `chat-agents/README.md`: documents both deployment modes; replaces `PERSONALIZATION.md` (removed — its block became
  `goodbehavior.md`, its usage notes became the README). Top-level README pointer updated.

## 2026-07-12 — chat-only companion

- `chat-agents/PERSONALIZATION.md`: a standalone copy-paste block that carries the operating principles into plain
  Claude.ai chat (no skills, no hook, no filesystem). Audited/enhanced from a user template — adds the gate-vs-drive
  throughline, ✔/⚠ evidence tagging, a done-is-not-self-declared gate, and the unknown-vs-brainstorm distinction; keeps
  the understanding gate and running ledger. All examples are domain-neutral (stated as schema, not instance) so the
  base doesn't prime a frame or infect future variants. Companion only — not installed, not part of the core method.
  README pointer added.

## 2026-07-08 — generalize beyond dev; shrink the trust surface

**Profiles — the method is no longer dev-only.**
- `templates/profiles/`: four composable core profiles (development · analysis · research · creative), each defining
  *the-real-thing / verify / evidence* for its truth source; an INDEX for cheap on-demand loading; a custom-elicit
  fallback. Only the matched profile(s) install into a target — never all four.
- `/adopt-goodbehavior`: new intent-elicitation phase **before** the file survey (what is this project / what does done
  mean / who consumes it / how do you check it's right); the survey is corroboration, not the decider. Adopt must never
  say "GoodBehavior isn't meant for this project."
- Invariant layer reworded artifact-agnostic (CLAUDE.md definition of done, verify/gate-build/audit/roadmap/uatplan
  skills, hook message, templates): "exercised the way its **consumer** would," with the dev phrasing moved into the
  development profile.

**Enforcement — the done-gate is now behavioral, not just lexical.**
- `done-gate.py`: honest hedges always pass; verification vocabulary ("verified", "tests pass") is honored **only if
  something was actually run/observed after the last file change that turn**. "Edited files, ran nothing, said
  'verified'" now blocks. Doc-only turns exempt; bash-only turns pass; sub-agent results don't count as firsthand.

**Determinism — mechanics moved out of prompts into scripts.**
- `scripts/install.py`: adopt's mechanical half (copy, hash, wire the Stop hook without clobbering settings.json, write
  the manifest). Idempotent; never clobbers.
- `scripts/update.py`: update's mechanical half (manifest-driven git 3-way merge; fast-forward / merge / conflict /
  keep-upstream-removed; exit 2 on conflicts).
- The skills keep the judgment (profile resolution, proposals, conflict walkthroughs) and call the scripts.

**Self-test — the bundle held to its own standard.**
- `tests/run_all.py`: hook behavior (14 cases incl. the hollow-proof cheat), install round-trip + idempotency, update's
  four merge paths against a real second commit, structural + drift lint (profiles well-formed; invariant files must not
  re-acquire unscoped dev-coded phrasing). One command; green before shipping.

**Housekeeping.**
- `/adopt-goodbehavior` is no longer copied into targets (run-once installer; targets carry the working skills +
  `/update-goodbehavior`). Seeded memories point at the canonical principles instead of restating them. Stale TODO
  items superseded explicitly.

## 2026-06-28 — promotions from a real adopter

Standing-proceed; ✔/⚠ verified-vs-relayed tagging; adversarial multi-lens audit; `/uatplan-goodbehavior` + UAT template.

## 2026-06-23 — adopt learns deploy ≠ run-locally ≠ verify-target

Adopt analyzes and confirms the three dev-workflow facets separately; flags push-to-branch = deploy; captures the
verify URL.
