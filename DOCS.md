# How the boundary is built

The README argues the case. This is the part a reader implements from: what is
in the receipt, what the post-validator checks, where each check gives up, and
which claims are scoped to what was actually run.

---

## 1. Order of operations

```
request ──▶ schema ──▶ closure ──▶ compute ──▶ canonicalise ──▶ receipt (sealed)
                                                                     │
                                                          ┌──────────┘
                                                          ▼
                                              prompt ──▶ model ──▶ answer
                                                                     │
                                                          post-validation
                                                                     │
                                              accepted ─────┬─── refused
                                                            │        │
                                                            │   repair once
                                                            │        │
                                                            │   refused again
                                                            ▼        ▼
                                                        shown    template render
```

The ordering carries the whole argument. The receipt exists, is complete, and
is hashed before a prompt is constructed. Nothing downstream writes to it.
The interface renders statuses from the receipt, never from the answer, so an
answer that disagrees is a rejected answer and not a changed status.

## 2. The domain

`gate/domain.py` declares four laws, four outputs, and a map from each output
to the laws that close it:

| output | requires |
|--------|----------|
| `slippage_bps` | `book_depth_profile` |
| `fill_price` | `book_depth_profile`, `gap_size` |
| `liquidation_risk` | `book_depth_profile`, `gap_size`, `panic_multiplier`, `liquidation_threshold` |
| `defensive_factor` | — *no closing relation exists* |

The empty requirement is not an omission. It is the claim that the quantity
follows from nothing declarable, and it produces a status of its own. Three
statuses an output can carry, and one it cannot reach:

- `COMPUTABLE_READY` — every required law is declared and the value is computed;
- `WITHHELD_MISSING_DECLARED_LAW` — declare the laws and it computes;
- `WITHHELD_NO_DECLARED_LAW` — no declaration will ever release it.

`unlock_list()` reports the second kind under a separate key, so an explainer
can say the output is unreachable instead of proposing a way to fix it.

`WITHHELD_UPSTREAM` is implemented and currently unreachable: every output
requires at least the laws its upstreams require, so law closure subsumes value
closure. `test_upstream_is_subsumed` pins that containment — an adapted domain
that breaks it fails there first, and the engine's check starts earning its
keep.

## 3. The receipt

The receipt carries statuses, reason codes, values with units, the missing-law
list per output, the unlock list, the unreachable list, the declared and
undeclared law names, `input_hash`, and `receipt_sha` over its own body.

It deliberately does **not** carry the request's free text. Untrusted fields
are recorded as present and committed to by a content hash:

```json
"untrusted_input": {
  "fields_present": ["description"],
  "content_sha256": {"description": "de22553f…"},
  "content_forwarded": false
}
```

An instruction hidden in `description` therefore cannot reach the model — not
because a filter caught it, but because nothing carries it there. This is why
the injection cases in the suite are filed under *structure* rather than under
a defence.

### Canonicalisation

A receipt is a claim about an input, and the claim is only as stable as its
serialisation. Four degrees of freedom are fixed: key order (sorted), separators
(no whitespace), non-ASCII (escaped), and float precision (12 significant
digits, `-0.0` collapsed to `0.0`).

The rounding is the one that matters. Arithmetic that differs in the last bit —
a different libm, a reordered sum — would otherwise produce a different receipt
for the same input.

**Scope of the claim.** Receipts are reproducible bit for bit across processes,
hash seeds, and — now measured rather than expected — across two architectures
and two CPython versions: darwin/arm64 on 3.14 and linux/x86_64 on 3.12 produce
identical digests, including the raw floats behind the rounding
([docs/arch-digests.md](docs/arch-digests.md)). That is a claim about the two
machines that were run, not a theorem about every machine;
`tools/arch_receipts.py` prints the digests for a third.

## 4. The post-validation contract

The model's answer is compared against the receipt, and any disagreement
refuses the whole answer. Nothing is patched: a half-corrected explanation is
harder to reason about than none.

| check | what it refuses |
|-------|-----------------|
| status echo | any output whose status differs from the receipt's, is duplicated, omitted, or unknown |
| unlock list | an unlock the receipt does not list, a law the receipt did not name for that output, or any unlock offered for an output with no closing relation |
| unreachable list | any disagreement with the receipt's own |
| status literals in prose | a status code anywhere in `summary`, `restated_reason` or `next_questions` — statuses live in the status field, which turns "did it quietly call a withheld output ready" into a string search |
| numbers | any figure that does not trace back to the receipt (§5) |
| reason attribution | a reason attached to an output the receipt gives a different one (§6) |
| law attribution | a law named beside an output that does not require it (§6) |
| release offers | a sentence that suggests an output with no closing relation could still be released — even when it names no law and offers no unlock (§6) |

