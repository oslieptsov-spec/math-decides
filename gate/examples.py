"""The two built-in inputs. All data is synthetic and generated here.

Both describe the same market and the same order. They differ only in how
many laws the caller is willing to declare, which is the point: the gate's
answer is a function of declared closure, not of how the request is phrased.
"""
import copy

BOOK = {"d0": 500.0, "k": -2.0, "tick_size": 0.01}
GAP = {"gap_ticks": 250.0}
PANIC = {"m_panic": 3.0}
THRESHOLD = {"maintenance_margin": 0.08}

ALL_LAWS = {
    "book_depth_profile": BOOK,
    "gap_size": GAP,
    "panic_multiplier": PANIC,
    "liquidation_threshold": THRESHOLD,
}

_BASE = {
    "scenario": "gap_panic_sweep",
    "market": {"mid": 100.0, "position_notional": 600000.0, "equity": 73200.0},
    "order": {"side": "buy", "size": 6000.0},
}

EXAMPLES = {
    "incomplete-laws": dict(
        _BASE,
        description="overnight gap, unwinding into a thinning book",
        declared_laws={"book_depth_profile": BOOK},
    ),
    "declared-laws": dict(
        _BASE,
        description="same unwind, every closing relation declared",
        declared_laws=ALL_LAWS,
    ),
}


def load(name):
    if name not in EXAMPLES:
        raise KeyError(f"unknown example {name!r}; have {sorted(EXAMPLES)}")
    return copy.deepcopy(EXAMPLES[name])
