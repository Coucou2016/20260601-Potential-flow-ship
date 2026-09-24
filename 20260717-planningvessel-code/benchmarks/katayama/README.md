# Katayama / Hinami / Ikeda Regular-Wave Benchmarks

Reference target:

- Super high-speed planing craft in regular head waves, with speed range around `Fn=2-5`.
- Intended checks: heave, pitch, vertical acceleration, nonlinear/jumping response classification.

Planned files:

- `regular_wave_response_digitized.csv`
- `jumping_classification_digitized.csv` (present; source-backed Fig. 7 classification subset)

Minimum response columns:

- `case_id`
- `fn` or `fn_b`
- `wave_height_over_b`
- `lambda_over_l`
- `heave_rao_m_per_m`
- `pitch_rao_rad_per_m` or `pitch_rao_rad_per_wave_slope`

Optional response columns:

- `cg_accel_g`
- `bow_accel_g`

Motion-only files digitized from Fig. 9/Fig. 10 are accepted so the heave/pitch
comparison can start before a source-backed acceleration dataset is available.
Missing acceleration columns are reported as `NOT_EVALUATED`; they do not count
as a completed Katayama amplitude gate.

Minimum classification columns:

- `case_id`
- `fn_l`
- `wave_height_over_draft`
- `lambda_over_loa`
- `expected_jumping`
- `observed_class`

Recommended `observed_class` values:

- `linear`
- `nonlinear_no_jump`
- `regular_jumping`
- `irregular_jumping`

Do not add placeholder numeric data here. Add only digitized or tabulated values with a source note.

Pitch ordinate convention:

- Katayama Fig. 9/Fig. 10 label pitch as `theta/(K*zeta_w)`, where `K=2*pi/lambda` and `zeta_w=H_w/2` is wave amplitude.
- If a digitized file provides `pitch_rao_rad_per_wave_slope`, the validator converts it to `pitch_rao_rad_per_m` using the row wavelength before comparing with the model.
- If a digitized file already provides `pitch_rao_rad_per_m`, it is used directly.

Current screening cases:

- `no_jump`: `Fn_L=1.21`, `H_W/d=0.68`, `lambda/LOA=1.60`
- `regular_jump`: `Fn_L=3.63`, `H_W/d=0.51`, `lambda/LOA=3.59`
- `irregular_jump`: `Fn_L=4.04`, `H_W/d=1.02`, `lambda/LOA=3.59`

The validation command treats these as a jump/non-jump classification check only. Motion and acceleration amplitude checks require additional digitized response curves.

Qualitative trend gate:

- `validate --benchmark all` also writes `katayama_qualitative_trends.csv` and `figures/katayama_qualitative_trends.png`.
- This gate is based on source-text statements around Fig. 9/Fig. 10, not on digitized ordinates.
- It checks that low-speed response increases with wavelength, high-speed response has a peak, and increasing wave height lowers the peak and shifts it to longer wavelength/period.
- The current linear frequency-domain RAO path is expected to fail the wave-height-dependent peak checks because its RAO is independent of wave amplitude.
- The validator also writes `katayama_nonlinear_pilot_trends.csv`, a short deterministic RK4 nonlinear time-domain probe at `Fn_L=3.63` and `lambda/LOA={3.0, 4.5, 6.0}`. It checks medium-wave peak reduction/shift only on non-dryout points and separately records large-wave dryout/model-limit risk.
- The nonlinear pilot is a development diagnostic. It is intentionally too sparse and too short to replace digitized response curves.
- Passing or failing this qualitative gate does not replace `regular_wave_response_digitized.csv`; source-backed numeric heave/pitch and acceleration curves are still required for amplitude acceptance.

Validation behavior for `regular_wave_response_digitized.csv`:

- If the file is missing, `validate --benchmark all` reports `NOT_EVALUATED`.
- If present, the validator reconstructs each regular-wave case and writes `katayama_regular_wave_amplitudes_comparison.csv`.
- If `case_id` matches `jumping_classification_digitized.csv`, model dimensions are filled from that source-backed table unless explicitly provided in the amplitude CSV.
- The comparison CSV records `reference_source_column` so the pitch conversion path remains auditable.
- If only Fig. 9/Fig. 10 heave/pitch data are present, `cg_accel_g` and
  `bow_accel_g` rows remain `NOT_EVALUATED` until source-backed acceleration
  data are added.
