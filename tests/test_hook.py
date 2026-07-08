#!/usr/bin/env python3
"""done-gate.py behavior tests — drive the hook as a real subprocess with synthetic transcripts.

Each case builds a JSONL transcript (human turn -> assistant tool uses -> final assistant text),
pipes the Stop-hook stdin JSON, and asserts the exit code (0 = stop allowed, 2 = blocked) and,
when blocked, which message fired (bare-claim vs hollow-proof)."""
import json, os, subprocess, sys, tempfile

HOOK = os.path.join(os.path.dirname(__file__), "..", ".claude", "hooks", "done-gate.py")


def entry_human(text):
    return {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": text}]}}


def entry_tool(name, tool_input=None):
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "name": name, "input": tool_input or {}}]}}


def entry_text(text):
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "text", "text": text}]}}


def run_hook(tools, final_text, stop_hook_active=False):
    entries = [entry_human("please do the task")]
    entries += [entry_tool(n, i) for n, i in tools]
    entries.append(entry_text(final_text))
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")
        path = f.name
    try:
        r = subprocess.run([sys.executable, HOOK],
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


def main():
    failures = 0
    for i, (label, tools, text, want_exit, want_frag) in enumerate(CASES):
        active = "stop_hook_active" in label
        code, err = run_hook(tools, text, stop_hook_active=active)
        ok = code == want_exit and (want_frag is None or want_frag in err)
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
        if not ok:
            failures += 1
            print(f"        expected exit={want_exit} frag={want_frag!r}; got exit={code} stderr={err[:200]!r}")
    print(f"test_hook: {len(CASES) - failures}/{len(CASES)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
