# 完整 2.5D 滑行艇运动预报的可验证目标

## 目标定义

本项目的下一阶段目标不是只生成看起来平滑的 RAO 或时历曲线，而是把当前的纵向滑行艇预报程序升级为一个可验证的完整 2.5D 程序：

- 船体由站位剖面描述，程序沿纵向对各站 2D 截面流场结果积分，形成 heave/pitch 为核心、6DOF 统一输出的运动方程。
- 每个站位需要计算或读取频率相关的附加质量、辐射阻尼、绕射/入射波激励，并正确处理前进速度、遭遇频率和船体姿态。
- 结果必须同时通过数值一致性、物理趋势和公开文献/试验 benchmark 三类检查，才能称为“合理”。

一句话验收目标：

> 完整 2.5D 模型只有在 Faltinsen Ch. 9 纵向基准、Fridsma/Katayama 滑行艇波浪试验、Ma 2005 Wigley III/SL-7 水动力系数对照、以及内部数值收敛检查均通过后，才视为达到可验证工程模型水平。

## 2026-07-18 当前结论快照

最近一次完整验证命令：

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs\validation_current --ma-compare-hydro-models --ma-bem-free-surface-panels 8 --ma-bem-body-panels 12
```

当前判定：

| Benchmark | 当前状态 | 对结果合理性的含义 |
| --- | --- | --- |
| `faltinsen_ch9_prescribed_state` | `PASS` | 现有 Faltinsen/Savitsky 纵向 heave/pitch 模型在书本规定运行状态下可作为可信开发基线。 |
| `numerical_sanity` | `PASS` | 基础矩阵、RAO、时间/谱收敛没有暴露明显数值错误。 |
| `physical_trend_sanity` | `PASS` | 示例扫速趋势具有初步物理意义。 |
| `section_bem_numerical_sanity` | `PASS` | 当前截面 BEM/面元路径的残差、条件数、加密趋势、多模态矩阵一致性、压力积分闭合、pressure-based main-radiation 组装闭合和 pressure-based PDSTRIP-step pressure-gradient/end-term 组装闭合可用于诊断；最近一次 `outputs\validation_current` 为 25/25 PASS，但这仍不等于 2.5D 已验证。 |
| `katayama_regular_head_waves` | `PASS` | 明显跳跃/不跳跃筛查趋势可用。 |
| `katayama_regular_wave_qualitative_trends` | `FAIL` | 已把 Katayama Fig. 9/Fig. 10 文字描述的趋势接入自动检查；当前线性 RAO 不能复现波高增大后峰值降低并向长波移动的非线性趋势，因此合理地失败。新增 `katayama_nonlinear_pilot_trends.csv` 可显示短时域非线性 RK4 pilot 在中等波高峰值降低/右移上已有部分正确趋势，但它仍只是开发诊断，不替代幅值图点验收。 |
| `ma2005_wigley_iii_coefficients` | `FAIL` | 完整站位式 2.5D 水动力系数还没有通过公开 benchmark；最近一次默认模型为 32 PASS / 26 FAIL。 |
| `fridsma_regular_wave_amplitudes` | `FAIL` | Fridsma configuration A development 幅值数据已接入；在 `outputs\validation_current` 中使用 Sun & Faltinsen 规定的 `trim=4 deg`, `lambda_W=3.6` 后为 15 PASS / 12 FAIL，其中直接幅值对比为 9 PASS / 11 FAIL，另有 1 个汇总误差 gate 失败；自动对照图写入 `figures/fridsma_regular_wave_amplitudes_comparison.png`，并包含时域诊断曲线。新增 response-model diagnostics 显示 nonlinear time-domain 的中位误差略低但有 8 个 impact/model-limit 标记，最佳无模型限制路径仍是 linear time-series，说明不能靠简单切换非线性时域通过该 gate。 |
| `katayama_regular_wave_amplitudes` | `PENDING_REFERENCE_OR_IMPLEMENTATION` | 还缺 Katayama heave/pitch/加速度幅值曲线数字化。 |
| `ma2005_sl7_coefficients` | `FAIL` | SL-7 Figures 19-26 development digitization 已接入；在 `outputs\validation_current` 中，应用 Ma Table 2 LCG 后为 12 PASS / 39 FAIL，并有 1 个真实 offsets `NOT_EVALUATED`，完整 2.5D/真实 offsets 仍未通过。 |
| `complete_2p5d_solver` | `PENDING_REFERENCE_OR_IMPLEMENTATION` | 多模态截面 radiation audit、compact pressure-transfer diagnostics、pressure-based main-radiation 组装闭合、pressure-based PDSTRIP-step pressure-gradient/end-term 组装闭合，以及可选 `strip_2p5d_pdstrip_step`、`pressure_transfer_forward`、`pressure_transfer_pdstrip_step`、`pressure_transfer_pdstrip_damping_forward`、`pressure_transfer_pdstrip_damping_pdstrip_step`、`hybrid_pressure_damping_coupling` Ma 诊断模型已接入；但底层压力解仍未通过 Ma 2005，不能宣称完整 2.5D 已实现并验证。 |
| `pdstrip_external_smoke` | `PASS` | 可选外部 PDSTRIP smoke 已能在本机编译运行并解析；`sectionresults` 为 260/260 section-frequency blocks，解析后为 5 个剖面、52 个频率的 radiation/diffraction/Froude-Krylov 长表。外部 PDSTRIP 现在也能从任意 `StationHull` 生成 section hydrodynamics；示例站位船型为 6 个剖面、312 个 block，并能装配零航速 6DOF added/damping 矩阵。这证明外部参考代码可运行、可读入、可连接现有船型输入、可回到 6DOF 矩阵输出，但还没有完成 Ma 2005 forward-speed 系数映射与验收。 |

一句话判断：当前结果是“纵向模型能跑、数值上自洽、部分文献趋势通过，并且已经暴露 Fridsma 幅值失配”，不是“完整 2.5D 已验证”。要把结果变成工程上可信，必须继续让 Fridsma 幅值 gate、Katayama 幅值 gate、Ma 2005 系数 gate 和完整 2.5D gate 通过。

## 现在的结果如何判断

当前结果应分层判断：

1. 如果 `validation_status_by_benchmark.csv` 中 `faltinsen_ch9_prescribed_state` 为 `PASS`，说明当前 Faltinsen/Savitsky 纵向 heave/pitch 模型在已实现范围内是可信的。
2. 如果 `katayama_regular_head_waves` 为 `PASS`，说明当前模型对明显跳跃/不跳跃工况的筛查趋势是合理的，但这不等于已经能准确预报飞离水面和再入水冲击。
3. 如果 `katayama_regular_wave_qualitative_trends` 为 `FAIL`，说明当前模型还不能完整复现 Katayama 文字明确描述的波高相关非线性峰值变化；同时查看 `katayama_nonlinear_pilot_trends.csv` 可判断现有非线性时域路径是否已经朝峰值降低/右移和离水风险标记的方向靠近。
4. 如果 `ma2005_wigley_iii_coefficients` 为 `FAIL` 或 `complete_2p5d_solver` 为 `NOT_EVALUATED`，说明完整站位式 2.5D radiation/diffraction 求解器还没有验证通过。
5. 如果 Fridsma 幅值 gate 为 `FAIL`，说明当前模型还没有通过滑行艇规则波运动/加速度试验幅值对照；如果 Katayama 幅值数据仍为 `NOT_EVALUATED`，说明还缺少另一组高 Fn 运动幅值、CG 加速度、艏部加速度定量对照。

因此，当前曲线能作为开发基线和纵向简化模型示例使用，但不能作为“完整 2.5D 已验证”的结论。

## 可对照案例

公开/可追溯对照物按用途分为四类：

- Faltinsen Ch. 9：项目本地 Markdown 与书中 Table 9.2、Figures 9.34/9.35，用来对照纵向特征值和 RAO。
- Fridsma 1969/1971：系统粗水滑行艇试验，用来对照规则/不规则波下运动幅值、加速度和增阻趋势；公开入口包括 TRID 条目与可下载扫描件。
- Katayama, Hinami & Ikeda：高速滑行艇规则迎浪试验，用来对照 heave、pitch、bow/CG acceleration 和 jumping/non-jumping 分类。
- Ma 2005 Wigley III/SL-7：用来对照完整 2.5D added mass / damping 系数；这不是滑行艇算例，但正适合作为站位式 2.5D radiation/diffraction 求解器的硬验证。
- PDSTRIP / OpenPlaning 等开源代码：不直接替代验证数据，但可作为 strip-theory 组装、Savitsky 平衡和程序结构的参考实现。

Katayama 幅值图的 pitch 原始纵坐标可按论文图示直接录为
`pitch_rao_rad_per_wave_slope = theta/(K*zeta_w)`，其中
`K=2*pi/lambda`。验证器会按每个工况的波长转换为
`pitch_rao_rad_per_m`，并在 comparison CSV 的 `reference_source_column`
中记录实际使用的参考列。

### Gate A: Faltinsen Ch. 9 规定运行状态

用途：验证当前纵向 heave/pitch 线性化模型、特征值和 RAO 形状。

对照量：

- Table 9.2 的无量纲特征值实部/虚部。
- Figures 9.34/9.35 的 heave 和 pitch RAO 峰值位置、峰值大小、曲线形状。

验收标准：

- 主要模态特征值误差不超过 10%。
- RAO 峰值位置误差不超过 10%。
- RAO 峰值幅值误差不超过 20%。

### Gate B: Fridsma / Katayama 规则波滑行艇试验

用途：验证滑行艇在规则迎浪中的 heave、pitch、CG 垂向加速度、艏部垂向加速度，以及跳跃/不跳跃边界。

对照量：

- 低波高非跳跃工况的 heave 和 pitch 幅值。
- CG 与 bow 垂向加速度。
- 明确跳跃/不跳跃工况分类。

验收标准：

- heave/pitch 幅值误差不超过 25%。
- CG/bow 垂向加速度误差不超过 35%。
- 明确分类工况的跳跃/不跳跃判断正确。

### Gate C: Ma 2005 Wigley III / SL-7 2.5D 系数

用途：这是“完整站位式 2.5D”最关键的硬门槛。只有通过该 gate，才能说明程序不再只是 Faltinsen 近似纵向模型，而是具备站位截面 radiation/diffraction 的 2.5D 求解能力。

对照量：

- Heave/pitch 相关附加质量：`A33`, `A35`, `A53`, `A55`。
- Heave/pitch 相关辐射阻尼：`B33`, `B35`, `B53`, `B55`。
- 不同前进速度与遭遇频率下的系数曲线。

验收标准：

- 主对角项 `A33`, `B33`, `A55`, `B55` 误差不超过 15%。
- 重要耦合项 `A35`, `A53`, `B35`, `B53` 误差不超过 30%。
- 曲线趋势、符号、峰值位置不能系统性错误。

### Gate D: 数值与物理 sanity checks

用途：防止模型“碰巧贴合某个图”，但数值上不稳定或物理上不合理。

验收标准：

- 无 `NaN`/`Inf`。
- 总质量矩阵正定或至少在被求解自由度上非奇异。
- 辐射阻尼主项非负，矩阵条件数处于可控范围。
- 时间步减半后 RMS 变化小于 5%-10%。
- 频率/面元/站位加密后主要水动力系数变化收敛。
- 小波幅下时域规则波响应与频域 RAO 幅值一致。
- 波高加倍时，低波幅线性范围内响应幅值近似加倍。
- `sanity_wave_height_response.csv` 必须记录规则波波高扫描；小波幅 RMS 应接近线性缩放，大波幅若触发干舷/冲击/积分失败风险必须显式报告。
- `sanity_matrix_equilibrium.csv` 必须记录每个航速的总质量矩阵特征值、恢复矩阵特征值、平衡残差和线性化稳定特征值；若最大实部为正，应作为 porpoising/divergence 风险明确报告。
- 高速或大波高出现干舷、飞离水面、再入水等超范围事件时，程序必须报告模型限制，不能静默给出伪精确结果。

## 具体实现目标

1. 站位输入目标：支持硬舭 V 型船、Wigley III、SL-7 或用户自定义 station offset 表；所有几何量有单位和坐标约定检查。当前代码已能读取内嵌 `offsets_m` 点列和外部 `offsets_file` CSV，并由点列推导水线宽度、吃水、面积和剖面质心；`station_geometry_audit.csv` 用于检查点序、端点、水线宽、吃水、面积和质心是否可用；`--bem-body-panels` 可在 BEM 求解前按弧长重采样截面。
2. 截面 2D 求解目标：实现可替换的 2D radiation/diffraction 求解器，至少输出每站 heave/pitch 相关单位长度附加质量、阻尼和波浪激励；当前新增的 sway/heave/roll 零航速 radiation 矩阵审计、compact pressure-transfer diagnostics、pressure-based main-radiation 组装闭合、pressure-based PDSTRIP-step pressure-gradient/end-term 组装闭合，以及可选择的 pressure-transfer Ma 诊断模型是接口进展，还需要把底层截面压力解替换或升级到可通过 Ma/PDSTRIP 对照的形式。
3. 2.5D 组装目标：沿船长积分截面结果，形成频率相关的 6DOF `A(omega)`, `B(omega)`, `C`, `F_wave(omega)`；`station-prototype` 当前已输出单频矩阵快照、每频率 `station_frequency_matrices_long.csv`、`station_excitation.csv` 和 `station_rao.csv`，但这些仍是未验证开发模型；重点自由度为 heave/pitch，其他自由度允许先给出对称工况下的零响应或诊断状态。
4. 前进速度目标：使用遭遇频率和 2.5D 前进速度修正，能覆盖 Froude 数扫描，不把零航速 BEM 结果直接冒充高速结果。
5. 响应目标：输出频域 RAO、规则波时域、不规则波时域、CG/bow 垂向加速度、RMS-航速图。
6. 验证目标：`python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs/validation` 必须将核心 gate 全部置为 `PASS`，且 `complete_2p5d_solver` 不再是 `NOT_EVALUATED`。

## Current Diagnostic Solver Paths

The complete 2.5D gate is still open. In addition to the default `prototype`
and compact `section_bem` paths, the code now exposes `pdstrip_style`, a
PDSTRIP-inspired sectional heave-radiation diagnostic using panel-integral
source influence coefficients. It can be run with:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs/validation_pdstrip_style --ma-hydro-model pdstrip_style --ma-bem-free-surface-panels 10 --ma-bem-body-panels 16 --ma-compare-hydro-models
```

