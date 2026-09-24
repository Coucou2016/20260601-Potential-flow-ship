# 下一阶段目标与验收条件：线性 2.5D Gate 1 硬验证通过

日期：2026-08-02

## 1. 阶段定位

本阶段服务于《高速船型运动预报系统总体目标》，承接上一阶段 `Eq.31/Eq.32` 公式级输运诊断结果。上一阶段已经把 Ma 2005 Wigley III 八系数失败源定位到具体公式链路，但尚未使八系数全部通过。因此，本阶段目标从“诊断封口”推进到“方程级修正落地”。

本阶段仍只聚焦线性高速 `2.5D` 核心，不扩展非线性 `2D+t`、双体船、三体船或水翼生产模型。

## 2. 阶段目标

完成 Ma-Duan-Song 型线性高速 `2.5D` 求解器的方程级修正，使 Ma 2005 Wigley III 八个水动力系数在默认 `matched_bie_station_sweep` 路径下全部通过 Gate 1；若仍不能全部通过，则必须把剩余失败项压缩到明确的、不可由当前资料解决的理论或数据缺口。

本阶段的核心不是增加更多候选，而是把已有诊断中确认的主阻塞项逐一转化为可验证的默认实现：

1. `B33/A35/B35`：处理 zero-`m3` 行中分布式几何输运与 `Eq.31/Eq.32` 转换的闭合问题。
2. `A33/A53`：处理开放剖面 body potential 到时间压力的尺度链路问题。
3. `A55/B55`：处理 pitch row 中 `N5/m5`、力臂、Stokes body moment、pressure-gradient moment 与 end-contour moment 的一致性问题。

## 3. 工作范围

1. 从公式层推导并实现固定控制面映射下的分布式几何输运项，替代上一阶段的系数级 delta 候选。
2. 对 heave 时间压力链路建立独立二维剖面 radiation pressure 校核，确认 body potential 尺度、压力符号、归一化和广义力行。
3. 对 pitch row 建立统一的 `N5/m5`、力臂、端部矩和整船装配实现，消除只在局部候选中改善的符号/尺度歧义。
4. 将通过验证的方程级修正接入默认 `LinearFrequencyProvider(source="linear_2p5d", formulation="matched_bie")` 路径。
5. 保留所有旧候选诊断输出，用于证明新默认路径不是经验拟合或单系数调参。
6. 重新运行示例运动预报，确认修正后的水动力核心不破坏配置读取、六自由度输出、规则波/不规则波时域响应和可视化链路。

## 4. 暂不纳入本阶段

1. 不实现生产级非线性 `2D+t` 自由面边界元。
2. 不实现双体船、三体船共同边界积分。
3. 不实现水翼控制与水翼-船体耦合。
4. 不用经验比例系数、按参考值反推系数、全局最小二乘拟合或单项后处理差值替代方程修正。

## 5. 可验收条件

| 类别 | 验收条件 |
|---|---|
| 默认路径 | `LinearFrequencyProvider(source="linear_2p5d", formulation="matched_bie")` 默认路径可运行，且验证输出中 `provider_route` 全部为 `matched_bie_station_sweep`。 |
| 方程级修正 | 新实现必须落在压力恢复、几何输运、body potential、`N_i/m_i` 或 end-contour 装配等方程位置，不允许只在最终系数上加修正量。 |
| zero-`m3` 闭合 | `B33/A35/B35` 的 `formula_transport_identity_summary` 中，分布式几何输运、边界项、端部项和剩余项均可解释；三项 Gate Ratio 均小于等于 `1.0`。 |
| 时间压力闭合 | `A33/A53` 必须通过 Gate 1；同时输出独立二维剖面 radiation pressure 校核表，说明 body potential 到时间压力的尺度来源。 |
| 纵摇矩闭合 | `A55/B55` 必须通过 Gate 1；同时输出 pitch row moment chain 表，说明 `N5/m5`、力臂、Stokes body moment 和 end-contour moment 的一致性。 |
| 八系数硬门槛 | `ma2005_wigley_iii_coefficients_comparison.csv` 中 `A33/B33/A35/B35/A53/B53/A55/B55` 全部为 `PASS`。 |
| 候选纪律 | `candidate_impact_summary.csv` 保留；所有未进入默认路径的候选均标注 `candidate_default_gate_eligible=false` 和明确排除原因。 |
| 数值稳定 | 验证输出中关键水动力 CSV 无 `NaN/Inf`；mass、added-mass、damping、restoring 矩阵无非有限值。 |
| 运动链路 | 示例船运动预报可运行，输出 `summary.csv`、`rao.csv`、规则波/不规则波时序、图像和报告；所有时序 CSV 含六自由度列且无 `NaN/Inf`。 |
| 回归测试 | `python -m pytest -q` 全部通过。 |
| 阶段报告 | 生成阶段报告，记录推导位置、代码改动、验证命令、八系数对照表、运动链路结果、剩余风险和后续建议。 |

## 6. 固定验收命令

```powershell
python -m planing_seakeeping validate `
  --benchmark all `
  --out outputs\gate1_linear_2p5d_hard_pass\results `
  --reference-root outputs\matched_bie_provider_gate_probe\reference `
  --ma-hydro-model matched_bie_provider `
  --ma-bem-free-surface-panels 4 `
  --ma-bem-body-panels 8
```

```powershell
python -m planing_seakeeping run configs\example_planing.yml --out outputs\gate1_linear_2p5d_hard_pass_motion_demo
```

```powershell
python -m pytest -q
```

## 7. 交付物

1. `docs/线性2p5D_Gate1硬验证通过_阶段报告.md`
2. `ma2005_wigley_iii_coefficients_comparison.csv`
3. `ma2005_wigley_iii_coefficients_formula_transport_identity_summary.csv`
4. `ma2005_wigley_iii_coefficients_time_pressure_source_audit.csv`
5. `ma2005_wigley_iii_coefficients_pitch_row_moment_chain_audit.csv`
6. `ma2005_wigley_iii_coefficients_candidate_impact_summary.csv`
7. 新增或更新的二维剖面 pressure/radiation 校核表
8. 示例运动预报输出目录 `outputs\gate1_linear_2p5d_hard_pass_motion_demo`

## 8. 合格结果定义

本阶段的理想合格结果是 Ma 2005 Wigley III 八系数全部 `PASS`，且修正进入默认 `matched_bie` 路径。

若八项仍未全部通过，本阶段只能作为有限阶段封口验收：必须证明剩余失败项已经不是当前代码实现或候选选择问题，而是缺少可追溯理论、参考数据或独立剖面验证数据。此时不得把候选修正写入默认路径。
