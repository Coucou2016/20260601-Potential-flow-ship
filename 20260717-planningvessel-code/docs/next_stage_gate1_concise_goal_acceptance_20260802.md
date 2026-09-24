# 下一阶段目标与验收条件：Ma 2005 Wigley III Gate 1

日期：2026-08-02

## 当前进展

当前代码已经完成第一轮可扩展、可测试、边界清楚的升级，主程序、命令行、文献验证框架、CSV 审计输出和回归测试已经建立。现在工作重点已从“搭框架”转入“硬基准闭合”：用 Ma 2005 Wigley III 八个频域水动力系数验证 Ma--Duan--Song 型线性高速 2.5D matched BIE 求解器。

当前固定生产入口为：

```python
LinearFrequencyProvider(source="linear_2p5d", formulation="matched_bie")
```

当前固定生产路由为：

```python
metadata["provider_route"] == "matched_bie_station_sweep"
```

最新验证状态：

| 项目 | 状态 |
|---|---|
| 验证输出目录 | `outputs/matched_bie_provider_eq30_component_audit_probe/results` |
| 验证统计 | `PASS=65`，`INFO=49`，`NOT_EVALUATED=8`，`FAIL=15` |
| Ma 2005 Wigley III 八系数 | `B53` 通过；`A33/B33/A35/B35/A53/A55/B55` 未通过 |
| 最新完整回归测试 | `python -m pytest -q` 通过，`168 passed` |
| Gate 1 状态 | `PENDING` |

已排除的主要错误路径：

| 已审计路径 | 当前结论 |
|---|---|
| A/B 符号、整体翻转、Eq.34 长度幂归一化 | 不能让八系数同时通过，不能进入默认模型 |
| 单一全局比例、逐行/逐列/系数族共享比例 | 最优候选也只能通过 5/8，属于 diagnostic-only |
| 去掉 end term 的 Eq.31 direct-gradient 路径 | 0/8 通过，不能作为默认修正 |
| 改用 Eq.32 Stokes body + end 路径 | 0/8 通过，不能作为默认修正 |
| `gradient - (Stokes body + end)` forward-speed identity | 只在 2/8 上闭合，说明 Eq.30/Eq.32 链条仍有局部不一致 |
| 站位级 forward identity 定位 | 站位积分与全船残差闭合到 `1.8e-15` 量级；残差不是单一端部项错误，而是沿站位传播分布 |
| A/B 复幅值截面力导数代理 | `pressure-gradient` 与 `U/(-i omega) dF_time/dx` 的差异同样沿站位分布，说明问题更接近纵向势函数/截面广义力传播链 |
| 自由面 marching 与时间步候选 | 关闭 marching 可改善 6/8 行但仍只通过 1/8；`time_step_scale=0.25` 通过 0/8，不能作为默认修正 |
| Eq.30/Eq.32 四分量贡献审计 | `time-pressure` 主导 3/8，`forward-speed pressure-gradient` 主导 5/8；A33/A53 指向 body-potential 尺度，B33/A35/A55/B55 指向 station mapping/gradient |

最新新增文件：

| 文件 | 作用 |
|---|---|
| `ma2005_wigley_iii_coefficients_station_forward_identity_audit.csv` | 逐站输出 `rho U dphi/dx`、Stokes body forward term、end contour term 和 station residual |
| `ma2005_wigley_iii_coefficients_station_forward_identity_summary.csv` | 按系数汇总全船 residual、站位积分闭合误差、峰值站位、首站占比、端部占比和残差质心 |
| `ma2005_wigley_iii_coefficients_section_force_derivative_audit.csv` | 用 A/B 成对数据重建截面复广义力，逐站比较当前 Eq.30 pressure-gradient 与 `U/(-i omega) dF_time/dx` 代理路径 |
| `ma2005_wigley_iii_coefficients_section_force_derivative_summary.csv` | 汇总每个系数的 pressure-gradient 积分、截面力导数代理积分、二者差值和峰值位置 |
| `ma2005_wigley_iii_coefficients_free_surface_marching_candidate_summary.csv` | 比较关闭 marching、速度缩放、历史项关闭和时间步缩小等候选，证明这些候选不能进入默认主线 |
| `ma2005_wigley_iii_coefficients_eq30_component_contribution_audit.csv` | 逐系数列出 time-pressure、pressure-gradient、Stokes body forward、end contour 四分量贡献、主导分量和反推诊断尺度 |
| `ma2005_wigley_iii_coefficients_eq30_component_contribution_summary.csv` | 汇总四分量主导关系、闭合残差、失败源计数和剩余阻塞项 |
| `ma2005_wigley_iii_coefficients_gate1_failure_summary.csv` | 把自由面 marching/时间步候选排除结论写入 Gate 1 失败审计 |

