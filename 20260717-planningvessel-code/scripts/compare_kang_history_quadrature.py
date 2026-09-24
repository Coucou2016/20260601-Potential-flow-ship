"""Controlled spectral quadrature refinement; no physical acceptance decision."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def compare(runs,out,refinement='quadrature'):
    runs=list(map(Path,runs)); out=Path(out)
    contracts=[json.loads((p/'contract.json').read_text()) for p in runs]
    if refinement not in ('quadrature','cutoff'):
        raise ValueError('Explicit refinement type required')
    key='history_quadrature_count' if refinement=='quadrature' else 'history_k_max'
    expected=[64,128,256] if refinement=='quadrature' else [25.,50.,100.]
    if [c.get(key) for c in contracts] != expected:
        raise ValueError(f'Explicit ordered {expected} {refinement} contracts required')
    if refinement=='cutoff' and any(c.get('history_quadrature_count')!=512 for c in contracts):
        raise ValueError('Cutoff comparison requires 512 quadrature points throughout')
    fixed=[{k:v for k,v in c.items() if k not in ('hashes',key)} for c in contracts]
    if any(c!=fixed[0] for c in fixed[1:]):
        raise ValueError('Other input settings changed')
    if fixed[0].get('body_neumann_convention')!='fluid_domain_outward_diffraction_minus_incident':
        raise ValueError('Corrected normal convention required')
    fields=[]
    for directory in runs:
        with np.load(directory/'fields.npz') as data:
            fields.append({k:data[k].copy() for k in ('x_m','y','z_down','incident','diffraction','total')})
    for data in fields[1:]:
        for name in ('x_m','y','z_down','incident'):
            np.testing.assert_allclose(fields[0][name],data[name],rtol=1e-12,atol=1e-12)
    rows=[]
    for index in (0,1):
        for name in ('diffraction','total'):
            a,b=fields[index][name],fields[index+1][name]
            if not np.isfinite(a).all() or not np.isfinite(b).all():
                raise ValueError('Nonfinite load')
            rows.append(dict(coarse=contracts[index][key],
                fine=contracts[index+1][key],component=name,
                absolute_complex_change=abs(b-a).tolist(),
                relative_complex_change=(abs(b-a)/np.maximum(abs(b),1e-30)).tolist()))
    files=[p/name for p in runs for name in ('contract.json','fields.npz')]+[Path(__file__)]
    out.mkdir(parents=True,exist_ok=False)
    result=dict(stage_acceptance=False,rows=rows,modes=['heave','geometric_midship_pitch'],
        refinement=refinement,scope='Single-frequency spectral diagnostic; not full-band mesh validation',
        denominator='Fine complex modulus; absolute changes retained for near-zero inspection',
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
    (out/'comparison.json').write_text(json.dumps(result,indent=2)); print(json.dumps(rows,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runs',type=Path,nargs=3,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--refinement',choices=('quadrature','cutoff'),default='quadrature')
    args=p.parse_args(); compare(args.runs,args.out,args.refinement)
