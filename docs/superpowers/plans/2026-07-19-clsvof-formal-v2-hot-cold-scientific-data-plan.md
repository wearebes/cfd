# CLSVOF formal_v2 热数据集、冷检查点归档与可绘图完备性计划

状态：**DRAFT — 仅供严格审核，尚未实施**  
计划日期：2026-07-19  
适用仓库：`/Users/jcy/research/cfd`  
目标矩阵：180 行主矩阵 + 48 行 oscillating droplet = **228 行**  
绘图后端：Python / matplotlib（除非作者另行指定）

> 本文是 planning-only 合同。本轮只新增本文，不修改运行器、发布器、数据集、图脚本或服务器状态，不删除任何已有文件。

---

## 1. 一句话决策

`formal_v2` 不再把小型 ASCII 科学输出和大型 Basilisk `.dump` 混在逐行发布目录中：

- **热数据层**：保留松散、路径可寻址的小型原始科学输出，供指标重算和图表构建直接读取；
- **冷归档层**：只保存完整状态 `.dump`、恢复索引和必要的运行复现证据，按 `case × resolution` 打包；
- **全局索引层**：用少量全局表管理 228 行身份、指标、文件哈希、运行时间和 checkpoint 实际时刻；
- **图表源层**：继续位于 `figures/<case>/shared_data/`，由热数据可重复生成，不反向成为原始证据。

这个设计同时满足两件事：

1. 当前正式图脚本仍能按路径读取 `wave.dat`、`history.dat`、`interface.dat`、`timeseries.dat` 等小文件；
2. 未来需要新增曲率、压力、速度或界面状态指标时，仍可从冷归档中的 Basilisk dump 恢复，而不是因为策展时只保留最终指标而无法重算。

---

## 2. 对外部审核意见的裁决

### 2.1 应完全吸收的意见

| 审核意见 | 裁决 | 本计划中的处理 |
|---|---|---|
| 数据应按“热/冷”而不是简单按 case 打包 | **接受** | ASCII 热数据保持松散；只有 dump 进入冷包 |
| 正式图表依赖逐 run 的小型原始文件 | **接受** | formal_v2 热层保持稳定路径，不要求绘图前解包 |
| rising `circularity.csv` 在运行时存在、旧 dataset 策展时丢失 | **接受** | 将它列为 96 个 rising 行的强制热数据流和发布 gate |
| 文件数量不是首要科学风险，观测量遗漏才是 | **接受** | 在冻结发布 schema 前先完成逐观测量完备性审计 |
| `checkpoint_index_long` 的核心价值是实际时刻与恢复能力 | **接受** | 强制保存 target、actual、偏差、iteration、状态和 pair eligibility |
| 静态参考与相同模型权重不应逐行复制 | **接受** | 参考数据和模型资产只保存一次，逐行按 ID + SHA256 引用 |

### 2.2 审核中需要修正或收窄的意见

| 外部审核表述 | 仓库事实 | 修正后的结论 |
|---|---|---|
| “现有 `dataset/` 已经是正确发布结构” | 当前 `dataset/` 有 376 个文件、0 个 dump、0 个 rising `circularity.csv`；stationary/oscillating 也不是完整 228 行 v2 | 旧 dataset 的松散路径模式值得保留，但内容不完整，不能原样冻结为 v2 |
| “提案只是在重打包现有 dataset” | 当前 `hpc/lib/dataset_publish.py` 会发布 contract 中所有 `publish:true` 文件，包括 dump、逐行 metrics/plot/index 和两个 JSON | 真正需要修改的是尚未正式运行的 v2 发布器，而不是重打包旧 dataset |
| “final interface 图直接读取逐 run `interface.dat`” | `plot.py` 读取 `shared_data/interfaces_*.csv`；上游 builder 才读取逐 run `interface.dat` | 依赖关系成立，但应准确描述为 `dataset -> builder -> shared_data -> plot` |
| “oscillating 过程图从 dump 编译提取” | `generate_process_source.py` 实际重新编译并短跑 native/NN/VOF-HF，使用 `--snapshots` 生成界面 | 这是独立 visualization rerun，不是 dump 恢复；必须单独策展其输出与 provenance |
| “dataset 完全不需要改，只需归档 dump” | formal_v2 必须新增 circularity、stationary terminal/termination、oscillating fit 链等旧 dataset 没有的流 | 旧 dataset 不动；新增路径兼容但内容更完整的 formal_v2 热层 |

### 2.3 本计划不接受的两个极端

1. **不把全部 228 行、所有 ASCII 和 dump 放入一个或 19 个只能解包后使用的总归档。** 这会破坏图表热路径。
2. **不因为当前论文图暂时不用 dump 就删除 dump。** 用户明确要求未来可以新增指标和状态图；冷归档正是为此保留。

---

## 3. 当前仓库事实基线

### 3.1 已存在且已验证的工作

