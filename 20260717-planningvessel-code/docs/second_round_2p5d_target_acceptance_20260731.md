# 第二轮 2.5D 完整模型开发目标与验收条件

日期：2026-07-31

## 1. 阶段目标

本阶段目标是把第一轮“可扩展、可测试、边界清楚”的框架，推进为“可由公开文献数据逐项验收的最小完整 2.5D 耐波求解器”。

本阶段不以经验调参让单个曲线偶然贴合为目标，而以建立可追溯、可复现、可解释的计算链为目标。任何未通过文献验收的数据、替代船型或 surrogate 都必须保留 `PENDING`、`NOT_EVALUATED` 或 `SURROGATE_NOT_FOR_VALIDATION` 状态。

## 2. 主线模型入口

第二轮起，线性高速 2.5D 的主线入口为：

```python
LinearFrequencyProvider(
    source="linear_2p5d",
    config=Linear2p5DProviderConfig(formulation="matched_bie"),
)
```

该入口必须路由到 Ma-Duan-Song 型 matched BIE station sweep，并输出标准 `FrequencyDomainHydrodynamics`：

- `added_mass[n_omega, 6, 6]`
- `radiation_damping[n_omega, 6, 6]`
- `restoring[n_omega, 6, 6]`
- `excitation[n_omega, 6]`
- `contribution_breakdown`
- `ValidityReport`
- `metadata["provider_route"] == "matched_bie_station_sweep"`

旧的站位经验/诊断装配只能通过：

```python
build_legacy_2p5d_provider()
```

或 `source="legacy_station_prototype"` 显式调用。旧入口不能被误认为第二轮的生产模型。

## 3. 必须具备的数据条件

| 数据对象 | 当前结论 | 必要条件 |
|---|---|---|
| A1 Wigley III | 可作为 Gate 1 主验收对象 | 继续复核 Ma 2005 曲线数字化、坐标轴、归一化和速度工况 |
| A1 SL-7 | 暂不能硬验收 | 必须找到真实 machine-readable station offsets；否则只能做趋势和流程 smoke test |
| B2 Delft 372 | 已具备真实几何输入 | `delft372_demihull_offsets.csv` 静水复核误差需保持在 2% 内 |
| B1/B2 Delft 372 响应曲线 | 待数字化 | 需要 heave、pitch、主要六自由度、连接载荷曲线 CSV |
| C1 三体船 | 暂不能硬验收 | 必须找到主片体和侧片体真实 offsets；否则 analytic trimaran surrogate 只能用于干扰趋势检查 |
| Fridsma/Katayama | 部分可用 | 规则波运动、加速度、不规则波统计、跳跃分类要分别建 gate |

## 4. 硬验收 Gates

| Gate | 名称 | 通过条件 |
|---|---|---|
| Gate 1 | Ma-Duan-Song 线性 2.5D 单体船内核 | Wigley III `A33/B33/A55/B55` 误差不超过 15%；`A35/B35/A53/B53` 误差不超过 30% |
| Gate 2 | Delft 372 真实双体几何 | 左右片体按中心距 `0.70 m` 装配；排水质量和浮心误差保持在 2% 到 5% 内 |
| Gate 3 | Delft 372 多体共同边界积分 | cross-radiation 和 cross-diffraction 在矩阵中显式出现，不能只做左右片体独立相加 |
| Gate 4 | B1/B2 运动响应 | 主峰位置误差不超过 10%；主要 RAO 幅值误差目标 15% 到 20% |
| Gate 5 | Sun-Faltinsen 2D+t 最小闭环 | 楔形入水和 V 型柱入水趋势正确；压力辅助函数、jet cut、spray cut 和重网格可稳定运行 |
| Gate 6 | Fridsma/Katayama 滑行艇响应 | heave/pitch 幅值误差目标不超过 25%；CG/艏部加速度误差目标不超过 35%；跳跃分类清晰正确 |

## 5. 当前第二轮最小验收动作

1. 固定 `LinearFrequencyProvider(source="linear_2p5d", formulation="matched_bie")` 为主线模型入口。
2. 对 Wigley III 使用同一个 provider 入口生成 `A33/B33/A35/B35/A53/B53/A55/B55`。
3. 每次比较输出：
   - 参考值；
   - 计算值；
   - 相对误差；
   - gate 阈值；
   - `PASS` 或 `FAIL`；
   - 失败来源诊断，包括 body pressure、free-surface state、outer control balance、pressure-gradient 和 end-term contribution。
4. 若某个经验符号或尺度候选只能改善单个系数，但不能同时改善四个或八个系数，不得进入生产默认。
5. 若 SL-7 或 C1 仍无真实 offsets，报告中必须明确标注为缺数据阻塞，不能用 surrogate 代替硬验收。

## 6. 本轮已落实的代码条件

| 条件 | 状态 |
|---|---|
| matched BIE station sweep 接入统一 provider | 已完成 |
| legacy station prototype 与 matched BIE 路由分离 | 已完成 |
| `production=true` 防止误用未验证 in-package 2.5D | 已完成 |
| 裸 `pytest` 能从项目根导入本地包 | 已完成 |
| provider 路由单元测试 | 已完成 |

## 7. 下一步技术焦点

Gate 1 仍为 `PENDING`。已有诊断表明，内域 closed/mixed Green identity、自由面 oscillator、Eq. (24) 瞬时控制面、历史核导数、历史 RHS 收敛和历史继承均已有实现级审计证据。因此下一步不应继续随意调整单个符号，而应集中检查：

1. BIE 生成的 `inner_free_surface_normal_derivative` 的尺度和相位。
2. `free_surface_potential_by_station` 在站位间传播时对 body pressure 的放大路径。
3. Eq. (30) 压力恢复中时间导数项与前进速度梯度项的相对贡献。
4. Eq. (32) Stokes body forward-speed term 和 end contour term 的坐标映射。
5. pitch generalized force row 的 `N5/m5` 坐标变换是否与 Ma 2005 的符号和无量纲定义完全一致。

只有当 Wigley III 八个系数在同一套默认配置下同时达到 Gate 1 阈值，才能把 matched BIE 2.5D 内核从 `PENDING` 推进为 `PASS`。

## 8. 外部代码与几何资料检索结论

2026-07-31 已复查可借鉴的开源路线：

| 对象 | 结论 | 在本项目中的使用方式 |
|---|---|---|
| PDSTRIP | 可作为 strip-theory/section-results 的外部参考程序 | 已有 `pdstrip_external.py` 和相关测试；适合作为诊断路径，不直接替代 Ma-Duan-Song matched BIE |
| OpenPlaning | 可作为 Savitsky 类型静水滑行估算参考 | 适合复核 reduced-order calm-water/running-state 估算，不提供完整 2.5D 波浪耐波内核 |
| Capytaine / Nemoh / HAMS | 可作为通用势流边界元参考 | 适合未来外部频域数据库或低速势流对照，不直接解决高速 2.5D 局部时间 marching |
| SL-7 offsets | 未发现可靠公开 machine-readable offsets | 继续标记 `SURROGATE_NOT_FOR_VALIDATION`；若后续使用，必须人工数字化 body plan 或取得来源明确的数据 |
| C1 trimaran offsets | 未发现可靠公开 main/side-hull machine-readable offsets | C1 只能作为方法和曲线目标；没有真实 offsets 前不能作为硬几何验收 |

因此，本阶段的硬验证优先级保持为：Wigley III 用于单体 2.5D 系数 gate，Delft 372 用于真实双体几何和多体耦合 gate，Fridsma/Katayama 用于滑行艇运动与加速度 gate。SL-7 和 C1 在取得真实 offsets 前只保留为缺数据对象和趋势诊断对象。

## 9. 2026-08-01 主线入口探针基线

为避免“目标已经写清楚，但代码入口仍然停留在旧原型”的问题，本轮已经把 `matched_bie_provider` 接入 `validate` 验证流水线。验证命令为：

```bash
python -m planing_seakeeping validate --benchmark all --out outputs/matched_bie_provider_gate_probe/results --reference-root outputs/matched_bie_provider_gate_probe/reference --ma-hydro-model matched_bie_provider --ma-bem-free-surface-panels 4 --ma-bem-body-panels 8
```

该命令使用 `LinearFrequencyProvider(source="linear_2p5d", config=Linear2p5DProviderConfig(formulation="matched_bie"))` 作为计算入口，输出的比较表包含参考值、计算值、误差、门槛、状态、provider 路由、matched BIE 有效性说明、体面压力分量、时间导数压力分量、前进速度压力梯度分量、Stokes 体积分前进速度项、端部项、自由面状态范数、外域历史右端范数和 Eq. (24) 外域控制面相对残差。

首行 Wigley III 探针结果如下。这里的目的不是宣布 Gate 1 通过，而是建立一个固定、可复现、可解释的失败基线。只有先承认这些误差在哪里，后续每一次理论修正才有判据。

| 系数 | 参考值 | 当前计算值 | Gate error ratio | 状态 | 当前主导分量 | 对目标的含义 |
|---|---:|---:|---:|---|---|---|
| `A33` | 1.000 | 10.290 | 61.93 | `FAIL` | body pressure | 垂荡附加质量仍显著偏大，说明体面势尺度、自由面状态回馈或归一化仍未闭合。 |
| `B33` | 2.100 | 9.646 | 23.96 | `FAIL` | body pressure | 垂荡阻尼同样偏大，不能只通过 pitch 符号修正解释。 |
| `A35` | -0.200 | -2.814 | 43.56 | `FAIL` | body pressure | 垂荡力对纵摇模态的耦合过强，仍需复核广义力矩臂和前进速度项。 |
| `B35` | 0.130 | 6.522 | 163.90 | `FAIL` | body pressure | 耦合阻尼相位或尺度存在明显偏差，是当前最强阻塞项之一。 |
| `A53` | 0.150 | 1.445 | 28.77 | `FAIL` | body pressure | 纵摇力矩对垂荡模态的耦合仍过大，尚未满足 30% 耦合门槛。 |
| `B53` | -0.100 | -0.094 | 0.19 | `PASS` | stokes_body_forward | 这是当前唯一通过的首行系数，说明部分前进速度耦合链条已有正确量级，但不能单独证明整体模型正确。 |
| `A55` | 0.063 | 0.090 | 2.87 | `FAIL` | stokes_body_forward | 纵摇附加质量接近但仍未达 15% 对角门槛，需要继续审计 pitch 模态和端部项。 |
| `B55` | 0.090 | 1.859 | 131.03 | `FAIL` | body pressure | 纵摇阻尼偏大最明显，下一步必须重点检查压力恢复的相位和尺度。 |

因此，当前目标状态必须保持为：`Gate 1 = PENDING/FAIL 基线已建立`，而不是 `PASS`。下一步“做实”的最小条件是：

1. 固定上述命令为回归探针；任何理论修正后必须重新输出同一张比较表。
2. 修正必须同时改善 `A33/B33/A55/B55` 对角项和 `A35/B35/A53/B53` 耦合项；只改善单个系数不能进入默认模型。
3. 每个失败项都必须保留主导分量诊断，使误差能追溯到 body pressure、time derivative、pressure gradient、Stokes body forward term 或 end term，而不是只给一个总误差。
4. `matched_bie_provider` 的缓存键必须包含控制面半径、历史步数、历史积分点数和历史截断上限，确保不同诊断设置不会复用同一套矩阵。
5. 在 Wigley III 八个系数同时达标前，SL-7 surrogate、C1 surrogate、外部 PDSTRIP smoke 和经验 reduced-order 模型都只能用于解释与排查，不能替代 Gate 1。

### 9.1 放大链诊断的新增验收证据

2026-08-01 继续把上述探针扩展为“自由面状态到体面压力”的放大链诊断。新增输出目录为：

```text
outputs/matched_bie_provider_gate_probe_augmented/results
```

新增诊断列包括：

- `matched_heave_inner_free_surface_normal_derivative_norm_max`
- `matched_pitch_inner_free_surface_normal_derivative_norm_max`
- `matched_heave_free_surface_potential_increment_to_normal_derivative_gain_max`
- `matched_pitch_free_surface_potential_increment_to_normal_derivative_gain_max`
- `matched_heave_free_surface_potential_increment_normal_derivative_phase_deg_median`
- `matched_pitch_free_surface_potential_increment_normal_derivative_phase_deg_median`
- `matched_heave_body_pressure_to_body_potential_gain_max`
- `matched_pitch_body_pressure_to_body_potential_gain_max`
- `matched_heave_body_pressure_to_free_surface_potential_after_gain_max`
- `matched_pitch_body_pressure_to_free_surface_potential_after_gain_max`
- `matched_heave_body_pressure_forward_to_time_norm_ratio_max`
- `matched_pitch_body_pressure_forward_to_time_norm_ratio_max`

首行 Wigley III 探针给出的代表性量级如下。

| 指标 | 当前量级 | 解释 |
|---|---:|---|
| heave inner free-surface normal derivative norm max | `6.39` 到 `15.97` | BIE 求得的内自由面法向导数不是零，也没有在该小网格探针中表现为无穷大。 |
| pitch inner free-surface normal derivative norm max | `8.37` 到 `12.93` | pitch 模态同样有可追踪的自由面法向导数输入。 |
| free-surface potential increment to normal-derivative gain max | 约 `0.4645` | 自由面势增量相对法向导数的推进增益在各首行工况下稳定，说明当前失败不宜简单归结为站位间自由面势增量随机爆炸。 |
| free-surface increment phase median | 约 `180 deg` | 势增量相对法向导数呈近反相，这与当前 `-g * zeta` 型势更新符号有关，仍需继续对照 A1 Eq. (19)-Eq. (22) 的坐标约定。 |
| body pressure to body potential gain max | 约 `7.9e4` 到 `8.2e4` | 体面压力相对体面势的恢复增益很大，下一步应优先复核 Eq. (30) 中 `i omega phi` 与 `U partial phi / partial x` 的单位、相位和归一化。 |
| body pressure to free-surface potential after gain max | 约 `1.45e8` | 相对自由面更新后势的压力增益极大，说明“自由面状态进入体面势，再进入压力”的尺度闭合仍是 Gate 1 的主要嫌疑。 |
| body pressure forward/time norm ratio max | 约 `17.8` 到 `44.4` | 前进速度压力梯度项相对时间导数压力项非常强，尤其会影响 `B33/B35/B55` 这类阻尼项。 |

这组证据把 Gate 1 的下一步进一步收窄为三项肯定需要完成的条件：

1. 复核 `recover_body_pressure_from_matched_solution()` 中 Eq. (30) 的量纲链，明确 `body_potential` 的单位是否与 `pressure_time_derivative_pa = -rho * i * omega * phi` 的实现一致。
2. 对 `estimate_body_potential_x_gradient()` 输出做 station-wise 单位闭合检查，确认 `U * partial phi / partial x` 没有因为站位坐标、局部时间或面板索引产生系统性放大。
3. 建立 `body_potential -> pressure -> generalized force -> Ma2005 nondimensional coefficient` 的逐步归一化表；在这张表通过前，任何让单个 `Aij/Bij` 靠近文献的符号或尺度扫描仍只能保留为 diagnostic。

### 9.2 Eq. (30) 压力链逐级闭合探针

2026-08-01 进一步新增 `body_potential -> pressure -> generalized force -> nondimensional coefficient` 的逐系数闭合字段。新增输出目录为：

```text
outputs/matched_bie_provider_pressure_chain_probe/results
```

新增字段包括：

- `matched_selected_pressure_time_formula_ratio_median`
- `matched_selected_pressure_forward_formula_ratio_median`
- `matched_selected_body_pressure_to_body_potential_gain_max`
- `matched_selected_body_pressure_forward_to_time_norm_ratio_max`
- `matched_selected_generalized_force_to_pressure_norm_gain_max`
- `matched_selected_coefficient_raw_from_total_force`
- `matched_selected_reference_raw_coefficient`
- `matched_selected_raw_to_reference_raw_ratio`
- `matched_selected_required_scale_to_reference`

首行 Wigley III 探针的核心结论如下。

| 系数 | 状态 | time formula ratio | forward formula ratio | raw/reference raw | required scale | 解释 |
|---|---|---:|---:|---:|---:|---|
| `A33` | `FAIL` | `1.0` | `1.0` | `10.29` | `0.097` | 压力公式本身闭合，但垂荡附加质量 raw 系数约为参考的 10.3 倍。 |
| `B33` | `FAIL` | `1.0` | `1.0` | `4.59` | `0.218` | 阻尼项不是公式缺项造成的，而是上游势/梯度或下游力积分尺度偏大。 |
| `A35` | `FAIL` | `1.0` | `1.0` | `14.07` | `0.071` | pitch 模态产生 heave force 的耦合 raw 系数明显过大。 |
| `B35` | `FAIL` | `1.0` | `1.0` | `50.17` | `0.020` | 这是当前首行最强阻塞项，说明耦合阻尼链条存在严重尺度/相位问题。 |
| `A53` | `FAIL` | `1.0` | `1.0` | `9.63` | `0.104` | heave 模态产生 pitch moment 的 raw 系数约为参考的 9.6 倍。 |
| `B53` | `PASS` | `1.0` | `1.0` | `0.943` | `1.060` | 当前唯一通过的首行项；不能代表整体 Gate 1 通过，但说明部分前进速度耦合量级可达正确范围。 |
| `A55` | `FAIL` | `1.0` | `1.0` | `1.43` | `0.699` | 纵摇附加质量已接近，但仍未达到 15% 对角项门槛。 |
| `B55` | `FAIL` | `1.0` | `1.0` | `20.65` | `0.048` | 纵摇阻尼依然严重偏大，下一步应优先检查 `dphi/dx` 的站位尺度和 pitch 行归一化。 |

这说明 Eq. (30) 的两条压力公式在代码层面是闭合的：`pressure_time_derivative_pa` 与 `rho * omega * body_potential` 的范数比为 `1.0`，`pressure_forward_speed_pa` 与 `rho * U * partial phi / partial x` 的范数比也为 `1.0`。因此 Gate 1 当前不应优先寻找 `rho`、`omega` 或 `U` 的漏乘因子，而应继续审计：

1. matched BIE 解出的 `body_potential` 是否已经比 A1 论文势函数定义大一个固定或频率相关尺度；
2. `estimate_body_potential_x_gradient()` 中 station 坐标、局部时间方向、差分方向和面板索引是否使 `partial phi / partial x` 系统性放大；
3. pressure-to-force 几何积分中的 `N3/N5` 行、lever arm 和 Ma 2005 moment reference 是否完全一致；
4. Ma 2005 图中 `Aij/Bij` 的无量纲尺度是否使用当前实现假设的 `rho * displacement * L^rotational` 与 `sqrt(g/L)`，尤其是 pitch 相关项的长度幂。

### 9.3 Eq. (34) 归一化长度幂反证

2026-08-01 又把 Ma 2005 Eq. (34) 的归一化审计直接接入主 comparison CSV。新增输出目录为：

```text
outputs/matched_bie_provider_normalization_audit_probe/results
```

新增字段包括：

- `ma2005_eq34_normalization_formula`
- `ma2005_eq34_documented_length_power`
- `ma2005_eq34_documented_scale`
- `ma2005_required_normalization_scale`
- `ma2005_required_normalization_scale_over_documented`
- `ma2005_normalization_scale_diagnosis`
- `ma2005_candidate_length_power_0_gate_error_ratio`
- `ma2005_candidate_length_power_1_gate_error_ratio`
- `ma2005_candidate_length_power_2_gate_error_ratio`
- `ma2005_best_length_power_candidate`
- `ma2005_best_length_power_candidate_status`

其中阻尼项的分母明确写为 `rho * displacement_volume * L^r * sqrt(g/L)`；这与论文常见写法 `b/(rho*displacement_volume*L^r) * sqrt(L/g)` 等价，避免把 `sqrt(L/g)` 误读为分母。

首行 Wigley III 的归一化审计结论如下。

