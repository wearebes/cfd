#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent


def number(row: dict[str, str], key: str) -> float | None:
    value = row.get(key, "")
    if value == "":
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def delta_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    completed = [row for row in rows if row["execution_state"] == "completed"]
    references = {
        (row["benchmark"], row["method"], row["N"]): row
        for row in completed
        if row["imax"] == "3"
    }
    output = []
    metric_keys = (
        "relative_rms",
        "amplitude_l2_error",
        "max_abs_amplitude_error",
        "final_volume_drift",
        "max_abs_volume_drift",
        "final_center",
        "final_velocity",
        "peak_velocity",
        "time_at_peak_velocity",
        "shape_mean_distance",
        "shape_max_distance",
        "center_reference_rmse",
        "velocity_reference_rmse",
        "post_b15_egrad_mean",
        "post_b15_egrad_mean_p95",
        "post_b15_egrad_linf",
        "run_seconds",
    )
    for row in completed:
        key = (row["benchmark"], row["method"], row["N"])
        reference = references.get(key)
        if reference is None:
            continue
        record: dict[str, Any] = {
            "row_id": row["row_id"],
            "benchmark": row["benchmark"],
            "method": row["method"],
            "N": int(row["N"]),
            "imax": int(row["imax"]),
            "reference_imax": 3,
        }
        for metric in metric_keys:
            value = number(row, metric)
            baseline = number(reference, metric)
            record[metric] = value
            record[f"delta_{metric}"] = (
                value - baseline if value is not None and baseline is not None else None
            )
            record[f"ratio_{metric}"] = (
                value / baseline
                if value is not None and baseline not in (None, 0.0)
                else None
            )
        output.append(record)
    return sorted(output, key=lambda row: (row["benchmark"], row["method"], row["N"], row["imax"]))


