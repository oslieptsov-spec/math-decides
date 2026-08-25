"""Closed forms for the declared laws. Textbook mathematics, synthetic data.

Every quantity here is computed twice by independent routes: once by walking
the book level by level, once algebraically. The engine uses the walk; the
test suite asserts the two agree. A single implementation checked against
itself proves nothing, which is the same reason the attack suite carries a
negative control.

None of this is a risk model. It is public arithmetic chosen so that a reader
can verify the gate's behaviour without trusting the domain.
"""
import math


class InsufficientDepth(Exception):
    """The order cannot be filled by the declared book. Fail closed."""


def level_count(d0, k):
    """Number of levels with positive size: size(i) = d0 + k*i > 0."""
    if k >= 0:
        raise ValueError("k must be negative: a linear book has to thin out")
    return int(math.ceil(d0 / -k))


def cumulative_size(d0, k, n):
    """Size available in the first n levels."""
    return n * d0 + k * n * (n - 1) / 2.0


def total_depth(d0, k):
    return cumulative_size(d0, k, level_count(d0, k))


def walk_book(d0, k, tick_size, mid, size):
    """Volume-weighted fill price, by walking the book one level at a time."""
    n_max = level_count(d0, k)
    remaining, cost = float(size), 0.0
    for i in range(n_max):
        take = min(d0 + k * i, remaining)
        cost += take * (mid + (i + 1) * tick_size)
        remaining -= take
        if remaining <= 0:
            return cost / size
    raise InsufficientDepth(
        f"order of {size} exceeds declared depth of {total_depth(d0, k)}")


def walk_book_closed_form(d0, k, tick_size, mid, size):
    """The same fill price, derived algebraically. Used only to check the walk.

    The level at which the order completes is the smaller positive root of
    cumulative_size(n) = size, a quadratic in n. The cost of the full levels
    below it is a Faulhaber sum. A +/-1 guard corrects the root for floating
    point before the sums are taken.
    """
    if size > total_depth(d0, k) + 1e-9:
        raise InsufficientDepth(
            f"order of {size} exceeds declared depth of {total_depth(d0, k)}")

    a, b, c = k / 2.0, d0 - k / 2.0, -float(size)
    disc = b * b - 4 * a * c
    roots = [r for r in ((-b + math.sqrt(disc)) / (2 * a),
                         (-b - math.sqrt(disc)) / (2 * a)) if r > 0]
    n = max(1, int(math.floor(min(roots))))
    while cumulative_size(d0, k, n) < size:
        n += 1
    while n > 0 and cumulative_size(d0, k, n - 1) >= size:
        n -= 1

    m = n - 1                                   # fully consumed levels
    s1 = m * (m + 1) / 2.0                      # sum of (i+1), i in [0, m)
    s2 = m * (m - 1) / 2.0                      # sum of i
    s3 = (m - 1) * m * (2 * m - 1) / 6.0 + s2   # sum of i*(i+1)
    cost = (m * d0 * mid + d0 * tick_size * s1
            + k * mid * s2 + k * tick_size * s3)
    cost += (size - cumulative_size(d0, k, m)) * (mid + (m + 1) * tick_size)
    return cost / size


def slippage_bps(book, mid, size):
    """Execution slippage against the mid, in basis points."""
    vwap = walk_book(book["d0"], book["k"], book["tick_size"], mid, size)
    return (vwap - mid) / mid * 1e4


def gap_fraction(gap, mid, tick_size):
    return gap["gap_ticks"] * tick_size / mid


def fill_price(mid, gap_frac, slip_bps):
    return mid * (1.0 + gap_frac) * (1.0 + slip_bps / 1e4)


def liquidation_risk(book, gap, panic, threshold, market, order):
    """Share of the margin buffer consumed by a panic-swept adverse move.

    The sweep executes the order amplified by the panic multiplier. Gap and
    the swept slippage are both taken as adverse. The result is the fraction
    of the move that the remaining buffer cannot absorb, clipped to [0, 1]:
    0 when the buffer covers the whole move, 1 when it is already gone.

    A sweep that exhausts the declared book returns 1.0 — the book cannot
    absorb it at any price, and a gate that fails closed reports certainty of
    liquidation rather than an unbounded number.
    """
    mid = market["mid"]
    notional, equity = market["position_notional"], market["equity"]
    swept = order["size"] * panic["m_panic"]
    try:
        slip = slippage_bps(book, mid, swept) / 1e4
    except InsufficientDepth:
        return 1.0
    adverse = gap_fraction(gap, mid, book["tick_size"]) + slip
    if adverse <= 0:
        return 0.0
    buffer = (equity - notional * adverse) / notional - threshold["maintenance_margin"]
    return min(1.0, max(0.0, 1.0 - buffer / adverse))
