# Stationary bubble runner strict reproduction report

Date: 2026-07-12  
Case: stationary bubble CLSVOF, N64  
Generator: `cases/stationary_bubble/generate/nn.sh`  
Method: NN cell-offset curvature  
Status: PASS

## 1. Verification scope

The migrated runner was checked against five requirements:

1. default physical execution content is unchanged;
2. the new code compiles and runs;
3. smoke and formal output routing matches the repository contract;
4. repeated smoke runs are deterministic and a nondefault `imax` is effective;
5. newly generated smoke result/work artifacts are removed after this report.

## 2. Code and input identity

| Item | Result |
| --- | --- |
| Stock `integral.h` versus archived accepted smoke overlay | byte-identical |
| Migrated cell-curvature header versus source header | byte-identical |
| `imax=3` generated `two-phase-clsvof.h` versus stock | byte-identical |
| Cell-curvature header SHA-256 | `4e9509025d48dcbdf59f9407aa868321fdf54abd8129097fd17748dd78f5dc1b` |
| N64 weights SHA-256 | `c52015fbba38c58f3613d3f1627308ac78f1f25d029950781ae7b1833b347b20` |
| Stock `integral.h` SHA-256 | `234d407ac3012a9be14e91747fae10dfe0a2c4677c5ca5a8bb93ae0d3511a395` |
| Stock `two-phase-clsvof.h` SHA-256 | `c0f21472c2d6acac0bdda0a2c43602273ee35d6c111cce4a98005ff9f6dbd048` |

The stationary case adds only `STATIONARY_TAU_MAX`, defaulting to `1.0`, so short smoke runs can stop early. The complete reproduction explicitly used `STATIONARY_TAU_MAX=1.0`; all other physical definitions remain unchanged.

## 3. Complete default reproduction

Reference:

```text
experiments/stationary_clsvof_smoke/results/20260712T113747Z_nn/
```

Migrated-path reproduction used `--smoke --imax 3 --level 6 --tau-max 1.0`.

| Check | Reference | Migrated runner | Verdict |
| --- | ---: | ---: | --- |
| Time-series rows | 71,133 | 71,133 | exact |
| `La-12000-6` SHA-256 | `35893bcf...a5bcb` | `35893bcf...a5bcb` | byte-identical |
| Provider evaluations | 3,698,968 | 3,698,968 | exact |
| Clamp hits | 0 | 0 | exact |
| Denominator guard hits | 0 | 0 | exact |
| Minimum absolute denominator | 0.9809494798605789 | 0.9809494798605789 | exact |
| Maximum `abs(d/h)` | 0.48796347089887804 | 0.48796347089887804 | exact |

All summary fields were exactly equal after excluding the intentionally changed mode label (`nn_64` versus `nn`). The final provider-stat line and physical error line were also byte-identical.

## 4. Repeated short smoke and `imax` effectiveness

Two independent `imax=3`, `tau_max=0.002` runs produced:

| Check | Run A | Run B | Verdict |
| --- | ---: | ---: | --- |
| Samples | 143 | 143 | exact |
| Time-series SHA-256 | `6e76e373...087fa` | `6e76e373...087fa` | byte-identical |
| Summary CSV | same bytes | same bytes | byte-identical |

The `imax=2`, `tau_max=0.002` smoke produced:

| Metric | `imax=3` | `imax=2` |
| --- | ---: | ---: |
| Samples | 143 | 143 |
| `u_star_max` | 0.00848024 | 0.00705572 |
| `ca_max` | 7.741364568429349e-05 | 6.440961672400583e-05 |
| Time-series SHA-256 | `6e76e373...087fa` | `c4880681...e263` |

The generated local header contains `redistance(d, imax = 2, ...)`, proving the parameter is applied to the executed solver path rather than only recorded in metadata.

These short values are smoke diagnostics and are not formal scientific conclusions about the optimal `imax`.

## 5. Output routing

Actual smoke runs published only under:

```text
tem/stationary_bubble/nn/try_*
```

Formal route checks returned:

```text
imax=3 -> dataset/stationary_bubble/nn_matched/N0064
imax=2 -> dataset/stationary_bubble/nondefault_redistance/imax_2/N0064
```

No formal dataset files were created during smoke verification. Existing output targets are rejected rather than overwritten. During execution, work is isolated under `tem/stationary_bubble/_work`; the visible smoke directory is published only after solver and summary completion.

## 6. Independent tests

| Test group | Result |
| --- | --- |
| C raw27 golden vector and C/PyTorch forward parity | 2 passed |
| Cell-offset formula, active mode, and integral overlay | 6 passed |
| Redistance overlay for `imax=0..5` and provenance | 11 passed |
| Total | 19 passed |

An initial combined pytest invocation from the repository root produced a collection-only import error for the redistance-local module. A second offset invocation from its experiment directory likewise lacked the repository package root. Neither invocation entered test logic. Running each suite from its authoritative working directory produced the passing results above.

## 7. Cleanup

The four newly generated smoke result directories and their four work directories are deleted after capturing this report. The historical accepted reference and earlier audit/equivalence results are not part of this cleanup.

## 8. Verdict

The migrated stationary runner preserves the complete default `imax=3` behavior byte-for-byte, executes successfully, applies nondefault `imax` values to the solver, routes smoke/formal outputs according to the new repository contract, and is deterministic across repeated short smoke runs.

This verifies the stationary N64 migration path only. It does not by itself validate capwave or rising-bubble raw27 adapters.
