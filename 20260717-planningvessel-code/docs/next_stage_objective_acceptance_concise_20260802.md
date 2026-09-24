# 下一阶段目标与验收条件（简版）

日期：2026-08-02

## 当前进展

项目已经完成第一轮“可继续扩展、可测试、边界清楚”的升级，当前主程序、文献整理、配置读取、命令行运行、可视化输出、验证框架和回归测试链路均已建立。

最新可核对输出目录为：

```text
outputs/matched_bie_provider_projection_balance_probe/results
```

当前验证统计为：

| 状态 | 数量 |
|---|---:|
| PASS | 65 |
| INFO | 55 |
| NOT_EVALUATED | 8 |
| FAIL | 15 |

Ma 2005 Wigley III 八个频域水动力系数的 Gate 1 状态仍为 `PENDING`。当前计算结果中，仅 `B53` 已通过，其余 `A33`、`B33`、`A35`、`B35`、`A53`、`A55`、`B55` 未达到验收精度。最近一次完整回归测试记录为 `python -m pytest -q` 通过，结果为 `173 passed`。

已完成的关键审计说明：站位推进方向不是当前失败主因；简单符号翻转、统一缩放、局部峰值删除、端部项统一放大或后处理拟合都不能作为默认修正。当前失败焦点已经收敛到 Ma--Duan--Song 线性 2.5D matched boundary integral equation 路线中的 Eq.30 压力恢复、Eq.31/Eq.32 前进速度恒等项、纵向导数、端部轮廓项、广义力投影和整船装配闭合问题。

本轮新增 `complex_forward_identity` 审计，把同一矩阵单元的 added mass 与 damping 还原为复广义力 `F_ij = omega^2 A_ij - i omega B_ij`。实际结果表明，当前硬基准八行中只有 `53` 和 `55` 两个矩阵单元可做同频 A/B 配对，`33` 和 `35` 因 A/B 频率不一致不可强行配对；在可配对的 `53` 和 `55` 中，最终系数与分量求和的复数闭合残差接近零，但 Eq.31 pressure-gradient 与 Eq.32 `Stokes body + end contour` 的复数恒等式不闭合，残差范数约为 `0.8335` 到 `0.9008`，说明问题仍集中在前进速度项的分布式公式、投影或离散装配链路，而不是输出求和误差。

本轮继续新增 `projection_derivative_balance` 审计，把 `G = Eq.31 direct pressure-gradient`、`D = d(phi*N_i)/dx projection-derivative proxy` 和 `S+E = Eq.32 Stokes body + end contour` 放到同一张表中比较。实际结果为 `same_frequency=4/8`，`frequency_gap_or_missing=4/8`，`G_vs_D_pass=2/8`，`G_vs_SE_pass=2/8`，`D_vs_SE_pass=2/8`；最大残差范数分别为 `max_G_D_norm=1.33726`、`max_G_SE_norm=0.93351`、`max_D_SE_norm=1.29414`。这说明不能把 `d(phi*N_i)/dx` 代理当成默认修正；它既没有闭合 direct gradient，也没有闭合 Stokes+end。下一步应继续回到 A1 Eq.31/Eq.32 的固定控制面、`N_i/m_i` 投影、轮廓方向和端部项定义，而不是再试简单替代项。

## 下一阶段目标

在不更换默认求解主线的前提下，把 Ma--Duan--Song 型线性高速 2.5D matched BIE 求解器的 Gate 1 做实。

默认主线必须保持为：

```python
LinearFrequencyProvider(source="linear_2p5d", formulation="matched_bie")
```

输出元数据必须保持为：

```text
metadata["provider_route"] == "matched_bie_station_sweep"
```

具体目标是：以 Ma 2005 Wigley III 八个公开水动力系数为硬基准，完成 Eq.30 压力恢复链、Eq.31/Eq.32 前进速度等价链、站位局部时间推进、纵向导数、端部轮廓项、广义力坐标投影和整船积分装配的逐项校核与修正，使默认 matched BIE 主线达到可复现、可追溯、可验证的线性 2.5D 基准精度。