This path is useful for triage, but it still fails the Ma 2005 gate in the
current worktree. Passing `pdstrip_style` numerical sanity is therefore not a
substitute for the required Ma 2005 Wigley III / SL-7 coefficient acceptance.

The code also exposes `strip_2p5d_forward`, a PDSTRIP-like global station
assembly diagnostic. It keeps the PDSTRIP-style sectional heave-radiation
coefficients but assembles heave/pitch through a complex dynamic operator with
a forward-speed section-velocity map and a continuous longitudinal-gradient
term:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs/validation_strip_2p5d_forward --ma-hydro-model strip_2p5d_forward --ma-bem-free-surface-panels 8 --ma-bem-body-panels 12 --ma-compare-hydro-models
```

Latest local status: this branch improves several forward-speed coupling
diagnostics relative to plain `pdstrip_style`, but still fails Ma 2005. It is
evidence that forward-speed station assembly is required; it is not evidence
that the complete 2.5D goal is validated.

The code also exposes `strip_2p5d_pdstrip_step`, which uses the same
sectional coefficients but applies the bow-to-stern PDSTRIP-step
gradient/end-term difference as a selectable hydro model:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs/validation_pdstrip_step_forward --ma-hydro-model strip_2p5d_pdstrip_step --ma-bem-free-surface-panels 8 --ma-bem-body-panels 12
```