def paired_method_deltas(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    completed = [row for row in rows if row["execution_state"] == "completed"]
    groups: dict[tuple[str, int, int], dict[str, dict[str, str]]] = defaultdict(dict)
    for row in completed:
        groups[(row["benchmark"], int(row["N"]), int(row["imax"]))][row["method"]] = row
    metrics = (
        "relative_rms", "amplitude_l2_error", "max_abs_amplitude_error",
        "final_volume_drift", "max_abs_volume_drift", "final_center",
        "final_velocity", "peak_velocity", "shape_mean_distance",
        "shape_max_distance", "center_reference_rmse", "velocity_reference_rmse",
        "post_b15_egrad_mean", "post_b15_egrad_mean_p95", "post_b15_egrad_linf",
        "run_seconds",
    )
    output = []
    for (benchmark, n, imax), methods in sorted(groups.items()):
        native = methods.get("clsvof_native")
        nn = methods.get("clsvof_nn")
        if native is None or nn is None:
            continue
        record: dict[str, Any] = {
            "benchmark": benchmark,
            "N": n,
            "imax": imax,
            "native_row_id": native["row_id"],
            "nn_row_id": nn["row_id"],
        }
        for metric in metrics:
            native_value = number(native, metric)
            nn_value = number(nn, metric)
            record[f"native_{metric}"] = native_value
            record[f"nn_{metric}"] = nn_value
            record[f"delta_nn_minus_native_{metric}"] = (
                nn_value - native_value
                if native_value is not None and nn_value is not None
                else None
            )
            record[f"ratio_nn_over_native_{metric}"] = (
                nn_value / native_value
                if nn_value is not None and native_value not in (None, 0.0)
                else None
            )
        output.append(record)
    return output


def log_slope(points: list[tuple[int, float]], negate: bool = False) -> float | None:
    usable = [(n, value) for n, value in points if n > 0 and value > 0]
    if len(usable) < 2:
        return None
    xs = [math.log(n) for n, _ in usable]
    ys = [math.log(value) for _, value in usable]
    xmean = sum(xs) / len(xs)
    ymean = sum(ys) / len(ys)
    denominator = sum((value - xmean) ** 2 for value in xs)
    if denominator == 0:
        return None
    slope = sum((x - xmean) * (y - ymean) for x, y in zip(xs, ys)) / denominator
    return -slope if negate else slope


def convergence_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    completed = [
        row for row in rows
        if row["execution_state"] == "completed" and row["benchmark"] == "capwave"
    ]
    groups: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for row in completed:
        groups[(row["method"], int(row["imax"]))].append(row)
    output = []
    for (method, imax), selected in sorted(groups.items()):
        selected.sort(key=lambda row: int(row["N"]))
        errors = [(int(row["N"]), number(row, "relative_rms")) for row in selected]
        runtimes = [(int(row["N"]), number(row, "run_seconds")) for row in selected]
        valid_errors = [(n, value) for n, value in errors if value is not None]
        valid_runtimes = [(n, value) for n, value in runtimes if value is not None]
        record: dict[str, Any] = {
            "benchmark": "capwave",
            "method": method,
            "imax": imax,
            "N_values": ",".join(str(n) for n, _ in valid_errors),
            "relative_rms_values": ",".join(f"{value:.17g}" for _, value in valid_errors),
            "observed_order_global": log_slope(valid_errors, negate=True),
            "runtime_scaling_global": log_slope(valid_runtimes),
        }
        for (n0, value0), (n1, value1) in zip(valid_errors, valid_errors[1:]):
            record[f"observed_order_{n0}_{n1}"] = -math.log(value1 / value0) / math.log(n1 / n0)
        output.append(record)
    return output


def rankdata(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    index = 0
    while index < len(order):
        end = index + 1
        while end < len(order) and values[order[end]] == values[order[index]]:
            end += 1
        average_rank = (index + 1 + end) / 2.0
        for position in order[index:end]:
            ranks[position] = average_rank
        index = end
    return ranks


def pearson(x: list[float], y: list[float]) -> float | None:
    if len(x) != len(y) or len(x) < 2:
        return None
    xmean = sum(x) / len(x)
    ymean = sum(y) / len(y)
    numerator = sum((a - xmean) * (b - ymean) for a, b in zip(x, y))
    denominator = math.sqrt(
        sum((a - xmean) ** 2 for a in x) * sum((b - ymean) ** 2 for b in y)
    )
    return numerator / denominator if denominator else None


def physical_metric(benchmark: str) -> str:
    return "relative_rms" if benchmark == "capwave" else "velocity_reference_rmse"


def pareto_imax(rows: list[dict[str, str]], metrics: tuple[str, ...]) -> str:
    points = []
    for row in rows:
        values = tuple(number(row, metric) for metric in metrics)
        if all(value is not None for value in values):
            points.append((int(row["imax"]), tuple(float(value) for value in values)))
    frontier = []
    for imax, values in points:
        dominated = any(
            all(other_value <= value for other_value, value in zip(other, values))
            and any(other_value < value for other_value, value in zip(other, values))
            for other_imax, other in points
            if other_imax != imax
        )
        if not dominated:
            frontier.append(imax)
    return ",".join(str(value) for value in sorted(frontier))


def tradeoff_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    completed = [row for row in rows if row["execution_state"] == "completed"]
    groups: dict[tuple[str, str, int], list[dict[str, str]]] = defaultdict(list)
    for row in completed:
        groups[(row["benchmark"], row["method"], int(row["N"]))].append(row)
    output = []
    for (benchmark, method, n), selected in sorted(groups.items()):
        if len(selected) != 6 or {int(row["imax"]) for row in selected} != set(range(6)):
            continue
        metric = physical_metric(benchmark)
        physical = [(row, number(row, metric)) for row in selected]
        sdf = [(row, number(row, "post_b15_egrad_mean")) for row in selected]
        cost = [(row, number(row, "run_seconds")) for row in selected]
        if any(value is None for _, value in physical + sdf + cost):
            continue
        best_physical = min(physical, key=lambda item: float(item[1]))
        best_sdf = min(sdf, key=lambda item: float(item[1]))
        best_cost = min(cost, key=lambda item: float(item[1]))
        stock = next(row for row in selected if int(row["imax"]) == 3)
        output.append(
            {
                "benchmark": benchmark,
                "method": method,
                "N": n,
                "physical_metric": metric,
                "best_physics_imax": int(best_physical[0]["imax"]),
                "best_physics_value": best_physical[1],
                "best_sdf_imax": int(best_sdf[0]["imax"]),
                "best_sdf_value": best_sdf[1],
                "lowest_cost_imax": int(best_cost[0]["imax"]),
                "lowest_cost_seconds": best_cost[1],
                "stock_imax3_physics": number(stock, metric),
                "stock_imax3_sdf": number(stock, "post_b15_egrad_mean"),
                "stock_imax3_seconds": number(stock, "run_seconds"),
                "pareto_physics_runtime_imax": pareto_imax(selected, (metric, "run_seconds")),
                "pareto_physics_sdf_runtime_imax": pareto_imax(
                    selected, (metric, "post_b15_egrad_mean", "run_seconds")
                ),
            }
        )
    return output


def relationship_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    completed = [row for row in rows if row["execution_state"] == "completed"]
    groups: dict[tuple[str, str, int], list[dict[str, str]]] = defaultdict(list)
    for row in completed:
        groups[(row["benchmark"], row["method"], int(row["N"]))].append(row)
    output = []
    for (benchmark, method, n), selected in sorted(groups.items()):
        if len(selected) != 6 or {int(row["imax"]) for row in selected} != set(range(6)):
            continue
        metric = physical_metric(benchmark)
        selected.sort(key=lambda row: int(row["imax"]))
        sdf = [number(row, "post_b15_egrad_mean") for row in selected]
        physics = [number(row, metric) for row in selected]
        if any(value is None for value in sdf + physics):
            continue
        sdf_values = [float(value) for value in sdf]
        physics_values = [float(value) for value in physics]
        output.append(
            {
                "benchmark": benchmark,
                "method": method,
                "N": n,
                "physical_metric": metric,
                "samples": len(selected),
                "spearman_egrad_vs_physics": pearson(
                    rankdata(sdf_values), rankdata(physics_values)
                ),
                "pearson_egrad_vs_physics": pearson(sdf_values, physics_values),
                "egrad_monotone_nonincreasing_with_imax": all(
                    right <= left for left, right in zip(sdf_values, sdf_values[1:])
                ),
                "physics_monotone_nonincreasing_with_imax": all(
                    right <= left for left, right in zip(physics_values, physics_values[1:])
                ),
            }
        )
    return output


def mean(values: list[float | None]) -> float | None:
    finite = [value for value in values if value is not None and math.isfinite(value)]
    return sum(finite) / len(finite) if finite else None


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["benchmark"], row["method"], row["imax"])].append(row)
    output = []
    for (benchmark, method, imax), selected in sorted(groups.items()):
        record: dict[str, Any] = {
            "benchmark": benchmark,
            "method": method,
            "imax": imax,
            "completed_resolutions": len(selected),
            "N_values": ",".join(str(row["N"]) for row in selected),
        }
        for metric in (
            "relative_rms",
            "max_abs_volume_drift",
            "shape_mean_distance",
            "center_reference_rmse",
            "velocity_reference_rmse",
            "post_b15_egrad_mean",
            "post_b15_egrad_mean_p95",
            "post_b15_egrad_linf",
            "run_seconds",
        ):
            record[f"mean_{metric}"] = mean([row.get(metric) for row in selected])
            record[f"mean_ratio_{metric}"] = mean(
                [row.get(f"ratio_{metric}") for row in selected]
            )
        for metric in ("final_center", "final_velocity", "peak_velocity"):
            deltas = [row.get(f"delta_{metric}") for row in selected]
            record[f"mean_abs_delta_{metric}"] = mean(
                [abs(value) if value is not None else None for value in deltas]
            )
        output.append(record)
    return output