站位级审计给出的关键判断：

| 系数 | forward identity residual | 峰值站位 | 峰值 `x/L` | 首站占比 | 端部占比 | 结论 |
|---|---:|---:|---:|---:|---:|---|
| `B33` | `8.443666` | 2 | `0.075` | `0.0348` | `0.0348` | 残差沿站位分布 |
| `B53` | `3.450345` | 2 | `0.075` | `0.0523` | `0.0523` | 残差沿站位分布；当前系数本身仍通过 |
| `A35` | `-1.501096` | 2 | `0.075` | `0.0348` | `0.0348` | 残差沿站位分布 |
| `A55` | `-1.380138` | 2 | `0.075` | `0.0523` | `0.0523` | 残差沿站位分布 |
| `B35` | `1.240203` | 3 | `0.100` | `0.0314` | `0.0314` | 残差沿站位分布 |
| `B55` | `0.287609` | 3 | `0.100` | `0.0472` | `0.0472` | 残差沿站位分布 |
| `A33` | `0.0` | 0 | `0.025` | `0.0` | `0.0` | forward identity 本身数值闭合，失败源不在 forward 项 |
| `A53` | `0.0` | 0 | `0.025` | `0.0` | `0.0` | forward identity 本身数值闭合，失败源不在 forward 项 |

这意味着：下一轮修正不应优先继续试探 end contour 的加减、单站删除或自由面时间步缩放，而应转向纵向传播链本身，尤其是 body potential 的 `dphi/dx` 构造、自由面已知势项进入内域方程的方式、Stokes body row `m_i`、moment row 坐标和 station-to-station 相位/幅值连续性是否严格服从同一套 Ma--Duan--Song 公式。

最新 Eq.30/Eq.32 四分量贡献审计进一步把失败源分成两组：`A33/A53` 的误差由 time-derivative pressure 主导，反推所需 time scale 分别约为 `0.097/0.104`，因此不能靠 forward gradient 或 end contour 修复；`B33/A35/A55/B55` 主要由 forward-speed pressure-gradient/station mapping 主导，反推 gradient scale 差异很大且有正有负，只能作为定位证据，不能作为生产调参。`B35` 是 time-pressure 与 forward-speed 项混合抵消问题，需要结合 station-level 贡献继续追查。

进一步的 A/B 复幅值截面力导数审计表明：最强差异仍来自 `B33`，当前 pressure-gradient 积分为 `9.04507`，而由 time-pressure 截面力导数得到的代理积分为 `2.05533`，差值为 `6.98974`；峰值位于 `x/L=0.025`，但峰值占比只有 `0.0946`，残差质心约为 `x/L=0.252`，结论仍是沿站位分布。这个结果进一步排除了“单个端部项或单个首站修正即可解决”的解释，下一步应重点检查相邻站体势插值、变化剖面上的面元对应关系、`N_i(x)` 与 `m_i` 的积分分部关系，以及 `dphi/dx` 是否应在固定控制面/固定物面映射下计算。

## 下一阶段唯一目标

闭合 Ma--Duan--Song 型线性高速 2.5D matched BIE 求解器的压力恢复、前进速度项、端部项、广义力坐标、站位积分和无量纲化公式链，使默认 `matched_bie_station_sweep` 主线通过 Ma 2005 Wigley III 八个频域水动力系数的硬验收。

换成工程语言，就是下一阶段只解决一个问题：

> 找到并修正 Eq.30 压力恢复链或 Eq.32 前进速度等价链中的真实公式/坐标/积分错误，而不是用经验比例、逐系数拟合、符号试错或 reduced-order 补偿把结果调到参考值。