| 系数 | Eq. (34) 长度幂 | 当前所需尺度 / Eq. (34) 尺度 | 最佳长度幂候选 | 最佳候选状态 | 解释 |
|---|---:|---:|---:|---|---|
| `A33` | `0` | `10.29` | `2` | `PASS` | 错误使用 `L^2` 可让 A33 偶然进入门槛，但这直接违背 Eq. (34)，不能作为生产修正。 |
| `B33` | `0` | `4.59` | `2` | `FAIL` | 即使用错误长度幂仍不过，说明 B33 不只是尺度公式问题。 |
| `A35` | `1` | `14.07` | `2` | `FAIL` | pitch 耦合项需要远大于一个长度幂误差的修正。 |
| `B35` | `1` | `50.17` | `2` | `FAIL` | 当前最强阻塞项之一，归一化候选无法解释。 |
| `A53` | `1` | `9.63` | `2` | `FAIL` | 错误长度幂能减小误差但仍无法通过。 |
| `B53` | `1` | `0.94` | `1` | `PASS` | 当前通过项使用的正是 Eq. (34) 文档长度幂。 |
| `A55` | `2` | `1.43` | `2` | `FAIL` | 已在正确长度幂下最接近，但仍未达 15% 对角项门槛。 |
| `B55` | `2` | `20.65` | `2` | `FAIL` | 即使用正确 pitch 长度幂也严重偏大，下一步仍应查 pitch damping 物理链条。 |

这组结果把“能不能靠改无量纲尺度过 Gate 1”回答得更清楚：不能。`A33` 的错误 `L^2` 候选虽然会偶然通过，但它不是文献定义；其他主要失败项在 `L^0/L^1/L^2` 三个候选下也不能整体通过。因此 Gate 1 下一步应继续聚焦求解链，而不是改 hard gate 的 Eq. (34) 归一化约定。

### 9.4 `partial phi / partial x` 站位梯度链诊断

2026-08-01 继续把 Eq. (30) 中的 `U * partial phi / partial x` 通道拆成可读的站位梯度尺度。新增输出目录为：

```text
outputs/matched_bie_provider_gradient_chain_probe/results
```

新增字段包括：

- `matched_heave_body_potential_x_gradient_norm_max`
- `matched_pitch_body_potential_x_gradient_norm_max`
- `matched_heave_body_potential_x_gradient_to_potential_gain_max`
- `matched_pitch_body_potential_x_gradient_to_potential_gain_max`
- `matched_heave_body_potential_x_gradient_characteristic_length_min`
- `matched_pitch_body_potential_x_gradient_characteristic_length_min`
- `matched_heave_body_potential_x_gradient_gain_times_hull_length_max`
- `matched_pitch_body_potential_x_gradient_gain_times_hull_length_max`
- `matched_selected_body_potential_x_gradient_norm_max`
- `matched_selected_body_potential_x_gradient_to_potential_gain_max`
- `matched_selected_body_potential_x_gradient_characteristic_length_min`
- `matched_selected_body_potential_x_gradient_gain_times_hull_length_max`

首行 Wigley III 探针的代表性结果如下。

| 系数 | 状态 | `|dphi/dx|/|phi|` 最大值 | 等效变化长度最小值 | `L*|dphi/dx|/|phi|` 最大值 | forward/time 压力比最大值 | 解释 |
|---|---|---:|---:|---:|---:|---|
| `A33` | `FAIL` | `36.999 1/m` | `0.0270 m` | `110.998` | `44.399` | heave 模态体面势沿站位变化很陡，前进速度压力项有足够条件压过时间导数项。 |
| `B33` | `FAIL` | `36.999 1/m` | `0.0270 m` | `110.998` | `22.200` | 同一 heave 梯度链影响阻尼项。 |
| `A35` | `FAIL` | `35.607 1/m` | `0.0281 m` | `106.821` | `28.486` | pitch 模态产生 heave force 的耦合项受到强站位梯度影响。 |
| `B35` | `FAIL` | `35.349 1/m` | `0.0283 m` | `106.047` | `16.967` | 耦合阻尼仍是强阻塞项，梯度链是主要嫌疑之一。 |
| `A53` | `FAIL` | `36.999 1/m` | `0.0270 m` | `110.998` | `22.200` | heave 模态产生 pitch moment 的链条也继承同一梯度陡峭度。 |
| `B53` | `PASS` | `36.999 1/m` | `0.0270 m` | `110.998` | `22.200` | 虽然该项通过，但不代表梯度链整体正确；它可能来自 Stokes body forward term 的抵消。 |
| `A55` | `FAIL` | `35.933 1/m` | `0.0278 m` | `107.798` | `43.119` | pitch 对角项的梯度通道仍很强。 |
| `B55` | `FAIL` | `35.933 1/m` | `0.0278 m` | `107.798` | `43.119` | 纵摇阻尼严重偏大，和强 `dphi/dx` 通道一致。 |

这组证据说明：Eq. (30) 的前进速度压力项之所以强，并不是公式漏乘，而是当前站位体面势在 x 方向上的数值梯度过陡。以 `L=3 m` 的 Wigley III 为例，`L*|dphi/dx|/|phi|` 达到约 `106-111`，对应的势函数等效变化长度只有约 `2.7 cm`。这明显小于船长尺度，也小于通常希望看到的平滑站位变化尺度。

因此下一步 Gate 1 的硬动作应为：

1. 输出并比较相邻站位 `body_potential` 的复相位差、范数跳变和面板索引对应关系，确认没有因站位重采样或左右舷排序导致伪梯度。
2. 对 `central/forward/backward` 差分结果做同一套 `|dphi/dx|/|phi|` 与 `L*gain` 审计，不把任何一个差分格式直接写为生产修正。
3. 将 `U * partial phi / partial x` 与 Eq. (32) 的 Stokes body/end-term 路线继续并列表达，检查是否存在有限差分前进速度项与 Stokes 端部项的双计或漏计。

### 9.5 相邻站位势函数连续性与面板索引诊断

2026-08-01 按 9.4 节的下一步要求，把相邻站位 `body_potential` 连续性和面板几何索引连续性接入 `matched_bie_provider` 的 `contribution_breakdown` 与 Ma 2005 comparison CSV。新增输出目录为：

```text
outputs/matched_bie_provider_station_continuity_probe/results
```

本次 probe 命令为：

```text
python -m planing_seakeeping validate --benchmark all --out outputs/matched_bie_provider_station_continuity_probe/results --reference-root outputs/matched_bie_provider_gate_probe/reference --ma-hydro-model matched_bie_provider --ma-bem-free-surface-panels 4 --ma-bem-body-panels 8
```

新增字段包括：

- `matched_selected_adjacent_body_potential_relative_jump_max`
- `matched_selected_adjacent_body_potential_symmetric_norm_ratio_max`
- `matched_selected_adjacent_body_potential_phase_deg_abs_max`
- `matched_selected_adjacent_body_potential_real_alignment_min`
- `matched_body_panel_mid_y_adjacent_relative_jump_max`
- `matched_body_panel_mid_z_adjacent_relative_jump_max`
- `matched_body_panel_normal_adjacent_relative_jump_max`
- `matched_body_panel_length_adjacent_relative_jump_max`

首行 Wigley III 探针的代表性结果如下。

| 系数 | 状态 | 相邻势函数相对跳变最大值 | 相邻势函数范数比最大值 | 相位差绝对值最大值 | 实部对齐最小值 | 面板 `y` 中点跳变 | 面板 `z` 中点跳变 | 面板法向跳变 | 解释 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `A33` | `FAIL` | `1.292` | `2.842` | `180.000 deg` | `-0.775` | `0.485` | `0.008` | `0.083` | heave 模态相邻站位出现近似反相，足以制造很强的有限差分梯度。 |
| `B33` | `FAIL` | `1.292` | `2.842` | `180.000 deg` | `-0.775` | `0.485` | `0.008` | `0.083` | 与 A33 使用同一 heave 模态势函数，因此继承同一相位问题。 |
| `A35` | `FAIL` | `1.349` | `3.376` | `178.596 deg` | `-0.775` | `0.485` | `0.008` | `0.083` | pitch 模态到 heave force 的耦合也存在近反相站位跳变。 |
| `B35` | `FAIL` | `1.378` | `3.599` | `178.981 deg` | `-0.775` | `0.485` | `0.008` | `0.083` | 当前最强阻塞项之一；相邻势函数范数比和相位翻转同时偏大。 |
| `A53` | `FAIL` | `1.292` | `2.842` | `180.000 deg` | `-0.775` | `0.485` | `0.008` | `0.083` | heave 模态产生 pitch moment 时，错误仍来自同一上游势函数链。 |
| `B53` | `PASS` | `1.292` | `2.842` | `180.000 deg` | `-0.775` | `0.485` | `0.008` | `0.083` | 该项通过不能证明势函数链正确，只说明局部抵消后数值落入门槛。 |
| `A55` | `FAIL` | `1.323` | `3.075` | `178.427 deg` | `-0.775` | `0.485` | `0.008` | `0.083` | pitch 对角附加质量仍受相邻站位相位不连续影响。 |
| `B55` | `FAIL` | `1.323` | `3.075` | `178.427 deg` | `-0.775` | `0.485` | `0.008` | `0.083` | pitch 阻尼偏大，与 9.4 节的强 `dphi/dx` 通道互相印证。 |

这组结果把 9.4 节的“梯度过陡”进一步定位到了更上游：相邻站位体面势函数本身并不平滑，而是出现接近 `180 deg` 的复相位翻转。面板几何诊断没有显示同等量级的法向或纵向中点异常：`z` 中点相对跳变约 `0.008`，法向跳变约 `0.083`，面板长度跳变约 `0.023`。`y` 中点跳变约 `0.485` 较大，主要与 Wigley 解析剖面在艏艉区域水线宽度快速变化有关，需要继续和 station beam 分布并读，但它不足以单独解释近 `180 deg` 的复相位反转。

因此 Gate 1 的下一步不应优先改 Eq. (34) 归一化，也不应继续做单个系数符号试探，而应集中检查 matched BIE 求解器的复相位规范：

1. 逐站输出 heave/pitch `body_potential` 的主相位，并比较 bow-to-stern marching 顺序与 `x_m` 返回顺序，确认差分前没有隐含反向排列。
2. 检查每个二维站位内域 Green identity 的未知量符号约定，尤其是 Dirichlet `phi` 与 Neumann `partial phi / partial n` 的行符号是否会在相邻站位随剖面尺度变化出现相位翻转。
3. 对 station-to-station `body_potential` 做只读的 phase unwrapping diagnostic，观察去除全局复相位后 `|dphi/dx|/|phi|` 是否显著下降；该步骤只能作为诊断，不能在未证明论文相位约定前进入生产默认。
4. 把面板 `y` 中点跳变与局部 beam 梯度并列表达，区分真实几何快速变化与 panel-index 错配。

### 9.6 只读 phase-aligned 梯度诊断

在 9.5 节之后，同一 probe 又增加了 `phase_aligned` 诊断字段。这个诊断的做法是：沿相邻站位逐步乘以一个单位复数，使当前站位 `body_potential` 与上一站位的复内积变为正实数。它的目的不是修改生产模型，而是回答一个非常具体的问题：如果相邻站位之间的整体复相位翻转被拿掉，`partial phi / partial x` 的异常放大是否会自然消失。

新增字段包括：

- `matched_selected_phase_aligned_body_potential_x_gradient_to_potential_gain_max`
- `matched_selected_phase_aligned_body_potential_x_gradient_characteristic_length_min`
- `matched_selected_phase_aligned_body_potential_x_gradient_gain_times_hull_length_max`
- `matched_selected_phase_aligned_gradient_gain_to_raw_gain_ratio_median`
- `matched_selected_phase_aligned_adjacent_body_potential_relative_jump_max`
- `matched_selected_phase_aligned_adjacent_body_potential_phase_deg_abs_max`
- `matched_selected_phase_aligned_adjacent_body_potential_real_alignment_min`

首行 Wigley III 的对齐前后对比如下。

| 系数 | 状态 | 原始 `|dphi/dx|/|phi|` 最大值 | 相位对齐后 `|dphi/dx|/|phi|` 最大值 | 相位对齐后等效变化长度最小值 | 相位对齐后 `L*gain` 最大值 | 原始相位差最大值 | 对齐后相位差最大值 | 解释 |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `A33` | `FAIL` | `36.999 1/m` | `27.387 1/m` | `0.0365 m` | `82.162` | `180.000 deg` | `~0 deg` | 相位翻转被移除后梯度下降，但仍远高于船长尺度。 |
| `B33` | `FAIL` | `36.999 1/m` | `27.387 1/m` | `0.0365 m` | `82.162` | `180.000 deg` | `~0 deg` | 阻尼链条同样没有因相位对齐而恢复到合理尺度。 |
| `A35` | `FAIL` | `35.607 1/m` | `32.485 1/m` | `0.0308 m` | `97.456` | `178.596 deg` | `~0 deg` | pitch-to-heave 耦合对相位对齐不敏感，说明还存在幅值/几何/边界条件放大。 |
| `B35` | `FAIL` | `35.349 1/m` | `33.096 1/m` | `0.0302 m` | `99.287` | `178.981 deg` | `~0 deg` | 最强阻塞项仍保持强梯度，不能靠简单 phase unwrap 解释。 |
| `A53` | `FAIL` | `36.999 1/m` | `27.387 1/m` | `0.0365 m` | `82.162` | `180.000 deg` | `~0 deg` | heave 模态 pitch moment 链条仍需检查 `N5`、lever arm 和压力积分。 |
| `B53` | `PASS` | `36.999 1/m` | `27.387 1/m` | `0.0365 m` | `82.162` | `180.000 deg` | `~0 deg` | 通过项也保留异常梯度证据，因此不能把 B53 作为整链正确性的证明。 |
| `A55` | `FAIL` | `35.933 1/m` | `31.574 1/m` | `0.0317 m` | `94.721` | `178.427 deg` | `~0 deg` | 纵摇对角项仍需要继续检查 pitch 行和端部项。 |
| `B55` | `FAIL` | `35.933 1/m` | `31.574 1/m` | `0.0317 m` | `94.721` | `178.427 deg` | `~0 deg` | 纵摇阻尼偏大不是单纯相位规范问题。 |

这组结果很重要：相位对齐确实把相邻站位的复相位差从接近 `180 deg` 降到约 `0 deg`，但 `|dphi/dx|/|phi|` 最大值仍维持在 `27-33 1/m`，对应的等效变化长度只有 `3.0-3.7 cm`。也就是说，当前 Gate 1 失败不能被简化成“站位相位没展开”这一件事。相位翻转是可疑症状，但对齐后仍有强幅值梯度和耦合项放大。

下一步硬动作因此进一步收窄为：

1. 对每个站位输出 `body_potential` 范数、局部 beam、局部 draft、局部水下面积和 `body_potential`/beam 或 `body_potential`/area 归一化量，检查是否是艏艉小剖面导致势函数幅值归一化奇异。
2. 对 `central/forward/backward` 三种差分格式同时输出原始与 phase-aligned 的 `|dphi/dx|/|phi|`，确认异常是否由端点差分、非均匀站距或艏艉活动站筛选放大。
3. 单独审计 `B35/B55` 的 pressure-gradient force density 沿站位分布，找出贡献峰值来自艏部、艉部还是中体。
4. 保持 `phase_aligned` 为只读诊断。除非能从 Ma 2005 的势函数相位定义和 marching 方程推出相同处理，否则绝不把它并入生产默认。

### 9.7 站位几何、差分格式与 force-density 峰值诊断

2026-08-01 继续把 9.6 节列出的三项硬动作接入 `matched_bie_provider`。新增输出目录为：

```text
outputs/matched_bie_provider_geometry_gradient_force_density_probe/results
```

本次新增字段分三类：

- 站位几何尺度：`station_waterplane_beam_*`、`station_effective_draft_*`、`station_submerged_area_*`，以及 `body_potential_norm_to_beam_squared`、`body_potential_norm_to_submerged_area`。
- 差分格式对比：`central/forward/backward` 三种 `body_potential_x_gradient_to_potential_gain`，以及相同三种 `phase_aligned` 诊断。
- 力密度峰值定位：`heave_pitch_total/time_derivative/forward_speed_force_density_peak_x_over_l`、`abs_centroid_x_over_l` 和 `peak_to_integral_abs_ratio`。

这里的 `x/L` 采用 `StationHull` 的坐标，`x=0` 为艉端，`x=L` 为艏端。首行 Wigley III 代表性结果如下。

| 系数 | 状态 | `phi/B^2` 最大值 | `phi/B^2` 峰值 `x/L` | `phi/area` 最大值 | `phi/area` 峰值 `x/L` | beam 梯度峰值 `x/L` | area 梯度峰值 `x/L` | 解释 |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `A33` | `FAIL` | `1.23e4` | `0.025` | `2.87e3` | `0.025` | `0.975` | `0.975` | heave 势函数经局部尺度归一化后在艉端第一活动站最大。 |
| `B33` | `FAIL` | `2.45e4` | `0.025` | `5.74e3` | `0.025` | `0.975` | `0.975` | 阻尼项继承同一艉端小剖面尺度敏感性。 |
| `A35` | `FAIL` | `5.49e4` | `0.025` | `1.28e4` | `0.025` | `0.975` | `0.975` | pitch 模态到 heave force 的耦合在艉端更尖。 |
| `B35` | `FAIL` | `8.93e4` | `0.025` | `2.09e4` | `0.025` | `0.975` | `0.975` | 当前最强阻塞项的势函数几何归一化峰值位于艉端。 |
| `A53` | `FAIL` | `2.45e4` | `0.025` | `5.74e3` | `0.025` | `0.975` | `0.975` | heave 模态 pitch moment 链条也被艉端尺度放大影响。 |
| `B53` | `PASS` | `2.45e4` | `0.025` | `5.74e3` | `0.025` | `0.975` | `0.975` | 单项通过不消除艉端异常证据。 |
| `A55` | `FAIL` | `3.82e4` | `0.025` | `8.93e3` | `0.025` | `0.975` | `0.975` | pitch 对角项的端部尺度问题仍明显。 |
| `B55` | `FAIL` | `3.82e4` | `0.025` | `8.93e3` | `0.025` | `0.975` | `0.975` | 纵摇阻尼偏大与艉端小剖面归一化峰值一致。 |

差分格式对比显示，异常并不只属于某一种差分格式。

| 系数 | central | forward | backward | phase-aligned central | phase-aligned forward | phase-aligned backward | 解释 |
|---|---:|---:|---:|---:|---:|---:|---|
| `A33/B33/A53/B53` | `36.999` | `47.994` | `48.961` | `27.387` | `29.688` | `28.816` | heave 模态在三种差分下都偏高；相位对齐只能部分降低。 |
| `B35` | `35.349` | `35.444` | `47.188` | `33.096` | `24.013` | `46.394` | `B35` 对 backward 端点差分尤其敏感，但 forward/central 也不低。 |
| `B55` | `35.933` | `40.426` | `47.853` | `31.574` | `24.100` | `40.123` | `B55` 的强梯度不是 central 差分单独造成的。 |

力密度峰值进一步把 `B35/B55` 的 pressure-gradient 阻塞位置定位到艉端第一活动站。

| 系数 | total 峰值 `x/L` | time 峰值 `x/L` | forward 峰值 `x/L` | forward 绝对质心 `x/L` | forward 峰值/绝对积分比 | 解释 |
|---|---:|---:|---:|---:|---:|---|
| `A33` | `0.025` | `0.300` | `0.025` | `0.334` | `5.11` | 前进速度压力力密度峰值在艉端，但整体绝对质心仍在前 1/3 船长附近。 |
| `B35` | `0.025` | `0.325` | `0.025` | `0.276` | `9.22` | 阻塞最严重的耦合阻尼项有更强的艉端局部峰值。 |
| `B55` | `0.025` | `0.250` | `0.025` | `0.228` | `12.77` | 纵摇阻尼的 forward-speed 密度更加向艉端集中。 |

本节结论是：Gate 1 当前最值得优先排查的不是 Eq. (34) 无量纲尺度，也不是单一差分格式，而是**端部活动站与压力梯度链条的耦合**。几何梯度最大值出现在 `x/L=0.975` 的艏端，但势函数按局部尺度归一化后的最大值、以及 forward-speed force-density 峰值，都落在 `x/L=0.025` 的艉端第一活动站。这说明艉端小湿剖面、端点差分、end-term/Stokes body term 与 Eq. (30) 有限差分前进速度项之间可能存在重复、漏计或坐标映射不一致。

下一步硬动作应进一步收窄为：

