# 下一阶段目标与验收条件

日期：2026-08-01

## 当前进展快照

当前项目已经完成第一轮可扩展、可测试、边界清楚的升级，主程序位置为：

```text
D:/Projects/20260601-Potential-flow-ship/20260717-planningvessel-code
```

已经具备的基础包括：

| 项目 | 当前状态 |
|---|---|
| Python 包与命令行 | 已建立 `planing_seakeeping` 包和 `python -m planing_seakeeping run/validate` 命令 |
| 统一水动力入口 | 已接入 `LinearFrequencyProvider(source="linear_2p5d", formulation="matched_bie")` |
| 主线与旧模型隔离 | `matched_bie_station_sweep` 已作为第二轮主线；legacy / reduced-order 模型只作为对照 |
| 数据与验证目录 | 已建立 `benchmarks`、`configs`、`docs`、`outputs` |
| Delft 372 双体几何 | 已有 `delft372_demihull_offsets.csv`，可作为下一轮多体几何输入 |
| SL-7 与 C1 三体船 | 仍缺真实 machine-readable offsets，不能作为硬验收，只能作为待补充或替代趋势检查 |
| 当前最新验证状态 | `PASS=65`、`FAIL=15`、`NOT_EVALUATED=8`、`INFO=34` |
| Ma 2005 Wigley III Gate 1 | 仍为 `PENDING/FAIL`；八个核心系数中当前仅 `B53` 通过 |

最新主要证据目录：

```text
outputs/matched_bie_provider_inner_free_block_normalization_probe/results
```

当前 Wigley III 八个核心系数结果如下：

| 系数 | 参考值 | 当前计算值 | gate ratio | 状态 |
|---|---:|---:|---:|---|
| `A33` | 1.000 | 10.290 | 61.933 | `FAIL` |
| `B33` | 2.100 | 9.646 | 23.957 | `FAIL` |
| `A35` | -0.200 | -2.814 | 43.563 | `FAIL` |
| `B35` | 0.130 | 6.522 | 163.904 | `FAIL` |
| `A53` | 0.150 | 1.445 | 28.772 | `FAIL` |
| `B53` | -0.100 | -0.094 | 0.190 | `PASS` |
| `A55` | 0.063 | 0.090 | 2.865 | `FAIL` |
| `B55` | 0.090 | 1.859 | 131.032 | `FAIL` |

已经排除或暂不接受为生产默认的方向包括：

| 方向 | 当前判断 |
|---|---|
| 只调 Eq.23 自由面 block 的 `2π` 或 `1/(2π)` 归一化 | 不能通过 Gate 1 |
| 移除 `known_phi_free_rhs` | 可显著改善部分项，但仍只有 `1/8` 通过，且缺物理闭合 |
| 只改端部项符号或权重 | 有局部改善，但不能整体通过 |
| 只改 pressure-gradient 差分 | 仍不能通过 Gate 1 |
| 只拆 pitch body condition | 可定位 pitch 列问题，但不能解释 heave 行和整体误差 |

## 下一阶段总目标

在现有主线

```python
LinearFrequencyProvider(
    source="linear_2p5d",
    config=Linear2p5DProviderConfig(formulation="matched_bie"),
)
```

下，把 Ma--Duan--Song 型线性高速 2.5D matched BIE 求解器从“可运行、可诊断的研究原型”推进为“可用公开文献数据验收的最小完整频域内核”。

下一阶段只以 Ma 2005 Wigley III 为硬验收对象，集中闭合 Eq.30 pressure recovery 与 Eq.32 forward-speed/end-contour 装配链条，使同一套默认配置下的 `A33/B33/A55/B55` 相对误差不超过 15%，`A35/B35/A53/B53` 相对误差不超过 30%。在达到该目标前，SL-7、C1 三体船、Fridsma/Katayama、Delft 372 和水翼模块均保持为扩展验证或待补充入口，不替代 Gate 1。

## 下一阶段必须完成的工作

| 编号 | 工作项 | 交付物 |
|---|---|---|
| 1 | 接通 Eq.30/Eq.32 pressure-balance 诊断链 | 生成 `ma2005_wigley_iii_coefficients_eq30_pressure_balance_candidate_detail.csv` 和 `summary.csv` |
| 2 | 逐项审计压力恢复 | 表中必须拆出 time-derivative pressure、forward-speed pressure-gradient、Stokes body forward-speed、end-contour 四类贡献 |
| 3 | 固定生产入口 | `metadata["provider_route"]` 必须稳定等于 `matched_bie_station_sweep` |
| 4 | 修正只允许来自方程溯源 | 任何进入默认配置的改动，必须能追溯到 Ma 2005 / Faltinsen 的方程符号、坐标、归一化或积分方向 |
| 5 | 建立二维剖面单元验收 | 至少一个解析或半解析二维剖面测试证明 BIE 符号、相位、压力积分和力矩臂一致 |
| 6 | 输出完整验证证据 | 每次探针必须输出 CSV、Markdown 报告、失败项说明和下一步判断 |

