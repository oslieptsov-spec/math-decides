#!/usr/bin/env python3
"""Read or restart the public attack counter.

    python3 tools/counter.py
    python3 tools/counter.py --reset 2026-09-08 --reason "first public run"

A counter that can be quietly zeroed is decoration. Every reset is kept with the
total it discarded and the reason for it, and the page publishes the date the
surviving count runs from. Development runs are honest to keep — as long as the
date says so — and honest to discard, as long as the discard is on record.

Each increment also records what caused it. That is not bookkeeping for its own
sake: the count once stood at 33 with no way to say what had incremented it, and
a number nobody can account for is worth less than no number.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from web import server


def main(argv):
    if "--reset" in argv:
        since = argv[argv.index("--reset") + 1]
        reason = next((argv[argv.index("--reason") + 1]
                       for _ in [0] if "--reason" in argv), "unspecified")
        state = server.reset_counter(since, reason)
        print(f"counter restarted at 0, counting since {since}")
    else:
        state = server._load_counter()
    print(json.dumps(state, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
