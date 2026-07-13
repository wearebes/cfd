# 抢救性复制记录（recovered_from_private_tmp）

- 执行日期：2026-07-12
- 来源：`/private/tmp/cfd-capwave-clsvof-kreplace`（注册在主仓库上的 git worktree，分支 `codex/capwave-clsvof-kreplace`，HEAD=`2bbed03`）
- 动机：`/private/tmp` 重启即清空；该 worktree 中存在**未提交**且主仓库没有副本的内容。
- 操作性质：纯新增复制。没有覆盖、移动或删除任何现有文件；没有改动临时 worktree 本身。

## 已抢救（分支里没有、worktree 丢失即无法找回）

| 文件 | 说明 |
| --- | --- |
| `run_canary.sh` | worktree 工作副本，相对 `2bbed03` 有未提交修改（见 patch）。注意：它**不含** `CAPWAVE_SELECTED_MODES` 支持，不是产生主仓库六组 accepted 结果的那个 runner。 |
| `summarize_canary.py` | worktree 工作副本，相对 `2bbed03` 有未提交修改；与主仓库现存同名文件也不同。 |
| `uncommitted_vs_2bbed03.patch` | 上述两文件相对 `2bbed03` 的 `git diff` 原文。 |
| `results_20260709T134408Z/` | 临时区第四组结果（matched-resolution 运行，报告标 blocked/partial，从未导入主仓库；前三组 093531Z/122142Z/130114Z 已在 `../diagnostic_imports/20260710_from_private_tmp/`）。 |
| `temp_export_manifests/baseline_*.export_manifest.json` | 临时区四份模型导出 manifest。与主仓库同名文件的差异是**语义性**的：临时区记录 kreplace 时期旧换算 `kappa = hkappa / Delta`；主仓库现版本记录 kappa-offset 转换 `q_cell = q_gamma / (1 + (d/Delta) q_gamma)`。`nn_weights.h` 本身四份均与主仓库逐字节一致。旧 manifest 是 kreplace accepted 数据当时解释口径的历史依据。 |
| `temp_worktree_git_status_20260712.txt` | 抢救时刻该 worktree 的 `git status --short` 快照。 |
| `sha256sums.txt` | 本目录全部文件的 SHA-256 清单。 |

## 未抢救（安全或无价值，理由如下）

- 分支 `2bbed03` 已提交的 capwave 实现（README、`include/capwave_k_provider.h`、`include/clsvof_nn_features.h`、`make_overlay_integral.py`、基线版 `run_canary.sh`/`summarize_canary.py`、`tests/test_feature_header_compile.sh`、`tests/test_make_overlay_integral.py`）：对象存于主仓库共享 `.git`，worktree 消失也不丢，取回方式 `git show 2bbed03:<path>`。**前提是不删除该分支。**
- `make_single_resolution_case.py`、`tests/test_make_single_resolution_case.py`：与主仓库现存副本逐字节一致。
- `dataset/model/c_exports/*/nn_weights.h`（临时区副本）：与主仓库逐字节一致。
- `work/`（约 4.4M 编译产物）、35 个 `.qcc*` 临时目录、`.DS_Store`：一次性产物。
- `tools/clsvof_model_export/include/clsvof_mlp_infer.h`：与主仓库 `tools/clsvof_model/include/clsvof_mlp_infer.h` 一致（目录名是旧称）。

## 已确认的不可恢复项

产生主仓库六组 accepted 结果（`../results/20260709T17*Z`、`20260709T18*Z`、`20260709T19*Z`）的 runner 版本（带 `CAPWAVE_SELECTED_MODES` 选择模式支持）当时在主工作区、未被 git 跟踪、现已被删除；临时 worktree 与分支中均无该版本。重建须以六组结果各自 `manifest.json` 里的 `source_fingerprint`（三个 sha256）、`raw27_contract`、`clamp`、`matched_resolution`、`selected_modes` 字段为规范。
