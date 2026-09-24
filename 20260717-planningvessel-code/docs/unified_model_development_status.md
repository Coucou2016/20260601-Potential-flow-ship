# 高速船统一模型开发状态

日期：2026-07-28

本文件记录根据 `高速船_2.5D_2Dt_多体船_水翼统一模型完整实施方案.md`
完成的首批代码升级。重点是把现有 `planing_seakeeping` 从单一滑行艇纵向
程序扩展为可承接 2.5D、2D+t、多体船和水翼模块的统一架构，同时保持未验证
内核的边界清晰。

## 已落地内容

| 模块 | 文件 | 状态 |
|---|---|---|
| 能力与有效性元数据 | `planing_seakeeping/types.py` | 已新增 `ModelCapabilities`、`ValidityReport`、`HydroLoadResult`、`FrequencyDomainHydrodynamics` |
| Provider 配置 | `planing_seakeeping/schema.py` | 已新增线性 2.5D、非线性 2D+t、多体、水翼配置和生产级校验 |
| 航态仲裁 | `planing_seakeeping/regimes.py` | 已实现 smoothstep 和分量级载荷权重，避免直接混合水动力矩阵 |
| 统一几何 | `planing_seakeeping/geometry.py` | 已实现统一 offsets CSV 读取、几何来源审计、Delft 372/C1 surrogate |
| 线性 2.5D kernel | `planing_seakeeping/kernels/linear_2p5d` | 已建立 Ma-Duan-Song matched BIE API 合同，并可路由旧 station assembly |
| 非线性 2D+t kernel | `planing_seakeeping/kernels/nonlinear_2dt` | 已建立 Sun-Faltinsen 移动剖面管理器和 provider 合同 |
| 多体 kernel | `planing_seakeeping/kernels/multihull` | 已实现片体载荷到全船六分量装配和耦合完整性报告 |
| 水翼 kernel | `planing_seakeeping/kernels/hydrofoil` | 已实现第一阶段有限翼小攻角载荷与四阶 Routh-Hurwitz 检查 |
| Provider 命名修正 | `planing_seakeeping/providers/planing_2dt.py` | `ReducedOrderPlaning2DtProvider` 已降级为兼容别名，新名为 `ReducedOrderPlaningLoadProvider` |

## 几何数据缺口处理

1. Delft 372：B2 第 14 页 offsets 可以用 `pypdf` 的 layout 模式抽取文本，但存在 OCR 错字和错列风险。当前代码先提供 surrogate 和统一 CSV 导入器；真实验证前必须完成人工复核或 OCR 表格校正。
2. SL-7：当前仍使用 `make_sl7_surrogate_hull`。未找到可直接替代的机器可读真实 offsets；surrogate 不可用于 SL-7 几何验收。
3. C1 三体船：当前使用主尺度 surrogate，并保留主片体/侧片体相对位置参数。真实 C1 offsets 未找到前，只能做 API 和趋势开发，不能做论文曲线验收。

## 不能越界的结论

- `NonlinearBEM2DtProvider` 现在只是生产内核合同，不是已完成的 Sun-Faltinsen 自由面 BEM。
- `linear_2p5d` 新 kernel 目前能承接旧 station assembly，但 Ma-Duan-Song 内外域匹配 BIE 仍未实现。
- 多体船目前只有装配、拓扑和 placeholder guard；cross-radiation/cross-diffraction 仍需真实横剖面耦合 BIE。
- 水翼模块是小攻角一阶模型和控制接口基础，不包含通气、空化、自由面和真实舵机试验标定。

## 下一步建议

1. 用 B2 第 14 页生成 `benchmarks/delft372/delft372_demihull_offsets.csv`，并把每个 OCR 修正写入审计表。
2. 为 `Matched2p5DSectionSolver` 实现内域简单 Green 函数、外域瞬态自由面 Green 函数和控制面匹配矩阵。
3. 给 `NonlinearBEM2DtProvider` 增加二维楔形入水 BEM 最小闭环，并先通过 Wagner/von Karman 基准。
4. 将 C1 三体船 surrogate 接到 `multibody_sections`，完成四布局的输入配置和非验证 smoke test。
5. 给水翼模块加入舵机一阶动态、限幅和控制延迟状态。
## 2026-07-30 进展：Delft 372 真实几何落地

已从 `D:/Projects/20260601-Potential-flow-ship/20260729-文献收集/md/B2.md` 的 `TABLE OF OFFSETS`
提取 Delft 372 单片体 offsets，并生成：

| 文件 | 状态 |
|---|---|
| `benchmarks/delft372/delft372_demihull_offsets.csv` | 可由 `load_station_offsets_csv` 直接读取 |
| `benchmarks/delft372/delft372_demihull_offsets_raw.csv` | 保留原始表坐标，便于追溯 |
| `benchmarks/delft372/delft372_demihull_geometry_audit.csv` | 23 个站位全部通过剖面积、水线半宽、吃水基础审计 |
| `configs/delft372_demihull_offsets.yml` | Delft 372 单片体真实 offsets 示例配置 |

几何静水复核结果：按 `z_table=1.5` 为水线、表格比例尺 `0.1 m`，两片体总排水质量为
`86.219 kg`，与 B2 报告 `87.07 kg` 的相对误差约 `0.98%`；单片体浮心纵向位置为
`1.416 m`，接近报告给出的 `LCG=1.41 m`。因此 Delft 372 已可作为几何级真实 benchmark。

注意：这只解决几何输入。B1/B2 的运动响应和连接载荷曲线仍需数字化；多体水动力上仍需实现共同横剖面边界积分、
cross-radiation 和 cross-diffraction 后，才可进入 RAO 幅值验收。
## 2026-07-30 进展：A1 线性 2.5D 基础块与验收矩阵

在 `planing_seakeeping/kernels/linear_2p5d/formulation.py` 中新增 Ma-Duan-Song 型 2.5D 的两个基础块：

| 接口 | 作用 | 当前边界 |
|---|---|---|
| `build_section_marching_grid()` | 将 `StationHull` 的纵向站位映射为从艏到艉的局部时间网格 | 只实现 A1 局部时间关系，未求解自由面历史项 |
| `build_inner_domain_panel_geometry()` | 将二维湿剖面离散为直线面元 | 只处理物体边界面元 |
| `inner_domain_source_normal_matrix()` | 组装内域简单 Green 函数源项法向影响矩阵 | 未包含外域瞬态自由面 Green 函数 |
| `inner_domain_source_potential_matrix()` | 组装内域势影响矩阵 | 用于后续压力恢复与控制面匹配 |
| `Matched2p5DSectionSolver.assemble_inner_domain_system()` | 给定边界法向速度，求解内域源强系统 | 明确标记为 `a1_inner_domain_simple_green_block_no_free_surface_matching` |

新增 `benchmarks/validation_targets.csv` 和 `docs/next_phase_acceptance_gates_20260730.md`。其中 Delft 372 几何门槛已为 `PASS`；
SL-7 与 C1 因缺真实 machine-readable offsets 继续为 `BLOCKED`；A1 完整 2.5D、Delft 372 多体 RAO、
Sun-Faltinsen 2D+t 和 Fridsma/Katayama 滑行艇波浪验证均为 `PENDING`。

## 2026-07-30 进展：Delft 372 双体船组件装配

新增 `make_delft372_catamaran_from_offsets()`，按 B2 主尺度中的片体中心距 `0.70 m` 从同一份
`delft372_demihull_offsets.csv` 生成 `port_demihull` 和 `starboard_demihull` 两个组件。

该入口已经通过测试，能与 `multibody_sections()` 共同使用，为下一步“同一横剖面内两片体共同边界积分”
提供真实几何和拓扑输入。当前仍不声称 cross-radiation/cross-diffraction 已实现。

## 2026-07-30 进展：A1 外域自由面历史项和控制面方程块

继续推进 Gate 1，新增以下 A1 外域基础接口：

| 接口 | 对应 A1 位置 | 当前作用 |
|---|---|---|
| `initialize_free_surface_state()` | Eq. (21)-(22) | 从初始自由面和竖向速度初始化交错自由面高程和势 |
| `advance_free_surface_state()` | Eq. (19)-(20) | 按 Chapman 稳定格式推进自由面高程和势 |
| `build_control_surface_geometry()` | Section 3.3 | 构建固定半圆控制面 `S_C` |
| `build_transient_free_surface_history()` | Eq. (12), Eq. (28) | 用有限积分截断生成瞬态自由面 Green 函数历史核 |
| `TransientFreeSurfaceHistory.convolution_rhs()` | Eq. (24) 右端 | 计算历史卷积项 |
| `Matched2p5DSectionSolver.assemble_outer_control_surface_system()` | Eq. (24) | 组装外域控制面方程块 |

新的外域块已经返回 `MatchedBoundarySystem`，并通过测试确认矩阵维度、历史卷积和有限解都正常。

Gate 1 的 Eq. (23)-Eq. (24) 方阵闭环已在 2026-07-31 补上；Eq. (30) 压力恢复和单站压力积分也已补上。
随后还需要做前进速度梯度项、端部项和整船 heave/pitch 系数装配。

## 2026-07-31 进展：A1 Eq. (23)-Eq. (24) matched square system

新增 `MatchedSectionBoundaryData` 和 `assemble_matched_section_system()`，并在
`Matched2p5DSectionSolver.assemble_matched_section_system()` 中提供求解器入口。

该方阵采用以下未知量顺序：

```text
psi_body, psi_n_inner_free_surface, psi_control, psi_n_control
```

其中体面法向速度来自物体边界条件，内自由面势来自 A1 Eq. (20)，控制面势和控制面法向导数由
内域 Eq. (23) 与外域 Eq. (24) 共同约束。新测试确认了方阵维度、未知量标签、有限解和相对残差。

Gate 1 仍为 `PENDING`，但缺口已经从“没有完整方阵”推进为：

1. 从方阵解中恢复体面势和压力；
2. 加入前进速度梯度项；
3. 加入端部项；
4. 沿站位装配 `A33, B33, A35, B35, A53, B53, A55, B55`；
5. 用 Wigley III 数字化曲线跑 Ma 2005 coefficient gate。

## 2026-07-31 进展：A1 Eq. (30) 压力恢复和单站广义力

在 matched square system 之后，新增从方阵解到体面压力和单站广义力的最小闭环：

| 接口 | 作用 |
|---|---|
| `split_matched_section_solution()` | 按 `psi_body, psi_n_inner_free_surface, psi_control, psi_n_control` 切分方阵解 |
| `recover_body_pressure_from_matched_solution()` | 按 A1 Eq. (30) 从体面势恢复复压力；`U * partial phi / partial x` 作为显式可传入项 |
| `integrate_section_heave_pitch_force()` | 将体面压力积分成单站 heave 力和 pitch 力矩 |
| `pressure_force_to_added_mass_damping()` | 按 A1 Eq. (33) 将复广义力转换为 added mass 和 damping |

当前压力恢复已经可测试，但仍只是单站链条。下一步必须把相邻站位的势、压力和力组合起来，处理前进速度梯度项、
端部项，并装配整船 `A33/B33/A35/B35/A53/B53/A55/B55`。

## 2026-07-31 进展：A1 站位梯度与整船 heave/pitch 系数装配

在单站压力恢复之后，Gate 1 又补上了从站位链条走向整船频域系数的基础接口：

| 接口 | 作用 | 当前验收边界 |
|---|---|---|
| `estimate_body_potential_x_gradient()` | 对相邻站位的体面势做纵向数值梯度，给 `recover_body_pressure_from_matched_solution()` 的 `U * partial phi / partial x` 项提供输入 | 已通过线性场回归测试；仍需接入真实 matched station sweep 后检查面元对应、站位加密和噪声 |
| `StationPotentialGradient` | 保存站位、体面势梯度和 `ValidityReport` | 状态为 `a1_station_body_potential_x_gradient_not_benchmark_validated` |
| `assemble_whole_ship_heave_pitch_coefficients()` | 沿船长积分每站 heave-mode 与 pitch-mode 广义力，输出整船 2x2 复广义力矩阵、added mass 矩阵和 damping 矩阵 | 已通过合成站位力与端部项注入测试；端部项可由 Eq. (32) helper 或外部矩阵传入，但仍未通过文献曲线验收 |
| `WholeShipHeavePitchAssembly.coefficient_dict()` | 以 `A33/B33/A35/B35/A53/B53/A55/B55` 名称导出系数，便于后续 Wigley III gate 和报告生成 | 状态为 `a1_whole_ship_heave_pitch_coefficients_no_benchmark_gate` |
| `assemble_heave_pitch_from_matched_station_solutions()` | 对一组 heave-mode 与 pitch-mode matched station solution 批量恢复压力、积分单站力，并调用整船装配接口 | 已通过合成站位势场回归测试；它只接收已求出的 station solution，不声称真实 BIE station solve 已完成 |
| `MatchedStationHeavePitchSweep` | 汇总站位势梯度、每站压力、每站广义力和整船系数 | 状态为 `a1_matched_station_sweep_pipeline_no_benchmark_gate` |
| `compute_heave_pitch_stokes_end_term_force_matrix()` | 按 A1 Eq. (32) 的 `C_A` 轮廓项计算 heave/pitch 2x2 端部广义力矩阵 | 已通过合成轮廓势场回归测试；端部站位选取、方向和符号仍需 Wigley III coefficient gate 复核 |
| `solve_station_hull_heave_pitch_matched_sweep()` | 从 `StationHull` 直接构造每站体面、自由面、控制面和历史核，按艏到艉顺序求 heave/pitch matched solution，并输出整船系数 | 已通过小型 Wigley III sweep 回归测试；默认会推进非零内自由面势，但未通过 Ma 2005 曲线和网格加密验收 |
| `StationHullMatchedHeavePitchSweep` | 保存 active station、求解顺序、每站条件数/残差、自由面势/高程轨迹、端部项和整船装配结果 | 状态为 `a1_station_hull_matched_sweep_free_surface_marching_not_benchmark_validated` |
| `assemble_frequency_domain_from_matched_station_hull()` | 将 matched StationHull sweep 的 heave/pitch 2x2 辐射块嵌入标准 6DOF `FrequencyDomainHydrodynamics` | 已通过小型 Wigley III 频域契约测试；仅填充 heave/pitch radiation 和静水恢复力，diffraction/excitation 仍为零 |
| `matched-wigley-sensitivity` CLI | 读取 Ma 2005 Wigley III 数字化系数表，调用 matched StationHull sweep，输出 `matched_wigley_sensitivity.csv`、`matched_wigley_sensitivity_summary.csv` 和 `matched_wigley_sensitivity_best_cases.csv` | 已通过 A33 第一行 smoke 和自由面/端部项 2x2 矩阵 smoke；当前小网格 A33 仍未达 gate，但 best-case 摘要已能定位自由面 marching 与端部项对误差的影响 |

