#!/usr/bin/env python3
"""Measure how often the explainer's first answer survives post-validation.

    python3 tools/calibrate.py [runs] [--model M] [--base-url U]

Acceptance is a property of a model on a serving stack, not of the prompt
alone, so this has to be re-run whenever either changes — notably against a
self-hosted NIM, whose guided decoding is not the hosted endpoint's. A rate
that drops after a provider-side model update is the signal the provenance
cannot give us, since the endpoint reports no build identifier.

Rejections are not failures of the demo. The receipt stands either way; what
changes is whether the caller reads the model's prose or the deterministic
rendering. This measures how often they get the former.
"""
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from explainer import client, explain
from gate import engine, examples


def main(argv):
    runs = next((int(a) for a in argv if a.isdigit()), 5)
    model = next((argv[i + 1] for i, a in enumerate(argv) if a == "--model"), None)
    base = next((argv[i + 1] for i, a in enumerate(argv) if a == "--base-url"), None)
    config = client.Config(model=model, base_url=base)

    print(f"model      {config.model}")
    print(f"path       {config.path}  ({config.base_url})")
    print(f"runs       {runs} per example\n")

    overall = collections.Counter()
    for name in examples.EXAMPLES:
        receipt = engine.evaluate(examples.load(name))
        first_pass = model_served = 0
        codes = collections.Counter()
        for _ in range(runs):
            out = explain.explain(receipt, config=config)
            first = out["attempts"][0]["findings"]
            first_pass += not first
            model_served += out["source"] == "model"
            codes.update(f["code"] for a in out["attempts"] for f in a["findings"])
        overall["first_pass"] += first_pass
        overall["model_served"] += model_served
        overall["runs"] += runs
        print(f"{name}")
        print(f"   accepted first try : {first_pass}/{runs}")
        print(f"   answered by model  : {model_served}/{runs}"
              f"   (rest fell back to the template)")
        for code, count in codes.most_common():
            print(f"   {code:<32} {count}")
        print()

    total = overall["runs"]
    print(f"overall: {overall['first_pass']}/{total} accepted first try, "
          f"{overall['model_served']}/{total} answered by the model")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