def fields(rows: list[dict[str, Any]]) -> list[str]:
    preferred = ["row_id", "benchmark", "method", "N", "imax", "reference_imax"]
    discovered = {key for row in rows for key in row}
    return [key for key in preferred if key in discovered] + sorted(discovered - set(preferred))


def atomic_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = fields(rows)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def fmt(value: Any) -> str:
    if value is None or value == "":
        return "n/a"
    return f"{float(value):.6g}"


def median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def distribution(values: list[int]) -> str:
    counts = Counter(values)
    return ", ".join(f"{key}:{counts[key]}" for key in sorted(counts))


def build_report(
    matrix_id: str,
    raw: list[dict[str, str]],
    deltas: list[dict[str, Any]],
    tradeoffs: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    audit_passed: bool,
) -> str:
    completed = [row for row in raw if row["execution_state"] == "completed"]
    if audit_passed:
        evidence = "formal row audit passed"
    elif len(completed) == 96:
        evidence = "96 rows complete; strict row audit pending or failed"
    else:
        evidence = "formal in progress"
    lines = [
        "# CLSVOF redistance imax formal analysis",
        "",
        f"Matrix ID: `{matrix_id}`",
        "",
        f"Evidence level: **{evidence}** "
        f"({len(completed)}/96 rows completed).",
        "",
        "All deltas below use the same `(benchmark, method, N)` row at official `imax=3`",
        "as the reference. Scientific recommendations are gated on the 96-row audit.",
        "",
        "## Mechanism and evidence checks",
        "",
        f"- Returned-step range equals configured `imax` in "
        f"**{sum(number(row, 'returned_min') == int(row['imax']) and number(row, 'returned_max') == int(row['imax']) for row in completed)}/{len(completed)}** completed rows.",
        f"- Total recorded curvature clamp hits: **{sum(int(number(row, 'provider_clamp_hits') or 0) for row in completed)}**.",
        f"- Complete six-imax trade-off identities: **{len(tradeoffs)}/16**.",
        "",
        "## Capillary-wave matrix",
        "",
        "| Method | N | imax | relative RMS | delta vs 3 | Egrad mean (1.5D) | Egrad p95 | Egrad Linf | run s |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in deltas:
        if row["benchmark"] != "capwave":
            continue
        lines.append(
            f"| {row['method']} | {row['N']} | {row['imax']} | {fmt(row.get('relative_rms'))} "
            f"| {fmt(row.get('delta_relative_rms'))} | {fmt(row.get('post_b15_egrad_mean'))} "
            f"| {fmt(row.get('post_b15_egrad_mean_p95'))} | {fmt(row.get('post_b15_egrad_linf'))} "
            f"| {fmt(row.get('run_seconds'))} |"
        )
    lines.extend(
        [
            "",
            "## Rising-bubble Case 1 matrix",
            "",
            "| Method | N | imax | final xb | d xb | final vb | d vb | velocity RMSE | center RMSE | max vol drift | shape mean | Egrad mean (1.5D) | run s |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in deltas:
        if row["benchmark"] != "rising_case1":
            continue
        lines.append(
            f"| {row['method']} | {row['N']} | {row['imax']} | {fmt(row.get('final_center'))} "
            f"| {fmt(row.get('delta_final_center'))} | {fmt(row.get('final_velocity'))} "
            f"| {fmt(row.get('delta_final_velocity'))} | {fmt(row.get('velocity_reference_rmse'))} "
            f"| {fmt(row.get('center_reference_rmse'))} | {fmt(row.get('max_abs_volume_drift'))} "
            f"| {fmt(row.get('shape_mean_distance'))} "
            f"| {fmt(row.get('post_b15_egrad_mean'))} | {fmt(row.get('run_seconds'))} |"
        )
    lines.extend(
        [
            "",
            "## Physical, SDF, and runtime optima by identity",
            "",
            "| Benchmark | Method | N | physical metric | best physics imax | best SDF imax | lowest-cost imax | physics/runtime Pareto imax | stock imax3 physics |",
            "| --- | --- | ---: | --- | ---: | ---: | ---: | --- | ---: |",
        ]
    )
    for row in tradeoffs:
        lines.append(
            f"| {row['benchmark']} | {row['method']} | {row['N']} | {row['physical_metric']} "
            f"| {row['best_physics_imax']} | {row['best_sdf_imax']} | {row['lowest_cost_imax']} "
            f"| {row['pareto_physics_runtime_imax']} | {fmt(row['stock_imax3_physics'])} |"
        )
    lines.extend(["", "## Cross-resolution synthesis", ""])
    for benchmark in ("capwave", "rising_case1"):
        for method in ("clsvof_native", "clsvof_nn"):
            selected = [
                row for row in tradeoffs
                if row["benchmark"] == benchmark and row["method"] == method
            ]
            related = [
                row for row in relationships
                if row["benchmark"] == benchmark and row["method"] == method
            ]
            if not selected:
                continue
            penalties = [
                float(row["stock_imax3_physics"]) / float(row["best_physics_value"])
                for row in selected
                if float(row["best_physics_value"]) != 0.0
            ]
            stock_pareto = sum(
                3 in {int(value) for value in str(row["pareto_physics_runtime_imax"]).split(",") if value}
                for row in selected
            )
            lines.append(
                f"- `{benchmark}/{method}` ({len(selected)} resolutions): best-physics imax "
                f"distribution **{distribution([int(row['best_physics_imax']) for row in selected])}**; "
                f"best-SDF distribution **{distribution([int(row['best_sdf_imax']) for row in selected])}**; "
                f"`imax=3` lies on the physics/runtime Pareto frontier in **{stock_pareto}/{len(selected)}**; "
                f"median stock-to-best physical-error ratio **{fmt(median(penalties))}**; "
                f"E-grad is monotone nonincreasing in **{sum(bool(row['egrad_monotone_nonincreasing_with_imax']) for row in related)}/{len(related)}**, "
                f"whereas physical error is monotone nonincreasing in **{sum(bool(row['physics_monotone_nonincreasing_with_imax']) for row in related)}/{len(related)}**."
            )
    lines.extend(
        [
            "",
            "A lower E-grad is therefore reported separately from physical benchmark accuracy; "
            "the two are not treated as interchangeable objectives.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix-id", required=True)
    return parser.parse_args()


def final_summary(summary: str, report: str) -> str:
    marker = "## Final scientific synthesis"
    base = summary.split(marker, 1)[0].rstrip()
    synthesis_marker = "## Cross-resolution synthesis"
    if synthesis_marker not in report:
        raise RuntimeError("formal analysis is missing cross-resolution synthesis")
    synthesis = report.split(synthesis_marker, 1)[1].strip()
    return (
        f"{base}\n\n{marker}\n\n{synthesis}\n\n"
        "The complete row-by-row tables and physical/SDF/runtime optima are in `formal_analysis.md`.\n"
    )


def main() -> int:
    args = parse_args()
    root = HERE / "results" / args.matrix_id
    with (root / "metrics_wide.csv").open(newline="", encoding="utf-8") as stream:
        raw = list(csv.DictReader(stream))
    deltas = delta_rows(raw)
    paired = paired_method_deltas(raw)
    convergence = convergence_rows(raw)
    tradeoffs = tradeoff_rows(raw)
    relationships = relationship_rows(raw)
    aggregated = aggregate(deltas)
    atomic_csv(root / "delta_vs_imax3.csv", deltas)
    atomic_csv(root / "paired_native_nn_deltas.csv", paired)
    atomic_csv(root / "convergence_by_imax.csv", convergence)
    atomic_csv(root / "tradeoff_by_identity.csv", tradeoffs)
    atomic_csv(root / "sdf_physics_relationship.csv", relationships)
    atomic_csv(root / "aggregate_by_imax.csv", aggregated)
    audit_path = root / "audit.json"
    audit_passed = (
        json.loads(audit_path.read_text(encoding="utf-8")).get("passed") is True
        if audit_path.is_file()
        else False
    )
    report = build_report(
        args.matrix_id, raw, deltas, tradeoffs, relationships, audit_passed
    )
    temporary = root / "formal_analysis.md.tmp"
    temporary.write_text(report, encoding="utf-8")
    os.replace(temporary, root / "formal_analysis.md")
    if audit_passed and sum(row["execution_state"] == "completed" for row in raw) == 96:
        summary_path = root / "summary.md"
        summary = final_summary(summary_path.read_text(encoding="utf-8"), report)
        temporary = root / "summary.md.tmp"
        temporary.write_text(summary, encoding="utf-8")
        os.replace(temporary, summary_path)
    print(json.dumps({
        "completed": sum(row["execution_state"] == "completed" for row in raw),
        "delta_rows": len(deltas),
        "paired_rows": len(paired),
        "convergence_rows": len(convergence),
        "tradeoff_rows": len(tradeoffs),
        "relationship_rows": len(relationships),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
