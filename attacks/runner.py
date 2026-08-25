"""Execution of the suite, with and without the guardrail.

The headline number of an adversarial suite is usually how many attacks were
blocked, which is the easy half. The number that carries evidence is the other
one: how many outputs reached a consumer marked ready that the receipt does not
mark ready. It is published on every run, and it is zero — a zero that means
something only because `--sabotage` shows what the same suite produces when the
post-validator is removed.

Nothing here reaches the network. Model attacks are delivered through a fake
transport, so the suite runs on a laptop with no key and no GPU.
"""
import copy
import json

from explainer import client, explain, render, validate
from gate import canonical, engine, examples, schema

from . import cases


def _offline_config():
    config = client.Config()
    config.api_key = "offline-suite"
    return config


def _fake_response(payload):
    content = payload if isinstance(payload, str) else json.dumps(payload)
    return {"id": "chatcmpl-attack", "model": "fake/adversarial",
            "usage": {"completion_tokens": 0},
            "choices": [{"message": {"content": content}}]}


def _released(statuses, receipt):
    """Outputs presented as ready that the receipt does not mark ready."""
    return sorted(name for name, status in statuses.items()
                  if status == "COMPUTABLE_READY"
                  and receipt["outputs"].get(name, {}).get("status")
                  != "COMPUTABLE_READY")


def run_input_case(case):
    """A crafted request. Either the schema refuses it, or it is inert."""
    baseline = engine.evaluate(examples.load(case["example"]))
    request = examples.load(case["example"])
    case["mutate"](request)
    try:
        receipt = engine.evaluate(request)
    except schema.InvalidInput as exc:
        return {"observed": "schema", "blocked": True,
                "evidence": sorted({e["code"] for e in exc.errors}),
                "silently_released": []}

    statuses = {name: entry["status"] for name, entry in receipt["outputs"].items()}
    released = _released(statuses, baseline)
    serialised = canonical.dumps(receipt)
    leaked = case.get("marker") and case["marker"] in serialised
    evidence = []
    if case.get("marker"):
        evidence.append("payload absent from receipt" if not leaked
                        else "PAYLOAD PRESENT IN RECEIPT")
    evidence.append("statuses identical to the clean run" if not released
                    else "STATUSES MOVED")
    return {"observed": "structure", "blocked": not released and not leaked,
            "evidence": evidence, "silently_released": released}


def run_model_case(case, post_validation=True):
    """An adversarial answer, delivered through a fake transport."""
    receipt = engine.evaluate(examples.load(case["example"]))
    payload = case["mutate"](copy.deepcopy(render.render(receipt)))

    original = validate.validate
    if not post_validation:
        validate.validate = lambda answer, receipt: []
    try:
        result = explain.explain(receipt, config=_offline_config(),
                                 transport=lambda body: _fake_response(payload))
    finally:
        validate.validate = original

    answer = result["explanation"]
    statuses = {entry["name"]: entry["status"] for entry in answer.get("outputs", [])}
    released = _released(statuses, receipt)
    codes = sorted({finding["code"] for attempt in result["attempts"]
                    for finding in attempt["findings"]})
    return {"observed": "post-validator" if codes else "none",
            "blocked": result["source"] == "template",
            "evidence": codes or ["answer served unchecked"],
            "silently_released": released,
            "receipt_sha": result["receipt_sha"]}


def run(post_validation=True, mark_releases=None):
    """Every case. Input cases are unaffected by the guardrail switch.

    `mark_releases` carries the ids that silently release under the negative
    control, so the guarded table can point at them. A case that is blocked
    today and would release without the validator is the one worth reading.
    """
    results = []
    for case in cases.ALL_CASES:
        if case["surface"] == "input":
            outcome = run_input_case(case)
        else:
            outcome = run_model_case(case, post_validation=post_validation)
        results.append({k: case[k] for k in ("id", "title", "surface", "expected")}
                       | {"note": case.get("note"),
                          "releases_without_guardrail": case["id"] in (mark_releases or ())}
                       | outcome)
    return results


def releasing_ids(sabotaged):
    """Cases that put a withheld output in front of a consumer as ready."""
    return {r["id"] for r in sabotaged if r["silently_released"]}


def summarise(results):
    released = [name for r in results for name in r["silently_released"]]
    return {
        "cases": len(results),
        "blocked": sum(1 for r in results if r["blocked"]),
        "input_cases": sum(1 for r in results if r["surface"] == "input"),
        "model_cases": sum(1 for r in results if r["surface"] == "model"),
        "silently_released": len(released),
        "released_outputs": sorted(set(released)),
    }
