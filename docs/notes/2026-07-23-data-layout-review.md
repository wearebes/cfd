# Canonical `data/` 架构审核稿

状态：用户已接受目录方案；新路径和共享 provenance 已实施。旧 `dataset/`
不迁移，formal 未运行；30 项 smoke 只在静态检查通过后运行，并继续等待用户与
Claude 审核。

## 1. 已确认的边界

- 新实验统一写入新的 `data/` 根目录；旧 `dataset/` 只作历史记录，不混跑、不覆盖。
- 数据集使用科学身份命名，不使用时间戳：`vof_clsvof_nn_benchmarks_v1`。
- smoke 与 formal 物理隔离；smoke 用来审核正式产物形态，不能被 formal 续跑。
- 完整 formal 为 312 项：24 VOF-HF、144 CLSVOF、144 NN。
- smoke 为 30 项：五个物理分支的 N32/N64，VOF-HF/CLSVOF/NN 各 10 项。
- VOF-HF 没有 `imax`；CLSVOF/NN 才进入 `imax00`--`imax05` 配对目录。
- 每行保留原始科学数据、`metrics.csv`、`plot_data.csv`、manifest、逐文件哈希和必要日志；不复制生成脚本。

## 2. 推荐的 case-centered 目录

```text
data/
├── _smoke/
│   └── vof_clsvof_nn_benchmarks_v1/
│       └── ...                         # 与 formal 同构，仅有 N32/N64、imax03
└── vof_clsvof_nn_benchmarks_v1/
    ├── READY.json
    ├── _campaign/
    │   ├── campaign.json
    │   ├── rows.csv
    │   └── logs/
    ├── _provenance/
    │   ├── source_lock.json
    │   ├── object_index.json
    │   ├── objects/sha256/<hash>       # 每个唯一源码/overlay 只存一次
    │   ├── references/
    │   │   └── prosperetti.h
    │   └── models/
    │       └── baseline_<N>_hgradient/
    │           ├── export_manifest.json
    │           └── nn_weights.h
    ├── capwave/
    │   └── Nxxxx/
    │       ├── VOF-HF/
    │       └── imaxNN/{CLSVOF,NN}/
    ├── rising_bubble/
    │   └── caseK/Nxxxx/
    │       ├── VOF-HF/
    │       └── imaxNN/{CLSVOF,NN}/
    ├── stationary_bubble/
    │   └── Nxxxx/
    │       ├── VOF-HF/
    │       └── imaxNN/{CLSVOF,NN}/
    └── oscillating_droplet/
        └── Nxxxx/
            ├── VOF-HF/
            └── imaxNN/{CLSVOF,NN}/
```

推荐 case-centered 而不是单独的顶层 `VOF-HF/<case>/`，因为一次分析通常先选 case 和 N，再比较三种方法。VOF-HF 仍通过 `experiment_role=official_reference`、`imax=null` 保持独立，不会被误作 CLSVOF/NN 的第三个配对成员。

## 3. 每行最小公共结构

```text
<row>/
├── manifest.json
├── scientific_artifacts.json
├── metrics.csv
├── plot_data.csv
├── case 原始科学文件
├── provider_stats.csv              # 仅 NN
├── compile.stdout
├── compile.stderr
└── case runtime/stdout log
```

`manifest.json` 直接记录 `_provenance` 对象路径、SHA-256、Git commit、命令、环境、方法、网格、角色和 `analysis_ready`；不再保留 312 份可见的 `source_snapshot/`。`scientific_artifacts.json` 只锁定科学原始文件、metrics 和 plot-ready 文件。

日志沿用 runner/benchmark 的稳定文件名并放在行根目录，避免移动后破坏 manifest
中已锁定的 stdout/stderr 路径；三种方法的公共日志仍是 `compile.stdout` 与
`compile.stderr`，运行日志名称按 case 保留。

## 4. 不应重复或长期保留的内容

- NN 权重和 export manifest：每个 N 在 `_provenance/models/` 保存一次。
- `prosperetti.h`：在 `_provenance/references/` 保存一次。
- 相同 stock 源码、共享 header、生成 overlay：按内容哈希保存一次，由 manifest 引用。
- 生成脚本：只保留在 Git 仓库，不进入数据行。
- 编译产物、临时工作目录、checkpoint dump：不进入长期数据。
- oscillating 的 `VOF-HF_report.json`、`VOF-HF_RESULTS.md`、`verification.json` 三份状态摘要彼此重复；建议 formal 行只保留 manifest、metrics、严格 diff，smoke 审核报告改为 campaign 级一份。

## 5. 不能为了简洁删除的内容

- 原始 benchmark 通道：否则无法重算 metrics 或检查后处理错误。
- `metrics.csv`：带单位、定义、时间、来源和 origin，供汇总与审稿。
- `plot_data.csv`：三种方法同 case 同 schema，供后续直接画图。
- `scientific_artifacts.json`：锁定 required metrics、plot columns、文件大小与哈希。
- 编译/runtime stderr：用于解释平台警告、拟合失败和运行异常。
- stationary 的 `milestones.csv`/`termination.csv`、rising 的 `circularity.csv`、oscillating 的完整拟合通道。

## 6. 现场重复证据

当前 `dataset/_generate_rebuild` 只有 42 条旧 capwave 行，总计约 32 MiB，其中 42 份 `source_snapshot/` 约 28 MiB。`two-phase-clsvof.h`、`integral.h`、`prosperetti.h` 和生成 case 各重复 42 次，NN 权重及推理 header 各重复 21 次。共享 provenance 对正式 312 项不是美化，而是主要的结构和空间优化。

## 7. 实施与审核顺序

1. 已固定 case-centered 路径和数据集名称。
2. campaign 启动时建立 `_provenance`，行 manifest 只引用共享对象。
3. `verify_pairs` 读取 manifest 中已锁定的 redistance overlay 哈希，不再读取行内 snapshot；capwave 的 `prosperetti.h` 改为共享 reference 引用，并将 scientific contract 升级为 schema 2。
4. `job.sh layout` 只读输出已接受目录树；`plan` 使用 312 项新路径。
5. 静态测试所有路径、引用、哈希和恢复规则。
6. 静态检查通过后只运行 30 项 smoke 到 `data/_smoke/...`。
7. 用户与 Claude 审核 smoke；不自动提交，不启动 formal。
8. 审核通过后提交完整版本，再由用户明确授权 formal。