这一步把“单个 station 可以恢复压力”的结果推进为“多个 station 可以被统一装配”。但 Gate 1 仍是 `PENDING`，原因有三点：

1. 当前纵向梯度是基础数值差分接口，尚未在真实站位 marching 解上做网格收敛和噪声控制。
2. 当前端部项已有 `C_A` 轮廓积分 helper，但哪个 station 应作为物理端部、轮廓方向和符号仍需通过 Wigley III 误差门槛确认。
3. 当前 `StationHull` sweep 已经可以跑通小型 Wigley 几何、推进非零内自由面势、输出标准频域对象，并通过 `matched-wigley-sensitivity` 与 Ma 2005 数字化表形成诊断 CSV；2x2 smoke 显示关闭自由面 marching 的粗网格 A33 反而更接近第一行基准，说明当前自由面 marching/历史核幅值、符号或归一化仍需校准。diffraction/excitation、端部方向和系数归一化仍要用 Wigley III 的完整水动力系数曲线完成误差验收，因此不能把它称为完整 Ma-Duan-Song 2.5D 内核。

2026-07-31 又补上了 sensitivity summary 的稳健化输出：

| 新增输出 | 用途 |
|---|---|
| `matched_wigley_sensitivity_summary.csv` | 按 case 和 coefficient 汇总 pass/fail/error 数、误差倍率、残差和条件数 |
| `matched_wigley_sensitivity_best_cases.csv` | 对每个 coefficient 自动选出当前扫描矩阵中误差最小的诊断组合，便于快速定位下一轮校准方向 |
| `--compare-free-surface-marching` / `--compare-end-term` / `--compare-end-term-signs` | 在同一 CLI 运行中同时比较自由面 marching 开/关、A1 Eq. (32) 端部项开/关和 `+C_A/-C_A` 符号 |

对应冒烟输出目录为 `outputs/matched_wigley_sensitivity_matrix_smoke`。A33 第一行的当前 best case 为 `st5_bp8_fs4_cp4_r2p0_h2_zerofs_end`，`median_gate_error_ratio=2.322`，仍为 `FAIL`，但相比开启自由面 marching 的 `50.870` 已显著缩小。这一结果只能用于误差定位，不能作为关闭自由面物理项的依据。

端部项符号 smoke 输出目录为 `outputs/matched_wigley_endterm_sign_smoke`。在同一 A33 第一行、关闭自由面 marching 的粗网格条件下，`+C_A`、`-C_A` 和 `noend` 的 `computed_value` 均为 `0.6517`，说明这个单点误差当前不由端部项符号主导；后续仍需在 `A35/A53/A55` 等耦合/转动系数上继续检查端部项影响。

耦合/纵摇端部项 smoke 输出目录为 `outputs/matched_wigley_coupling_endterm_sign_smoke`，对 `A35/A53/A55` 各取第一行并比较 `+C_A`、`-C_A` 和 `noend`。当前粗网格结论如下：

| coefficient | 当前 best case | 参考值 | 计算值 | gate error ratio | 诊断含义 |
|---|---|---:|---:|---:|---|
| `A35` | `+C_A` | `-0.200` | `-0.0931` | `1.782` | 端部项正号能改善 heave force due to pitch 的符号和幅值，但仍未达 30% 耦合项误差门槛 |
| `A53` | 三种端部设置相同 | `0.150` | `3.16e-05` | `3.333` | 当前 pitch moment due to heave 几乎没有被端部项改变，说明问题更可能在力矩臂、广义力定义或主体压力装配 |
| `A55` | `-C_A` | `0.063` | `0.0487` | `1.513` | 反号端部项明显优于正号和 noend，但仍未达 15% 对角项误差门槛 |

因此端部项不能用一个全局符号简单修正。下一轮应拆分检查 `A35` 与 `A55` 的 lever arm、pitch radiation normal velocity、端部轮廓方向和 pitch moment 正负约定。

2026-07-31 又新增 pitch/端部约定矩阵 smoke：`outputs/matched_wigley_pitch_convention_smoke`。该矩阵对 `A35/A53/A55` 各取第一行，在关闭自由面 marching 的粗网格下扫描：

| 诊断参数 | 含义 |
|---|---|
| `pitch_radiation_sign` | pitch 模态体边界条件整列符号 |
| `pitch_radiation_lever_sign` | pitch 模态中 `LCG-x` 力矩臂的符号 |
| `pitch_forward_speed_sign` | pitch 模态前进速度项 `U` 的符号 |
| `pitch_moment_sign` | pitch 广义力矩行中 `LCG-x` 力矩臂的符号 |
| `end_station` / `end_term_scale` | `C_A` 端部站位和 `+C_A/-C_A/noend` |

同时，`matched_wigley_sensitivity.csv` 已新增 `computed_body_integral_value` 和 `computed_end_term_value`，用于把最终无量纲系数拆成“沿船主体积分”和“端部项”两部分。当前 best-detail 摘要为：

| coefficient | reference | computed | body integral | end term | gate error ratio | 诊断结论 |
|---|---:|---:|---:|---:|---:|---|
| `A35` | `-0.200` | `-0.0931` | `-2.78e-05` | `-0.0931` | `1.782` | 当前 A35 几乎完全来自端部项；主体 pitch 模态压力积分贡献过小 |
| `A53` | `0.150` | `3.16e-05` | `3.16e-05` | `0.0` | `3.333` | A53 缺口不是端部项造成的，而是 heave 模态压力到 pitch moment 的主体积分几乎没有形成 |
| `A55` | `0.063` | `0.0560` | `0.00365` | `0.0524` | `0.740` | A55 在该粗网格单点已进入 15% gate，但主要依赖端部项和 pitch moment 反号诊断组合，不能外推为完整通过 |

因此下一步的 A1 优先级进一步收敛为：

1. 检查 `A53` 的 heave-mode pressure distribution、`U * partial phi / partial x` 梯度项和 pitch moment generalized force 装配；
2. 检查 `A35` 的 pitch-mode 主体积分为何几乎为零，只靠端部项给出主要幅值；
3. 在上述两点修正前，不把 `A55` 的单点过 gate 视为整体验收。

随后新增 `outputs/matched_wigley_free_surface_a53_smoke`，在同样的 `A35/A53/A55` 第一行上比较自由面 marching 开/关。该 smoke 表明：

| coefficient | best setting | computed | body integral | end term | gate error ratio | 诊断含义 |
|---|---|---:|---:|---:|---:|---|
| `A53` closed/free-surface-off | `zerofs` | `3.16e-05` | `3.16e-05` | `0.0` | `3.333` | 无自由面 marching 时几乎没有 heave-to-pitch 主体力矩 |
| `A53` free-surface-on 示例 | `fsm` | `1.306` | `1.306` | `0.0` | `25.689` | 自由面 marching 能产生前后不对称力矩，但当前幅值远大于 Ma 2005 参考 |

这说明 A53 的问题不是“完全没有机制”，而是自由面历史项/内自由面 marching 的幅值、时间步、历史核或符号校准仍不正确。下一步应优先对 `advance_free_surface_state()`、`TransientFreeSurfaceHistory.convolution_rhs()`、控制面半径和 `dt=dx/U` 进行网格/时间步收敛扫描。

2026-07-31 继续新增自由面路径诊断参数：

| 参数 | 作用位置 | 默认值 | 说明 |
|---|---|---:|---|
| `time_step_scale` | `dt = dx/U` 映射后统一缩放 | `1.0` | 用于检查局部时间步是否控制自由面历史项幅值 |
| `free_surface_velocity_scale` | `advance_free_surface_state()` 中进入自由面高程更新的法向速度 | `1.0` | 用于检查内自由面 normal derivative 是否被过量推进 |
| `history_rhs_scale` | `TransientFreeSurfaceHistory.convolution_rhs()` 的 Eq. (24) 历史卷积右端 | `1.0` | 用于检查外域控制面历史项是否主导误差 |

输出目录 `outputs/matched_wigley_a53_free_surface_scale_smoke` 对 `A53` 第一行扫描了上述三个参数。结果显示：

| best setting | reference | computed | gate error ratio | 诊断结论 |
|---|---:|---:|---:|---|
| `time_step_scale=1.0`、`free_surface_velocity_scale=0.1`、`history_rhs_scale=0.0` | `0.150` | `0.136` | `0.305` | `A53` 单点进入 30% 耦合项门槛；主控因素是自由面速度推进幅值，历史 RHS 从 `0` 到 `1` 的影响很小 |

随后用 `outputs/matched_wigley_fvscale_joint_smoke` 检查 `A33/A35/A53/A55` 各第一行的副作用。固定 `free_surface_velocity_scale=0.1` 后：

| coefficient | reference | best computed | gate error ratio | 说明 |
|---|---:|---:|---:|---|
| `A33` | `1.000` | `1.472` | `3.144` | 仍明显失败 |
| `A35` | `-0.200` | `-0.107` | `1.547` | 较接近但未过 30% 耦合项门槛 |
| `A53` | `0.150` | `0.136` | `0.305` | 单点通过 |
| `A55` | `0.063` | `0.0938` | `3.259` | 反而明显失败 |

因此 `free_surface_velocity_scale=0.1` 不能作为全局校正常数。它只说明当前自由面 normal derivative 的推进幅值确实是 A53 的主控误差源；要通过 Gate 1，下一步必须回到自由面边界条件、内外域匹配尺度、Green 函数归一化和时间步映射本身，而不是把 scale 写成生产参数。

随后对 A1 Eq. (21)-(22) 做了一个真实实现修正：原 station sweep 在第一站求出自由面 normal derivative 后，直接用 Eq. (19) 全步推进自由面高程；但 A1 的初始条件要求第一步为

```text
zeta(dt/2) = zeta(0) + psi_z(0) * dt / 2
psi(dt)    = psi(0) - g * zeta(dt/2) * dt
```

因此第一步应使用 `initialize_free_surface_state()`，而不是 `advance_free_surface_state()`。代码已修正，并在 `tests/test_unified_architecture.py` 中增加回归检查：第二个被求解站位的自由面势必须等于 `-0.5 * g * psi_z(first_station) * dt^2`。

修正后新增输出目录：

| 输出目录 | 作用 | 关键观察 |
|---|---|---|
| `outputs/matched_wigley_free_surface_initial_step_fix_smoke` | 比较首步修正后的自由面开/关结果 | `A53` 自由面开启示例从修正前约 `1.306` 降到约 `0.939`，说明首步半步条件确实降低了过推，但仍远高于参考 `0.150` |
| `outputs/matched_wigley_a53_initial_step_fix_scale_smoke` | 重新扫描 `time_step_scale/free_surface_velocity_scale/history_rhs_scale` | 最接近 A53 的组合变为 `time_step_scale=0.75`、`free_surface_velocity_scale=0.25`、`history_rhs_scale=0.0`，得到 `A53=0.136`，`gate_error_ratio=0.312` |

这一步是公式一致性修正；它不能单独完成 Gate 1，但把自由面过推的一部分从“经验 scale”推进为“首步时间层错误已修正”。剩余问题仍集中在内自由面 normal derivative 的尺度、控制面历史核和 station/time 网格一致性。

## 2026-07-31 进展：A1 推荐网格审计与 A53 站位收敛诊断

在首步自由面时间层修正之后，又补上了 A1 网格建议审计。`matched-wigley-sensitivity` 的 detail、summary 和 best-case 输出现在会记录：

| 审计字段 | 判据 |
|---|---|
| `a1_control_radius_ok` | 控制面半径至少为 `3B` |
| `a1_inner_free_surface_panels_ok` | 内自由面面元数至少为 `11` |
| `a1_outer_or_control_panels_ok` | 外自由面或控制面代理面元数至少为 `9` |
| `a1_station_count_ok` | `Fn_L <= 0.25` 时至少 `60` 个站位；较高速度诊断至少 `40` 个站位 |
| `a1_grid_recommendation_status` | 所有条件满足时为 `A1_GRID_RECOMMENDED`，否则为 `A1_GRID_COARSE_DIAGNOSTIC` |

两个新增诊断输出目录为：

| 输出目录 | 目的 | 关键结果 |
|---|---|---|
| `outputs/matched_wigley_a1_grid_a53_smoke` | 用满足 A1 推荐门槛的网格重新计算 A53 第一行 | `station_count=41`、`free_surface_inner_panels=12`、`control_surface_panels=10`、`control_radius=3B` 时，审计状态为 `A1_GRID_RECOMMENDED`，但 `A53=5.282`，参考值为 `0.150`，`gate_error_ratio=114.039` |
| `outputs/matched_wigley_a53_station_count_grid_sweep` | 固定 A1 推荐级面元和控制面半径，只扫站位数 | `station_count=5/11/21/41` 时，`A53` 约为 `0.518/3.556/3.951/5.282`，误差随站位加密放大 |

这一步给出的判断比单纯 smoke test 更硬：当前 A53 偏差不能归因于“网格太粗”。相反，在满足 A1 推荐级别的控制面半径和面元数后，站位加密会积累更大的 heave-to-pitch 主体力矩。这提示问题更可能位于以下环节：

1. 从纵向站位到局部时间的 `dt=dx/U` 映射和首站/后续站时间层衔接；
2. 内自由面 normal derivative 进入 `zeta` 与 `psi` 推进时的尺度或符号；
3. 外域瞬态 Green 函数历史核与控制面法向导数匹配的归一化；
4. heave-mode 压力场沿站位积分为 pitch moment 时的力矩臂和端部处理。

因此 Gate 1 仍为 `PENDING`。下一轮不应把经验 scale 固化为生产参数，而应针对上述四个链条做逐项守恒量、单位量纲和局部解析解检查。

## 2026-07-31 进展：A53 站位级贡献诊断

为避免只盯着整船 `A53` 一个最终数字，又新增 `matched_wigley_station_diagnostics.csv`。CLI 开关为：

```bash
python -m planing_seakeeping.cli matched-wigley-sensitivity ... --write-station-diagnostics
```

该文件逐站输出局部力密度、梯形积分权重、累计主体积分、自由面势/高程范数、内自由面法向导数范数、压力范数、条件数、残差和 A1 网格审计字段。它的作用不是替代 gate，而是解释“整船系数为什么失败”。

本轮针对 `outputs/matched_wigley_a53_station_diagnostics` 运行了 A1 推荐网格 A53 第一行诊断：