- `hpc/config/matrix_180.json` 定义 180 行主矩阵；
- oscillating droplet 定义 `levels=[6,7,8,9]`、两种方法、`imax=0..5`，共 48 行；
- 当前 N64/imax=3 smoke 覆盖五个 benchmark identity、两种方法，共 10 行；
- smoke 已生成 44 个 dump，并通过 restore probe；
- rising smoke 已生成 `circularity.csv`，当前四个 rising smoke 行均存在该文件；
- `build_scientific_artifacts.py` 已能生成逐行 metrics、plot data、artifact contract 和 checkpoint 清单；
- 当前发布器保持目标路径不可覆盖，但尚未进行热/冷角色选择，会把 dump 与派生文件全部发布到 formal_v2 叶子。

### 3.2 当前旧 dataset 的边界

- 旧 `dataset/` 是松散、路径寻址的小型数据树；
- 旧 `dataset/` 当前没有 `.dump`；
- 旧 `dataset/rising_bubble/` 当前没有 `circularity.csv`；
- 多个正式图脚本或其 builder 将旧路径写死为 `dataset/<case>/...`；
- 旧数据不能被 v2 原地覆盖，因为 stationary 曲率口径、缺失流和 provenance 已发生变化。

### 3.3 07-15 历史计划的关系

`2026-07-15-clsvof-full-evidence-data-curation-and-publication-figures.md` 已明确标记为“整套图件方案被撤销、仅保留历史记录”。

本文：

- **取代** 07-15 文档中关于新 formal 数据目录、raw/derived 打包和统一图集实施的安排；
- **保留** 其中的证据分级、同 host 配对、方法命名、Python/matplotlib、Source Data 和 QA 原则；
- **不恢复** 已被作者否决的全局总图设计；
- **不自动复制**任何候选图进入 `report/figures/`。

---

## 4. formal_v2 精确矩阵

| benchmark identity | 分辨率 | 方法 | imax | 行数 | checkpoint/行 | dump 上限 |
|---|---|---|---|---:|---:|---:|
| capwave | 64, 128, 256, 512 | native + NN cell-offset | 0–5 | 48 | 5 | 240 |
| rising Case 1 | 64, 128, 256, 512 | native + NN cell-offset | 0–5 | 48 | 4 | 192 |
| rising Case 2 | 64, 128, 256, 512 | native + NN cell-offset | 0–5 | 48 | 4 | 192 |
| stationary bubble | 64, 128, 256 | native + NN cell-offset | 0–5 | 36 | 最多 5 | 最多 180 |
| oscillating droplet | 64, 128, 256, 512 | native + NN cell-offset | 0–5 | 48 | 6 | 288 |
| **总计** | | | | **228** | | **最多 1,092** |

禁止项：stationary bubble N512 不属于 formal_v2。

方法 ID 冻结为：

```text
clsvof
nn
```

NN 行必须同时记录：

```text
model_id
model_resolution
checkpoint_sha256
export_manifest_sha256
weights_header_sha256
```

主矩阵 scheduler 可以继续保持 180 行；oscillating 48 行可以由其 case-local runner 执行。二者必须在数据层通过一个 228 行全局 matrix contract 汇合，不强迫为了“一个 scheduler”而重写已验证的运行路径。

`hpc/config/matrix_v2_228.yaml` 是实施时的可执行源合同；`dataset/formal_v2/matrix_contract_228.yaml` 是发布时冻结的字节相同快照。两者 SHA256 必须一致，这一份受控快照不算科学数据重复。

---

## 5. 五层数据模型

### L0：运行工作层（row-isolated，非发布）

位置示例：

```text
hpc/results/<matrix_id>/<benchmark>/N####/imax##/<method>/
```

允许包含：源码副本、生成头、编译日志、可执行文件、原始 stdout/stderr、逐行 metrics/plot/index、dump、manifest 和临时 QA 文件。

用途：运行、失败定位、逐行验收。文件可以多，但不得在验收前自动删除。

### L1：热科学数据层（公开、松散、路径可寻址）

位置保持 case-centered：

```text
dataset/capwave/formal_v2/
dataset/rising_bubble/formal_v2/
dataset/stationary_bubble/formal_v2/
dataset/oscillating_droplet/formal_v2/
```

只包含：

- 运行产生且未来重算/绘图需要的小型原始 ASCII/CSV；
- 不包含 dump；
- 不包含逐行 `metrics.csv`、`plot_data.csv`、`checkpoint_index.csv`；
- 不包含逐行 `scientific_artifacts.json` 与 `manifest.json`；
- 不逐行复制静态参考文件或模型权重。

### L2：冷恢复归档层（公开或独立交付、压缩）

位置：

```text
dataset/formal_v2/checkpoints/
```

只包含：

- Basilisk `.dump`；
- 每个归档包一个 `bundle_manifest.json`；
- 必要的恢复 schema 和成员 SHA256；
- 不包含热 ASCII 的第二份副本。

归档粒度为 `case × resolution`，共 19 个包：capwave 4、rising Case 1 4、rising Case 2 4、stationary 3、oscillating 4。

默认格式使用 `.tar.gz`，因为当前环境已实测 gzip 压缩并具有最大可移植性。若实施前决定改为 `.tar.zst`，必须先将 `zstd` 纳入 bootstrap/preflight，并重新实测压缩与恢复，不得只改后缀。

