from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_submit_propagates_selected_policy_to_every_identity_gate() -> None:
    script = (ROOT / "hpc/submit_matrix.sh").read_text(encoding="utf-8")

    assert 'preflight_hpc.py" --matrix-id "$matrix_id" --cpus "$cpus" --policy "$policy"' in script
    assert script.count('verify_matrix.py" --matrix-id "$matrix_id"') == 2
    assert script.count('--phase n64 --policy "$policy"') == 1
    assert script.count('--phase all --policy "$policy"') == 1
    assert 'collect_results.sh" "$matrix_id" "$policy"' in script


def test_collect_uses_selected_policy_for_final_verification() -> None:
    script = (ROOT / "hpc/collect_results.sh").read_text(encoding="utf-8")

    assert 'policy="${2:-$repo_root/hpc/config/thread_policy.json}"' in script
    assert '--phase all --policy "$policy"' in script
