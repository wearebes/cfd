# CFD 仓库文件整理计划

状态：执行中；runner/matrix 已建立，dataset/figures 实体迁移和旧目录退役未执行
盘点日期：2026-07-12
适用仓库：`/Users/jcy/research/cfd`

修订记录：

- v6（2026-07-12）：按云服务器批量运行需求，将新 NN cell-offset 灵敏度范围扩展为 `imax=0..10`，加入 stationary bubble，形成 `3 case × 4 resolution × 11 imax = 132` 行云矩阵。`--jobs N` 只控制独立单线程 row 的并发数；`imax=3` 仍只进入 matched dataset，其余 10 个值进入 nondefault dataset。旧 `20260710T172910Z` retained native 证据仍保持原 0..5/48-row 历史边界，不追写成 0..10。
- v5（2026-07-12）：按用户决定锁定 D1/D2/D3。所有物理 case 采用相同的默认/非默认数据骨架；rising 明确建立 `nn_cell_offset_matched`。每个 case 只提供一个 `generate/nn_cell_offset.sh`，由 `--imax` 参数决定运行默认 `imax=3` 还是非默认 `imax=0,1,2,4,5`；跨 case matrix 只负责调度、并发、状态和审计，不再拥有第二套物理生成实现。stationary 旧三头文件 raw 采用 B：Phase 5 前完整保留，外部证据备份和等价性登记完成后再列入单独删除确认。
- v4（2026-07-12）：审查 stationary `20260712T113747Z_nn_cell_offset` smoke 的实物证据。确认新单头文件与旧三头文件在 stationary N64 上汇总指标一致（仅 mode 名变化），完整 `La-12000-6` 字节相同，且 clamp/denominator guard 均为零；将它登记为当前受支持的 stationary smoke，旧 `143057Z` 降为等价性审计。与此同时，撤回“该 smoke 已证明全仓可直接共用同一 raw27 实现”的过强表述：旧 capwave/rising 的 stencil 行序和 rising `ny` 符号与当前共享头不同，必须先过 per-case raw27/符号/compile gate；若不通过，采用共享核心 + case adapter，不允许为了单头文件形式牺牲特征契约。新增 §11 待用户选择项。
- v3（2026-07-12）：按 Codex 严格证据审计修订。旧 `20260710T172910Z` matrix bundle 当前仅保留 48 个 native row，删除“96/96 可直接迁移”和“10 reuse”表述；确认实际 `candidate_reuse=5` 且五行 retained manifest 均含 `reuse_validation`；将所有未来 NN 路径统一为共享 `clsvof_nn_cell_curvature.h` 的 cell-offset 语义；历史 direct capwave/rising/stationary 数据降为 audit-only，禁止重建为当前可执行方法；stationary 唯一 NN runner 锁定为现 `run_nn_smoke.sh`；rising 取回锚点固定为 `95c8076`；补 capwave runner 不可完全重建的自由度清单、分层 tar 备份范围和临时 worktree 全量差异结论。
- v2（2026-07-12）：按仓库实测核查修订。主要变化：capwave/rising 生成代码按现状改为「重建/找回」而非「迁移」（§2.1、§5、Phase 2）；新增 `/private/tmp` 临时 worktree 处置（§5.1）并记录唯一一次已执行的抢救性复制（纯新增文件）；补 `_shared` 两单元间的编译依赖（§5、Phase 2）；补 dataset 内 figures/sources 的映射行（§5、Phase 4）；矩阵 NN 方法身份登记（§2.4、§6）；Phase 0 增加临时区清点与仓库外备份；Phase 2 验收测试基线改为当前实际可通过集合；报告迁移改为原文冻结。

## 1. 目标

把当前按临时实验任务分散的仓库，整理成以物理 case 为入口、以确定后的科研数据为 dataset、以图表主题为工作单元、以 `report/` 为论文图片选择面的结构。

本计划优先解决以下实际问题：

1. capwave、rising bubble、stationary bubble 的运行代码、数据和图表入口分散；
2. smoke、诊断实验、正式数据和论文图片容易混在一起；
3. `experiments/*/results/` 同时承担代码目录和数据目录职责；
4. 绘图代码散落在 `tools/`、`experiments/` 和 `tem/`，图片又留在 dataset 或 result 目录；
5. `imax=3` 的官方默认 CLSVOF 数据与 `imax!=3` 的非默认 redistance 敏感性数据没有在目录语义上分开；
6. stationary bubble 当前只有 N64 smoke/机理诊断，尚不应包装成正式 dataset；
7. capwave 的旧 direct-kreplace 代码主体在 `/private/tmp` 的 git worktree（分支 `codex/capwave-clsvof-kreplace`）；产生六组历史结果的确切 runner 版本已确认不可恢复（详见 §5.1）；rising 的旧 direct 运行入口是 tracked 删除。两者只允许用于历史审计，不恢复为当前 NN 执行链；未来正式 NN 统一走共享 cell-offset 实现。
8. 旧 matrix 的 NN 行使用了已废弃的 direct `q_gamma/Delta` 口径且已被删除；当前 bundle 只有 48 个 native row，不能再按 96-row 完整矩阵组织或报告。

## 2. 已锁定的整理原则

### 2.1 case 是运行入口

物理问题是第一组织维度：

- `capwave`
- `rising_bubble`
- `stationary_bubble`

每个 case 只保留一个 `summary.yaml` 作为总索引。它记录：

- 官方 Basilisk 源码位置；
- 有哪些确定的数据集；
- 每个数据集由哪个脚本生成；
- 数据实际位于哪个目录；
- 有哪些图表主题；
- 哪些内容只是 smoke 或 diagnostic。

不为每个数据集再建立 README、说明 MD、manifest MD 等描述文件。

`generator` 字段必须如实反映现状，配套 `generator_status` 取值约定：

- `existing`：脚本在所写路径存在且可运行；
- `deleted-in-worktree`：生成脚本被用户从工作树删除（tracked 删除）；必须附 `recover_from: git show <commit>:<path>`，只读取回内容作重建底稿，不恢复工作树；
- `to-rebuild`：脚本在任何工作区和分支中都已不存在；必须附重建规范来源（结果 `manifest.json` 的 `source_fingerprint`、raw27 契约、clamp、selected_modes 等字段）。
- `audit-only`：数据来自已废弃或错误的方法链，不提供当前可执行 generator；必须登记历史 provenance、失效原因和禁止用于正式结论的边界。

