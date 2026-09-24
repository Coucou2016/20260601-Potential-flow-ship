import json

import pandas as pd
import pytest

from scripts.verify_refined_kernel_connection import verify


def fixture_data(tmp_path):
    run, grid = tmp_path / "run", tmp_path / "grid"
    run.mkdir()
    grid.mkdir()
    mesh = dict(station_count=113, body_panels_per_section=72,
        free_surface_inner_panels=96, free_surface_outer_panels=120)
    contract = dict(grids=[mesh], history_steps=128,
        history_quadrature_counts_by_grid=[64], history_k_max=25,
        cutoff_quadrature="clipped_linear")
    (grid / "contract.json").write_text(json.dumps(contract))
    (grid / "results.json").write_text(json.dumps(dict(passed=True, checks=240)))
    mesh = dict(mesh, history_steps=128, history_quadrature_count=64,
                history_k_max=25, frequency_sampling="case_frequencies")
    config = dict(mesh=mesh, hydrodynamics=dict(cutoff_quadrature="clipped_linear",
        head_sea_excitation_formulation="matched_domain_incident_diffraction"),
        boat={k: 1 for k in ("rho_water_kg_m3", "length_m", "beam_m", "gravity_m_s2")}, cases=[])
    refs = []
    for case in ("fn167", "fn226", "fn282"):
        directory = run / case
        directory.mkdir()
        config["cases"].append(dict(id=case, encounter_omega_rad_s=list(range(1, 9))))
        matrices, forces = [], []
        for index in range(8):
            omega = index+1
            forces.append(dict(omega_e_rad_s=omega, F3_real=1, F3_imag=2, M5_real=3, M5_imag=4))
            for i in (3, 5):
                for j in (3, 5):
                    matrices.append(dict(frequency_index=index, omega_e_rad_s=omega, i=i, j=j, A=1, B=2))
                    for name, value in (("A", 1), ("B", 2)):
                        refs.append(dict(level=2, case=case, omega=omega, component=f"{name}{i}{j}", real=value, imag=0))
            for name, real, imag in (("F3", 1, 2), ("F5", 3, 4)):
                refs.append(dict(level=2, case=case, omega=omega, component=name, real=real, imag=imag))
        pd.DataFrame(matrices).to_csv(directory / "matrices.csv", index=False)
        pd.DataFrame(forces).to_csv(directory / "excitation.csv", index=False)
    pd.DataFrame(refs).to_csv(grid / "dimensionless_coefficients.csv", index=False)
    (run / "input_snapshot.json").write_text(json.dumps(config))
    return run, grid


def test_connection_checks_all_240_quantities(tmp_path):
    assert verify(*fixture_data(tmp_path)) == 0


def test_modified_coefficient_fails(tmp_path):
    run, grid = fixture_data(tmp_path)
    path = run / "fn167/matrices.csv"
    frame = pd.read_csv(path)
    frame.loc[0, "A"] = 10
    frame.to_csv(path, index=False)
    assert verify(run, grid) == 2


def test_missing_matrix_is_rejected(tmp_path):
    run, grid = fixture_data(tmp_path)
    path = run / "fn167/matrices.csv"
    pd.read_csv(path).iloc[:-1].to_csv(path, index=False)
    with pytest.raises(ValueError, match="Incomplete"):
        verify(run, grid)
