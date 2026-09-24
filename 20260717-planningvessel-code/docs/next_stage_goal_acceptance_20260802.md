# 下一阶段目标与验收条件：Ma 2005 Wigley III Gate 1

日期：2026-08-02

## 当前进展

当前程序已经完成第一轮可扩展、可测试、边界清楚的升级，并进入 Ma--Duan--Song 型线性高速 2.5D matched BIE 求解器的文献硬验收排错阶段。

| 项目 | 当前状态 |
|---|---|
| 主程序 | 已建立 `planing_seakeeping` Python 包与 `python -m planing_seakeeping run/validate` 命令 |
| 生产主线 | 固定为 `LinearFrequencyProvider(source="linear_2p5d", formulation="matched_bie")` |
| 生产路由 | 固定为 `metadata["provider_route"] == "matched_bie_station_sweep"` |
| 当前硬基准 | Ma 2005 Wigley III 八个频域水动力系数 |
| 当前结果 | `B53` 通过；`A33/B33/A35/B35/A53/A55/B55` 未通过 |
| 最新验证统计 | `PASS=65`，`INFO=50`，`NOT_EVALUATED=8`，`FAIL=15` |
| 最新新增审计 | 已加入 A/B 映射、Eq.34 归一化、系数族共享尺度、Eq31/Eq32 forward-speed identity 候选排除审计、站位级 forward identity 定位审计、A/B 复幅值截面力导数代理审计、自由面 marching/时间步候选排除审计、Eq.30/Eq.32 四分量贡献审计、station mapping/gradient 审计，以及 mapped-gradient 候选排除审计 |
| 回归测试 | `python -m pytest -q` 已通过，结果为 `169 passed` |

最新输出目录：

```text
outputs/matched_bie_provider_mapped_gradient_candidate_probe/results
```

最新审计说明：单独改变 A/B 符号、整体翻转、或把 Eq.34 无量纲尺度改成 `L^0/L^1/L^2`，均不能让八个 Wigley III 系数共同通过。逐系数反推比例虽然可以让表面误差为零，但所需比例差异极大，不能解释为一个共同的物理归一化约定，因此只能作为排除证据，不能进入默认模型。

2026-08-02 进一步新增系数族共享尺度审计，输出目录为：

```text
outputs/matched_bie_provider_coefficient_family_scale_probe/results
```

新增文件：

| 文件 | 作用 |
|---|---|
| `ma2005_wigley_iii_coefficients_coefficient_family_scale_exclusion_audit.csv` | 逐系数记录 A/B 家族、广义力行、辐射模态列、对角/耦合类和 heave/pitch 矩阵单元共享尺度候选的计算值、误差和排除原因 |
| `ma2005_wigley_iii_coefficients_coefficient_family_scale_exclusion_summary.csv` | 汇总每个共享尺度候选的分组数、通过数、最大 gate ratio、尺度离散度和默认决策 |

关键结果如下：

| 候选 | 分组数 | 通过数 | 最大 gate ratio | 结论 |
|---|---:|---:|---:|---|
| `column_and_ab_family_scale` | 4 | 5/8 | 约 `5.98` | 当前最好，但仍不能通过八系数 Gate 1 |
| `matrix_cell_shared_ab_scale` | 4 | 2/8 | 约 `6.19` | 不能解释同一 heave/pitch 单元内的 A/B 差异 |
| `radiation_column_family_scale` | 2 | 0/8 | 约 `6.39` | 不能归结为 radiation column 共同比例错误 |
| `single_global_scale` | 1 | 1/8 | 约 `17.89` | 排除单一全局尺度错误 |
| `current_default` | 1 | 1/8 | 约 `163.90` | Gate 1 仍为 `PENDING` |

本轮判断：错误不能简化为 A/B 家族、heave/pitch 行、radiation 列、对角/耦合类或矩阵单元的共同尺度问题。剩余阻塞应继续聚焦 Eq.30/Eq.32 的压力分量装配、站位纵向传播、前进速度梯度与端部项之间的重复/漏计/相位关系。

2026-08-02 继续新增 Eq31/Eq32 forward-speed identity 审计，输出目录为：

```text
outputs/matched_bie_provider_eq31_eq32_identity_probe/results
```

新增文件：

