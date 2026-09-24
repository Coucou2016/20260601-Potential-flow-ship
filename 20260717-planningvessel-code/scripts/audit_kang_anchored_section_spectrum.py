"""Frozen-history section spectrum on the actual anchored grid, not full stability."""
import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.kang_reference_geometry import build_hull
from planing_seakeeping.kernels.linear_2p5d import formulation as f
from planing_seakeeping.kernels.linear_2p5d.anchored_free_surface import build_anchored_free_surface


def trapezoidal_radius(eigenvalues,dt,gravity=9.80665):
    eigenvalues=np.asarray(eigenvalues,complex)
    if (not eigenvalues.size or not np.isfinite(eigenvalues).all()
            or not np.isfinite([dt,gravity]).all() or min(dt,gravity)<=0):
        raise ValueError('Finite eigenvalues and positive timestep/gravity required')
    roots=np.sqrt(-gravity*eigenvalues)
    rates=np.r_[roots,-roots]
    return float(np.max(np.abs((1+dt*rates/2)/(1-dt*rates/2))))


def run(out):
    out.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[1]
    sources=[Path(__file__),root/'scripts/kang_reference_geometry.py',
             *sorted((root/'planing_seakeeping/kernels/linear_2p5d').glob('*.py'))]
    indices=[80,60,40,20,1]
    contract=dict(stage_acceptance=False,station_indices=indices,stations=161,
        scope='Frozen section and zero frozen control history; excludes remap and history feedback',
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    (out/'contract.json').write_text(json.dumps(contract,indent=2))
    hull=build_hull(161,161,moment_reference_x=1.5)
    speed=.2*np.sqrt(9.80665*3)
    dt=(hull.stations[1].x_m-hull.stations[0].x_m)/speed
    control=f.build_control_surface_geometry(radius_m=.9,panel_count=96)
    history=f.build_transient_free_surface_history(control,dt,1,quadrature_count=64,k_max=25.)
    rows=[]
    for index in indices:
        station=hull.stations[index]
        body=f.build_inner_domain_panel_geometry(station.section_offsets(),body_panel_count=64)
        free=build_anchored_free_surface(.9,.15,station.waterplane_beam_m()/2,20,44)
        nf=free.panel_count
        data=f.MatchedSectionBoundaryData(body=body,inner_free_surface=free,control=control,
            history=history,body_normal_velocity=np.zeros(64,complex),
            free_surface_potential=np.zeros(nf,complex),past_control_potential=np.zeros((1,96),complex),
            past_control_normal_derivative=np.zeros((1,96),complex))
        system=f.assemble_matched_section_system(data)
        rhs_map=np.vstack([-f._inner_a_matrix(geometry,free,same_boundary=j==1,diagonal_sign=-1.)
            for j,geometry in enumerate((body,free,control))]+[np.zeros((96,nf))])
        solution_map=np.linalg.solve(system.matrix,rhs_map)
        residual=np.linalg.norm(system.matrix@solution_map-rhs_map)/np.linalg.norm(rhs_map)
        phi=np.random.default_rng(24).normal(size=nf)+1j*np.random.default_rng(25).normal(size=nf)
        check=f.assemble_matched_section_system(replace(data,free_surface_potential=phi))
        replay=np.linalg.norm(check.rhs-rhs_map@phi)/np.linalg.norm(check.rhs)
        if not np.isfinite([residual,replay]).all() or max(residual,replay)>1e-10:
            raise ValueError('Section operator failed original-equation replay')
        operator=solution_map[64:64+nf]
        eig=np.linalg.eigvals(operator)
        np.savez_compressed(out/f'operator_{index}.npz',operator=operator,eigenvalues=eig)
        rows.append(dict(index=index,x_m=station.x_m,free_panels=nf,
            minimum_free_length_m=float(min(free.length_m)),
            minimum_eigenvalue_real=float(min(eig.real)),maximum_eigenvalue_real=float(max(eig.real)),
            maximum_eigenvalue_imag=float(max(abs(eig.imag))),
            trapezoidal_radius_dt161=trapezoidal_radius(eig,dt),
            trapezoidal_radius_dt321=trapezoidal_radius(eig,dt/2),
            map_residual=float(residual),rhs_replay_error=float(replay)))
    frame=pd.DataFrame(rows)
    frame.to_csv(out/'spectrum.csv',index=False)
    print(frame.to_string(index=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    run(parser.parse_args().out)
