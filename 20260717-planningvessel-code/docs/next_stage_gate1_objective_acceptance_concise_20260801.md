# 下一阶段目标与验收条件：线性 2.5D Gate 1

日期：2026-08-01

## 当前进展

项目已经完成第一轮可扩展、可测试、边界清楚的升级：

| 项目 | 当前状态 |
|---|---|
| 主程序 | 已建立 `planing_seakeeping` Python 包与 `python -m planing_seakeeping run/validate` 命令 |
| 主求解路线 | 已接入 `LinearFrequencyProvider(source="linear_2p5d", formulation="matched_bie")` |
| 生产路由 | 当前固定为 `provider_route == "matched_bie_station_sweep"` |
| 验证材料 | 已整理 Ma 2005、Faltinsen、Fridsma、Delft 372、ITTC 等资料与验证路线 |
| Delft 372 | 已具备双体片体 offsets，可作为后续多体船扩展输入 |
| SL-7 / C1 三体船 | 仍缺真实 machine-readable offsets，只能作替代趋势或待补充验证，不能作硬验收 |
| 最新验证状态 | `PASS=65`、`FAIL=15`、`NOT_EVALUATED=8`、`INFO=40` |
| 最新定向测试 | `python -m pytest -q tests/test_validation.py -k matched_bie_provider_model` 通过 |

当前核心缺口仍是 Ma 2005 Wigley III 八个频域水动力系数。默认 `matched_bie_station_sweep` 路线下，仅 `B53` 通过；`A33/B33/A35/B35/A53/A55/B55` 仍失败。已有审计已经说明：问题不是输出缺失、不是数值发散、不是单一整体符号错误，也不是简单全局尺度因子可以修复。

## 下一阶段唯一目标

在不切换主模型、不引入经验补偿、不使用事后拟合系数的前提下，把 Ma--Duan--Song 型线性高速 2.5D matched BIE 求解器推进到可由 Ma 2005 Wigley III 公开文献数据硬验收的最小完整频域内核。

具体目标是：

> 使用同一套默认 `matched_bie_station_sweep` 配置，使 Wigley III 的 `A33/B33/A55/B55` 相对误差不超过 15%，`A35/B35/A53/B53` 相对误差不超过 30%；同时每个系数都必须能由二维剖面 BIE、Eq.30 压力恢复、Eq.32 前进速度/端部项、整船积分和无量纲化链条逐项解释。

## 必须完成的工作

| 编号 | 工作项 | 完成产物 |
|---|---|---|
| 1 | 审计并修正 `inner free-surface normal derivative -> body potential` 传递链 | 新增逐站 CSV，说明自由面法向导数、船体法向速度、船体势函数之间的量级关系 |
| 2 | 审计并修正 `A33/A53` 的 heave time-pressure 尺度 | `A33/A53` 不再依赖约 `0.1` 的诊断性全局缩放即可接近文献参考 |
| 3 | 审计并修正首个活动站 `x/L=0.025` 的 pressure-gradient 尖峰 | `B33/A35/B35/A55/B55` 的纵向梯度贡献不再出现无物理解释的首站放大 |
| 4 | 保留 Eq.30/Eq.32 四分量拆分 | time-derivative、pressure-gradient、Stokes body forward-speed、end-contour 均可逐项输出和闭合 |
| 5 | 固化自动验证流程 | 一条 `validate --benchmark all` 命令生成 comparison、diagnostics、summary、report |
| 6 | 更新文档 | 记录最终采用的公式、符号、坐标、无量纲化、被排除候选和适用边界 |

## 硬验收条件

| 类别 | 验收条件 | 判定方式 |
|---|---|---|
| 主路由 | 只能使用 `linear_2p5d/matched_bie` 主线 | `comparison.csv` 中 `provider_route == matched_bie_station_sweep` |
| 八系数精度 | `A33/B33/A55/B55` 全部误差 `<= 15%`；`A35/B35/A53/B53` 全部误差 `<= 30%` | 每行 `gate_error_ratio <= 1.0` |
| 闭合残差 | 压力分量求和与最终系数一致 | `current_force_closure_residual_value < 1e-9` |
| 数值健康 | 无 `NaN`、无 `Inf`、无空矩阵导致的空输出 | 自动检查关键 CSV 与测试结果 |
| 可解释性 | 每个通过项都能追溯到站位贡献、压力分量、端部项和无量纲化 | 保留 pressure-balance、source-audit、station-scale CSV |
| 非调参性 | 不允许用全局经验缩放、强行符号翻转或 reduced-order 结果补偿 | 默认配置中无诊断候选参数进入生产路径 |
| 回归测试 | 现有功能不被破坏 | `python -m pytest -q` 全部通过 |
| 文档同步 | 通过项、失败项、公式来源、候选排除和剩余边界全部记录 | 更新 `docs` 中对应阶段审计文档 |

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

验收通过时，`validation_summary.csv` 中 Ma 2005 Wigley III 的硬失败数必须为 0。若仍有失败，则 Gate 1 保持 `PENDING`，只能报告已定位的失败来源、已排除的候选方案和下一步阻塞点，不能宣称“完整 2.5D 模型已完成”。

