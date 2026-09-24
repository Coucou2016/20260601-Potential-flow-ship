# Gate 1 Projection Transport 审计记录

日期：2026-08-02

## 背景

A1/Ma 2005 中 Eq.30 写为：

```text
p_j = -rho * (i*omega*phi_j - U*d(phi_j)/dx)
```

Eq.31 将压力沿船体横剖面和纵向积分得到广义力；Eq.32 进一步用 Stokes 定理把直接的 `d(phi_j)/dx` 项转换为 `Stokes body forward-speed term` 与 `end contour term`。文献明确这样做的目的，是避免直接数值差分 `partial psi_j / partial x` 带来的误差。

当前默认 `matched_bie_station_sweep` 路线中，直接 pressure-gradient、projection derivative proxy 和 Eq.32 `Stokes body + end contour` 已经被证明不闭合。为了进一步判断问题是否来自变截面输运项，本轮新增 `projection_transport` 审计。

## 新增产物

最新验证目录：

```text
outputs/matched_bie_provider_row_measure_transport_probe/results
```

新增文件：

```text
ma2005_wigley_iii_coefficients_projection_transport_audit.csv
ma2005_wigley_iii_coefficients_projection_transport_summary.csv
ma2005_wigley_iii_coefficients_geometry_transport_balance_audit.csv
ma2005_wigley_iii_coefficients_geometry_transport_balance_summary.csv
ma2005_wigley_iii_coefficients_station_geometry_transport_closure_audit.csv
ma2005_wigley_iii_coefficients_station_geometry_transport_closure_summary.csv
ma2005_wigley_iii_coefficients_interior_mi_transport_consistency_audit.csv
ma2005_wigley_iii_coefficients_interior_mi_transport_consistency_summary.csv
ma2005_wigley_iii_coefficients_row_measure_transport_audit.csv
ma2005_wigley_iii_coefficients_row_measure_transport_summary.csv
```

该审计已经接入：

```text
ma2005_wigley_iii_coefficients_gate1_failure_audit.csv
ma2005_wigley_iii_coefficients_gate1_failure_summary.csv
validation_summary.csv
```

## 审计方法

由 Eq.30 时间导数压力项可反推出截面投影量：

```text
time_pressure_density = -i * rho * omega * int(phi_j * N_i ds)
```

因此：

```text
rho * int(phi_j * N_i ds) = time_pressure_density / (-i * omega)
```

本审计将该投影量沿纵向求导，得到：

```text
T = U * d[ rho * int(phi_j * N_i ds) ] / dx
```

然后比较四条路径：

| 符号 | 含义 |
|---|---|
| `G` | 当前 Eq.31 direct pressure-gradient 路径 |
| `T` | 由 Eq.30 时间压力反推的 projection transport derivative |
| `endpoint` | projection transport 的端点跳变 |
| `S+E` | Eq.32 Stokes body forward-speed term 加 end contour term |

该审计只在同频 A/B 系数配对可用时重构复广义力。若 A/B 频率不一致，则标记为 `frequency_or_case_mismatch_unpaired`，不强行配对。

## 最新结果

最新验证统计：

| 状态 | 数量 |
|---|---:|
| PASS | 65 |
| INFO | 60 |
| NOT_EVALUATED | 8 |
| FAIL | 15 |

完整回归测试：

```text
python -m pytest -q
178 passed
```

`projection_transport_summary` 的核心结果为：

| 指标 | 数值 |
|---|---:|
| same-frequency rows | 4 / 8 |
| max `G-T` residual norm | 1.33726 |
| max `T-endpoint` residual norm | 0.723426 |
| max `G-(S+E)` residual norm | 0.900796 |
| max `T-(S+E)` residual norm | 1.29414 |

逐项结论：

