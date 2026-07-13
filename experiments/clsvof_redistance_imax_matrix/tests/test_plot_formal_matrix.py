import csv

from plot_formal_matrix import figure_physical_tradeoff, moonmd_shape


def test_physical_tradeoff_renders_complete_96_cell_source_table(tmp_path) -> None:
    rows = []
    for benchmark in ("capwave", "rising_case1"):
        for method in ("clsvof_native", "clsvof_nn"):
            for n in (64, 128, 256, 512):
                for imax in range(6):
                    rows.append(
                        {
                            "benchmark": benchmark,
                            "method": method,
                            "N": str(n),
                            "imax": str(imax),
                            "relative_rms": str((imax + 1) / n),
                            "velocity_reference_rmse": str((imax + 2) / n),
                        }
                    )

    outputs = figure_physical_tradeoff(rows, tmp_path / "figures", tmp_path / "source")

    assert {path.suffix for path in outputs} == {".svg", ".pdf", ".png"}
    with (tmp_path / "source/fig01_physical_tradeoff.csv").open(newline="") as stream:
        source_rows = list(csv.DictReader(stream))
    assert len(source_rows) == 96
    assert all(row["benchmark"] and row["physical_error"] for row in source_rows)


def test_moonmd_shape_uses_same_nonnegative_symmetry_half_as_solver(tmp_path) -> None:
    source = tmp_path / "shape.txt"
    source.write_text("0.4 1.0\n0.5 1.1\n0.6 1.2\n")

    assert moonmd_shape(source) == [(1.1, 0.0), (1.2, 0.09999999999999998)]
