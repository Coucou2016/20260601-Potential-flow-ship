"""Radiation-only one-parameter-at-a-time section refinement diagnostic."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from planing_seakeeping.section_bem import SectionOffsets, _solve_heave_radiation_pdstrip_near_count


def run(reference, out):
    c = json.loads(reference.read_text(encoding="utf-8"))
    if hashlib.sha256(reference.read_bytes()).hexdigest() != reference.with_suffix(".sha256").read_text().strip():
        raise ValueError("Reference contract hash mismatch")
    out.mkdir(parents=True, exist_ok=False)
    contract = {"source_contract": str(reference.resolve()), "source_hash": hashlib.sha256(reference.read_bytes()).hexdigest(),
                "periods_s": c["periods_s"], "body_counts": [12,24,48], "free_counts": [40,64,96],
                "fixed_body": 48, "fixed_free": 64, "near_counts": [25,28],
                "relative_limit": .05, "absolute_a_limit": .001, "absolute_b_limit": .001,
                "scope": "section-only; free count changes domain extent; body spacing changes first free spacing; not fully independent domain-length test"}
    (out / "contract.json").write_text(json.dumps(contract, indent=2), encoding="utf-8")
    rows=[]; checks=[]
    for name, data in c["sections"].items():
        section=SectionOffsets(np.array(data["y"]),np.array(data["z"]))
        for period in c["periods_s"]:
            omega=2*np.pi/period
            for axis,counts in (("body",contract["body_counts"]),("free",contract["free_counts"])):
                values=[]
                for count in counts:
                    body=count if axis=="body" else contract["fixed_body"]
                    free=count if axis=="free" else contract["fixed_free"]
                    results=[_solve_heave_radiation_pdstrip_near_count(section,omega,c["rho"],c["g"],free,body,nf,strict=True)
                             for nf in contract["near_counts"]]
                    value=np.mean([r[0] for r in results])
                    a,b=float(value.real),float(-omega*value.imag)
                    values.append((a,b))
                    rows.append(dict(section=name,period_s=period,axis=axis,count=count,a=a,b=b,
                                     residual=max(r[2] for r in results),condition=max(r[1] for r in results)))
                for j,quantity in enumerate(("a","b")):
                    delta=abs(values[-1][j]-values[-2][j])
                    limit=max(contract[f"absolute_{quantity}_limit"],.05*abs(values[-1][j]))
                    checks.append(dict(section=name,period_s=period,axis=axis,quantity=quantity,
                                       absolute_change=delta,limit=limit,passed=delta<=limit))
    report={"checks_passed":sum(r["passed"] for r in checks),"check_count":len(checks),
            "negative_damping_count":sum(r["b"] < -1e-8 for r in rows),
            "rows":rows,"checks":checks,"overall_stage_complete":False}
    (out/"results.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k not in ("rows","checks")}))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("reference",type=Path)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    run(args.reference,args.out)
