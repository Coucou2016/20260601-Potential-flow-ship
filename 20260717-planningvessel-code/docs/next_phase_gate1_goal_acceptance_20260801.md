# 下一阶段 Gate 1 目标与验收条件

日期：2026-08-01

## 当前进展

当前代码已经完成第一轮“可扩展、可测试、边界清楚”的升级：

| 项目 | 当前状态 |
|---|---|
| 主程序 | 已建立 `planing_seakeeping` Python 包和 `python -m planing_seakeeping run/validate` 命令 |
| 主水动力路线 | 已接入 `LinearFrequencyProvider(source="linear_2p5d", formulation="matched_bie")` |
| 生产路由 | 当前主线为 `metadata["provider_route"] == "matched_bie_station_sweep"` |
| 统一架构 | 已建立 `kernels/linear_2p5d`、`nonlinear_2dt`、`multihull`、`hydrofoil` 等预留结构 |
| 文献与验证资料 | 已整理 Faltinsen、Ma 2005、Fridsma、Katayama、Delft 372、ITTC 等验证路线 |
| Delft 372 | 已有可机读双体片体 offsets，可作为后续多体船输入 |
| SL-7 与 C1 三体船 | 仍缺真实可机读 offsets，只能作为替代或趋势诊断，不能作为硬验收 |
| 最近代码健康检查 | `python -m py_compile planing_seakeeping/validation.py` 通过；`pytest -q tests/test_validation.py -k matched_bie_provider_model` 通过；完整回归 `python -m pytest -q` 为 `166 passed` |
| 最近验证探针 | 输出在 `outputs/matched_bie_provider_eq30_component_scale_fit_probe/results`；验证命令正常完成，但硬门仍未通过 |

当前 Ma 2005 Wigley III 八个频域水动力系数仍是核心缺口。默认 `matched_bie_station_sweep` 路线下，仅 `B53` 通过；`A33/B33/A35/B35/A53/A55/B55` 仍失败。新增的 Eq.30/Eq.32 压力分量审计、body-potential/source 审计、全局分量尺度最小二乘拟合审计均已说明：当前失败不是输出缺失、不是数值发散、也不是单纯整体符号或整体尺度错误。

最新诊断结论：

1. Eq.30/Eq.32 四类贡献已经能完整输出：time-derivative pressure、forward-speed pressure-gradient、Stokes body forward-speed、end-contour。
2. 分量闭合残差最大约 `1.55e-15`，满足 `< 1e-9`。
3. 44 个关键 CSV 文件中未发现数值型 `NaN` 或 `Inf`。
4. 全局最小二乘缩放即使用 4 个自由尺度，也只能让 4/8 个系数通过，仍失败于 `A35/B35/A55/B55`，因此不能用全局经验系数修补。
5. 主要问题已经定位到上游链路：heave/pitch radiation body potential 的量级、二维剖面边界积分压力恢复、以及第一活动站 `x/L=0.025` 的 pressure-gradient 尖峰。

## 下一阶段唯一总目标

在保持 `LinearFrequencyProvider(source="linear_2p5d", formulation="matched_bie")` 为唯一主线、保持 `provider_route == "matched_bie_station_sweep"`、不引入经验补偿或事后拟合系数的前提下，把 Ma--Duan--Song 型线性高速 2.5D matched BIE 求解器推进到可由 Ma 2005 Wigley III 公开文献数据硬验收的最小完整频域内核。

一句话目标：

> 用同一套默认 `matched_bie_station_sweep` 配置，使 Wigley III 的 `A33/B33/A55/B55` 误差不超过 15%，`A35/B35/A53/B53` 误差不超过 30%，并且每个系数都能由可追溯的二维剖面 BIE、Eq.30 压力恢复、Eq.32 前进速度/端部项和整船积分链条解释。

## 必须完成的工作

