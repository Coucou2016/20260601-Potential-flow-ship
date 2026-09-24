# 下一阶段目标与验收条件

日期：2026-07-30

## 1. 总目标

下一阶段的目标不是继续堆叠更多近似公式，而是把当前“可扩展、可测试、边界清楚”的第一轮框架推进成一个可被公开文献逐项验收的高速船耐波计算程序。

最小完整目标定义如下：

1. 对单体高速船，实现 Ma-Duan-Song 型线性 2.5D 求解链：站位几何、局部时间 marching、内域简单 Green 函数、外域瞬态自由面历史项、控制面匹配、压力积分、前进速度梯度项、端部项、整船 heave/pitch 系数装配。
2. 对滑行艇纵向运动，实现规则波和不规则波下 heave、pitch、垂向加速度、艏部加速度、均方根和峰值统计的可重复计算。
3. 对多体船，先以 Delft 372 双体船为真实几何 benchmark，完成两片体共同横剖面边界积分接口，再进入 B1/B2 的运动响应和连接载荷验证。
4. 对强非线性滑行与跳跃问题，保留 Sun-Faltinsen 型 2D+t BEM 为独立生产内核，不把 reduced-order planing load provider 误称为真实 2D+t。
5. 所有输出都必须附带 `ValidityReport` 或等价状态，明确 `PASS`、`FAIL`、`PENDING`、`BLOCKED` 或 `NOT_EVALUATED`。

## 2. 当前已经完成的硬成果

| 项目 | 状态 | 证据 |
|---|---|---|
| 14 份 Markdown 资料接收 | 已完成 | `D:/Projects/20260601-Potential-flow-ship/20260729-文献收集/md` |
| Delft 372 B2 offsets 提取 | 已完成 | `benchmarks/delft372/delft372_demihull_offsets.csv` |
| Delft 372 几何审计 | 已通过 | 两片体排水质量 `86.219 kg`，对 B2 `87.07 kg` 误差约 `0.98%` |
| Delft 372 配置入口 | 已完成 | `configs/delft372_demihull_offsets.yml` |
| A1 局部时间 marching 网格 | 已完成基础实现 | `build_section_marching_grid()` |
| A1 内域简单 Green 函数块 | 已完成基础实现 | `assemble_inner_domain_system()` |
| A1 外域瞬态自由面历史项 | 基础闭环已完成，系数装配未完成 | 已有历史核、控制面方程块和 Eq. (23)-Eq. (24) matched square system |
| SL-7 真实 offsets | 缺失 | 当前只能使用 surrogate，不能验收 |
| C1 三体船真实 offsets | 缺失 | 当前只能使用 surrogate，不能验收 |

## 3. 必须满足的数据条件

| 数据对象 | 是否必须 | 当前状态 | 验收要求 |
|---|---:|---|---|
| A1 Wigley III coefficient curves | 必须 | 已有数字化文件，仍需复核坐标轴和归一化 | 每条曲线必须记录图号、坐标轴、无量纲方式和速度案例 |
| A1 SL-7 offsets | 条件必须 | 未找到 | 未找到前 SL-7 不进入硬验收 |
| B2 Delft 372 offsets | 必须 | 已完成 | 几何静水误差小于 2% |
| B1/B2 Delft 372 response curves | 必须 | 待数字化 | heave、pitch、主要六自由度和连接载荷曲线转 CSV |
| C1 trimaran offsets | 条件必须 | 未找到 | 未找到前 C1 不进入硬验收 |
| Fridsma/Katayama curves | 必须 | 部分已有 | 规则波运动、加速度、不规则波统计和跳跃分类要分开验收 |

## 4. 下一阶段验收门

| Gate | 目标 | 通过条件 | 不通过时的解释 |
|---|---|---|---|
| Gate 1 | A1 线性 2.5D 完整内核 | Wigley III 对角水动力系数误差不超过 15%，耦合项误差不超过 30% | 说明内外域匹配、自由面历史项、压力梯度项或端部项仍需修正 |
| Gate 2 | Delft 372 几何和多体装配 | 两片体按中心距 `0.70 m` 共同装配，几何静水误差不超过 2% | 如果失败，优先检查坐标比例、水线、左右片体间距和质量密度 |
| Gate 3 | Delft 372 多体水动力 | cross-radiation 和 cross-diffraction 在矩阵中显式出现 | 如果只是左右片体独立相加，不能通过此门 |
| Gate 4 | B1/B2 运动响应 | 主峰位置误差不超过 10%，主要幅值误差目标为 15% 到 20% | 如果几何已过而响应不过，问题主要在辐射/绕射/耦合而不是 offsets |
| Gate 5 | Sun-Faltinsen 2D+t 最小闭环 | 楔形入水和 V 型柱入水趋势正确，再进入 Fridsma/Katayama | 如果基础入水不稳，不能直接进入滑行艇波浪响应 |
| Gate 6 | Fridsma/Katayama 滑行艇响应 | 运动幅值误差目标不超过 25%，加速度误差目标不超过 35%，清晰跳跃案例分类正确 | 若加速度先不过，不代表运动响应全错，需分离峰值、入水冲击和湿长变化误差 |

## 5. SL-7、C1 和替代对象的结论

### SL-7

当前不能作为硬验收几何。A1 中可以用 SL-7 的主尺度和曲线检查趋势，但真实 station offsets 没有进入程序前，`make_sl7_surrogate_hull` 只能做数值流程和稳定性 smoke test。

可替代对象：

1. Wigley III：优先用于 Ma 2005 线性 2.5D 水动力系数验收，因为几何解析、可复现、不会被 offsets 缺失卡住。
2. 潜没椭球：适合验证内外域匹配和瞬态自由面历史项的基础行为。
3. Delft 372：适合替代为真实多体几何 benchmark，但它不是 SL-7 的单体船验证替身。

### C1 三体船

当前不能作为硬验收几何。C1 文献给出主尺度、布局参数、速度点、heave、pitch 和 added resistance 曲线，但未提供主片体和侧片体的机器可读 offsets。三体船的核心是主片体和侧片体水动力干扰，不能用三个独立 surrogate 简单相加代替论文验证。

可替代对象：

1. Delft 372：先完成双体船共同边界积分和 cross-radiation/cross-diffraction。
2. 解析三体 surrogate：只用于拓扑、装配、历史项数据结构和趋势检查，必须标记 `SURROGATE_NOT_FOR_VALIDATION`。

## 6. 立即执行顺序

