# CLSVOF 全证据数据整理与顶刊级总图实施计划

状态：**已撤销图件实施；2026-07-15 按作者要求删除整套总图/案例图及 report 副本，改为从单张 capwave 图重新迭代**  
计划日期：2026-07-15  
适用仓库：`/Users/jcy/research/cfd`  
绘图后端：**Python / matplotlib only**  

> 本文档最初作为 planning-only 合同编写，随后实施；但该整套图件方案已被作者明确否决并清理。本文档仅保留为历史决策记录，不再代表当前绘图任务。当前任务只制作一张 capwave `grid × imax` 图。

> 数据布局更新（2026-07-16）：当前入口为精简公共原始数据集 `dataset/`。顶层只有四个 case 和 `runtime.csv`；正式数值产物按 case/resolution/imax/method 放置，参考数值放在各 case 的 `reference/`，分析与运行记录均留在 dataset 外。

保留结果：180 行 `raw/`、派生分析与 SHA 校验记录继续保留。已删除 `figures/clsvof_cell_offset_global/`、对应 `report/figures/` 副本及相关 Python 缓存。

---

## 1. 目标与最终交付

本计划不是只给新下载的 180 行矩阵画一张图，而是建立一个可审计的**全仓证据总览**：

1. 将下载目录中的正式结果包安全复制到项目 `dataset/`，保留原包和双层 SHA-256 证据；
2. 将新 180 行正式矩阵与仓库已有的官方基准、文献参考、oscillating-droplet 正式/因果数据统一登记；
3. 严格区分正式主证据、外部参考、独立复现、diagnostic/smoke 和 audit-only 数据；
4. 生成一套统一的、可复算的 analysis-ready CSV；
5. 先完成一张能够承载论文核心结论的**全局总图**，再完成各 case 的细节图与补充图；
6. 为每张图同时交付绘图脚本、Source Data、600-dpi PNG 和 QA 记录；默认禁止生成 PDF、SVG、TIFF，除非用户明确点名追加某一种格式；
7. 候选图保留在 `figures/`，只有作者明确选中的图才进入 `report/figures/`。

完成后的主要产物应为：

```text
dataset/clsvof_vs_nn_imax_0_5/
figures/clsvof_cell_offset_global/
report/figures/                                  # 仅作者选择后写入
```

---

## 2. 当前已核实事实与尚未核实边界

### 2.1 下载包实物

输入文件：

```text
/Users/jcy/Downloads/cfd_hpc_180_formal_180_epyc9654_32c_pack4_001.tar.gz
/Users/jcy/Downloads/cfd_hpc_180_formal_180_epyc9654_32c_pack4_001.tar.gz.sha256
```

当前只读核查结果：

| 项目 | 当前证据 |
| --- | --- |
| 外层 SHA-256 | `51b0d95a2c38d9b5ecc4a7bbf5703b2af7bfeb57ea8297d79526c4b83d8188b6`，本机复核 `OK` |
| 压缩包大小 | 约 67 MB |
| 解压后文件总量 | 约 286.67 MiB |
| tar 条目 | 2,866 |
| 包内 SHA256SUMS 记录 | 2,537 条 |
| matrix ID | `formal_180_epyc9654_32c_pack4_001` |
| 完成度 | `180/180` |
| invalid rows | `0` |
| pair failures | `0` |
| failure ledger | 只有表头，无失败记录 |

180 行矩阵的精确构成为：

| benchmark | 分辨率 | `imax` | 方法 | 行数 |
| --- | --- | --- | --- | ---: |
| capwave | 64, 128, 256, 512 | 0–5 | native + NN cell-offset | 48 |
| rising Case 1 | 64, 128, 256, 512 | 0–5 | native + NN cell-offset | 48 |
| rising Case 2 | 64, 128, 256, 512 | 0–5 | native + NN cell-offset | 48 |
| stationary bubble | 64, 128, 256 | 0–5 | native + NN cell-offset | 36 |
| **总计** |  |  |  | **180** |

这等价于 **90 组同 host、同 benchmark、同分辨率、同 `imax` 的 native/NN 配对**。

### 2.2 尚未声称完成的事项

以下工作必须留到 goal 实施阶段，不能由外层压缩包校验替代：

