"""Orchestration: ask, verify, repair once, otherwise fall back.

The order is the point. The receipt exists before the call and is unchanged by
it; the model's answer is admitted only after it has been checked against that
receipt; and when it is refused twice the deterministic renderer answers
instead. At no point does an answer influence a status.
"""
import datetime
import json

from gate import canonical

from . import client, render, schema, validate

MAX_ATTEMPTS = 2


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


REPAIR_HINTS = {
    "STATUS_LITERAL_IN_PROSE":
        "Write the status in English in prose fields; the code belongs only in "
        "the status field.",
    "NUMBER_NOT_IN_RECEIPT":
        "Quote only numbers the receipt carries, rounded to no fewer than two "
        "significant digits.",
    "UNLOCK_FOR_LAWLESS_OUTPUT":
        "That output has no closing relation; do not offer laws for it.",
}


def _detail(finding):
    """Findings quote what was wrong — except the token that must not be echoed.

    Naming a forbidden literal back to the model is how it ends up in the next
    answer: the repair note was re-priming the very failure it reported.
    """
    if finding["code"] != "STATUS_LITERAL_IN_PROSE":
        return finding["detail"]
    return "a raw status code appears in a prose field; paraphrase it instead"


def repair_prompt(findings):
    lines = "\n".join(f"- {f['code']}: {_detail(f)}" for f in findings)
    hints = sorted({REPAIR_HINTS[f["code"]] for f in findings
                    if f["code"] in REPAIR_HINTS})
    guidance = ("\n" + "\n".join(hints)) if hints else ""
    return ("Your previous answer was rejected against the receipt:\n"
            f"{lines}{guidance}\n"
            "Answer again using only what the receipt states.")


def explain(receipt, config=None, transport=None):
    """Return an explanation bound to the receipt, however it was produced.

    `transport` takes a request body and returns a raw response, so the whole
    path can be exercised offline in tests.
    """
    config = config or client.Config()
    send = transport or (lambda body: client.post(config, body))
    receipt_json = canonical.dumps(receipt)
    messages = [{"role": "system", "content": schema.SYSTEM_PROMPT},
                {"role": "user", "content": schema.user_prompt(receipt_json)}]

    def probe(mode):
        body = client.build_body(
            config, [{"role": "user", "content": "ok"}],
            schema.explanation_schema(list(receipt["outputs"])), mode)
        body["max_tokens"] = 1
        send(body)

    mode = client.schema_mode(config, probe)
    attempts, provenance = [], None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        record = {"attempt": attempt}
        try:
            body = client.build_body(
                config, messages,
                schema.explanation_schema(list(receipt["outputs"])), mode)
            content, provenance = client.extract(send(body))
            provenance["build"] = (provenance.get("system_fingerprint")
                                   or client.probe_build(config))
            provenance["structured_output"] = mode
        except client.TransportError as exc:
            record["findings"] = [{"code": "TRANSPORT_ERROR", "detail": str(exc)}]
            attempts.append(record)
            break
        try:
            answer = json.loads(content) if content else None
        except json.JSONDecodeError as exc:
            answer = None
            record["parse_error"] = str(exc)
        if answer is None:
            record["findings"] = [{"code": "EMPTY_OR_UNPARSEABLE_ANSWER",
                                   "detail": f"{len(content)} characters returned"}]
            attempts.append(record)
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user",
                             "content": repair_prompt(record["findings"])})
            continue

        findings = validate.validate(answer, receipt)
        record["findings"] = findings
        attempts.append(record)
        if not findings:
            return _result(answer, receipt, config, provenance, attempts, "model")
        messages.append({"role": "assistant", "content": content})
        messages.append({"role": "user", "content": repair_prompt(findings)})

    fallback = render.render(receipt)
    return _result(fallback, receipt, config, provenance, attempts, "template")


def _note(provenance):
    """What can honestly be said about identifying the thing that answered.

    A hosted endpoint returns a model name and nothing that pins the build, so
    an update on the provider side shows up in behaviour rather than in a
    version. A self-hosted NIM publishes its build, and saying otherwise on
    that path would be a claim about the run that the run contradicts.
    """
    build = (provenance or {}).get("build")
    if build:
        return (f"answered by {build}; the explanation is still bound to the "
                "receipt rather than trusted for its own sake")
    return ("the endpoint supplies no build identifier; a provider-side "
            "model update is visible in behaviour, not in a version")


def _result(explanation, receipt, config, provenance, attempts, source):
    return {
        "explanation": explanation,
        "source": source,
        "receipt_sha": receipt["receipt_sha"],
        "attempts": attempts,
        "provenance": {
            "requested": config.redacted(),
            "returned": provenance,
            "generated_at": _now(),
            # The explanation is bound to a receipt, not reproducible from it.
            "reproducible": False,
            "note": _note(provenance),
        },
    }
