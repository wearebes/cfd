# Resource policy and observed scheduler decision

Matrix ID: `20260710T172910Z`

## Machine and workload

- Apple M3, 8 CPU cores, 24 GB RAM.
- Each Basilisk matrix row is compiled and executed as a serial, single-process
  solver; no OpenMP/MPI flag is present in the recorded commands.
- User-approved hard ceiling was initially four simultaneous rows and was
  explicitly raised to five on 2026-07-11.
- Foreground-use requirement: preserve enough CPU capacity for normal daily
  work and avoid making the Mac unresponsive.

## Measured canaries

| Phase | Concurrent rows | Observed free-memory range | Outcome |
| --- | ---: | ---: | --- |
| N64, imax 0/5 extreme gate | 2 | about 56--58% | all 8 rows completed |
| N64 remaining formal rows | 3 | about 55--57% | all 14 new rows completed |
| N128 formal rows | 3 | about 55--56% | all 22 new rows completed |
| N256 heavy NN launch | 3 | about 53--55% | progressing normally |

During the N256 three-row capwave-NN group, `uptime` load averages were
observed between roughly 5 and 8.6 while memory pressure remained healthy.
The initial decision was to keep three as the routine target. The user later
explicitly chose faster completion and authorised five concurrent rows. Memory
is not the limiting resource; CPU headroom is the accepted tradeoff. The
managed environment rejected both
`taskpolicy` background QoS and positive `nice`, so concurrency is the only
reliable foreground-protection control.

## Locked production policy

- Routine target after the user's updated instruction: **5 concurrent
  single-core rows**, subject to the same live gates.
- Hard ceiling: **5**.
- Launch only on AC power.
- Do not launch a new row when `memory_pressure -Q` reports less than 30% free.
- Use longest-processing-time-first ordering within each resolution phase.
- If the user observes lag, allow active healthy rows to finish, then resume the
  next queue at two concurrent rows; do not kill progressing formal rows.
- Do not infer thermal state from memory. A sustained fall in per-row throughput
  is treated as a reason to lower the next phase's concurrency, not as a reason
  to invalidate completed physics.

This policy changes only scheduling. It does not change any row identity,
physical parameter, `imax`, resolution, method, model checkpoint, or acceptance
criterion.