1. 增加 A1 matched system 的相邻站位压力梯度项和端部项。
2. 沿站位形成整船 heave/pitch 系数装配。
3. 用 Wigley III 跑第一组 Ma 2005 coefficient gate。
4. 数字化 B1/B2 Delft 372 运动和连接载荷曲线。
5. 实现 Delft 372 左右片体共同横剖面边界积分，而不是独立片体相加。
6. 在 2D+t 方向先做楔形入水最小闭环，暂不把它混入线性 2.5D 验收。

## 7. 2026-07-30 执行更新

原第 1 项“完成 A1 外域瞬态自由面 Green 函数历史项和控制面匹配矩阵”已经推进为可测试基础接口：

| 已新增接口 | 说明 |
|---|---|
| `build_transient_free_surface_history()` | 生成 Eq. (12)/(28) 的控制面瞬态 Green 函数历史核 |
| `TransientFreeSurfaceHistory.convolution_rhs()` | 计算 Eq. (24) 右端历史卷积 |
| `initialize_free_surface_state()` / `advance_free_surface_state()` | 实现 Eq. (19)-(22) 的交错自由面推进 |
| `Matched2p5DSectionSolver.assemble_outer_control_surface_system()` | 组装 Eq. (24) 外域控制面方程块 |

该步骤已在 2026-07-31 推进为完整 matched square system；下一步转入压力恢复和整船系数装配。

## 8. 2026-07-31 执行更新

上一节末尾的 matched square system 已经完成基础实现。新增 `MatchedSectionBoundaryData` 和
`Matched2p5DSectionSolver.assemble_matched_section_system()`，将 Eq. (23) 与 Eq. (24) 统一为方阵。

新的下一步是从方阵解进入水动力系数：

| 下一步 | 说明 |
|---|---|
| 体面势提取 | 从 `psi_body` 标签切片恢复湿体表面势 |
| 压力恢复 | 由势的时间/频率关系形成辐射压力，基础接口已完成 |
| 前进速度梯度项 | 避免数值差分 `partial psi / partial x` 时的噪声，按 A1 后续公式处理 |
| 端部项 | 补齐整船积分边界贡献 |
| 系数装配 | 输出 `A33, B33, A35, B35, A53, B53, A55, B55` |

## 9. 2026-07-31 压力恢复更新

已新增 `split_matched_section_solution()`、`recover_body_pressure_from_matched_solution()`、
`integrate_section_heave_pitch_force()` 和 `pressure_force_to_added_mass_damping()`。这说明从方阵解到单站压力、
单站 heave 力、单站 pitch 力矩的链条已经可测试。

站位方向的 `U * partial phi / partial x` 基础梯度接口和整船系数装配接口已经在下一节补上；仍未完成的是
A1 Eq. (32) 的端部站位/方向验证、真实 matched station sweep 接入以及 Wigley III 曲线验收。

## 10. 2026-07-31 站位梯度与整船装配更新

已新增 `estimate_body_potential_x_gradient()`、`assemble_whole_ship_heave_pitch_coefficients()`、
`assemble_heave_pitch_from_matched_station_solutions()`、`compute_heave_pitch_stokes_end_term_force_matrix()` 和
`solve_station_hull_heave_pitch_matched_sweep()`、`assemble_frequency_domain_from_matched_station_hull()` 和
`matched-wigley-sensitivity`：

| 已新增接口 | 当前用途 | 不能越界声明 |
|---|---|---|
| `estimate_body_potential_x_gradient()` | 沿船长方向计算体面势梯度，为前进速度压力项提供可测试输入 | 还没有在真实 Wigley III station sweep 上证明收敛 |
| `assemble_whole_ship_heave_pitch_coefficients()` | 将 heave-mode 与 pitch-mode 的单站广义力积分为整船 `A33/B33/A35/B35/A53/B53/A55/B55` | 端部项可由 Eq. (32) helper 或外部矩阵传入，但文献验收前不能视为完整物理闭环 |
| `assemble_heave_pitch_from_matched_station_solutions()` | 把多站 matched solution 批量接到梯度、压力、单站力和整船装配链条 | 它不生成真实 station solution，因此不能替代 Wigley III coefficient gate |
| `compute_heave_pitch_stokes_end_term_force_matrix()` | 计算 A1 Eq. (32) 的 `C_A` 轮廓端部项，并可直接传给整船装配接口 | 端部 station 选取、轮廓方向和符号仍需要文献曲线验收确认 |
| `solve_station_hull_heave_pitch_matched_sweep()` | 对 `StationHull` 执行 heave/pitch 两个 radiation 模态的 matched station sweep，并保留条件数、残差、自由面势/高程轨迹和求解顺序 | 当前已接入非零内自由面势 marching；下一步要做网格/时间步敏感性和 Wigley III gate |
| `assemble_frequency_domain_from_matched_station_hull()` | 把 matched sweep 的纵向辐射块转换成标准 `FrequencyDomainHydrodynamics`，便于验证器和报告复用 | 目前 excitation 为零，不能用于运动响应幅值验收 |
| `matched-wigley-sensitivity` | 快速生成 matched sweep 对 Ma 2005 Wigley III 数字化系数的诊断 CSV、summary 和 best-case 摘要 | 这是诊断入口，支持 pitch/端部/自由面时间步和历史项 sensitivity，`gate_role=diagnostic_matched_wigley_sensitivity_not_hard_gate`，不能替代完整 gate |

因此“立即执行顺序”更新为：

