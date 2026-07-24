#!/usr/bin/env python3
"""Plan, run, and verify the canonical generate campaign."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import platform
import signal
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESOLUTIONS = (32, 64, 128, 256, 512)
IMAX_VALUES = (0, 1, 2, 3, 4, 5, 10, 15, 20)
HIGH_IMAX_VALUES = (10, 15, 20)
METHODS = ("CLSVOF", "NN")
DATASET_NAME = "vof_clsvof_nn_benchmarks_v2"
FORMAL_ROW_COUNT = 397
SMOKE_ROW_COUNT = 56
DEFAULT_POLICY = ROOT / "generate/resource_policy.linux-auto.json"
ACTIVE_PROCESS_GROUPS: set[subprocess.Popen[str]] = set()
FINAL_ROW_FILES = {
    "capwave": {"timeseries.csv", "fields.csv.gz", "run.log"},
    "rising_bubble": {
        "timeseries.csv", "interface_t3.csv.gz", "fields.csv.gz", "run.log",
    },
    "stationary_bubble": {
        "timeseries.csv", "milestones.csv", "fields.csv.gz", "run.log",
    },
    "oscillating_droplet": {
        "timeseries.csv", "fit.csv", "fields.csv.gz", "run.log",
    },
}


def cgroup_cpu_quota(
    v2_path: Path | None = None,
    v1_quota_path: Path | None = None,
    v1_period_path: Path | None = None,
) -> int | None:
    """Return the integer CPU quota for the current Linux cgroup, if any."""
    v2_path = v2_path or Path("/sys/fs/cgroup/cpu.max")
    try:
        quota, period = v2_path.read_text(encoding="utf-8").split()[:2]
        if quota != "max":
            return max(1, int(quota) // int(period))
    except (OSError, ValueError):
        pass
    locations = (
        ((v1_quota_path, v1_period_path),)
        if v1_quota_path is not None and v1_period_path is not None
        else (
            (
                Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us"),
                Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us"),
            ),
            (
                Path("/sys/fs/cgroup/cpu,cpuacct/cpu.cfs_quota_us"),
                Path("/sys/fs/cgroup/cpu,cpuacct/cpu.cfs_period_us"),
            ),
        )
    )
    for quota_path, period_path in locations:
        assert quota_path is not None and period_path is not None
        try:
            quota = int(quota_path.read_text(encoding="utf-8").strip())
            period = int(period_path.read_text(encoding="utf-8").strip())
            if quota >= 0:
                return max(1, quota // period)
        except (OSError, ValueError, ZeroDivisionError):
            pass
    return None


def available_logical_cpus() -> int:
    """Return CPUs available to this process, respecting affinity and cgroup quota."""
    affinity = (
        len(os.sched_getaffinity(0))
        if hasattr(os, "sched_getaffinity")
        else (os.cpu_count() or 1)
    )
    quota = cgroup_cpu_quota()
    return max(1, min(affinity, quota) if quota is not None else affinity)


def configured_qcc() -> Path:
    return Path(
        os.environ.get("BASILISK_QCC", str(ROOT / "basilisk/src/qcc"))
    ).resolve()


def host_record() -> dict[str, object]:
    qcc = configured_qcc()
    logical_cpus = available_logical_cpus()
    return {
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "logical_cpus": logical_cpus,
        "linux_distribution": (
            platform.freedesktop_os_release().get("PRETTY_NAME")
            if platform.system() == "Linux"
            else None
        ),
        "python": sys.version.split()[0],
        "python_executable": str(Path(sys.executable).resolve()),
        "qcc": str(qcc),
        "qcc_sha256": sha256(qcc) if qcc.is_file() else None,
        "cc99": os.environ.get("CC99"),
    }


def load_resource_policy(path: Path | None = None) -> dict[str, object]:
    source = (path or DEFAULT_POLICY).resolve()
    if not source.is_file():
        raise ValueError(f"missing resource policy: {source}")
    policy = json.loads(source.read_text(encoding="utf-8"))
    if policy.get("schema_version") != 1:
        raise ValueError("resource policy schema_version must be 1")
    configured_slots = policy.get("cpu_slots")
    if configured_slots == "auto":
        cpu_slots = available_logical_cpus()
    elif isinstance(configured_slots, int) and configured_slots > 0:
        cpu_slots = configured_slots
    else:
        raise ValueError("resource policy cpu_slots must be 'auto' or a positive integer")
    policy["cpu_slots_config"] = configured_slots
    policy["cpu_slots"] = cpu_slots
    policy["detected_logical_cpus"] = available_logical_cpus()
    configured_compile_slots = policy.get("compile_slots")
    if not isinstance(configured_compile_slots, int) or configured_compile_slots < 1:
        raise ValueError("resource policy compile_slots must be a positive integer")
    policy["compile_slots_config"] = configured_compile_slots
    policy["compile_slots"] = min(configured_compile_slots, cpu_slots)
    if policy.get("vof_hf_threads") != 1:
        raise ValueError("VOF-HF must remain single-threaded")
    raw_threads = policy.get("threads_per_row")
    if not isinstance(raw_threads, dict):
        raise ValueError("resource policy lacks threads_per_row")
    expected = {str(resolution) for resolution in RESOLUTIONS}
    if set(raw_threads) != expected:
        raise ValueError(f"threads_per_row keys must be {sorted(expected)}")
    for resolution, threads in raw_threads.items():
        if not isinstance(threads, int) or threads < 1:
            raise ValueError(
                f"invalid threads_per_row[{resolution}]={threads!r}"
            )
    policy["policy_path"] = str(source)
    policy["policy_sha256"] = sha256(source)
    return policy


def row_threads(row: "CampaignRow", policy: dict[str, object]) -> int:
    if isinstance(row, VOFHFRow):
        return 1
    threads = policy["threads_per_row"]
    assert isinstance(threads, dict)
    return min(int(threads[str(row.resolution)]), int(policy["cpu_slots"]))


def verify_execution_host(policy: dict[str, object]) -> None:
    contract = policy.get("host_contract")
    if not isinstance(contract, dict) or contract.get("environment") != "Linux":
        raise ValueError("resource policy must declare a Linux host")
    if platform.system() != "Linux":
        raise ValueError(
            "solver execution requires Linux; "
            "layout, check and plan remain available on this machine"
        )
    qcc = configured_qcc()
    if not qcc.is_file() or not os.access(qcc, os.X_OK):
        raise ValueError("Linux qcc is missing; run generate/setup_linux.sh --install")


def terminate_process_groups(
    processes: list[subprocess.Popen[str]], grace_seconds: float = 5.0
) -> None:
    """Stop campaign-owned process groups after an interrupt or exception.

    Each compiler/runner is launched as a new session, so this also reaches
    qcc, shell and solver grandchildren instead of orphaning expensive jobs.
    """
    live = [process for process in processes if process.poll() is None]
    for process in live:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + grace_seconds
    while live and time.monotonic() < deadline:
        live = [process for process in live if process.poll() is None]
        if live:
            time.sleep(0.05)
    for process in live:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    for process in processes:
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            pass


def interrupt_on_termination(signum: int, _frame: object) -> None:
    """Route terminal shutdown through the normal campaign cleanup path."""
    raise KeyboardInterrupt(f"received signal {signum}")


def scheduler_order(
    rows: list[tuple[int, "CampaignRow"]], policy: dict[str, object]
) -> list[tuple[int, "CampaignRow"]]:
    """Order rows for slot packing while keeping high-resolution tail full.

    Single-threaded VOF-HF rows enter early as backfill instead of becoming an
    under-filled serial tail after all OpenMP rows have finished.
    """
    return sorted(
        rows,
        key=lambda item: (
            row_threads(item[1], policy),
            item[1].resolution,
            item[0],
        ),
    )


def imax_values(case: str) -> tuple[int, ...]:
    """Return the reviewed formal redistance matrix for one physical case."""
    return (0,) if case == "stationary_bubble" else IMAX_VALUES


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def write_locked_json(path: Path, payload: object, description: str) -> None:
    if path.is_file():
        if json.loads(path.read_text(encoding="utf-8")) != payload:
            raise ValueError(f"{description} changed; refusing to mix run settings")
        return
    atomic_json(path, payload)


def git_head() -> str:
    completed = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


def clean_git_baseline() -> str:
    commit = git_head()
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(ROOT),
            "status",
            "--porcelain",
            "--untracked-files=normal",
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    changed = completed.stdout.splitlines()
    if changed:
        preview = "\n".join(changed[:20])
        suffix = "\n..." if len(changed) > 20 else ""
        raise ValueError(
            "formal campaign must start from a clean committed worktree; "
            "finish requirements and smoke review, then commit the complete version:\n"
            f"{preview}{suffix}"
        )
    verify_campaign_inputs_committed()
    return commit


def verify_campaign_inputs_committed() -> None:
    """Require every reproducibility input except the built qcc to be in Git."""
    completed = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
        capture_output=True,
        check=True,
    )
    tracked = {
        entry.decode("utf-8")
        for entry in completed.stdout.split(b"\0")
        if entry
    }
    qcc = configured_qcc()
    missing = [
        path.relative_to(ROOT).as_posix()
        for path in source_files()
        if path != qcc and path.relative_to(ROOT).as_posix() not in tracked
    ]
    if missing:
        raise ValueError(
            "formal campaign inputs are not committed:\n" + "\n".join(missing)
        )


@dataclass(frozen=True)
class Row:
    case: str
    benchmark_case: int | None
    resolution: int
    imax: int
    method: str

    @property
    def model(self) -> str | None:
        return f"baseline_{self.resolution}_hgradient" if self.method == "NN" else None

    @property
    def experiment_role(self) -> str:
        """Paper-facing role of this imax row within the fixed campaign."""
        default_imax = 0 if self.case == "stationary_bubble" else 3
        return "default" if self.imax == default_imax else "sensitivity"

    @property
    def grid_strategy(self) -> str:
        return "uniform"

    @property
    def relative_output(self) -> Path:
        parts = [self.case]
        if self.benchmark_case is not None:
            parts.append(f"case{self.benchmark_case}")
        if self.case == "oscillating_droplet":
            parts.append(self.grid_strategy)
        parts.extend(
            [f"N{self.resolution:04d}", f"imax{self.imax:02d}", self.method]
        )
        return Path(*parts)

    @property
    def label(self) -> str:
        return self.relative_output.as_posix()

    def command(self, campaign_root: Path, purpose: str, threads: int) -> list[str]:
        runner_name = f"{self.method}.sh"
        command = [
            "bash",
            str(ROOT / "generate" / self.case / runner_name),
            f"--{purpose}",
            "--resolution",
            str(self.resolution),
            "--imax",
            str(self.imax),
            "--threads",
            str(threads),
            "--output",
            str(campaign_root / self.relative_output),
        ]
        if self.benchmark_case is not None:
            command.extend(["--case", str(self.benchmark_case)])
        if self.model:
            command.extend(["--model", self.model])
        if self.case == "oscillating_droplet":
            command.extend(["--grid", self.grid_strategy])
        if self.case == "stationary_bubble" and purpose == "smoke":
            command.extend(["--tau-max", "2.0"])
        return command


@dataclass(frozen=True)
class VOFHFRow:
    case: str
    benchmark_case: int | None
    resolution: int
    grid_mode: str | None = None

    method = "VOF-HF"
    imax = None
    model = None

    @property
    def grid_strategy(self) -> str:
        if self.grid_mode is not None:
            return self.grid_mode
        return "uniform" if self.case in {"capwave", "rising_bubble"} else "adaptive"

    @property
    def experiment_role(self) -> str:
        return (
            "matched_reference"
            if self.case == "oscillating_droplet" and self.grid_strategy == "uniform"
            else "official_reference"
        )

    @property
    def grid_role(self) -> str:
        if self.case == "oscillating_droplet" and self.grid_strategy == "uniform":
            return "uniform_matched"
        native = (
            self.resolution <= 128
            if self.case in {
                "capwave", "stationary_bubble", "oscillating_droplet"
            }
            else self.resolution == 256
        )
        return "stock_native" if native else "stock_compatible_extension"

    @property
    def relative_output(self) -> Path:
        parts = [self.case]
        if self.benchmark_case is not None:
            parts.append(f"case{self.benchmark_case}")
        if self.case == "oscillating_droplet":
            parts.append(self.grid_strategy)
        parts.extend((f"N{self.resolution:04d}", self.method))
        return Path(*parts)

    @property
    def label(self) -> str:
        return self.relative_output.as_posix()

    def command(self, campaign_root: Path, purpose: str, threads: int = 1) -> list[str]:
        command = [
            "bash",
            str(ROOT / "generate" / self.case / "VOF-HF.sh"),
            f"--{purpose}",
            "--resolution",
            str(self.resolution),
            "--threads",
            "1",
            "--output",
            str(campaign_root / self.relative_output),
        ]
        if self.benchmark_case is not None:
            command.extend(["--case", str(self.benchmark_case)])
        if self.case == "oscillating_droplet":
            command.extend(["--grid", self.grid_strategy])
        return command


CampaignRow = Row | VOFHFRow


@dataclass(frozen=True)
class BuildArtifact:
    directory: Path
    executable: Path
    executable_sha256: str
    manifest_sha256: str


class ResourceMonitor:
    """Record host utilization without adding a non-standard dependency."""

    def __init__(self, path: Path, interval_seconds: float = 1.0) -> None:
        self.path = path
        self.interval_seconds = interval_seconds
        self.last_sample = 0.0
        self.last_cpu = self._cpu_counters()
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            with path.open("w", newline="", encoding="utf-8") as stream:
                csv.writer(stream).writerow(
                    (
                        "timestamp", "phase", "active_rows", "allocated_slots",
                        "cpu_utilization_percent", "memory_available_bytes",
                        "swap_used_bytes",
                    )
                )

    @staticmethod
    def _cpu_counters() -> tuple[int, int] | None:
        path = Path("/proc/stat")
        if not path.is_file():
            return None
        fields = path.read_text(encoding="utf-8").splitlines()[0].split()[1:]
        values = [int(value) for value in fields]
        idle = values[3] + (values[4] if len(values) > 4 else 0)
        return sum(values), idle

    @staticmethod
    def _memory() -> tuple[int | None, int | None]:
        path = Path("/proc/meminfo")
        if not path.is_file():
            return None, None
        values = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            key, raw = line.split(":", 1)
            values[key] = int(raw.split()[0]) * 1024
        swap_used = values.get("SwapTotal", 0) - values.get("SwapFree", 0)
        return values.get("MemAvailable"), swap_used

    def sample(self, phase: str, active_rows: int, allocated_slots: int) -> None:
        now = time.monotonic()
        if now - self.last_sample < self.interval_seconds:
            return
        current = self._cpu_counters()
        utilization: float | str = ""
        if current is not None and self.last_cpu is not None:
            total_delta = current[0] - self.last_cpu[0]
            idle_delta = current[1] - self.last_cpu[1]
            if total_delta > 0:
                utilization = 100.0 * (total_delta - idle_delta) / total_delta
        self.last_cpu = current
        self.last_sample = now
        memory_available, swap_used = self._memory()
        with self.path.open("a", newline="", encoding="utf-8") as stream:
            csv.writer(stream).writerow(
                (
                    utc_now(), phase, active_rows, allocated_slots, utilization,
                    "" if memory_available is None else memory_available,
                    "" if swap_used is None else swap_used,
                )
            )


def write_resource_summary(campaign_root: Path, cpu_slots: int) -> None:
    path = campaign_root / "_meta/resource_usage.csv"
    samples = []
    if path.is_file():
        with path.open(newline="", encoding="utf-8") as stream:
            samples = list(csv.DictReader(stream))
    full = [
        float(row["cpu_utilization_percent"])
        for row in samples
        if row["phase"] == "solve"
        and int(row["allocated_slots"]) == cpu_slots
        and row["cpu_utilization_percent"]
    ]
    atomic_json(
        campaign_root / "_meta/resource_summary.json",
        {
            "schema_version": 1,
            "cpu_slots": cpu_slots,
            "samples": len(samples),
            "full_slot_solve_samples": len(full),
            "full_slot_mean_cpu_utilization_percent": (
                sum(full) / len(full) if full else None
            ),
            "interpretation": (
                "allocated slots are the scheduler contract; measured CPU can dip "
                "during solver serial sections and I/O"
            ),
        },
    )


def matched_rows() -> list[Row]:
    rows: list[Row] = []
    for case, cases, resolutions in (
        ("capwave", (None,), RESOLUTIONS),
        ("rising_bubble", (1, 2), RESOLUTIONS),
        ("stationary_bubble", (None,), RESOLUTIONS[:-1]),
        ("oscillating_droplet", (None,), RESOLUTIONS),
    ):
        for benchmark_case in cases:
            for resolution in resolutions:
                for imax in imax_values(case):
                    for method in METHODS:
                        rows.append(Row(case, benchmark_case, resolution, imax, method))
    if len(rows) != 368 or len({row.label for row in rows}) != 368:
        raise AssertionError("matched matrix must contain 368 unique rows")
    return rows


def vof_hf_rows(resolutions: tuple[int, ...]) -> list[VOFHFRow]:
    rows = [
        VOFHFRow(case, benchmark_case, resolution)
        for case, benchmark_case, allowed in (
            ("capwave", None, RESOLUTIONS),
            ("rising_bubble", 1, RESOLUTIONS),
            ("rising_bubble", 2, RESOLUTIONS),
            ("stationary_bubble", None, RESOLUTIONS[:-1]),
            ("oscillating_droplet", None, RESOLUTIONS),
        )
        for resolution in resolutions
        if resolution in allowed
    ]
    return rows


def formal_rows() -> list[CampaignRow]:
    rows: list[CampaignRow] = [
        *vof_hf_rows(RESOLUTIONS),
        *(VOFHFRow("oscillating_droplet", None, resolution, "uniform")
          for resolution in RESOLUTIONS),
        *matched_rows(),
    ]
    if len(rows) != FORMAL_ROW_COUNT or len({row.label for row in rows}) != FORMAL_ROW_COUNT:
        raise AssertionError("formal campaign must contain 397 unique rows")
    return rows


def matched_canary_rows() -> list[Row]:
    return [
        Row(
            case,
            benchmark_case,
            resolution,
            0 if case == "stationary_bubble" else 3,
            method,
        )
        for case, benchmark_case in (
            ("capwave", None),
            ("rising_bubble", 1),
            ("rising_bubble", 2),
            ("stationary_bubble", None),
            ("oscillating_droplet", None),
        )
        for resolution in (32, 64)
        for method in METHODS
    ]


def high_imax_canary_rows() -> list[Row]:
    """Exercise every newly-added redistance setting once at N32."""
    return [
        Row(case, benchmark_case, 32, imax, method)
        for case, benchmark_case in (
            ("capwave", None),
            ("rising_bubble", 1),
            ("rising_bubble", 2),
            ("oscillating_droplet", None),
        )
        for imax in HIGH_IMAX_VALUES
        for method in METHODS
    ]


def canary_rows() -> list[CampaignRow]:
    rows: list[CampaignRow] = [
        *vof_hf_rows((32, 64)),
        *(VOFHFRow("oscillating_droplet", None, resolution, "uniform")
          for resolution in (32, 64)),
        *matched_canary_rows(),
        *high_imax_canary_rows(),
    ]
    if len(rows) != SMOKE_ROW_COUNT or len({row.label for row in rows}) != SMOKE_ROW_COUNT:
        raise AssertionError("smoke campaign must contain 56 unique rows")
    return rows


def source_files() -> list[Path]:
    files = [
        path
        for path in (ROOT / "generate").rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and "tests" not in path.parts
        and path.name not in {".DS_Store"}
        and path.name not in {"README.md", "summary.yaml", "render_summaries.py"}
        and not path.name.endswith((".pyc", ".pyo"))
    ]
    files.extend(
        ROOT / path
        for path in (
            "basilisk/src/qcc.c",
            "basilisk/src/include.c",
            "basilisk/src/postproc.c",
            # Linux setup constructs its isolated qcc toolchain from this
            # tracked template.  Do not lock ``config`` here: in the upstream
            # tree it is a host-selected symlink (and may be intentionally
            # dangling in a clean checkout on another platform).
            "basilisk/src/config.gcc",
            "basilisk/src/integral.h",
            "basilisk/src/two-phase-clsvof.h",
            "basilisk/src/redistance.h",
            "basilisk/src/test/capwave.c",
            "basilisk/src/test/prosperetti.h",
            "basilisk/src/test/rising.c",
            "basilisk/src/test/c1g3l4.txt",
            "basilisk/src/test/c1g3l4s.txt",
            "basilisk/src/test/c2g3l4.txt",
            "basilisk/src/test/c2g3l4s.txt",
            "basilisk/src/test/spurious.c",
            "basilisk/src/test/oscillation.c",
            "basilisk/src/test/oscillation.ref",
        )
    )
    for resolution in RESOLUTIONS:
        model = f"baseline_{resolution}_hgradient"
        files.extend(
            (
                ROOT / "dataset/model/c_exports" / model / "nn_weights.h",
                ROOT / "dataset/model/c_exports" / model / "export_manifest.json",
                ROOT / "dataset/model" / f"{model}.pt",
            )
        )
    files.append(configured_qcc())
    missing = [path for path in files if not path.is_file()]
    if missing:
        raise ValueError("missing campaign dependencies:\n" + "\n".join(map(str, missing)))
    return sorted(set(files))


def source_lock() -> dict[str, str]:
    records: dict[str, str] = {}
    qcc = configured_qcc()
    for path in source_files():
        logical = (
            "toolchain/qcc"
            if path == qcc
            else path.relative_to(ROOT).as_posix()
        )
        records[logical] = sha256(path)
    return records


def object_relative_path(digest: str) -> Path:
    return Path("_meta/sources/sha256") / digest


def ensure_provenance_object(source: Path, campaign_root: Path) -> Path:
    """Store one immutable-by-hash campaign object and return its path."""
    digest = sha256(source)
    target = campaign_root / object_relative_path(digest)
    if target.is_file():
        if target.stat().st_size != source.stat().st_size or sha256(target) != digest:
            raise ValueError(f"corrupt provenance object: {target}")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp.{os.getpid()}")
    shutil.copyfile(source, temporary)
    if sha256(temporary) != digest:
        temporary.unlink()
        raise ValueError(f"copied provenance object hash mismatch: {source}")
    try:
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def ensure_named_hardlink(source: Path, target: Path) -> None:
    """Expose a readable named provenance file without storing another copy."""
    digest = sha256(source)
    if target.is_file():
        if target.stat().st_size != source.stat().st_size or sha256(target) != digest:
            raise ValueError(f"named provenance file does not match object: {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp.{os.getpid()}")
    try:
        os.link(source, temporary)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def initialize_provenance(
    campaign_root: Path,
    current_lock: dict[str, str],
    rows: list[CampaignRow],
) -> None:
    metadata = campaign_root / "_meta"
    lock_payload = {
        "schema_version": 1,
        "source_lock_sha256": canonical_sha256(current_lock),
        "files": current_lock,
    }
    lock_path = metadata / "source_lock.json"
    if lock_path.is_file():
        if json.loads(lock_path.read_text()) != lock_payload:
            raise ValueError("campaign provenance source lock changed")
    else:
        atomic_json(lock_path, lock_payload)

    named_sources = {
        Path("references/prosperetti.h"): ROOT / "basilisk/src/test/prosperetti.h",
        Path("references/hysing/case1_history.txt"): ROOT / "basilisk/src/test/c1g3l4.txt",
        Path("references/hysing/case1_interface.txt"): ROOT / "basilisk/src/test/c1g3l4s.txt",
        Path("references/hysing/case2_history.txt"): ROOT / "basilisk/src/test/c2g3l4.txt",
        Path("references/hysing/case2_interface.txt"): ROOT / "basilisk/src/test/c2g3l4s.txt",
    }
    model_resolutions = sorted({row.resolution for row in rows if row.method == "NN"})
    for resolution in model_resolutions:
        model = f"baseline_{resolution}_hgradient"
        for filename in ("export_manifest.json", "nn_weights.h"):
            named_sources[Path("models") / model / filename] = (
                ROOT / "dataset/model/c_exports" / model / filename
            )
    for relative, source in named_sources.items():
        object_path = ensure_provenance_object(source, campaign_root)
        ensure_named_hardlink(object_path, metadata / relative)
    regenerate_object_index(campaign_root)


def provenance_source_records(manifest: dict[str, object]) -> dict[str, dict[str, object]]:
    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict):
        return {}
    sources = provenance.get("sources")
    return sources if isinstance(sources, dict) else {}


def verify_source_references(
    manifest: dict[str, object], row_dir: Path, campaign_root: Path
) -> None:
    shared = provenance_source_records(manifest)
    plan = manifest.get("plan")
    if not isinstance(plan, dict) or not isinstance(plan.get("sources"), dict):
        raise ValueError(f"{row_dir}: missing planned sources")
    for label, source in plan["sources"].items():
        if not isinstance(source, dict):
            raise ValueError(f"{row_dir}: invalid planned source {label}")
        source_path = Path(str(source["path"]))
        if not source_path.parts or source_path.parts[0] != "source_snapshot":
            continue
        local = row_dir / source_path
        if local.is_file():
            candidate = local
        else:
            record = shared.get(label)
            if not isinstance(record, dict):
                raise ValueError(f"{row_dir}: missing shared source reference {label}")
            if record.get("sha256") != source.get("sha256"):
                raise ValueError(f"{row_dir}: shared source digest mismatch {label}")
            candidate = campaign_root / str(record.get("object"))
        if not candidate.is_file() or sha256(candidate) != source["sha256"]:
            raise ValueError(f"{row_dir}: source hash mismatch: {source_path}")


def compact_row_provenance(row_dir: Path, campaign_root: Path) -> None:
    """Move row-local source snapshots into the campaign object store."""
    manifest_path = row_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    existing = provenance_source_records(manifest)
    records: dict[str, dict[str, object]] = dict(existing)
    plan_sources = manifest.get("plan", {}).get("sources", {})
    for label, source in plan_sources.items():
        logical = Path(source["path"])
        if not logical.parts or logical.parts[0] != "source_snapshot":
            continue
        local = row_dir / logical
        if local.is_file():
            object_path = ensure_provenance_object(local, campaign_root)
        else:
            existing_record = records.get(label)
            if not existing_record:
                raise ValueError(f"{row_dir}: cannot compact missing source {logical}")
            object_path = campaign_root / str(existing_record["object"])
        if not object_path.is_file() or sha256(object_path) != source["sha256"]:
            raise ValueError(f"{row_dir}: invalid shared source object for {label}")
        records[label] = {
            "logical_path": logical.as_posix(),
            "sha256": source["sha256"],
            "bytes": source["bytes"],
            "object": object_path.relative_to(campaign_root).as_posix(),
        }
    manifest["provenance"] = {
        "schema_version": 1,
        "source_storage": "dataset_content_addressed_objects",
        "sources": dict(sorted(records.items())),
    }
    atomic_json(manifest_path, manifest)

    snapshot = row_dir / "source_snapshot"
    if snapshot.is_dir():
        files = sorted((path for path in snapshot.rglob("*") if path.is_file()), reverse=True)
        for path in files:
            path.unlink()
        directories = sorted(
            (path for path in snapshot.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts),
            reverse=True,
        )
        for path in directories:
            path.rmdir()
        snapshot.rmdir()
    regenerate_object_index(campaign_root)


def regenerate_object_index(campaign_root: Path) -> None:
    objects_root = campaign_root / "_meta/sources/sha256"
    references: dict[str, list[str]] = {}
    for manifest_path in campaign_root.glob("**/manifest.json"):
        if "_meta" in manifest_path.parts:
            continue
        manifest = json.loads(manifest_path.read_text())
        for record in provenance_source_records(manifest).values():
            object_relative = str(record["object"])
            references.setdefault(object_relative, []).append(
                f"{manifest_path.parent.relative_to(campaign_root).as_posix()}::"
                f"{record['logical_path']}"
            )
    metadata = campaign_root / "_meta"
    named_paths = list((metadata / "references").glob("**/*"))
    if (metadata / "models").is_dir():
        named_paths.extend((metadata / "models").glob("*/*"))
    for named in named_paths:
        if named.is_file():
            object_relative = object_relative_path(sha256(named)).as_posix()
            references.setdefault(object_relative, []).append(
                named.relative_to(campaign_root).as_posix()
            )
    entries = []
    if objects_root.is_dir():
        for object_path in sorted(path for path in objects_root.iterdir() if path.is_file()):
            digest = object_path.name
            if sha256(object_path) != digest:
                raise ValueError(f"corrupt provenance object: {object_path}")
            relative = object_path.relative_to(campaign_root).as_posix()
            entries.append(
                {
                    "sha256": digest,
                    "bytes": object_path.stat().st_size,
                    "object": relative,
                    "references": sorted(references.get(relative, [])),
                }
            )
    atomic_json(
        metadata / "object_index.json",
        {"schema_version": 1, "object_count": len(entries), "objects": entries},
    )


def write_rows_csv(rows: list[CampaignRow], campaign_root: Path) -> None:
    path = campaign_root / "_meta/tasks.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            ("row", "case", "benchmark_case", "resolution", "imax", "role", "method", "model", "grid_strategy", "grid_role", "output")
        )
        for index, row in enumerate(rows, 1):
            writer.writerow(
                (
                    index,
                    row.case,
                    row.benchmark_case if row.benchmark_case is not None else "",
                    row.resolution,
                    row.imax if row.imax is not None else "",
                    row.experiment_role,
                    row.method,
                    row.model or "",
                    row.grid_strategy,
                    row.grid_role if isinstance(row, VOFHFRow) else "",
                    row.relative_output.as_posix(),
                )
            )
    os.replace(temporary, path)


def write_case_summaries(rows: list[CampaignRow], campaign_root: Path) -> None:
    groups: dict[Path, list[CampaignRow]] = {}
    for row in rows:
        base = campaign_root / row.case
        if row.benchmark_case is not None:
            base /= f"case{row.benchmark_case}"
        groups.setdefault(base / "summary.csv", []).append(row)
    fieldnames = [
        "row", "resolution", "imax", "role", "method", "model",
        "grid_strategy", "grid_role",
        "analysis_ready", "artifact_bytes", "field_bytes", "metrics_json",
    ]
    for path, grouped_rows in groups.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
        with temporary.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            for row in grouped_rows:
                manifest = json.loads(
                    (campaign_root / row.relative_output / "manifest.json").read_text()
                )
                artifacts = manifest["published_artifacts"]
                metric_values = {
                    item["metric"]: item["value"]
                    for item in manifest["analysis"]["metrics"]
                }
                writer.writerow(
                    {
                        "row": row.relative_output.as_posix(),
                        "resolution": row.resolution,
                        "imax": "" if row.imax is None else row.imax,
                        "role": row.experiment_role,
                        "method": row.method,
                        "model": row.model or "",
                        "grid_strategy": row.grid_strategy,
                        "grid_role": row.grid_role if isinstance(row, VOFHFRow) else "",
                        "analysis_ready": str(manifest["analysis_ready"]).lower(),
                        "artifact_bytes": sum(int(item["bytes"]) for item in artifacts.values()),
                        "field_bytes": int(artifacts["fields.csv.gz"]["bytes"]),
                        "metrics_json": json.dumps(metric_values, sort_keys=True, separators=(",", ":")),
                    }
                )
        os.replace(temporary, path)


def provider_evaluations(manifest: dict[str, object]) -> int | None:
    analysis = manifest.get("analysis")
    if not isinstance(analysis, dict):
        return None
    stats = analysis.get("provider_stats")
    if stats is None:
        return None
    if not isinstance(stats, dict) or "evaluations" not in stats:
        raise ValueError("invalid embedded provider statistics")
    return int(stats["evaluations"])


def verify_compact_artifacts(
    manifest: dict[str, object], row_dir: Path, case: str, label: str
) -> None:
    if manifest.get("row_schema_version") != 1:
        raise ValueError(f"{label}: unsupported compact row schema")
    published = manifest.get("published_artifacts")
    if not isinstance(published, dict) or set(published) != FINAL_ROW_FILES[case]:
        raise ValueError(f"{label}: compact artifact inventory mismatch")
    for name, record in published.items():
        if not isinstance(record, dict):
            raise ValueError(f"{label}: invalid artifact record {name}")
        candidate = row_dir / name
        if (
            not candidate.is_file()
            or candidate.stat().st_size != record.get("bytes")
            or sha256(candidate) != record.get("sha256")
        ):
            raise ValueError(f"{label}: compact artifact hash mismatch: {name}")
    actual_files = {path.name for path in row_dir.iterdir() if path.is_file()}
    expected_files = {"manifest.json", *FINAL_ROW_FILES[case]}
    if actual_files != expected_files:
        raise ValueError(
            f"{label}: unexpected row files: "
            f"missing={sorted(expected_files - actual_files)} "
            f"extra={sorted(actual_files - expected_files)}"
        )
    analysis = manifest.get("analysis")
    if (
        not isinstance(analysis, dict)
        or analysis.get("benchmark_output_coverage_complete") is not True
        or not isinstance(analysis.get("metrics"), list)
    ):
        raise ValueError(f"{label}: embedded analysis contract is incomplete")
    snapshots = manifest.get("field_snapshots")
    if (
        not isinstance(snapshots, dict)
        or set(snapshots.get("snapshots", {})) != {"middle", "final"}
    ):
        raise ValueError(f"{label}: two field snapshots are required")
    with gzip.open(row_dir / "fields.csv.gz", "rt", encoding="utf-8") as stream:
        header = stream.readline().rstrip("\n")
    if header.split(",") != snapshots.get("columns"):
        raise ValueError(f"{label}: compressed field schema mismatch")


def verify_vof_hf_row(row: VOFHFRow, campaign_root: Path, purpose: str) -> None:
    row_dir = campaign_root / row.relative_output
    manifest_path = row_dir / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"incomplete VOF-HF row: {row.label}")
    manifest = json.loads(manifest_path.read_text())
    expected = {
        "status": "completed",
        "case": row.case,
        "method": "VOF-HF",
        "purpose": purpose,
        "resolution": row.resolution,
        "experiment_role": row.experiment_role,
        "grid_strategy": row.grid_strategy,
        "grid_role": row.grid_role,
        "analysis_ready": True,
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise ValueError(
                f"{row.label}: manifest {key}={manifest.get(key)!r}, expected {value!r}"
            )
    if not manifest.get("plan", {}).get("plan_sha256"):
        raise ValueError(f"{row.label}: missing resolved plan hash")
    if Path(manifest["plan"]["output"]) != row_dir.resolve():
        raise ValueError(f"{row.label}: manifest output path mismatch")
    verify_build_binding(manifest, row.label)
    if row.case == "oscillating_droplet":
        verification = manifest.get("oscillating_vof_hf_verification")
        if not isinstance(verification, dict):
            raise ValueError(f"{row.label}: missing embedded VOF-HF verification")
    verify_compact_artifacts(manifest, row_dir, row.case, row.label)
    verify_source_references(manifest, row_dir, campaign_root)


def verify_row(row: CampaignRow, campaign_root: Path, purpose: str) -> None:
    if isinstance(row, VOFHFRow):
        verify_vof_hf_row(row, campaign_root, purpose)
        return
    row_dir = campaign_root / row.relative_output
    manifest_path = row_dir / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"incomplete row: {row.label}")
    manifest = json.loads(manifest_path.read_text())
    expected = {
        "status": "completed",
        "case": row.case,
        "method": row.method,
        "purpose": purpose,
        "resolution": row.resolution,
        "imax": row.imax,
        "model": row.model,
        "experiment_role": row.experiment_role,
        "grid_strategy": row.grid_strategy,
        "analysis_ready": True,
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise ValueError(
                f"{row.label}: manifest {key}={manifest.get(key)!r}, expected {value!r}"
            )
    if not manifest.get("plan", {}).get("plan_sha256"):
        raise ValueError(f"{row.label}: missing resolved plan hash")
    if Path(manifest["plan"]["output"]) != row_dir.resolve():
        raise ValueError(f"{row.label}: manifest output path mismatch")
    verify_build_binding(manifest, row.label)
    verify_compact_artifacts(manifest, row_dir, row.case, row.label)
    verify_source_references(manifest, row_dir, campaign_root)
    evaluations = provider_evaluations(manifest)
    if row.method == "NN" and (evaluations is None or evaluations <= 0):
        raise ValueError(f"{row.label}: NN provider was not exercised")
    if row.method == "CLSVOF" and evaluations is not None:
        raise ValueError(f"{row.label}: CLSVOF row contains NN provider metrics")


def verify_pairs(rows: list[CampaignRow], campaign_root: Path) -> None:
    grouped: dict[tuple[str, int | None, int, int], dict[str, Row]] = {}
    for row in rows:
        if isinstance(row, VOFHFRow):
            continue
        grouped.setdefault(
            (row.case, row.benchmark_case, row.resolution, row.imax), {}
        )[row.method] = row
    for pair in grouped.values():
        if set(pair) != set(METHODS):
            raise ValueError("campaign contains an incomplete CLSVOF/NN pair")
        overlays = []
        for method in METHODS:
            manifest_path = campaign_root / pair[method].relative_output / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            source = manifest.get("plan", {}).get("sources", {}).get("redistance_overlay")
            if not source or not source.get("sha256"):
                raise ValueError(f"{pair[method].label}: missing redistance source hash")
            overlays.append(source["sha256"])
        if overlays[0] != overlays[1]:
            raise ValueError(f"redistance source mismatch in pair {pair['CLSVOF'].label}")


def verify_campaign(
    rows: list[CampaignRow], campaign_root: Path, purpose: str
) -> None:
    for row in rows:
        verify_row(row, campaign_root, purpose)
        row_dir = campaign_root / row.relative_output
        if (row_dir / "source_snapshot").exists():
            raise ValueError(f"{row.label}: row-local source snapshot was not compacted")
        manifest = json.loads((row_dir / "manifest.json").read_text())
        planned_shared = {
            label
            for label, source in manifest["plan"]["sources"].items()
            if Path(source["path"]).parts
            and Path(source["path"]).parts[0] == "source_snapshot"
        }
        recorded_shared = set(provenance_source_records(manifest))
        if planned_shared != recorded_shared:
            raise ValueError(f"{row.label}: incomplete shared provenance mapping")
        if row.case == "capwave":
            if (row_dir / "prosperetti.h").exists():
                raise ValueError(f"{row.label}: capwave reference was not shared")
    verify_pairs(rows, campaign_root)


def write_oscillating_vof_hf_report(
    rows: list[CampaignRow], campaign_root: Path
) -> None:
    """One campaign-level report replaces the removed per-row status files.

    Derived idempotently from the compact verification record embedded in each
    row manifest; written only by
    run_campaign after verify_campaign, never by the read-only verify path.
    """
    entries = []
    for row in rows:
        if (
            not isinstance(row, VOFHFRow)
            or row.case != "oscillating_droplet"
            or row.experiment_role != "official_reference"
        ):
            continue
        row_dir = campaign_root / row.relative_output
        manifest = json.loads((row_dir / "manifest.json").read_text())
        verification = manifest.get("oscillating_vof_hf_verification")
        if not isinstance(verification, dict):
            raise ValueError(f"{row.label}: missing compact official verification")
        execution = verification.get("execution_status", {})
        if not isinstance(execution, dict):
            raise ValueError(f"{row.label}: invalid compact execution status")
        strict_match = (
            bool(verification.get("strict_log_ref_match"))
            if row.grid_role == "stock_native"
            else None
        )
        if strict_match is None:
            status = "stock_compatible_extension"
        elif strict_match:
            status = "official_pass"
        else:
            status = "official_regression_mismatch"
        entries.append(
            {
                "row": row.relative_output.as_posix(),
                "resolution": row.resolution,
                "grid_role": row.grid_role,
                "status": status,
                "strict_log_ref_match": strict_match,
                "compile_exit_status": int(verification["compile_exit_status"]),
                "standard_run_exit_status": int(verification["run_exit_status"]),
                "started_at": verification["started_at"],
                "ended_at": verification["ended_at"],
                "wall_seconds": int(verification["wall_seconds"]),
                "fit_summary_sha256": verification["actual_log_sha256"],
                "official_ref_sha256": verification["official_ref_sha256"],
            }
        )
    if not entries:
        return
    atomic_json(
        campaign_root / "_meta/oscillating_vof_hf_official.json",
        {
            "schema_version": 1,
            "case": "oscillating_droplet",
            "method": "VOF-HF",
            "solver_variant": "Standard",
            "excluded_solver_variants": ["Momentum", "Compressible"],
            "replaces_row_files": [
                "VOF-HF_report.json",
                "VOF-HF_RESULTS.md",
                "verification.json",
            ],
            "generated_at": utc_now(),
            "rows": entries,
        },
    )


def plan(
    rows: list[CampaignRow],
    campaign_root: Path,
    purpose: str,
    policy: dict[str, object],
) -> None:
    print(
        "row\tcase\tbenchmark_case\tresolution\timax\trole\tmethod\tgrid_strategy\tthreads\tmodel\toutput"
    )
    for index, row in enumerate(rows, 1):
        print(
            f"{index}\t{row.case}\t{row.benchmark_case or '-'}\t"
            f"{row.resolution}\t{row.imax if row.imax is not None else '-'}\t"
            f"{row.experiment_role}\t"
            f"{row.method}\t{row.grid_strategy}\t{row_threads(row, policy)}\t{row.model or '-'}\t"
            f"{campaign_root / row.relative_output}"
        )
    print(
        f"rows={len(rows)} purpose={purpose} cpu_slots={policy['cpu_slots']} "
        f"policy_sha256={policy['policy_sha256']}",
        file=sys.stderr,
    )


def publish_resource_policy(
    campaign_root: Path, policy: dict[str, object]
) -> dict[str, object]:
    published = {
        key: value
        for key, value in policy.items()
        if key not in {"policy_path", "policy_sha256"}
    }
    published["source_sha256"] = policy["policy_sha256"]
    published["host"] = host_record()
    write_locked_json(
        campaign_root / "_meta/resource_policy.json",
        published,
        "resource policy",
    )
    return published


def publish_schema(campaign_root: Path) -> None:
    schema = {
        "schema_version": 2,
        "dataset": DATASET_NAME,
        "method_names": ["VOF-HF", "CLSVOF", "NN"],
        "campaign_contract": {
            "formal_rows": FORMAL_ROW_COUNT,
            "smoke_rows": SMOKE_ROW_COUNT,
            "redistance_imax": {
                "default_non_stationary": 3,
                "non_stationary": list(IMAX_VALUES),
                "stationary_bubble": [0],
            },
            "grid_strategy": {
                "capwave": {"VOF-HF": "uniform", "CLSVOF": "uniform", "NN": "uniform"},
                "rising_bubble": {"VOF-HF": "uniform", "CLSVOF": "uniform", "NN": "uniform"},
                "stationary_bubble": {"VOF-HF": "adaptive", "CLSVOF": "uniform", "NN": "uniform"},
                "oscillating_droplet": {
                    "official_VOF-HF": "adaptive",
                    "matched_VOF-HF": "uniform",
                    "CLSVOF": "uniform",
                    "NN": "uniform",
                },
            },
        },
        "row_files": {
            case: sorted(files) for case, files in FINAL_ROW_FILES.items()
        },
        "tables": {
            "capwave/timeseries.csv": [
                "tau", "amplitude", "reference_amplitude", "amplitude_error",
            ],
            "rising_bubble/timeseries.csv": [
                "time", "iteration", "relative_volume_change",
                "center_of_mass_x", "rise_velocity_x", "dt", "circularity",
                "half_area", "half_perimeter",
            ],
            "rising_bubble/interface_t3.csv.gz": [
                "segment_id", "x1", "y1", "x2", "y2",
            ],
            "stationary_bubble/timeseries.csv": [
                "tau", "u_star", "delta_fraction", "capillary_number",
            ],
            "stationary_bubble/milestones.csv": [
                "milestone", "tau", "iteration", "u_star",
                "capillary_number", "shape_error_avg", "shape_error_rms",
                "shape_error_max", "official_style_ekmax",
                "active_provider_ekmax", "active_provider_samples",
            ],
            "oscillating_droplet/timeseries.csv": [
                "time", "kinetic_energy", "pressure_iterations",
            ],
            "oscillating_droplet/fit.csv": [
                "cells_per_diameter", "fit_a", "fit_a_stderr", "fit_b",
                "fit_b_stderr", "fit_c", "fit_c_stderr",
                "frequency_error_signed", "frequency_error_abs_percent",
                "equivalent_laplace", "damping_regime",
            ],
            "fields.csv.gz": [
                "snapshot", "target_solver_time", "actual_solver_time",
                "actual_benchmark_time", "iteration", "x", "y", "Delta",
                "level", "u_x", "u_y", "pressure", "vorticity",
                "phase_fraction", "common_curvature",
                "common_curvature_valid", "active_curvature",
                "active_curvature_valid",
            ],
        },
        "field_snapshot_selection": {
            "middle": "first native solver state at or after the case target",
            "final": "terminal solver state",
        },
        "embedded_in_manifest": [
            "resolved compile/run plan", "source hashes", "build binding",
            "scientific metrics", "NN provider counters", "artifact hashes",
        ],
    }
    write_locked_json(campaign_root / "_meta/schema.json", schema, "data schema")


def build_directory(campaign_root: Path, row: CampaignRow) -> Path:
    return campaign_root / "_meta/builds" / row.relative_output


def remove_build_directory(campaign_root: Path, row: CampaignRow) -> None:
    """Remove only the scheduler-owned temporary build for one exact row."""
    builds_root = (campaign_root / "_meta/builds").resolve()
    target = build_directory(campaign_root, row).resolve()
    try:
        relative = target.relative_to(builds_root)
    except ValueError as error:
        raise ValueError(f"unsafe build cleanup target: {target}") from error
    if relative == Path("."):
        raise ValueError("refusing to remove the campaign builds root")
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.is_dir():
        shutil.rmtree(target)


def verify_build_artifact(
    row: CampaignRow,
    campaign_root: Path,
    purpose: str,
    threads: int,
) -> BuildArtifact:
    directory = build_directory(campaign_root, row)
    manifest_path = directory / "manifest.json"
    executable = directory / "executable"
    if not manifest_path.is_file() or not executable.is_file():
        raise ValueError(f"{row.label}: incomplete campaign build")
    if executable.stat().st_size == 0:
        raise ValueError(f"{row.label}: empty campaign executable")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {
        "status": "completed",
        "case": row.case,
        "method": row.method,
        "purpose": purpose,
        "resolution": row.resolution,
        "experiment_role": row.experiment_role,
        "grid_strategy": row.grid_strategy,
    }
    if row.imax is not None:
        expected["imax"] = row.imax
    if row.model is not None:
        expected["model"] = row.model
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise ValueError(
                f"{row.label}: build manifest {key}={manifest.get(key)!r}, "
                f"expected {value!r}"
            )
    plan = manifest.get("plan")
    if not isinstance(plan, dict):
        raise ValueError(f"{row.label}: build manifest lacks a plan")
    if Path(str(plan.get("output"))) != directory.resolve():
        raise ValueError(f"{row.label}: build output path mismatch")
    parameters = plan.get("parameters")
    if not isinstance(parameters, dict):
        raise ValueError(f"{row.label}: build parameters missing")
    if parameters.get("compile_only") not in (1, True):
        raise ValueError(f"{row.label}: scheduler build is not compile-only")
    if parameters.get("compile_reused") not in (0, False):
        raise ValueError(f"{row.label}: scheduler build unexpectedly reused a binary")
    if parameters.get("openmp_threads") != threads:
        raise ValueError(f"{row.label}: build thread policy mismatch")
    run_argv = plan.get("commands", {}).get("run", {}).get("argv")
    if run_argv != []:
        raise ValueError(f"{row.label}: compile-only build contains a run command")
    verify_source_references(manifest, directory, campaign_root)
    return BuildArtifact(
        directory=directory,
        executable=executable,
        executable_sha256=sha256(executable),
        manifest_sha256=sha256(manifest_path),
    )


def bind_build_to_completed_row(
    row: CampaignRow,
    campaign_root: Path,
    artifact: BuildArtifact,
) -> None:
    """Prove the solved row used the executable from its reviewed build plan."""
    row_dir = campaign_root / row.relative_output
    manifest_path = row_dir / "manifest.json"
    build_manifest_path = artifact.directory / "manifest.json"
    if not manifest_path.is_file() or not build_manifest_path.is_file():
        raise ValueError(f"{row.label}: missing build or result manifest for binding")
    result = json.loads(manifest_path.read_text(encoding="utf-8"))
    build = json.loads(build_manifest_path.read_text(encoding="utf-8"))
    result_plan = result.get("plan", {})
    build_plan = build.get("plan", {})
    if result_plan.get("generator") != build_plan.get("generator"):
        raise ValueError(f"{row.label}: generator changed between build and solve")
    if result_plan.get("commands", {}).get("compile") != build_plan.get(
        "commands", {}
    ).get("compile"):
        raise ValueError(f"{row.label}: compile command changed between build and solve")
    if result_plan.get("environment") != build_plan.get("environment"):
        raise ValueError(f"{row.label}: OpenMP environment changed between build and solve")
    result_parameters = dict(result_plan.get("parameters", {}))
    build_parameters = dict(build_plan.get("parameters", {}))
    if result_parameters.pop("compile_only", None) not in (0, False):
        raise ValueError(f"{row.label}: solve manifest is marked compile-only")
    if result_parameters.pop("compile_reused", None) not in (1, True):
        raise ValueError(f"{row.label}: solve did not record executable reuse")
    if build_parameters.pop("compile_only", None) not in (1, True):
        raise ValueError(f"{row.label}: build manifest is not compile-only")
    if build_parameters.pop("compile_reused", None) not in (0, False):
        raise ValueError(f"{row.label}: build manifest reused an executable")
    if result_parameters != build_parameters:
        raise ValueError(f"{row.label}: scientific parameters changed after build")
    result_sources = dict(result_plan.get("sources", {}))
    precompiled = result_sources.pop("precompiled_executable", None)
    if not isinstance(precompiled, dict):
        raise ValueError(f"{row.label}: solve manifest lacks the campaign executable")
    if precompiled.get("sha256") != artifact.executable_sha256:
        raise ValueError(f"{row.label}: solved executable hash does not match build")
    if result_sources != build_plan.get("sources"):
        raise ValueError(f"{row.label}: compiled sources changed before solve")
    if sha256(artifact.executable) != artifact.executable_sha256:
        raise ValueError(f"{row.label}: campaign executable changed before binding")
    result["build_binding"] = {
        "schema_version": 1,
        "strategy": "campaign_two_stage",
        "build_manifest_sha256": artifact.manifest_sha256,
        "build_plan_sha256": build_plan.get("plan_sha256"),
        "executable_sha256": artifact.executable_sha256,
        "verified_at": utc_now(),
    }
    atomic_json(manifest_path, result)


def verify_build_binding(manifest: dict[str, object], label: str) -> None:
    plan = manifest.get("plan")
    binding = manifest.get("build_binding")
    if not isinstance(plan, dict) or not isinstance(binding, dict):
        raise ValueError(f"{label}: missing two-stage build binding")
    if binding.get("strategy") != "campaign_two_stage":
        raise ValueError(f"{label}: unsupported build strategy")
    parameters = plan.get("parameters", {})
    if not isinstance(parameters, dict) or parameters.get("compile_reused") not in (
        1,
        True,
    ):
        raise ValueError(f"{label}: final row did not reuse a campaign build")
    source = plan.get("sources", {}).get("precompiled_executable")
    if not isinstance(source, dict) or source.get("sha256") != binding.get(
        "executable_sha256"
    ):
        raise ValueError(f"{label}: build binding executable hash mismatch")
    for key in ("build_manifest_sha256", "build_plan_sha256", "executable_sha256"):
        value = binding.get(key)
        if not isinstance(value, str) or len(value) != 64:
            raise ValueError(f"{label}: invalid build binding field {key}")


def compile_pending_rows(
    pending_rows: list[tuple[int, CampaignRow]],
    campaign_root: Path,
    purpose: str,
    policy: dict[str, object],
    current_lock: dict[str, str],
    monitor: ResourceMonitor,
) -> dict[str, BuildArtifact]:
    """Compile rows with a memory-safe process cap before the solve stage."""
    compile_slots = int(policy["compile_slots"])
    metadata_dir = campaign_root / "_meta"
    queued: list[tuple[int, CampaignRow]] = []
    artifacts: dict[str, BuildArtifact] = {}
    for index, row in pending_rows:
        if build_directory(campaign_root, row).exists():
            try:
                artifacts[row.label] = verify_build_artifact(
                    row, campaign_root, purpose, row_threads(row, policy)
                )
                print(f"[build {index}/{len(pending_rows)}] reused {row.label}", flush=True)
                continue
            except (OSError, ValueError, json.JSONDecodeError):
                remove_build_directory(campaign_root, row)
        queued.append((index, row))

    active: dict[
        subprocess.Popen[str], tuple[int, CampaignRow, object, Path]
    ] = {}
    failure: tuple[CampaignRow, Path, str] | None = None
    while queued or active:
        while failure is None and queued and len(active) < compile_slots:
            index, row = queued.pop(0)
            if source_lock() != current_lock:
                raise ValueError("campaign source files changed during compilation")
            threads = row_threads(row, policy)
            command = [
                *row.command(campaign_root / "_meta/builds", purpose, threads),
                "--compile-only",
            ]
            log_path = metadata_dir / "logs/build" / f"{index:03d}.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log = log_path.open("w", encoding="utf-8")
            environment = os.environ.copy()
            environment["CFD_CAMPAIGN_BUILD"] = "1"
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                env=environment,
                text=True,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            ACTIVE_PROCESS_GROUPS.add(process)
            active[process] = (index, row, log, log_path)
            print(
                f"[build {index}/{len(pending_rows)}] compiling {row.label} "
                f"compilers={len(active)}/{compile_slots}",
                flush=True,
            )
        monitor.sample("compile", len(active), len(active))
        finished = [process for process in active if process.poll() is not None]
        if not finished:
            if active:
                time.sleep(0.25)
                continue
            break
        for process in finished:
            ACTIVE_PROCESS_GROUPS.discard(process)
            index, row, log, log_path = active.pop(process)
            log.close()
            if process.returncode:
                if failure is None:
                    failure = (row, log_path, f"exit status {process.returncode}")
                continue
            try:
                artifacts[row.label] = verify_build_artifact(
                    row, campaign_root, purpose, row_threads(row, policy)
                )
                print(f"[build {index}/{len(pending_rows)}] completed {row.label}", flush=True)
            except (OSError, ValueError, json.JSONDecodeError) as error:
                if failure is None:
                    failure = (row, log_path, str(error))
        if failure is not None and not active:
            break
    if failure is not None:
        row, log_path, detail = failure
        raise RuntimeError(f"build failed ({row.label}): {detail}; see {log_path}")
    if set(artifacts) != {row.label for _, row in pending_rows}:
        missing = sorted({row.label for _, row in pending_rows} - set(artifacts))
        raise RuntimeError(f"campaign build phase is incomplete: {missing[:3]}")
    return artifacts


def run_campaign(
    rows: list[CampaignRow],
    campaign_root: Path,
    purpose: str,
    policy: dict[str, object],
) -> None:
    verify_execution_host(policy)
    metadata_dir = campaign_root / "_meta"
    campaign_path = metadata_dir / "run.json"
    current_lock = source_lock()
    lock_hash = canonical_sha256(current_lock)
    cpu_slots = int(policy["cpu_slots"])
    published_policy = publish_resource_policy(campaign_root, policy)
    policy_hash = canonical_sha256(published_policy)
    if campaign_path.is_file():
        campaign = json.loads(campaign_path.read_text())
        if purpose == "formal" and campaign.get("git_commit") != git_head():
            raise ValueError(
                "formal campaign HEAD changed; resume from the original committed version"
            )
        if campaign.get("source_lock_sha256") != lock_hash:
            raise ValueError("campaign source lock changed; do not mix rows from different source states")
        expected_campaign = {
            "purpose": purpose,
            "row_count": len(rows),
            "cpu_slots": cpu_slots,
            "resource_policy_sha256": policy_hash,
        }
        for key, value in expected_campaign.items():
            if campaign.get(key) != value:
                raise ValueError(
                    f"campaign {key}={campaign.get(key)!r}, expected {value!r}; "
                    "do not mix campaign execution settings"
                )
    else:
        baseline_commit = clean_git_baseline() if purpose == "formal" else git_head()
        campaign = {
            "schema_version": 1,
            "purpose": purpose,
            "row_count": len(rows),
            "cpu_slots": cpu_slots,
            "resource_policy_sha256": policy_hash,
            "host": host_record(),
            "git_commit": baseline_commit,
            "initial_worktree_clean": purpose == "formal",
            "source_lock_sha256": lock_hash,
            "source_lock": current_lock,
            "created_at": utc_now(),
            "completed_rows": [],
        }
        atomic_json(campaign_path, campaign)
    publish_schema(campaign_root)
    initialize_provenance(campaign_root, current_lock, rows)
    write_rows_csv(rows, campaign_root)
    monitor = ResourceMonitor(metadata_dir / "resource_usage.csv")
    completed = set(campaign.get("completed_rows", []))
    pending: list[tuple[int, CampaignRow]] = []
    for index, row in enumerate(rows, 1):
        row_dir = campaign_root / row.relative_output
        if row.label in completed or row_dir.exists():
            verify_row(row, campaign_root, purpose)
            compact_row_provenance(row_dir, campaign_root)
            verify_row(row, campaign_root, purpose)
            remove_build_directory(campaign_root, row)
            completed.add(row.label)
            print(f"[{index}/{len(rows)}] verified {row.label}", flush=True)
        else:
            pending.append((index, row))

    builds = compile_pending_rows(
        pending, campaign_root, purpose, policy, current_lock, monitor
    )
    # VOF-HF rows enter early as one-slot backfill. Larger rows remain for a
    # fully occupied tail rather than leaving only 24 serial references last.
    pending = scheduler_order(pending, policy)
    active: dict[
        subprocess.Popen[str],
        tuple[int, CampaignRow, int, object, Path],
    ] = {}
    used_slots = 0
    failure: tuple[CampaignRow, Path, str] | None = None
    while pending or active:
        launched = False
        if failure is None:
            for position, (index, row) in enumerate(pending):
                slots = row_threads(row, policy)
                if used_slots + slots > cpu_slots:
                    continue
                if source_lock() != current_lock:
                    raise ValueError("campaign source files changed during execution")
                artifact = builds[row.label]
                command = [
                    *row.command(campaign_root, purpose, slots),
                    "--precompiled",
                    str(artifact.executable),
                ]
                log_path = metadata_dir / "logs/solve" / f"{index:03d}.log"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log = log_path.open("w", encoding="utf-8")
                environment = os.environ.copy()
                environment["CFD_CAMPAIGN_PRECOMPILED"] = "1"
                process = subprocess.Popen(
                    command,
                    cwd=ROOT,
                    env=environment,
                    text=True,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                ACTIVE_PROCESS_GROUPS.add(process)
                active[process] = (index, row, slots, log, log_path)
                used_slots += slots
                pending.pop(position)
                print(
                    f"[{index}/{len(rows)}] running {row.label} "
                    f"slots={slots} used={used_slots}/{cpu_slots}",
                    flush=True,
                )
                launched = True
                break
        monitor.sample("solve", len(active), used_slots)
        finished = [process for process in active if process.poll() is not None]
        if not finished:
            if active:
                time.sleep(0.25)
                continue
            if pending and not launched:
                raise ValueError("resource policy cannot schedule a pending row")
            continue
        for process in finished:
            ACTIVE_PROCESS_GROUPS.discard(process)
            index, row, slots, log, log_path = active.pop(process)
            log.close()
            used_slots -= slots
            if process.returncode:
                if failure is None:
                    failure = (row, log_path, f"exit status {process.returncode}")
                print(
                    f"[{index}/{len(rows)}] failed {row.label}; "
                    "no new rows will be launched",
                    file=sys.stderr,
                    flush=True,
                )
                continue
            try:
                artifact = builds[row.label]
                row_dir = campaign_root / row.relative_output
                bind_build_to_completed_row(row, campaign_root, artifact)
                verify_row(row, campaign_root, purpose)
                compact_row_provenance(row_dir, campaign_root)
                verify_row(row, campaign_root, purpose)
                remove_build_directory(campaign_root, row)
                completed.add(row.label)
                campaign["completed_rows"] = sorted(completed)
                campaign["updated_at"] = utc_now()
                atomic_json(campaign_path, campaign)
                print(
                    f"[{index}/{len(rows)}] completed {row.label} "
                    f"used={used_slots}/{cpu_slots}",
                    flush=True,
                )
            except (OSError, ValueError, json.JSONDecodeError) as error:
                if failure is None:
                    failure = (row, log_path, str(error))
                print(
                    f"[{index}/{len(rows)}] validation failed {row.label}; "
                    "no new rows will be launched",
                    file=sys.stderr,
                    flush=True,
                )
    if failure is not None:
        row, log_path, detail = failure
        raise RuntimeError(f"row failed ({row.label}): {detail}; see {log_path}")
    builds_root = metadata_dir / "builds"
    if builds_root.is_dir() and not any(builds_root.iterdir()):
        builds_root.rmdir()
    verify_campaign(rows, campaign_root, purpose)
    write_case_summaries(rows, campaign_root)
    write_oscillating_vof_hf_report(rows, campaign_root)
    write_resource_summary(campaign_root, cpu_slots)
    campaign["completed_rows"] = sorted(completed)
    campaign["updated_at"] = utc_now()
    atomic_json(campaign_path, campaign)
    ready = {
        "schema_version": 1,
        "status": "ready",
        "purpose": purpose,
        "row_count": len(rows),
        "source_lock_sha256": lock_hash,
        "verified_at": utc_now(),
    }
    atomic_json(campaign_root / "READY.json", ready)
    print(json.dumps(ready, sort_keys=True))


def check(policy: dict[str, object]) -> None:
    rows = formal_rows()
    source_lock()
    representatives = canary_rows()
    for row in representatives:
        command = row.command(
            ROOT / "tem/dry_run_contract/campaign",
            "formal",
            row_threads(row, policy),
        )
        subprocess.run([*command, "--dry-run"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    print(
        json.dumps(
            {
                "status": "ok",
                "formal_rows": len(rows),
                "dry_run_rows": len(representatives),
                "cpu_slots": policy["cpu_slots"],
                "policy_sha256": policy["policy_sha256"],
            },
            sort_keys=True,
        )
    )


def layout() -> None:
    """Print the implemented review-candidate tree without creating directories."""
    print(
        f"""status=implementation_ready_for_review