禁止把尚不存在的脚本路径登记成 `existing`。

### 2.2 运行语言按实际复杂度选择

- 官方 Basilisk 复现、固定参数或少量循环：优先简洁的 `.sh + .c`；
- 需要复制官方源码并生成局部 overlay：允许 `.sh + 小型 Python 生成器`；
- 需要旧 96-cell 或新 132-row matrix、并发调度、补跑和审计：保留 Python；
- 科研绘图：使用 Python/matplotlib；
- 例外：官方风格复现图（现 `tools/capwave`、`tools/rising bubble` 的 gnuplot `.plt`/`.sh`）保留 gnuplot 不改写，随其图片一起迁移；
- 不为了形式统一，把简单 Basilisk 命令包装成复杂 Python 框架。

### 2.3 dataset 按科学身份命名，不按运行时间命名

正式 dataset 表示已经确定、只需要正式生成一次的科研数据。其目录名必须表达科学内容，例如：

- `official_vof`
- `official_clsvof`
- `nn_cell_offset_matched`
- `nondefault_redistance`

时间戳和 `try_001` 只属于 smoke/探索过程，不属于正式 dataset 身份。

正式 dataset 目录已存在时，生成脚本必须拒绝静默覆盖。若实验定义真正改变，使用有科学含义的新名字或 `_v2`，不能仅换一个日期目录。

各物理 case 的公共数据骨架统一为：

```text
dataset/<case>/
├── official.../
├── nn_cell_offset_matched/     # 默认 imax=3
└── nondefault_redistance/      # imax=0,1,2,4,5,6,7,8,9,10
```

某个 case 尚无正式数据时只在 `summary.yaml` 声明该骨架，不提前创建空目录，也不把 smoke 填进去。

### 2.4 NN 方法身份与 `imax=3` 严格分开

`basilisk/src/two-phase-clsvof.h` 中的 `imax=3` 是官方默认 CLSVOF 路径，因此：

- `imax=3` 数据归入各 case 的默认 `official_clsvof` 或确定的 NN dataset；
- `imax=0,1,2,4,5,6,7,8,9,10` 才归入 `nondefault_redistance`；
- 不创建名为 `redistance_imax` 的正式 dataset；
- 不把 `imax=3` 再复制为一份“非默认 redistance 数据”；
- retained native matrix 中的 `imax=3` 行只作为对照、等价性验证和旧结果迁移审计依据；未来 NN `imax=3` 必须新跑；
- 旧 `20260710T172910Z` matrix 的 NN 行是 direct `q_gamma/Delta`，已删除且无效；不得把它们描述为 cell-offset，也不得从旧 bundle 迁出 NN 数据；
- 未来重跑的 NN 行必须使用统一的 cell-offset 数学核心 + 匹配分辨率 checkpoint：`q_cell=q_gamma/(1+(d/Delta)q_gamma)`，`kappa_cell=q_cell/Delta`；当前候选实现是 `clsvof_nn_cell_curvature.h`；
- stationary 的 `cell offset` 与未来 matrix 的 NN 数学完全相同，统一标签为 `nn_provider: cell_offset`；旧目录名 `kappa_offset` 仅是历史实验名；
- stationary N64 smoke 只证明单头文件重构在 stationary 上保持行为，尚未证明 capwave/rising 的 solver-to-raw27 适配正确。旧 capwave feature 采用 `j=-1..1, ny=+gy`，旧 rising feature 采用 `j=-1..1, ny=-gy`，当前共享头采用 `j=+1..-1, ny=+gy`；三者不得在未验证时视作相同；
- 共享化的强制边界是 MLP inference、cell-offset 公式、guard/clamp 和统计逻辑。raw27 solver adapter 只有在 capwave、rising、stationary 分别通过训练 golden vector、t=0 符号/方向检查和官方 case compile smoke 后才能合并；否则保留 case-specific adapter；
- 旧 capwave/rising direct-kreplace 和 stationary direct triplet 都是 `audit-only`，不是当前可执行方法，也不能作为未来 NN 正式结果；
- `nondefault_redistance` 的 summary 必须记录共享头文件 SHA-256、checkpoint、`nn_provider: cell_offset`、guard/clamp 统计，防止与历史 direct 数据混同比较。

### 2.5 绘图代码与其图片放在一起

每个图表主题一个目录：

```text
figures/capwave/rms_convergence/
  plot.py
  smoke_linear.png
  smoke_loglog.png
  rms_convergence.png
```

图表目录是科研试图工作区，可以保存少量有比较价值的 smoke 图片。它不再额外拆成 `drafts/`、`final/`、`versions/` 等层级。

### 2.6 `report/` 是论文图片选择面

`figures/` 保存绘图代码和候选图；`report/figures/` 只保存作者明确选择用于论文、汇报或正式报告的图片。

图进入 `report/` 是人工科研判断，不由脚本仅根据“运行完成”自动晋级。

## 3. 目标目录结构

