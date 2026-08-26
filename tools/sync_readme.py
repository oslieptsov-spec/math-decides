#!/usr/bin/env python3
"""Bring the README's test count back in line with the suite.

The count is worth stating and worth checking, but keeping it current by hand
has now failed three times in a row — twice caught by its own guard, once
pushed past it. So the number gets a command instead of a habit.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    total = sum(len(re.findall(r"^    def test_", p.read_text(encoding="utf-8"), re.M))
                for p in sorted((ROOT / "tests").glob("test_*.py")))
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    updated = re.sub(r"make test(\s+)# \d+ tests", rf"make test\g<1># {total} tests", text)
    if updated == text:
        print(f"already current: {total} tests")
        return 0
    readme.write_text(updated, encoding="utf-8")
    print(f"README updated: {total} tests")
    return 0


if __name__ == "__main__":
    sys.exit(main())
