# Gate 1 Row-Measure Transport Audit

日期：2026-08-02

## 1. 目的

本审计用于继续追踪 Ma 2005 Wigley III Gate 1 失败源。上一轮 `interior_mi_transport_consistency` 已经说明：排除 configured end station 后，projection transport 与 Eq.32 Stokes body `m_i` 行仍存在反号或弱相关问题。新的 `row_measure_transport` 审计进一步把问题下钻到程序内部的几何行：

```text
N_i ds
m_i ds
d(N_i ds)/dx
rho*U*int(phi_j*d(N_i ds)/dx)
rho*U*int(phi_j*m_i ds)
```

它只做诊断，不改变默认 `matched_bie_station_sweep` 的任何系数。

## 2. 公式背景

A1/Ma 2005 中 Eq.31 的前进速度压力梯度项包含：

```text
rho*U*int(partial(phi_j)/partial x * N_i ds)
```

Eq.32 用 Stokes 定理将其改写为：

```text
rho*U*int(phi_j*m_i ds) - rho*U*int_CA(phi_j*N_i dl)
```

因此，如果程序中的 `N_i ds`、`m_i ds`、纵向坐标方向、面板映射和端部轮廓定义一致，那么 `d(N_i ds)/dx` 与 `m_i ds` 的关系应当能够被解释。当前审计不假定二者必须简单相等，而是把二者在相同站位、相同面板索引和相同无量纲化下摊开，定位符号和量级问题。

## 3. 本轮新增输出

最新输出目录：

```text
outputs/matched_bie_provider_row_measure_mapping_probe/results
```

新增文件：

```text
ma2005_wigley_iii_coefficients_row_measure_transport_audit.csv
ma2005_wigley_iii_coefficients_row_measure_transport_summary.csv
ma2005_wigley_iii_coefficients_row_measure_transport_direction_candidate_detail.csv
ma2005_wigley_iii_coefficients_row_measure_transport_direction_candidate_summary.csv
ma2005_wigley_iii_coefficients_row_measure_mapping_candidate_detail.csv
ma2005_wigley_iii_coefficients_row_measure_mapping_candidate_summary.csv
ma2005_wigley_iii_coefficients_row_measure_mapping_candidate_overview.csv
```

同步验证结果：

```text
validation_summary.csv: PASS=65, INFO=62, NOT_EVALUATED=8, FAIL=15
python -m pytest -q: 180 passed
```

Gate 1 仍为 `PENDING`，默认主线仍为：

```text
provider_route == matched_bie_station_sweep
```

## 4. 关键结果

| 系数 | 行/列 | row-measure transport | Stokes body forward | LS scale | 反号比例 | 中位行向量对齐度 | 结论 |
|---|---|---:|---:|---:|---:|---:|---|
| A33 | N3 / heave | 0.00000 | 0.00000 | NaN | 0.00000 | NaN | row_measure_transport_matches_stokes_mi_row |
| B33 | N3 / heave | -7.81812 | 0.00000 | NaN | 0.00000 | NaN | row_measure_transport_scale_or_mapping_mismatch |
| A35 | N3 / pitch | 1.38989 | 0.00000 | NaN | 0.00000 | NaN | row_measure_transport_scale_or_mapping_mismatch |
| B35 | N3 / pitch | -0.83253 | 0.00000 | NaN | 0.00000 | NaN | row_measure_transport_scale_or_mapping_mismatch |
| A53 | N5 / heave | 0.00000 | 0.00000 | NaN | 0.00000 | -0.94654 | row_measure_transport_matches_stokes_mi_row |
| B53 | N5 / heave | 1.08352 | -4.11600 | +0.38167 versus negative-Stokes | 0.58974 | -0.94654 | row_measure_transport_expected_opposite_sign_but_scale_mismatch |
| A55 | N5 / pitch | -0.43341 | 1.64640 | +0.38167 versus negative-Stokes | 0.58974 | -0.94654 | row_measure_transport_expected_opposite_sign_but_scale_mismatch |
| B55 | N5 / pitch | -0.59857 | 0.43954 | +0.11617 versus negative-Stokes | 0.58974 | -0.94654 | row_measure_transport_expected_opposite_sign_but_scale_mismatch |