### L3：全局索引与派生指标层

位置：

```text
dataset/formal_v2/
```

保存少量全局表，不在每行重复：

```text
README.md
schema.yaml
matrix_contract_228.yaml
catalog.csv
run_manifests.jsonl
artifact_inventory.csv
metrics_long.csv
runtime.csv
checkpoint_index_long.csv
archive_catalog.csv
SHA256SUMS
READY.json
```

### L4：图表 Source Data 与图片层

继续使用：

```text
figures/<case>/shared_data/
figures/<case>/<figure_name>/
```

`shared_data` 是可重复生成的图表输入，不是原始数据。图脚本不得把它反向当成 solver 原始证据。

---

## 6. 最终目录合同

```text
dataset/
├── formal_v2/
│   ├── README.md
│   ├── schema.yaml
│   ├── matrix_contract_228.yaml
│   ├── catalog.csv
│   ├── run_manifests.jsonl
│   ├── artifact_inventory.csv
│   ├── metrics_long.csv
│   ├── runtime.csv
│   ├── checkpoint_index_long.csv
│   ├── archive_catalog.csv
│   ├── SHA256SUMS
│   ├── READY.json                         # 全部 gate 通过后最后写入
│   ├── checkpoints/
│   │   ├── capwave/N0064.tar.gz
│   │   ├── capwave/N0128.tar.gz
│   │   ├── ...
│   │   ├── rising_case1/N0064.tar.gz
│   │   ├── rising_case2/N0064.tar.gz
│   │   ├── stationary_bubble/N0064.tar.gz
│   │   └── oscillating_droplet/N0512.tar.gz
│   └── support/
│       └── models.tar.gz
│
├── capwave/
│   ├── reference/                         # static reference, one copy
│   └── formal_v2/N####/imax##/<method>/
│       ├── wave.dat
│       └── official_error.dat
│
├── rising_bubble/
│   ├── case1/reference/
│   ├── case2/reference/
│   └── formal_v2/case#/N####/imax##/<method>/
│       ├── history.dat
│       ├── interface.dat
│       └── circularity.csv
│
├── stationary_bubble/
│   ├── reference/
│   └── formal_v2/N####/imax##/<method>/
│       ├── timeseries.dat
│       ├── runtime_and_terminal.log
│       ├── official_terminal.dat
│       └── termination.csv
│
└── oscillating_droplet/
    ├── reference/
    ├── formal_v2/N####/imax##/<method>/
    │   ├── timeseries.dat
    │   ├── fit_curve.dat
    │   ├── fit.log
    │   ├── error.dat
    │   ├── laplace.dat
    │   └── fit_summary.dat
    └── process_snapshots/                 # 独立 visualization evidence，不算入228行
        └── N0128/imax03/
            ├── process_contours.csv
            ├── snapshot_times.csv
            └── provenance.json
```

旧 `dataset/<case>/N####/...` 路径保持原样，既不覆盖，也不偷偷改成 v2。

---

## 7. 为什么不把所有热数据再合并成五个大 CSV

全局大表适合指标，不适合替代所有原始流：

- `interface.dat` 是分段几何，不同 run 行数不同；
- `fit.log` 包含 gnuplot 拟合报告，不能无损塞进普通数值长表；
- `history.dat`、`wave.dat` 和 `timeseries.dat` 的 schema 不同；
- 当前 figure builders 已经按 run 路径读取原始文件；
- 将所有原始流复制进全局 CSV 反而制造第二份数值数据。

因此：

- 小型原始流保持每行松散；
- `catalog.csv` 提供统一定位；
- `metrics_long.csv` 只保存低体积派生指标；
- figure-specific 组合表只存在 `figures/*/shared_data/`，可以随时重建。

按当前合同，热层预计约 816 个逐行原始文件，而不是 3,096 个含 dump/辅助 JSON 的散文件。每个叶子只有 2–6 个文件，配合 228 行 `catalog.csv` 管理；冷层只暴露 19 个主要归档包。

---

## 8. 文件角色与去重合同

| 当前角色 | 工作层 | 热层 | 冷层 | 全局表 | 去重规则 |
|---|---:|---:|---:|---:|---|
| `official_raw` | 保留 | 保留 | 不复制 | 仅登记路径/hash | 每行唯一 |
| `extension_raw` | 保留 | 保留 | 不复制 | 仅登记路径/hash | circularity/termination 必须发布 |
| `official_reference` | 保留 | case reference 一份 | 不再复制 | hash 引用 | 禁止逐行或跨层复制 |
| `derived_metrics` | 保留验收副本 | 不逐行发布 | 不发布 | `metrics_long.csv` | 全局一份 |
| `derived_plot` | 保留 QA 副本 | 不逐行发布 | 不发布 | figure shared_data 按需生成 | 不作为 canonical 数据 |
| `checkpoint_index` | 保留 | 不逐行发布 | 包内 manifest | `checkpoint_index_long.csv` | 全局一份 + 包内必要索引 |
| `checkpoint` | 保留 | 禁止 | 归档 | 仅登记 | dump 不做跨行内容去重 |
| run manifest | 保留 | 不逐行发布 | bundle manifest | `catalog.csv` + `run_manifests.jsonl` | 可查询身份与无损 provenance 分开保存 |
| artifact contract | 保留 | 不逐行发布 | bundle manifest | `artifact_inventory.csv` | 文件粒度聚合 |
| NN weights | 工作层按需 | 不逐行复制 | support 一份/模型 | model ID + hash | 每模型分辨率一份 |