```text
cfd/
├── basilisk/                         # 官方/上游 Basilisk，整理时不改源码
│
├── cases/
│   ├── capwave/
│   │   ├── summary.yaml
│   │   ├── generate/                 # official/NN 固定实验，优先 sh
│   │   └── src/                      # provider、feature header、overlay 工具
│   │
│   ├── rising_bubble/
│   │   ├── summary.yaml
│   │   ├── generate/
│   │   └── src/
│   │
│   ├── stationary_bubble/
│   │   ├── summary.yaml
│   │   ├── smoke/                    # 当前 N64 探索运行脚本
│   │   └── src/
│   │
│   └── _shared/
│       ├── nondefault_redistance/    # 三 case 的 imax!=3 调度与分析
│       │   ├── summary.yaml
│       │   ├── config/               # matrix.json 随代码走
│       │   ├── run_matrix.py / run_row.py / 审计、汇总脚本
│       │   └── src/                  # make_redistance_overlay.py、redistance_matrix_metrics.h
│       └── nn_cell_curvature/        # 跨 case NN 核心；raw27 adapter 受 per-case gate 约束
│           ├── summary.yaml
│           └── src/                  # core + 通过 gate 后可共享的 adapter
│
├── dataset/
│   ├── capwave/
│   │   ├── official_vof/
│   │   ├── official_clsvof/          # 官方默认 imax=3
│   │   ├── legacy_nn_direct/         # 历史 direct-kreplace，仅 audit-only
│   │   ├── nn_cell_offset_matched/   # 正确共享链路重跑后建立
│   │   └── nondefault_redistance/    # 仅 imax=0,1,2,4,5,6,7,8,9,10
│   │
│   ├── rising_bubble/
│   │   ├── official/
│   │   ├── legacy_nn_direct/         # 当前旧 checkpoint 数据，role=audit-only
│   │   ├── nn_cell_offset_matched/   # 新 imax=3 数据，与 capwave 对称
│   │   └── nondefault_redistance/    # 仅 imax=0,1,2,4,5,6,7,8,9,10
│   │
│   ├── stationary_bubble/             # 结构已锁定；正式实验完成前不创建实体目录
│   │   ├── official_clsvof/
│   │   ├── nn_cell_offset_matched/
│   │   └── nondefault_redistance/
│   │
│   └── model/                         # 第一轮保持不动，避免破坏 C include 路径
│
├── figures/
│   ├── capwave/
│   ├── rising_bubble/
│   ├── stationary_bubble/
│   └── nondefault_redistance/         # 跨 case 敏感性比较图
│
├── report/
│   ├── figures/                       # 作者选择的论文/正式报告图片
│   └── notes/                         # 现有结论性 MD、状态总结
│
├── tools/                              # 只留跨 case 公共底座
│   ├── basilisk-cc
│   ├── basilisk-run
│   └── clsvof_model/
│
├── docs/                               # 工作流、计划和仓库级说明
├── tem/                                # smoke 数据、临时编译、试验性脚本
└── build/                              # 构建产物；不作为 CFD 数据源
```

说明：`dataset/stationary_bubble/` 的目标骨架已经与其他 case 对齐，但当前不建立实体目录。只有 stationary bubble 的实验定义、分辨率矩阵和正式 gate 确定并完成正式运行后，才发布稳定 dataset。

## 4. `summary.yaml` 最小契约

### 4.1 capwave 示例

```yaml
case: capwave
solver: basilisk

sources:
  vof: basilisk/src/test/capwave.c
  clsvof: basilisk/src/test/capwave-clsvof.c
  prosperetti: basilisk/src/test/prosperetti.h
  n512_extension: basilisk/src/test/capwave-n512.c   # 本地扩展副本，非官方文件（§5）

datasets:
  official_vof:
    path: dataset/capwave/official_vof
    generator: cases/capwave/generate/official_vof.sh
    role: reference

  official_clsvof:
    path: dataset/capwave/official_clsvof
    generator: cases/capwave/generate/official_clsvof.sh
    role: reference
    redistance_imax: 3

  legacy_nn_direct:
    path: dataset/capwave/legacy_nn_direct
    generator_status: audit-only
    provenance:
      committed_scaffold: "git show 2bbed03:experiments/capwave_clsvof_kreplace/<path>"
      rescued_copy: experiments/capwave_clsvof_kreplace/recovered_from_private_tmp/
      authority: 六组历史结果 manifest + archived integral.h
    invalid_reason: direct q_gamma/Delta method retired; exact selected-mode runner unavailable
    role: audit-evidence
    redistance_imax: 3

  nn_cell_offset_matched:
    path: dataset/capwave/nn_cell_offset_matched
    generator: cases/capwave/generate/nn_cell_offset.sh
    generator_args: ["--imax", "3"]
    generator_status: to-rebuild
    method_contract: cases/_shared/nn_cell_curvature/src/clsvof_nn_cell_curvature.h
    role: pending-formal
    redistance_imax: 3

  nondefault_redistance:
    path: dataset/capwave/nondefault_redistance
    generator: cases/capwave/generate/nn_cell_offset.sh
    matrix_scheduler: cases/_shared/nondefault_redistance/run_matrix.py
    role: sensitivity
    nn_provider: cell_offset                # §2.4
    imax: [0, 1, 2, 4, 5]

figures:
  amplitude: figures/capwave/amplitude
  rms_convergence: figures/capwave/rms_convergence
  redistance_sensitivity: figures/nondefault_redistance/capwave
```

### 4.2 stationary bubble 示例

```yaml
case: stationary_bubble
solver: basilisk_clsvof
official_source: basilisk/src/test/spurious.c
redistance_imax: 3                     # 全部 smoke 走 stock two-phase-clsvof.h

formal_datasets: {}

smoke:
  native_vs_contour_analytic:
    runner: cases/stationary_bubble/smoke/run_native_vs_contour.sh   # 现 run_smoke.sh
    current_results: experiments/stationary_clsvof_smoke/results/20260711T082337Z
    role: diagnostic

  nn_cell_offset:
    runner: cases/stationary_bubble/smoke/run_nn_smoke.sh            # 现唯一 NN runner；共享 cell-offset 头文件
    current_results: experiments/stationary_clsvof_smoke/results/20260712T113747Z_nn_cell_offset
    header_sha256: 4e9509025d48dcbdf59f9407aa868321fdf54abd8129097fd17748dd78f5dc1b
    role: diagnostic

audit_only:
  nn_contour_offset_three_header:
    current_results: experiments/stationary_clsvof_smoke/results/20260711T143057Z_nn_contour_offset
    role: equivalence-evidence         # 与现单头文件时间序列字节一致

  nn_direct_triplet:
    current_results: experiments/stationary_clsvof_smoke/results/20260711T130557Z_nn_triplet
    role: audit-evidence               # 历史 direct 路径，不可执行审计证据（§7 第 4 条）
```

迁移完成前，`current_results` 可以指向旧路径；完成核验后再统一改到 `tem/stationary_bubble/`。这允许先整理入口，不冒险移动诊断数据。

## 5. 当前目录到目标目录的映射

