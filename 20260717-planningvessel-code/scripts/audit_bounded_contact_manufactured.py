"""Compare actual bounded transfer against manufactured exposure, not ship physics."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scripts.audit_moving_free_surface_manufactured import simulate

POLICIES=('exact_exposure','bounded_nearest_unvalidated',
          'exact_exposure_bounded_edges','bounded_exposure_linear_edges',
          'linear_exposure_bounded_edges_unvalidated','linear_all_unvalidated')


def run(out):
    out=Path(out); out.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[1]
    paths=[Path(__file__),root/'scripts/audit_moving_free_surface_manufactured.py',
        *[root/'planing_seakeeping/kernels/linear_2p5d'/name for name in
          ('free_surface_transfer.py','implicit_free_surface.py','anchored_free_surface.py')]]
    (out/'contract.json').write_text(json.dumps(dict(stage_acceptance=False,
        policies=POLICIES,refinements=[1,2,4,8],
        reference='Analytic Fourier free-surface oscillator; q=k*phi is prescribed diagonal operator',
        scope='Migration and time-integration consistency, not physical contact BEM validation',
        acceptance='Retain existing manufactured maximum weighted error limit 0.01; no ship threshold replaced',
        manufactured_maximum_weighted_error_limit=.01,
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}),indent=2))
    rows=[]
    for policy in POLICIES:
        for level in (1,2,4,8):
            result=simulate(level,policy)
            frame=pd.DataFrame(result['rows'])
            frame.to_csv(out/f'{policy}_{level}.csv',index=False)
            np.savez_compressed(out/f'{policy}_{level}.npz',y=result['final_y'],
                values=result['final_values'],reference=result['final_exact'])
            rows.append(dict(policy=policy,level=level,
                final_weighted_error=float(frame.relative_phi_eta_error.iloc[-1]),
                maximum_weighted_error=float(frame.relative_phi_eta_error.max()),
                maximum_scaled_point_error=float(frame.maximum_scaled_point_error.max()),
                exposure_visits=int(frame.newly_exposed.sum()),
                algebra_residual=result['maximum_equation_error']))
    pd.DataFrame(rows).to_csv(out/'comparison.csv',index=False)
    decisions={policy:bool(next(r for r in rows if r['policy']==policy and r['level']==8)
                          ['maximum_weighted_error']<.01)
               for policy in POLICIES}
    (out/'summary.json').write_text(json.dumps(dict(stage_acceptance=False,
        physical_contact_validated=False,manufactured_error_limit_pass=decisions,rows=rows),indent=2))
    print(pd.DataFrame(rows).to_string(index=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--out',type=Path,required=True)
    run(p.parse_args().out)