## 硬验收条件

| 类别 | 验收条件 | 判定方式 |
|---|---|---|
| 入口唯一性 | Gate 1 只能使用 `linear_2p5d/matched_bie` 主线，不能混入经验模型补偿 | `comparison.csv` 中 `provider_route == matched_bie_station_sweep` |
| 数据冻结 | Wigley III 几何、速度、频率、参考系数和无量纲方式固定在仓库中 | `benchmarks/ma2005/wigley_iii_coefficients_digitized.csv` 可复现读取 |
| 对角项精度 | `A33/B33/A55/B55` 全部通过 15% 误差门槛 | 每行 `gate_error_ratio <= 1.0` |
| 耦合项精度 | `A35/B35/A53/B53` 全部通过 30% 误差门槛 | 每行 `gate_error_ratio <= 1.0` |
| 数值健壮性 | 核心输出不得出现 `NaN`、`Inf` 或空矩阵 | 自动测试和验证 CSV 检查 |
| 方程闭合 | 最终值必须能由四类压力/端部贡献逐项重构，闭合残差接近零 | `matched_force_closure_residual_value` 保持有限并接近零 |
| 诊断完整性 | Eq.30/Eq.32 候选表、压力符号候选表、自由面 block 候选表均输出 | 输出目录存在对应 CSV |
| 回归稳定性 | 单元测试与验证命令必须通过 | `python -m pytest -q` 通过；Gate 1 验证无硬失败 |
| 报告可追溯 | 报告明确写出已通过项、失败项、原因、排除的候选和待补充数据 | `validation_report.md` 或阶段报告可直接阅读 |

## 不应作为下一阶段硬目标的内容

| 内容 | 原因 |
|---|---|
| SL-7 系数硬验收 | 当前缺真实可机读 offsets，已有数据只能用于 surrogate 趋势检查 |
| C1 三体船硬验收 | 当前缺主片体和侧片体真实 offsets，不能证明多体干扰矩阵正确 |
| 完整强非线性 2D+t BEM | 这是后续大模块，应在 Gate 1 线性 2.5D 闭合后再进入硬验收 |
| 完整斜浪六自由度高精度响应 | 当前主线仍是迎浪 heave/pitch 频域内核，横向六自由度应作为 Gate 2/Gate 3 |
| 水翼控制闭环验收 | 需要水翼几何、舵机、控制器和试验数据，不应与 Gate 1 混合 |

## 一句话验收定义

下一阶段完成的判据是：同一套 `matched_bie_station_sweep` 默认配置，在固定 Wigley III 文献数据上让八个 Ma 2005 频域水动力系数全部通过 Gate 1，并且每个通过结果都能由可追溯的 Eq.30/Eq.32 压力恢复、端部项、整船装配和无量纲化链条解释。

## 本轮 Eq.30/Eq.32 压力链审计进展

本轮已经把 Eq.30/Eq.32 pressure-balance 诊断链正式接入 `validate_goal_gap_audit`。该诊断不改变生产默认配置，只把已经计算出的四类贡献重新组合，用于判断误差主要来自哪条物理或数值通道：

| 分量 | 在本项目中的含义 | 对应审计目的 |
|---|---|---|
| `time-derivative pressure` | Eq.30 中由非定常速度势时间导数产生的压力项 | 判断 added-mass 主量级和 harmonic time convention 是否正确 |
| `forward-speed pressure-gradient` | Eq.30 中由前进速度乘纵向势梯度产生的压力项 | 判断纵向差分、站位传播和前进速度项是否放大或转相位 |
| `Stokes body forward-speed` | Eq.32 中用于对照的 Stokes body forward-speed 诊断项 | 判断是否存在和 pressure-gradient 项重复、漏计或符号不一致 |
| `end contour` | Eq.32 端部轮廓项 | 判断艏艉端部积分方向、力臂和端点贡献是否合理 |

本轮输出目录为：

```text
outputs/matched_bie_provider_eq30_pressure_balance_probe/results
```

新增输出文件为：

| 文件 | 作用 |
|---|---|
| `ma2005_wigley_iii_coefficients_eq30_pressure_balance_candidate_detail.csv` | 逐系数、逐候选记录参考值、计算值、误差、gate ratio、四类分量贡献、闭合残差和 PASS/FAIL |
| `ma2005_wigley_iii_coefficients_eq30_pressure_balance_candidate_summary.csv` | 汇总每个候选跨八个 Wigley III 系数的通过数、中位 gate ratio、最大 gate ratio、改善行数和恶化行数 |

候选整体结果如下：