| 编号 | 工作 | 完成产物 |
|---|---|---|
| 1 | 建立二维剖面解析或半解析校核 | 一个固定剖面测试，证明 `body normal velocity -> body potential -> time pressure -> heave force` 的符号、相位、量级和积分方向正确 |
| 2 | 修正 matched BIE 上游势函数尺度 | 站位审计表显示 `body_potential_to_body_normal_velocity_gain` 与理论剖面校核一致，不再依赖全局经验缩放 |
| 3 | 修正第一活动站启动问题 | `x/L=0.025` 附近的 pressure-gradient 尖峰必须有物理解释或被数值方案消除 |
| 4 | 闭合 Eq.30 压力恢复 | time-derivative、pressure-gradient、Stokes body forward-speed、end-contour 分量均保留并逐项可追溯 |
| 5 | 闭合 Eq.32 整船装配 | 端部项、纵向积分方向、力矩臂、坐标原点和无量纲化全部在 CSV 中可审计 |
| 6 | 固化验证命令 | `validate --benchmark all` 能自动输出 comparison、diagnostic、summary、report，不需要手工改表 |
| 7 | 更新说明文档 | 在 `docs` 中记录最终采用的公式、符号约定、坐标约定、排除过的错误候选和剩余适用范围 |

## 硬验收条件

| 类别 | 验收条件 | 判定方式 |
|---|---|---|
| 主路由 | 不允许切换到 reduced-order、经验模型或外部拟合补偿 | `comparison.csv` 中 `provider_route == matched_bie_station_sweep` |
| 八系数精度 | `A33/B33/A55/B55` 全部误差不超过 15%；`A35/B35/A53/B53` 全部误差不超过 30% | 每行 `gate_error_ratio <= 1.0` |
| 闭合残差 | 压力分量求和与最终系数一致 | `current_force_closure_residual_value < 1e-9` |
| 数值健康 | 无 `NaN`、无 `Inf`、无奇异矩阵导致的空输出 | 自动检查关键 CSV 和测试结果 |
| 可解释性 | 每个通过项都能说明来自哪个压力分量和哪个站位区间 | 保留 pressure-balance、source-audit、station-contribution CSV |
| 二维剖面校核 | 至少一个剖面级单元测试通过，用于证明 BIE 压力积分不是黑箱调参 | 新增或更新 `tests/test_station_2p5d.py` / `tests/test_validation.py` |
| 回归测试 | 现有功能不被破坏 | `python -m pytest -q` 全部通过 |
| 文档 | 验收结果、公式依据、失败候选和适用边界均已记录 | 更新 `docs/next_stage_target_acceptance_20260801.md` 或同级最终审计文档 |

## 固定验收命令

```powershell
python -m planing_seakeeping validate `
  --benchmark all `
  --out outputs\gate1_final_validation\results `
  --reference-root outputs\matched_bie_provider_gate_probe\reference `
  --ma-hydro-model matched_bie_provider `
  --ma-bem-free-surface-panels 4 `
  --ma-bem-body-panels 8
```

验收通过时，`validation_summary.csv` 中 Ma 2005 Wigley III 的硬失败数必须为 0；若仍有失败，则 Gate 1 保持 `PENDING`，不能进入“完整 2.5D 已实现”的结论。

## 暂不纳入硬验收的内容

| 内容 | 原因 |
|---|---|
| SL-7 硬验收 | 缺真实可机读 offsets；找到替代型线前只能做趋势诊断 |
| C1 三体船硬验收 | 缺主片体与侧片体真实 offsets；不能证明 cross-radiation/cross-diffraction |
| Fridsma/Katayama 幅值硬验收 | 主要用于响应合理性和非线性趋势验证，不替代 Ma 2005 系数门 |
| Delft 372 多体船 | 已具备几何输入价值，但应放在 Gate 2 多体扩展 |
| Sun--Faltinsen 强非线性 2D+t BEM | 属于后续生产内核，不应在 Gate 1 线性 2.5D 闭合前混入 |
| 水翼控制闭环 | 需要真实水翼、舵机、控制器和试验数据，属于更后阶段 |