| 文件 | 作用 |
|---|---|
| `ma2005_wigley_iii_coefficients_eq31_eq32_forward_identity_audit.csv` | 逐系数对比当前 hybrid 路径、Eq31 direct-gradient 路径、Eq32 Stokes body+end 路径，以及 `gradient - (Stokes body + end)` 的 forward-speed 等价残差 |
| `ma2005_wigley_iii_coefficients_eq31_eq32_forward_identity_summary.csv` | 汇总每条方程路径的通过数、最大 gate ratio、等价残差和默认排除原因 |

关键结果如下：

| 路径 | 物理含义 | 通过数 | 最大 gate ratio | 结论 |
|---|---|---:|---:|---|
| `eq31_direct_time_plus_gradient` | 直接采用 Eq.31 的 time + finite-difference gradient，不额外加 end term | 0/8 | 约 `148.95` | 不能作为默认修正 |
| `eq32_stokes_time_plus_body_plus_end` | 采用 Eq.32 的 time + Stokes body + end-contour，替代直接 `dphi/dx` | 0/8 | 约 `161.00` | 不能作为默认修正 |
| `current_hybrid_eq30_gradient_plus_end` | 当前默认的 time + gradient + end | 1/8 | 约 `163.90` | 仍未通过 Gate 1 |
| `forward_identity_gradient_minus_body_end` | 检查 Eq31 forward gradient 是否等价于 Eq32 body + end | 2/8 | 残差最大远超容差 | Eq31/Eq32 forward-speed 路径尚未闭合 |

本轮判断：

1. 不能把 Gate 1 失败简单归因于“应该去掉 end term”。去掉 end term 的 Eq31 direct 路径虽然局部改善 `B33/A35/B35/B55`，但八项仍全部失败。
2. 也不能把默认路径直接替换成 Eq32 Stokes 形式。`time + Stokes body + end` 同样为 `0/8`，且会严重破坏 `B53/A55`。
3. `gradient - (Stokes body + end)` 等价残差在 6 个系数上不闭合，说明当前更深层的问题是：由站位势函数导出的 `dphi/dx`、Stokes body row `m_i`、end-contour row `N_i`、端部选取和坐标/相位约定之间尚未形成同一套方程链。
4. 下一步应优先做站位级 forward identity 审计：逐站比较 `rho U dphi/dx * N_i` 与 Stokes body 密度及端部边界项的贡献来源，尤其检查 `x/L=0.025` 附近的启动站和 `B53/A55` 的 pitch row。

2026-08-02 已新增站位级 forward identity 审计，输出目录为：

```text
outputs/matched_bie_provider_station_forward_identity_probe/results
```

新增文件：

| 文件 | 作用 |
|---|---|
| `ma2005_wigley_iii_coefficients_station_forward_identity_audit.csv` | 逐站输出 pressure-gradient、Stokes body forward、end contour 和 `gradient - (Stokes + end)` residual |
| `ma2005_wigley_iii_coefficients_station_forward_identity_summary.csv` | 汇总各系数的 residual、站位积分闭合误差、峰值站位、首站占比、端部占比和残差质心 |

关键结果：站位积分 residual 与 comparison 中的全船 residual 闭合到 `1.8e-15` 量级；`B33/B53/A35/A55/B35/B55` 的 forward identity residual 均表现为 `residual_distributed_along_station_sweep`，不是单纯端部项错误或单一首站尖峰。`A33/A53` 的 forward identity residual 为零，因此它们的失败源仍应集中在 heave time-derivative pressure/body-potential scale 链条，而不是 forward-speed 项。

2026-08-02 继续新增 A/B 复幅值截面力导数代理审计，输出目录为：

```text
outputs/matched_bie_provider_section_force_derivative_probe/results
```

新增文件：

| 文件 | 作用 |
|---|---|
| `ma2005_wigley_iii_coefficients_section_force_derivative_audit.csv` | 用同一矩阵元的 `Aij/Bij` 成对数据重建复截面广义力，逐站比较当前 Eq.30 pressure-gradient 与 `U/(-i omega) dF_time/dx` 代理路径 |
| `ma2005_wigley_iii_coefficients_section_force_derivative_summary.csv` | 汇总每个系数的 pressure-gradient 积分、截面力导数代理积分、差值、峰值站位、首站占比和残差质心 |

