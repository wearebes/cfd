# Oscillating Droplet：CLSVOF NN 曲率插入与验证计划

> 状态：**已于 2026-07-15 实施并完成验证；以下保留审核后的原始执行合同**  
> 审核对象：Claude 代码与数值方法审核  
> Case 身份：官方 `oscillation.c` 物理工况上的本地 CLSVOF 扩展；Basilisk 官方没有该 case 的 CLSVOF/NN `.ref`
> 正式数值结果：`dataset/oscillating_droplet/N{0064,0128}/imax03/{native,nn}/`；完整验证目录保留在 `hpc/results/oscillating_droplet/`

## 0. 先给结论

1. 当前 `Oscillating droplet` 确实是我们刚完成的 case：
   `cases/oscillating_droplet/clsvof_extension/oscillation-clsvof.c`。
2. 模型输出是**零 level set（真实界面）上的无量纲曲率**：
   
   \[
   q_{\Gamma,\mathrm{model}}=\Delta\kappa_{\Gamma,\mathrm{model}}.
   \]
3. 当前 `integral.h` 默认 `CURVATURE=1` 的 solver 插点需要的不是界面曲率，
   而是**当前受力单元中心所经过的 level-set 等值线曲率**：
   
   ```c
   double ki = distance_curvature (point, d);
   ```
4. 因此主方法必须采用仓库现有的 cell-offset 语义：
   
   \[
   q_{\rm cell}=\frac{q_\Gamma}
   {1+(d/\Delta)q_\Gamma},\qquad
   \kappa_{\rm cell}=\frac{q_{\rm cell}}{\Delta}.
   \]
5. 这个 case 还有一个不可忽略的符号差异：
   - 训练模型使用 `phi = r - R`，界面内负、外正；
   - 当前 oscillation solver 使用 `d = R(theta) - r`，界面内正、外负；
   - 所以 raw27 不能直接从 `d` 构造，必须使用 `phi_model = -d`，模型输出也必须反号回 solver 约定后再进行 cell-offset。
6. 不实施、也不恢复旧的直接替换 `q_gamma/Delta`。它只可作为数学说明，不能成为可执行 solver 方法。
7. 第一轮正式验证建议只做匹配模型的两个分辨率：
   - LEVEL 6 / N64 / `baseline_64_hgradient`；
   - LEVEL 7 / N128 / `baseline_128_hgradient`。
   当前没有 N16/N32 checkpoint，不能把 LEVEL 4/5 混入“matched-resolution NN”正式结论。
8. 证据分两层（见 §6），两层都交付但用途不同：
   - **L1 因果受控对** `CLSVOF_NN_CELL_OFFSET vs CLSVOF_NATIVE`：同一 host，唯一变量 = 曲率来源，是唯一能对 NN 曲率作因果归因的证据；
   - **L2 描述性 landscape**：standard / momentum / compressible / CLSVOF-native + NN 五方法在同一物理工况上的落点，用来展示复现广度，不做跨 solver 因果归因。
   VOF-HF 在 damping 轴上作为参考线（reference line），不是可弃背景；NN 的正向判据见 §6.4 win condition。

---

## 1. 当前权威代码与数据面

### 1.1 Host case

- CLSVOF case：
  `cases/oscillating_droplet/clsvof_extension/oscillation-clsvof.c`
- 冻结 native 数值结果：
  `dataset/oscillating_droplet/Nxxxx/imax03/clsvof/timeseries.dat`
- 官方三方法数值结果：
  `dataset/oscillating_droplet/reference/{standard,momentum,compressible}/`

Host 当前使用：

```c
#include "navier-stokes/centered.h"
#define FILTERED 1
#include "two-phase-clsvof.h"
#include "integral.h"
```

并通过：

```c
const scalar sigma[] = 1.;
d.sigmaf = sigma;
```

激活 integral surface-tension operator。

### 1.2 CLSVOF 与曲率实现

- `basilisk/src/two-phase-clsvof.h`
  - `d` 是 advected tracer；
  - VOF 在界面单元内以权重 `0.1` 将 `d` 松弛到 VOF 重构；
  - 默认 `redistance(d, imax=3, phixxmin=HUGE)`。
