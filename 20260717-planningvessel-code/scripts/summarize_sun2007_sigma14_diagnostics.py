from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class Candidate:
    name: str
    relative_csv: str
    reference_variant: str
    section_planes: int
    body_panels: int
    bem_substeps: int
    pressure_interpolation: str
    transom_correction: bool
    fixed_jet_threshold_over_beam: float | None
    role: str


CANDIDATES = (
    Candidate(
        "formal_legacy_constant_pressure",
        "outputs/sun2007_forced_motion_sigma14_full_matrix_artificial_handoff_0p8B_short/identified_coefficients.csv",
        "sun_2dt_without_stern_3d_correction",
        11,
        12,
        8,
        "constant_panel",
        False,
        None,
        "current_formal_checkpoint",
    ),
    Candidate(
        "coarse_legacy_constant_pressure",
        "outputs/sun2007_sigma14_constant_panel_pressure_coarse_heave/identified_coefficients.csv",
        "sun_2dt_without_stern_3d_correction",
        11,
        8,
        4,
        "constant_panel",
        False,
        None,
        "single_variable_control",
    ),
    Candidate(
        "coarse_linear_node_pressure",
        "outputs/sun2007_sigma14_linear_node_pressure_coarse_heave/identified_coefficients.csv",
        "sun_2dt_without_stern_3d_correction",
        11,
        8,
        4,
        "match_potential",
        False,
        None,
        "excluded_pressure_candidate",
    ),
    Candidate(
        "coarse_transom_correction",
        "outputs/sun2007_sigma14_constant_panel_transom_correction_coarse_heave/identified_coefficients.csv",
        "sun_2dt_with_stern_3d_correction",
        11,
        8,
        4,
        "constant_panel",
        True,
        None,
        "source_transom_correction_probe",
    ),
    Candidate(
        "coarse_sections_15",
        "outputs/sun2007_sigma14_constant_panel_sections15_coarse_heave/identified_coefficients.csv",
        "sun_2dt_without_stern_3d_correction",
        15,
        8,
        4,
        "constant_panel",
        False,
        None,
        "section_count_convergence_probe",
    ),
    Candidate(
        "coarse_fixed_physical_jet_threshold",
        "outputs/sun2007_sigma14_fixed_jet_0p03326B_coarse_heave/identified_coefficients.csv",
        "sun_2dt_without_stern_3d_correction",
        11,
        8,
        4,
        "constant_panel",
        False,
        0.03325555538987225,
        "fixed_scale_grid_independence_probe",
    ),
    Candidate(
        "body16_sub8_fixed_physical_jet_threshold",
        "outputs/sun2007_sigma14_fixed_jet_body16_sub8_heave/identified_coefficients.csv",
        "sun_2dt_without_stern_3d_correction",
        11,
        16,
        8,
        "constant_panel",
        False,
        0.03325555538987225,
        "formal_candidate",
    ),
    Candidate(
        "body20_sub8_fixed_physical_jet_threshold",
        "outputs/sun2007_sigma14_fixed_jet_body20_sub8_heave/identified_coefficients.csv",
        "sun_2dt_without_stern_3d_correction",
        11,
        20,
        8,
        "constant_panel",
        False,
        0.03325555538987225,
        "panel_refinement_candidate",
    ),
    Candidate(
        "body24_sub8_fixed_physical_jet_threshold",
        "outputs/sun2007_sigma14_fixed_jet_body24_sub8_heave/identified_coefficients.csv",
        "sun_2dt_without_stern_3d_correction",
        11,
        24,
        8,
        "constant_panel",
        False,
        0.03325555538987225,
        "panel_refinement_candidate",
    ),
    Candidate(
        "body24_sub16_fixed_physical_jet_threshold",
        "outputs/sun2007_sigma14_fixed_jet_body24_sub16_heave/identified_coefficients.csv",
        "sun_2dt_without_stern_3d_correction",
        11,
        24,
        16,
        "constant_panel",
        False,
        0.03325555538987225,
        "time_refinement_candidate",
    ),
    Candidate(
        "body24_sub32_fixed_physical_jet_threshold",
        "outputs/sun2007_sigma14_fixed_jet_body24_sub32_heave/identified_coefficients.csv",
        "sun_2dt_without_stern_3d_correction",
        11,
        24,
        32,
        "constant_panel",
        False,
        0.03325555538987225,
        "time_refinement_candidate",
    ),
    Candidate(
        "body24_sub64_fixed_physical_jet_threshold",
        "outputs/sun2007_sigma14_fixed_jet_body24_sub64_heave/identified_coefficients.csv",
        "sun_2dt_without_stern_3d_correction",
        11,
        24,
        64,
        "constant_panel",
        False,
        0.03325555538987225,
        "time_refinement_candidate",
    ),
    Candidate(
        "body28_sub16_fixed_physical_jet_threshold",
        "outputs/sun2007_sigma14_fixed_jet_body28_sub16_heave/identified_coefficients.csv",
        "sun_2dt_without_stern_3d_correction",
        11,
        28,
        16,
        "constant_panel",
        False,
        0.03325555538987225,
        "space_time_refinement_candidate",
    ),
)