关键结果：最强差异仍来自 `B33`，当前 pressure-gradient 积分为 `9.04507`，由 time-pressure 截面力导数得到的代理积分为 `2.05533`，差值为 `6.98974`。该差异的峰值在 `x/L=0.025`，但峰值占比仅约 `0.0946`，残差质心约为 `x/L=0.252`，结论为 `difference_distributed_along_station_sweep`。因此，下一步不应继续用单点删除、端部项缩放或符号翻转解释问题，而应检查相邻站 body potential 插值、变化剖面面元对应关系、`N_i(x)` 与 `m_i` 的积分分部关系，以及 `dphi/dx` 是否需要在固定控制面/固定物面映射下计算。

2026-08-02 继续新增自由面 marching 与时间步候选排除审计，输出目录为：

```text
outputs/matched_bie_provider_time_step_gate_summary_probe/results
```

新增文件：

| 文件 | 作用 |
|---|---|
| `ma2005_wigley_iii_coefficients_free_surface_marching_candidate_detail.csv` | 逐系数比较关闭 marching、自由面速度缩放、历史项关闭、`time_step_scale=0.5/0.25` 等候选的计算值、误差和通过状态 |
| `ma2005_wigley_iii_coefficients_free_surface_marching_candidate_summary.csv` | 汇总各候选通过数、最大 gate ratio、中位 gate ratio、改善/恶化行数和 diagnostic-only 结论 |
| `ma2005_wigley_iii_coefficients_gate1_failure_summary.csv` | 将自由面 marching/时间步候选排除证据纳入 Gate 1 失败审计 |

关键结果：关闭自由面 marching 是当前候选中整体最好的排错线索，可改善 6/8 行，但仍只通过 1/8，最大 gate ratio 约为 `21.47`，因此不能替代默认物理路径。真正的时间步缩小候选也不能通过硬基准：`time_step_scale=0.25` 通过 0/8，最大 gate ratio 约为 `61.22`；`time_step_scale=0.5` 同样通过 0/8。因此，问题不应被简化为自由面 marching 时间步粗细，而应继续追查自由面已知势项如何进入内域方程、自由面站位与船体站位交错关系、以及 station-to-station 势函数传播的一致性。

2026-08-02 继续新增 Eq.30/Eq.32 四分量贡献审计，输出目录为：

```text
outputs/matched_bie_provider_eq30_component_audit_probe/results
```

新增文件：

| 文件 | 作用 |
|---|---|
| `ma2005_wigley_iii_coefficients_eq30_component_contribution_audit.csv` | 逐系数列出 Eq.30 time-derivative pressure、Eq.30 forward-speed pressure-gradient、Eq.32 Stokes body forward-speed 和 Eq.32 end contour 四类贡献，并给出主导分量、闭合残差、反推单分量尺度和剩余阻塞 |
| `ma2005_wigley_iii_coefficients_eq30_component_contribution_summary.csv` | 汇总 8 个 Wigley III 系数的通过数、最大 gate ratio、最大闭合残差、主导分量计数、失败源计数和下一步判断 |
| `ma2005_wigley_iii_coefficients_gate1_failure_summary.csv` | 增加 `eq30_component_contribution_audit` 要求行，使四分量审计成为 Gate 1 失败证据的一部分 |

关键结果：四分量贡献审计显示当前默认路径仍只通过 `1/8`，最大 gate ratio 约为 `163.904`，但分量闭合残差仍约为 `1.55e-15`，说明问题不是输出记账错误。默认分量主导关系为：`time_derivative_pressure:3`，`forward_speed_pressure_gradient:5`。失败源进一步归类为：`A33/A53` 属于 `time_derivative_body_potential_scale`，反推所需 time scale 分别约为 `0.097` 和 `0.104`；`B33/A35/A55/B55` 属于 `forward_speed_pressure_gradient_station_mapping`，反推 gradient scale 差异较大且有正有负；`B35` 属于 `mixed_component_cancellation`。这些反推尺度只能说明“哪条链不闭合”，不能作为生产默认调参。下一步应优先审计开放截面 body potential 尺度、自由面已知势项进入内域方程的方式、相邻站 body potential 映射，以及固定物面或固定控制面下的 `dphi/dx` 定义。