1. 用 `matched-wigley-sensitivity` 对 `solve_station_hull_heave_pitch_matched_sweep()` 的自由面 marching、时间步、面元数、控制面半径和端部项做系统敏感性检查。当前 CLI 已支持 `--compare-free-surface-marching`、`--compare-end-term`、`--compare-end-term-signs`、`--end-term-scales`、`--time-step-scales`、`--free-surface-velocity-scales` 和 `--history-rhs-scales`，并输出 `matched_wigley_sensitivity_best_cases.csv`。
2. 用 Wigley III 对 `C_A` 端部站位、方向和符号做敏感性检查，并保留端部项开关用于误差定位。A33 第一行 smoke 暂未显示端部项影响；`A35/A53/A55` 第一行 smoke 显示 `A35` 偏向 `+C_A`、`A55` 偏向 `-C_A`、`A53` 基本不受端部项影响，因此下一轮必须分解检查 lever arm、pitch radiation normal velocity、端部轮廓方向和 pitch moment 正负约定，不能用一个全局符号修正所有系数。最新 `outputs/matched_wigley_pitch_convention_smoke` 进一步表明：`A53` 的缺口来自 heave-mode 主体压力积分到 pitch moment 的贡献过小，而不是端部项缺失。
3. 用 `outputs/matched_wigley_free_surface_a53_smoke` 的结果继续校准自由面 marching：自由面关闭时 `A53≈3.16e-05`，自由面开启时 `A53≈1.306`，而参考值为 `0.150`。这说明自由面路径已经产生了正确类型的前后不对称力矩，但幅值、历史卷积或 `dt=dx/U` 映射仍未校准。
4. 用 `outputs/matched_wigley_a53_free_surface_scale_smoke` 和 `outputs/matched_wigley_fvscale_joint_smoke` 的结果回查自由面边界条件尺度：`free_surface_velocity_scale=0.1` 可让 A53 单点进入 30% 门槛，但 A33/A55 仍失败，因此不能作为全局调参；下一步要检查 normal derivative 的物理归一化、内外域 Green 函数尺度和 Eq. (19)-(24) 的时间层。
5. 首步自由面推进已按 A1 Eq. (21)-(22) 修正：第一站后的自由面势现在使用 `-0.5*g*psi_z*dt^2`，而不是全步 Eq. (19) 推进。`outputs/matched_wigley_free_surface_initial_step_fix_smoke` 显示该修正将 A53 自由面开启示例从约 `1.306` 降到约 `0.939`，仍需继续校准 normal derivative 尺度和控制面历史核。
6. 用 Wigley III 数字化曲线跑第一组 Ma 2005 coefficient gate。
7. 数字化 B1/B2 Delft 372 运动和连接载荷曲线。
8. 实现 Delft 372 左右片体共同横剖面边界积分，而不是独立片体相加。
9. 在 2D+t 方向先做楔形入水最小闭环，暂不把它混入线性 2.5D 验收。

## 11. 2026-07-31 A1 网格审计更新

已新增 A1 推荐网格审计，并把审计结果写入 `matched_wigley_sensitivity.csv`、`matched_wigley_sensitivity_summary.csv` 和 `matched_wigley_sensitivity_best_cases.csv`。当前审计标准为：控制面半径不小于 `3B`，内自由面面元数不小于 `11`，外自由面或控制面代理面元数不小于 `9`，`Fn_L <= 0.25` 时站位数不小于 `60`，较高速度诊断时站位数不小于 `40`。

最新两个输出目录给出新的阻塞判断：

| 输出目录 | 当前结果 | 对 Gate 1 的含义 |
|---|---|---|
| `outputs/matched_wigley_a1_grid_a53_smoke` | A1 推荐网格下 `A53=5.282`，参考 `0.150`，`gate_error_ratio=114.039` | 满足 A1 推荐网格并不能让 A53 收敛到文献值 |
| `outputs/matched_wigley_a53_station_count_grid_sweep` | `station_count=5/11/21/41` 时 A53 约 `0.518/3.556/3.951/5.282` | 误差随站位加密放大，说明主要问题不是粗网格，而是 marching/尺度/归一化链条 |

因此 Gate 1 新增一个硬性验收条件：在进入完整 Wigley III coefficient gate 前，A53 至少应表现出合理的网格收敛趋势；也就是站位数、控制面半径和自由面面元数提高后，误差不能系统性放大。若推荐网格仍使误差扩大，必须先检查 `dt=dx/U` 局部时间映射、内自由面 normal derivative 尺度、外域历史核归一化和 pitch moment 广义力装配。

已继续新增 `--write-station-diagnostics`，输出 `matched_wigley_station_diagnostics.csv`。在 `outputs/matched_wigley_a53_station_diagnostics` 中，A1 推荐网格 A53 第一行的最终累计主体积分为 `5.282`，最大单站归一化贡献为 `1.572`，位于靠艉的 `station_local_index=2`；最大自由面势范数也位于该站，最大内自由面法向导数范数位于相邻的 `station_local_index=1`。这些站位的 `solve_order_rank` 为 `36-37`，属于 bow-to-stern marching 后期。

因此下一轮 Gate 1 的最小验收动作更加具体：必须把 station 1-4 的 Eq. (21)-(24) 中间量逐步输出并复核；如果这些靠艉站位的自由面势、法向导数或历史 RHS 不能随时间步/面元加密表现出有界收敛，则不得把整船 A53 的任何经验调参结果视为物理验证。

最新实现已经把上述中间量写入站位诊断。`outputs/matched_wigley_a53_station_diagnostics` 的刷新结果显示：station `1-6` 的 `free_surface_update_kind` 全部为 `advance_eq19_20`，最大外域历史 RHS 范数为 `0.232`，出现在 station `1`；最大正贡献 `1.572` 出现在 station `2`；最大 after-update 自由面势范数 `30.955` 出现在 station `3` 推进后。由此可把下一轮验收动作收敛为三项小实验：

1. 固定或关闭 Eq. (24) 外域历史 RHS，观察 station `1-3` 的贡献是否显著下降；
2. 固定或关闭 Eq. (19)-(20) 自由面速度推进，观察 after-update 自由面势峰值是否消失；
3. 暂时关闭 `U * partial phi / partial x` 压力梯度通道，判断 A53 峰值是来自自由面势本身还是来自前进速度压力梯度放大。

只有当这些通道拆分后能解释 station `2` 的 `1.572` 单站贡献，并且推荐网格下 A53 呈现有界收敛趋势，Gate 1 才能继续进入完整曲线误差验收。

2026-07-31 后续三通道拆分已经完成。新增 `pressure_gradient_scale` 后，`outputs/matched_wigley_a53_channel_split` 显示：关闭 `U * partial phi / partial x` 压力梯度不改变 A53；关闭 Eq. (24) 外域历史 RHS 也几乎不改变 A53；只有关闭 Eq. (19)-(20) 内自由面速度推进时，A53 从约 `5.282` 降到近零。因此 Gate 1 的当前主要阻塞不在压力梯度项，也不在外域历史 RHS 的一阶影响，而在内自由面 normal derivative 推进尺度。

`outputs/matched_wigley_a53_free_surface_velocity_sign_scale` 进一步显示负号不是解法：`free_surface_velocity_scale=-1` 时 A53 约 `-6.749`，偏差更大。`outputs/matched_wigley_a53_free_surface_velocity_narrow_scale` 显示 `free_surface_velocity_scale=0.03` 可让 A53 单点变成 `0.148`，但 `outputs/matched_wigley_joint_fv0p03_recommended` 证明它不是全局修正：同一设置下 `A33=1.410`、`A35=-0.540`、`A55=-0.330`，均失败。

因此下一轮 Gate 1 的验收条件增加一条：任何自由面速度尺度修正必须同时改善 `A33/A35/A53/A55` 的趋势，并能由 A1 方程单位、法向方向或时间层推导解释；不得把 `free_surface_velocity_scale=0.03` 这种单点经验值写成生产默认值。

