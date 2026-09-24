# Station-Based 2.5D Prototype API

This file documents the first station-based API scaffold for the complete 2.5D target.

## Status

`planing_seakeeping.station_2p5d` is a prototype and is not yet a validated boundary-integral 2.5D solver.

The module deliberately exports:

- `STATION_2P5D_STATUS = "frequency_forward_speed_prototype_not_validated"`
- `STATION_2P5D_VALIDATED = False`

Because of that, `python -m planing_seakeeping validate --benchmark all` must continue reporting the complete station-based solver gate as `NOT_EVALUATED`.

## Current Capability

The prototype can:

- read a hard-chine V-section hull file such as `configs/example_station_hull.yml`
- read explicit wetted-section offset point lists such as `configs/example_station_offsets.yml`
- read long-form offset CSV tables through `offsets_file`, as in `configs/example_station_offsets_csv.yml`
- generate Wigley III and SL-7-surrogate station hulls for benchmark wiring
- compute section waterline beam, submerged area, and centroid estimates
- integrate displacement volume, waterplane area, and pitch waterplane moment
- assemble 6DOF development strip matrices in `[surge, sway, heave, roll, pitch, yaw]` order
- include frequency-dependent heave/pitch radiation kernels and a forward-speed coupling channel inspired by Ma 2005 Eq. (4), Eq. (6), Eq. (32), and Eq. (33)
- solve an experimental 2D free-surface source-panel heave-radiation problem for each station through `planing_seakeeping.section_bem`
- solve an experimental zero-speed sway/heave/roll section-radiation matrix audit and flatten it by station through `section_bem_multimode_station_diagnostics`
- solve experimental body-panel radiation/diffraction pressure-transfer diagnostics and flatten them by station through `section_bem_pressure_transfer_station_diagnostics`
- reconstruct the forward-speed main-radiation heave/pitch operator from body-panel pressure transfers through `forward_speed_pressure_transfer_diagnostics`
- reconstruct the PDSTRIP-step pressure-gradient/end-term heave/pitch operator from body-panel pressure transfers through `forward_speed_pressure_gradient_diagnostics`
- assemble selectable `pressure_transfer_forward` and `pressure_transfer_pdstrip_step` heave/pitch operators from pressure-transfer-derived sectional coefficients
- assemble diagnostic `pressure_transfer_pdstrip_damping_forward` and `pressure_transfer_pdstrip_damping_pdstrip_step` heave/pitch operators that keep pressure-transfer added mass but use `pdstrip_style` sectional damping for Ma `B35/B53` frequency-shape triage
- decompose longitudinal `A33/B33/A35/B35/A53/B53/A55/B55` forward-speed contributions by station through `forward_speed_coupling_station_contribution_diagnostics`
- solve a PDSTRIP-style symmetric-section heave-radiation diagnostic using panel-integral source influence coefficients and a far-field free-surface radiation condition
- assemble a diagnostic `strip_2p5d_forward` heave/pitch operator from PDSTRIP-style sectional coefficients, a forward-speed section-velocity map, and a continuous longitudinal-gradient term
- assemble a diagnostic `strip_2p5d_pdstrip_step` heave/pitch operator from the same section data using the bow-to-stern PDSTRIP-step gradient/end-term difference
- assemble a diagnostic `hybrid_forward_coupling` matrix that keeps prototype diagonal terms and uses forward-speed heave/pitch couplings
- assemble a diagnostic `hybrid_pressure_damping_coupling` matrix that keeps prototype diagonal terms, uses forward-speed added-mass couplings, and uses pressure-transfer PDSTRIP-step damping couplings
- assemble zero-speed 6DOF added-mass and damping matrices from external PDSTRIP section radiation through `assemble_external_pdstrip_section_6dof_matrices`
- solve an experimental fixed-section incident/diffraction wave-excitation problem for each station
- compute a prototype complex Froude-Krylov excitation vector
- solve a prototype or experimental-BEM 6DOF RAO sweep through the `station-prototype` CLI command; the BEM path now uses BEM-derived wave excitation rather than only the prototype Froude-Krylov vector
- export per-frequency 6DOF added-mass, damping, restoring, excitation, and RAO tables through `station_frequency_matrices_long.csv`, `station_excitation.csv`, and `station_rao.csv`

The prototype cannot yet:

