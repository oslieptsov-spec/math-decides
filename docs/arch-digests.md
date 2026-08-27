# Receipt digests across architectures

The reproducibility claim was scoped to one runtime and architecture because
that was all that had been run. This is the second one.

Produced by `python3 tools/arch_receipts.py` on each machine.

## darwin/arm64 · CPython 3.14.3

```
declared-laws
   input_hash   85639ef397dba19d0611ac09ea917eae5f114d0fa2867985505da2bebcec972f
   receipt_sha  19926a969678466e90114329f0b40ce9f5cada832df10cc23060db55375ea789
   fill_price         102.56760216666666
   liquidation_risk   0.44116576057707213
   slippage_bps       6.595333333335418

incomplete-laws
   input_hash   ed4e5e33a01674a7e99bef8c10e4693b738ece713b79ad347d662526417abd42
   receipt_sha  89660faf9eb45a6db0e5b40dd9c8d73239964a4a78c44172dffbfa0ab508bb64
   slippage_bps       6.595333333335418
```

## linux/x86_64 · CPython 3.12.3 · NVIDIA H100 PCIe

```
declared-laws
   input_hash   85639ef397dba19d0611ac09ea917eae5f114d0fa2867985505da2bebcec972f
   receipt_sha  19926a969678466e90114329f0b40ce9f5cada832df10cc23060db55375ea789
   fill_price         102.56760216666666
   liquidation_risk   0.44116576057707213
   slippage_bps       6.595333333335418

incomplete-laws
   input_hash   ed4e5e33a01674a7e99bef8c10e4693b738ece713b79ad347d662526417abd42
   receipt_sha  89660faf9eb45a6db0e5b40dd9c8d73239964a4a78c44172dffbfa0ab508bb64
   slippage_bps       6.595333333335418
```

## What this earns

Identical, including the raw floats behind the rounding — two architectures,
two instruction sets, two CPython versions. The claim moves from *within a
runtime and architecture* to *across the two that have been run*, which is
still a claim about what was run and not a theorem.

`make test` passes on both: 161 tests, offline, no key.

The rounding in `gate/canonical.py` is what makes this survivable: without it,
a last-bit difference anywhere in the arithmetic would have produced a
different digest, and the comparison above would have been the finding instead
of the confirmation.