Latest local status: direct use of this path gives
`ma2005_wigley_iii_coefficients=FAIL` with 18 PASS / 40 FAIL. In the
side-by-side run `outputs/validation_compare_pdstrip_step`, both
`strip_2p5d_forward` and `strip_2p5d_pdstrip_step` pass 17/55 diagnostic rows.
The step form slightly improves `B53` and slightly worsens `A53`; it does not
fix the diagonal failures. This reinforces that the next target is the
sectional radiation/pressure solution, not only the longitudinal differencing
formula.

The code also exposes `hybrid_forward_coupling`, a diagnostic split that keeps
the prototype diagonal coefficients and replaces only the heave/pitch coupling
terms with the forward-speed assembly:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs/validation_hybrid_forward_coupling --ma-hydro-model hybrid_forward_coupling --ma-bem-free-surface-panels 8 --ma-bem-body-panels 12 --ma-compare-hydro-models
```

Latest local status: with nondimensional near-zero reference handling, this
branch preserves the diagonal passes but still fails the coupling acceptance,
especially `B53/B35`, low-frequency `A35`, and part of `B55`. The coupling
variant sweep shows that simple sign, transpose, continuous-gradient, and
PDSTRIP-step end-difference changes do not close the Ma 2005 error. The next
technical target is therefore the missing multi-mode sectional radiation /
pressure-coupling information needed by the forward-speed damping terms; this
path is not a validated solver.

The code also exposes `hybrid_pressure_damping_coupling`, a narrower damping
coupling diagnostic. It keeps prototype diagonal terms, keeps `A35/A53` from
the forward-speed assembly, and replaces only `B35/B53` with pressure-transfer
PDSTRIP-step damping couplings:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs/validation_hybrid_pressure_damping_coupling --ma-hydro-model hybrid_pressure_damping_coupling --ma-bem-free-surface-panels 8 --ma-bem-body-panels 12 --ma-compare-hydro-models
```