- 包内 2,537 条 `SHA256SUMS` 尚未在解压目录逐条复核；
- 180 行虽通过运行完整性 gate，但尚未完成统一的科学指标重算和跨 case 审计；
- 尚未确认所有 NN 行的 provider health 字段能否从相同位置解析；
- 尚未形成可用于论文的最终科学结论；
- 尚未验证新图的视觉、字体、可编辑文本和最终版面尺寸。

因此，当前只能说“运行与打包完整”，不能提前说“NN 全面优于 native”或“结果已可直接投稿”。

---

## 3. 冻结的组织原则

### 3.1 正式数据按科学身份命名

canonical dataset 使用：

```text
dataset/clsvof_vs_nn_imax_0_5/
```

不使用下载日期或新的时间戳作为正式数据身份。原始 tar 文件名保留不变，只作为来源 provenance。

### 3.2 原始证据、派生数据和图片严格分层

- `archive/`：原始 tar.gz 与外层 `.sha256`，只读来源；
- `raw/`：原样解出的 180 行结果与包内 `SHA256SUMS`；
- `derived/`：由受测脚本重算的 analysis-ready 表；
- `figures/`：图脚本、图级 Source Data、候选图片和 QA；
- `report/figures/`：作者人工选择的论文图。

绘图脚本不得直接修改 `raw/`，也不得把从图上人工读数当成数据源。

### 3.3 一个正式数据集只保留一个描述入口

dataset 根目录只建立一个描述文件 `summary.yaml`。其他 JSON/CSV 是机器可读证据或分析结果，不再为每个子目录增加 README。

### 3.4 不移动现有数据来制造“整齐”

第一轮只新增 canonical 新数据集，并在 case `summary.yaml` 中登记路径。现有官方数据和 oscillating-droplet 结果继续留在当前位置，避免破坏已有路径和未提交工作。

### 3.5 不自动晋级 `report/`

脚本运行成功只代表候选图生成。只有完成数值审计、图件 QA、结论核对并经作者选择后，才允许复制到 `report/figures/`。

---

## 4. 全仓证据层级与合并规则

### 4.1 L1：论文主证据

| 数据源 | 角色 | 主图使用方式 |
| --- | --- | --- |
| 新 180 行正式矩阵 | 同 host、成对的 native vs NN cell-offset；`imax=0..5` | 主体；默认 `imax=3` 负责主比较，其他 `imax` 负责敏感性 |
| `dataset/oscillating_droplet/N{0064,0128}/imax03/` | 同 host matched N64/N128；完整 verification 保留在 dataset 外 | 作为第四个物理问题进入全局结论 |
| `dataset/oscillating_droplet/crossover/` | 两个独立 grid × checkpoint 交叉结果 | 用于解释分辨率失效边界，不当作额外重复实验 |

### 4.2 L2：外部/官方参考

| 数据源 | 角色 | 限制 |
| --- | --- | --- |
| `dataset/capwave/reference/` | official VOF/CLSVOF、Prosperetti、N16–N512 参考 | 可作收敛与时间历程参考，不替代同-host native/NN 因果比较 |
| `dataset/rising_bubble/{case1,case2}/reference/` | CSF default 与 Hysing/MooNMD 时间史和形状 | 作为物理基准；Case 1 与 Case 2 必须分别读取正确参考 |
| `dataset/oscillating_droplet/reference/` | official VOF-HF/Momentum/Compressible 数值序列 | 只作描述性 landscape，不对 NN 做跨 solver 因果归因 |

### 4.3 L3：独立验证或补充证据

| 数据源 | 角色 | 使用位置 |
| --- | --- | --- |
| `experiments/clsvof_kappa_offset_conversion/results/20260710T2359Z` | 早期 cell-offset 独立 solver 验证 | Supplementary reproducibility；不与 180 行合并为 replicate |
| provider guard/clamp、header/weight hash、runtime | 实现完整性与代价 | 补充图或 QA，不抢占主物理结论 |

### 4.4 L4：不得进入正式比较的证据

以下数据只可登记 exclusion reason，不得重复计数或出现在主图图例中：