| 指标 | 结果 | 含义 |
|---|---:|---|
| 有效湿站数 | `39` | 原始 `41` 个 Wigley 站位中，首尾零湿面积站位不进入压力积分 |
| 最终累计主体积分 | `5.282` | 与 sensitivity best-case 中的 A53 一致，说明 station CSV 与整船装配闭合 |
| 最大单站归一化贡献 | `1.572`，位于 `station_local_index=2` | 靠艉晚求解站位给出异常大的正贡献 |
| 最大自由面势范数 | `30.955`，位于 `station_local_index=2` | 大贡献站位也对应大的自由面势输入 |
| 最大内自由面法向导数范数 | `306.169`，位于 `station_local_index=1` | 自由面推进速度在靠艉晚期站位出现强峰值 |

站位排序显示，最大贡献集中在 `station_local_index=1-4`，这些站位对应 `x_from_bow≈2.625-2.850 m`，也就是靠艉区域；同时它们的 `solve_order_rank≈34-37`，说明它们是在 bow-to-stern marching 的后期被求解。这个结果进一步支持上一节判断：A53 的过大值更像是自由面历史推进在靠艉累积放大，而不是全船压力积分统一偏移。

下一轮最小可验证目标因此进一步具体化为：

1. 对 station 1-4 单独输出 Eq. (21)-(24) 每一步的 `zeta`、`psi`、`psi_z` 和控制面历史 RHS，检查是否有单步过大或符号翻转；
2. 对比 `free_surface_velocity_scale=1.0/0.25/0.1` 时这些站位的范数变化，确认 scale 改变的是局部速度输入、历史 RHS，还是压力梯度响应；
3. 在靠艉站位上加入局部解析或半解析自由面响应检查，避免只用整船系数反推错误来源。

## 2026-07-31 进展：Eq. (21)-(24) marching 中间量输出

在 station 级贡献诊断之后，又把自由面 marching 的关键中间量直接写入 `StationHullMatchedHeavePitchSweep` 和 `matched_wigley_station_diagnostics.csv`：

| 新增字段 | 含义 |
|---|---|
| `free_surface_update_kind` | 当前站位求解后使用的自由面更新时间层，取值包括 `initialize_eq21_22`、`advance_eq19_20` 和 `disabled` |
| `outer_history_rhs_norm_before_solve` | 当前站位求解前 A1 Eq. (24) 外域控制面历史卷积右端范数 |
| `free_surface_potential_norm_after_update` | 当前站位求解并按 Eq. (19)-(22) 推进后，将传递给下一站的自由面势范数 |
| `free_surface_elevation_norm_after_update` | 当前站位推进后的自由面高程范数 |
| `free_surface_potential_growth_ratio` | `after_update / before_solve`，用于判断单步是否放大自由面势 |
| `control_potential_norm`、`control_normal_derivative_norm` | 控制面匹配解的势和法向导数范数，用于判断 Eq. (24) 是否在局部产生异常边界值 |

刷新后的 `outputs/matched_wigley_a53_station_diagnostics` 表明：

| 观察项 | 数值 | 解释 |
|---|---:|---|
| 最大 A53 单站正贡献 | `1.572`，station `2` | 该站位仍是整船 A53 过大的主要来源 |
| 最大外域历史 RHS 范数 | `0.232`，station `1` | 历史卷积峰值位于最大正贡献的相邻靠艉站 |
| 最大 after-update 自由面势范数 | `30.955`，station `3` 推进后 | 说明 station `3` 的推进把高自由面势继续传递给 station `2` |
| station `1` 内自由面法向导数范数 | `306.169` | 这是当前靠艉区域最大的自由面速度峰值 |
| station `1-6` 更新时间层 | 全部为 `advance_eq19_20` | 异常不是首站 `initialize_eq21_22` 造成，而是在后期全步推进中积累 |

这一轮把下一步目标又缩小了一格：应优先检查 Eq. (19)-(20) 的全步更新和 Eq. (24) 历史 RHS 在靠艉 station `1-3` 的相位、尺度和符号，而不是继续审查首步 Eq. (21)-(22)。如果要做最小实验，应分别固定 `outer_history_rhs=0`、`free_surface_velocity_scale=0`、关闭 `U * partial phi / partial x` 压力梯度，观察 station `2` 的 `1.572` 单站贡献到底由哪条通道触发。

## 2026-07-31 进展：A53 三通道拆分实验

为执行上一节的最小实验，新增 `pressure_gradient_scale` 诊断开关。该开关只作用于 A1 Eq. (30) 中的 `U * partial phi / partial x` 压力梯度项；默认值为 `1.0`，设为 `0.0` 时不改变船速、pitch 边界条件或 encounter 频率，只关闭压力恢复中的前进速度梯度贡献。CLI 新增参数为：

```bash
--pressure-gradient-scales 1.0 0.0
```

随后运行了三个诊断矩阵：

| 输出目录 | 目的 |
|---|---|
| `outputs/matched_wigley_a53_channel_split` | A1 推荐网格下，对 A53 第一行同时扫描 `free_surface_velocity_scale=1/0`、`history_rhs_scale=1/0`、`pressure_gradient_scale=1/0` |
| `outputs/matched_wigley_a53_free_surface_velocity_sign_scale` | 扫描自由面速度推进的正负号和粗尺度，判断是否只是符号错误 |
| `outputs/matched_wigley_a53_free_surface_velocity_narrow_scale` | 在 `0.02-0.05` 范围内窄扫，估计单点贴合 A53 所需的经验尺度 |

三通道拆分结果如下：

| 设置 | A53 计算值 | 解释 |
|---|---:|---|
| `fv=1, hr=1, pg=1` | `5.282` | 当前 baseline，远高于参考 `0.150` |
| `fv=1, hr=0, pg=1` | `5.279` | 关闭外域历史 RHS 几乎不改变结果 |
| `fv=1, hr=1, pg=0` | `5.282` | 关闭 `U * partial phi / partial x` 压力梯度完全不改变结果 |
| `fv=0, hr=1, pg=1` | `3.08e-07` | 关闭内自由面速度推进后，A53 几乎归零 |
| `fv=0, hr=0, pg=1` | `≈0` | 内自由面速度推进关闭时，历史 RHS 也无法产生主要 A53 |

station `2` 的局部贡献也给出同样结论：`fv=1` 时该站归一化贡献约 `1.572`，`fv=0` 时降到约 `0.00907`；`hr=0/1` 和 `pg=0/1` 的差异均可忽略。因此 A53 异常主控通道已经明确为 Eq. (19)-(20) 中内自由面 normal derivative 对自由面势/高程的推进，而不是外域历史 RHS 或压力梯度项。

自由面速度正负号 sweep 进一步表明：

| `free_surface_velocity_scale` | A53 |
|---:|---:|
| `-1.0` | `-6.749` |
| `-0.5` | `-3.216` |
| `-0.25` | `-1.330` |
| `-0.1` | `-0.504` |
| `0.0` | `≈0` |
| `0.1` | `0.494` |
| `0.25` | `1.240` |
| `0.5` | `2.533` |
| `1.0` | `5.282` |

这说明问题不是简单符号反了；负号会产生更大的负向偏差。窄扫显示 `free_surface_velocity_scale≈0.03` 可让 A53 第一行接近参考值：

| `free_surface_velocity_scale` | A53 | gate error ratio |
|---:|---:|---:|
| `0.02` | `0.0990` | `1.132` |
| `0.03` | `0.14846` | `0.034` |
| `0.04` | `0.19782` | `1.063` |
| `0.05` | `0.24715` | `2.159` |

但这不能作为生产修正。用同一 `fv=0.03`、A1 推荐网格检查 `A33/A35/A53/A55` 第一行，结果为：

| coefficient | reference | computed | gate status |
|---|---:|---:|---|
| `A33` | `1.000` | `1.410` | `FAIL` |
| `A35` | `-0.200` | `-0.540` | `FAIL` |
| `A53` | `0.150` | `0.148` | `PASS` |
| `A55` | `0.063` | `-0.330` | `FAIL` |

因此 `fv=0.03` 只是定位尺度误差的证据，不是全局校准常数。下一轮应检查内自由面 normal derivative 的物理归一化、自由面面元法向方向、Eq. (19)-(20) 中 `zeta` 与 `psi` 的时间层关系，以及 body/free/control 三类边界在 matched system 中的单位一致性。

## 2026-07-31 进展：按水线裁剪内自由面网格

回查 A1 第 3.3 和第 3.5 节后，发现当前实现与论文网格还有一个重要差别：A1 的内自由面网格从船体水线交点向外布置，并且由于水线随站位变化，`zeta` 和 `psi` 需要在相邻站位之间插值；旧实现使用一条固定的 full-width 自由面 `[-R, R]`，这条自由面穿过了船体水线内部区域，等价于把船体内部不属于自由面的区域也参与 Eq. (19)-(20) 推进。

为此新增了诊断模式：

| 接口/参数 | 作用 |
|---|---|
| `build_waterline_clipped_free_surface_geometry()` | 生成左右两段水线外自由面，跳过 `[-B(x)/2, B(x)/2]` 船体水线内部区间 |
| `resample_free_surface_state()` | 将上一站的 `zeta` 与 `psi` 插值到当前站位的自由面 y 网格 |
| `clip_inner_free_surface_to_waterline` | `StationHullMatchedHeavePitchSweep` 和 sensitivity case 的布尔开关 |
| `--clip-inner-free-surface-to-waterline` | CLI 中启用水线裁剪自由面 |
| `--compare-inner-free-surface-clipping` | CLI 中同时比较 full-width 与 waterline-clipped 两种自由面网格 |

新增输出目录：

| 输出目录 | 目的 |
|---|---|
| `outputs/matched_wigley_a53_free_surface_clipping_compare` | A53 第一行 full-width 与 waterline-clipped 自由面直接对比 |
| `outputs/matched_wigley_joint_clipped_recommended` | 用 waterline-clipped 模式检查 `A33/A35/A53/A55` 第一行联合表现 |

A53 对照结果非常明显：

| 模式 | A53 | gate error ratio | station 2 单站贡献 | station 2 自由面势范数 |
|---|---:|---:|---:|---:|
| full-width free surface | `5.282` | `114.039` | `1.572` | `30.955` |
| waterline-clipped free surface | `0.336` | `4.128` | `0.0699` | `1.332` |

也就是说，仅把内自由面从“穿过船体内部”改为“水线外两段”后，A53 误差降低了一个数量级以上，station 2 的异常局部贡献从 `1.572` 降到 `0.0699`，自由面势范数从 `30.955` 降到 `1.332`。这证明 A1 的水线外自由面布置是当前 Ma-Duan-Song 内核里缺失的关键物理结构，不是可忽略的网格细节。

但联合检查仍未通过：

| coefficient | reference | clipped computed | status |
|---|---:|---:|---|
| `A33` | `1.000` | `4.558` | `FAIL` |
| `A35` | `-0.200` | `-0.712` | `FAIL` |
| `A53` | `0.150` | `0.336` | `FAIL` |
| `A55` | `0.063` | `0.0532` | 接近但仍 `FAIL` |

因此水线裁剪不能直接宣布 Gate 1 通过。它给出的下一步方向是：默认生产内核应逐步迁移到 station-wise waterline-clipped 自由面和插值框架，但还必须继续处理 A1 中 `n2i/n2e` 内外自由面分区、端部项、pitch 耦合约定以及全系数曲线收敛。

## 2026-07-31 进展：A1 n2i/n2e 两区段水线外自由面诊断

在 station-wise 水线裁剪之后，又把 A1 第 3.3 节中“水线附近内区 + 外区延伸”的网格思想落实为可开关诊断路径。新增接口和参数为：

| 接口/参数 | 作用 |
|---|---|
| `build_two_zone_waterline_free_surface_geometry()` | 在每个站位的左右水线外区域生成两区段自由面网格：水线到最大水线半宽附近为内区，最大水线半宽到控制面半径为外区 |
| `two_zone_inner_free_surface` | `StationHullMatchedHeavePitchSweep` 和 `MatchedWigleySensitivityCase` 中记录是否启用两区段水线外网格 |
| `--two-zone-inner-free-surface` | CLI 中对 waterline-clipped 自由面启用两区段分布 |
| `--compare-two-zone-inner-free-surface` | CLI 中同时比较 one-zone 与 two-zone 水线外自由面 |

实现时增加了一个必要的数值保护：当局部水线半宽已经非常接近最大水线半宽时，强行保留极短内区会产生退化小面元。第一次直接两区段试算曾把最小面元长度压到 `5.4e-5 m`，条件数升至 `1.0e5`，自由面势范数放大到 `1.1e10`，这属于网格病态，不是物理响应。因此当前函数在内区或外区短于该侧跨度约 `10%` 时，会把该侧面元重新均匀分布在剩余水线外区间内，避免零长度或近零长度面元。

同时，`resample_free_surface_state()` 已从单一全宽插值升级为自动分段插值：当源网格或目标网格呈现左右两段自由面时，左舷目标点只从左舷源自由面继承 `zeta/psi`，右舷目标点只从右舷源自由面继承 `zeta/psi`。这样可以避免水线宽度变化时把自由面状态跨过船体内部间隙进行线性插值。`tests/test_unified_architecture.py` 中新增了回归测试：目标点落在新水线附近但位于上一站自由面间隙内时，插值结果应钳制到同侧水线端点，而不是从左舷穿过中心插到右舷。

新增输出目录如下：

| 输出目录 | 目的 |
|---|---|
| `outputs/matched_wigley_a53_two_zone_free_surface_compare` | 在 `station_count=41`、`free_surface_inner_panels=24`、`control_surface_panels=10`、`control_radius=3B` 条件下比较 one-zone 与 two-zone 水线外自由面 |
| `outputs/matched_wigley_joint_two_zone_recommended` | 同一网格下检查 `A33/A35/A53/A55` 四个核心第一行系数 |

A53 单点对照结果为：

| 模式 | A53 | reference | gate error ratio | 最大条件数 | 最大 after-update 自由面势范数 |
|---|---:|---:|---:|---:|---:|
| one-zone waterline-clipped | `0.3685` | `0.150` | `4.856` | `113.95` | `2.874` |
| two-zone waterline-clipped | `0.4259` | `0.150` | `6.131` | `465.54` | `12.301` |

四系数联合结果为：

| coefficient | reference | one-zone computed | two-zone computed | 结论 |
|---|---:|---:|---:|---|
| `A33` | `1.000` | `4.662` | `4.633` | 两者均失败，两区段略改善但仍远超 15% 门槛 |
| `A35` | `-0.200` | `-0.761` | `-1.270` | 两区段使 pitch-to-heave 耦合更差 |
| `A53` | `0.150` | `0.369` | `0.426` | 两区段未改善 heave-to-pitch 耦合 |
| `A55` | `0.063` | `0.0343` | `-0.510` | 两区段使纵摇项符号和幅值都偏离 |

