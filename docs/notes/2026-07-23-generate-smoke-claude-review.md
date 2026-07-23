# `generate` 30 项 smoke：用户与 Claude 审核稿

状态：**smoke 产物与执行契约通过；科学结果尚未获用户/Claude 批准；未提交 Git；未运行 formal。**

本文件只审核新范式和真实 N32/N64 smoke。`READY.json` 的含义是 30 条行级
产物、哈希、配对关系和共享 provenance 都完整，不等于所有方法的物理表现已被
接受。

上一轮 Claude 审核提出的实现缺口已经关闭：

- `scientific_artifacts.json` 与 `plot_data.csv` 都保留在每行；
- `verify_pairs` 改读 manifest 中的 redistance overlay SHA-256，不再依赖行内
  snapshot；
- capwave `prosperetti.h` 改为共享 reference，campaign 产物中的 capwave
  scientific contract 升为 schema 2；
- 编译旗标已经成对：capwave/rising/stationary 的 CLSVOF 与 NN 都有
  `-disable-dimensions`，oscillating 两侧都没有。

## 1. 请 Claude 优先审核的结论

1. 是否接受 case-centered 路径：
   `<case>/[caseK]/Nxxxx/VOF-HF` 与
   `<case>/[caseK]/Nxxxx/imax03/{CLSVOF,NN}`。
2. 是否接受 campaign 级 `_provenance`：30 个行内 `source_snapshot/` 已全部
   移除，179 个逻辑源码引用收敛为 28 个唯一 SHA-256 对象；每行 manifest
   直接记录对象路径和哈希。
3. 是否同意把 `analysis_ready` 严格解释为“数据完整、可重算、可画图”，而不是
   “物理结果已通过”。建议 formal 前保留这个语义或将名称改成更明确的
   `artifact_ready`。
4. oscillating NN 在 N32、N64 都出现负拟合阻尼，应由用户/Claude 决定这是
   只记录的物理结果，还是 formal 前必须修复/设门。当前代码遵守此前决定：保存
   完整拟合产物，但不发明 stock case 没有规定的残差/R2 阈值。
5. stationary CLSVOF/NN 在 τ=1 到 τ=2 维持明显大于 VOF-HF 的残余速度。
   这是真实 smoke 结果，不是缺数据；请判断是否允许进入正式 6 个 imax 扫描。

## 2. 执行范围与完整性

数据根目录：
`data/_smoke/vof_clsvof_nn_benchmarks_v1/`

| 检查 | 结果 |
|---|---:|
| 真实行数 / 唯一路径 | 30 / 30 |
| VOF-HF / CLSVOF / NN | 10 / 10 / 10 |
| `manifest.json` | 30/30 |
| `scientific_artifacts.json` | 30/30 |
| `metrics.csv` | 30/30 |
| `plot_data.csv` | 30/30 |
| NN `provider_stats.csv` | 10/10；非 NN 为 0 |
| 行内 `source_snapshot/` | 0 |
| 共享对象 / 逻辑引用 | 28 / 179；零引用对象为 0 |
| manifest `analysis_ready=true` | 30/30 |
| campaign `completed_rows` | 30/30 |
| 当前源码锁与 smoke 启动锁 | 完全一致 |
| `READY.json` | `status=ready`, `purpose=smoke`, `row_count=30` |

产物总计约 53 MiB。各行累计 solver elapsed time 约 2651 s；最慢三项是
oscillating N32 NN（728 s）、stationary N64 NN（500 s）和 oscillating N64
NN（413 s）。这是单线程真实运行，不是 dry-run 或旧数据复用。

静态门槛在运行前为 312 条 formal plan、30 条 dry-run；相关测试结果为
`113 passed, 6 skipped`。skip 是仓库现有的可选/平台测试，不是 smoke 行失败。

## 3. 每个 case 的正式产物形态

所有方法都有同一公共核心：

```text
<row>/
├── manifest.json
├── scientific_artifacts.json
├── metrics.csv
├── plot_data.csv
├── compile.stdout
├── compile.stderr
└── case-specific raw data and runtime logs
```

NN 额外有 `provider_stats.csv`。case-specific 原始数据如下；不同物理问题不能
强制使用同一个原始文件名，但三个方法在同一 case 内使用同一 plotting schema。

| case | 三方法共同的 `plot_data.csv` 列 | 必要原始/诊断通道 |
|---|---|---|
| capwave | `tau, amplitude, reference_amplitude, amplitude_error` | `wave.dat`, `official_error.dat`; `prosperetti.h` 只在 `_provenance/references/` 保存一次 |
| rising bubble | `time, relative_volume_change, center_of_mass_x, rise_velocity_x, dt, circularity, half_area, half_perimeter` | `history.dat`, `interface.dat`, `circularity.csv` |
| stationary bubble | `tau, u_star, delta_fraction, capillary_number` | `timeseries.dat`, `milestones.csv`, `termination.csv`, `official_terminal.dat`, `runtime_and_terminal.log` |
| oscillating droplet | `time, kinetic_energy, pressure_iterations` | `timeseries.dat`, `fit_curve.dat`, `fit.log`, `error.dat`, `laplace.dat`, `fit_summary.dat`, `termination.csv` |

