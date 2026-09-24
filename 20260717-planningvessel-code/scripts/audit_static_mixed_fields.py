"""Analytic harmonic mixed-boundary solve on saved real section geometry."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from planing_seakeeping.kernels.linear_2p5d.formulation import (
    InnerDomainPanelGeometry, build_control_surface_geometry,
    build_waterline_clipped_free_surface_geometry, _inner_a_matrix, _inner_b_matrix,
    _body_geometry_with_inner_fluid_outward_normal)
from planing_seakeeping.kernels.linear_2p5d.panel_integrals import panel_integration_route


def harmonic(geometry, name):
    y,z=geometry.mid_y_m,geometry.mid_z_down_m
    if name=='linear_z':
        return z,geometry.normal_z
    if name=='quadratic':
        return y*y-z*z,2*y*geometry.normal_y-2*z*geometry.normal_z
    raise ValueError('Unknown analytic potential')


def solve_known_control(body,free,control,name,arc_self_correction=False,arc_order=None,known_data_order=None,reconstruct_known=False,reconstruct_all=False):
    boundaries=(body,free,control)
    phi,qn=zip(*(harmonic(b,name) for b in boundaries))
    blocks,rhs=[],[]
    for i,field in enumerate(boundaries):
        aa=[_inner_a_matrix(field,source,same_boundary=i==j) for j,source in enumerate(boundaries)]
        if arc_self_correction and i==2:
            radius=np.hypot(control.mid_y_m,control.mid_z_down_m)
            aa[2]=aa[2]+np.diag(control.length_m/(2*radius))
        bb=[_inner_b_matrix(field,source,same_boundary=i==j) for j,source in enumerate(boundaries)]
        if arc_order is not None:
            from planing_seakeeping.kernels.linear_2p5d.arc_integrals import circular_arc_integrals
            bb[2],aa[2]=circular_arc_integrals(field,control,order=arc_order,same_boundary=i==2)
        if reconstruct_all:
            from planing_seakeeping.kernels.linear_2p5d.reconstructed_operators import reconstructed_log_operators
            for j,source in enumerate(boundaries):
                bb[j],aa[j]=reconstructed_log_operators(field,source,
                    geometry_kind='circular' if j==2 else 'straight',
                    breaks=() if j==2 else (source.panel_count//2,),
                    same_boundary=i==j,order=arc_order or 32)
        blocks.append(np.hstack([aa[0],-bb[1],-bb[2]]))
        if known_data_order is None:
            rhs.append(bb[0]@qn[0]-aa[1]@phi[1]-aa[2]@phi[2])
        else:
            from scripts.harmonic_boundary_rhs import integrated_known_term
            terms=[integrated_known_term(field,source,name,kind=kind,self_boundary=i==j,order=known_data_order,
                                        sample_values=(qn[0] if j==0 else phi[j]) if reconstruct_known else None)
                   for j,(source,kind) in enumerate(zip(boundaries,('body_flux','free_potential','control_potential')))]
            rhs.append(terms[0]-terms[1]-terms[2])
    matrix,forcing=np.vstack(blocks),np.concatenate(rhs)
    solution=np.linalg.solve(matrix,forcing)
    return solution[:body.panel_count],solution[body.panel_count:body.panel_count+free.panel_count],float(np.linalg.norm(matrix@solution-forcing)/max(np.linalg.norm(forcing),1e-15))


def subdivide_body(body,factor):
    if type(factor) is not int or factor<1:
        raise ValueError('Subdivision factor must be a positive integer')
    if factor==1:
        return body
    nodes=np.column_stack((body.node_y_m,body.node_z_down_m))
    if len(nodes)!=body.panel_count+1:
        raise ValueError('Continuous straight body panels required')
    delta=np.diff(nodes,axis=0)
    if not np.allclose(np.linalg.norm(delta,axis=1),body.length_m,rtol=1e-10,atol=1e-12):
        raise ValueError('Body panels must be straight')
    refined=(nodes[:-1,None,:]+np.arange(factor)[None,:,None]/factor*delta[:,None,:]).reshape(-1,2)
    refined=np.vstack([refined,nodes[-1]])
    mids=(refined[:-1]+refined[1:])/2
    return InnerDomainPanelGeometry(mid_y_m=mids[:,0],mid_z_down_m=mids[:,1],
        normal_y=np.repeat(body.normal_y,factor),normal_z=np.repeat(body.normal_z,factor),
        length_m=np.repeat(body.length_m/factor,factor),node_y_m=refined[:,0],node_z_down_m=refined[:,1])


def run(saved,out,arc_self_correction=False,arc_order=None,control_panels=96,joint_factor=1,known_data_order=None,reconstruct_known=False,reconstruct_all=False):
    if reconstruct_all and (known_data_order is not None or reconstruct_known):
        raise ValueError('All-boundary reconstruction must use its own consistent RHS')
    if reconstruct_known and known_data_order is None:
        raise ValueError('Reconstruction requires known-data quadrature')
    if type(control_panels) is not int or control_panels<4:
        raise ValueError('control_panels must be an integer >= 4')
    if type(joint_factor) is not int or joint_factor not in (1,2,4):
        raise ValueError('joint_factor must be 1, 2 or 4')
    out.mkdir(parents=True,exist_ok=False)
    contract=dict(source_sha256=hashlib.sha256(saved.read_bytes()).hexdigest(),
        driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        arc_self_normal_correction=arc_self_correction,
        arc_order=arc_order,
        reconstructed_all_boundaries=reconstruct_all,
        known_data_order=known_data_order,
        known_data_reconstruction='sample_only_linear' if reconstruct_known else 'analytic_or_constant',
        known_data_helper_sha256=hashlib.sha256(Path('scripts/harmonic_boundary_rhs.py').read_bytes()).hexdigest() if known_data_order is not None else None,
        control_panels=control_panels*joint_factor,joint_factor=joint_factor,
        kernel_hashes={name:hashlib.sha256((Path('planing_seakeeping/kernels/linear_2p5d')/name).read_bytes()).hexdigest()
                       for name in ('formulation.py','panel_integrals.py','arc_integrals.py','boundary_reconstruction.py','reconstructed_operators.py')},
        station_indices=[12,42,80],free_counts=[n*joint_factor for n in (48,72,96)],grading_exponents=[1.,1.5],
        potentials=['linear_z','quadratic'],route='analytic_straight_midpoint_curved',
        normalized_rms_limit=.02,normalization='phi/R^degree, q/R^(degree-1)',
        scope='Static Laplace mixed problem with exact outer Dirichlet data; not transient diffraction validation')
    (out/'contract.json').write_text(json.dumps(contract,indent=2))
    rows,profiles=[],[]
    with np.load(saved) as data, panel_integration_route(contract['route']):
        radius=max(6*np.max(np.abs(data['node_y'])),1.25*np.max(data['node_z']))
        control=build_control_surface_geometry(radius,contract['control_panels'])
        for i in contract['station_indices']:
            body=InnerDomainPanelGeometry(mid_y_m=data['y'][i],mid_z_down_m=data['z'][i],
                normal_y=data['normal_y'][i],normal_z=data['normal_z'][i],length_m=data['length'][i],
                node_y_m=data['node_y'][i],node_z_down_m=data['node_z'][i])
            body=_body_geometry_with_inner_fluid_outward_normal(body)
            body=subdivide_body(body,joint_factor)
            for exponent in contract['grading_exponents']:
                for count in contract['free_counts']:
                    free=build_waterline_clipped_free_surface_geometry(-radius,radius,
                        np.max(np.abs(body.node_y_m)),count,grading_exponent=exponent)
                    for name in contract['potentials']:
                        phi,q,residual=solve_known_control(body,free,control,name,arc_self_correction,arc_order,known_data_order,reconstruct_known,reconstruct_all)
                        exact_phi=harmonic(body,name)[0]
                        exact_q=harmonic(free,name)[1]
                        degree=1 if name=='linear_z' else 2
                        for field,actual,exact,length,scale in [
                            ('body_phi',phi,exact_phi,body.length_m,radius**degree),
                            ('free_q',q,exact_q,free.length_m,radius**(degree-1))]:
                            error=float(np.sqrt(np.sum(length*np.abs(actual-exact)**2)/np.sum(length))/scale)
                            rows.append(dict(station=i,x=data['x'][i],exponent=exponent,count=count,
                                potential=name,field=field,normalized_rms=error,
                                passed=bool(np.isfinite(error) and error<=.02),solve_residual=residual))
                        for j,y in enumerate(free.mid_y_m):
                            profiles.append(dict(station=i,exponent=exponent,count=count,potential=name,
                                y=y,computed_q=q[j],exact_q=exact_q[j]))
    frame=pd.DataFrame(rows)
    frame.to_csv(out/'checks.csv',index=False)
    pd.DataFrame(profiles).to_csv(out/'free_profiles.csv',index=False)
    result=dict(checks=len(frame),passed_count=int(frame.passed.sum()),
        max_normalized_rms=float(frame.normalized_rms.max()),max_solve_residual=float(frame.solve_residual.max()),
        full_diffraction_validation=False)
    (out/'results.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))
    print(frame.groupby(['exponent','field']).normalized_rms.agg(['median','max']).to_string())


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--saved',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--arc-self-correction',action='store_true')
    p.add_argument('--arc-order',type=int,choices=(32,64))
    p.add_argument('--control-panels',type=int,default=96)
    p.add_argument('--joint-factor',type=int,choices=(1,2,4),default=1)
    p.add_argument('--known-data-order',type=int,choices=(32,64))
    p.add_argument('--reconstruct-known',action='store_true')
    p.add_argument('--reconstruct-all',action='store_true')
    a=p.parse_args()
    run(a.saved,a.out,a.arc_self_correction,a.arc_order,a.control_panels,a.joint_factor,a.known_data_order,a.reconstruct_known,a.reconstruct_all)
