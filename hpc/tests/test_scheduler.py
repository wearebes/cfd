from __future__ import annotations

from pathlib import Path

import pytest

from hpc.lib.matrix import formal_rows
from hpc.lib.scheduler import (
    greedy_batches,
    load_policy,
    parse_lscpu_p,
    phase_rows,
    release_cpus,
    take_cpus,
    threads_for,
)


ROOT = Path(__file__).resolve().parents[2]


def policy():
    return load_policy(ROOT / "hpc/config/thread_policy.json")[0]


def test_phase_counts_and_stationary_boundary() -> None:
    rows = formal_rows()
    assert len(phase_rows(rows, "n64")) == 48
    remaining = phase_rows(rows, "remaining")
    assert len(remaining) == 132
    assert not any(
        row.benchmark == "stationary_bubble" and row.resolution == 512
        for row in remaining
    )


def test_lpt_order_is_deterministic() -> None:
    rows = formal_rows()
    first = [row.row_id for row in phase_rows(rows, "remaining")]
    second = [row.row_id for row in phase_rows(reversed(rows), "remaining")]
    assert first == second


def test_greedy_batches_never_oversubscribe() -> None:
    selected = phase_rows(formal_rows(), "all")
    loaded = policy()
    batches = greedy_batches(selected, loaded, 128)
    assert sum(len(batch) for batch in batches) == 180
    for batch in batches:
        assert sum(threads_for(row, loaded) for row in batch) <= 128


def test_cpu_allocations_are_disjoint_and_reusable() -> None:
    free = list(range(16))
    first = take_cpus(free, 8)
    second = take_cpus(free, 8)
    assert first is not None and second is not None
    assert set(first).isdisjoint(second)
    assert free == []
    release_cpus(free, first)
    assert free == list(range(8))
    assert take_cpus(free, 4) == [0, 1, 2, 3]


def test_policy_has_every_row_and_rejects_too_small_pool() -> None:
    loaded = policy()
    assert all(threads_for(row, loaded) > 0 for row in formal_rows())
    with pytest.raises(ValueError, match="more CPUs"):
        greedy_batches(phase_rows(formal_rows(), "remaining"), loaded, 32)


def test_lscpu_order_prefers_one_thread_per_core_and_numa_order() -> None:
    text = """# CPU,Core,Socket,Node
0,0,0,0
4,0,0,0
1,1,0,0
5,1,0,0
2,2,1,1
6,2,1,1
3,3,1,1
7,3,1,1
"""
    assert parse_lscpu_p(text) == [0, 1, 2, 3, 4, 5, 6, 7]
    assert parse_lscpu_p(text, {0, 2, 4, 6}) == [0, 2, 4, 6]
