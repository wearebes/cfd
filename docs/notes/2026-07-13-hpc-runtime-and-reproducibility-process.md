# Ubuntu HPC 正式矩阵运行与可复现流程

更新时间：2026-07-13  
适用仓库：`cfd-hpc`  
当前正式 matrix ID：`formal_180_epyc9654_32c_pack4_001`

## 1. 目标

本流程的目标是在一台 Ubuntu 22.04 x86_64 服务器上，以 OpenMP 运行完整 CFD 实验矩阵，并保证：

- 每个实验 row 的代码、模型、参数和平台身份可追溯；
- SSH 断开后实验继续运行；
- 已完成结果不会被静默覆盖；
- 中断后可以严格校验并恢复；
- formal、smoke、canary 和临时 work 不混合；
- 最后交付一个经过完整性验证、带 SHA-256 清单的 `tar.gz`。

这里的可复现不是“相似配置重新跑一次”，而是要求源码、权重、runner、线程 policy、matrix identity 和结果文件哈希能够逐项核对。

## 2. 正式科学矩阵

当前矩阵共 180 行：

| benchmark | resolution | method | imax | 行数 |
|---|---|---|---|---:|
| capwave | 64、128、256、512 | native、NN cell-offset | 0–5 | 48 |
| rising bubble Case 1 | 64、128、256、512 | native、NN cell-offset | 0–5 | 48 |
| rising bubble Case 2 | 64、128、256、512 | native、NN cell-offset | 0–5 | 48 |
| stationary bubble | 64、128、256 | native、NN cell-offset | 0–5 | 36 |
| 合计 | — | — | — | **180** |

约束：

- `imax` 只允许 0–5；
- native 和 NN cell-offset 都运行同一组 `imax`；
- rising Case 1 与 Case 2 使用独立 benchmark identity 和结果目录；
- stationary N512 不属于本矩阵，并由生成器和矩阵类型共同拒绝；
- 当前 matrix 启动后，不再修改科学参数、源码、权重或线程 policy。

## 3. 部署包边界

Git/部署包只传输运行实验必需的内容：

- 锁定的 Basilisk 源码；
- `cases/`；
- native 和 NN cell-offset 生成器；
- 四个分辨率对应的 C 权重头；
- 共享 C inference / curvature 头；
- `hpc/` runner、矩阵定义、线程 policy、preflight、canary 和测试；
- provenance lock 和操作文档。

不传输：

- macOS ARM `qcc`；
- `*.o`、`*.a`、Mach-O 文件；
- `.qcc/` 和编译缓存；
- work、smoke、canary 临时结果；
- formal dataset；
- `.DS_Store` 和其他本地缓存。

`qcc` 必须在服务器上的最终 clone/extract 路径中重新构建。构建完成后不要移动仓库，因为 Basilisk 构建过程可能记录最终绝对路径。

## 4. 新服务器上的复现顺序

### 4.1 获取代码

服务器上将仓库放到最终位置，例如：

```bash
cd /root
git clone <private-repository-url> cfd
cd /root/cfd
```

或者上传经过校验的 deployment tar 包并解压到 `/root/cfd`。

### 4.2 Bootstrap

```bash
bash hpc/bootstrap_ubuntu.sh
```

bootstrap 负责：

- 安装固定的 Ubuntu 构建/运行依赖；
- 将 `basilisk/src/config` 指向相对的 `config.gcc`；
- 从源码构建本机 ELF x86_64 `qcc`；
- 保持幂等，重复运行不会破坏已完成环境。

构建后至少核对：

```bash
test -x basilisk/src/qcc
file basilisk/src/qcc
readlink basilisk/src/config
```

正确结果应是 Linux ELF x86_64 `qcc` 和相对目标 `config.gcc`。

### 4.3 Preflight

preflight 在花费大量计算时间之前检查：

- Ubuntu/x86_64 平台；
- 可见 CPU 和 CPU affinity；
- OpenMP 编译与运行；
- RAM 和磁盘；
- Basilisk `qcc`；
- provenance lock 中源码、权重、头文件和生成器哈希；
- 180行 dry-run 的数量与唯一 row ID；
- `imax` 边界；
- 三个 benchmark 的基本编译/运行能力。

preflight 或 provenance 不通过时，不允许启动正式矩阵。

### 4.4 Canary

canary 只用于验证平台能力和线程策略，结果不进入 formal dataset。它记录：

- 不同 OpenMP 线程数是否真实生效；
- 短时编译和运行时间；
- 可用 CPU 列表；
- 容量报告和建议 policy；
- rising Case 1/2 native/NN 是否都达到规定的 `t=3`。

canary 通过后才运行 formal N64。

## 5. 一条命令启动正式实验

当前32核服务器使用：

```bash
bash hpc/submit_matrix.sh \
  --cpus 32 \
  --matrix-id formal_180_epyc9654_32c_pack4_001 \
  --policy hpc/config/thread_policy_32.json \
  --max-active-rows 4 \
  --resume
```

正式运行放在 tmux 后端：

