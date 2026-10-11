#!/usr/bin/env python3
"""done-gate.py behavior tests — drive the hook as a real subprocess with synthetic transcripts.

Each case builds a JSONL transcript (human turn -> assistant tool uses -> final assistant text),
pipes the Stop-hook stdin JSON, and asserts the exit code (0 = stop allowed, 2 = blocked) and,
when blocked, which message fired (bare-claim vs hollow-proof)."""
import json, os, shutil, subprocess, sys, tempfile

HOOK = os.path.join(os.path.dirname(__file__), "..", ".claude", "hooks", "done-gate.py")
DEVOPS = os.path.join(os.path.dirname(__file__), "..", "templates", "profiles", "devops.md")


def entry_human(text):
    return {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]}}


def entry_tool(name, tool_input=None):
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "name": name, "input": tool_input or {}}]}}


def entry_text(text):
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "text", "text": text}]}}


def run_hook(tools, final_text, stop_hook_active=False, project_dir=""):
    entries = [entry_human("please do the task")]
    entries += [entry_tool(n, i) for n, i in tools]
    entries.append(entry_text(final_text))
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")
        path = f.name
    try:
        env = dict(os.environ, CLAUDE_PROJECT_DIR=project_dir)  # hermetic: never the caller's project
        r = subprocess.run([sys.executable, HOOK], env=env,
                           input=json.dumps({"transcript_path": path,
                                             "stop_hook_active": stop_hook_active}),
                           capture_output=True, text=True)
        return r.returncode, r.stderr
    finally:
        os.unlink(path)


EDIT_CODE = ("Edit", {"file_path": "src/app.py"})
EDIT_DOC = ("Edit", {"file_path": "README.md"})
BASH = ("Bash", {"command": "pytest -q"})
BROWSER = ("mcp__browser__navigate", {"url": "http://localhost:3000"})

CASES = [
    # (label, tools, final_text, expect_exit, expect_msg_fragment_or_None)
    ("discussion turn, bare claim -> allowed (activity gate)",
     [], "Done. The feature is complete.", 0, None),
    ("edited code, bare 'Done.' -> blocked (no evidence)",
     [EDIT_CODE], "Done. The feature is complete.", 2, "claimed completion"),
    ("edited code, 'verified' but ran NOTHING -> blocked (hollow proof)",
     [EDIT_CODE], "Done — I verified it works.", 2, "ran/observed NOTHING"),
    ("'confirmed' cheat with zero observation -> blocked (hollow proof)",
     [EDIT_CODE], "Complete. I confirm everything is correct.", 2, "ran/observed NOTHING"),
    ("edit then bash, 'tests pass' -> allowed (proof backed by behavior)",
     [EDIT_CODE, BASH], "Done — I ran the tests and they pass.", 0, None),
    ("bash BEFORE last edit, 'verified' -> blocked (final state never observed)",
     [BASH, EDIT_CODE], "Done — verified earlier, all good to go.", 2, "ran/observed NOTHING"),
    ("edit then browser drive, 'verified' -> allowed (browser counts as observing)",
     [EDIT_CODE, BROWSER], "Done — verified in the browser.", 0, None),
    ("doc-only edit, 'verified' -> allowed (nothing to run for prose)",
     [EDIT_DOC], "Done — reworded the section, verified the links.", 0, None),
    ("doc-only edit, bare 'Done.' -> still blocked (lexical layer holds)",
     [EDIT_DOC], "Done. All finished.", 2, "claimed completion"),
    ("honest hedge -> always allowed",
     [EDIT_CODE], "The code is written but not yet verified live.", 0, None),
    ("hedge with completion word -> allowed (honesty never punished)",
     [EDIT_CODE], "Done with the edits, but this is unverified — needs a live run.", 0, None),
    ("bash-only turn, 'confirmed' -> allowed (execution is itself observation)",
     [BASH], "Done — migration ran, confirmed row counts.", 0, None),
    ("meta discussion about the gate -> allowed",
     [EDIT_CODE], "The done-gate is now stricter. Done.", 0, None),
    ("stop_hook_active guard -> allowed (no loop)",
     [EDIT_CODE], "Done. The feature is complete.", 0, None),
]


EDIT_TF = ("Edit", {"file_path": "infra/main.tf"})
TF_APPLY = ("Bash", {"command": "terraform apply tfplan"})
TF_PLAN = ("Bash", {"command": "terraform plan -detailed-exitcode"})
READ_PROBE = ("Bash", {"command": "nc -zv db.internal 5432"})