data/
├── _smoke/{DATASET_NAME}/
└── {DATASET_NAME}/
    ├── READY.json
    ├── _meta/
    │   ├── run.json
    │   ├── tasks.csv
    │   ├── schema.json
    │   ├── source_lock.json
    │   ├── resource_policy.json
    │   ├── resource_usage.csv
    │   ├── resource_summary.json
    │   ├── object_index.json
    │   ├── oscillating_vof_hf_official.json
    │   ├── logs/
    │   ├── sources/sha256/<hash>
    │   ├── references/{{prosperetti.h,hysing/*}}
    │   └── models/baseline_<N>_hgradient/{{export_manifest.json,nn_weights.h}}
    ├── capwave/{{summary.csv,Nxxxx/{{VOF-HF,imaxNN/{{CLSVOF,NN}}}}}}/
    ├── rising_bubble/caseK/{{summary.csv,Nxxxx/{{VOF-HF,imaxNN/{{CLSVOF,NN}}}}}}/
    ├── stationary_bubble/{{summary.csv,Nxxxx/{{VOF-HF,imax00/{{CLSVOF,NN}}}}}}/
    └── oscillating_droplet/
        ├── summary.csv
        ├── adaptive/Nxxxx/VOF-HF/
        └── uniform/Nxxxx/{{VOF-HF,imaxNN/{{CLSVOF,NN}}}}/

formal_items={FORMAL_ROW_COUNT} smoke_items={SMOKE_ROW_COUNT}
note=case-centered paths and one compact dataset-level _meta directory are active"""
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=("layout", "check", "plan", "smoke", "canary", "formal", "verify"),
    )
    parser.add_argument("--root", type=Path)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--scope", choices=("smoke", "formal"), default="formal")
    args = parser.parse_args()
    if args.action == "layout":
        layout()
        return 0
    policy = load_resource_policy(args.policy)
    if args.action == "check":
        check(policy)
        return 0
    purpose = (
        "smoke"
        if args.action in {"smoke", "canary"}
        else args.scope
        if args.action in {"plan", "verify"}
        else "formal"
    )
    rows = canary_rows() if purpose == "smoke" else formal_rows()
    default_root = ROOT / (
        f"data/_smoke/{DATASET_NAME}" if purpose == "smoke" else f"data/{DATASET_NAME}"
    )
    campaign_root = (args.root or default_root).resolve()
    if args.action == "plan":
        plan(rows, campaign_root, purpose, policy)
    elif args.action == "verify":
        verify_campaign(rows, campaign_root, purpose)
        print(json.dumps({"status": "ready", "rows": len(rows)}, sort_keys=True))
    else:
        run_campaign(rows, campaign_root, purpose, policy)
    return 0


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, interrupt_on_termination)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, interrupt_on_termination)
    try:
        raise SystemExit(main())
    except (ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("error: campaign interrupted; active process groups were stopped", file=sys.stderr)
        raise SystemExit(130)
    finally:
        terminate_process_groups(list(ACTIVE_PROCESS_GROUPS))
        ACTIVE_PROCESS_GROUPS.clear()