| 当前路径 | 目标角色/路径 | 迁移规则 |
| --- | --- | --- |
| `experiments/capwave_clsvof_kreplace/` | `cases/capwave/` + `dataset/capwave/legacy_nn_direct/` | 旧 direct runner/provider 只作审计底稿，不重建成当前入口；历史结果与 manifest 登记为 audit-only。未来 `nn_cell_offset_matched` 从共享头文件新建并使用新实验身份 |
| `experiments/rising_clsvof_kreplace/` | `cases/rising_bubble/` + `dataset/rising_bubble/legacy_nn_direct/` | 保留当前用户删除状态；历史读取锚点固定为 `git show 95c8076:experiments/rising_clsvof_kreplace/<path>`，不得用会漂移的 `HEAD`，也不得恢复旧 direct 链为当前入口 |
| `experiments/stationary_clsvof_smoke/` | `cases/stationary_bubble/` | 运行代码归 `smoke/`，C/header/overlay 归 `src/`；现有结果先原地登记 |
| `experiments/clsvof_redistance_imax_matrix/` | `cases/_shared/nondefault_redistance/` | 代码/config 保留；旧结果 bundle 只迁出 48 个 native row。旧 NN row 和 derived audit/figure 已删除，不得写成可迁移；未来 NN 用共享 cell-offset 链重跑 |
| `experiments/clsvof_kappa_offset_conversion/` | `cases/_shared/nn_cell_curvature/` | 当前 cell-offset 核心候选是单头文件 `include/clsvof_nn_cell_curvature.h`；stationary N64 已验证。capwave/rising raw27 adapter 仍需 per-case gate，不能把 stationary 结果外推成全仓验证。该目录历史 diagnostic results 不自动晋级正式 dataset |
| `dataset/official_data/capwave/raw/official_vof/` | `dataset/capwave/official_vof/` | 保留原始数据和来源文件 |
| `dataset/official_data/capwave/raw/official_clsvof/` | `dataset/capwave/official_clsvof/` | 作为默认 `imax=3` 数据；其中 `capwave` 是 Mach-O arm64 编译产物（SHA-256 `e64737c2...798e`），先登记/备份，Phase 5 再单独决定是否删除 |
| `dataset/official_data/capwave/raw/extended_*` | 并入对应 official dataset | 先按文件 hash 审计重复 N16-N128，再合并 N256/N512；不盲目覆盖 |
| `dataset/official_data/capwave-clsvof/` | 待与 `official_clsvof` 去重 | 只有 hash/数值等价审计后才能删除重复副本 |
| `dataset/official_data/rising_bubble/` | `dataset/rising_bubble/official/` | case1/case2 和方法变体继续保持可区分 |
| `dataset/nn_data/rising-clsvof/` | `dataset/rising_bubble/legacy_nn_direct/` | 旧 direct checkpoint 数据，仅 audit-only；不重命名成 matched-resolution 正式结论 |
| `dataset/official_data/staionary bubble/` | 暂不建立对应正式 dataset | 当前为空；确认无隐藏文件/引用后再处理拼写和空目录 |
| `tools/capwave/` | `figures/capwave/<topic>/` | plot 代码与生成图片同目录；通用工具才留 `tools/` |
| `tools/rising bubble/` | `figures/rising_bubble/<topic>/` | 同上；含空格目录的改名放到最后阶段 |
| `experiments/.../results/.../figures/` | `figures/<case-or-study>/<topic>/` | plot 脚本与图一起迁移；数据来源改指 canonical dataset |
| `reports/` | `report/notes/` | 原文冻结不改（历史报告是证据快照），另附新旧路径映射附注；不直接删除旧目录 |
| `tem/` | `tem/` | 继续承担 smoke/探索；任何 report 不得长期依赖 tem 路径 |
| `/private/tmp/cfd-capwave-clsvof-kreplace/` | 见 §5.1 | git worktree（分支 `codex/capwave-clsvof-kreplace`）；已提交内容由分支保底，未提交差异与未导入结果已抢救；Phase 5 验收通过后才 `git worktree remove` |
| `dataset/official_data/capwave/figures/`、`dataset/official_data/rising_bubble/figures/` | `figures/<case>/official_reproduction/` | gnuplot 脚本与其 `.svg`/`author_style` 输出同迁，脚本内 dataset 路径同步更新 |
| `dataset/official_data/*/sources/` | 随对应 official dataset 保留 | 是 `summarize_canary.py` 与 matrix 汇总/绘图的读取依赖（`c1g3l4*.txt` 等），移动时同步更新引用 |
| `basilisk/src/test/capwave-n512.c` | 登记进 capwave summary `sources`；后续迁入 `cases/capwave/src/` | 本地扩展文件，非官方；被 `dataset/official_data/capwave/README.md` 引用，迁移时一并更新 |
| `basilisk/src/test/static_bubble` | Phase 5 删除清单 | 遗留已编译二进制（Mach-O arm64），非官方文件；删除需单独确认 |
| `experiments/capwave_clsvof_kreplace/diagnostic_imports/`、`recovered_from_private_tmp/` | 原地保留，summary 登记 role=diagnostic/rescue | 临时区导入与抢救内容；Phase 5 再议去留 |

### 5.1 `/private/tmp` 临时 worktree 的处置

`/private/tmp/cfd-capwave-clsvof-kreplace` 是注册在主仓库上的 git worktree（分支 `codex/capwave-clsvof-kreplace`，HEAD=`2bbed03`）。分工如下：