随后又补上 A1 第 3.3/3.5 节要求的 station-wise 水线外自由面诊断。旧 full-width 自由面把 `[-R, R]` 全部当作自由面，会穿过船体水线内部；新的 `--clip-inner-free-surface-to-waterline` 模式把自由面裁剪为左右两段水线外区域，并在站位之间插值 `zeta` 和 `psi`。

`outputs/matched_wigley_a53_free_surface_clipping_compare` 表明：水线裁剪将 A53 从 `5.282` 降到 `0.336`，station `2` 的单站贡献从 `1.572` 降到 `0.0699`。这是目前最强的结构性改进证据，说明 Gate 1 不能继续依赖 full-width 自由面作为生产默认。与此同时，`outputs/matched_wigley_joint_clipped_recommended` 表明裁剪模式下 `A33=4.558`、`A35=-0.712`、`A53=0.336`、`A55=0.0532`，联合 gate 仍失败。

因此下一轮 Gate 1 的具体条件再增加两条：

1. 内自由面生产路径必须采用 station-wise 水线外自由面，而不是 full-width 自由面；
2. 水线裁剪后必须继续复核 `n2i/n2e` 分区、自由面插值、端部项和 pitch 耦合约定，直到 `A33/A35/A53/A55` 不再出现只改善单个系数的情况。

2026-07-31 继续把 `n2i/n2e` 分区落实为可测试诊断。新增 `--two-zone-inner-free-surface` 与 `--compare-two-zone-inner-free-surface`，在 waterline-clipped 自由面基础上，把每侧水线外网格分为水线附近内区和外区延伸区。实现中同时加入退化区段保护：如果局部水线半宽已经接近最大水线半宽，强行分出很短内区会制造极小面元并导致条件数爆炸，因此短于单侧跨度约 `10%` 的分区会自动并入均匀分布。

随后又把 `resample_free_surface_state()` 改成左右分段插值。只要源或目标自由面网格存在明显中心间隙，上一站的 `zeta/psi` 就分别在左舷和右舷自由面内插值；落在新水线附近、但位于上一站自由面间隙内的点会钳制到同侧水线端点，而不是穿过船体内部间隙从另一侧插值。这一步是两区段和水线裁剪进入生产前必须具备的稳定性条件。

`outputs/matched_wigley_a53_two_zone_free_surface_compare` 显示：在 `station_count=41`、`free_surface_inner_panels=24`、`control_surface_panels=10`、`control_radius=3B` 条件下，one-zone waterline-clipped A53 为 `0.3685`，two-zone waterline-clipped A53 为 `0.4259`，参考值仍为 `0.150`。两区段不再出现未保护版本的巨大数值爆炸，但最大条件数仍从 `113.95` 增至 `465.54`，最大 after-update 自由面势范数从 `2.874` 增至 `12.301`。

`outputs/matched_wigley_joint_two_zone_recommended` 进一步证明两区段不是当前 Gate 1 的直接修正：`A33/A35/A53/A55` 的 one-zone 结果分别为 `4.662/-0.761/0.369/0.0343`，two-zone 结果分别为 `4.633/-1.270/0.426/-0.510`，全部仍未满足 Ma 2005 第一行门槛。尤其 `A35` 和 `A55` 对面元分布更加敏感，说明真正阻塞仍在内外域匹配尺度、自由面状态插值、端部项和 pitch generalized-force 装配，而不是简单缺少两区段网格。

因此下一阶段 Gate 1 的目标和肯定需要的条件应收敛为：

1. `build_two_zone_waterline_free_surface_geometry()`、station-wise 插值和 CLI 诊断必须保留，但默认生产路径暂以 waterline-clipped one-zone 为较稳基线；
2. 两区段网格必须通过网格收敛验收：加密 `free_surface_inner_panels`、`control_surface_panels` 和 `station_count` 后，`A33/A35/A53/A55` 不能出现符号翻转或系统性放大；
3. `zeta/psi` 的站位间插值已经做到不跨船体内部中心间隙；下一步必须继续做到不跨 `n2i/n2e` 退化短分区，并输出插值前后的能量/范数诊断；
4. 必须用 Ma 2005 Wigley III 至少首行四系数作为硬 gate，要求对角项 15%、耦合项 30%；未达标前，两区段结果只能标注为 diagnostic。

随后又把 A1 Eq. (24) 的历史卷积积分规则显式化。A1 第 3.4 节文字说明卷积积分采用 trapezoid method，因此新增 `history_convolution_rule` 和 CLI 参数 `--history-convolution-rules rectangle trapezoid`。默认规则改为 `trapezoid`，其中最老的保留滞后项使用半权；旧的等权求和作为 `rectangle` 诊断保留。

`outputs/matched_wigley_history_quadrature_compare` 表明，trapezoid 规则会按预期降低外域历史 RHS 峰值，例如 `A53` 的最大 `outer_history_rhs_norm_before_solve` 从 `0.1021` 降到 `0.0695`。但四系数变化很小：`A33` 从 `4.662` 到 `4.659`，`A35` 从 `-0.761` 到 `-0.756`，`A53` 从 `0.3685` 到 `0.3673`，`A55` 从 `0.0343` 到 `0.0377`，仍全部失败。因此历史卷积权重已按 A1 规范化，但它不是当前 Gate 1 的主阻塞。下一轮若继续处理外域历史项，应优先复核 transient Green 函数核的归一化、法向导数方向和控制面即时项，而不是只调积分权重。

进一步的历史核分通道诊断也已经完成。新增 `--history-potential-kernel-scales` 和 `--history-normal-derivative-kernel-scales`，分别作用于 Eq. (24) 右端 `B^{m-k}_{ij} psi_n` 和 `C^{m-k}_{ij} psi` 两个历史通道。`outputs/matched_wigley_history_kernel_channel_compare` 的 A53 九宫格显示，无论 `B/C` 通道取 `-1/0/+1`，A53 只在 `0.360-0.369` 之间移动，仍高于 `0.150` 参考值。`outputs/matched_wigley_joint_history_kernel_channel_compare` 显示，`B` 通道反号可让 `A55` 单点进入门槛，但 `A33/A35/A53` 仍大幅失败。

因此 Gate 1 下一步不应把历史核通道反号固化为默认。新的最小验收动作是：检查 Eq. (24) 左端瞬时控制面项 `(A - Abar)`、`(B - Bbar)` 的镜像项符号、控制面法向方向和对角项；同时重新对齐 pitch generalized-force、pitch radiation body condition 与 A1 Eq. (32) 端部项的力矩正负约定。

