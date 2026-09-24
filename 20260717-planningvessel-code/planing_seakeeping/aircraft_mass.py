"""Consistent synthetic aircraft mass properties, not historical identification."""
import numpy as np


def component_mass_properties(components):
    """Uniform axis-aligned cuboids; all positions share one metre datum.

    I_CG = sum(I_local + m * ((r.r) identity - outer(r,r))).
    Component positions must not be confused with offsets relative to the CG.
    """
    if not components:
        raise ValueError("At least one component is required")
    masses, positions, local = [], [], []
    for c in components:
        m = float(c["mass_kg"])
        p = np.asarray(c["center_m"], dtype=float)
        d = np.asarray(c["dimensions_m"], dtype=float)
        if not c.get("assumption"):
            raise ValueError("Each component needs provenance or an assumption")
        if p.shape != (3,) or d.shape != (3,) or not np.isfinite([m,*p,*d]).all():
            raise ValueError("Finite scalar mass and three-vector geometry required")
        if m <= 0 or np.any(d <= 0):
            raise ValueError("Positive mass and component dimensions required")
        masses.append(m)
        positions.append(p)
        local.append(m/12*np.diag([d[1]**2+d[2]**2,d[0]**2+d[2]**2,d[0]**2+d[1]**2]))
    total = sum(masses)
    cg = np.average(positions, axis=0, weights=masses)
    inertia = np.zeros((3,3))
    for m, p, own in zip(masses,positions,local):
        r=p-cg
        inertia += own+m*(np.dot(r,r)*np.eye(3)-np.outer(r,r))
    eigenvalues=np.linalg.eigvalsh(inertia)
    if not np.isfinite(inertia).all() or eigenvalues[0] <= 0 or eigenvalues[-1] > sum(eigenvalues[:2])+1e-8:
        raise ValueError("Nonphysical inertia tensor")
    return {"mass_kg":total,"cg_m":cg.tolist(),"inertia_cg_kg_m2":inertia.tolist(),
            "principal_inertias_kg_m2":eigenvalues.tolist(),
            "status":"synthetic_component_model_not_measured"}