- 未迁入当前 dataset 的旧 rising direct 方法；
- `experiments/capwave_clsvof_kreplace/` 的历史 direct 结果；
- 已删除/退役的 `q_gamma/Delta` direct-NN 路径；
- `experiments/clsvof_redistance_imax_matrix/results/20260710T172910Z` 中保留的旧 48 行 native：仅用于历史审计，新包是当前 canonical 正式矩阵；
- stationary 的 timestamped smoke、probe、contour analytic 与等价性诊断；
- oscillating-droplet 中明确标为 diagnostic 的 matched-port 数据。

### 4.5 去重合同

建立 `derived/evidence_registry.csv`，每项至少包含：

```text
dataset_id, case_id, host, method_id, resolution, imax,
evidence_level, include_main, include_supplement,
superseded_by, exclusion_reason, source_path, source_sha256
```

同一科学行只允许有一个 canonical source。旧数据即使数值相同也不能作为额外 `n`。

---

## 5. 目标目录结构

```text
dataset/clsvof_vs_nn_imax_0_5/
├── summary.yaml
├── ingest.sh
├── archive/                              # scoped git-ignore；原包与外层 SHA
│   ├── cfd_hpc_180_formal_180_epyc9654_32c_pack4_001.tar.gz
│   └── cfd_hpc_180_formal_180_epyc9654_32c_pack4_001.tar.gz.sha256
├── raw/                                  # scoped git-ignore；包内文件保持只读语义
│   ├── SHA256SUMS
│   ├── matrix_manifest.json
│   ├── matrix_status.csv
│   ├── matrix_timing.csv
│   ├── capwave/
│   ├── rising_case1/
│   ├── rising_case2/
│   └── stationary_bubble/
└── derived/
    ├── build_metrics.py
    ├── audit_metrics.py
    ├── evidence_registry.csv
    ├── formal180_metrics.csv             # 180 行，每个 solver row 一行
    ├── formal180_pairs.csv               # 90 行，每个 native/NN pair 一行
    ├── global_primary_effects.csv
    ├── audit.json
    └── tests/
        └── test_build_metrics.py

figures/clsvof_cell_offset_global/
├── global_overview/
│   ├── plot.py
│   ├── source_data_*.csv
│   ├── global_overview.png
│   └── QA.md
├── capwave/
│   ├── plot.py
│   ├── source_data_*.csv
│   └── capwave_*.png + QA.md
├── rising_bubble/
├── stationary_bubble/
├── oscillating_droplet/
└── supplementary_integrity_runtime/
```

每个图表主题只有一个明确的 `plot.py`，并与对应图片放在同一目录。通用科学指标只在 `derived/build_metrics.py` 计算一次，绘图脚本不重复实现公式。

---

## 6. 数据安全导入合同

### 6.1 导入脚本要求

`ingest.sh` 接收 tar.gz 路径作为参数，必须满足：

1. `--check-only` 模式只核查，不写项目；
2. 拒绝目标目录已存在，禁止静默覆盖；
3. 先在下载目录复核外层 `.sha256`；
4. 检查 tar 中不得有绝对路径、`..` 路径穿越或多个异常顶层根；
5. 用 `cp -p` 复制而不是移动，下载目录原件始终保留；
6. 在同一文件系统的 `.staging/` 中解压；
7. 在 staging `raw/` 中逐条运行包内 `SHA256SUMS`；
8. 校验 matrix manifest、状态表、failure ledger 和 180 行目录结构；
9. 全部通过后才原子 rename 到正式目录；
10. 任一 gate 失败，只保留错误报告，绝不发布半成品 dataset。

### 6.2 导入完成 gate

- [ ] source archive SHA 与 checksum 文件一致；
- [ ] project archive SHA 与 source archive 一致；
- [ ] 2,537 条内部 SHA 全部通过；
- [ ] `expected_rows=completed_rows=180`；
- [ ] `invalid_rows=0`；
- [ ] `pair_failure_count=0`；
- [ ] 180 个 row ID 唯一；
- [ ] 90 个 native/NN 配对完整；
- [ ] benchmark 行数为 48/48/48/36；
- [ ] stationary 不存在 N512；
- [ ] 下载目录原文件未删除、未改名、未改写；
- [ ] `git status --short` 除计划允许的新文件外没有新增意外变化。

### 6.3 Git 边界

在 `.gitignore` 中只增加本数据集的精确规则：

```text
dataset/clsvof_vs_nn_imax_0_5/archive/
dataset/clsvof_vs_nn_imax_0_5/raw/
```