## 最小通过定义

下一阶段完成只认一个结果：固定命令、固定 Wigley III benchmark、固定 `matched_bie_station_sweep` 主路由下，Ma 2005 八个频域水动力系数全部通过阈值，并且完整测试集通过。除此之外的平滑曲线、示例可视化、替代型线趋势或局部调参结果，只能作为辅助证据，不能宣称 Gate 1 完成。

## 2026-08-01 本轮推进记录

本轮新增了结论型 Gate 1 失败审计输出，不改变 `matched_bie_station_sweep` 默认求解路线，只把已有的 Eq.30/Eq.32 分量、候选重组、全局尺度拟合和 station source 审计合并为可复查证据。

新增文件：

| 文件 | 作用 |
|---|---|
| `ma2005_wigley_iii_coefficients_gate1_failure_audit.csv` | 每个 Wigley III 系数一行，记录参考值、计算值、误差、gate ratio、PASS/FAIL、四类压力贡献、闭合残差、主导分量、失败源和剩余阻塞 |
| `ma2005_wigley_iii_coefficients_gate1_failure_summary.csv` | 按验收条件汇总主路由、输出完整性、Eq.30 拆分、闭合残差、数值健康、候选排除、四分量尺度拟合排除和 SL-7/C1 数据纪律 |
| `ma2005_wigley_iii_coefficients_gate1_failure_report.md` | 面向阅读的 Gate 1 失败审计报告，说明当前为什么保持 `PENDING` |

最新探针目录：

```text
outputs/matched_bie_provider_gate1_failure_audit_probe/results
```

关键结果：

| 验收项 | 当前结果 | 状态 |
|---|---|---|
| 主路由 | `matched_bie_station_sweep` | `PASS` |
| 每系数参考值、计算值、误差、gate ratio、状态 | 8 行完整输出 | `PASS` |
| Eq.30/Eq.32 四分量拆分 | time、gradient、Stokes、end 全部输出且有限 | `PASS` |
| 分量闭合残差 | 最大约 `1.55e-15` | `PASS` |
| 数值稳定 | 46 个关键 CSV 未发现数值型 `NaN/Inf` | `PASS` |
| 条件数、残差与站位贡献 | comparison 中保留 condition number 和 BIE residual；`matched_station_contributions.csv`、`matched_station_transfer_path.csv`、`matched_body_potential_source_audit.csv` 均生成 | `PASS` |
| 当前默认精度 | `pass=1/8`，仅 `B53` 通过 | `PENDING` |
| 固定候选排除 | 最好 pressure-balance 候选 `gradient_flipped_keep_time_end` 仍为 `0/8` 通过 | `PASS` |
| 全局尺度拟合排除 | 四分量最小二乘 `time+gradient+Stokes+end` 仅 `4/8` 通过，最大 gate ratio 为 `9.045` | `PASS` |
| 回归测试 | `python -m pytest -q` 为 `166 passed` | `PASS` |

当前失败源已收敛为两类：

| 失败源 | 影响系数 | 证据 | 下一步 |
|---|---|---|---|
| `heave_time_derivative_body_potential_scale` | `A33`, `A53` | 两项由 time-derivative pressure 主导，pressure-gradient 或 end-contour 符号候选无法修复 | 建立独立二维剖面 heave radiation 压力积分校核，闭合 `body normal velocity -> body potential -> time pressure -> heave force` |
| `first_active_station_pressure_gradient_spike` | `B33`, `A35`, `B35`, `A55`, `B55` | pressure-gradient 路径峰值集中在 `x/L=0.025`，`body-potential x-gradient gain times L` 约为 `106-111` | 审计第一活动湿剖面、ghost/startup 处理和纵向导数公式 |