## 暂不作为下一阶段硬验收

| 内容 | 原因 |
|---|---|
| SL-7 | 缺真实可机读 offsets，只能作趋势检查或替代型线测试 |
| C1 三体船 | 缺主片体与侧片体真实 offsets，不能硬验证 cross-radiation/cross-diffraction |
| Delft 372 多体船 | 已有几何价值，但应放入 Gate 2 多体船扩展 |
| Fridsma/Katayama | 适合后续运动响应合理性与非线性趋势验证，不替代 Ma 2005 系数闭合 |
| Sun--Faltinsen 强非线性 2D+t BEM | 属于后续生产内核，需在线性 2.5D Gate 1 闭合后进入 |
| 水翼闭环控制 | 需要真实水翼、舵机、控制器和试验数据，属于更后阶段 |

## 本轮新增进展：自由面法向导数传递链审计

本轮新增 `A33/A53` 专项审计，用于检查：

```text
inner free-surface normal derivative -> body potential -> Eq.30 time pressure -> heave generalized force
```

新增输出目录：

```text
outputs/matched_bie_provider_free_normal_chain_probe/results
```

新增文件：

| 文件 | 作用 |
|---|---|
| `ma2005_wigley_iii_coefficients_heave_free_normal_to_body_potential_audit.csv` | 逐站输出自由面法向导数、船体法向速度、船体势函数、局部时间压力贡献和峰值标记 |
| `ma2005_wigley_iii_coefficients_heave_free_normal_to_body_potential_summary.csv` | 汇总最大/中位传递比、峰值站位、与时间压力贡献峰值是否同站、相关系数和剩余阻塞 |

关键结果：

| 系数 | 最大自由面法向导数/船体法向速度 | 最大值位置 `x/L` | 时间压力贡献峰值 `x/L` | 峰值贡献占比 | 是否同站 | 诊断结论 |
|---|---:|---:|---:|---:|---|---|
| `A33` | 12.6778 | 0.025 | 0.300 | 0.06884 | 否 | `free_normal_gain_is_large_but_not_colocated_with_peak_time_pressure` |
| `A53` | 12.6778 | 0.025 | 0.250 | 0.07759 | 否 | `free_normal_gain_is_large_but_not_colocated_with_peak_time_pressure` |

本轮判断：

1. 自由面法向导数确实在首个活动站 `x/L=0.025` 存在较大传递比，但 `A33/A53` 的 heave time-pressure 主贡献峰值位于 `x/L=0.300/0.250`，二者没有同站。
2. 因此，`A33/A53` 的主失败源不能简单归结为“首站自由面法向导数尖峰直接制造 heave 时间压力主峰”。
3. 剩余阻塞进一步收窄为：需要审计 Eq.23/Eq.24 自由面法向导数单位、inner/free/control 匹配符号、开剖面自由面截断，以及中前部站位的 body-potential 尺度。
4. 本轮新增审计仍为 `diagnostic-only`，没有把任何符号翻转、尺度缩放或候选方案写入默认生产路径。

验证状态：

| 检查 | 结果 |
|---|---|
| Ma 2005 探针 | 正常输出；`Hard failures=15`、`pending reference data=8`，Gate 1 仍为 `PENDING` |
| `validation_summary.csv` | `PASS=65`、`FAIL=15`、`NOT_EVALUATED=8`、`INFO=41` |
| 关键 CSV 数值健康 | 未发现数值型 `NaN/Inf` |
| 定向测试 | `python -m pytest -q tests/test_validation.py -k matched_bie_provider_model` 通过 |
| 完整回归 | `python -m pytest -q`：`166 passed` |

## 本轮新增进展：Gradient Stencil / Phase 候选排除审计

本轮把 central、forward、backward、phase-aligned central、phase-aligned forward、phase-aligned backward 以及 startup-gradient 反事实统一整理成“能否进入默认”的排除审计。目的不是寻找局部最好看的曲线，而是防止某个候选只改善部分系数就被误写入生产路径。

新增输出目录：

```text
outputs/matched_bie_provider_stencil_phase_exclusion_probe/results
```

新增文件：

| 文件 | 作用 |
|---|---|
| `ma2005_wigley_iii_coefficients_pressure_gradient_stencil_phase_exclusion_audit.csv` | 逐系数、逐候选记录 gate ratio、相对 current default 的改善/恶化、是否破坏已通过项和行级判定 |
| `ma2005_wigley_iii_coefficients_pressure_gradient_stencil_phase_exclusion_summary.csv` | 按候选汇总 pass count、improved/worsened count、是否破坏当前通过项和默认排除原因 |

关键结果：

| 候选 | pass count | improved | worsened | breaks current pass | max gate ratio | 默认判定 |
|---|---:|---:|---:|---:|---:|---|
| `phase_aligned_forward` | 0/8 | 4 | 3 | 1 | 78.495 | 排除：破坏当前通过项 |
| `phase_aligned_central` | 0/8 | 4 | 3 | 1 | 110.057 | 排除：破坏当前通过项 |
| `phase_aligned_backward` | 0/8 | 4 | 3 | 1 | 136.011 | 排除：破坏当前通过项 |
| `scheme_forward` | 0/8 | 4 | 2 | 1 | 136.888 | 排除：破坏当前通过项 |
| `current_default / scheme_central` | 1/8 | 2 | 2 | 0 | 163.904 | 未通过 Gate 1 |
| `scheme_backward` | 0/8 | 2 | 4 | 1 | 171.183 | 排除：破坏当前通过项 |