- solve the validated 2D matched radiation and diffraction boundary-integral problems
- compute validated sectional added mass/damping/excitation
- output validated full 6DOF station-based coefficients
- pass Ma 2005 Wigley III / SL-7 coefficient benchmarks

The Ma 2005 validator can already consume digitized coefficient CSV files, parse Froude-number speed cases such as `Fn0.4`, and produce coefficient-error rows. With the current development solver those rows are diagnostics; the complete solver gate remains `NOT_EVALUATED` until a validated matched boundary-integral section method is connected.

The experimental `section_bem` path uses a compact Rankine-source/free-surface panel formulation for heave radiation, a zero-speed sway/heave/roll radiation-matrix audit, body-panel radiation/diffraction pressure-transfer diagnostics, and fixed-section incident/diffraction excitation. It is useful for API wiring, conditioning checks, and future replacement of the empirical radiation/excitation kernels, but it does not yet include the full Ma 2005 matched inner/outer-domain time-stepping formulation or validated forward-speed diffraction terms.

The experimental `pdstrip_style` path ports the open-source PDSTRIP section-solver idea of panel-integral source kernels and a free-surface radiation condition into the Python diagnostic API. It is a stronger sectional-radiation sanity path than the compact collocation BEM, but the latest Ma 2005 run still fails the coefficient gates, so it is evidence for triage rather than validation.

The experimental `strip_2p5d_forward` path keeps the PDSTRIP-style sectional heave radiation data and changes the global station assembly. It forms a complex heave/pitch dynamic operator from `a - i b / omega`, a forward-speed velocity map, and a finite-difference longitudinal-gradient term, then decomposes that operator back into `A(omega)` and `B(omega)`. The experimental `strip_2p5d_pdstrip_step` path uses the same section data but applies the bow-to-stern PDSTRIP-step end-difference used by the pressure-gradient diagnostic. In the latest local Ma 2005 diagnostics both paths pass 17/55 side-by-side Ma rows, so the step path is a reproducible diagnostic branch rather than a validation fix.

The validation command now writes `ma2005_*_pdstrip_step_sign_audit.csv` when `--ma-compare-hydro-models` is enabled. This audit compares the selected station-convention `pdstrip_step` sign with the opposite accumulator-sign variant already present in `forward_speed_coupling_variant_diagnostics`. A focused Wigley B53 run supports retaining the current station sign because the opposite accumulator sign flips the B53 damping-coupling sign relative to Ma 2005 references; the remaining B35/B53 error is therefore treated as a frequency-shape/section-pressure problem, not a simple sign switch.

The validation command also accepts `--ma-panel-convergence`. It reruns selected Ma rows for `pressure_transfer_forward` and `pressure_transfer_pdstrip_step` over three section-BEM panel settings and writes `ma2005_*_panel_convergence.csv` plus `ma2005_*_panel_convergence_summary.csv`. A failed coefficient with low panel-change but high Ma gate error should be treated as a formulation or pressure-frequency-shape blocker; a panel-sensitive row should be rerun with finer section numerics before changing the physical model.

The experimental `hybrid_forward_coupling` path is an error-isolation model. It preserves the prototype diagonal terms that currently pass many Ma 2005 checks and replaces only `A35`, `A53`, `B35`, and `B53` with the forward-speed assembly. Latest local diagnostics show the complete Ma gate still fails, so this path should be used to debug coupling assembly, not to predict final motions.

The experimental `hybrid_pressure_damping_coupling` path is an even narrower damping-coupling probe. It preserves prototype diagonal terms, keeps `A35/A53` from the forward-speed assembly, and replaces only `B35/B53` with the pressure-transfer PDSTRIP-step damping couplings. It is meant to test the current blocker-ranking evidence that pressure-transfer paths are closest for Wigley `B35/B53`; it is not a validated hydrodynamic model.

The experimental `pressure_transfer_forward` and `pressure_transfer_pdstrip_step` paths make the body-panel pressure-transfer route selectable in the same places as the other station radiation models. They derive each station's heave added mass and damping from pressure integration, then feed those section coefficients into the continuous-gradient or PDSTRIP-step forward-speed assembly. The latest Ma 2005 diagnostics show the path is finite and traceable, with 16/55 PASS for Wigley III and 0/48 PASS for SL-7 in `outputs/validation_current`; it remains tied to the current compact pressure-transfer accuracy and is not a validated coefficient source.

