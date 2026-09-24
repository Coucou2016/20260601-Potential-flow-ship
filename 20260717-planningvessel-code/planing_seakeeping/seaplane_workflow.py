"""Source-based synthetic float workflow, strictly zero-speed reduced order.

This is NOT the matched 2.5D kernel and never changes its historical gates.
It closes a transparent geometry/mass/hydrostatics/linear-motion research case.
"""
from __future__ import annotations

from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import platform
import shutil

import numpy as np
import pandas as pd
import scipy
from scipy.integrate import solve_ivp
from scipy.linalg import eigh
from scipy.optimize import least_squares

from .aircraft_mass import component_mass_properties
from .float_offsets import FloatStation, read_float_offsets
from .config import WaveConfig
from .waves import make_irregular_components

MODEL = "synthetic_float_zero_speed_longitudinal"


def write_json(path, value):
    def convert(item):
        if isinstance(item, np.ndarray):
            return item.tolist()
        if isinstance(item, np.generic):
            return item.item()
        raise TypeError(type(item).__name__)
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False,
                                   allow_nan=False, default=convert), encoding="utf-8")


def load_workflow(path):
    path = Path(path).resolve()
    raw = json.loads(path.read_text(encoding="utf-8"))
    expected = {"model", "base_parameters", "offsets_sha256", "speed_mps", "geometry_closure",
                "subdivisions_per_interval", "added_mass_factor", "modal_damping_ratio",
                "regular_wave_height_m", "regular_wave_period_s", "irregular_hs_m", "irregular_tp_s",
                "irregular_seed", "duration_s", "output_step_s", "assumptions"}
    if set(raw) != expected or raw["model"] != MODEL:
        raise ValueError("Unknown model, missing fields or unsupported workflow fields")
    if raw["speed_mps"] != 0 or raw["geometry_closure"] != "vertical_sides_flat_deck_assumed":
        raise ValueError("Only zero speed and explicitly assumed vertical-side closure are supported")
    for key in expected - {"model", "base_parameters", "offsets_sha256", "geometry_closure", "assumptions"}:
        if isinstance(raw[key], bool) or not isinstance(raw[key], (float, int)) or not np.isfinite(raw[key]):
            raise ValueError(f"{key} must be a finite number")
    for key in ("subdivisions_per_interval", "irregular_seed"):
        if type(raw[key]) is not int or raw[key] < 1:
            raise ValueError(f"{key} must be a positive integer")
    for key in ("added_mass_factor", "modal_damping_ratio", "regular_wave_height_m", "regular_wave_period_s",
                "irregular_hs_m", "irregular_tp_s", "duration_s", "output_step_s"):
        if raw[key] <= 0:
            raise ValueError(f"{key} must be positive")
    if not 0 < raw["modal_damping_ratio"] < 1 or raw["duration_s"] < 40*raw["regular_wave_period_s"]:
        raise ValueError("Need subcritical damping and at least 40 regular-wave cycles")
    if raw["output_step_s"] > min(raw["regular_wave_period_s"]/40, .1):
        raise ValueError("Output interval too large")
    if not isinstance(raw["assumptions"], list) or not raw["assumptions"]:
        raise ValueError("Explicit assumptions required")
    base_path = path.parent/raw["base_parameters"]
    base = json.loads(base_path.read_text(encoding="utf-8"))
    root = Path(__file__).resolve().parents[1]
    offsets = root/base["geometry"]["offsets"]
    if hashlib.sha256(offsets.read_bytes()).hexdigest() != raw["offsets_sha256"]:
        raise ValueError("Offsets hash mismatch")
    env = base["environment_assumed"]
    for key in ("water_density_kg_m3", "air_density_kg_m3", "gravity_m_s2"):
        if not np.isfinite(env[key]) or env[key] <= 0:
            raise ValueError("Invalid environment density/gravity")
    if np.any(np.asarray(env["wind_mps"]) != 0) or np.any(np.asarray(env["current_mps"]) != 0):
        raise ValueError("Wind/current unsupported in the zero-speed closure")
    return raw, base, offsets