| 系数 | 结论 |
|---|---|
| `A33` | A/B 频率不一致，不能重构同一复广义力 |
| `B33` | A/B 频率不一致，不能重构同一复广义力 |
| `A35` | A/B 频率不一致，不能重构同一复广义力 |
| `B35` | A/B 频率不一致，不能重构同一复广义力 |
| `A53` | 零贡献行，`G` 与 `T` 闭合 |
| `B53` | `G`、`T`、`endpoint`、`S+E` 均不闭合，差异沿站位分布 |
| `A55` | `G`、`T`、`endpoint`、`S+E` 均不闭合，差异沿站位分布 |
| `B55` | `G`、`T`、`endpoint`、`S+E` 均不闭合，差异沿站位分布 |

## 解释

这个结果说明，不能把 `T = U*d[rho*int(phi_j*N_i ds)]/dx` 当成默认 pressure-gradient 的替代项。它既没有稳定闭合当前 direct pressure-gradient，也没有闭合 Eq.32 的 `Stokes body + end contour`，同时与端点跳变之间也存在可观残差。

物理上，这意味着当前错误很可能不只是 `phi_x` 的一个单独差分格式问题，而是涉及变截面船体上的输运关系：当站位变化时，`phi_j`、`N_i`、面元长度 `ds`、力臂、端部轮廓方向和固定控制面定义必须作为一个整体闭合。若只替换某一项，容易让个别系数变近，但不能形成可验证的 Ma--Duan--Song 2.5D 公式链。

## 几何输运平衡补充

为了把上述差异再拆细，本轮新增 `geometry_transport_balance` 审计。该审计比较：

```text
inferred = T - G
required = (S + E) - G
```

其中 `inferred` 是由时间压力投影输运反推出的变截面几何输运项，`required` 是为了让 Eq.31 的 direct pressure-gradient 与 Eq.32 的 Stokes+end 闭合所必须补上的几何项。

最新结果为：

| 指标 | 数值 |
|---|---:|
| same-frequency rows | 4 / 8 |
| pass | 1 |
| fail | 3 |
| opposite sign | 2 |
| max residual norm | 1.43667 |
| max abs inferred geometry transport | 1.50665 |
| max abs required geometry transport | 3.45034 |

逐项看：

| 系数 | inferred | required | 结论 |
|---|---:|---:|---|
| `A53` | 0.00000 | 0.00000 | 零项闭合 |
| `B53` | 1.50665 | -3.45034 | 反号 |
| `A55` | -0.60266 | 1.38014 | 反号 |
| `B55` | -0.48992 | -0.28761 | 同号但量级不闭合 |

这个结果比单纯的 `G`、`T`、`S+E` 对照更直接：当前由时间压力反推出的几何输运项，不能解释 Eq.32 要求的 Stokes/end 几何平衡；其中两个非零同频项甚至方向相反。因此下一步应优先审计 `d(N_i ds)/dx`、`m_i`、pitch/heave 力行符号和 `C_A` 端部轮廓方向，而不是继续调节差分 stencil 或全局尺度。

## 站位级几何输运定位

为了进一步区分“端点轮廓项错误”和“沿船长分布式输运错误”，本轮新增 `station_geometry_transport_closure` 审计。它把系数级的：

```text
inferred = T - G
required = (S + E) - G
```

拆回每个站位的梯形积分贡献，并把 `end contour` 作为 configured end station 上的端点集中贡献加入同一张表。这样可以直接判断：如果残差主要集中在 configured end station，下一步优先查 `C_A` 端点方向、端点站位和端点尺度；如果残差沿多个站位分布，则下一步优先查 `d(N_i ds)/dx`、`m_i`、固定控制面映射和相邻站位投影定义。

最新结果为：

| 系数 | integral residual norm | abs station residual sum | peak x/L | peak share | configured end share | centroid x/L | 结论 |
|---|---:|---:|---:|---:|---:|---:|---|
| `A53` | 0.00000 | 0.00000 | 0.02500 | 0.00000 | 0.00000 | 0.00000 | 站位级闭合 |
| `A55` | 1.43667 | 3.68732 | 0.05000 | 0.09196 | 0.08459 | 0.31205 | 分布式残差 |
| `B53` | 1.43667 | 9.21830 | 0.05000 | 0.09196 | 0.08459 | 0.31205 | 分布式残差 |
| `B55` | 0.41294 | 2.08887 | 0.02500 | 0.10818 | 0.10818 | 0.29214 | 分布式残差 |

