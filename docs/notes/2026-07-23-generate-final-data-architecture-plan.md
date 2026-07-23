# generate 最终实施候选：用户 / Claude 审核包

日期：2026-07-23
状态：**Claude 的上一轮先决工程修复已实施；本轮任务矩阵已按用户新要求扩展，正在等待用户 / Claude 最终审核；尚未运行新的 56 项 smoke；尚未提交 Git；禁止启动 397 项 formal。**

本文件用于审核“会跑哪些任务、以什么设置运行、如何占满 WSL CPU、最终保存什么数据、如何复现”。真实入口为 `generate/job.sh`，详细使用说明为 `generate/README.md`。

## 1. 需要审核的最终结论

- 新数据集：`data/vof_clsvof_nn_benchmarks_v1/`；历史 `dataset/` 不迁移、不覆盖；旧版同名 smoke 已按用户要求删除。
- 数值方法名只使用 `VOF-HF`、`CLSVOF`、`NN`。
- `VOF-HF` 是独立官方参考；Oscillating 保留 adaptive 官方 VOF-HF，并加入 uniform VOF-HF/CLSVOF/NN 匹配实验；两者都只用 Standard centered variant。
- Capillary、Rising case1/2、Oscillating 的 CLSVOF/NN 跑 `imax={0,1,2,3,4,5,10,15,20}`，`imax=3` 是 default，其余八个是正式 sensitivity。
- Stationary 只跑 `imax=0`，N32/64/128/256，固定到 `tau=2`，精确保留 `tau=1`；不因收敛提前结束。
- NN 严格使用与 N 匹配的 `baseline_<N>_hgradient`。
- 正式矩阵 397 项；smoke 56 项。
- WSL 目标机合同为 32 physical cores / 32 logical CPUs；调度器按 32 CPU slots 并行装填任务，不串行逐项跑。
- repo 与 `data/` 必须位于 WSL 原生 Linux 文件系统，拒绝 `/mnt/c` 一类 Windows mount。
- 每个 row 保存中点与终点两份完整场数据，可重画速度/压力/涡量/界面/曲率热力图。
- 最终 row 只保留 4–5 个科学文件；中间 raw/metrics 文件验证后删除，信息进入 `manifest.json`。

## 2. 正式任务表

| 物理分支 | 网格合同 | N | VOF-HF | CLSVOF | NN | 合计 |
|---|---|---|---:|---:|---:|---:|
| Capillary Wave | 三方法 uniform | 32, 64, 128, 256, 512 | 5 | 45 | 45 | 95 |
| Rising Bubble Case 1 | 三方法 uniform | 32, 64, 128, 256, 512 | 5 | 45 | 45 | 95 |
| Rising Bubble Case 2 | 三方法 uniform | 32, 64, 128, 256, 512 | 5 | 45 | 45 | 95 |
| Stationary Bubble | VOF-HF adaptive；CLSVOF/NN uniform | 32, 64, 128, 256 | 4 | 4（仅 imax0） | 4（仅 imax0） | 12 |
| Oscillating Droplet | adaptive 官方 VOF-HF + uniform 三方法匹配 | 32, 64, 128, 256, 512 | 10（5+5） | 45 | 45 | 100 |
| **总计** | — | — | **29** | **184** | **184** | **397** |

角色计数：24 个 `official_reference`、5 个 `matched_reference`、48 个 `default`、320 个 `sensitivity`。

## 3. 56 项 smoke

smoke 的第一层是所有分支的 N32/N64 default；第二层是所有非 Stationary
分支在 N32 对新增 `imax=10,15,20` 的 CLSVOF/NN canary。这样新增的
redistance 设置不会第一次到 formal 才被执行。

| 分支 | default 层 | 新 imax canary | VOF-HF | CLSVOF | NN | 合计 |
|---|---|---|---:|---:|---:|---:|
| Capillary | N32/N64，三方法，imax3 | N32，imax10/15/20，CLSVOF/NN | 2 | 5 | 5 | 12 |
| Rising Case 1 | N32/N64，三方法，imax3 | N32，imax10/15/20，CLSVOF/NN | 2 | 5 | 5 | 12 |
| Rising Case 2 | N32/N64，三方法，imax3 | N32，imax10/15/20，CLSVOF/NN | 2 | 5 | 5 | 12 |
| Stationary | N32/N64，三方法，imax0 | 无 | 2 | 2 | 2 | 6 |
| Oscillating | N32/N64，adaptive 官方 VOF-HF + uniform 三方法 | N32，imax10/15/20，uniform CLSVOF/NN | 4 | 5 | 5 | 14 |
| **合计** | — | — | **12** | **22** | **22** | **56** |