本轮判断：

1. `phase_aligned_forward` 是当前候选中最大 gate ratio 最低的方案，但它仍然 `0/8` 通过，因此不能作为默认。
2. 多数 phase-aligned 或 forward/backward stencil 会破坏目前唯一通过的 `B53`，说明“相位对齐/换差分方向”不是一个全局一致修正。
3. 这些候选对 `A33/A53` 基本无帮助，因为二者由 time-derivative pressure 主导，pressure-gradient stencil 不可能解决它们。
4. 剩余工作应从“选择哪个简单 stencil”转向更深的装配链条：Eq.30 forward-speed 项符号/相位、纵向 marching 坐标方向、body-potential 沿站位传播的复相位，以及 time-pressure 与 pressure-gradient 的共同无量纲化。

验证状态：

| 检查 | 结果 |
|---|---|
| Ma 2005 探针 | 正常输出；`Hard failures=15`、`pending reference data=8`，Gate 1 仍为 `PENDING` |
| `validation_summary.csv` | `PASS=65`、`FAIL=15`、`NOT_EVALUATED=8`、`INFO=43` |
| 关键 CSV 数值健康 | 未发现数值型 `NaN/Inf` |
| 定向测试 | `python -m pytest -q tests/test_validation.py -k matched_bie_provider_model` 通过 |
| 完整回归 | `python -m pytest -q`：`166 passed` |

## 本轮新增进展：Pressure-Gradient 首站尖峰审计

本轮新增 Eq.30 forward-speed pressure-gradient 的逐站积分审计，用于检查：

```text
body potential longitudinal derivative -> forward-speed pressure-gradient -> station integral -> coefficient
```

新增输出目录：

```text
outputs/matched_bie_provider_pressure_gradient_spike_probe/results
```

新增文件：

| 文件 | 作用 |
|---|---|
| `ma2005_wigley_iii_coefficients_pressure_gradient_startup_spike_audit.csv` | 逐站输出 pressure-gradient density、梯形积分贡献、贡献占比、纵向梯度增益和首站/峰值标记 |
| `ma2005_wigley_iii_coefficients_pressure_gradient_startup_spike_summary.csv` | 汇总首站、第二站、前两站、其余站和峰值站贡献，并给出去首站/去前两站的诊断性 gate ratio |

关键结果：

| 系数 | 当前 gate ratio | 首站占比 | 前两站占比 | 峰值 `x/L` | 去首站 gate ratio | 诊断结论 |
|---|---:|---:|---:|---:|---:|---|
| `B33` | 23.957 | 0.0639 | 0.1132 | 0.075 | 19.918 | `pressure_gradient_peak_not_limited_to_startup_station` |
| `A35` | 43.563 | 0.0639 | 0.1132 | 0.075 | 39.793 | `pressure_gradient_peak_not_limited_to_startup_station` |
| `B35` | 163.904 | 0.1416 | 0.1640 | 0.025 | 145.299 | `first_active_station_is_peak_but_not_dominant` |
| `B53` | 0.190 | 0.1322 | 0.2288 | 0.075 | 19.955 | `pressure_gradient_peak_not_limited_to_startup_station` |
| `A55` | 2.865 | 0.1322 | 0.2288 | 0.075 | 28.446 | `pressure_gradient_peak_not_limited_to_startup_station` |
| `B55` | 131.032 | 0.2084 | 0.2396 | 0.025 | 105.501 | `first_active_station_is_peak_but_not_dominant` |

本轮判断：

1. 首个活动站 `x/L=0.025` 的 pressure-gradient density 确实偏强，但它并不是全部失败项的主峰；`B33/A35/B53/A55` 的峰值反而在 `x/L=0.075`。
2. 去掉首站不能让失败项通过；对已经通过的 `B53`，去首站会把 gate ratio 从 `0.190` 恶化到 `19.955`。
3. 因此，“删除首站”“首站置零”或简单 startup 平滑不能进入生产默认，只能作为已排除的诊断候选。
4. 剩余阻塞进一步指向纵向 body-potential derivative stencil、相位对齐、station marching 方向和 Eq.30 前进速度压力项的符号/相位装配。

验证状态：

| 检查 | 结果 |
|---|---|
| Ma 2005 探针 | 正常输出；`Hard failures=15`、`pending reference data=8`，Gate 1 仍为 `PENDING` |
| `validation_summary.csv` | `PASS=65`、`FAIL=15`、`NOT_EVALUATED=8`、`INFO=42` |
| 关键 CSV 数值健康 | 未发现数值型 `NaN/Inf` |
| 定向测试 | `python -m pytest -q tests/test_validation.py -k matched_bie_provider_model` 通过 |
| 完整回归 | `python -m pytest -q`：`166 passed` |
