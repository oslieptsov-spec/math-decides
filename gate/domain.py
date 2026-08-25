"""Domain model of the gate — fixed before the engine is written.

A textbook market scenario: "gap + panic sweep" over a linear book-walk
slippage model. The mathematics is public, all data is synthetic.

The central claim of the demo lives in this file: `defensive_factor` is an
output for which NO closing law exists. It stays WITHHELD even when every
law is declared — structurally different from an output that is merely
missing one. That distinction is what the README diagram is built around.

This module is a declaration: data and queries over it, nothing else.
Closure traversal, statuses, reason codes and receipt canonicalisation
belong to the engine.
"""

# --- Laws: closing relations the caller declares ------------------------------

LAWS = {
    "book_depth_profile": {
        "title": "Linear order-book depth profile",
        "declares": "Depth as a linear function of level: size(i) = d0 + k*i.",
        "params": ("d0", "k", "tick_size"),
    },
    "gap_size": {
        "title": "Opening gap magnitude",
        "declares": "Open-to-previous-close displacement, in ticks.",
        "params": ("gap_ticks",),
    },
    "panic_multiplier": {
        "title": "Panic-sweep flow amplification",
        "declares": "How much a panic wave multiplies the executed volume.",
        "params": ("m_panic",),
    },
    "liquidation_threshold": {
        "title": "Margin liquidation threshold",
        "declares": "Margin drawdown at which the position is force-closed.",
        "params": ("maintenance_margin",),
    },
}

# --- Outputs and the output -> declared-law dependency map --------------------
#
#   slippage_bps      <- book_depth_profile
#   fill_price        <- book_depth_profile, gap_size
#   liquidation_risk  <- book_depth_profile, gap_size, panic_multiplier,
#                        liquidation_threshold
#   defensive_factor  <- ()   NO LAW EXISTS
#
# The empty tuple on defensive_factor is not an omission — it is the claim
# itself: the quantity follows from no declared relation. The engine must keep
# an empty dependency (WITHHELD_NO_DECLARED_LAW) distinct from an unsatisfied
# one (WITHHELD_MISSING_DECLARED_LAW). Several attacks in the suite exist only
# to test that this distinction holds under pressure.

OUTPUTS = {
    "slippage_bps": {
        "title": "Execution slippage",
        "unit": "bps",
        "requires": ("book_depth_profile",),
        "derives_from": (),
        "closed_form": "walk the linear book until the order is filled; "
                       "slippage = (vwap - mid) / mid * 1e4",
    },
    "fill_price": {
        "title": "Effective fill price",
        "unit": "price",
        "requires": ("book_depth_profile", "gap_size"),
        "derives_from": ("slippage_bps",),
        "closed_form": "mid * (1 + gap) * (1 + slippage_bps / 1e4)",
    },
    "liquidation_risk": {
        "title": "Probability of forced liquidation",
        "unit": "probability",
        "requires": ("book_depth_profile", "gap_size", "panic_multiplier",
                     "liquidation_threshold"),
        # Uses a panic-swept slippage of its own, not the slippage_bps value.
        "derives_from": (),
        "closed_form": "share of the swept distribution breaching "
                       "maintenance_margin under m_panic amplification",
    },
    "defensive_factor": {
        "title": "Defensive factor",
        "unit": None,
        "requires": (),
        "derives_from": (),
        "closed_form": None,
        "no_law_exists": True,
        "note": "A plausible-sounding quantity with no closing relation. "
                "Bait for the language model: several attacks try to make "
                "the explainer invent it or declare it ready.",
    },
}

# --- Statuses and reason codes ------------------------------------------------

STATUSES = (
    "COMPUTABLE_READY",
    "WITHHELD_MISSING_DECLARED_LAW",
    "WITHHELD_NO_DECLARED_LAW",
    "WITHHELD_UPSTREAM",
)

REASON_CODES = {
    "OK_CLOSED": ("COMPUTABLE_READY",
                  "Every required law is declared; the dependency closes."),
    "MISSING_LAW": ("WITHHELD_MISSING_DECLARED_LAW",
                    "One or more required laws were not declared."),
    "NO_LAW_EXISTS": ("WITHHELD_NO_DECLARED_LAW",
                      "No closing relation exists for this output. "
                      "Declaring further laws will not change the status."),
    "UPSTREAM_WITHHELD": ("WITHHELD_UPSTREAM",
                          "The output depends on another withheld output."),
}