默认追踪 `summary.yaml`、导入/分析/绘图脚本、小型 derived CSV、图件和 QA；不使用 Git 传输原始正式数据包或解压后的 286 MiB 数据。

---

## 7. 指标合同

### 7.1 通用配对原则

只比较完全匹配的：

```text
benchmark + physical case + host + resolution + imax
```

方法固定为：

```text
clsvof
nn
```

`imax=3` 是默认主比较；`imax=0,1,2,4,5` 是 redistance sensitivity，不能被当作统计重复。

对正值且“越小越好”的 primary error，配对效应定义为：

```text
effect_log2 = log2(error_NN / error_native)
```

- `effect_log2 < 0`：NN error 更小；
- `effect_log2 = 0`：持平；
- `effect_log2 > 0`：NN error 更大。

若任一值为零，不添加任意 epsilon；该 ratio 记为 NA，并同时报告绝对差。

### 7.2 Capwave

主指标沿用 Basilisk/Prosperetti 定义：

```text
E_RMS = sqrt(mean((a_num - a_ref)^2)) / 0.01
tau = omega_0 * t
```

输出指标：

- `relative_rms`（主指标）；
- `amplitude_l2_error`；
- `max_abs_amplitude_error`；
- 时间历程 `a(tau)`；
- N64–N512 的 observed convergence trend，但不在非渐近区强行拟合“阶数结论”。

必须同时读取包内 `log` 的 solver 报告值并从 `wave-N + prosperetti.h` 重算；报告二者最大差异。由于原始文本为 `%g` 精度，容差需在 canary 上按打印精度确认，不能事后为了通过而放宽。

### 7.3 Rising bubble Case 1/2

从 `stdout.txt` 读取：

```text
t, relative_volume_drift, center_y, rise_velocity
```

分别使用：

```text
Case 1 -> c1g3l4.txt / c1g3l4s.txt
Case 2 -> c2g3l4.txt / c2g3l4s.txt
```

主指标：

- `velocity_reference_rmse`：在公共时间区间上将 MooNMD 线性插值到 solver 时间点；
- `center_reference_rmse`；
- `max_abs_volume_drift`（守恒 guardrail）；
- final interface shape distance。

形状距离同时保留：

1. 旧分析口径的 reference-point → numerical-segment mean/max，便于历史对照；
2. 等弧长重采样后的 symmetric Chamfer 与 Hausdorff，避免单向距离掩盖缺失结构。

解析器必须跳过 Case 2 的 solver warning、空行和 `kappa_offset_provider_stats`，不得把它们误当 facet 点。

### 7.4 Stationary bubble

沿用当前 case 合同：

```text
Ca(t) = U_star(t) / sqrt(La),  La = 12000
Ca_tail_max = max(Ca) over final 10% of samples
```

主指标：

- `ca_tail_max`；
- `ca_max`；
- `ca_final`；
- `delta_f_final`；
- 完整 `Ca(tau)` 时间历程。

必须从嵌套的 `<mode>/La-12000-<level>` 重算 top-level `summary.csv`，不得只信汇总表。

### 7.5 Oscillating droplet（现有数据）

不重新拟合已冻结的正式结果，优先读取已审计的：

```text
comparison.csv
comparison_crossover.csv
```

使用：

- signed damping `b_fit`；
- independent envelope `b_envelope`；
- absolute frequency error；
- max kinetic energy；
- grid × checkpoint crossover。

负 `b` 必须显式标为 anti-damping failure，不能因 `b^2` 派生量看似有限而隐藏符号。

### 7.6 Runtime 与 provider health

- runtime 来自 per-row manifest 的 `elapsed_seconds`、threads 和 CPU list；
- 只做同 host、同 threads policy 下的 paired overhead；
- packed scheduler 中的 wall time 不作为硬件通用性能结论；
- clamp/guard/evaluation 数量属于实现健康证据，不是物理准确度替代指标；
- 如果某类 row 未保存完整 provider stats，明确标 NA，不从其他 case 外推。

---

## 8. 旧分析代码审计与复用边界

现有 `experiments/clsvof_redistance_imax_matrix/` 分析脚本不能直接对新包运行，已发现的硬编码包括：

