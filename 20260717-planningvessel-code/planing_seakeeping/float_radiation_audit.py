"""Strict raw section radiation on actual clipped float stations.

Zero-speed strip assembly is a diagnostic, not a forward-speed 2.5D solver.
Wave excitation deliberately stays the old hydrostatic approximation for a
controlled radiation-only comparison. No candidate is promoted automatically.
"""
from pathlib import Path
import hashlib
import html
import json

import numpy as np
import pandas as pd

from .section_bem import SectionOffsets, solve_heave_radiation_pdstrip_style
from .seaplane_workflow import load_workflow, FloatHydrostatics, build_model, excitation, transfer, write_json
from .float_offsets import read_float_offsets


def wetted_section(model, index):
    h=model["hydro"]
    level=model["static"]["level"][index]
    y=h.y[index]
    bottom=h.bottom[index]
    if level <= min(bottom):
        return None
    if level >= h.deck[index]:
        raise ValueError("Deck immersion is outside the section-radiation audit")
    if np.any(np.diff(bottom)<-1e-12):
        raise ValueError("Nonmonotone bottom needs general polygon clipping")
    keep=bottom<level
    ys=list(y[keep]); zs=list(bottom[keep])
    if level < bottom[-1]:
        j=np.flatnonzero(bottom>=level)[0]
        endpoint=y[j-1]+(y[j]-y[j-1])*(level-bottom[j-1])/(bottom[j]-bottom[j-1])
    else:
        endpoint=y[-1]
    ys.append(endpoint); zs.append(level)
    ys=np.asarray(ys); depth=(level-np.asarray(zs))*np.cos(model["q0"][1])
    # Starboard waterline -> keel -> port waterline; no artificial closure segment.
    return SectionOffsets(np.r_[ys[::-1],-ys[1:]],np.r_[depth[::-1],depth[1:]])