1. 对 `x/L=0.025` 的艉端第一活动站做单站审计：输出剖面 beam、draft、area、panel 长度、法向、`body_potential`、`partial phi / partial x`、pressure time/forward 分量和 generalized row。
2. 做一个只读的 `exclude_end_active_station` 或 `end_gradient_one_sided_only` 诊断，不进入生产默认，只观察去除艉端第一活动站后八个 Ma 系数的 raw/reference ratio 是否整体改善。
3. 并列比较 Eq. (30) forward-gradient 通道与 Eq. (32) Stokes body/end-contour 通道在艉端附近的贡献，专门排查重复计算或端部符号不一致。

### 9.8 艉端第一活动站单站审计与排除端部对照

2026-08-01 继续把 9.7 节列出的端部活动站审计接入 `matched_bie_provider`。新增输出目录为：

```text
outputs/matched_bie_provider_end_station_audit_probe/results
```

本次 probe 命令为：

```text
python -m planing_seakeeping validate --benchmark all --out outputs/matched_bie_provider_end_station_audit_probe/results --reference-root outputs/matched_bie_provider_gate_probe/reference --ma-hydro-model matched_bie_provider --ma-bem-free-surface-panels 4 --ma-bem-body-panels 8
```

总体结果仍未通过 Gate 1：`validation_summary.csv` 中有 `PASS=65`、`INFO=17`、`NOT_EVALUATED=8`、`FAIL=15`。这说明新增诊断只是把错误来源定位得更细，尚未构成生产修正。

艉端第一活动站的几何审计结果如下。该站位位于 `x/L=0.025`，即离艉端很近的第一个有效湿剖面；它的水线宽度只有 `0.02925 m`，水下面积只有 `0.003656 m^2`，但面板总长度达到 `0.37649 m`。这种“小面积、长边界”的组合很容易放大边界积分矩阵、纵向差分和压力积分中的局部误差。

| 系数 | 状态 | 艉端站 `x/L` | beam | draft | area | `|phi|` | `|dphi/dx|/|phi|` | forward/time 压力范数比 | 艉端 forward force-density |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `A33` | `FAIL` | `0.025` | `0.02925 m` | `0.18750 m` | `0.003656 m^2` | `10.497` | `32.761 1/m` | `39.313` | `8866.878` |
| `B33` | `FAIL` | `0.025` | `0.02925 m` | `0.18750 m` | `0.003656 m^2` | `20.994` | `32.761 1/m` | `19.656` | `17733.757` |
| `A35` | `FAIL` | `0.025` | `0.02925 m` | `0.18750 m` | `0.003656 m^2` | `46.935` | `22.998 1/m` | `18.399` | `25121.133` |
| `B35` | `FAIL` | `0.025` | `0.02925 m` | `0.18750 m` | `0.003656 m^2` | `76.400` | `22.419 1/m` | `10.761` | `39391.684` |
| `A53` | `FAIL` | `0.025` | `0.02925 m` | `0.18750 m` | `0.003656 m^2` | `20.994` | `32.761 1/m` | `19.656` | `25270.603` |
| `B53` | `PASS` | `0.025` | `0.02925 m` | `0.18750 m` | `0.003656 m^2` | `20.994` | `32.761 1/m` | `19.656` | `25270.603` |
| `A55` | `FAIL` | `0.025` | `0.02925 m` | `0.18750 m` | `0.003656 m^2` | `32.668` | `23.956 1/m` | `28.747` | `26405.730` |
| `B55` | `FAIL` | `0.025` | `0.02925 m` | `0.18750 m` | `0.003656 m^2` | `32.668` | `23.956 1/m` | `28.747` | `26405.730` |

只读排除端部对照的结果如下。这里的排除并不是候选生产算法，而是为了回答一个具体问题：如果把艉端第一活动站、艏端第一活动站或两端活动站从压力积分中拿掉，Ma 2005 的八个首行系数是否会整体恢复合理。

| 系数 | 状态 | 原始 raw/reference | 排除艉端 | 排除艏端 | 排除两端 | 判断 |
|---|---|---:|---:|---:|---:|---|
| `A33` | `FAIL` | `10.290` | `10.296` | `10.291` | `10.297` | 几乎无改善，说明 `A33` 的主偏差不是单个端部站直接积分造成的。 |
| `B33` | `FAIL` | `4.594` | `3.935` | `4.342` | `3.970` | 排除艉端略有改善，但仍远高于 15% 门槛。 |
| `A35` | `FAIL` | `14.069` | `12.880` | `13.602` | `12.948` | 端部贡献存在，但不是全部错误。 |
| `B35` | `FAIL` | `50.171` | `39.683` | `45.414` | `39.411` | 艉端对最严重阻尼耦合有显著影响，但去除后仍数量级错误。 |
| `A53` | `FAIL` | `9.632` | `9.647` | `9.629` | `9.644` | 几乎无改善，说明 moment 链条还有系统性问题。 |
| `B53` | `PASS` | `0.943` | `7.634` | `4.164` | `7.998` | 当前通过依赖局部抵消，不能作为整体模型可靠的证据。 |
| `A55` | `FAIL` | `1.430` | `5.613` | `3.478` | `5.847` | 排除端部反而变差，说明 pitch 对角项中有重要抵消结构。 |
| `B55` | `FAIL` | `20.655` | `13.472` | `17.771` | `13.665` | 艉端会放大阻尼，但不是唯一来源。 |

本节结论是：**不能把 Gate 1 失败简单修正为“删掉端部活动站”**。端部活动站确实暴露出小剖面尺度放大、强纵向势梯度和 forward-speed 压力项偏大的问题；但是排除端部后，`A33/A53` 基本不变，`A55` 甚至变差，`B53` 的通过也会被破坏。这说明当前主问题更像是压力链条、纵向梯度项、Stokes body/end-term 与整船装配之间的系统性一致性问题，而不是单点异常。

下一轮真正有价值的硬动作应为：

1. 做 Eq. (30) 与 Eq. (32) 的逐项守恒审计：分别输出 time-derivative pressure、forward-speed pressure、Stokes body correction、end-contour correction 对八个 Ma 系数的贡献矩阵，检查符号、量纲、力矩臂和是否重复计入。
2. 对 `B53` 做“抵消拆解”：逐站列出正负贡献，使它不再只是数值上通过，而要知道它为什么通过。
3. 引入一个解析或半解析低速/无前速剖面基准，例如 Lewis section、矩形剖面或半圆剖面二维附加质量，用来单独验证内域 BIE 的 `phi` 与 `partial phi / partial n` 符号规范。
4. 将 `exclude_end_active_station` 保持为验证报告字段，禁止作为默认生产开关。只有当 Eq. (30)/(32) 链条被证明正确后，才能讨论端部平滑、端部截断或非均匀积分权重。

### 9.9 Eq. (30)/Eq. (32) 组合候选与逐站抵消诊断

2026-08-01 继续把 9.8 节提出的“逐项守恒审计”和“`B53` 抵消拆解”做成可重复输出。新增输出目录为：

```text
outputs/matched_bie_provider_station_contribution_probe/results
```

本次新增两类验证证据：

1. `ma2005_wigley_iii_coefficients_comparison.csv` 增加只读组合候选字段，例如 `time_only`、`time_plus_pressure_gradient`、`time_plus_pressure_gradient_plus_end`、`time_plus_stokes_body_plus_end` 和 `all_terms`。这些字段回答的是：如果只改变 Eq. (30) 前进速度压力项、Eq. (32) Stokes body 项和 end-contour 项的组合关系，八个 Ma 系数会不会自然接近文献。
2. 新增 `ma2005_wigley_iii_coefficients_matched_station_contributions.csv`，逐站列出选中系数的 `total`、`time_derivative`、`pressure_gradient` 和 `stokes_body_forward` 的系数密度。这样 `B53` 这类“最终数值通过”的项可以继续拆成每个站位的正负贡献，而不是只看一个通过标签。

组合候选的首行 Wigley III 结论如下。

| 系数 | Gate 状态 | 当前 raw/reference | 最佳只读组合 | 最佳组合 raw/reference | 解释 |
|---|---|---:|---|---:|---|
| `A33` | `FAIL` | `10.290` | `time_only` | `10.290` | 前进速度项和端部项对该项几乎不起作用，主偏差来自时间导数/势函数幅值链。 |
| `B33` | `FAIL` | `4.594` | `time_plus_stokes_body_plus_end` | `0.286` | 去掉 pressure-gradient 可显著降低阻尼，但会低估；说明不是简单替换即可过关。 |
| `A35` | `FAIL` | `14.069` | `time_only` | `5.494` | pressure-gradient 和 end term 都会进一步放大耦合附加质量。 |
| `B35` | `FAIL` | `50.171` | `time_only` | `31.662` | 最严重耦合阻尼即使只保留时间项也远高于参考。 |
| `A53` | `FAIL` | `9.632` | `time_only` | `9.632` | 与 `A33` 类似，主偏差不由端部项决定。 |
| `B53` | `PASS` | `0.943` | `time_plus_pressure_gradient_plus_end` | `0.943` | 当前通过依赖 pressure-gradient 与 end term 的抵消，不代表链条整体正确。 |
| `A55` | `FAIL` | `1.430` | `time_only` | `0.831` | 只保留时间项已接近，但仍超出 15% 门槛；Stokes body 会显著放大。 |
| `B55` | `FAIL` | `20.655` | `time_only` | `6.421` | 纵摇阻尼的主问题不是 end term 单独造成，而是压力链整体过强。 |

逐站抵消诊断进一步解释了为什么 `B53` 当前能通过。`B53` 的 pressure-gradient 分量为 `-0.37998`，end term 为 `+0.28567`，二者相加后得到 `-0.09431`，刚好接近参考 `-0.1`。但是逐站系数密度显示，该接近值来自很强的正负抵消：

| 排名 | 站位 `x/L` | `B53` total density | 符号 | 解释 |
|---:|---:|---:|---|---|
| 1 | `0.025` | `+16.116` | positive | 艉端第一活动站给出巨大正贡献。 |
| 2 | `0.075` | `-11.527` | negative | 紧邻上游站给出巨大负贡献。 |
| 3 | `0.050` | `-5.891` | negative | 第二活动站继续抵消艉端正峰。 |
| 4 | `0.100` | `+5.856` | positive | 第四站又反向抵消前两站。 |
| 5 | `0.350` | `+2.656` | positive | 中前部还有次级正贡献。 |

`B53` 的 total density cancellation index 为 `12.03`。这个指标可理解为“正贡献绝对量加负贡献绝对量，再除以最终净值的绝对量”。数值越大，说明最终结果越依赖抵消。`12.03` 表示站位正负贡献的总活动量约为净结果的 12 倍，因此 `B53` 的 `PASS` 不能证明模型已可信。

本节结论是：

1. 当前 Gate 1 失败不是一个简单的 “Eq. (32) Stokes body 替换 Eq. (30) pressure-gradient” 问题。`Stokes body` 对 `A55/B55` 会明显放大，直接叠加会更差。
2. `time_only` 对多个失败项是最佳只读候选，但 `A33/A35/B35/A53/B55` 仍远超门槛，说明 body potential 幅值、相位、压力积分和 station marching 仍需继续审计。
3. `B53` 的通过应从“模型正确证据”降级为“局部抵消现象”。后续报告必须继续展示 `matched_selected_total_density_cancellation_index`，不能只按 PASS/FAIL 汇总。
4. 下一步最硬的技术目标应转向二维剖面层基准：用解析/半解析剖面测试证明内域 BIE 的势函数幅值、法向导数、压力积分行和符号规范是对的。否则整船层面的 Eq. (30)/Eq. (32) 组合只会在错误底座上反复试探。

### 9.10 二维圆柱附加质量解析审计

2026-08-01 继续落实 9.9 节第 4 条，把“二维剖面层基准”做成自动化输出。新增输出目录为：

```text
outputs/matched_bie_provider_closed_cylinder_audit_probe/results
```

新增文件包括：

| 文件 | 内容 | 作用 |
|---|---|---|
| `a1_closed_cylinder_added_mass.csv` | 不同面元数下的圆柱 heave 附加质量审计明细。 | 检查内域 source-panel Neumann 求解、体面势恢复、Eq. (30) 时间压力项和体面积分链条。 |
| `a1_closed_cylinder_added_mass_summary.csv` | 最细网格结果、误差和诊断结论。 | 给总体验收报告提供一行可读摘要。 |
| `a1_closed_cylinder_added_mass_metadata.csv` | 解析参考、公式和审计范围。 | 明确该测试是 diagnostic，不是 Ma 2005 硬门槛。 |

本审计使用二维无限流体中圆柱横向振荡的解析结果。半径为 `r` 的圆柱在 heave 方向的单位长度附加质量为：

```text
m_a = rho*pi*r^2
```

这里 `rho` 是水密度，`pi*r^2` 是圆柱排开流体面积。它适合作为底层基准，是因为它不涉及船长方向积分、自由面历史卷积、前进速度梯度、端部项和无量纲化；如果这个最小压力链都不能闭合，那么整船 2.5D 的八个系数即使偶然接近文献，也缺乏可信解释。

本轮结果如下。

| panel_count | raw added-mass ratio | pressure-sign-corrected ratio | corrected relative error | diagnostic status |
|---:|---:|---:|---:|---|
| 64 | `-1.01046` | `1.01046` | `0.01046` | `PASS` |
| 128 | `-1.00539` | `1.00539` | `0.00539` | `PASS` |
| 256 | `-1.00274` | `1.00274` | `0.00274` | `PASS` |

最细网格的 source-system relative residual 为 `6.88e-16`，说明线性方程本身求解精度很高；body potential 与解析势函数的最佳比例约为 `-1.00284`，说明幅值已经非常接近解析解，但符号约定相反。用当前 Eq. (30) 时间压力链直接积分时，computed added mass ratio 为 `-1.00274`；把压力符号修正后，ratio 变为 `+1.00274`，相对误差降到 `0.2736%`。

因此本节给出的不是一个可以直接写进生产模型的“改符号结论”，而是一个更窄、更可靠的定位结论：

1. 闭合圆柱基准显示，内域 Neumann source solve 的幅值是可信的，面元加密后误差稳定下降。
2. 当前 pressure-to-force 链条在最简单解析测试中暴露出符号约定反向：体面势与解析势函数的对齐比例约为 `-1`，直接压力积分得到负的附加质量。
3. Ma 2005 Gate 1 仍然失败，不能因为圆柱 pressure-sign-corrected 结果很好就全局翻转生产符号。原因是 matched station 还包含 inner/free/control 混合边界、外域匹配、自由面 marching、pressure-gradient、Stokes body 和 end-contour 项，这些项之间可能有成对符号约定。
4. 下一步应沿着“二维解析基准 -> mixed boundary -> 单站剖面 -> 整船装配”的顺序追踪符号，而不是在整船层对八个系数做经验性候选组合。

该审计已经接入 `validate_goal_gap_audit()`，总体验收表中新增指标：

```text
a1_closed_cylinder_added_mass_inner_pressure_chain
```

当前该指标状态为 `INFO`，实际值为：

```text
raw_ratio=-1.00274; corrected_ratio=1.00274; conclusion=closed_cylinder_exposes_inner_pressure_sign_reversal
```

这个结果把下一步目标进一步压实为：在不破坏 closed-boundary Green identity 和 mixed-boundary Green identity 的前提下，解释并统一圆柱压力链符号、matched station 体面势符号、Eq. (30) pressure-gradient 符号与 Eq. (32) Stokes/end-term 符号。只有当这个符号审计链闭合后，才能对生产 `matched_bie_provider` 做公式修正，并重新冲击 Ma 2005 Gate 1。

### 9.11 Eq. (30) 压力符号候选的整船层筛查

2026-08-01 继续把 9.10 节的圆柱反号线索推进到 Wigley III 整船层。新增输出目录为：

```text
outputs/matched_bie_provider_pressure_sign_candidates_probe/results
```

新增文件包括：

| 文件 | 内容 | 作用 |
|---|---|---|
| `ma2005_wigley_iii_coefficients_pressure_sign_candidate_detail.csv` | 每个 Ma 2005 参考点、每个压力符号候选的计算值、误差、gate ratio 和状态。 | 回答“某个符号候选改善了哪些系数、恶化了哪些系数”。 |
| `ma2005_wigley_iii_coefficients_pressure_sign_candidate_summary.csv` | 每个候选跨八个 Wigley III 系数的通过数、中位 gate ratio 和最大 gate ratio。 | 防止只因为某个候选改善单个系数，就被误认为可进入生产默认。 |

本轮候选不改变生产 `matched_bie_provider`，只在已有 `time_derivative`、`pressure_gradient`、`Stokes body` 和 `end term` 复力分量上做只读重组。候选设计如下：

| 候选 | 含义 |
|---|---|
| `current_default` | 当前生产默认，即 Eq. (30) time derivative + pressure gradient + end term。 |
| `time_derivative_flipped_keep_gradient_end` | 只翻 Eq. (30) 时间导数压力项，保留 pressure-gradient 和 end term。 |
| `pressure_gradient_flipped_keep_time_end` | 只翻 Eq. (30) 前进速度 pressure-gradient 项，保留时间导数和 end term。 |
| `body_pressure_flipped_keep_end` | 翻转完整 Eq. (30) body pressure，保留 end term。 |
| `body_pressure_and_end_flipped` | 同时翻转 Eq. (30) body pressure 和当前 end term。 |
| `all_terms_flipped` | 同时翻转 Eq. (30)、Stokes body diagnostic term 和 end term。 |

Wigley III 八个系数的汇总结果如下。

| 候选 | pass_count | fail_count | pass_fraction | median gate ratio | max gate ratio | 状态 |
|---|---:|---:|---:|---:|---:|---|
| `pressure_gradient_flipped_keep_time_end` | 0 | 8 | 0.000 | 29.037 | 70.405 | `FAIL` |
| `time_derivative_flipped_keep_gradient_end` | 1 | 7 | 0.125 | 29.698 | 75.267 | `FAIL` |
| `body_pressure_flipped_keep_end` | 0 | 8 | 0.000 | 43.524 | 140.672 | `FAIL` |
| `current_default` | 1 | 7 | 0.125 | 36.167 | 163.904 | `FAIL` |
| `body_pressure_and_end_flipped` | 0 | 8 | 0.000 | 43.760 | 170.571 | `FAIL` |
| `all_terms_flipped` | 0 | 8 | 0.000 | 109.472 | 190.421 | `FAIL` |

这个结果说明三件事：

1. 圆柱解析审计暴露出的 pressure sign reversal 是真实线索，但不能直接等价为整船层“把 Eq. (30) 全部翻号”。`body_pressure_flipped_keep_end` 的八项全失败，最大 gate ratio 仍达 `140.672`。
2. `pressure_gradient_flipped_keep_time_end` 是本轮整船候选中最大误差最小的一项，说明 pressure-gradient 通道确实值得继续追；但它八项没有一项通过，不能进入生产默认。
3. 当前默认至少保住 `B53` 一项通过，而若只翻 pressure-gradient，`B53` 的抵消结构被破坏。因此 `B53` 的通过依然应解释为局部抵消现象，而不是模型已正确。

因此，本节把下一步技术焦点进一步缩窄为：

1. 继续追踪 `pressure_gradient` 的来源，不是简单翻号，而是检查 `partial phi / partial x` 的站位传播、相位对齐、端部差分和局部时间映射。
2. 将 `pressure_gradient_flipped_keep_time_end` 保持为 diagnostic candidate，禁止作为默认生产开关。
3. 在单站和相邻两站层面建立更小的可解析/半解析审计，检查 `free_surface_potential_by_station -> body_potential_by_station -> x-gradient -> pressure-gradient force` 的放大路径。

### 9.12 相邻站 pressure-gradient 放大路径审计

2026-08-01 继续落实 9.11 节第 3 条，把 `free-surface potential -> body potential -> x-gradient -> pressure-gradient force` 做成逐相邻站输出。新增输出目录为：

```text
outputs/matched_bie_provider_station_transfer_path_probe/results
```

新增文件包括：

| 文件 | 内容 | 作用 |
|---|---|---|
| `ma2005_wigley_iii_coefficients_matched_station_transfer_path.csv` | 每个 Ma 2005 系数、每一对相邻站的 free-surface potential norm、body potential norm、相邻站相位/跳变、gradient gain、pressure-gradient force density 等。 | 把“压力梯度为何过大”拆成可读的站位传播链。 |
| `ma2005_wigley_iii_coefficients_matched_station_transfer_path_summary.csv` | 每个系数的 pressure-gradient 峰值站位、最大相邻跳变、最大 `L*|dphi/dx|/|phi|`、相位对齐影响和符号变化次数。 | 判断问题是否集中在局部站位，而不是平均分布在全船。 |

