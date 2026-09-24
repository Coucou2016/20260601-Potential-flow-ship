"""Resolve a transparent mass budget and sensitivity without claiming flight."""
import copy
import json
import math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from planing_seakeeping.aircraft_mass import component_mass_properties


def main():
    config=json.loads((ROOT/"configs/edo106k_synthetic_aircraft.json").read_text(encoding="utf-8"))
    result=component_mass_properties(config["mass_components"])
    cases=[]
    for factor in config["sensitivity_assumed"]["all_component_mass_factors"]:
        for shift in config["sensitivity_assumed"]["payload_longitudinal_shift_m"]:
            components=copy.deepcopy(config["mass_components"])
            for c in components:
                c["mass_kg"]*=factor
                if c["name"]=="payload_fuel":
                    c["center_m"][0]+=shift
            cases.append({"mass_factor":factor,"payload_shift_m":shift,**component_mass_properties(components)})
    aero=config["aerodynamics_assumed"]
    ar=aero["span_m"]**2/aero["area_m2"]
    slope=2*math.pi/(1+2*math.pi/(math.pi*aero["oswald_efficiency"]*ar))
    result["derived_aero_assumptions"]={"aspect_ratio":ar,"cl_per_rad":slope,"induced_drag_factor":1/(math.pi*aero["oswald_efficiency"]*ar)}
    result["sensitivity_cases"]=cases
    result["equilibrium_status"]="NOT_SOLVED; no closed float volume or hydrostatic/propulsive trim acceptance"
    out=ROOT/"outputs/edo106k_synthetic_assumptions"
    out.mkdir(parents=True,exist_ok=True)
    (out/"mass_and_sensitivity.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="sensitivity_cases"},indent=2))


if __name__=="__main__":
    main()
