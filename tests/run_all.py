#!/usr/bin/env python3
"""GoodBehavior self-test — the bundle held to its own standard: verified, not self-declared.

Runs every tests/test_*.py as a subprocess and aggregates. One command, exit 0 = green:

    python3 tests/run_all.py
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    suites = sorted(f for f in os.listdir(HERE) if f.startswith("test_") and f.endswith(".py"))
    failed = []
    for suite in suites:
        print(f"\n== {suite} ==")
        r = subprocess.run([sys.executable, os.path.join(HERE, suite)])
        if r.returncode != 0:
            failed.append(suite)
    print(f"\n{'=' * 40}")
    if failed:
        print(f"FAILED: {', '.join(failed)}")
        return 1
    print(f"all {len(suites)} suites passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
