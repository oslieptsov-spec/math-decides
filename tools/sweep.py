#!/usr/bin/env python3
"""Denylist sweep over three surfaces: working tree, git history, file names.

    python3 tools/sweep.py             # working tree + file names
    python3 tools/sweep.py --history   # + the full git history, all refs
    python3 tools/sweep.py --staged    # staged diff only (pre-commit mode)
    python3 tools/sweep.py --email A   # check a commit author address

Media — video and screenshots — is not covered here. A terminal prompt, a
namespace or a browser tab in a screen recording leaks just as effectively,
and only a human can check that. It stays a manual item on the freeze list.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_patterns(name):
    path = ROOT / "tools" / name
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def load_allow():
    allow = []
    for line in load_patterns("allow.txt"):
        if "::" in line:
            path_part, pat = line.split("::", 1)
            allow.append((path_part.strip(), re.compile(pat.strip(), re.I)))
    return allow


def allowed(allow, path, text):
    return any(p in path and rx.search(text) for p, rx in allow)


def git(*args):
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, errors="replace"
    ).stdout


def scan_lines(rules, allow, path, text, hits):
    for n, line in enumerate(text.splitlines(), 1):
        for rx in rules:
            if rx.search(line) and not allowed(allow, path, line):
                hits.append((path, n, line.strip()[:160]))
                break


def scan_name(rules, allow, path, hits):
    if allowed(allow, path, path):
        return
    for rx in rules:
        if rx.search(path):
            hits.append((path, 0, "file name"))
            return


def main():
    mode_history = "--history" in sys.argv
    mode_staged = "--staged" in sys.argv
    mode_email = sys.argv[sys.argv.index("--email") + 1] if "--email" in sys.argv else None

    raw = load_patterns("denylist.txt")
    if not raw:
        print("sweep: the denylist is empty — nothing to check", file=sys.stderr)
        return 1
    rules = [re.compile(p, re.I) for p in raw]
    allow = load_allow()
    hits = []

    if mode_email is not None:
        for rx in rules:
            if rx.search(mode_email):
                print(f"sweep: work address <{mode_email}> in commit authorship — "
                      f"this entry is personal.", file=sys.stderr)
                return 1
        print(f"sweep ok (authorship): {mode_email}")
        return 0

    if mode_staged:
        for f in git("diff", "--cached", "--name-only").splitlines():
            if not f:
                continue
            scan_name(rules, allow, f, hits)
            scan_lines(rules, allow, f, git("show", f":{f}"), hits)
    else:
        for f in git("ls-files").splitlines():
            if not f:
                continue
            p = ROOT / f
            if not p.is_file():
                continue
            scan_name(rules, allow, f, hits)
            try:
                scan_lines(rules, allow, f, p.read_text(encoding="utf-8"), hits)
            except (UnicodeDecodeError, OSError):
                continue

        if mode_history:
            # Track the file each diff line belongs to, otherwise the allow-list
            # cannot be applied and the sweep trips over its own denylist.
            current = "<unknown>"
            for n, line in enumerate(git("log", "--all", "-p", "--no-color").splitlines(), 1):
                if line.startswith("diff --git "):
                    current = line.rsplit(" b/", 1)[-1]
                    continue
                if line.startswith(("+++", "---", "@@")) or not line.startswith(("+", "-")):
                    continue
                if allowed(allow, current, line):
                    continue
                for rx in rules:
                    if rx.search(line):
                        hits.append((f"<history> {current}", n, line.strip()[:160]))
                        break

    if hits:
        print(f"SWEEP FAILED — {len(hits)} denylist matches:\n", file=sys.stderr)
        for path, n, line in hits[:60]:
            loc = f"{path}:{n}" if n else path
            print(f"  {loc}\n      {line}", file=sys.stderr)
        if len(hits) > 60:
            print(f"  … and {len(hits) - 60} more", file=sys.stderr)
        return 1

    scope = "staged" if mode_staged else ("tree + history" if mode_history else "tree")
    print(f"sweep ok ({scope}): no matches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
