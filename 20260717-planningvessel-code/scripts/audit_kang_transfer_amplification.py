"""Actual-grid remap-only matrix product; no fluid evolution or physical validation."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scripts.kang_reference_geometry import build_hull
from planing_seakeeping.kernels.linear_2p5d.anchored_free_surface import build_anchored_free_surface
from planing_seakeeping.kernels.linear_2p5d.free_surface_transfer import limited_linear_exposure,transfer_fields


def stationary_fields(y):
    return np.c_[np.ones_like(y),abs(y),np.cos(3*y)]


def evaluate(stations,inner_count=20,outer_count=44):
    hull=build_hull(stations,161,moment_reference_x=1.5)
    old=None; old_half=None; product=None; initial_fields=None; rows=[]
    for station in hull.stations[::-1]:
        half=station.waterplane_beam_m()/2
        free=build_anchored_free_surface(.9,.15,half,inner_count,outer_count)
        if old is None:
            product=np.eye(free.panel_count,dtype=complex)
            initial_fields=stationary_fields(free.mid_y_m)
        else:
            kwargs={}
            if np.any(abs(free.mid_y_m)<old_half):
                try:
                    fill,_=limited_linear_exposure(old.mid_y_m,free.mid_y_m,product,old_half,maximum_spacing_ratio=1.)
                except ValueError as error:
                    raise ValueError(f'{error}; x_m={station.x_m}; completed_stations={len(rows)}') from error
                kwargs=dict(exposed_values=fill,exposed_source='linear_matrix_extension_unvalidated')
            product=transfer_fields(old.mid_y_m,free.mid_y_m,product,
                previous_half_beam=old_half,control_radius=.9,**kwargs).values
        error=product@initial_fields-stationary_fields(free.mid_y_m)
        rows.append(dict(x_m=station.x_m,free_panels=free.panel_count,
            cumulative_infinity_gain=float(np.max(np.sum(abs(product),axis=1))),
            constant_error=float(max(abs(error[:,0]))),affine_error=float(max(abs(error[:,1]))),
            smooth_cosine_error=float(max(abs(error[:,2])))))
        old,old_half=free,half
    return pd.DataFrame(rows),product


def run(out):
    out.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[1]
    paths=[Path(__file__),root/'scripts/kang_reference_geometry.py',
           root/'planing_seakeeping/kernels/linear_2p5d/free_surface_transfer.py',
           root/'planing_seakeeping/kernels/linear_2p5d/anchored_free_surface.py']
    (out/'contract.json').write_text(json.dumps(dict(stage_acceptance=False,
        levels=[[161,20,44],[321,20,44],[321,40,88],[641,40,88]],scope='Pure transfer only; induced infinity gain is not fluid energy',
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}),indent=2))
    results=[]
    for n,inner,outer in ((161,20,44),(321,20,44),(321,40,88),(641,40,88)):
        try:
            frame,product=evaluate(n,inner,outer)
        except ValueError as error:
            if not str(error).startswith('New exposure exceeds frozen continuation distance'):
                raise
            results.append(dict(stations=n,inner_count=inner,outer_count=outer,
                status='EXPOSURE_POLICY_REJECTED',reason=str(error)))
            continue
        frame.to_csv(out/f'stations_{n}_inner{inner}.csv',index=False)
        np.savez_compressed(out/f'transfer_{n}_inner{inner}.npz',matrix=product)
        results.append(dict(stations=n,inner_count=inner,outer_count=outer,status='DIAGNOSTIC_COMPLETED',maximum_gain=float(frame.cumulative_infinity_gain.max()),
            maximum_constant_error=float(frame.constant_error.max()),maximum_affine_error=float(frame.affine_error.max()),
            maximum_cosine_error=float(frame.smooth_cosine_error.max())))
    summary=dict(stage_acceptance=False,physical_model_validated=False,results=results)
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    run(parser.parse_args().out)