检查和重算用的重复允许存在于 L0；L1/L2/L3 正式发布不保留无意义副本。

---

## 9. 全局表 schema

### 9.1 `catalog.csv`：一行一个 solver row

主键：`row_id`

必需字段：

```text
row_id, case, subcase, benchmark, method, resolution, actual_grid,
imax, model_id, model_resolution, checkpoint_sha256,
purpose, host_id, matrix_id, hot_path, archive_id,
actual_terminal_time, termination_reason,
official_coverage_complete, extension_coverage_complete,
checkpoint_coverage_status, pair_id, manifest_sha256, publish_status
```

必须恰好 228 行、228 个唯一 row ID、114 个 native/NN pair。

### 9.2 `run_manifests.jsonl`：一行一个完整运行 manifest

`catalog.csv` 只保留稳定、可查询的公共字段，不能承载不同 case 的所有嵌套 provenance。`run_manifests.jsonl` 按 `row_id` 排序，每行保存：

```text
{"row_id": "...", "manifest": {...原逐行 manifest 的完整内容...}}
```

约束：

- 恰好 228 个 JSON object；
- `row_id` 唯一并与 catalog 一一对应；
- catalog 中 `manifest_sha256` 必须匹配规范化前的原逐行 manifest 文件；
- 任何 case-specific nested field 不得因为转成 CSV 而丢失；
- 这是 query catalog 与 lossless provenance 之间唯一允许的身份字段重复。

### 9.3 `artifact_inventory.csv`：一行一个热文件或冷包成员

主键：`owner_kind + owner_id + tier + logical_name`

```text
owner_kind, owner_id, row_id, tier, artifact_role, logical_name, path_or_member,
bytes, sha256, schema_id, required, source_runtime_path
```

普通实验文件使用 `owner_kind=row`、`owner_id=row_id`；共享模型或静态支持资产使用 `owner_kind=support`、`owner_id=model_id/reference_id`，不伪造 row ID。

它取代 formal_v2 叶子中的 228 份 `scientific_artifacts.json`。

### 9.4 `metrics_long.csv`：一行一个指标值

```text
row_id, case, subcase, method, resolution, imax,
model_id, model_resolution,
metric, value, unit, scope, time,
definition_id, definition, source_artifact, source_sha256, origin
```

约束：

- `definition_id` 与单位组合不可在不同 case 中静默改变；
- 官方值与重算值使用不同 metric ID；
- percent 与 dimensionless ratio 使用不同 metric ID 和单位；
- stationary 修正前的错误 `ekmax` 不得进入 v2；
- 同一 row/metric/scope/time 不得重复。

### 9.5 `checkpoint_index_long.csv`

```text
row_id, pair_id, label, coordinate_name,
target_coordinate, target_time,
actual_coordinate, actual_time,
coordinate_error, time_error, iteration,
status, reason, archive_id, archive_member,
restore_status, restored_time, restored_iteration,
paired_actual_time_delta, field_comparison_eligible
```

该表既服务恢复，也明确未来状态图能否进行严格配对。

### 9.6 `archive_catalog.csv`

```text
archive_id, case, subcase, resolution, format,
rows_expected, rows_present, members, bytes_raw, bytes_archive,
sha256, manifest_member, restore_checks, status
```

---

## 10. 逐观测量完备性合同

发布 gate 不再只问“这个 case 的官方文件齐不齐”，而要问“计划使用或未来合理需要的每个观测量有没有保存”。

建立机器可读 `observable_registry.yaml`，每项至少包含：

```text
observable_id
case
source_artifact
columns
units
sampling_rule
tier
required_rows
derivation
paired_comparison_rule
known_figure_consumers
future_use
```

### 10.1 初始 registry

| Case | 观测量 | 来源 | 采样 | tier | 强制覆盖 |
|---|---|---|---|---|---|
| Capwave | amplitude history | `wave.dat` | 官方每个输出样本 | hot | 48/48 |
| Capwave | official relative RMS | `official_error.dat` | terminal/global | hot | 48/48 |
| Rising 1/2 | volume, center, velocity, dt | `history.dat` | solver history | hot | 96/96 |
| Rising 1/2 | terminal interface facets | `interface.dat` | t=3 | hot | 96/96 |
| Rising 1/2 | numerical circularity history | `circularity.csv` | 每个记录迭代，覆盖 0–3 | hot | **96/96** |
| Stationary | `u_star`, `delta_fraction` | `timeseries.dat` | 每个记录迭代 | hot | 36/36 |
| Stationary | shape errors + `ekmax` | `official_terminal.dat` | 实际终止时刻 | hot | 36/36 |
| Stationary | termination reason/time | `termination.csv` | terminal | hot | 36/36 |
| Oscillating | kinetic energy history | `timeseries.dat` | 官方 trace | hot | 48/48 |
| Oscillating | fit curve/log/error/laplace | 六件官方链 | global/fit | hot | 48/48 |
| All | full-state checkpoint | `.dump` | case-specific targets | cold | 按合法策略 |

