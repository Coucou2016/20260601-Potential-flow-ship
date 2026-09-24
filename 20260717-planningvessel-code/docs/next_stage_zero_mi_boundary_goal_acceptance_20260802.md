# 下一阶段目标与验收条件：zero-m_i 行输运与边界项封口

日期：2026-08-02

## 1. 当前结论

当前默认主线保持：

```python
LinearFrequencyProvider(source="linear_2p5d", formulation="matched_bie")
```

验证元数据保持：

```text
provider_route == "matched_bie_station_sweep"
```

最新验证目录：

```text
outputs/gate1_zero_mi_boundary_validation/results
```

最新验证统计：

| 状态 | 数量 |
|---|---:|
| PASS | 65 |
| INFO | 63 |
| NOT_EVALUATED | 8 |
| FAIL | 15 |

Ma 2005 Wigley III Gate 1 仍为 `PENDING`。当前只有 `B53` 通过；`A33/B33/A35/B35/A53/A55/B55` 未通过。

本阶段新增的 `row_measure_zero_mi_boundary_audit` 已经证明：`B33/A35/B35` 中 `m3=0` 但 `d(N3 ds)/dx` 非零的问题不是端部站位主导，也不是简单固定控制面映射主导，而是变截面面板法向变化主导。三项分解的闭合残差均约为 `1e-17` 量级，说明审计分解本身可信。

## 2. 下一阶段唯一目标

> 将 heave row 的 zero-`m3` 非零输运写成可追溯的公式项，并把它纳入 Eq.31 到 Eq.32 的压力装配闭合链；若该项能使八个 Wigley III 系数满足 Gate 1，则进入默认模型，否则保留为诊断并明确剩余阻塞项。

## 3. 必须完成的技术任务

1. 从 A1/Ma 2005 的 Eq.31 与 Eq.32 出发，重写 `d(N3 ds)/dx` 的几何输运推导。
2. 在代码中区分并输出以下分量：面板法向变化、面板长度变化、力臂变化、乘积法则残差、端点/水线面板贡献、内部面板贡献、boundary share、固定控制面映射残差。
3. 建立 `B33/A35/B35` 的站位级闭合表，报告 residual centroid、peak station、configured end share、interior share、endpoint panel share 和 boundary share。
4. 如果引入候选装配项，必须同时输出旧装配值、新候选值、分量闭合残差和八系数误差变化。
5. 新候选在通过完整 Gate 1 前必须保持 `diagnostic-only`。

## 4. 专项验收条件

| 类别 | 验收条件 |
|---|---|
| 公式来源 | 文档中必须给出 `d(N3 ds)/dx` 从 Eq.31 到 Eq.32 的具体推导，不得只写“经验修正” |
| 数值闭合 | `row_measure_zero_mi_boundary_summary.csv` 中三项 `decomposition_closure_residual` 均小于 `1e-9` |
| 来源定位 | `residual_source_class` 不得为 `unknown`；当前已定位为 `panel_normal_variation_dominant` |
| 候选纪律 | 候选进入默认模型前，所有相关 CSV 的 `candidate_default_gate_eligible` 必须仍为 `false` |
| Gate 1 | 默认路线最终必须使八个 Ma 2005 Wigley III 系数全部 `PASS`，否则保持 `PENDING` |
| 测试 | 新增或修改测试后，`python -m pytest -q` 必须全部通过 |
| 文档 | 本文件、当前进展文件和 Gate 1 审计文件必须同步更新 |

## 5. 当前证据摘要

| 系数 | 残差积分 | 法向变化占比 | 面板长度占比 | 力臂变化占比 | boundary share | 端点/水线占比 | 内部站位占比 | 残差质心 x/L | 来源分类 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| B33 | -7.8181 | 0.7924 | 0.2085 | 0.0000 | 0.1171 | 0.1171 | 0.9712 | 0.2617 | panel_normal_variation_dominant |
| A35 | 1.3899 | 0.7924 | 0.2085 | 0.0000 | 0.1171 | 0.1171 | 0.9712 | 0.2617 | panel_normal_variation_dominant |
| B35 | -0.8325 | 0.8510 | 0.1500 | 0.0000 | 0.1018 | 0.1018 | 0.8497 | 0.2845 | panel_normal_variation_dominant |

Eq.31/Eq.32 boundary-proxy 闭合摘要：

| 系数 | Eq.31 积分 | Eq.32 Stokes 积分 | Eq.32 boundary proxy 积分 | Eq.31-Eq.32 proxy 残差积分 | proxy 残差范数 | proxy 残差质心 x/L |
|---|---:|---:|---:|---:|---:|---:|
| B33 | -7.8181 | 0.0000 | -0.9808 | -6.8373 | 0.8841 | 0.2555 |
| A35 | 1.3899 | 0.0000 | 0.1744 | 1.2155 | 0.8841 | 0.2555 |
| B35 | -0.8325 | 0.0000 | -0.0212 | -0.8113 | 0.9039 | 0.2757 |

## 6. 固定命令

```powershell
python -m planing_seakeeping validate `
  --benchmark all `
  --out outputs\gate1_zero_mi_boundary_validation\results `
  --reference-root outputs\matched_bie_provider_gate_probe\reference `
  --ma-hydro-model matched_bie_provider `
  --ma-bem-free-surface-panels 4 `
  --ma-bem-body-panels 8
```

```powershell
python -m pytest -q
```
