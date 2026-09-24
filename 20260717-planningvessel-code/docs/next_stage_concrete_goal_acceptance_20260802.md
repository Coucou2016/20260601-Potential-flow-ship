# 下一阶段具体目标与验收条件

日期：2026-08-02

## 1. 当前进展

当前项目已经完成第一轮基础建设：`planing_seakeeping` Python 包、命令行入口、示例配置、线性 2.5D matched BIE 主线、诊断 CSV、验证报告、科研报告和自动化测试体系均已建立。

最新可复核输出目录为：

```text
outputs/matched_bie_provider_stokes_end_lever_probe/results
```

当前状态如下：

| 项目 | 当前结果 |
|---|---|
| 验证统计 | `PASS=65`，`FAIL=15`，`INFO=51`，`NOT_EVALUATED=8` |
| 回归测试 | `python -m pytest -q` 已通过，`169 passed` |
| Ma 2005 Wigley III 八系数 | 仅 `B53` 通过；`A33/B33/A35/B35/A53/A55/B55` 未通过 |
| Gate 1 状态 | `PENDING` |
| 默认主线 | `LinearFrequencyProvider(source="linear_2p5d", formulation="matched_bie")` |
| 默认路由 | `metadata["provider_route"] == "matched_bie_station_sweep"` |

目前已经排除的方向包括：单纯符号翻转、单纯归一化调整、逐系数拟合、全局比例缩放、端部项简单加减、首站压力尖峰删除、自由面时间步调整、横向简单插值映射和 `reduced-order` 经验补偿。这些方法不能作为默认模型修正，只能保留为诊断候选。

当前最明确的失败来源有两类：

| 失败来源 | 主要影响 | 当前判断 |
|---|---|---|
| 开放截面体势幅值和相位链 | `A33`、`A53` | Eq.30 时间压力项偏大，需要回查边界积分方程、自由面已知势项和体边界条件 |
| 相邻站体势映射和纵向导数链 | `B33`、`A35`、`A55`、`B55` | Eq.30 前进速度压力梯度项异常，需要回查固定物面/固定控制面上的 `dphi/dx` 定义、站位映射和端部项等价关系 |

`B35` 属于两条链路混合抵消错误，必须在上述两类问题同时收敛后重新判定。

本轮新增 `stokes_end_lever_consistency` 审计后，Eq.32 链路的判断进一步收窄：`heave` 行的 `m3=0` 检查为 `4/4` 通过，端部项所用力臂与站位 pitch moment 力臂一致性为 `8/8` 通过，说明当前失败不能简单归因于 Stokes body 行漏项或端部力臂错位。但 Eq.31 前进速度压力梯度项与 Eq.32 `Stokes body + end contour` 等价关系只有 `2/8` 闭合，最大恒等式残差约为有效容差的 `146.046` 倍；端部项与端点压力梯度贡献的绝对比值范围约为 `0.4727` 到 `0.8035`，也排除了“把端部项简单替换成端点 pressure-gradient 贡献”的默认修正路径。

## 2. 下一阶段唯一目标

在不切换默认主线、不引入经验调参、不使用逐系数拟合、不用 reduced-order 模型替代物理公式的前提下，修正 Ma--Duan--Song 型线性高速 2.5D matched BIE 求解器的压力恢复和整船装配链，使默认 `matched_bie_station_sweep` 主线通过 Ma 2005 Wigley III 八个频域水动力系数的 Gate 1 验收。

一句话目标：

> 找到并修正 Eq.30 压力恢复、Eq.31/Eq.32 前进速度等价项、端部项、广义力坐标、站位纵向导数、整船积分或 Eq.34 无量纲化中的真实公式/坐标/离散错误，并用 Ma 2005 Wigley III 八系数证明默认线性 2.5D 内核可追溯、可复现、可验证。

## 3. 必须完成的工作

