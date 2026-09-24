"""Response-blind decomposition of saved coupled longitudinal systems."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


def decompose(dynamic, incident, diffraction):
    dynamic = np.asarray(dynamic, dtype=complex)
    forces = np.column_stack((incident, diffraction))
    response = np.linalg.solve(dynamic, forces)
    total = np.linalg.solve(dynamic, forces.sum(axis=1))
    if abs(dynamic[0, 0]) < 1e-12 * np.linalg.norm(dynamic):
        raise ValueError("Heave pivot too small for this Schur diagnostic")
    coupling = dynamic[1, 0] / dynamic[0, 0]
    schur = dynamic[1, 1] - coupling * dynamic[0, 1]
    effective_force = forces[1] - coupling * forces[0]
    return response, total, schur, effective_force


def run(source, destination):
    source, destination = Path(source), Path(destination)
    if destination.exists():
        raise ValueError("Use a clean diagnostic directory")
    config_path = source / "input_snapshot.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config["mesh"].get("frequency_sampling") != "case_frequencies":
        raise ValueError("Requires direct case frequencies, not interpolated excitation")
    boat = config["boat"]
    length = boat["length_m"]
    transform = np.diag([1.0, 1.0 / length])
    stiffness_scale = boat["rho_water_kg_m3"] * boat["gravity_m_s2"] * length * boat["beam_m"]
    rows, terms, hashes = [], [], {}
    def read(path):
        hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        return pd.read_csv(path)
    hashes[str(config_path)] = hashlib.sha256(config_path.read_bytes()).hexdigest()
    for case in config["cases"]:
        folder = source / case["id"]
        matrices = read(folder / "matrices.csv")
        saved_response = read(folder / "rao.csv")
        components = [read(folder / f"excitation_component_matched_domain_{name}.csv")
                      for name in ("froude_krylov", "diffraction")]
        for n, omega in enumerate(case["encounter_omega_rad_s"]):
            part = matrices[matrices.frequency_index == n]
            if len(part) != 4 or not np.allclose(part.omega_e_rad_s, omega, rtol=1e-10):
                raise ValueError("Missing or mismatched matrix rows")
            operators = {}
            for name, column, factor in (("rigid_inertia", "M", -omega**2),
                    ("added_inertia", "A", -omega**2), ("radiation", "B", 1j*omega),
                    ("restoring", "C", 1)):
                matrix = part.pivot(index="i", columns="j", values=column).loc[[3,5],[3,5]].to_numpy()
                operators[name] = factor * transform @ matrix @ transform / stiffness_scale
            dynamic = sum(operators.values())
            forces = []
            for frame in components:
                selected = frame[np.isclose(frame.omega_e_rad_s, omega, rtol=1e-10, atol=1e-12)]
                if len(selected) != 1:
                    raise ValueError("Missing or ambiguous excitation frequency")
                v = selected.iloc[0]
                forces.append(transform @ np.array([complex(v.F3_real, v.F3_imag),
                    complex(v.M5_real, v.M5_imag)]) / stiffness_scale)
            response, total, schur, eff = decompose(dynamic, *forces)
            record = saved_response[saved_response.frequency_index == n]
            if len(record) != 1:
                raise ValueError("Missing response row")
            v = record.iloc[0]
            saved = np.array([complex(v.heave_response_real_m_per_m, v.heave_response_imag_m_per_m),
                length*complex(v.pitch_response_real_rad_per_m, v.pitch_response_imag_rad_per_m)])
            residual = np.linalg.norm(total-saved) / max(np.linalg.norm(saved), 1e-15)
            for i, dof in enumerate(("heave", "pitch_times_length")):
                budget = abs(response[i,0]) + abs(response[i,1])
                row = dict(case=case["id"], index=n, omega=omega, dof=dof,
                    incident_response_abs=abs(response[i,0]), diffraction_response_abs=abs(response[i,1]),
                    total_response_abs=abs(total[i]),
                    cancellation_fraction=1-abs(total[i])/budget if budget else 0,
                    reconstruction_relative_residual=residual,
                    smallest_dimensionless_singular_value=np.linalg.svd(dynamic, compute_uv=False)[-1],
                    pitch_schur_abs=abs(schur), effective_pitch_force_abs=abs(eff.sum()),
                    schur_reconstruction_error=abs(eff.sum()/schur-total[1]))
                for label, value in (("incident_response", response[i,0]), ("diffraction_response", response[i,1]),
                        ("pitch_schur", schur), ("effective_pitch_force", eff.sum())):
                    row[label+"_real"], row[label+"_imag"] = value.real, value.imag
                rows.append(row)
                for name, operator in operators.items():
                    for j, coordinate in enumerate(("heave", "pitch_times_length")):
                        value = operator[i,j]*total[j]
                        terms.append(dict(case=case["id"], index=n, omega=omega, equation=dof,
                            term=name, coordinate=coordinate, real=value.real, imag=value.imag))
    destination.mkdir(parents=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(destination / "response_decomposition.csv", index=False)
    pd.DataFrame(terms).to_csv(destination / "equation_terms.csv", index=False)
    (destination / "source_hashes.json").write_text(json.dumps(hashes, indent=2))
    summary = dict(rows=len(frame), response_reference_read=False,
        max_response_reconstruction_residual=float(frame.reconstruction_relative_residual.max()),
        max_schur_reconstruction_error=float(frame.schur_reconstruction_error.max()),
        interpretation="scaled coordinates [heave,L*pitch]; diagnostic only, not independent validation or stability",
        physical_acceptance="NOT_PASSED")
    (destination / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    run(args.run, args.out)