### 10.2 rising circularity 强 gate

每个 rising 行必须满足：

- `circularity.csv` 存在且非空；
- 列为 `time,iteration,half_area,half_perimeter,circularity`；
- time 单调递增；
- 覆盖 t=0 到 t=3；
- circularity 全部有限且大于 0；
- t=0 面积、圆度通过 canary 物理检查；
- final circularity 与 `interface.dat + history.dat` 独立重算在预冻结容差内一致。

任何一行缺失都阻止 rising formal_v2 发布，不能再退化成“只有 t=3 一个圆度点”。

### 10.3 stationary 提前终止

- 终止时刻必须记录实际 `tau`；
- `tau=0,0.01,0.1,0.5,terminal` 为目标，不是保证全部到达；
- 只有 `termination.csv` 明确记录科学性提前收敛时，未到达 checkpoint 才合法；
- 合法缺失写入 `status=not_reached` 和具体 reason；
- terminal 指标的 `time` 必须是实际终止时刻；
- 不允许用名义 `tau_max` 伪装实际终止时间。

### 10.4 oscillating 周期定义

formal checkpoint 周期明确为动能周期：

```text
T_KE = pi / omega0
cycles = [0, 5, 10, 15, 20, terminal]
```

不得解释成形状周期 `2*pi/omega0`，否则 15/20 周期会超出 t=1。

### 10.5 任意时间状态图的真实能力边界

- 标量过程图：可在实际记录时间点绘制，并可按科学规则插值；
- 全场状态图：只能直接使用已保存 checkpoint 的实际时刻；
- 用户后来指定任意 `t=n` 时，先查 `checkpoint_index_long.csv`；
- 若没有足够接近的 checkpoint，只能从较早 dump 恢复并重新积分，不能声称已有精确状态；
- 本计划不保存每个 timestep 的 full field，因为那会把规模推到数百 GB 甚至更高。

---

## 11. checkpoint 时刻、非扰动与配对规则

formal run 的 checkpoint 采用“现有时间步首次越过目标后写出”的非强制策略，避免显式时间事件改变 dt 序列和科学文本。

每个 checkpoint 必须记录：

- target coordinate/time；
- actual coordinate/time；
- 偏差；
- iteration；
- terminal/early-stop reason；
- native/NN 对应 checkpoint 的实际时间差。

在 N64 canary 前冻结每个 case 的 `field_comparison_eligible` 容差。不得在看到完整结果后为通过而放宽。

如果 formal run 的实际时间差不满足容差：

- dump 仍保留，可用于单方法状态图或非严格描述；
- 该 pair 的严格同时间场比较标为不合格；
- 需要严格相位图时，另做 output-instrumented visualization rerun，并将它标为独立 evidence，不混入 228 行定量主结果。

t=0 dump 必须在由距离函数初始化体积分数/界面以后写出，禁止保存未初始化状态。

---

## 12. oscillating 过程图的独立证据合同

当前 `n128_process_three_method/generate_process_source.py` 会现场重新编译并短跑三种方法；它不是从 formal dump 离线提取。

正式化方式：

1. 保持该短跑与 228 行 formal matrix 分离；
2. 冻结 N128、imax=3、五个形状相位目标和三方法身份；
3. 将 `process_contours.csv`、`snapshot_times.csv`、commands、source hashes 和环境信息发布到 `dataset/oscillating_droplet/process_snapshots/`；
4. 图脚本只读取已策展 source，不在普通 `plot.py` 中重新运行求解器；
5. 重新生成 source 的命令单独保留，并进行 deterministic/hash QA；
6. 该 evidence 不增加 228 行的样本数，也不用于冒充 full t=1 定量 trace。

---

## 13. 发布器改造设计

### 13.1 需要修改的文件

```text
cases/_shared/build_scientific_artifacts.py
hpc/lib/dataset_publish.py
hpc/verify_matrix.py
hpc/tests/test_dataset_publish.py
cases/_shared/audit_scientific_smokes.py
```

新增：

```text
cases/_shared/audit_dataset_completeness.py
cases/_shared/observable_registry.yaml
hpc/config/matrix_v2_228.yaml
hpc/tests/test_dataset_completeness.py
hpc/tests/test_cold_archive.py
```

oscillating 的 48 行发布适配器必须显式列入实施，不允许只改 180 行 `verify_matrix.py` 后声称完成 228 行。

当前 `hpc/verify_matrix.py` 写 `dataset/runtime_v2.csv`；实施后 canonical 路径改为 `dataset/formal_v2/runtime.csv`，并同步更新 case summaries 和所有消费者。由于完整 formal_v2 尚未发布，不同时维护两份 runtime CSV；如果审核发现已有外部消费者，再增加显式迁移工具，而不是静默双写。

