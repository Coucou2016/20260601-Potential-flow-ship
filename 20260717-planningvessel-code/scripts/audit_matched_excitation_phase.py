"""Independent analytic incident-pressure check, no experimental response input."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from scipy.integrate import quad

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from planing_seakeeping.station_2p5d import StationHull,HardChineStation
from planing_seakeeping.schema import Linear2p5DProviderConfig
from planing_seakeeping.planing_frequency_correction import assemble_matched_domain_head_sea_excitation


def run(contract_path,out):
    c=json.loads(contract_path.read_text())
    out.mkdir(parents=True,exist_ok=False)
    contract_bytes=contract_path.read_bytes()
    (out/"contract.json").write_bytes(contract_bytes)
    (out/"contract.sha256").write_text(hashlib.sha256(contract_bytes).hexdigest())
    length,beam,draft,cg=[c[x] for x in ("length_m","beam_m","draft_m","lcg_m")]
    offsets=((beam/2,0.),(0.,draft),(-beam/2,0.))
    hull=StationHull(length,tuple(HardChineStation(float(x),beam,draft,
        float(np.degrees(np.arctan2(2*draft,beam))),offset_points_m=offsets)
        for x in np.linspace(0,length,c["stations"])),cg)
    config=Linear2p5DProviderConfig(hull_stations=c["stations"],body_panels_per_section=c["body_panels"],
        free_surface_inner_panels=c["free_inner"],free_surface_outer_panels=c["free_outer"])
    rows=[]
    for speed in c["speeds_mps"]:
        for k in c["wavenumbers_rad_m"]:
            omega=np.sqrt(c["g"]*k)+speed*k
            total,parts,diag=assemble_matched_domain_head_sea_excitation(hull=hull,
                encounter_omega_rad_s=np.array([omega]),speed_mps=speed,gravity_m_s2=c["g"],
                rho_water_kg_m3=c["rho"],config=config)
            density=c["rho"]*c["g"]*beam*(-np.expm1(-k*draft))/(k*draft)
            for mode in (0,1):
                weight=lambda x:(x-cg)**mode
                integral=quad(lambda x:weight(x)*np.cos(k*(x-cg)),0,length,epsabs=1e-11)[0]+1j*quad(
                    lambda x:weight(x)*np.sin(k*(x-cg)),0,length,epsabs=1e-11)[0]
                reference=-1j*density*integral
                actual=parts["matched_domain_froude_krylov"][0,mode]
                amp_error=abs(abs(actual)-abs(reference))/abs(reference)
                phase_error=abs(np.degrees(np.angle(actual/reference)))
                long_limit=-1j*c["rho"]*c["g"]*beam*(length if mode==0 else length*(length/2-cg))
                long_error=abs(actual-long_limit)/abs(long_limit) if k==min(c["wavenumbers_rad_m"]) else None
                rows.append(dict(speed=speed,k=k,mode=[3,5][mode],reference_real=reference.real,
                    reference_imag=reference.imag,actual_real=actual.real,actual_imag=actual.imag,
                    amplitude_error=float(amp_error),phase_error_deg=float(phase_error),
                    long_wave_error=None if long_error is None else float(long_error),
                    pressure_identity=diag["matched_domain_excitation_maximum_incident_pressure_identity_relative_residual"],
                    passed=bool(amp_error<=c["amplitude_relative_limit"] and phase_error<=c["phase_absolute_limit_deg"]
                        and (long_error is None or long_error<=c["long_wave_relative_limit"])
                        and diag["matched_domain_excitation_maximum_incident_pressure_identity_relative_residual"]<=c["pressure_identity_limit"])))
    report={"passed":all(r["passed"] for r in rows),"rows":rows,"diffraction_validation":"NOT_EVALUATED",
        "source_hashes":{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
            [ROOT/"planing_seakeeping/planing_frequency_correction.py",ROOT/"planing_seakeeping/kernels/linear_2p5d/formulation.py",Path(__file__)]}}
    (out/"results.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
    return 0 if report["passed"] else 2


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    raise SystemExit(run(ROOT/"benchmarks/excitation_phase_20260921/contract.json",args.out))
