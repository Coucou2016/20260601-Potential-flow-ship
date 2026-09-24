# 当前进展与下一阶段目标验收条件

日期：2026-08-02

## 1. 当前进展

当前工程已经完成第一轮“可继续扩展、可测试、边界清楚”的升级，但还没有达到“完整 2.5D 模型已验证通过”的状态。默认求解路线仍为：

```python
LinearFrequencyProvider(source="linear_2p5d", formulation="matched_bie")
```

所有正式验证输出必须继续保持：

```text
provider_route == "matched_bie_station_sweep"
```

最新固定验证目录为：

```text
outputs/gate1_linear_2p5d_core_validation/results
```

最新固定验证统计为：

| 状态 | 数量 |
|---|---:|
| PASS | 65 |
| INFO | 64 |
| NOT_EVALUATED | 8 |
| FAIL | 15 |

固定验证命令执行结果为：

```text
Hard failures: 15; checks pending reference data: 8
```

这 15 个硬失败仍来自 Ma 2005 Wigley III 频域水动力系数 Gate 1。当前八个核心系数中只有 `B53` 通过，其余七项仍未达标：

| 系数 | 参考值 | 当前计算值 | 相对误差 | Gate ratio | 状态 |
|---|---:|---:|---:|---:|---|
| A33 | 1.0000 | 10.2900 | 9.28999 | 61.9333 | FAIL |
| B33 | 2.1000 | 9.6465 | 3.59356 | 23.9571 | FAIL |
| A35 | -0.2000 | -2.8138 | 13.0689 | 43.5631 | FAIL |
| B35 | 0.1300 | 6.5223 | 49.1713 | 163.9045 | FAIL |
| A53 | 0.1500 | 1.4447 | 8.63155 | 28.7718 | FAIL |
| B53 | -0.1000 | -0.0943 | 0.05687 | 0.1896 | PASS |
| A55 | 0.0630 | 0.0901 | 0.42981 | 2.8654 | FAIL |
| B55 | 0.0900 | 1.8589 | 19.6548 | 131.0319 | FAIL |

本轮新增了 `row_measure_zero_mi_boundary_audit`，专门审计 `B33/A35/B35` 中 `m3=0` 但 `d(N3 ds)/dx` 非零的问题。真实 Wigley III 输出显示，三项均已被定位为面板法向变化主导，而不是端点站位或简单固定控制面映射主导：

| 系数 | zero-m3 残差积分 | 法向变化积分 | 面板长度积分 | 闭合残差 | 法向变化占比 | 力臂变化占比 | boundary share | 端点/水线占比 | 内部站位占比 | 残差质心 x/L | 来源分类 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| B33 | -7.8181 | -6.1817 | -1.6450 | 2.58e-17 | 0.7924 | 0.0000 | 0.1171 | 0.1171 | 0.9712 | 0.2617 | panel_normal_variation_dominant |
| A35 | 1.3899 | 1.0990 | 0.2924 | -5.01e-17 | 0.7924 | 0.0000 | 0.1171 | 0.1171 | 0.9712 | 0.2617 | panel_normal_variation_dominant |
| B35 | -0.8325 | -0.8110 | -0.0228 | -4.07e-17 | 0.8510 | 0.0000 | 0.1018 | 0.1018 | 0.8497 | 0.2845 | panel_normal_variation_dominant |

同时，审计表已经显式输出 Eq.31/Eq.32 proxy 闭合列。`Eq.32` 的 Stokes body 项在 zero-`m3` 行中为零，端点/水线 boundary proxy 只能解释小部分差值，剩余差值仍为沿船长分布的内部面板法向变化输运：

| 系数 | Eq.31 积分 | Eq.32 Stokes 积分 | Eq.32 boundary proxy 积分 | Eq.31-Eq.32 proxy 残差积分 | proxy 残差范数 | proxy 残差质心 x/L |
|---|---:|---:|---:|---:|---:|---:|
| B33 | -7.8181 | 0.0000 | -0.9808 | -6.8373 | 0.8841 | 0.2555 |
| A35 | 1.3899 | 0.0000 | 0.1744 | 1.2155 | 0.8841 | 0.2555 |
| B35 | -0.8325 | 0.0000 | -0.0212 | -0.8113 | 0.9039 | 0.2757 |

这说明当前问题已经从“结果不合理”推进到更具体的结论：heave row 的 zero-`m3` 行输运不应被简单丢弃，也不能由端点/水线 boundary proxy 单独解释；`d(N3 ds)/dx` 中由变截面面板法向变化产生的分布式几何输运项需要在 Eq.31 到 Eq.32 的压力装配链中被公式化处理。

进一步的 `zero_mi_normal_transport_candidate` 候选审计显示：`add_full_zero_m3_transport` 对 `B33/A35/B35` 三行均有改善，并使 `B33` 单行通过，但 `A35/B35` 仍远未达标；因此该候选只能作为公式推导线索，不能进入默认模型。

测试状态：