| 编号 | 工作 | 必须产物 |
|---|---|---|
| 1 | 核查 heave/pitch 开放截面体势的幅值、相位、边界条件和自由面已知势项 | body-potential scale 审计 CSV 与结论 |
| 2 | 核查 Eq.30 中时间压力项与前进速度压力梯度项 | pressure balance 明细 CSV 与站位贡献表 |
| 3 | 核查 Eq.31/Eq.32 的 Stokes body term、end-contour term 与 Eq.30 梯度项是否等价 | Eq.31/Eq.32 identity 审计 CSV |
| 4 | 核查相邻站面元对应、体势插值、固定坐标下 `dphi/dx` 计算 | station mapping/gradient 审计表 |
| 5 | 核查 Stokes body row、end-contour row、端部力臂与端点贡献比例 | stokes/end/lever consistency 审计 CSV |
| 6 | 只修正可由文献公式、坐标定义、边界条件、单位或积分定义推出的真实错误 | 代码变更、公式说明、修正前后八系数对照 |
| 7 | 将所有未采用候选保留为 `diagnostic-only` | 候选排除表 |
| 8 | 同步更新验证报告和文档 | Gate 1 通过证据，或失败来源与剩余阻塞点 |

## 4. 硬验收条件

| 类别 | 验收条件 | 判定方式 |
|---|---|---|
| 主线固定 | 必须仍使用 `linear_2p5d/matched_bie` | 输出 `provider_route == matched_bie_station_sweep` |
| 八系数精度 | `A33/B33/A55/B55` 相对误差不超过 15%；`A35/B35/A53/B53` 相对误差不超过 30% | 八个系数均 `status == PASS`，且 `gate_error_ratio <= 1.0` |
| 分量闭合 | 最终系数必须能由时间压力项、前进速度项、Stokes body 项和端部项闭合重构 | `current_force_closure_residual_value < 1e-9` |
| 数值健康 | 不允许 NaN、Inf、空矩阵伪通过、未报告奇异矩阵或异常条件数 | 验证 CSV 和测试扫描无异常 |
| 可追溯性 | 每个修正都必须对应到公式、坐标、边界条件、离散格式或归一化定义 | 代码注释、诊断 CSV 和报告中可查 |
| 禁止调参 | 逐系数比例、全局经验缩放、强行符号翻转、结果后处理缩放不得进入默认路径 | 此类候选全部标记为 `diagnostic-only` |
| 回归测试 | 现有功能不能退化 | `python -m pytest -q` 全部通过 |
| 文档同步 | 修正依据、失败源、排除路径、剩余风险必须记录 | 更新 `docs` 与验证报告 |

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

固定回归命令：

```powershell
python -m pytest -q
```

## 5. 本阶段肯定需要的条件

| 条件 | 原因 |
|---|---|
| Ma 2005 Wigley III 八系数继续作为 Gate 1 硬基准 | 它有可复核几何、速度、频率和系数，是当前最适合验证线性 2.5D 水动力内核的公开对照物 |
| A1、A3、A4 系列文献必须保持高准确 Markdown | 需要逐公式核对 Ma--Duan--Song、边界元、压力恢复、自由面 marching 和端部项 |
| 所有候选修正必须先诊断、后进入默认主线 | 防止局部误差变小但整体物理链被污染 |
| 每次核心修正后必须重跑 Gate 1 和全量测试 | 阶段完成必须同时满足物理基准和工程回归 |
| SL-7、C1 三体船、Delft 372、Fridsma/Katayama 暂不替代 Gate 1 | 它们适合作为后续 Gate 2/Gate 3；缺真实 offsets 或数字化运动曲线时，不能作为当前硬验收 |

## 6. 完成判据

下一阶段只有两种合格结局：

1. **Gate 1 通过**：Ma 2005 Wigley III 八系数全部达标，默认 `matched_bie_station_sweep` 主线保持不变，全量测试通过，文档同步完成。
2. **Gate 1 仍为 PENDING，但失败可封口**：如果仍未通过，必须明确交付失败源、已排除候选、剩余阻塞公式或数据，并说明为什么当前结果不能宣称为完整 2.5D 验证通过。