| 候选 | time scale | gradient scale | Stokes scale | end scale | pass_count | median gate ratio | max gate ratio | 结论 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `gradient_flipped_keep_time_end` | 1.0 | -1.0 | 0.0 | 1.0 | 0/8 | 29.037 | 70.405 | 最大误差最低，但仍全部失败，不能进入默认 |
| `time_flipped_keep_gradient_end` | -1.0 | 1.0 | 0.0 | 1.0 | 1/8 | 29.698 | 75.267 | 有局部改善，但同时恶化一半系数 |
| `time_removed_keep_gradient_end` | 0.0 | 1.0 | 0.0 | 1.0 | 1/8 | 15.312 | 88.225 | 说明时间项也参与放大，但不能物理删除 |
| `time_only_no_gradient_no_end` | 1.0 | 0.0 | 0.0 | 0.0 | 0/8 | 21.876 | 102.205 | 单独时间项仍不够，且无法解释阻尼项 |
| `time_half_keep_gradient_end` | 0.5 | 1.0 | 0.0 | 1.0 | 2/8 | 25.795 | 111.135 | 通过数最多，但最大误差仍很大，属于调参型候选 |
| `gradient_removed_keep_time_end` | 1.0 | 0.0 | 0.0 | 1.0 | 0/8 | 22.767 | 117.155 | 去掉梯度不能通过，说明不能把问题简化为“梯度项多算” |
| `end_flipped_keep_pressure` | 1.0 | 1.0 | 0.0 | -1.0 | 0/8 | 34.386 | 134.005 | 端部项反号不能闭合 Gate 1 |
| `current_default` | 1.0 | 1.0 | 0.0 | 1.0 | 1/8 | 36.167 | 163.904 | 当前生产默认仍失败 |
| `all_terms_include_stokes` | 1.0 | 1.0 | 1.0 | 1.0 | 0/8 | 99.472 | 177.087 | 直接叠加 Stokes body 会恶化整体结果 |

默认链路下，四类分量对代表系数的贡献如下：

| 系数 | reference | default computed | time contribution | gradient contribution | Stokes contribution | end contribution | closure residual | 状态 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `A33` | 1.000 | 10.290 | 10.290 | 0.000 | 0.000 | 0.000 | 0.0 | `FAIL` |
| `B33` | 2.100 | 9.646 | 0.000 | 9.045 | 0.000 | 0.601 | 0.0 | `FAIL` |
| `A35` | -0.200 | -2.814 | -1.099 | -1.608 | 0.000 | -0.107 | ~1.5e-15 | `FAIL` |
| `B35` | 0.130 | 6.522 | 4.116 | 1.823 | 0.000 | 0.583 | ~9.3e-16 | `FAIL` |
| `A53` | 0.150 | 1.445 | 1.445 | 0.000 | 0.000 | 0.000 | 0.0 | `FAIL` |
| `B53` | -0.100 | -0.094 | 0.000 | -0.380 | 0.000 | 0.286 | 0.0 | `PASS` |
| `A55` | 0.063 | 0.090 | 0.052 | 0.152 | 0.000 | -0.114 | ~2.4e-17 | `FAIL` |
| `B55` | 0.090 | 1.859 | 0.578 | 1.004 | 0.000 | 0.277 | ~3.9e-16 | `FAIL` |

本轮判断：

1. 闭合条件已经满足：默认候选的 `current_force_closure_residual_value` 在八个系数上均接近零，达到 `< 1e-9` 目标。这说明“最终系数是否等于四类贡献求和”不是当前主要问题。
2. Eq.30 前进速度梯度项是明确的误差放大通道。`B33/B35/B55` 中 gradient contribution 占主导；翻转梯度项能把最大 gate ratio 从 `163.904` 降到 `70.405`，但仍 `0/8` 通过。
3. 时间导数项也存在量级偏大问题。`A33/A53` 完全由 time contribution 决定，关闭或翻转梯度项对它们没有任何帮助；因此 Gate 1 不能只靠 pressure-gradient 修正解决。
4. Stokes body forward-speed term 不能直接叠加进默认链路。`all_terms_include_stokes` 和 `time_plus_stokes_plus_end` 都没有通过，并且会显著恶化若干 pitch/yaw-generalized 项。
5. 端部项不是单独的一阶修复点。端部项反号或去除可以改善个别项，但不能让八项同时过关。
6. Gate 1 继续保持 `PENDING`。下一步应从“分量重组候选”进入“分量来源审计”：重点检查 heave/pitch radiation body potential 本身的量级、二维 BIE 压力积分符号、广义力行方向、以及 Ma 2005 无量纲参考曲线数字化是否与当前 `omega_e_sqrt_l_over_g`、长度尺度和坐标原点完全一致。

数据纪律不变：SL-7 和 C1 trimaran 在没有真实 machine-readable offsets 前，继续标记为 `SURROGATE_NOT_FOR_VALIDATION` 或 `NOT_EVALUATED`，不得用于硬验收。

## 本轮 body-potential/source 上游链路审计进展

在 Eq.30/Eq.32 分量重组之后，本轮继续把诊断上移到 `body normal velocity -> body potential -> pressure -> generalized force density`。新增的审计仍然只读 `contribution_breakdown` 中已有数组，不改变 `matched_bie_station_sweep` 的默认配置。