PHYSICAL_RESTORING_CANDIDATES = (
    Candidate(
        "body24_sub8_fig7p4_restoring",
        "outputs/sun2007_sigma14_fixed_jet_body24_sub8_heave_fig7p4_restoring/identified_coefficients_reprocessed.csv",
        "sun_2dt_without_stern_3d_correction",
        11,
        24,
        8,
        "constant_panel",
        False,
        0.03325555538987225,
        "physical_restoring_space_time_candidate",
    ),
    Candidate(
        "body24_sub16_fig7p4_restoring",
        "outputs/sun2007_sigma14_fixed_jet_body24_sub16_heave_fig7p4_restoring/identified_coefficients_reprocessed.csv",
        "sun_2dt_without_stern_3d_correction",
        11,
        24,
        16,
        "constant_panel",
        False,
        0.03325555538987225,
        "physical_restoring_time_refinement_candidate",
    ),
    Candidate(
        "body28_sub16_fig7p4_restoring",
        "outputs/sun2007_sigma14_fixed_jet_body28_sub16_heave_fig7p4_restoring/identified_coefficients_reprocessed.csv",
        "sun_2dt_without_stern_3d_correction",
        11,
        28,
        16,
        "constant_panel",
        False,
        0.03325555538987225,
        "physical_restoring_space_time_candidate",
    ),
    Candidate(
        "body24_sub32_fig7p4_restoring",
        "outputs/sun2007_sigma14_fixed_jet_body24_sub32_heave_fig7p4_restoring/identified_coefficients_reprocessed.csv",
        "sun_2dt_without_stern_3d_correction",
        11,
        24,
        32,
        "constant_panel",
        False,
        0.03325555538987225,
        "physical_restoring_time_refinement_candidate",
    ),
    Candidate(
        "body24_sub64_fig7p4_restoring",
        "outputs/sun2007_sigma14_fixed_jet_body24_sub64_heave_fig7p4_restoring/identified_coefficients_reprocessed.csv",
        "sun_2dt_without_stern_3d_correction",
        11,
        24,
        64,
        "constant_panel",
        False,
        0.03325555538987225,
        "physical_restoring_time_refinement_candidate",
    ),
    Candidate(
        "body28_sub32_fig7p4_restoring",
        "outputs/sun2007_sigma14_fixed_jet_body28_sub32_heave_fig7p4_restoring/identified_coefficients_reprocessed.csv",
        "sun_2dt_without_stern_3d_correction",
        11,
        28,
        32,
        "constant_panel",
        False,
        0.03325555538987225,
        "physical_restoring_panel_refinement_candidate",
    ),
)