smoke 与 formal 使用同一物理终点、同一 row schema、同一资源 policy；只是矩阵变小，不是短时间测试。完成后停止，交用户与 Claude 检查，不自动提交。

## 4. 物理与网格设置

| Case | 固定设置 | 时间 | N 的含义 / 官方边界 |
|---|---|---|---|
| Capillary | `L0=2`, `sigma=1`, `mu=0.0182571749236`, `a=0.01`, `TOLERANCE=1e-6` | solver `t=0..2.2426211256`，738 个官方样本 | uniform `N×N`；N256/512 为 extension |
| Rising 1 | Hysing case1 原参数，`tolerance=1e-4` | `t=0..3` | uniform `N×N/4`；stock 默认 N256 |
| Rising 2 | Hysing case2 原参数，含 `FILTERED=1` | `t=0..3` | uniform `N×N/4`；stock 默认 N256 |
| Stationary | `D=0.8`, `La=12000`, Stokes, 四分之一圆 | `tau=0..2`，精确 `tau=1,2` | VOF-HF adaptive TREE；CLSVOF/NN uniform；无 N512 |
| Oscillating | `L0=0.5`, `D=0.2`, `rho=1/0.001`, `sigma=1`, inviscid | 官方 `t<=1` | adaptive TREE 作为官方 VOF-HF；uniform 作为三方法匹配；Standard centered only |

同一个 CLSVOF/NN pair 除 active curvature provider/model 外，host、N、`imax`、时间终点、编译 flags、OpenMP threads 都相同。

## 5. 32-thread 并行设计

### 5.1 两阶段

1. 对所有 pending row 并行 compile-only，最多同时 32 个 compiler process。
2. 编译全部通过后，按 32 slots 并行运行多个 solver row。

这样避免“一个 row 编译+运行完才开始下一个”的串行模式。VOF-HF 的 1-slot row 提前作为 backfill，避免最后只剩 29 个串行任务。

### 5.2 当前待 smoke 审核的资源表

| Row | threads/slots | 同类任务最大并发 |
|---|---:|---:|
| VOF-HF | 1 | backfill |
| CLSVOF/NN N32 | 2 | 16 |
| CLSVOF/NN N64 | 4 | 8 |
| CLSVOF/NN N128 | 8 | 4 |
| CLSVOF/NN N256 | 8 | 4 |
| CLSVOF/NN N512 | 16 | 2 |

这是面向整批 wall time 的吞吐优先候选：所有 N 都允许至少两个 row 并发，避免二维 N512 单行独占 32 核。调度硬约束为 `sum(allocated_slots) <= 32`；只要队列中有能放入剩余 slots 的 row 就启动。`OMP_DYNAMIC=false`，同 N 的 CLSVOF/NN 分配相同线程。

`_meta/resource_usage.csv` 每秒记录 phase、active rows、allocated slots、实际 CPU%、available memory、swap；`resource_summary.json` 汇总 32 slots 满配时的实测 CPU 平均值。slots 满配是实现可保证的合同；真实 CPU% 会因 solver 串行段和 I/O 短暂下降，因此必须看 WSL smoke 证据后才能批准 policy。

### 5.3 编译与求解绑定

内部两阶段不是允许任意外部 executable：

- direct runner 仍拒绝 `--precompiled`；
- campaign build 记录源码 hash、qcc hash、compile argv、参数、OpenMP 环境和 executable hash；
- solve 前逐项比对；任何变化都拒绝；
- 成功后 `manifest.json` 写入 `build_binding`；
- 对应 `_meta/builds/<row>` 临时编译目录随后删除。
- 每个 compiler/solver 使用独立 process group；SIGINT、SIGTERM、SIGHUP 会终止所有活动组，避免中断后留下孤儿进程。

## 6. WSL 环境

```bash
bash generate/setup_wsl.sh --install
bash generate/setup_wsl.sh --check
```

