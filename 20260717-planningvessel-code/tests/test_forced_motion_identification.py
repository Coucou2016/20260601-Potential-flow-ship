from __future__ import annotations

import math
import unittest

import numpy as np

from planing_seakeeping.forced_motion_identification import (
    assemble_forced_motion_matrices,
    extract_forced_motion_column,
    fit_periodic_harmonics,
)


class ForcedMotionIdentificationTests(unittest.TestCase):
    def test_sun_first_harmonic_equations_recover_known_matrices(self) -> None:
        omega = 2.4
        period = 2.0 * math.pi / omega
        time = np.linspace(0.0, 8.0 * period, 4001)
        added = np.asarray([[4.0, -2.0], [1.0, 3.0]])
        damping = np.asarray([[5.0, -1.0], [2.0, 4.0]])
        restoring = np.asarray([[10.0, -3.0], [2.0, 8.0]])
        amplitudes = (0.02, 0.008)
        columns = []
        for column, (motion_dof, amplitude) in enumerate(
            zip(("heave", "pitch"), amplitudes)
        ):
            sine = restoring[:, column] * amplitude - omega**2 * added[:, column] * amplitude
            cosine = omega * damping[:, column] * amplitude
            loads = (
                np.asarray([7.0, -3.0])[None, :]
                + np.sin(omega * time)[:, None] * sine[None, :]
                + np.cos(omega * time)[:, None] * cosine[None, :]
                + 0.03 * np.sin(2.0 * omega * time)[:, None]
            )
            columns.append(
                extract_forced_motion_column(
                    time,
                    loads,
                    motion_dof=motion_dof,
                    omega_rad_s=omega,
                    motion_amplitude=amplitude,
                    restoring_column=restoring[:, column],
                    discard_cycles=1.0,
                    retained_cycles=6.0,
                    fitted_harmonics=2,
                )
            )
        matrices = assemble_forced_motion_matrices(columns[0], columns[1])
        np.testing.assert_allclose(matrices.added_mass, added, rtol=1.0e-11, atol=1.0e-11)
        np.testing.assert_allclose(matrices.damping, damping, rtol=1.0e-11, atol=1.0e-11)
        self.assertFalse(bool(matrices.metadata["response_calibration_used"]))

    def test_harmonic_fit_requires_sufficient_retained_cycles(self) -> None:
        omega = 2.0
        time = np.linspace(0.0, 2.0 * math.pi / omega, 100)
        with self.assertRaises(ValueError):
            fit_periodic_harmonics(time, np.sin(omega * time), omega)

    def test_exact_requested_minimum_window_allows_one_sampling_interval(self) -> None:
        omega = 2.3
        period = 2.0 * math.pi / omega
        time = np.arange(0.0, 2.4 * period, period / 137.0)
        fit = fit_periodic_harmonics(
            time,
            np.sin(omega * time),
            omega,
            discard_cycles=0.75,
            retained_cycles=1.5,
        )

        self.assertGreaterEqual(
            fit.retained_cycle_count + 2.0 * (time[1] - time[0]) / period,
            1.5,
        )
        self.assertAlmostEqual(fit.sine[0], 1.0, places=12)


if __name__ == "__main__":
    unittest.main()
