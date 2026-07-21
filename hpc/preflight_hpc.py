#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hpc.lib.integrity import atomic_json, sha256_file  # noqa: E402
from hpc.lib.scheduler import available_cpu_ids, load_policy  # noqa: E402


def run(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def os_release() -> dict[str, str]:
    path = Path("/etc/os-release")
    if not path.is_file():
        return {}
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value.strip().strip('"')
    return result


def verify_provenance(lock_path: Path) -> tuple[list[dict[str, str]], list[str]]:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    records = []
    failures = []
    for relative, expected in lock["files"].items():
        path = ROOT / relative
        actual = sha256_file(path) if path.is_file() else "missing"
        records.append({"path": relative, "expected": expected, "actual": actual})
        if actual != expected:
            failures.append(f"provenance mismatch: {relative}")
    return records, failures


def topology_summary(text: str, visible: set[int]) -> dict[str, Any]:
    records = []
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
        if cpu in visible:
            records.append((cpu, core, socket, node))
    physical = {(socket, core) for _, core, socket, _ in records}
    sockets = {socket for _, _, socket, _ in records}
    nodes = {node for _, _, _, node in records}
    logical = len(records)
    return {
        "logical_cpus": logical,
        "physical_cores": len(physical),
        "sockets": len(sockets),
        "numa_nodes": len(nodes),
        "smt_threads_per_core": logical / len(physical) if physical else None,
        "records": [
            {"cpu": cpu, "core": core, "socket": socket, "node": node}
            for cpu, core, socket, node in records
        ],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix-id", required=True)
    parser.add_argument("--cpus", type=int, default=128)
    parser.add_argument(
        "--policy", type=Path, default=ROOT / "hpc/config/thread_policy.json"
    )
    parser.add_argument(
        "--provenance",
        type=Path,
        default=ROOT / "hpc/config/provenance.lock.json",
    )
    parser.add_argument("--allow-non-ubuntu", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    policy_path = args.policy.resolve()
    try:
        policy_relative = policy_path.relative_to(ROOT)
    except ValueError as error:
        raise SystemExit("--policy must be a file inside the repository") from error
    output = ROOT / "hpc/results" / args.matrix_id / "platform"
    output.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    release = os_release()
    if not args.allow_non_ubuntu:
        if platform.system() != "Linux":
            failures.append("target must be Linux")
        if release.get("ID") != "ubuntu" or release.get("VERSION_ID") != "22.04":
            failures.append("target must be Ubuntu 22.04")
        if platform.machine() not in {"x86_64", "amd64"}:
            failures.append("target must be x86_64")

    visible = available_cpu_ids()
    if args.cpus < 1:
        failures.append("--cpus must be positive")
    if args.cpus > len(visible):
        failures.append(
            f"requested {args.cpus} CPUs but only {len(visible)} are visible"
        )

    provenance, provenance_failures = verify_provenance(args.provenance)
    failures.extend(provenance_failures)
    policy, policy_hash = load_policy(policy_path)
    shutil.copy2(args.provenance, output / "provenance.lock.json")
    shutil.copy2(policy_path, output / "thread_policy.json")
    qcc = ROOT / "basilisk/src/qcc"
    if not qcc.is_file() or not os.access(qcc, os.X_OK):
        failures.append("basilisk/src/qcc is missing or not executable")

    command_reports: dict[str, Any] = {}
    for name, command in {
        "lscpu": ["lscpu"],
        "lscpu_extended": ["lscpu", "-e=CPU,CORE,SOCKET,NODE,ONLINE"],
        "lscpu_parse": ["lscpu", "-p=CPU,CORE,SOCKET,NODE"],
        "numactl": ["numactl", "--hardware"],
        "memory": ["free", "-h"],
        "disk": ["df", "-h", str(ROOT)],
        "qcc_file": ["file", str(qcc)],
        "gcc": ["gcc", "--version"],
        "gnuplot": ["gnuplot", "--version"],
    }.items():
        executable = shutil.which(command[0])
        if executable is None:
            command_reports[name] = {
                "command": command,
                "returncode": 127,
                "stdout": "",
                "stderr": "command not found",
            }
            if name in {"lscpu", "numactl", "qcc_file", "gcc", "gnuplot"}:
                failures.append(f"required command missing: {command[0]}")
            continue
        command_reports[name] = run([executable, *command[1:]])
        if command_reports[name]["returncode"] != 0:
            failures.append(f"preflight command failed: {name}")
        (output / f"{name}.txt").write_text(
            command_reports[name]["stdout"] + command_reports[name]["stderr"],
            encoding="utf-8",
        )

    gnuplot = shutil.which("gnuplot")
    fit_data = output / "gnuplot_fit_smoke.dat"
    fit_data.write_text("0 1\n1 3\n2 5\n3 7\n", encoding="utf-8")
    fit_log = output / "gnuplot_fit_smoke.log"
    if gnuplot:
        fit_expression = (
            f"set fit logfile '{fit_log}'; "
            "f(x)=a*x+b; a=1; b=0; "
            f"fit f(x) '{fit_data}' via a,b; "
            "if (abs(a-2)>1e-8 || abs(b-1)>1e-8) exit 1; print a,b"
        )
        command_reports["gnuplot_fit"] = run([gnuplot, "-e", fit_expression])
    else:
        command_reports["gnuplot_fit"] = {
            "command": ["gnuplot", "-e", "fit smoke"],
            "returncode": 127,
            "stdout": "",
            "stderr": "command not found",
        }
    if command_reports["gnuplot_fit"]["returncode"] != 0:
        failures.append("preflight command failed: gnuplot_fit")
    (output / "gnuplot_fit.txt").write_text(
        command_reports["gnuplot_fit"]["stdout"]
        + command_reports["gnuplot_fit"]["stderr"],
        encoding="utf-8",
    )

    payload = {
        "schema_version": 1,
        "status": "PASS" if not failures else "FAIL",
        "matrix_id": args.matrix_id,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "release": platform.release(),
            "python": platform.python_version(),
            "os_release": release,
        },
        "requested_cpus": args.cpus,
        "visible_cpu_ids": visible,
        "visible_cpu_count": len(visible),
        "cpu_topology": topology_summary(
            command_reports.get("lscpu_parse", {}).get("stdout", ""), set(visible)
        ),
        "policy_sha256": policy_hash,
        "policy": policy,
        "provenance": provenance,
        "commands": command_reports,
        "failures": failures,
    }
    atomic_json(output / "preflight.json", payload)
    capacity = {
        "schema_version": 1,
        "status": payload["status"],
        "matrix_id": args.matrix_id,
        "requested_cpus": args.cpus,
        "visible_cpu_count": len(visible),
        "policy_path": str(policy_relative),
        "policy_sha256": policy_hash,
        "measured_openmp_scaling": False,
        "note": "Initial policy only; formal release still requires target-host scaling canaries.",
    }
    atomic_json(output / "capacity.json", capacity)
    print(json.dumps({"status": payload["status"], "failures": failures}))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