- `basilisk/src/integral.h`
  - 默认 `#define CURVATURE 1`；
  - `distance_curvature(point,d)` 在当前 cell center 上对 `d` 做 3×3 中心差分；
  - 默认有效调用位于 `acceleration` event 的 surface-stress tensor 组装内部；
  - 只有在 `d[]` 与某个相邻 cell 的符号跨过零 level set 时才进入受力贡献。

### 1.3 当前受支持 NN 合同

- 模型 C exports：
  `experiments/clsvof_kappa_offset_conversion/models/c_exports/baseline_{64,128,256,512}_hgradient/`
- C inference：
  `tools/clsvof_model/include/clsvof_mlp_infer.h`
- 当前 cell-offset 候选实现：
  `cases/_shared/nn_cell_curvature/src/clsvof_nn_cell_curvature.h`
- 唯一替换点生成器：
  `cases/_shared/nn_cell_curvature/src/make_overlay_integral.py`
- 现有语义说明：
  `experiments/clsvof_kappa_offset_conversion/SOLVER_K_SEMANTICS.md`

模型输入/输出合同：

```text
raw27 = phi9/Delta + nx9 + ny9
order = j:+1 -> -1, i:-1 -> +1
output = q_gamma = Delta*kappa_gamma on phi=0
dtype = float32 inference; solver conversion = double
```

---

## 2. 这个 case 的 `ki` 到底是 interface 还是 contour-line curvature

### 2.1 `integral.h` 的实际计算位置

默认 `CURVATURE=1` 分支中：

```c
if (d[]*(d[] + d[i]) < 0.) {
  double xi = d[]/(d[] - d[i]);
  ...
  double ki = distance_curvature (point, d);
  S.y.y[] += sigmai*(fabs(nx)/Delta - sign(d[])*ki*(0.5 - xi));
}
```

`xi` 是 cell 到零 level set 交点的插值位置，但 `ki` 本身仍在当前
`point`/cell center 调用 `distance_curvature()`，并没有把 stencil 投影到
`d=0` 后再求界面曲率。

因此 solver 当前语义是：

```text
ki = 当前 cell center 所在 d=constant 等值线的曲率
```

而不是：

```text
ki = 最近 d=0 界面点的曲率
```

### 2.2 为什么不能直接返回模型的界面曲率

模型预测：

\[
\kappa_{\Gamma}=\kappa(d=0).
\]

solver 需要：

\[
\kappa_{\rm cell}=\kappa(d=d_{\rm cell}).
\]

对局部平行等值线，二者关系为：

\[
\kappa_{\rm cell}
=\frac{\kappa_\Gamma}{1+d_{\rm cell}\kappa_\Gamma}.
\]

无量纲化后即：

\[
q_{\rm cell}
=\frac{q_\Gamma}{1+(d/\Delta)q_\Gamma}.
\]

直接将 `q_gamma/Delta` 塞给所有受力 cell，相当于假设所有 cell 都在
`d=0`，会产生几何位置错配；这也是仓库已经废弃 direct provider 的原因。

---

## 3. Oscillation case 特有的符号映射

### 3.1 训练符号

训练/Golden fixture 使用圆的 SDF：

\[
\phi_{\rm model}=r-R,
\]

即：

- 液滴内部 `phi_model < 0`；
- 液滴外部 `phi_model > 0`；
- 法向 `grad(phi_model)` 指向外部；
- 凸圆界面的模型曲率为正。

### 3.2 当前 oscillation solver 符号

当前 case 初始化：

```c
d[] = D/2.*(1. + 0.05*cos(2.*atan2(y,x)))
  - sqrt(sq(x) + sq(y));
```

圆形极限下：

\[
d_{\rm solver}=R-r=-\phi_{\rm model}.
\]

因此：

- 液滴内部 `d_solver > 0`；
- 液滴外部 `d_solver < 0`；
- `distance_curvature(point,d_solver)` 对凸圆返回负曲率。