This path tests whether the pressure route really helps the highest-priority
Wigley damping-coupling blockers. It remains a diagnostic split, not a validated
solver.

The compact `section_bem` path now also exposes a zero-speed `sway/heave/roll`
section-radiation matrix audit, body-panel pressure-transfer diagnostics,
pressure-based main-radiation station assembly, and pressure-based PDSTRIP-step
pressure-gradient/end-term assembly. The station CLI writes
`section_bem_multimode_radiation_diagnostics.csv`,
`section_bem_pressure_transfer_diagnostics.csv`,
`forward_speed_pressure_transfer_diagnostics.csv`, and
`forward_speed_pressure_gradient_diagnostics.csv` for `--radiation-model
section_bem`, `pressure_transfer_forward`, `pressure_transfer_pdstrip_step`,
`pressure_transfer_pdstrip_damping_forward`,
`pressure_transfer_pdstrip_damping_pdstrip_step`, or
`hybrid_pressure_damping_coupling`.
The same pressure-transfer route is now selectable in Ma 2005 diagnostics:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs/validation_pressure_transfer --ma-hydro-model pressure_transfer_forward --ma-bem-free-surface-panels 4 --ma-bem-body-panels 8
```

Use `--ma-hydro-model pressure_transfer_pdstrip_step` for the same
pressure-derived section coefficients routed through the bow-to-stern
PDSTRIP-step assembly. Use `pressure_transfer_pdstrip_damping_forward` or
`pressure_transfer_pdstrip_damping_pdstrip_step` to keep pressure-transfer
sectional added mass but replace sectional damping with the local
`pdstrip_style` damping path for B35/B53 shape triage. The latest comprehensive run at
`outputs\validation_current` confirms both pressure-transfer models are finite
and appear in `ma2005_*_hydro_model_diagnostics.csv`; they reach 16/55 PASS for
Wigley III and 0/48 PASS for SL-7, so they are pressure-path diagnostics rather
than validated coefficient sources. This confirms the API can
carry multi-mode section data,
pressure distributions, and both forward-speed operator assembly layers, but
the complete Ma/PDSTRIP-style forward-speed path still needs a validated
sectional pressure solution before the Ma 2005 coupling gate can be accepted.

The local open-source PDSTRIP source can now be compiled and run through an
optional smoke command:

```powershell
python -m planing_seakeeping pdstrip-smoke --out outputs/pdstrip_external_cli
```

The external PDSTRIP section-radiation adapter can also be selected as an
explicit, slow Ma diagnostic:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs/validation_external_pdstrip_sections --ma-hydro-model external_pdstrip_sections
```

