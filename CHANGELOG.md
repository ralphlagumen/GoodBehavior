# Changelog

Every entry here is a unit a downstream project will 3-way-merge via `/update-goodbehavior` — write entries so an
adopter skimming before an update knows what's coming and why.

## 2026-10-12 — devops profile: guides, guard, security and cost

A fifth core profile for infrastructure work, cloud or on-prem, with guides that pair every rule with a live probe
and a guard that lets investigation run but stops changes and secret leaks.

**Profile** (`templates/profiles/devops.md`)
- The real thing is the live environment read back from the provider; verify by applying to non-prod (with the
  user's yes), probing from the consumer's position, and re-planning for no changes; evidence names the environment
  and account.
- Every infrastructure change, in any environment, waits for the user's yes. Before asking: what was found, the exact
  change, why it fixes it, what could break, how to undo it, where it runs, and what it does to the bill. Investigate
  read-only first. Talk in plain words to someone who isn't an infra expert.
- Cost in every proposal (now, change, saving, performance and risk, way back); size from 14+ days of real use.
- Secrets go in a gitignored `.secret` file (mode 600); `.env` and `.secret` are never read. Keeping `AWS_PROFILE`
  and similar in `.env` is suggested, not required.
- Audit lenses: wiring, security (judged against automated attacks; each finding states risk, how likely, impact,
  fix, evidence), reliability, drift, cost. A cluster with no secrets manager gets an OpenBao suggestion.
- Done-gate questions for changes (environment, every destroy/replace, saved plan, no-change re-plan, consent) and
  for investigations (observed vs inferred, live state, alternatives ruled out, propose don't apply).

**Guides** (`templates/profiles/devops/`, installed only when they match: `"devops/<guide>"` in the install plan)
- `baseline`: IaC and state, CI/CD, secrets and identity, networking, security and attack surface, observability,
  backup/DR (restore-tested), cost.
- Tools: `terraform`, `shell`, `kubernetes` (kubeconfig at gitignored `files/kubeconfig`, cluster attack surface,
  OpenBao), `helm`. Platforms: `aws`, `azure`, `gcp`, `digitalocean`, `onprem`.
- Corrections to common advice, each tested: S3 state locking uses `use_lockfile` (`dynamodb_table` is deprecated);
  `set -e` alone misses pipeline failures and unset variables; never clean up with `rm -rf /tmp/*`;
  `openssl s_client -tls1_1` needs `-cipher 'DEFAULT@SECLEVEL=0'` on OpenSSL 3+; Pod Security `enforce` rejects Pods
  but only warns about Deployments; an Azure VM that is "stopped" but not deallocated is still billed; a powered-off
  DigitalOcean droplet is billed in full, and a managed database with no trusted sources is open to everyone.

**Guard** (`templates/profiles/devops/guard.py`)
- `done-gate.py` hands every tool call to it (PreToolUse, matcher `*`, wired only for devops). Other profiles
  (development, analysis, research, creative) see no change: no PreToolUse wiring, the generic Stop-hook messages,
  no guard log. It parses each command (quotes, variables,
  `$(...)`, heredocs, pipes, `cd`) and reads what it would run: `make` recipes, scripts and their functions and
  sourced files, package scripts, inline Python.
- **Runs:** reads, plans, tests, scans, dry runs, local git and docker, SSM and ssh tunnels, ssh commands that only
  read. **Asks:** anything that changes something or can't be shown safe, including edits to `.claude/`. **Denies:**
  anything that would show a secret (credential files, `.env`/`.secret`, secret-manager and token commands, state
  dumps, `files/kubeconfig`).
- Fails closed on a crash; turns every ask into a deny when permissions are bypassed (Claude Code was seen skipping
  a hook's ask for Edit in that mode); logs every ask and deny to `.claude/goodbehavior/guard.log`.
- Without `guard.py`, `done-gate.py` falls back to a simpler text-matching guard built from the profile's gate
  sections.

**Install and update**
- `install.py` accepts `devops/<guide>` and `devops/guard.py` profile entries, wires the Stop hook for every
  profile and PreToolUse (`*`) only when a planned profile ships a guard or gate rules (today only devops), expands
  `~` in paths and keeps `updatedAt` when adding files; `update.py` expands `~` too. `adopt` asks which
  platforms and tools a project uses; `audit` points devops audits at the profile's lenses.
- **Existing adopters:** `/update-goodbehavior` updates files, not `settings.json`. Set the PreToolUse matcher for
  `done-gate.py` to `*`, add `devops/guard.py` with the install script, and add `.claude/goodbehavior/guard.log`,
  `.secret` and (for Kubernetes) `files/kubeconfig` to `.gitignore`.

**Tests and verification**
- `tests/test_guard.py` (538 guard decisions, including an adopter's hand-built bypass suite, identity-stripped),
  `test_hook.py`, `test_install.py`, `test_lint.py` (every guide rule has a probe; the invariant layer stays
  provider-neutral) and `test_guide_cli.py` (every cloud CLI command in the guides parses, offline; skipped when a
  CLI isn't installed).
- Probes were run or checked against: AWS CLI 2.36, Azure CLI 2.89, Google Cloud SDK 588, doctl 1.166, Terraform
  1.15, bash 5.3 and shellcheck, a Debian 12 container (on-prem tools, restic/borg restores), a local Kubernetes 1.35
  cluster with Helm 3.18 and OpenBao 2.7.1, and live `claude -p` sessions with and without permissions bypassed.
  Probes against real cloud accounts are not yet run.

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