- 已提交、由分支保底（worktree 消失也不丢，前提是不删分支）：capwave README、`include/capwave_k_provider.h`、`include/clsvof_nn_features.h`、`make_overlay_integral.py`、基线版 `run_canary.sh`/`summarize_canary.py`、`tests/test_feature_header_compile.sh`、`tests/test_make_overlay_integral.py`。取回方式 `git show 2bbed03:<path>`。
- 未提交、有丢失风险的内容已于 2026-07-12 抢救性复制到 `experiments/capwave_clsvof_kreplace/recovered_from_private_tmp/`（纯新增，含 `PROVENANCE.md` 与 sha256 清单）：改版 `run_canary.sh`、改版 `summarize_canary.py`、未导入结果 `results/20260709T134408Z`（blocked/partial）、四份旧语义 `export_manifest.json`（记录 kreplace 时期 `kappa = hkappa/Delta` 直换口径；主仓库现版本已改为 cell-offset 口径，`nn_weights.h` 四份均逐字节一致）。
- 已确认不可恢复：产生主仓库六组历史结果的 runner 版本（带 `CAPWAVE_SELECTED_MODES` 支持）不在 worktree 也不在分支。六份 manifest 记录了 common flags、NN 的 `-disable-dimensions` 说明、selected mode、matched resolution、raw27 顺序、clamp 和三项 source fingerprint，但**没有**完整 qcc argv/环境、provider/features/weights hash、`CAPWAVE_SELECTED_MODES` 解析实现或 `native_wrapper_fixed_sweep` 的精确 patch。因此“manifest + `2bbed03` 足以行为等价重建”的断言不成立；只能重建一个新身份并通过输出等价 gate，且旧 direct 方法不再恢复为当前执行链。
- 不抢救：`work/`（约 4.4M 编译产物）、`.qcc*` 临时目录、与主仓库逐字节一致的文件（`make_single_resolution_case.py`、`tests/test_make_single_resolution_case.py`、`nn_weights.h`、`clsvof_mlp_infer.h`）。
- worktree 本体与分支：Phase 5 验收通过前不删除分支、不执行 `git worktree remove`（§9）。
- 全量差异复核：临时 `dataset/` 共 8 个文件，无 `Only in temp`；4 个 `nn_weights.h` 与主仓库一致，只有 4 个旧语义 export manifest 不同且已抢救。临时 `tools/clsvof_model_export/` 只有 `clsvof_mlp_infer.h`，与主仓库一致。`work/` 与 `.qcc*` 仍判定为可再生编译产物，不进入抢救包。

## 6. 非默认 redistance 数据的拆分规则

旧矩阵身份原计划包含：

```text
2 benchmarks x 2 methods x 4 resolutions x imax(0..5)
```

但当前 `results/20260710T172910Z/NATIVE_ONLY_RETAINED.md` 明确记录：旧 NN 行使用废弃的 direct `q_gamma/Delta`，其 48 个 NN row、全部聚合表、figure、audit verdict、scheduler 和 verification bundle 均已删除。当前可核验内容是 **48/48 native row**，不是完整 96-row matrix。`docs/experiment_inventory.md` 原有“96/96、10 reuses、全部 PASS”条目已在本轮同步修正，不得从旧报告恢复该表述。

未来恢复完整研究矩阵有两条互不混用的证据线：

1. retained native：可以迁移 48 个 native row，其中非默认 `imax=0,1,2,4,5` 共 40 行，默认 `imax=3` 共 8 行；
2. 新 NN cell-offset 云矩阵：必须用统一 cell-offset 核心和通过 per-case gate 的 raw27 adapter 运行 132 行；其中非默认 120 行进入三个 case 的 sensitivity dataset，默认 12 行分别进入三个 case 的 `nn_cell_offset_matched`。其中 capwave/rising 的 0..5 子集与旧 48-row native 证据范围重叠；stationary 和 imax=6..10 没有旧 native matrix，不得虚构对照。

新 NN summary 必须携带 `nn_provider: cell_offset`、cell-offset core 与 raw27 adapter 的 SHA-256、checkpoint、guard/clamp 统计和新 matrix ID。禁止复用旧 NN 指标或旧 96-row 聚合结论。

整理时必须按以下规则拆分：

### 6.1 capwave

```text
dataset/capwave/nondefault_redistance/
├── imax_0/
├── imax_1/
├── imax_2/
├── imax_4/
├── imax_5/
├── imax_6/
├── imax_7/
├── imax_8/
├── imax_9/
└── imax_10/
```

每个 `imax_*` 内保留 native/NN 和分辨率区分。native 可来自 retained bundle；NN 只能来自新 cell-offset 重跑。`imax_3` 不进入这里。

### 6.2 rising bubble

```text
dataset/rising_bubble/nondefault_redistance/
├── imax_0/
├── imax_1/
├── imax_2/
├── imax_4/
├── imax_5/
├── imax_6/
├── imax_7/
├── imax_8/
├── imax_9/
└── imax_10/
```

同样保留 native/NN、case 和分辨率身份；NN 只能来自新 cell-offset 重跑。矩阵只覆盖 Hysing Case 1，不能在 summary 中写成覆盖全部 rising 数据。

### 6.2.1 stationary bubble

stationary 使用同一目录集合和四个匹配 checkpoint，`N64/128/256/512`
分别映射到 `LEVEL=6/7/8/9`。该分支是新云矩阵的一部分，没有旧 retained
native 0..5 matrix 可以冒充对照；其结果身份必须保持 NN cell-offset。

### 6.3 `imax=3` 的处理

1. 将 retained native 的 8 个 `imax=3` 行与 canonical 默认 CLSVOF 数据做 hash 或物理量等价审计；
2. 新 cell-offset NN 的 8 个 `imax=3` 行只与同一新方法身份的 canonical NN 数据对齐，不与旧 direct kreplace 对齐；
3. canonical 默认数据继续留在各 case 的 default dataset；
4. retained native `imax=3` 行在旧结果目录中保留到整个迁移验收完成；
5. 新 figures 可以把默认 dataset 作为 reference 与 `imax!=3` 比较；
6. 在没有确认所有新图、表和报告均可重建前，不删除旧 native bundle；
7. 当前 `config/matrix.json` 恰有 5 个 `candidate_reuse`（4 个 capwave native + 1 个 rising native），retained 48 个 manifest 中也恰有 5 个 `planning_status=candidate_reuse`，且五者均保存 `reuse_validation`。因此当前可证数字是 **5 个 native reuse replay**，不是 10；旧 aggregate audit 已删除，不能再“以 bundle 顶层审计为准”。

## 7. stationary bubble CLSVOF 的整理边界

当前 `experiments/stationary_clsvof_smoke/` 明确是 N64 smoke，包含：

- stock `clsvof_native`；
- `clsvof_contour_analytic`；
- 历史 direct `clsvof_nn_baseline_64_hgradient`；
- 旧三头文件 `clsvof_nn_contour_offset_64`；
- 当前单头文件 `clsvof_nn_cell_offset_64`；
- 四组结果目录，其中只有 native/analytic 控制组和当前单头文件结果进入当前 smoke 比较；其余两组只作 audit/equivalence evidence。

