# Generate 新范式：Claude 审核稿

日期：2026-07-22

状态：只修改并静态核对生成规范；未启动任何 CFD 算例，未迁移或改写已有数据。

## 1. 已由用户确认的正式口径

- 本轮目标是一次性跑完并固定一套高成本正式数据；以后只补少量新增项。
- 288 行配对矩阵只包含匹配的 CLSVOF/NN。每个物理条件下，两者使用同一 case、网格、`imax`、时间终点、编译参数和线程数。
- `imax=3` 是默认主结果，角色记为 `default`；`imax=0,1,2,4,5` 是敏感性结果，角色记为 `sensitivity`。
- `VOF-HF` 是独立正式基准，`experiment_role=official_reference` 表示其来源角色；它不计入 288 行配对矩阵，但要进入 smoke、formal 和 READY 验收。VOF-HF 跟随 CLSVOF/NN 网格，共 24 行，因此完整 formal campaign 是 312 项。
- 方法命名大小写固定为 `VOF-HF`、`CLSVOF`、`NN`；runner 文件名、manifest 的 `method` 和未来产物方法目录全部使用这三个数值方法名。
- stationary 只运行一条到 `tau=2` 的正式轨迹；途中精确到达 `tau=1` 时多保存一行中间里程碑，终点再保存 `tau=2`。精确事件可能缩短到达 `tau=1` 前的一个时间步，但 CLSVOF/NN 使用同一事件和时间点，因此配对一致。此前 smoke 已验证，不设计 `tau=2` 后的自动续跑或收敛阈值。
- stationary 同时保存两类曲率误差：
  - `official_style_ekmax`：沿用 stock-style fraction/height-function 诊断；
  - `active_provider_ekmax`：在 `integral.h` 实际插入位置的单元上，直接评估当前有效 provider（CLSVOF 的 `distance_curvature` 或 NN provider）。
- NN provider 运行统计只保存在单独的 `provider_stats.csv`；CLSVOF 行没有该文件。benchmark/runtime 日志不再混入 provider 统计行。
- oscillating 沿用官方 gnuplot fit、error 和 Laplace 输出。stock 脚本没有 residual/R2 硬门槛，因此新规范也不额外发明门槛，只要求官方输出通道完整、可解析。
- oscillating 的独立 `VOF-HF` 参考只运行 `Standard` centered-solver 分支；Basilisk stock Makefile 中另有 Momentum、Compressible 两个不同求解器变体，但本次明确排除，避免把三者误当作三种界面方法，也保持与 CLSVOF/NN 的 centered host 对齐。

## 2. 固定矩阵与角色

| case | 物理分支 | N | imax | 方法 | 行数 |
|---|---|---|---|---|---:|
| capwave | 1 | 32, 64, 128, 256, 512 | 0--5 | CLSVOF, NN | 60 |
| rising_bubble | case 1, case 2 | 32, 64, 128, 256, 512 | 0--5 | CLSVOF, NN | 120 |
| stationary_bubble | 1 | 32, 64, 128, 256 | 0--5 | CLSVOF, NN | 48 |
| oscillating_droplet | 1 | 32, 64, 128, 256, 512 | 0--5 | CLSVOF, NN | 60 |
| 合计 | | | | | 288 |

角色计数：48 行 `default`（`imax=3`），240 行 `sensitivity`（其余 `imax`），另有 24 行正式 `official_reference` VOF-HF。完整 campaign 共 312 项。

## 3. 每个 case 的产物形式

以下是本轮 runner 实际会生成并检查的 v1 行产物。公共文件迁移到 `_provenance/` 的瘦身方案见第 4 节，目前尚未执行。

### 3.1 Capwave

```text
capwave/Nxxxx/imaxNN/<CLSVOF|NN>/
├── manifest.json
├── wave.dat
├── official_error.dat
├── prosperetti.h
├── metrics.csv
├── plot_data.csv
├── provider_stats.csv          # 仅 NN
├── scientific_artifacts.json
├── compile.stdout / compile.stderr / solver.stdout.txt
└── source_snapshot/
```

核心科学量：738 点振幅历程、Prosperetti 参考、官方定义的相对 RMS，以及独立重算的 RMS 一致性检查。

### 3.2 Rising bubble

```text
rising_bubble/caseK/Nxxxx/imaxNN/<CLSVOF|NN>/
├── manifest.json
├── history.dat
├── interface.dat
├── circularity.csv
├── metrics.csv
├── plot_data.csv
├── provider_stats.csv          # 仅 NN
├── scientific_artifacts.json
├── compile.stdout / compile.stderr
└── source_snapshot/
```

核心科学量：`t=0..3` 的体积变化、质心和上升速度，`t=3` 界面，以及全时段 circularity。

### 3.3 Stationary bubble