def _sha256(path: Path) -> str:
    with open(str(path), "rb") as stream:
        return hashlib.sha256(stream.read()).hexdigest()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize source-matched Sun (2007) sigma=1.4 diagnostics."
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("outputs/sun2007_sigma14_diagnostic_summary"),
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    root = args.root.resolve()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    reference_path = root / "benchmarks/sun2007_troesch_forced_motion_coefficients.csv"
    reference = pd.read_csv(reference_path)
    reference = reference[reference["omega_sqrt_B_over_g"].eq(1.4)]
    beam = 0.318
    lcg_over_beam = 1.47
    rows: list[dict[str, object]] = []
    sources: dict[str, str] = {str(reference_path): _sha256(reference_path)}
    stability_path = (
        root
        / "outputs/sun2007_sigma14_fixed_jet_body28_ground_plane_stability.json"
    )
    if stability_path.exists():
        sources[str(stability_path)] = _sha256(stability_path)

    for candidate in CANDIDATES:
        path = root / candidate.relative_csv
        if not path.exists():
            continue
        sources[str(path)] = _sha256(path)
        table = pd.read_csv(path)
        total = table[table["component"].eq("total")].set_index("coefficient")
        candidate_reference = reference[
            reference["model_variant"].eq(candidate.reference_variant)
        ].set_index("coefficient")
        for coefficient in ("B33", "B53"):
            if coefficient not in total.index:
                continue
            value = float(total.loc[coefficient, "value_nondimensional"])
            target = float(candidate_reference.loc[coefficient, "value_nondimensional"])
            rows.append(
                {
                    "candidate": candidate.name,
                    "role": candidate.role,
                    "reference_variant": candidate.reference_variant,
                    "section_planes": candidate.section_planes,
                    "body_panels_per_side": candidate.body_panels,
                    "bem_substeps_per_plane": candidate.bem_substeps,
                    "pressure_interpolation": candidate.pressure_interpolation,
                    "transom_correction": candidate.transom_correction,
                    "fixed_jet_threshold_over_beam": candidate.fixed_jet_threshold_over_beam,
                    "coefficient": coefficient,
                    "value_nondimensional": value,
                    "reference_nondimensional": target,
                    "relative_error_percent": 100.0 * abs(value - target) / abs(target),
                    "harmonic_fit_residual_percent": 100.0
                    * float(total.loc[coefficient, "harmonic_fit_residual_nrmse"]),
                    "damping_center_from_transom_over_beam": (
                        lcg_over_beam
                        + float(total.loc["B53", "value_dimensional"])
                        / float(total.loc["B33", "value_dimensional"])
                        / beam
                    ),
                    "response_calibration_used": False,
                }
            )

    csv_path = output / "sigma14_heave_damping_diagnostics.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    physical_rows: list[dict[str, object]] = []
    for candidate in PHYSICAL_RESTORING_CANDIDATES:
        path = root / candidate.relative_csv
        if not path.exists():
            continue
        sources[str(path)] = _sha256(path)
        table = pd.read_csv(path)
        total = table[table["component"].eq("total")].set_index("coefficient")
        candidate_reference = reference[
            reference["model_variant"].eq(candidate.reference_variant)
        ].set_index("coefficient")
        for coefficient in ("A33", "A53", "B33", "B53"):
            if coefficient not in total.index:
                continue
            value = float(total.loc[coefficient, "value_nondimensional"])
            target = float(candidate_reference.loc[coefficient, "value_nondimensional"])
            physical_rows.append(
                {
                    "candidate": candidate.name,
                    "role": candidate.role,
                    "section_planes": candidate.section_planes,
                    "body_panels_per_side": candidate.body_panels,
                    "bem_substeps_per_plane": candidate.bem_substeps,
                    "coefficient": coefficient,
                    "value_nondimensional": value,
                    "reference_nondimensional": target,
                    "relative_error_percent": 100.0 * abs(value - target) / abs(target),
                    "harmonic_fit_residual_percent": 100.0
                    * float(total.loc[coefficient, "harmonic_fit_residual_nrmse"]),
                    "restoring_subtraction": str(
                        total.loc[coefficient, "restoring_subtraction"]
                    ),
                    "response_calibration_used": False,
                }
            )
    physical_csv_path = output / "sigma14_heave_physical_coefficients.csv"
    if physical_rows:
        with physical_csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(physical_rows[0]))
            writer.writeheader()
            writer.writerows(physical_rows)
    convergence_pairs = (
        (
            "time_step_24_panels_8_to_16_substeps",
            "body24_sub8_fig7p4_restoring",
            "body24_sub16_fig7p4_restoring",
        ),
        (
            "body_panels_24_to_28_at_16_substeps",
            "body24_sub16_fig7p4_restoring",
            "body28_sub16_fig7p4_restoring",
        ),
        (
            "time_step_24_panels_16_to_32_substeps",
            "body24_sub16_fig7p4_restoring",
            "body24_sub32_fig7p4_restoring",
        ),
        (
            "time_step_24_panels_32_to_64_substeps",
            "body24_sub32_fig7p4_restoring",
            "body24_sub64_fig7p4_restoring",
        ),
        (
            "body_panels_24_to_28_at_32_substeps",
            "body24_sub32_fig7p4_restoring",
            "body28_sub32_fig7p4_restoring",
        ),
    )
    convergence_rows: list[dict[str, object]] = []
    physical_by_key = {
        (str(row["candidate"]), str(row["coefficient"])): row
        for row in physical_rows
    }
    for axis, coarse_name, refined_name in convergence_pairs:
        for coefficient in ("A33", "A53", "B33", "B53"):
            coarse = physical_by_key.get((coarse_name, coefficient))
            refined = physical_by_key.get((refined_name, coefficient))
            if coarse is None or refined is None:
                missing = []
                if coarse is None:
                    missing.append(coarse_name)
                if refined is None:
                    missing.append(refined_name)
                convergence_rows.append(
                    {
                        "axis": axis,
                        "coarse_candidate": coarse_name,
                        "refined_candidate": refined_name,
                        "coefficient": coefficient,
                        "coarse_value_nondimensional": None,
                        "refined_value_nondimensional": None,
                        "relative_change": None,
                        "limit": 0.05,
                        "status": "NOT_EVALUATED",
                        "reason": "missing: " + ", ".join(missing),
                    }
                )
                continue
            coarse_value = float(coarse["value_nondimensional"])
            refined_value = float(refined["value_nondimensional"])
            relative_change = abs(refined_value - coarse_value) / max(
                abs(refined_value), 1.0e-14
            )
            convergence_rows.append(
                {
                    "axis": axis,
                    "coarse_candidate": coarse_name,
                    "refined_candidate": refined_name,
                    "coefficient": coefficient,
                    "coarse_value_nondimensional": coarse_value,
                    "refined_value_nondimensional": refined_value,
                    "relative_change": relative_change,
                    "limit": 0.05,
                    "status": "PASS" if relative_change <= 0.05 else "FAIL",
                    "reason": "",
                }
            )
    convergence_csv_path = output / "sigma14_heave_convergence_checks.csv"
    with convergence_csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(convergence_rows[0]))
        writer.writeheader()
        writer.writerows(convergence_rows)
    manifest = {
        "source": "Sun_2007_Figs7.13_7.14_sigma_1p4_diagnostic_comparison",
        "reference_csv": str(reference_path),
        "candidate_sources": sources,
        "generated_csv_sha256": _sha256(csv_path),
        "generated_physical_csv_sha256": (
            _sha256(physical_csv_path) if physical_csv_path.exists() else None
        ),
        "generated_convergence_csv_sha256": (
            _sha256(convergence_csv_path) if convergence_csv_path.exists() else None
        ),
        "selection_policy": (
            "Candidate results are compared only with their matching corrected or "
            "uncorrected source variant. Missing candidates are not fabricated."
        ),
        "stability_diagnostic": str(stability_path),
        "response_calibration_used": False,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True), encoding="utf-8"
    )
    print(csv_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
