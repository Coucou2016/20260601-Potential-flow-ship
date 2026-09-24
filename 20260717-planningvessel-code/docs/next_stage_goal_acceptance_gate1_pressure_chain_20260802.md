# 下一阶段目标与验收条件：把线性 2.5D Gate 1 做实

日期：2026-08-02

## 当前进展

当前项目已经完成第一轮“可继续扩展、可测试、边界清楚”的升级，主要成果包括：

| 类别 | 当前状态 |
|---|---|
| 主程序 | 已建立 `planing_seakeeping` Python 包、命令行入口、示例配置、输出报告和可视化链路 |
| 文献与方法 | 已整理 Faltinsen、Ma--Duan--Song、Sun--Faltinsen、Fridsma、Delft 372、C1 trimaran、ITTC 等资料路线 |
| 验证框架 | 已形成 `validate` 命令、基准数据、诊断 CSV、Gate 1 审计表和回归测试 |
| 最新验证输出 | `outputs/matched_bie_provider_projection_balance_probe/results` |
| 最新验证统计 | `PASS=65`，`INFO=55`，`NOT_EVALUATED=8`，`FAIL=15` |
| 自动化测试 | 最近一次完整测试为 `python -m pytest -q`，结果 `173 passed` |
| Gate 1 状态 | `PENDING`，尚不能宣布完整线性 2.5D 验证通过 |

Ma 2005 Wigley III 八个频域水动力系数的当前状态如下：

| 系数 | 参考值 | 当前计算值 | 当前状态 |
|---|---:|---:|---|
| `A33` | 1.000 | 10.290 | FAIL |
| `B33` | 2.100 | 9.646 | FAIL |
| `A35` | -0.200 | -2.814 | FAIL |
| `B35` | 0.130 | 6.522 | FAIL |
| `A53` | 0.150 | 1.445 | FAIL |
| `B53` | -0.100 | -0.094 | PASS |
| `A55` | 0.063 | 0.090 | FAIL |
| `B55` | 0.090 | 1.859 | FAIL |

当前最重要的判断是：失败已经不是“程序整体不可用”的模糊问题，而是集中在 Ma--Duan--Song 线性高速 2.5D matched boundary integral equation 路线中的压力恢复、站位推进方向、前进速度梯度项、端部项和整船装配链路上。

已排除或降级为诊断候选的方向包括：单纯符号翻转、单纯归一化缩放、逐系数拟合、经验补偿、删除局部峰值站、自由面时间步粗细调整、端部项简单加减、横向插值后直接替代默认结果等。这些候选可以帮助定位问题，但不能作为默认模型修正。

最近新增的 `stokes_end_lever_consistency` 审计给出两个关键结论：

1. `heave` 行的 `m3 = 0` 判断是自洽的，不能把当前失败简单归因于 Stokes body 项漏加。
2. `end contour` 的力臂一致性通过，但 Eq.31 的前进速度压力梯度项与 Eq.32 的 `Stokes body + end contour` 恒等关系只在 2/8 个系数上闭合，因此下一步必须继续追查坐标、站位顺序、纵向导数、控制面匹配和端部轮廓定义。

本轮新增的 `station_marching_direction` 审计进一步把“站位顺序”问题从模糊嫌疑变成了可复核证据：

| 项目 | 审计结论 |
|---|---|
| A1 局部时间 marching | `8/8` 个系数均满足艏到艉推进 |
| 实际首个推进站 | `x/L = 0.975`，即接近艏端 |
| 实际最后推进站 | `x/L = 0.025`，即接近艉端 |
| 压力梯度峰值位置 | `8/8` 个系数均在艉端附近 |
| 是否为 marching 起点峰值 | `0/8`，不是起点初始化峰值 |
| 结论 | `a1_bow_to_aft_marching_confirmed_aft_terminal_gradient_peak_remains` |

这说明“把 station sweep 方向反过来”不应作为默认修正。当前更准确的失败焦点是：艉端终端压力梯度差分、end-contour 站位约定，以及 Eq.31/Eq.32 前进速度恒等式之间没有闭合。

本轮继续新增 `aft_terminal_end_closure` 审计，用来判断“只改艉端终端站”或“只给 end-contour 项乘一个统一系数”能否解释失败。最新结论如下：

