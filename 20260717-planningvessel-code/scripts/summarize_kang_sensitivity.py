"""Summarize saved Kang diagnostic runs without fitting or physics pass claims."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd


def run(out):
    root = Path(__file__).resolve().parents[1]/'outputs'
    names = dict(baseline='kang_heave_excitation_diagnostic_20260924',
        medium='kang_heave_medium_20260924', fine='kang_heave_fine_20260924',
        history='kang_heave_history_only_20260924', endpoint='kang_heave_endpoint_only_20260924')
    data, hashes = {}, {}
    for label, name in names.items():
        directory = root/name
        for filename in ('contract.json','computed.csv','comparison.csv'):
            p=directory/filename
            hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
        data[label]=pd.read_csv(directory/'computed.csv').set_index('omega_e_sqrt_L_g')
        if set(data[label].index)!={2.,3.,4.} or len(data[label])!=3:
            raise ValueError('Incomplete frequency coverage')
    rows=[]
    for frequency in (2.,3.,4.):
        row=dict(frequency=frequency)
        for label in names:
            row[label+'_amplitude']=float(data[label].loc[frequency,'amplitude'])
        row['fine_medium_amplitude_change']=abs(row['fine_amplitude']/row['medium_amplitude']-1)
        for label in ('history','endpoint'):
            row[label+'_baseline_amplitude_change']=abs(row[label+'_amplitude']/row['baseline_amplitude']-1)
        for component in ('incident','diffraction','total'):
            values=[]
            for label in ('medium','fine'):
                path=root/names[label]/f'fields_{frequency:g}.npz'
                hashes[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
                with np.load(path,allow_pickle=False) as fields:
                    values.append(complex(fields[component][0]))
            row[component+'_fine_medium_complex_change']=abs(values[1]-values[0])/abs(values[1])
        rows.append(row)
    out.mkdir(parents=True,exist_ok=False)
    pd.DataFrame(rows).to_csv(out/'sensitivity.csv',index=False)
    (out/'summary.json').write_text(json.dumps(dict(stage_acceptance=False,
        scope='Three diagnostic heave points only, not full-band complex validation',
        source_hashes=hashes, rows=rows),indent=2))
    print(pd.DataFrame(rows).to_string(index=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    run(p.parse_args().out)
