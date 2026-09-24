# 可验证完整 2.5D 模型目标卡

## 目标名称

实现可验证的完整 2.5D 高速滑行艇运动预报模型。

## 目标判定

本目标的成功标准不是“程序能跑”或“曲线看起来合理”，而是程序能在自动验证命令下复现公开文献和试验中的关键量，并清楚报告误差、失效范围和未完成项。

验收命令：

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs/validation
```

完成条件：

- `validation_status_by_benchmark.csv` 中所有核心 gate 为 `PASS`。
- `validation_summary.csv` 中没有硬失败 `FAIL`。
- `goal_gap_audit.csv` 中没有与完整 2.5D、Fridsma/Katayama 幅值数据、Ma 2005 系数数据相关的 `NOT_EVALUATED`。
- `validation_report.md` 明确说明模型适用范围、误差、跳跃/离水/再入水等超范围事件。
- Fridsma/Katayama 幅值 comparison CSV 必须同时保留频域硬 gate 值和时域诊断列；时域诊断只能作为辅助证据，不能替代公开文献误差门槛。

## 当前快照

2026-07-18 本地运行：

```powershell
python -m planing_seakeeping validate --benchmark all --reference-root benchmarks --out outputs\validation_current --ma-compare-hydro-models --ma-bem-free-surface-panels 8 --ma-bem-body-panels 12
```

结果：

- 总计：`120 PASS`, `77 FAIL`, `4 NOT_EVALUATED`, `24 INFO`，基于 `outputs\validation_current`。
- 已可认为合理的部分：Faltinsen Ch. 9 纵向 heave/pitch 基准、Katayama 明显跳跃/不跳跃分类、数值 sanity、物理趋势 sanity。
- 不能宣称完成的部分：Fridsma configuration A 幅值 gate 已接入但当前 15 PASS / 12 FAIL，其中直接幅值对比为 9 PASS / 11 FAIL，另有 1 个汇总误差 gate 失败；Ma 2005 Wigley III 仍有 26 个系数失败；Ma 2005 SL-7 当前为 12 PASS / 39 FAIL，且真实 SL-7 `offsets_file` 仍为 `NOT_EVALUATED`；Katayama 幅值曲线仍缺数据；`complete_2p5d_solver` 仍为待完成。

一句话判断：

> 当前结果是“纵向模型能跑、数值自洽、部分文献基准通过”，不是“完整 2.5D 已验证”。

## 怎么判断结果合不合理

判断分三层：

1. 数值合理性：无 `NaN/Inf`，质量矩阵非奇异，阻尼主项非负，时间步/谱分量/站位/面元加密后主要输出收敛。
2. 物理合理性：trim、湿长、加速度量级、RAO 峰值位置、航速和波高趋势符合滑行艇运动规律；发生跳跃、离水或再入水时必须报告模型限制。
3. 对照合理性：必须和 Faltinsen、Fridsma、Katayama、Ma 2005 等公开 benchmark 比较，给出误差并由 gate 判定通过/失败。

只有第三层也通过，结果才可用于工程判断；前两层通过只能说明程序没有明显数值问题、趋势大体正确。

## 对照案例

| Gate | 对照物 | 用途 | 当前状态 |
| --- | --- | --- | --- |
| A | Faltinsen Ch. 9 Table 9.2, Figures 9.34/9.35 | 验证滑行艇纵向 heave/pitch 线性特征值和 RAO | 已接入，当前 PASS |
| B | Fridsma 1969/1971 粗水滑行艇试验 | 验证 heave、pitch、CG/bow 加速度、增阻 | configuration A development 幅值数据已激活，当前 FAIL |
| C | Katayama, Hinami & Ikeda 规则迎浪试验 | 验证高 Fn 下跳跃/非跳跃分类和响应幅值 | 分类已接入且 PASS，幅值曲线待数字化 |
| D | Ma 2005 Wigley III / SL-7 2.5D 系数 | 验证完整站位式 2.5D added mass / damping | Wigley III 和 SL-7 均已接入 development digitization，但当前均 FAIL |
| E | PDSTRIP / OpenPlaning 开源代码 | 作为截面 strip 组装和 Savitsky 平衡的参考实现 | 已作为诊断路径，不作为单独验收替代 |

公开入口：

- Faltinsen book information: <https://assets.cambridge.org/052184/5688/frontmatter/0521845688_frontmatter.htm>
- Fridsma TRID entry: <https://trid.trb.org/View/2061>
- Fridsma scanned PDF entry: <https://scispace.com/pdf/a-systematic-study-of-the-rough-water-performance-of-planing-1rfm2q8d3u.pdf>
- Katayama regular-head-wave paper page: <https://www.researchgate.net/publication/238103035_LONGITUDINAL_MOTION_OF_A_SUPER_HIGH-SPEED_PLANING_CRAFT_IN_REGULAR_HEAD_WAVES>
- Ma 2005 method summary in ITTC report: <https://ittc.info/media/3463/volume1_7seakeepingcommittee.pdf>
- PDSTRIP public-domain strip method mirror: <https://github.com/eriove/pdstrip>
- Capytaine open-source BEM solver: <https://github.com/capytaine/capytaine>
- OpenPlaning source: <https://github.com/elcf/python-openplaning>

## 核心验收标准

### Gate A: Faltinsen Ch. 9

- 规定状态：`beta=20 deg`, `lambda_W=4`, `trim=4 deg`, `Fn_B=3`, `lcg/B=2.13`, `vcg/B=0.25`, `M/(rho B^3)=1.28`, `r55/B=1.3`。
- Table 9.2 主要模态特征值误差不超过 10%。
- Figures 9.34/9.35 RAO 峰值位置误差不超过 10%。
- RAO 峰值幅值误差不超过 20%，曲线归一化误差满足验证报告门槛。

### Gate B: Fridsma / Katayama 滑行艇试验

- 非跳跃、小波幅规则迎浪：heave/pitch 幅值误差不超过 25%。
- CG 和 bow 垂向加速度误差不超过 35%。
- 明显跳跃/不跳跃工况分类正确。
- 对跳跃、离水、再入水工况输出风险标记；不能把线性 RAO 当作完整非线性冲击预报。
- Katayama Fig. 9/Fig. 10 的 pitch 图上坐标可直接录为 `pitch_rao_rad_per_wave_slope = theta/(K*zeta_w)`；验证器会按每个工况的波数 `K=2*pi/lambda` 转换为 `pitch_rao_rad_per_m`，并在 comparison CSV 中用 `reference_source_column` 记录来源列。

### Gate C: Ma 2005 完整 2.5D 系数

- 输入站位剖面，求解或读取每站 2D radiation/diffraction/pressure 函数。
- 沿船长组装频率相关 6DOF `A(omega)`, `B(omega)`, `C`, `F_wave(omega)`。
- Wigley III 与 SL-7 的 `A33`, `B33`, `A55`, `B55` 主对角项误差不超过 15%。
- `A35`, `A53`, `B35`, `B53` 重要耦合项误差不超过 30%。
- 曲线符号、峰值位置和频率趋势不能系统性错误。
- `ma2005_*_geometry_audit.csv` 必须说明几何来源。Wigley III 可使用解析线型；SL-7 必须最终接入真实数字 station offsets。当前 SL-7 仅使用 Ma 2005 Table 2 主尺度、`LCG aft of amidship=11.7 m`、`trim_by_stern=0.043 m`、`pitch radius=0.21 LBP` 约束 surrogate，因此真实 offsets 行保持 `NOT_EVALUATED`。
- `--ma-compare-hydro-models` 会额外输出 `ma2005_*_hydro_model_gap_summary.csv` 和 `ma2005_*_hydro_model_blocker_ranking.csv`，用于定位最佳诊断模型、阻塞系数和下一步优先证据；当前横向诊断包括 `pressure_transfer_forward`、`pressure_transfer_pdstrip_step`、`pressure_transfer_pdstrip_damping_forward`、`pressure_transfer_pdstrip_damping_pdstrip_step` 和 `hybrid_pressure_damping_coupling`，但这些 pressure-transfer/hybrid 路径只能指导开发，不能替代 Ma 2005 硬 gate。
- `--ma-coupling-station-contributions` 可额外输出较慢的 `ma2005_*_coupling_station_contributions.csv` 和图，用于把纵向 `A33/B33/A35/B35/A53/B53/A55/B55` 误差定位到具体站位；它只解释失败，不改变验收 gate。

### Gate D: 自动化与可追溯

- 每次验证都输出 CSV、图和 Markdown 报告。
- 每个 benchmark 文件记录来源、图表编号、单位、坐标约定和数字化方法。
- 诊断路径必须标注为 diagnostic，不能把 PDSTRIP smoke、prototype、hybrid 或局部 subset 当作完整验收。

## 下一阶段任务

1. 审核 Fridsma configuration A development digitization，并补齐 Katayama heave、pitch、CG/bow 加速度幅值曲线数字化数据。
2. 人工复核 Ma 2005 SL-7 Figures 19-26 的 development digitization，并补充真实 SL-7 station offsets；补齐前不能把 SL-7 surrogate 的通过项视为几何验收。
3. 修正 Ma 2005 Wigley III/SL-7 中当前失败的 `A35/A53/B35/B53/B55/A55` 等系数。
4. 对 PDSTRIP `sectionresults` 的单位、符号、频率缩放和 station 集成约定做源码级审计，并写入解析器/验证报告。当前已把 radiation 存储约定、转置约定、坐标约定和 damping sign 约定导出到 `pdstrip_*_sectionresults_conventions.csv`，但 station 集成和 Ma 2005 forward-speed pressure/diffraction 映射仍未验收。
5. 将 validated section pressure/radiation/diffraction 函数接入 forward-speed 2.5D 组装，使 `complete_2p5d_solver` 从 `NOT_EVALUATED` 变为 `PASS`。

## 2026-07-31 Ma 2005 Gate C Implementation Note

The Gate C plumbing now includes station-wise body-potential longitudinal
gradient estimation, whole-ship 2x2 heave/pitch coefficient assembly, and a
matched-station pressure/force sweep that connects recovered station solutions
to the assembly step. It also includes an A1 Eq. (32) `C_A` contour end-term
helper, a `StationHull` heave/pitch matched sweep entry, and a standard
frequency-domain wrapper. A diagnostic CLI now writes matched Wigley sensitivity
CSV files, case summaries, and per-coefficient best-case diagnostics against the
Ma 2005 digitized table. The new interfaces are
`estimate_body_potential_x_gradient()`,
`assemble_whole_ship_heave_pitch_coefficients()`, and
`assemble_heave_pitch_from_matched_station_solutions()`, and
`compute_heave_pitch_stokes_end_term_force_matrix()`,
`solve_station_hull_heave_pitch_matched_sweep()`, and
`assemble_frequency_domain_from_matched_station_hull()`.
The CLI command is `python -m planing_seakeeping.cli matched-wigley-sensitivity`.
For switch-level diagnosis it supports `--compare-free-surface-marching` and
`--compare-end-term`; for end-contour sign diagnosis it supports
`--compare-end-term-signs` and `--end-term-scales`. The smoke directory
`outputs/matched_wigley_sensitivity_matrix_smoke` shows that the current coarse
grid still fails the A33 first-row tolerance, while the best-case summary narrows
the next calibration target to the free-surface marching/history-kernel path.
The additional `outputs/matched_wigley_endterm_sign_smoke` run shows no A33
first-row change between `+C_A`, `-C_A`, and `noend`, so end-term sign must be
checked next on coupling and pitch coefficients rather than being judged from
this single heave added-mass point.
The coupling smoke directory
`outputs/matched_wigley_coupling_endterm_sign_smoke` confirms that this is not a
single global-sign issue: `A35` is closest with `+C_A`, `A55` is closest with
`-C_A`, and `A53` is unchanged by the current end-term switch. Gate C therefore
requires coefficient-by-coefficient checks of lever-arm convention, pitch
radiation normal velocity, end-contour orientation, and pitch-moment sign.
The expanded directory `outputs/matched_wigley_pitch_convention_smoke` adds
pitch-row/column convention scanning and decomposes each coefficient into
`computed_body_integral_value` and `computed_end_term_value`. Its current
diagnostic result is that `A53` is missing because the heave-mode body-pressure
integral produces almost no pitch moment; `A35` and `A55` are dominated by the
end-contour term. This narrows the next code check to the `U * partial phi /
partial x` pressure-gradient channel and generalized pitch-force assembly.
The follow-up directory `outputs/matched_wigley_free_surface_a53_smoke` shows
why the free-surface path is now the priority: with free-surface marching off,
`A53` stays near zero; with it on, the body integral becomes nonzero but
overshoots the reference by more than an order of magnitude. This is direct
evidence that Gate C next depends on calibrating the free-surface marching,
history-kernel convolution, control-surface radius, and `dt=dx/U` mapping.
The newer `outputs/matched_wigley_a53_free_surface_scale_smoke` run splits that
path into `time_step_scale`, `free_surface_velocity_scale`, and
`history_rhs_scale`. Its best A53 first-row diagnostic is
`time_step_scale=1.0`, `free_surface_velocity_scale=0.1`, and
`history_rhs_scale=0.0`, giving `A53=0.136` against the `0.150` reference.
However, `outputs/matched_wigley_fvscale_joint_smoke` shows that the same
free-surface velocity scale does not make `A33/A35/A55` pass. The scale is
therefore a localization probe, not an acceptable calibration constant for the
production model.
The first concrete formula correction from this diagnosis is now in the station
sweep: the first free-surface update after the bow station uses A1 Eq. (21)-(22),
so the potential passed to the next station is `-0.5*g*psi_z*dt^2` rather than
the full-step value. `outputs/matched_wigley_free_surface_initial_step_fix_smoke`
shows that this lowers the free-surface-on A53 example from about `1.306` to
about `0.939`. This is a real consistency fix, but it still leaves Gate C
pending because the coefficient remains far above the `0.150` reference.

The next diagnostic step adds A1 recommended-grid auditing to all matched Wigley
sensitivity outputs. A case is marked `A1_GRID_RECOMMENDED` only when the
control-surface radius is at least `3B`, the inner free-surface discretization
has at least `11` panels, the outer/control-surface proxy has at least `9`
panels, and the station count meets the Froude-number-dependent minimum
(`60` at low `Fn_L <= 0.25`, otherwise `40`). The directory
`outputs/matched_wigley_a1_grid_a53_smoke` satisfies those audit checks for the
A53 first-row case, but gives `A53=5.282` against the `0.150` reference
(`gate_error_ratio=114.039`). The station-count sweep in
`outputs/matched_wigley_a53_station_count_grid_sweep` gives approximately
`0.518`, `3.556`, `3.951`, and `5.282` for `5`, `11`, `21`, and `41` stations.
This means the present A53 error is not explained by a merely coarse grid; the
error grows as the station marching is refined. Gate C therefore requires a
local-time/free-surface normalization audit before further calibration is
accepted as physical.

The diagnostic file `matched_wigley_station_diagnostics.csv` is now available
through the `--write-station-diagnostics` CLI switch. The run in
`outputs/matched_wigley_a53_station_diagnostics` closes the station-wise buildup
against the whole-ship A53 value: the final cumulative body integral is `5.282`,
matching the sensitivity summary. The largest normalized station contribution is
`1.572` at `station_local_index=2`; the largest free-surface potential norm is
also at that station, and the largest inner-free-surface normal-derivative norm
is at the neighboring `station_local_index=1`. Both stations are near the stern
and occur late in the bow-to-stern solve order. This narrows the next Gate C
audit to the local Eq. (21)-(24) marching variables at the stern-side late
stations rather than a hull-wide uniform correction.

The station diagnostic has since been expanded with explicit Eq. (21)-(24)
marching fields: `free_surface_update_kind`,
`outer_history_rhs_norm_before_solve`,
`free_surface_potential_norm_after_update`, and the corresponding elevation and
growth-ratio fields. The refreshed A53 recommended-grid run shows that the
stern-side high-contribution stations are all in the `advance_eq19_20` update
phase, not the initial `initialize_eq21_22` phase. The largest history-RHS norm
is `0.232` at station `1`, the largest positive A53 contribution is `1.572` at
station `2`, and the largest after-update free-surface potential norm is
`30.955` after station `3`. Gate C should therefore test the outer history RHS,
full-step free-surface velocity update, and forward-speed pressure-gradient
channel separately before accepting any coefficient tuning.

That channel split is now available through `pressure_gradient_scale` and the
diagnostic directories `outputs/matched_wigley_a53_channel_split`,
`outputs/matched_wigley_a53_free_surface_velocity_sign_scale`,
`outputs/matched_wigley_a53_free_surface_velocity_narrow_scale`, and
`outputs/matched_wigley_joint_fv0p03_recommended`. The split shows that turning
off the forward-speed pressure-gradient term does not change this A53 case, and
turning off the outer history RHS changes it only marginally. Turning off the
inner-free-surface velocity update drives A53 nearly to zero. A narrow scale
sweep can fit A53 at `free_surface_velocity_scale=0.03`, but the same setting
fails A33, A35, and A55. This confirms that the scale is a diagnostic symptom,
not an acceptable production calibration.

The next structural diagnostic implements station-wise waterline-clipped inner
free-surface panels, following A1 Sections 3.3 and 3.5 more closely than the old
full-width `[-R, R]` line. The new mode skips the local hull waterline interval
and interpolates `zeta` and `psi` between stations. In
`outputs/matched_wigley_a53_free_surface_clipping_compare`, this lowers A53 from
`5.282` to `0.336` and lowers the station-2 contribution from `1.572` to
`0.0699`. However, `outputs/matched_wigley_joint_clipped_recommended` still
fails the joint first-row check: A33 and A35 worsen, A53 remains outside the
30% coupling tolerance, and only A55 becomes close. The waterline-clipped grid
is therefore a necessary structural correction path, not a complete Gate C pass.

The next A1 grid diagnostic implements a two-zone waterline-outboard grid for
the paper's `n2i/n2e` idea. The implementation adds
`build_two_zone_waterline_free_surface_geometry()`,
`two_zone_inner_free_surface`, `--two-zone-inner-free-surface`, and
`--compare-two-zone-inner-free-surface`. A degenerate-zone guard merges an inner
or outer zone when it is shorter than about 10% of the local outboard span,
because the first unguarded attempt created near-zero panels, condition numbers
above `1.0e5`, and nonphysical free-surface growth. With the guard in place,
`outputs/matched_wigley_a53_two_zone_free_surface_compare` gives one-zone
`A53=0.3685` and two-zone `A53=0.4259` against the `0.150` reference.
`outputs/matched_wigley_joint_two_zone_recommended` shows that
`A33/A35/A53/A55` still all fail, with two-zone values
`4.633/-1.270/0.4259/-0.5097`. This confirms that the two-zone grid is an
implemented diagnostic representation of A1's mesh concept, but not yet a
validated correction. Future acceptance must require bounded grid convergence
and simultaneous improvement of the four first-row coefficients before the
two-zone path can become the production default.

The free-surface state interpolation has also been tightened. When the source
or target grid is split into port/starboard waterline-outboard intervals,
`resample_free_surface_state()` now interpolates `zeta/psi` side by side rather
than across the hull center gap. This prevents a target point near a changed
waterline from inheriting a value produced by linear interpolation through the
non-free-surface hull interior. The current result does not change the A53 and
joint two-zone numbers above, but it removes a nonphysical interpolation path
that would otherwise contaminate later grid-convergence studies.

A further Eq.24 diagnostic adds an explicit history-convolution quadrature
choice. A1 Section 3.4 states that the transient free-surface Green-function
convolution is evaluated with the trapezoid method, so
`history_convolution_rule` and `--history-convolution-rules` now expose both
`rectangle` and `trapezoid` for comparison, with `trapezoid` as the default.
`outputs/matched_wigley_history_quadrature_compare` confirms that trapezoid
weighting lowers the retained history RHS peaks, but it barely changes the
first-row Wigley III coefficients: `A33=4.659`, `A35=-0.756`, `A53=0.367`,
and `A55=0.0377`, all still outside their gates. Therefore the history-weight
choice is now closer to the paper, but the remaining blocker is not solved by
this quadrature correction alone.

The Eq.24 history kernel has also been split into its two physical channels.
`history_potential_kernel_scale` acts on the transient Green potential term
`B^{m-k}_{ij} psi_n`, and `history_normal_derivative_kernel_scale` acts on
the transient Green normal-derivative term `C^{m-k}_{ij} psi`. The A53
nine-case diagnostic in
`outputs/matched_wigley_history_kernel_channel_compare` stays in the narrow
range `0.360-0.369`, so a simple sign error in either retained history channel
does not explain the A53 gate failure. In
`outputs/matched_wigley_joint_history_kernel_channel_compare`, reversing the
`B` history channel can make the first-row A55 value pass, but A33, A35, and
A53 remain far outside tolerance. This is useful evidence, but not a valid
production correction.

The next Eq.24 diagnostic exposes the instantaneous control-surface block.
`control_image_scale`, `control_potential_kernel_scale`,
`control_normal_derivative_kernel_scale`, and `control_diagonal_sign` are now
available through the matched solver and CLI. In
`outputs/matched_wigley_control_instant_a53_compare`, using
`control_image_scale=-1` with a non-singular diagonal convention can bring the
first-row A53 value down to about `0.183-0.186` against the `0.150` reference.
The joint check in `outputs/matched_wigley_joint_control_image_compare` is the
important result: the same image-sign family can make A35 and A53 pass their
coupling tolerances, but A33 stays near `4.03` and A55 rises to about `0.34`.
Therefore the instantaneous image sign is a strong formula-audit signal, not a
production default. Gate C now requires a simultaneous A33/A35/A53/A55 closure
before any Eq.24 sign convention can be accepted.

A pressure-component diagnostic now splits A1 Eq. (30) into the local
time-derivative pressure `-rho*i*omega*phi` and the forward-speed pressure
`rho*U*partial phi/partial x`. The split is written both at the whole-coefficient
level and at the station-diagnostic level. In
`outputs/matched_wigley_a33_a55_pressure_component_diagnostics`, the nearest
first-row A33 value (`0.886`) is entirely from the time-derivative channel, while
the passing A35 case (`-0.215`) is dominated by the forward-speed channel. The
passing A53 cases are again time-derivative dominated, and the nearest A55 case
(`0.0377`) is a residual after cancellation between `0.181` from the
time-derivative channel and `-0.143` from the forward-speed channel. The next
Gate C audit should therefore focus on pitch-mode body condition, lever arm,
`partial phi/partial x` differencing, and the A1 Eq. (32) end-term convention.

The `partial phi/partial x` differencing audit is now explicit through
`pressure_gradient_scheme` and `--pressure-gradient-schemes`. In
`outputs/matched_wigley_pressure_gradient_scheme_compare`, central, forward,
and backward station differences do not close the first-row A55 gate: the best
central value is about `0.0377`, backward about `0.0333`, and forward about
`0.3009` against the `0.063` reference. A35 remains sensitive to the differencing
choice, but A55 failure is not solved by changing finite-difference direction.
The next audit should treat the Eq. (32) Stokes end term and the pitch `U m_j`
body-condition channel as the primary suspects.

The pitch body-condition channel audit is now explicit. Station diagnostics
write the norms of the `i*omega*N5` channel and the `U*m5` channel separately.
In `outputs/matched_wigley_pitch_body_condition_channel_compare`, reversing the
pitch `U*m5` channel can move first-row A55 to about `0.0687`, inside the
tolerance around the `0.063` reference, but the same case gives A35 about
`+0.319` against the `-0.200` reference. This rejects a simple `m5` sign flip as
a production correction and points instead to the full Eq. (32) Stokes assembly
and force-row convention.

This is an implementation milestone, not a validation pass. The remaining hard
requirements are: calibrate the newly connected inner-free-surface marching
against Wigley III with time-step/grid/control-surface sensitivity checks,
implement diffraction/excitation before motion-response use, verify the physical
end station/orientation and sign convention for the A1 Eq. (32) helper, and compare
`A33/B33/A35/B35/A53/B53/A55/B55` against the Wigley III digitized curves under
the Gate C error limits.

## 2026-07-18 Fridsma Update

Fridsma configuration A is now an active development benchmark through
`benchmarks/fridsma/regular_wave_motion_digitized.csv`. The data were taken
from the local parsed Sun & Faltinsen 2010 Fig. 4/Fig. 6 tables that compare
against Fridsma experiments.

Latest local result at `outputs/validation_current`:

- `fridsma_regular_wave_amplitudes`: `FAIL`, with 15 PASS and 12 FAIL checks.
- The rows use Sun & Faltinsen's prescribed running state, `trim=4 deg` and
  `lambda_W=3.6`, so calm-water attitude reconstruction is no longer a hidden
  source of the amplitude mismatch.
- The 20 direct amplitude comparisons are 9 PASS / 11 FAIL. The aggregate
  max-error row also fails and points to
  `figures/fridsma_regular_wave_amplitudes_comparison.png`. The short-wave and
  resonance-near points are the main mismatch; long-wave motion amplitudes are
  closer.
- This means the present outputs can be called a development baseline, not a
  validated complete 2.5D prediction.

Concrete next target: audit the Fridsma values against the original report,
digitize the remaining Katayama amplitude curves, and replace the current
compact/prototype hydrodynamics with a validated section pressure/radiation/
diffraction 2.5D solver that passes Fridsma, Katayama, and Ma 2005 gates.

## 2026-07-18 Katayama Amplitude Input Update

Katayama amplitude validation remains pending because no reliable numeric
Fig. 9/Fig. 10 response points were exposed in the currently accessible source
text. The benchmark interface is ready for manual digitization:

- `benchmarks/katayama/regular_wave_response_digitized.csv` may provide pitch
  either as `pitch_rao_rad_per_m` or as the raw figure ordinate
  `pitch_rao_rad_per_wave_slope`.
- The validator converts the raw ordinate to rad/m using each row's wavelength
  and writes `reference_source_column` in the comparison CSV.
- Until those digitized amplitude rows are present, the corresponding gate must
  remain `NOT_EVALUATED`; passing the jumping-classification gate alone is not
  sufficient for complete 2.5D validation.

## 2026-07-31 Eq.32 Stokes Body-Term Audit Update

The Ma 2005 Gate C audit now includes an explicit A1 Eq. (32) body
forward-speed diagnostic. The implementation stores `rho U integral(phi_j m_i
ds)` separately from the default Eq. (30) finite-difference pressure-gradient
path, and writes both coefficient-level and station-level columns under
`outputs/matched_wigley_eq32_stokes_body_diagnostics`.

The first-row focused comparison shows that the Stokes body term is structurally
zero for `A35` because the heave-force row has `m3=0`. For `A55`, however, the
same diagnostic gives about `+0.699` with the default pitch-row convention and
about `-0.699` when the pitch forward-speed sign is reversed, while the
reference value is only `0.063`. This means the Stokes body term is implemented
and visible, but it is not yet a production replacement for the Eq. (30)
gradient term. The remaining acceptance condition is now sharper: the end
contour term `-rho U integral_CA(phi_j N_i dl)`, its station/orientation
convention, and the pitch-row `m5/N5` convention must be audited together. Gate
C remains `PENDING` until one physically justified setting improves
`A33/A35/A53/A55` simultaneously.

The paired end-contour scan in
`outputs/matched_wigley_eq32_stokes_end_body_balance` shows that the current
`C_A` helper cannot by itself balance the large pitch-row body term. The aft
`+C_A` option reduces the Eq. (30) `A55` result from about `0.219` to `0.127`,
but the full Stokes reconstruction still remains about `0.805`. The next gate
therefore requires a coordinate and generalized-row audit before further tuning:
`m5/N5`, body normal direction, pitch lever arm, pitch moment sign, and end
contour orientation must be checked as one convention set.

That convention set now has an explicit audit in
`outputs/matched_wigley_a1_convention_audit`. The default implementation is
internally consistent: the recovered `N5` and `m5` residuals are near zero for
the default pitch lever and forward-speed signs, and deliberately reversing
those signs raises the corresponding residual to about `2`. The failure is
therefore no longer classified as an untracked internal sign mismatch. The next
acceptance step is a fixed coordinate-convention layer that maps A1 paper
coordinates, normals, and pitch reference points into the package's
`z_down/heave_up` convention before any further coefficient tuning is accepted.

The fixed layer is now implemented as `A1HeavePitchCoordinateConvention` and
`DEFAULT_A1_HEAVE_PITCH_CONVENTION`. It supplies the heave/pitch body-condition
rows, Eq. (30) pressure rows, Eq. (32) body `m_i` rows, and Eq. (32) end-contour
`N_i` rows from one object. The smoke run
`outputs/matched_wigley_a1_convention_layer` confirms that this was a neutral
refactor, not a numerical tuning step: `A35` and `A55` remain outside the Ma
2005 tolerances. The next evidence required for Gate C is a written and tested
paper-to-package coordinate mapping table before changing any convention signs.

That mapping table is now available as code through `A1CoordinateMappingRow` and
`DEFAULT_A1_HEAVE_PITCH_CONVENTION.paper_to_package_mapping_rows()`. It covers
the paper symbols `N3`, `N5`, `m3`, `m5`, the Eq. (30) pressure rows, and the
Eq. (32) body/end rows. The smoke run
`outputs/matched_wigley_a1_mapping_table` confirms that station diagnostics also
carry the convention name and validity status. Gate C remains `PENDING`; any
future sign or lever change must cite a mapping-table row and improve the joint
Wigley III coefficient gate, not only one coefficient.

The sign/lever audit is now executable as controlled candidate diagnostics. The
new `A1ConventionCandidate` layer, `a1_convention_candidate_cases()`, and
`write_a1_convention_candidate_benchmark()` generate annotated Wigley III
comparisons plus a candidate-to-mapping table under
`outputs/matched_wigley_a1_convention_candidates`. The current recommended-grid
first-row probe tested five candidates: the default mapping, reversed `N5` plus
pitch force row, reversed `m5` forward-speed row, reversed pitch output force
row, and all pitch rows reversed. None passes the joint gate. The best values by
coefficient are `A33=4.554` versus `1.000`, `A35=-0.668` versus `-0.200`,
`A53=0.334` versus `0.150`, and `A55=0.0847` versus `0.063`. The immediate
acceptance implication is that Gate C is not blocked by a single untracked pitch
sign. Further work should return to Eq. (23)-Eq. (24) inner/outer matching,
instantaneous control-surface terms, free-surface normal-derivative scaling, and
the source-figure normalization audit.

The Eq. (24) instantaneous control-surface terms now have the same controlled
diagnostic treatment through `A1ControlSurfaceCandidate`,
`a1_control_surface_candidate_cases()`, and
`write_a1_control_surface_candidate_benchmark()`. The output directory
`outputs/matched_wigley_a1_control_surface_candidates` shows that
`reverse_image_and_both_columns` is the relative best for `A33/A35/A53`, but it
still gives `A33=4.220`, `A35=-0.458`, and `A53=0.233`, all outside the gate.
The relative best `A55` control-surface candidate is `reverse_image_terms`, with
`A55=0.152` versus `0.063`. Reversing only the potential column, only the
normal-derivative column, or the diagonal term produces pathological magnitudes.
The acceptance implication is that no single Eq. (24) sign switch should be
promoted to production default; the control-surface kernel scaling, normal
direction, and full matched matrix normalization must be audited together.

Matched Wigley sensitivity rows also now include Ma 2005 Eq. (34) normalization
audit fields. The paper states the `rho*displacement_volume`, `rho*
displacement_volume*L`, and `rho*displacement_volume*L^2` denominators, and the
current code uses that convention. The first A33 row would need a normalization
scale about `4.55` times larger to match the reference, so the diagnostic is
`normalization_scale_unlikely_as_sole_explanation`. The A33 blocker should
therefore be treated as a section-radiation/free-surface/control-surface
matching problem rather than a simple nondimensionalization typo.

The matched-section matrix now has a block-level audit through
`MatchedSystemBlockAudit` and `audit_matched_system_blocks()`. The audit splits
each solved section into Eq. (23) body, Eq. (23) free-surface, Eq. (23) inner
control, and Eq. (24) outer-control equation rows, and into `psi_body`,
`psi_n_free_surface`, `psi_control`, and `psi_n_control` unknown blocks. The
new station diagnostics under `outputs/matched_wigley_a1_block_audit` show that
the first-row `A33` and `A53` peak station contributions are both dominated by
`eq23_body<-psi_body`; the same block is dominant at 37 of 39 active stations
for both coefficients. The next Gate C acceptance action is therefore to audit
the Eq. (23) body-row raw log kernel, self-term, `2*pi` normalization, and
`psi_body` unit scale before further tuning Eq. (24) history or pitch-sign
candidates.

The Eq. (23) inner-kernel normalization candidates are now executable through
`A1InnerKernelCandidate` and `write_a1_inner_kernel_candidate_benchmark()`. The
joint first-row output under
`outputs/matched_wigley_a1_inner_kernel_candidates_joint` shows that applying
`1/(2*pi)` to both `Aij` and `Bij` leaves the solution unchanged, as expected
for consistent row scaling. Applying `1/(2*pi)` to `Bij` only is the relative
best candidate for `A33/A35/A53/A55`, but it still fails all four checks:
`A33=0.749`, `A35=-0.111`, `A53=0.0157`, and `A55=-0.0300`. This makes
`Bij/2*pi` an important diagnostic clue, not a production correction. The next
acceptance action is to close the relative unit scale between `psi`, `psi_n`,
the Eq. (23) `Aij/Bij` blocks, and Eq. (30) pressure recovery.

That unit-scale audit is now an explicit diagnostic output. Station rows include
`a1_unit_closure_status`,
`a1_unit_body_potential_per_normal_velocity_length_m`,
`a1_unit_body_potential_per_normal_velocity_over_span`,
`a1_unit_inner_fs_normal_derivative_to_body_condition_norm_ratio`, and
`a1_unit_pressure_time_over_rho_omega_phi_norm_ratio`. The smoke output under
`outputs/cli_inner_kernel_smoke` confirms that the direct Eq. (30) time-pressure
identity closes with a ratio of `1.0`. The recommended-grid comparison under
`outputs/matched_wigley_a1_unit_closure_probe` shows that raw Eq. (25) gives a
median body-potential length scale of about `4.210` local spans, while
`Bij/(2*pi)` lowers it to about `0.783` local spans. This explains why the
B-only candidate reduces the over-large heave potential channel, but it also
over-suppresses `A53`.

The combined `Bij/(2*pi)` plus A1 convention candidate output under
`outputs/matched_wigley_a1_inner_b2pi_convention_candidates` still fails the
joint first-row gate: the best values are `A33=0.749`, `A35=-0.111`,
`A53=0.0157`, and `A55=0.0300`. Therefore Gate C/Gate 1 cannot be closed by a
single B-kernel normalization or a pitch-row sign change. The next accepted
movement must derive a physically consistent Eq. (23) kernel/unknown unit
mapping and a pitch-mode `N5/m5/U*m_j` coordinate transform, then pass the joint
`A33/A35/A53/A55` check.

The Eq. (23) closed-boundary Green-identity audit is now executable and written
under `outputs/matched_wigley_a1_inner_kernel_green_identity`. It uses a closed
ellipse and analytic harmonic potentials, so it isolates the local inner-kernel
math from Wigley digitization, free-surface marching, control-surface matching,
and pitch conventions. The result is decisive for this layer: raw Eq. (25) with
the Eq. (23) `-pi` self term passes all four analytic potentials, and applying
`1/(2*pi)` to both `Aij` and `Bij` also passes because it is only row scaling.
Applying `1/(2*pi)` to `Bij` only fails the identity, as do `+pi` self term and
A/B sign reversal. Therefore, the next Gate C/Gate 1 work should stop treating
B-only normalization as a possible production correction and instead audit the
open body/free/control mixed-boundary unit mapping and the pitch-mode coordinate
transform.

The open mixed-boundary unit-mapping audit is now also executable under
`outputs/matched_wigley_a1_inner_mixed_boundary_identity`. It splits one closed
ellipse into body, inner-free-surface, and control blocks, then substitutes
analytic harmonic potentials into the same Eq. (23) known/unknown placement used
by the matched solver: known body `phi_n`, known inner-free-surface `phi`, and
unknown control `phi/phi_n`. Raw Eq. (25) passes all four analytic potentials at
the recommended audit panel counts, while B-only normalization, `+pi` self term,
and A/B sign reversal fail. This removes the Eq. (23) raw inner kernel and the
body/free/control Eq. (23) row transfer from the primary suspect list. Remaining
Gate C/Gate 1 work should target the free-surface state update, Eq. (24)
outer-control matching, station history inheritance, Eq. (30)/Eq. (32)
forward-speed accounting, and pitch-mode coordinate mapping.

## 不接受的完成方式

- 只展示自拟船型响应曲线。
- 只通过 Faltinsen 纵向 RAO，但 Ma 2005 系数失败。
- 只让外部 PDSTRIP smoke 能运行，但没有映射进 Ma 2005 验收。
- 只用经验系数调参贴合单条曲线，缺少站位/面元/时间步收敛检查。
- Fridsma 幅值 gate 失败或缺 Katayama 幅值数据时宣称滑行艇波浪运动已完整验证。
## 2026-07-31 A1 Free-Surface Oscillator Audit

The A1 Eq. (19)-Eq. (22) staggered free-surface marching has a new analytic
oscillator audit under `outputs/matched_wigley_a1_free_surface_oscillator_audit`.
The audit drives the marching state with an exact linear free-surface solution:
`eta=A cos(omega t + phase)`, `phi=-(g A / omega) sin(omega t + phase)`, and
`eta_t=-A omega sin(omega t + phase)`.  The comparison uses the package time
levels directly: elevation is checked at `half_step_time_s`, while potential is
checked at `time_s`.

The four-step refinement run gives max normalized errors of `0.032451`,
`0.008106`, `0.002026`, and `0.000512` for `dt_s=0.08, 0.04, 0.02, 0.01`.
The observed RMS convergence order is about `1.999` for elevation and `2.014`
for potential.  This result does not close Gate C/Gate 1 because it does not
include the Eq. (23)-Eq. (24) matched BIE feedback. It does, however, remove the
standalone Eq. (19)-Eq. (22) time-level discretization from the primary suspect
list. Remaining Wigley III failures should now be traced through the BIE-derived
inner-free-surface normal derivative scale, station history inheritance, Eq.
(24) control-surface matching, Eq. (30)/Eq. (32) forward-speed accounting, and
pitch-mode coordinate mapping.
## 2026-07-31 A1 Eq. (24) Outer-Control Green Identity Audit

The A1 Eq. (24) instantaneous outer-control block now has a half-plane analytic
identity audit under `outputs/matched_wigley_a1_outer_control_green_identity`.
The audit uses an antisymmetric image source inside the half-cylinder control
surface, `phi=ln(r)-ln(r')`.  This field is harmonic in the outer half-plane and
is zero on the free surface, so it isolates the no-history control-surface
terms from Wigley digitization, body pressure integration, pitch conventions,
and station marching.

The default Eq. (24) instantaneous terms pass the audit: the finest-grid maximum
relative residual over the two source points is `0.000686`.  Reversing the image
terms fails with finest residual `0.808718`; reversing the diagonal self term
fails with residual `1.000000`; reversing either unknown column alone also
fails. Reversing both unknown columns passes the homogeneous no-history identity,
but that is only a row-sign ambiguity until the history right-hand side is
included.

This result rejects `control_image_scale=-1` as a production correction even
though that candidate locally improved some Wigley coupling coefficients.  The
remaining Gate C/Gate 1 work should therefore move from the Eq. (24)
instantaneous image/diagonal signs toward BIE-fed history-RHS sign and scaling,
control-surface state inheritance, inner-free-surface normal-derivative scale,
Eq. (30)/Eq. (32) forward-speed accounting, and pitch generalized-force
assembly.
## 2026-07-31 A1 Eq. (28) Transient-History Kernel Derivative Audit

The transient free-surface history kernel now has a direct derivative-channel
audit under `outputs/matched_wigley_a1_history_kernel_derivative_audit`.  The
audit checks whether the Eq. (28) normal-derivative kernel `C_ij^{m-k}` is
actually the source-normal derivative of the transient Green potential kernel
`B_ij^{m-k}`.  It perturbs the source control-surface collocation points by
`+epsilon` and `-epsilon` along the stored panel normal and compares the central
finite difference of the potential kernel with the implemented normal-derivative
kernel.

The formal run uses `panel_count=8/16/32`, `lag_s=0.02/0.05/0.10`,
`quadrature_count=256`, `k_max=50`, and `epsilon=1e-4 m`.  All rows pass.  The
maximum relative residual over the audit matrix is about `1.05e-6`; the lag-wise
finest-panel residuals are `1.05e-6`, `9.69e-7`, and `7.00e-7`.

This result supports the internal consistency of the transient-history
normal-derivative channel. It does not close Gate C/Gate 1 because the complete
history right-hand side also depends on time-convolution signs, cutoff and
quadrature convergence, station-to-station control-state inheritance, and phase
alignment with the instantaneous Eq. (24) terms.
## 2026-07-31 A1 Eq. (24) History-RHS Quadrature/Cutoff Convergence Audit

The Eq. (24) history right-hand side now has a reference-refinement audit under
`outputs/matched_wigley_a1_history_rhs_convergence_audit`.  The audit uses a
deterministic smooth complex control-surface history state and compares each
candidate `quadrature_count/k_max` pair with a higher-resolution transient
kernel reference.  It reports the total RHS residual and the two individual
history channels: the potential-kernel channel `B_ij^{m-k} psi_n` and the
normal-derivative-kernel channel `C_ij^{m-k} psi`.

The formal run uses `panel_count=10`, `dt=0.05 s`, `history_steps=4`,
`quadrature_rule=trapezoid`, and reference settings
`reference_quadrature_count=768`, `reference_k_max=120`.  All rows pass the
`1e-3` diagnostic tolerance.  The maximum channel residual decreases from
`8.63e-4` at `(quadrature_count=48, k_max=40)` to `4.94e-5` at
`(quadrature_count=256, k_max=80)`.  The residual is dominated by the
potential-kernel channel; the normal-derivative channel is already between
`1.27e-5` and `5.91e-8`.

This supports the numerical quadrature/cutoff convergence of the synthetic
history RHS.  It does not close Gate C/Gate 1 because the real Wigley chain also
depends on station-to-station control-state inheritance, BIE-generated history
states, and phase/scale consistency between the Eq. (24) history RHS and the
instantaneous control-surface block.

## 2026-07-31 A1 Control-History Inheritance Acceptance Note

`outputs/matched_wigley_a1_control_history_inheritance_audit` has been added as
an implementation acceptance artifact for A1 Eq. (24). It reconstructs the real
Wigley station-sweep control-surface history queue from `solve_order` and the
returned station solutions, then recomputes the stored history RHS for every
active station.

The formal run uses `a1_history_inheritance_recommended` on the first `A33` and
`A53` reference rows. The four summary groups (`A33/heave`, `A33/pitch`,
`A53/heave`, `A53/pitch`) each have 39 pass rows and zero fail rows. The maximum
RHS relative residual and maximum lag-0 inheritance residual are both `0.0`.

Acceptance implication: station-to-station history queue ordering is no longer
a primary Gate 1 suspect. This is still not a hydrodynamic pass. Gate 1 remains
`PENDING` until the Ma 2005 Wigley coefficients meet the diagonal 15 percent and
coupling 30 percent error gates. The remaining checks should focus on the
physical scale and phase of `psi_control/psi_n_control`, inner free-surface
normal-derivative scale, Eq. (30)/Eq. (32) forward-speed accounting, pitch
coordinate mapping, and source-curve digitization/normalization.

## 2026-07-31 A1 Outer-Control Balance Acceptance Note

`outputs/matched_wigley_a1_outer_control_balance_audit` has been added as the
next A1 Eq. (24) acceptance artifact. It uses the real Wigley station sweep and
splits the solved outer-control equation into instantaneous potential-column,
instantaneous normal-derivative-column, history `B_ij psi_n`, and history
`C_ij psi` components.

The formal recommended-style run again evaluates the first `A33/A53` rows for
heave and pitch. All 156 detail rows pass the `1e-5` numerical balance
tolerance. The maximum relative balance residual is about `1e-6` to `5e-6`.
The diagnostic ratios show that the Eq. (24) row balances the history RHS
(`median_rhs_to_lhs_norm_ratio=1.0`), while the two instantaneous columns nearly
cancel (`median_potential_normal_real_alignment` about `-0.9998`, phase near
`180 deg`). The two history channels also strongly oppose each other
(`median_history_channel_real_alignment` about `-0.91`).

Acceptance implication: Eq. (24) assembly, history RHS reconstruction, and
station inheritance are now implementation-consistent on the real Wigley sweep.
The remaining Gate 1 question is physical, not bookkeeping: whether the
near-cancelling control-surface balance has the correct scale and phase after
coupling with Eq. (23), the inner free-surface normal derivative, Eq. (30)
pressure recovery, Eq. (32) forward-speed terms, and pitch generalized-force
mapping.

## 2026-07-31 A1 RHS Source Decomposition Acceptance Note

`outputs/matched_wigley_a1_rhs_source_decomposition_audit` has been added to
identify which known source drives the matched Eq. (23)-Eq. (24) solution. Each
station is solved three extra times with only one RHS source active:
`body_normal_velocity`, `inner_free_surface_potential`, or
`outer_control_history`.

The formal recommended-style Wigley run produces 468 detail rows and 12 summary
groups. All source decompositions pass, with maximum source-sum relative
residual about `1.6e-15`. The median full-solution norm ratios show the driver
ordering clearly: `inner_free_surface_potential` contributes about `0.88-0.91`,
`body_normal_velocity` contributes about `0.61-0.71`, and
`outer_control_history` contributes only about `0.002-0.003`.

Acceptance implication: the current first-row Wigley gap should no longer be
primarily attributed to the transient outer-history RHS. The dominant path into
the control-surface unknowns is the Eq. (23) inner-free-surface known potential
and its marched state. The next Gate 1 audit should therefore check
`free_surface_potential_by_station`, BIE-derived
`inner_free_surface_normal_derivative`, free-surface interpolation/marching
scale, and their propagation into Eq. (30) and Eq. (32).