- `generate/requirements.txt`：只安装 `pytest>=8,<9`。
- `setup_wsl.sh`：apt 安装 GCC/build tools、gnuplot、sysstat、Python venv 等。
- Basilisk 源复制到 ignored `build/wsl-toolchain/basilisk/`，使用官方 `config.gcc` 构建 Linux `qcc`；不直接复用 Mac 二进制。
- venv 位于 ignored `build/wsl-venv/`。
- `job.sh` 自动选择两者，无需手工 export。
- `--check` 要求 `nproc=32`，并运行 GCC/OpenMP 2-thread probe 与最小 qcc compile/run probe。
- `--check` 同时拒绝 `/mnt/c`、`drvfs`、`9p` 等 Windows 文件系统路径。

不能只用 `requirements.txt`，因为 pip 不能安装 GCC、OpenMP runtime、gnuplot、apt packages 或 Basilisk qcc。

## 7. 最终 data 架构

```text
data/
├── _smoke/vof_clsvof_nn_benchmarks_v1/
└── vof_clsvof_nn_benchmarks_v1/
    ├── READY.json
    ├── _meta/
    │   ├── run.json
    │   ├── tasks.csv
    │   ├── schema.json
    │   ├── source_lock.json
    │   ├── resource_policy.json
    │   ├── resource_usage.csv
    │   ├── resource_summary.json
    │   ├── object_index.json
    │   ├── oscillating_vof_hf_official.json
    │   ├── logs/{build,solve}/
    │   ├── sources/sha256/<hash>
    │   ├── references/prosperetti.h
    │   ├── references/hysing/{case1_history,case1_interface,
    │   │                        case2_history,case2_interface}.txt
    │   └── models/baseline_<N>_hgradient/{export_manifest.json,nn_weights.h}
    ├── capwave/{summary.csv,Nxxxx/{VOF-HF,imaxNN/{CLSVOF,NN}}/}
    ├── rising_bubble/caseK/{summary.csv,Nxxxx/{VOF-HF,imaxNN/{CLSVOF,NN}}/}
    ├── stationary_bubble/{summary.csv,Nxxxx/{VOF-HF,imax00/{CLSVOF,NN}}/}
    └── oscillating_droplet/
        ├── summary.csv
        ├── adaptive/Nxxxx/VOF-HF/
        └── uniform/Nxxxx/{VOF-HF,imaxNN/{CLSVOF,NN}}/
```

`sha256` 目录只是相同源文件的内容去重和篡改检测，不是创建新模型。`models/` 只复制/硬链接现有模型 C export。

`data/` 因体积原因不进入 Git。正式运行前必须指定第二存储位置；完成后将整个数据集（含 `READY.json` 和 `_meta/` hashes）复制一份。旧 `dataset/`、archive 和既有结果不要求为本 campaign 提交。

## 8. 每个 row 的最终产物

| Case | 最终文件 |
|---|---|
| Capillary | `manifest.json`, `timeseries.csv`, `fields.csv.gz`, `run.log` |
| Rising | `manifest.json`, `timeseries.csv`, `interface_t3.csv.gz`, `fields.csv.gz`, `run.log` |
| Stationary | `manifest.json`, `timeseries.csv`, `milestones.csv`, `fields.csv.gz`, `run.log` |
| Oscillating | `manifest.json`, `timeseries.csv`, `fit.csv`, `fields.csv.gz`, `run.log` |

`manifest.json` 内嵌：身份、resolved plan、source/build hashes、scalar metrics、provider counters、final artifact hashes。中间 `scientific_artifacts.json`、`metrics.csv`、`plot_data.csv`、raw benchmark files 只用于完成检查，随后压缩为上述正式文件并删除；信息没有丢失。

主要表：

- Capillary timeseries：`tau, amplitude, reference_amplitude, amplitude_error`。
- Rising timeseries：`time, iteration, relative_volume_change, center_of_mass_x, rise_velocity_x, dt, circularity, half_area, half_perimeter`；终点界面保存 segment endpoints。
- Stationary timeseries：`tau, u_star, delta_fraction, capillary_number`；milestones 明确为 `tau_1`、`tau_2`，含 shape error、官方式 curvature error、active-provider curvature error。
- Oscillating fit：fit a/b/c 及误差、frequency error、equivalent Laplace、`damped`/`nonphysical_growth`。

## 9. 两时刻完整场