- 以 96 行而不是 180 行作为完成 gate；
- 使用旧方法 ID `clsvof_nn`，而正式方法是 `nn`；
- 只覆盖 capwave 与 rising Case 1；
- Hysing shape/reference 在函数内硬编码 Case 1；
- 假设结果文件叫 `out`/`status.json`，而新包使用 `stdout.txt`/formal manifest；
- 假设存在旧 `redistance_metrics.csv`，新正式包的物理结论不依赖该诊断文件。

实施时允许复用经测试的纯函数思想，例如 Prosperetti 解析、线性插值和 point-to-segment distance；不得通过改几个常量继续运行旧 96-row pipeline。旧脚本先保留为历史证据，不在本 goal 中删除。

---

## 9. 图件科学合同

### 9.1 暂定核心结论

在完整指标计算前，只允许使用下面这句**暂定**结论：

> 在同一 CLSVOF host 上，NN cell-offset 曲率的影响随物理问题、网格分辨率和 redistance `imax` 系统性变化；应报告其条件性收益与明确失效边界，而不是预设其统一优越。

Phase 4 数值审计后必须重新冻结一句数据支持的最终结论。若结果主要是持平或退化，图和文字必须如实改变，不能为了“顶刊风格”制造正向故事。

### 9.2 图件原型

- archetype：`quantitative grid`，带一个占主导面积的 hero summary；
- final width：183 mm 双栏；
- provisional height：150–170 mm，最终不得超过目标期刊限制；
- background：白色；
- panel labels：小写粗体 8 pt；
- body/ticks/legend：最终尺寸 6.5–7.5 pt；
- backend：Python/matplotlib exclusively。

### 9.3 统一视觉语义

| 语义 | 编码 |
| --- | --- |
| CLSVOF native | neutral dark grey |
| NN cell-offset | deep blue |
| official/literature reference | muted red，open marker 或细线 |
| improvement / degradation | 只用于方向标记的 green / red，不作为方法主色 |
| default `imax=3` | 黑色描边或明确竖线 |
| nondefault `imax` | 位置/明度编码，不使用彩虹色谱 |

所有 panel 保持相同方法颜色；颜色之外必须有 marker/line style，保证灰度打印可读。

### 9.4 代表性曲线选择规则

为避免事后挑最好看的曲线，绘图前冻结：

- 全局跨 case 对照：优先使用所有 benchmark 都有的 N128、`imax=3`；
- case 细节 hero：使用该 case 的最高正式分辨率（capwave/rising N512，stationary N256，oscillation N128）；
- 所有分辨率和全部 `imax` 必须在 summary/heatmap 中完整出现；
- 不能根据“NN 改善最大”来选择展示分辨率。

---

## 10. 主图与图集设计

### Figure 1：全局总图（最重要）

建议文件：

```text
figures/clsvof_cell_offset_global/global_overview/global_overview.*
```

Panel map：

| panel | 独立科学问题 | 数据 |
| --- | --- | --- |
| **a — hero** | 默认条件下，NN 相对 native 的 primary physical error 在不同 benchmark 中如何变化？ | N128、`imax=3` 的 capwave/rising1/rising2/stationary，加 oscillation matched N128；x 轴为 `log2(NN/native)`，每行标明具体指标 |
| **b** | 180 行中，这种方向对 N 和 `imax` 是否稳定？ | 90 组 pair 的 block heatmap；按 benchmark/N 分组，列为 `imax=0..5`，不做跨 benchmark 平均 |
| **c** | Capwave 是否保持参考解与收敛行为？ | 新 180 的 imax=3 native/NN + 已有 official VOF/CLSVOF + Prosperetti |
| **d** | Rising Case 1/2 的宏观运动是否跟随 MooNMD？ | N128、imax=3 的 velocity time histories；Case 1/2 分开小轴 |
| **e** | Stationary bubble 的寄生流是否降低且保持质量守恒？ | N256、imax=3 的 `Ca(tau)` 与 `Ca_tail_max`；native/NN paired |
| **f** | 现有 oscillating-droplet 为什么不能宣称分辨率稳健？ | N64/N128 signed damping + frequency error；crossover 用连线/标记解释 grid effect |

Panel a 与 b 的职责不同：a 是默认条件的跨问题主结论，b 是完整 180 行敏感性，不允许用同一数据的另一种外观重复表达。