这个结果很关键：`B53` 和 `A55` 的符号反向并不是由 configured end station 单点主导，`B55` 的量级不闭合也不是端点项单独造成。configured end station 的残差占比只有约 `8%` 到 `11%`，峰值站位也只占约 `9%` 到 `11%`，残差质心位于 `x/L≈0.29--0.31`。因此，“只反转端部项”或“只缩放端部项”不具备进入默认模型的依据；它们继续保持 `diagnostic-only`。

## 行测度输运补充

为了把 `d(N_i ds)/dx` 和 `m_i ds` 的关系从系数级进一步拆到几何行级，本轮新增 `row_measure_transport` 审计。它直接输出程序中的 `N_i ds` 压力广义行、`m_i ds` Stokes body 行、等面板索引纵向导数，以及：

```text
rho*U*int(phi_j*d(N_i ds)/dx)
rho*U*int(phi_j*m_i ds)
```

最新结果为：

| 系数 | row transport | Stokes body | LS scale | opposite fraction | median alignment | 结论 |
|---|---:|---:|---:|---:|---:|---|
| `A33` | 0.00000 | 0.00000 | NaN | 0.00000 | NaN | 零项闭合 |
| `B33` | -7.81812 | 0.00000 | NaN | 0.00000 | NaN | heave row 几何输运非零 |
| `A35` | 1.38989 | 0.00000 | NaN | 0.00000 | NaN | heave row 几何输运非零 |
| `B35` | -0.83253 | 0.00000 | NaN | 0.00000 | NaN | heave row 几何输运非零 |
| `A53` | 0.00000 | 0.00000 | NaN | 0.00000 | -0.94654 | 零项闭合 |
| `B53` | 1.08352 | -4.11600 | -0.38167 | 0.58974 | -0.94654 | pitch row 反向/弱尺度 |
| `A55` | -0.43341 | 1.64640 | -0.38167 | 0.58974 | -0.94654 | pitch row 反向/弱尺度 |
| `B55` | -0.59857 | 0.43954 | -0.11617 | 0.58974 | -0.94654 | pitch row 反向/弱尺度 |

该结果说明，当前剩余问题已经不只是“端部项是否选错”或“projection transport 是否可替代 pressure-gradient”。heave row 中理论 `m3=0`，但等面板索引 `d(N3 ds)/dx` 仍产生非零几何输运；pitch row 中 `d(N5 ds)/dx` 与当前 `m5` 行高度反向但量级不统一。因此下一步应优先核对 A1 坐标下 `N5=-xNz`、`m5=Nz` 与程序 `lever=LCG-x`、`z_down/heave_up`、固定控制面映射之间的精确变换关系。

## 当前判定

Gate 1 仍为：

```text
PENDING
```

默认主线仍保持：

```text
metadata["provider_route"] == "matched_bie_station_sweep"
```

`projection_transport` 保持：

```text
diagnostic-only
candidate_default_gate_eligible = false
```

## 下一步

下一步不应再尝试简单符号、尺度或单项替换，而应回到 A1 Eq.31 到 Eq.32 的几何推导，逐项确认：

1. 固定控制面上 `partial phi_j / partial x` 的离散定义。
2. 相邻站位势函数应在物理 `y,z`、归一化横向坐标、剖面弧长还是控制面坐标上匹配。
3. `d(phi_j*N_i ds)/dx` 与 `phi_j*m_i ds`、端部 `C_A` 之间的输运关系。
4. 端部轮廓方向、艏艉端选取和当前 `end_station` 配置是否与 Eq.32 一致。
5. `N_i/m_i` 的 z-down/heave-up 映射是否需要在 Stokes body 项和 pressure-gradient 项中使用不同符号层。

只有当这些关系能够在同一复广义力链中闭合，并且八个 Wigley III 系数全部达到 Gate 1 精度，才能把修正写入默认模型。
