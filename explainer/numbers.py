"""Number admission — the fail-closed half of the post-validation contract.

Every number appearing in the model's prose must trace back to a number in the
receipt. The difficulty is that one receipt number has many honest spellings:
6.595333 bps is also 6.6, also 0.00066 as a fraction, also 0.066%. A permissive
rule would let an invented figure through under cover of formatting; a rigid one
would reject correct prose for rounding.

The rule here is explicit rather than clever:

  * every receipt number generates a family of admissible values through a
    declared unit map — nothing is converted by guesswork;
  * comparison is decimal text at a stated precision, never a tolerance. An
    epsilon loose enough to absorb arithmetic noise is also loose enough to
    absorb a wrong final digit, so there is no epsilon here at all;
  * a written number is admitted when it agrees with a family member at the
    receipt's own precision, or when rounding that member to exactly as many
    significant digits as were written reproduces it;
  * rounding to a single significant digit is refused unless the value is exact,
    so 6.595333 may be quoted as 6.6, never as 7;
  * anything this routine cannot parse is refused rather than skipped. An
    unrecognised format is a rejection, not a pass.

Cardinals written as words are mapped to digits and checked like any other
number. Leaving them unmapped would have been worse than refusing them: an
unmatched word is invisible to a regex, so "two outputs are withheld" would pass
a check it never underwent.

The limits are real and documented rather than hidden. A ratio, an ordinal, or a
locale that separates decimals with a comma is refused even when the underlying
claim is true. And admission is membership, not comprehension: a count that is
wrong for this sentence but right somewhere else in the receipt is admitted. The
admissible set is kept deliberately small for exactly that reason.
"""
import math
import re

from gate import canonical

MIN_SIGNIFICANT_DIGITS_FOR_ROUNDING = 2
RECEIPT_PRECISION = canonical.SIGNIFICANT_DIGITS

# A candidate number: optional sign, digits with optional thousands separators,
# optional fraction, optional exponent, optional percent sign.
_TOKEN = re.compile(r"[-+]?\d[\d,  ]*(?:\.\d+)?(?:[eE][-+]?\d+)?%?")
_THOUSANDS = re.compile(r"^\d{1,3}(?:[,  ]\d{3})+$")

# Cardinals a model reaches for when counting outputs. Mapped, not ignored.
WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}
_WORD = re.compile(r"\b(" + "|".join(WORD_NUMBERS) + r")\b", re.IGNORECASE)

# How a unit may legitimately be re-expressed. Anything not listed here is not
# converted at all, which keeps the admissible set small and inspectable.
UNIT_FORMS = {
    "bps": (1.0, 1e-4, 1e-2),      # basis points, fraction, percent
    "probability": (1.0, 1e2),     # fraction, percent
    "price": (1.0,),
    None: (1.0,),
}


class UnparseableNumber(ValueError):
    """A numeric token that cannot be read. Refused, never ignored."""


def significant_digits(token):
    """Significant digits as written, so that 6.60 is three and 0.44 is two."""
    body = token.lstrip("+-").rstrip("%").split("e")[0].split("E")[0]
    digits = body.replace(".", "").lstrip("0")
    return len(digits) if digits else 1


def parse_token(token):
    """A written token as a float, or UnparseableNumber."""
    raw = token.rstrip("%")
    sign, raw = (raw[0], raw[1:]) if raw[:1] in "+-" else ("", raw)
    if any(sep in raw for sep in (",", " ", " ")):
        if not _THOUSANDS.match(raw.split(".")[0]):
            raise UnparseableNumber(token)
        raw = re.sub(r"[,  ]", "", raw)
    try:
        return float(sign + raw)
    except ValueError as exc:                       # pragma: no cover - regex guards
        raise UnparseableNumber(token) from exc


def round_significant(value, digits):
    if value == 0.0:
        return 0.0
    exponent = math.floor(math.log10(abs(value)))
    return round(value, digits - 1 - exponent)


def at_precision(value, digits):
    """Decimal text at a given significant precision, for exact comparison."""
    return f"{value:.{max(1, digits)}g}"


def admissible_values(receipt):
    """Every value the prose is allowed to quote, with its unit conversions."""
    values = set()
    for entry in receipt["outputs"].values():
        if entry["value"] is None:
            continue
        for factor in UNIT_FORMS.get(entry["unit"], (1.0,)):
            # The receipt the model was handed carries canonicalised numbers, so
            # those — not the raw floats behind them — are what prose may quote.
            values.add(float(canonical._canon_number(entry["value"] * factor)))

    # Structural counts, kept to the few a summary actually needs. Every extra
    # count widens the admissible set and lets a wrong claim borrow a right
    # number: dependency lengths used to be here, and they were what admitted
    # "two outputs are withheld" over a receipt withholding three.
    outputs = receipt["outputs"]
    withheld = [e for e in outputs.values() if e["status"] != "COMPUTABLE_READY"]
    for count in (len(outputs), len(withheld), len(outputs) - len(withheld),
                  len(receipt["declared_laws"]), len(receipt["undeclared_laws"])):
        values.add(float(count))
    return values


def find_tokens(text):
    """Numeric tokens as written, digits and spelled-out cardinals alike."""
    tokens = [m.group(0) for m in _TOKEN.finditer(text)]
    tokens += [str(WORD_NUMBERS[m.group(1).lower()]) for m in _WORD.finditer(text)]
    return tokens


def check(text, receipt):
    """Numbers in `text` that the receipt does not support.

    Returns a list of findings; an empty list means every number traced back.
    """
    allowed = admissible_values(receipt)
    findings = []
    for token in find_tokens(text):
        try:
            written = parse_token(token)
        except UnparseableNumber:
            findings.append({"token": token, "code": "UNPARSEABLE_NUMBER"})
            continue
        # A trailing % is stripped by parse_token; the percent reading is
        # supplied by UNIT_FORMS, so 44.1% matches a probability of 0.441166.
        digits = significant_digits(token)
        ok = False
        for base in allowed:
            if at_precision(base, RECEIPT_PRECISION) == \
                    at_precision(written, RECEIPT_PRECISION):
                ok = True
                break
            if digits < MIN_SIGNIFICANT_DIGITS_FOR_ROUNDING:
                continue
            if at_precision(base, digits) == at_precision(written, digits):
                ok = True
                break
        if not ok:
            findings.append({"token": token, "code": "NUMBER_NOT_IN_RECEIPT"})
    return findings
