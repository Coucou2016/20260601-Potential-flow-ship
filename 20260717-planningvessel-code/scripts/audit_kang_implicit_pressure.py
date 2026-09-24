"""Saved implicit-field pressure replay and fixed-space chain-rule diagnostic."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from scripts.curved_trace_pressure_diagnostic import recover_gradient
from scripts.integrated_trace_transport import integrated_fixed_space_derivative
from scripts.audit_kang_contact_trace import endpoint_trace
from scripts.kang_reference_geometry import half_breadth


def run(directory,out):
    contract=json.loads((directory/'contract.json').read_text())
    if (contract['exposure_policy']!='bounded_nearest_unvalidated'
            or contract['history_policy']!='full'
            or contract.get('panel_integration')!='analytic_straight_midpoint_curved'):
        raise ValueError('Complete-history bounded candidate with analytic straight panels required')
    if contract.get('body_neumann_convention') != 'fluid_domain_outward_diffraction_minus_incident':
        raise ValueError('Explicit corrected body Neumann convention required; legacy pressure audit is not admissible')
    out.mkdir(parents=True,exist_ok=False)
    files=[Path(__file__),Path(__file__).with_name('curved_trace_pressure_diagnostic.py'),
           Path(__file__).with_name('integrated_trace_transport.py'),
           Path(__file__).with_name('audit_kang_contact_trace.py'),
           Path(__file__).with_name('kang_reference_geometry.py'),
           directory/'contract.json',directory/'fields.npz']
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    (out/'contract.json').write_text(json.dumps(dict(stage_acceptance=False,hashes=hashes,
        algebra_tolerance=1e-10,experimental_response_read=False,
        scope='Same saved potential, not a new diffraction solve or conservative pressure method',
        policy='Subtract moving-trace chain term from saved phase-based derivative only'),indent=2))
    rho,g=1000.,9.80665
    speed=contract['speed_m_s']; omega=contract['omega_e_sqrt_L_g']*np.sqrt(g/3)
    omega0=2*omega/(1+np.sqrt(1+4*speed*omega/g)); k=omega0**2/g
    with np.load(directory/'fields.npz') as data:
        x,phi=data['x_m'],data['phi']
        time=(x[-1]-x)/speed
        errors={}
        def relative(a,b):
            return float(np.linalg.norm(a-b)/max(np.linalg.norm(b),1e-30))
        errors['phase']=relative(phi,data['psi']*np.exp(-1j*omega*time[:,None]))
        original=-rho*1j*omega*phi+rho*speed*data['pressure_gradient']
        errors['pressure']=relative(original,data['pressure'])
        measure=-data['normal_z']*data['length']
        def integrate(pressure):
            heave=np.sum(pressure*measure,axis=1)
            density=np.c_[heave,heave*(1.5-x)]
            return np.trapezoid(density,x,axis=0),density
        original_force,original_density=integrate(original)
        errors['force']=relative(original_force,data['diffraction'])
        if not np.isfinite(list(errors.values())).all() or max(errors.values())>1e-10:
            raise ValueError('Saved pressure/phase/load replay failed')
        incident_phi=1j*g/omega0*np.exp(-k*data['z_down'])*np.exp(1j*k*(x[:,None]-1.5))
        # Gradient recovery uses the stored hull-outward normal, opposite to
        # the fluid-domain outward derivative passed to the matched solve.
        qn=k*incident_phi*data['normal_z']
        recovered=recover_gradient(x,data['y'],data['z_down'],phi,qn,data['normal_y'],data['normal_z'])
        corrected=original-rho*speed*recovered['chain']
        corrected_force,corrected_density=integrate(corrected)
        total=corrected_force+data['incident']
        half=half_breadth(x,0.,3.,.3,.1875)
        half_x=np.gradient(half,x,edge_order=2)
        contact_sum=np.empty(len(x),complex)
        for i in range(len(x)):
            contacts=[]
            for sign in (-1,1):
                selected=sign*data['y'][i]>0
                distance=np.hypot(data['y'][i,selected]-sign*half[i],data['z_down'][i,selected])
                contacts.append(endpoint_trace(distance,phi[i,selected]))
            contact_sum[i]=sum(contacts)
        edge_flux=-half_x*contact_sum
        yx=np.gradient(data['y'],x,axis=0,edge_order=2)
        zx=np.gradient(data['z_down'],x,axis=0,edge_order=2)
        shape_flux=np.sum(recovered['grad_z']*(-zx*data['normal_z']-yx*data['normal_y'])*data['length'],axis=1)
        section_potential=np.sum(phi*measure,axis=1)
        transport=integrated_fixed_space_derivative(x,section_potential,edge_flux,shape_flux,1.5)
        integrated_force=(-rho*1j*omega*np.trapezoid(np.c_[section_potential,section_potential*(1.5-x)],x,axis=0)
                          +rho*speed*transport)
        integrated_total=integrated_force+data['incident']
        norm=rho*g*(29144/51975*3*.3*.1875)/np.array([3.,1.])
        np.savez_compressed(out/'pressure.npz',x_m=x,original_pressure=original,
            corrected_pressure=corrected,original_density=original_density,corrected_density=corrected_density,
            original_diffraction=original_force,corrected_diffraction=corrected_force,
            original_total=data['total'],corrected_total=total,
            integrated_diffraction=integrated_force,integrated_total=integrated_total,
            waterline_flux=edge_flux,shape_flux=shape_flux,section_potential=section_potential,
            phase_differencing_gap=recovered['material']-data['pressure_gradient'],**recovered)
        summary=dict(stage_acceptance=False,algebra_replay=errors,
            corrected_total_amplitude=(abs(total)/norm).tolist(),
            original_total_amplitude=(abs(data['total'])/norm).tolist(),
            diffraction_complex_change=(abs(corrected_force-original_force)/np.maximum(abs(original_force),1e-30)).tolist(),
            total_complex_change=(abs(total-data['total'])/np.maximum(abs(data['total']),1e-30)).tolist(),
            integrated_total_amplitude=(abs(integrated_total)/norm).tolist(),
            integrated_vs_chain_diffraction_change=(abs(integrated_force-corrected_force)/np.maximum(abs(corrected_force),1e-30)).tolist(),
            modes=['heave','geometric_midship_pitch'],production_changed=False,
            limitations=['Midpoint curved tangent differentiation','One-sided derivatives at tip and keel',
                         'Not a new solved potential','No independent complex reference',
                         'Integrated transport uses extrapolated waterline potentials and discrete geometry derivatives'])
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args(); run(args.run,args.out)