因此，Gate 1 继续保持 `PENDING`。下一轮开发不应再优先做整体符号或全局尺度试探，而应集中在两个可检验点：第一，二维剖面 BIE 的 heave 势函数与 time-pressure 积分尺度；第二，第一活动站处的湿剖面启动和 pressure-gradient 纵向导数。

## 2026-08-01 Heave Time-Pressure 链路校核

本轮进一步把 `heave_time_derivative_body_potential_scale` 阻塞项拆到二维剖面层。新增审计表使用封闭圆柱在无限流体中横向运动的解析附加质量作为参照：

```text
expected added mass per unit length = rho*pi*r^2
```

该校核只检查局部链路：

```text
body normal velocity -> source strength -> body potential -> Eq.30 time pressure -> heave force
```

新增文件：

| 文件 | 作用 |
|---|---|
| `a1_heave_time_pressure_chain.csv` | 按 panel count 输出解析 heave force、原始压力积分、显式压力符号修正后的 heave force、势函数对齐尺度、残差和诊断状态 |
| `a1_heave_time_pressure_chain_summary.csv` | 汇总 finest panel count 下的误差、符号反转、势函数对齐和 Gate 1 含义 |

最新输出目录：

```text
outputs/matched_bie_provider_heave_time_pressure_chain_probe/results
```

关键结果：

| panel count | 解析 heave force | 原始 heave force | 显式符号修正 heave force | 修正后 added-mass ratio | 修正后误差 | 状态 |
|---:|---:|---:|---:|---:|---:|---|
| 64 | 12566.371 | -12697.854 | 12697.854 | 1.01046 | 1.046% | `PASS` |
| 128 | 12566.371 | -12634.135 | 12634.135 | 1.00539 | 0.539% | `PASS` |
| 256 | 12566.371 | -12600.753 | 12600.753 | 1.00274 | 0.274% | `PASS` |

审计含义：

1. 闭合圆柱的内域 pressure chain 可以被量化，并且在显式压力符号修正后收敛到解析附加质量，finest error 约 `0.002736`。
2. 势函数与解析形式的对齐尺度约为 `-1.00284`，说明局部内域链路存在清晰的符号约定问题，但量级本身不是无界发散。
3. 这不能直接把压力符号翻入 Ma 2005 生产默认，因为全局候选已经证明简单符号/尺度变换不能让 Wigley III 八项全部通过。
4. 对 `A33/A53` 的下一步判断变得更具体：问题不应再笼统写成“Eq.30 时间项可能错”，而应检查 matched open-section/free-surface/wet-station 中的 heave body potential 尺度、自由面匹配和广义力行方向。

本轮验证：

| 检查 | 结果 |
|---|---|
| 定向测试 | `2 passed, 37 deselected` |
| 完整回归 | `166 passed` |
| 关键 CSV 数值健康 | 48 个关键 CSV 未发现数值型 `NaN/Inf` |

Gate 1 结论不变：仍为 `PENDING`。失败源仍是两类，但其中 `heave_time_derivative_body_potential_scale` 已经被进一步限定到 matched open-section/free-surface/wet-station 链路，而不是封闭剖面内域压力积分无法闭合。

## 2026-08-01 Wigley III Heave Time-Pressure 站位尺度审计

在 closed-cylinder 局部链路校核之后，本轮继续把同一问题放回 Wigley III 的 `matched_bie_station_sweep` 主线中，新增 open-section station-scale 审计。该审计只读取当前默认求解器已经输出的 `matched_body_potential_source_audit` 和 `comparison` 数据，不改变任何默认水动力计算。

新增文件：

| 文件 | 作用 |
|---|---|
| `ma2005_wigley_iii_coefficients_heave_time_pressure_station_scale_audit.csv` | 对 `A33/A53` 的每个活动站输出局部 time-derivative density、梯形积分权重、站位贡献、贡献占比、局部面积/梁宽归一化、body potential gain 和所需参考尺度 |
| `ma2005_wigley_iii_coefficients_heave_time_pressure_station_scale_summary.csv` | 汇总 `A33/A53` 的 station 积分闭合、正负贡献、峰值站位、贡献质心、所需全局参考尺度和剩余阻塞 |

