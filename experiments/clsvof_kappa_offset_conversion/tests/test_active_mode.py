from pathlib import Path

from experiments.clsvof_kappa_offset_conversion.run_host import MODES


def test_only_cell_local_nn_mode_is_runnable() -> None:
    assert MODES == ("nn_cell_levelset",)


def test_provider_has_no_legacy_nn_return_path() -> None:
    text = (Path(__file__).parents[1] / "include" / "clsvof_nn_cell_curvature.h").read_text(
        encoding="utf-8"
    )
    assert "KAPPA_OFFSET_NN_DIRECT" not in text
    assert "KAPPA_OFFSET_NN_OFFSET_GRAD" not in text
    assert "KAPPA_OFFSET_NATIVE_WRAPPER" not in text
    assert "KAPPA_OFFSET_MODE" not in text
    assert "q_direct" not in text
    assert "q_offset_grad" not in text
    assert "return q_cell/Delta;" in text
