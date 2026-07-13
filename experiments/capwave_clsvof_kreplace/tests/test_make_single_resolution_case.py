from pathlib import Path

from experiments.capwave_clsvof_kreplace.make_single_resolution_case import build_case_text


def test_case_replaces_only_stock_resolution_loop():
    source = """
int main() {
  for (N = 16; N <= 128; N *= 2) {
    run();
  }
}
"""
    output = build_case_text(source, 256)

    assert "for (N = 256; N <= 256; N *= 2) {" in output
    assert "for (N = 16; N <= 128; N *= 2) {" not in output
    assert output.count("run();") == 1


def test_case_rejects_missing_stock_loop():
    try:
        build_case_text("int main() { run(); }\n", 64)
    except ValueError as exc:
        assert "expected exactly one stock capwave resolution loop" in str(exc)
    else:
        raise AssertionError("missing stock loop was not rejected")


def test_case_rejects_ambiguous_stock_loop():
    source = (
        "for (N = 16; N <= 128; N *= 2) {}\n"
        "for (N = 16; N <= 128; N *= 2) {}\n"
    )
    try:
        build_case_text(source, 64)
    except ValueError as exc:
        assert "expected exactly one stock capwave resolution loop" in str(exc)
    else:
        raise AssertionError("ambiguous stock loop was not rejected")


def test_case_cli_writes_file(tmp_path: Path):
    src = tmp_path / "capwave-clsvof.c"
    dst = tmp_path / "single.c"
    src.write_text("for (N = 16; N <= 128; N *= 2) {\n  run();\n}\n", encoding="utf-8")

    from experiments.capwave_clsvof_kreplace.make_single_resolution_case import main

    assert main([str(src), str(dst), "--resolution", "512"]) == 0
    assert "N = 512" in dst.read_text(encoding="utf-8")