2026-08-02 继续新增 station mapping/gradient 审计，输出目录为：

```text
outputs/matched_bie_provider_station_mapping_gradient_probe/results
```

新增文件：

| 文件 | 作用 |
|---|---|
| `ma2005_wigley_iii_coefficients_station_mapping_gradient_audit.csv` | 将每个系数的 Eq.30 四分量失败源与相邻站 transfer path 对齐，逐系数列出压力梯度峰值站对、体势跳变、相位跳变、面元几何跳变、水线宽/浸没面积跳变和 `dphi/dx` 增益 |
| `ma2005_wigley_iii_coefficients_station_mapping_gradient_summary.csv` | 汇总 forward-gradient 失败数、high mapping risk 数、近艉部启动区峰值数、最大体势跳变、最大几何跳变、最大纵向导数增益和下一阻塞项 |
| `ma2005_wigley_iii_coefficients_gate1_failure_summary.csv` | 增加 `station_mapping_gradient_audit` 要求行，使站位映射/纵向导数证据进入 Gate 1 失败审计 |

关键结果：4 个 forward-gradient 主导失败全部被标记为 high mapping risk，8 个系数的压力梯度峰值站对都出现在 `x/L=0.0375` 附近。峰值处最大相邻体势跳变约为 `1.058`，最大横向面元中点跳变约为 `0.485`，最大水线宽和浸没面积跳变约为 `0.487`，最大 `dphi/dx` 增益约为 `98.28/L`。这说明下一步不应把问题处理成平滑、删首站、改端部项或比例缩放，而应推导并实现固定物面或固定控制面上的相邻站体势映射和纵向导数定义，再与 Eq.32 Stokes body/end identity 作同一公式链对照。

2026-08-02 继续新增 mapped-gradient pressure-gradient 候选，输出目录为：

```text
outputs/matched_bie_provider_mapped_gradient_candidate_probe/results
```

新增或扩展内容：

| 内容 | 作用 |
|---|---|
| `mapped_fixed_y_central/forward/backward` | 将邻站体势插值到目标站同一物理横向坐标 `y` 后，再按 central/forward/backward 求 `dphi/dx` |
| `mapped_normalized_y_central/forward/backward` | 将邻站体势插值到同一归一化横向坐标 `y/(Bwl/2)` 后，再按 central/forward/backward 求 `dphi/dx` |
| `ma2005_wigley_iii_coefficients_startup_pressure_gradient_candidate_summary.csv` | 从原来的 10 个候选扩展为 16 个候选，比较每个候选对八系数 gate ratio 的影响 |
| `ma2005_wigley_iii_coefficients_pressure_gradient_stencil_phase_exclusion_summary.csv` | 将 mapped-gradient 候选纳入候选排除证据，防止局部改善被误用为默认修正 |

关键结果：mapped-gradient 候选均未通过 Gate 1，全部为 `0/8` 通过。`mapped_fixed_y_forward` 是 mapped 候选中最好的一项，但最大 gate ratio 仍约为 `130.24`，只能改善 4 行并恶化 2 行；`mapped_normalized_y_forward` 最大 gate ratio 约为 `137.82`。总体最好候选仍是旧的 `phase_aligned_forward`，但也只有 `0/8` 通过，最大 gate ratio 约为 `78.49`，且会破坏当前已经通过的系数。因此，简单的固定横向坐标插值或归一化横向坐标插值不能作为生产默认修正；下一步必须继续追查完整的固定物面/固定控制面导数、自由面已知势项、Stokes body term 与 end contour term 的同一公式链闭合。

## 下一阶段唯一目标

在不切换主模型、不引入经验补偿、不使用事后拟合比例的前提下，闭合 Ma--Duan--Song 型线性高速 2.5D matched BIE 求解器的压力恢复与整船装配链条，使同一套默认 `matched_bie_station_sweep` 配置能够通过 Ma 2005 Wigley III 八个频域水动力系数的硬验收。

更具体地说：

> 下一阶段只做一件事：把 Eq.30 压力恢复、Eq.32 前进速度体积分与端部项、heave/pitch 广义力坐标、站位间纵向梯度、整船积分和 Eq.34 无量纲化统一到同一套可追溯公式链中，并让 `A33/B33/A55/B55` 相对误差不超过 15%，`A35/B35/A53/B53` 相对误差不超过 30%。