不能为了迁就模型把 host 的 `d` 直接改成 `r-R`，因为
`two-phase-clsvof.h` 用 `d` 的正负初始化 `f`；直接反号会交换两相和密度身份。

### 3.3 推荐 adapter

定义：

\[
\chi=-1,\qquad
\phi_{\rm model}=\chi d_{\rm solver}=-d_{\rm solver}.
\]

raw27 必须由 `phi_model` 构建：

\[
\begin{aligned}
\phi_9/\Delta &= -d_9/\Delta,\\
n_x &= -d_x/|\nabla d|,\\
n_y &= -d_y/|\nabla d|.
\end{aligned}
\]

模型给出 `q_gamma_model` 后，先转换到 solver 符号：

\[
q_{\Gamma,\rm solver}=\chi q_{\Gamma,\rm model}
=-q_{\Gamma,\rm model}.
\]

再使用 solver 自己的：

\[
s_{\rm solver}=d_{\rm solver}/\Delta
\]

进行 offset：

\[
q_{\rm cell,solver}
=\frac{q_{\Gamma,solver}}
{1+s_{\rm solver}q_{\Gamma,solver}},
\qquad
\kappa_{\rm cell,solver}=q_{\rm cell,solver}/\Delta.
\]

圆形解析检查：

\[
\kappa_{\Gamma,solver}=-1/R,qquad d=R-r,
\]

则：

\[
\frac{-1/R}{1-d/R}=-\frac{1}{R-d}=-\frac{1}{r},
\]

与 `distance_curvature(point,d_solver)` 的 contour-line 符号和位置一致。

---

## 4. 推荐软件结构

不修改 Basilisk 正式源码，不在 `basilisk/src/integral.h` 中写条件宏。

```text
cases/oscillating_droplet/nn/
  README.md
  summary.yaml
  src/
    oscillation-nn-single-level.c
    oscillation_raw27_adapter.h
  generate/
    run_row.py
    run_canary.sh
    run_matched_matrix.sh
  analyze/
    summarize_rows.py
    plot_comparison.gp
  tests/
    test_host_contract.py
    test_sign_adapter.py
    test_raw27_golden.py
    test_overlay_unique_site.py
    test_native_single_level_equivalence.py
    test_manifest_contract.py
```

共享面继续使用：

```text
cases/_shared/nn_cell_curvature/src/
  clsvof_nn_cell_curvature.h
  kappa_offset_stats.h
  make_overlay_integral.py
```

### 4.1 共享 provider 的最小参数化

建议为共享 header 增加默认值为 `+1` 的编译期适配参数：

```c
#ifndef KAPPA_OFFSET_MODEL_PHI_SIGN
# define KAPPA_OFFSET_MODEL_PHI_SIGN 1.
#endif
```

oscillation case 在 case-local adapter 中设：

```c
#define KAPPA_OFFSET_MODEL_PHI_SIGN (-1.)
#include "clsvof_nn_cell_curvature.h"
```

共享 header 内部需要明确区分：

```text
q_gamma_model
q_gamma_solver = sign*q_gamma_model
s_solver = d_solver/Delta
q_cell_solver
```

默认 `sign=+1` 必须保持 stationary 当前行为不变。若不能证明默认路径等价，
则停止共享 header 重构，改用“共享数学核心 + oscillation case adapter”，
不能复制或改写一份新的 offset 公式。

### 4.2 唯一 overlay 插点

仍通过生成的 worktree-local `integral.h`，唯一替换：

```diff
- double ki = distance_curvature (point, d);
+ double ki = kappa_offset_provider (point, d);
```

要求：

- 原字符串在源文件中恰好出现一次；
- `CURVATURE` 必须严格等于 1；
- 不替换 `CURVATURE==2` 中预计算 `kappa[]` 的调用；
- 不重定义全局 `distance_curvature()`；
- provider 仍可调用原生 `distance_curvature()` 做只读 probe，不发生递归；
- 生成的 `integral.h`、diff 和 SHA-256 全部归档到单行结果目录。

