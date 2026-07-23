from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_ROWS = {
    "capwave": 90,
    "rising_bubble": 180,
    "stationary_bubble": 8,
    "oscillating_droplet": 90,
}
EXPECTED_VOF_HF_ROWS = {
    "capwave": 5,
    "rising_bubble": 10,
    "stationary_bubble": 4,
    "oscillating_droplet": 10,
}


def test_case_summaries_are_small_stable_contracts() -> None:
    for case, rows in EXPECTED_ROWS.items():
        text = (ROOT / "generate" / case / "summary.yaml").read_text()
        assert len(text.splitlines()) <= 45
        assert "schema_version: 5" in text
        assert f"case: {case}" in text
        assert "campaign_entry: generate/job.sh" in text
        assert f"  rows: {rows}" in text
        assert f"  vof_hf_rows: {EXPECTED_VOF_HF_ROWS[case]}" in text
        expected = 0 if case == "stationary_bubble" else 3
        assert f"  default_imax: {expected}" in text
        sensitivity = (
            "[]"
            if case == "stationary_bubble"
            else "[0, 1, 2, 4, 5, 10, 15, 20]"
        )
        assert f"  sensitivity_imax: {sensitivity}" in text
        assert "outputs:" in text
        assert "official_difference:" in text
        assert "  VOF-HF: generate/" in text
        assert "  CLSVOF: generate/" in text
        assert "  NN: generate/" in text
        assert "  methods: [CLSVOF, NN]" in text
        assert str(ROOT) not in text
        assert "commands:" not in text
        assert "optional arguments:" not in text
