from pathlib import Path

from experiments.rising_clsvof_kreplace.make_overlay_integral import build_overlay_text


def test_overlay_replaces_only_curvature_provider_line():
    source = """
static inline double distance_curvature (Point point, scalar d)
{
  return 0.;
}
#endif // CURVATURE

event acceleration (i++)
{
  double ki = distance_curvature (point, d);
}
"""
    output = build_overlay_text(source)

    assert "double ki = rising_k_provider (point, d);" in output
    assert "double ki = distance_curvature (point, d);" not in output
    assert output.count('include "rising_k_provider.h"') == 1
    assert output.index('include "rising_k_provider.h"') > output.index("#endif // CURVATURE")


def test_overlay_rejects_missing_ki_line():
    source = "#endif // CURVATURE\n"
    try:
        build_overlay_text(source)
    except ValueError as exc:
        assert "expected exactly one curvature assignment" in str(exc)
    else:
        raise AssertionError("missing ki assignment was not rejected")


def test_overlay_rejects_ambiguous_ki_line():
    source = """
#endif // CURVATURE
double ki = distance_curvature (point, d);
double ki = distance_curvature (point, d);
"""
    try:
        build_overlay_text(source)
    except ValueError as exc:
        assert "expected exactly one curvature assignment" in str(exc)
    else:
        raise AssertionError("ambiguous ki assignment was not rejected")


def test_overlay_cli_writes_file(tmp_path: Path):
    src = tmp_path / "integral.h"
    dst = tmp_path / "generated_integral.h"
    src.write_text(
        "#endif // CURVATURE\n"
        "double ki = distance_curvature (point, d);\n",
        encoding="utf-8",
    )

    from experiments.rising_clsvof_kreplace.make_overlay_integral import main

    assert main([str(src), str(dst)]) == 0
    assert dst.exists()
    assert "rising_k_provider" in dst.read_text(encoding="utf-8")
