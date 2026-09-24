"""Manufactured counterexample for clipping after integration by parts."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from planing_seakeeping.planing_frequency_correction import apply_transom_sectional_force_cutoff


def counterexample(cutoff, length=2.):
    # phi=(L-x)*amplitude, N=1+x, phi(L)=0; the density -phi*N' is affine.
    amplitude = 1.+.5j
    x = np.linspace(0,length,41)
    density = np.zeros((1,len(x),2,2),complex)
    density[0,:,0,0] = -(length-x)*amplitude
    end = np.zeros((1,2,2),complex)
    end[0,0,0] = -length*amplitude
    _,_,legacy,_ = apply_transom_sectional_force_cutoff(station_x_m=x[None,:],
        force_density_by_station=density,end_force_matrices=end,end_station_x_m=np.array([0.]),
        cutoff_length_m=cutoff,cutoff_quadrature='clipped_linear')
    pressure_integral = -amplitude*((length-cutoff)+(length**2-cutoff**2)/2)
    new_edge = -amplitude*(length-cutoff)*(1+cutoff)
    return dict(cutoff=cutoff, pressure_integral=pressure_integral,
                clipped_transformed_integral=legacy[0,0,0], missing_edge=new_edge,
                corrected=legacy[0,0,0]+new_edge)


def run(out):
    out.mkdir(parents=True,exist_ok=False)
    sources=[Path(__file__),Path('planing_seakeeping/planing_frequency_correction.py'),
             Path('planing_seakeeping/quadrature.py')]
    contract=dict(length=2.,cutoffs=[.2,.37,.8],phi='(2-x)*(1+0.5j)',N='1+x',
        identity='int_a^L phi_x*N = [phi*N]_a^L - int_a^L phi*N_x',
        scope='Calculus counterexample, not validation of a replacement ship-load model',
        tolerance=1e-12,hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    (out/'contract.json').write_text(json.dumps(contract,indent=2))
    rows=[]
    for cutoff in contract['cutoffs']:
        data=counterexample(cutoff)
        rows.append(dict(cutoff=cutoff,
            legacy_absolute_error=abs(data['clipped_transformed_integral']-data['pressure_integral']),
            corrected_absolute_error=abs(data['corrected']-data['pressure_integral']),
            missing_edge_real=data['missing_edge'].real,missing_edge_imag=data['missing_edge'].imag))
    (out/'results.json').write_text(json.dumps(dict(rows=rows,
        identity_verified=all(r['corrected_absolute_error']<=1e-12 for r in rows),
        ship_correction_validated=False),indent=2))
    print(json.dumps(rows,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    run(p.parse_args().out)
