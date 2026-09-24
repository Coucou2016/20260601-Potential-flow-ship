# Fridsma Configuration A Digitization Notes

Source used in this repository:

- Sun, H. and Faltinsen, O. M. (2010), planing-vessel 2D+t comparison with Fridsma experiments.
- Local parsed file: `early_stage_materials/parsed_markdown/literature/planing_craft/Sun_Faltinsen_2010_planing/hybrid_auto/Sun_Faltinsen_2010_planing.md`.
- Figure data source: parsed tables below Fig. 4(a-b) for heave/pitch amplitudes and Fig. 6 for COG/bow acceleration amplitudes.

Configuration A metadata:

- `B=0.2286 m`, `L=5B=1.143 m`.
- `beta=20 deg`.
- `vcg=0.294B`.
- `M/(rho*B^3)=0.608`.
- Pitch radius of gyration is `0.251L`.
- `Fn_B=2.66`.
- Calm-water trim is reported as `4 deg`.
- Distance from COG to stem is `0.59L`, so `lcg_from_transom=0.41L`.
- Regular wave amplitude is `zeta_a=0.0555B`, therefore validator input `wave_height_over_b=0.111`.
- Bow accelerometer is 10 percent `L` aft of the stem, so `bow_x_from_cg=-(0.90L-0.41L)`.

Conversions:

- Heave values in Fig. 4(a) are `eta3a/zeta_a`; they are stored directly as `heave_rao_m_per_m`.
- Pitch values in Fig. 4(b) are `eta5a/(k*zeta_a)`. The validator compares `eta5a/zeta_a`, so each value was multiplied by `k=2*pi/(lambda_over_l*L)`.
- Acceleration values in Fig. 6 are amplitudes divided by `g`; they are stored directly as `cg_accel_g` and `bow_accel_g`.

Quality status:

- These are development-grade values extracted from already parsed figure tables whose numeric entries were marked approximate.
- They are suitable for activating a fail/pass development gate and identifying model gaps.
- They should be replaced or audited with a manual digitization from the original Fridsma report before final acceptance.