### 13.2 artifact contract schema v2

将当前单一 `publish: true/false` 改成明确 tier：

```text
publish_tier: hot | cold | aggregate_only | support | work_only
```

每个 artifact 必须有：

```text
logical_name
role
publish_tier
source_path
publish_path_or_member
bytes
sha256
schema_id
required
```

schema v1 smoke 继续可读，但 formal_v2 只接受 schema v2；不要让 `hpc/lib/scheduler.py` 的 thread-policy schema 与 artifact schema 混为同一个版本概念。

### 13.3 事务发布

发布分三段：

1. 在 staging 构建 hot row 与全局表候选；
2. 在 staging 构建冷 archive、成员 manifest 和 archive SHA；
3. 完成文件集合、hash、restore、coverage、pair 和 figure-source canary 后，再原子发布。

由于热层分布在四个 case root，不能假装一次 `rename()` 可以原子替换整个 dataset。实施采用：

- 每个 case 的完整 `formal_v2` 先在同一父目录 staging，整 case 验收后原子 rename；
- 全局 catalog/archives 在 `dataset/formal_v2/.staging` 完成后原子发布；
- `dataset/formal_v2/READY.json` 是最后一个写入的完成标记，包含 228 行 catalog hash、19 个 archive hash 和四个 case root hash；
- figure builders 默认拒绝没有 READY 标记或 READY hash 不匹配的 formal_v2；
- case summaries 只有在 READY 写入后才从 `populated_only_after_full_v2_rerun` 更新为 ready。

规则：

- 已存在相同路径且 hash 完全相同：可复用；
- 已存在相同路径但 hash 不同：拒绝覆盖；
- legacy 与 formal_v2 跨版本内容相同：允许，不做跨版本全局 hash 拒绝；
- formal_v2 内部同一 logical identity 不得有两个 canonical source；
- 发布器不得删除整个目标 case 或 dataset 根；
- 不允许一行失败后留下“看似完整”的半发布目录。

`READY.json` 中的 case root hash 定义为：按相对路径排序后，对每个正式热文件写入 `path + NUL + sha256 + LF`，再对该规范字节流计算 SHA256。禁止使用依赖文件系统遍历顺序的“目录 hash”。

### 13.4 冷归档确定性合同

19 个 `.tar.gz` 必须可重复构建：

- archive member 按路径字典序；
- 禁止绝对路径、`..`、symlink 和 device member；
- tar uid/gid、uname/gname、mode 和 mtime 规范化；
- gzip header 不携带本机文件名，mtime 固定；
- `bundle_manifest.json` 在打包前生成并列出所有成员 hash/bytes；
- 同一 staging 连续构建两次必须得到相同 archive SHA256；
- 解包到临时目录后逐成员复核，再运行 restore probe；
- archive SHA 写入 `archive_catalog.csv` 和顶层 `SHA256SUMS`。

---

## 14. 图表兼容改造

### 14.1 统一原则

所有 dataset-backed builder 增加显式 `--dataset-root` 或等价参数，并在 QA 中记录解析后的绝对/仓库相对路径与源 hash。

默认不得静默混用 legacy 与 formal_v2。

### 14.2 Capwave

- 保留读取 loose `wave.dat` 的方式；
- 将 hardcoded `dataset/capwave` 改为参数化 root；
- Prosperetti/reference 从 case reference 单一位置读取；
- builder/plot QA 标记 dataset generation 为 legacy 或 formal_v2。

### 14.3 Rising bubble

- `build_source_data_from_dataset.py` 增加 formal_v2 circularity 读取；
- v2 模式下 `numerical_circularity_history_available` 必须为 true；
- legacy 模式可继续报告 unavailable，但不得将其结果混入 v2 完备性结论；
- interface 图仍通过 builder 从逐 run `interface.dat` 生成 shared_data；
- formal_v2 必须能生成 numerical circularity minimum、time-at-minimum 和 circularity RMSE。

### 14.4 Stationary bubble

- 补齐从 formal_v2 热层重建 `shared_data/imax_metrics.csv` 的单一 builder；
- 所有 terminal 指标按实际终止时刻解释；
- 不把不同终止时间的 `Ca(tau)` 末端值伪装成固定 tau 对比；
- 需要固定 tau 的图必须只纳入覆盖该 tau 的行并报告 coverage。

### 14.5 Oscillating droplet

- 定量 trace 图参数化读取 formal_v2 `timeseries.dat`；
- fit/频率/阻尼指标来自 formal_v2 六件官方链；
- process contour 图读取独立策展的 `process_contours.csv`，普通绘图不触发 qcc/solver；
- negative damping 明确保留符号，不用平方派生量掩盖。

---

## 15. 数据量与文件数预算

基于当前 N64 smoke 的真实 dump 大小和 N² 外推：

