"""python -m explainer [example]"""
import json
import sys

from gate import engine, examples

from . import explain


def main(argv):
    name = next((a for a in argv if not a.startswith("-")), "incomplete-laws")
    receipt = engine.evaluate(examples.load(name))
    result = explain.explain(receipt)
    if "--json" in argv:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    answer = result["explanation"]
    print("-" * 72)
    print(f"receipt {result['receipt_sha'][:32]}…")
    print(f"source  {result['source']}   attempts {len(result['attempts'])}")
    returned = result["provenance"]["returned"] or {}
    print(f"model   {returned.get('model')}   path {result['provenance']['requested']['path']}")
    print("-" * 72)
    print(answer["summary"])
    print()
    for output in answer["outputs"]:
        print(f"  {output['name']:<18} {output['status']}")
        print(f"  {'':<18} {output['restated_reason']}")
    if answer["unreachable"]:
        print(f"\n  unreachable: {', '.join(answer['unreachable'])}")
    print("\n  next:")
    for question in answer["next_questions"]:
        print(f"    - {question}")
    for attempt in result["attempts"]:
        if attempt["findings"]:
            print(f"\n  attempt {attempt['attempt']} rejected: "
                  f"{', '.join(sorted({f['code'] for f in attempt['findings']}))}")
    print("-" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