Because statuses cannot reach the model except through the receipt, and
untrusted text never reaches it at all, the prompt-injection classes are closed
upstream. What remains for this contract is the model's own drift, which is the
failure a language model actually produces.

**A note on the prompt.** The instruction that forbids status codes in prose
must not print them. It once did — three codes given as examples of what to
paraphrase — and the repair note echoed whichever one had slipped, so a refusal
re-primed the failure it reported. Both attempts came back with a code in prose
and the demo fell to its template on the happy path. Neither the prompt nor a
repair note names a status code now, and a test asserts it.

**On refusal:** one repair attempt with the findings, then the deterministic
renderer answers and says so. `render.render()` satisfies the same validator it
backs up — a test asserts it.

## 5. Number admission

One receipt number has many honest spellings: `6.59533333334` bps is also
`6.6`, also `0.000659…` as a fraction, also `0.066%`. A permissive rule lets an
invented figure through under cover of formatting; a rigid one refuses correct
prose for rounding.

The rule:

1. every receipt number generates a family through a declared unit map —
   nothing is converted by guesswork:

   | unit | admissible forms |
   |------|------------------|
   | `bps` | itself, ÷10⁴ (fraction), ÷10² (percent) |
   | `probability` | itself, ×10² (percent) |
   | `price`, none | itself |

2. comparison is **decimal text at a stated precision, never a tolerance**. An
   epsilon loose enough to absorb arithmetic noise is loose enough to absorb a
   wrong final digit;
3. a written number is admitted when it agrees with a family member at the
   receipt's own precision, or when rounding that member to exactly as many
   significant digits as were written reproduces it;
4. rounding to a single significant digit is refused unless the value is exact,
   so `6.595…` may be quoted as `6.6`, never as `7`;
5. spelled-out cardinals are mapped to digits and checked like any other number.
   Leaving them unmapped is worse than refusing them: an unmatched word is
   invisible to a regex, so "two outputs are withheld" would pass a check it
   never underwent;
6. anything unparseable is refused rather than skipped.

Structural counts — total outputs, computed, withheld, declared and undeclared
laws — are admitted so that the most natural sentence in an explanation is not
refused. That set is kept deliberately small.

**Documented limits.** A ratio, an ordinal, or a locale that separates decimals
with a comma is refused even when the claim is true. And admission is
*membership, not comprehension*: a count that is wrong for its sentence but
right somewhere else in the receipt is admitted. Dependency lengths used to be
in the admissible set, and they are what once admitted "two outputs are
withheld" over a receipt withholding three.

## 6. Attribution

The two withheld statuses differ in the only way that matters — one is
releasable and the other never is — and the prompt mandates their English. So a
sentence may use those phrasings, but every reason it invokes must belong to an
output it names, and every law it names must be one that output requires.

This was found in a screenshot of a live answer, not by the suite: the status
field said `WITHHELD_MISSING_DECLARED_LAW` and the sentence beside it said no
closing relation exists. Every status echoed correctly, every number traceable,
and the prose still told the reader an output could never be released when
declaring two laws would release it. A reader believes the sentence.

A third rule covers the case both of those miss. "Are there any undeclared
laws that could enable defensive_factor?" names no law, offers no unlock, and
contradicts the receipt — it came back from a live answer on the second preset,
past every check that existed. So the check is on the act rather than the
vocabulary: a sentence naming an output with no closing relation may not talk
about declaring, unlocking, releasing or enabling it.

The true sentence uses the same words — "declaring further laws will not change
the status" — so a negation somewhere in the sentence is what separates stating
the limit from offering a way around it. That is a heuristic and is documented
as one: an unnegated sentence about a lawless output is refused even where a
reader would have understood it.

The law rule refuses a true sentence as readily as a false one: "declaring
`gap_size` will not release `defensive_factor`" is accurate and still refused,
because a lawless output has no business appearing beside a law name. Fail-closed
costs a phrasing; the alternative costs the guarantee.

## 7. Provenance

Every answer records what produced it: `model`, `build`, `temperature`, `path`,
`structure`, the response id, and whether reasoning was returned. The
explanation is **bound** to a receipt digest and is not reproducible from it —
a language model is not a deterministic function, and the page says so in its
footer.