## 必须完成的工作

| 编号 | 工作 | 产物 |
|---|---|---|
| 1 | 审计 Eq.30 中 `-rho*i*omega*phi` 与 `rho*U*dphi/dx` 的相位、符号和站位差分方向 | 每个系数的 time-pressure、pressure-gradient、station contribution 明细 CSV |
| 2 | 审计 Eq.32 Stokes body forward-speed term 与 end-contour term 是否与 Eq.30 梯度项重复、漏计或符号不一致 | body/end 分量拆分表、闭合残差表、候选排除表 |
| 3 | 审计 heave/pitch 广义力和力矩臂坐标映射 | 论文坐标到程序坐标的机器可读映射表，且每次修改均有八系数对照 |
| 4 | 修正真实公式链中的错误，只允许基于方程、单位、坐标或边界条件推导进入生产默认 | 代码变更、公式说明、修改前后误差对照 |
| 5 | 保留所有未通过候选为 diagnostic-only | 每个候选有 pass count、max gate ratio、排除原因 |
| 6 | 更新验证文档 | 记录采用公式、失败来源、被排除候选、剩余边界和最终 Gate 1 状态 |

## 硬验收条件

| 类别 | 验收条件 | 判定方式 |
|---|---|---|
| 入口唯一 | 只能使用 `linear_2p5d/matched_bie` 主线 | `comparison.csv` 中 `provider_route == matched_bie_station_sweep` |
| 八系数精度 | `A33/B33/A55/B55 <= 15%`，`A35/B35/A53/B53 <= 30%` | 每行 `gate_error_ratio <= 1.0` 且 `gate_status == PASS` |
| 压力闭合 | 最终系数等于 Eq.30/Eq.32 分量之和 | `current_force_closure_residual_value < 1e-9` |
| 数值健康 | 无 `NaN`、无 `Inf`、无空矩阵伪通过 | 自动验证 CSV 与测试断言通过 |
| 可追溯性 | 每个系数都能追溯到站位贡献、压力分量、端部项和无量纲化 | 输出 comparison、station contribution、pressure balance、failure audit 表 |
| 非调参 | 不使用逐系数比例、全局经验缩放、强行符号翻转或 reduced-order 补偿 | 候选表必须标注 `diagnostic-only`，默认配置不得依赖它们 |
| 自动测试 | 现有功能不回退 | `python -m pytest -q` 全部通过 |
| 文档同步 | 结果、原因、失败来源和边界清楚记录 | 更新 `docs` 中最终 Gate 1 审计文档 |

固定验收命令：

```powershell
python -m planing_seakeeping validate `
  --benchmark all `
  --out outputs\gate1_final_validation\results `
  --reference-root outputs\matched_bie_provider_gate_probe\reference `
  --ma-hydro-model matched_bie_provider `
  --ma-bem-free-surface-panels 4 `
  --ma-bem-body-panels 8
```

辅助回归命令：

```powershell
python -m pytest -q
```

## 暂不纳入下一阶段硬验收

| 内容 | 原因 |
|---|---|
| SL-7 硬验收 | 仍缺真实 machine-readable station offsets，只能做 surrogate 趋势或流程检查 |
| C1 三体船硬验收 | 仍缺主片体和侧片体真实 offsets，不能证明 cross-radiation 与 cross-diffraction |
| Delft 372 多体船 | 已有几何线索，适合作为 Gate 2 多体船扩展，不替代 Gate 1 |
| Fridsma/Katayama 运动响应 | 适合检查运动合理性和非线性趋势，不替代 Ma 2005 系数闭合 |
| Sun--Faltinsen 强非线性 2D+t BEM | 属于后续生产内核，应在线性 2.5D Gate 1 通过后再设硬验收 |
| 水翼控制闭环 | 需要真实水翼、舵机、控制器和试验数据，不能与当前 Gate 1 混合验收 |

## 一句话完成判据

只有当固定命令在默认 `matched_bie_station_sweep` 主线下使 Ma 2005 Wigley III 八个系数全部通过，并且完整测试集通过时，下一阶段才算完成；否则只能宣布 Gate 1 仍为 `PENDING`，并报告已定位的失败来源和已排除的错误修正路径。