---

## 5. 分辨率与 checkpoint 计划

当前 exports 只有：

```text
baseline_64_hgradient
baseline_128_hgradient
baseline_256_hgradient
baseline_512_hgradient
```

官方 oscillation 的四个 LEVEL 为：

| LEVEL | N | cells/D | 当前匹配 checkpoint | 第一轮身份 |
|---:|---:|---:|---|---|
| 4 | 16 | 6.4 | 缺失 | 不进入 matched formal |
| 5 | 32 | 12.8 | 缺失 | 不进入 matched formal |
| 6 | 64 | 25.6 | `baseline_64_hgradient` | canary + formal |
| 7 | 128 | 51.2 | `baseline_128_hgradient` | formal |

一个 `nn_weights.h` 是编译期静态符号，不能在当前 LEVEL 4–7 单二进制循环中
自动切换四套模型。第一轮应建立 row-isolated、single-level harness；每一行只编译
一个 matched checkpoint。

不得：

- 用 `baseline_64_hgradient` 填补 N16/N32 后仍称为 matched；
- 在同一正式表中混合 matched 与 cross-resolution/OOD 模型；
- 只因输入已用 `Delta` 无量纲化，就假设 checkpoint 与分辨率无关。

如以后需要完整 LEVEL 4–7 NN 曲线，有两个合法选择：

1. 训练并导出 `baseline_16_hgradient`、`baseline_32_hgradient`；
2. 单独定义一个跨分辨率模型，并重新建立训练/验证身份。

两者均属于后续工作，不能在本轮默认假设。

---

## 6. 实验方法与证据身份

本计划刻意区分两层证据，二者都要交付，但回答的是不同问题，绝不能混成一句话。

### 6.1 两层证据结构

| 层 | 交付物 | 回答的问题 | 性质 | 能否把差异归因给 NN 曲率 |
|---|---|---|---|---|
| L1 因果受控对 | `CLSVOF_NN_CELL_OFFSET` vs `CLSVOF_NATIVE` | NN 曲率**这一个变量**改变了什么 | 因果（其余一切相同） | 可以 |
| L2 描述性 landscape | 5 方法在同一物理工况上的落点表/图 | 各复现方法整体**落在哪** | 描述性（展示复现广度与可信度） | 不可以 |

L2 里 NN 与 standard/momentum/compressible 相差的是**整个 solver**，不是只有曲率来源；
因此 landscape 只能说明“NN 版 CLSVOF 落在哪”，不能证明“NN 曲率优于/劣于某官方方法”。
任何关于 NN 曲率作用的因果结论只能来自 L1。

### 6.2 L1：因果受控对（主结论来源）

第一轮只有两个可执行科学方法：

| 方法 ID | 曲率路径 | 角色 |
|---|---|---|
| `CLSVOF_NATIVE` | stock `distance_curvature(point,d)` | 同 host 基线 |
| `CLSVOF_NN_CELL_OFFSET` | interface NN → sign adapter → cell offset → `ki` | 待验证方法 |

因果主比较必须写成：

```text
CLSVOF_NN_CELL_OFFSET vs CLSVOF_NATIVE   （同一 host，唯一变量 = 曲率来源）
```

而不能写成 `NN vs Standard VOF-HF`（那是跨 solver 的混淆比较）。

### 6.3 L2：描述性 landscape（复现广度）

landscape 复用仓库已冻结的复现结果，把 NN 作为第 5 个方法叠加进去：

| 方法 | solver | 证据身份 | 分辨率 |
|---|---|---|---|
| Standard VOF-HF | `two-phase.h`+`tension.h` | official | 16/32/64/128 |
| Momentum | 官方 momentum 分支 | official | 16/32/64/128 |
| Compressible | 官方 compressible 分支 | official | 16/32/64/128 |
| `CLSVOF_NATIVE` | `two-phase-clsvof.h`+`integral.h` | nonofficial extension | 16/32/64/128 |
| `CLSVOF_NN_CELL_OFFSET` | 同上 + NN 曲率 | nonofficial extension | 仅 64/128（受 checkpoint 限制） |

