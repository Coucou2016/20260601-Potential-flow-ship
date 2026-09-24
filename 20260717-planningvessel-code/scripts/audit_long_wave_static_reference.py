"""Independent continuous waterplane limit versus the current calm-load derivative."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.integrate import quad
from planing_seakeeping.linear_case import load_linear_case
from planing_seakeeping.config import PrescribedRunningStateConfig
from planing_seakeeping.equilibrium import make_prescribed_equilibrium
from planing_seakeeping.planing_frequency_correction import build_planing_wetted_station_hull
from planing_seakeeping.quadrature import clipped_piecewise_linear_integral
from scripts.audit_prescribed_restoring import analytic_restoring


def run(config,out):
    raw,boat = load_linear_case(config)
    out.mkdir(parents=True,exist_ok=False)
    sources = [Path(__file__),config,Path('scripts/audit_prescribed_restoring.py'),
               *sorted(Path('planing_seakeeping').rglob('*.py'))]
    (out/'contract.json').write_text(json.dumps(dict(stations=[29,113,401],cutoff_beams=.5,
        scope='Continuous limiting waterplane integrals; not experimental validation',
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}),indent=2))
    rows = []
    for case in raw['cases']:
        eq = make_prescribed_equilibrium(boat,case['speed_mps'],PrescribedRunningStateConfig(
            enabled=True,trim_deg=case['trim_deg'],lambda_w=case['lambda_w']))
        length,transition = eq.geometry.keel_wetted_length_m,eq.geometry.x_s_m
        cutoff = .5*boat.beam_m
        def width(x):
            return boat.beam_m*min(1.,max(0.,(length-x)/transition))
        reference = boat.rho_water_kg_m3*boat.gravity_m_s2*np.array([
            quad(lambda x: width(x)*(x-boat.lcg_m)**i,cutoff,length,
                 points=[length-transition] if cutoff<length-transition<length else None,
                 epsabs=1e-12,epsrel=1e-12)[0] for i in range(2)])
        restoring = analytic_restoring(boat,eq)[:,0]
        for count in (29,113,401):
            hull = build_planing_wetted_station_hull(boat,eq,station_count=count)
            x = np.array([s.x_m for s in hull.stations])
            beam = np.array([s.waterplane_beam_m() for s in hull.stations])
            actual = boat.rho_water_kg_m3*boat.gravity_m_s2*clipped_piecewise_linear_integral(
                x,np.column_stack([beam,beam*(x-boat.lcg_m)]),cutoff)
            for i,mode in enumerate((3,5)):
                rows.append(dict(case=case['id'],stations=count,mode=mode,continuous_incident=reference[i],
                    discrete_incident=actual[i],calm_derivative=restoring[i],
                    discrete_minus_continuous=actual[i]-reference[i],
                    calm_minus_continuous=restoring[i]-reference[i]))
    frame = pd.DataFrame(rows)
    frame.to_csv(out/'static_limits.csv',index=False)
    print(frame.to_string(index=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    run(a.config,a.out)