本轮输出目录为：

```text
outputs/matched_bie_provider_body_potential_source_probe/results
```

新增输出文件为：

| 文件 | 作用 |
|---|---|
| `ma2005_wigley_iii_coefficients_matched_body_potential_source_audit.csv` | 逐 station 输出 body normal velocity、body potential、自由面/控制面状态、压力范数、纵向梯度增益和三类 force density |
| `ma2005_wigley_iii_coefficients_matched_body_potential_source_audit_summary.csv` | 按八个 Wigley III 系数汇总峰值 station、峰值位置、最大势函数增益、最大梯度增益和主导力密度分量 |

关键结果如下：

| 系数 | mode | row | peak body potential `x/L` | peak gradient `x/L` | peak gradient density | max `phi/velocity` gain | max gradient gain `L` | 主导分量 |
|---|---|---|---:|---:|---:|---:|---:|---|
| `A33` | heave | heave_force | 0.075 | 0.025 | 0.000 | 23.105 | 110.998 | time_derivative_density |
| `B33` | heave | heave_force | 0.075 | 0.025 | 33.928 | 23.105 | 110.998 | pressure_gradient_density |
| `A35` | pitch | heave_force | 0.025 | 0.025 | 6.032 | 42.144 | 106.821 | pressure_gradient_density |
| `B35` | pitch | heave_force | 0.025 | 0.025 | 19.350 | 44.735 | 106.047 | time_derivative_density |
| `A53` | heave | pitch_moment | 0.075 | 0.025 | 0.000 | 23.105 | 110.998 | time_derivative_density |
| `B53` | heave | pitch_moment | 0.075 | 0.025 | 16.116 | 23.105 | 110.998 | stokes_body_forward_density |
| `A55` | pitch | pitch_moment | 0.025 | 0.025 | 6.446 | 38.598 | 107.798 | stokes_body_forward_density |
| `B55` | pitch | pitch_moment | 0.025 | 0.025 | 9.191 | 38.598 | 107.798 | stokes_body_forward_density |

本轮判断：

1. `A33` 和 `A53` 的失败不受 pressure-gradient 候选影响，因为它们在当前输出中完全由 time-derivative density 主导。这把问题进一步指向 heave radiation body potential 的量级、二维 BIE 边界积分尺度、或 heave generalized row 的积分规范。
2. `B33` 的最强 pressure-gradient density 出现在 `x/L=0.025` 第一活动站，且 `max gradient gain L` 约为 `111`。这不是普通光滑纵向变化，而是非常强的站位起步放大，必须继续检查首站启动、active wet-section 选择和 Eq.23/Eq.24 传播初值。
3. pitch radiation 相关项的 `phi/velocity` gain 更高，`B35` 达到约 `44.7`，说明 pitch body condition 的 `iωN5 + U m5` 通道仍可能与力矩臂、坐标原点或 forward-speed 项存在耦合放大。
4. 新增 source-audit 表与 Eq.30 pressure-balance 表均无 `NaN/Inf`；`provider_route` 仍为 `matched_bie_station_sweep`；最大分量闭合残差约 `1.55e-15`，满足 `<1e-9`。因此当前失败来源不是输出缺失或闭合不一致，而是上游势函数/梯度链路的物理尺度仍未与 Ma 2005 基准闭合。
5. Gate 1 继续保持 `PENDING`。下一步应优先建立二维剖面解析/半解析校核，尤其是 heave 模态下 `body normal velocity -> body potential -> time pressure -> heave force` 的尺度；其次检查第一活动站 `x/L=0.025` 的启动/湿剖面选择是否导致 pressure-gradient density 人为尖峰。

## 本轮 Gate 1 失败审计固化

本轮新增了一个结论型 Gate 1 审计层，用于把分散在 comparison、Eq.30 pressure-balance、component-scale fit、body-potential/source audit 等表中的证据合并为固定产物。该审计层不改变 `matched_bie_station_sweep` 默认路线，也不把任何候选符号或尺度试探写入生产配置。

最新输出目录为：

```text
outputs/matched_bie_provider_gate1_failure_audit_probe/results
```

新增输出文件如下：

| 文件 | 说明 |
|---|---|
| `ma2005_wigley_iii_coefficients_gate1_failure_audit.csv` | 按 Wigley III 八个系数逐项记录参考值、计算值、误差、gate ratio、状态、四类 Eq.30/Eq.32 分量、闭合残差、主导分量、失败源和剩余阻塞项 |
| `ma2005_wigley_iii_coefficients_gate1_failure_summary.csv` | 按验收条件汇总主路由、输出完整性、Eq.30 拆分、闭合残差、数值稳定、候选排除、全四分量尺度拟合排除和 SL-7/C1 数据纪律 |
| `ma2005_wigley_iii_coefficients_gate1_failure_report.md` | 适合人工阅读的 Gate 1 PENDING 说明报告 |

关键验收状态如下：