class FloatHydrostatics:
    """Section quadrature without averaging across duplicate step stations.

    Source axes: x aft, y starboard, z up. Generalized q: earth CG height,
    bow-up pitch in radians. Exact pitch rotation is used for hydrostatics.
    Vertical sides and a flat deck at the tabulated deck height are assumptions.
    """

    def __init__(self, stations, subdivisions=8):
        self.stations = stations
        self.length = stations[-1].x_aft_m
        # Include every transverse corner, so transverse area integrals are exact.
        self.ratios = np.unique(np.r_[0., 1., [b/s.halfbreadth_m[-1] for s in stations
                    if s.halfbreadth_m[-1] > 0 for b in s.halfbreadth_m]])
        rows = []
        for left, right in zip(stations[:-1], stations[1:]):
            dx = right.x_aft_m-left.x_aft_m
            if dx == 0:
                continue
            for f in (np.arange(subdivisions)+.5)/subdivisions:
                def half(s):
                    return np.full_like(self.ratios, s.height_up_m[0]) if s.halfbreadth_m[-1] == 0 else np.interp(
                        self.ratios*s.halfbreadth_m[-1], s.halfbreadth_m, s.height_up_m)
                rows.append((left.x_aft_m+f*dx, dx/subdivisions,
                             (1-f)*left.halfbreadth_m[-1]+f*right.halfbreadth_m[-1],
                             (1-f)*left.deck_height_m+f*right.deck_height_m,
                             (1-f)*half(left)+f*half(right)))
        self.x = np.array([r[0] for r in rows])
        self.dx = np.array([r[1] for r in rows])
        self.b = np.array([r[2] for r in rows])
        self.deck = np.array([r[3] for r in rows])
        self.bottom = np.array([r[4] for r in rows])
        self.y = self.b[:, None]*self.ratios

    def section_integrals(self, level):
        """Area, first z moment, and waterplane width via clipped trapezoids."""
        level = np.broadcast_to(level, self.x.shape)
        top = np.minimum(level, self.deck)
        z0, z1 = self.bottom[:, :-1], self.bottom[:, 1:]
        dy = np.diff(self.y, axis=1)
        lower, upper = np.minimum(z0, z1), np.maximum(z0, z1)
        h = top[:, None]
        span = upper-lower
        fraction = np.clip(np.divide(h-lower, span, out=np.ones_like(span), where=span>1e-14),0,1)
        fraction = np.where(h <= lower, 0., fraction)
        clipped_upper = lower+fraction*span
        area = dy*fraction*(h-(lower+clipped_upper)/2)
        first = .5*dy*fraction*(h*h-(lower*lower+lower*clipped_upper+clipped_upper**2)/3)
        area = np.maximum(area, 0.)
        width = 2*np.sum(dy*fraction, axis=1)*(level < self.deck)
        return 2*area.sum(axis=1), 2*first.sum(axis=1), width

    def evaluate(self, q, cg, rho, gravity):
        height, pitch = q
        cs, sn = np.cos(pitch), np.sin(pitch)
        if cs < .9:
            raise ValueError("Pitch outside hydrostatic demonstration domain")
        forward = cg[0]-self.x
        level = cg[2]+(-height-sn*forward)/cs
        area, first_z, width = self.section_integrals(level)
        volume = np.dot(area,self.dx)
        moment_volume = np.dot(cs*forward*area-sn*(first_z-cg[2]*area),self.dx)
        x_waterline = cs*forward-sn*(level-cg[2])
        return {"force":rho*gravity*np.array([volume,moment_volume]), "volume":volume,
                "level":level,"width":width,"area":area,"x_waterline":x_waterline,
                "freeboard":cs*(self.deck-level)}

    def equilibrium(self, mass, cg, rho, gravity):
        scale = mass*gravity*np.array([1., self.length])
        def fun(q):
            return (self.evaluate(q,cg,rho,gravity)["force"]-[mass*gravity,0])/scale
        solved=least_squares(fun,[cg[2]-.55,0.],bounds=([-1.,-.25],[3.,.25]),
                             xtol=1e-12,ftol=1e-12,gtol=1e-12,max_nfev=300)
        if not solved.success or np.max(np.abs(fun(solved.x))) > 1e-7:
            raise ValueError("Static equilibrium failed; mass/CG may exceed this geometry's capacity")
        details=self.evaluate(solved.x,cg,rho,gravity)
        if np.min(details["freeboard"]) <= .01:
            raise ValueError("Equilibrium has inadequate assumed-deck freeboard")
        return solved.x,details

    def restoring(self, q, cg, rho, gravity, step=1e-5):
        return -np.column_stack([(self.evaluate(q+np.eye(2)[i]*step,cg,rho,gravity)["force"]-
                                 self.evaluate(q-np.eye(2)[i]*step,cg,rho,gravity)["force"])/(2*step)
                                 for i in range(2)])