最新输出目录：

```text
outputs/matched_bie_provider_heave_time_station_scale_probe/results
```

关键结果：

| 系数 | reference | current | gate ratio | time component | station integral | closure residual | peak `x/L` | centroid `x/L` | required scale |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `A33` | 1.000 | 10.290 | 61.933 | 10.290 | 10.290 | `1.78e-15` | 0.300 | 0.357 | 0.09718 |
| `A53` | 0.150 | 1.445 | 28.772 | 1.445 | 1.445 | `2.22e-16` | 0.250 | 0.300 | 0.10383 |

审计含义：

1. `A33/A53` 的 station time-pressure 积分与 `comparison.csv` 中的 Eq.30 time component 完全闭合，残差在 `1e-15` 量级。这说明这两项的错误不是“表格输出或积分记账不一致”。
2. 两个系数都表现为 open-section heave time-pressure 量级偏大：若只从 time integral 打到参考值，需要约 `0.097-0.104` 的尺度。这个范围解释了为什么全局 `time_only` 最小二乘会倾向于约 `0.09` 的尺度，但这种尺度不能作为物理修正。
3. 贡献峰值不是首站尖峰，而集中在中前部：`A33` 峰值约 `x/L=0.300`，`A53` 峰值约 `x/L=0.250`；贡献质心分别约 `0.357` 和 `0.300`。这将 `A33/A53` 与 pressure-gradient 的 `x/L=0.025` 启动尖峰区分开。
4. 最大 `body_potential_to_body_normal_velocity_gain` 仍约 `23.105`，最大 `body_potential_norm_to_submerged_area_ratio` 对 `A33` 约 `2871`，对 `A53` 约 `5742`。这些是下一步审计 open-section/free-surface 匹配尺度的直接指标。
5. 结论仍是 diagnostic-only：station-scale 表证明了“open-section heave time-pressure integral is closed but over-scaled”，但不允许把 `0.1` 尺度作为默认修正，因为四分量全局尺度拟合仍不能让八个 Wigley III 系数全部通过。

本轮验证：

| 检查 | 结果 |
|---|---|
| 定向测试 | `1 passed, 38 deselected` |
| Ma 2005 探针 | 正常完成，硬失败仍为 15，待数据项 8 |
| 数值健康 | 50 个关键 CSV 未发现数值型 `NaN/Inf` |
| 完整回归 | `166 passed` |

Gate 1 继续保持 `PENDING`。下一步对 `A33/A53` 的最佳推进点已经变成：检查 Wigley III 开剖面/自由面匹配中 heave body potential 相对于 body normal velocity 的尺度来源，尤其是 inner/free/control 边界方程的单位、自由面 panel 截断、以及 open-section 与 closed-section pressure-row 符号约定之间的差异。

## 2026-08-01 Open-Section / Free-Surface 匹配尺度补充审计

本轮在 `ma2005_wigley_iii_coefficients_heave_time_pressure_station_scale_audit.csv` 中继续补充了自由面与控制面相关的无量纲比值，目的不是增加新候选，而是判断 heave body potential 放大更接近哪个边界块或匹配环节。

新增字段包括：

| 字段 | 含义 |
|---|---|
| `free_surface_potential_to_body_potential_ratio` | 每站自由面势函数范数相对 body potential 范数的比例 |
| `control_potential_to_body_potential_ratio` | 每站控制面势函数范数相对 body potential 范数的比例 |
| `inner_free_surface_normal_derivative_to_body_normal_velocity_ratio` | 每站内域自由面法向导数相对船体法向速度范数的比例 |
| `time_pressure_to_body_potential_gain` | Eq.30 时间压力相对 body potential 的范数增益，用于确认 `rho*omega` 通道一致 |