| 检查项 | 当前证据 | 状态 |
|---|---|---|
| 主线入口 | `provider_route == matched_bie_station_sweep` | `PASS` |
| 输出完整 | 8 个 Wigley III 系数均有 reference、computed、error、gate ratio、status | `PASS` |
| Eq.30/Eq.32 拆分 | time-derivative pressure、forward-speed pressure-gradient、Stokes body forward-speed、end contour 均逐项输出 | `PASS` |
| 闭合误差 | 最大分量闭合残差约 `1.55e-15` | `PASS` |
| 数值稳定 | 46 个关键 CSV 未发现数值型 `NaN/Inf` | `PASS` |
| 条件数、残差与站位贡献 | comparison 保留 condition number 和 BIE residual；station contribution、station transfer、body potential source 审计表均已生成 | `PASS` |
| 当前默认精度 | `pass=1/8`，仅 `B53` 通过 | `PENDING` |
| 候选排除 | 最好 pressure-balance 候选 `gradient_flipped_keep_time_end` 仍 `0/8` 通过 | `PASS` |
| 全局尺度拟合排除 | `time+gradient+Stokes+end` 四分量最小二乘仅 `4/8` 通过，最大 gate ratio `9.045` | `PASS` |
| 回归测试 | `python -m pytest -q` 为 `166 passed` | `PASS` |

当前失败源被明确归为两类：

| 失败源 | 系数 | 解释 | 下一步 |
|---|---|---|---|
| `heave_time_derivative_body_potential_scale` | `A33`, `A53` | 这两项由 time-derivative pressure 主导，说明仅调整 pressure-gradient 或 end contour 不可能修复 | 建立二维剖面 heave radiation 压力积分校核 |
| `first_active_station_pressure_gradient_spike` | `B33`, `A35`, `B35`, `A55`, `B55` | pressure-gradient 路径峰值集中在 `x/L=0.025`，`body-potential x-gradient gain times L` 约 `106-111` | 审计第一活动湿剖面、ghost/startup 处理和纵向导数 |

因此，本轮结论是：Gate 1 仍为 `PENDING`，但失败已不再是“缺少诊断输出”或“无法定位”的状态。下一步应停止全局符号/尺度扫参，转向两个更硬的物理与数值校核：二维剖面 BIE 的 heave 势函数尺度，以及第一活动站处 pressure-gradient 的启动尖峰。

## 本轮 heave time-pressure 链路剖面校核

在 Gate 1 失败审计之后，本轮继续针对 `A33/A53` 的 `heave_time_derivative_body_potential_scale` 阻塞项建立了更贴近 Eq.30 的剖面级校核。该校核仍为 diagnostic-only，不改变 `matched_bie_station_sweep` 默认配置。

校核对象为封闭圆柱在无限流体中的横向运动。解析参照为二维圆柱单位长度附加质量：

```text
expected added mass per unit length = rho*pi*r^2
```

该案例的目的不是替代 Ma 2005，而是把局部链路

```text
body normal velocity -> source strength -> body potential -> Eq.30 time pressure -> heave force
```

从 Wigley III 的复杂自由面/开剖面/站位传播问题中单独拿出来检查。

新增输出目录为：

```text
outputs/matched_bie_provider_heave_time_pressure_chain_probe/results
```

新增文件如下：

| 文件 | 说明 |
|---|---|
| `a1_heave_time_pressure_chain.csv` | 按 panel count 输出解析 heave force、原始 pressure-chain heave force、显式压力符号修正后的 heave force、势函数对齐尺度、线性系统残差和诊断状态 |
| `a1_heave_time_pressure_chain_summary.csv` | 汇总 finest panel count 下的误差、符号反转、势函数对齐结果和对 Gate 1 的含义 |

关键数值如下：

| panel count | expected heave force | raw heave force | sign-corrected heave force | corrected added-mass ratio | corrected error | status |
|---:|---:|---:|---:|---:|---:|---|
| 64 | 12566.371 | -12697.854 | 12697.854 | 1.01046 | 0.01046 | `PASS` |
| 128 | 12566.371 | -12634.135 | 12634.135 | 1.00539 | 0.00539 | `PASS` |
| 256 | 12566.371 | -12600.753 | 12600.753 | 1.00274 | 0.002736 | `PASS` |

该结果说明：

1. 闭合圆柱内域源强、body potential、Eq.30 time pressure 和 heave force 积分链路是可量化、可收敛的。
2. 原始链路呈现压力符号反转；显式符号修正后，finest panel count 下 added-mass ratio 为 `1.00274`，相对误差约 `0.274%`。
3. 势函数对齐尺度为 `-1.00284`，进一步说明这是明确的局部符号约定证据，而不是数值发散。
4. 但是，该证据不能直接转化为 Ma 2005 生产默认符号翻转；上一轮全局候选已经证明简单压力符号或尺度候选不能让 Wigley III 八个系数同时通过。
5. 因此，`A33/A53` 的下一步阻塞被进一步限定：需要审计 matched open-section、自由面匹配、湿剖面起止和广义力行方向，而不是继续怀疑封闭剖面内域压力积分不可用。