因此，两区段网格当前的意义是“诊断能力已实现”，不是 Gate 1 修正。它证明了程序已经能够表达 A1 的 `n2i/n2e` 网格概念，也暴露出当前 matched BIE、站位间自由面插值和压力装配对近水线面元分布仍较敏感。下一轮不应继续通过面元分布经验调参追逐单个系数，而应把验收目标放在三个更硬的条件上：

1. one-zone 与 two-zone 的结果在网格加密后必须表现出有界收敛，而不能在 `A35/A55` 上出现符号和幅值失控；
2. 站位间 `zeta/psi` 已实现左右分段插值，下一步还要扩展为显式区分内区/外区的 `n2i/n2e` 分区插值，避免跨退化短分区传播自由面状态；
3. `A33/A35/A53/A55` 四项必须共同改善，任何只让 `A53` 单点变好的设置都只能作为定位证据，不能进入生产默认。

## 2026-07-31 进展：A1 Eq.24 历史卷积积分规则诊断

回到 A1 第 3.4 节后，发现文献文字明确说明：Eq. (16) 中瞬态自由面 Green 函数的卷积积分采用梯形积分法；而此前 `TransientFreeSurfaceHistory.convolution_rhs()` 对所有保留历史滞后项使用等权求和，更接近矩形规则。为把这个差异变成可验证程序路径，新增：

| 接口/参数 | 作用 |
|---|---|
| `quadrature_rule` | `TransientFreeSurfaceHistory.convolution_rhs()` 的参数，支持 `rectangle` 和 `trapezoid` |
| `history_convolution_rule` | `MatchedSectionBoundaryData`、`StationHullMatchedHeavePitchSweep`、`MatchedWigleySensitivityCase` 中记录历史卷积积分规则 |
| `--history-convolution-rules` | CLI sensitivity 中同时比较 `rectangle` 与 `trapezoid` |

实现选择为：`trapezoid` 默认半权最老的保留滞后项；当前时刻端点由 Eq. (24) 左端的瞬时 log-kernel 项表达，不再作为历史数组中的一个普通 past point 参与 RHS。`rectangle` 保留为诊断对照，便于复现旧结果。

新增输出目录：

| 输出目录 | 目的 |
|---|---|
| `outputs/matched_wigley_history_quadrature_compare` | 在 waterline-clipped one-zone 推荐级设置下，对 `A33/A35/A53/A55` 比较 `rectangle` 与 `trapezoid` 历史卷积规则 |

四系数结果为：

| coefficient | reference | rectangle | trapezoid | 诊断结论 |
|---|---:|---:|---:|---|
| `A33` | `1.000` | `4.662` | `4.659` | 变化极小，仍 FAIL |
| `A35` | `-0.200` | `-0.761` | `-0.756` | 变化极小，仍 FAIL |
| `A53` | `0.150` | `0.3685` | `0.3673` | 变化极小，仍 FAIL |
| `A55` | `0.063` | `0.0343` | `0.0377` | 略改善，但仍 FAIL |

站位诊断显示，`trapezoid` 确实降低了历史 RHS 峰值，例如 A53 的最大 `outer_history_rhs_norm_before_solve` 从 `0.1021` 降到 `0.0695`，但自由面势范数和单站力贡献几乎不随之变化。这与前一轮三通道拆分结论一致：当前 Gate 1 主阻塞不在 Eq. (24) 外域历史 RHS 的一阶权重，而更可能在内自由面 normal derivative 推进尺度、自由面/控制面匹配单位、pitch 广义力装配和端部项约定。

因此下一轮 Gate 1 条件更新为：默认历史卷积使用 `trapezoid`，但任何声称修正 Gate 1 的改动，必须在 `outputs/matched_wigley_history_quadrature_compare` 之外继续证明 `A33/A35/A53/A55` 同时改善；单纯更换历史积分权重不足以通过 Ma 2005 验收。

## 2026-07-31 进展：Eq.24 历史核 B/C 分通道诊断

在确认历史卷积权重不是主阻塞后，继续把 Eq. (24) 右端的两个历史核通道拆开：

| 诊断参数 | 对应项 | 目的 |
|---|---|---|
| `history_potential_kernel_scale` | `B^{m-k}_{ij} * psi_n` | 检查瞬态 Green 势核通道的幅值和符号 |
| `history_normal_derivative_kernel_scale` | `C^{m-k}_{ij} * psi` | 检查瞬态 Green 法向导数核通道的幅值和符号 |
| `--history-potential-kernel-scales` | CLI 参数 | 扫描 `B` 核通道 |
| `--history-normal-derivative-kernel-scales` | CLI 参数 | 扫描 `C` 核通道 |

新增输出目录：

| 输出目录 | 内容 |
|---|---|
| `outputs/matched_wigley_history_kernel_channel_compare` | A53 第一行，`B` 与 `C` 两通道分别取 `-1/0/1` 的九宫格 |
| `outputs/matched_wigley_joint_history_kernel_channel_compare` | `A33/A35/A53/A55` 第一行，`B` 与 `C` 两通道取 `-1/+1` 的四组合 |

A53 九宫格结果显示，任意历史核通道反号或关闭后，`A53` 只在 `0.360-0.369` 范围内变化，仍明显高于参考 `0.150`。即使外域历史 RHS 峰值随通道组合变化，主导的自由面势和单站力矩贡献几乎不被改变。这进一步排除了“Eq.24 历史核某一项符号反了就是 A53 主因”的可能。

四系数对照结果如下：

| `B` scale | `C` scale | A33 | A35 | A53 | A55 | 结论 |
|---:|---:|---:|---:|---:|---:|---|
| `-1` | `-1` | `4.643` | `-0.734` | `0.362` | `0.0539` | A55 单点 PASS，其他失败 |
| `-1` | `+1` | `4.638` | `-0.727` | `0.360` | `0.0585` | A55 单点 PASS，其他失败 |
| `+1` | `-1` | `4.665` | `-0.763` | `0.369` | `0.0329` | 全局失败 |
| `+1` | `+1` | `4.659` | `-0.756` | `0.367` | `0.0377` | 当前默认，仍失败 |

因此，历史核 `B` 通道反号对 `A55` 有明显局部影响，但不能作为生产默认，因为 `A33/A35/A53` 没有同步改善。这个结果把下一步重点进一步缩小到三处：

1. Eq. (24) 左端瞬时控制面项 `(A - Abar)` 与 `(B - Bbar)` 的镜像项符号、法向方向和对角项；
2. pitch generalized-force 行的力矩臂和正负约定；
3. A1 Eq. (32) 端部项与主体压力积分之间的同一 pitch 约定。

## 2026-07-31 进展：Eq.24 瞬时控制面项镜像/列符号/对角项诊断

在历史卷积权重和历史核 `B/C` 通道均未解释 Gate 1 失败后，继续检查 A1 Eq. (24) 左端的瞬时控制面项。这个位置对应控制面上当前时刻的外域匹配矩阵，文献形式可概括为 `(A - Abar)` 与 `(B - Bbar)` 两组 log-kernel 及其镜像项。如果这里的镜像符号、势列/法向导数列符号或边界积分对角项约定错误，会直接改变控制面给内域自由面反馈的相位与幅值，因此比右端历史项更可能影响 `A35/A53` 这类前后耦合系数。

新增诊断参数如下：

| 诊断参数 | 作用 |
|---|---|
| `control_image_scale` | 扫描控制面瞬时镜像项比例；`+1` 对应当前 `(kernel - image)`，`-1` 对应 `(kernel + image)` |
| `control_potential_kernel_scale` | 扫描 Eq. (24) 左端势核列的整体符号 |
| `control_normal_derivative_kernel_scale` | 扫描 Eq. (24) 左端法向导数核列的整体符号 |
| `control_diagonal_sign` | 扫描 log-kernel 自身边界对角项符号，用于区分积分方程内外侧极限约定 |
| `--control-image-scales` | CLI sensitivity 参数，批量扫描 `control_image_scale` |
| `--control-potential-kernel-scales` | CLI sensitivity 参数，批量扫描势核列符号 |
| `--control-normal-derivative-kernel-scales` | CLI sensitivity 参数，批量扫描法向导数核列符号 |
| `--control-diagonal-signs` | CLI sensitivity 参数，批量扫描对角项符号 |

本轮新增两个输出目录：

| 输出目录 | 内容 |
|---|---|
| `outputs/matched_wigley_control_instant_a53_compare` | 仅检查 `A53` 第一行，扫描控制面镜像项、势列、法向导数列和对角项 |
| `outputs/matched_wigley_joint_control_image_compare` | 检查 `A33/A35/A53/A55` 第一行，在 `control_diagonal_sign=+1` 下扫描控制面镜像项和两列符号 |

`A53` 单项诊断出现了一个很强的信号：当 `control_image_scale=-1`，也就是瞬时控制面从 `(A - Abar)` 型变为 `(A + Abar)` 型、从 `(B - Bbar)` 型变为 `(B + Bbar)` 型时，部分列符号组合可以让 `A53` 从默认的约 `0.367` 降到约 `0.183-0.186`，进入耦合项 30% 门槛。更重要的是，`control_diagonal_sign=+1` 的这些组合最大条件数约 `418`，不是 `control_diagonal_sign=-1` 下 `4.176e9` 那种病态偶然解。

但四系数联合诊断说明它还不能成为生产默认：

| control image | potential column | normal-derivative column | A33 | A35 | A53 | A55 | 结论 |
|---:|---:|---:|---:|---:|---:|---:|---|
| `+1` | `+1` | `+1` | `4.659` | `-0.756` | `0.367` | `0.0377` | 当前默认，四项均失败 |
| `-1` | `+1` | `-1` | `4.026` | `-0.215` | `0.183` | `0.348` | `A35/A53` 通过，但 `A33/A55` 失败 |
| `-1` | `-1` | `+1` | `4.034` | `-0.230` | `0.186` | `0.336` | `A35/A53` 通过，但 `A33/A55` 失败 |

因此，本轮最重要的结论不是“把镜像项直接反号”，而是更精确地定位了 Gate 1 的阻塞结构：Eq. (24) 左端瞬时镜像项确实控制了 heave/pitch 耦合项的主要幅值，但当前 `A33` 对角项仍偏大约 4 倍，`A55` 在修正耦合项的同时被推得过大。这说明下一步不能只在控制面符号上继续调参，而必须同步检查三条链：

1. `A33` 对角项：复核体面 heave radiation 边界条件、内域简单 Green 函数尺度、水线裁剪自由面与控制面匹配单位；
2. `A55` 纵摇项：复核 pitch radiation normal velocity、pitch generalized-force 力矩臂、参考点和 A1 Eq. (32) 端部项是否共享同一正负约定；
3. `A35/A53` 耦合项：把 `control_image_scale=-1` 的有限条件数结果作为公式审计线索，回到 A1 Eq. (24) 推导确认镜像项在所采用法向方向下到底应为减号还是加号。

Gate 1 仍为 `PENDING`。新增诊断接口会保留，因为它们能把“历史项、自由面推进、控制面瞬时项、pitch 约定”分开验算；但任何默认设置变更都必须在 Ma 2005 Wigley III 至少首行 `A33/A35/A53/A55` 同时通过后才能进入生产路径。

## 2026-07-31 进展：A33/A55 压力分量贡献诊断

上一轮已经确认 Eq. (24) 瞬时控制面镜像项对 `A35/A53` 耦合项有强影响，但不能同时闭合 `A33/A55`。因此本轮不再继续堆叠全局 scale，而是把 A1 Eq. (30) 的压力恢复拆成两个可审计分量：

| 分量 | 程序字段 | 物理/方程含义 |
|---|---|---|
| `-rho * i * omega * phi` | `pressure_time_derivative_pa` | 势函数时间导数项，对应局部非定常压力，是传统辐射 added mass 的主来源 |
| `rho * U * partial phi / partial x` | `pressure_forward_speed_pa` | 前进速度梯度项，对应 A1 Eq. (30) 中由船体前进和站位势变化引入的压力修正 |
| 两者之和 | `pressure_pa` | 原有总压力，保持既有求解接口不变 |

同时，`MatchedSectionForceResult` 新增了 `heave_force_time_derivative_per_m`、`heave_force_forward_speed_per_m`、`pitch_moment_time_derivative_per_m` 和 `pitch_moment_forward_speed_per_m`。整船装配也新增 `time_derivative_force_matrix` 与 `forward_speed_force_matrix`，并写入 `FrequencyDomainHydrodynamics.contribution_breakdown`。因此 `matched_wigley_sensitivity.csv` 和 `matched_wigley_station_diagnostics.csv` 现在都能同时输出总贡献、时间导数贡献和前进速度贡献。

新增诊断输出目录：

| 输出目录 | 内容 |
|---|---|
| `outputs/matched_wigley_a33_a55_pressure_component_diagnostics` | 在 waterline-clipped one-zone、A1 推荐级网格下，扫描 `control_image_scale`、控制面法向导数列符号和 `free_surface_velocity_scale=0/0.03/1`，并输出 `A33/A35/A53/A55` 的压力分量贡献 |

首行四系数的代表性结果如下：

| coefficient | 最接近设置的 computed | 时间导数贡献 | 前进速度贡献 | 结论 |
|---|---:|---:|---:|---|
| `A33` | `0.886` | `0.886` | `0.000` | 关闭自由面推进时可过单点门槛，但该设置使 `A35/A53` 几乎归零；说明 `A33` 主要受 heave 模态时间导数压力控制 |
| `A35` | `-0.215` | `0.052` | `-0.267` | 通过门槛的组合主要依赖前进速度梯度项，说明 pitch radiation 到 heave force 的耦合强烈受 `U * partial phi / partial x` 控制 |
| `A53` | `0.142` | `0.142` | `0.000` | 通过门槛的组合主要来自 heave 模态时间导数压力；前进速度梯度项对该行几乎不贡献 |
| `A55` | `0.0377` | `0.181` | `-0.143` | 最接近设置仍失败，而且是两个大分量相互抵消后的结果；这指向 pitch 模态相位、力矩臂和前进速度项相对符号仍需审计 |

这个结果进一步细化了 Gate 1 的阻塞位置：

1. `A33` 不是由前进速度压力项推偏，主要要回查 heave radiation 的时间导数压力、控制面条件数和自由面推进耦合；
2. `A35` 的有效耦合来自前进速度梯度项，因此不能在不审计 `partial phi / partial x` 的站位差分和 pitch radiation body condition 的情况下修改符号；
3. `A53` 与 `A35` 不对称：`A53` 当前来自时间导数项，`A35` 当前来自前进速度项，这提示互易性/广义力装配约定仍未闭合；
4. `A55` 的错误不是单个分量爆炸，而是 `i omega phi` 与 `U partial phi / partial x` 两项抵消后的残差不对。下一步应优先检查 pitch 模态的 lever arm、forward-speed sign、body condition 里的 `U` 项，以及 A1 Eq. (32) 端部项是否应补偿这类抵消。

