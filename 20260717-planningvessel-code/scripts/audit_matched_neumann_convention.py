"""Independent harmonic-field audit of the inner system's body Neumann convention."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from scripts.kang_reference_geometry import build_hull
from planing_seakeeping.kernels.linear_2p5d import formulation as f
from planing_seakeeping.kernels.linear_2p5d.anchored_free_surface import build_anchored_free_surface
from planing_seakeeping.kernels.linear_2p5d.panel_integrals import panel_integration_route


def check(body_count=64,control_count=96):
    hull=build_hull(5,161,moment_reference_x=1.5)
    body=f.build_inner_domain_panel_geometry(hull.stations[2].section_offsets(),body_panel_count=body_count)
    free=build_anchored_free_surface(.9,.15,.15,20,44)
    control=f.build_control_surface_geometry(radius_m=.9,panel_count=control_count)
    history=f.build_transient_free_surface_history(control,.01,1,quadrature_count=32,k_max=25.)
    # phi=z_down is harmonic. Known control values close the *inner* problem;
    # this does not claim the growing field satisfies the outer radiation condition.
    known_control=np.r_[control.mid_z_down_m,control.normal_z]
    expected=np.r_[body.mid_z_down_m,-np.ones(free.panel_count)]
    n=body_count+free.panel_count
    results=[]
    for label,sign in (('fluid_domain_outward',-1.),('hull_outward',1.)):
        data=f.MatchedSectionBoundaryData(body=body,inner_free_surface=free,control=control,
            history=history,body_normal_velocity=sign*body.normal_z,
            free_surface_potential=np.zeros(free.panel_count),
            past_control_potential=np.zeros((1,control_count)),past_control_normal_derivative=np.zeros((1,control_count)))
        with panel_integration_route('analytic_straight_midpoint_curved'):
            system=f.assemble_matched_section_system(data)
        rhs=system.rhs[:n]-system.matrix[:n,n:]@known_control
        solution=np.linalg.solve(system.matrix[:n,:n],rhs)
        residual=np.linalg.norm(system.matrix[:n,:n]@solution-rhs)/np.linalg.norm(rhs)
        results.append(dict(convention=label,body_panels=body_count,control_panels=control_count,
            body_potential_relative_error=float(np.linalg.norm(solution[:body_count]-expected[:body_count])/np.linalg.norm(expected[:body_count])),
            free_normal_relative_error=float(np.linalg.norm(solution[body_count:]-expected[body_count:])/np.linalg.norm(expected[body_count:])),
            algebra_residual=float(residual)))
    return results


def run(out):
    out.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[1]
    paths=[Path(__file__),root/'scripts/kang_reference_geometry.py',
           *sorted((root/'planing_seakeeping/kernels/linear_2p5d').glob('*.py'))]
    (out/'contract.json').write_text(json.dumps(dict(stage_acceptance=False,
        reference='Exact phi=z_down harmonic field with prescribed control Cauchy data',
        independent_of_experiment=True,body_panels=[64,128],control_panels=[96,192],
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}),indent=2))
    rows=check()+check(128,192)
    (out/'results.json').write_text(json.dumps(dict(stage_acceptance=False,rows=rows),indent=2))
    print(json.dumps(rows,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    run(parser.parse_args().out)
