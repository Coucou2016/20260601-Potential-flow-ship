# Katayama / Hinami / Ikeda Digitization Notes

Current source audit:

- Source page: `https://www.researchgate.net/publication/238103035_LONGITUDINAL_MOTION_OF_A_SUPER_HIGH-SPEED_PLANING_CRAFT_IN_REGULAR_HEAD_WAVES`
- The page text identifies the paper as *Longitudinal Motion of a Super High-Speed Planing Craft in Regular Head Waves*, Proceedings of the 4th Osaka Colloquium on Seakeeping Performance of Ships, pp. 214-220, 2000.
- The page text reports the model particulars used by the existing classification benchmark: `LOA=0.625 m`, `B=0.250 m`, `draft=0.059 m`, `beta=22 deg`, `W=4.28 kgf`, `KG=0.111 m`, and `LCG=0.285 m from transom`.
- The text around Fig. 9 and Fig. 10 states that the plotted motion amplitudes are crest-to-trough based and that the axes are `zeta/zeta_w` for heave and `theta/(K*zeta_w)` for pitch, with `K=2*pi/lambda` and `zeta_w=H_w/2`.
- The accessible OCR text does not expose reliable numeric curve points from Fig. 9/Fig. 10, so no amplitude CSV has been added yet.

Validator convention:

- Add digitized heave points as `heave_rao_m_per_m = zeta/zeta_w`.
- Add digitized pitch points either as `pitch_rao_rad_per_wave_slope = theta/(K*zeta_w)` or as already converted `pitch_rao_rad_per_m`.
- The validator automatically converts `pitch_rao_rad_per_wave_slope` to `pitch_rao_rad_per_m` using each row's wavelength.
- A motion-only `regular_wave_response_digitized.csv` is acceptable for Fig. 9/Fig. 10 activation. `cg_accel_g` and `bow_accel_g` remain pending unless a separate source provides those acceleration amplitudes.

Quality status:

- `jumping_classification_digitized.csv` is active and checks clear jumping/non-jumping classification.
- `regular_wave_response_digitized.csv` is still pending because Fig. 9/Fig. 10 points need manual digitization from figure images.
