"""Manufactured convolution checks: actual start versus retained-memory endpoint."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from planing_seakeeping.kernels.linear_2p5d.formulation import TransientFreeSurfaceHistory
from planing_seakeeping.types import ValidityReport


def evaluate(n, zero_initial):
    dt=1./n
    lag=dt*np.arange(1,2*n+1)
    kernel=TransientFreeSurfaceHistory(lag_s=lag,green_potential=np.zeros((2*n,1,1)),
        green_normal_derivative=lag[:,None,None],dt_s=dt,quadrature_count=16,k_max=1.,
        validity=ValidityReport(status='manufactured',reference_cases=(),notes=()))
    phi=np.zeros((2*n,1),complex)
    phi[:n,0]=1-lag[:n] if zero_initial else 1.
    original=kernel.convolution_rhs(phi,np.zeros_like(phi))[0].real
    # The current endpoint has zero kernel. Only the actual initial-time endpoint
    # differs when the retained buffer extends into the zero-filled prehistory.
    corrected=original-.5*dt*lag[n-1]*phi[n-1,0].real
    exact=1/6 if zero_initial else .5
    return dict(n=n,zero_initial=zero_initial,exact=exact,original=original,corrected=corrected,
        original_error=abs(original-exact),corrected_error=abs(corrected-exact))


def run(out):
    out.mkdir(parents=True,exist_ok=False)
    rows=[evaluate(n,zero) for zero in (False,True) for n in (8,16,32)]
    sources=[Path(__file__),Path(__file__).resolve().parents[1]/'planing_seakeeping/kernels/linear_2p5d/formulation.py']
    (out/'results.json').write_text(json.dumps(dict(stage_acceptance=False,rows=rows,
        exact_problem='Integral_0^1 (1-t)*phi(t) dt; memory length 2; phi=1 or t on [0,1], zero before start',
        scope='Manufactured temporal quadrature, not a physical Green-function solution',
        production_changed=False,hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}),indent=2))
    print(json.dumps(rows,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    run(p.parse_args().out)