本轮验证结果：

| 检查 | 结果 |
|---|---|
| 定向测试 | `2 passed, 37 deselected` |
| 完整回归 | `166 passed` |
| 数值健康 | 48 个关键 CSV 未发现数值型 `NaN/Inf` |

Gate 1 继续保持 `PENDING`。下一步应并行推进两个检查：其一，把 closed-cylinder heave 链路思想移植到 Wigley III 的开剖面/自由面匹配站位上；其二，继续审计第一活动站 `x/L=0.025` 的 pressure-gradient 启动尖峰。

## 本轮 Wigley III heave time-pressure 站位尺度审计

在封闭圆柱剖面链路校核之后，本轮把 heave time-pressure 问题重新放回 Wigley III 的 `matched_bie_station_sweep` 主线中，新增 open-section station-scale 审计。该审计读取现有 `matched_body_potential_source_audit` 和 `comparison` 数据，不改变默认求解器。

新增输出目录为：

```text
outputs/matched_bie_provider_heave_time_station_scale_probe/results
```

新增文件如下：

| 文件 | 说明 |
|---|---|
| `ma2005_wigley_iii_coefficients_heave_time_pressure_station_scale_audit.csv` | 对 `A33/A53` 每个活动站输出 time-derivative density、梯形权重、站位贡献、贡献占比、局部面积/梁宽归一化、body potential gain 和所需参考尺度 |
| `ma2005_wigley_iii_coefficients_heave_time_pressure_station_scale_summary.csv` | 汇总 station 积分闭合、峰值站位、贡献质心、正负抵消、所需参考尺度和剩余阻塞 |

关键结果如下：

| coefficient | reference | current | gate ratio | time component | station integral | closure residual | peak `x/L` | centroid `x/L` | required scale |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `A33` | 1.000 | 10.290 | 61.933 | 10.290 | 10.290 | `1.78e-15` | 0.300 | 0.357 | 0.09718 |
| `A53` | 0.150 | 1.445 | 28.772 | 1.445 | 1.445 | `2.22e-16` | 0.250 | 0.300 | 0.10383 |

该结果带来的判断变化：

1. `A33/A53` 的 station 积分与 Eq.30 time component 完全闭合，残差在 `1e-15` 量级。因此，当前不是后处理表格或整船积分漏项问题。
2. 两项的放大比例接近但不完全相同，若只从 time integral 打到参考值，需要约 `0.097-0.104` 的尺度。这解释了全局 `time_only` 最小二乘为什么会给出约 `0.09` 的尺度，但它仍不能成为默认修正。
3. `A33/A53` 的峰值贡献位置分别约为 `x/L=0.300` 和 `x/L=0.250`，贡献质心分别约为 `0.357` 和 `0.300`。这说明它们与 pressure-gradient 的第一活动站尖峰是不同问题。
4. 最大 `body_potential_to_body_normal_velocity_gain` 约 `23.105`，最大 `body_potential_norm_to_submerged_area_ratio` 在 `A33` 为约 `2871`，在 `A53` 为约 `5742`。这些指标把下一步明确指向 open-section/free-surface 匹配尺度。
5. 该审计继续保持 diagnostic-only。因为四分量全局尺度拟合仍只通过 `4/8`，所以不能用 `0.1` 经验因子替代方程级修正。

本轮验证：

| 检查 | 结果 |
|---|---|
| 定向测试 | `1 passed, 38 deselected` |
| Ma 2005 探针 | 正常完成，硬失败仍为 15，待数据项 8 |
| 数值健康 | 50 个关键 CSV 未发现数值型 `NaN/Inf` |
| 完整回归 | `166 passed` |

## 2026-08-01 Free-Normal / Body-Potential 链路专项审计

本轮新增 `A33/A53` 的自由面法向导数传递链审计，进一步检查：

```text
inner free-surface normal derivative -> body potential -> Eq.30 time pressure -> heave generalized force
```

新增输出目录：

```text
outputs/matched_bie_provider_free_normal_chain_probe/results
```

新增文件：

| 文件 | 说明 |
|---|---|
| `ma2005_wigley_iii_coefficients_heave_free_normal_to_body_potential_audit.csv` | 逐站记录自由面法向导数、船体法向速度、船体势函数、局部时间压力贡献和峰值标记 |
| `ma2005_wigley_iii_coefficients_heave_free_normal_to_body_potential_summary.csv` | 汇总最大/中位传递比、峰值站位、同站判断、相关系数和剩余阻塞 |

关键结果：

| coefficient | max free-normal/body-velocity | median free-normal/body-velocity | max ratio x/L | time-pressure peak x/L | peak share | conclusion |
|---|---:|---:|---:|---:|---:|---|
| `A33` | 12.6778 | 0.39548 | 0.025 | 0.300 | 0.06884 | `free_normal_gain_is_large_but_not_colocated_with_peak_time_pressure` |
| `A53` | 12.6778 | 0.39548 | 0.025 | 0.250 | 0.07759 | `free_normal_gain_is_large_but_not_colocated_with_peak_time_pressure` |

