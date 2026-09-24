# 线性高速 2.5D `A33/A53` 方程链闭合阶段报告

日期：2026-08-15  
状态：**本阶段 `A33/A53` 目标通过；完整八系数 Gate 1 尚未通过**  
上位目标：[高速船型运动预报系统总体目标](./高速船型运动预报系统总体目标.md)

## 1. 摘要

本阶段针对 Ma--Duan--Song 型线性高速 2.5D 求解器中

```text
A1 Eq.23 RHS -> body potential -> Eq.30 time pressure -> Eq.32 force -> A33/A53
```

这一条方程链进行了公式级、边界级、站位级和分量级闭合。修正进入默认 `matched_bie_station_sweep` 路径，不包含最终系数缩放、按参考值拟合或经验 `1/pi^2` 补丁。

主要结果如下：

1. 固定低分辨率验证中，`A33/A53` 的 4 个参考行全部为 `PASS`，最大 `gate_error_ratio=0.678134`。
2. 文献离散量级 `Nx=41, n1=30, n2=20, n3=40` 下，4 个 `A33/A53` 点相对 Ma 2005 Matched BIEM 理论曲线的最大误差为 `1.8621%`。
3. 加密至 `n1=40, n2=30, n3=60` 后，最大网格变化为 `0.2422%`，两级网格的 4 个理论复现点均满足 `5%` 门槛。
4. Eq.19--Eq.22 自由面状态传递重构 `8/8` 通过，更新和传递残差均为 `0.0`。
5. Eq.23/Eq.24 RHS 三来源分解能够重构原 body potential，最大相对残差为 `4.0944e-15`。
6. 实际 Eq.32 装配路线的整船系数闭合残差不超过 `9.7145e-17`。
7. 体势归一化审计与 Eq.23→body potential→Eq.30→Eq.32 时间压力链审计均为 `PASS`，阻塞项均为 0。
8. 完整自动测试为 `278 passed`。

这些证据证明的是“`A33/A53` 理论求解器复现链已经闭合”，不是“完整八系数、独立试验或整船耐波性已经验证”。当前 10 个 Ma 理论参考行中有 9 行通过，`B55` 仍失败。

## 2. 阶段目标与边界

本阶段的硬目标是使 `A33/A53` 在默认求解路径中通过 Ma 2005 Wigley III Gate 1，并解释尺度、符号、相位和归一化来源。

本阶段不把以下内容列为完成声明：

1. `B55` 及完整八系数 Gate 1。
2. Journee 1992、Fridsma 或 Katayama 独立试验验证。
3. 规则波、不规则波整船运动响应验证。
4. 非线性 2D+t、多体船、三体船或水翼生产模型。

## 3. 参考数据分层

### 3.1 理论复现基准

`benchmarks/ma2005/wigley_iii_coefficients_digitized.csv` 中本阶段使用的基准是 Ma 2005 图 11 和图 13 的 Matched BIEM 理论曲线。数据记录了原图页码、图号、内嵌图像、数字化不确定度、归一化和求解配置。

该数据的角色是 `implementation_reproduction_gate`，用于回答“程序是否复现论文中的求解器结果”。

### 3.2 独立试验对照

Journee 1992 数据代表物理试验，不能与 Ma 理论曲线混为同一真值。Ma 论文已经显示部分理论系数与试验存在偏差，因此本阶段不通过修改默认求解器去追平试验表格。

结论应分层表述：

```text
Ma Matched BIEM 理论曲线通过 -> 实现复现证据；
Journee 试验差异             -> 后续物理验证证据；
二者不能互相替代。
```

## 4. 方程链与实现

### 4.1 局部时间与相位

高速 2.5D 方法把纵向站位映射为局部时间：

$$
t=\frac{x_0-x}{U},
\qquad
\psi=\phi\exp(i\omega t),
\qquad
\phi=\psi\exp(-i\omega t).
$$

其中，`x` 为纵向站位，`U` 为前进速度，`omega` 为圆频率，`psi` 为局部时间域势函数，`phi` 为整船频域复势。

由链式法则：

$$
\frac{\partial\phi}{\partial x}
=\exp(-i\omega t)
\left(
\frac{\partial\psi}{\partial x}
+\frac{i\omega}{U}\psi
\right).
$$

