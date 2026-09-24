# Planing Seakeeping Run Report

- Config: `D:\Projects\20260601-Potential-flow-ship\20260717-planningvessel-code\configs\faltinsen_ch9_prescribed.yml`
- Method: Savitsky/Faltinsen calm-water planing equilibrium; Faltinsen Ch. 9 2.5D heave/pitch wave excitation; nonlinear time-domain quasi-steady restoring.
- 6DOF convention: `[surge, sway, heave, roll, pitch, yaw]`; v1 solves heave/pitch in head sea and emits zero placeholders for the other DOFs.

## Summary

```text
 speed_mps  speed_kn  speed_through_water_mps  fn_b  trim_deg   z_wl_m  keel_wetted_length_m  chine_wetted_length_m  lambda_w       equilibrium_source  equilibrium_converged  heave_force_residual_weight_fraction  pitch_moment_residual_weight_beam_fraction  stable_linear_hp  max_eigen_real irregular_method  heave_m_rms  pitch_rad_rms  heave_accel_mps2_rms  bow_vertical_accel_mps2_rms  regular_finite_response  regular_max_cg_vertical_accel_g  regular_max_bow_vertical_accel_g  regular_max_relative_heave_over_transom_draft  regular_jump_risk_flag  regular_dryout_risk_flag                                   regular_model_limit_note                                                                                     sixdof_note
  9.394671 18.261776                 9.394671   3.0       4.0 0.058686              4.863863               3.136137       4.0 prescribed_running_state                  False                             -0.470495                                    0.062745              True       -0.355867             none     0.025999       0.014207              1.005667                     2.907143                     True                         0.156735                          0.484457                                       0.148304                   False                     False no_jump_or_dryout_flag_from_simple_time_domain_diagnostics Head-sea 2.5D v1: heave/pitch solved; surge/sway/roll/yaw set to zero by symmetry/placeholders.
```

## Open-source references used for implementation guidance

- OpenPlaning: Savitsky empirical planing-hull structure and validation examples.
- OpenPlaning: <https://github.com/elcf/python-openplaning>
- MSS/PythonVehicleSimulator: <https://github.com/cybergalactic/PythonVehicleSimulator> and <https://github.com/cybergalactic/MSS>
- waveresponse: <https://github.com/4Subsea/waveresponse-python>
- Capytaine: <https://github.com/capytaine/capytaine>
