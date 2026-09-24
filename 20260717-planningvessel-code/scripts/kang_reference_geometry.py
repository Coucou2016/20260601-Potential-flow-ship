"""Source-defined Kang Eq. 7.65 offsets; no response or mass fitting."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from planing_seakeeping.station_2p5d import HardChineStation, StationHull


def half_breadth(x, depth, length, beam, draft):
    X, Z = 2*np.asarray(x)/length-1, np.asarray(depth)/draft
    return beam/2*((1-Z**2)*(1-X**2)*(1+.2*X**2) + Z**2*(1-Z**8)*(1-X**2)**4)


def build_hull(stations, points_per_side, *, length=3., beam=.3, draft=.1875,
               moment_reference_x=None, endpoint_fraction=1e-6):
    if not np.isfinite([length, beam, draft, endpoint_fraction]).all() or min(length, beam, draft) <= 0:
        raise ValueError('Finite positive dimensions required')
    if not 0 < endpoint_fraction < .01:
        raise ValueError('Endpoint exclusion must be explicit and small')
    if not isinstance(stations, int) or not isinstance(points_per_side, int) or min(stations, points_per_side) < 5:
        raise ValueError('At least five stations and points per side required')
    if moment_reference_x is None or not np.isfinite(moment_reference_x):
        raise ValueError('Explicit moment reference required; do not assume experimental CG')
    result = []
    z = np.linspace(0., draft, points_per_side)
    for x in np.linspace(length*endpoint_fraction, length*(1-endpoint_fraction), stations):
        y = half_breadth(x, z, length, beam, draft)
        # Package contour is starboard waterline -> keel -> port waterline.
        points = tuple(zip(np.r_[y, -y[-2::-1]], np.r_[z, z[-2::-1]]))
        result.append(HardChineStation(x_m=float(x), beam_m=float(2*y[0]),
            draft_m=draft, deadrise_deg=0., waterplane_beam_override_m=float(2*y[0]),
            offset_points_m=points))
    return StationHull(length_m=length, stations=tuple(result), lcg_from_transom_m=moment_reference_x)


def run(out):
    root = Path(__file__).resolve().parents[1]
    source = root/'benchmarks/excitation_reference_candidates_20260924/sources/Kang2009.pdf'
    expected = '82c16b2b268679b86dfb0b6ec1fc4e7e24dd4e7e5dd517d3596fdc63eecc29e5'
    if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
        raise ValueError('Source hash mismatch')
    out.mkdir(parents=True, exist_ok=False)
    exact_volume = (29144/51975)*3*.3*.1875
    exact_waterplane = 3*.3*52/75
    rows = []
    for n, m in ((41, 41), (81, 81), (161, 161)):
        hull = build_hull(n, m, moment_reference_x=1.5)
        hydro = hull.hydrostatics()
        payload = dict(length_m=3., coordinate='x forward from aft end; y starboard; z down',
            geometric_moment_reference_x_m=1.5, experimental_cg_verified=False,
            source_equation='Kang 2009 Eq 7.65, scaled uniformly 1/40 from Table 7.2',
            endpoint_fraction=1e-6,
            stations=[dict(x_m=s.x_m, beam_m=s.beam_m, draft_m=s.draft_m,
                offsets_m=s.offset_points_m) for s in hull.stations])
        (out/f'geometry_{n}.json').write_text(json.dumps(payload, indent=2))
        rows.append(dict(stations=n, points_per_side=m,
            volume_m3=hydro.displacement_volume_m3,
            volume_relative_error=abs(hydro.displacement_volume_m3/exact_volume-1),
            waterplane_m2=hydro.waterplane_area_m2,
            waterplane_relative_error=abs(hydro.waterplane_area_m2/exact_waterplane-1),
            buoyancy_x_m=hydro.center_of_buoyancy_x_m))
    summary = dict(source_sha256=expected, script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        status='GEOMETRY_ONLY_NOT_HYDRODYNAMIC_ACCEPTANCE', exact_volume_m3=exact_volume,
        exact_waterplane_m2=exact_waterplane, rows=rows,
        contour='Open wetted body contour; closure at waterline only for area integration',
        limitations=['Finite tip exclusion and polygon discretization', 'No experimental CG or phase assumed'])
    (out/'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    run(p.parse_args().out)