```bash
tmux new-session -d -s cfd180 \
  "cd /root/cfd && bash hpc/submit_matrix.sh \
   --cpus 32 \
   --matrix-id formal_180_epyc9654_32c_pack4_001 \
   --policy hpc/config/thread_policy_32.json \
   --max-active-rows 4 \
   --resume 2>&1 | tee /root/autodl-tmp/cfd-runtime/formal_180_epyc9654_32c_pack4_001.submit.log"
```

启动后可直接断开 SSH。tmux 会继续运行。

## 6. 32核 pack4 调度策略

`--max-active-rows 4` 表示最多允许4个 row 同时存在，但实际并发由32核 CPU池和每个 row 的线程数共同决定。

| benchmark / resolution | 每行线程数 | 最大实际并发 |
|---|---:|---:|
| capwave、rising N64 | 8 | 4行 |
| stationary N64 | 16 | 2行 |
| capwave、rising N128 | 16 | 2行 |
| stationary N128 | 32 | 1行 |
| capwave、rising N256 | 32 | 1行 |
| capwave、rising N512 | 32 | 1行 |
| stationary N256 | 32 | 1行 |

每个活动 row：

- 获得独占 CPU ID 列表；
- 使用 `taskset`/affinity 和 OpenMP 线程绑定；
- 不与其他 row 使用同一个已分配核心；
- 完成后释放 CPU，调度器再装入下一个 row。

因此 stationary N256 只看到一个仿真进程并不表示只用了一个核心。当前实测该进程有32个 OpenMP 线程，CPU使用率约3182%，已经使用全部32核额度。

## 7. 两阶段正式运行

### 阶段一：N64验收

先运行全部48个 N64 row：

- capwave 12行；
- rising Case 1 12行；
- rising Case 2 12行；
- stationary 12行。

N64不是废弃 canary，而是正式 dataset 的组成部分。只有48行全部完成并通过完整性检查，才进入 remaining 阶段。

### 阶段二：remaining

剩余132行按照估计成本从长到短排序。调度器优先运行 stationary N256 等长任务，再逐步处理其他分辨率。

这种 LPT 策略的目标是：

- 尽早暴露最昂贵任务的真实耗时；
- 避免最后只剩一个超长 row；
- 小任务可以在存在空余 CPU 时装箱；
- 不让多个 row 争抢同一核心。

## 8. 单个 row 的生命周期

每个正式 row 按以下顺序执行：

1. 根据 row ID 解析 benchmark、method、resolution 和 `imax`；
2. 验证 matrix ID、policy SHA-256、源码和模型身份；
3. 创建唯一 attempt work 目录；
4. 生成单分辨率 Basilisk 源码；
5. 使用本机 `qcc` 和指定 OpenMP 线程编译；
6. 在绑定的 CPU 列表上运行；
7. 检查程序返回码和 benchmark 终点；
8. 计算主要输出的 SHA-256、字节数和行数；
9. 写入 manifest；
10. 在同一文件系统中从 staging 原子发布到正式目录；
11. 成功后清理编译 work，失败时保留 work 诊断。

正式目标已经存在时，runner 不会自动覆盖。

## 9. Manifest 与 provenance

每个正式结果的 manifest 至少记录：

- matrix ID；
- row ID；
- benchmark 和 rising case；
- method；
- resolution 和实际网格；
- `imax`；
- 模型名称；
- policy SHA-256；
- CPU线程数和CPU列表；
- 平台信息；
- 运行耗时；
- 源码、权重、生成头和主要数据文件的 SHA-256；
- 文件字节数和行数。

仓库级 provenance lock 用于证明服务器使用的科学源码、模型权重、共享头和主要 runner 与部署时一致。

## 10. 严格 Resume

中断后使用同一个 matrix ID、同一个线程 policy 和 `--resume`：

```bash
bash hpc/submit_matrix.sh \
  --cpus 32 \
  --matrix-id formal_180_epyc9654_32c_pack4_001 \
  --policy hpc/config/thread_policy_32.json \
  --max-active-rows 4 \
  --resume
```

resume 只有在以下条件全部满足时才跳过 row：

- manifest identity 与期望 row 完全一致；
- matrix ID 一致；
- policy SHA-256 一致；
- 所有必需输出存在；
- 所有输出重新计算的 SHA-256 与 manifest 一致。

下列情况会报错，而不是自动覆盖：

- 文件缺失；
- 哈希错误；
- manifest 身份错误；
- 残留 staging；
- 同一 row 已有不可信正式目录；
- 使用新 policy 恢复旧 matrix ID。

如果需要改变源码、权重、科学参数或 policy，必须建立新的 matrix ID。

## 11. 运行中监控

监控只读，不修改或重启任务。常用检查：

```bash
tmux ls
tmux capture-pane -pt cfd180 | tail -n 40
```

```bash
cat hpc/results/formal_180_epyc9654_32c_pack4_001/scheduler_n64.json | jq
cat hpc/results/formal_180_epyc9654_32c_pack4_001/scheduler_remaining.json | jq
```

