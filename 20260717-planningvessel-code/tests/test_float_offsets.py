from pathlib import Path
import numpy as np
import pytest
from planing_seakeeping.float_offsets import read_float_offsets, bottom_mesh, assemble_float_layout

SOURCE = Path(__file__).resolve().parents[1]/"benchmarks/seaplane_edo/106k_offsets_inches.csv"


def test_real_dimensions_and_steps():
    stations = read_float_offsets(SOURCE)
    assert len(stations) == 24
    assert stations[-1].x_aft_m == pytest.approx(8.509)
    assert max(s.halfbreadth_m[-1] for s in stations)*2 == pytest.approx(1.143)
    assert stations[10].halfbreadth_m[-1] == pytest.approx(22.30*.0254)
    assert stations[14].x_aft_m == stations[15].x_aft_m
    assert stations[15].height_up_m[0]-stations[14].height_up_m[0] == pytest.approx(3.75*.0254)


def test_mesh_does_not_smooth_over_steps():
    stations = read_float_offsets(SOURCE)
    vertices, faces = bottom_mesh(stations)
    assert np.isfinite(vertices).all()
    assert len(faces) > 0
    for i in (14,21):
        for f in faces:
            assert not (i in f//17 and i+1 in f//17)
    assert np.all(np.linalg.norm(np.cross(vertices[faces[:,1]]-vertices[faces[:,0]],
                                        vertices[faces[:,2]]-vertices[faces[:,0]]),axis=1)>0)


def test_bad_transverse_count():
    with pytest.raises(ValueError):
        bottom_mesh(read_float_offsets(SOURCE), 4)


@pytest.mark.parametrize("count", [2, 3])
def test_multibody_layout(count):
    s = read_float_offsets(SOURCE)
    v, f = bottom_mesh(s)
    vv, ff, ids = assemble_float_layout(s, [[0, 2*i, 0] for i in range(count)])
    assert len(vv) == count*len(v)
    assert len(ff) == count*len(f)
    assert set(ids) == set(range(count))
    np.testing.assert_allclose(vv[len(v):2*len(v)]-v, np.tile([0,2,0], (len(v),1)))


def test_overlapping_layout_rejected():
    with pytest.raises(ValueError, match="Overlapping"):
        assemble_float_layout(read_float_offsets(SOURCE), [[0,0,0], [0,.1,0]])