汇总结果如下。

| 系数 | pressure-gradient 峰值 pair | 峰值 `x/L` | peak pressure-gradient density | 最大 body-potential jump | 最大相位差 | 最小 real alignment | 最大 `L*|dphi/dx|/|phi|` | phase-aligned/raw 最大比值 | 最大 forward/time pressure 比值 | pressure-gradient 符号变化 pair 数 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `A33` | 0 | 0.0375 | 0.000 | 1.292 | 180.000 | -0.775 | 110.998 | 1.739 | 44.399 | 0 |
| `B33` | 0 | 0.0375 | 33.928 | 1.292 | 180.000 | -0.775 | 110.998 | 1.739 | 22.200 | 7 |
| `A35` | 0 | 0.0375 | 6.032 | 1.349 | 178.596 | -0.775 | 106.821 | 1.673 | 28.486 | 7 |
| `B35` | 0 | 0.0375 | 19.350 | 1.378 | 178.981 | -0.775 | 106.047 | 1.656 | 16.967 | 8 |
| `A53` | 0 | 0.0375 | 0.000 | 1.292 | 180.000 | -0.775 | 110.998 | 1.739 | 22.200 | 0 |
| `B53` | 0 | 0.0375 | 16.116 | 1.292 | 180.000 | -0.775 | 110.998 | 1.739 | 22.200 | 9 |
| `A55` | 0 | 0.0375 | 6.446 | 1.323 | 178.427 | -0.775 | 107.798 | 1.697 | 43.119 | 9 |
| `B55` | 0 | 0.0375 | 9.191 | 1.323 | 178.427 | -0.775 | 107.798 | 1.697 | 43.119 | 10 |

这张表有几个直接结论。

第一，八个系数的 pressure-gradient 峰值全部落在 pair `0`，也就是 `x/L = 0.025` 到 `0.050` 之间的第一对艉端活动站，中点为 `x/L = 0.0375`。这说明 pressure-gradient 的主要异常不是全船平均噪声，而是一个非常局部的起始站传播/差分问题。

第二，最大 `L*|dphi/dx|/|phi|` 约为 `106` 到 `111`。如果把它换成特征变化长度，就是 `L / 111`，对于 `L = 3 m` 的 Wigley III 模型约为 `0.027 m`。这比船长尺度小得多，也比 station spacing 代表的全船平滑变化尺度更激烈，因此它会把 Eq. (30) 中的 `U * partial phi / partial x` 项放大到不合理水平。

第三，相邻 body potential 的相位差接近 `180 deg`，real alignment 约为 `-0.775`。这意味着第一对活动站的体面势不是平滑同相传播，而是近似反相跳变。相位对齐后的 gradient gain 比 raw 还可达到约 `1.66` 到 `1.74`，说明问题不只是一个简单的复数相位旋转；幅值跳变、起始站状态继承和边界条件共同参与了放大。

第四，`B33/B35/B53/B55` 等阻尼项的 pressure-gradient density 符号在多个相邻站之间频繁变化。尤其 `B55` 有 `10` 个 sign-change pairs，`B53/A55` 也有 `9` 个。这与前面 `B53` 的抵消指数结论一致：当前模型中某些“看起来接近”的结果来自正负大数抵消，而不是平滑、可解释的压力分布。

因此，本节进一步把 Gate 1 下一步压缩为一个更小的技术任务：

1. 单独审计第一对艉端活动站的自由面状态初始化、station history inheritance 和局部时间步长，确认为什么 body potential 会出现接近反相跳变。
2. 对 `x/L = 0.025 -> 0.050` 这对站位做局部两站 BIE 重算，输出 body/free/control 三类边界上的 `phi`、`phi_n`、RHS 分量和 pressure-gradient 分量。
3. 检查第一活动站是否应作为 physical integration station、ghost/start-up station 或需要更明确的 initial transient treatment。只有这个起始站问题解释清楚后，才讨论端部平滑或差分格式改动。

### 9.13 艉端两站 boundary/RHS 源项审计

2026-08-01 继续落实 9.12 节第 2 条，把 `x/L = 0.025` 与 `x/L = 0.050` 两个艉端活动站单独拆出。新增输出目录为：

```text
outputs/matched_bie_provider_aft_pair_boundary_rhs_probe/results
```

新增文件包括：

| 文件 | 内容 | 作用 |
|---|---|---|
| `ma2005_wigley_iii_coefficients_matched_aft_pair_boundary_rhs.csv` | 每个系数、艉端第 0/1 个活动站的 body/free/control 边界范数、RHS 三源项范数与比例、压力项范数和 pressure-gradient density。 | 直接检查第一对站里到底是 body condition、inner free-surface potential 还是 outer history 在主导 RHS。 |
| `ma2005_wigley_iii_coefficients_matched_aft_pair_boundary_rhs_summary.csv` | 每个系数的峰值站、RHS 源项最大比例和 forward/time pressure 最大比值。 | 给报告提供可读摘要，避免在大表里人工查找。 |

八个系数的摘要如下。

| 系数 | 峰值站 | 峰值 `x/L` | peak pressure-gradient density | max forward/time pressure | max RHS body ratio | max RHS free-surface ratio | max RHS history ratio | max body `phi/phi_n` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `A33` | 0 | 0.025 | 0.000 | 39.313 | 0.171 | 0.975 | 0.016 | 23.105 |
| `B33` | 0 | 0.025 | 33.928 | 19.656 | 0.171 | 0.975 | 0.016 | 23.105 |
| `A35` | 0 | 0.025 | 6.032 | 18.399 | 0.233 | 0.937 | 0.010 | 42.144 |
| `B35` | 0 | 0.025 | 19.350 | 10.761 | 0.256 | 0.924 | 0.007 | 44.735 |
| `A53` | 0 | 0.025 | 0.000 | 19.656 | 0.171 | 0.975 | 0.016 | 23.105 |
| `B53` | 0 | 0.025 | 16.116 | 19.656 | 0.171 | 0.975 | 0.016 | 23.105 |
| `A55` | 0 | 0.025 | 6.446 | 28.747 | 0.212 | 0.950 | 0.012 | 38.598 |
| `B55` | 0 | 0.025 | 9.191 | 28.747 | 0.212 | 0.950 | 0.012 | 38.598 |

其中 `B33` 与 `B53` 的艉端两站明细尤其能说明问题：

| 系数 | station | `x/L` | body `phi` norm | body known `phi_n` norm | free known `phi` norm | free solution `phi_n` norm | RHS body ratio | RHS free ratio | RHS history ratio | forward/time pressure | pressure-gradient density |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `B33` | 0 | 0.025 | 20.994 | 0.909 | 2.506 | 11.520 | 0.107 | 0.975 | 0.016 | 19.656 | 33.928 |
| `B33` | 1 | 0.050 | 11.606 | 1.743 | 2.721 | 10.400 | 0.171 | 0.943 | 0.013 | 9.451 | -13.092 |
| `B53` | 0 | 0.025 | 20.994 | 0.909 | 2.506 | 11.520 | 0.107 | 0.975 | 0.016 | 19.656 | 16.116 |
| `B53` | 1 | 0.050 | 11.606 | 1.743 | 2.721 | 10.400 | 0.171 | 0.943 | 0.013 | 9.451 | -5.891 |

这组数据给出一个比 9.12 节更窄的判断：

1. 艉端第一站的 RHS 并不是由 body-normal boundary condition 主导。`RHS body ratio` 只有约 `0.107-0.256`。
2. 主导 RHS 的是 `inner_free_surface_potential`，比例约为 `0.924-0.975`。因此第一站异常更像自由面势进入 Eq. (23) 内域方程后的放大，而不是单纯的船体边界速度过大。
3. `outer_control_history` 在这两个站的 RHS 比例只有约 `0.007-0.016`，所以当前峰值不应优先归咎于 Eq. (24) 历史卷积项。
4. `B33/B53` 在第 0 站与第 1 站的 pressure-gradient density 符号相反，分别为 `+33.928 -> -13.092` 和 `+16.116 -> -5.891`。这直接解释了前面观察到的抵消和反相传播现象。

因此，下一步最具体的技术任务是：

1. 对 `inner_free_surface_potential` 进入 Eq. (23) RHS 的矩阵块 `-A_free * phi_free` 做局部块级审计，输出每个 free-surface panel 对 body/control/free 行的贡献。
2. 检查第一活动站在 bow-to-stern marching 中是否继承了不适合直接作为 physical station 的初始化自由面势。
3. 尝试引入只读的 start-up/ghost-station 候选审计：例如将第一活动站只用于初始化，不纳入整船积分，或使用前两站平滑初始化；但在通过八系数 Gate 1 前不得进入生产默认。

### 9.14 Eq. (23) 自由面 RHS 矩阵块审计

2026-08-01 继续落实 9.13 节第 1 条，把 `inner_free_surface_potential` 源项继续拆成 `-A_free * phi_free` 的行块和面元贡献。新增输出目录为：

```text
outputs/matched_bie_provider_free_rhs_block_probe/results
```

新增文件包括：

| 文件 | 内容 | 作用 |
|---|---|---|
| `ma2005_wigley_iii_coefficients_matched_inner_free_surface_rhs_blocks.csv` | 每个系数、艉端前两站、每个 Eq. (23) 行块、每个自由面面元的 `-A_free * phi_free` 贡献范数、面元势、矩阵列范数和相位对齐。 | 把“自由面势 RHS 主导”从整体范数继续拆到矩阵块和面元层。 |
| `ma2005_wigley_iii_coefficients_matched_inner_free_surface_rhs_blocks_summary.csv` | 每个系数的最大贡献站位、行块、自由面面元、贡献范数和相对总自由面 RHS 比例。 | 快速定位下一步要审计的 Eq. (23) 局部块。 |

八个系数的摘要如下。

| 系数 | 主导站 | `x/L` | 主导行块 | 主导自由面面元 | `y` | 主导贡献范数 | panel/total RHS | max row-block/total RHS |
|---|---:|---:|---|---:|---:|---:|---:|---:|
| `A33` | 1 | 0.050 | `eq23_free_surface` | 0 | -0.450 | 2.916 | 0.568 | 0.873 |
| `B33` | 1 | 0.050 | `eq23_free_surface` | 0 | -0.450 | 5.831 | 0.568 | 0.873 |
| `A35` | 1 | 0.050 | `eq23_free_surface` | 0 | -0.450 | 3.559 | 0.429 | 0.778 |
| `B35` | 0 | 0.025 | `eq23_free_surface` | 1 | -0.150 | 5.041 | 0.432 | 0.746 |
| `A53` | 1 | 0.050 | `eq23_free_surface` | 0 | -0.450 | 5.831 | 0.568 | 0.873 |
| `B53` | 1 | 0.050 | `eq23_free_surface` | 0 | -0.450 | 5.831 | 0.568 | 0.873 |
| `A55` | 1 | 0.050 | `eq23_free_surface` | 0 | -0.450 | 3.526 | 0.491 | 0.811 |
| `B55` | 1 | 0.050 | `eq23_free_surface` | 0 | -0.450 | 3.526 | 0.491 | 0.811 |

这组数据把 9.13 节的判断进一步收窄：

1. 主导贡献几乎全部落在 `eq23_free_surface` 行块，而不是 `eq23_body` 或 `eq23_inner_control` 行块。因此，当前最强 RHS 放大不是船体边界速度直接驱动，也不是控制面历史项直接驱动，而是内域自由面边界方程自身的已知势项在起始两站被放大。
2. `B33/B53` 的主导面元位于第 1 个活动站 `x/L = 0.05`、自由面外侧面元 `y = -0.45 m`，单个面元贡献已经达到总自由面 RHS 的约 `0.568`。同一面元对所在行块的贡献比例约为 `0.682`，说明主导不是许多小面元均匀累积，而是少数自由面面元贡献集中。
3. 明细表显示 `B33/B53` 在 `eq23_free_surface` 自行块中的主导面元 `matrix_column_norm = pi`。这不是随机噪声，更像简单 Green 函数边界积分在自由面自边界上的对角项、法向约定或半跳项处理进入了 RHS 放大链。
4. 这并不说明可以直接改 `inner_diagonal_sign` 或缩放 `inner_a_scale`。已有候选扫描表明，单一符号或尺度调整若不能让八个 Ma 2005 系数同时改善，就不能进入生产默认。当前结论只是把下一步的公式审计范围压缩到 Eq. (23) 自由面自边界块、自由面状态初始化和 `-A_free * phi_free` 的符号/半跳项来源。

因此，下一步最具体的技术动作是：

1. 对 `eq23_free_surface <- free_surface_potential` 自边界块单独建立半解析审计：区分非对角 Green normal-derivative 积分、对角半跳项和当前 `inner_diagonal_sign` 的贡献。
2. 做只读候选比较：`current_default`、`free_self_diagonal_removed`、`free_self_diagonal_opposite_sign`、`inner_a_normalized_by_2pi`。这些候选只能输出诊断表，不得改变生产默认。
3. 若某个候选能同时降低八个 Ma 2005 系数的 gate ratio，再追溯它是否符合 A1 Eq. (23) 的边界极限方向、法向定义和自由面 marching 变量定义；只有理论链闭合后才能转为默认实现。

### 9.15 Eq. (23) 自由面自边界候选排除

2026-08-01 继续落实 9.14 节第 2 条，新增一个默认不变的诊断参数：

```text
inner_free_surface_self_diagonal_scale = 1.0
```

该参数只作用于 Eq. (23) 中 `eq23_free_surface <- free_surface_potential` 自边界块的对角项。默认值 `1.0` 完全保持现有生产路径；诊断候选设置为 `0.0` 时表示移除自由面自对角项，设置为 `-1.0` 时表示只反转自由面自对角项。另一个候选 `inner_a_normalized_by_2pi` 通过已有 `inner_a_scale` 把内域 `A` 核整体乘以 `1/(2*pi)`。

新增输出目录为：

```text
outputs/matched_bie_provider_free_self_candidate_probe/results
```

新增文件包括：

| 文件 | 内容 | 作用 |
|---|---|---|
| `ma2005_wigley_iii_coefficients_inner_free_surface_self_block_candidate_detail.csv` | 每个 Ma 2005 系数、每个候选的计算值、参考值、raw/reference 比值、误差、gate ratio 和候选状态。 | 回答某个候选改善了哪些系数、恶化了哪些系数。 |
| `ma2005_wigley_iii_coefficients_inner_free_surface_self_block_candidate_summary.csv` | 每个候选跨八个系数的通过数、通过比例、中位 gate ratio 和最大 gate ratio。 | 防止单个系数改善被误读为整体 Gate 1 进步。 |

候选整体摘要如下。

| 候选 | pass_count | fail_count | pass_fraction | median gate ratio | max gate ratio | 状态 |
|---|---:|---:|---:|---:|---:|---|
| `current_default` | 1 | 7 | 0.125 | 36.167 | 163.904 | `FAIL` |
| `inner_a_normalized_by_2pi` | 0 | 8 | 0.000 | 179.461 | 672.097 | `FAIL` |
| `free_self_diagonal_removed` | 0 | 8 | 0.000 | 134.125 | 752.207 | `FAIL` |
| `free_self_diagonal_opposite_sign` | 0 | 8 | 0.000 | 3560.058 | 12888.346 | `FAIL` |

代表性阻尼项细节如下。

| 系数 | 候选 | 计算值 | 参考值 | raw/reference | gate ratio | 状态 |
|---|---|---:|---:|---:|---:|---|
| `B33` | `current_default` | 9.646 | 2.100 | 4.594 | 23.957 | `FAIL` |
| `B33` | `free_self_diagonal_removed` | 53.152 | 2.100 | 25.310 | 162.069 | `FAIL` |
| `B33` | `inner_a_normalized_by_2pi` | 52.372 | 2.100 | 24.939 | 159.595 | `FAIL` |
| `B35` | `current_default` | 6.522 | 0.130 | 50.171 | 163.904 | `FAIL` |
| `B35` | `free_self_diagonal_removed` | -1.902 | 0.130 | -14.633 | 52.109 | `FAIL` |
| `B35` | `inner_a_normalized_by_2pi` | 8.947 | 0.130 | 68.822 | 226.074 | `FAIL` |
| `B55` | `current_default` | 1.859 | 0.090 | 20.655 | 131.032 | `FAIL` |
| `B55` | `free_self_diagonal_removed` | -1.028 | 0.090 | -11.420 | 82.800 | `FAIL` |
| `B55` | `inner_a_normalized_by_2pi` | 0.982 | 0.090 | 10.914 | 66.091 | `FAIL` |

这组候选给出一个重要的排除结论：

1. `current_default` 仍是四个候选中整体最好的结果，但它只有 `1/8` 系数通过，最大 gate ratio 仍为 `163.904`，因此 Gate 1 继续保持 `PENDING`。
2. 移除自由面自对角项并没有消除阻尼项偏大的问题。它虽然让 `B35/B55` 的 gate ratio 相比默认下降，但同时使 `B33` 和其他系数整体恶化，八个系数无一通过。
3. 自由面自对角项单独反号会导致数量级爆炸，最大 gate ratio 达 `12888.346`，可以排除为生产候选。
4. 内域 `A` 核整体乘以 `1/(2*pi)` 也不能改善整体 Gate 1；它对 `B55` 有局部改善，但对 `B33/B35` 仍明显失败，不能作为默认尺度修正。

因此，当前不能把 Gate 1 失败简单归咎于 Eq. (23) 自由面自对角项的“有无、反号或 `2*pi` 缩放”。下一步应回到更完整的传播链：

```text
free-surface state initialization/transfer
  -> Eq. (23) known free-surface potential RHS
  -> body potential station-to-station phase jump
  -> x-gradient pressure term
  -> whole-ship A/B coefficient assembly
```

最小下一步是做 `start-up/ghost-station` 候选审计：保留默认求解器不变，分别比较“第一活动站仅用于自由面状态启动、不进入整船压力积分”和“前两活动站平滑初始化”的八系数 gate ratio。如果它们不能整体改善八个系数，也必须继续保留为 diagnostic，不得进入生产默认。

### 9.16 start-up/ghost-station 压力积分候选审计

2026-08-01 继续落实 9.15 节最后的最小下一步，新增 `start-up/ghost-station` 只读候选表。这里的候选不重新求解 BIE，也不改变自由面 marching；它只改变已经求得的站位 pressure-density 如何进入整船积分。因此候选的物理含义是：

> 第一活动站仍用于自由面状态启动、控制面历史推进和站位传播，但在整船压力积分中被视作 ghost station，不直接贡献整船 `A/B` 系数。

新增输出目录为：

```text
outputs/matched_bie_provider_startup_ghost_probe/results
```

新增文件包括：

| 文件 | 内容 | 作用 |
|---|---|---|
| `ma2005_wigley_iii_coefficients_startup_ghost_station_candidate_detail.csv` | 每个 Ma 2005 系数、每个 endpoint/ghost 候选的计算值、参考值、raw/reference、误差、gate ratio 和相对当前默认的 gate ratio 变化。 | 判断“艉端第一活动站作为启动站但不积分”是否真能整体改善八个系数。 |
| `ma2005_wigley_iii_coefficients_startup_ghost_station_candidate_summary.csv` | 每个候选跨八个系数的通过数、通过比例、中位 gate ratio、最大 gate ratio、改善/恶化行数。 | 防止只看 `B35/B55` 局部改善而误判为 Gate 1 已可接受。 |

候选整体摘要如下。

| 候选 | pass_count | fail_count | pass_fraction | median gate ratio | max gate ratio | improved rows | worsened rows | 状态 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `ghost_aft_pressure_no_end` | 0 | 8 | 0.000 | 35.177 | 128.944 | 4 | 4 | `FAIL` |
| `both_end_pressure_excluded_plus_end` | 0 | 8 | 0.000 | 35.210 | 142.986 | 4 | 4 | `FAIL` |
| `ghost_aft_forward_only_removed_keep_time_end` | 0 | 8 | 0.000 | 35.010 | 143.831 | 4 | 2 | `FAIL` |
| `ghost_aft_pressure_plus_end` | 0 | 8 | 0.000 | 35.102 | 143.894 | 4 | 4 | `FAIL` |
| `bow_pressure_excluded_plus_end` | 0 | 8 | 0.000 | 36.275 | 162.997 | 2 | 6 | `FAIL` |
| `current_default` | 1 | 7 | 0.125 | 36.167 | 163.904 | 0 | 0 | `FAIL` |
| `ghost_aft_time_only_removed_keep_forward_end` | 1 | 7 | 0.125 | 36.260 | 163.967 | 2 | 6 | `FAIL` |