Use `--ma-compare-external-pdstrip` together with `--ma-compare-hydro-models`
only when the external Fortran reference path should be included in the
side-by-side hydro-model sweep. This includes the zero-speed
`external_pdstrip_sections` adapter plus the `external_pdstrip_forward` and
`external_pdstrip_pdstrip_step` forward-speed adapters.

For fast external-PDSTRIP triage without changing the hard Ma 2005 gate, filter
only the optional side-by-side diagnostics:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs/validation_external_subset --ma-compare-hydro-models --ma-compare-external-pdstrip --ma-compare-coefficients A33 B33 --ma-compare-row-limit 2
```

`--ma-compare-coefficients` and `--ma-compare-row-limit` do not affect
`ma2005_*_comparison.csv`, so they cannot make a partial subset count as full
Ma 2005 acceptance.

For repeated development runs, persist the external PDSTRIP section data:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs/validation_external_cached --ma-compare-hydro-models --ma-compare-external-pdstrip --ma-compare-coefficients A33 --ma-compare-row-limit 1 --ma-external-pdstrip-cache-dir outputs/pdstrip_ma_cache
```

The cache directory is keyed by hull parameters and stores parseable
`sectionresults` so later runs can reuse the same external reference sections
without rerunning Fortran. This is for reproducible triage only; it does not
change any acceptance gate.