```text
stationary_bubble/Nxxxx/imaxNN/<CLSVOF|NN>/
├── manifest.json
├── timeseries.dat
├── runtime_and_terminal.log
├── official_terminal.dat
├── milestones.csv
├── termination.csv
├── metrics.csv
├── plot_data.csv
├── provider_stats.csv          # 仅 NN
├── scientific_artifacts.json
├── compile.stdout / compile.stderr / solver.stdout.txt
└── source_snapshot/
```

`milestones.csv` 固定包含：

```text
milestone,tau,iteration,u_star,shape_error_avg,shape_error_rms,
shape_error_max,official_style_ekmax,active_provider_ekmax,
active_provider_samples
```

正式行必须有 `tau_1` 和 `terminal/tau=2` 两行。NN 的里程碑诊断调用不进入 provider evaluations/clamp/guard 统计。

### 3.4 Oscillating droplet

```text
oscillating_droplet/Nxxxx/imaxNN/<CLSVOF|NN>/
├── manifest.json
├── timeseries.dat
├── fit_curve.dat
├── fit.log
├── error.dat
├── laplace.dat
├── fit_summary.dat
├── termination.csv
├── command.txt
├── metrics.csv
├── plot_data.csv
├── provider_stats.csv          # 仅 NN
├── scientific_artifacts.json
├── compile.stdout / compile.stderr / runtime.stderr.txt
└── source_snapshot/
```

完成条件是动力学历史达到官方时间终点且 stock fit/error/Laplace 通道均完整可解析；不额外设置 residual/R2 门槛。

### 3.5 Independent VOF-HF official reference

建议最终与 288 行矩阵分开存放：

```text
<campaign>/VOF-HF/<case>/...
```

它表示 VOF-HF 正式基准；manifest 中记为 `method=VOF-HF`、`experiment_role=official_reference`。它不是某个 `imax` 的第三种配对方法，不进入 CLSVOF/NN 配对统计，但属于 formal READY 的必需产物。

VOF-HF 跟随配对网格：capwave 5 行、rising 两个 case 共 10 行、stationary 4 行、oscillating 5 行。oscillating 的 manifest 固定 `solver_variant=Standard`，但科学文件直接位于对应 N 行目录，与 CLSVOF/NN 使用同名输出；不再增加冗余的 `Standard/` 子目录，也不生成 Momentum 或 Compressible 产物。stock 未覆盖的高分辨率明确标为 `stock_compatible_extension`。

所有 VOF-HF 正式行与 CLSVOF/NN 一样生成 `metrics.csv`、`plot_data.csv` 和带逐文件 SHA-256 的 `scientific_artifacts.json`。为保证后续同图比较不缺量：rising VOF-HF 使用相同的只观测 circularity 事件；stationary VOF-HF 固定运行至 tau=2、精确记录 tau=1 和 tau=2，并把 active provider 明确解释为 VOF height-function curvature；oscillating VOF-HF 使用根目录下统一的 kinetic/fit/error/Laplace 文件名。

分析充分性不是人工约定：共享 builder 为每个 case 固定必需 metric 名称和 `plot_data.csv` 列名，并将它们写入 `scientific_artifacts.json`；只有原始输出完整、metric 齐全、绘图列完全匹配时才写 `analysis_ready=true`。其中 rising 的 plot-ready 表直接含 circularity/area/perimeter，stationary 的 metrics 同时含 tau=1 与 tau=2 的速度、形状和两类曲率误差，oscillating 同时保留动力学历程与 a/b/c 拟合、频率误差和等效 Laplace 数。

## 4. 待单独审核的瘦身迁移计划

用户已认可“一次固定、公共内容只保存一次”的方向，但要求先看计划，因此本轮没有移动产物。建议审核通过后再做一次无求解器的结构迁移：

```text
dataset/<formal-name>/
├── _provenance/
│   ├── source_lock.json
│   ├── references/
│   │   └── prosperetti.h
│   └── models/
│       └── baseline_<N>_hgradient/
│           ├── export_manifest.json
│           └── nn_weights.h
├── VOF-HF/
│   └── <case>/...
└── <case>/[caseK/]Nxxxx/imaxNN/<method>/
    ├── manifest.json
    ├── scientific_artifacts.json
    ├── case 原始数据
    ├── metrics.csv
    ├── plot_data.csv
    ├── run.log
    ├── milestones.csv           # stationary
    └── provider_stats.csv       # 仅 NN
```

`plot_data.csv` 作为长期直接画图的数据保留。行内不复制生成脚本；生成逻辑只在仓库的共享 builder 中维护一次，并由 manifest 的 Git/source hash 锁定。

迁移原则：

1. 先让 Claude/用户确认最小文件清单和共享引用方式。
2. 只改产物组织与 manifest 引用，不改求解器、矩阵或科学定义。
3. 迁移工具必须重算哈希并证明科学原始数据逐字节不变。
4. 旧目录在新结构完整验收前不删除。
5. 新结构必须在 `verify_campaign` 全绿后才算迁移完成。