代表性阻尼项细节如下。

| 系数 | 候选 | 计算值 | 参考值 | raw/reference | gate ratio | 相对默认变化 | 状态 |
|---|---|---:|---:|---:|---:|---:|---|
| `B33` | `current_default` | 9.646 | 2.100 | 4.594 | 23.957 | 0.000 | `FAIL` |
| `B33` | `ghost_aft_pressure_no_end` | 8.264 | 2.100 | 3.935 | 19.567 | -4.390 | `FAIL` |
| `B33` | `ghost_aft_forward_only_removed_keep_time_end` | 8.865 | 2.100 | 4.221 | 21.477 | -2.480 | `FAIL` |
| `B35` | `current_default` | 6.522 | 0.130 | 50.171 | 163.904 | 0.000 | `FAIL` |
| `B35` | `ghost_aft_pressure_no_end` | 5.159 | 0.130 | 39.683 | 128.944 | -34.961 | `FAIL` |
| `B35` | `ghost_aft_forward_only_removed_keep_time_end` | 5.739 | 0.130 | 44.149 | 143.831 | -20.073 | `FAIL` |
| `B55` | `current_default` | 1.859 | 0.090 | 20.655 | 131.032 | 0.000 | `FAIL` |
| `B55` | `ghost_aft_pressure_no_end` | 1.212 | 0.090 | 13.472 | 83.146 | -47.886 | `FAIL` |
| `B55` | `ghost_aft_forward_only_removed_keep_time_end` | 1.489 | 0.090 | 16.539 | 103.593 | -27.439 | `FAIL` |

这组结果给出两个并存结论：

1. 艉端第一活动站确实参与了误差放大。`ghost_aft_pressure_no_end` 把最大 gate ratio 从 `163.904` 降到 `128.944`，并显著改善 `B35/B55` 等最严重阻尼项；`ghost_aft_forward_only_removed_keep_time_end` 也能降低多个阻尼项。这与 9.12 到 9.14 中 pressure-gradient 峰值集中在艉端第一对站位的诊断一致。
2. 但 ghost-station 不是完整修正。所有 ghost 候选仍为 `FAIL`，最好的候选也没有任何系数通过；并且有些候选会使部分系数恶化。按照 Gate 1 规则，它们只能保留为 diagnostic，不能进入生产默认。

因此，当前最合理的下一步不是直接删除艉端站压力，而是解释为什么删除艉端站能降低阻尼却不能恢复正确量级。建议把下一轮焦点压缩到两项：

1. 对 `x/L = 0.025 -> 0.050` 的 body-potential x-gradient 做 start-up 差分候选审计：比较 current central gradient、first-pair one-sided smoothing、phase-aligned smoothing 和 ghost-gradient initialization。
2. 把 Eq. (30) pressure-gradient 与 Eq. (32) end contour term 的组合在艉端局部重新审计，尤其检查 `ghost_aft_pressure_no_end` 优于 `ghost_aft_pressure_plus_end` 是否说明当前 end term 与艉端压力积分存在重复或参考点不一致。

### 9.17 start-up pressure-gradient 差分候选审计

2026-08-01 继续落实 9.16 节第 1 条，新增 `start-up pressure-gradient` 只读候选表。与 9.16 的 ghost-station 候选不同，本轮候选不删除任何站位压力积分，而是在同一次 matched BIE 求解结果上，只替换 Eq. (30) 中前进速度压力项所使用的 `body_potential` 纵向梯度矩阵：

```text
matched BIE solution fixed
  + pressure time-derivative term fixed
  + end contour term fixed
  + only forward-speed pressure-gradient matrix replaced
```

因此，这一组候选的物理问题更窄：如果第一对站位 `x/L = 0.025 -> 0.050` 的相位跳变或差分格式是主要误差源，那么只替换纵向梯度估计就应当能同时改善 Ma 2005 Wigley III 的八个系数；如果只改善少数阻尼项而破坏其他项，则说明误差链还包含自由面状态传播、压力恢复符号、端部项或力矩坐标映射，不能把差分候选升为生产默认。

新增输出目录为：

```text
outputs/matched_bie_provider_startup_gradient_probe/results
```

新增文件包括：

| 文件 | 内容 | 作用 |
|---|---|---|
| `ma2005_wigley_iii_coefficients_startup_pressure_gradient_candidate_detail.csv` | 每个 Ma 2005 系数、每个梯度候选的计算值、参考值、raw/reference、误差、gate ratio、相对当前默认的 gate ratio 变化，以及时间项、梯度项和端部项的分量值。 | 判断“只替换 Eq. (30) pressure-gradient 差分”是否足以解释 Gate 1 失败。 |
| `ma2005_wigley_iii_coefficients_startup_pressure_gradient_candidate_summary.csv` | 每个候选跨八个系数的通过数、通过比例、中位 gate ratio、最大 gate ratio、改善/恶化行数和梯度分量幅值摘要。 | 防止局部改善被误认为整体 Gate 1 可接受。 |

候选整体摘要如下。

| 候选 | pass_count | fail_count | pass_fraction | median gate ratio | max gate ratio | improved rows | worsened rows | 状态 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `phase_aligned_forward` | 0 | 8 | 0.000 | 34.678 | 78.495 | 4 | 3 | `FAIL` |
| `phase_aligned_central` | 0 | 8 | 0.000 | 55.647 | 110.057 | 4 | 3 | `FAIL` |
| `phase_aligned_backward` | 0 | 8 | 0.000 | 69.193 | 136.011 | 4 | 3 | `FAIL` |
| `scheme_forward` | 0 | 8 | 0.000 | 34.709 | 136.888 | 4 | 2 | `FAIL` |
| `startup_aft_gradient_zero` | 0 | 8 | 0.000 | 34.283 | 145.299 | 4 | 2 | `FAIL` |
| `startup_aft_gradient_copy_second` | 0 | 8 | 0.000 | 36.310 | 145.999 | 4 | 2 | `FAIL` |
| `current_default` | 1 | 7 | 0.125 | 36.167 | 163.904 | 2 | 2 | `FAIL` |
| `scheme_central` | 1 | 7 | 0.125 | 36.167 | 163.904 | 2 | 2 | `FAIL` |
| `scheme_backward` | 0 | 8 | 0.000 | 35.603 | 171.183 | 2 | 4 | `FAIL` |
| `startup_first_pair_gradient_average` | 0 | 8 | 0.000 | 44.148 | 189.788 | 0 | 6 | `FAIL` |

代表性阻尼项细节如下。

| 系数 | 候选 | 计算值 | 参考值 | raw/reference | gate ratio | 相对默认变化 | 状态 |
|---|---|---:|---:|---:|---:|---:|---|
| `B33` | `current_default` | 9.646 | 2.100 | 4.594 | 23.957 | 0.000 | `FAIL` |
| `B33` | `scheme_forward` | 8.662 | 2.100 | 4.125 | 20.831 | -3.126 | `FAIL` |
| `B33` | `phase_aligned_forward` | -8.274 | 2.100 | -3.940 | 32.934 | +8.977 | `FAIL` |
| `B33` | `startup_aft_gradient_zero` | 8.374 | 2.100 | 3.988 | 19.918 | -4.039 | `FAIL` |
| `B33` | `startup_aft_gradient_copy_second` | 8.119 | 2.100 | 3.866 | 19.107 | -4.850 | `FAIL` |
| `B35` | `current_default` | 6.522 | 0.130 | 50.171 | 163.904 | 0.000 | `FAIL` |
| `B35` | `scheme_forward` | 5.469 | 0.130 | 42.066 | 136.888 | -27.016 | `FAIL` |
| `B35` | `phase_aligned_forward` | 3.176 | 0.130 | 24.428 | 78.094 | -85.811 | `FAIL` |
| `B35` | `startup_aft_gradient_zero` | 5.797 | 0.130 | 44.590 | 145.299 | -18.605 | `FAIL` |
| `B35` | `startup_aft_gradient_copy_second` | 5.824 | 0.130 | 44.800 | 145.999 | -17.906 | `FAIL` |
| `B55` | `current_default` | 1.859 | 0.090 | 20.655 | 131.032 | 0.000 | `FAIL` |
| `B55` | `scheme_forward` | 1.415 | 0.090 | 15.723 | 98.152 | -32.880 | `FAIL` |
| `B55` | `phase_aligned_forward` | 1.150 | 0.090 | 12.774 | 78.495 | -52.537 | `FAIL` |
| `B55` | `startup_aft_gradient_zero` | 1.514 | 0.090 | 16.825 | 105.501 | -25.531 | `FAIL` |
| `B55` | `startup_aft_gradient_copy_second` | 1.527 | 0.090 | 16.969 | 106.461 | -24.571 | `FAIL` |

这组结果给出更精确的判断：

1. `phase_aligned_forward` 是本轮候选中最大 gate ratio 最低的一项，把最坏误差从 `163.904` 降到 `78.495`，说明相邻站相位跳变和 one-sided 差分确实参与了 pressure-gradient 误差放大。
2. 但 `phase_aligned_forward` 仍然 `0/8` 通过，并且有 3 个系数相对当前默认恶化。尤其 `B33` 从 `9.646` 变为 `-8.274`，虽然 `B35/B55` 明显改善，但 `B33` 的符号和量级被破坏。这说明不能把“相位对齐 + forward gradient”作为生产默认。
3. `scheme_forward`、`startup_aft_gradient_zero` 和 `startup_aft_gradient_copy_second` 都能改善 `B33/B35/B55`，但改善幅度不足，且八个系数仍全部或几乎全部失败。它们支持“艉端 start-up 差分存在问题”的判断，但不构成完整修正。
4. `startup_first_pair_gradient_average` 最差，最大 gate ratio 进一步升到 `189.788`，说明简单平均前两站梯度会破坏原本的站位相位/幅值结构，可以排除为默认候选。
5. `current_default` 与 `scheme_central` 完全一致，证明生产默认当前使用的就是 central x-gradient；新增候选表没有改变生产结果，只是把替代梯度路径显式量化。

因此，Gate 1 继续保持 `PENDING`。本轮可确认的进展不是通过验收，而是把失败链路从“压力梯度过大”进一步收窄为：

```text
first active station free-surface RHS
  -> adjacent-station body-potential phase jump
  -> central/one-sided x-gradient sensitivity
  -> damping terms B35/B55 over-prediction
  -> B33 and pitch-coupled terms still require additional sign/scale/coordinate audit
```

下一步最具体的技术动作应是：

1. 对 `phase_aligned_forward` 做局部闭合审计：逐站输出它相对于 current central gradient 的梯度相位、梯度幅值、压力分量和积分分量，检查为何 `B35/B55` 改善而 `B33` 恶化。
2. 将 Eq. (30) pressure-gradient 与 Eq. (32) end contour term 联合审计，而不是单独替换一个差分格式；9.16 已显示 `ghost_aft_pressure_no_end` 优于保留 end term 的候选，提示端部项与艉端压力积分可能存在参考点或重复计入问题。
3. 单独审计 pitch generalized force row 的 `N5/m5` 坐标映射，因为 `A35/B35/A55/B55` 对力矩臂、纵向原点和正号约定极敏感，单靠梯度平滑无法解决。

### 9.18 pressure-gradient 候选逐站局部闭合审计

2026-08-01 继续落实 9.17 节最后的第 1 条，新增 station-level closure 表。上一节已经知道 `phase_aligned_forward` 可以把最大 gate ratio 从 `163.904` 降到 `78.495`，但仍然 `0/8` 通过，并且会使部分系数恶化。本节的目的不是再比较整船结果，而是回答更细的问题：

> `phase_aligned_forward` 到底在哪些站位改变了 pressure-gradient force density？它改善 `B35/B55` 和恶化 `B33` 是否来自同一个局部艉端问题？

新增输出目录为：

```text
outputs/matched_bie_provider_gradient_station_probe/results
```

新增文件包括：

| 文件 | 内容 | 作用 |
|---|---|---|
| `ma2005_wigley_iii_coefficients_startup_pressure_gradient_candidate_station_detail.csv` | 每个 Ma 2005 系数、每个 pressure-gradient 候选、每个站位的 `x/L`、梯度项 force density、梯度范数、峰值面元相位、梯形积分权重和相对 current default 的局部变化。 | 逐站解释某个候选为何改善或恶化整船系数。 |
| `ma2005_wigley_iii_coefficients_startup_pressure_gradient_candidate_station_summary.csv` | 每个系数和候选的整船 forward-gradient 积分变化、主导变化站位、主导变化占总绝对变化比例、最大梯度范数比和最大相位变化。 | 快速定位候选变化是局部艉端效应，还是全船分布式相位翻转。 |

`validation_summary.csv` 中本轮 station-level 总览为：

```text
largest_delta_candidate = phase_aligned_backward
coefficient             = B33
station                 = 2
x/L                     = 0.075
station_delta           = 5.465
share                   = 0.132
max_phase_delta         = 180 deg
```

这个总览说明，最大的单站变化并不只发生在第一个艉端活动站，而是已经向第二、第三个站位扩展。更重要的是，`share = 0.132` 表明最大单站变化只占该候选总绝对变化的约 `13.2%`，也就是说候选影响不是一个点状修正，而是较强的分布式相位/梯度重排。

`phase_aligned_forward` 在三个代表性阻尼项上的整船 pressure-gradient 积分变化如下。

| 系数 | current forward-gradient 积分 | candidate forward-gradient 积分 | 总变化 | 主导变化站 | 主导 `x/L` | 主导变化 | 主导变化占比 | 最大相位变化 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `B33` | 9.045 | -8.876 | -17.921 | 1 | 0.050 | +3.334 | 0.096 | 180.000 |
| `B35` | 1.823 | -1.523 | -3.347 | 3 | 0.100 | -0.854 | 0.187 | 178.348 |
| `B55` | 1.004 | 0.295 | -0.709 | 1 | 0.050 | +0.332 | 0.199 | 177.994 |

这张表解释了为什么 `phase_aligned_forward` 不能作为默认修正：

1. 对 `B35/B55` 来说，当前默认的 pressure-gradient 积分是明显偏大的正贡献，`phase_aligned_forward` 把它显著压低，所以 gate ratio 降低。
2. 但对 `B33` 来说，候选把 forward-gradient 积分从 `+9.045` 直接变成 `-8.876`，已经不是适度修正，而是近似全局翻转。这会让 `B33` 符号和量级都偏离文献结果。
3. `B33` 的主导变化站虽然是 `x/L = 0.050`，但主导变化占总绝对变化只有约 `9.6%`。这说明 `B33` 恶化不是单站尖峰导致，而是多个站位的相位翻转共同累积。
4. 三个代表系数的最大相位变化都接近 `180 deg`。这与 9.12 节相邻站相位跳变诊断一致，但也说明“相位对齐”本身不是物理闭合修正；它可能在某些耦合阻尼项上抵消过大贡献，却同时破坏直接升沉阻尼。

前六个站位的 `B33` 明细进一步说明这种分布式相位翻转：

| station | `x/L` | current density | candidate density | station integral delta | current gradient norm | candidate gradient norm | norm ratio | phase delta |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0.025 | 33.928 | 13.557 | -0.764 | 687.784 | 296.109 | 0.431 | 0.000 |
| 1 | 0.050 | -13.092 | 31.362 | +3.334 | 182.806 | 344.560 | 1.885 | -180.000 |
| 2 | 0.075 | -27.123 | -21.811 | +0.398 | 197.464 | 163.656 | 0.829 | 0.000 |
| 3 | 0.100 | 14.640 | -1.374 | -1.201 | 88.787 | 21.692 | 0.244 | -180.000 |
| 4 | 0.125 | -0.634 | 2.839 | +0.261 | 19.549 | 22.664 | 1.159 | -180.000 |
| 5 | 0.150 | -4.156 | 4.942 | +0.682 | 25.016 | 27.597 | 1.103 | -180.000 |

这说明 `B33` 并非只受第一活动站影响。`phase_aligned_forward` 在第 1、3、4、5 站都出现接近 `180 deg` 的局部相位变化，导致整船积分出现大范围符号重排。换句话说，它揭示了 current central gradient 的相位问题，但它自己并不是物理修正。

相比之下，`startup_aft_gradient_zero` 和 `startup_aft_gradient_copy_second` 的变化是严格局部的：

| 系数 | 候选 | 总变化 | 主导站 | 主导 `x/L` | 主导变化占比 | 最大相位变化 |
|---|---|---:|---:|---:|---:|---:|
| `B33` | `startup_aft_gradient_zero` | -1.272 | 0 | 0.025 | 1.000 | 90.000 |
| `B35` | `startup_aft_gradient_zero` | -0.726 | 0 | 0.025 | 1.000 | 78.257 |
| `B55` | `startup_aft_gradient_zero` | -0.345 | 0 | 0.025 | 1.000 | 62.539 |
| `B33` | `startup_aft_gradient_copy_second` | -1.528 | 0 | 0.025 | 1.000 | 180.000 |
| `B35` | `startup_aft_gradient_copy_second` | -0.698 | 0 | 0.025 | 1.000 | 10.382 |
| `B55` | `startup_aft_gradient_copy_second` | -0.332 | 0 | 0.025 | 1.000 | 156.449 |

这组对照很关键：

1. 如果只改第一活动站，影响确实集中在 `x/L = 0.025`，而且对 `B33/B35/B55` 都是降低 forward-gradient 积分。
2. 但只改第一活动站的幅度不够，无法把 `B35/B55` 从几十倍误差拉回 Gate 1。
3. 如果采用 `phase_aligned_forward`，幅度足够大，但它不再是局部艉端修正，而是全船多个站位的相位重排；这种做法缺少明确的 Ma--Duan--Song 方程来源，不能进入生产默认。

因此，当前最可靠的结论是：

```text
第一活动站 start-up 问题存在，但不是唯一误差源；
station-to-station phase jump 问题存在，但直接 phase-align 会破坏 B33；
Gate 1 的下一步必须联合审计 pressure-gradient、end contour term 和 pitch/generalized-force 坐标映射。
```

下一步技术动作应改为两个并行审计：

1. **Eq. (30) + Eq. (32) 局部端部闭合**：对 `x/L = 0.025` 附近同时输出 pressure-gradient station integral、end contour contribution、二者合计和 `ghost_aft_pressure_no_end / ghost_aft_pressure_plus_end` 差异，判断 end term 是否与艉端压力积分存在重复或参考点不一致。
2. **pitch row 坐标映射审计**：对 `A35/B35/A55/B55` 输出 `N3`、`N5`、lever arm、`m5` 正负号、纵向原点和 Ma 2005 无量纲化之间的关系。`B35/B55` 对力矩臂和相位最敏感，只有把这一路闭合，才能判断 pressure-gradient 的剩余误差是不是由力矩坐标造成。

### 9.19 Eq. (30) pressure-gradient 与 Eq. (32) end contour / pitch row 坐标联合审计

2026-08-01 继续落实 9.18 节最后提出的两个并行审计。本轮没有改变默认求解结果，而是新增两类只读诊断：

1. `matched_end_pressure_closure`：把 Eq. (30) 的 endpoint pressure-gradient station integral 与 Eq. (32) 的 end contour term 放在同一张表里，看二者是抵消、同号叠加，还是数量级不相关。
2. `pitch_row_coordinate_audit`：逐站输出 pitch 模态的 lever arm、`N5` 对应的 oscillatory body condition、`m5` 对应的 forward-speed body condition，以及 pitch pressure-gradient force density。

新增输出目录为：

```text
outputs/matched_bie_provider_end_pitch_probe/results
```

新增文件包括：