默认路径现同时启用 `apply_local_time_phase=True` 和 `local_time_phase_gradient_correction=True`。这不是相位调参，而是把 A1 Eq.7--Eq.10 的变量定义贯彻到压力恢复。

### 4.2 Eq.23 内域匹配边界积分

离散后的 Eq.23 可写成块算子形式：

$$
\mathbf{K}
\begin{bmatrix}
\phi_B\\
\phi_{n,F}\\
\phi_{n,C}
\end{bmatrix}
=
\mathbf{b}
\left(
v_{n,B},\phi_F,\mathcal{H}_C
\right).
$$

下标 `B`、`F`、`C` 分别表示船体、内自由面和固定控制面；`v_{n,B}` 是船体已知法向速度，`phi_F` 是自由面已知势，`mathcal{H}_C` 是 Eq.24 外域历史卷积产生的控制面项。

本阶段把 RHS 分为三项独立重求：

1. `body_normal_velocity`。
2. `inner_free_surface_potential`。
3. `outer_control_history`。

三项解之和必须重构完整 body potential。该审计证明最大重构残差为 `4.0944e-15`，因此没有用来源比例去修改最终系数。

### 4.3 船体边界法向

型线面元按“右舷水线--龙骨--左舷水线”遍历，几何中存储的法向指向船体外部流体。但在 A1 Eq.11/Eq.23 的内流域 Green 恒等式中，船体是流域的内边界，源法向应指向内流域之外，也就是指入船体。

因此只有 Green 核的船体源法向反向；面元位置、长度和未知量顺序保持不变。运动边界条件仍按本包的正向约定使用：

$$
N_3=-n_z.
$$

该约定由 `audit_body_boundary_inner_fluid_normal` 使用解析调和势在船体、自由面和控制面的复合边界上独立检验。加密网格下，正确法向残差相对错误法向继续下降。

关键实现位置：

1. `planing_seakeeping/kernels/linear_2p5d/formulation.py:2994`：构造内流域外法向。
2. `planing_seakeeping/kernels/linear_2p5d/formulation.py:3018`：复合边界法向审计。
3. `tests/test_unified_architecture.py:1776`：两级网格回归测试。

### 4.4 Eq.30 压力与 Eq.32 广义力

频域压力恢复采用线性 Bernoulli 形式：

$$
p=-\rho\left(i\omega\phi-U\phi_x\right).
$$

Eq.31 可直接保留纵向梯度项；Eq.32 则把相应的前进速度贡献变换为船体 Stokes 项和端部轮廓项。两个表达必须作为不同的等价装配路线使用，不能把 Eq.31 梯度和 Eq.32 Stokes/端部贡献重复相加。

当前生产路线固定为：

$$
F_{ij}=T_{ij}+S_{ij}+E_{ij},
$$

即 `force_assembly_route=eq32_stokes_body_plus_end`。其中 `T` 是 Eq.30 时间压力，`S` 是 Eq.32 船体 Stokes 项，`E` 是 Eq.32 端部项。

水动力复力与系数按当前谐波约定满足：

$$
F_{ij}=\omega^2 A_{ij}-i\omega B_{ij},
$$

再按 Ma Eq.34 的对应尺度无量纲化。本阶段新增的路线感知审计直接按每个求解结果记录的 `force_assembly_route` 重构广义力，最大闭合残差为 `9.7145e-17`。

## 5. 默认路径修正

本阶段进入生产默认的修正均有方程或边界定义依据：

1. 船体 Green 核源法向改为内流域外法向。
2. 船体边界条件统一使用 `N3=-normal_z`。
3. 首个有效站位采用正确的自由面局部时间推进关系。
4. 启用 A1 局部时间相位和压力梯度链式法则。
5. 内自由面裁剪到实际水线范围。
6. Eq.32 端部项使用实际端部，退化端部严格为零。
7. 默认广义力装配固定为 Eq.32 的 `T+S+E`。

以下内容没有进入默认路径：

1. `1/pi^2` 或其他 `pi` 因子经验缩放。
2. 最终 `A33/A53` 比例校准。
3. 单频或单系数拟合。
4. 常数势模态删除。
5. 按参考结果反推法向、符号或端部项。