# devops profile installed: the profile's own questions replace the generic self-check
DEVOPS_CASES = [
    ("devops: edited .tf, bare 'Done.' -> change questions",
     [EDIT_TF], "Done. The VPC is updated.", 2, "read the whole plan"),
    ("devops: bash-only apply, bare claim -> change questions (match: command)",
     [TF_APPLY], "Applied. All done.", 2, "saved, reviewed plan file"),
    ("devops: read-only probes, 'root cause' claim -> investigation questions",
     [READ_PROBE], "The root cause is the security group.", 2, "which are inference"),
    ("devops: read-only plan run, 'done' -> investigation (plan is not a change)",
     [TF_PLAN], "Done. Nothing to change.", 2, "symptom"),
    ("devops: investigation backed by an observation -> allowed",
     [READ_PROBE], "Root cause: port 5432 blocked, confirmed with nc.", 0, None),
    ("devops: edited .tf, 'verified' with nothing run -> hollow proof + change questions",
     [EDIT_TF], "Done — verified.", 2, "Also answer (change)"),
    ("devops: honest hedge -> allowed",
     [EDIT_TF], "The plan is written but not yet applied.", 0, None),
]


# guard (PreToolUse): with devops installed, commands that change infrastructure must ask the user first
GUARD_ASK = [
    "terraform apply tfplan", "terraform -chdir=infra apply", "tofu destroy -auto-approve",
    "terraform state rm aws_instance.x", "terraform import aws_s3_bucket.b b", "pulumi up",
    "aws ec2 terminate-instances --instance-ids i-1", "aws s3 rm s3://b/k", "aws iam attach-role-policy --role-name r",
    "aws cloudformation deploy --template t", "aws rds modify-db-instance --db-instance-identifier d",
    "az group delete -n rg", "az vm deallocate -g rg -n vm", "az network nsg rule create -g rg",
    "az deployment group create -g rg", "gcloud compute instances delete vm", "gcloud run deploy svc",
    "gcloud projects add-iam-policy-binding p", "doctl compute droplet delete 123", "doctl kubernetes cluster create c",
    "kubectl apply -f x.yaml", "kubectl -n prod delete pod p", "kubectl rollout restart deploy/x",
    "kubectl scale deploy/x --replicas=0", "helm upgrade app chart", "ansible-playbook site.yml",
    "sudo systemctl restart nginx", "ssh host sudo reboot",
]
GUARD_PASS = [
    "terraform plan -out tfplan", "terraform show tfplan", "terraform state list", "terraform validate",
    "aws ec2 describe-instances", "aws s3 ls", "aws sts get-caller-identity", "az vm list",
    "az network nsg rule list -g rg --nsg-name n", "az account show", "gcloud compute instances list",
    "doctl compute droplet list", "kubectl get pods", "kubectl describe pod p", "kubectl logs p", "helm list",
    "ansible-playbook site.yml --check --diff", "dig +short x", "curl -sI https://x", "git status", "pytest -q",
]


def run_guard(command, project_dir):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=project_dir)
    r = subprocess.run([sys.executable, HOOK], env=env, capture_output=True, text=True,
                       input=json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash",
                                         "tool_input": {"command": command}}))
    out = json.loads(r.stdout) if r.stdout.strip() else {}
    return r.returncode, out.get("hookSpecificOutput", {}).get("permissionDecision", "pass")


def main():
    failures = 0
    profile_dir = tempfile.mkdtemp()
    os.makedirs(os.path.join(profile_dir, ".claude", "goodbehavior", "profiles"))
    shutil.copy(DEVOPS, os.path.join(profile_dir, ".claude", "goodbehavior", "profiles", "devops.md"))
    cases = [c + ("",) for c in CASES] + [c + (profile_dir,) for c in DEVOPS_CASES]
    for i, (label, tools, text, want_exit, want_frag, pdir) in enumerate(cases):
        active = "stop_hook_active" in label
        code, err = run_hook(tools, text, stop_hook_active=active, project_dir=pdir)
        ok = code == want_exit and (want_frag is None or want_frag in err)
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
        if not ok:
            failures += 1
            print(f"        expected exit={want_exit} frag={want_frag!r}; got exit={code} stderr={err[:200]!r}")
    empty_dir = tempfile.mkdtemp()
    guard_cases = ([(c, profile_dir, "ask") for c in GUARD_ASK] + [(c, profile_dir, "pass") for c in GUARD_PASS]
                   + [("terraform apply tfplan", empty_dir, "pass")])  # no profile match: lines -> no-op
    guard_bad = []
    for command, pdir, want in guard_cases:
        code, got = run_guard(command, pdir)
        if code != 0 or got != want:
            guard_bad.append(f"{command!r}: want {want}, got {got} (exit {code})")
    print(f"  {'PASS' if not guard_bad else 'FAIL'}  guard: {len(guard_cases)} commands decided correctly")
    for b in guard_bad:
        print(f"        {b}")
    failures += bool(guard_bad)
    cases += [None]
    shutil.rmtree(profile_dir, ignore_errors=True)
    shutil.rmtree(empty_dir, ignore_errors=True)
    print(f"test_hook: {len(cases) - failures}/{len(cases)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
