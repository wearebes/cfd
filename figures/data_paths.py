"""Canonical paths for CFD benchmark data consumed by figures.

The large ``data/`` tree is intentionally not a Python package.  Figure scripts
should use this module instead of spelling its on-disk layout themselves.  A
``CFD_DATA_ROOT`` override makes the same consumer runnable against a migration
staging tree before that tree is activated.

Canonical run directories have this shape::

    <data-root>/<case>/<mode>[/caseK]/<grid>/N####/[imax##|steps##]/<method>

Only the rising-bubble benchmark has a ``caseK`` component.  VOF-HF is the one
run method that never has a redistance-axis component.
"""

from __future__ import annotations

import os
import json
import hashlib
import warnings
from pathlib import Path
from typing import Mapping, Optional, Union


CFD_DATA_ROOT_ENV = "CFD_DATA_ROOT"

# Same switch the generators use, so a campaign and its figures are selected
# with one name. ``float64-forward`` is the manuscript default and reads
# the ``-FP64`` sibling; an explicit ``float32`` selects the older run.
CFD_NN_PRECISION_ENV = "CFD_NN_INFERENCE_PRECISION"
FP64_SUFFIX = "-FP64"
NN_PRECISIONS = frozenset({"float32", "float64-forward"})

CASES = frozenset(
    {
        "capwave",
        "rising_bubble",
        "stationary_bubble",
        "oscillating_droplet",
        "marangoni",
    }
)
MODES = frozenset({"comparators", "cell", "direct", "crossing", "_studies"})
GRID_STRATEGIES = frozenset({"uniform", "adaptive"})
RESOLUTIONS = frozenset({32, 64, 128, 256, 512})

_METHOD_MODE = {
    "VOF-HF": "comparators",
    "CLSVOF": "comparators",
    "CLSVOF-native-C2": "crossing",
    "LevelSet": "comparators",
    "NN": "cell",
    "NN-cell": "cell",
    "LevelSet-NN": "cell",
    "LevelSet-NN-cell": "cell",
    "NN-interface-C1": "direct",
    "LevelSet-NN-C1": "direct",
    "NN_direct_interface": "direct",
    "C1": "direct",
    "direct-interface": "direct",
    "NN-interface-C2": "crossing",
    "Cell-NN-C2": "crossing",
    "Cell-NN-C2-FP64": "crossing",
    "LevelSet-NN-C2": "crossing",
    "C2": "crossing",
    "crossing": "crossing",
    "Oracle": "_studies",
    "cell_1_over_r": "_studies",
    "interface_1_over_R": "_studies",
}

PathLike = Union[str, os.PathLike]


def repository_root(start: Optional[PathLike] = None) -> Path:
    """Return the repository root without depending on an existing data tree."""

    candidate = Path(start).expanduser() if start is not None else Path(__file__)
    candidate = candidate.resolve()
    if candidate.is_file():
        candidate = candidate.parent
    for parent in (candidate, *candidate.parents):
        if (parent / "figures").is_dir() and (parent / "generate").is_dir():
            return parent
    raise RuntimeError(
        "Could not locate the CFD repository root (expected figures/ and generate/)"
    )


