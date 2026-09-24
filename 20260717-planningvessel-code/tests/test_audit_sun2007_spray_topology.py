from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.audit_sun2007_spray_topology import main


def test_reuse_existing_spray_trajectories_builds_traceable_manifest(tmp_path: Path) -> None:
    output = tmp_path / "audit"
    output.mkdir()
    row = {
        "motion_dof": "heave",
        "creation_phase_rad": "0.0",
        "creation_phase_deg": "0.0",
        "creation_time_s": "0.0",
        "activation_time_s": "0.0",
        "activation_phase_deg": "0.0",
        "simulated_step_count": "160",
        "simulated_duration_s": "0.25",
        "trajectory_status": "physical_wet_interval_exit",
        "maximum_spray_overturning_panel_count": "0",
        "first_overturning_time_s": "",
        "minimum_spray_outward_tangent_cosine": "0.2",
        "minimum_spray_nonadjacent_distance_ratio": "1.3",
        "final_jet_cut_count": "40",
        "maximum_potential_bvp_relative_residual": "1e-15",
    }
    csv_path = output / "spray_topology_trajectories.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(row))
        writer.writeheader()
        writer.writerow(row)

    exit_code = main(
        [
            "--out",
            str(output),
            "--phase-count",
            "1",
            "--workers",
            "1",
            "--motion-dofs",
            "heave",
            "--reuse-existing-trajectories",
        ]
    )

    assert exit_code == 0
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "NO_SPRAY_CUT_PRECURSOR_IN_SCANNED_TRAJECTORIES"
    assert manifest["trajectory_count"] == 1
    assert manifest["source"]["source_pdf_sha256"]
    assert manifest["response_calibration_used"] is False
