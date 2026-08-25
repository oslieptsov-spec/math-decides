"""The gate: input in, receipt out. No language model is involved here.

The receipt is produced before any explainer exists and does not depend on
one. That ordering is the whole architecture — a model that runs after the
statuses are sealed and hashed has nothing left to decide.

Two structural choices are worth stating outright.

Untrusted free text never leaves this module. The receipt records that a
free-text field was present and commits to its content with a hash, but the
text itself is not forwarded. An injection placed in `description` therefore
cannot reach the explainer at all — not because a filter caught it, but
because nothing carries it there.

Statuses are decided by law closure alone. Values are computed only for
outputs already marked ready, so a computation can never promote an output.
"""
from . import canonical, domain, laws, schema

ENGINE = {"name": "gate", "version": "0.1.0", "receipt_schema": "1"}


def _status_of(output, declared):
    if domain.has_no_law(output):
        return "WITHHELD_NO_DECLARED_LAW", "NO_LAW_EXISTS", ()
    missing = domain.missing_laws(output, declared)
    if missing:
        return "WITHHELD_MISSING_DECLARED_LAW", "MISSING_LAW", missing
    return "COMPUTABLE_READY", "OK_CLOSED", ()


def _order_of_evaluation(names):
    """Outputs before the outputs that consume their values."""
    ordered, placed = [], set()
    remaining = list(names)
    while remaining:
        progressed = False
        for name in list(remaining):
            if all(up in placed or up not in names
                   for up in domain.upstream_outputs(name)):
                ordered.append(name)
                placed.add(name)
                remaining.remove(name)
                progressed = True
        if not progressed:                       # pragma: no cover - guarded by selfcheck
            raise ValueError(f"cyclic derivation among {remaining}")
    return ordered


def _compute(name, request, values):
    law = request["declared_laws"]
    market, order = request["market"], request["order"]
    book, mid = law["book_depth_profile"], market["mid"]
    if name == "slippage_bps":
        return laws.slippage_bps(book, mid, order["size"])
    if name == "fill_price":
        gap_frac = laws.gap_fraction(law["gap_size"], mid, book["tick_size"])
        return laws.fill_price(mid, gap_frac, values["slippage_bps"])
    if name == "liquidation_risk":
        return laws.liquidation_risk(book, law["gap_size"], law["panic_multiplier"],
                                     law["liquidation_threshold"], market, order)
    raise ValueError(f"no closed form for {name}")       # pragma: no cover


def _untrusted(request):
    present = [f for f in domain.UNTRUSTED_TEXT_FIELDS if f in request]
    return {
        "fields_present": present,
        "content_sha256": {f: canonical.sha256_of(request[f]) for f in present},
        # The gate commits to the text without carrying it forward.
        "content_forwarded": False,
    }


def evaluate(request):
    """Validate, decide statuses, compute what is closed, seal the receipt."""
    schema.validate(request)
    declared = tuple(sorted(request["declared_laws"]))
    requested = request.get("requested_outputs") or list(domain.OUTPUTS)

    outputs, values = {}, {}
    for name in _order_of_evaluation(requested):
        status, reason, missing = _status_of(name, declared)
        entry = {
            "status": status,
            "reason_code": reason,
            "reason": domain.REASON_CODES[reason][1],
            "requires": list(domain.OUTPUTS[name]["requires"]),
            "missing_laws": list(missing),
            "unit": domain.OUTPUTS[name]["unit"],
            "value": None,
        }
        # An upstream that is itself withheld withholds this output too. With
        # the current dependency map every output requires at least the laws
        # its upstreams require, so law closure already covers this and the
        # branch cannot fire; test_upstream_is_subsumed pins that invariant so
        # an adapted domain cannot lose the check silently.
        if status == "COMPUTABLE_READY":
            blocked = [up for up in domain.upstream_outputs(name)
                       if outputs.get(up, {}).get("status") != "COMPUTABLE_READY"]
            if blocked:
                entry.update(status="WITHHELD_UPSTREAM",
                             reason_code="UPSTREAM_WITHHELD",
                             reason=domain.REASON_CODES["UPSTREAM_WITHHELD"][1],
                             blocked_by=sorted(blocked))
            else:
                values[name] = _compute(name, request, values)
                entry["value"] = values[name]
        outputs[name] = entry

    body = {
        "engine": dict(ENGINE),
        "scenario": request["scenario"],
        "input_hash": canonical.sha256_of(request),
        "declared_laws": list(declared),
        "undeclared_laws": [n for n in sorted(domain.LAWS) if n not in declared],
        "outputs": {name: outputs[name] for name in sorted(outputs)},
        "untrusted_input": _untrusted(request),
    }
    body.update(domain.unlock_list(declared))
    body["unreachable_by_declaration"] = list(body["unreachable_by_declaration"])
    body["unlock"] = {k: list(v) for k, v in body["unlock"].items()}

    receipt = dict(body)
    receipt["receipt_sha"] = canonical.sha256_of(body)
    return receipt
