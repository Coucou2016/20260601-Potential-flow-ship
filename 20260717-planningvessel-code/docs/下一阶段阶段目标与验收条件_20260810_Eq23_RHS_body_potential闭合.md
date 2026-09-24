# 下一阶段阶段目标与验收条件：Eq.23 RHS / body-potential / time-pressure 链闭合

日期：2026-08-10  
对应总体目标：高速船型运动预报系统总体目标  
阶段定位：线性高速 2.5D 核心 Gate 1 方程级闭合的下一执行阶段

## 1. 当前状态

当前系统已经具备高速船型运动预报的基础框架，并已建立 Ma 2005 Wigley III、Faltinsen、Fridsma、Katayama、Delft 372、ITTC 等验证路线。

但线性 2.5D 核心仍未通过 Ma 2005 Wigley III Gate 1。当前八个核心水动力系数状态为：

| 系数 | 当前状态 | Gate error ratio |
|---|---|---:|
| A33 | FAIL | 61.243 |
| B33 | FAIL | 22.478 |
| A35 | FAIL | 41.680 |
| B35 | FAIL | 164.377 |
| A53 | FAIL | 28.176 |
| B53 | FAIL | 5.069 |
| A55 | FAIL | 10.249 |
| B55 | FAIL | 131.016 |

最新审计已经确认：

1. A1 Eq.19--Eq.22 自由面状态传递可重构，`8/8` 行通过，更新残差与传递残差均为 `0.0`。
2. 自由面更新公式本身不再是当前首要嫌疑。
3. `A33/A53` 失败主要剩余在 `Eq.23 RHS -> body potential -> Eq.30 time pressure` 尺度与相位链。
4. `B33/A35/B35` 和 `A55/B55` 仍分别受几何输运链、纵摇矩链阻塞。

## 2. 下一阶段主目标

下一阶段主目标是：

**完成 `A33/A53` 的 `Eq.23 RHS -> body potential -> Eq.30 time pressure` 方程链闭合，建立可追溯的尺度、符号、相位和归一化关系，使 `A33/A53` 在默认 `matched_bie_station_sweep` 路径下通过 Ma 2005 Wigley III Gate 1，并为后续闭合 `B33/A35/B35` 与 `A55/B55` 提供可信基础。**

一句话目标：

> 先把 `A33/A53` 从“自由面状态已自洽但 body-potential/time-pressure 尺度不对”推进到“默认方程实现可验证通过”。

## 3. 工作范围

必须完成：

1. 核对 A1 Eq.23 中已知 inner-free-surface potential RHS 对 body potential 的贡献路径。
2. 分离 body row、free-surface row、control row 对 open Wigley body potential 尺度和相位的影响。
3. 追踪 raw `ln r` Green 函数、`pi`/`2pi` 系数、自项符号、边界法向和 Eq.23/Eq.24 连续条件对 body potential 的影响。
4. 解释或排除当前接近 `1/pi^2` 的数值尺度线索，不允许直接把它作为经验补丁。
5. 建立 `body potential -> Eq.30 i omega phi time pressure -> A33/A53` 的机器可读审计表。
6. 若找到可追溯修正，接入默认 `matched_bie_station_sweep`，并重新运行 Ma 2005 固定验证。
7. 若仍不能闭合，必须明确写出缺少的公式、参考剖面数据、开域势函数基准或实验对照。

暂不作为本阶段主线：

1. 不进入非线性 2D+t 生产实现。
2. 不展开双体船、三体船或水翼生产模型。
3. 不用最终系数缩放、全局拟合、按参考值反推或经验比例通过 Gate。
4. 不把 SL-7、C1 三体船或替代几何作为本阶段硬验收对象。

## 4. 可验收条件

| 类别 | 验收条件 |
|---|---|
| 默认路径 | `A33/A53` 验证结果必须来自 `provider_route=matched_bie_station_sweep`。 |
| A33/A53 硬门槛 | `ma2005_wigley_iii_coefficients_comparison.csv` 中 `A33` 与 `A53` 均为 `PASS`，且 `gate_error_ratio <= 1.0`。 |
| 方程来源 | 修正必须能追溯到 A1/Ma 的 Eq.23、Eq.24、Eq.30、Green 函数归一化、法向定义或压力恢复公式。 |
| 禁止捷径 | 不允许通过最终系数重标定、经验 `1/pi^2` 补丁、单项拟合或手动改 CSV 达成通过。 |
| 自由面状态 | `a1_free_surface_grid_implementation_summary.csv` 必须继续显示 Eq.19--Eq.22 状态传递重构通过。 |
| RHS 分解 | `rhs_source_decomposition_summary.csv` 必须能说明 inner-free-surface potential、body normal velocity、outer control history 对 body potential 的贡献比例。 |
| body-potential 尺度 | 新增或更新审计表必须给出 body potential 尺度来源、相位关系、候选排除理由和默认修正依据。 |
| 候选纪律 | 所有未进入默认路径的候选必须保留 `candidate_default_gate_eligible=false` 与排除原因。 |
| 全八系数复核 | 即使本阶段重点是 `A33/A53`，仍必须重新输出八系数 comparison，确认其他六项没有出现 `NaN/Inf` 或异常发散。 |
| 测试 | 至少通过相关定向测试和 `python -m pytest -q`。 |
| 报告 | 更新 `docs/线性2p5D_Gate1硬验证通过_阶段报告.md`，记录公式依据、代码位置、修正前后对照、失败候选和剩余风险。 |

## 5. 固定验证命令

```powershell
python -m planing_seakeeping validate --benchmark all --out outputs\gate1_linear_2p5d_hard_pass\results --reference-root outputs\matched_bie_provider_gate_probe\reference --ma-hydro-model matched_bie_provider --ma-bem-free-surface-panels 4 --ma-bem-body-panels 8
```

```powershell
python -m pytest -q
```

## 6. 阶段完成判定

本阶段完成必须同时满足：

1. `A33/A53` 全部通过 Gate 1。
2. 通过结果来自默认 `matched_bie_station_sweep`。
3. 修正具有可追溯公式来源，不是经验补丁。
4. Eq.19--Eq.22 自由面状态传递仍保持重构通过。
5. 八系数 comparison、候选隔离表、RHS/body-potential 审计表、阶段报告和自动测试均完整。

若 `A33/A53` 仍未通过，则本阶段未完成；此时必须把剩余缺口压缩为明确的数据或理论缺口，而不是转向更复杂船型或非线性模型。

## 7. 完成后进入的下一步

本阶段完成后，再进入以下工作：

1. 闭合 `B33/A35/B35` 的 zero-`m3` 分布式几何输运链。
2. 闭合 `A55/B55` 的 pitch row moment 链。
3. 重新执行完整八系数 Gate 1。
4. Gate 1 全部通过后，再回到示例滑行艇运动预报、Fridsma/Katayama 响应验证和后续多船型扩展。