正式发布顺序固定为：需求对齐、N32/N64 smoke 通过、把 smoke 产物交给用户与 Claude 审核、用户明确批准后才提交一个干净完整版本、从该 commit 启动 formal。smoke 完成后不得自动 commit。首次 formal 启动要求 clean worktree；续跑必须保持同一 commit 和 source lock。

smoke 固定覆盖五个 case 分支的 N32 与 N64：20 行 `imax=3` CLSVOF/NN（10 个配对）加 10 行 VOF-HF，共 30 项。stationary smoke 与 formal 一样完整跑到 `tau=2`，必须同时产出精确 `tau=1` 和 `tau=2` 里程碑；不再采用 `tau=0.01` 启动测试。

## 5. 现有 42 行 capwave 数据：只作 smoke/staging 摘要

现场状态：旧 228 行 campaign 中有 42 行存在且 manifest 均为 `completed`，共 21 个完整 CLSVOF/NN 对；没有 `READY.json`。它既不包含新加入的 N32 正式矩阵，也未经用户审核，且当前 generate 源码已改变，因此只能视为历史 smoke/staging，不能与新的 288 行规范续跑混合。

覆盖：N64、N128、N256 的 imax 0--5 全部完成；N512 只完成 imax 0--2。下表是已有 `metrics.csv` 中的 capwave `relative_rms_error`：

| N | imax | role（新口径） | CLSVOF | NN |
|---:|---:|---|---:|---:|
| 64 | 0 | sensitivity | 0.0203397 | 0.0209568 |
| 64 | 1 | sensitivity | 0.00759309 | 0.00750492 |
| 64 | 2 | sensitivity | 0.00715937 | 0.00705089 |
| 64 | 3 | default | 0.00722669 | 0.00710109 |
| 64 | 4 | sensitivity | 0.00736625 | 0.00724236 |
| 64 | 5 | sensitivity | 0.00752609 | 0.0074028 |
| 128 | 0 | sensitivity | 0.00497938 | 0.00491091 |
| 128 | 1 | sensitivity | 0.00200721 | 0.0020478 |
| 128 | 2 | sensitivity | 0.00204258 | 0.00208637 |
| 128 | 3 | default | 0.00205188 | 0.0020996 |
| 128 | 4 | sensitivity | 0.00205587 | 0.00210806 |
| 128 | 5 | sensitivity | 0.00205973 | 0.00211091 |
| 256 | 0 | sensitivity | 0.00139116 | 0.00136695 |
| 256 | 1 | sensitivity | 0.0010873 | 0.00110409 |
| 256 | 2 | sensitivity | 0.00108856 | 0.00110879 |
| 256 | 3 | default | 0.00109024 | 0.00110943 |
| 256 | 4 | sensitivity | 0.00109001 | 0.00111008 |
| 256 | 5 | sensitivity | 0.00109057 | 0.00110904 |
| 512 | 0 | sensitivity | 0.000384541 | 0.000373497 |
| 512 | 1 | sensitivity | 0.000836893 | 0.000836707 |
| 512 | 2 | sensitivity | 0.000836739 | 0.000836668 |

这些数值只说明 smoke/staging 产物可以被读取和汇总；不能替代新规范下的正式行，也不构成方法优劣结论。

## 6. 本轮刻意未做的事情

- 没有运行 canary、formal 或任何求解器。
- 没有把 42 行旧数据补跑、续跑、重写或迁移。
- 没有把 official 塞进 288 行矩阵。
- 没有引入 `tau=2` 后自动续跑逻辑。
- 已按用户确认把 N32 加入全部生成 case；rising N32 对应实际网格 32x8。
- 没有执行第 4 节的目录瘦身；等待审核。

## 7. 请 Claude 重点审核

1. stationary `active_provider_ekmax` 的采样单元是否严格匹配 `integral.h` 的 active diagonal provider 条件，符号是否应与 `+1/R_equiv` 比较。
2. `tau=1` 精确事件与 `tau=2` 终点诊断是否保持 CLSVOF/NN 排程一致；诊断本身不得修改求解场或 provider 统计。
3. `provider_stats.csv` 抽取后，benchmark/runtime 文件是否保持纯科学输出且操作可重复执行。
4. `experiment_role` 是否在 direct runner、campaign manifest 和 scientific contract 三层一致。
5. 第 4 节共享 provenance 方案是否足够简洁，哪些文件仍应保留在行内。
6. VOF-HF 的 observational hosts 是否只增加 circularity、固定时间里程碑和单网格选择，没有改变各 case 的数值方法；四个 case 的 `analysis_ready` 必需指标/绘图列是否足以支持后续三方法同图。