该最小验收动作已经进入可测试状态。新增 `--control-image-scales`、`--control-potential-kernel-scales`、`--control-normal-derivative-kernel-scales` 和 `--control-diagonal-signs` 后，`outputs/matched_wigley_control_instant_a53_compare` 显示：当瞬时控制面镜像项采用 `control_image_scale=-1` 且对角项保持 `+1` 时，部分列符号组合可让第一行 `A53` 降至 `0.183-0.186`，相对 `0.150` 参考值进入耦合项 30% 门槛，且最大条件数约 `418`，不属于病态偶然解。随后 `outputs/matched_wigley_joint_control_image_compare` 证明，同一类组合能让 `A35/A53` 同时通过，但 `A33≈4.03` 和 `A55≈0.34` 仍明显失败。因此下一步 Gate 1 的目标应从“寻找单个符号修正”改为“联合闭合四系数”：以 `control_image_scale=-1` 作为 Eq. (24) 镜像项公式审计线索，继续复核 `A33` 的体面/自由面/控制面单位闭合，以及 `A55` 的 pitch radiation、pitch moment 和 Eq. (32) 端部项正负约定。未能让 `A33/A35/A53/A55` 同时满足对角项 15%、耦合项 30% 前，所有这些控制面参数都只能保持为 diagnostic。

随后新增 A1 Eq. (30) 压力分量诊断，把总压力拆为 `-rho*i*omega*phi` 和 `rho*U*partial phi/partial x` 两部分，并把分量贡献写入 `matched_wigley_sensitivity.csv` 与 `matched_wigley_station_diagnostics.csv`。`outputs/matched_wigley_a33_a55_pressure_component_diagnostics` 的代表性结果显示：`A33` 的最接近单点结果 `0.886` 完全来自时间导数压力；`A35=-0.215` 的通过主要来自前进速度梯度项 `-0.267`；`A53=0.142` 主要来自时间导数压力；`A55=0.0377` 则是时间导数项 `0.181` 与前进速度项 `-0.143` 抵消后的失败结果。因此下一步的 Gate 1 验收动作必须针对 pitch 模态的 `U partial phi / partial x`、lever arm、pitch body condition 和 Eq. (32) 端部补偿做联合审计，而不是继续使用单一自由面速度 scale 或单一控制面符号来贴合某个系数。

进一步又把 `partial phi / partial x` 的站位差分格式显式化为 `--pressure-gradient-schemes central forward backward`。`outputs/matched_wigley_pressure_gradient_scheme_compare` 表明：`A35` 对差分格式敏感但三种格式中至少有组合能通过，`A55` 则在三种格式下仍全部失败，最佳 central 约 `0.0377`、backward 约 `0.0333`、forward 约 `0.3009`，参考值为 `0.063`。因此差分方向不是 A55 的直接修正；下一步应把 Eq. (32) 端部项作为替代/补偿 `partial phi / partial x` 差分误差的主要审计对象，并同步检查 pitch body condition 的 `U m_j` 项和 pitch generalized-force 参考点。

随后把 pitch body condition 的 `i omega N5` 与 `U m5` 两个通道写入 station diagnostics，并用 `outputs/matched_wigley_pitch_body_condition_channel_compare` 扫描 `pitch_radiation_lever_sign=0/+1/-1` 与 `pitch_forward_speed_sign=0/+1/-1`。结果显示：默认 `U m5` 符号下 `A35=-0.215` 通过但 `A55=0.0377` 失败；反号 `U m5` 时 `A55=0.0687` 通过但 `A35=+0.319` 符号错误。由此可判定，A55 不能通过简单反号 `m5` 解决，真正缺口在 `T_ij` 的行列互易性和 Eq. (32) 的 Stokes 装配：必须显式装配 `rho U integral phi_j m_i ds` 与 `-rho U integral_CA phi_j N_i dl`，而不是只依赖 Eq. (30) 的有限差分压力梯度。

本轮已把 Eq. (32) 的 `rho U integral phi_j m_i ds` 作为显式诊断接入。新增 `compute_heave_pitch_stokes_body_forward_speed_force_matrix()`、`StokesBodyForwardSpeedForceMatrix`、`stokes_body_forward_speed_force_matrix` 和 station-level `cumulative_stokes_body_forward_speed_value` 等输出；结果写入 `outputs/matched_wigley_eq32_stokes_body_diagnostics`。聚焦首行结果表明：`A35` 的 Eq. (32) 体积分前进速度项为 `0`，这是因为 heave row 有 `m3=0`；`A55` 的 Eq. (32) 体积分前进速度项约为 `+0.699`，反号约为 `-0.699`，幅值远大于参考 `0.063`。因此 Eq. (32) 体积分项已经实现为可审计对象，但不能直接替代 Eq. (30) 有限差分前进速度项。下一步验收条件收敛为：必须同时拆解 `C_A` 端部项的 heave/pitch row、端部站位方向和轮廓法向约定，并验证 `time + Eq32 body + Eq32 end` 在同一设置下同时改善 `A33/A35/A53/A55`；否则 Gate 1 继续保持 `PENDING`。

端部平衡扫描也已完成，输出目录为 `outputs/matched_wigley_eq32_stokes_end_body_balance`。在 `end_station=aft/bow` 与 `end_term_scale=+1/-1` 四组合中，aft `+C_A` 能把 Eq.30 路线的 `A55` 从无端部时的 `0.219` 降到 `0.127`，但完整 Stokes 路线仍为 `0.805`，远高于 `0.063`；bow 端部项更小，不能形成有效抵消。由此确认：端部项符号不是当前 Gate 1 的独立解法。下一步必须回到坐标映射和行列定义本身，逐项核对 `m5/N5`、`normal_z`、`lever=Lcg-x`、pitch moment row sign、控制面端部轮廓方向，以及 A1 Eq. (32) 从论文坐标到程序 `z_down/heave_up` 约定的变换。

坐标/广义力行自洽性审计也已完成，输出目录为 `outputs/matched_wigley_a1_convention_audit`。新增 `audit_heave_pitch_a1_convention()` 后，station diagnostics 可以直接给出 `N3`、`N5`、`m5` 与程序 heave/pitch row 的相对残差。默认 `pitch_radiation_lever_sign=+1`、`pitch_forward_speed_sign=+1` 时，A55 末站 `N5` 残差约 `1.4e-16`、`m5` 残差为 `0`；反号时相应残差变为 `2`。这说明当前默认实现内部是自洽的，但仍不能通过 Ma 2005；因此下一步不是继续扩大符号扫描，而是建立固定 convention layer，逐公式写清 A1 论文坐标、法向、`x` 原点和程序 `z_down/heave_up`、heave-up force row 之间的映射。

