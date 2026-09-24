"""Summarize verified full-frequency checks without promoting numerical to physical acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd


def summarize(directory,out):
    directory,out=Path(directory),Path(out)
    report=json.loads((directory/'verification.json').read_text())
    if not all(report.get(k) is True for k in ('coverage_and_arithmetic_verified',
            'source_hashes_verified','original_24_case_input_verified')):
        raise ValueError('Verified original full-case scope required')
    frame=pd.read_csv(directory/'recomputed_checks.csv',float_precision='round_trip')
    if len(frame)!=240 or report.get('fine_checks')!=240 or report.get('records')!=720:
        raise ValueError('Expected 720 records and 240 fine-grid checks')
    if not np.isfinite(frame[['absolute_change','tolerance']]).all().all() or (frame.tolerance<=0).any():
        raise ValueError('Finite errors and positive tolerances required')
    frame['error_to_limit']=frame.absolute_change/frame.tolerance
    frame['near_zero_absolute_rule']=abs(frame.real_fine+1j*frame.imag_fine)<.02
    frame['recomputed_pass']=frame.absolute_change<=frame.tolerance
    if not np.array_equal(frame.recomputed_pass,frame.passed):
        raise ValueError('Stored decision mismatch')
    summary=frame.groupby(['case','component']).agg(checks=('passed','size'),
        passed=('passed','sum'),maximum_error_to_limit=('error_to_limit','max'),
        near_zero_checks=('near_zero_absolute_rule','sum')).reset_index()
    failures=frame[~frame.recomputed_pass].sort_values('error_to_limit',ascending=False)
    out.mkdir(parents=True,exist_ok=False)
    summary.to_csv(out/'component_summary.csv',index=False)
    failures.to_csv(out/'failed_frequency_components.csv',index=False)
    files=[directory/'verification.json',directory/'recomputed_checks.csv',Path(__file__)]
    (out/'summary.json').write_text(json.dumps(dict(stage_acceptance=False,
        numerical_checks=len(frame),numerical_passed=int(frame.recomputed_pass.sum()),
        failed_checks=len(failures),scope='24 specified input frequencies, not a continuous-frequency proof',
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}),indent=2))
    print(summary.to_string(index=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--verified',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args(); summarize(args.verified,args.out)