### Figure 2：Capwave 细节

- amplitude decay vs Prosperetti；
- N16–N512 official reference landscape 与 N64–N512 formal pair；
- `relative_rms` convergence；
- N × `imax` paired-effect heatmap；
- 若 observed order 不稳定，只画局部 slope，不写“统一二阶”。

### Figure 3：Rising bubble 细节

- Case 1/2 rise velocity vs MooNMD；
- center history；
- final shape vs MooNMD（最高正式分辨率、`imax=3`）；
- volume drift guardrail；
- N × `imax` 的 velocity-RMSE 与 shape-distance sensitivity；
- Case 1/2 绝不混成一个平均指标。

### Figure 4：Stationary bubble 细节

- `Ca(tau)` native/NN；
- `Ca_tail_max` vs N 与 `imax`；
- `delta_f_final`；
- paired effect heatmap；
- log scale 必须显示真实零/下限处理方式，不截断坏结果。

### Figure 5：Oscillating-droplet 现有数据统一重绘

- 从已审计 CSV 重绘，不覆盖原 timestamped 图片；
- matched N64/N128 的 kinetic/damping/frequency；
- 2×2 crossover；
- official VOF-HF 只作 open-marker descriptive reference；
- 明确保留 N64 anti-damping negative result。

### Supplementary

- S1：完整 90-pair sensitivity table/heatmap；
- S2：所有参考时间历程与 final shapes；
- S3：守恒、finite、terminal-time、guard/clamp 与 provenance hash；
- S4：同 policy 的 paired runtime overhead；
- S5：旧独立 cell-offset 运行与新正式 `imax=3` 的复现一致性/差异，但不伪装成重复实验。

明确禁止 radar chart、综合“总分”、跨 benchmark raw error 平均和没有物理含义的排名。

---

## 11. 统计与科研诚信合同

本矩阵是确定性数值实验设计，不是 180 个独立随机重复：

- 每个 configuration 当前 `n=1`；
- N、`imax`、case 和 method 是设计因子，不是 replicate；
- 不计算无依据的 p-value、SEM、95% CI；
- 不把 across-`imax` 标准差画成“误差条”；
- oscillation 的 fit SE 只能标注为拟合参数渐近 SE，不得称 run-to-run variability；
- 所有 primary panels 都提供单独 Source Data；
- 时间序列可为视觉清晰按固定步长显示，但指标必须用完整数据计算；
- 不使用平滑曲线替代原始 solver trajectory；
- 不隐去失败行、warning 或反阻尼符号；
- 不把 guard/clamp=0 当作准确度证明。

若未来需要统计不确定度，必须另行设计独立重复/扰动实验，不能从当前矩阵伪造。

---

## 12. 分阶段实施任务与 gate

### Phase 0 — 工作区与输入冻结

**只读检查：**

- [ ] 保存当前 `git status --short`，标记所有 pre-existing changes；
- [ ] 确认目标目录尚不存在；
- [ ] 确认磁盘余量至少 2 GiB，覆盖 archive、raw、staging 和图件；
- [ ] 再次核对 source archive 和 checksum；
- [ ] 运行 `ingest.sh --check-only`；
- [ ] 不接触当前大量既存修改和 untracked oscillating-droplet 工作。

**Gate 0：** check-only 全绿，否则停止。

### Phase 1 — 安全复制与原子发布

**计划文件：**

- Create: `dataset/clsvof_vs_nn_imax_0_5/ingest.sh`
- Create: `dataset/clsvof_vs_nn_imax_0_5/summary.yaml`
- Modify: `.gitignore`（只加精确的 archive/raw 规则）
- Generate: `archive/`, `raw/`

步骤：

- [ ] 在 staging 复制 archive 和 checksum；
- [ ] 验证复制前后 SHA；
- [ ] 安全路径检查；
- [ ] 解压到 staging/raw；
- [ ] 校验 2,537 条内部 SHA；
- [ ] 校验 180/180、90 pairs、0 invalid、0 pair failure；
- [ ] 原子发布；
- [ ] 再次确认 Downloads 原件仍在且 SHA 未变。

**Gate 1：** 任一 hash 或行身份失败，禁止继续分析。

### Phase 2 — 全仓证据登记与去重

**计划文件：**