最新探针仍为：

```text
outputs/matched_bie_provider_heave_open_section_scale_probe/results
```

关键汇总：

| 系数 | required scale | max free phi/body phi | max control phi/body phi | max free normal/body velocity |
|---|---:|---:|---:|---:|
| `A33` | 0.09718 | 0.23447 | 0.13112 | 12.6778 |
| `A53` | 0.10383 | 0.23447 | 0.13112 | 12.6778 |

这进一步说明：在 `A33/A53` 的主贡献站位附近，自由面势和控制面势相对 body potential 并不是同量级放大源；更需要检查的是自由面法向导数/船体法向速度的传递比例、inner/free/control 方程单位，以及开剖面自由面匹配如何把 body normal velocity 转成偏大的 body potential。当前仍不得把 `0.1` 尺度或 closed-cylinder 符号修正写进默认模型，因为它们没有通过八系数共同验收。

本轮补充验证：

| 检查 | 结果 |
|---|---|
| 定向测试 | `1 passed, 38 deselected` |
| 数值健康 | 50 个关键 CSV 未发现数值型 `NaN/Inf` |
| 完整回归 | `166 passed` |

## 2026-08-01 Free-Normal -> Body-Potential 传递链专项审计

本轮继续把 `A33/A53` 的 heave time-pressure 失败源向上游推进，新增一个更聚焦的专项审计：

```text
inner free-surface normal derivative -> body potential -> Eq.30 time pressure -> heave generalized force
```

该审计的目的不是生成新的修正候选，而是判断自由面法向导数的异常传递比是否与 `A33/A53` 的时间压力主贡献同站发生。如果同站，则应优先修正自由面法向导数传递；如果不同站，则说明 heave time-pressure 放大还需要继续追查中前部开剖面 body-potential 尺度。

新增输出目录：

```text
outputs/matched_bie_provider_free_normal_chain_probe/results
```

新增文件：

| 文件 | 作用 |
|---|---|
| `ma2005_wigley_iii_coefficients_heave_free_normal_to_body_potential_audit.csv` | 逐站输出 body normal velocity、inner free-surface normal derivative、body potential、free/control potential、time-pressure station contribution 和峰值标记 |
| `ma2005_wigley_iii_coefficients_heave_free_normal_to_body_potential_summary.csv` | 按 `A33/A53` 汇总最大/中位传递比、峰值站位、与时间压力主贡献是否同站、相关系数和剩余阻塞 |

关键结果如下：

| 系数 | 最大 free-normal/body-velocity | 中位值 | 最大值 `x/L` | time-pressure 峰值 `x/L` | 峰值贡献占比 | 相关系数 | 结论 |
|---|---:|---:|---:|---:|---:|---:|---|
| `A33` | 12.6778 | 0.39548 | 0.025 | 0.300 | 0.06884 | 0.01476 | `free_normal_gain_is_large_but_not_colocated_with_peak_time_pressure` |
| `A53` | 12.6778 | 0.39548 | 0.025 | 0.250 | 0.07759 | 0.18707 | `free_normal_gain_is_large_but_not_colocated_with_peak_time_pressure` |

本轮判断：

1. 自由面法向导数相对船体法向速度的最大传递比确实偏大，且发生在首个活动站 `x/L=0.025`。
2. `A33/A53` 的时间压力主贡献并不在该站，而是在中前部 `x/L=0.300/0.250`；二者没有同站，相关系数也很弱。
3. 因此，不能把 `A33/A53` 的失败简单归因于首站自由面法向导数尖峰。下一步应继续审计 Eq.23/Eq.24 自由面法向导数单位、inner/free/control 匹配符号、开剖面自由面截断，以及中前部站位 body-potential 尺度。
4. 新增表保持 `diagnostic-only`：没有把任何尺度、符号或候选方案写入 `matched_bie_station_sweep` 默认生产路径。