现有 `hpc/results/oscillating_droplet/clsvof_extension/.../four_method_comparison.csv`
已经是前四个方法的 landscape；本轮只是加第 5 行，且只有 64/128 两点，不得伪装成四级曲线。

### 6.4 win condition（正向结果的判据）

从冻结 native 数据可观察到 CLSVOF 家族既有的 trade-off：

- **频率优势**：CLSVOF 在粗网格（6.4/12.8 cells/D）frequency abs error 约 `0.015%/0.048%`，
  比官方三法低一到两个数量级；
- **阻尼短板**：无粘工况（μ=0，理想 `b=0`）下 standard/momentum 随加密 `b→0`，
  而 CLSVOF 的 `b` 停在 `~0.24–0.30`、不随加密收敛。

因此 NN 的正向结果判据是：

```text
NN 把 CLSVOF 的残余 damping b（native ~0.24）压向 VOF-HF 的 ~0，
同时不牺牲 CLSVOF 已有的 frequency 优势。
```

只降低 frequency error、或以更大 `b`（更强数值耗散）换取频率更准，都不算整体正向。

### 6.5 不是正式方法

- `q_gamma/Delta` direct：已废弃，不可执行；
- `NN_PROBE_ONLY`：仅用于 canary 插入正确性，不进入最终物理比较；
- Momentum/Compressible：只进入 L2 landscape，不参与 L1 因果结论；
- Standard VOF-HF：进入 L2 landscape，并在 damping 轴上作为 CLSVOF 家族的参考线（reference line），
  既不是可弃背景，也不替代 L1 的 `CLSVOF_NATIVE`。

---

## 7. 分阶段实施计划

### Phase A：冻结 host 与静态合同

1. 记录以下 SHA-256：
   - oscillation CLSVOF host；
   - `two-phase-clsvof.h`；
   - `integral.h`；
   - shared provider、stats、overlay；
   - C inference header；
   - 两份 matched `nn_weights.h` 和 export manifest。
2. 静态断言 host 参数未漂移：
   - `D=0.2`；
   - `rho1=1, rho2=1e-3`；
   - `sigma=1`；
   - `L0=0.5`；
   - `TOLERANCE=1e-4`；
   - initial mode `0.05*cos(2 theta)`；
   - `t<=1`；
   - adapt tolerances `{5e-3,1e-3,1e-3}`；
   - native redistance `imax=3`。
3. 断言 `integral.h`：
   - `CURVATURE==1`；
   - active `ki` target 恰好一处；
   - overlay diff 除 include 和该行外没有其他修改。

**Phase A gate**：任何 host/overlay 漂移均停止，不编译 NN。

### Phase B：raw27、符号和 C/PyTorch parity

1. 保留现有通用 golden-vector test：C raw27 与训练 extractor 一致。
2. 新增 oscillation sign-adapter 解析测试：
   - 构造 `d_solver=R-r` 5×5 patch；
   - adapter 生成的 raw27 必须逐元素等于对 `phi_model=r-R` 使用训练 extractor；
   - 容差 `<=2e-7`（float32 raw features）。
3. 对 N64/N128 checkpoint 分别验证：
   - C forward 与 PyTorch forward `<=1e-6`；
   - `q_gamma_model` 为训练符号；
   - `q_gamma_solver=-q_gamma_model`。
4. 解析圆 offset test：
   - 多个 `d/Delta in [-1,1]`；
   - `kappa_cell_solver` 与 `-1/(R-d)` 一致；
   - round-trip 误差 `<1e-12`；
   - 符号全程与 native solver 一致。

**Phase B gate**：raw 顺序、`ny` 符号、曲率符号或尺度任一失败即停止。

### Phase C：native single-level 等价性

因为模型按分辨率编译，需把 host 转成 single-level row。先只运行 native：

```text
LEVEL 6 / N64
LEVEL 7 / N128
```

与已冻结 multi-level native 数据比较：

- `k-6`/`k-7` 时间点和动能严格 diff；
- `a,b,c,error,laplace` 严格 diff；
- final time、sample count、编译 flags 一致。