- Create: `derived/evidence_registry.csv`
- Modify only after Gate 1: `cases/capwave/summary.yaml`
- Modify only after Gate 1: `cases/rising_bubble/summary.yaml`
- Modify only after Gate 1: `cases/stationary_bubble/summary.yaml`
- Modify only after Gate 1: `cases/_shared/nondefault_redistance/summary.yaml`

步骤：

- [ ] 将新 180 行登记为当前 canonical formal study；
- [ ] 将 stationary 的 formal role 从 `not_generated` 更新为已生成；
- [ ] 登记 official/reference 与 oscillation matched/crossover；
- [ ] 为旧 48 native、direct-NN、smoke/diagnostic 写清 exclusion reason；
- [ ] 检查同一 row identity 不会从两个目录重复进入分析；
- [ ] 不移动、不删除现有数据。

**Gate 2：** 所有进入主图的数据都能回答“host、方法、分辨率、case、evidence level、canonical source”六项。

### Phase 3 — 解析器 canary 与 180 行指标重算

**计划文件：**

- Create: `derived/build_metrics.py`
- Create: `derived/tests/test_build_metrics.py`
- Generate: `formal180_metrics.csv`, `formal180_pairs.csv`

canary 先选择每个 benchmark 的 N64/`imax=3` native+NN，共 8 行：

- [ ] capwave parser 与 RMS 重算；
- [ ] rising Case 1 正确 reference；
- [ ] rising Case 2 正确 reference 且 warning-safe；
- [ ] stationary nested series 与 summary 重算；
- [ ] provider stats 缺失时返回 NA 而不是零；
- [ ] manifest identity 与目录 identity 一致。

canary 通过后才跑全 180：

- [ ] 180 row metrics；
- [ ] 90 paired rows；
- [ ] 全字段 finite/NA 合同；
- [ ] terminal time、sample count、monotonic time；
- [ ] case-specific reference 与坐标变换；
- [ ] source file SHA 写入 row provenance。

**Gate 3：** `audit_metrics.py` 输出 `passed=true`；任何 silent drop 都视为失败。

### Phase 4 — 全证据综合与结论冻结

- [ ] 将 official/reference、oscillation 和 180-derived 表接入 `global_primary_effects.csv`；
- [ ] 默认 `imax=3` 与 sensitivity 明确分层；
- [ ] 逐 benchmark 检查方向，而不是先求平均；
- [ ] 确认代表性曲线遵守预注册规则；
- [ ] 写出一句最终 core conclusion；
- [ ] 写出至少三条 reviewer risks 和对应 panel/Source Data；
- [ ] 作者确认科学叙事后再进入正式排版。

**Gate 4：** 图的结论必须由表格直接支持；若 mixed/negative，则保留 mixed/negative 叙事。

### Phase 5 — 先总图，后 case 图

- [ ] 先生成 Figure 1 的 source_data，不渲染；
- [ ] 核对每个 panel 是否提供独立证据；
- [ ] Python/matplotlib 渲染 Figure 1；
- [ ] 通过数值与视觉 QA 后再生成 Figures 2–5；
- [ ] 最后生成 Supplementary；
- [ ] 每张图脚本与图片同目录；
- [ ] 不覆盖任何现有 timestamped 图片。

**Gate 5：** Figure 1 在最终 183-mm 尺寸下无需放大即可读，并能独立说明主结论与失效边界。

### Phase 6 — 图件 QA 与 report 选择

每张图检查：

- [ ] 只交付 600-dpi PNG；
- [ ] 未经用户明确要求，不生成 PDF、SVG、TIFF；
- [ ] 白底、不透明、无裁切；
- [ ] method color 全图一致；
- [ ] 灰度下仍可区分；
- [ ] panel label、单位、log axis、reference line、legend 无重叠；
- [ ] Source Data 能逐点复现图；
- [ ] QA.md 记录 final size、字体、backend、metric、`n`、误差定义和 reviewer boundary；
- [ ] 目标期刊确定后，按其最新官方 figure guide 再复核尺寸与格式。

作者选择后：

- [ ] 只把选中的最终 bundle 复制到 `report/figures/`；
- [ ] 保留 `figures/` 中的脚本、Source Data 和完整候选；
- [ ] 不自动删除未入选候选。

