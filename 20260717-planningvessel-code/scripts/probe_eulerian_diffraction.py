"""Candidate geometric pressure correction using actual solved boundary data."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from planing_seakeeping.linear_case import load_linear_case
from planing_seakeeping.config import PrescribedRunningStateConfig
from planing_seakeeping.equilibrium import make_prescribed_equilibrium
from planing_seakeeping.planing_frequency_correction import build_planing_wetted_station_hull
from planing_seakeeping.schema import Linear2p5DProviderConfig
from planing_seakeeping.quadrature import clipped_piecewise_linear_integral
from planing_seakeeping.kernels.linear_2p5d.formulation import (
    solve_station_hull_head_sea_excitation_matched_sweep, _integrate_pressure_heave_pitch)
from planing_seakeeping.kernels.linear_2p5d.pressure_gradient import remove_geometry_chain_term
from planing_seakeeping.kernels.linear_2p5d.panel_integrals import panel_integration_route


REFINED_GRIDS = ((57,48,48,72,32), (85,60,72,96,48), (113,72,96,120,64))


def hull_outward_diffraction_derivative(fluid_outward_derivative):
    """Convert matched-BIE Cauchy data to the stored body-normal convention."""
    values = np.asarray(fluid_outward_derivative, dtype=complex)
    if not np.isfinite(values).all():
        raise ValueError('Fluid-outward boundary derivative must be finite')
    return -values


def run(config_path, out, grid_level=None, body_panels_override=None, stations_override=None,
        free_panels_override=None, integration_route='midpoint', grading_exponent=1., history_steps_override=None):
    with panel_integration_route(integration_route):
        pass
    if not np.isfinite(grading_exponent) or not 1. <= grading_exponent <= 2.:
        raise ValueError('grading_exponent must be finite and between 1 and 2')
    raw, boat = load_linear_case(config_path)
    if grid_level is not None and grid_level not in (0,1,2):
        raise ValueError("grid_level must be 0, 1 or 2")
    stations, body_panels, free_panels, control_panels, quadrature = (
        (29,36,18,36,32) if grid_level is None else REFINED_GRIDS[grid_level])
    if body_panels_override is not None:
        if (isinstance(body_panels_override, bool)
                or not isinstance(body_panels_override, int)
                or body_panels_override < 6 or body_panels_override % 2):
            raise ValueError("body_panels_override must be an even integer >= 6")
        body_panels = body_panels_override
    if stations_override is not None:
        if type(stations_override) is not int or stations_override < 3:
            raise ValueError("stations_override must be an integer >= 3")
        stations = stations_override
    if free_panels_override is not None:
        if type(free_panels_override) is not int or free_panels_override < 4 or free_panels_override % 2:
            raise ValueError("free_panels_override must be an even integer >= 4")
        free_panels = free_panels_override
    history_steps = 64 if grid_level is None else 128
    if history_steps_override is not None:
        if type(history_steps_override) is not int or history_steps_override < 1:
            raise ValueError('history_steps_override must be a positive integer')
        history_steps = history_steps_override
    if history_steps < stations:
        raise ValueError('Diagnostic history must cover all stations')
    out.mkdir(parents=True, exist_ok=False)
    config = Linear2p5DProviderConfig(formulation="matched_bie", hull_stations=stations,
        body_panels_per_section=body_panels, free_surface_inner_panels=free_panels, free_surface_outer_panels=control_panels,
        control_surface_radius_beams=3., include_steady_perturbation=True, include_end_terms=True)
    contract = dict(config_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),
        solver_normal_convention='fluid_domain_outward',
        gradient_normal_convention='stored_hull_outward',
        normal_derivative_conversion=-1,
        integration_route=integration_route,
        waterline_grading_exponent=grading_exponent,
        stations=stations, body=body_panels, free=free_panels, control=control_panels,
        history_steps=history_steps, history_quadrature_count=quadrature,
        history_k_max=25., frequency_index=4, corner_node=body_panels//2, cutoff_beams=.5,
        scope="same solved potentials; pressure postprocess candidate only; not full-band acceptance")
    (out/"contract.json").write_text(json.dumps(contract,indent=2))
    root=Path(__file__).resolve().parents[1]
    sources=[Path(__file__),*sorted((root/"planing_seakeeping").rglob("*.py"))]
    (out/"source_hashes.json").write_text(json.dumps({str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},indent=2))
    rows, panels=[] , []
    for case in raw["cases"]:
        eq=make_prescribed_equilibrium(boat,case["speed_mps"],PrescribedRunningStateConfig(
            enabled=True,trim_deg=case["trim_deg"],lambda_w=case["lambda_w"]))
        hull=build_planing_wetted_station_hull(boat,eq,station_count=stations)
        omega=case["encounter_omega_rad_s"][4]
        with panel_integration_route(integration_route):
            result=solve_station_hull_head_sea_excitation_matched_sweep(hull,omega,case["speed_mps"],
                config=config,rho_water_kg_m3=boat.rho_water_kg_m3,gravity_m_s2=boat.gravity_m_s2,
                parametric_section_shape="hard_chine_v",matched_sweep_options=dict(
                    waterline_grading_exponent=grading_exponent,
                    history_steps=history_steps,history_quadrature_count=quadrature,history_k_max=25.))
        sweep=result.diffraction_sweep
        phase=np.exp(1j*omega*np.asarray(sweep.local_time_s_by_station)) if sweep.apply_local_time_phase else np.ones(len(sweep.x_m))
        phi=np.asarray([v.body_potential for v in sweep.heave_mode_solutions])*np.conj(phase[:,None])
        material=sweep.pressure_force_sweep.heave_potential_gradient.body_potential_x_gradient
        qn=hull_outward_diffraction_derivative(result.diffraction_body_normal_velocity_by_station)
        corrected,chain=remove_geometry_chain_term(sweep.x_m,sweep.bodies,material,phi,
            qn,corner_nodes=(body_panels//2,))
        y=np.asarray([b.mid_y_m for b in sweep.bodies])
        z=np.asarray([b.mid_z_down_m for b in sweep.bodies])
        ny=np.asarray([b.normal_y for b in sweep.bodies])
        nz=np.asarray([b.normal_z for b in sweep.bodies])
        normal_chain=qn*(ny*np.gradient(y,sweep.x_m,axis=0,edge_order=2)
                         +nz*np.gradient(z,sweep.x_m,axis=0,edge_order=2))
        tangent_chain=chain-normal_chain
        np.savez_compressed(out/f"free_surface_{case['id']}.npz",x=sweep.x_m,
            y=sweep.inner_free_surface_y_by_station,
            length=sweep.inner_free_surface_panel_length_by_station,
            phi_local=sweep.heave_free_surface_potential_by_station,
            phi_after_local=sweep.heave_free_surface_potential_after_station,
            elevation_local=sweep.heave_free_surface_elevation_by_station,
            normal_derivative_local=np.asarray([s.inner_free_surface_normal_derivative for s in sweep.heave_mode_solutions]),
            local_time=sweep.local_time_s_by_station,
            time_before=sweep.heave_free_surface_time_before_by_station,
            time_after=sweep.heave_free_surface_time_after_by_station,
            phase=phase)
        np.savez_compressed(out/f"boundary_{case['id']}.npz",x=sweep.x_m,y=y,z=z,
            normal_y=ny,normal_z=nz,length=np.asarray([b.length_m for b in sweep.bodies]),
            node_y=np.asarray([b.node_y_m for b in sweep.bodies]),
            node_z=np.asarray([b.node_z_down_m for b in sweep.bodies]),
            phi=phi,normal_derivative=qn,material_gradient=material,
            normal_derivative_convention=np.asarray('stored_hull_outward'),
            chain=chain,normal_chain=normal_chain,tangent_chain=tangent_chain)
        pressure_delta=-boat.rho_water_kg_m3*case["speed_mps"]*chain
        density=[]
        split_density={"normal":[],"tangent":[]}
        for i,body in enumerate(sweep.bodies):
            lever=sweep.pitch_moment_sign*(hull.lcg_m-sweep.x_m[i])
            density.append(_integrate_pressure_heave_pitch(pressure_delta[i],body.normal_z,body.length_m,lever))
            for label,values in (("normal",normal_chain),("tangent",tangent_chain)):
                split_density[label].append(_integrate_pressure_heave_pitch(
                    -boat.rho_water_kg_m3*case["speed_mps"]*values[i],body.normal_z,body.length_m,lever))
            for j in range(body.panel_count):
                panels.append(dict(case=case["id"],x=sweep.x_m[i],panel=j,
                    chain_real=chain[i,j].real,chain_imag=chain[i,j].imag,
                    pressure_delta_real=pressure_delta[i,j].real,pressure_delta_imag=pressure_delta[i,j].imag))
        delta=clipped_piecewise_linear_integral(sweep.x_m,np.asarray(density),.5*boat.beam_m)*np.array([1j,-1j])
        split_forces={label:clipped_piecewise_linear_integral(sweep.x_m,np.asarray(values),.5*boat.beam_m)*np.array([1j,-1j])
                      for label,values in split_density.items()}
        original=clipped_piecewise_linear_integral(sweep.x_m,result.total_force_density_by_station,.5*boat.beam_m)*np.array([1j,-1j])
        for j,mode in enumerate((3,5)):
            candidate=original[j]+delta[j]
            rows.append(dict(case=case["id"],omega=omega,mode=mode,
                original_real=original[j].real,original_imag=original[j].imag,
                delta_real=delta[j].real,delta_imag=delta[j].imag,
                candidate_real=candidate.real,candidate_imag=candidate.imag,
                normal_real=split_forces["normal"][j].real,normal_imag=split_forces["normal"][j].imag,
                tangent_real=split_forces["tangent"][j].real,tangent_imag=split_forces["tangent"][j].imag,
                complex_relative_change=abs(delta[j])/max(abs(original[j]),1e-15)))
    pd.DataFrame(rows).to_csv(out/"force_changes.csv",index=False)
    pd.DataFrame(panels).to_csv(out/"panel_pressure_changes.csv",index=False)
    (out/"summary.json").write_text(json.dumps(dict(status="DIAGNOSTIC_ONLY",physical_validation="NOT_PASSED",response_reference_read=False)))
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--grid-level",type=int,choices=(0,1,2))
    parser.add_argument("--body-panels",type=int)
    parser.add_argument("--stations",type=int)
    parser.add_argument("--free-panels",type=int)
    parser.add_argument('--integration-route', choices=('midpoint','analytic_straight_midpoint_curved','reconstructed_symmetric'), default='midpoint')
    a=parser.parse_args()
    run(a.config,a.out,a.grid_level,a.body_panels,a.stations,a.free_panels,a.integration_route)
