# 当前下一阶段目标与验收条件

日期：2026-08-02

## 当前状态

项目已经具备可运行的 `planing_seakeeping` 包、CLI、配置读取、验证框架、诊断 CSV、可视化输出和回归测试链。当前默认水动力路线为：

```python
LinearFrequencyProvider(source="linear_2p5d", formulation="matched_bie")
```

正式输出必须保持：

```text
provider_route == "matched_bie_station_sweep"
```

最新验证目录：

```text
outputs/gate1_linear_2p5d_core_validation/results
```

最新状态：

| 状态 | 数量 |
|---|---:|
| PASS | 65 |
| INFO | 64 |
| NOT_EVALUATED | 8 |
| FAIL | 15 |

最新全量测试：

```text
183 passed
```

当前结论很明确：程序不是“不能算”，而是“完整 2.5D matched BIE 尚未通过 Ma 2005 Wigley III 八系数硬验收”。本轮已经把 `B33/A35/B35` 的 heave row zero-`m3` 非零输运定位到 `d(N3 ds)/dx` 的面板法向变化主导项；审计表已显式输出法向变化、面板长度变化、力臂变化、端点/水线面板、boundary share、内部面板、映射残差和 Eq.31/Eq.32 boundary-proxy 闭合列。最新 `zero_mi_normal_transport_candidate` 证据表明，加入完整 zero-`m3` 输运能局部改善三行并使 `B33` 单行通过，但 `A35/B35` 仍远未达标，因此候选继续保持 `diagnostic-only`。下一步必须把该线索从系数 delta 推进到公式级 Eq.31/Eq.32 输运恒等式。

## 下一阶段目标

> 完成 Ma--Duan--Song 型线性高速 2.5D matched BIE 求解器的 Eq.31/Eq.32 几何输运与边界项闭合，使默认 `matched_bie_station_sweep` 路线通过 Ma 2005 Wigley III 八个频域水动力系数 Gate 1；若未通过，则必须把剩余失败源精确定位到公式、坐标、边界积分、端部项、投影链或数据缺口。

## 验收条件

1. 默认路线不变：仍使用 `linear_2p5d/matched_bie`，元数据为 `matched_bie_station_sweep`。
2. 八系数 Gate 1：`A33/B33/A55/B55` 误差不超过 15%，`A35/B35/A53/B53` 误差不超过 30%。
3. zero-`m3` 封口：`B33/A35/B35` 的 `d(N3 ds)/dx` 非零输运必须有公式来源、站位表、分量表和闭合残差。
4. 分量闭合：任何进入候选装配的几何输运或边界项，其分量求和闭合残差必须 `<1e-9`。
5. 候选纪律：未通过完整验收前，所有候选保持 `diagnostic-only`，不得进入默认模型。
6. 数值稳定：所有输出无 `NaN/Inf`，无奇异矩阵伪通过。
7. 测试通过：`python -m pytest -q` 全部通过。
8. 文档同步：当前进展、Gate 1 审计、失败项、排除候选和剩余阻塞项必须写入 `docs`。
9. 数据边界：SL-7 与 C1 trimaran 在没有真实 machine-readable offsets 前只可作为替代/探索对象，不可作为硬验收基准。

## 固定命令

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