**Build.** Neither path returns `system_fingerprint`, and it was first assumed
that no build identifier existed anywhere. A self-hosted NIM does publish one —
on `/v1/version`, not in the OpenAI-shaped response — so provenance reads
`nim 1.8.4 (api 3.1.0)` there and `n/a (api-catalog)` on the hosted path, where
no such route exists. The note under it is derived from what was obtained, not
written once and left to be wrong on the path that contradicts it.

Where no build is available, a provider-side model update is visible in
behaviour rather than in a version, which is what the acceptance rate is for:
`tools/calibrate.py` measures how often a first answer survives
post-validation, and a drop in that rate is the instrument that would notice.
It calibrates *a model on a serving stack* and is not a ranking statistic.

**Structure.** `structure` names which rung of the decoder ladder the request
actually got: `json_schema`, `nvext`, or `json_object`. A stack that refuses
the OpenAI-standard schema may still accept the identical schema through the
NIM extension, and the difference between that and bare `json_object` is not
cosmetic — see [docs/readback.md](docs/readback.md) for the run where the
weakest rung produced nine hundred tokens of whitespace. The field exists
because "structure imposed by the decoder" is a claim that has to be true of
the run it describes.

**Deployment.** `path` is measured — it follows from the endpoint that
answered. Where the process runs is not: a self-hosted NIM on a rented H100 and
one on GKE answer identically, and nothing in the API distinguishes them. So
`NIM_DEPLOYMENT` is declared by whoever starts the process, rendered as its own
token after the measured path, and says on hover that it is declared rather
than detected. A label that looked measured would be the one dishonest thing on
the page.

**Reasoning** is switched off through both switches that exist:
`chat_template_kwargs: {"thinking": false}`, which the templates that know it
read, and the line `detailed thinking off` opening the system message, which is
how the llama-nemotron family takes it. A reasoning trace is prose no schema
covers, and prose the validator does not see must not be shown; switching it
off removes the channel rather than policing it. Set only one way, a model in
that family spent its entire token budget reasoning and returned an answer of
zero characters — a switch that was set and not read.

## 8. The attack suite

Two surfaces, kept apart because one number mixing them says nothing. Input
cases go at the gate with crafted requests; model cases go at the explainer with
adversarial answers delivered through a fake transport, so the whole suite runs
offline with no key and no GPU.

Three columns, and the difference matters more than the total:

- **structure** — no path exists;
- **schema** — refused at the door, or an answer that never decoded;
- **post-validator** — well-formed and disagreeing with the receipt.

Only the third is a check rather than an absence, so the suite proves it earns
its place: with post-validation removed, exactly the cases filed under it get
through, and two of them put `defensive_factor` in front of a consumer as ready.
Four tests hold that correspondence, including one that fails if a case is filed
in a column that is not the one that stops it — a defect this suite committed
twice against itself before the test existed.

The published statistic is **silently released**: outputs presented as ready
that the receipt does not mark ready. Blocking counts successes, which is the
easy half.

## 9. Adapting the domain

Edit `gate/domain.py`. The engine, the receipt, the explainer contract and the
attack suite follow without changes:

1. name your laws and the parameters each declares;
2. name your outputs and the laws each requires;
3. keep one output with **no** closing relation — it costs nothing and it is the
   case that separates a system that refuses honestly from one that obliges;
4. run `python3 -m gate.domain` — it self-checks the declaration;
5. run `make test`.

The explainer's schema and prompt are generated from the domain, so the enum of
output names, the unlock vocabulary and the status ladder all move with it.

## 10. What is not claimed

- **Explanation correctness.** Not claimed. What is checked is agreement with
  the receipt on statuses, numbers, unlock lists and attribution. Prose can be
  true, checked, and unhelpful.
- **Attack coverage.** The suite is evidence that these attacks are stopped, not
  proof that an unlisted one would be.
- **Cross-architecture digests.** Expected, unverified, and therefore unclaimed.
- **The production kernel.** There is none here. This is a public-safe surrogate
  domain with synthetic data, built so the pattern can be read without trusting
  the domain.
- **Model quality.** The acceptance rate calibrates a pairing, not a model.

## 11. Reproducing

```bash
make test                 # offline, no key
make attacks              # the suite
make sabotage             # the negative control
make results              # regenerate attacks/RESULTS.md
make record               # refresh canned answers and the recording (needs a key)
make calibrate RUNS=10    # acceptance rate (needs a key)
python3 tools/arch_receipts.py   # digests, for comparison on a second machine
RUN_LIVE=1 python3 -m unittest tests.test_explainer.Live
```