本轮验证：

| 检查 | 结果 |
|---|---|
| Ma 2005 探针 | 正常完成；`Hard failures=15`、`pending reference data=8`，Gate 1 仍为 `PENDING` |
| `validation_summary.csv` | `PASS=65`、`FAIL=15`、`NOT_EVALUATED=8`、`INFO=41` |
| 关键 CSV 数值健康 | 未发现数值型 `NaN/Inf` |
| 定向测试 | `python -m pytest -q tests/test_validation.py -k matched_bie_provider_model` 通过 |
| 完整回归 | `python -m pytest -q`：`166 passed` |

## 2026-08-02 Gradient Stencil / Phase 候选排除审计

在首站尖峰被排除为单独修正之后，本轮进一步把 pressure-gradient 的 stencil 与相位对齐候选整理成默认准入审计。审计对象包括：

```text
central, forward, backward,
phase-aligned central, phase-aligned forward, phase-aligned backward,
startup aft zero/copy/first-pair average
```

新增输出目录：

```text
outputs/matched_bie_provider_stencil_phase_exclusion_probe/results
```

新增文件：

| 文件 | 作用 |
|---|---|
| `ma2005_wigley_iii_coefficients_pressure_gradient_stencil_phase_exclusion_audit.csv` | 按候选和系数逐行记录 gate ratio、相对 current default 的改善/恶化、是否破坏当前通过项和行级判定 |
| `ma2005_wigley_iii_coefficients_pressure_gradient_stencil_phase_exclusion_summary.csv` | 按候选汇总通过数、改善数、恶化数、是否破坏当前通过项和默认排除原因 |

关键结果：

| 候选 | pass count | improved rows | worsened rows | breaks current pass | max gate ratio | 默认判定 |
|---|---:|---:|---:|---:|---:|---|
| `phase_aligned_forward` | 0/8 | 4 | 3 | 1 | 78.495 | 排除：破坏当前通过项 |
| `phase_aligned_central` | 0/8 | 4 | 3 | 1 | 110.057 | 排除：破坏当前通过项 |
| `phase_aligned_backward` | 0/8 | 4 | 3 | 1 | 136.011 | 排除：破坏当前通过项 |
| `scheme_forward` | 0/8 | 4 | 2 | 1 | 136.888 | 排除：破坏当前通过项 |
| `startup_aft_gradient_zero` | 0/8 | 4 | 2 | 1 | 145.299 | 排除：破坏当前通过项 |
| `current_default / scheme_central` | 1/8 | 2 | 2 | 0 | 163.904 | 未通过 Gate 1 |
| `scheme_backward` | 0/8 | 2 | 4 | 1 | 171.183 | 排除：破坏当前通过项 |

本轮判断：

1. `phase_aligned_forward` 是当前候选里最大 gate ratio 最低的方案，但仍为 `0/8` 通过，且破坏当前唯一通过的 `B53`。
2. `forward/backward/phase-aligned` 都不能作为生产默认；它们最多说明 pressure-gradient 项存在相位/方向敏感性，但没有形成 Ma 2005 八系数共同闭合。
3. `A33/A53` 对这些 stencil 候选基本不响应，因为它们由 time-derivative pressure 主导；这再次证明 Gate 1 不是单一 pressure-gradient stencil 问题。
4. 下一步应转向更基础的 Eq.30 forward-speed 项约定：纵向坐标方向、marching 方向、复相位约定、body-potential 沿站位传播的相位，以及 time-pressure 与 gradient-pressure 的共同无量纲化。

本轮验证：

