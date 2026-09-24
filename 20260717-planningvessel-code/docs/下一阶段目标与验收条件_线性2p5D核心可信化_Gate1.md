# 下一阶段目标与可验收条件：线性 2.5D 核心可信化 Gate 1

日期：2026-08-02

## 1. 阶段定位

本阶段服务于《高速船型运动预报系统总体目标》，是从“可扩展原型”走向“可验证核心模型”的关键阶段。

当前不追求扩大船型覆盖范围，而是集中把高速单体船线性 2.5D 水动力主线做实，使后续滑行艇、非线性 2D+t、多体船和水翼扩展建立在可信的基础内核之上。

## 2. 阶段目标

完成高速单体船线性 2.5D matched BIE 水动力核心的公式级修正与验证，使 Ma 2005 Wigley III 八个水动力系数在默认计算路径下通过 Gate 1 硬验证，并保持规则波、不规则波和 6 自由度运动输出链路稳定可运行。

若八个系数仍不能全部通过，必须把剩余失败项压缩到明确的理论、数据或独立验证缺口；不得用最终系数缩放、最小二乘拟合或经验补偿替代方程实现。

## 3. 本阶段范围

1. 聚焦线性高速 2.5D 方法。
2. 聚焦单体船纵向水动力：升沉、纵摇及其耦合系数。
3. 聚焦 matched BIE 站位扫描路径。
4. 修正并验证剖面势函数、压力恢复、前进速度梯度项、端部项、几何输运项和整船装配。
5. 保持现有运动预报程序可读取船型、质量、航速、波浪、海流、风和仿真参数。
6. 保持规则波、不规则波、响应幅值算子、时域响应、加速度和 6 自由度统一输出可运行。

## 4. 本阶段不做

1. 不实现生产级强非线性 2D+t 自由面边界元。
2. 不实现双体船、三体船共同边界积分生产内核。
3. 不实现真实水翼、压浪板和控制系统耦合模型。
4. 不把经验比例系数、最终系数差值、全局最小二乘拟合写入默认物理路径。
5. 不把未验证的横向自由度半经验结果包装成完整 6 自由度高精度模型。

## 5. 必要前置条件

1. A1、A3、A4_1、A4_2、A4_3、A5、A6、A7、D2 等 Markdown 文献文本可检索。
2. Ma 2005 Wigley III 八个水动力系数参考值可追溯。
3. 当前代码中的 `matched_bie_station_sweep` 路径可复现运行。
4. Python 测试环境、示例配置和输出目录可正常使用。
5. 本阶段不依赖 SL-7 真实 offsets，也不依赖 C1 三体船真实 offsets；这些属于后续扩展验证资料。

## 6. 可验收条件

| 类别 | 验收条件 |
|---|---|
| 默认路径 | `LinearFrequencyProvider(source="linear_2p5d", formulation="matched_bie")` 可运行，验证输出中的 `provider_route` 为 `matched_bie_station_sweep`。 |
| 硬基准 | `ma2005_wigley_iii_coefficients_comparison.csv` 中 `A33`、`B33`、`A35`、`B35`、`A53`、`B53`、`A55`、`B55` 全部为 `PASS`，且 Gate Ratio 均小于等于 `1.0`。 |
| 方程级实现 | 通过项必须来自压力恢复、势函数尺度、前进速度项、端部项、几何输运或整船装配等方程位置的修正，不得来自最终系数后处理。 |
| zero-m3 闭合 | `B33/A35/B35` 的几何输运、边界项、端部项和剩余项有清晰审计表，剩余误差不再主导 Gate 失败。 |
| 时间压力闭合 | `A33/A53` 输出二维剖面 pressure/radiation 校核表，说明 body potential 到时间压力的尺度、符号、归一化和广义力来源。 |
| 纵摇矩闭合 | `A55/B55` 输出 pitch row moment chain 审计表，说明 `N5/m5`、力臂、Stokes body moment、pressure-gradient moment 和 end-contour moment 的一致性。 |
| 候选排除 | `candidate_impact_summary.csv` 保留；未进入默认路径的候选必须标注 `candidate_default_gate_eligible=false` 和排除原因。 |
| 数值稳定 | 核心水动力 CSV、质量矩阵、附加质量矩阵、阻尼矩阵和恢复矩阵无 `NaN/Inf`。 |
| 运动预报 | 示例配置可输出 `summary.csv`、`rao.csv`、规则波/不规则波时序、图像和报告；所有时序 CSV 包含 6 自由度列。 |
| 不规则波 | 固定随机种子下结果可复现；响应均方根值为正，波高变化时响应趋势合理。 |
| 测试 | `python -m pytest -q` 全部通过。 |
| 阶段报告 | 生成阶段报告，包含目标、方法、代码改动、验证命令、八系数对照、失败项说明、运动示例和后续风险。 |

## 7. 固定验收命令

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

## 8. 交付物

1. `docs/线性2p5D_Gate1硬验证通过_阶段报告.md`
2. `outputs/gate1_linear_2p5d_hard_pass/results/ma2005_wigley_iii_coefficients_comparison.csv`
3. `outputs/gate1_linear_2p5d_hard_pass/results/ma2005_wigley_iii_coefficients_formula_transport_identity_summary.csv`
4. `outputs/gate1_linear_2p5d_hard_pass/results/ma2005_wigley_iii_coefficients_time_pressure_source_audit_summary.csv`
5. `outputs/gate1_linear_2p5d_hard_pass/results/ma2005_wigley_iii_coefficients_pitch_row_moment_chain_audit_summary.csv`
6. `outputs/gate1_linear_2p5d_hard_pass/results/ma2005_wigley_iii_coefficients_candidate_impact_summary.csv`
7. 新增或更新的二维剖面 pressure/radiation 校核表。
8. `outputs/gate1_linear_2p5d_hard_pass_motion_demo`

## 9. 合格定义

本阶段的理想合格结果是 Ma 2005 Wigley III 八个水动力系数全部通过 Gate 1，并且修正进入默认 matched BIE 路径。

若未全部通过，则本阶段不能称为硬通过，只能称为有限阶段封口。有限阶段封口必须满足三个条件：失败项数量明显减少；每个剩余失败项都有具体公式链路和数据缺口说明；默认路径中没有任何经验拟合或最终系数补偿。
