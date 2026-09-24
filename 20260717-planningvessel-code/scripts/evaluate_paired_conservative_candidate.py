"""Evaluate every predeclared paired variant, never select a winner."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scripts.evaluate_conservative_candidate import evaluate


def run(directory,frozen,out):
    source_contract=json.loads((directory/'contract.json').read_text())
    variants=('baseline','radiation_only','excitation_only','combined')
    if source_contract.get('paired_routes')!=list(variants):
        raise ValueError('Predeclared paired routes missing or mismatched')
    summary=json.loads((directory/'summary.json').read_text())
    if summary.get('computation_complete') is not True:
        raise ValueError('Solve must complete before experimental evaluation')
    out.mkdir(parents=True,exist_ok=False)
    metrics=[]
    for variant in variants:
        destination=out/variant
        evaluate(directory,frozen,destination,variant)
        frame=pd.read_csv(destination/'per_speed_metrics.csv')
        frame.insert(0,'variant',variant)
        metrics.append(frame)
    pd.concat(metrics,ignore_index=True).to_csv(out/'all_variants_metrics.csv',index=False)
    config=json.loads((frozen/'run.json').read_text())
    checks=[]
    for case in config['cases']:
        for index in range(8):
            with np.load(directory/f"{case['id']}_frequency{index}.npz") as d:
                delta=d['paired_combined']-d['paired_baseline']
                radiation=d['paired_radiation_increment']; excitation=d['paired_excitation_increment']
                residual=np.linalg.norm(delta-radiation-excitation)/max(
                    np.linalg.norm(delta)+np.linalg.norm(radiation)+np.linalg.norm(excitation),1e-15)
                if not np.isfinite(residual) or residual>1e-12:
                    raise ValueError('Complex response increment decomposition failed')
                checks.append(dict(case=case['id'],frequency_index=index,residual=residual))
    pd.DataFrame(checks).to_csv(out/'response_increment_identity.csv',index=False)
    (out/'summary.json').write_text(json.dumps(dict(stage_acceptance='NOT_PASSED',
        variants_evaluated=list(variants),cases_per_variant=24,selected_variant=None,
        max_increment_residual=max(r['residual'] for r in checks),
        source_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        limits_unchanged=True,reference_role='regression_not_blind_holdout'),indent=2))
    return 2


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('run','frozen','out'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    raise SystemExit(run(a.run,a.frozen,a.out))
