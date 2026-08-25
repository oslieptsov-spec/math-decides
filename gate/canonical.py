"""Canonical serialisation and hashing.

A receipt is a claim about an input, and the claim is only as stable as its
serialisation. Two structurally identical receipts must produce one hash on
any machine, so this module fixes every degree of freedom JSON leaves open:
key order, separators, non-ASCII escaping, and float precision.

Float precision is the one that actually bites. Arithmetic that differs in
the last bit — a different libm, a reordered sum — would otherwise produce a
different receipt for the same input. Values are rounded to a fixed number of
significant digits before serialisation, well below the noise floor of the
computation and well above what any explanation would ever quote.
"""
import hashlib
import json
import math

SIGNIFICANT_DIGITS = 12


def _canon_float(x):
    if math.isnan(x) or math.isinf(x):
        raise ValueError("non-finite value cannot be canonicalised")
    if x == 0.0:
        return 0.0  # collapses -0.0
    digits = SIGNIFICANT_DIGITS - 1 - math.floor(math.log10(abs(x)))
    return round(x, digits) + 0.0


def canonicalise(obj):
    """Recursively normalise a receipt-shaped structure."""
    if isinstance(obj, float):
        return _canon_float(obj)
    if isinstance(obj, bool) or obj is None or isinstance(obj, (int, str)):
        return obj
    if isinstance(obj, dict):
        return {str(k): canonicalise(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [canonicalise(v) for v in obj]
    raise TypeError(f"not canonicalisable: {type(obj).__name__}")


def dumps(obj):
    """Deterministic JSON text: sorted keys, no whitespace, ASCII-escaped."""
    return json.dumps(
        canonicalise(obj),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def sha256_of(obj):
    return hashlib.sha256(dumps(obj).encode("utf-8")).hexdigest()