`plot_data.csv` 行数在方法间按同一 case/N 完全一致：capwave 每行 738 个样本；
stationary N32/N64 分别 50301/142267 个样本；oscillating N32/N64 分别
1294/3640 个样本。rising 的样本数随 case/N 的自适应时间步变化，但同一
case/N 的三方法一致。

## 4. smoke 数值摘要

### Capwave

`relative_rms_error_recomputed`（无量纲）：

| N | VOF-HF | CLSVOF | NN |
|---:|---:|---:|---:|
| 32 | 0.0242356 | 0.0364221 | 0.0363779 |
| 64 | 0.00639228 | 0.00722669 | 0.00710109 |

六行都有 738 个样本，且重算值与保存的 official error 通道一致。N64 相比
N32 都降低；没有数据完整性异常。

### Rising bubble

所有 12 行精确到 `t=3`。下表为
`max(abs(relative_volume_change)) / terminal rise velocity / minimum circularity`：

| case | N | VOF-HF | CLSVOF | NN |
|---|---:|---|---|---|
| 1 | 32 | 0.001854 / 0.196355 / 0.850039 | 0.001286 / 0.202440 / 0.850370 | 0.001445 / 0.202614 / 0.846937 |
| 1 | 64 | 0.000203 / 0.192910 / 0.861814 | 0.000226 / 0.193636 / 0.880935 | 0.000266 / 0.193744 / 0.881409 |
| 2 | 32 | 0.000387 / 0.178801 / 0.532260 | 0.000394 / 0.180970 / 0.569916 | 0.000394 / 0.182314 / 0.563273 |
| 2 | 64 | 0.000840 / 0.188579 / 0.508496 | 0.000848 / 0.188213 / 0.508226 | 0.000837 / 0.188538 / 0.505957 |

NN provider 确实执行。case2 的 offset 分母保护发生少量 clamp：N32 为
6/1056，N64 为 11/5963；denominator guard 为 0。建议保留为正式运行时诊断，
目前不足以判定结果错误。

### Stationary bubble

六行都在同一条轨迹精确保存 τ=1，并精确终止于 τ=2：N32 为 50300 次迭代，
N64 为 142266 次迭代。`u_star` 在 τ=1 / τ=2 为：

| N | VOF-HF | CLSVOF | NN |
|---:|---|---|---|
| 32 | 3.44e-14 / 3.70e-14 | 0.00329888 / 0.00329888 | 0.00328541 / 0.00328541 |
| 64 | 6.34e-14 / 7.10e-14 | 0.00273906 / 0.00273906 | 0.00312702 / 0.00312702 |

终端最大形状误差分别为：N32 VOF-HF/CLSVOF/NN =
0.015214/0.020701/0.020662；N64 = 0.006671/0.008485/0.008519。

数据本身完整，但物理上 CLSVOF/NN 的 τ=1 到 τ=2 残余速度几乎不下降，且
显著高于 VOF-HF。应在 formal 前作为科学审核点，而不是把它误报成 pipeline
错误或静默忽略。

沿用 Claude 上轮指出的语义：τ=1 的测量事件本身不改写 `d/f/u`，但 Basilisk
会为精确落在 τ=1 而缩短一个时间步，因此 τ=1 之后的 dt 序列相对“没有里程碑
事件”的运行会有变化。三种方法都使用相同里程碑调度，当前 smoke 的横向可比性
不受这一点破坏；文稿中不应称其为“完全不影响轨迹”。

### Oscillating droplet

所有六行使用 Standard centered host，并达到固定 `t>=1`。拟合摘要：

| N | method | `abs frequency error` | fitted `b` | regime |
|---:|---|---:|---:|---|
| 32 | VOF-HF | 0.4098% | 0.909822 | damped |
| 32 | CLSVOF | 0.04839% | 0.0203646 ± 0.02922 | damped, but weakly identified |
| 32 | NN | 0.03865% | -1.33376 ± 0.06490 | **nonphysical_growth** |
| 64 | VOF-HF | 0.1169% | 0.231450 | damped |
| 64 | CLSVOF | 0.1015% | 0.301941 ± 0.001954 | damped |
| 64 | NN | 0.1937% | -0.448354 ± 0.02062 | **nonphysical_growth** |

因此频率误差列可画，但 NN 的阻尼和 equivalent-Laplace 解释不能直接进入论文。
建议把这个问题定为 **formal 授权前必须明确处理的高优先级科学审核项**。最小
动作不是删除数据，而是先由 Claude 复核 host/sign adapter/能量曲线和拟合定义，
再由用户决定“接受并标注”还是修复后重跑 NN oscillating smoke。

## 5. 警告与非阻塞项

- 8 个非空 `compile.stderr` 均为编译 warning：capwave VOF-HF 两行是 stock
  `capwave.c` 的 non-void return warning；oscillating 六行是 Basilisk
  `tree.h` 的 misleading-indentation warning。没有编译错误。