def data_root(
    repo_root: Optional[PathLike] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> Path:
    """Return the active data root, honoring ``CFD_DATA_ROOT`` when present.

    Relative overrides are interpreted relative to ``repo_root``.  This keeps
    command-line use deterministic even when a figure is launched from a nested
    directory.  The path need not exist yet, which is useful while constructing
    a migration staging tree.
    """

    environment = os.environ if environ is None else environ
    base = (
        repository_root()
        if repo_root is None
        else Path(repo_root).expanduser().resolve()
    )
    override = environment.get(CFD_DATA_ROOT_ENV)
    if override:
        path = Path(override).expanduser()
        if not path.is_absolute():
            path = base / path
        return path.resolve()
    return (base / "data").resolve()


def reference_file(
    case: str,
    source: str,
    name: str,
    *,
    benchmark_case: Optional[int] = None,
    root: Optional[PathLike] = None,
    repo_root: Optional[PathLike] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> Path:
    """Return a published benchmark reference file for ``case``.

    Reference data is external published material rather than a run of ours,
    so it sits beside the run modes as ``<case>/reference/<source>`` instead of
    under one.  Only the rising-bubble benchmark splits its references by
    ``benchmark_case``.
    """

    if case not in CASES:
        raise ValueError("Unknown CFD case: {!r}".format(case))
    base = (
        Path(root).expanduser().resolve()
        if root is not None
        else data_root(repo_root=repo_root, environ=environ)
    )
    directory = base / case / "reference" / source
    if benchmark_case is not None:
        directory = directory / "case{:d}".format(benchmark_case)
    return directory / name


def nn_inference_precision(
    environ: Optional[Mapping[str, str]] = None,
) -> str:
    """Return the selected NN inference precision, defaulting to ``float64-forward``."""

    environment = os.environ if environ is None else environ
    value = environment.get(CFD_NN_PRECISION_ENV) or "float64-forward"
    # The generators accept this compatibility spelling; normalize it here too.
    if value == "float64-accum":
        value = "float64-forward"
    if value not in NN_PRECISIONS:
        raise ValueError(
            "{} must be one of {}".format(
                CFD_NN_PRECISION_ENV, sorted(NN_PRECISIONS)
            )
        )
    return value


def nn_precision_output_suffix(
    environ: Optional[Mapping[str, str]] = None,
) -> str:
    """Return a filename suffix identifying a non-default NN precision."""

    precision = nn_inference_precision(environ)
    return "" if precision == "float32" else "_{}".format(precision)


def apply_nn_precision(
    method: str,
    environ: Optional[Mapping[str, str]] = None,
) -> str:
    """Return ``method`` with the precision suffix the environment selects.

    Only NN methods carry the suffix, and a method that already names its own
    precision is returned untouched so an explicit caller always wins.
    """

    if FP64_SUFFIX in method or "NN" not in method:
        return method
    if nn_inference_precision(environ) != "float64-forward":
        return method
    return method + FP64_SUFFIX


def method_mode(method: str) -> str:
    """Return the canonical mode for a known scientific method."""

    try:
        return _METHOD_MODE[method]
    except KeyError as exc:
        raise ValueError(
            "Unknown method {!r}; pass a canonical method name".format(method)
        ) from exc


def canonical_run_dir(
    case: str,
    method: str,
    resolution: int,
    *,
    grid: str,
    imax: Optional[int] = None,
    steps: Optional[int] = None,
    benchmark_case: Optional[int] = None,
    mode: Optional[str] = None,
    root: Optional[PathLike] = None,
    repo_root: Optional[PathLike] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> Path:
    """Build and validate a canonical run-directory path.

    ``mode`` normally follows from ``method``.  Supplying it is allowed as an
    assertion, but a method cannot be placed under a different mode.
    """

    if case not in CASES:
        raise ValueError("Unknown CFD case: {!r}".format(case))
    if grid not in GRID_STRATEGIES:
        raise ValueError("Unknown grid strategy: {!r}".format(grid))
    if isinstance(resolution, bool) or resolution not in RESOLUTIONS:
        raise ValueError(
            "resolution must be one of {}".format(sorted(RESOLUTIONS))
        )
    if not method or method in {".", ".."} or "/" in method or "\\" in method:
        raise ValueError("method must be one safe path component")

    # The precision suffix is applied before mode resolution so that both the
    # unsuffixed and the -FP64 leaf resolve to the same canonical mode.
    method = apply_nn_precision(method, environ)
    inferred_mode = method_mode(method)
    selected_mode = inferred_mode if mode is None else mode
    if selected_mode not in MODES:
        raise ValueError("Unknown canonical mode: {!r}".format(selected_mode))
    if selected_mode != inferred_mode:
        raise ValueError(
            "method {!r} belongs to mode {!r}, not {!r}".format(
                method, inferred_mode, selected_mode
            )
        )

    if case == "rising_bubble":
        if benchmark_case not in {1, 2}:
            raise ValueError("rising_bubble requires benchmark_case=1 or 2")
    elif benchmark_case is not None:
        raise ValueError("benchmark_case is only valid for rising_bubble")

    if imax is not None and steps is not None:
        raise ValueError("imax and steps are mutually exclusive")
    if method == "VOF-HF":
        if imax is not None or steps is not None:
            raise ValueError("VOF-HF does not have a redistance component")
    elif selected_mode != "_studies":
        if imax is None and steps is None:
            raise ValueError(
                "exactly one of imax=0..99 or steps=0..99 is required "
                "for non-VOF-HF run methods"
            )
    for name, value in (("imax", imax), ("steps", steps)):
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 0 <= value <= 99
        ):
            raise ValueError(f"{name} must be in the range 0..99")

    base = (
        Path(root).expanduser().resolve()
        if root is not None
        else data_root(repo_root=repo_root, environ=environ)
    )
    parts = [case, selected_mode]
    if benchmark_case is not None:
        parts.append("case{}".format(benchmark_case))
    parts.extend([grid, "N{:04d}".format(resolution)])
    if imax is not None:
        parts.append("imax{:02d}".format(imax))
    if steps is not None:
        parts.append("steps{:02d}".format(steps))
    parts.append(method)
    directory = base.joinpath(*parts)
    if method.endswith(FP64_SUFFIX):
        manifest = json.loads((directory / "manifest.json").read_text())
        parameters = manifest["plan"]["parameters"]
        if parameters.get("inference_precision") not in {"float64-forward", "float64-accum"}:
            raise ValueError(f"FP64 precision is not recorded: {directory}")
        if "-DKAPPA_OFFSET_INFERENCE_DOUBLE=1" not in manifest["plan"]["commands"]["compile"]["argv"]:
            raise ValueError(f"FP64 compile flag is missing: {directory}")
        # N256 has complete, verified terminal artifacts but retains a failed
        # runner status. Do not reinterpret this exception as a successful run.
        terminal_exception = (case == "stationary_bubble" and resolution == 256
                              and manifest.get("status") == "failed"
                              and manifest.get("field_snapshots", {}).get("snapshots", {})
                              .get("final", {}).get("actual_benchmark_time") == 2.0)
        if terminal_exception:
            warnings.warn("Stationary N256: verified terminal artifacts are used, but the runner status remains failed.", RuntimeWarning)
        if manifest.get("status") != "completed" and not terminal_exception:
            raise ValueError(f"FP64 run is incomplete: {directory}")
        if manifest.get("analysis_ready") is not True:
            raise ValueError(f"FP64 artifacts are not analysis-ready: {directory}")
        for name, artifact in manifest["published_artifacts"].items():
            digest = hashlib.sha256((directory / name).read_bytes()).hexdigest()
            if digest != artifact["sha256"]:
                raise ValueError(f"FP64 artifact hash mismatch: {directory / name}")
    return directory


def catalog_path(
    filename: str = "rows.csv",
    *,
    root: Optional[PathLike] = None,
    repo_root: Optional[PathLike] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> Path:
    """Return a file under the canonical ``_meta/catalog`` directory."""

    if not filename or filename in {".", ".."} or Path(filename).name != filename:
        raise ValueError("catalog filename must be one safe path component")
    base = (
        Path(root).expanduser().resolve()
        if root is not None
        else data_root(repo_root=repo_root, environ=environ)
    )
    return base / "_meta" / "catalog" / filename


def logical_data_path(
    path: PathLike,
    *,
    root: Optional[PathLike] = None,
    repo_root: Optional[PathLike] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> str:
    """Return a staging-independent ``data/...`` provenance path.

    QA manifests and source-data tables should record logical paths rather than
    absolute staging locations.  A path outside the selected data root is
    rejected instead of being silently converted to ``../`` notation.
    """

    base = (
        Path(root).expanduser().resolve()
        if root is not None
        else data_root(repo_root=repo_root, environ=environ)
    )
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    try:
        relative = candidate.resolve().relative_to(base)
    except ValueError as exc:
        raise ValueError(
            "Path is outside the selected CFD data root: {}".format(path)
        ) from exc
    return (Path("data") / relative).as_posix()