| 文件 | 内容 | 作用 |
|---|---|---|
| `ma2005_wigley_iii_coefficients_matched_end_pressure_closure_detail.csv` | 每个系数、配置端点/艉端/艏端的 pressure-gradient 站位积分、time-pressure 站位积分、end term、端部力矩臂和二者组合。 | 检查 Eq. (30) endpoint pressure 与 Eq. (32) end contour 是否存在同号叠加、抵消或参考面不一致。 |
| `ma2005_wigley_iii_coefficients_matched_end_pressure_closure_summary.csv` | 每个系数的配置端点摘要，包含 endpoint forward integral、end term、`|end/forward|` 和 lever delta。 | 快速判断 end term 相对艉端 pressure-gradient 的量级。 |
| `ma2005_wigley_iii_coefficients_pitch_row_coordinate_audit_detail.csv` | 每个 pitch 相关系数、每个站位的 base lever、radiation lever、moment lever、pitch forward/oscillation body-condition 比值、相位和 pressure-gradient density。 | 检查 `N5/m5` 坐标映射是否内部一致，以及 pitch forward-speed body condition 是否过强。 |
| `ma2005_wigley_iii_coefficients_pitch_row_coordinate_audit_summary.csv` | 每个 pitch 相关系数的最大 forward/oscillation 比值、主导 pressure-gradient 站位、主导站 lever arm 和 lever ratio。 | 快速定位 pitch 相关误差是否集中在艉端与大 lever arm 区。 |

端部闭合摘要如下。

| 系数 | 配置端点 `x/L` | endpoint forward integral | endpoint pressure integral | end term | `|end/forward|` | `|end/pressure|` | endpoint forward + end | lever delta |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `A33` | 0.025 | 0.000 | 0.019 | 0.000 | 待补充 | 0.000 | 0.000 | 0.000 |
| `B33` | 0.025 | 1.272 | 1.272 | 0.601 | 0.473 | 0.473 | 1.874 | 0.000 |
| `A35` | 0.025 | -0.226 | -0.208 | -0.107 | 0.473 | 0.514 | -0.333 | 0.000 |
| `B35` | 0.025 | 0.726 | 0.733 | 0.583 | 0.804 | 0.795 | 1.309 | 0.000 |
| `A53` | 0.025 | 0.000 | 0.009 | 0.000 | 待补充 | 0.000 | 0.000 | 0.000 |
| `B53` | 0.025 | 0.604 | 0.604 | 0.286 | 0.473 | 0.473 | 0.890 | 0.000 |
| `A55` | 0.025 | -0.242 | -0.233 | -0.114 | 0.473 | 0.490 | -0.356 | 0.000 |
| `B55` | 0.025 | 0.345 | 0.348 | 0.277 | 0.804 | 0.795 | 0.622 | 0.000 |

这张表有三个关键含义：

1. 当前 end term 使用的端点确实是艉端第一活动站 `x/L = 0.025`，且 `end_lever_minus_station_moment_lever = 0`。也就是说，本轮没有发现“end term 使用的 lever arm 与 pressure row 不一致”的内部错误。
2. 对 `B35/B55`，end term 与 endpoint forward-gradient integral 同号叠加，而且量级分别达到 endpoint forward 的约 `80.4%`。这解释了为什么 9.16 中 `ghost_aft_pressure_no_end` 明显优于保留 end term 的候选：端部项不是在抵消过大的艉端 pressure-gradient，而是在继续放大。
3. 对 `B53`，全船层面当前结果通过依赖的是 pressure-gradient 与 end term 的抵消结构。comparison 表显示 `B53` 的 pressure-gradient component 为 `-0.380`，end term 为 `+0.286`，合计后得到 `-0.094`，接近参考 `-0.100`。这再次说明 `B53 PASS` 不能被解释为模型已正确，而应视为局部抵消。

为了把端部效应和整船误差联系起来，本轮同时读取 comparison 表中的总分量：

| 系数 | reference | computed | pressure-gradient component | end term | time + pressure-gradient | time + pressure-gradient + end | gate ratio | 状态 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `B33` | 2.100 | 9.646 | 9.045 | 0.601 | 9.045 | 9.646 | 23.957 | `FAIL` |
| `B35` | 0.130 | 6.522 | 1.823 | 0.583 | 5.939 | 6.522 | 163.904 | `FAIL` |
| `B53` | -0.100 | -0.094 | -0.380 | 0.286 | -0.380 | -0.094 | 0.190 | `PASS` |
| `B55` | 0.090 | 1.859 | 1.004 | 0.277 | 1.582 | 1.859 | 131.032 | `FAIL` |

这说明 end term 的问题不是“整体偏大或整体偏小”这么简单，而是和系数方向耦合：

1. 对 `B33/B35/B55`，end term 把已经偏大的正阻尼继续抬高。
2. 对 `B53`，end term 把负 pressure-gradient 拉回参考附近，形成了看似通过的抵消。
3. 因此，不能简单删除、翻转或缩放 end term。下一步必须回到 Eq. (32) 中 `C_A` 端部轮廓方向、端部法向、前进方向和坐标原点的定义，确认当前 `-rho U integral_CA(phi_j N_i dl)` 的方向是否与 Ma 2005 参考曲线一致。

pitch row 坐标审计摘要如下。

| 系数 | max forward/oscillation | median forward/oscillation | max phase | 主导 pressure-gradient 站 | 主导 `x/L` | 主导 pressure-gradient abs | 主导站 base lever | 主导站 moment lever | lever ratio range |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `A35` | 10.667 | 1.067 | 90.000 | 0 | 0.025 | 6.032 | 1.425 | 1.425 | 1.000--1.000 |
| `B35` | 6.400 | 0.640 | 90.000 | 0 | 0.025 | 19.350 | 1.425 | 1.425 | 1.000--1.000 |
| `A53` | 8.000 | 0.800 | 90.000 | 0 | 0.025 | 0.000 | 1.425 | 1.425 | 1.000--1.000 |
| `B53` | 8.000 | 0.800 | 90.000 | 0 | 0.025 | 16.116 | 1.425 | 1.425 | 1.000--1.000 |
| `A55` | 16.000 | 1.600 | 90.000 | 0 | 0.025 | 6.446 | 1.425 | 1.425 | 1.000--1.000 |
| `B55` | 16.000 | 1.600 | 90.000 | 0 | 0.025 | 9.191 | 1.425 | 1.425 | 1.000--1.000 |

这个结果给出两个并行结论：

1. `moment_radiation_lever_ratio` 全部为 `1.0`，说明当前代码中 pitch radiation lever 和 pitch pressure moment lever 是内部一致的；也就是说，当前没有发现“求解 pitch 模态用一个 lever，积分 pitch moment 用另一个 lever”的错误。
2. pitch forward-speed body condition 相对 oscillatory pitch condition 非常强，`A55/B55` 的最大比值达到 `16.0`，并且主导 pressure-gradient 站位仍是艉端第一活动站 `x/L = 0.025`。这说明 pitch 模态误差不只是 pressure integration 的后处理问题，pitch 边界条件中的 `U m5` 通道本身也可能在高速/低遭遇频率组合下显著放大。

前六个站位的局部明细可以进一步说明 pitch 通道的趋势。以 `B55` 为例：

| station | `x/L` | base lever | oscillation norm | forward-speed norm | forward/oscillation | phase | pressure-gradient density | Stokes body density |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0.025 | 1.425 | 0.647 | 0.545 | 0.842 | -90.000 | 9.191 | -0.194 |
| 1 | 0.050 | 1.350 | 1.177 | 1.046 | 0.889 | -90.000 | 0.687 | 0.108 |
| 2 | 0.075 | 1.275 | 1.586 | 1.493 | 0.941 | -90.000 | -2.861 | -0.445 |
| 3 | 0.100 | 1.200 | 1.884 | 1.884 | 1.000 | -90.000 | 3.483 | -0.236 |
| 4 | 0.125 | 1.125 | 2.084 | 2.223 | 1.067 | -90.000 | 1.484 | -0.167 |
| 5 | 0.150 | 1.050 | 2.200 | 2.514 | 1.143 | -90.000 | 1.168 | -0.102 |

这说明 `m5` forward-speed 通道与 oscillatory `N5` 通道大体保持 `-90 deg` 相位差，并且沿船长方向逐渐增强。由于主导 pressure-gradient density 仍集中在艉端第一站，当前误差可能来自两层叠加：

```text
pitch body condition U*m5 channel is strong
  -> first active station/free-surface start-up amplifies body potential
  -> Eq. (30) pressure-gradient over-predicts damping
  -> Eq. (32) end contour term can either amplify B35/B55 or cancel B53
```

因此，本轮把下一步目标进一步压实为：

1. 对 Eq. (32) end contour term 单独建立方向候选审计，但候选必须同时比较 `B33/B35/B53/B55`，不能因为 `B35/B55` 改善就采用。
2. 对 pitch body condition 拆分求解做只读候选：`pitch_oscillation_only`、`pitch_forward_only`、`pitch_oscillation_plus_forward_current`。这不是为了改默认，而是判断 `U*m5` 是在 BIE 求解阶段放大，还是只在压力恢复阶段放大。
3. 把 `C_A` 端部轮廓方向、船体法向方向、`x` 正方向和 Ma 2005 图中 pitch 正方向集中整理成一张符号表。只有符号表闭合后，才允许提出生产默认修正。

### 9.20 Eq. (32) end contour term 方向/尺度候选排除

2026-08-01 继续落实 9.19 节第 1 条，新增 Eq. (32) end contour term 的只读候选表。本轮候选不重新求解 BIE，不改变 Eq. (30) pressure time/gradient，也不改变 station sweep，只改变整船系数装配中 end contour term 的后处理组合：

```text
candidate = Eq.30(time + pressure-gradient) + scale * Eq.32(end contour)
```

候选包括：

| 候选 | end scale | 物理解释 |
|---|---:|---|
| `current_default` | 1.0 | 当前默认端部项。 |
| `end_removed` | 0.0 | 删除端部项，只保留 Eq. (30) pressure result。 |
| `end_flipped` | -1.0 | 仅翻转端部项符号，用于诊断端部轮廓方向或法向约定。 |
| `end_half_scale` | 0.5 | 端部项半权，用于诊断端点梯形权重或半跳项问题。 |
| `end_double_scale` | 2.0 | 端部项双倍，用于诊断是否遗漏成对端部轮廓。 |

新增输出目录为：

```text
outputs/matched_bie_provider_end_candidate_probe/results
```

新增文件包括：

| 文件 | 内容 | 作用 |
|---|---|---|
| `ma2005_wigley_iii_coefficients_end_contour_term_candidate_detail.csv` | 每个 Ma 2005 系数、每个 end term 候选的计算值、参考值、base pressure result、end term 分量、误差和 gate ratio。 | 判断端部项删除、翻转或缩放对每个系数的影响。 |
| `ma2005_wigley_iii_coefficients_end_contour_term_candidate_summary.csv` | 每个候选跨八个系数的通过数、通过比例、中位 gate ratio、最大 gate ratio、改善/恶化行数。 | 判断某个端部候选是否有资格进入生产默认。 |

候选整体摘要如下。

| 候选 | end scale | pass_count | fail_count | pass_fraction | median gate ratio | max gate ratio | improved rows | worsened rows | 状态 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `end_flipped` | -1.0 | 0 | 8 | 0.000 | 34.386 | 134.005 | 4 | 2 | `FAIL` |
| `end_removed` | 0.0 | 0 | 8 | 0.000 | 35.276 | 148.955 | 4 | 2 | `FAIL` |
| `end_half_scale` | 0.5 | 0 | 8 | 0.000 | 35.722 | 156.430 | 4 | 2 | `FAIL` |
| `current_default` | 1.0 | 1 | 7 | 0.125 | 36.167 | 163.904 | 3 | 3 | `FAIL` |
| `end_double_scale` | 2.0 | 0 | 8 | 0.000 | 37.058 | 178.854 | 0 | 6 | `FAIL` |

代表性阻尼项细节如下。

| 系数 | 候选 | reference | computed | base pressure result | end term | gate ratio | 相对默认变化 | 状态 |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `B33` | `current_default` | 2.100 | 9.646 | 9.045 | 0.601 | 23.957 | 0.000 | `FAIL` |
| `B33` | `end_removed` | 2.100 | 9.045 | 9.045 | 0.601 | 22.048 | -1.909 | `FAIL` |
| `B33` | `end_flipped` | 2.100 | 8.444 | 9.045 | 0.601 | 20.139 | -3.818 | `FAIL` |
| `B35` | `current_default` | 0.130 | 6.522 | 5.939 | 0.583 | 163.904 | 0.000 | `FAIL` |
| `B35` | `end_removed` | 0.130 | 5.939 | 5.939 | 0.583 | 148.955 | -14.950 | `FAIL` |
| `B35` | `end_flipped` | 0.130 | 5.356 | 5.939 | 0.583 | 134.005 | -29.899 | `FAIL` |
| `B53` | `current_default` | -0.100 | -0.094 | -0.380 | 0.286 | 0.190 | 0.000 | `PASS` |
| `B53` | `end_removed` | -0.100 | -0.380 | -0.380 | 0.286 | 9.333 | +9.143 | `FAIL` |
| `B53` | `end_flipped` | -0.100 | -0.666 | -0.380 | 0.286 | 18.855 | +18.665 | `FAIL` |
| `B55` | `current_default` | 0.090 | 1.859 | 1.582 | 0.277 | 131.032 | 0.000 | `FAIL` |
| `B55` | `end_removed` | 0.090 | 1.582 | 1.582 | 0.277 | 110.518 | -20.514 | `FAIL` |
| `B55` | `end_flipped` | 0.090 | 1.305 | 1.582 | 0.277 | 90.003 | -41.029 | `FAIL` |

这组候选给出明确排除结论：

1. `end_flipped` 是本轮最大 gate ratio 最低的候选，说明 Eq. (32) end contour term 的方向/符号确实值得继续审计。
2. 但 `end_flipped` 仍然 `0/8` 通过，最大 gate ratio 仍为 `134.005`，不能进入生产默认。
3. 删除端部项或半权端部项同样不能通过 Gate 1。它们会改善 `B33/B35/B55`，但幅度远远不够。
4. 当前 `B53` 的唯一通过被端部项候选破坏：`current_default` 通过来自 `base pressure = -0.380` 与 `end term = +0.286` 的抵消；一旦删除或翻转 end term，`B53` 立即失败。因此 `B53 PASS` 再次被确认是抵消现象，而不是整条公式链正确。
5. `end_double_scale` 全面恶化，说明“缺少双倍端部项”可以排除。

因此，端部项不能靠经验 scale 修正。下一步不应继续扫描 `end_term_scale`，而应进入更根本的符号闭合：

```text
C_A contour orientation
  -> outward normal on end contour
  -> x coordinate and pitch positive direction
  -> package N5 = lever*(-normal_z)
  -> Eq.32 sign -rho*U*int_CA(phi_j*N_i dl)
  -> Ma 2005 coefficient sign convention
```

同时，pitch body condition 的拆分求解仍然是必要下一步。因为 9.19 已显示 pitch `U*m5` 通道相对振荡通道可达到 `16` 倍，end term 候选只能解释后处理端部项，不能解释 BIE 求解阶段的 pitch body potential 放大。

### 9.21 pitch body condition 拆分求解候选排除

2026-08-01 继续落实 9.19 节第 2 条，新增 pitch radiation body condition 的只读拆分求解候选。本轮与 9.20 不同：9.20 只改变已求解结果的端部项后处理；本节候选会重新进入 matched BIE station sweep，分别控制纵摇边界条件中的两个输入通道：

```text
pitch body normal velocity = scale_osc * (i*omega*N5) + scale_fwd * (U*m5)
```

其中，`i*omega*N5` 是单位纵摇位移在频域中产生的振荡法向速度项，`U*m5` 是前进速度与纵摇几何导数相乘得到的 Stokes body forward-speed 项。拆分这两个通道的目的不是把某一个经验组合调成默认，而是回答一个更具体的问题：当前 `B35/B55` 的过大值，到底主要来自 BIE 求解阶段的 pitch radiation body potential 放大，还是来自 Eq. (30) 压力恢复时的前进速度梯度放大。

新增输出目录为：

```text
outputs/matched_bie_provider_pitch_split_probe/results
```

新增文件包括：

| 文件 | 内容 | 作用 |
|---|---|---|
| `ma2005_wigley_iii_coefficients_pitch_body_condition_split_candidate_detail.csv` | 每个 Ma 2005 系数、每个 pitch body-condition 候选的参考值、计算值、误差、gate ratio、是否影响 pitch radiation 列、是否重新求解 BIE。 | 判断关闭或保留某一条 pitch body-condition 通道后，哪些系数改善、哪些系数恶化。 |
| `ma2005_wigley_iii_coefficients_pitch_body_condition_split_candidate_summary.csv` | 每个候选跨八个系数的通过数、通过比例、中位 gate ratio、最大 gate ratio、改善/恶化行数。 | 判断某个 pitch body-condition 候选是否有资格进入生产默认。 |

候选整体摘要如下。

| 候选 | oscillation scale | forward-speed scale | affected rows | pass_count | pass_fraction | median gate ratio | max gate ratio | improved rows | worsened rows | 状态 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `pitch_body_condition_zero` | 0.0 | 0.0 | 4 | 1 | 0.125 | 6.667 | 61.933 | 3 | 1 | `FAIL` |
| `pitch_oscillation_only` | 1.0 | 0.0 | 4 | 1 | 0.125 | 26.364 | 88.225 | 4 | 0 | `FAIL` |
| `pitch_forward_only` | 0.0 | 1.0 | 4 | 1 | 0.125 | 27.010 | 102.205 | 4 | 0 | `FAIL` |
| `current_combined` | 1.0 | 1.0 | 4 | 1 | 0.125 | 36.167 | 163.904 | 0 | 0 | `FAIL` |

pitch radiation 列的代表性细节如下。

| 系数 | 候选 | reference | computed | gate ratio | 相对默认变化 | 状态 |
|---|---|---:|---:|---:|---:|---|
| `A35` | `current_combined` | -0.200 | -2.814 | 43.563 | 0.000 | `FAIL` |
| `A35` | `pitch_oscillation_only` | -0.200 | -1.099 | 14.981 | -28.582 | `FAIL` |
| `A35` | `pitch_forward_only` | -0.200 | -1.715 | 25.249 | -18.314 | `FAIL` |
| `A35` | `pitch_body_condition_zero` | -0.200 | 0.000 | 3.333 | -40.230 | `FAIL` |
| `B35` | `current_combined` | 0.130 | 6.522 | 163.904 | 0.000 | `FAIL` |
| `B35` | `pitch_oscillation_only` | 0.130 | 2.406 | 58.366 | -105.538 | `FAIL` |
| `B35` | `pitch_forward_only` | 0.130 | 4.116 | 102.205 | -61.699 | `FAIL` |
| `B35` | `pitch_body_condition_zero` | 0.130 | 0.000 | 3.333 | -160.571 | `FAIL` |
| `A55` | `current_combined` | 0.063 | 0.090 | 2.865 | 0.000 | `FAIL` |
| `A55` | `pitch_oscillation_only` | 0.063 | 0.052 | 1.127 | -1.739 | `FAIL` |
| `A55` | `pitch_forward_only` | 0.063 | 0.038 | 2.675 | -0.191 | `FAIL` |
| `A55` | `pitch_body_condition_zero` | 0.063 | 0.000 | 6.667 | +3.801 | `FAIL` |
| `B55` | `current_combined` | 0.090 | 1.859 | 131.032 | 0.000 | `FAIL` |
| `B55` | `pitch_oscillation_only` | 0.090 | 1.281 | 88.225 | -42.807 | `FAIL` |
| `B55` | `pitch_forward_only` | 0.090 | 0.578 | 36.140 | -94.892 | `FAIL` |
| `B55` | `pitch_body_condition_zero` | 0.090 | 0.000 | 6.667 | -124.365 | `FAIL` |

这组候选给出三个明确结论：

1. pitch body condition 的两个通道都参与了误差放大。`pitch_oscillation_only` 和 `pitch_forward_only` 都能改善 pitch radiation 列，但任何一个单独通道都不能让 `A35/B35/A55/B55` 通过 Gate 1。
2. `pitch_body_condition_zero` 的最大 gate ratio 最低，是因为 pitch radiation 列被人为压成零；它仍然不能通过 Gate 1，并且会让 `A55` 比当前默认更差。因此它只是数值通道 sanity check，不是物理候选。
3. 即使完全关闭 pitch radiation body condition，`A33/B33/A53/B53` 仍不受影响；其中 `A33/B33/A53` 仍然失败。这证明 Gate 1 不是单一 pitch body-condition 问题，还必须继续检查 heave radiation、自身压力恢复和无量纲/坐标闭合。

