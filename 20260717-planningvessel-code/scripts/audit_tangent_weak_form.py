"""Same-potential weak-form diagnostic; no production substitution or fitting."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from planing_seakeeping.linear_case import load_linear_case
from planing_seakeeping.quadrature import clipped_piecewise_linear_integral
from planing_seakeeping.kernels.linear_2p5d.formulation import DEFAULT_A1_HEAVE_PITCH_CONVENTION
from scripts.audit_eulerian_diffraction_grid import compare


def weak_integral(length, phi, weight, endpoint_order):
    """Integral phi_s*w ds by parts, for affine w on one straight leg."""
    length,phi,weight=np.asarray(length),np.asarray(phi),np.asarray(weight)
    if endpoint_order not in (1,2) or len(length)<endpoint_order+1:
        raise ValueError("Need two or three samples for specified endpoint order")
    s=np.cumsum(length)-length/2
    slope,intercept=np.polyfit(s,weight,1)
    if not np.allclose(slope*s+intercept,weight,rtol=1e-8,atol=1e-10):
        raise ValueError("Weak diagnostic requires affine geometric weight")
    n=endpoint_order+1
    lo=np.polyval(np.polyfit(s[:n],phi[:n],endpoint_order),0)
    hi=np.polyval(np.polyfit(s[-n:]-length.sum(),phi[-n:],endpoint_order),0)
    integral=np.trapezoid(np.r_[lo,phi,hi],np.r_[0,s,length.sum()])
    boundary=hi*(slope*length.sum()+intercept)-lo*intercept
    return boundary-slope*integral


def run(config, mid, fine, out):
    raw,boat=load_linear_case(config)
    out.mkdir(parents=True,exist_ok=False)
    files=[config,Path(__file__)]
    for folder in (mid,fine):
        files.extend(folder.glob("boundary_*.npz"))
        files.append(folder/"force_changes.csv")
    (out/"contract.json").write_text(json.dumps(dict(endpoint_orders=[1,2],
        source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        scope="same solved phi; full wet contour including extrapolated end terms; diagnostic only",
        comparison="existing 5%/near-zero 0.001 dimensionless limits"),indent=2))
    rows=[]
    for level,folder in (("mid",mid),("fine",fine)):
        saved=pd.read_csv(folder/"force_changes.csv")
        for case in raw["cases"]:
            with np.load(folder/f"boundary_{case['id']}.npz") as d:
                dx_y=np.gradient(d["y"],d["x"],axis=0,edge_order=2)
                dx_z=np.gradient(d["z"],d["x"],axis=0,edge_order=2)
                ty=np.diff(d["node_y"],axis=1)/d["length"]
                tz=np.diff(d["node_z"],axis=1)/d["length"]
                weight=DEFAULT_A1_HEAVE_PITCH_CONVENTION.heave_row_per_length(d["normal_z"])*(ty*dx_y+tz*dx_z)
                n=d["phi"].shape[1]
                for order in (1,2):
                    density=[]
                    for i,x in enumerate(d["x"]):
                        value=sum(weak_integral(d["length"][i,a:b],d["phi"][i,a:b],weight[i,a:b],order)
                            for a,b in ((0,n//2),(n//2,n)))
                        heave=-boat.rho_water_kg_m3*case["speed_mps"]*value
                        density.append([heave,heave*(boat.lcg_m-x)])
                    force=clipped_piecewise_linear_integral(d["x"],np.asarray(density),.5*boat.beam_m)*np.array([1j,-1j])
                    for j,mode in enumerate((3,5)):
                        r=saved[(saved.case==case["id"])&(saved['mode']==mode)].iloc[0]
                        delta=force[j]+complex(r.normal_real,r.normal_imag)
                        rows.append(dict(level=level,case=case["id"],mode=mode,order=order,
                            delta_real=delta.real,delta_imag=delta.imag,
                            difference_from_pointwise=abs(force[j]-complex(r.tangent_real,r.tangent_imag))))
    frame=pd.DataFrame(rows)
    frame.to_csv(out/"weak_forces.csv",index=False)
    pairs=frame[frame.level=="mid"].merge(frame[frame.level=="fine"],on=["case","mode","order"],suffixes=("_mid","_fine"),validate="one_to_one")
    checks=[]
    for r in pairs.itertuples():
        scale=boat.rho_water_kg_m3*boat.gravity_m_s2*boat.length_m*boat.beam_m*(boat.length_m if r.mode==5 else 1)
        err,tol,passed=compare(complex(r.delta_real_mid,r.delta_imag_mid),complex(r.delta_real_fine,r.delta_imag_fine),scale)
        checks.append(dict(case=r.case,mode=r.mode,order=r.order,error=err,tolerance=tol,passed=passed))
    check=pd.DataFrame(checks)
    check.to_csv(out/"grid_checks.csv",index=False)
    print(check.to_string(index=False))
    (out/"summary.json").write_text(json.dumps(dict(checks=len(check),passed=int(check.passed.sum()),physical_acceptance="NOT_PASSED")))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("config","mid","fine","out"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    run(a.config,a.mid,a.fine,a.out)