## 6. 固定验证结果

固定命令为：

```powershell
python -m planing_seakeeping validate --benchmark all --out outputs\gate1_linear_2p5d_hard_pass\results --reference-root outputs\matched_bie_provider_gate_probe\reference --ma-hydro-model matched_bie_provider --ma-bem-free-surface-panels 4 --ma-bem-body-panels 8
```

该命令已完整运行，耗时约 `1646.5 s`。由于 `--benchmark all` 同时包含尚未完成的 Katayama、Fridsma、SL-7 和完整 2.5D 等检查，整体退出码为 1；这不改变 Ma `A33/A53` 子目标的逐行状态。

| 无量纲频率 | 系数 | Ma 理论值 | 计算值 | Gate Ratio | 状态 |
|---:|---|---:|---:|---:|---|
| 2.00 | A33 | 1.0700 | 1.018150 | 0.323050 | PASS |
| 2.23 | A33 | 0.9410 | 0.895492 | 0.322410 | PASS |
| 2.23 | B33 | 2.0500 | 1.786181 | 0.857947 | PASS |
| 2.00 | A53 | 0.1900 | 0.155445 | 0.606224 | PASS |
| 2.23 | A53 | 0.1450 | 0.115501 | 0.678134 | PASS |
| 2.23 | B53 | -0.1060 | -0.124932 | 0.595345 | PASS |
| 2.23 | A35 | -0.1250 | -0.113230 | 0.313867 | PASS |
| 2.23 | B35 | 0.1630 | 0.140337 | 0.463450 | PASS |
| 2.23 | A55 | 0.0458 | 0.040559 | 0.762816 | PASS |
| 2.23 | B55 | 0.0703 | 0.048332 | 2.083271 | FAIL |

表中 10 个计算值全部有限。`A33/A53` 为 `4/4 PASS`；完整表为 `9/10 PASS`，剩余失败项是 `B55`。

## 7. 文献离散量级复现

复现命令：

```powershell
python -m scripts.run_ma2005_a33_a53_reproduction --out outputs\ma2005_a33_a53_source_resolution
```

配置为 `Nx=41, n1=30, n2=20, n3=40`，与 A1 Section 4.2 的 Wigley III 离散量级一致。

| 频率 | 系数 | 参考值 | 计算值 | 相对误差 | 5% 门槛 |
|---:|---|---:|---:|---:|---|
| 2.00 | A33 | 1.070 | 1.076187 | 0.5782% | PASS |
| 2.23 | A33 | 0.941 | 0.947349 | 0.6747% | PASS |
| 2.00 | A53 | 0.190 | 0.186462 | 1.8621% | PASS |
| 2.23 | A53 | 0.145 | 0.144538 | 0.3189% | PASS |

这里的 `5%` 是实现复现误差门槛；CSV 中另列的 `gate_error_ratio` 使用图像数字化不确定度，是更严格且不同目的的统计量。两者不能混写。

## 8. 网格收敛

加密网格使用 `n1=40, n2=30, n3=60`。结果如下：

| 频率 | 系数 | 基准网格 | 加密网格 | 相对变化 | 5% 门槛 |
|---:|---|---:|---:|---:|---|
| 2.00 | A33 | 1.076187 | 1.074038 | 0.2000% | PASS |
| 2.23 | A33 | 0.947349 | 0.945061 | 0.2422% | PASS |
| 2.00 | A53 | 0.186462 | 0.186797 | 0.1795% | PASS |
| 2.23 | A53 | 0.144538 | 0.144706 | 0.1164% | PASS |

最大相对变化 `0.2422%`，说明 `A33/A53` 的通过不是 `4/8` 低分辨率网格的偶然结果。

## 9. 方程级审计

### 9.1 自由面状态

`ma2005_wigley_iii_coefficients_a1_free_surface_grid_implementation_summary.csv` 给出：

| 指标 | 结果 |
|---|---:|
| Eq.19--Eq.22 重构行 | 8 |
| 通过行 | 8 |
| 最大更新残差 | 0.0 |
| 最大传递残差 | 0.0 |
| 当前 A33/A53 目标行 | 4/4 PASS |