因此，本轮排除结论是：不得把 `pitch_oscillation_only`、`pitch_forward_only` 或 `pitch_body_condition_zero` 作为生产默认。它们的价值在于缩小误差来源：`B35/B55` 的过大值确实与 pitch radiation column 的 BIE 求解输入有关，但 `A33/B33` 的大误差说明当前 matched BIE 的主体压力链仍有更基础的问题。下一步应把排查重点转回：

```text
heave radiation column
  -> inner free-surface normal derivative scale/phase
  -> propagated free-surface potential
  -> Eq.30 pressure time derivative and pressure-gradient recovery
  -> Ma 2005 normalization and coordinate sign closure
```

本节配套测试：

```text
python -m pytest -q tests/test_validation.py -k "matched_bie_provider_model or pitch_coordinate_audit"
python -m pytest -q tests/test_unified_architecture.py -k "matched_sweep or linear_frequency_provider_routes"
```

两组定向测试均已通过。真实 probe 命令：

```text
python -m planing_seakeeping validate --benchmark all --out outputs\matched_bie_provider_pitch_split_probe\results --reference-root outputs\matched_bie_provider_gate_probe\reference --ma-hydro-model matched_bie_provider --ma-bem-free-surface-panels 4 --ma-bem-body-panels 8
```

该命令输出 `Hard failures: 15; checks pending reference data: 8`，Gate 1 仍为 `PENDING`。

### 9.22 free-surface marching 路径候选排除

2026-08-01 继续沿 9.21 的结论，把排查重点转向 `A33/B33` 所在的 heave radiation column 和自由面状态传播路径。本轮新增 free-surface marching 只读候选。与 9.20 的端部项后处理不同，也与 9.21 的 pitch body condition 拆分不同，本轮候选会重新求解 matched BIE station sweep，并只改变下面两类量：

```text
inner free-surface state marching:
  phi_free(x_k) and eta_free(x_k) propagated station-to-station

outer control history RHS:
  transient control-surface history contribution used in Eq.24 matching
```

候选包括：

| 候选 | use marching | free-surface velocity scale | history RHS scale | 物理解释 |
|---|---|---:|---:|---|
| `current_marching` | true | 1.0 | 1.0 | 当前默认：自由面状态沿站位传播，外域历史 RHS 正常参与。 |
| `free_surface_marching_disabled` | false | 1.0 | 1.0 | 每个站位的内域自由面势/高程置零，但仍保留外域控制面历史。 |
| `free_surface_velocity_zero` | true | 0.0 | 1.0 | marching 机制仍在，但 BIE 得到的自由面法向速度不推进到下一站。 |
| `free_surface_velocity_half` | true | 0.5 | 1.0 | 自由面法向速度半幅传播，用于诊断传播尺度。 |
| `free_surface_velocity_flipped` | true | -1.0 | 1.0 | 仅翻转自由面法向速度传播符号，用于诊断垂向速度符号。 |
| `outer_history_rhs_disabled` | true | 1.0 | 0.0 | 保留自由面 marching，但关闭外域瞬态历史 RHS。 |

新增输出目录为：

```text
outputs/matched_bie_provider_free_surface_probe/results
```

新增文件包括：

| 文件 | 内容 | 作用 |
|---|---|---|
| `ma2005_wigley_iii_coefficients_free_surface_marching_candidate_detail.csv` | 每个 Ma 2005 系数、每个自由面候选的参考值、计算值、误差、gate ratio、自由面势范数、自由面法向导数范数、压力-势增益和 pressure-gradient 分量。 | 判断自由面传播对 heave/pitch pressure recovery 的影响方向和量级。 |
| `ma2005_wigley_iii_coefficients_free_surface_marching_candidate_summary.csv` | 每个候选跨八个系数的通过数、通过比例、中位 gate ratio、最大 gate ratio、改善/恶化行数和典型自由面/压力增益指标。 | 判断某个自由面传播候选是否有资格进入生产默认。 |

候选整体摘要如下。

| 候选 | use marching | velocity scale | history scale | pass_count | pass_fraction | median gate ratio | max gate ratio | improved rows | worsened rows | median heave free-surface potential norm | median pressure/body-potential gain | 状态 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `free_surface_marching_disabled` | false | 1.0 | 1.0 | 1 | 0.125 | 5.550 | 21.471 | 6 | 2 | 0.000 | 80120.818 | `FAIL` |
| `free_surface_velocity_zero` | true | 0.0 | 1.0 | 1 | 0.125 | 5.550 | 21.471 | 6 | 2 | 0.000 | 80120.818 | `FAIL` |
| `free_surface_velocity_half` | true | 0.5 | 1.0 | 0 | 0.000 | 55.246 | 148.817 | 4 | 4 | 2.622 | 80616.077 | `FAIL` |
| `current_marching` | true | 1.0 | 1.0 | 1 | 0.125 | 36.167 | 163.904 | 0 | 0 | 3.747 | 81108.579 | `FAIL` |
| `outer_history_rhs_disabled` | true | 1.0 | 0.0 | 1 | 0.125 | 35.927 | 164.032 | 4 | 4 | 3.741 | 81102.779 | `FAIL` |
| `free_surface_velocity_flipped` | true | -1.0 | 1.0 | 0 | 0.000 | 4718.998 | 17177.500 | 0 | 8 | 388.437 | 79122.072 | `FAIL` |

heave/self radiation 相关系数的代表性细节如下。

| 系数 | 候选 | reference | computed | gate ratio | 相对默认变化 | heave free-surface potential norm | pressure/body-potential gain | pressure-gradient component | 状态 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `A33` | `current_marching` | 1.000 | 10.290 | 61.933 | 0.000 | 2.141 | 82301.453 | 0.000 | `FAIL` |
| `A33` | `free_surface_marching_disabled` | 1.000 | 1.062 | 0.411 | -61.522 | 0.000 | 81302.977 | 0.000 | `PASS` |
| `A33` | `free_surface_velocity_zero` | 1.000 | 1.062 | 0.411 | -61.522 | 0.000 | 81302.977 | 0.000 | `PASS` |
| `A33` | `free_surface_velocity_half` | 1.000 | 7.741 | 44.942 | -16.991 | 1.498 | 81803.605 | 0.000 | `FAIL` |
| `A33` | `free_surface_velocity_flipped` | 1.000 | -100.899 | 679.325 | +617.392 | 221.964 | 80293.418 | 0.000 | `FAIL` |
| `B33` | `current_marching` | 2.100 | 9.646 | 23.957 | 0.000 | 4.283 | 82364.023 | 9.045 | `FAIL` |
| `B33` | `free_surface_marching_disabled` | 2.100 | 0.055 | 6.493 | -17.464 | 0.000 | 81366.315 | -0.000 | `FAIL` |
| `B33` | `free_surface_velocity_zero` | 2.100 | 0.055 | 6.493 | -17.464 | 0.000 | 81366.315 | -0.000 | `FAIL` |
| `B33` | `free_surface_velocity_half` | 2.100 | 14.354 | 38.902 | +14.945 | 2.996 | 81866.556 | 12.150 | `FAIL` |
| `B33` | `free_surface_velocity_flipped` | 2.100 | -942.207 | 2997.799 | +2973.842 | 443.928 | 80357.552 | -697.467 | `FAIL` |
| `A53` | `current_marching` | 0.150 | 1.445 | 28.772 | 0.000 | 4.283 | 82364.023 | 0.000 | `FAIL` |
| `A53` | `free_surface_marching_disabled` | 0.150 | -0.000 | 3.333 | -25.438 | 0.000 | 81366.315 | 0.000 | `FAIL` |
| `B53` | `current_marching` | -0.100 | -0.094 | 0.190 | 0.000 | 4.283 | 82364.023 | -0.380 | `PASS` |
| `B53` | `free_surface_marching_disabled` | -0.100 | 0.124 | 7.457 | +7.267 | 0.000 | 81366.315 | 0.098 | `FAIL` |
| `B53` | `outer_history_rhs_disabled` | -0.100 | -0.127 | 0.900 | +0.711 | 4.276 | 82358.146 | -0.403 | `PASS` |

这组候选给出非常明确的定位结论：

1. `A33` 的主要过大来自自由面 marching 传播。当前默认 `A33 = 10.290`，关闭 marching 或把自由面速度置零后 `A33 = 1.062`，直接进入 15% 门槛内。
2. `B33` 对自由面传播也极敏感，但不是简单“关闭就对”。当前默认 `B33 = 9.646` 过大；关闭 marching 后 `B33 = 0.055`，从过大变成严重偏低。这说明阻尼项需要正确的自由面辐射/历史传播，而不能把自由面状态硬关掉。
3. `free_surface_velocity_flipped` 全局爆炸，最大 gate ratio 达 `17177.500`。这基本排除“简单把自由面速度传播符号反过来”的修正路线。
4. `outer_history_rhs_disabled` 与当前默认非常接近，说明本算例的主要误差不是外域 history RHS 是否参与，而是内域自由面状态 `phi_free/eta_free` 沿站位传播的尺度、相位或局部时间步映射。
5. `free_surface_marching_disabled` 与 `free_surface_velocity_zero` 数值一致，说明当前影响主要来自 BIE-derived `inner_free_surface_normal_derivative` 被推进到下一站；只要该推进量为零，后续站位的自由面输入就回到相同状态。

因此，本轮排除结论是：不能把关闭自由面 marching 作为生产默认，因为它虽然修好了 `A33`，却破坏了 `B33/B53`，并且八项仍只有 `1/8` 通过。它的价值在于把 Gate 1 的下一步焦点压缩到一个更具体的问题：

```text
BIE-derived inner_free_surface_normal_derivative
  -> Eq.19-Eq.22 station-to-station phi_free/eta_free update
  -> local time step dx/U and encounter-frequency phase convention
  -> body potential re-solve
  -> Eq.30 pressure time/gradient recovery
```

下一步不应继续扫描经验 scale，而应审计 Eq. (19)--Eq. (22) 的离散时间推进式：`eta_t` 与 `phi_t` 的符号、`g` 项位置、`dt = dx/U` 是否需要随 marching 方向取符号、以及 station order 从 bow-to-stern 与 Ma 2005 局部时间定义是否完全一致。

### 9.23 Eq. (19)--Eq. (22) free-surface update formula 候选排除

2026-08-01 继续落实 9.22 的下一步，把自由面 marching 的问题进一步压到 Eq. (19)--Eq. (22) 离散推进公式本身。本轮候选不改变 BIE 矩阵、不改变压力恢复、不改变端部项，也不关闭自由面 marching；它只改变三个公式层面的选择：

```text
eta update:
  eta_new = eta_old + w * signed_dt

phi update:
  phi_new = phi_old + dynamic_sign * g * eta_level * signed_dt

where:
  signed_dt = time_direction_sign * dt
  eta_level = updated / previous / average half-step elevation
```

候选包括：

| 候选 | time direction | dynamic gravity sign | eta level | 物理解释 |
|---|---:|---:|---|---|
| `current_eq19_22` | 1 | -1 | `updated` | 当前默认：正局部时间步，势函数用更新后的半步高程，动态条件为 `-g eta`。 |
| `reverse_local_time` | -1 | -1 | `updated` | 同时反向运动学和动力学时间步，用于检查站位推进方向。 |
| `dynamic_gravity_sign_flipped` | 1 | 1 | `updated` | 仅把动态自由面条件从 `-g eta` 翻成 `+g eta`。 |
| `potential_uses_previous_elevation` | 1 | -1 | `previous` | 势函数更新使用旧半步高程。 |
| `potential_uses_average_elevation` | 1 | -1 | `average` | 势函数更新使用新旧半步高程平均。 |
| `reverse_time_and_dynamic_sign` | -1 | 1 | `updated` | 同时反向局部时间并翻转动态符号，用于分离 `dt` 方向和势函数符号。 |

新增输出目录为：

```text
outputs/matched_bie_provider_free_surface_update_probe/results
```

新增文件包括：

| 文件 | 内容 | 作用 |
|---|---|---|
| `ma2005_wigley_iii_coefficients_free_surface_update_formula_candidate_detail.csv` | 每个系数、每个公式候选的参考值、计算值、误差、gate ratio、自由面势范数、自由面势增量/法向速度增益、增量相位和 pressure-gradient 分量。 | 判断 Eq. (19)--Eq. (22) 的符号、时间方向和高程时间层是否能解释 Gate 1 误差。 |
| `ma2005_wigley_iii_coefficients_free_surface_update_formula_candidate_summary.csv` | 每个候选跨八个系数的通过数、通过比例、中位 gate ratio、最大 gate ratio、改善/恶化行数。 | 判断是否存在可替代当前推进公式的候选。 |

候选整体摘要如下。

| 候选 | time direction | dynamic sign | eta level | pass_count | pass_fraction | median gate ratio | max gate ratio | improved rows | worsened rows | median increment gain | median increment phase | 状态 |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `current_eq19_22` | 1 | -1 | `updated` | 1 | 0.125 | 36.167 | 163.904 | 0 | 0 | 0.465 | 180.000 | `FAIL` |
| `reverse_local_time` | -1 | -1 | `updated` | 1 | 0.125 | 36.167 | 163.904 | 0 | 0 | 0.465 | 180.000 | `FAIL` |
| `potential_uses_average_elevation` | 1 | -1 | `average` | 0 | 0.000 | 38.484 | 165.748 | 1 | 7 | 0.388 | 180.000 | `FAIL` |
| `potential_uses_previous_elevation` | 1 | -1 | `previous` | 0 | 0.000 | 41.344 | 167.089 | 0 | 8 | 0.322 | 180.000 | `FAIL` |
| `dynamic_gravity_sign_flipped` | 1 | 1 | `updated` | 0 | 0.000 | 4718.998 | 17177.500 | 0 | 8 | 0.096 | 0.000 | `FAIL` |
| `reverse_time_and_dynamic_sign` | -1 | 1 | `updated` | 0 | 0.000 | 4718.998 | 17177.500 | 0 | 8 | 0.096 | 0.000 | `FAIL` |

heave/self radiation 相关代表性细节如下。

| 系数 | 候选 | reference | computed | gate ratio | 相对默认变化 | heave free-surface potential norm | increment gain | increment phase | pressure-gradient component | 状态 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `A33` | `current_eq19_22` | 1.000 | 10.290 | 61.933 | 0.000 | 2.141 | 0.465 | 180.000 | 0.000 | `FAIL` |
| `A33` | `reverse_local_time` | 1.000 | 10.290 | 61.933 | 0.000 | 2.141 | 0.465 | 180.000 | 0.000 | `FAIL` |
| `A33` | `potential_uses_average_elevation` | 1.000 | 10.435 | 62.899 | +0.965 | 2.222 | 0.388 | 180.000 | 0.000 | `FAIL` |
| `A33` | `potential_uses_previous_elevation` | 1.000 | 10.617 | 64.115 | +2.182 | 2.316 | 0.322 | 180.000 | 0.000 | `FAIL` |
| `A33` | `dynamic_gravity_sign_flipped` | 1.000 | -100.899 | 679.325 | +617.392 | 221.964 | 0.096 | 0.000 | 0.000 | `FAIL` |
| `B33` | `current_eq19_22` | 2.100 | 9.646 | 23.957 | 0.000 | 4.283 | 0.465 | 180.000 | 9.045 | `FAIL` |
| `B33` | `reverse_local_time` | 2.100 | 9.646 | 23.957 | 0.000 | 4.283 | 0.465 | 180.000 | 9.045 | `FAIL` |
| `B33` | `potential_uses_average_elevation` | 2.100 | 10.107 | 25.418 | +1.460 | 4.444 | 0.388 | 180.000 | 9.558 | `FAIL` |
| `B33` | `potential_uses_previous_elevation` | 2.100 | 10.735 | 27.411 | +3.454 | 4.632 | 0.322 | 180.000 | 10.230 | `FAIL` |
| `B33` | `dynamic_gravity_sign_flipped` | 2.100 | -942.207 | 2997.799 | +2973.842 | 443.928 | 0.096 | 0.000 | -697.467 | `FAIL` |

这组候选给出四个排除结论：

1. 当前 Eq. (19)--Eq. (22) 离散式是本轮候选中最好的，虽然仍未通过 Gate 1。
2. `reverse_local_time` 与当前结果完全一致，说明在当前线性复幅、bow-to-stern station sweep 的实现中，单独把局部时间步取反不会改变整船系数；因此“只需把 `dt` 改成负号”不是修正路线。
3. 把动态自由面符号从 `-g eta` 改成 `+g eta` 会使结果爆炸，最大 gate ratio 达 `17177.500`；这排除了动态自由面条件简单反号。
4. 势函数更新使用 previous 或 average 高程都比当前 `updated` 更差；因此 `eta` 时间层选择也不能解释 `A33/B33` 的主误差。

结合 9.22 的结果，可以得到更精确的下一步定位：

```text
关闭自由面 marching:
  A33 通过，但 B33 严重偏低

改变 Eq.19-Eq.22 公式层候选:
  当前公式最好，其他公式更差或爆炸

因此剩余问题更可能位于:
  BIE-derived inner_free_surface_normal_derivative 的尺度/相位
  或 free_surface_potential 进入 Eq.23 内域 RHS 的耦合强度/符号
  或 inner free-surface self/block 系数与 body/control block 的相对归一化
```

下一步应聚焦 `inner_free_surface_normal_derivative` 本身，而不是继续扫描自由面推进公式。需要建立站位级的“自由面法向导数替代源”候选，例如解析 oscillator 约束、只保留实部/虚部、按 body velocity 投影归一化、或者用外域控制面平衡反推法向导数。所有候选仍必须保持 diagnostic-only，直到八个 Wigley III 系数在同一默认配置下同时过 Gate 1。

### 9.24 inner free-surface normal derivative source 候选排除

2026-08-01 继续落实 9.23 的下一步，新增 `inner_free_surface_normal_derivative` 传播源候选。本轮不改变 BIE 方程本身，也不改变 Eq. (19)--Eq. (22) 的推进公式，而是在 BIE 求得自由面法向导数之后、把它作为自由面垂向速度推进到下一站之前，改变传播源：

```text
raw BIE solution:
  phi_n_free = inner_free_surface_normal_derivative

diagnostic marching velocity:
  w_free = filter(phi_n_free)
```

候选包括：

| 候选 | source | 物理解释 |
|---|---|---|
| `current_raw` | `raw` | 当前默认：原样传播 BIE 解出的自由面法向导数。 |
| `real_part_only` | `real_part_only` | 只传播实部，用于检查同相分量是否导致 added mass 放大。 |
| `imaginary_part_only` | `imaginary_part_only` | 只传播虚部/正交相位分量，用于检查 radiation damping 相关分量。 |
| `phase_lead_90` | `phase_lead_90` | 将自由面法向导数整体前移 90 度。 |
| `phase_lag_90` | `phase_lag_90` | 将自由面法向导数整体滞后 90 度。 |
| `body_velocity_norm_normalized` | `body_velocity_norm_normalized` | 保留 BIE 解出的相位分布，但把范数缩放到局部 body normal velocity 范数。 |

新增输出目录为：

```text
outputs/matched_bie_provider_free_surface_normal_source_probe/results
```

新增文件包括：

| 文件 | 内容 | 作用 |
|---|---|---|
| `ma2005_wigley_iii_coefficients_free_surface_normal_derivative_source_candidate_detail.csv` | 每个系数、每个 source 候选的参考值、计算值、gate ratio、自由面势范数、自由面法向导数范数、势增量/法向导数增益和 pressure-gradient 分量。 | 判断 BIE 解出的自由面法向导数中哪些相位/分量造成后续传播放大。 |
| `ma2005_wigley_iii_coefficients_free_surface_normal_derivative_source_candidate_summary.csv` | 每个候选跨八个系数的通过数、通过比例、中位 gate ratio、最大 gate ratio、改善/恶化行数。 | 判断是否存在可替代 raw source 的候选。 |

候选整体摘要如下。

| 候选 | source | pass_count | pass_fraction | median gate ratio | max gate ratio | improved rows | worsened rows | median heave free-surface potential norm | median heave free-surface normal derivative norm | median increment gain | 状态 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `imaginary_part_only` | `imaginary_part_only` | 1 | 0.125 | 26.364 | 88.225 | 3 | 1 | 3.747 | 11.179 | 0.465 | `FAIL` |
| `real_part_only` | `real_part_only` | 1 | 0.125 | 6.975 | 116.120 | 6 | 2 | 0.000 | 2.393 | 0.000 | `FAIL` |
| `current_raw` | `raw` | 1 | 0.125 | 36.167 | 163.904 | 0 | 0 | 3.747 | 11.179 | 0.465 | `FAIL` |
| `body_velocity_norm_normalized` | `body_velocity_norm_normalized` | 0 | 0.000 | 152.429 | 398.807 | 0 | 8 | 8.018 | 19.976 | 0.976 | `FAIL` |
| `phase_lag_90` | `phase_lag_90` | 0 | 0.000 | 183.244 | 831.045 | 1 | 7 | 13.761 | 27.583 | 0.125 | `FAIL` |
| `phase_lead_90` | `phase_lead_90` | 0 | 0.000 | 214.477 | 937.001 | 0 | 8 | 13.761 | 27.583 | 0.125 | `FAIL` |

