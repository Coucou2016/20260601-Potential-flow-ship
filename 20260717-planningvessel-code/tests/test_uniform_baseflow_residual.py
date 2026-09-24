import numpy as np
import pytest
from scripts.audit_uniform_baseflow_residual import graph_metrics


@pytest.mark.parametrize('slope', [0., .1, -.2])
def test_sloping_v_with_moving_panel_coordinates(slope):
    x = np.linspace(0, 2, 11)
    y = (1+.2*x[:, None])*np.array([.9,.5,.1,-.1,-.5,-.9])
    z = .5+slope*x[:, None]-.3*abs(y)
    result = graph_metrics(x, y, z, 4.)
    np.testing.assert_allclose(result['fx'], slope, atol=1e-14)
    np.testing.assert_allclose(result['normal_velocity'], 4*slope/np.sqrt(1+slope**2+.3**2), atol=1e-13)
    np.testing.assert_allclose(result['required_transverse_normal_velocity'], -4*slope/np.sqrt(1+.3**2), atol=1e-13)


def test_invalid_stations_rejected():
    with pytest.raises(ValueError):
        graph_metrics(np.array([0,0,1]), np.ones((3,6)), np.ones((3,6)), 3.)
