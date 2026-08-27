## A finding before the readback: the two paths do not intersect today

Checked 2026-08-27 with an NGC key valid for the registry (`docker login
nvcr.io` succeeded) and a separate key valid for the hosted catalog.

| model | hosted catalog | NIM registry |
|---|---|---|
| `nemotron-3-nano-30b-a3b` | **served** | not published |
| `nvidia-nemotron-nano-9b-v2` | HTTP 410 Gone | **pullable** |
| `llama-3.1-nemotron-nano-8b-v1` | HTTP 410 Gone | **pullable** |
| `llama-3.3-nemotron-super-49b-v1.5` | HTTP 410 Gone | **pullable** |

Every model available as a NIM image returns 410 from the hosted catalog, and
the model the demo runs on is not published as a NIM image. A same-model
comparison across the two decoders is therefore not possible today with these
credentials.

That matters twice over. It is the reason the readback below measures NIM on a
different model and says so, rather than presenting a decoder comparison it
cannot support. And it is the provenance argument arriving unprompted: three of
these models were listed as available in the catalog when this repository chose
its default, and are gone now. A provider-side change is visible in behaviour,
not in a version — which is what the acceptance rate exists to notice.

# Readback — nim on linux/x86_64

- model `nvidia/nvidia-nemotron-nano-9b-v2`
- endpoint `http://127.0.0.1:8000/v1`
- python 3.12.3

## Receipts

| example | receipt_sha | input_hash |
|---|---|---|
| `declared-laws` | `19926a969678466e90114329f0b40ce9f5cada832df10cc23060db55375ea789` | `85639ef397dba19d0611ac09ea917eae5f114d0fa2867985505da2bebcec972f` |
| `incomplete-laws` | `89660faf9eb45a6db0e5b40dd9c8d73239964a4a78c44172dffbfa0ab508bb64` | `ed4e5e33a01674a7e99bef8c10e4693b738ece713b79ad347d662526417abd42` |

Identical to the digests from darwin/arm64 on CPython 3.14 — see
[arch-digests.md](arch-digests.md). The receipt does not depend on the machine
that computed it, and it does not depend on the endpoint at all: no model runs
before it exists.

## Attack suite (offline — independent of the endpoint)

- blocked **35/35**
- silently released **0**
- unblocked: none

## What the endpoint was

```
NVIDIA H100 PCIe, 580.178.04, 72447 MiB, 81559 MiB
nvcr.io/nim/nvidia/nvidia-nemotron-nano-9b-v2:latest | Up 8 minutes
```

Guided decoding was verified directly before the run: the strict JSON schema is
honoured, `chat_template_kwargs: {"thinking": false}` is respected, and the
statuses come back echoed rather than invented. That is the claim the README
makes about structure being imposed by the decoder, checked on a decoder that
is not the hosted one.

**The build identifier is still absent.** This repository said a self-hosted NIM
would supply what the hosted catalog does not. It does not: `system_fingerprint`
came back null here too. The claim has been corrected rather than repeated —
provenance names the model, the path, the temperature and the response id, and
no build, on either path.

## Acceptance on this path

| example | accepted first try | answered by model | findings |
|---|---|---|---|
| `declared-laws` | 10/10 | 10/10 | — |
| `incomplete-laws` | 0/10 | 10/10 | `NUMBER_NOT_IN_RECEIPT`×10 |

Acceptance calibrates a model on a serving stack. It is not a ranking statistic,
and a difference between two decoders is a measurement, not a verdict on either.
The comparison here is across **different models**, for the reason stated at the
top, so it says nothing about which decoder is stricter.

### A build identifier does exist here

`system_fingerprint` is null on both paths, and that was read as no build being
available anywhere. It was wrong in the direction that matters: NIM publishes
one on its own route.

```
GET /v1/version  →  {"release": "1.12.2", "api": "3.1.0"}
```

Provenance now reads `build nim 1.12.2 (api 3.1.0)` on this path and keeps
saying `n/a (api-catalog)` on the hosted one, where no such route exists. The
absence belongs to the path, and now so does the presence.

### The zero is the interesting number

`incomplete-laws` failed its first answer ten times out of ten, always with the
same finding, and the repair attempt fixed it ten times out of ten. The number
was `6.59`.

The receipt says `6.59533333334`. At three significant digits that rounds to
`6.60`; `6.59` is a truncation. The rule refuses it, correctly — a truncation
misstates the value at the precision it claims — and the repair note is enough
to get a corrected answer every time.

Two attempts were made to fix it in the prompt before recording. The rule
already forbade rounding past two significant digits; a line was added
forbidding truncation outright, in the model's own terms and without an example
that might prime the digits. Ten runs before the rule and ten after it: `6.59`
every time, twenty first answers out of twenty. The model answered in the end
on all twenty, because the repair works.

That is the argument of this repository arriving as a measurement. A prompt is
advice; the model took it and carried on. The check is not advice, and it
caught the same habit on every first answer, on a model and a decoder neither
was written against. The cost is one extra round trip on one preset — ten
seconds instead of five — and the benefit is that nothing wrong ever reaches
the reader.

What that demonstrates is worth more than a matching acceptance rate would
have been. The post-validator was written against one model's habits on one
stack, and here it met a different model on a different decoder with a habit
the first one does not have. It caught it on the first answer, every time, and
the fallback never had to run. A check tuned to a particular model would have
let this through.