The diagnostic `pressure_transfer_pdstrip_damping_forward` and `pressure_transfer_pdstrip_damping_pdstrip_step` paths keep pressure-transfer-derived sectional added mass but replace sectional damping with the local `pdstrip_style` section solver. They are shape-matched probes for the B35/B53 damping-coupling blockers; they are not a validated pressure-transfer formulation and their status strings remain `diagnostic_*_not_validated`.

The `forward_speed_coupling_station_contribution_diagnostics` helper is an error-localization tool for Ma 2005 longitudinal coefficients. It writes station-level contributions for `A33/B33/A35/B35/A53/B53/A55/B55` from force-integrated collocation, force-integrated PDSTRIP-style, raw pressure-transfer, and clipped pressure-transfer sources under both continuous-gradient and PDSTRIP-step assemblies. The validation wrapper also writes a contribution-summary CSV that compares each source/operator total with the Ma row and reports required multiplier, cancellation ratio, and the longitudinal centroid of absolute contribution. Use these outputs to find where heave, pitch, or coupling errors originate along the hull; do not treat them as a separate accepted solver.

The external PDSTRIP station-section path is a reference adapter rather than a production dependency. The `pdstrip-station-sections` command writes package `StationHull` geometry to PDSTRIP, runs section hydrodynamics, parses `sectionresults`, and assembles zero-speed 6DOF added-mass/damping matrices from the external sway/heave/roll section radiation data. It closes the data path from station geometry to external section coefficients to package matrices, but it does not yet include the validated forward-speed pressure-gradient/diffraction mapping required for Ma 2005 acceptance.

When Ma external section profiles are enabled, the validation command now writes `ma2005_*_external_section_frequency_shape_summary.csv` in addition to the station profiles. This summary compares external PDSTRIP and local section-integral log slopes plus ratio spread for B33/B35/B55 terms over the selected frequencies. It is meant to flag sectional radiation-frequency-shape divergence before those errors are folded into B35/B53 forward-speed coupling coefficients.

For sparse or digitized offset tables, `--bem-body-panels N` arclength-resamples each wetted section before the experimental section-BEM solve. The original geometry is still audited in `station_geometry_audit.csv`; the resampled contour is only used for radiation/diffraction panel solves.

When `--radiation-model section_bem`, `pdstrip_style`, `strip_2p5d_forward`, `strip_2p5d_pdstrip_step`, `pressure_transfer_forward`, `pressure_transfer_pdstrip_step`, `pressure_transfer_pdstrip_damping_forward`, `pressure_transfer_pdstrip_damping_pdstrip_step`, `hybrid_forward_coupling`, or `hybrid_pressure_damping_coupling` is selected, the CLI writes `section_bem_diagnostics.csv`. Each row gives one station and one frequency with heave added mass per metre, damping per metre, matrix condition number, residual norm, panel counts, and the selected `section_solver`. This is the first audit layer needed before claiming full station-based 2.5D validation.

The same CLI mode also writes `section_bem_excitation_diagnostics.csv`. Each row gives one station and wave frequency with experimental incident/diffraction heave, sway, and roll excitation magnitudes plus residual and conditioning diagnostics. These rows make the excitation path auditable, but they still do not count as Ma 2005 acceptance.

For `--radiation-model section_bem`, `pressure_transfer_forward`, `pressure_transfer_pdstrip_step`, `pressure_transfer_pdstrip_damping_forward`, `pressure_transfer_pdstrip_damping_pdstrip_step`, or `hybrid_pressure_damping_coupling`, the CLI also writes `section_bem_multimode_radiation_diagnostics.csv`. Each row gives one station, one frequency, and one response/excitation mode pair from the experimental sway/heave/roll section-radiation matrix. It is a capability and reciprocity audit for the future complete 2.5D assembly, not an accepted Ma 2005 coefficient source.

For `--radiation-model section_bem`, `pressure_transfer_forward`, `pressure_transfer_pdstrip_step`, `pressure_transfer_pdstrip_damping_forward`, `pressure_transfer_pdstrip_damping_pdstrip_step`, or `hybrid_pressure_damping_coupling`, the CLI also writes `section_bem_pressure_transfer_diagnostics.csv`. Each row gives one station, one body panel, and one pressure component: radiation pressure by mode, incident wave pressure, diffracted pressure, or total wave pressure. The validation command checks that these pressure distributions integrate back to the section radiation matrix and fixed-section excitation forces. They are still experimental pressure transfers, not Ma 2005-validated pressure functions.