解释：

1. 首个活动站 `x/L=0.025` 的自由面法向导数传递比确实偏大，但它没有与 `A33/A53` 的 heave time-pressure 主贡献同站。
2. `A33/A53` 的主贡献仍集中在中前部站位，因此不能用“首站自由面法向导数尖峰”单独解释 heave time-pressure 量级偏大。
3. 下一步应继续追查 Eq.23/Eq.24 自由面法向导数单位、inner/free/control 匹配符号、开剖面自由面截断和中前部 body-potential 尺度。
4. 新审计为 `diagnostic-only`，没有改变 `matched_bie_station_sweep` 默认配置。

本轮验证：

| 检查 | 结果 |
|---|---|
| Ma 2005 探针 | 正常完成；`Hard failures=15`，待数据项 `8` |
| `validation_summary.csv` | `PASS=65`、`FAIL=15`、`NOT_EVALUATED=8`、`INFO=41` |
| 关键 CSV 数值健康 | 未发现数值型 `NaN/Inf` |
| 定向测试 | `python -m pytest -q tests/test_validation.py -k matched_bie_provider_model` 通过 |
| 完整回归 | `python -m pytest -q`：`166 passed` |

## 2026-08-02 Gradient Stencil / Phase Exclusion 审计

本轮把 Eq.30 forward-speed pressure-gradient 的 stencil 与相位候选整理成默认准入审计，避免把局部改善误判为生产修正。

新增输出目录：

```text
outputs/matched_bie_provider_stencil_phase_exclusion_probe/results
```

新增文件：

| 文件 | 说明 |
|---|---|
| `ma2005_wigley_iii_coefficients_pressure_gradient_stencil_phase_exclusion_audit.csv` | 逐候选、逐系数记录 gate ratio、改善/恶化、是否破坏当前通过项和行级判定 |
| `ma2005_wigley_iii_coefficients_pressure_gradient_stencil_phase_exclusion_summary.csv` | 按候选汇总通过数、改善数、恶化数、破坏当前通过项数量和默认排除原因 |

关键结果：

| candidate | pass count | improved | worsened | breaks current pass | max gate ratio | decision |
|---|---:|---:|---:|---:|---:|---|
| `phase_aligned_forward` | 0/8 | 4 | 3 | 1 | 78.495 | excluded |
| `phase_aligned_central` | 0/8 | 4 | 3 | 1 | 110.057 | excluded |
| `phase_aligned_backward` | 0/8 | 4 | 3 | 1 | 136.011 | excluded |
| `scheme_forward` | 0/8 | 4 | 2 | 1 | 136.888 | excluded |
| `current_default / scheme_central` | 1/8 | 2 | 2 | 0 | 163.904 | Gate 1 pending |
| `scheme_backward` | 0/8 | 2 | 4 | 1 | 171.183 | excluded |

解释：

1. `phase_aligned_forward` 的最大 gate ratio 最低，但仍然没有任何系数通过，且会破坏当前唯一通过的 `B53`。
2. 直接切换 central/forward/backward 或 phase-aligned stencil 不是 Gate 1 的生产修正。
3. `A33/A53` 由 time-derivative pressure 主导，对 pressure-gradient stencil 候选基本不响应。
4. 下一步应继续审计 Eq.30 forward-speed term 的坐标方向、marching 方向、复相位约定和整船无量纲化链条。

本轮验证：

| 检查 | 结果 |
|---|---|
| Ma 2005 探针 | 正常完成；`Hard failures=15`，待数据项 `8` |
| `validation_summary.csv` | `PASS=65`、`FAIL=15`、`NOT_EVALUATED=8`、`INFO=43` |
| 关键 CSV 数值健康 | 未发现数值型 `NaN/Inf` |
| 定向测试 | `python -m pytest -q tests/test_validation.py -k matched_bie_provider_model` 通过 |
| 完整回归 | `python -m pytest -q`：`166 passed` |

## 2026-08-02 Pressure-Gradient Startup Spike 审计

本轮新增 Eq.30 forward-speed pressure-gradient 逐站积分表，专门判断首个活动站是否足以解释 `B33/A35/B35/A55/B55` 等项的失败。

新增输出目录：

```text
outputs/matched_bie_provider_pressure_gradient_spike_probe/results
```

新增文件：

| 文件 | 说明 |
|---|---|
| `ma2005_wigley_iii_coefficients_pressure_gradient_startup_spike_audit.csv` | 逐站记录 pressure-gradient density、站位贡献、贡献占比、纵向梯度增益和首站/峰值标记 |
| `ma2005_wigley_iii_coefficients_pressure_gradient_startup_spike_summary.csv` | 汇总首站、前两站、其余站、峰值站贡献，并给出去首站/去前两站后的诊断性 gate ratio |

