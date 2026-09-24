"""Numeric-only archive of computed steady 2D+t free-surface states."""
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np


def export_surface_history(path, result, config, *, speed, trim, length, initial_draft):
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    if len(result.states) != len(result.time_s):
        raise ValueError('State and time counts differ')
    values = dict(time_s=np.asarray(result.time_s), draft_m=np.asarray(result.draft_m),
        x_from_transom_m=length-initial_draft/np.tan(trim)-speed*np.asarray(result.time_s),
        sectional_force_n_m=np.asarray(result.vertical_force_per_length_n_m))
    for i, state in enumerate(result.states):
        if not np.isclose(state.time_s, result.time_s[i], rtol=0, atol=1e-10):
            raise ValueError('State time and recorded time differ')
        for side in ('right', 'left'):
            y, z, phi = (np.asarray(getattr(state, side+suffix)) for suffix in
                         ('_free_y_m', '_free_z_up_m', '_free_potential_m2_s'))
            if (y.ndim != 1 or z.shape != y.shape or len(y)<3
                    or phi.shape not in (y.shape, (len(y)-1,))
                    or not all(np.isfinite(a).all() for a in (y,z,phi))):
                raise ValueError('Invalid surface snapshot')
            for name, array in [('y_m',y), ('z_up_m',z), ('potential_m2_s',phi)]:
                values[f'{i}_{side}_{name}'] = array
        values[f'{i}_jet_cut_count'] = np.array(state.jet_cut_count)
    np.savez_compressed(path, **values)
    path.with_suffix('.json').write_text(json.dumps(dict(
        scope='Computed free surface and surface potential only; no exported body pressure or 3D velocity Hessian',
        physical_acceptance='NOT_PASSED', coordinate='earth-fixed transverse sections; z up',
        mapping='x_transom=length-initial_draft/tan(trim)-U*time',
        potential_location='per side: len(phi)==len(y) means nodes; otherwise panel centres',
        speed_mps=speed, trim_rad=trim, length_m=length, initial_draft_m=initial_draft,
        reference_draft_m=result.reference_draft_m, state_count=len(result.states),
        config=asdict(config)), indent=2), encoding='utf-8')