For `--radiation-model section_bem`, `pressure_transfer_forward`, `pressure_transfer_pdstrip_step`, `pressure_transfer_pdstrip_damping_forward`, `pressure_transfer_pdstrip_damping_pdstrip_step`, or `hybrid_pressure_damping_coupling`, the CLI also writes `forward_speed_pressure_transfer_diagnostics.csv`. It reconstructs the forward-speed main-radiation heave/pitch operator from body-panel pressure data and writes the pressure-based operator, the force-integrated operator, and their difference. This closes the pressure-to-operator mapping for the main-radiation term.

For `--radiation-model section_bem`, `pressure_transfer_forward`, `pressure_transfer_pdstrip_step`, `pressure_transfer_pdstrip_damping_forward`, `pressure_transfer_pdstrip_damping_pdstrip_step`, or `hybrid_pressure_damping_coupling`, the CLI also writes `forward_speed_pressure_gradient_diagnostics.csv`. It applies the same pressure-derived section coefficients to the PDSTRIP-step longitudinal-gradient/end-term assembly and compares the pressure-derived operator with the current force-integrated section-coefficient path. Passing this audit means the pressure-to-operator wiring matches the current scalar section-BEM path; it does not mean the underlying compact pressure transfer has passed Ma 2005.

For `--radiation-model strip_2p5d_forward`, `strip_2p5d_pdstrip_step`, `hybrid_forward_coupling`, or `hybrid_pressure_damping_coupling`, the CLI also writes `forward_speed_assembly_diagnostics.csv`. It splits each heave/pitch added-mass and damping term into `main_radiation`, `forward_gradient`, and `total` components, and includes an `assembly_method` column. This is intended for PDSTRIP/Ma 2005 assembly debugging and not for acceptance by itself.

Every station prototype run writes `station_geometry_audit.csv`. This file checks the parsed station geometry before hydrodynamic use: beam, draft, area, centroid location, offset signed area, point count, endpoint position at the calm-water free surface, and whether the section came from offsets or a parametric station. It is intended to catch digitization or coordinate-convention mistakes before they contaminate BEM coefficients.

## Next Implementation Step

Replace the prototype sectional coefficient estimate in `assemble_prototype_strip_matrices` with a validated section solver:

1. Load station offsets or generated hard-chine sections.
2. Replace the compact source-panel section model with the matched 2D radiation/diffraction method needed by Ma 2005 over encounter frequency.
3. Integrate sectional coefficients into 6DOF global matrices.
4. Compare against `benchmarks/ma2005/*_coefficients_digitized.csv`.
5. Set `STATION_2P5D_VALIDATED = True` only after the Ma 2005 gates pass.

## Prototype CLI

```powershell
python -m planing_seakeeping station-prototype configs\example_station_hull.yml --out outputs\station_prototype
```

Explicit station-offset input:

```yaml
length_m: 4.0
lcg_from_transom_m: 1.7
stations:
  - x_m: 1.3
    offsets_m:
      - [0.18, 0.0]
      - [0.0, 0.20]
      - [-0.18, 0.0]
```

`offsets_m` are wetted-section points ordered from starboard waterline to port waterline. Coordinates are `y_m` positive to starboard and `z_down_m` positive downward from the calm-water free surface. When offsets are present, station waterline beam, draft, submerged area, and centroid are derived from the point list unless explicit override fields are provided.

For digitized offset tables, use a separate CSV:

```yaml
length_m: 4.0
lcg_from_transom_m: 1.7
offsets_file: example_station_offsets.csv
```

The CSV is long-form, with one point per row:

```csv
station_id,x_m,point_order,y_m,z_down_m
s1,1.3,0,0.18,0.0
s1,1.3,1,0.0,0.20
s1,1.3,2,-0.18,0.0
```

Required CSV columns are `x_m`, `y_m`, and `z_down_m`. Optional columns include `station_id`, `point_order`, `beam_m`, `draft_m`, `deadrise_deg`, `waterplane_beam_m`, `submerged_area_m2`, and `centroid_z_below_waterline_m`. Relative `offsets_file` paths are resolved from the hull YAML/JSON location.

