# 规则迎浪升沉--纵摇 Gate 2 阶段报告

## 结论

机器验收状态：**FAIL**（17/20）。

本次计算首次将冻结的 `(heave, pitch)` 矩阵契约、Faltinsen Eq. 9.110--9.117 非零波浪激励、Eq. 9.119 复数运动方程、刚体点加速度和 `solve_ivp` 小波幅复算放在同一条可追溯路径中。计算未使用响应倍率、参考值反推或逐点拟合。

## 数值闭合

- 三个航速：`Fn_B=2, 3, 4`；每个航速 25 个频率点。
- 最大复数方程相对残差：`5.894e-15`。
- 最大频域--时域幅值误差：`2.070e-15`。
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
- Fridsma 线性长波子集主峰是否全部夹持（仅作稀疏数据诊断）：`False`。
- 全测量范围主峰频率最大相对误差（含非线性共振，仅作诊断）：`27.816%`。
- 艏部加速度是试验中的非线性冲击峰值，本阶段完整输出并保留误差，但不以线性谐波幅值冒充冲击峰值通过项。

## Begovic 规则波密集独立对照

Begovic 原始试验的单体滑行艇 EFD 数据由 Kahramanoglu 等（2020）Figures 6--8 重新发表。本验收从冻结 PDF 的红色三角试验标记自动数字化，三航速各 8 个波长点；源 PDF、内嵌图像、坐标标定、候选像素和数字化不确定度均可追溯。`kA>0.055` 的点保留在全表中但不参加线性幅值统计。

三航速的运行纵倾采用 Begovic 等（2014）Table 3 实测值，龙骨湿长采用 Javaherian（2021）Table 5.2 对 Begovic 和 Bertorello（2012）试验值的逐点抄录。二者仅用于重建试验运行状态，不含任何运动响应信息；程序不再用遗漏拖曳力矩的静水平衡替代已知试验状态。原表 sinkage 因垂向基准与符号定义不足，仅保留为诊断字段，未参与坐标换算。

| scope | metric | eligible_point_count | median_relative_error | nrmse | status |
| --- | --- | --- | --- | --- | --- |
| Begovic EFD kA<=0.055 | heave_motion | 21 | 0.29789406 | 0.84398338 | FAIL |
| Begovic EFD kA<=0.055 | pitch_motion | 21 | 0.34159734 | 0.81659482 | FAIL |

| configuration | metric | peak_is_resolved | computed_peak_is_interior | peak_frequency_relative_error | status | reason |
| --- | --- | --- | --- | --- | --- | --- |
| FnB=1.67 | heave | True | True | 0.13917841 | FAIL | experimental peak is bracketed and uncertainty-resolved |
| FnB=1.67 | pitch | False | True | 0.52387503 | UNRESOLVED | experimental maximum is at the measured-range boundary |
| FnB=2.26 | heave | False | True | 0.24025046 | UNRESOLVED | experimental peak prominence does not exceed digitization uncertainty |
| FnB=2.26 | pitch | True | True | 0.14752586 | FAIL | experimental peak is bracketed and uncertainty-resolved |
| FnB=2.82 | heave | True | True | 0.30789917 | FAIL | experimental peak is bracketed and uncertainty-resolved |
| FnB=2.82 | pitch | True | True | 0.31875907 | FAIL | experimental peak is bracketed and uncertainty-resolved |

- 可用于硬验收的主峰：`4` 个，覆盖 `3` 个航速和 `2` 类运动。
- 已解析主峰最大频率相对误差：`31.876%`，限值为 `10%`。
- 试验边界最大值或峰高不超过数字化不确定度的宽平台均标为 `UNRESOLVED`，不伪装成通过项。

## 未通过项

| check | evidence |
| --- | --- |
| begovic_heave_experiment_accuracy | Begovic kA<=0.055: median relative error <=15% and NRMSE <=20%. |
| begovic_pitch_experiment_accuracy | Begovic kA<=0.055: median relative error <=15% and NRMSE <=20%. |
| begovic_peak_frequency_accuracy | max resolved-peak error=0.31876, limit=0.10; every hard resolved peak must pass. |

## 边界

本阶段只处理小幅规则迎浪升沉--纵摇。当前 Faltinsen Chapter 9 紧凑模型采用关于稳态滑行姿态的高频附加质量和动升力阻尼近似；若 Begovic 主峰门槛失败，下一步应补齐与滑行基流相容的频率相关辐射、前进速度交叉项和波浪激励分解。不得直接叠加不相容的排水型 2.5D 阻尼矩阵，也不得加入经验响应倍率。Fridsma 的冲击峰值和强非线性范围留待后续 2D+t 阶段。
