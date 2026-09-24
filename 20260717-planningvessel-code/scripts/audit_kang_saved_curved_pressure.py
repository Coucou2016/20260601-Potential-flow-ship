"""Replay actual pressure and diagnose curved-trace transport on the same potentials."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scripts.curved_trace_pressure_diagnostic import recover_gradient


def run(directory, out):
    contract = json.loads((directory/'contract.json').read_text())
    if not contract.get('save_boundary') or contract['frequencies'] != [2., 3., 4.]:
        raise ValueError('Explicit saved boundary fields at all three frozen frequencies required')
    rho, g, length = contract['rho'], contract['gravity'], contract['length']
    speed = contract['froude_length']*np.sqrt(g*length)
    files = [Path(__file__), Path(__file__).with_name('curved_trace_pressure_diagnostic.py'), directory/'contract.json']
    files += [directory/f'{prefix}_{w}.npz' for prefix in ('boundary', 'fields') for w in (2, 3, 4)]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    out.mkdir(parents=True, exist_ok=False)
    (out/'contract.json').write_text(json.dumps(dict(stage_acceptance=False, hashes=hashes,
        scope='Saved-field algebra replay and nonconservative curved-trace diagnostic, no production edits',
        derivative_policy='Keep production local-phase differentiation, subtract only moving-trace chain term; direct physical differentiation difference exported separately',
        algebra_tolerance=1e-10, experimental_response_read=False,
        phase='Physical harmonic potential after inverse local-time phase; raw geometric Neumann normal'), indent=2))
    rows = []
    for w in (2, 3, 4):
        omega = w*np.sqrt(g/length)
        with np.load(directory/f'boundary_{w}.npz') as d, np.load(directory/f'fields_{w}.npz') as forces:
            if any(not np.isfinite(d[key]).all() for key in d.files) or any(
                    not np.isfinite(forces[key]).all() for key in forces.files):
                raise ValueError('Nonfinite saved boundary or load fields')
            x, phi = d['x_m'], d['pressure_body_potential']
            expected = d['solved_body_potential']*np.exp(-1j*omega*d['local_time_s'])[:, None]
            phase_error = np.linalg.norm(phi-expected)/max(np.linalg.norm(phi), 1e-30)
            old_pressure = -rho*1j*omega*phi+rho*speed*d['pressure_body_x_gradient']
            pressure_error = np.linalg.norm(old_pressure-d['pressure'])/max(np.linalg.norm(d['pressure']), 1e-30)
            measure = -d['normal_z']*d['length']
            heave_density = np.sum(old_pressure*measure, axis=1)
            old_density = np.stack((heave_density, heave_density*(length/2-x)), axis=1)
            old_force = np.trapezoid(old_density, x, axis=0)
            force_error = np.linalg.norm(old_force-forces['diffraction'])/max(np.linalg.norm(forces['diffraction']), 1e-30)
            errors = np.array([phase_error, pressure_error, force_error])
            if not np.isfinite(errors).all() or np.max(errors) > 1e-10:
                raise ValueError('Saved phase, pressure or integrated force could not be reconstructed')
            recovered = recover_gradient(x, d['y'], d['z_down'], phi,
                d['physical_body_normal_velocity'], d['normal_y'], d['normal_z'])
            diagnostic_gradient = d['pressure_body_x_gradient']-recovered['chain']
            new_pressure = -rho*1j*omega*phi+rho*speed*diagnostic_gradient
            heave_new = np.sum(new_pressure*measure, axis=1)
            new_density = np.stack((heave_new, heave_new*(length/2-x)), axis=1)
            new_force = np.trapezoid(new_density, x, axis=0)
            np.savez_compressed(out/f'pressure_{w}.npz', x_m=x, original_pressure=old_pressure,
                diagnostic_pressure=new_pressure, original_density=old_density,
                diagnostic_density=new_density, diagnostic_gradient=diagnostic_gradient,
                phase_differencing_gap=recovered['material']-d['pressure_body_x_gradient'], **recovered)
            for j, mode in enumerate(('heave', 'geometric_pitch')):
                rows.append(dict(frequency=w, mode=mode, phase_replay_error=phase_error,
                    pressure_replay_error=pressure_error, force_replay_error=force_error,
                    original_real=old_force[j].real, original_imag=old_force[j].imag,
                    diagnostic_real=new_force[j].real, diagnostic_imag=new_force[j].imag,
                    complex_relative_change=abs(new_force[j]-old_force[j])/max(abs(old_force[j]), 1e-30)))
    frame = pd.DataFrame(rows)
    frame.to_csv(out/'comparison.csv', index=False)
    (out/'summary.json').write_text(json.dumps(dict(stage_acceptance=False, pressure_replay_pass=True,
        diagnostic_validated_on_experiment=False, production_changed=False,
        limitations=['Midpoint tangential differentiation and tip errors remain',
                    'Not a conservative flux formulation', 'Same potential solution, not an independent diffraction solution']), indent=2))
    print(frame.to_string(index=False))


if __name__=='__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    run(a.run, a.out)