一句话目标：

> 将 Ma 2005 Wigley III 八个系数从“诊断清楚但仍未通过”推进到“默认 matched BIE 主线通过硬验收”；若仍无法通过，则必须把失败源、已排除路径、剩余缺口和不可宣称通过的原因完整封口。

## 必须完成的工作

1. 完成 Eq.31/Eq.32 的复数形式闭合审计，按 `33`、`35`、`53`、`55` 四个矩阵单元重构 added-mass 与 damping 对应的同一个复广义力，判断 pressure-gradient 项与 `Stokes body + end contour` 项在幅值、相位和符号上是否闭合。
2. 对纵向导数、控制面匹配、端部轮廓方向、法向量、`N_i`/`m_i` 投影和积分符号逐项建立可追溯证据。
3. 只允许把有公式依据、坐标依据和数值闭合证据的修正进入默认模型。
4. 保留所有诊断候选为 `diagnostic-only`，不得用逐系数拟合、经验缩放或后处理修正冒充物理模型通过。
5. 同步更新验证报告、CSV 审计表、测试和阶段文档。

## 验收条件

| 类别 | 验收条件 | 判定方式 |
|---|---|---|
| 默认主线 | 不得切换到 legacy、经验模型、reduced-order 模型或拟合模型 | `provider_route == "matched_bie_station_sweep"` |
| 八系数精度 | `A33`、`B33`、`A55`、`B55` 相对误差不超过 15%；`A35`、`B35`、`A53`、`B53` 相对误差不超过 30% | `ma2005_wigley_iii_coefficients_comparison.csv` 八项均为 `PASS` |
| 压力链闭合 | Eq.30 时间导数项、前进速度压力梯度项、Eq.32 Stokes body 项和 end contour 项能够重构最终系数 | 分量求和残差为数值舍入量级，目标 `< 1e-9` |
| 公式可追溯 | 每一处默认修正均能对应到文献公式、坐标定义、边界条件或离散积分定义 | 代码注释、CSV 字段和 Gate 1 报告中均有记录 |
| 数值稳定性 | 不得出现 `NaN`、`Inf`、奇异矩阵伪通过或未报告异常条件数 | `validation_summary.csv` 与诊断 CSV 稳定性检查通过 |
| 审计完整性 | 站位方向、艉端闭合、复广义力闭合、符号候选、端部项候选均有明确保留或排除结论 | 对应 audit/summary CSV 存在且结论明确 |
| 回归测试 | 现有功能不得退化 | 定向测试通过，且 `python -m pytest -q` 全部通过 |
| 文档同步 | 当前状态、修正依据、失败项、通过项、排除候选和剩余风险同步记录 | `docs` 中生成或更新阶段报告 |
| 数据边界 | SL-7 与 C1 trimaran 在没有真实 machine-readable offsets 前不得作为硬验收基准 | 继续标记为 `SURROGATE_NOT_FOR_VALIDATION` |

## 固定验收命令

```powershell
python -m planing_seakeeping validate `
  --benchmark all `
  --out outputs\gate1_final_validation\results `
  --reference-root outputs\matched_bie_provider_gate_probe\reference `
  --ma-hydro-model matched_bie_provider `
  --ma-bem-free-surface-panels 4 `
  --ma-bem-body-panels 8
```

```powershell
python -m pytest -q
```

## 合格交付物

下一阶段只接受两种结局。

第一种是 Gate 1 通过：八个 Ma 2005 Wigley III 系数全部达标，默认 matched BIE 主线不变，完整回归测试通过，文档与报告同步完成。

第二种是 Gate 1 仍为 `PENDING`，但失败已经封口：必须明确指出失败源、已排除候选、仍缺少的公式或数据证据，并说明为什么当前模型还不能宣称为完整 2.5D 验证通过。