def run_audit(config_path,out_dir):
    raw,base,path=load_workflow(config_path)
    out=Path(out_dir)
    if out.exists() and any(out.iterdir()):
        raise ValueError("A clean output directory is required")
    out.mkdir(parents=True,exist_ok=True)
    # Freeze the diagnostic matrix and criteria before computing the candidate.
    contract={"periods_s":[1.6,2.,3.,5.,8.],"grids":[[2,12,16],[4,24,32],[8,48,64]],
              "grid_scaled_tolerance":.05,"residual_limit":1e-8,"condition_limit":1e12,
              "damping_negative_tolerance":1e-8,"excitation":"unchanged_hydrostatic_approximation",
              "status":"diagnostic_only_never_automatic_promotion"}
    write_json(out/"contract.json",contract)
    write_json(out/"input_snapshot.json",{"workflow":raw,"base":base})
    stations=read_float_offsets(path)
    omega=2*np.pi/np.asarray(contract["periods_s"])
    rows=[]; section_rows=[]; grids=[]
    for grid,(subdivisions,body,free) in enumerate(contract["grids"]):
        model=build_model(FloatHydrostatics(stations,subdivisions),base,raw)
        sections=[wetted_section(model,i) for i in range(len(model["hydro"].x))]
        matrices=[]
        for period,w in zip(contract["periods_s"],omega):
            a=np.zeros((2,2)); b=np.zeros((2,2)); residual=0.; condition=0.; negative=0
            for i,section in enumerate(sections):
                if section is None:
                    continue
                result=solve_heave_radiation_pdstrip_style(section,w,model["rho"],model["g"],free,body,strict=True)
                shape=model["n"][i]
                weight=model["hydro"].dx[i]*np.outer(shape,shape)
                a+=result.added_mass_per_m*weight
                b+=result.damping_per_m*weight
                residual=max(residual,result.residual_norm)
                condition=max(condition,result.condition_number)
                negative+=result.damping_per_m < -contract["damping_negative_tolerance"]
                section_rows.append({"grid":grid,"period_s":period,"station_index":i,"x_aft_m":model["hydro"].x[i],
                    "a33_raw_kg_per_m":result.added_mass_per_m,"b33_raw_kg_per_m_s":result.damping_per_m,
                    "relative_residual":result.residual_norm,"condition_number":result.condition_number})
            effective_positive=np.linalg.eigvalsh(model["M"]+a).min()>0
            passive=np.linalg.eigvalsh(b).min()>=-contract["damping_negative_tolerance"] and negative==0
            admissible=effective_positive and passive and residual<=contract["residual_limit"] and condition<=contract["condition_limit"]
            candidate=np.full(2,np.nan,dtype=complex)
            if admissible:
                candidate=np.linalg.solve(model["C"]-w*w*(model["M"]+a)+1j*w*b,excitation(model,np.array([w]))[0])
            baseline=transfer(model,np.array([w]))[0][0]
            row={"grid":grid,"period_s":period,"negative_section_damping_count":negative,
                "mass_positive":bool(effective_positive),"passive":bool(passive),"candidate_admissible":bool(admissible),
                "residual":residual,"condition":condition,"heave_baseline":abs(baseline[0]),"pitch_baseline":abs(baseline[1]),
                "heave_candidate":abs(candidate[0]),"pitch_candidate":abs(candidate[1])}
            for name,mat in (("A",a),("B",b)):
                for j in range(2):
                    for k in range(2):
                        row[f"{name}{[3,5][j]}{[3,5][k]}"]=mat[j,k]
            rows.append(row);matrices.append((a,b))
        grids.append(matrices)
    table=pd.DataFrame(rows)
    table.to_csv(out/"radiation_and_response.csv",index=False)
    pd.DataFrame(section_rows).to_csv(out/"raw_section_coefficients.csv",index=False)
    comparisons=[]
    for i,period in enumerate(contract["periods_s"]):
        for j,name in enumerate(("A","B")):
            medium,fine=grids[1][i][j],grids[2][i][j]
            # Dimensionally distinct entry floors: kg, kg*m, kg*m^2 (or /s).
            scale=np.maximum(np.sqrt(np.outer(abs(np.diag(fine)),abs(np.diag(fine)))),np.array([[1.,1.],[1.,1.]]))
            change=float(np.max(abs(medium-fine)/scale))
            comparisons.append({"period_s":period,"matrix":name,"scaled_change":change,
                                "passed":bool(change<=contract["grid_scaled_tolerance"])})
    pd.DataFrame(comparisons).to_csv(out/"grid_checks.csv",index=False)
    passed=all(c["passed"] for c in comparisons) and bool(table.candidate_admissible.all())
    status={"numerical_screen":"PASS" if passed else "FAIL","physical_validation":"NOT_VALIDATED",
            "enabled_in_default_workflow":False,"forward_speed_2p5d":False,"experiments_read":False,
            "grid_checks":comparisons,"negative_section_damping_occurrences":int(table.negative_section_damping_count.sum()),
            "notes":["No sign flipping, coefficient clipping or least-squares fallback in strict mode.",
                     "The kernel still averages two near/far panel split choices; independent reference validation remains pending.",
                     "Response candidate is withheld when effective mass, damping or solve diagnostics fail.",
                     "Hydrostatic excitation has NOT been replaced by a diffraction solution."]}
    write_json(out/"acceptance.json",status)
    write_json(out/"source_hashes.json",{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (Path(__file__),Path(__file__).with_name("section_bem.py"),path,Path(config_path),
                  Path(__file__).with_name("seaplane_workflow.py"))})
    explanation=("本轮将EDO配平后的浸水剖面接入严格模式剖面辐射求解，保留原始正负号。"
        "每个频率装配升沉/纵摇附加质量与阻尼，与原假设模型比较。三档同时加密纵向与剖面离散，"
        "检验细两档变化。空白响应表示候选未满足基本数值准入，不是零运动。"
        "即使筛查通过，也只属于零航速条带研究；未完成前进速度2.5D、绕射激励或真实飞机验证。")
    body=f"<h1>浮筒实际剖面辐射接入审计</h1><p>{explanation}</p><h2>状态：{status['numerical_screen']}</h2>"
    body+="<p>默认工作流未替换；旧研究示例和历史实验门保持原状。</p><h2>三档结果</h2>"+table.to_html(index=False,na_rep="未准入",float_format=lambda x:f"{x:.5g}")
    body+="<h2>细两档变化，限值5%</h2>"+pd.DataFrame(comparisons).to_html(index=False)
    (out/"report.html").write_text("<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'><style>body{font:16px/1.7 sans-serif;margin:30px}table{border-collapse:collapse;font-size:12px}td,th{border:1px solid #ccc;padding:5px}h1{font-size:26px}</style></head><body>"+body+"</body></html>",encoding="utf-8")
    (out/"report.md").write_text("# 浮筒剖面辐射接入审计\n\n"+explanation+"\n\n```json\n"+json.dumps(status,ensure_ascii=False,indent=2)+"\n```\n",encoding="utf-8")
    print(json.dumps(status,ensure_ascii=False,indent=2))
    return 0 if passed else 2
