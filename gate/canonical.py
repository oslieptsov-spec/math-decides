"""Canonical serialisation and hashing.

A receipt is a claim about an input, and the claim is only as stable as its
serialisation. Two structurally identical receipts must produce one hash on
any machine, so this module fixes every degree of freedom JSON leaves open:
key order, separators, non-ASCII escaping, and float precision.

The claim this buys is scoped, and the scope is what has been run: receipts are
reproducible bit for bit across processes, hash seeds, two architectures and two
CPython versions (docs/arch-digests.md). The rounding is what makes that
survivable — without it a last-bit difference anywhere in the arithmetic would
have produced a different digest. tools/arch_receipts.py emits the digests for
a third machine.

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


def _canon_number(x):
    """One representation per number, whatever spelling it arrived in.

    JSON has a single number type, and 100 and 100.0 are the same number. They
    were not the same receipt: a request typed in the browser serialises 100.0
    as 100, and the gate hashed a different document than the one Python built
    from the same preset. Two digests for one logical input is the failure this
    module exists to prevent, so an integral value now renders as an integer
    from either side.
    """
    if isinstance(x, int):
        return x
    if math.isnan(x) or math.isinf(x):
        raise ValueError("non-finite value cannot be canonicalised")
    if x == 0.0:
        return 0  # collapses -0.0 and 0.0
    digits = SIGNIFICANT_DIGITS - 1 - math.floor(math.log10(abs(x)))
    rounded = round(x, digits) + 0.0
    return int(rounded) if rounded.is_integer() else rounded


def canonicalise(obj):
    """Recursively normalise a receipt-shaped structure."""
    if isinstance(obj, bool) or obj is None or isinstance(obj, str):
        return obj
    if isinstance(obj, (int, float)):
        return _canon_number(obj)
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
