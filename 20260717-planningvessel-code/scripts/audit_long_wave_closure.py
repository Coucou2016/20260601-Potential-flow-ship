"""Response-blind long-wave consistency diagnostic, not an EFD acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from planing_seakeeping.linear_case import load_linear_case
from planing_seakeeping.config import PrescribedRunningStateConfig
from planing_seakeeping.equilibrium import make_prescribed_equilibrium
from planing_seakeeping.coefficients import compute_hydro_matrices
from planing_seakeeping.planing_frequency_correction import compute_matched_bie_frequency_correction, build_planing_wetted_station_hull
from planing_seakeeping.quadrature import clipped_piecewise_linear_integral
from planing_seakeeping.kernels.linear_2p5d.panel_integrals import panel_integration_route


def translation_residual(stiffness, excitation):
    """Uniform raised water level: qhat=-i*[1,0] for sine elevation."""
    return np.asarray(stiffness) @ np.array([-1j,0.]) - np.asarray(excitation)


def run(config, out):
    raw, boat = load_linear_case(config)
    out.mkdir(parents=True,exist_ok=False)
    kl = np.array([1e-2,1e-3,1e-4])
    mesh = dict(station_count=29,body_panels_per_section=36,free_surface_inner_panels=36,
                free_surface_outer_panels=48,history_steps=64,history_quadrature_count=48,history_k_max=25.)
    sources = [Path(__file__),config,*sorted(Path('planing_seakeeping').rglob('*.py'))]
    (out/'contract.json').write_text(json.dumps(dict(kL=kl.tolist(),mesh=mesh,
        route='reconstructed_symmetric',grading=1.5,cutoff_beams=.5,
        scope='Long-wave model consistency; diagnostic grid; no acceptance or response fitting',
        hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}),indent=2))
    rows = []
    for case in raw['cases']:
        eq = make_prescribed_equilibrium(boat,case['speed_mps'],PrescribedRunningStateConfig(
            enabled=True,trim_deg=case['trim_deg'],lambda_w=case['lambda_w']))
        hydro = compute_hydro_matrices(boat,eq)
        k = kl/boat.length_m
        omega = np.sqrt(boat.gravity_m_s2*k)+case['speed_mps']*k
        hull = build_planing_wetted_station_hull(boat,eq,station_count=29)
        x = np.array([s.x_m for s in hull.stations])
        beam = np.array([s.waterplane_beam_m() for s in hull.stations])
        static_incident = boat.rho_water_kg_m3*boat.gravity_m_s2*clipped_piecewise_linear_integral(
            x,np.column_stack((beam,beam*(x-boat.lcg_m))),.5*boat.beam_m)
        with panel_integration_route('reconstructed_symmetric'):
            correction = compute_matched_bie_frequency_correction(boat,eq,omega,
                high_frequency_reference_rad_s=2*omega.max(),**mesh,restoring_matrix=hydro.restoring,
                transom_force_cutoff_length_beams=.5,head_sea_excitation_formulation='matched_domain_incident_diffraction',
                cutoff_quadrature='clipped_linear',waterline_grading_exponent=1.5)
        for kval,w in zip(kl,omega):
            index = int(np.flatnonzero(np.isclose(correction.sample_omega_rad_s,w,rtol=1e-12,atol=0))[0])
            added, damping = correction.raw_added_mass[index],correction.raw_radiation_damping[index]
            radiation = -w*w*added+1j*w*damping
            rigid = np.diag([boat.mass_kg,boat.mass_kg*boat.pitch_radius_gyration_m**2])
            stiffness = hydro.restoring+radiation-w*w*rigid
            excitation = correction.excitation_components['matched_domain_incident_plus_diffraction'][index]
            fk = correction.excitation_components['matched_domain_froude_krylov'][index]
            diff = correction.excitation_components['matched_domain_diffraction'][index]
            q = np.linalg.solve(stiffness,excitation)
            residual = translation_residual(stiffness,excitation)
            for i,mode in enumerate((3,5)):
                scale = boat.rho_water_kg_m3*boat.gravity_m_s2*boat.length_m*boat.beam_m*boat.length_m**i
                rows.append(dict(case=case['id'],kL=kval,omega=w,mode=mode,
                    restoring_heave_column=hydro.restoring[i,0],static_incident=static_incident[i],
                    incident_phase_aligned_real=(1j*fk[i]).real,incident_phase_aligned_imag=(1j*fk[i]).imag,
                    diffraction_abs=abs(diff[i]),radiation_heave_column_abs=abs(radiation[i,0]),
                    radiation_pitch_column_real=radiation[i,1].real,radiation_pitch_column_imag=radiation[i,1].imag,
                    translation_residual_normalized=abs(residual[i])/scale,
                    motion_phase_aligned_real=(1j*q[i]).real,motion_phase_aligned_imag=(1j*q[i]).imag))
        pd.DataFrame(rows).to_csv(out/'long_wave_closure.csv',index=False)
        print(case['id']+' complete',flush=True)
    frame = pd.DataFrame(rows)
    print(frame[frame.kL==kl[-1]].to_string(index=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a = p.parse_args()
    run(a.config,a.out)