若严格 diff 因运行平台舍入不一致，则保留 diff，并要求：

- 时间网格一致；
- `c` 与 frequency error 只出现已解释的末位差；
- 不允许通过改拟合窗口或精度制造相等。

**Phase C gate**：single-level harness 若改变 native 物理结果，不能用于 NN 对比。

### Phase D：N64 `NN_PROBE_ONLY` t=0/首步 canary

生成只读 probe overlay：计算 native `ki` 和 NN `ki`，但返回 native `ki`。
该 run 只放在 `tem/`，不进入正式 dataset。

记录实际 evolving `d` 上的：

- raw27 finite count；
- `q_gamma_model`、`q_gamma_solver`、`q_cell_solver`；
- native `Delta*kappa`；
- sign agreement；
- denominator；
- guard/clamp；
- `d/Delta`；
- `|grad d|`；
- provider 调用所在 AMR level 直方图。

硬门：

- inference count > 0；
- NaN/Inf = 0；
- convex initial droplet 上 NN/native 曲率同号率 = 100%；
- denominator guard hits = 0；
- clamp hits = 0；
- N64 checkpoint 和权重 hash 匹配；
- probe-only 与 native 的物理输出严格一致。

NN/native 数值大小差异在此阶段只记录，不用人为阈值筛掉模型表现。

### Phase E：N64 短时 active canary

启用真实 NN `ki`，只跑到 `t=0.02`（约四分之一 shape period）：

- 完成初始化与多个 surface-tension/pressure step；
- 无 NaN/Inf；
- 无 guard/clamp hit；
- 时间单调、dt 非零；
- 动能有限；
- provider evaluations > 0；
- 保存失败现场，不自动修改 clamp、TOLERANCE、dt 或 redistance。

该 canary 只判断插入能否安全进入完整计算，不形成物理优劣结论。

### Phase F：N64 完整 paired run

从同一 runner、同一 host 生成：

```text
LEVEL6 / CLSVOF_NATIVE
LEVEL6 / CLSVOF_NN_CELL_OFFSET / baseline_64_hgradient
```

两行均运行到 `t=1`，原样保留：

```text
k-6, fit-6, error, laplace, out, log
compile stdout/stderr
provider stats
source/overlay/model hashes
```

进入 N128 的运行门：

- 两行均到达 final time；
- NN 无 NaN/Inf；
- guard/clamp hits = 0；
- `a,b,c,error,laplace` 均有限；
- 绝对 frequency error `<5%` 仅作为防灾性 canary 门，不作为论文成功阈值。

### Phase G：N128 完整 paired run

完全相同流程：

```text
LEVEL7 / CLSVOF_NATIVE
LEVEL7 / CLSVOF_NN_CELL_OFFSET / baseline_128_hgradient
```

不复用 N64 权重，不修改物理参数，不因为 N64 结果好坏改变 N128 设置。

### Phase H：汇总与绘图

正式物理指标只用官方口径，并区分主轴与附录：

主轴（用于结论）：

1. `b`：数值阻尼（无粘工况理想为 0，是本 case 真正区分方法的量）；
2. signed/absolute frequency error；
3. `a`：动能振幅；
4. `c`：动能角频率；
5. 原始 `K(t)` 动能曲线。

附录（不作主结论）：

- equivalent Laplace number：在 `b→0` 附近发散（冻结数据里 standard/momentum 的 51.2 行
  已退化为 `{…, …}` 元组），恰在方法最好时失效，故降为附录参考，不当头号指标。

Provider 指标只作为实现健康门：

- evaluations；
- guard/clamp hits；
- min absolute denominator；
- max `|d/Delta|`；
- `|grad d|` stats；
- AMR level histogram；
- sign mismatch/nonfinite counts。

推荐图：

1. **主图 A/B（L1 因果）**：N64、N128 的 `K(t)`，每个 panel 叠加 native 与 NN；
2. **damping 主图（L1 因果）**：`b_native` 与 `b_NN` 在 N64/N128 上对比，
   并叠一条 VOF-HF 的 `b` 参考线（reference line），直接读出 NN 是否把 CLSVOF 的 `b` 压向 0；