```text
python -m py_compile planing_seakeeping\kernels\linear_2p5d\formulation.py planing_seakeeping\validation.py tests\test_validation.py
python -m pytest tests\test_validation.py::ValidationTests::test_ma2005_row_measure_zero_mi_boundary_audit_covers_heave_row_coefficients tests\test_validation.py::ValidationTests::test_ma2005_row_measure_zero_mi_boundary_summary_localizes_endpoint_panels -q
2 passed
python -m pytest tests\test_validation.py::ValidationTests::test_ma2005_digitized_dataset_can_use_matched_bie_provider_model -q
1 passed
python -m pytest -q
183 passed
```

## 2. 下一阶段目标

下一阶段的唯一目标是：

> 在保持默认 `matched_bie_station_sweep` 路线不变、所有未经验证候选继续 `diagnostic-only` 的前提下，完成 Ma--Duan--Song 型线性高速 2.5D matched boundary integral equation 求解器中 Eq.31 到 Eq.32 的几何输运与边界项封口，使 Ma 2005 Wigley III 八个频域水动力系数通过 Gate 1；如果仍不能通过，则必须把剩余失败源明确封口到具体公式项、坐标映射项、边界积分项或缺失参考数据项。

更短地说：

> 把当前“可运行、可诊断”的 matched BIE 2.5D 求解器推进到“可用 Ma 2005 Wigley III 八系数硬验收”的状态；若未通过，必须给出不可再含糊的剩余阻塞项。

## 3. 必须完成的工作

1. 重新推导并实现 `d(N_i ds)/dx` 的物理坐标输运，尤其是 heave row 中 `d(N3 ds)/dx` 的面板法向变化和面板长度变化。
2. 对 Eq.31 的前进速度压力梯度项与 Eq.32 的 Stokes body 项、end contour 项建立同一站位、同一面板、同一符号约定下的闭合表。
3. 明确 `N_i`、`m_i`、面板法向、轮廓方向、力臂和固定控制面映射的定义，避免把 pitch row 的自然反号误判为 bug。
4. 保留候选修正为 `diagnostic-only`，只有在公式依据、坐标依据、分量闭合和八系数 Gate 1 同时满足后，才允许进入默认模型。
5. 更新验证输出、单元测试、阶段文档和最终验收报告。

## 4. 验收条件

| 类别 | 验收条件 | 判定方式 |
|---|---|---|
| 默认主线 | 继续使用 `linear_2p5d/matched_bie`，不得切换到 legacy、reduced-order、经验拟合或后处理补偿模型 | `provider_route == "matched_bie_station_sweep"` |
| 八系数精度 | `A33/B33/A55/B55` 相对误差不超过 15%，`A35/B35/A53/B53` 相对误差不超过 30% | `ma2005_wigley_iii_coefficients_comparison.csv` 八项均为 `PASS` |
| zero-m3 封口 | `B33/A35/B35` 的 `d(N3 ds)/dx` 非零输运必须被公式化解释，并能分解到法向变化、面板长度变化、力臂变化、端点/水线面板、内部面板、boundary share 和映射残差 | `row_measure_zero_mi_boundary_audit.csv` 与 summary 存在，来源分类不为 `unknown` |
| 分量闭合 | 新引入的几何输运或边界项候选必须满足分量求和闭合残差 `< 1e-9` | component closure CSV |
| 默认修改纪律 | 未同时通过公式依据、坐标依据、闭合残差和 Gate 1 的候选不得进入默认模型 | 所有候选表中 `candidate_default_gate_eligible == false`，直到正式通过 |
| 数值稳定 | 不得出现 `NaN/Inf`、奇异矩阵伪通过或未报告异常 | `validation_summary.csv` 和诊断 CSV |
| 回归测试 | 现有功能不得退化 | `python -m pytest -q` 全部通过 |
| 文档同步 | 当前状态、通过项、失败项、排除候选、剩余阻塞项和验证命令必须同步记录 | `docs` 阶段文档更新 |
| 数据边界 | SL-7 与 C1 trimaran 在没有真实 machine-readable offsets 前不得作为硬验收基准 | 继续标记为 `SURROGATE_NOT_FOR_VALIDATION` |

## 5. 固定验收命令

```powershell
python -m planing_seakeeping validate `
  --benchmark all `
  --out outputs\gate1_linear_2p5d_core_validation\results `
  --reference-root outputs\matched_bie_provider_gate_probe\reference `
  --ma-hydro-model matched_bie_provider `
  --ma-bem-free-surface-panels 4 `
  --ma-bem-body-panels 8
```

```powershell
python -m pytest -q
```

## 6. 合格结局

下一阶段只接受两种合格结局：

1. Gate 1 通过：Ma 2005 Wigley III 八个系数全部达标，默认 `matched_bie_station_sweep` 主线保持不变，完整测试通过，报告和文档同步完成。
2. Gate 1 仍为 `PENDING`，但失败源进一步封口：必须明确说明问题卡在公式定义、坐标映射、边界积分、端部项、投影链或外部数据缺口中的哪一处，并列出已经排除的错误修正路线；此时不得宣称完整 2.5D 验证通过。