每行一个 `fields.csv.gz`，包含：

```text
snapshot,target_solver_time,actual_solver_time,actual_benchmark_time,
iteration,x,y,Delta,level,u_x,u_y,pressure,vorticity,phase_fraction,
common_curvature,common_curvature_valid,
active_curvature,active_curvature_valid
```

- middle：原生轨迹中第一个达到/越过 target 的 solver state，不插入 scheduled time，不改变 dt。
- final：terminal solver state。
- targets：Capillary solver t=1.1213105628；Rising t=1.5；Stationary 精确 tau=1；Oscillating t=0.5。
- invalid curvature 留空并用 valid flag 标记，不写假零。
- 可直接重建 velocity magnitude、Ca、pressure、vorticity、interface、common/active curvature 热力图。

56-row smoke 将给出实际压缩 bytes 和 cell-records；在真实证据出来前，不声称 formal 总空间已经确定，也不自行删字段或降采样。

## 10. 已完成的代码级自审证据

- `job.sh check`：397 formal、56 smoke/dry-run 全部通过；`plan` 分别输出 397 与 56 个唯一 row。
- 完整 `pytest generate`：160 passed、6 个合理平台/数据 skip；shell syntax 与关键 Python compile checks 通过。
- 新增 imax10/15/20 的离散参数合同和 Oscillating uniform 路径均有独立测试；非法 imax（例如 6、9、11、21）会被拒绝。
- 五个物理分支 × 三方法，共 15 个 N32、threads=1 compile-only：通过。
- Capillary、Rising、Stationary、Oscillating 的 CLSVOF/NN，共 8 个 GCC/OpenMP threads=4 compile-only：通过。
- `requirements.txt` 以本机已安装依赖做 `pip --dry-run --no-index`：通过。
- shell syntax / Python bytecode checks：通过。
- compile-only 中发现并修复：snapshot event iteration scope、Rising curvature include、Mac GCC feature macros；WSL toolchain 已明确使用 `config.gcc`。
- Claude 审核后的先决修复：六个 runner 统一为大写 Git 路径；`oscillation.ref` 纳入 source lock；formal 明确拒绝未提交的 campaign 输入（含 N32 C export）；中断时清理活动 process groups；WSL 拒绝 Windows-mounted 工作目录。
- Oscillating uniform feasibility compile-only：VOF-HF、CLSVOF、NN 使用 `-grid=multigrid` 的 N32 host 均编译通过；现在已加入正式矩阵，但尚未运行科学轨迹。
- 所有本轮 `/private/tmp`、失败 compile work、Python/pytest 临时产物均已清理。

这些只证明代码合同和编译路径，不是科学结果。没有执行任何真实 smoke/formal solver row。

## 11. 仍需用户 / Claude 审核、目前保持不动的部分

1. `resource_policy.wsl-32.json` 当前是 `review_candidate`；实际 WSL CPU% 和吞吐量只能由 56 项 smoke 给证据。
2. `fields.csv.gz` 的 formal 总大小只有保守估计；以 smoke 实测为准。
3. CLSVOF、NN、VOF-HF 的新科学结果尚不存在；`analysis_ready` 只表示数据完整可画图，不表示物理上批准。
4. 本轮不迁移、不删除旧 `dataset/`；旧版同名 v1 smoke 已按用户明确授权删除，新 smoke 将从空路径开始。
5. Oscillating 的 adaptive VOF-HF 只承担官方参考；uniform VOF-HF/CLSVOF/NN 才承担同网格直接比较，目录明确分开，绘图时不得混淆这两个角色。
6. 未经用户 / Claude 审核，不再修改任务矩阵、线程表、字段 schema，不启动 smoke，不提交 Git。

代码还会在 `policy_status != approved` 时硬性拒绝 formal；只有 smoke 审核通过后才修改该状态并纳入完整提交。

## 12. 审核后的执行顺序

```text
当前代码/计划审核
-> WSL setup_wsl.sh --install / --check
-> job.sh check
-> 用户授权运行 56-row smoke
-> 用户 + Claude 审核数据结构、场大小、CPU 利用率和科学结果
-> 修正并重新验证（若需要）
-> 用户同意后提交一个完整 Git 版本
-> 用户再次明确授权 formal
-> WSL 上运行 397 rows
-> verify + READY.json
```