- oscillating 的 VOF-HF 行仍保留 `VOF-HF_report.json`、`VOF-HF_RESULTS.md`
  和 `verification.json` 三份额外审核文件，而 CLSVOF/NN 没有。它们不影响公共
  核心，但若用户要求“文件列表也完全一致”，需在 formal 前决定是否只保留一份
  campaign 级报告；当前先不动。
- 日志已全部保存，但仍使用各 runner 的根目录文件名，没有再人为套一层
  `logs/`。这保留了命令记录与原 benchmark channel 的直接对应关系；若要统一
  到 `logs/`，必须同步升级 manifest plan，而不能只移动文件。

## 6. 当前发布门

- [x] 新 `data/` 路径实施
- [x] 312 条正式清单静态生成
- [x] 30 条真实 smoke 完成并校验
- [x] 用户要求的原始数据、metrics、plot-ready 数据、日志和 provenance 齐全
- [ ] 用户审核本文件与逐 case 产物
- [x] Claude 审核共享 provenance 与科学异常（2026-07-23，见 §7）
- [x] 用户决定 oscillating NN 负阻尼的处理方式（接受并标注，见 §7）
- [ ] 所有需求与 smoke 获批后才创建完整 Git commit
- [ ] commit 获批后才允许 formal 312 项

当前明确禁止：提交 Git、启动 formal、删除/覆盖任一 smoke 行、用旧 dataset
替换本次真实结果。

## 7. 审核决议（2026-07-23）

Claude 完成 §1 五项审核，用户逐项批准。权威记录：campaign 级
`data/_smoke/vof_clsvof_nn_benchmarks_v1/science_review.json`（新增文件，
未触碰任何 smoke 行）。

1. **case-centered 路径**：通过，实地核对与 §3 一致。
2. **campaign 级 `_provenance`**：通过；28 个共享对象实地确认，manifest
   引用（object 路径 + SHA-256 + logical_path）抽查无误。
3. **`analysis_ready` 不改名**：行 manifest 与 formal 保持 schema 同一；
   语义严格限定为"数据完整、可重算、可画图"；科学裁决落在
   `science_review.json`。
4. **oscillating NN 负阻尼：接受并标注，不重跑。** pipeline 五重免责：
   同 host CLSVOF 阻尼为正（N64 +0.30）；频率误差 0.19% 排除符号翻转；
   原始动能包络单调增长（N32 ×2.9、N64 ×1.25），非拟合伪影；
   provider_stats 92203 次求值 0 clamp、0 分母保护；b–c 拟合相关仅
   -0.019，频率列不受污染。归因为 NN 曲率噪声与 stock `adapt_wavelet`
   在低分辨率下的相互作用（归档源码第 229 行确认自适应；smoke b =
   -1.33/-0.45 与 2026-07-22 tem/ 受控实验 -1.38/-0.32 跨 harness 吻合；
   同 N 均匀网格阻尼为正、自适应 N128 自行恢复、crossover 排除
   checkpoint）。分析期屏蔽规则（方法中立）：regime != damped 的行屏蔽
   `fit_b`/`equivalent_laplace`，频率列保留；|b| < 2·stderr 标注
   weakly_identified（含 CLSVOF N32 的 0.020±0.029）。
5. **stationary 残余速度：按测量结果接受，准入 formal imax 扫描。**
   VOF-HF 良平衡高度函数到机器零、CLSVOF/NN 维持 ~3e-3 持久寄生流平台
   （τ=1→τ=2 九位有效数字不变）正是该基准的测量目的。观察项：NN 的
   u_star 随 N 收敛慢于 CLSVOF。

新增非阻塞记录：oscillating **N64 VOF-HF 对上游 `oscillation.ref` 的严格
diff 仅差拟合参数 a 的末位**（0.000290→0.000291，b/c 相同），与
spurious.ref 在本机的平台浮点不可复现同类；N32 为精确 official_pass。

冗余报告决议已实施：formal 行不再生成
`VOF-HF_report.json`/`VOF-HF_RESULTS.md`/`verification.json`，由
`_campaign/oscillating_vof_hf_official.json`（campaign 完成时生成）替代；
行级严格 diff `fit_summary_vs_ref.diff` 保留；smoke 行历史文件原样保留，
校验对其不要求也不禁止。改动：`build_official_report.py`（只写 diff 与
stdout 记录）、`campaign.py`（校验清单 + rollup）、测试更新。验证：
`pytest generate` 114 passed 6 skipped（基线 113+新增 1）；`job.sh check`
ok（312 formal / 30 dry-run）；用归档 N64 行重放新构建器，七字段与归档
报告一致、diff 逐字节相同。

**源码锁必然分叉**：本决议的代码改动使当前 generate/ 锁偏离 smoke 启动锁
（e454f4e3…）。smoke 的运行时锁永久保存在其 `_campaign/campaign.json` 与
`_provenance/source_lock.json`；`run_campaign` 的锁守卫自此拒绝向冻结
smoke 追加行（正是设计要的隔离）。formal 将在 commit 后的干净树上记录
自己的锁。

剩余门：用户逐 case 产物审核 → 批准后创建完整 commit → 用户明确授权
formal 312 项。
