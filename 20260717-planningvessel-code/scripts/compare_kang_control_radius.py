"""Compare explicit corrected-Neumann radius probes; never grant stage acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def compare(base, expanded, out):
    base, expanded, out = map(Path, (base, expanded, out))
    contracts=[json.loads((p/'contract.json').read_text()) for p in (base,expanded)]
    allowed={'radius_beams','control_panels','outer_panels_per_side','hashes'}
    if {k:v for k,v in contracts[0].items() if k not in allowed} != {
            k:v for k,v in contracts[1].items() if k not in allowed}:
        raise ValueError('Non-domain settings differ')
    if contracts[0].get('body_neumann_convention') != 'fluid_domain_outward_diffraction_minus_incident':
        raise ValueError('Corrected Neumann inputs required')
    results={}
    with np.load(base/'fields.npz') as a,np.load(expanded/'fields.npz') as b:
        for name in ('x_m','y','z_down','normal_y','normal_z','length','incident'):
            np.testing.assert_allclose(a[name],b[name],rtol=1e-12,atol=1e-12)
        for name in ('diffraction','total'):
            av,bv=a[name],b[name]
            if not np.isfinite(av).all() or not np.isfinite(bv).all():
                raise ValueError('Nonfinite load')
            results[name]=dict(base_real=av.real.tolist(),base_imag=av.imag.tolist(),
                expanded_real=bv.real.tolist(),expanded_imag=bv.imag.tolist(),
                absolute_complex_change=abs(bv-av).tolist(),
                relative_complex_change=(abs(bv-av)/np.maximum(abs(av),1e-30)).tolist())
    dimensions=[dict(radius_m=.3*c['radius_beams'],control_panels=c['control_panels'],
        mean_control_arc_spacing_m=np.pi*.3*c['radius_beams']/c['control_panels'],
        outer_free_spacing_m=(.3*c['radius_beams']-.15)/c['outer_panels_per_side']) for c in contracts]
    paths=[p/name for p in (base,expanded) for name in ('contract.json','fields.npz')]+[Path(__file__)]
    out.mkdir(parents=True,exist_ok=False)
    result=dict(stage_acceptance=False,scope='Single-frequency domain sensitivity, not full convergence',
        normalization='Relative differences use base complex modulus, not amplitude difference',
        near_zero_warning='No acceptance decision; inspect absolute differences near zero',
        dimensions=dimensions,modes=['heave','geometric_midship_pitch'],results=results,
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    (out/'comparison.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',type=Path,required=True)
    p.add_argument('--expanded',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args(); compare(args.base,args.expanded,args.out)