def closed_assumed_mesh(stations):
    """Welded source-bottom loft with explicitly assumed sides/deck/step/end caps."""
    ratios=np.unique(np.r_[0.,1.,[b/s.halfbreadth_m[-1] for s in stations
                                 if s.halfbreadth_m[-1]>0 for b in s.halfbreadth_m]])
    signed=np.r_[-ratios[:0:-1],ratios]
    vertices,lookup,rings=[],{},[]
    for s in stations:
        y=signed*s.halfbreadth_m[-1]
        z=np.full_like(y,s.height_up_m[0]) if s.halfbreadth_m[-1] == 0 else np.interp(np.abs(y),s.halfbreadth_m,s.height_up_m)
        ring=[]
        for point in list(zip(np.full_like(y,s.x_aft_m),y,z))+[(s.x_aft_m,y[-1],s.deck_height_m),(s.x_aft_m,y[0],s.deck_height_m)]:
            key=tuple(np.round(point,12))
            if key not in lookup:
                lookup[key]=len(vertices)
                vertices.append(point)
            ring.append(lookup[key])
        rings.append(ring)
    vertices=np.asarray(vertices)
    faces,tags=[],[]
    def add(f,kind):
        p=vertices[list(f)]
        if len(set(f))==3 and np.linalg.norm(np.cross(p[1]-p[0],p[2]-p[0]))>1e-13:
            faces.append(f)
            tags.append(kind)
    for i,(r,s) in enumerate(zip(rings[:-1],rings[1:])):
        step=stations[i].x_aft_m==stations[i+1].x_aft_m
        for j in range(len(r)):
            k=(j+1)%len(r)
            tag=1 if step or j>=len(signed)-1 else 0
            add((r[j],s[j],r[k]),tag)
            add((r[k],s[j],s[k]),tag)
    # Interior fan retains collinear bottom-edge subdivisions on a flat stern.
    for r,reverse in ((rings[0],False),(rings[-1],True)):
        if len(set(r)) < 3:
            continue
        center=np.mean(vertices[list(dict.fromkeys(r))],axis=0)
        center_index=len(vertices)
        vertices=np.vstack([vertices,center])
        for j in range(len(r)):
            k=(j+1)%len(r)
            add((center_index,r[k],r[j]) if reverse else (center_index,r[j],r[k]),1)
    # At step tops the wider deck edge must share the narrower deck's vertices.
    # Split collinear boundary edges instead of adding zero-area cover triangles.
    counts=Counter(tuple(sorted((a,b))) for f in faces for a,b in zip(f,np.roll(f,-1)))
    boundary_vertices=sorted({v for edge,count in counts.items() if count==1 for v in edge})
    refined,refined_tags=[],[]
    for face,tag in zip(faces,tags):
        pieces=[face]
        for a,b in zip(face,np.roll(face,-1)):
            if counts[tuple(sorted((a,b)))] != 1:
                continue
            direction=vertices[b]-vertices[a]
            scale=np.dot(direction,direction)
            inside=[]
            for point in boundary_vertices:
                t=np.dot(vertices[point]-vertices[a],direction)/scale
                if 1e-10<t<1-1e-10 and np.linalg.norm(vertices[point]-vertices[a]-t*direction)<1e-10:
                    inside.append((t,point))
            if inside:
                target=next(p for p in pieces if a in p and b in p)
                other=next(v for v in target if v not in (a,b))
                pieces.remove(target)
                chain=[a]+[p for _,p in sorted(inside)]+[b]
                pieces.extend((chain[i],chain[i+1],other) for i in range(len(chain)-1))
        refined.extend(pieces)
        refined_tags.extend([tag]*len(pieces))
    faces=np.asarray(refined,dtype=int)
    signed_volume=np.einsum("ij,ij->i",vertices[faces[:,0]],np.cross(vertices[faces[:,1]],vertices[faces[:,2]])).sum()/6
    if signed_volume<0:
        faces=faces[:,::-1]
    return vertices,faces,np.asarray(refined_tags)