### 7.1 已核验的 stationary 单头文件 smoke

这里的“旧/新”只描述代码包装方式，不表示两个不同模型或两种不同物理方法：

- 旧 `143057Z`：同一个 cell-offset 公式分散在 `kappa_offset_features.h`、`kappa_offset_math.h`、`kappa_offset_provider.h` 三个头文件；
- 新 `113747Z`：把完全相同的 feature/math/provider 合并到 `clsvof_nn_cell_curvature.h` 一个头文件；
- 两者使用同一 baseline-64 checkpoint、同一 stationary case、同一 `imax=3` 和同一 cell-offset 数学；
- 历史 `130557Z_nn_triplet` 才是另一条 direct `q_gamma/Delta` 方法，不能与上述两者混为一谈。

当前受支持结果：

```text
experiments/stationary_clsvof_smoke/results/20260712T113747Z_nn_cell_offset/
```

核验事实：

1. runner 实际复制 `experiments/clsvof_kappa_offset_conversion/include/clsvof_nn_cell_curvature.h`，并由生成后的 `integral.h` 在唯一 `ki` 位置调用 `kappa_offset_provider(point,d)`；
2. 运行结果和归档头文件 SHA-256 均为 `4e9509025d48dcbdf59f9407aa868321fdf54abd8129097fd17748dd78f5dc1b`；
3. 新旧 summary 除 mode 名 `clsvof_nn_cell_offset_64` / `clsvof_nn_contour_offset_64` 外，七项数值完全相同；
4. 新旧完整 `La-12000-6` SHA-256 均为 `35893bcf780c1ae0521c0d1aa07d81a839da951715af5ca7c26658e8c31a5bcb`，可判定为字节一致；
5. 新 log 记录 `evaluations=3698968`、`clamp_hits=0`、`denominator_guard_hits=0`、`min_abs_denominator=0.9809494798605789`、`max_abs_d_over_h=0.48796347089887804`；
6. 该证据证明 stationary N64 上的头文件重构保持行为，不证明 capwave/rising raw27 adapter 已正确，也不将 smoke 晋级 formal dataset。

整理时：

1. 代码进入 `cases/stationary_bubble/smoke/` 和 `src/`；
2. 四组现有结果先保持原地，在 `summary.yaml` 中区分 current、equivalence-evidence 和 audit-only；
3. 不把它们放入 `dataset/stationary_bubble/`；
4. 历史 direct 结果仅作不可执行审计证据，不进入当前汇总或正式矩阵；
5. 如需保留少量对比图，代码和图片放入 `figures/stationary_bubble/<topic>/`；
6. 只有以后正式定义 resolution/method matrix 并通过 gate，才创建稳定的 stationary dataset。

## 8. 分阶段执行计划

### Phase 0：冻结与清点

目标：在移动任何文件前固定当前事实。

任务：

1. 保存当前 `git status --short` 清单；
2. 将当前已删除的 rising tracked 文件标记为用户现有改动，整理过程不恢复；历史只读锚点固定为 commit `95c8076`。capwave 旧 direct runner/provider 只做审计登记，不恢复为当前执行链；
3. 每个移动批次开始前重新检查 capwave/rising/stationary/redistance 进程；2026-07-12 已检查过一次进程表、未发现活动 writer，但该结论不跨批次沿用；
4. 对 retained 48-row native matrix、capwave/rising 历史 direct 结果、共享 cell-offset 头文件和 model exports 生成迁移前 hash 清单；
5. 统计所有旧路径被脚本、summary、report 引用的位置；
6. 按 §5.1 清点 `/private/tmp` 临时 worktree：核验分支 `codex/capwave-clsvof-kreplace` 对象完整、未提交差异已抢救；
7. 对未被 git 跟踪的关键目录做分层仓库外 tar 备份。强制 evidence archive 包含完整 `dataset/`（实测约 14M，含 `.pt`，无需排除）、各 experiment 的代码/`results/`/抢救目录和 `reports/`；单独 optional scratch archive 保存 matrix/stationary 的 `work/`（实测约 98M）。缓存、`.qcc*`、`.DS_Store` 和可重建 binary 不进入强制包；两个 archive 均生成 SHA-256 和文件清单；
8. 在这个阶段不移动、不改名、不删除。

验收：得到一份路径、大小、角色、引用者和可否再生的清单。

### Phase 1：建立目标空骨架和 summary

目标：先建立新入口，不触碰旧数据。

任务：

1. 创建 `cases/capwave`、`cases/rising_bubble`、`cases/stationary_bubble`；
2. 创建 `cases/_shared/nondefault_redistance` 和 `nn_cell_curvature`；
3. 每个单元只建立一个 `summary.yaml`；
4. 创建 `figures/` 和 `report/figures`、`report/notes`；
5. summary 暂时可以指向旧路径。

验收：从 summary 能找到当前所有重要数据和运行入口，不需要移动旧文件。

### Phase 2：迁移运行代码

目标：按 case 收拢“怎么跑”。

任务：

1. capwave/rising 的官方/native 固定运行优先整理成简洁 sh。旧 direct NN 代码只可用 `git show 2bbed03:<path>`（capwave）或 `git show 95c8076:<path>`（rising）做 provenance 审计，不恢复为当前入口；新的 NN runner 从共享 cell-offset 契约建立，并使用新实验身份；
2. 将共享 MLP inference、cell-offset 公式、guard/clamp 和统计逻辑放入 `_shared/nn_cell_curvature/src/`。当前 `clsvof_nn_cell_curvature.h` 作为候选底稿迁入；raw27 solver adapter 必须先分别通过 capwave/rising/stationary gate，未通过前允许放在各 case 的 `src/`，禁止为了“只有一个头文件”强行统一；
3. stationary smoke 脚本移入 `cases/stationary_bubble/smoke/`；
4. redistance matrix 的调度/审计代码移入 `_shared/nondefault_redistance`；
5. 更新路径时保持 Basilisk 官方源码只读；
6. 对被迁移代码运行原有测试、overlay 生成检查和“只编译不执行”的官方 case smoke；Basilisk binary 不保证支持只读 `--help`，不得用 `-help/--help` 触发意外求解；
7. `nondefault_redistance` 与 `nn_cell_curvature` 同一批迁移，并同步更新 `run_row.py` 的硬编码依赖路径：共享 `clsvof_nn_cell_curvature.h`、`tools/clsvof_model/include/clsvof_mlp_infer.h`、`dataset/model/c_exports/baseline_*/nn_weights.h`、`basilisk/src/test/capwave-clsvof.c`、`basilisk/src/test/rising.c`，以及自身 `include/redistance_matrix_metrics.h` 与 `config/matrix.json`。
8. capwave、rising、stationary 各自只保留一个 `generate/nn_cell_offset.sh`。脚本接受显式 `--imax <N>`（0..10）；`imax=3` 发布到该 case 的 `nn_cell_offset_matched`，其余值发布到 `nondefault_redistance/imax_<N>` 的 staging/目标位置。matrix 只能调用这些 per-case 脚本，不能复制一套 provider、compile flags 或 case patch 逻辑。