3. **频率误差图（L1 因果）**：只画 N64/N128 两点，不用两个点拟合“收敛阶”；
4. **landscape 图（L2 描述性）**：5 方法在 `b` 与 frequency-error 两轴上的落点——
   官方三法 + CLSVOF-native 各 4 级（16/32/64/128），NN 仅 64/128 两点，
   明确标注 NN 只有两点、不画四级曲线，且不据此做跨 solver 因果排名。

结论顺序：

```text
先报告 provider 是否有效且无 guard/clamp（实现门）；
再报告 L1：NN 是否把 CLSVOF 的 damping b 压向 VOF-HF 的 0，且不牺牲 frequency（win condition）；
最后给 L2：5 方法 landscape 作为复现广度背景，不做因果归因。
```

---

## 8. 数据目录与身份

### 8.1 目录结构

```text
hpc/results/oscillating_droplet/nn_matched/<run_id>/
  level_6/
    clsvof/
    nn/
  level_7/
    clsvof/
    nn/
  comparison.csv          # L1 受控对（native vs NN），逐 level
  landscape_5method.csv   # L2 描述性（复用统一口径，见 8.2）
  manifest.json
  verification.json
  RESULTS.md

figures/oscillating_droplet/nn_matched/<run_id>/
  kinetic_energy_native_vs_nn.png       # L1 主图 A/B
  damping_native_vs_nn.png              # L1 damping 主图（含 VOF-HF 参考线）
  frequency_error_native_vs_nn.png      # L1 频率误差
  landscape_b_vs_freq_5method.png       # L2 五方法 landscape
  plot_*.gp
  PLOT_NOTES.md
```

### 8.2 聚合口径统一（关键）

L2 的五方法 landscape 不得新造第三套 schema。仓库现有两套**不一致**的聚合：
`four_method_comparison.csv`（四舍五入、无 post-startup）与
`diagnostic_matched_port/.../summary.csv`（全精度、含 post-startup 拟合）。本轮以后者为 canonical：

- NN 行必须由 `diagnostic_matched_port/src/aggregate_results.py` 的同一口径产出
  （同拟合窗口、同 post-startup 处理、全精度），字段与 §9 manifest 对齐；
- `landscape_5method.csv` = 官方三法 + CLSVOF-native（沿用冻结结果）+ NN 两行，
  全部经同一聚合器，禁止混精度/混流水线；
- 若冻结的官方/native 结果无法用 canonical 聚合器重算，则在 landscape 中标注其口径来源，
  并禁止跨口径做数值排名，只作定性落点。

### 8.3 其它路径约束

Canary 和 probe-only：

```text
tem/oscillating_droplet/nn_canary/<run_id>/
```

禁止写入或覆盖：

```text
dataset/oscillating_droplet/reference/
dataset/oscillating_droplet/Nxxxx/imax03/clsvof/
```

---

## 9. 每行 manifest 必填字段

```text
case_id
method_id
evidence_level
level
N
cells_per_diameter
model_name
checkpoint_sha256
weights_sha256
export_manifest_sha256
host_source_sha256
two_phase_clsvof_sha256
stock_integral_sha256
generated_integral_sha256
overlay_sha256
shared_provider_sha256
oscillation_adapter_sha256
feature_order = phi9+nx9+ny9
raw27_order = j:+1..-1, i:-1..+1
model_phi_sign = outside_positive
solver_d_sign = inside_positive
solver_to_model_sign = -1
model_output = Delta*kappa_gamma_model
solver_output = kappa_cell_solver
nn_provider = cell_offset
denominator_guard = 0.25
clamp_factor = 1.0
redistance_imax = 3
compile_command
compiler_output
start/end/wall_time
final_time
provider_stats
raw_artifact_hashes
```

---

## 10. 验收与停止条件

### 10.1 实现验收