因此 Gate 1 的下一步硬动作更新为：用同一套分量诊断继续扫描 pitch radiation body condition、pitch generalized-force 参考点、端部项站位/方向和 `partial phi / partial x` 差分格式。任何修正必须让 `A33/A35/A53/A55` 在同一个、条件数可接受的设置下同时改善；只让其中一项通过仍只能记为 diagnostic。

## 2026-07-31 进展：A1 Eq.30 `partial phi / partial x` 差分格式诊断

A1 文献在 Eq. (31) 之后明确指出，直接对 `partial phi / partial x` 做数值差分会带来误差，因此后续引入 Stokes theorem 和 Eq. (32) 端部项来避免或补偿这类差分问题。当前程序仍保留有限差分压力梯度链条用于诊断，所以本轮把站位势函数梯度从固定 `np.gradient` 改为显式可选：

| 参数/字段 | 作用 |
|---|---|
| `pressure_gradient_scheme` | 记录 A1 Eq. (30) 中 `partial phi / partial x` 的站位差分格式 |
| `central` | 默认值，保持原来的中心差分/二阶边界差分行为 |
| `forward` | 按 `x_m` 增大方向做一阶前向差分，末站沿用相邻差分 |
| `backward` | 按 `x_m` 增大方向做一阶后向差分，首站沿用相邻差分 |
| `--pressure-gradient-schemes` | CLI sensitivity 参数，可一次扫描 `central/forward/backward` |

新增输出目录：

| 输出目录 | 内容 |
|---|---|
| `outputs/matched_wigley_pressure_gradient_scheme_compare` | 在 `free_surface_velocity_scale=1`、waterline-clipped one-zone、A1 推荐级网格下，对 `A33/A35/A53/A55` 比较三种 `partial phi / partial x` 差分格式 |

代表性结论如下：

| coefficient | central best | backward best | forward best | 结论 |
|---|---:|---:|---:|---|
| `A33` | `4.026` | `4.026` | `4.026` | `A33` 不受压力梯度格式影响，因为 heave-force 行当前没有前进速度梯度贡献 |
| `A35` | `-0.215` | `-0.213` | `-0.163` | 三者均可通过耦合项门槛，但 forward 会明显削弱前进速度贡献 |
| `A53` | `0.183` | `0.183` | `0.183` | `A53` 不受压力梯度格式影响，因为该项主要来自时间导数压力 |
| `A55` | `0.0377` | `0.0333` | `0.3009` | 三者均失败；forward 反而使 A55 大幅偏高，backward 比 central 更低 |

这说明 `partial phi / partial x` 的一阶差分方向不是 A55 失败的直接解法。A55 的问题更像是 pitch 模态中 `i omega phi` 与 `U partial phi / partial x` 两个分量的相对相位、力矩臂和端部补偿没有闭合：central 情况下 `A55=0.0377` 来自 `0.181` 的时间导数贡献与 `-0.143` 的前进速度贡献抵消；forward 改变了前进速度项符号/幅值后会让 A55 偏到 `0.3009`，说明仅换差分方向会破坏而不是修正该抵消。

因此 Gate 1 下一步进一步收敛为：保留 `pressure_gradient_scheme` 作为诊断开关，但默认仍使用 `central`；真正需要审计的是 pitch radiation body condition 中 `U m_j` 的定义、`LCG - x` lever arm 的参考点、pitch generalized-force 行的力矩正负约定，以及 Eq. (32) 端部项是否应以 Stokes 形式替代当前有限差分压力梯度链条。

## 2026-07-31 进展：pitch body condition 的 `i omega N5` / `U m5` 分通道诊断

A1 Eq. (4)-Eq. (6) 给出辐射模态体面边界条件：

```text
partial phi_j / partial N = i omega N_j + U m_j
N5 = -x Nz,    m5 = Nz
```

在当前程序约定中，pitch 模态被写成 `-(i*omega*lever + U)*Nz`，其中 `lever = LCG - x_station`。此前程序只保存二者之和，无法判断 A55 的问题来自 `i omega N5` 通道还是 `U m5` 通道。本轮新增 `pitch_radiation_normal_velocity_components()`，并在 station diagnostics 中写出：

| 字段 | 含义 |
|---|---|
| `body_condition_norm` | 当前所选辐射模态体面边界条件总范数 |
| `pitch_body_condition_oscillation_norm` | pitch 模态 `i omega N5` 通道范数 |
| `pitch_body_condition_forward_speed_norm` | pitch 模态 `U m5` 通道范数 |
| `pitch_body_condition_forward_to_oscillation_norm_ratio` | `U m5` 与 `i omega N5` 的范数比 |

新增输出目录：

| 输出目录 | 内容 |
|---|---|
| `outputs/matched_wigley_pitch_body_condition_channel_compare` | 扫描 `pitch_radiation_lever_sign = 0/+1/-1` 与 `pitch_forward_speed_sign = 0/+1/-1`，比较 `A33/A35/A53/A55` 首行结果，并输出 pitch body condition 分通道范数 |

诊断结果显示：

| 情况 | 结果 |
|---|---|
| 关闭 `i omega N5` 与关闭 `U m5` | `A35/A55` 多数归零或偏离，说明两个通道都不是可随意删除的项 |
| 默认 `pitch_forward_speed_sign=+1` | `A35=-0.215` 可通过，`A55=0.0377` 仍失败 |
| 反号 `pitch_forward_speed_sign=-1` | `A55=0.0687` 可通过，但 `A35=+0.319` 符号错误且失败 |

最佳 A55 case 的四系数为：

| coefficient | reference | computed | 结论 |
|---|---:|---:|---|
| `A33` | `1.000` | `4.026` | 失败 |
| `A35` | `-0.200` | `+0.319` | 符号错误，失败 |
| `A53` | `0.150` | `0.183` | 通过 |
| `A55` | `0.063` | `0.0687` | 通过 |

因此，`U m5` 反号不是生产修正；它只说明 A55 对 pitch forward-speed body condition 非常敏感，而 A35 对同一通道的符号要求与 A55 相冲突。下一步不能继续单独追 A55，而应检查 `T_ij` 的行列互易性：pitch radiation column、heave-force row、pitch-moment row、`N_i/m_i` 的定义是否全部处在同一坐标和正负约定中。尤其要把 Eq. (32) 中的 `rho U integral phi_j m_i ds` 与 `-rho U integral_CA phi_j N_i dl` 显式装配出来，替代当前仅靠 Eq. (30) 有限差分压力梯度的方式。

## 2026-07-31 进展：A1 Eq.32 Stokes 体积分前进速度项诊断

本轮已经把上一节提出的 Eq. (32) 显式体积分项落成代码诊断。新增 `StokesBodyForwardSpeedForceMatrix` 与 `compute_heave_pitch_stokes_body_forward_speed_force_matrix()`，按 A1 Eq. (32) 中的 `rho U integral phi_j m_i ds` 计算 heave/pitch 2x2 矩阵，并把 station-wise 密度 `force_density_by_station` 一并保留。该矩阵只作为诊断写入 `WholeShipHeavePitchAssembly.stokes_body_forward_speed_force_matrix` 和 `FrequencyDomainHydrodynamics.contribution_breakdown`，默认结果仍沿用 Eq. (30) 的压力梯度链条，避免未经验证的 Stokes 替代项直接进入生产路径。

在 heave/pitch 子块里，A1 Eq. (6) 给出 `m3=0` 与 `m5=Nz`。由于程序内部采用 `z` 向下、heave force 向上的约定，当前诊断默认把 pitch-row 的 `m5` 写成 `-normal_z`，并随 `pitch_moment_sign` 同步变号。对应新增输出列包括：

| 输出位置 | 新增字段 | 作用 |
|---|---|---|
| `matched_wigley_sensitivity.csv` | `computed_stokes_body_forward_speed_value` | Eq. (32) 体积分前进速度项对应的无量纲系数 |
| `matched_wigley_sensitivity.csv` | `computed_stokes_forward_speed_with_end_term_value` | Eq. (32) 体积分前进速度项加 `C_A` 端部项 |
| `matched_wigley_sensitivity.csv` | `computed_stokes_total_with_end_term_value` | 时间导数项加 Eq. (32) 体积分前进速度项再加端部项 |
| `matched_wigley_station_diagnostics.csv` | `station_weighted_stokes_body_forward_speed_normalized_contribution` | 每站对 Stokes 体积分项的归一化贡献 |
| `matched_wigley_station_diagnostics.csv` | `cumulative_stokes_body_forward_speed_value` | 从艉向艏累计的 Stokes 体积分项 |
| `matched_wigley_station_diagnostics.csv` | `cumulative_forward_minus_stokes_body_value` | Eq. (30) 有限差分前进速度项与 Eq. (32) 体积分项的差额 |

新增输出目录为 `outputs/matched_wigley_eq32_stokes_body_diagnostics`。在 waterline-clipped one-zone、A1 推荐级网格、`control_image_scale=-1`、关闭端部项、只比较 `pitch_forward_speed_sign=+1/-1` 的聚焦诊断下，首行四个系数得到：

| coefficient | reference | `U m5` sign | Eq.30 computed | time term | Eq.30 forward term | Eq.32 body forward term | time + Eq.32 body + end |
|---|---:|---:|---:|---:|---:|---:|---:|
| `A33` | `1.000` | `+1/-1` | `4.366` | `4.366` | `0.000` | `0.000` | `4.366` |
| `A35` | `-0.200` | `+1` | `-0.462` | `-0.00483` | `-0.457` | `0.000` | `-0.00483` |
| `A35` | `-0.200` | `-1` | `+0.453` | `-0.00483` | `+0.457` | `0.000` | `-0.00483` |
| `A53` | `0.150` | `+1/-1` | `0.275` | `0.275` | `0.000` | `0.000` | `0.275` |
| `A55` | `0.063` | `+1` | `0.219` | `0.198` | `0.0211` | `0.699` | `0.896` |
| `A55` | `0.063` | `-1` | `0.177` | `0.198` | `-0.0211` | `-0.699` | `-0.501` |

这个结果给出两个新的判断。第一，`A35` 的 Stokes 体积分前进速度项为零是符合 Eq. (32) 结构的，因为它属于 heave-force row，而 `m3=0`；所以 A35 当前主要来自 Eq. (30) 的 `U partial phi / partial x` 压力梯度项。第二，`A55` 的 Eq. (32) 体积分前进速度项幅值约 `0.699`，远大于参考值 `0.063`，与时间导数项相加后会把 A55 推到 `0.896`，反号则推到 `-0.501`。这说明不能简单用 Eq. (32) 体积分项替代有限差分前进速度项；真正缺口仍在 pitch row 的 `m5/N5` 坐标约定、`C_A` 端部轮廓补偿、端部站位方向，以及 Eq. (30) 与 Eq. (32) 两种压力恢复路线的符号一致性。

Gate 1 仍为 `PENDING`。下一步最小验收动作改为：在不改变默认结果的前提下，把 `C_A` 端部项也拆成 heave row 与 pitch row 的 station/end orientation 诊断，并检查 `time + Eq.32 body + Eq.32 end` 是否能同时改善 `A33/A35/A53/A55`。如果只让 `A55` 或只让 `A35/A53` 局部接近文献，仍只能记录为 diagnostic，不能进入生产默认。

随后已用 `outputs/matched_wigley_eq32_stokes_end_body_balance` 做了 `end_station=aft/bow` 与 `end_term_scale=+1/-1` 的端部项平衡扫描。该扫描仍采用同一 waterline-clipped one-zone 推荐级网格、`control_image_scale=-1` 和默认 `pitch_forward_speed_sign=+1`。代表性结果为：

| coefficient | end station | end scale | Eq.30 computed | end term | Eq.32 body forward | time + Eq.32 body + end | 结论 |
|---|---|---:|---:|---:|---:|---:|---|
| `A35` | aft | `+1` | `-0.548` | `-0.0857` | `0.000` | `-0.0906` | Eq.32 体积分路线不能产生 A35 主贡献 |
| `A35` | aft | `-1` | `-0.376` | `+0.0857` | `0.000` | `0.0809` | 端部反号改善 Eq.30 值但仍失败 |
| `A55` | aft | `+1` | `0.127` | `-0.0916` | `0.699` | `0.805` | 端部项量级不足以抵消体积分偏大 |
| `A55` | bow | `-1` | `0.212` | `-0.00728` | `0.699` | `0.889` | bow 端部项更小，不能修正 A55 |

因此，`C_A` 端部项在当前实现里确实影响 Eq.30 的最终结果，例如 aft `+C_A` 能把 A55 从无端部时的 `0.219` 降到 `0.127`，但它无法让完整 Stokes 路线 `time + body + end` 接近参考值。新的结论是：如果 Eq. (32) 路线要成为生产压力恢复方式，就不能只调整端部项符号；必须重新复核 pitch-row `m5` 的坐标定义、体积分中的法向选择、端部轮廓的实际方向，以及 A1 论文坐标系到程序 `z_down/heave_up` 坐标系的映射。

## 2026-07-31 进展：A1 `N_i/m_i` 坐标映射自洽性审计

为了避免继续盲目扫描符号，本轮新增 `HeavePitchA1ConventionAudit` 与 `audit_heave_pitch_a1_convention()`。该 helper 做的事情很简单：从当前 body-condition 反推程序实际使用的 `N3`、`N5` 和 `m5`，再把它们分别与压力积分的 heave row、pitch moment row 以及 Eq. (32) Stokes 体积分 row 对比。它不会判断论文坐标映射一定正确，只判断“当前程序内部是否自洽”。

新增 station diagnostics 字段包括：

| 字段 | 说明 |
|---|---|
| `a1_convention_audit_status` | 坐标/广义力行审计状态 |
| `a1_radiation_lever_arm_m` | pitch radiation body condition 中使用的力矩臂 |
| `a1_moment_lever_arm_m` | pressure integration pitch row 中使用的力矩臂 |
| `a1_heave_n3_to_force_row_relative_residual` | 从 heave body condition 反推的 `N3` 与 heave force row 的相对残差 |
| `a1_pitch_n5_to_moment_row_relative_residual` | 从 pitch oscillatory body condition 反推的 `N5` 与 pitch moment row 的相对残差 |
| `a1_pitch_m5_forward_to_stokes_relative_residual` | 从 pitch forward-speed body condition 反推的 `m5` 与 Stokes body row 的相对残差 |
| `a1_pitch_m5_to_n5_norm_ratio` | `m5` 与 `N5` 的范数比，用于观察无力矩臂项和有力矩臂项的量级关系 |

