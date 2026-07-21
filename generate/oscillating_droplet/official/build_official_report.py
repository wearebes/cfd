#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import Path


METHODS = {
    "standard": {
        "title": "Standard",
        "ref": "oscillation.ref",
        "compile": "official default branch",
    },
    "momentum": {
        "title": "Momentum",
        "ref": "oscillation-momentum.ref",
        "compile": "-DMOMENTUM=1",
    },
    "compressible": {
        "title": "Compressible",
        "ref": "oscillation-compressible.ref",
        "compile": "-DCOMPRESSIBLE=1",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_exact_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def parse_hash_listing(text: str, repo: Path) -> dict[str, str]:
    hashes = {}
    for line in text.splitlines():
        digest, path_text = line.split(maxsplit=1)
        path = Path(path_text)
        try:
            name = str(path.relative_to(repo))
        except ValueError:
            name = str(path)
        hashes[name] = digest
    return hashes


def parse_keyed(path: Path, prefix: str = "") -> dict[str, list[str]]:
    parsed = {}
    for line in read_exact_lines(path):
        fields = line.split()
        if not fields:
            continue
        if prefix:
            if fields[0] != prefix or len(fields) < 2:
                raise ValueError(f"unexpected line in {path}: {line}")
            parsed[fields[1]] = fields[2:]
        else:
            parsed[fields[0]] = fields[1:]
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--mirror", type=Path, required=True)
    parser.add_argument("--make-exit-status", type=int, required=True)
    parser.add_argument("--started-at", required=True)
    parser.add_argument("--ended-at", required=True)
    parser.add_argument("--wall-seconds", type=int, required=True)
    args = parser.parse_args()

    repo = args.repo.resolve()
    dataset = args.dataset.resolve()
    refs = dataset / "source_snapshot"

    before = (dataset / "source_hashes_before.txt").read_text(encoding="utf-8")
    after = (dataset / "source_hashes_after.txt").read_text(encoding="utf-8")
    source_unchanged = before == after
    recovery_commands = read_exact_lines(dataset / "recovery_commands.txt")
    recovery_status = read_exact_lines(dataset / "recovery_status.txt")

    manifest = {
        "schema_version": 1,
        "case": "official_basilisk_elliptical_droplet_oscillation",
        "source": "basilisk/src/test/oscillation.c",
        "command": "make -o Makefile.deps oscillation.tst",
        "make_exit_status": args.make_exit_status,
        "started_at": args.started_at,
        "ended_at": args.ended_at,
        "wall_seconds": args.wall_seconds,
        "mirror_path": str(args.mirror),
        "source_unchanged": source_unchanged,
        "official_input_sha256_before": parse_hash_listing(before, repo),
        "official_input_sha256_after": parse_hash_listing(after, repo),
        "levels": [4, 5, 6, 7],
        "grid_sizes": [16, 32, 64, 128],
        "cells_per_diameter": ["6.4", "12.8", "25.6", "51.2"],
        "aggregate_stopped_on_strict_diff": args.make_exit_status != 0,
        "recovery_commands": recovery_commands,
        "recovery_status": recovery_status,
        "methods": {},
    }

    report = [
        "# Official Basilisk Elliptical Droplet Oscillation Reproduction",
        "",
        "本报告只使用官方 `oscillation.c`、官方 Makefile/runtest 规则和官方 `.ref`。",
        "未增加观测量、未改变数值设置、未拆分 LEVEL、未重新拟合。",
        "",
        "官方方法只有 Standard、Momentum 和 Compressible；CLSVOF matched port 不属于官方复现。",
        "",
        "## Execution",
        "",
        "```text",
        "make -o Makefile.deps oscillation.tst",
        "```",
        "",
        f"- aggregate make exit status: `{args.make_exit_status}`",
        f"- source hashes unchanged: `{str(source_unchanged).lower()}`",
        f"- mirror: `{args.mirror}`",
        "- aggregate target stopped at the first strict `.ref` mismatch; remaining official branches were completed with the recorded official Make/runtest recipes.",
        "- recovery command/status evidence: `recovery_commands.txt`, `recovery_status.txt`",
        "",
    ]

    overall_complete = True
    for method, info in METHODS.items():
        directory = dataset / method
        ref_path = refs / info["ref"]
        log_path = directory / "log"
        required = [directory / name for name in ("error", "laplace", "out", "log")]
        required += [directory / f"k-{level}" for level in range(4, 8)]
        required += [directory / f"fit-{level}" for level in range(4, 8)]
        complete = directory.is_dir() and all(
            path.is_file() and path.stat().st_size > 0 for path in required
        )
        overall_complete = overall_complete and complete

        actual = read_exact_lines(log_path) if log_path.exists() else []
        expected = read_exact_lines(ref_path)
        diff_lines = list(
            difflib.unified_diff(
                expected, actual,
                fromfile=f"source_snapshot/{info['ref']}",
                tofile=f"{method}/log",
                lineterm="",
            )
        )
        (directory / "log_vs_ref.diff").write_text(
            "\n".join(diff_lines) + ("\n" if diff_lines else ""),
            encoding="utf-8",
        )
        strict_match = complete and not diff_lines
        status = (
            "official_pass" if strict_match else
            "official_regression_mismatch" if complete else
            "incomplete"
        )
        pass_present = (directory / "pass").exists()
        fail_present = (directory / "fail").exists()
        warn_present = (directory / "warn").exists()

        manifest["methods"][method] = {
            "title": info["title"],
            "compile_selection": info["compile"],
            "status": status,
            "complete_artifacts": complete,
            "strict_log_ref_match": strict_match,
            "pass_present": pass_present,
            "fail_present": fail_present,
            "warn_present": warn_present,
            "actual_log_sha256": sha256(log_path) if log_path.exists() else None,
            "official_ref_sha256": sha256(ref_path),
        }

        report += [
            f"## {info['title']}",
            "",
            f"- compile selection: `{info['compile']}`",
            f"- status: `{status}`",
            f"- strict log/ref match: `{str(strict_match).lower()}`",
            f"- pass/fail/warn present: `{pass_present}/{fail_present}/{warn_present}`",
            "",
        ]

        if complete:
            fits = parse_keyed(log_path, "fit")
            errors = parse_keyed(directory / "error")
            laplace = parse_keyed(directory / "laplace")
            report += [
                "| cells/D | a | b | c | frequency error | equivalent Laplace |",
                "|---:|---:|---:|---:|---:|---:|",
            ]
            for cells in ("6.4", "12.8", "25.6", "51.2"):
                fit = fits[cells]
                frequency_error = " ".join(errors[cells][:-1])
                equivalent_laplace = " ".join(laplace[cells][:-1])
                report.append(
                    f"| {cells} | {fit[0]} | {fit[1]} | {fit[2]} | "
                    f"{frequency_error} | {equivalent_laplace} |"
                )
            report += [
                "",
                "### Exact `log`",
                "",
                "```text",
                *read_exact_lines(log_path),
                "```",
                "",
                "### Exact `error`",
                "",
                "```text",
                *read_exact_lines(directory / "error"),
                "```",
                "",
                "### Exact `laplace`",
                "",
                "```text",
                *read_exact_lines(directory / "laplace"),
                "```",
                "",
            ]
            if diff_lines:
                report += [
                    "### Strict diff",
                    "",
                    "```diff",
                    *diff_lines,
                    "```",
                    "",
                ]

    manifest["all_methods_complete"] = overall_complete
    manifest["overall_status"] = (
        "official_pass"
        if overall_complete and all(
            item["status"] == "official_pass"
            for item in manifest["methods"].values()
        )
        else "official_regression_mismatch"
        if overall_complete else "incomplete"
    )

    report += [
        "## Final status",
        "",
        f"`{manifest['overall_status']}`",
        "",
        "严格 diff 不一致时，本报告保留本机实际值与原始 diff；没有修改官方参考值或拟合精度。",
        "",
    ]

    (dataset / "official_report.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (dataset / "OFFICIAL_RESULTS.md").write_text(
        "\n".join(report), encoding="utf-8"
    )

    verification = {
        "source_hashes_unchanged": source_unchanged,
        "all_methods_complete": overall_complete,
        "method_statuses": {
            name: item["status"] for name, item in manifest["methods"].items()
        },
        "overall_status": manifest["overall_status"],
        "report_present": (dataset / "OFFICIAL_RESULTS.md").is_file(),
    }
    (dataset / "verification.json").write_text(
        json.dumps(verification, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(verification, sort_keys=True))
    return 0 if source_unchanged and overall_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