验收：新入口能调用旧数据路径或临时工作区；测试基线为当前实际可通过的集合，并额外要求 C/PyTorch forward parity、cell-offset 公式、overlay 唯一替换点和官方 case compile smoke 全部通过。raw27 不能只测数组形式的 golden fixture，还要分别测试 capwave/rising/stationary 的 solver adapter；rising 必须单独锁定 `ny` 符号。未通过这些 gate 时，不得在 summary 中写“全仓共用同一 raw27 实现”；不引用 2026-07-10 报告中已删除测试的计数。

#### Phase 2A：迁移代码严格复现 gate

每条迁移后的 case runner 在进入 canonical dataset 前必须完成：

1. 对比旧/新 case、overlay、provider/core、模型权重和默认 `two-phase-clsvof.h` 的哈希或精确差异；
2. 用新路径跑一次完整默认参数 smoke，与已接受旧路径结果比较完整时间序列和所有 summary 指标；
3. 至少再跑两次独立短 smoke，验证重复结果确定性；
4. 至少跑一个 `imax!=3` 短 smoke，确认生成的本地 header 中参数确实改变，且输出仍进入 smoke/tem 而不是 formal dataset；
5. 核验 manifest 中 case、method、purpose、imax、resolution、模型与输入哈希；
6. formal 路由只能发布到 `dataset/<case>/nn_cell_offset_matched` 或 `nondefault_redistance/imax_N`，已存在目标拒绝覆盖；
7. 形成一份数据报告后，删除本轮新产生的 smoke result、staging 和 work；历史基准不随 smoke 清理删除。

只有完整复现和重复 smoke 全部通过，才能把 runner 标为 `verified`。

### Phase 3：整理 canonical dataset

目标：正式数据脱离代码目录。

任务：

1. 先整理 capwave official VOF/CLSVOF；旧 direct NN 结果进入 `legacy_nn_direct` audit-only，正确的 `nn_cell_offset_matched` 只在新运行完成并通过 gate 后建立；
2. 再整理 rising official；旧 direct checkpoint ablation 进入 `legacy_nn_direct` audit-only；预留但不提前创建 `nn_cell_offset_matched`，只在新 `imax=3` 数据通过 gate 后发布；
3. 对 official/extended/capwave-clsvof 重复数据做 hash 和数值审计；
4. 从 retained bundle 抽取 40 个 native 非默认行；新 cell-offset NN 40 行完成后再加入两个 case 的 `nondefault_redistance`，禁止从已删除的旧 NN 行补值；
5. `imax=3` 只注册为 default reference，不复制到非默认目录；
6. stationary smoke 不进入 canonical dataset。

验收：每个 dataset 都有语义稳定的目录名，并能由相应 summary 找到生成脚本。

### Phase 4：整理 figures 与 report

目标：每个绘图代码和对应图片放在同一目录。

任务：

1. 把 `tools/capwave`、`tools/rising bubble` 中的 case-specific plot（gnuplot）连同 `dataset/official_data/*/figures/` 中它们生成的图与 `author_style` 输出一起迁入 `figures/<case>/official_reproduction/`；
2. 把 redistance matrix 的 plot 脚本按图表主题拆分到 `figures/nondefault_redistance/`；旧 96-row derived figures 已删除，必须等新 cell-offset NN 行完成后从 retained native + 新 NN raw data 重建，不能迁移或引用旧图；
3. 修改 plot 与分析脚本的数据入口，使其读取 canonical dataset，而不是旧 `experiments/*/results`；已知受影响引用：gnuplot 脚本读写 `dataset/official_data/*/{raw,sources,figures}`；`summarize_canary.py`（capwave/rising）与 matrix `summarize/plot` 读 `dataset/official_data/rising_bubble/sources/c*.txt`、`dataset/official_data/capwave-clsvof`；
4. 保留少量有意义的 smoke 图，其余候选先登记，后续再决定是否删除；
5. 将作者明确选择的图复制到 `report/figures/`；
6. 把当前 `reports/*.md` 复制到 `report/notes/`：原文冻结不改（历史报告是证据快照），另附一份新旧路径映射附注。

验收：打开任一 figure 目录即可同时看到 plot 代码和它生成的图片；report 不依赖 tem。

### Phase 5：旧目录退役与低风险卫生清理

目标：在新结构通过验证后处理重复和临时内容。

任务：

1. 检查旧 `experiments/*/results` 与 canonical dataset 的文件数、hash、关键指标；
2. 检查新 figures 与旧 figures 的数据来源和图像输出；
3. 只有在确认 canonical/audit-only 登记完整后，才提出旧 results/diagnostic_imports/work 的删除清单；历史 direct 数据不要求“可由当前正确链路重建”，而要求 provenance 与失效说明可追溯；
4. 单独处理 `.DS_Store`、`__pycache__`、`.pytest_cache`、`.qcc` 和 build 中间文件；
5. 修复 `staionary bubble` 拼写和 `tools/rising bubble` 空格目录；
6. `dataset/official_data/capwave/raw/official_clsvof/capwave` 和 `basilisk/src/test/static_bubble` 两个 Mach-O 二进制分别登记 hash，作为独立删除项；删除必须单独获得用户确认，不能把“执行整理计划”解释成自动删除许可。

验收：旧目录没有仍被 summary、plot 或 report 引用；删除清单逐项可解释。

