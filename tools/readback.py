#!/usr/bin/env python3
"""Cross-rule readback: run the same checks against a second serving stack.

    python3 tools/readback.py --base-url http://nim:8000/v1 [--runs 10]

A self-hosted NIM decodes differently from the hosted catalog. Agreement
between them is therefore evidence rather than repetition — and disagreement
is a finding, not a failure to hide. This writes both into a report so the
session produces an artifact instead of a memory.

What it measures, in order of what would hurt most to lose:

1. receipt digests on this machine — the cross-architecture claim the
   repository has so far declined to make;
2. the post-validator's verdicts on the same adversarial answers, which must
   not depend on which endpoint produced them;
3. acceptance on the live path, which is a property of a model on a stack and
   is expected to differ.
"""
import argparse
import json
import platform
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from attacks import runner
from explainer import client, explain
from gate import engine, examples


def receipts():
    rows = {}
    for name in sorted(examples.EXAMPLES):
        receipt = engine.evaluate(examples.load(name))
        rows[name] = {"input_hash": receipt["input_hash"],
                      "receipt_sha": receipt["receipt_sha"],
                      "values": {k: v["value"] for k, v in receipt["outputs"].items()
                                 if v["value"] is not None}}
    return rows


def suite():
    guarded = runner.run(post_validation=True)
    summary = runner.summarise(guarded)
    return {"summary": summary,
            "columns": {r["id"]: r["observed"] for r in guarded},
            "unblocked": [r["id"] for r in guarded if not r["blocked"]]}


def acceptance(config, runs):
    out = {}
    for name in sorted(examples.EXAMPLES):
        receipt = engine.evaluate(examples.load(name))
        first, served, codes = 0, 0, {}
        for _ in range(runs):
            result = explain.explain(receipt, config=config)
            first += not result["attempts"][0]["findings"]
            served += result["source"] == "model"
            for attempt in result["attempts"]:
                for finding in attempt["findings"]:
                    codes[finding["code"]] = codes.get(finding["code"], 0) + 1
        out[name] = {"runs": runs, "accepted_first": first, "answered_by_model": served,
                     "findings": codes}
    return out


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--out", default="docs/readback.md")
    parser.add_argument("--skip-live", action="store_true")
    args = parser.parse_args(argv)

    config = client.Config(model=args.model, base_url=args.base_url)
    report = {
        "platform": f"{platform.system().lower()}/{platform.machine()}",
        "python": platform.python_version(),
        "path": config.path,
        "base_url": config.base_url,
        "model": config.model,
        "receipts": receipts(),
        "suite": suite(),
        "acceptance": None if args.skip_live else acceptance(config, args.runs),
    }

    lines = [f"# Readback — {report['path']} on {report['platform']}", "",
             f"- model `{report['model']}`", f"- endpoint `{report['base_url']}`",
             f"- python {report['python']}", "",
             "## Receipts", "", "| example | receipt_sha | input_hash |",
             "|---|---|---|"]
    for name, row in report["receipts"].items():
        lines.append(f"| `{name}` | `{row['receipt_sha']}` | `{row['input_hash']}` |")
    lines += ["", "Compare these against the digests from the other architecture. "
                  "Equality earns the claim the repository has so far declined to "
                  "make; inequality is the finding it was waiting for.", ""]

    s = report["suite"]["summary"]
    lines += ["## Attack suite (offline — independent of the endpoint)", "",
              f"- blocked **{s['blocked']}/{s['cases']}**",
              f"- silently released **{s['silently_released']}**",
              f"- unblocked: {report['suite']['unblocked'] or 'none'}", ""]

    if report["acceptance"]:
        lines += ["## Acceptance on this path", "",
                  "| example | accepted first try | answered by model | findings |",
                  "|---|---|---|---|"]
        for name, row in report["acceptance"].items():
            found = ", ".join(f"`{k}`×{v}" for k, v in sorted(row["findings"].items()))
            lines.append(f"| `{name}` | {row['accepted_first']}/{row['runs']} | "
                         f"{row['answered_by_model']}/{row['runs']} | {found or '—'} |")
        lines += ["", "Acceptance calibrates a model on a serving stack. It is not a "
                      "ranking statistic, and a difference between two decoders is a "
                      "measurement, not a verdict on either.", ""]

    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwritten {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