```bash
find hpc/results/formal_180_epyc9654_32c_pack4_001 \
  -name manifest.json -type f | wc -l
```

```bash
ps -eo pid,etimes,nlwp,%cpu,rss,cmd \
  | grep -E 'stationary-clsvof|rising-clsvof|capwave-clsvof|run_row.py'
```

```bash
grep -En 'Traceback|error:|failed_runtime|failed_validation|"status": "FAIL"' \
  /root/autodl-tmp/cfd-runtime/formal_180_epyc9654_32c_pack4_001.submit.log
```

主要健康信号：

- `tmux cfd180` 存在；
- scheduler 的更新时间继续变化；
- active row 对应的 OpenMP 线程数正确；
- manifest 数量只增加不减少；
- 没有失败标记和残留 staging；
- 内存和磁盘保持安全。

## 12. 当前实测快照

2026-07-13 23:06 的只读审计：

| benchmark | 总行数 | 已完成 | 运行中 | 未开始 |
|---|---:|---:|---:|---:|
| capwave | 48 | 12 | 0 | 36 |
| rising Case 1 | 48 | 12 | 0 | 36 |
| rising Case 2 | 48 | 12 | 0 | 36 |
| stationary bubble | 36 | 14 | 1 | 21 |
| 合计 | 180 | **50** | **1** | **129** |

已完成的两行 stationary N256 实测：

- native N256 `imax=5`：3小时24分39秒；
- native N256 `imax=4`：3小时18分37秒。

当前运行 native N256 `imax=3`。没有发现失败或 staging 残留。

基于目标服务器长任务实测，剩余时间估计为35–50小时，中心约41小时。该快照只用于进度判断，不改变正式实验定义。

## 13. 完成门禁

只有满足以下条件，矩阵才算完成：

- 180个唯一 row 全部存在；
- 每个 row 的 manifest identity 正确；
- native/NN、case、resolution、`imax` 组合完整；
- stationary N512 不存在；
- 所有主要输出的哈希重新验证通过；
- 没有 staging 或失败 work 被误认为 formal；
- matrix-level manifest 和 timing/status 表生成成功。

完成验证由：

```bash
python3 hpc/verify_matrix.py \
  --matrix-id formal_180_epyc9654_32c_pack4_001 \
  --phase all \
  --policy hpc/config/thread_policy_32.json
```

执行。

## 14. 最终结果打包

完整验证通过后运行：

```bash
bash hpc/collect_results.sh \
  formal_180_epyc9654_32c_pack4_001 \
  hpc/config/thread_policy_32.json
```

预期生成：

```text
hpc/packages/cfd_hpc_180_formal_180_epyc9654_32c_pack4_001.tar.gz
hpc/packages/cfd_hpc_180_formal_180_epyc9654_32c_pack4_001.tar.gz.sha256
```

下载前在服务器验证：

```bash
sha256sum -c \
  hpc/packages/cfd_hpc_180_formal_180_epyc9654_32c_pack4_001.tar.gz.sha256
```

下载到本地后再次验证 SHA-256。最终压缩包才是正式交付物；服务器上的 work、canary 和 smoke 不属于交付数据。

## 15. 从最终包复查与复现

在另一台机器上复查时：

1. 校验 tar.gz SHA-256；
2. 解压到新目录；
3. 检查 matrix-level manifest；
4. 统计180个唯一 row；
5. 按 manifest 重新计算所有主要文件哈希；
6. 核对源码、模型、policy 和平台 provenance；
7. 如需数值复现，在新的 Ubuntu 22.04 x86_64 环境重新 bootstrap；
8. 使用相同 matrix ID定义、相同 policy 和相同科学输入重新运行；
9. 将数值结果比较与字节级哈希复现分开解释。

不同 CPU、编译器或并行归约顺序可能造成浮点末位差异，因此：

- 同一次正式运行的文件完整性使用 SHA-256；
- 跨机器科学复现使用预先定义的数值容差和物理指标；
- 不把跨平台浮点末位差异误判为科学结论变化。

## 16. 当前不应做的操作

正式矩阵运行期间不要：

- 修改源码或权重；
- 修改 `thread_policy_32.json`；
- 修改 `tau_max`、终止条件或 `imax` 范围；
- 移动 `/root/cfd`；
- 手工覆盖正式结果目录；
- 把 smoke/canary 复制进 formal 目录；
- 用新的 matrix ID伪装恢复当前任务；
- 根据行数百分比直接线性推算耗时。

## 17. 流程总结

完整链路是：

```text
干净代码/部署包
  → Ubuntu本机构建qcc
  → provenance与环境preflight
  → OpenMP和benchmark canary
  → N64正式48行验收
  → remaining按LPT和线程policy调度
  → row级staging、验证、原子发布
  → 严格resume
  → 180行全矩阵验证
  → tar.gz与SHA-256
  → 本地二次校验和归档
```

当前第一台服务器严格按照这条链路运行。未来任何新算例应使用独立 experiment identity、独立 matrix ID 和独立结果包，不改变正在运行的180行。