| 项目 | 审计结论 |
|---|---|
| 可计算 required end scale 的系数 | `6/8`，`A33/A53` 因当前 end term 为零不可用 |
| required end scale 范围 | `2.0385` 到 `15.0398` |
| required end scale 绝对跨度 | 约 `7.3778` 倍 |
| 艉端前 10% 船长残差高占比行 | `0/8` |
| 艉端前 10% 残差占比范围 | `0.0` 到 `0.3638` |
| end term / endpoint forward-gradient 比值范围 | `0.4727` 到 `0.8035` |
| 结论 | `end_scale_not_finite_for_all_rows_terminal_band_not_sufficient` |

因此，简单的艉端删除、端点梯度替换或统一端部项缩放不能作为默认修正。新增的 `complex_forward_identity` 审计进一步把 added mass 与 damping 按矩阵单元还原为同一个复广义力 `F_ij = omega^2 A_ij - i omega B_ij`。结果显示，当前硬门槛八行中 `33` 和 `35` 缺少同频 A/B 配对，不能被强行复数重构；可配对的 `53` 和 `55` 虽然最终系数与分量求和的闭合残差接近零，但 Eq.31 pressure-gradient 与 Eq.32 `Stokes body + end contour` 的复数恒等式残差范数约为 `0.8335` 到 `0.9008`。最新的 `projection_derivative_balance` 审计又把 `G = Eq.31 direct pressure-gradient`、`D = d(phi*N_i)/dx projection-derivative proxy` 和 `S+E = Eq.32 Stokes body + end contour` 放在同一表中比较，结果为 `G_vs_D_pass=2/8`、`G_vs_SE_pass=2/8`、`D_vs_SE_pass=2/8`，最大残差范数分别为 `1.33726`、`0.93351`、`1.29414`。这说明 projection-derivative proxy 也不能作为默认替代。下一步需要推导的是分布式的 Eq.31/Eq.32 恒等式：包括控制面或物面上的纵向导数定义、轮廓方向、`N_i/m_i` 的符号与投影，以及船体站位变化时的势函数映射。

## 下一阶段目标

在保持默认主线入口为 `LinearFrequencyProvider(source="linear_2p5d", formulation="matched_bie")`，并保持输出元数据 `provider_route == "matched_bie_station_sweep"` 的前提下，完成 Ma--Duan--Song 型线性高速 2.5D matched BIE 求解器的 Gate 1 修正或封口审计。

具体目标是：以 Ma 2005 Wigley III 八个公开频域水动力系数为硬基准，查明并修正 Eq.30 压力恢复、Eq.31/Eq.32 前进速度等价项、站位局部时间推进方向、纵向导数、端部轮廓项、广义力坐标和整船积分装配中的真实公式或离散错误，使默认模型达到可复现、可追溯、可验证的线性 2.5D 基准精度。

一句话概括：

> 下一阶段只解决一个核心问题：把 Ma 2005 Wigley III 八个水动力系数从“诊断清楚但仍失败”推进到“默认 matched BIE 主线可通过硬验收”；如果仍不能通过，则必须把失败源、已排除路径和所缺数据或公式证据完整封口。

## 验收条件

| 类别 | 必须满足的条件 | 判定方式 |
|---|---|---|
| 主线入口 | 默认仍使用 `linear_2p5d/matched_bie`，不得切换到 legacy、经验模型、拟合模型或 reduced-order 替代模型 | 输出 `metadata["provider_route"] == "matched_bie_station_sweep"` |
| 八系数精度 | `A33/B33/A55/B55` 误差不超过 15%；`A35/B35/A53/B53` 误差不超过 30% | `ma2005_wigley_iii_coefficients_comparison.csv` 中八项全部 `PASS`，且 `gate_error_ratio <= 1.0` |
| 压力链闭合 | Eq.30 时间导数压力项、前进速度压力梯度项、Eq.32 Stokes body 项、end contour 项必须能闭合重构最终系数 | 分量求和残差目标 `< 1e-9` |
| 公式可追溯 | 每一处修正必须能对应到文献公式、坐标定义、边界条件、控制面匹配、站位 marching 或积分离散定义 | 代码、CSV 字段和 Gate 1 报告中均有记录 |
| 诊断纪律 | 只改善个别系数、依靠后处理缩放、逐系数调参或经验补偿的候选不得进入默认模型 | 保持 `diagnostic-only`，并在审计表中说明排除原因 |
| 数值稳定性 | 不得出现 `NaN`、`Inf`、空矩阵伪通过、未报告的奇异矩阵或异常条件数 | `validation_summary.csv`、诊断 CSV 和测试全部通过稳定性检查 |
| 站位方向证据 | 必须证明 station 存储顺序、A1 局部时间 marching 顺序和压力梯度峰值位置三者可区分 | `station_marching_direction_audit.csv` 与 `station_marching_direction_summary.csv` |
| 艉端与端部项证据 | 必须证明简单艉端删除、端点替换或统一 end-contour 缩放是否足以解释 Eq.31/Eq.32 残差 | `aft_terminal_end_closure_audit.csv` 与 `aft_terminal_end_closure_summary.csv` |
| 回归测试 | 现有功能不得退化 | 相关定向测试通过，且 `python -m pytest -q` 全部通过 |
| 文档同步 | 目标、修正依据、失败项、通过项、排除候选、剩余风险必须同步到 `docs` 和验证报告 | 生成新的阶段报告或更新当前 Gate 1 文档 |
| 数据边界 | SL-7 与 C1 trimaran 在没有真实 machine-readable offsets 前不得作为硬验收基准 | 继续标记为 `SURROGATE_NOT_FOR_VALIDATION` |

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