Latest local subset evidence: `outputs/validation_external_forward_a33`
contains a one-row A33 hydro-model diagnostic with `external_pdstrip_sections`,
`external_pdstrip_forward`, and `external_pdstrip_pdstrip_step` included. The
external adapter filters zero-area Wigley end sections and runs the Fortran
PDSTRIP path on 39 active sections, then reuses cached sectionresults on
repeated runs. It returns finite A33 diagnostic values, but the external
forward row still fails by overprediction (`1.3869` vs reference `1.0`).
`outputs/validation_external_forward_b35` shows the B35 coupling single point:
local `strip_2p5d_forward` passes (`0.0949` vs reference `0.13`), while
`external_pdstrip_forward` overpredicts (`0.2085`). The hard Wigley comparison
remains the full 55-row dataset with 32 PASS / 26 FAIL.

Use `--ma-external-pdstrip-section-profiles` to write per-station heave section
radiation profiles and an integrated summary for the selected Ma rows. The
latest A33 profile run at `outputs/validation_external_profiles_a33` shows that
the endpoint-closure weight correction is only `0.075 m` over `2.85 m`
active-only weight, while integrated raw A33 contributions are `110.88` for
external PDSTRIP, `26.33` for local collocation, and `14.15` for local
`pdstrip_style`. This narrows the next technical target: the diagonal A33
disagreement is already present in the section-radiation / strip-integration
layer, not in endpoint weighting, final nondimensionalization, or forward-speed
coupling alone.

It can also run section hydrodynamics from a package station hull:

```powershell
python -m planing_seakeeping pdstrip-station-sections configs/example_station_hull.yml --out outputs/pdstrip_station_sections_example --compare-section-bem --bem-free-surface-panels 4 --bem-body-panels 8 --omega 1.0
```

Existing PDSTRIP `sectionresults` files can be parsed without rerunning the
Fortran program:

```powershell
python -m planing_seakeeping pdstrip-sectionresults outputs/pdstrip_external_cli/pdstrip_external_smoke/sectionresults --out outputs/pdstrip_sectionresults_parse
```

The parsed section coefficients can also be compared with the local compact
section-BEM solver on the same `geomet.out` sections:

```powershell
python -m planing_seakeeping pdstrip-compare-section-bem outputs/pdstrip_external_cli/pdstrip_external_smoke/sectionresults outputs/pdstrip_external_cli/pdstrip_external_smoke/geomet.out --out outputs/pdstrip_section_bem_compare --frequency-indices 1 26 52 --bem-free-surface-panels 4 --bem-body-panels 8
```

It can also be included in the validation summary:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs/validation_with_pdstrip_external --pdstrip-external-smoke
```

Latest local status: `pdstrip_external_smoke=PASS` with 5/5 checks. The smoke
case generates explicit full V sections and verifies that PDSTRIP writes all
260 expected section-frequency blocks. The parser recovers the complex section
radiation matrix as `A_complex = radiation_force / omega**2` and exports
radiation, diffraction, and Froude-Krylov rows. It now also writes
`pdstrip_*_sectionresults_conventions.csv`, tying the parser to the Fortran
source convention that `sectionresults` stores `omega**2 * complex_added_mass`,
then transposes the recovered matrix for PDSTRIP's internal transfer-function
assembly; the CSV also records the coordinate-basis and damping-sign convention.
A direct comparison command now writes 135 station/frequency/matrix-entry
checks for the smoke geometry and shows the current compact section-BEM
underpredicts external PDSTRIP added-mass diagonals. The station-hull command
now writes arbitrary package station
geometry into PDSTRIP and parses the resulting external section data; the latest
example has 6 sections, 52 frequencies, 312 section-frequency blocks, and
zero-speed 6DOF added/damping matrices assembled from external section radiation.
This is important infrastructure for a reference/adapter path and error localization,
but completion still requires mapping PDSTRIP
coefficients or pressure functions into the Ma 2005 Wigley III / SL-7 gates and
passing those gates.

## 2026-07-18 Fridsma Update

`benchmarks/fridsma/regular_wave_motion_digitized.csv` now activates a
development Fridsma configuration A amplitude gate from Sun & Faltinsen 2010
parsed Fig. 4 and Fig. 6 points. The values cover `lambda/L=1,2,3,4,6` and
include heave, pitch, COG acceleration, and bow acceleration.

Latest local command:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs\validation_current --ma-compare-hydro-models --ma-bem-free-surface-panels 8 --ma-bem-body-panels 12
```

Current grouped status from `outputs/validation_current`:

- `fridsma_regular_wave_amplitudes`: `FAIL`, 15 PASS / 12 FAIL / 0 NOT_EVALUATED.
- `katayama_regular_wave_amplitudes`: still `PENDING_REFERENCE_OR_IMPLEMENTATION`.
- `ma2005_wigley_iii_coefficients`: still `FAIL`.
- `ma2005_sl7_coefficients`: still `FAIL`.
- `complete_2p5d_solver`: still `PENDING_REFERENCE_OR_IMPLEMENTATION`.

Interpretation: Fridsma is no longer merely missing reference data. It is now
an active experimental amplitude check. The benchmark rows now use the
source-backed prescribed running state from Sun & Faltinsen 2010:
`trim=4 deg`, `lambda_W=3.6`. The 20 direct amplitude comparisons are
9 PASS / 11 FAIL, and the aggregate max-error row points to
`figures/fridsma_regular_wave_amplitudes_comparison.png`, so the current compact
longitudinal model still does not pass the experiment. This is useful evidence
for the complete 2.5D target. The same comparison CSV now includes
`time_domain_value`, `time_domain_rel_error`, `time_domain_status`, and
dryout-risk diagnostic columns, but these columns do not relax the hard
frequency-domain/reference-error gate: the next
solver work must improve the station pressure/radiation/diffraction model, not
just produce smoother example curves.

## 2026-07-18 Katayama Amplitude Input Update

The Katayama amplitude gate is now wired to accept either already converted
pitch amplitude `pitch_rao_rad_per_m` or the raw Fig. 9/Fig. 10 ordinate
`pitch_rao_rad_per_wave_slope = theta/(K*zeta_w)`. A source audit found the
paper metadata and axis convention in the currently accessible page text, but
not reliable numeric curve coordinates; therefore the amplitude CSV remains a
manual digitization task and the gate must stay `NOT_EVALUATED` until those
points are added.

## 2026-07-18 Ma Gap-Summary Update

