"""Post-validation: does the answer say what the receipt says?

The model is never trusted to have preserved the receipt. Its answer is
compared against the receipt field by field, and any divergence rejects the
whole answer rather than patching part of it. A half-corrected explanation is
harder to reason about than none.

Note which of these checks can actually fire. Statuses cannot reach the model
except through the receipt, and untrusted text never reaches it at all, so the
prompt-injection classes are already closed upstream. What remains here is the
model's own drift: a rounded number that is not a rounding, an unlock suggested
for an output that has no law, a status echoed wrong. That is the failure mode
this file exists for, and it is the one a language model actually produces.
"""
from gate import domain

from . import numbers

REQUIRED_KEYS = ("summary", "outputs", "unlock", "unreachable", "next_questions")

# The two withheld statuses differ in the only way that matters — one is
# releasable and the other never is — and their English is what the prompt
# mandates. A sentence may use these phrasings; it may not attach one to an
# output the receipt gives the other. Confusing them in prose while echoing the
# right code in the status field is the failure this catches, and a status enum
# cannot see it.
REASON_PHRASES = {
    "WITHHELD_NO_DECLARED_LAW": (
        "no closing relation", "no closing law", "no law exists",
        "no declaration releases", "declaring further laws will not",
        "no declared law can close", "cannot be released by declaring"),
    "WITHHELD_MISSING_DECLARED_LAW": (
        "missing laws are declared", "required laws were not declared",
        "additional laws to be declared", "requires additional laws",
        "missing law", "not been declared", "were not declared",
        "until the missing"),
}


def _implied_statuses(text):
    lowered = text.lower()
    return {status for status, phrases in REASON_PHRASES.items()
            if any(phrase in lowered for phrase in phrases)}


def _check_reasons(findings, text, receipt, owner=None):
    """A reason must belong to the output it is attached to.

    With an owner — a restated_reason — the comparison is direct. Without one,
    the sentence is judged against the outputs it names: the reasons it invokes
    must all be reasons those outputs actually have.
    """
    implied = _implied_statuses(text)
    if not implied:
        return
    if owner is not None:
        actual = {receipt["outputs"][owner]["status"]}
        named = owner
    else:
        mentioned = [name for name in receipt["outputs"] if name in text]
        if not mentioned:
            return
        actual = {receipt["outputs"][name]["status"] for name in mentioned}
        named = ", ".join(mentioned)
    stray = implied - actual
    if stray:
        _finding(findings, "REASON_MISATTRIBUTED",
                 f"{named}: receipt gives {sorted(actual)}, prose argues "
                 f"{sorted(stray)} in {text[:70]!r}")


def _finding(out, code, detail):
    out.append({"code": code, "detail": detail})


def _sentences(text):
    """Rough sentence split. Clause boundaries matter less than the rule that
    every reason in a sentence must belong to some output that sentence names."""
    pieces, current = [], ""
    for char in str(text):
        current += char
        if char in ".;:\n":
            pieces.append(current)
            current = ""
    if current.strip():
        pieces.append(current)
    return [p for p in pieces if p.strip()]


def _prose(answer):
    """Every free-text string the model authored."""
    texts = [answer.get("summary", "")]
    texts += [o.get("restated_reason", "") for o in answer.get("outputs", [])
              if isinstance(o, dict)]
    texts += [q for q in answer.get("next_questions", []) if isinstance(q, str)]
    return [t for t in texts if isinstance(t, str)]


def validate(answer, receipt):
    """Findings against the receipt. Empty means the answer is accepted."""
    findings = []
    if not isinstance(answer, dict):
        return [{"code": "NOT_AN_OBJECT", "detail": type(answer).__name__}]
    for key in REQUIRED_KEYS:
        if key not in answer:
            _finding(findings, "MISSING_FIELD", key)
    if findings:
        return findings
    if not str(answer["summary"]).strip():
        _finding(findings, "EMPTY_SUMMARY", "the model returned no summary")

    # 1. Statuses, echoed and compared.
    stated = {}
    for entry in answer["outputs"]:
        name = entry.get("name")
        if name in stated:
            _finding(findings, "DUPLICATE_OUTPUT", name)
        stated[name] = entry.get("status")
    for name, expected in receipt["outputs"].items():
        if name not in stated:
            _finding(findings, "OUTPUT_OMITTED", name)
        elif stated[name] != expected["status"]:
            _finding(findings, "STATUS_MISMATCH",
                     f"{name}: receipt says {expected['status']}, "
                     f"answer says {stated[name]}")
    for name in stated:
        if name not in receipt["outputs"]:
            _finding(findings, "UNKNOWN_OUTPUT", str(name))

    # 2. The unlock list is the receipt's, not the model's idea of it.
    offered = {u.get("output"): tuple(u.get("declare") or []) for u in answer["unlock"]}
    expected_unlock = {k: tuple(v) for k, v in receipt["unlock"].items()}
    for name, laws in offered.items():
        if name not in expected_unlock:
            _finding(findings, "UNLOCK_NOT_IN_RECEIPT", str(name))
        elif set(laws) - set(expected_unlock[name]):
            _finding(findings, "UNLOCK_LAWS_INVENTED",
                     f"{name}: {sorted(set(laws) - set(expected_unlock[name]))}")
    for name in expected_unlock:
        if name not in offered:
            _finding(findings, "UNLOCK_OMITTED", name)

    # 3. An output with no law must not be offered a way out.
    unreachable = set(receipt["unreachable_by_declaration"])
    for name in unreachable & set(offered):
        _finding(findings, "UNLOCK_FOR_LAWLESS_OUTPUT", name)
    if set(answer["unreachable"]) != unreachable:
        _finding(findings, "UNREACHABLE_MISMATCH",
                 f"receipt {sorted(unreachable)}, answer {sorted(answer['unreachable'])}")

    # 4. Statuses belong in status fields. Prose that names one is rejected
    #    outright, so no reading of the sentence is required to judge it.
    for text in _prose(answer):
        for status in domain.STATUSES:
            if status in text:
                _finding(findings, "STATUS_LITERAL_IN_PROSE", f"{status} in {text[:60]!r}")

    # 5. Every number traces back to the receipt.
    for text in _prose(answer):
        for hit in numbers.check(text, receipt):
            _finding(findings, hit["code"], f"{hit['token']} in {text[:60]!r}")

    # 6. A reason belongs to the output it is attached to. The status field can
    #    be right while the sentence beside it explains a different output's
    #    predicament, and a reader believes the sentence.
    for entry in answer["outputs"]:
        if entry.get("name") in receipt["outputs"]:
            for sentence in _sentences(entry.get("restated_reason", "")):
                _check_reasons(findings, sentence, receipt, owner=entry["name"])
    for text in [answer["summary"], *answer["next_questions"]]:
        if isinstance(text, str):
            for sentence in _sentences(text):
                _check_reasons(findings, sentence, receipt)

    return findings
