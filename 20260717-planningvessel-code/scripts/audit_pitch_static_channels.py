"""Separate pitch body-condition channels without changing the physical default."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from planing_seakeeping.linear_case import load_linear_case
from planing_seakeeping.config import PrescribedRunningStateConfig
from planing_seakeeping.equilibrium import make_prescribed_equilibrium
from planing_seakeeping.schema import Linear2p5DProviderConfig
from planing_seakeeping.planing_frequency_correction import build_planing_wetted_station_hull, matched_bie_matrix_to_bow_up
from planing_seakeeping.kernels.linear_2p5d.formulation import solve_station_hull_heave_pitch_matched_sweep
from planing_seakeeping.kernels.linear_2p5d.panel_integrals import panel_integration_route


def run(config,out):
    raw,boat = load_linear_case(config)
    if boat.gravity_m_s2 != 9.80665:
        raise ValueError('Diagnostic sweep currently uses fixed gravity 9.80665')
    out.mkdir(parents=True,exist_ok=False)
    sources = [Path(__file__),config,*sorted(Path('planing_seakeeping').rglob('*.py'))]
    (out/'contract.json').write_text(json.dumps(dict(omega=[.02,.01],stations=29,body=36,free=36,control=48,
        channels={'total':[1.,1.],'oscillatory':[1.,0.],'forward':[0.,1.]},
        scope='Full wetted contour and physical end term, no 0.5B cutoff; source attribution only',
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}),indent=2))
    provider = Linear2p5DProviderConfig(formulation='matched_bie',hull_stations=29,
        body_panels_per_section=36,free_surface_inner_panels=36,free_surface_outer_panels=48,
        control_surface_radius_beams=3.,include_steady_perturbation=False,include_end_terms=True)
    rows = []
    with panel_integration_route('reconstructed_symmetric'):
        for case in raw['cases']:
            eq = make_prescribed_equilibrium(boat,case['speed_mps'],PrescribedRunningStateConfig(
                enabled=True,trim_deg=case['trim_deg'],lambda_w=case['lambda_w']))
            hull = build_planing_wetted_station_hull(boat,eq,station_count=29)
            for omega in (.02,.01):
                forces = {}
                for name,(osc,forward) in {'total':(1.,1.),'oscillatory':(1.,0.),'forward':(0.,1.)}.items():
                    sweep = solve_station_hull_heave_pitch_matched_sweep(hull,omega,case['speed_mps'],
                        config=provider,rho_water_kg_m3=boat.rho_water_kg_m3,
                        parametric_section_shape='hard_chine_v',history_steps=64,history_quadrature_count=48,
                        history_k_max=25.,waterline_grading_exponent=1.5,
                        pitch_oscillation_scale=osc,pitch_forward_speed_scale=forward)
                    forces[name] = matched_bie_matrix_to_bow_up(sweep.pressure_force_sweep.assembly.complex_force_matrix)[:,1]
                residual = np.linalg.norm(forces['total']-forces['oscillatory']-forces['forward'])/max(np.linalg.norm(forces['total']),1e-12)
                for i,mode in enumerate((3,5)):
                    row = dict(case=case['id'],omega=omega,mode=mode,superposition_relative_residual=residual)
                    for name,value in forces.items():
                        row[name+'_real'],row[name+'_imag'] = value[i].real,value[i].imag
                    rows.append(row)
            pd.DataFrame(rows).to_csv(out/'channels.csv',index=False)
            print(case['id']+' complete',flush=True)
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    run(a.config,a.out)