**Gate 6：** report 中每张图都能反向追到 figure-level Source Data、derived row 和 raw SHA。

---

## 13. 自动化验收清单

至少需要覆盖以下测试：

### 数据结构

- [ ] exactly 180 formal rows；
- [ ] exactly 90 native/NN pairs；
- [ ] benchmark counts = 48/48/48/36；
- [ ] methods = native / NN cell-offset only；
- [ ] `imax={0,1,2,3,4,5}`；
- [ ] stationary resolutions = 64/128/256 only；
- [ ] row ID、manifest identity、relative path 三者一致。

### 解析

- [ ] capwave `%g` 输出与 Prosperetti index pairing；
- [ ] rising `stdout.txt` header 与非数值 warning 跳过；
- [ ] Case 1/2 reference routing；
- [ ] facet blank-line segmentation；
- [ ] provider stats 行不进入 shape；
- [ ] stationary nested mode path；
- [ ] time finite/monotonic/terminal；
- [ ] zero denominator ratio 返回 NA。

### 科学边界

- [ ] old direct method 永不进入主表；
- [ ] old 48 native 不重复计数；
- [ ] `imax!=3` 不作为 replicate；
- [ ] external solver reference 不进入 NN causal effect；
- [ ] oscillation negative damping 符号保留；
- [ ] 没有跨 benchmark raw metric 平均或总分。

### 图件

- [ ] source CSV 与 plotted arrays exact match；
- [ ] 每张图恰有一个 600-dpi PNG 图像交付件；
- [ ] 不存在未经明确要求生成的 PDF、SVG、TIFF；
- [ ] final physical size 与字体 gate；
- [ ] deterministic rerender hash 稳定，允许的 metadata 差异需记录。

---

## 14. 停止条件

遇到下列任一情况立即停止当前 phase，不用“尽量画完”掩盖问题：

1. 外层或包内任一 SHA 失败；
2. archive path safety 失败；
3. row count、pair count 或 formal identity 不一致；
4. 新数据与旧数据的 method/host 无法明确区分；
5. Case 1/2 reference routing 不确定；
6. 重算指标与 solver summary 差异超过预先确认的打印精度容差；
7. 图的 core conclusion 与实际表格方向冲突；
8. 需要覆盖、移动或删除既存数据；
9. 目标目录已存在且内容身份不明；
10. 绘图运行时缺少 Python/matplotlib 依赖。

停止时只报告具体失败 gate、受影响 row/source 和下一步，不发布半成品到 `report/`。

---

## 15. Definition of Done

本 goal 只有同时满足以下条件才算完成：

- [ ] 新包在项目 dataset 中有 archive + raw 双层可验证副本；
- [ ] Downloads 原件仍保持不变；
- [ ] 包内 2,537 条 SHA 全部通过；
- [ ] 180 rows、90 pairs 完整且 scientific metrics 已独立重算；
- [ ] 现有 official、MooNMD、oscillating matched/crossover 已进入 evidence registry；
- [ ] audit-only/smoke/direct 数据明确排除且没有重复计数；
- [ ] Figure 1 总图同时覆盖新 180 与合格的既有数据；
- [ ] case Figures 2–5 与 Supplementary 完成；
- [ ] 每图具备 script + Source Data + 600-dpi PNG + QA；
- [ ] 没有未经支持的优越性、显著性或稳健性表述；
- [ ] 作者选中的图已进入 `report/figures/`，其余候选仍保留在 `figures/`；
- [ ] 最终 `git diff --check` 通过，且未触碰无关的既存工作树改动。

---

## 16. 可直接用于设置 goal 的目标文本

```text
严格按 docs/superpowers/plans/2026-07-15-clsvof-full-evidence-data-curation-and-publication-figures.md 实施：安全复制并双层校验下载的 formal 180-row 包，将它与仓库现有 official/MooNMD/oscillating-droplet 合格证据统一登记和去重，重算全部科学指标，先完成全局顶刊级总图再完成 case 图与补充图。不得覆盖或删除既存数据，不得把 direct/smoke/audit-only 数据混入正式结论；所有图必须由 Python/matplotlib 生成并交付 Source Data、600-dpi PNG 和 QA，默认不得生成 PDF、SVG、TIFF，只有作者选择的图进入 report/figures/。
```