固定 convention layer 已落地。新增 `A1HeavePitchCoordinateConvention` 和 `DEFAULT_A1_HEAVE_PITCH_CONVENTION` 后，heave/pitch body condition、Eq. (30) pressure row、Eq. (32) body `m_i` row 和 Eq. (32) end-contour `N_i` row 均由同一对象生成。`outputs/matched_wigley_a1_convention_layer` 证明该重构没有改变默认数值：`A35=-0.462`、`A55=0.219`，仍为 `FAIL`。下一步 Gate 1 验收动作应在这个 convention layer 上补一张固定映射表：A1 paper `z/N_z/x/N5/m5` 到程序 `z_down/normal_z/LCG-x/heave_up/pitch_moment` 的逐项变换，并用 Wigley III 四系数验证任何变换修改。

该固定映射表也已经机器可读化。`A1CoordinateMappingRow` 和 `paper_to_package_mapping_rows()` 现在给出 9 行映射，覆盖 section `z`、`N3`、`N5`、`m3`、`m5`、Eq. (30) pressure rows、Eq. (32) body rows 与 Eq. (32) end-contour rows。`outputs/matched_wigley_a1_mapping_table` 证明输出 CSV 已携带 `a1_coordinate_convention_name=package_z_down_heave_up_lcg_minus_x` 和 `a1_coordinate_convention_status=a1_heave_pitch_coordinate_convention_layer_not_benchmark_validated`。下一步如果改符号或力矩臂，必须先指出对应映射表行，并保持 Gate 1 四系数联合验收，而不能只报告单个 A55 或 A35 变好。

上述“必须引用映射表”的要求已经进一步转成可执行诊断：新增 `A1ConventionCandidate`、`a1_convention_candidate_cases()` 与 `write_a1_convention_candidate_benchmark()`。推荐网格输出目录为 `outputs/matched_wigley_a1_convention_candidates`，其中 `a1_convention_candidate_mapping.csv` 明确记录每个候选改动了哪几行映射表，`a1_convention_candidate_best_cases.csv` 则按 `A33/A35/A53/A55` 给出最佳候选。当前首行四系数探针的最佳结果为：`A33=4.554` 对参考 `1.000`，`A35=-0.668` 对参考 `-0.200`，`A53=0.334` 对参考 `0.150`，`A55=0.0847` 对参考 `0.063`；所有候选仍为 `FAIL`，且没有一个候选能同时改善四个系数。由此 Gate 1 的下一步目标收窄为：复核 Eq. (23)-Eq. (24) 内外域匹配、控制面瞬时项和自由面尺度，不能继续把单个 pitch 符号候选当作生产修正。

Eq. (24) 控制面瞬时项也已经改成受控候选诊断。新增 `A1ControlSurfaceCandidate`、`a1_control_surface_candidate_cases()` 与 `write_a1_control_surface_candidate_benchmark()` 后，推荐网格输出 `outputs/matched_wigley_a1_control_surface_candidates` 显示：`reverse_image_and_both_columns` 是 `A33/A35/A53` 的相对最佳候选，但仍给出 `A33=4.220`、`A35=-0.458`、`A53=0.233`，全部失败；`A55` 的相对最佳候选为 `reverse_image_terms`，结果 `A55=0.152`，仍失败。单独反 potential 列、normal-derivative 列或 diagonal 自项会产生病态巨大系数。由此新增 Gate 1 约束：不得把 Eq. (24) 单项符号反号写成生产默认；下一步必须复核控制面核函数量纲、法向方向和整块匹配矩阵尺度，并继续用四系数联合门评价。

同时，matched Wigley sensitivity 行已加入 `ma2005_normalization_formula` 和所需归一化尺度倍率字段。A1 Eq. (34) 明确采用 `rho*∇`、`rho*∇*L` 和 `rho*∇*L^2`，当前首行 A33 若要靠归一化解释需把尺度放大约 `4.55` 倍，已标记为 `normalization_scale_unlikely_as_sole_explanation`。因此 A33 的下一步应优先审计 heave section radiation、控制面匹配和自由面法向导数尺度，而不是更换 Ma 2005 无量纲公式。

Eq. (23)-Eq. (24) 的 block-level audit 也已经落地。新增 `MatchedSystemBlockAudit` 和 `audit_matched_system_blocks()` 后，station diagnostics 可以输出 `a1_eq23_body_relative_residual`、`a1_eq24_outer_control_relative_residual`、四个未知量块范数、最大矩阵块标签和最大贡献块标签。推荐网格输出 `outputs/matched_wigley_a1_block_audit` 表明：首行 `A33` 和 `A53` 的最大单站贡献都由 `eq23_body<-psi_body` 主导；在 39 个活跃站中，两者均有 37 个站的最大贡献块为 `eq23_body<-psi_body`。因此 Gate 1 的下一步验收动作应优先复核 Eq. (23) body row 的 raw log kernel、自项、`2π` 归一化和 `psi_body` 单位尺度。只有当该内域体面势块的尺度解释闭合后，才继续判断 Eq. (24) 历史项或控制面项是否仍是主阻塞。

Eq. (23) inner-kernel 归一化候选也已完成。新增 `A1InnerKernelCandidate` 与 `write_a1_inner_kernel_candidate_benchmark()` 后，输出 `outputs/matched_wigley_a1_inner_kernel_candidates_joint` 显示：`Aij/Bij` 同除 `2π` 与 raw Eq. (25) 默认值完全相同，符合整行缩放不改线性解的预期；仅 `Bij` 除 `2π` 是四系数首行的共同最佳候选，但仍全部失败，结果为 `A33=0.749`、`A35=-0.111`、`A53=0.0157`、`A55=-0.0300`。因此新增 Gate 1 约束：不得把 `Bij/2π` 写成生产默认；下一步必须解释为什么 B-only 归一化会系统性降低 heave/pitch 体面势贡献，同时闭合 `psi` 与 `psi_n` 的单位尺度和 Eq. (30) 压力恢复。

该单位闭合诊断已经进入 station diagnostics。新增字段 `a1_unit_*` 后，`outputs/matched_wigley_a1_unit_closure_probe/a1_unit_closure_summary.csv` 对推荐网格的 raw Eq. (25) 与 `Bij/2π` 做了对照：raw 情况下 `a1_unit_body_potential_per_normal_velocity_over_span` 的中位数约为 `4.210`，最大值约为 `200.892`；`Bij/2π` 后中位数降为 `0.783`，最大值仍有 `40.685`。同时 `a1_unit_pressure_time_over_rho_omega_phi_norm_ratio=1.0`，说明 Eq. (30) 时间导数压力公式本身闭合，主要疑点在 Eq. (23) 求得的体面势尺度，而不是 `-rho*i*omega*phi` 的直接实现。

