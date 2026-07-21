from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Iterable

from hpc.lib.integrity import sha256_file
from hpc.lib.matrix import MatrixRow


def load_policy(path: Path) -> tuple[dict[str, object], str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported thread policy schema")
    if int(payload.get("cpu_pool", 0)) < 1:
        raise ValueError("thread policy cpu_pool must be positive")
    return payload, sha256_file(path)


def threads_for(row: MatrixRow, policy: dict[str, object]) -> int:
    try:
        value = int(policy["policy"][row.benchmark][str(row.resolution)])  # type: ignore[index]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"missing thread policy for {row.row_id}") from error
    if value < 1 or value > int(policy["cpu_pool"]):
        raise ValueError(f"invalid thread count for {row.row_id}: {value}")
    return value


def parse_lscpu_p(text: str, allowed: set[int] | None = None) -> list[int]:
    records: list[tuple[int, int, int, int]] = []
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split(",")
        if len(fields) < 4:
            continue
        try:
            cpu, core, socket, node = map(int, fields[:4])
        except ValueError:
            continue
        if allowed is None or cpu in allowed:
            records.append((cpu, core, socket, node))
    if not records:
        return []

    by_core: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for cpu, core, socket, node in records:
        by_core.setdefault((socket, core), []).append((cpu, node))
    primaries = []
    siblings = []
    for key in sorted(by_core, key=lambda item: (min(n for _, n in by_core[item]), *item)):
        threads = sorted(by_core[key])
        primaries.append(threads[0])
        siblings.extend(threads[1:])
    return [cpu for cpu, _ in sorted(primaries, key=lambda item: (item[1], item[0]))] + [
        cpu for cpu, _ in sorted(siblings, key=lambda item: (item[1], item[0]))
    ]


def available_cpu_ids() -> list[int]:
    try:
        affinity = set(os.sched_getaffinity(0))
    except AttributeError:
        affinity = set(range(os.cpu_count() or 1))
    try:
        completed = subprocess.run(
            ["lscpu", "-p=CPU,CORE,SOCKET,NODE"],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        completed = None
    if completed is not None and completed.returncode == 0:
        ordered = parse_lscpu_p(completed.stdout, affinity)
        if ordered:
            return ordered
    return sorted(affinity)


def estimate_cost(row: MatrixRow) -> float:
    imax_factor = {0: 0.65, 1: 0.77, 2: 0.88, 3: 1.0, 4: 1.12, 5: 1.23}[
        row.imax
    ]
    if row.benchmark == "capwave":
        base = {
            "clsvof": {64: 23, 128: 254, 256: 1800, 512: 24404},
            "nn": {
                64: 26,
                128: 207,
                256: 1917,
                512: 18587,
            },
        }[row.method][row.resolution]
    elif row.benchmark.startswith("rising_case"):
        base_case1 = {
            "clsvof": {64: 4, 128: 23, 256: 148, 512: 2925},
            "nn": {64: 8, 128: 44, 256: 281, 512: 5557},
        }[row.method][row.resolution]
        base = base_case1 * (2.0 if row.benchmark == "rising_case2" else 1.0)
    else:
        n64 = 2611 if row.method == "clsvof" else 1255
        base = n64 * (row.resolution / 64.0) ** 3.25
    return base * imax_factor


def phase_rows(rows: Iterable[MatrixRow], phase: str) -> list[MatrixRow]:
    selected = list(rows)
    if phase == "n64":
        selected = [row for row in selected if row.resolution == 64]
    elif phase == "remaining":
        selected = [row for row in selected if row.resolution != 64]
    elif phase != "all":
        raise ValueError(f"unsupported phase: {phase}")
    return sorted(selected, key=lambda row: (-estimate_cost(row), row.row_id))


def take_cpus(free_cpus: list[int], count: int) -> list[int] | None:
    if count > len(free_cpus):
        return None
    allocation = free_cpus[:count]
    del free_cpus[:count]
    return allocation


def release_cpus(free_cpus: list[int], allocation: Iterable[int]) -> None:
    free_cpus.extend(allocation)
    free_cpus.sort()


def greedy_batches(
    rows: Iterable[MatrixRow], policy: dict[str, object], cpu_pool: int
) -> list[list[MatrixRow]]:
    if cpu_pool < 1:
        raise ValueError("cpu_pool must be positive")
    batches: list[list[MatrixRow]] = []
    current: list[MatrixRow] = []
    used = 0
    for row in rows:
        threads = threads_for(row, policy)
        if threads > cpu_pool:
            raise ValueError(f"row {row.row_id} requests more CPUs than the pool")
        if current and used + threads > cpu_pool:
            batches.append(current)
            current = []
            used = 0
        current.append(row)
        used += threads
    if current:
        batches.append(current)
    return batches