Experimental section-BEM diagnostic:

```powershell
python -m planing_seakeeping station-prototype configs\example_station_hull.yml --out outputs\station_bem --radiation-model section_bem --period-count 5
```

Body-panel refinement example:

```powershell
python -m planing_seakeeping station-prototype configs\example_station_offsets_csv.yml --out outputs\station_offsets_csv --radiation-model section_bem --bem-body-panels 20 --bem-free-surface-panels 8
```

PDSTRIP-style sectional-radiation diagnostic:

```powershell
python -m planing_seakeeping station-prototype configs\example_station_hull.yml --out outputs\station_pdstrip_style --radiation-model pdstrip_style --bem-body-panels 16 --bem-free-surface-panels 10 --period-count 5
```

Forward-speed station-assembly diagnostic:

```powershell
python -m planing_seakeeping station-prototype configs\example_station_hull.yml --out outputs\station_strip_2p5d_forward --radiation-model strip_2p5d_forward --bem-body-panels 12 --bem-free-surface-panels 8 --speed-mps 2.0 --period-count 5
```

PDSTRIP-step station-assembly diagnostic:

```powershell
python -m planing_seakeeping station-prototype configs\example_station_hull.yml --out outputs\station_pdstrip_step_forward --radiation-model strip_2p5d_pdstrip_step --bem-body-panels 12 --bem-free-surface-panels 8 --speed-mps 2.0 --period-count 5
```

Hybrid diagonal/coupling diagnostic:

```powershell
python -m planing_seakeeping station-prototype configs\example_station_hull.yml --out outputs\station_hybrid_forward_coupling --radiation-model hybrid_forward_coupling --bem-body-panels 12 --bem-free-surface-panels 8 --speed-mps 2.0 --period-count 5
```

Hybrid pressure damping-coupling diagnostic:

```powershell
python -m planing_seakeeping station-prototype configs\example_station_hull.yml --out outputs\station_hybrid_pressure_damping_coupling --radiation-model hybrid_pressure_damping_coupling --bem-body-panels 12 --bem-free-surface-panels 8 --speed-mps 2.0 --period-count 5
```

Pressure-transfer forward-speed diagnostic:

```powershell
python -m planing_seakeeping station-prototype configs\example_station_hull.yml --out outputs\station_pressure_transfer --radiation-model pressure_transfer_forward --bem-body-panels 8 --bem-free-surface-panels 4 --speed-mps 2.0 --period-count 5
```

Use `--radiation-model pressure_transfer_pdstrip_step` for the bow-to-stern PDSTRIP-step assembly driven by the same pressure-derived section coefficients. Use `pressure_transfer_pdstrip_damping_forward` or `pressure_transfer_pdstrip_damping_pdstrip_step` for the shape-matched damping diagnostic.

External PDSTRIP section reference and zero-speed 6DOF assembly:

```powershell
python -m planing_seakeeping pdstrip-station-sections configs\example_station_hull.yml --out outputs\pdstrip_station_sections_example --compare-section-bem --bem-free-surface-panels 4 --bem-body-panels 8 --omega 1.0
```

Outputs:

- `hydrostatics.csv`
- `station_geometry_audit.csv`
- `added_mass_6dof.csv`
- `damping_6dof.csv`
- `restoring_6dof.csv`
- `station_frequency_matrices_long.csv`
- `station_excitation.csv`
- `station_rao.csv`
- `section_bem_diagnostics.csv` for the experimental section-BEM, PDSTRIP-style, forward-speed station-assembly, or hybrid coupling model
- `section_bem_multimode_radiation_diagnostics.csv` for the experimental section-BEM or pressure-transfer models
- `section_bem_pressure_transfer_diagnostics.csv` for the experimental section-BEM or pressure-transfer models
- `forward_speed_pressure_transfer_diagnostics.csv` for the experimental section-BEM or pressure-transfer models
- `forward_speed_pressure_gradient_diagnostics.csv` for the experimental section-BEM or pressure-transfer models
- `section_bem_excitation_diagnostics.csv` for the experimental section-BEM model
- `forward_speed_assembly_diagnostics.csv` for the continuous-gradient forward-speed, PDSTRIP-step forward-speed, or hybrid coupling model
- `station_report.md`