同时，`outputs/matched_wigley_a1_inner_b2pi_convention_candidates` 证明 `Bij/2π` 与 pitch convention 候选组合仍不能通过四系数联合门：最佳 `A33=0.749`、`A35=-0.111`、`A53=0.0157`、`A55=0.0300`，对应 gate error ratio 分别约为 `1.67`、`1.49`、`2.99` 和 `3.49`。因此 Gate 1 的下一步约束进一步收紧：任何声称修正 inner-kernel 归一化的改动，必须同时解释 `psi_body` 的局部长度尺度、`psi_n` 的速度尺度、body/free/control 三类边界块的共同量纲，以及 pitch mode 的 `N5/m5/U*m_j` 坐标变换；只靠 `Bij` 单独除 `2π` 或 pitch 行反号仍只能记为 diagnostic。

进一步的闭合边界 Green 恒等式审计已经完成，输出目录为 `outputs/matched_wigley_a1_inner_kernel_green_identity`。该审计在闭合椭圆边界上使用四个解析调和势函数，直接检查 Eq. (23) 的 `A phi - B phi_n = 0`。结果显示：`raw_eq25_default` 对四种调和势全部通过，最细网格相对残差约 `0.0050-0.0090`；`Aij/Bij` 同除 `2π` 也通过，因为它只是整行缩放；但 `Bij` 单独除 `2π`、Eq. (23) 自项改为 `+π`、A/B 反号全部失败。由此 Gate 1 的下一步判断更新为：raw Eq. (23) 内域 kernel 在闭合数学问题上是自洽的，当前 Wigley 误差更可能来自开边界 body/free/control 混合系统的单位配平、自由面状态传递、控制面匹配或 pitch 模态坐标变换，而不是闭合边界意义下的 `Bij` 单项归一化。

body/free/control 混合边界审计也已经完成，输出目录为 `outputs/matched_wigley_a1_inner_mixed_boundary_identity`。该审计把同一个闭合椭圆切成三段，并按真实 matched solver 的 Eq. (23) 已知/未知设置代入解析势：body 已知 `phi_n`，inner free surface 已知 `phi`，control 的 `phi` 与 `phi_n` 均作为未知。结果显示：`raw_eq25_default` 对四种调和势全部通过，最细网格总相对残差约 `0.00697-0.0160`；`Bij` 单独除 `2π`、`+π` 自项和 A/B 反号全部失败。由此 Gate 1 的阻塞进一步收窄：Eq. (23) 内域 raw kernel、`-π` 自项、body/free/control 的搬项符号都不再是首要嫌疑，下一步应集中审计 Eq. (19)-Eq. (22) 自由面状态推进、Eq. (24) 外域控制面匹配、station 历史继承、Eq. (30)/Eq. (32) 前进速度项关系和 pitch 模态坐标变换。
## 2026-07-31 新增条件：A1 Eq. (19)-Eq. (22) 自由面时间层通过解析审计

已新增 `outputs/matched_wigley_a1_free_surface_oscillator_audit`。该审计使用解析线性自由面振子直接驱动 `initialize_free_surface_state()` 和 `advance_free_surface_state()`，并按程序交错时间层分别检查 `eta(half_step_time_s)` 和 `phi(time_s)`。四个步长 `0.08/0.04/0.02/0.01 s` 的最大归一化误差分别为 `0.032451/0.008106/0.002026/0.000512`，高程和势的 RMS 观测收敛阶分别约为 `1.999` 和 `2.014`。

因此 Gate 1 的当前判定更新为：A1 Eq. (19)-Eq. (22) 离散推进本身具备解析层面的二阶收敛证据，但这不是完整水动力 gate。后续若 Wigley III `A33/A35/A53/A55` 仍失败，不应优先修改自由面首步/续步公式，而应集中审计 BIE 求得的内自由面 normal derivative 尺度、station-to-station 自由面状态继承、Eq. (24) 控制面匹配矩阵、Eq. (30)/Eq. (32) 前进速度项和 pitch 广义力装配。
## 2026-07-31 新增条件：A1 Eq. (24) 控制面瞬时项通过半平面解析审计

已新增 `outputs/matched_wigley_a1_outer_control_green_identity`。该审计用控制面内部的反对称镜像点源 `phi=ln(r)-ln(r')` 检查 Eq. (24) 无历史瞬时项。由于该解析场在外域半平面内调和且在自由面为零，它能直接检验 `(A-Abar)`、`(B-Bbar)`、控制面法向导数列和 Eq. (24) `+pi` 对角自项是否自洽。

输出显示：`default_control_terms` 在最细网格的最大相对残差为 `0.000686`，全部通过；`reverse_image_terms` 的最细残差为 `0.808718`，全部失败；`reverse_diagonal` 和单列反号残差约为 `1.0`，全部失败。`reverse_both_columns` 也通过，但这是无历史 RHS 情况下的整体行符号歧义，不能单独作为完整 Eq. (24) 生产默认。

因此 Gate 1 的新约束为：不得把 `control_image_scale=-1` 写成生产修正，即使它曾在 Wigley III 局部候选扫描中改善 A35/A53。下一步必须转向 Eq. (24) 历史 RHS 与瞬时项的联合符号/尺度、station-to-station 控制面历史继承、内自由面 normal derivative 尺度、Eq. (30)/Eq. (32) 前进速度项和 pitch 广义力装配。
## 2026-07-31 新增条件：A1 Eq. (28) 历史核法向导数通道通过有限差分审计

已新增 `outputs/matched_wigley_a1_history_kernel_derivative_audit`。该审计直接检查 Eq. (28) 中 `C_ij^{m-k}` 是否等于 `B_ij^{m-k}` 对源控制面法向的导数：把源面元配点沿法向扰动 `+epsilon/-epsilon`，用势核中心差分近似法向导数，再与程序实现的 normal-derivative kernel 比较。

在 `panel_count=8/16/32`、`lag_s=0.02/0.05/0.10`、`quadrature_count=256`、`k_max=50`、`epsilon=1e-4 m` 下，全部审计行通过，最大相对残差约 `1.05e-6`。因此 Gate 1 的新判断为：Eq. (28) 历史核的法向导数通道本身已经有独立闭合证据。

这不是完整历史 RHS 的通过条件。下一步仍必须检查：历史卷积时间权重和符号、`k_max`/quadrature 截断收敛、control-surface history inheritance、当前瞬时项与历史 RHS 的相位关系，以及这些量进入 Wigley III `A33/A35/A53/A55` 时是否满足联合门槛。
## 2026-07-31 新增条件：A1 Eq. (24) 历史 RHS quadrature/cutoff 收敛通过参考核审计