输出目录为 `outputs/matched_wigley_a1_convention_audit`。在 `A35/A55` 首行、`pitch_radiation_lever_sign=+1/-1` 与 `pitch_forward_speed_sign=+1/-1` 的四组合中，A55 最后一个 station 的残差为：

| pitch lever sign | pitch forward sign | `N5` row residual | `m5` row residual | `m5/N5` norm ratio | Stokes total |
|---:|---:|---:|---:|---:|---:|
| `+1` | `+1` | `1.4e-16` | `0.0` | `0.702` | `0.896` |
| `+1` | `-1` | `1.4e-16` | `2.0` | `0.702` | `-0.501` |
| `-1` | `+1` | `2.0` | `0.0` | `0.702` | `0.501` |
| `-1` | `-1` | `2.0` | `2.0` | `0.702` | `-0.896` |

这个结果说明当前默认设置在程序内部是自洽的：`N5` 与 pitch moment row 对齐，`m5` 与 Stokes body row 也对齐。A55 仍然失败，说明问题不再是“内部某个符号漏乘”，而更可能是 A1 论文坐标系、法向定义、`x` 参考点和程序 `z_down/heave_up` 映射之间仍有物理约定未闭合。Gate 1 下一步应停止扩大经验符号矩阵，改为逐公式审计 A1 Eq. (4)-Eq. (6)、Eq. (30) 和 Eq. (32) 从论文坐标到程序坐标的变换，并把审计结果写成固定 convention layer。

## 2026-07-31 进展：固定 A1 heave/pitch convention layer 落地

上述 convention layer 已经进入代码主路径。新增 `A1HeavePitchCoordinateConvention` 与默认实例 `DEFAULT_A1_HEAVE_PITCH_CONVENTION`，并把原先分散在多个 helper 里的行向量和符号集中到该对象中：

| convention 方法 | 统一管理的物理量 |
|---|---|
| `heave_n3()` | A1 Eq. (5) 中 heave 对应的 `N3`，在程序 `z_down/heave_up` 约定下等于 heave force row |
| `pitch_n5()` | A1 Eq. (5) 中 pitch 对应的 `N5`，使用调用方给出的 pitch 力矩臂 |
| `pitch_m5()` | A1 Eq. (6) 中 pitch 对应的 `m5` |
| `heave_body_normal_velocity()` | `i omega N3` body-condition 通道 |
| `pitch_body_normal_velocity_components()` | `i omega N5` 与 `U m5` 两个 pitch body-condition 通道 |
| `pressure_generalized_rows()` | Eq. (30) 压力积分的 heave/pitch 广义力行 |
| `stokes_body_m_rows()` | Eq. (32) 体积分中的 `m3/m5` 行 |
| `end_contour_n_rows()` | Eq. (32) 端部轮廓中的 `N3/N5` 行 |

因此，`heave_radiation_normal_velocity()`、`pitch_radiation_normal_velocity_components()`、`integrate_section_heave_pitch_force()`、`compute_heave_pitch_stokes_end_term_force_matrix()`、`compute_heave_pitch_stokes_body_forward_speed_force_matrix()` 和 `audit_heave_pitch_a1_convention()` 现在都通过同一个 convention layer 取行向量。该层带有 `ValidityReport`，状态为 `a1_heave_pitch_coordinate_convention_layer_not_benchmark_validated`，意思是内部可测试但尚未通过 Ma 2005 Gate 1。

新增 smoke 输出为 `outputs/matched_wigley_a1_convention_layer`。在同一推荐级 waterline-clipped one-zone 设置下，结果保持为：

| coefficient | reference | computed | Stokes total | status |
|---|---:|---:|---:|---|
| `A35` | `-0.200` | `-0.462` | `-0.00483` | `FAIL` |
| `A55` | `0.063` | `0.219` | `0.896` | `FAIL` |

这证明本次重构没有把数值“调好”或“调坏”，只是把坐标约定固定成一处可审计入口。Gate 1 下一步可以在该 convention layer 上逐项建立 A1 论文坐标到程序坐标的变换表，而不再在多个函数里分别追踪 `-normal_z`、`lever` 和 `m5` 的来源。

## 2026-07-31 进展：A1 paper-to-package 映射表机器可读化

固定 convention layer 已经进一步补上机器可读映射表。新增 `A1CoordinateMappingRow`，并在 `A1HeavePitchCoordinateConvention.paper_to_package_mapping_rows()` 中返回 9 行映射。每行都包含 A1 符号、来源方程、A1 表达式、程序表达式、用途、状态和备注；表级状态仍来自 `DEFAULT_A1_HEAVE_PITCH_CONVENTION.validity`。

当前映射表的核心行如下：

| A1 符号/项 | A1 来源 | 程序表达式 | 用途 | 状态 |
|---|---|---|---|---|
| `N3` | Eq. (5): `N3=Nz` | `heave_n3 = -normal_z` | heave body condition / heave pressure row | `PENDING_GATE1_BENCHMARK_VALIDATION` |
| `N5` | Eq. (5): `N5=-x*Nz` | `pitch_n5 = lever_arm_m * (-normal_z)` | pitch body condition / end contour row | `PENDING_GATE1_BENCHMARK_VALIDATION` |
| `m3` | Eq. (6): `m_j=0, j=1..4` | `m3=0` | Eq. (32) body heave row | `PENDING_GATE1_BENCHMARK_VALIDATION` |
| `m5` | Eq. (6): `m5=Nz` | `pitch_m5 = sign * (-normal_z)` | pitch `U m5` / Eq. (32) body pitch row | `PENDING_GATE1_BENCHMARK_VALIDATION` |
| Eq. (30) rows | body pressure integral | `pressure_generalized_rows()` | heave/pitch pressure integration | `PENDING_GATE1_BENCHMARK_VALIDATION` |
| Eq. (32) body rows | `rho U integral(phi_j m_i ds)` | `stokes_body_m_rows()` | Stokes body forward-speed diagnostic | `PENDING_GATE1_BENCHMARK_VALIDATION` |
| Eq. (32) end rows | `-rho U integral_CA(phi_j N_i dl)` | `end_contour_n_rows()` | Stokes `C_A` end-contour diagnostic | `PENDING_GATE1_BENCHMARK_VALIDATION` |

同时，`assemble_frequency_domain_from_matched_station_hull()` 的 metadata 已新增 `a1_coordinate_convention_name` 和 `a1_coordinate_convention_status`，station diagnostics 也新增同名字段。因此输出 CSV 不再只给数值，还能说明这些数值采用的是哪一套坐标约定。

新增 smoke 输出为 `outputs/matched_wigley_a1_mapping_table`。结果仍为 `A35=-0.462`、`A55=0.219`，并且 station diagnostics 第一行写出：

```text
a1_coordinate_convention_name   = package_z_down_heave_up_lcg_minus_x
a1_coordinate_convention_status = a1_heave_pitch_coordinate_convention_layer_not_benchmark_validated
```

这一步把“下一步必须建立映射表”的要求变成了代码事实。Gate 1 仍然 `PENDING`；下一步的有效改动必须引用这张映射表，说明改的是哪一行，并用 Wigley III `A33/A35/A53/A55` 联合结果证明它不是单项调参。

## 2026-07-31 进展：A1 约定候选集联合诊断

为避免继续用零散符号开关试探，本轮新增 `A1ConventionCandidate`、`a1_convention_candidate_cases()`、`matched_wigley_a1_convention_candidate_rows()` 与 `write_a1_convention_candidate_benchmark()`。这些对象把原先的 pitch lever、`m5` 前进速度项和 pitch generalized-force 行符号整理成少量受控候选。

| candidate | 改动的映射表行 | 目的 | 状态 |
|---|---|---|---|
| `default_mapping` | 无 | 默认 `z_down/heave_up/LCG-x` 映射的中性对照 | `diagnostic_a1_convention_candidate_not_hard_gate` |
| `reverse_n5_and_pitch_row` | `N5`、pitch pressure row、Eq.32 end contour term | 检查 pitch 力矩臂整体方向是否相反 | 同上 |
| `reverse_m5_forward_speed` | `m5` | 单独检查 `U m5` 前进速度体边界条件符号 | 同上 |
| `reverse_pitch_force_row` | pitch pressure row、Eq.32 body/end rows | 单独检查输出 pitch 广义力行符号 | 同上 |
| `reverse_all_pitch_rows` | `N5`、`m5`、pitch pressure row、Eq.32 body/end rows | 宽松 pitch 全反号审计，只作排错 | 同上 |

新增推荐网格诊断输出为 `outputs/matched_wigley_a1_convention_candidates`。该输出包含 `a1_convention_candidate_benchmark.csv`、`a1_convention_candidate_summary.csv`、`a1_convention_candidate_best_cases.csv`、`a1_convention_candidate_mapping.csv` 和 `a1_convention_candidate_metadata.csv`。本次只取 Wigley III 首行四个 added-mass 系数 `A33/A35/A53/A55` 做联合探针，结果如下：

| coefficient | 当前最佳候选 | reference | computed | gate error ratio | 结论 |
|---|---|---:|---:|---:|---|
| `A33` | `default_mapping` | `1.000` | `4.554` | `23.69` | pitch 约定不影响 heave 对角项，主缺口在内外域/自由面或归一化 |
| `A35` | `reverse_n5_and_pitch_row` | `-0.200` | `-0.668` | `7.80` | 反转 pitch lever 可局部改善，但仍远超耦合项 30% 门槛 |
| `A53` | `default_mapping` | `0.150` | `0.334` | `4.10` | 默认符号最接近，但仍未通过耦合项门槛 |
| `A55` | `reverse_pitch_force_row` | `0.063` | `0.0847` | `2.30` | 输出 pitch 行反号可改善 A55，但不能同时修正 A33/A35/A53 |

这个结果把问题进一步收窄：Gate 1 失败不能用“单个 pitch 符号写反”解释。即使选择对 `A55` 最有利的 `reverse_pitch_force_row`，`A33` 和 `A35` 仍明显失败；而对 `A35` 较有利的 `reverse_n5_and_pitch_row` 会让 `A55` 偏差变大。因此下一步应回到 A1 Eq. (23)-Eq. (24) 的内外域匹配、控制面瞬时项、自由面法向导数尺度和 Wigley III 数字化归一化复核，而不是继续把候选符号固化为生产默认。

## 2026-07-31 进展：A1 Eq. (24) 控制面瞬时项候选集

本轮继续把控制面瞬时项也整理为受控候选，新增 `A1ControlSurfaceCandidate`、`a1_control_surface_candidate_cases()`、`matched_wigley_a1_control_surface_candidate_rows()` 与 `write_a1_control_surface_candidate_benchmark()`。候选覆盖默认控制面项、镜像项反号、potential 列反号、normal-derivative 列反号、双列反号、镜像加双列反号和 diagonal 自项反号。

新增输出目录为 `outputs/matched_wigley_a1_control_surface_candidates`，包含 `a1_control_surface_candidate_benchmark.csv`、`a1_control_surface_candidate_summary.csv`、`a1_control_surface_candidate_best_cases.csv` 和 `a1_control_surface_candidate_metadata.csv`。推荐网格首行四系数探针结果如下：

| coefficient | 当前最佳控制面候选 | reference | computed | gate error ratio | 结论 |
|---|---|---:|---:|---:|---|
| `A33` | `reverse_image_and_both_columns` | `1.000` | `4.220` | `21.47` | 即使控制面瞬时项整体反号，heave added-mass 仍过大 |
| `A35` | `reverse_image_and_both_columns` | `-0.200` | `-0.458` | `4.30` | 较默认改善，但仍未过耦合项门槛 |
| `A53` | `reverse_image_and_both_columns` | `0.150` | `0.233` | `1.84` | 接近但仍未过耦合项门槛 |
| `A55` | `reverse_image_terms` | `0.063` | `0.152` | `9.46` | A55 与 A33 无法由控制面瞬时项单独闭合 |

候选输出同时暴露出一个数值稳定性结论：单独反 `potential column`、单独反 `normal-derivative column` 或反 diagonal 自项会产生极大系数，属于病态诊断而不是可采纳的物理修正。因此 Gate 1 的下一步不应再把 Eq. (24) 的某个单项符号作为默认值，而应复核控制面 B/C 核函数的量纲、法向导数方向和内外域匹配矩阵的整体归一化。

同一轮还在 matched Wigley sensitivity 行中加入了 Ma 2005 Eq. (34) 归一化尺度审计字段，包括 `ma2005_normalization_formula`、`required_normalization_scale`、`required_normalization_scale_over_current` 和 `normalization_scale_diagnosis`。A1.md 明确给出 `A33=a33/(rho*∇)`，当前代码也采用 `rho*∇`；首行 A33 若要靠归一化解释，需要把当前尺度放大约 `4.55` 倍，输出诊断为 `normalization_scale_unlikely_as_sole_explanation`。这说明 A33 主要仍是求解/匹配尺度问题，而不是 Eq. (34) 公式误读。

## 2026-07-31 进展：A1 Eq. (23)-Eq. (24) block-level audit

本轮新增 `MatchedSystemBlockAudit` 与 `audit_matched_system_blocks()`，把每个 matched section system 拆成四个方程行块和四个未知量块。方程行块为 `eq23_body`、`eq23_free_surface`、`eq23_inner_control`、`eq24_outer_control`；未知量块为 `psi_body`、`psi_n_free_surface`、`psi_control`、`psi_n_control`。每个 audit 记录行块残差、RHS 范数、未知量范数、矩阵块范数、矩阵块乘未知量后的贡献范数、整体条件数和 `ValidityReport` 状态。

这些字段已经进入 station diagnostics，输出目录为 `outputs/matched_wigley_a1_block_audit`。推荐网格首行 `A33/A53` 的站位诊断显示：

| coefficient | 最大单站贡献位置 | selected mode | station contribution | 最大贡献块 | 贡献块范数 | 解释 |
|---|---:|---|---:|---|---:|---|
| `A33` | station `15` | heave | `0.1918` | `eq23_body<-psi_body` | `5.752` | A33 峰值主要来自体面势在 Eq.23 body row 的贡献 |
| `A53` | station `2` | heave | `0.0695` | `eq23_body<-psi_body` | `5.773` | A53 的最大正贡献同样来自 heave 模式体面势块 |

对全部活跃站计数，`A33` 与 `A53` 都有 `37/39` 个站的最大贡献块为 `eq23_body<-psi_body`，只有 `2/39` 个站转为 `eq23_body<-psi_n_free_surface`。同时，A53 后半段的 `a1_eq24_to_eq23_control_rhs_norm_ratio` 多数只有千分量级，说明外域历史 RHS 在当前首行诊断中不是主导放大源。

