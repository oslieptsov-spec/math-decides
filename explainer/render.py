"""Deterministic fallback rendering.

When the model is unavailable, or answers something the receipt does not
support, the interface must still be useful. This module turns a receipt into
the same shape of explanation using no model at all — plainer prose, identical
facts, and no possibility of divergence.

Failing closed here means the user loses the phrasing, never the answer.
"""
REASON_TEXT = {
    "OK_CLOSED": "every required law is declared, so this one computes",
    "MISSING_LAW": "declare {laws} and this one computes",
    "NO_LAW_EXISTS": "no closing law exists for it, so no declaration releases it",
    "UPSTREAM_WITHHELD": "it depends on an output that is itself withheld",
}


def render(receipt, note="explanation unavailable — receipt stands"):
    outputs = []
    for name, entry in receipt["outputs"].items():
        reason = REASON_TEXT[entry["reason_code"]].format(
            laws=", ".join(entry["missing_laws"]))
        outputs.append({"name": name, "status": entry["status"],
                        "restated_reason": reason})

    ready = [n for n, e in receipt["outputs"].items()
             if e["status"] == "COMPUTABLE_READY"]
    withheld = [n for n in receipt["outputs"] if n not in ready]
    summary = (f"{len(ready)} of {len(receipt['outputs'])} outputs computed; "
               f"{len(withheld)} withheld.")
    return {
        "summary": summary,
        "outputs": outputs,
        "unlock": [{"output": name, "declare": list(laws)}
                   for name, laws in sorted(receipt["unlock"].items())],
        "unreachable": list(receipt["unreachable_by_declaration"]),
        # Not "which law would you declare" — the receipt says none will do.
        # The honest question is whether such a relation can be defined at all,
        # which is a change to the catalogue and not to this request. The suite
        # refuses a model that offers a way out for a lawless output; the
        # fallback must not do what a model is refused for.
        "next_questions": [
            f"Can a closing relation for {name} be defined at all, "
            f"or should it be dropped from the scope of this request?"
            for name in receipt["unreachable_by_declaration"]
        ] or ["Which of the undeclared laws can you supply?"],
        "_note": note,
    }
