# Gate 1 zero-m_i 边界项审计

日期：2026-08-02

## 1. 审计目的

本审计针对 Ma 2005 Wigley III Gate 1 中 `B33/A35/B35` 的特殊失败模式：A1/Ma 2005 公式给出 heave row 的 `m3=0`，但程序中的 `d(N3 ds)/dx` 并不为零。该现象会使 Eq.31 的前进速度压力梯度项与 Eq.32 的 Stokes body 项无法直接闭合。

本审计不改变默认求解路线，只回答一个问题：

> `m3=0` 时非零的 `d(N3 ds)/dx` 到底来自哪里？

## 2. 审计输出

固定验证目录：

```text
outputs/gate1_zero_mi_boundary_validation/results
```

主要输出文件：

```text
ma2005_wigley_iii_coefficients_row_measure_zero_mi_boundary_audit.csv
ma2005_wigley_iii_coefficients_row_measure_zero_mi_boundary_summary.csv
```

验证摘要中对应 INFO 项：

```text
ma2005_wigley_iii_coefficients_row_measure_zero_mi_boundary_summary
```

## 3. 分解方式

审计将 `d(N3 ds)/dx` 分解为以下可追溯分量：

| 分量 | 含义 |
|---|---|
| normal_variation | 相邻站之间面板法向量变化导致的 `N3` 变化 |
| panel_length_variation | 相邻站之间面板弧长或面板长度变化导致的 `ds` 变化 |
| lever_variation | 力臂变化项；对 heave row 的 `N3` 行为零，但仍显式输出，避免与 pitch row 力臂项混淆 |
| product_rule_residual | 当前离散导数与法向变化、长度变化乘积法则之间的剩余差 |
| waterline_contour | 横剖面端点或水线邻近面板贡献 |
| boundary | 本审计中的边界贡献汇总，目前等于端点/水线面板贡献 |
| section_endpoint_panel | 横剖面端点或水线邻近面板贡献，作为 `waterline_contour` 的面板级实现 |
| section_interior_panel | 横剖面内部面板贡献 |
| mapping_residual | 固定控制面映射候选无法解释的剩余量 |

## 4. 最新结果

| 系数 | 残差积分 | 法向变化积分 | 面板长度积分 | 力臂变化积分 | 乘积残差积分 | 闭合残差 | 来源分类 |
|---|---:|---:|---:|---:|---:|---:|---|
| B33 | -7.8181 | -6.1817 | -1.6450 | 0.0000 | 0.00853 | 2.58e-17 | panel_normal_variation_dominant |
| A35 | 1.3899 | 1.0990 | 0.2924 | 0.0000 | -0.00152 | -5.01e-17 | panel_normal_variation_dominant |
| B35 | -0.8325 | -0.8110 | -0.0228 | 0.0000 | 0.00124 | -4.07e-17 | panel_normal_variation_dominant |

空间分布摘要：

| 系数 | configured end share | bow share | interior share | boundary share | waterline/endpoint share | lever share | peak station x/L | centroid x/L |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B33 | 0.0264 | 0.0024 | 0.9712 | 0.1171 | 0.1171 | 0.0000 | 0.0750 | 0.2617 |
| A35 | 0.0264 | 0.0024 | 0.9712 | 0.1171 | 0.1171 | 0.0000 | 0.0750 | 0.2617 |
| B35 | 0.1439 | 0.0064 | 0.8497 | 0.1018 | 0.1018 | 0.0000 | 0.0750 | 0.2845 |

Eq.31/Eq.32 boundary-proxy 闭合摘要：

| 系数 | Eq.31 row-measure 积分 | Eq.32 Stokes 积分 | Eq.32 boundary proxy 积分 | Eq.31-Eq.32 proxy 残差积分 | proxy 残差范数 | proxy 残差质心 x/L |
|---|---:|---:|---:|---:|---:|---:|
| B33 | -7.8181 | 0.0000 | -0.9808 | -6.8373 | 0.8841 | 0.2555 |
| A35 | 1.3899 | 0.0000 | 0.1744 | 1.2155 | 0.8841 | 0.2555 |
| B35 | -0.8325 | 0.0000 | -0.0212 | -0.8113 | 0.9039 | 0.2757 |

## 5. 结论

1. 三个 zero-`m3` 问题系数的分解闭合残差均达到 `1e-17` 量级，说明审计分解是数值闭合的。
2. 残差主要来自面板法向变化，而不是 configured end station、bow station、端点/水线面板或力臂变化。
3. 残差峰值靠近 `x/L=0.075`，但残差质心位于 `x/L=0.26~0.28`，说明它是沿船长分布的变截面几何输运问题，不是单个端点尖峰问题。
4. Eq.32 的 Stokes body 项在 zero-`m3` 行中为零，端点/水线 boundary proxy 只能解释约 10% 左右的总输运；主要剩余差值仍是内部面板的分布式法向变化输运。
5. 当前固定控制面映射候选仍不能解释该项，因此不得进入默认模型。

## 6. 下一步

下一步必须把 `d(N3 ds)/dx` 中的面板法向变化项写回 Eq.31/Eq.32 的公式链，并作为候选装配输出以下证据：

1. 旧装配、候选装配和参考值对比。
2. `B33/A35/B35` 的分量闭合残差。
3. 八个 Ma 2005 Wigley III 系数的 Gate 1 变化。
4. 候选是否仍为 `diagnostic-only` 的明确标志。

只有当候选同时满足公式依据、闭合残差 `<1e-9`、八系数 Gate 1 全部通过和全量测试通过时，才允许改为默认路线。
