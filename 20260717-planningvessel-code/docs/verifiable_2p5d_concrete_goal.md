# 可验证完整 2.5D 滑行艇模型具体目标

## 目标一句话

把当前“能运行的纵向滑行艇响应程序”升级为“完整站位式 2.5D 运动预报程序”，并且让每一类输出都能用公开文献、试验数据或开源参考代码进行误差判定。曲线好看不算完成，自动验证 gate 通过才算完成。

验收命令固定为：

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs\validation
```

完成时必须满足：

- `validation_status_by_benchmark.csv` 中核心 gate 全部为 `PASS`。
- `validation_summary.csv` 中没有硬失败 `FAIL`。
- `goal_gap_audit.csv` 中不再有完整 2.5D、Fridsma/Katayama 幅值数据、Ma 2005 系数数据相关的 `NOT_EVALUATED`。
- 诊断模型、局部 subset、外部 PDSTRIP smoke 只能解释问题，不能替代完整验收。

## 如何判断现在的结果是否合理

判断分三层，从低到高：

1. 数值合理性：没有 `NaN/Inf`，质量矩阵非奇异，阻尼主项非负，时间步、谱分量、面元数、站位数加密后主要输出收敛。
2. 物理合理性：trim、湿长、RAO 峰值位置、垂向加速度量级、随航速和波高变化的趋势符合滑行艇运动规律；发生跳跃、离水、再入水时程序必须报告模型限制。
3. 对照合理性：同 Faltinsen、Fridsma、Katayama、Ma 2005、PDSTRIP/OpenPlaning 等对照对象比较，输出误差并由 gate 自动判定。

结论规则：

- 只通过第 1 层：说明程序没有明显数值炸裂。
- 通过第 1 和第 2 层：说明趋势可作为开发参考。
- 三层都通过：才可以说结果具备工程可信度。

## 可用对照物

| Gate | 对照物 | 用途 | 完成判据 |
| --- | --- | --- | --- |
| A | Faltinsen Ch. 9 Table 9.2, Figures 9.34/9.35 | 纵向 heave/pitch 特征值和 RAO 基准 | 特征值误差不超过 10%，RAO 峰位误差不超过 10%，峰值误差不超过 20% |
| B | Fridsma 1969/1971 粗水滑行艇试验 | 规则波 heave、pitch、CG/bow 垂向加速度、增阻趋势 | heave/pitch 幅值误差不超过 25%，加速度误差不超过 35% |
| C | Katayama, Hinami & Ikeda 高速滑行艇规则迎浪试验 | 高 Fn 下响应幅值和 jumping/non-jumping 分类 | 明显分类工况判断正确，幅值误差满足 Gate B 阈值 |
| D | Ma 2005 Wigley III / SL-7 2.5D 系数 | 验证完整站位式 2.5D `A(omega)`、`B(omega)` 组装 | 主对角项误差不超过 15%，重要耦合项误差不超过 30% |
| E | PDSTRIP、OpenPlaning、waveresponse 等开源代码 | 源码级对照、外部 strip-theory 路径、Savitsky 平衡、RAO/谱处理参考 | 只能作为诊断和交叉检查，不能单独替代 A-D 的公开数据 gate |

其中 Gate D 是“完整 2.5D”的硬门槛。Faltinsen 和 Fridsma/Katayama 能说明滑行艇纵向响应是否合理，但只有 Ma 2005 这类水动力系数对照通过，才能证明程序已经具备站位截面 radiation/diffraction 求解与前进速度组装能力。

## 当前状态判定

基于 `outputs\validation_current`：

| Benchmark | 当前状态 | 含义 |
| --- | --- | --- |
| `faltinsen_ch9_prescribed_state` | `PASS` | 当前纵向 Faltinsen/Savitsky heave/pitch 基线可用 |
| `numerical_sanity` | `PASS` | 基础数值检查通过 |
| `physical_trend_sanity` | `PASS` | 基础趋势检查通过 |
| `section_bem_numerical_sanity` | `PASS` | 截面 BEM 诊断路径数值上可用，但不是完整验收 |
| `katayama_regular_head_waves` | `PASS` | 明显跳跃/不跳跃分类筛查可用 |
| `katayama_regular_wave_qualitative_trends` | `FAIL` | 已接入 Katayama Fig. 9/Fig. 10 文字趋势检查；当前线性 RAO 尚不能复现波高增大后峰值降低和右移。新增 nonlinear RK4 pilot 可作为开发诊断，但不是最终幅值验收 |
| `fridsma_regular_wave_amplitudes` | `FAIL` | 滑行艇规则波幅值对照未通过 |
| `katayama_regular_wave_amplitudes` | `PENDING_REFERENCE_OR_IMPLEMENTATION` | 缺少 Katayama 幅值曲线数字化数据 |
| `ma2005_wigley_iii_coefficients` | `FAIL` | Wigley III 2.5D 系数对照未通过 |
| `ma2005_sl7_coefficients` | `FAIL` | SL-7 2.5D 系数对照未通过，且仍缺真实 offsets |
| `complete_2p5d_solver` | `PENDING_REFERENCE_OR_IMPLEMENTATION` | 完整 2.5D 求解器仍未验收 |

当前一句话结论：

> 现在的结果可以叫“开发基线合理”，不能叫“完整 2.5D 已验证合理”。

## 具体实现目标

### 目标 1：补齐可追溯 benchmark 数据

- 审核已有 Faltinsen、Fridsma、Ma 2005 数字化数据，保留来源、图号、单位、坐标变换和数字化方法。
- 补齐 Katayama heave、pitch、CG 垂向加速度、bow 垂向加速度幅值曲线。
- 补齐 SL-7 真实 station offsets，替换当前 surrogate 几何。
- 所有 benchmark CSV 不允许填入占位数值。

### 目标 2：实现完整站位式 2.5D 水动力路径

- 船体输入必须支持硬舭 V 型艇、Wigley III、SL-7、用户自定义 station offsets。
- 每个站位必须能求解或读取 2D radiation、diffraction、pressure-transfer 数据。
- 沿船长组装频率相关 6DOF `A(omega)`、`B(omega)`、`C`、`F_wave(omega)`。
- 正确处理前进速度、遭遇频率、trim、sinkage、LCG/VCG 和 pitch radius。
- head sea 中以 heave/pitch 为核心；其他自由度可在对称工况下输出零响应和模型范围说明。

### 目标 3：让验证器能解释失败来源

- 每次验证输出 `validation_summary.csv`、`validation_status_by_benchmark.csv`、`goal_gap_audit.csv`、comparison CSV、图和 `validation_report.md`。
- Ma 2005 失败时输出 coefficient-level gap、best diagnostic model、blocker ranking、row-wise best-model conflict summary、required-scale audit，以及带 best-fit scale、signed correlation、log-slope mismatch、scaled normalized RMSE 的 coefficient frequency-shape audit，避免把局部频段的诊断改善或一个全局倍率误认为完整 2.5D 修复。
- 对纵向 `A33/B33/A35/B35/A53/B53/A55/B55` 输出可选 station contribution 诊断，定位误差来自截面压力、纵向差分、符号约定还是几何。
- 外部 PDSTRIP、pressure-transfer、hybrid 模型必须明确标注为 diagnostic。

### 目标 4：通过完整验收

最终 Definition of Done：

- `faltinsen_ch9_prescribed_state`: `PASS`
- `fridsma_regular_wave_amplitudes`: `PASS`
- `katayama_regular_head_waves`: `PASS`
- `katayama_regular_wave_qualitative_trends`: `PASS`
- `katayama_regular_wave_amplitudes`: `PASS`
- `ma2005_wigley_iii_coefficients`: `PASS`
- `ma2005_sl7_coefficients`: `PASS`
- `complete_2p5d_solver`: `PASS`
- `numerical_sanity`: `PASS`
- `physical_trend_sanity`: `PASS`
- 截面求解器收敛、残差、条件数、pressure-transfer 闭合检查：`PASS`

任一核心 gate 为 `FAIL` 或关键 benchmark 为 `NOT_EVALUATED` 时，不能宣称完成。

## 下一步优先级

1. 先修 Ma 2005 Wigley III：它有解析几何，最适合定位 2.5D 系数求解器问题。
2. 同步补 Katayama 幅值曲线和 Fridsma 原始图复核：它们决定滑行艇运动响应是否可信。
3. 再补 SL-7 真实 offsets：没有真实几何时，SL-7 只能作为 surrogate 诊断，不能作为最终验收。
4. 把 PDSTRIP/OpenPlaning/waveresponse 保持为参考路径：借鉴实现与交叉检查，但最终仍以公开 benchmark gate 为准。

## 公开参考入口

- Fridsma 试验：公开摘要说明其系统试验覆盖 heave、pitch、bow/CG 加速度和粗水性能。
- Sun and Faltinsen 2010：2D+t 规则迎浪数值结果与 Fridsma 两个 Froude 数试验比较。
- Ma 2005：ITTC 报告概述其 2.5D matched boundary-integral 方法，用于高速细长体水动力特性。
- PDSTRIP：开源 strip-theory seakeeping 程序，可作为外部代码路径。
- OpenPlaning：基于 Savitsky 经验方法的开源 Python 滑行艇静水平衡参考。
- waveresponse：开源 RAO 与波谱处理工具，可作为频域响应后处理参考。
