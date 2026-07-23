# 归档：stationary_bubble imax=0 旧一代数据 (2026-07-16)

这些是 07-16 旧 runner 产出的 imax=0 运行，均未跑满 tau=1：

| 格子 | t_final | 说明 |
|---|---|---|
| N64  clsvof | 0.0649 | 发散终止 |
| N64  nn     | 0.2050 | 发散终止 |
| N128 clsvof | 0.0410 | 发散终止 |
| N128 nn     | 0.1237 | 发散终止 |

特征：6 位有效数字输出、无 termination.csv。
与 N256 imax0（07-21 新 runner，完整双精度、有 termination.csv、跑满 tau=1）不同代，不可直接比较。

于 2026-07-21 归档，原位置由新 runner 重跑结果取代。
保留原因：这是"imax=0 在旧代码下发散"的原始证据。