## 5. 解释

`A33` 和 `A53` 是零项闭合行，不能解释 Gate 1 的主要失败。

`B33`、`A35`、`B35` 属于 heave row。A1 Eq.6 给出 `m3=0`，所以 Eq.32 的 Stokes body forward-speed 项在 heave row 中为零；但程序按等面板索引计算的 `d(N3 ds)/dx` 产生了非零行测度输运。这说明 changing-section 几何输运、固定控制面映射或端部项分配仍未与 Eq.32 的 `m3=0` 表述闭合。

`B53`、`A55`、`B55` 属于 pitch row。三项的 `d(N5 ds)/dx` 与当前 `m5` 行呈明显反向；但 A1 Eq.5-Eq.6 给出 `N5=-xNz`、`m5=Nz`，所以简单力臂导数与 `m5` 的反向关系本来就是可预期的。新的判断不再把 pitch row 的“反向”本身视为错误，而是把问题定位为相对于 negative-Stokes 目标的尺度不足和站位/固定控制面映射不闭合：`B53` 与 `A55` 的 negative-Stokes 尺度约为 `0.38167`，`B55` 约为 `0.11617`。

新增 `row_measure_transport_direction_candidate` 审计进一步比较了当前等面板索引导数与简单 `x` 方向反转候选。当前方向中位 negative-Stokes 残差范数为 `1.59495`、中位尺度为 `0.381669`；反向候选中位残差范数为 `1.93079`、中位尺度为 `-0.381669`，并触发 expected-sign reversal。因此，简单反转 `x` 方向已被排除，不能进入默认模型。

新增 `row_measure_mapping_candidate` 审计进一步比较了三种固定控制面映射候选。`mapped_normalized_y_central` 是当前最好候选，中位 negative-Stokes 残差范数为 `1.52704`、中位尺度为 `0.418848`；`mapped_normalized_arclength_central` 中位残差范数为 `1.57471`、中位尺度为 `0.380975`；`mapped_fixed_y_central` 触发 expected-sign reversal。三种映射仍然都保留 3 个 zero-`m_i` 行非零输运问题，因此均被排除为默认修正。

## 6. 当前判断

本轮没有发现可进入默认模型的修正。新的证据把失败源进一步压缩到：

1. A1 Eq.31 到 Eq.32 中 `N_i ds` 与 `m_i ds` 的尺度关系和固定控制面映射。
2. 程序 `z_down/heave_up` 到论文 `Nz` 的转换。
3. pitch row 中 `N5=-xNz`、`m5=Nz` 与程序 `lever=LCG-x` 的坐标方向关系。
4. 固定控制面站位映射与等面板索引纵向导数之间的差别；当前 `fixed_y`、`normalized_y`、`normalized_arclength` 候选均未闭合。
5. changing-section 几何输运与 `C_A` 端部轮廓项的分配边界。

## 7. 下一步

下一步不应把 `row_measure_transport` 直接写入默认 pressure-gradient 通道。更合理的顺序是：

1. 写出 A1 论文坐标下 `N3`、`N5`、`m3`、`m5` 与程序 `normal_z`、`lever=LCG-x` 的逐项符号表。
2. 对 pitch row 继续审计 `d(N5 ds)/dx`、`-m5 ds` 和端部 `C_A` 的组合关系；简单 `x` 方向反转已经由 direction-candidate 表排除。
3. 继续定位 heave row 中 `m3=0` 但 `d(N3 ds)/dx` 非零的来源，尤其是变截面几何输运、端点分配和 Eq.31 到 Eq.32 的边界项分解。
4. 只有当该链条能同时改善或解释八个系数，且 Ma 2005 Gate 1 全部通过，才允许修改默认 `matched_bie_station_sweep`。
