# Faltinsen Ch. 9 Prescribed-State Benchmark

Reference:

- Odd M. Faltinsen, Hydrodynamics of High-Speed Marine Vehicles, Chapter 9.
- Prescribed state: `beta=20 deg`, `lambda_W=4`, `trim=4 deg`, `Fn_B=3`, `lcg/B=2.13`, `vcg/B=0.25`, `M/(rho B^3)=1.28`, `r55/B=1.3`.
- Table 9.2 eigenvalues are encoded in `planing_seakeeping.validation` and are written to `faltinsen_ch9_eigenvalues.csv` during validation.

Digitized RAO curve files used by the validator:

- `fig_9_34_heave_rao_digitized.csv`
- `fig_9_35_pitch_rao_digitized.csv`

Required columns:

- `lambda_over_l`: incident wavelength divided by average wetted length `L=lambda_W B`.
- `heave_rao_m_per_m` for Fig. 9.34.
- `pitch_rao_rad_per_wave_slope` for Fig. 9.35, because the published ordinate is `|eta5|/(k zeta_a)`.

The `.template` files remain as column-format references. The active CSV files contain the current manual digitization of the solid `Theory` curves. See `digitization_notes.md` for the source links, coordinate definitions, and uncertainty note.

`faltinsen_ch9_eigenvalues.csv` is not digitized from a curve; it is a direct Table 9.2 regression table written by the validator. The accepted tolerance is 10 percent for each nondimensional real part and modal frequency.