仍有 3 项显式网格/传递差距，主要是论文所述“自由面站位数为船体站位两倍”的完整半站位实现尚未进入生产路径。因此本审计证明当前状态传递自洽，但不宣称 A1 的所有离散细节已经逐字复现。

### 9.2 RHS 来源分解

`rhs_source_decomposition_summary.csv` 中，`A33/A53` 均包含 39 个有效站位和 3 个 RHS 来源，来源解相加重构状态为 `PASS`。

在 `omega_bar=2.23` 的升沉辐射列中：

1. 以 body-potential 中位范数比计，内自由面势贡献最大，比例约 `0.6126`。
2. 船体法向速度贡献比例约 `0.5929`。
3. 外控制面历史贡献比例约 `0.01335`。
4. 最大来源和重构相对残差为 `4.0944e-15`。

这些比例可以大于简单“百分比和为 1”的直觉，因为复势来源之间存在相位叠加和抵消。它们用于定位方程来源，不是校准权重。

### 9.3 body-potential 常数模态

常数模态审计证明分量分解残差约为 `1e-16`，但常数模态占主导并不等于允许删除它。A1/Ma 没有给出支持该删除的 gauge 条件，因此：

```text
default_correction_supported=false
candidate_default_gate_eligible=false
```

这排除了用常数势模态减法制造通过结果的捷径。

### 9.4 体势归一化与时间压力链

`body_potential_normalization_trace_summary.csv` 给出当前 `A33/A53` 目标失败数为 0、归一化阻塞项为 0，结论为 `current_a33_a53_gate_passes_no_body_potential_rescale_required`。这表示当前默认方程已经通过目标门槛，不需要、也不允许再引入未从 A1/Ma 方程推导出的体势比例修正。闭圆柱与开放 Wigley 剖面的历史尺度候选仍保留为诊断证据，但不再被误记为当前通过路径的阻塞项。

`body_potential_time_pressure_chain_summary.csv` 将 Eq.19--Eq.22 状态传递、Eq.23 RHS 来源、body potential、Eq.30 压力和实际 Eq.32 选定装配路线汇总到同一机器判据。结果为目标行 `4/4 PASS`、阻塞项 0，选定路线装配闭合残差 `1.3878e-17`，审计状态为 `PASS`。这里检查的是默认 `matched_bie_station_sweep` 真正使用的装配路线，而不是某个仅供比较的候选组合。

### 9.5 候选隔离

`candidate_impact_summary.csv` 共 163 行、26 个候选族，`candidate_default_gate_eligible=true` 的数量为 0。所有比例、符号、相位、自由面、端部和分量替换候选均保持诊断态。

## 10. 测试结果

最终命令：

```powershell
python -m pytest -q
```

结果：

```text
278 passed, 1247 warnings in 764.13s (0:12:44)
```

警告来自既有审计表对空候选集合执行 `nanmean`，未造成测试失败、`NaN/Inf` 硬门槛遗漏或求解异常。

本轮另增加或更新了以下回归覆盖：

1. 复合内流域船体法向解析恒等式。
2. 默认 Eq.32 路线的分量重构。
3. 多频 `A33/A53` 自由面目标行统计。
4. 多频 `A33/A53` 已通过链的归一化与时间压力闭合状态。
5. 多频失败链预算统计。
6. 默认控制面半径、自由面裁剪和 Eq.32 路线的缓存键识别。

## 11. 验收矩阵

| 验收项 | 证据 | 状态 |
|---|---|---|
| 默认路径 | `provider_route=matched_bie_station_sweep` | PASS |
| A33/A53 硬门槛 | 固定 comparison 中 4/4 PASS，最大 Gate Ratio 0.678134 | PASS |
| 方程来源 | Eq.23/Eq.24/Eq.30/Eq.32、法向和相位均有代码与测试映射 | PASS |
| 禁止捷径 | 无最终缩放；163 个候选全部不可进入默认路径 | PASS |
| 自由面状态 | Eq.19--Eq.22 重构 8/8，残差 0 | PASS |
| RHS 分解 | 三来源重构 PASS，最大残差 4.0944e-15 | PASS |
| body-potential 尺度 | 法向、常数模态、相位和压力链审计完整 | PASS |
| 体势归一化审计 | A33/A53 失败 0，阻塞项 0，无需经验重缩放 | PASS |
| 时间压力链审计 | 4/4 PASS，阻塞项 0，选定路线闭合残差 1.3878e-17 | PASS |
| 全八系数复核 | 10 个结果有限，9 PASS、1 FAIL，无 NaN/Inf | PASS（本阶段有限性要求） |
| 完整测试 | 278 passed | PASS |
| 阶段报告 | 本文件 | PASS |