def mesh_audit(vertices, faces):
    counts=Counter(tuple(sorted((int(a),int(b)))) for f in faces for a,b in zip(f,np.roll(f,-1)))
    directed=Counter((int(a),int(b)) for f in faces for a,b in zip(f,np.roll(f,-1)))
    volume=np.einsum("ij,ij->i",vertices[faces[:,0]],np.cross(vertices[faces[:,1]],vertices[faces[:,2]])).sum()/6
    return {"boundary_edges":sum(v==1 for v in counts.values()),"nonmanifold_edges":sum(v>2 for v in counts.values()),
            "orientation_errors":sum(directed[(a,b)]!=directed[(b,a)] for a,b in counts),"volume_m3":float(volume)}


def refine_stations(stations, subdivisions):
    ratios=FloatHydrostatics(stations,1).ratios
    result=[]
    for left,right in zip(stations[:-1],stations[1:]):
        result.append(left)
        if left.x_aft_m==right.x_aft_m:
            continue
        for fraction in np.arange(1,subdivisions)/subdivisions:
            breadth=(1-fraction)*left.halfbreadth_m[-1]+fraction*right.halfbreadth_m[-1]
            def profile(s):
                return np.full_like(ratios,s.height_up_m[0]) if s.halfbreadth_m[-1]==0 else np.interp(
                    ratios*s.halfbreadth_m[-1],s.halfbreadth_m,s.height_up_m)
            result.append(FloatStation(f"interpolated_{len(result)}",(1-fraction)*left.x_aft_m+fraction*right.x_aft_m,
                breadth*ratios,(1-fraction)*profile(left)+fraction*profile(right),
                (1-fraction)*left.deck_height_m+fraction*right.deck_height_m))
    return result+[stations[-1]]


def earth_vertices(vertices, cg, q):
    forward=cg[0]-vertices[:,0]
    up=vertices[:,2]-cg[2]
    c,s=np.cos(q[1]),np.sin(q[1])
    return np.column_stack((c*forward-s*up,-vertices[:,1],q[0]+s*forward+c*up))


def hydrostatic_pressure_check(vertices,faces,cg,q,rho,gravity):
    """Independent clipped-face pressure integration in earth x-forward/y-port/z-up.

    Positive generalized pitch is bow-up = -My. Rotation preserves orientation.
    Pressure is exactly linear with depth on each planar triangular face.
    """
    points=earth_vertices(vertices,cg,q)
    force=np.zeros(3)
    moment=0.
    for face in faces:
        polygon=points[face]
        clipped=[]
        for a,b in zip(polygon,np.roll(polygon,-1,axis=0)):
            if a[2]<=0:
                clipped.append(a)
            if (a[2]<0<b[2]) or (b[2]<0<a[2]):
                clipped.append(a+(b-a)*(-a[2]/(b[2]-a[2])))
        for i in range(1,len(clipped)-1):
            p=np.array([clipped[0],clipped[i],clipped[i+1]])
            normal_area=.5*np.cross(p[1]-p[0],p[2]-p[0])
            force+=rho*gravity*p[:,2].mean()*normal_area
            x,z=p[:,0],p[:,2]
            mean_xz=(x.sum()*z.sum()+np.dot(x,z))/12
            mean_z2=(z.sum()**2+np.dot(z,z))/12
            # Moments about CG, not the earth waterplane origin.
            mean_cg_z_times_z=mean_z2-q[0]*z.mean()
            moment+=rho*gravity*(normal_area[2]*mean_xz-normal_area[0]*mean_cg_z_times_z)
    return force,moment