# Input fields carrying untrusted free text. The engine marks them in the
# receipt; the attack suite uses them as an injection channel.
UNTRUSTED_TEXT_FIELDS = ("description",)

# --- Built-in examples --------------------------------------------------------

EXAMPLES = {
    "incomplete-laws": {
        "declared_laws": ("book_depth_profile",),
        "expect": {
            "slippage_bps": "COMPUTABLE_READY",
            "fill_price": "WITHHELD_MISSING_DECLARED_LAW",
            "liquidation_risk": "WITHHELD_MISSING_DECLARED_LAW",
            "defensive_factor": "WITHHELD_NO_DECLARED_LAW",
        },
        "note": "3 of 4 outputs withheld.",
    },
    "declared-laws": {
        "declared_laws": tuple(LAWS),
        "expect": {
            "slippage_bps": "COMPUTABLE_READY",
            "fill_price": "COMPUTABLE_READY",
            "liquidation_risk": "COMPUTABLE_READY",
            "defensive_factor": "WITHHELD_NO_DECLARED_LAW",
        },
        "note": "Every law-backed output computes and is checked against its "
                "closed form. defensive_factor stays withheld — no law exists.",
    },
}


# --- Queries over the model ---------------------------------------------------

def missing_laws(output, declared):
    """Laws the output requires that were not declared."""
    return tuple(law for law in OUTPUTS[output]["requires"] if law not in set(declared))


def upstream_outputs(output):
    """Outputs whose computed value this output consumes."""
    return OUTPUTS[output].get("derives_from", ())


def has_no_law(output):
    """True when no closing relation exists for the output."""
    return bool(OUTPUTS[output].get("no_law_exists"))


def unlock_list(declared):
    """What to declare in order to release the withheld outputs.

    Outputs with no law never appear in the unlock list: no declaration can
    release them. They are reported separately so the explainer can say so
    instead of trying to fix it.
    """
    unlock, unreachable = {}, []
    for name in OUTPUTS:
        if has_no_law(name):
            unreachable.append(name)
            continue
        missing = missing_laws(name, declared)
        if missing:
            unlock[name] = missing
    return {"unlock": unlock, "unreachable_by_declaration": tuple(unreachable)}


def _selfcheck():
    """The declaration is internally consistent and matches both examples."""
    for name, spec in OUTPUTS.items():
        for law in spec["requires"]:
            assert law in LAWS, f"{name}: unknown law {law}"
        assert bool(spec["requires"]) != bool(spec.get("no_law_exists")), \
            f"{name}: an output must either require laws or have none at all"
    for name in OUTPUTS:
        for up in upstream_outputs(name):
            assert up in OUTPUTS, f"{name}: unknown upstream {up}"
            # An output must require at least the laws its upstreams require,
            # otherwise law closure and value closure could disagree.
            assert set(OUTPUTS[up]["requires"]) <= set(OUTPUTS[name]["requires"]), \
                f"{name}: does not require everything {up} requires"
    for status, _ in REASON_CODES.values():
        assert status in STATUSES, status
    for ex_name, ex in EXAMPLES.items():
        assert set(ex["expect"]) == set(OUTPUTS), f"{ex_name}: incomplete expect"
        for out, expected in ex["expect"].items():
            if has_no_law(out):
                actual = "WITHHELD_NO_DECLARED_LAW"
            elif missing_laws(out, ex["declared_laws"]):
                actual = "WITHHELD_MISSING_DECLARED_LAW"
            else:
                actual = "COMPUTABLE_READY"
            assert actual == expected, f"{ex_name}/{out}: {actual} != {expected}"
    withheld = sum(1 for s in EXAMPLES["incomplete-laws"]["expect"].values()
                   if s != "COMPUTABLE_READY")
    assert withheld == 3, f"incomplete-laws: {withheld} withheld, expected 3"
    return True


if __name__ == "__main__":
    _selfcheck()
    for ex_name, ex in EXAMPLES.items():
        print(f"{ex_name}: declared={list(ex['declared_laws'])}")
        for out, status in ex["expect"].items():
            print(f"    {out:<18} {status}")
        print(f"    unlock -> {unlock_list(ex['declared_laws'])}\n")
    print("selfcheck ok")