```powershell
python -m pytest -q
```

## 合格结局

下一阶段只有两种合格结局：

1. **Gate 1 通过**：Ma 2005 Wigley III 八个系数全部达标，默认 `matched_bie_station_sweep` 主线保持不变，完整回归测试通过，文档同步完成。
2. **Gate 1 保持 PENDING 但失败封口**：如果仍不能通过，必须交付明确失败源、已排除候选、不能继续推进所缺的公式或数据证据，并说明为什么当前结果不能宣称为完整 2.5D 验证通过。

## 本轮新增证据

本轮已经完成一项封口式审计：`station_marching_direction`。它不改变默认结果，只把内部站位推进方向显式写入 CSV 和 Gate 1 failure summary。最新结果表明，当前代码并不是从艉向艏错误 marching；代码按 A1 Eq.7 的局部时间从艏向艉推进，然后再按从艉到艏的 `x` 数组顺序进行积分输出。因此，下一步不应反转 marching 方向，而应集中检查艉端终端差分、端部轮廓项和 Eq.31/Eq.32 的前进速度项闭合。

本轮又完成一项封口式审计：`aft_terminal_end_closure`。它同样不改变默认结果，只检验两个常见但危险的“看似简单”的修正方向：第一，是否可以删掉或替换艉端终端压力梯度；第二，是否可以给 end-contour 项乘一个统一尺度。结果显示，这两条路都不能直接进入默认模型，因为残差不是集中在艉端前 10% 船长，而且闭合所需端部项尺度在不同系数之间差异过大。

本轮继续完成一项封口式审计：`complex_forward_identity`。它不改变默认结果，只把同一矩阵单元的 `A_ij` 与 `B_ij` 合成为复广义力后检查 Eq.31/Eq.32 的幅值和相位闭合。最新结果为：`pairable=2/4`，可配对矩阵单元为 `53;55`；`unpairable=2/4`，不可配对矩阵单元为 `33;35`，原因是当前硬门槛行中的 A/B 频率不一致；`identity_pass=0`，`identity_fail=2`；`max_complex_identity_residual_norm=0.900796`，`median_complex_identity_residual_norm=0.867154`；`max_current_force_closure_residual_norm=2.08168e-16`。这说明当前输出分量自身的求和闭合是好的，但 Eq.31 pressure-gradient 与 Eq.32 `Stokes body + end contour` 在复数广义力层面仍不等价，不能用简单符号候选或统一尺度候选进入默认模型。

本轮又完成一项封口式审计：`projection_derivative_balance`。它不改变默认结果，只把三条前进速度路径并排：`G = Eq.31 direct pressure-gradient`、`D = d(phi*N_i)/dx projection-derivative proxy`、`S+E = Eq.32 Stokes body + end contour`。最新结果为：`row_count=8`，`finite_row_count=8`，`same_frequency_pair_count=4`，`frequency_mismatch_or_missing_count=4`；`gradient_projection_derivative_pass_count=2`，`gradient_stokes_end_pass_count=2`，`projection_derivative_stokes_end_pass_count=2`；`max_gradient_projection_derivative_residual_norm=1.33726`，`max_gradient_stokes_end_residual_norm=0.93351`，`max_projection_derivative_stokes_end_residual_norm=1.29414`；结论为 `same_frequency_projection_balance_does_not_close`。这说明 `d(phi*N_i)/dx` 投影导数代理不能解释当前 pressure-gradient 与 Stokes/end 的差异，也不能作为默认修正。下一步应追查固定控制面导数、变截面几何映射、`N_i/m_i` 的投影方向和 `C_A` 端部轮廓定义。