已新增 `outputs/matched_wigley_a1_history_rhs_convergence_audit`。该审计用确定性的光滑复数控制面历史状态生成 Eq. (24) 历史 RHS，并把每个 `quadrature_count/k_max` 候选与高精度参考核比较。审计同时拆分总 RHS、`B_ij^{m-k} psi_n` 势核通道和 `C_ij^{m-k} psi` 法向导数核通道。

在 `panel_count=10`、`dt=0.05 s`、`history_steps=4`、`quadrature_rule=trapezoid`、参考核 `768/120` 条件下，所有行通过 `1e-3` 诊断阈值。最大通道残差从 `(quadrature_count=48, k_max=40)` 的 `8.63e-4` 降到 `(quadrature_count=256, k_max=80)` 的 `4.94e-5`。误差主要来自 `B_ij psi_n` 势核通道；`C_ij psi` 通道已经小到 `1.27e-5` 至 `5.91e-8`。

因此 Gate 1 的新判断为：合成历史状态下，Eq. (24) 历史 RHS 对 Eq. (28) 核的 quadrature/cutoff 加密有清晰收敛证据。下一步不应再优先怀疑瞬态核积分本身，而应审计真实 Wigley station sweep 中控制面历史状态如何继承、BIE 生成的 `psi_control/psi_n_control` 是否具有合理相位和尺度，以及历史 RHS 与 Eq. (24) 瞬时项联合进入整船系数时是否闭合。

## 2026-07-31 Gate 1 更新：Eq. (24) 站位历史继承已通过实现级审计

新增输出目录 `outputs/matched_wigley_a1_control_history_inheritance_audit`。
该审计用真实 Wigley station sweep 的 `solve_order` 和已返回的 station
solutions 重建 Eq. (24) 控制面历史队列，并逐站复算原求解前保存的 history
RHS。它同时检查 lag-0 历史项来自哪一个上一站，能捕捉求解方向反了、历史
队列错一站、heave/pitch mode 混用等实现错误。

推荐式运行使用 41 个站、12 个内自由面面元、10 个控制面面元、控制面半径
`3B` 和水线裁剪，对 Ma 2005 Wigley III 的首个 `A33/A53` 行同时检查 heave
和 pitch。结果为 156 条明细全部通过：四个汇总组 `A33/heave`、`A33/pitch`、
`A53/heave`、`A53/pitch` 均为 39 个 active stations 通过、0 个失败；
`rhs_relative_residual` 和 `max_lag0_relative_residual` 的最大值均为 `0.0`。

由此，Gate 1 的剩余阻塞不再优先怀疑 station-to-station 历史队列继承。下一步
必须集中在更物理的问题上：BIE 生成的 `psi_control/psi_n_control` 尺度和相位、
内自由面 normal derivative 尺度、Eq. (24) 历史 RHS 与瞬时项联合作用、Eq.
(30)/Eq. (32) 前进速度项、pitch 坐标/广义力映射，以及 Ma 2005 原图数字化
和无量纲归一化复核。Gate 1 仍为 `PENDING`，直到 `A33/A55` 对角项误差不超过
15%，`A35/A53` 耦合项误差不超过 30%。

## 2026-07-31 Gate 1 更新：Eq. (24) 外控制面分量尺度/相位已落地

新增输出目录 `outputs/matched_wigley_a1_outer_control_balance_audit`。该审计
在真实 Wigley station sweep 中逐站拆分 Eq. (24)：左端拆为瞬时 potential 列
贡献和瞬时 normal-derivative 列贡献，右端历史项拆为 `B_ij psi_n` 通道和
`C_ij psi` 通道，并输出范数比、实部对齐度和相位角。

推荐式运行与历史继承审计一致：41 个站、12 个内自由面面元、10 个控制面面元、
控制面半径 `3B`、水线裁剪，并检查 Ma 2005 Wigley III 首个 `A33/A53` 行的
heave 和 pitch。156 条明细全部通过 `1e-5` 的 Eq. (24) 行平衡容差，四个汇总
组最大相对残差约为 `1e-6` 到 `5e-6`。

更重要的是尺度/相位信息：`median_rhs_to_lhs_norm_ratio=1.0`，说明已求解的
瞬时控制面左端确实平衡历史 RHS；但瞬时 potential 列和 normal-derivative 列
几乎 180 度反相，`median_potential_normal_real_alignment` 约为 `-0.9998`；
两个历史卷积通道也强烈反相，`median_history_channel_real_alignment` 约为
`-0.91`。瞬时 potential/normal 范数中位比约 `1.03`，历史 `B_ij psi_n` /
`C_ij psi` 范数中位比约 `3.5-3.6`。

因此 Gate 1 的下一步不应继续排查 Eq. (24) 代码装配或历史队列，而应验证这种
近抵消结构在物理上是否正确：先固定 Eq. (24) 当前实现，转向 Eq. (23) 解出的
控制面 `psi_control/psi_n_control` 尺度来源、内自由面 normal derivative 尺度、
Eq. (30) 压力恢复、Eq. (32) 前进速度项，以及 pitch 广义力行映射的联合闭合。

## 2026-07-31 Gate 1 更新：RHS 源分解显示主驱动来自内自由面已知势

新增输出目录 `outputs/matched_wigley_a1_rhs_source_decomposition_audit`。该审计
保持每站 matched matrix 不变，只分别激活三类 RHS：`body_normal_velocity`、
`inner_free_surface_potential` 和 `outer_control_history`，然后检查三类源解相加
能否重构完整解，并统计每类源对 `psi_body`、内自由面法向导数、`psi_control`
和 `psi_n_control` 的贡献。

推荐式 Wigley 首行运行得到 468 条明细和 12 个汇总组，全部通过；最大
`source_sum_relative_residual` 约 `1.6e-15`。这说明源分解在线性系统层面精确。

新的关键结论是源贡献排序：`inner_free_surface_potential` 对完整解的中位范数比
约 `0.88-0.91`，`body_normal_velocity` 约 `0.61-0.71`，而
`outer_control_history` 只有约 `0.002-0.003`。也就是说，在当前推荐式 Wigley
首行案例中，外历史 RHS 不是控制面未知量尺度的主要来源；主驱动来自 Eq. (23)
中的内自由面已知势。

因此下一步 Gate 1 的最小验收动作更新为：固定当前 Eq. (24) 实现，集中审计
`free_surface_potential_by_station`、BIE 解出的
`inner_free_surface_normal_derivative`、自由面站间插值/推进尺度，以及这些量进入
Eq. (30) 压力和 Eq. (32) 前进速度项后的放大路径。若内自由面状态不能通过
有界性、网格收敛和四系数联合改善检查，则不得把任何外历史项调参当作生产修正。