## 必须完成的产物

| 编号 | 产物 | 目的 |
|---|---|---|
| 1 | 站位级 forward identity 审计 CSV | 逐站比较 `rho U dphi/dx`、Stokes body forward term 和 end-contour term，定位残差来自启动站、尾端站、pitch row 还是全船传播 |
| 2 | 八系数对照 CSV | 每个系数必须列出参考值、计算值、误差、容差、gate ratio、PASS/FAIL |
| 3 | Eq.30/Eq.32 分量拆分 CSV | 每个系数必须保留 time derivative、pressure gradient、Stokes body forward、end contour 四类贡献 |
| 4 | 候选修正排除表 | 所有未被采用的符号、尺度、端部、差分、相位候选必须标注 diagnostic-only 和排除原因 |
| 5 | 代码修正说明 | 只记录基于方程、坐标、单位、边界条件或积分定义的真实修正 |
| 6 | Gate 1 验证报告 | 记录最终是否通过；若失败，明确剩余失败源和下一阻塞点 |

## 硬验收条件

| 类别 | 验收条件 | 判定方式 |
|---|---|---|
| 主线不变 | 必须仍使用 `linear_2p5d/matched_bie` | 输出中 `provider_route == matched_bie_station_sweep` |
| 八系数通过 | `A33/B33/A55/B55` 相对误差不超过 15%；`A35/B35/A53/B53` 相对误差不超过 30% | `gate_error_ratio <= 1.0` 且 `status == PASS` |
| 分量闭合 | 最终广义力必须等于 Eq.30/Eq.32 各分量装配和 | `current_force_closure_residual_value < 1e-9` |
| 数值健康 | 不允许 `NaN`、`Inf`、空矩阵伪通过或异常条件数未报告 | 自动扫描 CSV 并保留矩阵条件数、残差、站位贡献 |
| 可追溯 | 每个系数都能追溯到站位贡献、压力分量、端部项和归一化尺度 | 相关 CSV 全部生成且字段完整 |
| 非调参 | 不允许逐系数比例、全局经验缩放、强行符号翻转或 reduced-order 补偿进入默认路径 | 候选修正只能保留为 diagnostic-only |
| 回归测试 | 现有功能不回退 | `python -m pytest -q` 全部通过 |
| 文档同步 | 结果、原因、已排除路径、剩余风险必须同步记录 | 更新 `docs` 中 Gate 1 文档 |

固定验收命令：

```powershell
python -m planing_seakeeping validate `
  --benchmark all `
  --out outputs\gate1_final_validation\results `
  --reference-root outputs\matched_bie_provider_gate_probe\reference `
  --ma-hydro-model matched_bie_provider `
  --ma-bem-free-surface-panels 4 `
  --ma-bem-body-panels 8
```

回归测试命令：

```powershell
python -m pytest -q
```

## 暂不纳入本阶段硬验收

| 内容 | 原因 |
|---|---|
| SL-7 | 仍缺可机器读取的真实 offsets，只能做 surrogate 趋势验证 |
| C1 三体船 | 仍缺主片体和侧片体真实 offsets，不能作为 cross-radiation/cross-diffraction 硬基准 |
| Delft 372 双体船 | 适合作为 Gate 2 多体船扩展，不替代当前单体 Wigley III Gate 1 |
| Fridsma/Katayama 运动响应 | 适合验证运动趋势和非线性响应，不替代 Ma 2005 水动力系数闭合 |
| Sun--Faltinsen 强非线性 2D+t BEM | 属于后续生产内核，需在线性 2.5D Gate 1 通过后再硬验收 |
| 水翼控制闭环 | 需要真实水翼、舵机、控制器和试验数据，不能与当前 Gate 1 混合验收 |

## 完成判据

只有当固定验收命令在默认 `matched_bie_station_sweep` 主线下使 Ma 2005 Wigley III 八个系数全部通过，并且 `python -m pytest -q` 全部通过时，本阶段才算完成。否则 Gate 1 继续保持 `PENDING`，但必须交付可追溯的失败来源、已排除候选和下一阻塞点。
