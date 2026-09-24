# 规则迎浪升沉--纵摇 Gate 2 阶段报告

## 结论

机器验收状态：**FAIL**（16/18）。

本次计算首次将冻结的 `(heave, pitch)` 矩阵契约、Faltinsen Eq. 9.110--9.117 非零波浪激励、Eq. 9.119 复数运动方程、刚体点加速度和 `solve_ivp` 小波幅复算放在同一条可追溯路径中。计算未使用响应倍率、参考值反推或逐点拟合。

## 数值闭合

- 三个航速：`Fn_B=2, 3, 4`；每个航速 25 个频率点。
- 最大复数方程相对残差：`1.663e-15`。
- 最大频域--时域幅值误差：`1.863e-15`。
- 最大频域--时域相位误差：`1.705e-13 deg`。
- 最大波幅线性比偏差：`0.000e+00`。
- 最大点加速度运动学残差：`0.000e+00`。

## Fridsma 1969 独立对照

独立数据直接抄录自 Davidson Laboratory Report 1275 的 Table 1 和 Table 2，不是二手曲线拟合。A/B 两个航速共 11 组完整升沉、纵摇和加速度点；所有短波和共振点均保留在对照表中。

| metric | eligible_point_count | median_relative_error | nrmse | status |
| --- | --- | --- | --- | --- |
| heave_motion | 4 | 0.082281942 | 0.10611293 | PASS |
| pitch_motion | 4 | 0.12698251 | 0.13601386 | PASS |

- 线性长波范围相位中位循环误差：`13.970 deg`。
- 线性长波范围重心加速度 NRMSE：`23.620%`。
- 线性适用区主峰是否被有效频点夹持：`False`；未夹持时不计算为验收通过。
- 全测量范围主峰频率最大相对误差（含非线性共振，仅作诊断）：`27.816%`。
- 艏部加速度是试验中的非线性冲击峰值，本阶段完整输出并保留误差，但不以线性谐波幅值冒充冲击峰值通过项。

## 未通过项

| check | evidence |
| --- | --- |
| linear_scope_peak_frequency_resolved | Each experimental peak must be bracketed by at least three eligible points and lie inside the predeclared linear scope. |
| linear_scope_peak_frequency_accuracy | max=0.00000, limit=0.10; evaluated only when every peak is resolved. |

## 边界

本阶段只处理小幅规则迎浪升沉--纵摇。Fridsma 在 `lambda/L=2--3` 附近明确报告波高非线性和尖峰加速度；若全范围峰值门槛失败，应进入非线性恢复力、瞬时湿面和 2D+t 冲击载荷改进，而不是加入经验响应倍率。
