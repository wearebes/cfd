# HPC implementation audit

Status: **READY_FOR_UBUNTU_CI**

## Automated checks

| Check | Status | Evidence |
| --- | --- | --- |
| required_files | PASS | missing=[] |
| matrix_180 | PASS | rows=180 counts={'capwave': 48, 'rising_case1': 48, 'rising_case2': 48, 'stationary_bubble': 36} |
| phase_counts | PASS | n64=48 remaining=132 |
| stationary_n512_absent | PASS | generated matrix contains no stationary N512 |
| provenance_lock | PASS | mismatches=[] |
| thread_policy | PASS | policy_sha256=912344722a74e94d267a530cd5a7bfa2897387a5d78dd03811403c28df6595a5 max_threads=64 |
| bash_syntax | PASS |  |
| forbidden_runtime_patterns | PASS | {"absolute_conda_path": [], "formal_imax_0_10": [], "linux_shasum_dependency": []} |
| local_test_suite | PASS | 80 passed, 3 skipped in 11.27s |

## External release gates

- Ubuntu 22.04 GitHub Actions has not been executed in this local-only repository
- real 128-CPU host preflight/capacity canary has not been executed
- formal 180-row matrix has not been launched