heave/self radiation 相关代表性细节如下。

| 系数 | 候选 | reference | computed | gate ratio | 相对默认变化 | heave free-surface potential norm | heave normal derivative norm | increment gain | pressure-gradient component | 状态 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `A33` | `current_raw` | 1.000 | 10.290 | 61.933 | 0.000 | 2.141 | 6.388 | 0.465 | 0.000 | `FAIL` |
| `A33` | `imaginary_part_only` | 1.000 | 10.290 | 61.933 | 0.000 | 2.141 | 6.388 | 0.465 | 0.000 | `FAIL` |
| `A33` | `real_part_only` | 1.000 | 1.062 | 0.411 | -61.522 | 0.000 | 1.367 | 0.000 | 0.000 | `PASS` |
| `A33` | `phase_lag_90` | 1.000 | -14.299 | 101.995 | +40.062 | 7.863 | 15.762 | 0.125 | -21.954 | `FAIL` |
| `A33` | `phase_lead_90` | 1.000 | 36.907 | 239.381 | +177.448 | 7.863 | 15.762 | 0.125 | 21.954 | `FAIL` |
| `B33` | `current_raw` | 2.100 | 9.646 | 23.957 | 0.000 | 4.283 | 12.776 | 0.465 | 9.045 | `FAIL` |
| `B33` | `imaginary_part_only` | 2.100 | 9.646 | 23.957 | 0.000 | 4.283 | 12.776 | 0.465 | 9.045 | `FAIL` |
| `B33` | `real_part_only` | 2.100 | 0.055 | 6.493 | -17.464 | 0.000 | 2.735 | 0.000 | -0.000 | `FAIL` |
| `B33` | `phase_lag_90` | 2.100 | 80.304 | 248.266 | +224.309 | 15.727 | 31.524 | 0.125 | 42.900 | `FAIL` |
| `B33` | `phase_lead_90` | 2.100 | 30.000 | 88.571 | +64.614 | 15.727 | 31.524 | 0.125 | 42.900 | `FAIL` |
| `B53` | `current_raw` | -0.100 | -0.094 | 0.190 | 0.000 | 4.283 | 12.776 | 0.465 | -0.380 | `PASS` |
| `B53` | `real_part_only` | -0.100 | 0.124 | 7.457 | +7.267 | 0.000 | 2.735 | 0.000 | 0.098 | `FAIL` |

这组候选给出五个结论：

1. `real_part_only` 与上一轮“关闭自由面传播”表现相近：`A33` 可以通过，但 `B33` 严重偏低，且 `B53` 被破坏。因此不能把 real-only 传播作为生产默认。
2. `imaginary_part_only` 对 `A33/B33/A53/B53` 与当前 raw 基本一致，但跨八项最大 gate ratio 从 `163.904` 降到 `88.225`，改善主要来自 pitch 相关列。它说明 raw 的实部分量并不是 heave 主误差的唯一来源。
3. ±90 度相位旋转显著恶化，尤其会把 pressure-gradient 分量推到非常大的错误值；因此“整体相位差 90 度”不是正确修正。
4. 按 body velocity 范数归一化全面恶化，说明自由面法向导数不是简单应该与 body normal velocity 同范数。
5. heave 主链中 `imaginary_part_only == current_raw` 的现象说明，当前 A33/B33 的传播主导分量本身已经接近虚部/正交相位分量；问题更可能出现在该分量如何通过 Eq. (23) 内域自由面 RHS 反馈到 body potential，而不是简单实/虚筛选。

因此，下一步不应继续在传播后的 `w_free` 上做经验滤波，而应回到 BIE 线性系统本体，集中审计：

```text
Eq.23 inner-domain system:
  A_body * phi_body
  + A_free * phi_free
  + B_free * phi_n_free
  + control-surface coupling

unknown placement:
  phi_body unknown
  phi_n_free unknown
  control phi / phi_n unknown

known source:
  body normal velocity
  prescribed phi_free from previous station
```

特别要检查 `B_free * phi_n_free` 的列尺度、符号和边界极限系数，以及 `A_free * phi_free` 作为已知 RHS 时是否过强。因为 9.22 已经显示关闭 `phi_free` 传播可修正 `A33`，9.24 又显示传播源滤波无法同时修正 `A33/B33`，剩余最大嫌疑已经转移到 Eq. (23) 内域自由面 block coupling 本身。

### 9.25 Eq.23 inner free-surface block coupling 候选排除

2026-08-01 继续沿 Gate 1 失败路径审计 Eq. (23) 内域自由面 block coupling。本轮新增两个只用于诊断的参数，默认值均为 `1.0`，因此不会改变生产主线：

```text
Eq.23 current placement:
  unknown column: -B_free * phi_n_free
  known RHS term: -A_free * phi_free

diagnostic scales:
  inner_free_surface_unknown_normal_column_scale
  inner_free_surface_known_potential_rhs_scale
```

新增输出目录为：

```text
outputs/matched_bie_provider_inner_free_block_probe/results
```

新增文件包括：

| 文件 | 内容 | 作用 |
|---|---|---|
| `ma2005_wigley_iii_coefficients_inner_free_surface_block_coupling_candidate_detail.csv` | 每个 Wigley III 系数、每个 Eq.23 block 候选的参考值、计算值、gate ratio、相对当前默认的变化，以及自由面势、自由面法向导数、body-pressure gain 和 pressure-gradient 分量。 | 判断 `A_free * phi_free` 的 RHS block 和 `B_free * phi_n_free` 的未知列 block 是否存在一级符号/尺度错误。 |
| `ma2005_wigley_iii_coefficients_inner_free_surface_block_coupling_candidate_summary.csv` | 每个候选跨八个系数的通过数、通过比例、中位 gate ratio、最大 gate ratio、改善/恶化行数。 | 判断是否有候选能够作为生产默认修正。 |

候选整体结果如下：

| 候选 | known RHS scale | unknown column scale | pass_count | pass_fraction | median gate ratio | max gate ratio | improved rows | worsened rows | 状态 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `known_phi_free_rhs_removed` | 0.0 | 1.0 | 1 | 0.125 | 5.550 | 21.471 | 6 | 2 | `FAIL` |
| `current_default` | 1.0 | 1.0 | 1 | 0.125 | 36.167 | 163.904 | 0 | 0 | `FAIL` |
| `known_phi_free_rhs_flipped` | -1.0 | 1.0 | 0 | 0.000 | 4718.998 | 17177.500 | 0 | 8 | `FAIL` |
| `unknown_phi_n_free_column_flipped` | 1.0 | -1.0 | 0 | 0.000 | 4718.998 | 17177.500 | 0 | 8 | `FAIL` |
| `unknown_phi_n_free_column_removed` | 1.0 | 0.0 | 0 | 0.000 | 待补充 | 待补充 | 0 | 0 | `FAIL` |
| `both_free_blocks_removed` | 0.0 | 0.0 | 0 | 0.000 | 待补充 | 待补充 | 0 | 0 | `FAIL` |

代表性细节如下：

| 系数 | 候选 | reference | computed | gate ratio | 相对默认变化 | 状态 |
|---|---|---:|---:|---:|---:|---|
| `A33` | `current_default` | 1.000 | 10.290 | 61.933 | 0.000 | `FAIL` |
| `A33` | `known_phi_free_rhs_removed` | 1.000 | 1.062 | 0.411 | -61.522 | `PASS` |
| `B33` | `current_default` | 2.100 | 9.646 | 23.957 | 0.000 | `FAIL` |
| `B33` | `known_phi_free_rhs_removed` | 2.100 | 0.055 | 6.493 | -17.464 | `FAIL` |
| `B53` | `current_default` | -0.100 | -0.094 | 0.190 | 0.000 | `PASS` |
| `B53` | `known_phi_free_rhs_removed` | -0.100 | 0.124 | 7.457 | +7.267 | `FAIL` |
| `A35` | `current_default` | -0.200 | -2.814 | 43.563 | 0.000 | `FAIL` |
| `A35` | `known_phi_free_rhs_removed` | -0.200 | -0.010 | 3.172 | -40.391 | `FAIL` |
| `B35` | `current_default` | 0.130 | 6.522 | 163.904 | 0.000 | `FAIL` |
| `B35` | `known_phi_free_rhs_removed` | 0.130 | 0.967 | 21.471 | -142.434 | `FAIL` |
| `A55` | `current_default` | 0.063 | 0.090 | 2.865 | 0.000 | `FAIL` |
| `A55` | `known_phi_free_rhs_removed` | 0.063 | 0.012 | 5.344 | +2.479 | `FAIL` |
| `B55` | `current_default` | 0.090 | 1.859 | 131.032 | 0.000 | `FAIL` |
| `B55` | `known_phi_free_rhs_removed` | 0.090 | 0.012 | 5.755 | -125.277 | `FAIL` |

本轮结论：

1. 移除 `-A_free * phi_free` RHS 能显著降低最大 gate ratio，从 `163.904` 降到 `21.471`，并改善 6 个系数；这说明已知自由面势 RHS block 确实是当前误差放大的重要通道。
2. 但是该候选仍只有 1/8 通过，且会把原本通过的 `B53` 破坏，同时 `B33` 严重偏低。因此不能把 `known_phi_free_rhs_removed` 提升为生产默认。
3. 反转 `known phi_free` RHS 或反转 `unknown phi_n_free` 列会全面爆炸，最大 gate ratio 达 `17177.500`，可以排除简单符号反转。
4. 移除未知 `phi_n_free` 列或同时移除两个自由面 block 会导致候选求解失败或无有效有限数值，说明 Eq.23 的自由面未知列是保持系统闭合不可缺少的部分。
5. Gate 1 仍为 `PENDING`。下一步不应采用“关闭 RHS”这类非物理修补，而应继续检查 `A_free` 与 `B_free` block 相对归一化、边界极限系数、局部 free-surface state 的单位尺度，以及 pressure recovery 中时间项/前进速度梯度项如何把 body potential 放大成整船系数。

### 9.26 Eq.23 free-block canonical normalization 候选排除

2026-08-01 在 9.25 的基础上继续检查 canonical boundary-integral normalization。新增候选不再只是移除或反转自由面 block，而是检查 `2π` 与 `1/(2π)` 这类 Green identity 常数是否被遗漏在 `A_free * phi_free` 或 `B_free * phi_n_free` 的相对尺度中。

本轮仍使用同一主线入口：

```python
LinearFrequencyProvider(
    source="linear_2p5d",
    config=Linear2p5DProviderConfig(formulation="matched_bie"),
)
```

输出目录为：

```text
outputs/matched_bie_provider_inner_free_block_normalization_probe/results
```

候选整体结果如下：

| 候选 | known RHS scale | unknown column scale | pass_count | pass_fraction | median gate ratio | max gate ratio | improved rows | worsened rows | 状态 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `known_phi_free_rhs_removed` | 0.000 | 1.000 | 1 | 0.125 | 5.550 | 21.471 | 6 | 2 | `FAIL` |
| `unknown_phi_n_free_column_2pi` | 1.000 | 6.283 | 0 | 0.000 | 25.453 | 118.453 | 6 | 2 | `FAIL` |
| `known_phi_free_rhs_one_over_2pi` | 0.159 | 1.000 | 0 | 0.000 | 25.453 | 118.453 | 6 | 2 | `FAIL` |
| `current_default` | 1.000 | 1.000 | 1 | 0.125 | 36.167 | 163.904 | 0 | 0 | `FAIL` |
| `both_free_blocks_one_over_2pi` | 0.159 | 0.159 | 1 | 0.125 | 36.167 | 163.904 | 3 | 3 | `FAIL` |
| `both_free_blocks_2pi` | 6.283 | 6.283 | 1 | 0.125 | 36.167 | 163.904 | 4 | 3 | `FAIL` |
| `known_phi_free_rhs_2pi` | 6.283 | 1.000 | 0 | 0.000 | 47.476 | 340.754 | 5 | 3 | `FAIL` |
| `unknown_phi_n_free_column_one_over_2pi` | 1.000 | 0.159 | 0 | 0.000 | 47.476 | 340.754 | 5 | 3 | `FAIL` |
| `known_phi_free_rhs_flipped` | -1.000 | 1.000 | 0 | 0.000 | 4718.998 | 17177.500 | 0 | 8 | `FAIL` |
| `unknown_phi_n_free_column_flipped` | 1.000 | -1.000 | 0 | 0.000 | 4718.998 | 17177.500 | 0 | 8 | `FAIL` |
| `unknown_phi_n_free_column_removed` | 1.000 | 0.000 | 0 | 0.000 | 待补充 | 待补充 | 0 | 0 | `FAIL` |
| `both_free_blocks_removed` | 0.000 | 0.000 | 0 | 0.000 | 待补充 | 待补充 | 0 | 0 | `FAIL` |

主对角项代表性细节如下：

| 系数 | 候选 | reference | computed | gate ratio | 相对默认变化 | 状态 |
|---|---|---:|---:|---:|---:|---|
| `A33` | `current_default` | 1.000 | 10.290 | 61.933 | 0.000 | `FAIL` |
| `A33` | `known_phi_free_rhs_one_over_2pi` | 1.000 | 3.888 | 19.257 | -42.677 | `FAIL` |
| `A33` | `unknown_phi_n_free_column_2pi` | 1.000 | 3.888 | 19.257 | -42.677 | `FAIL` |
| `A33` | `known_phi_free_rhs_removed` | 1.000 | 1.062 | 0.411 | -61.522 | `PASS` |
| `B33` | `current_default` | 2.100 | 9.646 | 23.957 | 0.000 | `FAIL` |
| `B33` | `known_phi_free_rhs_one_over_2pi` | 2.100 | 8.674 | 20.871 | -3.086 | `FAIL` |
| `B33` | `unknown_phi_n_free_column_2pi` | 2.100 | 8.674 | 20.871 | -3.086 | `FAIL` |
| `B33` | `known_phi_free_rhs_removed` | 2.100 | 0.055 | 6.493 | -17.464 | `FAIL` |
| `A55` | `current_default` | 0.063 | 0.090 | 2.865 | 0.000 | `FAIL` |
| `A55` | `known_phi_free_rhs_one_over_2pi` | 0.063 | -1.056 | 118.453 | +115.587 | `FAIL` |
| `A55` | `unknown_phi_n_free_column_2pi` | 0.063 | -1.056 | 118.453 | +115.587 | `FAIL` |
| `B55` | `current_default` | 0.090 | 1.859 | 131.032 | 0.000 | `FAIL` |
| `B55` | `known_phi_free_rhs_one_over_2pi` | 0.090 | 0.142 | 3.881 | -127.151 | `FAIL` |
| `B55` | `unknown_phi_n_free_column_2pi` | 0.090 | 0.142 | 3.881 | -127.151 | `FAIL` |

本轮结论：

1. `known_phi_free_rhs_one_over_2pi` 与 `unknown_phi_n_free_column_2pi` 给出完全相同的结果；`known_phi_free_rhs_2pi` 与 `unknown_phi_n_free_column_one_over_2pi` 也互为等价。这说明当前 Eq.23 自由面耦合的关键是 `A_free` RHS block 与 `B_free` unknown-column block 的相对尺度，而不是某个单独 block 的绝对尺度。
2. `both_free_blocks_one_over_2pi` 和 `both_free_blocks_2pi` 与默认几乎完全一致，进一步说明把两个自由面 block 同时乘同一个常数只是改变同一组行内的公共尺度，不会改变求解出的物理未知量。
3. canonical `1/(2π)` 或 `2π` 单独作用于一个自由面 block 时，最多只能把最大 gate ratio 从 `163.904` 降到 `118.453`，仍远高于 Gate 1 门槛；因此不能把“漏掉 `2π` 常数”作为当前主要修正。
4. `B55` 在 `known_phi_free_rhs_one_over_2pi` 下从 `131.032` 降到 `3.881`，但 `A55` 同时从 `2.865` 恶化到 `118.453`；这属于典型的单项改善、整体失败，必须保持 diagnostic-only。
5. Gate 1 仍为 `PENDING`。下一步更应转向 Eq. (30) pressure recovery 链路，尤其是时间导数项与前进速度梯度项怎样从 body potential 转成整船 `A/B` 系数，而不是继续扫描 Eq.23 自由面 block 的单常数归一化。

## 10. 怎样把想要的目标做实

本项目下一步不能再定义为“继续完善 2.5D 模型”这样宽泛的任务，而应定义为一个可验收目标：

> 在 `LinearFrequencyProvider(source="linear_2p5d", config=Linear2p5DProviderConfig(formulation="matched_bie"))` 主线下，实现可重复验证的 Ma--Duan--Song 型线性高速 2.5D 频域求解器；以 Ma 2005 Wigley III 结果作为 Gate 1 硬基准，达到 `A33/B33/A55/B55` 相对误差不超过 15%，`A35/B35/A53/B53` 相对误差不超过 30%，并保留 Fridsma、Delft 372、C1 trimaran 和水翼模块作为后续 Gate 2/Gate 3 的扩展验证入口。

把这个目标做实，需要同时满足以下条件。

| 条件 | 必须做到什么 | 为什么这是硬条件 |
|---|---|---|
| 数据条件 | Ma 2005 Wigley III 的几何、速度、频率、无量纲定义和八个水动力系数参考值必须固定在仓库中；SL-7 和 C1 若缺少真实 offsets，只能列为待补充或替代验证，不能作为硬验收。 | 没有固定参考数据，就无法判断“算得像不像”，也无法比较每次修改是否进步。 |
| 模型入口条件 | 生产主线只允许走 `linear_2p5d/matched_bie`；legacy 的经验或 reduced-order 模型只能作为对照，不能混入 Gate 1。 | 验证对象必须唯一，否则通过结果可能来自经验补偿，而不是 2.5D 内核本身。 |
| 方程闭合条件 | Eq. (30) 压力项、Eq. (32) Stokes body/end-term、整船 `A/B` 装配和无量纲化必须能逐项输出并对照。 | 当前误差集中在压力梯度与端部项，必须能拆开看，不能只看最终矩阵。 |
| 单元验证条件 | 二维剖面 BIE 要先通过解析/半解析剖面测试；包括 heave/pitch 模态的势函数符号、法向导数、压力积分方向和力矩臂。 | 如果二维剖面层符号或相位不稳，整船 2.5D 积分一定会被放大。 |
| 回归测试条件 | 每个 Gate 1 修正都必须跑 `python -m pytest -q` 与 `python -m planing_seakeeping validate ... --ma-hydro-model matched_bie_provider`。 | 目标要靠自动化保持，不靠人工记忆。 |
| 验收报告条件 | 每次探针输出 `CSV + Markdown`，至少记录失败项、误差、关键诊断字段和下一步判断。 | 研究代码的可靠性来自可追溯证据链，而不是一次性跑通。 |

因此，下一轮最具体的验收清单应压缩为五件事：

1. `matched_bie_provider` 的八个 Ma 2005 Wigley III 系数全部达到 Gate 1 误差门槛。
2. `ma2005_wigley_iii_coefficients_comparison.csv` 中无 `NaN/Inf`，且所有新增诊断字段保持有限值。
3. `B53` 的通过必须能由逐项贡献解释，不能只接受抵消后的最终数值。
4. 至少一个二维剖面解析/半解析单元测试通过，用于证明 BIE 符号、相位和压力积分规范。
5. 生成一份更新后的 `run_report.md` 或研究报告，明确写出哪些目标已过、哪些仍是 `待补充`，尤其是 SL-7、C1 trimaran offsets 和目标艇真实试验数据。

一句话概括：**把目标做实，就是先把“完整 2.5D”收敛成“Ma 2005 Wigley III 可复现的 matched-BIE 2.5D 内核”，再用固定数据、固定命令、固定误差门槛和逐项诊断把每一步推进变成可检查的证据。**
