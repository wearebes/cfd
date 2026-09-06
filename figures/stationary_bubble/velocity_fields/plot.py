#!/usr/bin/env python3
"""Plot stationary-bubble velocity fields directly from canonical run data."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import gzip
import math
import os
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True
os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "cfd-velocity-fields-mpl")
)
os.environ.setdefault(
    "XDG_CACHE_HOME", str(Path(tempfile.gettempdir()) / "cfd-velocity-fields-cache")
)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np


HERE = Path(__file__).resolve().parent
REPOSITORY_ROOT = HERE.parents[2]
FIGURES_ROOT = HERE.parents[1]
sys.path.insert(0, str(FIGURES_ROOT))

from cfd_style import (  # noqa: E402
    FIELD_CMAP,
    INTERFACE_COLOR,
    INTERFACE_LINEWIDTH_PT,
    MATH_TEXT_PT,
    PANEL_LABEL_STYLE,
    apply_cfd_style,
    canonical_method_label,
    figure_size,
    save_figure,
    save_figure_pdf,
    save_figure_svg,
)
from data_paths import (  # noqa: E402
    canonical_run_dir,
    data_root as find_data_root,
    nn_precision_output_suffix,
)


ARROW_THRESHOLD_DEFAULT = 1.0e-17
VMIN_DEFAULT = 1.0e-18
VMAX_DEFAULT = 1.0e-8
DEFAULT_METHODS = ("vof-hf", "clsvof", "clsvof-nn")
NN_SOURCE_CHOICES = ("standard", "crossing")
STATIONARY_RADIUS = 0.4
MANUSCRIPT_STEM = (
    "N32_tau1_vof-hf_clsvof-crossing_nn-crossing"
)
FIGURE_HEIGHT_MM = 64.0


@dataclass(frozen=True)
class MethodSpec:
    key: str
    label: str
    source_method: str


def method_specs(nn_source: str) -> dict[str, MethodSpec]:
    if nn_source not in NN_SOURCE_CHOICES:
        raise ValueError(f"unknown CLSVOF source variant: {nn_source}")
    crossing = nn_source == "crossing"
    clsvof_method = "CLSVOF-native-C2" if crossing else "CLSVOF"
    nn_method = "Cell-NN-C2" if crossing else "NN"
    return {
        "vof-hf": MethodSpec(
            "vof-hf", canonical_method_label("vof-hf"), "VOF-HF"
        ),
        "clsvof": MethodSpec(
            "clsvof", canonical_method_label("clsvof"), clsvof_method
        ),
        "clsvof-nn": MethodSpec(
            "clsvof-nn", canonical_method_label("clsvof-nn"), nn_method
        ),
    }


def parse_method_keys(value: str) -> tuple[str, ...]:
    keys = tuple(part.strip().lower() for part in value.split(",") if part.strip())
    if not keys:
        raise argparse.ArgumentTypeError("at least one method is required")
    allowed = set(DEFAULT_METHODS)
    unknown = sorted(set(keys) - allowed)
    if unknown:
        raise argparse.ArgumentTypeError(
            "unknown method(s): {}; choose from {}".format(
                ", ".join(unknown), ", ".join(DEFAULT_METHODS)
            )
        )
    if len(set(keys)) != len(keys):
        raise argparse.ArgumentTypeError("methods must not be repeated")
    return keys


def snapshot_for_tau(tau: float, override: str | None = None) -> str:
    if override is not None:
        return override
    if math.isclose(tau, 1.0, abs_tol=1.0e-12):
        return "middle"
    return "final"


def format_tau(tau: float) -> str:
    return f"{tau:g}".replace(".", "p")


def output_stem(
    resolution: int,
    tau: float,
    method_keys: tuple[str, ...],
    nn_source: str,
) -> str:
    tags = list(method_keys)
    if nn_source == "crossing":
        if "clsvof-nn" not in tags:
            raise ValueError("crossing source requires the CLSVOF-NN panel")
        if "clsvof" not in tags:
            raise ValueError("crossing source requires the matched CLSVOF panel")
        tags[tags.index("clsvof")] = "clsvof-crossing"
        tags[tags.index("clsvof-nn")] = "nn-crossing"
    return f"N{resolution}_tau{format_tau(tau)}_{'_'.join(tags)}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render a stationary-bubble velocity-field comparison directly "
            "from canonical fields.csv.gz files."
        )
    )
    parser.add_argument("--resolution", type=int, required=True)
    parser.add_argument("--tau", type=float, required=True)
    parser.add_argument(
        "--snapshot",
        choices=("middle", "final"),
        default=None,
        help="Explicit stored snapshot label for diagnostic intermediate times.",
    )
    parser.add_argument(
        "--methods",
        type=parse_method_keys,
        default=DEFAULT_METHODS,
        help="Comma-separated panel order: " + ", ".join(DEFAULT_METHODS),
    )
    parser.add_argument(
        "--nn-source",
        choices=NN_SOURCE_CHOICES,
        default="standard",
        help=(
            "Use the standard CLSVOF/CLSVOF-NN pair or the matched crossing "
            "CLSVOF-native-C2/NN-interface-C2 pair."
        ),
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=find_data_root(repo_root=REPOSITORY_ROOT),
        help="Canonical data root (default: CFD_DATA_ROOT or repository data/).",
    )
    parser.add_argument("--output-dir", type=Path, default=HERE)
    parser.add_argument("--vmin", type=float, default=VMIN_DEFAULT)
    parser.add_argument("--vmax", type=float, default=VMAX_DEFAULT)
    parser.add_argument(
        "--arrow-threshold", type=float, default=ARROW_THRESHOLD_DEFAULT
    )
    parser.add_argument(
        "--mark-band-max-cells",
        type=int,
        default=0,
        help=(
            "Mark the maximum-speed cell in a band with this total width, "
            "in grid-spacing units, centred on the analytic interface."
        ),
    )
    return parser.parse_args()


def source_path(
    spec: MethodSpec, data_root: Path, resolution: int
) -> Path:
    run_dir = canonical_run_dir(
        "stationary_bubble",
        spec.source_method,
        resolution,
        grid="uniform",
        imax=(
            None
            if spec.source_method in {"VOF-HF", "Cell-NN-C2"}
            else 0
        ),
        steps=0 if spec.source_method == "Cell-NN-C2" else None,
        root=data_root,
    )
    compressed = run_dir / "fields.csv.gz"
    return compressed if compressed.is_file() else run_dir / "fields.csv"


def load_field(
    spec: MethodSpec,
    path: Path,
    resolution: int,
    tau_expected: float,
    snapshot_override: str | None = None,
) -> dict[str, np.ndarray | str]:
    if not path.is_file():
        raise FileNotFoundError(f"{spec.key}: canonical field does not exist: {path}")

    snapshot = snapshot_for_tau(tau_expected, snapshot_override)
    required = {
        "snapshot",
        "actual_benchmark_time",
        "x",
        "y",
        "Delta",
        "u_x",
        "u_y",
        "phase_fraction",
    }
    selected: list[dict[str, str]] = []
    open_field = gzip.open if path.suffix == ".gz" else open
    with open_field(path, "rt", newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{spec.key}: missing fields: {sorted(missing)}")
        selected = [row for row in reader if row["snapshot"] == snapshot]

    expected_cells = resolution * resolution
    if len(selected) != expected_cells:
        raise ValueError(
            f"{spec.key}: expected {expected_cells} {snapshot} cells, "
            f"found {len(selected)}"
        )

    tau = np.asarray(
        [float(row["actual_benchmark_time"]) for row in selected], dtype=float
    )
    delta = np.asarray([float(row["Delta"]) for row in selected], dtype=float)
    x = np.asarray([float(row["x"]) for row in selected], dtype=float)
    y = np.asarray([float(row["y"]) for row in selected], dtype=float)
    u_x = np.asarray([float(row["u_x"]) for row in selected], dtype=float)
    u_y = np.asarray([float(row["u_y"]) for row in selected], dtype=float)
    phase = np.asarray(
        [float(row["phase_fraction"]) for row in selected], dtype=float
    )
    arrays = (tau, delta, x, y, u_x, u_y, phase)
    if not all(np.isfinite(array).all() for array in arrays):
        raise ValueError(f"{spec.key}: non-finite canonical field values")
    if not np.allclose(tau, tau_expected, atol=1.0e-12, rtol=0.0):
        raise ValueError(f"{spec.key}: canonical snapshot is not at tau={tau_expected:g}")
    if not np.allclose(delta, 1.0 / resolution, atol=1.0e-14, rtol=0.0):
        raise ValueError(f"{spec.key}: canonical field is not uniform N={resolution}")

    x_unique = np.unique(x)
    y_unique = np.unique(y)
    if len(x_unique) != resolution or len(y_unique) != resolution:
        raise ValueError(f"{spec.key}: invalid {resolution}x{resolution} coordinates")
    order = np.lexsort((x, y))
    shape = (resolution, resolution)
    return {
        "label": spec.label,
        "x": x_unique,
        "y": y_unique,
        "u_x": u_x[order].reshape(shape),
        "u_y": u_y[order].reshape(shape),
        "speed": np.hypot(u_x, u_y)[order].reshape(shape),
        "phase": phase[order].reshape(shape),
    }


def add_direction_arrows(
    ax: plt.Axes,
    item: dict[str, np.ndarray | str],
    resolution: int,
    threshold: float,
) -> None:
    stride = max(1, resolution // 8)
    offset = max(0, stride // 2)
    arrow_slice = np.s_[offset::stride, offset::stride]
    x_grid, y_grid = np.meshgrid(item["x"], item["y"])
    arrow_speed = item["speed"][arrow_slice]
    valid = arrow_speed >= threshold
    direction_x = np.ma.masked_where(
        ~valid,
        np.divide(
            item["u_x"][arrow_slice],
            arrow_speed,
            out=np.zeros_like(arrow_speed),
            where=arrow_speed > 0.0,
        ),
    )
    direction_y = np.ma.masked_where(
        ~valid,
        np.divide(
            item["u_y"][arrow_slice],
            arrow_speed,
            out=np.zeros_like(arrow_speed),
            where=arrow_speed > 0.0,
        ),
    )
    ax.quiver(
        x_grid[arrow_slice],
        y_grid[arrow_slice],
        direction_x,
        direction_y,
        angles="xy",
        scale_units="xy",
        scale=18.0,
        pivot="mid",
        color="white",
        edgecolor=INTERFACE_COLOR,
        # Remain above the 0.25 pt print threshold after the 190 mm artwork is
        # reduced to the common manuscript's 468 pt text width.
        linewidth=0.30,
        width=0.006,
        headwidth=3.5,
        headlength=4.5,
        headaxislength=4.0,
        zorder=4,
    )


def main() -> None:
    args = parse_args()
    if args.resolution <= 0:
        raise ValueError("resolution must be positive")
    if not (args.tau > 0.0 and math.isfinite(args.tau)):
        raise ValueError("tau must be finite and positive")
    if not (args.vmin > 0.0 and math.isfinite(args.vmin)):
        raise ValueError("vmin must be finite and positive")
    if not (args.vmax > args.vmin and math.isfinite(args.vmax)):
        raise ValueError("vmax must be finite and greater than vmin")
    if args.arrow_threshold < 0.0 or not math.isfinite(args.arrow_threshold):
        raise ValueError("arrow-threshold must be finite and nonnegative")
    if args.mark_band_max_cells < 0:
        raise ValueError("mark-band-max-cells must be nonnegative")

    data_root = args.data_root.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    specs = method_specs(args.nn_source)
    fields = {
        key: load_field(
            specs[key],
            source_path(specs[key], data_root, args.resolution),
            args.resolution,
            args.tau,
            args.snapshot,
        )
        for key in args.methods
    }
    speed_max = max(float(np.max(fields[key]["speed"])) for key in args.methods)
    if speed_max > args.vmax:
        raise ValueError(
            f"shared vmax={args.vmax:.6g} clips data maximum {speed_max:.6g}"
        )

    apply_cfd_style()
    norm = LogNorm(vmin=args.vmin, vmax=args.vmax, clip=True)
    fig, axes_grid = plt.subplots(
        1,
        len(args.methods),
        figsize=figure_size("double", FIGURE_HEIGHT_MM),
        sharex=True,
        sharey=True,
        squeeze=False,
    )
    axes = axes_grid[0]
    fig.subplots_adjust(left=0.065, right=0.90, bottom=0.19, top=0.84, wspace=0.10)

    mesh = None
    edges = np.linspace(0.0, 1.0, args.resolution + 1)
    interface_width = sum(INTERFACE_LINEWIDTH_PT) / 2.0
    theta = np.linspace(0.0, 0.5 * np.pi, 361)
    for panel_index, (ax, key) in enumerate(zip(axes, args.methods, strict=True)):
        item = fields[key]
        mesh = ax.pcolormesh(
            edges,
            edges,
            item["speed"],
            cmap=FIELD_CMAP["nonnegative"],
            norm=norm,
            shading="flat",
        )
        ax.contour(
            item["x"],
            item["y"],
            item["phase"],
            levels=[0.5],
            colors=INTERFACE_COLOR,
            linewidths=interface_width,
        )
        if args.mark_band_max_cells:
            half_width = 0.5 * args.mark_band_max_cells / args.resolution
            for radius in (
                STATIONARY_RADIUS - half_width,
                STATIONARY_RADIUS + half_width,
            ):
                ax.plot(
                    radius * np.cos(theta),
                    radius * np.sin(theta),
                    color="white",
                    linewidth=0.9,
                    linestyle=(0, (2.0, 1.5)),
                    zorder=5,
                )
            x_grid, y_grid = np.meshgrid(item["x"], item["y"])
            in_band = (
                np.abs(np.hypot(x_grid, y_grid) - STATIONARY_RADIUS)
                <= half_width
            )
            band_speed = np.where(in_band, item["speed"], -np.inf)
            row, column = np.unravel_index(np.argmax(band_speed), band_speed.shape)
            max_x = float(x_grid[row, column])
            max_y = float(y_grid[row, column])
            max_speed = float(item["speed"][row, column])
            ax.scatter(
                [max_x],
                [max_y],
                s=34.0,
                marker="o",
                facecolor="#F05A28",
                edgecolor="white",
                linewidth=1.0,
                zorder=7,
            )
            print(
                f"{key}: band={args.mark_band_max_cells}h, "
                f"x={max_x:.9g}, y={max_y:.9g}, |u|={max_speed:.12e}"
            )
        add_direction_arrows(ax, item, args.resolution, args.arrow_threshold)
        ax.set_aspect("equal")
        ax.set_xlim(0.0, 1.0)
        ax.set_ylim(0.0, 1.0)
        ax.set_xticks((0.0, 0.5, 1.0))
        ax.set_yticks((0.0, 0.5, 1.0))
        ax.set_title(str(item["label"]), pad=5.0)
        ax.set_xlabel(r"$x$")
        ax.text(
            s=f"({chr(ord('a') + panel_index)})",
            transform=ax.transAxes,
            **PANEL_LABEL_STYLE,
        )
    axes[0].set_ylabel(r"$y$")

    # Keep colorbar tick labels inside the >= 3 mm visible-right-margin guard.
    color_axis = fig.add_axes((0.917, 0.215, 0.018, 0.565))
    colorbar = fig.colorbar(mesh, cax=color_axis)
    # Matplotlib rasterizes dense colorbar solids by default.  Keep the
    # manuscript PDF/SVG fully vector, matching the pcolormesh panels.
    colorbar.solids.set_rasterized(False)
    colorbar.ax.set_title(r"$|\mathbf{u}|$", pad=5.0)
    colorbar.ax.tick_params(
        direction="in", length=3.0, labelsize=MATH_TEXT_PT
    )

    base_stem = output_stem(
        args.resolution, args.tau, args.methods, args.nn_source
    )
    stem = base_stem + nn_precision_output_suffix()
    output = output_dir / f"velocity_field_{stem}.png"
    saved_output = save_figure(fig, output.with_suffix(""))
    plt.close(fig)
    if saved_output != output:
        raise ValueError(f"unexpected output path: {saved_output}")
    print(output)


if __name__ == "__main__":
    main()
