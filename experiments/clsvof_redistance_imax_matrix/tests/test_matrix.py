from pathlib import Path

from build_matrix import load_and_validate


ROOT = Path(__file__).resolve().parents[3]
PREVIEW = ROOT / "docs/superpowers/plans/2026-07-11-clsvof-redistance-imax-matrix-preview.csv"


def test_preview_is_the_approved_96_row_matrix() -> None:
    rows = load_and_validate(PREVIEW)
    assert len(rows) == 96
    assert len({row["row_id"] for row in rows}) == 96
    assert sum(row["planning_status"] == "candidate_reuse" for row in rows) == 5
    assert sum(row["planning_status"] == "planned_run" for row in rows) == 91


def test_rising_resolution_mapping() -> None:
    rows = load_and_validate(PREVIEW)
    expected = {
        64: (6, "64x16"),
        128: (7, "128x32"),
        256: (8, "256x64"),
        512: (9, "512x128"),
    }
    for row in rows:
        if row["benchmark"] == "rising_case1":
            assert (row["LEVEL"], row["actual_grid"]) == expected[row["N"]]
