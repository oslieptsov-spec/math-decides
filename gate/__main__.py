"""python -m gate [example] [--json]"""
import json
import sys

from . import engine, examples, schema

BAR = "-" * 72


def render(receipt):
    print(BAR)
    print(f"scenario     {receipt['scenario']}")
    print(f"declared     {', '.join(receipt['declared_laws']) or '(none)'}")
    print(f"undeclared   {', '.join(receipt['undeclared_laws']) or '(none)'}")
    print(f"input_hash   {receipt['input_hash']}")
    print(f"receipt_sha  {receipt['receipt_sha']}")
    print(BAR)
    for name, out in receipt["outputs"].items():
        value = "-" if out["value"] is None else f"{out['value']:.6f}"
        print(f"{name:<18} {out['status']:<30} {value:>14}")
        if out["missing_laws"]:
            print(f"{'':<18} missing: {', '.join(out['missing_laws'])}")
    print(BAR)
    for name, missing in receipt["unlock"].items():
        print(f"unlock {name}: declare {', '.join(missing)}")
    for name in receipt["unreachable_by_declaration"]:
        print(f"unreachable {name}: no declaration releases it")
    untrusted = receipt["untrusted_input"]
    if untrusted["fields_present"]:
        print(f"untrusted    {', '.join(untrusted['fields_present'])} "
              f"(committed by hash, not forwarded)")
    print(BAR)


def main(argv):
    name = next((a for a in argv if not a.startswith("-")), "incomplete-laws")
    try:
        receipt = engine.evaluate(examples.load(name))
    except schema.InvalidInput as exc:
        print(json.dumps(exc.as_dict(), indent=2), file=sys.stderr)
        return 2
    except KeyError as exc:
        print(exc, file=sys.stderr)
        return 2
    if "--json" in argv:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        render(receipt)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
