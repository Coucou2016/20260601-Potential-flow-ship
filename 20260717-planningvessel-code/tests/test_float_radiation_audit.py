from pathlib import Path
import numpy as np
import pytest
import planing_seakeeping.section_bem as bem
from planing_seakeeping.float_radiation_audit import wetted_section
from planing_seakeeping.seaplane_workflow import load_workflow,FloatHydrostatics,build_model
from planing_seakeeping.float_offsets import read_float_offsets


@pytest.mark.parametrize("with_centre", [True, False])
def test_flat_bottom_half_preserves_geometry(with_centre):
    y = [1., 1., .5, 0., -.5, -1., -1.] if with_centre else [1., 1., .5, -.5, -1., -1.]
    z = [0.] + [.3] * (len(y)-2) + [0.]
    half = bem._pdstrip_half_section(bem.SectionOffsets(np.array(y), np.array(z)))
    assert half.y_m[0] == 0.
    assert half.z_down_m[0] == .3
    assert np.all(half.y_m <= 0.)
    assert np.all(np.diff(half.y_m) <= 0.)
    assert -np.trapezoid(half.z_down_m, half.y_m) == pytest.approx(.3)


def test_strict_keeps_signs(monkeypatch):
    monkeypatch.setattr(bem,"_solve_heave_radiation_pdstrip_near_count",lambda *a,**k:(-3+2j,10.,1e-12,12,16))
    offsets=bem.SectionOffsets(np.array([1.,0.,-1.]),np.array([0.,1.,0.]))
    raw=bem.solve_heave_radiation_pdstrip_style(offsets,2.,strict=True)
    assert raw.added_mass_per_m==-3
    assert raw.damping_per_m==-4
    legacy=bem.solve_heave_radiation_pdstrip_style(offsets,2.)
    assert legacy.added_mass_per_m==3
    assert legacy.damping_per_m==4


def test_actual_float_clipping():
    root=Path(__file__).resolve().parents[1]
    raw,base,path=load_workflow(root/"configs/edo106k_workflow.json")
    model=build_model(FloatHydrostatics(read_float_offsets(path),2),base,raw)
    wet=0
    for i in range(len(model["hydro"].x)):
        s=wetted_section(model,i)
        if s is None:
            continue
        wet+=1
        assert abs(s.z_down_m[0])<1e-12 and abs(s.z_down_m[-1])<1e-12
        assert np.all(s.z_down_m>=-1e-12)
        assert np.min(np.hypot(np.diff(s.y_m),np.diff(s.z_down_m)))>0
        assert s.beam_m==pytest.approx(model["static"]["width"][i],abs=1e-10)
    assert wet>10


@pytest.mark.parametrize("omega",[0,-1,float("nan"),float("inf")])
def test_strict_rejects_frequency(omega):
    s=bem.SectionOffsets(np.array([1.,0.,-1.]),np.array([0.,1.,0.]))
    with pytest.raises(ValueError):
        bem.solve_heave_radiation_pdstrip_style(s,omega,strict=True)


def test_strict_singular_system_never_falls_back(monkeypatch):
    def singular(*args, **kwargs):
        raise np.linalg.LinAlgError("synthetic singular system")

    def forbidden(*args, **kwargs):
        pytest.fail("Strict mode must not silently call least squares")

    monkeypatch.setattr(np.linalg, "solve", singular)
    monkeypatch.setattr(np.linalg, "lstsq", forbidden)
    s = bem.SectionOffsets(np.array([1., 0., -1.]), np.array([0., 1., 0.]))
    with pytest.raises(np.linalg.LinAlgError, match="synthetic singular"):
        bem.solve_heave_radiation_pdstrip_style(s, 2., strict=True)


@pytest.mark.parametrize("period,a_reference,b_reference", [
    (1.6, 295.6835836481728, 1384.7784491617335),
    (8.0, 1038.1828181880528, 690.338004831566),
])
def test_raw_port_matches_original_fortran_reference(period, a_reference, b_reference):
    # Original routines, 64-bit build, frozen before the port correction:
    # outputs/pdstrip_port_verification_20260918/contract.json and comparison.json.
    section = bem.SectionOffsets(np.array([.5, 0., -.5]), np.array([0., .3, 0.]))
    omega = 2 * np.pi / period
    values = [bem._solve_heave_radiation_pdstrip_near_count(
        section, omega, 1025., 9.80665, 64, 48, near, strict=True)[0]
        for near in (25, 28)]
    value = np.mean(values)
    assert value.real == pytest.approx(a_reference, rel=1e-8)
    assert -omega * value.imag == pytest.approx(b_reference, rel=1e-8)