因此 Gate 1 的下一步目标进一步收窄为：先审计 Eq. (23) body row 的体面势尺度，包括 `_inner_a_matrix()` 的自项符号和 `pi/2pi` 因子、内域 Green 函数是否需要与简单 Green BIE 的 `1/(2π)` 归一化一致、体面势 `psi_body` 的单位尺度，以及 body/free/control 三类内域边界块是否混用了 raw log kernel 与 normalized simple-Green kernel。未完成该审计前，不应再优先扩大 Eq. (24) 历史项或 pitch sign 候选。

## 2026-07-31 进展：A1 Eq. (23) inner-kernel 归一化候选

根据 A1.md 中 Eq. (25) 的原文，`Aij` 与 `Bij` 定义为 raw `ln r` 和 `partial ln r / partial n_j` 的面元积分，且 Eq. (23) 中 `alpha=1`，自项为 `-π`；Eq. (24) 中 `alpha=2`，自项为 `+π`。因此，当前 matched system 使用 raw log kernel 与 Eq. (23) `-π` 自项并非显然错误。为了把这个判断变成可复现证据，本轮新增 `A1InnerKernelCandidate`、`a1_inner_kernel_candidate_cases()`、`matched_wigley_a1_inner_kernel_candidate_rows()` 与 `write_a1_inner_kernel_candidate_benchmark()`。

新增输出目录为 `outputs/matched_wigley_a1_inner_kernel_candidates` 和 `outputs/matched_wigley_a1_inner_kernel_candidates_joint`。候选包括：

| candidate | 改动 | 目的 |
|---|---|---|
| `raw_eq25_default` | 无 | A1 Eq. (25) raw kernel 与 Eq. (23) `-π` 自项 |
| `normalize_a_and_b_by_2pi` | `Aij` 与 `Bij` 同除 `2π` | 检查是否只是 raw/simple-Green 整体归一化问题 |
| `normalize_a_only_by_2pi` | 仅 `Aij` 除 `2π` | 检查 normal-derivative operator 相对尺度 |
| `normalize_b_only_by_2pi` | 仅 `Bij` 除 `2π` | 检查 log-potential operator 相对尺度 |
| `positive_eq23_self_term` | Eq. (23) 自项从 `-π` 改为 `+π` | 检查自项符号误读 |
| `reverse_a_operator` / `reverse_b_operator` | A/B 操作符反号 | 检查大范围法向/符号错误 |

四系数首行联合探针的最佳候选均为 `normalize_b_only_by_2pi`，结果如下：

| coefficient | reference | raw default | `B only / 2π` | gate error ratio | 结论 |
|---|---:|---:|---:|---:|---|
| `A33` | `1.000` | `4.554` | `0.749` | `1.67` | 明显改善但仍未过 15% 对角项门槛 |
| `A35` | `-0.200` | `-0.839` | `-0.111` | `1.49` | 明显改善但仍未过 30% 耦合项门槛 |
| `A53` | `0.150` | `0.334` | `0.0157` | `2.99` | 过度降低，仍失败 |
| `A55` | `0.063` | `-0.0847` | `-0.0300` | `9.84` | 符号仍错，说明 pitch 相关缺口未解决 |

整套 `Aij/Bij` 同除 `2π` 的结果与 raw default 完全相同，这符合“整行方程等比例缩放不改变线性方程解”的预期；仅 `Aij` 除 `2π`、自项改为 `+π` 或 A/B 反号都会产生更大偏差或病态结果。因此，`normalize_b_only_by_2pi` 是重要线索，但不能直接作为生产默认。它说明 Eq. (23) 中 `Bij` 与 `Aij` 的相对尺度、未知量 `psi_body` 与 `psi_n` 的单位配平、以及体面势压力恢复之间仍需逐公式闭合。Gate 1 仍为 `PENDING`。

## 2026-07-31 进展：A1 Eq. (23)-Eq. (30) 势函数单位闭合诊断

在 inner-kernel 候选之后，本轮把 `psi_body`、`psi_n` 与 Eq. (30) 压力恢复之间的尺度关系写入 station diagnostics。新增字段包括 `a1_unit_closure_status`、`a1_unit_body_potential_per_normal_velocity_length_m`、`a1_unit_body_potential_per_normal_velocity_over_span`、`a1_unit_inner_fs_normal_derivative_to_body_condition_norm_ratio`、`a1_unit_control_normal_derivative_to_body_condition_norm_ratio`、`a1_unit_pressure_time_over_rho_omega_phi_norm_ratio` 以及 force/moment 的前进速度项相对时间导数项比例。它们的作用不是修正数值，而是回答一个更基础的问题：在同一站位上，给定的体面法向速度通过 Eq. (23)-Eq. (24) 得到的体面势，是否具有合理的局部长度尺度；再经 Eq. (30) 变成压力时，是否仍满足 `pressure_time = -rho*i*omega*phi` 这个直接量纲关系。

一个 CLI smoke 已写入 `outputs/cli_inner_kernel_smoke`。使用 `--inner-b-scales 0.15915494309189535` 时，合法 `history_quadrature_count=16` 可正常生成 `matched_wigley_sensitivity.csv` 和 `matched_wigley_station_diagnostics.csv`。该 smoke 的 station diagnostics 显示 `a1_unit_pressure_time_over_rho_omega_phi_norm_ratio=1.0`，说明 Eq. (30) 时间导数压力的直接实现是闭合的；但 `a1_unit_body_potential_per_normal_velocity_over_span` 在三个有效站位中约为 `24.79`、`3.25` 和 `0.19`，变化很大，说明体面势尺度的站位分布仍需继续审计。

推荐网格的 raw Eq. (25) 与 `Bij/2π` 对比写入 `outputs/matched_wigley_a1_unit_closure_probe`，并生成 `a1_unit_closure_summary.csv`：

| case | coefficient | station count | median potential length / span | max potential length / span | median free-surface normal / body condition | max free-surface normal / body condition | median station contribution |
|---|---|---:|---:|---:|---:|---:|---:|
| `raw_eq25_unit_closure_probe` | `A33` | `39` | `4.210` | `200.892` | `0.278` | `2.481` | `0.135` |
| `raw_eq25_unit_closure_probe` | `A53` | `39` | `4.210` | `200.892` | `0.278` | `2.481` | `0.000` |
| `inner_b2pi_unit_closure_probe` | `A33` | `39` | `0.783` | `40.685` | `0.160` | `4.221` | `0.0197` |
| `inner_b2pi_unit_closure_probe` | `A53` | `39` | `0.783` | `40.685` | `0.160` | `4.221` | `0.000` |

这个结果解释了为什么 `Bij/2π` 能显著降低 `A33/A35`：它把体面势相对体面法向速度的等效长度尺度从中位数约 `4.21` 个局部跨度压到约 `0.78` 个局部跨度。但它同时把 `A53` 压得过小，并不能恢复 `A55` 的正确符号。因此，`Bij/2π` 是定位 `psi_body` 尺度问题的探针，不是生产默认。

同一轮还运行了 `Bij/2π + A1ConventionCandidate` 组合候选，输出目录为 `outputs/matched_wigley_a1_inner_b2pi_convention_candidates`。结果表明，组合候选仍不能通过四系数首行联合门：

| coefficient | best candidate under `Bij/2π` | reference | computed | gate error ratio | 结论 |
|---|---|---:|---:|---:|---|
| `A33` | `default_mapping` | `1.000` | `0.749` | `1.67` | 仍超出 15% 对角项门槛 |
| `A35` | `default_mapping` | `-0.200` | `-0.111` | `1.49` | 仍超出 30% 耦合项门槛 |
| `A53` | `default_mapping` | `0.150` | `0.0157` | `2.99` | `Bij/2π` 使该耦合项过度衰减 |
| `A55` | `reverse_pitch_force_row` | `0.063` | `0.0300` | `3.49` | 符号可局部修正但幅值仍不够，不能作为生产 convention |

因此 Gate 1 的下一步不应继续扩大经验候选矩阵，而应做两个更硬的动作：第一，复核 A1 Eq. (23) 中 `Aij`、`Bij`、自项和已知体面法向速度 RHS 的共同量纲，尤其是 paper 使用的 raw log kernel 与程序中 `psi` 单位之间是否缺少一致的边界积分归一化；第二，在物理公式层面对 pitch mode 的 `N5`、`m5`、`U*m_j`、lever arm 和 Eq. (32) 端部项做逐项坐标变换审计。Gate 1 仍为 `PENDING`。

## 2026-07-31 进展：A1 Eq. (23) 闭合边界 Green 恒等式审计

为了把上一节的“Eq. (23) 共同量纲”继续往下压实，本轮新增一个不依赖 Wigley III 数字化曲线的解析自检：在闭合椭圆边界上取已知调和势函数 `linear_y`、`linear_z`、`quadratic_y2_minus_z2` 和 `cross_yz`，直接检查 raw A1 Eq. (23) 是否满足 `A phi - B phi_n = 0`。这个问题没有自由面、没有控制面、没有端部项，也没有 heave/pitch 约定；它只检验内域 Green kernel、自项和法向导数的局部数学一致性。

新增代码包括 `A1InnerKernelGreenIdentityAudit`、`build_closed_ellipse_inner_boundary()`、`audit_inner_kernel_green_identity()`、`a1_inner_kernel_green_identity_rows()` 与 `write_a1_inner_kernel_green_identity_audit()`。输出目录为 `outputs/matched_wigley_a1_inner_kernel_green_identity`，其中 `a1_inner_kernel_green_identity.csv` 为明细，`a1_inner_kernel_green_identity_summary.csv` 为候选汇总。

核心结果如下：

| candidate | 解析闭合边界结论 | 代表性最细网格 residual | 对 Gate 1 的含义 |
|---|---|---:|---|
| `raw_eq25_default` | 四种调和势全部通过 | `0.0050-0.0090` | raw `ln r`、`partial ln r/partial n` 和 Eq. (23) `-π` 自项在闭合边界上自洽 |
| `normalize_a_and_b_by_2pi` | 四种调和势全部通过 | `0.0022-0.0030` | 整行同尺度归一化不改变方程本质；这与 Wigley 候选中结果不变一致 |
| `normalize_b_only_by_2pi` | 四种调和势全部失败 | 约 `0.841-0.842` | 单独缩放 `Bij` 会破坏 Green 恒等式，不能作为物理修正 |
| `positive_eq23_self_term` | 四种调和势全部失败 | 约 `1.129-1.764` | Eq. (23) 自项改为 `+π` 与闭合边界恒等式不符 |
| `reverse_a_operator` / `reverse_b_operator` | 四种调和势全部失败 | 约 `1.99` | 大范围 A/B 反号不是可接受修正 |

这条证据把 Gate 1 的问题进一步缩小：当前 raw Eq. (23) 内域 kernel 在闭合边界数学问题中是对的，`Bij/2π` 只是破坏恒等式后偶然压低 Wigley 体面势尺度的诊断。因此下一步不应继续追 `Bij` 单项归一化，而应转向 A1 的开边界混合系统：body、inner free surface、control surface 三类边界共同进入 Eq. (23) 时，已知 body normal velocity、已知 free-surface potential、未知 `psi_body/psi_n_free/psi_control/psi_n_control` 之间的单位配平是否仍与闭合边界恒等式一致。同时还要继续核对 pitch 模态的 `N5/m5/U*m_j` 变换。Gate 1 仍为 `PENDING`。

## 2026-07-31 进展：A1 Eq. (23) body/free/control 混合边界审计

上一节证明 raw Eq. (23) 在单一闭合边界上自洽后，本轮继续把同一个闭合椭圆按面元数切分成三段，分别模拟 `body`、`inner_free_surface` 和 `control`。然后按 matched solver 的真实已知/未知放置来检查 Eq. (23)：`body` 边界已知 `phi_n`，`inner_free_surface` 已知 `phi`，`control` 同时保留 `phi` 与 `phi_n` 作为未知。把解析调和势的准确边界值代入后，若装配符号正确，应满足 mixed 方程残差趋近于零。

新增代码包括 `A1InnerMixedBoundaryGreenIdentityAudit`、`split_inner_boundary_geometry_by_panel_counts()`、`closed_boundary_three_part_panel_counts()`、`audit_inner_mixed_boundary_green_identity()`、`a1_inner_mixed_boundary_identity_rows()` 和 `write_a1_inner_mixed_boundary_identity_audit()`。输出目录为 `outputs/matched_wigley_a1_inner_mixed_boundary_identity`。

推荐输出使用 `66/132/264` 面元，并保留四种解析调和势。结果如下：

| candidate | mixed-boundary 结论 | finest residual 范围 | 对 Gate 1 的含义 |
|---|---|---:|---|
| `raw_eq25_default` | 四种调和势全部通过 | `0.00697-0.0160` | body/free/control 的 Eq. (23) 已知/未知放置和 RHS 符号自洽 |
| `normalize_a_and_b_by_2pi` | 四种调和势全部通过 | `0.00142-0.00288` | 仍只是整行尺度，不改变 mixed 方程本质 |
| `normalize_b_only_by_2pi` | 四种调和势全部失败 | `1.322-1.532` | 单独改 `Bij` 不仅破坏闭合边界，也破坏 mixed 边界 |
| `positive_eq23_self_term` | 四种调和势全部失败 | `1.588-2.197` | Eq. (23) `+π` 自项不能接受 |
| `reverse_a_operator` / `reverse_b_operator` | 四种调和势全部失败 | `1.728-2.695` | A/B 反号不是合理修正 |

这一步把 Gate 1 的当前内域审计又推进了一层：不仅 raw kernel 本身是对的，当前 Eq. (23) 中 body/free/control 三类边界的已知/未知列和 RHS 搬项也能通过解析 mixed-boundary 检查。因此，Wigley III 首行失败不应继续归咎于 Eq. (23) raw kernel 或 `Bij` 单项归一化。下一步应把重点放在 Eq. (19)-Eq. (22) 自由面状态传递、Eq. (24) 外域控制面即时/历史匹配、station-to-station 控制面历史继承、Eq. (30) `U partial phi / partial x` 与 Eq. (32) 端部项之间的双计/漏计，以及 pitch 模态 `N5/m5/U*m_j` 的坐标变换。Gate 1 仍为 `PENDING`。
## 2026-07-31 进展：A1 Eq. (19)-Eq. (22) 自由面简谐振子审计

本轮新增 `A1FreeSurfaceOscillatorAudit`、`audit_free_surface_oscillator_marching()`、`a1_free_surface_oscillator_rows()` 和 `write_a1_free_surface_oscillator_audit()`，输出目录为 `outputs/matched_wigley_a1_free_surface_oscillator_audit`。

