# Literature Methods Extract

This note records the methods implemented in `planing_seakeeping` and the supporting local/open-source references reviewed.

## Core Implemented Method

- Faltinsen, *Hydrodynamics of High-Speed Marine Vehicles*, Ch. 9:
  - Planing-vessel steady running condition and geometry: eq. 9.48 plus wetted keel/chine length relations.
  - Linear heave/pitch equations: eq. 9.49.
  - Restoring coefficients by quasi-steady force derivatives: eq. 9.52.
  - Long-wave head-sea excitation: eqs. 9.90-9.116.
  - Frequency-domain RAO solve: eqs. 9.117-9.120.
  - Nonlinear time-domain heave/pitch solve: eqs. 9.121-9.125.
  - Exercise coefficients for regression/validation: eq. 9.138.
- Savitsky 1964:
  - Empirical lift coefficient, beam Froude number range, pressure-center trend, and planing trim relationship.
- Savitsky & Brown 1976 / Fridsma:
  - Useful for added resistance and average impact acceleration. The v1 code records this as a planned extension; the main response model currently uses Faltinsen wave excitation instead of these rough-water regressions.
- Fossen 2012:
  - 6DOF notation and environmental-force superposition.
  - Current effects are represented in v1 through an along-track speed-through-water correction.

## Open-Source Code Consulted

- OpenPlaning, MIT licensed, was available locally and online: <https://github.com/elcf/python-openplaning>. It informed the package decomposition for Savitsky/Faltinsen steady trim, wetted geometry, EOM matrices, and porpoising checks. The current implementation is self-contained.
- MSS / PythonVehicleSimulator were consulted for Fossen-style `eta`, `nu`, 6DOF output conventions, current-relative velocity notation, and simulation organization: <https://github.com/cybergalactic/PythonVehicleSimulator> and <https://github.com/cybergalactic/MSS>.
- `waveresponse` was consulted for the RAO plus wave-spectrum workflow pattern: <https://github.com/4Subsea/waveresponse-python>.
- Potential-flow and strip-theory tools in the local materials (`pdstrip`, `Nemoh`, `Capytaine`, `HAMS`) were treated as validation/upgrade paths rather than direct production dependencies for v1. The current `section_bem` diagnostic now includes a zero-speed sway/heave/roll radiation-matrix audit, compact body-panel radiation/diffraction pressure-transfer outputs, a pressure-based reconstruction of the forward-speed main-radiation station operator, and a pressure-based reconstruction of the PDSTRIP-step pressure-gradient/end-term operator. These pressure outputs are checked by integral closure and by station-operator closure against the current scalar section-BEM path, but the underlying compact pressure solution is not yet validated against Ma 2005. The current `pdstrip_style` diagnostic ports PDSTRIP-style sectional source influence integrals for heave-radiation triage, while remaining explicitly unvalidated against Ma 2005. The `strip_2p5d_forward` diagnostic follows PDSTRIP's global-assembly idea by adding a section-velocity `W` map and a continuous forward-speed longitudinal-gradient term before decomposing the dynamic operator into added mass and damping. The `strip_2p5d_pdstrip_step` diagnostic exposes the bow-to-stern PDSTRIP-step end-difference as a selectable station model; local Ma 2005 comparison shows it is not a validation fix by itself. The external `pdstrip-smoke` command now compiles and runs the local PDSTRIP source on a generated full-section V case, producing 260/260 section-frequency blocks; the `pdstrip-station-sections` command writes package `StationHull` geometry into PDSTRIP, parses arbitrary station-hull section hydrodynamics, and assembles zero-speed 6DOF added-mass/damping matrices from the external section radiation data; the `pdstrip-sectionresults` parser recovers `A_complex = radiation_force / omega**2` and exports section radiation, diffraction, and Froude-Krylov rows for later coefficient mapping. The `pdstrip-compare-section-bem` diagnostic compares those external section matrices with the local compact section-BEM on matching `geomet.out` sections, exposing current magnitude/sign/transpose differences before they are hidden by vessel-level integration. This proves PDSTRIP is runnable and parseable as a reference path but does not yet map its output into Ma 2005 acceptance. The `hybrid_forward_coupling` path is an error-isolation diagnostic that keeps prototype diagonal terms while testing forward-speed coupling terms; `hybrid_pressure_damping_coupling` narrows that split by testing pressure-transfer damping couplings only for `B35/B53`; and the station-contribution diagnostic now decomposes longitudinal `A33/B33/A35/B35/A53/B53/A55/B55` terms by source and station. These paths are explicitly unvalidated until the Ma 2005 gates pass. Useful open-source references include PDSTRIP <https://github.com/eriove/pdstrip>, Capytaine <https://github.com/capytaine/capytaine>, and OpenPlaning <https://github.com/elcf/python-openplaning>.
- Ma 2005 and the high-speed 2.5D review papers support why a 2.5D/slender-body method is appropriate at high speed, and why full 3D free-surface effects become important outside the v1 scope.

## Applicability And Limits

- Best suited to prismatic or near-prismatic hard-chine planing craft in head seas.
- `wave_heading_deg=180` is head sea. Other headings are accepted for encounter frequency, but v1 does not yet solve high-fidelity oblique 6DOF hydrodynamics.
- The heave/pitch model assumes no sustained jumping. When predicted wetted length collapses toward zero, slamming and re-entry loads are outside the implemented model.
- The linear RAO has no physical meaning if the heave/pitch system is linearly unstable; `summary.csv` reports the maximum eigenvalue real part.
