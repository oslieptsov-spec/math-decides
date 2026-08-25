#!/usr/bin/env python3
"""Record the two data files the page serves instead of computing live.

    python3 tools/record.py

canned.json   explanations for the built-in presets, served when no key is
              configured or the daily budget is spent. The page keeps working
              and says which path answered.
sabotage.json the negative-control run, recorded once and replayed. There is
              no live path that disables the post-validator, so a screenshot
              of an attack passing cannot be taken from a running deployment.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from attacks import runner
from explainer import explain
from gate import engine, examples

WEB = Path(__file__).resolve().parent.parent / "web"


def main():
    canned = {}
    for name in sorted(examples.EXAMPLES):
        receipt = engine.evaluate(examples.load(name))
        result = explain.explain(receipt)
        canned[name] = {"receipt_sha": receipt["receipt_sha"],
                        "explanation": result["explanation"],
                        "source": result["source"],
                        "attempts": result["attempts"],
                        "provenance": result["provenance"]}
        print(f"canned {name}: source={result['source']} "
              f"attempts={len(result['attempts'])}")
    (WEB / "canned.json").write_text(json.dumps(canned, indent=1), encoding="utf-8")

    sabotaged = runner.run(post_validation=False)
    summary = runner.summarise(sabotaged)
    recording = {
        "available": True,
        "watermark": "guardrail disabled — failure-mode demonstration",
        "headline": (f"{len(sabotaged) - summary['blocked']}/{len(sabotaged)} pass, "
                     f"{summary['silently_released']} silently released "
                     f"[{', '.join(summary['released_outputs'])}]"),
        "summary": summary,
        "cases": [{"id": r["id"], "title": r["title"], "surface": r["surface"],
                   "blocked": r["blocked"], "evidence": r["evidence"],
                   "silently_released": r["silently_released"]}
                  for r in sabotaged],
    }
    (WEB / "sabotage.json").write_text(json.dumps(recording, indent=1),
                                       encoding="utf-8")
    print(f"sabotage: {recording['headline']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