## 9. 不可跨越的安全边界

1. 不修改 `basilisk/src` 官方代码；
2. 不恢复或覆盖当前用户在 rising 目录中的删除/修改；
3. 不在未知进程可能写结果时移动对应目录；
4. 不把 smoke 重新命名为 formal；
5. 不把 `imax=3` 归入 `nondefault_redistance`；
6. 不删除当前 48-row native matrix bundle，直到 canonical native 数据、新 cell-offset NN 数据、全部图和 report 均通过重建检查；
7. 不移动 `dataset/model`，直到所有 C include 和脚本引用另有专项迁移计划；
8. 不因目录名看起来临时就删除未跟踪结果；
9. 不把选择论文图的判断自动化，`report/figures` 由作者人工选择；
10. 不修改已归档报告正文，路径变化只通过附注映射表达；
11. 对 `/private/tmp` 临时 worktree 只做只读复制与登记；Phase 5 验收通过前不删除分支 `codex/capwave-clsvof-kreplace`，不执行 `git worktree remove`。
12. 不恢复、重新暴露或包装任何 direct `q_gamma/Delta` NN runner；历史 direct 文件只能通过固定 commit/抢救包用于只读审计。
13. 不把旧 inventory 的“96/96 complete”或“10 reuses”写进当前报告；当前可证事实是 48 个 retained native row 和 5 个 native reuse validation。

## 10. 最终验收清单

- [ ] 每个物理 case 只有一个清晰入口和一个 `summary.yaml`；
- [ ] capwave/rising/stationary 的官方源码路径均明确；
- [ ] 固定 Basilisk 实验使用简洁 sh，复杂 matrix 才使用 Python 调度；
- [ ] 正式 dataset 不以时间命名；
- [ ] `nondefault_redistance` 中只出现 `imax=0,1,2,4,5,6,7,8,9,10`；
- [ ] 默认 `imax=3` 数据只归属于各 case 的 default CLSVOF/NN dataset；
- [ ] 历史 direct NN 数据全部标为 audit-only，当前可执行入口中不存在 `q_gamma/Delta` direct provider；
- [ ] capwave/rising/stationary 和未来 matrix 共用同一 cell-offset 数学核心；raw27 adapter 是否共用由 per-case gate 决定；
- [ ] stationary N64 结果仍明确标注为 smoke/diagnostic；
- [ ] 绘图代码与对应图片位于同一目录；
- [ ] `report/figures` 只含作者选择的正式图片；
- [ ] `report/`、figures 和 summary 不依赖 `tem/`；
- [ ] 旧 results 在退役前完成 hash、数值和图表重建核验；
- [ ] 所有删除均经过单独确认；
- [ ] 当前用户工作树改动完整保留；
- [ ] capwave/rising 的旧 direct provenance 已固定到 `2bbed03`/`95c8076` 和历史 manifest；新 cell-offset runner 使用新身份，不宣称与旧 direct runner 行为等价；
- [ ] retained 历史 matrix 明确为 48 native rows；5 个 reuse validation 已逐行核验；新 132-row NN 云矩阵未完成前不声称新灵敏度矩阵完整；
- [ ] C/PyTorch forward parity、cell-offset 公式、overlay 唯一替换点和官方 case compile smoke 全部通过；capwave/rising/stationary 的 solver raw27 adapter 分别通过，rising `ny` 符号已锁定；
- [ ] 临时 worktree 未提交内容已抢救或显式放弃，分支对象核验完整；
- [ ] 未跟踪关键目录在任何移动前已有仓库外 tar 备份。

## 11. 用户决策记录与剩余选择

### D1：rising 默认 NN dataset——已决定

决定采用：

```text
dataset/rising_bubble/nn_cell_offset_matched/
```

保存新 cell-offset 方法在默认 `imax=3` 下的确定数据；各 case 使用相同的默认/非默认数据骨架。

### D2：默认/非默认 NN 数据由谁生成——已决定

决定采用 per-case 单一 generator，并把 `imax` 作为脚本参数：

- `cases/capwave/generate/nn_cell_offset.sh --imax <N>`
- `cases/rising_bubble/generate/nn_cell_offset.sh --imax <N>`
- future `cases/stationary_bubble/generate/nn_cell_offset.sh --imax <N>`

`imax=3` 进入 matched dataset；其余允许值 `0,1,2,4,5,6,7,8,9,10` 进入 nondefault dataset。matrix 只负责批量调用、并发、补跑、汇总和审计。

### D3：stationary 旧三头文件等价结果永久保留到什么程度——已决定

决定采用 B：Phase 5 前完整保留；仓库外 evidence archive、summary、头文件 hash 和完整时间序列 hash 均确认后，只在仓库内保留新 `20260712T113747Z_nn_cell_offset` raw，加一条旧结果等价性登记。这样不重复长期保存两份字节一致的 2.26MB 时间序列。实际删除仍需单独确认。

## 2026-07-12 执行记录

- Phase 1 的 case/shared 骨架和单一 `summary.yaml` 已建立。
- Phase 2 的三个 `nn_cell_offset.sh` 已建立并实际运行；capwave、rising
  Case 1、stationary 分别完成默认复现、重复 smoke 和非默认 imax 控制。
- `_shared/nondefault_redistance/run_matrix.py` 已改为只调用 per-case shell；
  132 行 formal dry-run 已验证 0..10、三个 case、四个分辨率和全部唯一路由；
  `imax=3` 只路由到 matched dataset，不进入 nondefault dataset。
- 38 项独立测试通过。详细证据见
  `report/notes/2026-07-12-runner-framework-verification.md`。
- 云矩阵已扩展为三个 case、四个分辨率、`imax=0..10` 的 132 行；完整
  dry-run 132/132 通过，两轮并发 N64/imax=10 smoke 可重复，扩展后的
  authoritative 回归测试 56 项通过。云端命令见
  `report/notes/2026-07-12-cloud-imax-0-10-matrix.md`。
- 本轮没有发布 formal dataset；全部新 smoke/work 产物已在报告后删除。
- Phase 3（canonical dataset 实体迁移）、Phase 4（figures/report 图表整理）和
  Phase 5（旧目录退役）仍未执行，不能因 runner 验证通过而标记完成。
