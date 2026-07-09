from pathlib import Path

from experiments.rising_clsvof_kreplace.compare_out import compare_out, main


HEADER = "t sb -1 xb vb dt perf.t perf.speed\n"


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_identical_files_compare_equal():
    text = HEADER + "0 0 -1 0.5 0 0.000167809 0.01 100 1 2 3 4 5\n"
    assert compare_out(text, text) == []


def test_perf_only_fields_are_ignored():
    a = HEADER + "0 0 -1 0.5 0 0.000167809 0.01 100 1 2 3 4 5\n"
    b = HEADER + "0 0 -1 0.5 0 0.000167809 0.99 999 1 2 3 4 5\n"
    assert compare_out(a, b) == []


def test_non_perf_field_difference_is_reported_with_line_and_field():
    a = HEADER + "0 0 -1 0.5 0 0.000167809 0.01 100 1 2 3 4 5\n"
    b = HEADER + "0 0 -1 0.6 0 0.000167809 0.01 100 1 2 3 4 5\n"
    issues = compare_out(a, b)
    assert len(issues) == 1
    assert "line 2" in issues[0]
    assert "field 4" in issues[0]


def test_differing_line_counts_fail():
    a = HEADER + "0 0 -1 0.5 0 0.000167809 0.01 100\n"
    b = HEADER + "0 0 -1 0.5 0 0.000167809 0.01 100\n1 1 -1 0.5 0 0 0 0\n"
    issues = compare_out(a, b)
    assert issues
    assert "line count" in issues[0]


def test_header_line_compared_as_exact_string():
    a = "t sb -1 xb vb dt perf.t perf.speed\n" + "0 0 -1 0.5 0 0.000167809 0.01 100\n"
    b = "t sb -1 xb vb dt perf.t perf.speed extra\n" + "0 0 -1 0.5 0 0.000167809 0.01 100\n"
    issues = compare_out(a, b)
    assert any("header" in issue for issue in issues)


def test_trailer_comment_lines_are_ignored():
    a = (
        HEADER
        + "0 0 -1 0.5 0 0.000167809 0.01 100\n\n"
        + "# Multigrid, 10 steps, 1.0 CPU, 1.1 real, 1e6 points.step/s, 23 var\n"
    )
    b = (
        HEADER
        + "0 0 -1 0.5 0 0.000167809 0.01 100\n\n"
        + "# Multigrid, 10 steps, 9.9 CPU, 9.9 real, 9e6 points.step/s, 23 var\n"
    )
    assert compare_out(a, b) == []


def test_tol_allows_small_numeric_deviation_on_non_perf_fields():
    a = HEADER + "0 0 -1 0.500000001 0 0.000167809 0.01 100\n"
    b = HEADER + "0 0 -1 0.500000002 0 0.000167809 0.01 100\n"
    assert compare_out(a, b) != []
    assert compare_out(a, b, tol=1e-6) == []


def test_field_count_mismatch_reported_not_crashed():
    a = HEADER + "0 0 -1 0.5 0 0.000167809 0.01 100\n"
    b = HEADER + "0 0 -1 0.5 0 0.000167809 0.01 100 1 2 3\n"
    issues = compare_out(a, b)
    assert issues
    assert "field count" in issues[0]
    assert "line 2" in issues[0]


def test_cli_exit_codes(tmp_path: Path):
    a = _write(tmp_path, "a.out", HEADER + "0 0 -1 0.5 0 0.000167809 0.01 100\n")
    b = _write(tmp_path, "b.out", HEADER + "0 0 -1 0.5 0 0.000167809 0.99 999\n")
    c = _write(tmp_path, "c.out", HEADER + "0 0 -1 0.6 0 0.000167809 0.01 100\n")

    assert main([str(a), str(b)]) == 0
    assert main([str(a), str(c)]) == 1


def test_cli_tol_flag(tmp_path: Path):
    a = _write(tmp_path, "a.out", HEADER + "0 0 -1 0.500000001 0 0.000167809 0.01 100\n")
    b = _write(tmp_path, "b.out", HEADER + "0 0 -1 0.500000002 0 0.000167809 0.01 100\n")

    assert main([str(a), str(b)]) == 1
    assert main(["--tol", "1e-6", str(a), str(b)]) == 0