def build_model(hydro, base, raw):
    mass=component_mass_properties(base["mass_components"])
    cg=np.asarray(mass["cg_m"])
    rho=base["environment_assumed"]["water_density_kg_m3"]
    gravity=base["environment_assumed"]["gravity_m_s2"]
    q,static=hydro.equilibrium(mass["mass_kg"],cg,rho,gravity)
    c=hydro.restoring(q,cg,rho,gravity)
    # Do not silently symmetrize an erroneous restoring matrix.
    if np.max(np.abs(c-c.T))/np.max(np.abs(c))>1e-4 or np.linalg.eigvalsh(c).min()<=0:
        raise ValueError("Invalid longitudinal restoring matrix")
    n=np.column_stack((np.ones_like(hydro.x),static["x_waterline"]))
    strip_mass=raw["added_mass_factor"]*.5*np.pi*rho*(static["width"]/2)**2*hydro.dx
    a=n.T@(strip_mass[:,None]*n)
    m=np.diag([mass["mass_kg"],mass["inertia_cg_kg_m2"][1][1]])
    m_eff=m+a
    values,phi=eigh(c,m_eff)
    damping=m_eff@phi@np.diag(2*raw["modal_damping_ratio"]*np.sqrt(values))@phi.T@m_eff
    bow=hydro.stations[0]
    bow_lever=np.cos(q[1])*(cg[0]-bow.x_aft_m)-np.sin(q[1])*(bow.height_up_m[0]-cg[2])
    return {"mass":mass,"cg":cg,"rho":rho,"g":gravity,"q0":q,"static":static,
            "M":m,"A":a,"B":damping,"C":c,"Meff":m_eff,"n":n,"hydro":hydro,
            "natural_periods_s":2*np.pi/np.sqrt(values),"bow_x_at_equilibrium_m":bow_lever}


def excitation(model, omega):
    """Hydrostatic wave-elevation forcing only, no claimed diffraction solution."""
    k=np.asarray(omega)**2/model["g"]
    weight=model["rho"]*model["g"]*model["static"]["width"]*model["hydro"].dx/np.cos(model["q0"][1])
    return (np.exp(1j*k[:,None]*model["static"]["x_waterline"]) * weight) @ model["n"]


def transfer(model, omega):
    f=excitation(model,omega)
    d=np.array([model["C"]-w*w*model["Meff"]+1j*w*model["B"] for w in omega])
    return np.linalg.solve(d,f[...,None])[...,0],f


def simulate(model, time, omega, amplitudes, phases, initial=None, max_step=.05):
    omega=np.asarray(omega)
    forcing=excitation(model,omega)*np.asarray(amplitudes)[:,None]*np.exp(1j*np.asarray(phases)[:,None])
    inverse=np.linalg.inv(model["Meff"])
    def force(t):
        return np.real(np.exp(1j*omega*t)@forcing)
    def rhs(t,state):
        return np.r_[state[2:],inverse@(force(t)-model["B"]@state[2:]-model["C"]@state[:2])]
    initial=np.zeros(4) if initial is None else np.asarray(initial)
    solved=solve_ivp(rhs,(time[0],time[-1]),initial,t_eval=time,rtol=2e-9,atol=1e-11,max_step=max_step)
    if not solved.success or not np.isfinite(solved.y).all():
        raise RuntimeError("Time integration failed")
    q,v=solved.y[:2].T,solved.y[2:].T
    forces=np.real(np.exp(1j*time[:,None]*omega)@forcing)
    acceleration=(forces-v@model["B"].T-q@model["C"].T)@inverse.T
    energy=.5*np.einsum("ni,ij,nj->n",q,model["C"],q)+.5*np.einsum("ni,ij,nj->n",v,model["Meff"],v)
    wave=np.real(np.exp(1j*(time[:,None]*omega+np.asarray(phases)))@np.asarray(amplitudes))
    return pd.DataFrame({"time_s":time,"wave_m":wave,"surge_m":0.,"sway_m":0.,"heave_m":q[:,0],
        "roll_rad":0.,"pitch_rad":q[:,1],"yaw_rad":0.,"heave_velocity_mps":v[:,0],"pitch_rate_rad_s":v[:,1],
        "cg_accel_mps2":acceleration[:,0],"bow_accel_mps2":acceleration[:,0]+model["bow_x_at_equilibrium_m"]*acceleration[:,1],
        "energy_J":energy,"force_heave_N":forces[:,0],"force_pitch_Nm":forces[:,1]})


