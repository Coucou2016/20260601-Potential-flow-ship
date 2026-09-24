# Gate 1 Row-Measure Direction Candidate Audit

日期：2026-08-02

## 1. 审计目的

本轮审计针对 Ma--Duan--Song 线性高速 2.5D matched BIE 求解器中的 Eq.30/Eq.31/Eq.32 压力恢复链，专门检查一个具体问题：

> 当前 `row_measure_transport` 中的纵向导数是否只是 `x` 方向取反错误？

该问题需要独立输出证据，因为此前 `row_measure_transport` 已经显示 pitch row 中 `d(N5 ds)/dx` 与 `m5` 反向。但是根据 A1/Ma 2005 的定义，`N5=-xNz`、`m5=Nz`，简单力臂项导数本来就可能与 `m5` 反号。因此，不能把“反号现象”直接当作程序符号错误，也不能把反向候选写入默认模型。

## 2. 验证命令

```powershell
python -m planing_seakeeping validate `
  --benchmark all `
  --out outputs\matched_bie_provider_row_measure_direction_probe\results `
  --reference-root outputs\matched_bie_provider_gate_probe\reference `
  --ma-hydro-model matched_bie_provider `
  --ma-bem-free-surface-panels 4 `
  --ma-bem-body-panels 8
```

该命令最终完成，输出目录为：

```text
outputs/matched_bie_provider_row_measure_direction_probe/results
```

验证统计为：

| 状态 | 数量 |
|---|---:|
| PASS | 65 |
| INFO | 61 |
| NOT_EVALUATED | 8 |
| FAIL | 15 |

新增的 1 条 `INFO` 来自：

```text
ma2005_wigley_iii_coefficients_row_measure_transport_direction_candidate_summary
```

## 3. 新增输出文件

| 文件 | 作用 |
|---|---|
| `ma2005_wigley_iii_coefficients_row_measure_transport_direction_candidate_detail.csv` | 逐系数比较当前等面板索引纵向导数和 `x` 方向反转候选，对每个系数输出残差、尺度、符号一致性和 diagnostic-only 标记 |
| `ma2005_wigley_iii_coefficients_row_measure_transport_direction_candidate_summary.csv` | 汇总两个候选在八个 Wigley III 系数上的整体表现 |

## 4. 审计结果

| 候选 | 行数 | 闭合行数 | 符号反转行数 | zero-`m_i` 非零行数 | negative-Stokes 中位残差范数 | 中位尺度 | 结论 |
|---|---:|---:|---:|---:|---:|---:|---|
| `current_equal_panel_x_derivative` | 8 | 2 | 0 | 3 | 1.59495 | 0.381669 | `candidate_excluded_by_zero_mi_rows_and_scale_mismatch` |
| `reversed_x_derivative` | 8 | 2 | 3 | 3 | 1.93079 | -0.381669 | `candidate_excluded_by_expected_sign_reversal` |

这说明当前方向虽然不能闭合 Gate 1，但它比简单反向候选更接近 negative-Stokes 目标；而反向候选会在三个非零行中直接触发 expected-sign reversal。因此，当前问题不是“把 `x` 导数整体反过来”就能解决。

## 5. 对 Gate 1 的影响

Ma 2005 Wigley III 八个系数的硬验收状态未改变：

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

因此 Gate 1 继续保持 `PENDING`。

## 6. 排除结论

1. `reversed_x_derivative` 不能进入默认模型：它使非零 pitch-row 候选出现 expected-sign reversal，且整体残差更大。
2. `current_equal_panel_x_derivative` 也不能作为默认修正：它仍存在 zero-`m_i` 行非零输运和尺度/映射不闭合。
3. 两个候选都保持 `diagnostic-only`，不改变 `provider_route == "matched_bie_station_sweep"`。
4. 下一步应继续审计固定控制面映射、变截面几何输运、端点分配和 `N_i/m_i` 行测度定义，而不是使用简单的 `x` 方向反转。

## 7. 回归测试

已执行：

```powershell
python -m py_compile planing_seakeeping\validation.py tests\test_validation.py
python -m pytest tests\test_validation.py::ValidationTests::test_ma2005_row_measure_direction_candidate_audit_compares_reversed_x -q
python -m pytest tests\test_validation.py::ValidationTests::test_ma2005_digitized_dataset_can_use_matched_bie_provider_model -q
python -m pytest -q
```

全量测试结果为：

```text
179 passed
```