The optional internal Ma diagnostic run now writes
`ma2005_*_hydro_model_gap_summary.csv`,
`ma2005_*_hydro_model_blocker_ranking.csv`,
`ma2005_*_hydro_model_conflict_summary.csv`, and a matching
`validation_report.md` section:

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs\validation_ma_gap_summary_current --ma-compare-hydro-models --ma-bem-free-surface-panels 8 --ma-bem-body-panels 12
```

Current diagnostic result:

- `hybrid_forward_coupling` is the best current internal diagnostic model.
- Wigley III remains `FAIL`: 39/55 PASS, with blocking coefficients mainly
  `B53`, `B35`, `B55`, `A35`, and `A53`.
- SL-7 remains `FAIL`: 11/48 PASS, with blocking coefficients including
  `A55`, `A35`, `B53`, `B55`, `B35`, `A53`, `A33`, and `B33`.
- The blocker-ranking CSVs now show priority order and best available model per
  coefficient. For Wigley III, `B35` and `B53` are the highest-priority damping
  couplings, and the pressure-transfer models are currently closest for those
  terms. For SL-7, the first blockers are `A35`, `A55`, and `A53`, which remain
  geometry- and section-pressure-sensitive until real offsets and a validated
  sectional pressure solution are available.
- The conflict-summary CSVs show whether any single diagnostic path passes all
  selected rows of a coefficient and whether row-wise best models split by
  frequency/model family. This is used to prevent a local pressure-transfer or
  PDSTRIP-step improvement from being mistaken for a validated complete 2.5D
  assembly.
- `hybrid_pressure_damping_coupling` is now available as a focused follow-up
  diagnostic for the same `B35/B53` evidence. It does not alter the hard Ma
  gate.
- Use `--ma-coupling-station-contributions` with `--ma-compare-hydro-models`
  for the slower station-level longitudinal `A33/B33/A35/B35/A53/B53/A55/B55`
  contribution CSVs and figures. This
  probe localizes pressure-gradient and W-map errors by station; it does not
  alter the Ma hard gate.
- A focused hard-gate diagnostic at
  `outputs\validation_hybrid_pressure_damping_model` with
  `--ma-hydro-model hybrid_pressure_damping_coupling` improves Wigley III to
  42 PASS / 16 FAIL and the global count to 129 PASS / 68 FAIL / 4
  NOT_EVALUATED / 17 INFO. SL-7 remains 11 PASS / 40 FAIL plus the real-offsets
  gap, so this confirms the pressure damping route is useful for Wigley
  `B35/B53` but not a complete 2.5D validation fix.
- A focused amplitude residual diagnostic at
  `outputs\validation_residual_summary_probe` writes
  `fridsma_regular_wave_amplitudes_residual_summary.csv`. It keeps the Fridsma
  hard gate failed, but separates the current compact-model mismatch into
  short-wave underprediction, mid-wave heave/pitch overprediction, and generally
  soft CG/bow acceleration response.
- This confirms that the next technical target is not a simple sign,
  transpose, or PDSTRIP-step differencing change. The remaining work is a
  validated Ma/PDSTRIP-style sectional pressure/radiation/diffraction solution
  and real SL-7 offsets.

## 2026-07-18 Ma Geometry-Audit Update

The validator now writes `ma2005_*_geometry_audit.csv` before Ma 2005
coefficient comparison and includes the same geometry provenance in comparison
rows and the Markdown report.

- Wigley III is recorded as `ANALYTIC_FORMULA`, using the documented analytic
  Ma Table 1 hull form.
- SL-7 is recorded as `SURROGATE_NEEDS_REAL_OFFSETS` until a source-backed
  `offsets_file` is supplied. The validator now applies Ma 2005 Table 2
  particulars: `LCG aft of amidship=11.7 m` is converted to
  `lcg_from_transom_m=122.5 m` for `LBP=268.4 m`, with
  `trim_by_stern_m=0.043` and `pitch_radius_gyration_m=0.21 LBP` recorded.
- The latest comprehensive local run at `outputs/validation_current`
  reports 77 hard failures and 4 pending checks. `ma2005_wigley_iii_coefficients`
  remains 32 PASS / 26 FAIL; `ma2005_sl7_coefficients` becomes 12 PASS /
  39 FAIL plus one explicit `NOT_EVALUATED` real-offsets row after the
  source-backed LCG correction.
- This worsens some SL-7 coefficient counts relative to the previous midship-LCG
  surrogate, but it is the defensible geometry convention. The remaining target
  is real SL-7 offsets plus a validated sectional pressure/radiation/diffraction
  solution, not empirical tuning to recover accidental passes.

## 2026-07-23 Ma Scale-Audit Update

The optional Ma hydro-model comparison now also writes
`ma2005_*_hydro_model_scale_audit.csv` and
`ma2005_*_hydro_model_scale_audit_summary.csv`, plus
`ma2005_*_coefficient_frequency_shape_audit.csv`,
`ma2005_*_coefficient_frequency_shape_summary.csv`,
`ma2005_*_normalization_sensitivity.csv`,
`ma2005_*_normalization_sensitivity_summary.csv`,
`ma2005_*_pitch_axis_sensitivity.csv`, and
`ma2005_*_pitch_axis_sensitivity_summary.csv`. These files quantify
`computed/reference`, required magnitude multipliers, sign agreement, and
whether a failed coefficient behaves like a uniform scale error or a
frequency-shape/phase-gradient error. The coefficient frequency-shape files
directly compare reference and computed curves across encounter frequency using
best-fit scaling, signed correlation, log-slope mismatch, and scaled normalized
RMSE. The same audit also tests whether alternative nondimensional coefficient
conventions or A55/B55 pitch-reference-axis shifts could explain the mismatch.
This keeps B35/B53/B55 model work tied to source-backed Ma rows rather than to
visual curve fitting. The focused
`outputs/validation_ma_b55_pitch_axis_probe` run shows Wigley III B55 is not
primarily explained by a pitch-axis shift: the best small shift changes median
gate from `0.8587` to `0.8560` and still leaves 3/6 PASS.

## Definition of Done

完整 2.5D 目标完成时，应满足：

- `faltinsen_ch9_prescribed_state`: `PASS`
- `fridsma_regular_wave_amplitudes`: `PASS`
- `katayama_regular_head_waves`: `PASS`
- `katayama_regular_wave_amplitudes`: `PASS`
- `ma2005_wigley_iii_coefficients`: `PASS`
- `ma2005_sl7_coefficients`: `PASS`
- `complete_2p5d_solver`: `PASS`
- `numerical_sanity`: `PASS`
- `physical_trend_sanity`: `PASS`
- section BEM 或替代截面求解器的收敛、残差、条件数检查：`PASS`

如果其中任一文献数据集缺失，对应 gate 必须保持 `NOT_EVALUATED`；如果模型未通过对照，则必须保持 `FAIL`。不允许用主观判断或曲线外观替代 benchmark 结果。
