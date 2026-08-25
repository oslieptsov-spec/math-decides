#!/usr/bin/env python3
"""Emit receipt digests for cross-architecture comparison.

Run on each architecture and compare the output. Digest equality across
architectures is expected — every operation behind these numbers is IEEE-754
and the canonical rounding is explicit — but expected is not verified, and the
repository claims only what it has run. This is the instrument that turns the
expectation into evidence, or into a finding.

    python3 tools/arch_receipts.py
"""
import platform
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gate import engine, examples


def main():
    print(f"platform   {platform.system().lower()}/{platform.machine()}")
    print(f"python     {platform.python_version()}")
    print()
    for name in sorted(examples.EXAMPLES):
        receipt = engine.evaluate(examples.load(name))
        print(f"{name}")
        print(f"   input_hash   {receipt['input_hash']}")
        print(f"   receipt_sha  {receipt['receipt_sha']}")
        for output, entry in receipt["outputs"].items():
            if entry["value"] is not None:
                print(f"   {output:<18} {entry['value']!r}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
