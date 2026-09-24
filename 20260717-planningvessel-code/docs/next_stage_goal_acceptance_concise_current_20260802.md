# 下一阶段目标与验收条件：把线性 2.5D 模型做实

日期：2026-08-02

## 当前进展

项目已经完成第一轮可扩展、可测试、边界清楚的升级：`planing_seakeeping` Python 包、命令行入口、示例配置、验证框架、诊断 CSV、报告输出和自动化测试体系均已建立。

最新可复核输出位于：

```text
outputs/matched_bie_provider_stokes_end_lever_probe/results
```

当前验证统计为：

| 项目 | 状态 |
|---|---|
| 全体验证统计 | `PASS=65`，`INFO=51`，`NOT_EVALUATED=8`，`FAIL=15` |
| 自动化测试 | `python -m pytest -q` 已通过，`169 passed` |
| Ma 2005 Wigley III 八系数 | `B53` 通过；`A33/B33/A35/B35/A53/A55/B55` 未通过 |
| Gate 1 | `PENDING` |

目前已经排除的方向包括：单纯符号翻转、单纯归一化调整、逐系数拟合、全局比例缩放、端部项简单加减、首站压力尖峰删除、自由面时间步粗细调整、`reduced-order` 经验补偿。这些候选最多只能作为诊断，不允许进入默认模型。

最新 Eq.30/Eq.32 四分量贡献审计表明，主要失败源集中在两条链路：

| 失败源 | 影响系数 | 当前判断 |
|---|---|---|
| 开放截面体势幅值与相位链 | `A33`、`A53` | `time-derivative pressure` 贡献偏大，需回到边界积分方程、自由面已知势项和体边界条件核查 |
| 相邻站体势映射与纵向导数链 | `B33`、`A35`、`A55`、`B55` | `forward-speed pressure-gradient` 贡献异常，需核查站位间面元对应、插值、差分坐标和 Eq.31/Eq.32 等价关系 |
| 混合抵消链 | `B35` | 时间项与前进速度项相互抵消不正确，需同时检查上述两类链路 |

本轮新增的 station mapping/gradient 审计进一步确认：4 个 forward-gradient 主导失败全部被标记为 high mapping risk，压力梯度峰值均落在 `x/L=0.0375` 附近；峰值处最大相邻体势跳变约 `1.058`，最大横向面元中点跳变约 `0.485`，最大水线宽/浸没面积跳变约 `0.487`，最大 `dphi/dx` 增益约 `98.28/L`。这说明下一步应优先推导固定物面或固定控制面上的站位映射与纵向导数定义，而不是采用平滑、删除首站或比例缩放作为默认修正。

本轮继续加入 `mapped_fixed_y_*` 与 `mapped_normalized_y_*` 六个 pressure-gradient 候选，用来检查“将邻站体势插值到同一物理横向坐标或同一归一化横向坐标后再求 `dphi/dx`”是否能修复八系数。结果显示这些候选均为 `0/8` 通过；其中最好的是 `mapped_fixed_y_forward`，最大 gate ratio 仍约 `130.24`。因此，简单横向插值映射不能作为默认修正，仍必须回到 Ma--Duan--Song 的固定物面/固定控制面导数定义、端部项和 Stokes body identity 作完整推导。

本轮新增 `stokes_end_lever_consistency` 审计后，进一步确认：heave 行 `m3=0` 为 `4/4` 通过，end-contour 所用力臂一致性为 `8/8` 通过，因此不能把当前 Gate 1 失败简单归因于 Stokes body 行漏项或端部力臂错位；但 Eq.31 梯度项与 Eq.32 `Stokes body + end contour` 前进速度恒等式只有 `2/8` 闭合，最大恒等式残差约为有效容差的 `146.046` 倍，端部项与端点 forward-gradient 贡献的绝对比值约在 `0.4727` 到 `0.8035` 之间，说明 end term 也不能作为简单端点压力替换进入默认修正。

## 下一阶段唯一目标

在保持默认主线为 `LinearFrequencyProvider(source="linear_2p5d", formulation="matched_bie")`，且输出 `metadata["provider_route"] == "matched_bie_station_sweep"` 的前提下，完成 Ma--Duan--Song 型线性高速 2.5D matched BIE 求解器的公式链修正，使其在 Ma 2005 Wigley III 八个频域水动力系数上通过 Gate 1 验收。

换句话说，下一阶段只解决一个问题：

> 找到并修正 Eq.30 压力恢复、Eq.31/Eq.32 前进速度等价项、端部项、广义力坐标、相邻站映射、纵向导数、整船积分或 Eq.34 无量纲化中的真实公式/坐标/离散错误，并用八个公开基准系数证明默认模型可追溯、可复现、可验证。

## 必须满足的验收条件

| 类别 | 验收条件 | 判定方式 |
|---|---|---|
| 默认主线 | 仍使用 `linear_2p5d/matched_bie`，不得切换到 legacy、经验模型或拟合模型 | `provider_route == matched_bie_station_sweep` |
| 八系数精度 | `A33/B33/A55/B55` 相对误差不超过 15%；`A35/B35/A53/B53` 相对误差不超过 30% | 八行 `status == PASS` 且 `gate_error_ratio <= 1.0` |
| 分量闭合 | 最终系数必须能由 Eq.30 时间压力项、前进速度梯度项、Eq.32 Stokes body 项和端部项闭合重构 | `current_force_closure_residual_value < 1e-9` |
| 数值健康 | 不允许 NaN、Inf、空矩阵伪通过、未报告奇异矩阵或异常条件数 | 验证 CSV 与测试扫描全部通过 |
| 公式可追溯 | 每个修正必须能对应到文献公式、坐标定义、边界条件、积分定义或离散格式 | 在代码注释、诊断 CSV 和 Gate 1 报告中记录 |
| 禁止调参 | 不允许逐系数比例、经验补偿、结果后处理缩放进入默认模型 | 所有此类候选保留为 `diagnostic-only` |
| 回归测试 | 现有功能不得退化 | `python -m pytest -q` 全部通过 |
| 文档同步 | 修正原因、采用依据、排除路径和剩余风险必须同步记录 | 更新 `docs` 与验证报告 |

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

## 肯定需要的条件

| 条件 | 必要性 |
|---|---|
| Ma 2005 Wigley III 八系数基准继续作为 Gate 1 硬基准 | 它具备可复核的几何、速度、频率和水动力系数，适合验证线性 2.5D 水动力内核 |
| A1、A3、A4 系列文献的高准确 Markdown | 需要逐公式核查 Ma--Duan--Song、边界元、压力恢复和自由面 marching 的离散细节 |
| 所有候选修正都必须先进入诊断表，再进入默认主线 | 防止“看起来误差变小”的局部补丁污染模型可信度 |
| 每次修正后都必须重新跑 Gate 1 和全量测试 | 只有数值通过和工程回归同时通过，才算阶段完成 |
| SL-7、C1 三体船、Delft 372 和 Fridsma/Katayama 数据暂不替代 Gate 1 | 它们适合作为后续扩展或趋势验证；缺真实 offsets 或运动试验数字化曲线时，不能作为当前硬验收 |

## 完成判据

下一阶段只有两种合格结局：

1. **Gate 1 通过**：Ma 2005 Wigley III 八系数全部达标，默认 `matched_bie_station_sweep` 主线保持不变，完整回归测试通过，文档同步完成。
2. **Gate 1 保持 PENDING 但失败可封口**：如果仍未通过，必须交付明确失败源、已排除候选、无法继续推进所缺的公式或数据，并说明为什么当前结果不能被宣称为完整 2.5D 验证通过。
