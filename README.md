# math·decides

**AI may explain. Math decides.**

A risk engine that refuses to answer without declared assumptions — and a language
model that can explain its refusal, and can never overturn it.

The boundary is not a prompt. A deterministic gate computes what it can, refuses
what it cannot, and seals the result with a hash **before any model runs**. The
model receives that receipt and may restate it in English. It cannot change a
status, invent a number, or hand back anything the gate did not say.

[![the contrast](docs/img/contrast.png)](docs/img/contrast.png)

---

## Why this exists

Agentic systems fail the moment the model can decide. The usual answer is a
stricter prompt, then a stricter prompt again — a control that lives inside the
thing being controlled.

The answer here is older and duller: an **independent gate on the output**. The
same discipline a release gate applies to a numerical result applies to a
sentence. A schema check is a certificate, and a certificate can be formally
valid and vacuous; what makes the boundary real is a second check, against the
receipt, that the model has no way to satisfy by being persuasive.

## Quickstart

No GPU, no key, no account. Two commands:

```bash
git clone https://github.com/oslieptsov-spec/math-decides && cd math-decides
make demo
```

That runs the gate on both built-in examples and prints two receipts. Everything
below except the model's prose works exactly like this — offline, standard
library only, no dependencies at all.

To see the language model side, put a free
[NVIDIA API catalog](https://build.nvidia.com) key in `.env` and open the page:

```bash
echo 'NVIDIA_API_KEY=nvapi-…' > .env
make ui           # http://127.0.0.1:7690
```

Without a key the page still works: it serves recorded explanations and says so
in the mode chip. Nothing on it silently pretends to be live.

## What a receipt looks like

```
$ python3 -m gate incomplete-laws
------------------------------------------------------------------------
scenario     gap_panic_sweep
declared     book_depth_profile
undeclared   gap_size, liquidation_threshold, panic_multiplier
input_hash   9be18156139fb95fdc775640ea15f4bd6073d2cb1a6c163b41e30b9e3457788a
receipt_sha  7f78e8f6f6611e19fa679a195c1a285515744b1dda6e679e6952f258bbb49adb
------------------------------------------------------------------------
defensive_factor   WITHHELD_NO_DECLARED_LAW                    -
fill_price         WITHHELD_MISSING_DECLARED_LAW               -
                   missing: gap_size
liquidation_risk   WITHHELD_MISSING_DECLARED_LAW               -
                   missing: gap_size, panic_multiplier, liquidation_threshold
slippage_bps       COMPUTABLE_READY                     6.595333
------------------------------------------------------------------------
unlock fill_price: declare gap_size
unlock liquidation_risk: declare gap_size, panic_multiplier, liquidation_threshold
unreachable defensive_factor: no declaration releases it
untrusted    description (committed by hash, not forwarded)
------------------------------------------------------------------------
```

Read it like a store receipt: every line is a computed number or a refusal with
its reason printed. Two refusals here can be fixed by declaring a law. One
cannot: `defensive_factor` has **no closing relation at all**, so no declaration
releases it — the difference between *missing declaration*, which the caller can
fix, and *out of scope*, which nobody can.

Declare every law that exists and the first two compute. `defensive_factor` stays
refused. That is the whole argument in one screen.

## The boundary, in three walls

| wall | what it means | can it be switched off? |
|------|---------------|--------------------------|
| **structure** | No path exists. Free text in the request is committed to by hash and never carried into the prompt, so an instruction hidden in it has nothing to travel on. Nothing was filtered. | no |
| **schema** | Refused at the door. Unknown fields are rejected rather than ignored; the answer's shape is pinned by the decoder. | no |
| **post-validator** | The answer was well-formed and disagreed with the receipt. Statuses are compared, every number must trace back, reasons must belong to the output they sit beside. | **yes — and that is the point** |

Only the third is a check rather than an absence. So the suite is built to prove
it earns its place.

## The attack suite

```
$ python3 -m attacks
  cases              35 (19 input, 16 model)
  blocked            35/35
  silently released  0
```

Blocking counts successes, which is the easy half. The number that carries
evidence is the second one: **outputs presented to a consumer as ready that the
receipt does not mark ready — zero.**

A zero means nothing on its own, so the same suite runs with the post-validator
removed:

```
$ python3 -m attacks --sabotage
  blocked            20/35
  silently released  2  ['defensive_factor']
```

[![the negative control](docs/img/negative-control.png)](docs/img/negative-control.png)

Fifteen attacks reach the consumer, and two of them put the output no law can
release in front of the reader as ready. A test that never fails proves nothing;
this is the control that makes the zero mean something.

Sabotage runs locally and in CI only. It is never a live switch on a deployment —
a screenshot of an attack passing, stripped of its context, argues the opposite
of what it demonstrates.

The full table, generated by the suite and never written by hand:
**[attacks/RESULTS.md](attacks/RESULTS.md)**.

## When the model is refused

[![a refused answer](docs/img/refused-answer.png)](docs/img/refused-answer.png)

A rejected answer is not an error state to be hidden. One repair attempt is made
with the findings; if the answer is refused again, a deterministic renderer
answers instead and says so: *explanation unavailable — receipt stands*. The
reader loses the phrasing, never the answer.

## What is proven here, and what is not claimed

Four different claims are routinely conflated when someone says a system "was
tested". They are kept apart here.

| claim | status |
|-------|--------|
| The receipt is reproducible bit for bit for the same input | **proven by test**, and verified across two architectures: darwin/arm64 on CPython 3.14 and linux/x86_64 on CPython 3.12 produce identical digests ([docs/arch-digests.md](docs/arch-digests.md)). A claim about what was run, not a theorem about every machine. |
| The model cannot change a status | **structural.** The receipt is computed and hashed before the model is called, and the interface renders statuses from the receipt. There is no path, so there is nothing to filter. |
| These 35 attacks are stopped | **measured on this suite.** Evidence that these are stopped, not proof that an unlisted one would be. |
| The explanation is correct | **not claimed.** What is checked is agreement with the receipt on statuses, numbers, unlock lists and reason attribution. Prose can be true, checked, and still unhelpful; this repository does not claim otherwise. |

## Acceptance rate

Measured on `nvidia/nemotron-3-nano-30b-a3b` through the API catalog, ten runs
per example: **20 of 20 answers accepted on the first attempt.**
`tools/calibrate.py` reports it.

That figure was 13 of 20 until the prompt stopped printing the status codes it
forbids. Naming a forbidden literal to a model is how it reaches the next
answer, and the repair note was echoing whichever one had slipped — a refusal
re-priming the failure it reported. Rejections still happen; the recorded
example the demo replays is a real one, and the fallback path is exercised,
not decorative.

This number calibrates *a model on a serving stack*. It is **not** a ranking
statistic and must not be read as one — a different model on a different decoder
is a different measurement, not a better or worse model. It has to be re-run
against a self-hosted NIM for the same reason: guided decoding there is not the
hosted endpoint's.

## How it is built

[DOCS.md](DOCS.md) is the implementation companion: the order of operations, the
receipt's canonical form and the scope of its reproducibility claim, the full
post-validation contract, the number-admission rules with their documented
limits, provenance, and a list of what is not claimed.

## Adapt it to your domain

The domain is one file: [`gate/domain.py`](gate/domain.py). Four laws, four
outputs, and an explicit map from each output to the laws that close it. Change
that map and you have your own gate — the engine, the receipt, the explainer
contract and the attack suite follow without edits.

One convention is worth keeping: give yourself an output with **no** closing
relation. It costs nothing, and it is the case that separates a system that
refuses honestly from one that quietly obliges.

`gate/domain.py` self-checks its own consistency, and
`test_upstream_is_subsumed` pins the containment the engine relies on, so an
adapted domain fails loudly rather than silently.

## Running it on NVIDIA NIM

The hosted API catalog and a self-hosted [NIM](https://build.nvidia.com) speak
the same OpenAI-compatible interface, so the same client reaches both:

```bash
NVIDIA_BASE_URL=http://<your-nim>:8000/v1 make ui
```

`tools/readback.py` runs the same checks against that endpoint and writes a
report — receipts, the offline suite, and acceptance with its findings — so
that agreement between two decoders is recorded rather than assumed
([docs/H100.md](docs/H100.md) is the session runbook).

The mode chip on the page names which path answered, and provenance is recorded
per answer: model, build, temperature, path. Neither path supplies a build
identifier — measured on both — so a provider-side model update is visible in
behaviour rather than in a version, which is exactly what the acceptance rate
above is for. It happened during this project: three Nemotron models listed in
the catalog when the default was chosen now return 410 Gone
([docs/readback.md](docs/readback.md)).

## Reproducing everything

```bash
make test         # 163 tests, offline, no key required
make attacks      # the suite
make sabotage     # the negative control
make results      # regenerate attacks/RESULTS.md
make calibrate    # acceptance rate (needs a key)
```

The test suite runs with no key and no network. The live check is opt-in
(`RUN_LIVE=1`).

## Licence

Code: **MIT** — see [LICENSE](LICENSE).

The model is not distributed here. Nemotron is used through NVIDIA's endpoints
under the **NVIDIA Open Model License**; check its terms before shipping
anything built on it.

## Inspiration

The release-gate discipline this pattern borrows — a conjunctive fail-closed
gate, a named reason for every non-release, and a published count of results
released despite a failed check — comes from prior work on fail-closed release
gates for numerical claims: *Slieptsov (2026), "Fail-Closed Release Gates for
Numerical Operator Claims"*, [SSRN](https://ssrn.com/abstract=6893318).

The idea that a gate which has never blocked anything is untested policy is
taken from there, and is the reason `--sabotage` exists.
