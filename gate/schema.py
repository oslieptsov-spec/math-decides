"""Input validation — fail-closed.

Two properties matter more than coverage here.

Unknown keys are rejected. An input that carries a field the gate does not
understand is refused rather than ignored, so no attacker-supplied key can
ride along in the hashed input hoping some later stage reads it.

Declared laws must carry exactly their parameters — no more, no fewer. A law
is a closing relation, not a bag of hints, and an unrecognised parameter is a
claim the gate cannot honour.
"""
from . import domain

SIDES = ("buy", "sell")
MARKET_FIELDS = ("mid", "position_notional", "equity")


class InvalidInput(Exception):
    def __init__(self, errors):
        self.errors = errors
        super().__init__(f"{len(errors)} validation error(s)")

    def as_dict(self):
        return {"error": "INVALID_INPUT", "details": self.errors}


def _err(out, path, code, message):
    out.append({"path": path, "code": code, "message": message})


def _number(out, path, value, positive=True):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _err(out, path, "NOT_A_NUMBER", "expected a number")
        return False
    if positive and value <= 0:
        _err(out, path, "NOT_POSITIVE", "expected a positive number")
        return False
    return True


def _no_unknown_keys(out, path, got, allowed):
    for key in sorted(set(got) - set(allowed)):
        _err(out, f"{path}.{key}" if path else key, "UNKNOWN_FIELD",
             "field is not part of the input contract")


def validate(request):
    """Return the request unchanged, or raise InvalidInput with every error."""
    errors = []
    if not isinstance(request, dict):
        raise InvalidInput([{"path": "", "code": "NOT_AN_OBJECT",
                             "message": "the request must be a JSON object"}])

    allowed_top = ("scenario", "description", "market", "order",
                   "declared_laws", "requested_outputs")
    _no_unknown_keys(errors, "", request, allowed_top)

    if request.get("scenario") != "gap_panic_sweep":
        _err(errors, "scenario", "UNKNOWN_SCENARIO",
             "the only scenario this gate implements is 'gap_panic_sweep'")

    if "description" in request and not isinstance(request["description"], str):
        _err(errors, "description", "NOT_A_STRING", "expected a string")

    market = request.get("market")
    if not isinstance(market, dict):
        _err(errors, "market", "MISSING", "expected an object")
    else:
        _no_unknown_keys(errors, "market", market, MARKET_FIELDS)
        for field in MARKET_FIELDS:
            if field not in market:
                _err(errors, f"market.{field}", "MISSING", "required")
            else:
                _number(errors, f"market.{field}", market[field])

    order = request.get("order")
    if not isinstance(order, dict):
        _err(errors, "order", "MISSING", "expected an object")
    else:
        _no_unknown_keys(errors, "order", order, ("side", "size"))
        if order.get("side") not in SIDES:
            _err(errors, "order.side", "BAD_ENUM", f"expected one of {SIDES}")
        if "size" not in order:
            _err(errors, "order.size", "MISSING", "required")
        else:
            _number(errors, "order.size", order["size"])

    laws = request.get("declared_laws")
    if not isinstance(laws, dict):
        _err(errors, "declared_laws", "MISSING", "expected an object")
    else:
        _no_unknown_keys(errors, "declared_laws", laws, domain.LAWS)
        for name, params in sorted(laws.items()):
            if name not in domain.LAWS:
                continue
            if not isinstance(params, dict):
                _err(errors, f"declared_laws.{name}", "NOT_AN_OBJECT",
                     "a declared law carries its parameters as an object")
                continue
            expected = domain.LAWS[name]["params"]
            _no_unknown_keys(errors, f"declared_laws.{name}", params, expected)
            for param in expected:
                path = f"declared_laws.{name}.{param}"
                if param not in params:
                    _err(errors, path, "MISSING",
                         "a law must declare all of its parameters")
                else:
                    # k is a slope and is expected to be negative.
                    _number(errors, path, params[param], positive=(param != "k"))

    requested = request.get("requested_outputs")
    if requested is not None:
        if not isinstance(requested, list):
            _err(errors, "requested_outputs", "NOT_A_LIST", "expected a list")
        else:
            for i, name in enumerate(requested):
                if name not in domain.OUTPUTS:
                    _err(errors, f"requested_outputs[{i}]", "UNKNOWN_OUTPUT",
                         f"no such output: {name!r}")

    if errors:
        raise InvalidInput(sorted(errors, key=lambda e: (e["path"], e["code"])))
    return request