因此，2026-08-10 定义的 `A33/A53 Eq.23 RHS / body-potential / time-pressure` 阶段目标已经满足。

## 12. 未解决问题与下一步

### 12.1 `B55`

完整八系数 Gate 1 仍由 `B55` 阻塞：参考值 `0.0703`，当前值 `0.048332`，`gate_error_ratio=2.083271`。剩余链位于 pitch row 的 `N5/m5`、Stokes body moment、端部力矩和复数 `A55+iB55` 装配关系。

不得用单项删除、`U*m5` 比例、纵摇力矩缩放或端部裁剪修补。下一阶段应在同一站位网格上重新推导固定控制面的 pitch product rule。

### 12.2 完整半站位自由面网格

Eq.19--Eq.22 状态传递已自洽，但论文要求的两倍自由面纵向站位尚未完整显式实现。它应作为公式忠实度改进继续保留，不应反向否定当前 `A33/A53` 的收敛复现证据。

### 12.3 物理试验与运动响应

本阶段仍没有证明：

1. Journee 试验的所有水动力系数误差在工程容差内。
2. Fridsma/Katayama 的升沉、纵摇和加速度响应已经通过。
3. 不规则波统计响应已经通过。

完成 `B55` 和完整八系数 Gate 1 后，才进入规则波升沉--纵摇响应、试验对照和不规则波统计验证。

## 13. 关键产物

1. 固定结果：`outputs/gate1_linear_2p5d_hard_pass/results/ma2005_wigley_iii_coefficients_comparison.csv`。
2. RHS 审计：`outputs/gate1_linear_2p5d_hard_pass/results/ma2005_wigley_iii_coefficients_rhs_source_decomposition_summary.csv`。
3. body-potential 审计：`outputs/gate1_linear_2p5d_hard_pass/results/ma2005_wigley_iii_coefficients_body_potential_constant_mode_summary.csv`。
4. 自由面审计：`outputs/gate1_linear_2p5d_hard_pass/results/ma2005_wigley_iii_coefficients_a1_free_surface_grid_implementation_summary.csv`。
5. 候选隔离：`outputs/gate1_linear_2p5d_hard_pass/results/ma2005_wigley_iii_coefficients_candidate_impact_summary.csv`。
6. 文献离散量级复现：`outputs/ma2005_a33_a53_source_resolution/ma2005_a33_a53_source_resolution.csv`。
7. 网格收敛：`outputs/ma2005_a33_a53_source_resolution/ma2005_a33_a53_grid_convergence.csv`。
8. 可复现脚本：`scripts/run_ma2005_a33_a53_reproduction.py`。
9. 体势归一化审计：`outputs/gate1_linear_2p5d_hard_pass/results/ma2005_wigley_iii_coefficients_body_potential_normalization_trace_summary.csv`。
10. 时间压力链审计：`outputs/gate1_linear_2p5d_hard_pass/results/ma2005_wigley_iii_coefficients_body_potential_time_pressure_chain_summary.csv`。
11. 阶段机器验收：`outputs/gate1_linear_2p5d_hard_pass/results/ma2005_wigley_iii_coefficients_a33_a53_stage_acceptance_summary.csv`。

## 14. 阶段结论

本阶段已经把 `A33/A53` 从“自由面状态可以重构，但 Eq.23 RHS 到 body potential 和 Eq.30 压力的尺度/相位不可信”推进到以下状态：

```text
默认方程路径可追溯；
固定 Gate 行通过；
文献离散量级误差小于 2%；
网格加密变化小于 0.25%；
RHS 和广义力达到机器精度闭合；
无经验缩放；
完整自动测试通过。
```

因此可以正式关闭 `A33/A53` 方程链阶段，并把它冻结为后续 `B55`、完整八系数、运动响应和试验验证的回归基线。