- overlay 只替换一个 active `ki`；
- Basilisk 正式源码哈希不变；
- default sign `+1` 的 shared provider 通过 stationary 回归；
- oscillation sign `-1` 的 raw27 通过 training golden test；
- C/PyTorch forward parity 通过；
- interface-to-contour 解析公式通过；
- native single-level equivalence 通过。

### 10.2 运行验收

- N64/N128 paired rows 全部到 `t=1`；
- model 与 row resolution 匹配；
- provider evaluations > 0；
- NaN/Inf = 0；
- denominator guard hits = 0；
- clamp hits = 0；
- `k/fit/error/laplace/out/log` 完整；
- 失败行保留原始现场，不调参重跑制造成功。

### 10.3 科学解释边界

- NN 比 native 频率误差小：只能说明该 observable 改善；
- NN 的 `b` 更大：说明数值耗散更强，即使频率更准也不能称整体更好；
- 整体正向的判据见 §6.4 win condition：NN 需把 `b` 压向 VOF-HF 的 ~0 且不牺牲 frequency，二者缺一不算赢；
- L2 landscape 只作描述性落点：不得据其宣称“NN 曲率优于某官方 solver”，跨 solver 差异不能归因给曲率（见 §6.1）；
- provider 健康门通过：只证明插入/尺度/几何位置合法，不证明模型物理表现优越；
- N64/N128 两点不足以声明收敛阶；
- CLSVOF NN 仍不是官方 oscillation 方法或官方 `.ref`。

### 10.4 立即停止条件

- raw27 任一方向/符号与训练 extractor 不一致；
- NN/native 初始凸界面曲率出现符号错配；
- guard 或 clamp 非零；
- single-level native 不能复现冻结 native；
- 运行出现 NaN、dt collapse 或未到 final time；
- 为修复失败需要修改物理参数、TOLERANCE、redistance 或拟合窗口。

---

## 11. 不做的事情

- 不修改官方 `oscillation.c`、`.ref` 或 `integral.h`；
- 不把 CLSVOF/NN 写入 official reproduction；
- 不恢复 direct `q_gamma/Delta`；
- 不将 interface NN 直接广播到所有 contour-line force cells；
- 不在没有 N16/N32 checkpoint 时伪造四级 matched NN 曲线；
- 不增加面积、SDF、界面相位等指标到主物理结论；
- 不用 probe/offline MSE 代替最终 `a,b,c,error,laplace,K(t)`；
- 不因为 NN 结果不理想而修改官方拟合精度或参考值。

---

## 12. 请 Claude 重点审核的问题

1. **曲率位置判断**：是否同意默认 `CURVATURE=1` 的 `ki` 是 current-cell contour-line curvature，而不是 interface curvature？
2. **符号推导**：是否同意 oscillation 的 `d=R-r` 与训练 `phi=r-R` 相反，必须同时反转 raw27 的 `phi/nx/ny` 和模型曲率输出？
3. **offset 公式**：在 solver 符号下，
   `q_cell_solver=q_gamma_solver/(1+(d_solver/Delta)*q_gamma_solver)` 是否与 `-1/(R-d)` 圆解析解一致？
4. **唯一插点**：是否同意只替换 line-level `double ki = distance_curvature(point,d);`，而不重定义全局函数或触碰 `CURVATURE==2`？
5. **shared/provider 边界**：建议的 default `sign=+1` 参数化是否足够安全，还是应拆成共享 core + case adapter？
6. **分辨率范围**：是否同意第一轮正式 scope 只能是 matched N64/N128，而 LEVEL 4/5 等待 N16/N32 模型？
7. **native 等价门**：single-level runner 是否必须先逐文件复现 frozen multi-level native，再允许 NN paired comparison？
8. **结果主线**：是否同意 §6 的两层结构——L1 `CLSVOF NN vs CLSVOF native` 为因果主线，
   L2 五方法 landscape（含 VOF-HF 作 damping 参考线）为描述性背景，且 landscape 不做跨 solver 因果归因？

Claude 审核后已按上述 gate 实施；正式矩阵、验收和物理解释见本页顶部所列结果目录。
