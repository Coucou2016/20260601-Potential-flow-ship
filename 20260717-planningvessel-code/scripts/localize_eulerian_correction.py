"""Localize saved geometric correction without rerunning or fitting the flow."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from planing_seakeeping.linear_case import load_linear_case
from planing_seakeeping.quadrature import clipped_piecewise_linear_integral
from planing_seakeeping.kernels.linear_2p5d.formulation import _integrate_pressure_heave_pitch


def fraction_weights(length, intervals):
    right=np.cumsum(length,axis=1)/length.sum(axis=1)[:,None]
    left=right-length/length.sum(axis=1)[:,None]
    overlap=sum(np.maximum(0,np.minimum(right,b)-np.maximum(left,a)) for a,b in intervals)
    return overlap/(right-left)


def run(config, mid, fine, out):
    raw,boat=load_linear_case(config)
    out.mkdir(parents=True,exist_ok=False)
    (out/"contract.json").write_text(json.dumps(dict(
        waterline_intervals=[[0,.1],[.9,1]],keel_interval=[.45,.55],
        scope="fixed contour-arclength localization; fractional panel weights; not new acceptance"),indent=2))
    rows=[]
    for level,folder in (("mid",mid),("fine",fine)):
        for case in raw["cases"]:
            with np.load(folder/f"boundary_{case['id']}.npz") as d:
                regions=dict(waterline=fraction_weights(d["length"],[(0,.1),(.9,1)]),
                             keel=fraction_weights(d["length"],[(.45,.55)]))
                regions["interior"]=1-regions["waterline"]-regions["keel"]
                for component in ("normal","tangent"):
                    pressure=-boat.rho_water_kg_m3*case["speed_mps"]*d[component+"_chain"]
                    for region,weights in regions.items():
                        density=np.asarray([_integrate_pressure_heave_pitch(pressure[i]*weights[i],
                            d["normal_z"][i],d["length"][i],boat.lcg_m-x) for i,x in enumerate(d["x"])])
                        force=clipped_piecewise_linear_integral(d["x"],density,.5*boat.beam_m)*np.array([1j,-1j])
                        for j,mode in enumerate((3,5)):
                            rows.append(dict(level=level,case=case["id"],component=component,region=region,
                                mode=mode,real=force[j].real,imag=force[j].imag))
    frame=pd.DataFrame(rows)
    frame.to_csv(out/"regional_forces.csv",index=False)
    pairs=frame[frame.level=="mid"].merge(frame[frame.level=="fine"],
        on=["case","component","region","mode"],suffixes=("_mid","_fine"),validate="one_to_one")
    pairs["change_real"]=pairs.real_fine-pairs.real_mid
    pairs["change_imag"]=pairs.imag_fine-pairs.imag_mid
    pairs["change_abs"]=np.hypot(pairs.change_real,pairs.change_imag)
    pairs.to_csv(out/"regional_changes.csv",index=False)
    print(pairs[(pairs.component=="tangent")&(pairs['mode']==3)][
        ["case","region","change_real","change_imag","change_abs"]].to_string(index=False))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("config","mid","fine","out"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    run(a.config,a.mid,a.fine,a.out)