关键结果：

| coefficient | current gate ratio | first station share | first two share | peak x/L | without first gate ratio | conclusion |
|---|---:|---:|---:|---:|---:|---|
| `B33` | 23.957 | 0.0639 | 0.1132 | 0.075 | 19.918 | `pressure_gradient_peak_not_limited_to_startup_station` |
| `A35` | 43.563 | 0.0639 | 0.1132 | 0.075 | 39.793 | `pressure_gradient_peak_not_limited_to_startup_station` |
| `B35` | 163.904 | 0.1416 | 0.1640 | 0.025 | 145.299 | `first_active_station_is_peak_but_not_dominant` |
| `B53` | 0.190 | 0.1322 | 0.2288 | 0.075 | 19.955 | `pressure_gradient_peak_not_limited_to_startup_station` |
| `A55` | 2.865 | 0.1322 | 0.2288 | 0.075 | 28.446 | `pressure_gradient_peak_not_limited_to_startup_station` |
| `B55` | 131.032 | 0.2084 | 0.2396 | 0.025 | 105.501 | `first_active_station_is_peak_but_not_dominant` |

解释：

1. 首站 `x/L=0.025` 的 pressure-gradient density 偏强，但不是所有相关系数的主峰；多个系数的峰值出现在 `x/L=0.075`。
2. 首站贡献占比不足以解释全局失真；去首站不能让失败项通过。
3. 对已通过的 `B53`，去首站会明显恶化，因此“删首站”会破坏现有正确项。
4. 本轮排除首站删除、首站置零和简单 startup smoothing 作为生产默认；剩余工作应转向 longitudinal derivative stencil、相位对齐、marching 方向和 Eq.30 forward-speed term 装配。

本轮验证：

| 检查 | 结果 |
|---|---|
| Ma 2005 探针 | 正常完成；`Hard failures=15`，待数据项 `8` |
| `validation_summary.csv` | `PASS=65`、`FAIL=15`、`NOT_EVALUATED=8`、`INFO=42` |
| 关键 CSV 数值健康 | 未发现数值型 `NaN/Inf` |
| 定向测试 | `python -m pytest -q tests/test_validation.py -k matched_bie_provider_model` 通过 |
| 完整回归 | `python -m pytest -q`：`166 passed` |

Gate 1 继续保持 `PENDING`。下一轮的首要任务是检查 Wigley III 开剖面/自由面匹配中 heave body potential 相对于 body normal velocity 的尺度来源，包括 inner/free/control 边界方程单位、自由面 panel 截断、open-section 与 closed-section pressure-row 符号约定差异。

## 本轮 open-section/free-surface 匹配尺度补充审计

本轮继续在 `ma2005_wigley_iii_coefficients_heave_time_pressure_station_scale_audit.csv` 中增加自由面与控制面匹配比值，以判断 `A33/A53` 的 body potential 放大更像来自哪个上游边界块。

新增字段：

| 字段 | 说明 |
|---|---|
| `free_surface_potential_to_body_potential_ratio` | 自由面势函数范数与 body potential 范数之比 |
| `control_potential_to_body_potential_ratio` | 控制面势函数范数与 body potential 范数之比 |
| `inner_free_surface_normal_derivative_to_body_normal_velocity_ratio` | 内域自由面法向导数范数与船体法向速度范数之比 |
| `time_pressure_to_body_potential_gain` | Eq.30 时间压力范数相对 body potential 范数的增益 |

最新输出目录：

```text
outputs/matched_bie_provider_heave_open_section_scale_probe/results
```

关键结果：

| coefficient | required scale | max free phi/body phi | max control phi/body phi | max free normal/body velocity |
|---|---:|---:|---:|---:|
| `A33` | 0.09718 | 0.23447 | 0.13112 | 12.6778 |
| `A53` | 0.10383 | 0.23447 | 0.13112 | 12.6778 |

解释：

1. 自由面势和控制面势相对 body potential 的最大比值均小于 0.25 和 0.14，说明它们不是直接同量级放大的表现量。
2. 自由面法向导数相对船体法向速度的最大比值约 `12.68`，比势函数比值更显著，应优先检查自由面法向导数通道、Eq.23/Eq.24 单位和匹配方程尺度。
3. `time_pressure_to_body_potential_gain` 在明细表中保持常量关系，对应 Eq.30 的 `rho*omega` 通道，说明 pressure recovery 的时间导数公式记账是一致的。
4. Gate 1 继续为 `PENDING`。目前仍不能把 `0.1` 尺度、closed-cylinder 压力符号修正或任何局部候选写入默认模型。

本轮验证：

| 检查 | 结果 |
|---|---|
| 定向测试 | `1 passed, 38 deselected` |
| Ma 2005 探针 | 正常完成，硬失败仍为 15，待数据项 8 |
| 数值健康 | 50 个关键 CSV 未发现数值型 `NaN/Inf` |
| 完整回归 | `166 passed` |
