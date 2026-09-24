"""Frozen three-grid checks of candidate diffraction geometry correction."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scripts.probe_eulerian_diffraction import run as probe, REFINED_GRIDS
from planing_seakeeping.linear_case import load_linear_case


def compare(mid, fine, scale):
    change=abs(mid-fine)
    tolerance=.001 if abs(fine/scale)<.02 else .05*abs(fine/scale)
    return change/scale,tolerance,bool(np.isfinite(change) and change/scale <= tolerance)


def run(config, out):
    raw,boat=load_linear_case(config)
    out.mkdir(parents=True,exist_ok=False)
    contract=dict(input_sha256=hashlib.sha256(config.read_bytes()).hexdigest(),grids=REFINED_GRIDS,
        grid_columns=["stations","body","free","control","history_quadrature"],
        frequency_index=4,case_ids=[c["id"] for c in raw["cases"]],
        relative_limit=.05,near_zero_threshold=.02,absolute_dimensionless_limit=.001,
        normalization="F3=rho*g*L*B; F5=rho*g*L^2*B",
        scope="three speeds, one frequency each, original/delta/candidate; not full-band acceptance")
    (out/"contract.json").write_text(json.dumps(contract,indent=2))
    levels=[]
    for i in range(3):
        probe(config,out/f"grid_{i}",i)
        levels.append(pd.read_csv(out/f"grid_{i}/force_changes.csv"))
        print(f"Grid {i+1}/3 complete",flush=True)
    paired=levels[1].merge(levels[2],on=["case","omega","mode"],suffixes=("_mid","_fine"),validate="one_to_one")
    if len(paired)!=6:
        raise ValueError("Missing speed/mode coverage")
    checks=[]
    for row in paired.to_dict("records"):
        scale=boat.rho_water_kg_m3*boat.gravity_m_s2*boat.length_m*boat.beam_m
        if row["mode"]==5:
            scale*=boat.length_m
        for component in ("original","delta","candidate"):
            mid=complex(row[f"{component}_real_mid"],row[f"{component}_imag_mid"])
            fine=complex(row[f"{component}_real_fine"],row[f"{component}_imag_fine"])
            change,tolerance,passed=compare(mid,fine,scale)
            checks.append(dict(case=row["case"],mode=row["mode"],component=component,
                dimensionless_change=change,tolerance=tolerance,passed=passed,
                fine_real=fine.real/scale,fine_imag=fine.imag/scale))
    frame=pd.DataFrame(checks)
    frame.to_csv(out/"grid_checks.csv",index=False)
    result=dict(checks=len(frame),passed_count=int(frame.passed.sum()),passed=bool(frame.passed.all()),
        full_band_acceptance=False,physical_acceptance="NOT_PASSED")
    (out/"results.json").write_text(json.dumps(result,indent=2))
    print(json.dumps(result))
    return 0 if result["passed"] else 2


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    raise SystemExit(run(a.config,a.out))