| 检查 | 结果 |
|---|---|
| Ma 2005 探针 | 正常完成；`Hard failures=15`、`pending reference data=8` |
| `validation_summary.csv` | `PASS=65`、`FAIL=15`、`NOT_EVALUATED=8`、`INFO=43` |
| 关键 CSV 数值健康 | 未发现数值型 `NaN/Inf` |
| 定向测试 | `python -m pytest -q tests/test_validation.py -k matched_bie_provider_model` 通过 |
| 完整回归 | `python -m pytest -q`：`166 passed` |

## 2026-08-02 Eq.30 Pressure-Gradient 首站尖峰审计

本轮针对 `B33/A35/B35/A55/B55` 等受 forward-speed pressure-gradient 影响的系数，新增逐站积分审计：

```text
body potential longitudinal derivative -> forward-speed pressure-gradient -> station integral -> coefficient
```

该审计只读取当前 `matched_bie_station_sweep` 默认输出，不改变梯度计算、不删除站位、不写入任何候选修正。

新增输出目录：

```text
outputs/matched_bie_provider_pressure_gradient_spike_probe/results
```

新增文件：

| 文件 | 作用 |
|---|---|
| `ma2005_wigley_iii_coefficients_pressure_gradient_startup_spike_audit.csv` | 逐站记录 pressure-gradient density、梯形积分权重、站位贡献、贡献占比、body-potential 纵向梯度增益和首站/峰值标记 |
| `ma2005_wigley_iii_coefficients_pressure_gradient_startup_spike_summary.csv` | 汇总首站、第二站、前两站、其余站和峰值站贡献，并给出去首站/去前两站的诊断性 gate ratio |

关键结果：

| 系数 | 当前 gate ratio | pressure-gradient component | 首站占比 | 前两站占比 | 峰值 `x/L` | 去首站 gate ratio | 结论 |
|---|---:|---:|---:|---:|---:|---:|---|
| `B33` | 23.957 | 9.0451 | 0.0639 | 0.1132 | 0.075 | 19.918 | 峰值不局限于首站 |
| `A35` | 43.563 | -1.6080 | 0.0639 | 0.1132 | 0.075 | 39.793 | 峰值不局限于首站 |
| `B35` | 163.904 | 1.8232 | 0.1416 | 0.1640 | 0.025 | 145.299 | 首站为峰值但不占主导 |
| `B53` | 0.190 | -0.3800 | 0.1322 | 0.2288 | 0.075 | 19.955 | 去首站会破坏已通过项 |
| `A55` | 2.865 | 0.1520 | 0.1322 | 0.2288 | 0.075 | 28.446 | 峰值不局限于首站 |
| `B55` | 131.032 | 1.0041 | 0.2084 | 0.2396 | 0.025 | 105.501 | 首站为峰值但不占主导 |

本轮判断：

1. `x/L=0.025` 首站确实存在较大的 pressure-gradient density，但它不是所有相关失败项的峰值站；若干项峰值在 `x/L=0.075`。
2. 首站贡献占比最高约 `20.84%`，前两站最高约 `23.96%`，不足以解释全体系数失真。
3. 去首站不能让失败项通过，并且会把已通过的 `B53` 从 `gate ratio=0.190` 恶化到 `19.955`。
4. 因此，删除首站、首站置零、或简单 startup smoothing 都被排除为生产默认修正；它们只能保留为 diagnostic-only 反事实。
5. 剩余阻塞转向纵向 body-potential derivative stencil、相位对齐、station marching 方向、以及 Eq.30 forward-speed pressure-gradient 的符号/相位装配。

本轮验证：

| 检查 | 结果 |
|---|---|
| Ma 2005 探针 | 正常完成；`Hard failures=15`、`pending reference data=8` |
| `validation_summary.csv` | `PASS=65`、`FAIL=15`、`NOT_EVALUATED=8`、`INFO=42` |
| 关键 CSV 数值健康 | 未发现数值型 `NaN/Inf` |
| 定向测试 | `python -m pytest -q tests/test_validation.py -k matched_bie_provider_model` 通过 |
| 完整回归 | `python -m pytest -q`：`166 passed` |