这个审计不依赖 Wigley III 数字化曲线，也不经过 Eq. (23) 或 Eq. (24) 边界积分系统，而是直接把解析线性自由面振子作为外部已知输入喂给 `initialize_free_surface_state()` 和 `advance_free_surface_state()`。解析关系为：自由面高程 `eta=A cos(omega t + phase)`，自由面势 `phi=-(g A / omega) sin(omega t + phase)`，竖向速度 `eta_t=-A omega sin(omega t + phase)`。由于当前程序采用交错时间层，高程在 `half_step_time_s` 上比较，势在 `time_s` 上比较。

| `dt_s` | steps | max normalized error | RMS elevation error | RMS potential error | status |
|---:|---:|---:|---:|---:|---|
| `0.08` | `25` | `0.032451` | `0.005163` | `0.015464` | `PASS` |
| `0.04` | `50` | `0.008106` | `0.001290` | `0.003787` | `PASS` |
| `0.02` | `100` | `0.002026` | `0.000322` | `0.000937` | `PASS` |
| `0.01` | `201` | `0.000512` | `0.000081` | `0.000235` | `PASS` |

summary 显示高程 RMS 误差观测阶约 `1.999`，势 RMS 误差观测阶约 `2.014`。因此，A1 Eq. (19)-Eq. (22) 的离散时间层和首步/续步推进公式在单点解析自由面振子层面是自洽且随步长加密收敛的。Gate 1 仍为 `PENDING`，但当前主要嫌疑应从“Eq. (19)-Eq. (22) 公式本身不收敛”进一步收缩到：BIE 求得的内自由面 normal derivative 尺度、station-to-station 状态继承、Eq. (24) 控制面匹配、Eq. (30)/Eq. (32) 前进速度项与 pitch 广义力装配。
## 2026-07-31 进展：A1 Eq. (24) 控制面瞬时项 Green 恒等式审计

本轮新增 `A1OuterControlGreenIdentityAudit`、`audit_outer_control_surface_green_identity()`、`a1_control_surface_green_identity_rows()` 和 `write_a1_control_surface_green_identity_audit()`，输出目录为 `outputs/matched_wigley_a1_outer_control_green_identity`。

该审计使用控制面内部的反对称镜像点源 `phi=ln(r)-ln(r')`。这个解析场在控制面外部半平面内调和，并且在自由面 `z=0` 上满足 `phi=0`，因此适合检查 A1 Eq. (24) 的无历史瞬时项 `(A-Abar) phi - (B-Bbar) phi_n`。与前面的 Wigley III 候选扫描不同，这里不依赖整船压力积分、pitch 约定或数字化曲线，只检查控制面镜像核、对角自项和左右列符号在解析边界积分层面是否自洽。

| candidate | finest relative residual | 结论 |
|---|---:|---|
| `default_control_terms` | `0.000686` | 通过；当前 `A-Abar`、`B-Bbar` 镜像项和 Eq. (24) `+pi` 对角自项在无历史解析恒等式中自洽 |
| `reverse_image_terms` | `0.808718` | 失败；把镜像项改成 `A+Abar`、`B+Bbar` 不能通过半平面解析恒等式 |
| `reverse_potential_column` | `1.000000` | 失败；单独反 potential 列不自洽 |
| `reverse_normal_derivative_column` | `1.000000` | 失败；单独反 normal-derivative 列不自洽 |
| `reverse_both_columns` | `0.000686` | 通过但只代表无历史 RHS 的整体行符号歧义，不能单独证明生产修正 |
| `reverse_image_and_both_columns` | `0.808718` | 失败；镜像项反号仍不自洽 |
| `reverse_diagonal` | `1.000000` | 失败；Eq. (24) 对角自项不能改为 `-pi` |

因此，先前 Wigley 候选扫描中 `control_image_scale=-1` 曾局部改善 A35/A53，但这条解析审计显示它破坏 Eq. (24) 的半平面 Green 恒等式，不能写成生产默认。Gate 1 的剩余阻塞继续收敛为：BIE-fed 控制面历史 RHS 与瞬时项的联合符号、station-to-station 控制面历史继承、内自由面 normal derivative 尺度、Eq. (30)/Eq. (32) 前进速度项和 pitch 广义力装配。Gate 1 仍为 `PENDING`。
## 2026-07-31 进展：A1 Eq. (28) 瞬态 Green 历史核法向导数审计

本轮新增 `A1TransientHistoryKernelDerivativeAudit`、`audit_transient_history_kernel_normal_derivative()`、`a1_history_kernel_derivative_rows()` 和 `write_a1_history_kernel_derivative_audit()`，输出目录为 `outputs/matched_wigley_a1_history_kernel_derivative_audit`。

审计对象是 A1 Eq. (28) 中的瞬态自由面 Green 历史核：`B_ij^{m-k}` 是势核通道，`C_ij^{m-k}` 是势核对源面元法向的导数通道。为了避免直接依赖 Wigley III 整船系数，本审计把控制面源面元沿自身法向分别扰动 `+epsilon` 和 `-epsilon`，用中心差分近似 `dB/dn_source`，再与程序中的 `C` 核逐项比较。这样可以直接回答一个基础问题：历史 RHS 中的 normal-derivative kernel 是否真的是同一瞬态 Green 势核的法向导数。

正式输出采用 `panel_count=8/16/32`，`lag_s=0.02/0.05/0.10`，`quadrature_count=256`，`k_max=50`，`epsilon=1e-4 m`。结果如下：

| lag `s` | pass rows | fail rows | max relative residual | finest-panel residual | 结论 |
|---:|---:|---:|---:|---:|---|
| `0.02` | `3` | `0` | `1.05e-6` | `1.05e-6` | `C` 核与 `B` 核法向有限差分闭合 |
| `0.05` | `3` | `0` | `9.69e-7` | `9.69e-7` | `C` 核与 `B` 核法向有限差分闭合 |
| `0.10` | `3` | `0` | `7.00e-7` | `7.00e-7` | `C` 核与 `B` 核法向有限差分闭合 |

因此，A1 Eq. (28) 历史 RHS 的 `C_ij` 法向导数核通道目前有独立数值证据支持。Gate 1 仍为 `PENDING`，因为该审计只证明瞬态核的导数通道自洽，还没有证明完整历史 RHS 的时间卷积符号、截断 `k_max`、history inheritance 和控制面当前/历史状态之间的相位关系能通过 Wigley III 系数门槛。下一步应继续做历史 RHS 的时间卷积收敛和 station-to-station 控制面历史继承审计。
## 2026-07-31 进展：A1 Eq. (24) 历史 RHS quadrature/cutoff 收敛审计

本轮新增 `A1HistoryRhsConvergenceAudit`、`audit_history_rhs_quadrature_convergence()`、`a1_history_rhs_convergence_rows()` 和 `write_a1_history_rhs_convergence_audit()`，输出目录为 `outputs/matched_wigley_a1_history_rhs_convergence_audit`。

该审计使用确定性的光滑复数控制面历史状态，分别计算 Eq. (24) 历史 RHS 的总通道、`B_ij^{m-k} psi_n` 势核通道和 `C_ij^{m-k} psi` 法向导数核通道。每个候选的 `quadrature_count/k_max` 都与更高精度参考核比较，参考设置为 `reference_quadrature_count=768`、`reference_k_max=120`。这样可以直接检查 Eq. (28) 瞬态核有限积分截断和数值积分分辨率是否足以稳定生成历史 RHS。

正式输出采用 `panel_count=10`、`dt=0.05 s`、`history_steps=4`、`quadrature_rule=trapezoid`，结果如下：

| quadrature count | `k_max` | total relative residual | potential-channel residual | normal-derivative-channel residual | max channel residual | status |
|---:|---:|---:|---:|---:|---:|---|
| `48` | `40` | `6.80e-4` | `8.63e-4` | `1.27e-5` | `8.63e-4` | `PASS` |
| `96` | `50` | `2.02e-4` | `2.57e-4` | `1.22e-6` | `2.57e-4` | `PASS` |
| `192` | `70` | `6.49e-5` | `8.25e-5` | `1.46e-7` | `8.25e-5` | `PASS` |
| `256` | `80` | `3.89e-5` | `4.94e-5` | `5.91e-8` | `4.94e-5` | `PASS` |

因此，Eq. (24) 历史 RHS 在当前可控的解析式历史状态下表现出清晰的 quadrature/cutoff 收敛；主要截断误差来自 `B_ij psi_n` 势核通道，`C_ij psi` 通道误差低两个到四个数量级。Gate 1 仍为 `PENDING`，因为该审计不覆盖 station-to-station 控制面历史继承、真实 BIE 生成的控制面历史状态、以及历史 RHS 与瞬时项进入整船 `A33/A35/A53/A55` 后的相位/尺度关系。下一步应继续审计控制面历史继承与 Wigley active stations 中的实际历史状态范数。

## 2026-07-31 A1 Eq. (24) Station Control-History Inheritance Audit

The real Wigley station sweep now has an implementation-level inheritance audit
under `outputs/matched_wigley_a1_control_history_inheritance_audit`. The new
objects are `A1ControlHistoryInheritanceAudit`,
`audit_control_history_inheritance()`,
`a1_control_history_inheritance_rows()`, and
`write_a1_control_history_inheritance_audit()`.

This audit reconstructs the Eq. (24) control-surface history queue from the
returned station solutions and the recorded `solve_order`. For every active
station, it recomputes the history right-hand side using the saved `dt`,
`history_steps`, `quadrature_count`, `k_max`, control-surface radius, and
history kernel scales. It then compares that reconstructed RHS with the RHS
stored immediately before the original station solve. It also checks the lag-0
state, so an off-by-one station shift, reversed marching direction, or
heave/pitch mode mix-up would appear directly as a nonzero residual.

The formal run uses the recommended-style Wigley case
`a1_history_inheritance_recommended` with 41 stations, 12 inner free-surface
panels, 10 control panels, control radius `3B`, waterline clipping, and the
first `A33/A53` reference rows. The output contains 156 detail rows: 39 active
stations times two coefficients times heave/pitch. All rows pass with maximum
`rhs_relative_residual=0.0` and maximum `max_lag0_relative_residual=0.0`.

This closes the narrow implementation question of whether the stored Eq. (24)
history RHS follows the station marching order. Gate 1 remains `PENDING`
because this audit does not prove that the BIE-generated control-surface
`psi_control/psi_n_control` has the correct physical scale or phase, nor that
the combined Eq. (23)-Eq. (24)-Eq. (30)-Eq. (32) chain matches the Ma 2005
Wigley coefficients.

## 2026-07-31 A1 Eq. (24) Outer-Control Balance Scale/Phase Audit

The real Wigley Eq. (24) row now has a component-level balance audit under
`outputs/matched_wigley_a1_outer_control_balance_audit`. The new objects are
`A1OuterControlBalanceAudit`, `audit_outer_control_balance()`,
`a1_outer_control_balance_rows()`, and
`write_a1_outer_control_balance_audit()`.

This audit reconstructs, station by station, the Eq. (24) outer-control row and
splits it into four pieces: instantaneous potential-column contribution,
instantaneous normal-derivative-column contribution, history `B_ij psi_n`
channel, and history `C_ij psi` channel. It reports norms, residuals, norm
ratios, real alignments, and phase angles. The purpose is not to tune any sign;
it is to show whether the real BIE-fed control-surface terms are acting as a
small correction, a dominant load, or a near-cancelling pair.

The formal run uses the same recommended-style Wigley setup as the inheritance
audit: 41 stations, 12 inner free-surface panels, 10 control panels, control
radius `3B`, waterline clipping, and the first `A33/A53` reference rows. The
output again contains 156 detail rows and four summary groups. All groups pass
the Eq. (24) row-balance tolerance of `1e-5`; the maximum relative residual is
about `1e-6` to `5e-6`, consistent with solving the full matched linear system.

The diagnostic signal is important: `median_rhs_to_lhs_norm_ratio` is `1.0`,
so the solved instantaneous control row balances the history RHS. However, the
instantaneous potential and normal-derivative contributions are nearly opposite
in phase, with median real alignment about `-0.9998` and phase near `180 deg`.
The two history channels are also strongly opposed, with median real alignment
about `-0.91` and phase near `180 deg` for heave and about `-175 deg` to
`-178 deg` for pitch. The median potential-to-normal instantaneous norm ratio is
about `1.03`, while the median history potential-channel to normal-channel norm
ratio is about `3.5-3.6`.

This narrows Gate 1 further. The remaining problem is no longer Eq. (24) row
assembly or station history inheritance; both now balance on the real Wigley
sweep. The sharper question is whether this near-cancellation structure has the
right physical scale and phase after coupling to Eq. (23), the inner free-surface
normal derivative, Eq. (30) pressure recovery, Eq. (32) forward-speed terms, and
the pitch generalized-force convention.

## 2026-07-31 A1 Eq. (23)-Eq. (24) RHS Source Decomposition Audit

The matched system now has a real-sweep RHS-source decomposition audit under
`outputs/matched_wigley_a1_rhs_source_decomposition_audit`. The new objects are
`A1RhsSourceDecompositionAudit`, `audit_rhs_source_decomposition()`,
`a1_rhs_source_decomposition_rows()`, and
`write_a1_rhs_source_decomposition_audit()`.

This audit uses the same matched matrix at each station but solves it three
times with only one known RHS source active: `body_normal_velocity`,
`inner_free_surface_potential`, and `outer_control_history`. The three source
solutions must add back to the full solved section solution. The audit reports
the RHS norms, full-solution norm ratios, body-potential norms, inner
free-surface normal-derivative norms, control-potential norms,
control-normal-derivative norms, and phase/alignment of each source solution
relative to the full solution.

The formal recommended-style run uses the first `A33/A53` rows, heave and pitch,
39 active stations, and 3 RHS sources, giving 468 detail rows and 12 summary
groups. All rows pass: the maximum source-sum relative residual is about
`1.6e-15`. This proves the decomposition is exact at the linear-system level.

The source balance is highly informative. The median source-solution to
full-solution norm ratio is about `0.61-0.71` for `body_normal_velocity`, about
`0.88-0.91` for `inner_free_surface_potential`, and only about `0.002-0.003`
for `outer_control_history`. The median control-potential and
control-normal-derivative norms show the same ordering: the inner free-surface
known potential is the dominant driver of the control-surface unknowns, while
the outer history RHS is tiny in the current recommended Wigley first-row case.

This changes the next Gate 1 priority. The Eq. (24) history kernels, history
queue, and outer-control row are now internally consistent, but the main scale
path feeding the near-cancelling Eq. (24) control-surface balance comes through
Eq. (23) and the marched inner free-surface potential. The next diagnostic
should therefore focus on the inner free-surface state fed into Eq. (23):
`free_surface_potential_by_station`, the BIE-derived
`inner_free_surface_normal_derivative`, their interpolation/marching scale, and
how that state propagates into Eq. (30) pressure and Eq. (32) forward-speed
terms.
