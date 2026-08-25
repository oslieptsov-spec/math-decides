#!/usr/bin/env python3
"""Record the two data files the page serves instead of computing live.

    python3 tools/record.py

canned.json   explanations for the built-in presets, served when no key is
              configured or the daily budget is spent. The page keeps working
              and says which path answered. Recording retries until the model
              answers, because a fallback is the wrong default for a preset —
              and any rejection seen on the way is kept as its own artifact.
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


ATTEMPTS = 4
REJECTION_TRIES = 12


def main():
    canned, rejected = {}, None
    for name in sorted(examples.EXAMPLES):
        receipt = engine.evaluate(examples.load(name))
        for attempt in range(ATTEMPTS):
            result = explain.explain(receipt)
            # A refused answer is not a failure to hide: it is the frame that
            # shows the guardrail working, and it is kept the first time it
            # appears. The preset itself should still show the model at work.
            if rejected is None and result["attempts"][0]["findings"]:
                rejected = {"example": name,
                            "receipt_sha": receipt["receipt_sha"],
                            "source": result["source"],
                            "attempts": result["attempts"],
                            "explanation": result["explanation"],
                            "provenance": result["provenance"]}
                print(f"rejection captured on {name}: "
                      f"{sorted({f['code'] for f in result['attempts'][0]['findings']})}")
            if result["source"] == "model":
                break
        canned[name] = {"receipt_sha": receipt["receipt_sha"],
                        "explanation": result["explanation"],
                        "source": result["source"],
                        "attempts": result["attempts"],
                        "provenance": result["provenance"]}
        print(f"canned {name}: source={result['source']} "
              f"attempts={len(result['attempts'])}")
    # Rejections happen on roughly a third of answers, so the preset pass often
    # misses one. Fish for a real one rather than staging it: the frame is only
    # worth showing if the refusal actually happened.
    tries = 0
    while rejected is None and tries < REJECTION_TRIES:
        tries += 1
        receipt = engine.evaluate(examples.load("incomplete-laws"))
        result = explain.explain(receipt)
        if result["attempts"][0]["findings"]:
            rejected = {"example": "incomplete-laws",
                        "receipt_sha": receipt["receipt_sha"],
                        "source": result["source"],
                        "attempts": result["attempts"],
                        "explanation": result["explanation"],
                        "provenance": result["provenance"]}
            print(f"rejection captured after {tries} tries: "
                  f"{sorted({f['code'] for f in result['attempts'][0]['findings']})}")
    if rejected:
        canned["_rejected_example"] = rejected
    else:
        print(f"no rejection in {tries} tries; the recorded example is unchanged")
        previous = json.loads((WEB / "canned.json").read_text(encoding="utf-8")) \
            if (WEB / "canned.json").exists() else {}
        if previous.get("_rejected_example"):
            canned["_rejected_example"] = previous["_rejected_example"]
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
