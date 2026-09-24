"""One-axis-at-a-time diagnostics; never a substitute for full-band acceptance."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from planing_seakeeping.config import PrescribedRunningStateConfig
from planing_seakeeping.coefficients import compute_hydro_matrices
from planing_seakeeping.equilibrium import make_prescribed_equilibrium
from planing_seakeeping.linear_case import load_linear_case
from planing_seakeeping.planing_frequency_correction import compute_matched_bie_frequency_correction


def run(config_path, out, surface_split=False, surface_refinement=False):
    if surface_split and surface_refinement:
        raise ValueError('Choose only one surface audit mode')
    raw, boat = load_linear_case(config_path)
    case = next(c for c in raw['cases'] if c['id']=='fn167')
    omega = np.array([case['encounter_omega_rad_s'][i] for i in (0,7)])
    base = dict(station_count=57,body_panels_per_section=48,free_surface_inner_panels=24,
        free_surface_outer_panels=48,history_steps=128,history_quadrature_count=32,history_k_max=25.)
    axes = {
        'station': [dict(station_count=n) for n in (29,57,113)],
        'body': [dict(body_panels_per_section=n) for n in (24,48,72)],
        'free_surface': [dict(free_surface_inner_panels=n,free_surface_outer_panels=2*n) for n in (12,24,36)],
        'history_spectral': [dict(history_quadrature_count=n) for n in (16,32,64)]}
    if surface_split:
        base.update(free_surface_inner_panels=36, free_surface_outer_panels=72,
                    free_surface_substeps_per_station=2)
        axes = {
            'inner_free_surface': [dict(free_surface_inner_panels=n) for n in (24,36,48)],
            'matching_control_boundary': [dict(free_surface_outer_panels=n) for n in (48,72,96)],
            'free_surface_substeps': [dict(free_surface_substeps_per_station=n) for n in (1,2,4)]}
    if surface_refinement:
        base.update(free_surface_inner_panels=48, free_surface_outer_panels=96,
                    free_surface_substeps_per_station=1)
        axes = {'inner_free_surface': [dict(free_surface_inner_panels=n) for n in (48,72,96)]}
    out.mkdir(parents=True,exist_ok=False)
    contract = dict(input_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),case='fn167',
        omega_rad_s=omega.tolist(),base=base,axes=axes,relative_limit=.05,
        dimensionless_absolute_limit=.001,near_zero_dimensionless_threshold=.02,
        cutoff_quadrature='clipped_linear',scope='two-frequency numerical diagnosis, not full-band acceptance')
    frozen=json.dumps(contract,indent=2).encode()
    (out/'contract.json').write_bytes(frozen)
    (out/'contract.sha256').write_text(hashlib.sha256(frozen).hexdigest())
    root = Path(__file__).resolve().parents[1]
    sources = ['scripts/audit_directional_hydrodynamic_grid.py',
        'planing_seakeeping/planing_frequency_correction.py',
        'planing_seakeeping/quadrature.py',
        'planing_seakeeping/kernels/linear_2p5d/formulation.py']
    (out/'source_hashes.json').write_text(json.dumps({name:hashlib.sha256((root/name).read_bytes()).hexdigest()
        for name in sources},indent=2))
    eq=make_prescribed_equilibrium(boat,case['speed_mps'],PrescribedRunningStateConfig(
        enabled=True,trim_deg=case['trim_deg'],lambda_w=case['lambda_w']))
    restoring=compute_hydro_matrices(boat,eq).restoring
    L,B,rho,g=boat.length_m,boat.beam_m,boat.rho_water_kg_m3,boat.gravity_m_s2
    scales={'A':rho*L*B**2,'B':rho*L*B**2*np.sqrt(g/L),'F':rho*g*L*B}
    rows=[]
    cache={}
    for axis, levels in axes.items():
        for level, change in enumerate(levels):
            options=dict(base,**change)
            key=tuple(sorted(options.items()))
            if key not in cache:
                c=compute_matched_bie_frequency_correction(boat,eq,omega,
                    high_frequency_reference_rad_s=1.8*omega.max(),restoring_matrix=restoring,
                    transom_force_cutoff_length_beams=.5,cutoff_quadrature='clipped_linear',
                    head_sea_excitation_formulation='matched_domain_incident_diffraction',**options)
                data=[]
                for w in omega:
                    index=int(np.flatnonzero(np.isclose(c.sample_omega_rad_s,w,rtol=1e-12))[0])
                    for name,array in (('A',c.raw_added_mass),('B',c.raw_radiation_damping)):
                        for i in range(2):
                            for j in range(2):
                                v=complex(array[index,i,j])/(scales[name]*L**(i+j))
                                data.append(dict(omega=w,component=f'{name}{[3,5][i]}{[3,5][j]}',real=v.real,imag=v.imag))
                    for i,v in enumerate(c.excitation_components['matched_domain_incident_plus_diffraction'][index]):
                        v=v/(scales['F']*L**i)
                        data.append(dict(omega=w,component=f'F{[3,5][i]}',real=v.real,imag=v.imag))
                cache[key]=data
            rows.extend(dict(axis=axis,level=level,**r) for r in cache[key])
            pd.DataFrame(rows).to_csv(out/'coefficients.csv',index=False)
            print(f'{axis} level {level} complete',flush=True)
    frame=pd.DataFrame(rows)
    check=frame[frame.level==1].merge(frame[frame.level==2],on=['axis','omega','component'],suffixes=('_mid','_fine'),validate='one_to_one')
    fine=check.real_fine+1j*check.imag_fine
    check['change']=abs(check.real_mid+1j*check.imag_mid-fine)
    check['tolerance']=np.where(abs(fine)<.02,.001,.05*abs(fine))
    check['passed']=check.change<=check.tolerance
    assert len(check)==20*len(axes)
    check.to_csv(out/'checks.csv',index=False)
    result=dict(passed_count=int(check.passed.sum()),checks=len(check),full_band_accepted=False,
        by_axis=check.groupby('axis').passed.sum().astype(int).to_dict())
    (out/'results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    modes=p.add_mutually_exclusive_group()
    modes.add_argument('--surface-split',action='store_true')
    modes.add_argument('--surface-refinement',action='store_true')
    a=p.parse_args()
    run(a.config,a.out,a.surface_split,a.surface_refinement)