| 层 | 预计规模 | 文件管理方式 |
|---|---:|---|
| 热 ASCII + 全局表 | 约 0.2–0.8 GiB | 约 816 个逐行科学文件 + 少量全局文件 |
| 冷 dump 未压缩 | 约 3.50 GiB | 归档前最多 1,092 个 dump |
| 冷 dump gzip 实测外推 | 约 1.6–2.0 GiB | 19 个 checkpoint archive |
| 最终压缩交付总量 | 约 1.8–2.8 GiB | 热树 + 19 包 + support |
| 运行/验收/打包临时空间 | 建议至少 20 GiB | 验收前不删除 staging |

当前 smoke dump gzip-6 实测为 11,914,868 bytes -> 5,464,574 bytes，压缩后约 45.9%。完整矩阵仍需在 N64 formal canary 后重新外推；以上是预算，不是已经产生的数据量。

---

## 16. 实施阶段与硬 gate

### Gate 0：严格审核与范围冻结

- [ ] Claude/作者确认热/冷分层；
- [ ] 确认 228 行矩阵与 19 个冷包；
- [ ] 确认旧 dataset 不覆盖、不删除；
- [ ] 确认 observable registry 字段和每 case 强制流；
- [ ] 确认 07-15 历史计划不再作为实施入口；
- [ ] 未通过前不改发布器，不跑 formal matrix。

### Gate 1：只读完备性审计

实现 `audit_dataset_completeness.py`，对比：

```text
runtime outputs
artifact contract
publisher selection
hot dataset
cold archive
figure consumers
```

输出：

```text
completeness_by_row.csv
completeness_by_observable.csv
consumer_dependency.csv
leakage_report.csv
audit.json
audit.md
```

验收：

- [ ] 当前 legacy dataset 的 circularity 缺失被准确报告；
- [ ] 当前 10 行 smoke 的 circularity/checkpoint/official outputs 被准确识别；
- [ ] 不把 `checkpoints/` 当作 method 或 row；
- [ ] stationary 合法未到达不被报成采集失败；
- [ ] oscillating process rerun 被分类为独立 evidence。

### Gate 2：schema v2 与 publisher 单元测试

- [ ] hot/cold/aggregate/support/work_only 分类测试；
- [ ] rising circularity 不可被 publisher 丢弃；
- [ ] hot 层拒绝 `.dump`；
- [ ] cold archive 拒绝热 ASCII 重复副本；
- [ ] static reference/weights 去重；
- [ ] 同路径相同 hash 可复用，不同 hash 拒绝；
- [ ] legacy/formal_v2 跨版本同 hash 允许；
- [ ] archive 路径穿越和绝对成员名拒绝；
- [ ] 228 行 catalog primary key 唯一；
- [ ] 19 个 archive identity 唯一。

### Gate 3：本地/当前环境 10 行 smoke 重验

- [ ] 十行 artifact schema v2 通过；
- [ ] 所有 hot 流可读取；
- [ ] 44 个现有 dump 可恢复；
- [ ] metrics_long 与逐行重算一致；
- [ ] 两个 JSON 的信息成功汇入 catalog/artifact inventory；
- [ ] QA-only `plot_data.csv` 不进入 hot 发布；
- [ ] cold 包可解包并恢复成员。

### Gate 4：Ubuntu 服务器 preflight

必须检查：

- qcc/GCC；
- gnuplot 实际 fit smoke（当前 bootstrap/preflight 已包含，仍需服务器实测）；
- CPU/NUMA/threads policy；
- 模型 checkpoint/header/hash；
- 磁盘余量；
- gzip/tar；
- 同服务器 dump restore probe；
- t=0 初始化顺序；
- scientific text 的 checkpoint instrumentation 非扰动性。

### Gate 5：N64 formal canary（60 行）

先完成所有 case、两种方法、imax 0–5 的 N64：

- [ ] 60/60 row complete；
- [ ] 30/30 method pair complete；
- [ ] rising circularity 24/24；
- [ ] checkpoint 实际时刻偏差分布冻结；
- [ ] pair field comparison tolerance 冻结；
- [ ] stationary early-stop policy 实证通过；
- [ ] cold archive 大小和压缩率重新估算；
- [ ] formal_v2 hot 数据可重建代表性 figure shared_data；
- [ ] 没有官方流从 runtime 到 hot 策展过程中丢失。

若 N64 gate 失败，不启动 N128/N256/N512。

### Gate 6：完整 228 行运行

- 主矩阵 180 行按现有 row-isolated scheduler；
- oscillating 48 行按 case-local row-isolated runner；
- 服务器并发通过显式 jobs/CPU policy 控制；
- 不以修改科学参数换取运行速度；
- 不在 formal run 中混入 probe-only 或 crossover 行。

### Gate 7：完整发布与恢复验收

- [ ] catalog 228 行；
- [ ] `run_manifests.jsonl` 228 个唯一对象且与 catalog hash 一致；
- [ ] 114 对 native/NN；
- [ ] stationary 无 N512；
- [ ] hot artifact coverage 100%；
- [ ] rising circularity 96/96；
- [ ] 19 个 archive 完整；
- [ ] 所有 written dump 都在产出服务器 restore 成功；
- [ ] 所有 archive 和 hot 文件通过 SHA256；
- [ ] checkpoint 合法缺失只来自记录明确的 stationary early termination；
- [ ] `metrics_long` 单位、定义、来源和 model checkpoint 完整；
- [ ] stationary 修正后的 official metrics 通过 canary，不复用旧错误值；
- [ ] 不增加 N128 `spurious.ref` exact-match 之类已知不稳健的外部 gate。
- [ ] `READY.json` 最后写入且其引用的 catalog/case/archive hash 全部匹配。

