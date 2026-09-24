from __future__ import annotations

import numpy as np

from scripts.analyze_planing_station_harmonics import analyze_station_harmonics


def test_station_harmonic_spatial_and_direct_integrals_close() -> None:
    omega = 4.0
    period = 2.0 * np.pi / omega
    time = np.linspace(0.0, 2.5 * period, 161)
    x = np.asarray([0.1, 0.4, 0.75, 1.0])
    station_x = [x.copy() for _ in time]
    station_force = [
        (1.0 + 2.0 * x)
        * (2.0 + 3.0 * np.sin(omega * value) + 4.0 * np.cos(omega * value))
        for value in time
    ]

    rows, diagnostics = analyze_station_harmonics(
        time,
        station_x,
        station_force,
        omega_rad_s=omega,
        lcg_from_transom_m=0.35,
        discard_cycles=0.5,
        retained_cycles=2.0,
        x_point_count=1601,
    )

    assert len(rows) == 1601
    assert diagnostics["retained_cycle_count"] == 2.0
    assert diagnostics["max_density_fit_residual_nrmse"] < 1e-12
    assert diagnostics["max_spatial_harmonic_closure_relative_error"] < 2e-3
