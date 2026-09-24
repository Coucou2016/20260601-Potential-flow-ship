"""Check A1 pressure against its Eq7-8 local-time transformation, not printed Eq30 RHS."""
from types import SimpleNamespace

import numpy as np
import pytest

from planing_seakeeping.kernels.linear_2p5d.formulation import (
    build_inner_domain_panel_geometry, recover_body_pressure_from_matched_solution,
)
from planing_seakeeping.section_bem import SectionOffsets


@pytest.mark.parametrize('speed', [1.3, 4.7])
@pytest.mark.parametrize('omega', [2., 7., 11.])
def test_pressure_matches_independent_local_time_difference(speed, omega):
    y = np.linspace(-1., 1., 17)
    body = build_inner_domain_panel_geometry(SectionOffsets(y, .3*np.abs(y)))
    x0, tau, rho = 3., .19, 1000.
    x = x0-speed*tau
    transverse = body.mid_y_m+1j*body.mid_z_down_m

    def phi(position):
        return (1+.4j)*position**2+(.3-.2j)*position+transverse

    gradient = 2*(1+.4j)*x+(.3-.2j)
    pressure = recover_body_pressure_from_matched_solution(
        body, SimpleNamespace(body_potential=phi(x)), omega,
        rho_water_kg_m3=rho, forward_speed_mps=speed,
        body_potential_x_gradient=np.full(body.panel_count, gradient)).pressure_pa

    def psi(local_time):
        return phi(x0-speed*local_time)*np.exp(1j*omega*local_time)

    step = 1e-5
    derivative = (psi(tau+step)-psi(tau-step))/(2*step)
    independent = -rho*np.exp(-1j*omega*tau)*derivative
    np.testing.assert_allclose(pressure, independent, rtol=1e-8, atol=1e-5)