### Gate 8：图表数据再生验收

从 formal_v2 hot 层重建现有需要保留的 figure source：

- [ ] capwave wave/RMS 图；
- [ ] rising dynamics/circularity/final interface；
- [ ] stationary metric sweeps/参考比较；
- [ ] oscillating trace/fit 指标；
- [ ] oscillating process contour 使用独立策展 source；
- [ ] 每个 figure source 记录上游 path + SHA256；
- [ ] 不要求解包 dump 才能重画普通时间历程或终态界面图；
- [ ] 需要 full field 的新图明确走冷 archive extractor。

### Gate 9：交付与清理

只有 Gate 7–8 全部通过后：

- 生成最终 SHA256SUMS；
- 冻结 README/schema/版本；
- 保留 legacy dataset；
- 将运行 staging 标记为可清理候选；
- 任何实际删除另行列清单并获得作者确认；
- 不在本计划实施中自动删除用户未提交或历史结果。

---

## 17. 预期测试与命令合同

下面是实施后应存在的命令形态；当前文档阶段不运行不存在的脚本。

```bash
python3 -m pytest -q \
  hpc/tests/test_dataset_publish.py \
  hpc/tests/test_dataset_completeness.py \
  hpc/tests/test_cold_archive.py

python3 cases/_shared/audit_dataset_completeness.py \
  --matrix-contract hpc/config/matrix_v2_228.yaml \
  --runtime-root <validated-results-root> \
  --dataset-root dataset \
  --output <audit-output>

python3 cases/_shared/audit_scientific_smokes.py \
  tem/scientific_artifact_smoke_20260717
```

每个 figure builder 的 v2 调用必须显式给出 dataset root，例如：

```bash
python3 figures/rising_bubble/build_source_data_from_dataset.py \
  --dataset-root dataset/rising_bubble/formal_v2 \
  --output-dir figures/rising_bubble/shared_data
```

若实际 CLI 与此不同，实施者必须同步更新本文和测试，不得留下不可执行的验收命令。

---

## 18. 停止条件

遇到以下任一情况立即停止扩大运行：

1. runtime 有科学流但 publisher 未登记；
2. rising 任一行没有完整 circularity history；
3. stationary phase/reference 修正未在 canary 通过；
4. official metric 与独立重算差异超过预冻结容差；
5. dump restore 失败或 restored time/iteration 与索引不一致；
6. native/NN model checkpoint 身份混淆；
7. figure builder 无法仅从指定 v2 热数据生成 source；
8. checkpoint instrumentation 改变非 performance 科学文本；
9. gnuplot fit 链在服务器缺失或静默不产物；
10. 磁盘空间不足以同时保留 staging、archive 和验证副本；
11. 发布需要覆盖或删除 legacy 数据；
12. 工作树中用户既有修改与待改文件发生不可安全绕开的冲突。

停止后只报告证据和阻塞，不通过放宽指标、删除原始流或替换实验身份来“让 gate 通过”。

---

## 19. 明确非目标

- 不保存每个 solver timestep 的 full field；
- 不把 `imax=0..5` 当统计重复；
- 不把 smoke、probe、crossover、visualization rerun 混入 228 行；
- 不重新设计被作者否决的全局论文图；
- 不宣称 NN 必然优于 native；
- 不把旧错误 stationary ekmax 修成一个只存在于表格里的离线数字；
- 不为了减少文件数而牺牲原始输出、图表可重建性或 Basilisk restore；
- 不在作者确认前删除 staging、legacy dataset、下载包或模型资产。

---

## 20. 最终完成定义

只有同时满足以下条件，才能称 formal_v2 数据工作完成：

1. 228 行身份、方法、分辨率、imax 和模型 checkpoint 完整；
2. 每个 case 的官方与扩展观测量覆盖通过机器审计；
3. rising circularity 不再在策展阶段丢失；
4. 小型热数据可按稳定路径直接重算指标和生成 figure source；
5. 最多 1,092 个 dump 被压缩为 19 个冷包并全部通过成员 hash/restore 验收；
6. 全局 catalog、run manifests、metrics、runtime、artifact、checkpoint 和 archive 表均可追溯到原始文件；
7. 旧 dataset 保持不变，formal_v2 不混入 legacy；
8. 普通过程图不依赖解包 dump，full-field 新图有明确 cold-extract 路径；
9. oscillating process contour 的独立短跑证据已经策展，不再由普通 plot 命令隐式重跑；
10. 数据、脚本、schema、README、SHA256 和验收报告形成闭环。

完成定义强调的是**可重算、可比较、可绘图、可恢复和不遗漏**，而不是单纯把文件数量压到最少。