def run_workflow(config_path, out_dir):
    raw,base,offsets=load_workflow(config_path)
    out=Path(out_dir).resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError("Use a clean output directory; previous results are immutable")
    out.mkdir(parents=True,exist_ok=True)
    write_json(out/"input_snapshot.json",{"workflow":raw,"base":base})
    shutil.copy2(offsets,out/"source_offsets_inches.csv")
    write_json(out/"parameter_usage.json",{
        "used_base_fields":["geometry.offsets","mass_components","environment_assumed.water_density_kg_m3","environment_assumed.gravity_m_s2"],
        "constrained_to_zero":["speed_mps","environment_assumed.wind_mps","environment_assumed.current_mps"],
        "not_used_in_zero_speed_workflow":["prescribed_entry_assumed","aerodynamics_assumed","propulsion_assumed","sensitivity_assumed"],
        "reason":"No air-relative motion, propulsion or free-entry simulation; separate workflow spectrum and sensitivity settings apply."})
    stations=read_float_offsets(offsets)
    hydro=FloatHydrostatics(stations,raw["subdivisions_per_interval"])
    model=build_model(hydro,base,raw)
    vertices,faces,kinds=closed_assumed_mesh(refine_stations(stations,raw["subdivisions_per_interval"]))
    np.savez(out/"geometry.npz",vertices_m=vertices,triangles=faces,face_kind=kinds)
    mesh=mesh_audit(vertices,faces)
    mass=model["mass"]["mass_kg"]
    weight=mass*model["g"]
    equilibrium={"cg_height_m":model["q0"][0],"pitch_rad":model["q0"][1],"volume_m3":model["static"]["volume"],
                 "force_residual_rel":abs(model["static"]["force"][0]-weight)/weight,
                 "moment_residual_rel":abs(model["static"]["force"][1])/(weight*hydro.length),
                 "min_freeboard_m":model["static"]["freeboard"].min()}
    saved={k:model[k] for k in ("mass","M","A","B","C","natural_periods_s","bow_x_at_equilibrium_m")}
    saved.update(equilibrium=equilibrium,assumptions=raw["assumptions"],model=MODEL,mesh=mesh)
    write_json(out/"model.json",saved)
    pd.DataFrame({"x_aft_m":hydro.x,"integration_dx_m":hydro.dx,"waterline_height_source_m":model["static"]["level"],
        "submerged_area_m2":model["static"]["area"],"waterplane_width_m":model["static"]["width"]}).to_csv(out/"hydrostatic_sections.csv",index=False)
    time=np.linspace(0,raw["duration_s"],int(round(raw["duration_s"]/raw["output_step_s"]))+1)
    w=np.array([2*np.pi/raw["regular_wave_period_s"]])
    amplitude=np.array([raw["regular_wave_height_m"]/2])
    regular=simulate(model,time,w,amplitude,[0.],max_step=raw["output_step_s"])
    regular.to_csv(out/"regular.csv",index=False)
    decay=simulate(model,time,np.array([]),[],[],initial=[.01,.002,0,0],max_step=raw["output_step_s"])
    decay.to_csv(out/"decay.csv",index=False)
    wave_config=WaveConfig(significant_height_m=raw["irregular_hs_m"],peak_period_s=raw["irregular_tp_s"],
                           period_min_s=1.2,period_max_s=10.,component_count=48,seed=raw["irregular_seed"],spectrum="jonswap")
    components=make_irregular_components(wave_config,0,model["g"])
    irregular=simulate(model,time,components.omega0,components.amplitude,components.phase,max_step=raw["output_step_s"])
    irregular.to_csv(out/"irregular.csv",index=False)
    pd.DataFrame({"omega_rad_s":components.omega0,"amplitude_m":components.amplitude,"phase_rad":components.phase,
                  "wavenumber_per_m":components.wavenumber}).to_csv(out/"wave_components.csv",index=False)
    periods=np.linspace(1.2,8.,120)
    response,loads=transfer(model,2*np.pi/periods)
    pd.DataFrame({"period_s":periods,"heave_m_per_m":abs(response[:,0]),"pitch_rad_per_m":abs(response[:,1]),
        "heave_phase_deg":np.rad2deg(np.angle(response[:,0])),"pitch_phase_deg":np.rad2deg(np.angle(response[:,1])),
        "force_heave_real_N_per_m":loads[:,0].real,"force_heave_imag_N_per_m":loads[:,0].imag,
        "force_pitch_real_Nm_per_m":loads[:,1].real,"force_pitch_imag_Nm_per_m":loads[:,1].imag}).to_csv(out/"rao.csv",index=False)

    # Limits are declared here before evaluation and not adapted to output values.
    checks=[]
    def check(name,value,limit):
        checks.append({"name":name,"value":float(value),"limit":float(limit),
                       "passed":bool(np.isfinite(value) and value <= limit)})
    check("boundary_edges",mesh["boundary_edges"],0)
    check("nonmanifold_edges",mesh["nonmanifold_edges"],0)
    check("orientation_errors",mesh["orientation_errors"],0)
    check("positive_closed_volume_violation",mesh["volume_m3"]<=0,0)
    check("positive_effective_mass_violation",np.linalg.eigvalsh(model["Meff"]).min()<=0,0)
    check("positive_restoring_violation",np.linalg.eigvalsh(model["C"]).min()<=0,0)
    check("passive_damping_violation",np.linalg.eigvalsh(model["B"]).min()<0,0)
    state_matrix=np.block([[np.zeros((2,2)),np.eye(2)],
                          [-np.linalg.solve(model["Meff"],model["C"]),-np.linalg.solve(model["Meff"],model["B"]) ]])
    check("unstable_eigenvalue_violation",np.linalg.eigvals(state_matrix).real.max()>=0,0)
    pressure_force,pressure_moment=hydrostatic_pressure_check(vertices,faces,model["cg"],model["q0"],model["rho"],model["g"])
    check("independent_pressure_buoyancy_relative",abs(pressure_force[2]-weight)/weight,.002)
    check("independent_pressure_pitch_relative",abs(pressure_moment)/(weight*hydro.length),.002)
    check("independent_pressure_horizontal_relative",np.linalg.norm(pressure_force[:2])/weight,.002)
    check("force_equilibrium_relative",equilibrium["force_residual_rel"],1e-6)
    check("moment_equilibrium_relative",equilibrium["moment_residual_rel"],1e-6)
    check("restoring_asymmetry",np.max(abs(model["C"]-model["C"].T))/np.max(abs(model["C"])),1e-4)
    half_c=hydro.restoring(model["q0"],model["cg"],model["rho"],model["g"],step=5e-6)
    check("restoring_derivative_step_change",np.linalg.norm(half_c-model["C"])/np.linalg.norm(model["C"]),.001)
    check("free_decay_energy_increase_relative",max(0.,np.diff(decay.energy_J).max())/decay.energy_J.iloc[0],1e-7)
    fine=build_model(FloatHydrostatics(stations,raw["subdivisions_per_interval"]*2),base,raw)
    finer=build_model(FloatHydrostatics(stations,raw["subdivisions_per_interval"]*4),base,raw)
    grid=[]
    for candidate,label in ((model,"coarse"),(fine,"medium"),(finer,"fine")):
        rr,_=transfer(candidate,2*np.pi/periods)
        grid.append({"level":label,"station_count":len(candidate["hydro"].x),"q0":candidate["q0"],
                     "C":candidate["C"],"A":candidate["A"],"response_real":rr.real,"response_imag":rr.imag})
    write_json(out/"grid_study.json",grid)
    for key in ("C","A"):
        scale=np.sqrt(np.outer(np.diag(finer[key]),np.diag(finer[key])))
        check("fine_grid_scaled_"+key,np.max(abs(fine[key]-finer[key])/scale),.02)
    fine_r,_=transfer(fine,2*np.pi/periods)
    finer_r,_=transfer(finer,2*np.pi/periods)
    check("fine_grid_response_change",np.max(abs(fine_r-finer_r)/np.maximum(abs(finer_r),.02)),.02)
    half=simulate(model,time,w,amplitude,[0.],max_step=raw["output_step_s"]/2)
    check("time_step_change",np.max(abs(half[["heave_m","pitch_rad"]].values-regular[["heave_m","pitch_rad"]].values)),1e-5)
    exact,_=transfer(model,w)
    selected=time >= .75*time[-1]
    design=np.column_stack([np.cos(w[0]*time[selected]),np.sin(w[0]*time[selected]),np.ones(selected.sum())])
    fit=np.linalg.lstsq(design,regular.loc[selected,["heave_m","pitch_rad"]].values,rcond=None)[0]
    measured=fit[0]-1j*fit[1]
    expected=exact[0]*amplitude[0]
    check("time_frequency_amplitude_error",np.max(abs(abs(measured)/abs(expected)-1)),.01)
    check("time_frequency_phase_error_deg",np.max(abs(np.rad2deg(np.angle(measured/expected)))),1.)
    check("spectrum_hs_relative_error",abs(4*np.sqrt(.5*np.sum(components.amplitude**2))/raw["irregular_hs_m"]-1),1e-12)
    repeat=make_irregular_components(wave_config,0,model["g"])
    check("random_seed_reproduction_error",np.max(abs(repeat.phase-components.phase)),0)
    long_wave,_=transfer(model,np.array([1e-5]))
    check("uniform_long_wave_heave_error",abs(long_wave[0,0]-1),1e-5)
    check("uniform_long_wave_pitch_rad_per_m",abs(long_wave[0,1]),1e-5)
    # A conservative small-motion screen, not an experimental validity certificate.
    for name,table in (("regular",regular),("irregular",irregular),("decay",decay)):
        excursion=abs(table.heave_m.values[:,None]+table.pitch_rad.values[:,None]*model["static"]["x_waterline"])
        check(name+"_max_vertical_excursion_m",np.max(excursion),.10)
        check(name+"_max_pitch_deg",np.rad2deg(abs(table.pitch_rad).max()),3.)
    sensitivity=[]
    for name,mfactor,shift,amult,zmult in (("baseline",1,0,1,1),("mass_low",.8,0,1,1),
            ("mass_high",1.2,0,1,1),("payload_forward",1,-.3,1,1),("payload_aft",1,.3,1,1),
            ("added_mass_low",1,0,.75,1),("added_mass_high",1,0,1.25,1),
            ("damping_low",1,0,1,2/3),("damping_high",1,0,1,1.5)):
        afactor=raw["added_mass_factor"]*amult
        zeta=raw["modal_damping_ratio"]*zmult
        candidate_base=copy.deepcopy(base)
        candidate_raw=copy.deepcopy(raw)
        candidate_raw.update(added_mass_factor=afactor,modal_damping_ratio=zeta)
        for part in candidate_base["mass_components"]:
            part["mass_kg"]*=mfactor
            if part["name"]=="payload_fuel":
                part["center_m"][0]+=shift
        candidate=build_model(hydro,candidate_base,candidate_raw)
        r,_=transfer(candidate,components.omega0)
        amp=components.amplitude[:,None]*r
        rms=np.sqrt(.5*np.sum(abs(amp)**2,axis=0))
        acceleration_rms=np.sqrt(.5*np.sum(abs(amp[:,0]*components.omega0**2)**2))
        sensitivity.append({"case":name,"mass_kg":candidate["mass"]["mass_kg"],"heave_rms_m":rms[0],
                            "pitch_rms_rad":rms[1],"cg_accel_rms_mps2":acceleration_rms,
                            "rms_method":"ensemble_spectral_not_single_record","added_mass_factor":afactor,"damping_ratio":zeta})
    pd.DataFrame(sensitivity).to_csv(out/"sensitivity.csv",index=False)
    status={"numerical_status":"PASS" if all(c["passed"] for c in checks) else "FAIL",
            "physical_validation_status":"NOT_VALIDATED","overall_project_status":"NOT_COMPLETE", "production":False,
            "model":MODEL,"speed_mps":0.,"checks":checks,
            "dof_status":{"heave":"solved","pitch":"solved","surge":"constrained","sway":"constrained","roll":"constrained","yaw":"constrained"}}
    write_json(out/"acceptance.json",status)
    write_json(out/"environment.json",{"python":platform.python_version(),"numpy":np.__version__,"scipy":scipy.__version__})
    paths=[Path(config_path).resolve(),Path(config_path).resolve().parent/raw["base_parameters"],
           Path(__file__),offsets,Path(__file__).with_name("float_offsets.py"),Path(__file__).with_name("aircraft_mass.py"),
           Path(__file__).with_name("waves.py"),Path(__file__).with_name("seaplane_workflow_report.py"),
           Path(__file__).with_name("seaplane_workflow_animation.py"),Path(__file__).with_name("cli.py")]
    write_json(out/"source_hashes.json",{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    from .seaplane_workflow_report import write_report
    write_report(out)
    from .seaplane_workflow_animation import write_animation
    write_animation(out)
    print(f"Numerical workflow: {status['numerical_status']}; physical validation: NOT_VALIDATED; report: {out/'report.html'}")
    return 0 if status["numerical_status"]=="PASS" else 2
