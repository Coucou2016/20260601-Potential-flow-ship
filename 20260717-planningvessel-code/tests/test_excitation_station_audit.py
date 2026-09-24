import numpy as np

from scripts.audit_excitation_station_balance import origin_reference, response_density


def test_origin_transport_matches_distributed_load_integral():
    x = np.linspace(0, 2, 101)
    cg, shift, k = .7, .14, .8
    density = (1 + x) * np.exp(1j * k * (x-cg))
    force = np.array([np.trapezoid(density, x), np.trapezoid((x-cg)*density, x)])
    moved = density * np.exp(-1j*k*shift)
    expected = np.array([np.trapezoid(moved, x), np.trapezoid((x-cg-shift)*moved, x)])
    np.testing.assert_allclose(origin_reference(force, shift, k), expected, rtol=1e-13)


def test_response_density_converts_both_phase_and_pitch_sign():
    raw = np.array([[2+3j, 4-5j], [1-2j, 3+7j]])
    np.testing.assert_allclose(response_density(raw), raw * [1j, -1j])


def test_origin_transport_roundtrip():
    force = np.array([3+2j, 1-6j])
    np.testing.assert_allclose(origin_reference(origin_reference(force, .2, 1.4), -.2, 1.4), force)
