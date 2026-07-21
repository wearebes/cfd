from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


BENCHMARKS = ("capwave", "rising_case1", "rising_case2", "stationary_bubble")
METHODS = ("clsvof", "nn")
IMAX_VALUES = tuple(range(6))
GENERAL_RESOLUTIONS = (64, 128, 256, 512)
STATIONARY_RESOLUTIONS = (64, 128, 256)


@dataclass(frozen=True)
class MatrixRow:
    benchmark: str
    method: str
    resolution: int
    imax: int

    def __post_init__(self) -> None:
        if self.benchmark not in BENCHMARKS:
            raise ValueError(f"unsupported benchmark: {self.benchmark}")
        if self.method not in METHODS:
            raise ValueError(f"unsupported method: {self.method}")
        if self.imax not in IMAX_VALUES:
            raise ValueError(f"imax must be one of {IMAX_VALUES}: {self.imax}")
        allowed = (
            STATIONARY_RESOLUTIONS
            if self.benchmark == "stationary_bubble"
            else GENERAL_RESOLUTIONS
        )
        if self.resolution not in allowed:
            if self.benchmark == "stationary_bubble" and self.resolution == 512:
                raise ValueError("stationary N512 is outside the formal matrix")
            raise ValueError(
                f"unsupported resolution for {self.benchmark}: {self.resolution}"
            )

    @property
    def row_id(self) -> str:
        return (
            f"{self.benchmark}__{self.method}__"
            f"N{self.resolution:04d}__imax{self.imax:02d}"
        )

    @property
    def level(self) -> int | None:
        if self.benchmark == "capwave":
            return None
        return self.resolution.bit_length() - 1

    @property
    def actual_grid(self) -> str:
        if self.benchmark.startswith("rising_case"):
            return f"{self.resolution}x{self.resolution // 4}"
        return f"{self.resolution}x{self.resolution}"

    @property
    def model_name(self) -> str | None:
        if self.method == "nn":
            return f"baseline_{self.resolution}_hgradient"
        return None

    @property
    def rising_case(self) -> int | None:
        if self.benchmark == "rising_case1":
            return 1
        if self.benchmark == "rising_case2":
            return 2
        return None

    def to_dict(self) -> dict[str, object]:
        return {
            **asdict(self),
            "row_id": self.row_id,
            "level": self.level,
            "actual_grid": self.actual_grid,
            "model_name": self.model_name,
            "rising_case": self.rising_case,
        }


def formal_rows() -> list[MatrixRow]:
    rows: list[MatrixRow] = []
    for benchmark in BENCHMARKS:
        resolutions = (
            STATIONARY_RESOLUTIONS
            if benchmark == "stationary_bubble"
            else GENERAL_RESOLUTIONS
        )
        for method in METHODS:
            for resolution in resolutions:
                for imax in IMAX_VALUES:
                    rows.append(MatrixRow(benchmark, method, resolution, imax))
    assert len(rows) == 180
    assert len({row.row_id for row in rows}) == 180
    return rows


def result_relative_path(row: MatrixRow) -> Path:
    return (
        Path(row.benchmark)
        / f"N{row.resolution:04d}"
        / f"imax{row.imax:02d}"
        / row.method
    )


def generator_path(root: Path, row: MatrixRow) -> Path:
    script = (
        "clsvof.sh"
        if row.method == "clsvof"
        else "nn.sh"
    )
    case_dir = "rising_bubble" if row.rising_case else row.benchmark
    return root / "generate" / case_dir / script


def generator_command(
    root: Path,
    row: MatrixRow,
    *,
    purpose: str,
    output: Path,
    threads: int = 1,
    dry_run: bool = False,
) -> list[str]:
    if purpose not in {"smoke", "formal"}:
        raise ValueError(f"unsupported purpose: {purpose}")
    command = [str(generator_path(root, row))]
    if row.rising_case is not None:
        command.extend(["--case", str(row.rising_case)])
    command.extend([f"--{purpose}", "--imax", str(row.imax)])
    command.extend(["--resolution", str(row.resolution)])
    command.extend(["--threads", str(threads), "--output", str(output)])
    if dry_run:
        command.append("--dry-run")
    return command


def load_contract(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if int(payload.get("expected_rows", -1)) != 180:
        raise ValueError("matrix contract expected_rows must be 180")
    if payload.get("imax") != list(IMAX_VALUES):
        raise ValueError("matrix contract imax must be [0,1,2,3,4,5]")
    return payload


def rows_by_id(rows: Iterable[MatrixRow] | None = None) -> dict[str, MatrixRow]:
    selected = formal_rows() if rows is None else list(rows)
    result = {row.row_id: row for row in selected}
    if len(result) != len(selected):
        raise ValueError("duplicate row IDs")
    return result
