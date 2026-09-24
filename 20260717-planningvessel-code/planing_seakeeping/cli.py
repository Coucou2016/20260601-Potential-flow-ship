from __future__ import annotations

import argparse
from itertools import product
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from .config import load_config
from .solver import analyze_speed
from .pdstrip_external import (
    parse_pdstrip_geometry,
    parse_sectionresults,
    pdstrip_section_bem_comparison_rows,
    pdstrip_sectionresults_convention_rows,
    pdstrip_sectionresults_rows,
    run_pdstrip_station_hull_sections,
)
from .station_2p5d import (
    DOF_LABELS,
    RigidBody6DOF,
    assemble_external_pdstrip_section_6dof_matrices,
    assemble_experimental_bem_6dof_matrices,
    assemble_forward_speed_2p5d_matrices,
    assemble_hybrid_forward_coupling_matrices,
    assemble_hybrid_pressure_damping_coupling_matrices,
    assemble_pressure_transfer_forward_speed_matrices,
    assemble_pressure_transfer_pdstrip_damping_forward_speed_matrices,
    assemble_prototype_6dof_matrices,
    forward_speed_2p5d_component_diagnostics,
    forward_speed_pressure_gradient_diagnostics,
    forward_speed_pressure_transfer_diagnostics,
    load_station_hull,
    section_bem_excitation_diagnostics,
    section_bem_multimode_station_diagnostics,
    section_bem_pressure_transfer_station_diagnostics,
    section_bem_station_diagnostics,
    station_frequency_matrices_long,
    station_geometry_audit,
    station_rao_frequency_sweep,
)
from .kernels.linear_2p5d import (
    MatchedWigleySensitivityCase,
    write_matched_wigley_sensitivity,
    write_matched_wigley_station_diagnostics,
)
from .validation import (
    validate_all,
    validate_faltinsen_ch9,
    validate_katayama_classification,
    validate_pdstrip_external_smoke,
)
from .viz import plot_rao, plot_rms, plot_timeseries


def _write_report(out_dir: Path, config_path: Path, summary: pd.DataFrame) -> None:
    summary_text = "```text\n" + summary.to_string(index=False) + "\n```"
    lines = [
        "# Planing Seakeeping Run Report",
        "",
        f"- Config: `{config_path}`",
        "- Method: Savitsky/Faltinsen calm-water planing equilibrium; Faltinsen Ch. 9 2.5D heave/pitch wave excitation; nonlinear time-domain quasi-steady restoring.",
        "- 6DOF convention: `[surge, sway, heave, roll, pitch, yaw]`; v1 solves heave/pitch in head sea and emits zero placeholders for the other DOFs.",
        "",
        "## Summary",
        "",
        summary_text,
        "",
        "## Open-source references used for implementation guidance",
        "",
        "- OpenPlaning: Savitsky empirical planing-hull structure and validation examples.",
        "- OpenPlaning: <https://github.com/elcf/python-openplaning>",
        "- MSS/PythonVehicleSimulator: <https://github.com/cybergalactic/PythonVehicleSimulator> and <https://github.com/cybergalactic/MSS>",
        "- waveresponse: <https://github.com/4Subsea/waveresponse-python>",
        "- Capytaine: <https://github.com/capytaine/capytaine>",
        "- PDSTRIP local source: panel-integral strip-theory section-solver reference for the experimental `pdstrip_style` diagnostic.",
        "",
    ]
    (out_dir / "run_report.md").write_text("\n".join(lines), encoding="utf-8")


def run_command(args: argparse.Namespace) -> int:
    config_path = Path(args.config).resolve()
    import yaml
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "model" in raw:
        if raw["model"] == "synthetic_float_zero_speed_longitudinal":
            from .seaplane_workflow import run_workflow
            return run_workflow(config_path, args.out)
        from .linear_case import run_linear_case
        return run_linear_case(config_path, args.out)
    config = load_config(config_path)
    out_dir = Path(args.out).resolve()
    fig_dir = out_dir / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)

    summaries = []
    rao_frames = []
    for speed in config.speeds():
        result = analyze_speed(config, speed)
        speed_tag = f"{speed:.2f}".replace(".", "p")
        result.regular_timeseries.to_csv(out_dir / f"timeseries_regular_speed_{speed_tag}.csv", index=False)
        plot_timeseries(
            result.regular_timeseries,
            fig_dir / f"timeseries_regular_speed_{speed_tag}.png",
            f"Regular wave, speed {speed:.2f} m/s",
        )
        if result.irregular_timeseries is not None:
            result.irregular_timeseries.to_csv(out_dir / f"timeseries_irregular_speed_{speed_tag}.csv", index=False)
            plot_timeseries(
                result.irregular_timeseries,
                fig_dir / f"timeseries_irregular_speed_{speed_tag}.png",
                f"Irregular sea, speed {speed:.2f} m/s",
            )
        rao_frames.append(result.rao)
        summaries.append(result.summary)

    rao = pd.concat(rao_frames, ignore_index=True)
    summary = pd.DataFrame(summaries)
    rao.to_csv(out_dir / "rao.csv", index=False)
    summary.to_csv(out_dir / "summary.csv", index=False)
    plot_rao(rao, fig_dir / "rao.png")
    plot_rms(summary, fig_dir / "rms_by_speed.png")
    _write_report(out_dir, config_path, summary)
    print(f"Wrote results to {out_dir}")
    return 0


def validate_command(args: argparse.Namespace) -> int:
    out_dir = Path(args.out).resolve()
    reference_root = Path(args.reference_root).resolve() if args.reference_root else None
    benchmark = args.benchmark.lower()
    if benchmark == "all":
        summary = validate_all(
            out_dir,
            reference_root,
            ma_hydro_model=args.ma_hydro_model,
            ma_bem_free_surface_panel_count_per_side=args.ma_bem_free_surface_panels,
            ma_bem_body_panel_count=args.ma_bem_body_panels,
            ma_compare_hydro_models=args.ma_compare_hydro_models,
            ma_compare_external_pdstrip=args.ma_compare_external_pdstrip,
            ma_compare_row_limit=args.ma_compare_row_limit,
            ma_compare_coefficients=tuple(args.ma_compare_coefficients) if args.ma_compare_coefficients else None,
            ma_external_pdstrip_section_profiles=args.ma_external_pdstrip_section_profiles,
            ma_coupling_station_contributions=args.ma_coupling_station_contributions,
            ma_panel_convergence=args.ma_panel_convergence,
            ma_external_pdstrip_cache_dir=Path(args.ma_external_pdstrip_cache_dir).resolve()
            if args.ma_external_pdstrip_cache_dir
            else None,
            ma_external_pdstrip_source_dir=Path(args.pdstrip_source_dir).resolve() if args.pdstrip_source_dir else None,
            ma_external_pdstrip_compiler=args.pdstrip_compiler,
            ma_external_pdstrip_point_count_per_side=args.ma_external_pdstrip_point_count_per_side,
            pdstrip_external_smoke=args.pdstrip_external_smoke,
            pdstrip_source_dir=args.pdstrip_source_dir,
            pdstrip_compiler=args.pdstrip_compiler,
        )
    elif benchmark in {"faltinsen", "faltinsen_ch9"}:
        summary = validate_faltinsen_ch9(out_dir, reference_root)
    elif benchmark in {"katayama", "katayama_classification"}:
        summary = validate_katayama_classification(out_dir, reference_root)
    else:
        raise ValueError(f"Unknown benchmark '{args.benchmark}'. Supported values: all, faltinsen_ch9, katayama.")
    failures = int(summary["status"].eq("FAIL").sum())
    not_evaluated = int(summary["status"].eq("NOT_EVALUATED").sum())
    print(f"Wrote validation results to {out_dir}")
    print(f"Hard failures: {failures}; checks pending reference data: {not_evaluated}")
    return 1 if failures else 0


def pdstrip_smoke_command(args: argparse.Namespace) -> int:
    out_dir = Path(args.out).resolve()
    source_dir = Path(args.pdstrip_source_dir).resolve() if args.pdstrip_source_dir else None
    summary = validate_pdstrip_external_smoke(
        out_dir,
        source_dir=source_dir,
        compiler=args.pdstrip_compiler,
    )
    failures = int(summary["status"].eq("FAIL").sum())
    not_evaluated = int(summary["status"].eq("NOT_EVALUATED").sum())
    print(f"Wrote PDSTRIP smoke results to {out_dir}")
    print(f"Hard failures: {failures}; checks pending external setup: {not_evaluated}")
    return 1 if failures else 0


def pdstrip_sectionresults_command(args: argparse.Namespace) -> int:
    sectionresults_path = Path(args.sectionresults).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    parsed = parse_sectionresults(sectionresults_path)
    rows = pd.DataFrame(pdstrip_sectionresults_rows(parsed))
    rows.to_csv(out_dir / "pdstrip_sectionresults.csv", index=False)
    summary = pd.DataFrame(
        [
            {
                "title": parsed.title,
                "frequency_count": parsed.frequency_count,
                "section_count": parsed.section_count,
                "block_count": len(parsed.blocks),
                "has_complete_section_frequency_grid": parsed.has_complete_section_frequency_grid,
                "omega_min_rad_s": min(parsed.frequencies_rad_s),
                "omega_max_rad_s": max(parsed.frequencies_rad_s),
                "source_file": str(sectionresults_path),
                "radiation_storage_convention": "radiation_force_matrix = omega**2 * complex_added_mass_matrix",
                "complex_added_mass_recovery": "complex_added_mass_matrix_per_m = radiation_force_matrix / omega**2",
                "orientation_exports": "as_written_section_force_rows; pdstrip_internal_transposed",
            }
        ]
    )
    summary.to_csv(out_dir / "pdstrip_sectionresults_summary.csv", index=False)
    pd.DataFrame(pdstrip_sectionresults_convention_rows(sectionresults_path)).to_csv(
        out_dir / "pdstrip_sectionresults_conventions.csv",
        index=False,
    )
    print(f"Wrote parsed PDSTRIP sectionresults to {out_dir}")
    print(f"Parsed {len(parsed.blocks)} section-frequency blocks across {parsed.section_count} sections")
    return 0


def matched_wigley_sensitivity_command(args: argparse.Namespace) -> int:
    out_dir = Path(args.out).resolve()
    reference_csv = Path(args.reference_csv).resolve()
    cases: list[MatchedWigleySensitivityCase] = []
    free_surface_options = (
        (True, False) if args.compare_free_surface_marching else (not bool(args.no_free_surface_marching),)
    )
    free_surface_clipping_options = (
        (False, True)
        if args.compare_inner_free_surface_clipping
        else (bool(args.clip_inner_free_surface_to_waterline),)
    )
    two_zone_options = (
        (False, True) if args.compare_two_zone_inner_free_surface else (bool(args.two_zone_inner_free_surface),)
    )
    if (bool(args.two_zone_inner_free_surface) or bool(args.compare_two_zone_inner_free_surface)) and not (
        bool(args.clip_inner_free_surface_to_waterline) or bool(args.compare_inner_free_surface_clipping)
    ):
        raise ValueError(
            "--two-zone-inner-free-surface requires --clip-inner-free-surface-to-waterline "
            "or --compare-inner-free-surface-clipping."
        )
    end_term_options = (True, False) if args.compare_end_term else (not bool(args.no_end_term),)
    end_term_scales = tuple(float(value) for value in args.end_term_scales)
    if not end_term_scales:
        raise ValueError("At least one --end-term-scales value is required.")
    if any(not np.isfinite(value) for value in end_term_scales):
        raise ValueError("--end-term-scales values must be finite.")
    if args.compare_end_term_signs:
        signed_scales: list[float] = []
        for value in end_term_scales:
            for candidate in (value, -value):
                if not any(abs(candidate - existing) <= 1e-12 for existing in signed_scales):
                    signed_scales.append(float(candidate))
        end_term_scales = tuple(signed_scales)
    pitch_radiation_signs = tuple(float(value) for value in args.pitch_radiation_signs)
    pitch_radiation_lever_signs = tuple(float(value) for value in args.pitch_radiation_lever_signs)
    pitch_forward_speed_signs = tuple(float(value) for value in args.pitch_forward_speed_signs)
    pitch_moment_signs = tuple(float(value) for value in args.pitch_moment_signs)
    time_step_scales = tuple(float(value) for value in args.time_step_scales)
    free_surface_velocity_scales = tuple(float(value) for value in args.free_surface_velocity_scales)
    history_rhs_scales = tuple(float(value) for value in args.history_rhs_scales)
    history_convolution_rules = tuple(str(value).strip().lower() for value in args.history_convolution_rules)
    history_potential_kernel_scales = tuple(float(value) for value in args.history_potential_kernel_scales)
    history_normal_derivative_kernel_scales = tuple(float(value) for value in args.history_normal_derivative_kernel_scales)
    control_image_scales = tuple(float(value) for value in args.control_image_scales)
    control_potential_kernel_scales = tuple(float(value) for value in args.control_potential_kernel_scales)
    control_normal_derivative_kernel_scales = tuple(float(value) for value in args.control_normal_derivative_kernel_scales)
    control_diagonal_signs = tuple(float(value) for value in args.control_diagonal_signs)
    inner_a_scales = tuple(float(value) for value in args.inner_a_scales)
    inner_b_scales = tuple(float(value) for value in args.inner_b_scales)
    inner_diagonal_signs = tuple(float(value) for value in args.inner_diagonal_signs)
    pressure_gradient_schemes = tuple(str(value).strip().lower() for value in args.pressure_gradient_schemes)
    pressure_gradient_scales = tuple(float(value) for value in args.pressure_gradient_scales)
    for label, values in (
        ("--pitch-radiation-signs", pitch_radiation_signs),
        ("--pitch-radiation-lever-signs", pitch_radiation_lever_signs),
        ("--pitch-forward-speed-signs", pitch_forward_speed_signs),
        ("--pitch-moment-signs", pitch_moment_signs),
        ("--time-step-scales", time_step_scales),
        ("--free-surface-velocity-scales", free_surface_velocity_scales),
        ("--history-rhs-scales", history_rhs_scales),
        ("--history-potential-kernel-scales", history_potential_kernel_scales),
        ("--history-normal-derivative-kernel-scales", history_normal_derivative_kernel_scales),
        ("--control-image-scales", control_image_scales),
        ("--control-potential-kernel-scales", control_potential_kernel_scales),
        ("--control-normal-derivative-kernel-scales", control_normal_derivative_kernel_scales),
        ("--control-diagonal-signs", control_diagonal_signs),
        ("--inner-a-scales", inner_a_scales),
        ("--inner-b-scales", inner_b_scales),
        ("--inner-diagonal-signs", inner_diagonal_signs),
        ("--pressure-gradient-scales", pressure_gradient_scales),
    ):
        if not values:
            raise ValueError(f"At least one {label} value is required.")
        if any(not np.isfinite(value) for value in values):
            raise ValueError(f"{label} values must be finite.")
    if any(value <= 0.0 for value in time_step_scales):
        raise ValueError("--time-step-scales values must be positive.")
    if not history_convolution_rules:
        raise ValueError("At least one --history-convolution-rules value is required.")
    if any(value not in {"rectangle", "trapezoid"} for value in history_convolution_rules):
        raise ValueError("--history-convolution-rules values must be rectangle or trapezoid.")
    if not pressure_gradient_schemes:
        raise ValueError("At least one --pressure-gradient-schemes value is required.")
    if any(value not in {"central", "forward", "backward"} for value in pressure_gradient_schemes):
        raise ValueError("--pressure-gradient-schemes values must be central, forward, or backward.")
    end_stations = tuple(str(value).strip().lower() for value in args.end_stations)
    if any(value not in {"aft", "bow", "forward", "fore"} for value in end_stations):
        raise ValueError("--end-stations values must be aft or bow.")

    def scale_label(value: float) -> str:
        return str(float(value)).replace("-", "m").replace(".", "p")

    for (
        station_count,
        body_panels,
        free_panels,
        control_panels,
        radius,
        history_steps,
        use_free_surface_marching,
        include_end_term,
        pitch_radiation_sign,
        pitch_radiation_lever_sign,
        pitch_forward_speed_sign,
        pitch_moment_sign,
        time_step_scale,
        free_surface_velocity_scale,
        history_rhs_scale,
        history_convolution_rule,
        history_potential_kernel_scale,
        history_normal_derivative_kernel_scale,
        control_image_scale,
        control_potential_kernel_scale,
        control_normal_derivative_kernel_scale,
        control_diagonal_sign,
        inner_a_scale,
        inner_b_scale,
        inner_diagonal_sign,
        pressure_gradient_scheme,
        pressure_gradient_scale,
        clip_inner_free_surface_to_waterline,
        two_zone_inner_free_surface,
    ) in product(
        args.station_counts,
        args.body_panels,
        args.free_surface_panels,
        args.control_surface_panels,
        args.control_radius_beams,
        args.history_steps,
        free_surface_options,
        end_term_options,
        pitch_radiation_signs,
        pitch_radiation_lever_signs,
        pitch_forward_speed_signs,
        pitch_moment_signs,
        time_step_scales,
        free_surface_velocity_scales,
        history_rhs_scales,
        history_convolution_rules,
        history_potential_kernel_scales,
        history_normal_derivative_kernel_scales,
        control_image_scales,
        control_potential_kernel_scales,
        control_normal_derivative_kernel_scales,
        control_diagonal_signs,
        inner_a_scales,
        inner_b_scales,
        inner_diagonal_signs,
        pressure_gradient_schemes,
        pressure_gradient_scales,
        free_surface_clipping_options,
        two_zone_options,
    ):
        if bool(two_zone_inner_free_surface) and not bool(clip_inner_free_surface_to_waterline):
            continue
        end_options = tuple((station, scale) for station in end_stations for scale in end_term_scales) if include_end_term else (("none", 0.0),)
        for end_station, end_term_scale in end_options:
            end_label = (
                "noend"
                if not include_end_term
                else f"end{end_station}"
                if abs(float(end_term_scale) - 1.0) <= 1e-12
                else f"end{end_station}x{scale_label(end_term_scale)}"
            )
            convention_label = (
                f"pr{scale_label(pitch_radiation_sign)}_"
                f"pl{scale_label(pitch_radiation_lever_sign)}_"
                f"pf{scale_label(pitch_forward_speed_sign)}_"
                f"pm{scale_label(pitch_moment_sign)}_"
                f"dt{scale_label(time_step_scale)}_"
                f"fv{scale_label(free_surface_velocity_scale)}_"
                f"hr{scale_label(history_rhs_scale)}_"
                f"hq{history_convolution_rule}_"
                f"hp{scale_label(history_potential_kernel_scale)}_"
                f"hc{scale_label(history_normal_derivative_kernel_scale)}_"
                f"ci{scale_label(control_image_scale)}_"
                f"cp{scale_label(control_potential_kernel_scale)}_"
                f"cn{scale_label(control_normal_derivative_kernel_scale)}_"
                f"cd{scale_label(control_diagonal_sign)}_"
                f"ia{scale_label(inner_a_scale)}_"
                f"ib{scale_label(inner_b_scale)}_"
                f"id{scale_label(inner_diagonal_sign)}_"
                f"pgs{pressure_gradient_scheme}_"
                f"pg{scale_label(pressure_gradient_scale)}"
            )
            name = (
                f"st{station_count}_bp{body_panels}_fs{free_panels}_cp{control_panels}_"
                f"r{str(radius).replace('.', 'p')}_h{history_steps}_"
                f"{'fsm' if use_free_surface_marching else 'zerofs'}_"
                f"{'clipfs' if clip_inner_free_surface_to_waterline else 'fullfs'}_"
                f"{'twozonefs' if two_zone_inner_free_surface else 'onezonefs'}_"
                f"{end_label}_{convention_label}"
            )
            cases.append(
                MatchedWigleySensitivityCase(
                    name=name,
                    station_count=int(station_count),
                    body_panels_per_section=int(body_panels),
                    free_surface_inner_panels=int(free_panels),
                    free_surface_outer_panels=int(control_panels),
                    control_surface_radius_beams=float(radius),
                    history_steps=int(history_steps),
                    history_quadrature_count=int(args.history_quadrature_count),
                    history_k_max=float(args.history_k_max),
                    include_end_term=bool(include_end_term),
                    end_station=str(end_station),
                    end_term_scale=float(end_term_scale),
                    pitch_radiation_sign=float(pitch_radiation_sign),
                    pitch_radiation_lever_sign=float(pitch_radiation_lever_sign),
                    pitch_forward_speed_sign=float(pitch_forward_speed_sign),
                    pitch_moment_sign=float(pitch_moment_sign),
                    time_step_scale=float(time_step_scale),
                    free_surface_velocity_scale=float(free_surface_velocity_scale),
                    history_rhs_scale=float(history_rhs_scale),
                    history_convolution_rule=str(history_convolution_rule),
                    history_potential_kernel_scale=float(history_potential_kernel_scale),
                    history_normal_derivative_kernel_scale=float(history_normal_derivative_kernel_scale),
                    control_image_scale=float(control_image_scale),
                    control_potential_kernel_scale=float(control_potential_kernel_scale),
                    control_normal_derivative_kernel_scale=float(control_normal_derivative_kernel_scale),
                    control_diagonal_sign=float(control_diagonal_sign),
                    inner_a_scale=float(inner_a_scale),
                    inner_b_scale=float(inner_b_scale),
                    inner_diagonal_sign=float(inner_diagonal_sign),
                    pressure_gradient_scheme=str(pressure_gradient_scheme),
                    pressure_gradient_scale=float(pressure_gradient_scale),
                    clip_inner_free_surface_to_waterline=bool(clip_inner_free_surface_to_waterline),
                    two_zone_inner_free_surface=bool(two_zone_inner_free_surface),
                    use_free_surface_marching=bool(use_free_surface_marching),
                )
            )
    detail, summary = write_matched_wigley_sensitivity(
        reference_csv,
        out_dir,
        cases=tuple(cases),
        coefficients=tuple(args.coefficients) if args.coefficients else None,
        row_limit=None if args.row_limit_per_coefficient is not None else args.row_limit,
        row_limit_per_coefficient=args.row_limit_per_coefficient,
        rho_water_kg_m3=float(args.rho),
        gravity_m_s2=float(args.gravity),
    )
    station_rows = None
    if args.write_station_diagnostics:
        station_rows = write_matched_wigley_station_diagnostics(
            reference_csv,
            out_dir,
            cases=tuple(cases),
            coefficients=tuple(args.coefficients) if args.coefficients else None,
            row_limit=None if args.row_limit_per_coefficient is not None else args.row_limit,
            row_limit_per_coefficient=args.row_limit_per_coefficient,
            rho_water_kg_m3=float(args.rho),
            gravity_m_s2=float(args.gravity),
        )
    print(
        f"Wrote matched Wigley sensitivity diagnostics to {out_dir} "
        f"({len(detail)} rows, {len(summary)} summary rows, {len(cases)} cases)."
    )
    if station_rows is not None:
        print(f"Wrote matched Wigley station diagnostics ({len(station_rows)} rows).")
    return 0


def pdstrip_compare_section_bem_command(args: argparse.Namespace) -> int:
    sectionresults_path = Path(args.sectionresults).resolve()
    geomet_path = Path(args.geomet).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    parsed = parse_sectionresults(sectionresults_path)
    geometry = parse_pdstrip_geometry(geomet_path)
    frequency_indices = tuple(args.frequency_indices) if args.frequency_indices else None
    station_indices = tuple(args.station_indices) if args.station_indices else None
    rows = pd.DataFrame(
        pdstrip_section_bem_comparison_rows(
            parsed,
            geometry,
            station_indices=station_indices,
            frequency_indices=frequency_indices,
            rho_water_kg_m3=args.rho,
            gravity_m_s2=args.gravity,
            free_surface_panel_count_per_side=args.bem_free_surface_panels,
            body_panel_count=args.bem_body_panels,
        )
    )
    rows.to_csv(out_dir / "pdstrip_section_bem_comparison.csv", index=False)
    status = pd.DataFrame(
        [
            {
                "source_sectionresults": str(sectionresults_path),
                "source_geomet": str(geomet_path),
                "section_count": parsed.section_count,
                "frequency_count": parsed.frequency_count,
                "compared_rows": len(rows),
                "bem_free_surface_panels": args.bem_free_surface_panels,
                "bem_body_panels": args.bem_body_panels if args.bem_body_panels is not None else "",
                "status": "diagnostic_only_not_a_validation_gate",
            }
        ]
    )
    status.to_csv(out_dir / "pdstrip_section_bem_comparison_summary.csv", index=False)
    print(f"Wrote PDSTRIP/local section-BEM comparison to {out_dir}")
    print(f"Compared {len(rows)} matrix entries")
    return 0


def pdstrip_station_sections_command(args: argparse.Namespace) -> int:
    hull_path = Path(args.station_hull).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    hull = load_station_hull(hull_path)
    source_dir = Path(args.pdstrip_source_dir).resolve() if args.pdstrip_source_dir else None
    result = run_pdstrip_station_hull_sections(
        out_dir / "pdstrip_station_sections",
        hull,
        source_dir=source_dir,
        compiler=args.pdstrip_compiler,
        title=f"Station section hydrodynamics: {hull_path.name}",
        gravity_m_s2=args.gravity,
        rho_water_kg_m3=args.rho,
        wave_headings_deg=tuple(args.wave_headings_deg),
        point_count_per_side=args.point_count_per_side,
    )
    summary = pd.DataFrame(
        [
            {
                "station_hull": str(hull_path),
                "status": result.status,
                "message": result.message,
                "compile_returncode": result.compile_returncode if result.compile_returncode is not None else "",
                "run_returncode": result.run_returncode if result.run_returncode is not None else "",
                "section_count": result.parsed.section_count if result.parsed is not None else "",
                "frequency_count": result.parsed.frequency_count if result.parsed is not None else "",
                "block_count": len(result.parsed.blocks) if result.parsed is not None else "",
                "assembled_omega_rad_s": args.omega if result.parsed is not None else "",
                "sectionresults": str(result.sectionresults_path),
                "geomet": str(result.geomet_path),
                "pdstrip_out": str(result.pdstrip_out_path),
            }
        ]
    )
    summary.to_csv(out_dir / "pdstrip_station_sections_summary.csv", index=False)
    if result.parsed is not None:
        pd.DataFrame(pdstrip_sectionresults_rows(result.parsed)).to_csv(
            out_dir / "pdstrip_station_sectionresults.csv",
            index=False,
        )
        pd.DataFrame(pdstrip_sectionresults_convention_rows(result.sectionresults_path, result.source_dir)).to_csv(
            out_dir / "pdstrip_station_sectionresults_conventions.csv",
            index=False,
        )
        matrices = assemble_external_pdstrip_section_6dof_matrices(
            hull,
            result.parsed,
            rho_water_kg_m3=args.rho,
            gravity_m_s2=args.gravity,
            omega_rad_s=args.omega,
            damping_sign_convention=args.damping_sign_convention,
            symmetrize=not args.no_symmetrize,
        )
        _matrix_frame(matrices.added_mass).to_csv(out_dir / "pdstrip_external_added_mass_6dof.csv")
        _matrix_frame(matrices.damping).to_csv(out_dir / "pdstrip_external_damping_6dof.csv")
        _matrix_frame(matrices.restoring).to_csv(out_dir / "pdstrip_external_restoring_6dof.csv")
        if args.compare_section_bem:
            geometry = parse_pdstrip_geometry(result.geomet_path)
            comparison = pd.DataFrame(
                pdstrip_section_bem_comparison_rows(
                    result.parsed,
                    geometry,
                    rho_water_kg_m3=args.rho,
                    gravity_m_s2=args.gravity,
                    free_surface_panel_count_per_side=args.bem_free_surface_panels,
                    body_panel_count=args.bem_body_panels,
                )
            )
            comparison.to_csv(out_dir / "pdstrip_station_section_bem_comparison.csv", index=False)
    print(f"Wrote PDSTRIP station-section run to {out_dir}")
    print(f"Status: {result.status}; {result.message}")
    return 1 if result.status == "FAIL" else 0


def _matrix_frame(matrix: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame(matrix, index=DOF_LABELS, columns=DOF_LABELS)


def _write_station_report(
    out_dir: Path,
    hull_path: Path,
    hydro: object,
    mass_kg: float,
    status: str,
    radiation_model: str,
) -> None:
    lines = [
        "# Station 2.5D Prototype Report",
        "",
        f"- Station hull: `{hull_path}`",
        f"- Status: `{status}`",
        f"- Radiation model: `{radiation_model}`",
        "- Method: hard-chine station hydrostatics plus development strip/BEM added-mass/damping/excitation.",
        "- This is not the validated boundary-integral 2.5D solver required for Ma 2005 acceptance.",
        "",
        "## Hydrostatics",
        "",
        f"- Displacement volume: {hydro.displacement_volume_m3:.6g} m^3",
        f"- Estimated/used mass: {mass_kg:.6g} kg",
        f"- Waterplane area: {hydro.waterplane_area_m2:.6g} m^2",
        f"- LCB from transom: {hydro.center_of_buoyancy_x_m:.6g} m",
        f"- VCB below waterline: {hydro.center_of_buoyancy_z_below_waterline_m:.6g} m",
        "",
        "## Outputs",
        "",
        "- `added_mass_6dof.csv`",
        "- `damping_6dof.csv`",
        "- `station_geometry_audit.csv`",
        "- `restoring_6dof.csv`",
        "- `station_rao.csv`",
        "- `station_excitation.csv`",
        "- `station_frequency_matrices_long.csv`",
        "- `section_bem_diagnostics.csv` when an experimental section solver is used",
        "- `section_bem_multimode_radiation_diagnostics.csv` for `section_bem` runs",
        "- `section_bem_pressure_transfer_diagnostics.csv` for `section_bem` runs",
        "- `forward_speed_pressure_transfer_diagnostics.csv` for `section_bem` or pressure-transfer runs",
        "- `forward_speed_pressure_gradient_diagnostics.csv` for `section_bem` or pressure-transfer runs",
        "- `section_bem_excitation_diagnostics.csv` when an experimental section solver is used",
        "- `forward_speed_assembly_diagnostics.csv` for `strip_2p5d_forward`, `strip_2p5d_pdstrip_step`, `hybrid_forward_coupling`, and `hybrid_pressure_damping_coupling` runs",
        "",
    ]
    (out_dir / "station_report.md").write_text("\n".join(lines), encoding="utf-8")


def station_prototype_command(args: argparse.Namespace) -> int:
    hull_path = Path(args.station_hull).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    hull = load_station_hull(hull_path)
    experimental_models = {
        "section_bem",
        "pdstrip_style",
        "strip_2p5d_forward",
        "strip_2p5d_pdstrip_step",
        "pressure_transfer_forward",
        "pressure_transfer_pdstrip_step",
        "pressure_transfer_pdstrip_damping_forward",
        "pressure_transfer_pdstrip_damping_pdstrip_step",
        "hybrid_forward_coupling",
        "hybrid_pressure_damping_coupling",
    }
    pressure_models = {
        "section_bem",
        "pressure_transfer_forward",
        "pressure_transfer_pdstrip_step",
        "pressure_transfer_pdstrip_damping_forward",
        "pressure_transfer_pdstrip_damping_pdstrip_step",
        "hybrid_pressure_damping_coupling",
    }
    if args.radiation_model in experimental_models:
        if args.radiation_model in {"strip_2p5d_forward", "strip_2p5d_pdstrip_step"}:
            matrices = assemble_forward_speed_2p5d_matrices(
                hull,
                rho_water_kg_m3=args.rho,
                gravity_m_s2=args.gravity,
                omega_rad_s=args.omega,
                free_surface_panel_count_per_side=args.bem_free_surface_panels,
                body_panel_count=args.bem_body_panels,
                speed_mps=args.speed_mps,
                section_solver="pdstrip_style",
                assembly_method="pdstrip_step" if args.radiation_model == "strip_2p5d_pdstrip_step" else "continuous_gradient",
            )
        elif args.radiation_model in {"pressure_transfer_forward", "pressure_transfer_pdstrip_step"}:
            matrices = assemble_pressure_transfer_forward_speed_matrices(
                hull,
                rho_water_kg_m3=args.rho,
                gravity_m_s2=args.gravity,
                omega_rad_s=args.omega,
                free_surface_panel_count_per_side=args.bem_free_surface_panels,
                body_panel_count=args.bem_body_panels,
                speed_mps=args.speed_mps,
                assembly_method="pdstrip_step"
                if args.radiation_model == "pressure_transfer_pdstrip_step"
                else "continuous_gradient",
            )
        elif args.radiation_model in {
            "pressure_transfer_pdstrip_damping_forward",
            "pressure_transfer_pdstrip_damping_pdstrip_step",
        }:
            matrices = assemble_pressure_transfer_pdstrip_damping_forward_speed_matrices(
                hull,
                rho_water_kg_m3=args.rho,
                gravity_m_s2=args.gravity,
                omega_rad_s=args.omega,
                free_surface_panel_count_per_side=args.bem_free_surface_panels,
                body_panel_count=args.bem_body_panels,
                speed_mps=args.speed_mps,
                assembly_method=(
                    "pdstrip_step"
                    if args.radiation_model == "pressure_transfer_pdstrip_damping_pdstrip_step"
                    else "continuous_gradient"
                ),
            )
        elif args.radiation_model == "hybrid_forward_coupling":
            matrices = assemble_hybrid_forward_coupling_matrices(
                hull,
                rho_water_kg_m3=args.rho,
                gravity_m_s2=args.gravity,
                omega_rad_s=args.omega,
                free_surface_panel_count_per_side=args.bem_free_surface_panels,
                body_panel_count=args.bem_body_panels,
                speed_mps=args.speed_mps,
            )
        elif args.radiation_model == "hybrid_pressure_damping_coupling":
            matrices = assemble_hybrid_pressure_damping_coupling_matrices(
                hull,
                rho_water_kg_m3=args.rho,
                gravity_m_s2=args.gravity,
                omega_rad_s=args.omega,
                free_surface_panel_count_per_side=args.bem_free_surface_panels,
                body_panel_count=args.bem_body_panels,
                speed_mps=args.speed_mps,
            )
        else:
            matrices = assemble_experimental_bem_6dof_matrices(
                hull,
                rho_water_kg_m3=args.rho,
                gravity_m_s2=args.gravity,
                omega_rad_s=args.omega,
                free_surface_panel_count_per_side=args.bem_free_surface_panels,
                body_panel_count=args.bem_body_panels,
                speed_mps=args.speed_mps,
                section_solver="pdstrip_style" if args.radiation_model == "pdstrip_style" else "collocation",
            )
    else:
        matrices = assemble_prototype_6dof_matrices(
            hull,
            rho_water_kg_m3=args.rho,
            gravity_m_s2=args.gravity,
            omega_rad_s=args.omega,
            radiation_damping_ratio=args.damping_ratio,
            speed_mps=args.speed_mps,
        )
    hydro = matrices.hydrostatics
    data = hull.arrays()
    max_beam = float(np.max(data["beam"]))
    mass_kg = float(args.mass_kg) if args.mass_kg is not None else args.rho * hydro.displacement_volume_m3
    body = RigidBody6DOF.from_radii(
        mass_kg=mass_kg,
        roll_radius_gyration_m=args.roll_radius_m if args.roll_radius_m is not None else 0.35 * max_beam,
        pitch_radius_gyration_m=args.pitch_radius_m if args.pitch_radius_m is not None else 0.25 * hull.length_m,
        yaw_radius_gyration_m=args.yaw_radius_m if args.yaw_radius_m is not None else 0.28 * hull.length_m,
    )
    periods = np.linspace(args.period_min_s, args.period_max_s, args.period_count)
    rao = pd.DataFrame(
        station_rao_frequency_sweep(
            hull,
            body,
            periods,
            speed_mps=args.speed_mps,
            heading_deg=args.heading_deg,
            rho_water_kg_m3=args.rho,
            gravity_m_s2=args.gravity,
            radiation_damping_ratio=args.damping_ratio,
            radiation_model=args.radiation_model,
            bem_free_surface_panel_count_per_side=args.bem_free_surface_panels,
            bem_body_panel_count=args.bem_body_panels,
        )
    )
    hydro_frame = pd.DataFrame(
        [
            {
                "displacement_volume_m3": hydro.displacement_volume_m3,
                "estimated_or_used_mass_kg": mass_kg,
                "waterplane_area_m2": hydro.waterplane_area_m2,
                "center_of_buoyancy_x_m": hydro.center_of_buoyancy_x_m,
                "center_of_buoyancy_z_below_waterline_m": hydro.center_of_buoyancy_z_below_waterline_m,
                "waterplane_second_moment_roll_m4": hydro.waterplane_second_moment_roll_m4,
                "waterplane_second_moment_pitch_m4": hydro.waterplane_second_moment_pitch_m4,
                "status": matrices.status,
            }
        ]
    )
    hydro_frame.to_csv(out_dir / "hydrostatics.csv", index=False)
    pd.DataFrame(station_geometry_audit(hull)).to_csv(out_dir / "station_geometry_audit.csv", index=False)
    _matrix_frame(matrices.added_mass).to_csv(out_dir / "added_mass_6dof.csv")
    _matrix_frame(matrices.damping).to_csv(out_dir / "damping_6dof.csv")
    _matrix_frame(matrices.restoring).to_csv(out_dir / "restoring_6dof.csv")
    rao.to_csv(out_dir / "station_rao.csv", index=False)
    metadata_columns = [
        "wave_period_s",
        "omega0_rad_s",
        "omega_e_rad_s",
        "wavenumber_rad_m",
        "radiation_model",
        "excitation_model",
        "matrix_status",
    ]
    excitation_columns = [
        column
        for column in rao.columns
        if column.endswith("_excitation_abs_per_m") or column.endswith("_excitation_phase_rad")
    ]
    rao[metadata_columns + excitation_columns].to_csv(out_dir / "station_excitation.csv", index=False)
    pd.DataFrame(
        station_frequency_matrices_long(
            hull,
            periods,
            speed_mps=args.speed_mps,
            heading_deg=args.heading_deg,
            rho_water_kg_m3=args.rho,
            gravity_m_s2=args.gravity,
            radiation_damping_ratio=args.damping_ratio,
            radiation_model=args.radiation_model,
            bem_free_surface_panel_count_per_side=args.bem_free_surface_panels,
            bem_body_panel_count=args.bem_body_panels,
        )
    ).to_csv(out_dir / "station_frequency_matrices_long.csv", index=False)
    if args.radiation_model in experimental_models:
        diagnostic_omegas = np.unique(np.concatenate([np.asarray([args.omega], dtype=float), np.abs(rao["omega_e_rad_s"].to_numpy(dtype=float))]))
        diagnostics = pd.DataFrame(
            section_bem_station_diagnostics(
                hull,
                diagnostic_omegas,
                rho_water_kg_m3=args.rho,
                gravity_m_s2=args.gravity,
                free_surface_panel_count_per_side=args.bem_free_surface_panels,
                body_panel_count=args.bem_body_panels,
                section_solver="collocation" if args.radiation_model in pressure_models else "pdstrip_style",
            )
        )
        diagnostics.to_csv(out_dir / "section_bem_diagnostics.csv", index=False)
        if args.radiation_model in pressure_models:
            multimode_diagnostics = pd.DataFrame(
                section_bem_multimode_station_diagnostics(
                    hull,
                    diagnostic_omegas,
                    rho_water_kg_m3=args.rho,
                    gravity_m_s2=args.gravity,
                    free_surface_panel_count_per_side=args.bem_free_surface_panels,
                    body_panel_count=args.bem_body_panels,
                )
            )
            multimode_diagnostics.to_csv(out_dir / "section_bem_multimode_radiation_diagnostics.csv", index=False)
            pressure_diagnostics = pd.DataFrame(
                section_bem_pressure_transfer_station_diagnostics(
                    hull,
                    omega_rad_s=rao["omega0_rad_s"].to_numpy(dtype=float),
                    wave_amplitude_m=1.0,
                    wavenumber_rad_m=rao["wavenumber_rad_m"].to_numpy(dtype=float),
                    heading_deg=args.heading_deg,
                    rho_water_kg_m3=args.rho,
                    gravity_m_s2=args.gravity,
                    free_surface_panel_count_per_side=args.bem_free_surface_panels,
                    body_panel_count=args.bem_body_panels,
                )
            )
            pressure_diagnostics.to_csv(out_dir / "section_bem_pressure_transfer_diagnostics.csv", index=False)
            pressure_forward_diagnostics = pd.DataFrame(
                forward_speed_pressure_transfer_diagnostics(
                    hull,
                    rho_water_kg_m3=args.rho,
                    gravity_m_s2=args.gravity,
                    omega_rad_s=args.omega,
                    free_surface_panel_count_per_side=args.bem_free_surface_panels,
                    body_panel_count=args.bem_body_panels,
                    speed_mps=args.speed_mps,
                )
            )
            pressure_forward_diagnostics.to_csv(out_dir / "forward_speed_pressure_transfer_diagnostics.csv", index=False)
            pressure_gradient_diagnostics = pd.DataFrame(
                forward_speed_pressure_gradient_diagnostics(
                    hull,
                    rho_water_kg_m3=args.rho,
                    gravity_m_s2=args.gravity,
                    omega_rad_s=args.omega,
                    free_surface_panel_count_per_side=args.bem_free_surface_panels,
                    body_panel_count=args.bem_body_panels,
                    speed_mps=args.speed_mps,
                )
            )
            pressure_gradient_diagnostics.to_csv(out_dir / "forward_speed_pressure_gradient_diagnostics.csv", index=False)
        excitation_diagnostics = pd.DataFrame(
            section_bem_excitation_diagnostics(
                hull,
                omega_rad_s=rao["omega0_rad_s"].to_numpy(dtype=float),
                wave_amplitude_m=1.0,
                wavenumber_rad_m=rao["wavenumber_rad_m"].to_numpy(dtype=float),
                heading_deg=args.heading_deg,
                rho_water_kg_m3=args.rho,
                gravity_m_s2=args.gravity,
                free_surface_panel_count_per_side=args.bem_free_surface_panels,
                body_panel_count=args.bem_body_panels,
            )
        )
        excitation_diagnostics.to_csv(out_dir / "section_bem_excitation_diagnostics.csv", index=False)
    if args.radiation_model in {
        "strip_2p5d_forward",
        "strip_2p5d_pdstrip_step",
        "hybrid_forward_coupling",
        "hybrid_pressure_damping_coupling",
    }:
        forward_diagnostics = pd.DataFrame(
            forward_speed_2p5d_component_diagnostics(
                hull,
                rho_water_kg_m3=args.rho,
                gravity_m_s2=args.gravity,
                omega_rad_s=args.omega,
                free_surface_panel_count_per_side=args.bem_free_surface_panels,
                body_panel_count=args.bem_body_panels,
                speed_mps=args.speed_mps,
                section_solver="pdstrip_style",
                assembly_method="pdstrip_step" if args.radiation_model == "strip_2p5d_pdstrip_step" else "continuous_gradient",
            )
        )
        forward_diagnostics.to_csv(out_dir / "forward_speed_assembly_diagnostics.csv", index=False)
    _write_station_report(out_dir, hull_path, hydro, mass_kg, matrices.status, args.radiation_model)
    print(f"Wrote station prototype results to {out_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="planing_seakeeping")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Run a configured seakeeping prediction.")
    run.add_argument("config", help="Path to YAML/JSON run config.")
    run.add_argument("--out", required=True, help="Output directory.")
    run.set_defaults(func=run_command)
    validate = sub.add_parser("validate", help="Run published benchmark validation checks.")
    validate.add_argument("--benchmark", default="all", help="Benchmark name: all, faltinsen_ch9, or katayama.")
    validate.add_argument("--out", required=True, help="Output directory.")
    validate.add_argument("--reference-root", help="Directory containing digitized benchmark reference data.")
    validate.add_argument(
        "--ma-hydro-model",
        choices=[
            "matched_bie_provider",
            "prototype",
            "section_bem",
            "pdstrip_style",
            "strip_2p5d_forward",
            "strip_2p5d_pdstrip_step",
            "pressure_transfer_forward",
            "pressure_transfer_pdstrip_step",
            "pressure_transfer_pdstrip_damping_forward",
            "pressure_transfer_pdstrip_damping_pdstrip_step",
            "hybrid_forward_coupling",
            "hybrid_pressure_damping_coupling",
            "external_pdstrip_sections",
            "external_pdstrip_forward",
            "external_pdstrip_pdstrip_step",
        ],
        default="prototype",
        help="Hydrodynamic model used for Ma 2005 coefficient comparisons in --benchmark all.",
    )
    validate.add_argument(
        "--ma-bem-free-surface-panels",
        type=int,
        default=4,
        help="Free-surface panels per side for Ma 2005 section_bem coefficient comparisons.",
    )
    validate.add_argument(
        "--ma-bem-body-panels",
        type=int,
        help="Optional target body panels per section for Ma 2005 section_bem coefficient comparisons.",
    )
    validate.add_argument(
        "--ma-compare-hydro-models",
        action="store_true",
        help="Write optional side-by-side Ma 2005 diagnostic CSVs for all candidate hydro models.",
    )
    validate.add_argument(
        "--ma-compare-external-pdstrip",
        action="store_true",
        help="Include the slow external_pdstrip_sections model in --ma-compare-hydro-models diagnostics.",
    )
    validate.add_argument(
        "--ma-compare-row-limit",
        type=int,
        help="Limit optional --ma-compare-hydro-models diagnostics to the first N selected Ma 2005 rows; does not change the hard Ma gate.",
    )
    validate.add_argument(
        "--ma-compare-coefficients",
        nargs="+",
        help="Restrict optional --ma-compare-hydro-models diagnostics to coefficient labels such as A33 B33 or A35; does not change the hard Ma gate.",
    )
    validate.add_argument(
        "--ma-external-pdstrip-cache-dir",
        help="Optional persistent cache directory for external_pdstrip_sections Ma diagnostics; reuses parseable sectionresults when present.",
    )
    validate.add_argument(
        "--ma-external-pdstrip-section-profiles",
        action="store_true",
        help="Write optional per-station Ma 2005 external/local section-radiation profile CSVs; requires --ma-compare-hydro-models.",
    )
    validate.add_argument(
        "--ma-coupling-station-contributions",
        action="store_true",
        help="Write slow optional station-level longitudinal coefficient contribution diagnostics; requires --ma-compare-hydro-models.",
    )
    validate.add_argument(
        "--ma-panel-convergence",
        action="store_true",
        help="Write slow optional Ma 2005 section-BEM panel-refinement diagnostics for pressure-transfer forward-speed models; requires Ma coefficient data.",
    )
    validate.add_argument(
        "--ma-external-pdstrip-point-count-per-side",
        type=int,
        default=8,
        help="Offset points per side when generating Ma station sections for external_pdstrip_sections diagnostics.",
    )
    validate.add_argument(
        "--pdstrip-external-smoke",
        action="store_true",
        help="Compile and run the local open-source PDSTRIP smoke case and include its diagnostic rows.",
    )
    validate.add_argument(
        "--pdstrip-source-dir",
        help="Optional local PDSTRIP source directory containing pdstrip.f90 for smoke and external_pdstrip_sections Ma diagnostics.",
    )
    validate.add_argument(
        "--pdstrip-compiler",
        default="gfortran",
        help="Fortran compiler used for --pdstrip-external-smoke and external_pdstrip_sections Ma diagnostics.",
    )
    validate.set_defaults(func=validate_command)
    matched_wigley = sub.add_parser(
        "matched-wigley-sensitivity",
        help="Write diagnostic Ma 2005 Wigley III sensitivity rows using the matched 2.5D StationHull sweep.",
    )
    matched_wigley.add_argument(
        "reference_csv",
        help="Path to benchmarks/ma2005/wigley_iii_coefficients_digitized.csv.",
    )
    matched_wigley.add_argument("--out", required=True, help="Output directory.")
    matched_wigley.add_argument(
        "--coefficients",
        nargs="+",
        default=["A33"],
        help="Coefficient labels to evaluate, such as A33 B33 A55.",
    )
    matched_wigley.add_argument(
        "--row-limit",
        type=int,
        default=3,
        help="Limit rows from the selected coefficient subset for a quick diagnostic run.",
    )
    matched_wigley.add_argument(
        "--row-limit-per-coefficient",
        type=int,
        help="Limit rows separately for each selected coefficient; mutually exclusive with --row-limit.",
    )
    matched_wigley.add_argument("--station-counts", type=int, nargs="+", default=[5], help="Station counts to test.")
    matched_wigley.add_argument("--body-panels", type=int, nargs="+", default=[8], help="Body panels per section.")
    matched_wigley.add_argument(
        "--free-surface-panels",
        type=int,
        nargs="+",
        default=[4],
        help="Inner free-surface panels to test.",
    )
    matched_wigley.add_argument(
        "--control-surface-panels",
        type=int,
        nargs="+",
        default=[4],
        help="Control-surface panels to test.",
    )
    matched_wigley.add_argument(
        "--control-radius-beams",
        type=float,
        nargs="+",
        default=[2.0],
        help="Control-surface radius in maximum-beam units.",
    )
    matched_wigley.add_argument("--history-steps", type=int, nargs="+", default=[2], help="History steps to test.")
    matched_wigley.add_argument(
        "--history-quadrature-count",
        type=int,
        default=16,
        help="Transient Green quadrature count.",
    )
    matched_wigley.add_argument("--history-k-max", type=float, default=15.0, help="Transient Green k cutoff.")
    matched_wigley.add_argument(
        "--end-term-scales",
        type=float,
        nargs="+",
        default=[1.0],
        help="Scale factors applied to the A1 Eq.32 end-term helper when it is enabled.",
    )
    matched_wigley.add_argument(
        "--end-stations",
        nargs="+",
        default=["aft"],
        help="End stations used by the A1 Eq.32 contour helper; values may be aft or bow.",
    )
    matched_wigley.add_argument(
        "--pitch-radiation-signs",
        type=float,
        nargs="+",
        default=[1.0],
        help="Multipliers applied to the pitch radiation body-condition right-hand side.",
    )
    matched_wigley.add_argument(
        "--pitch-radiation-lever-signs",
        type=float,
        nargs="+",
        default=[1.0],
        help="Multipliers applied to the LCG-x lever arm inside the pitch radiation body condition.",
    )
    matched_wigley.add_argument(
        "--pitch-forward-speed-signs",
        type=float,
        nargs="+",
        default=[1.0],
        help="Multipliers applied to the forward-speed term inside the pitch radiation body condition.",
    )
    matched_wigley.add_argument(
        "--pitch-moment-signs",
        type=float,
        nargs="+",
        default=[1.0],
        help="Multipliers applied to the LCG-x lever arm used for the pitch generalized-force row.",
    )
    matched_wigley.add_argument(
        "--time-step-scales",
        type=float,
        nargs="+",
        default=[1.0],
        help="Diagnostic scale factors applied to the local 2.5D time step dt=dx/U.",
    )
    matched_wigley.add_argument(
        "--free-surface-velocity-scales",
        type=float,
        nargs="+",
        default=[1.0],
        help="Diagnostic scale factors applied to inner free-surface normal velocity during marching.",
    )
    matched_wigley.add_argument(
        "--history-rhs-scales",
        type=float,
        nargs="+",
        default=[1.0],
        help="Diagnostic scale factors applied to the outer control-surface history convolution RHS.",
    )
    matched_wigley.add_argument(
        "--history-convolution-rules",
        nargs="+",
        choices=["rectangle", "trapezoid"],
        default=["trapezoid"],
        help=(
            "Quadrature rule for the retained Eq.24 transient Green history terms. "
            "rectangle preserves the older equal-weight diagnostic; trapezoid half-weights the oldest retained lag."
        ),
    )
    matched_wigley.add_argument(
        "--history-potential-kernel-scales",
        type=float,
        nargs="+",
        default=[1.0],
        help="Diagnostic scale factors applied only to the Eq.24 transient Green potential kernel B history channel.",
    )
    matched_wigley.add_argument(
        "--history-normal-derivative-kernel-scales",
        type=float,
        nargs="+",
        default=[1.0],
        help="Diagnostic scale factors applied only to the Eq.24 transient Green normal-derivative kernel C history channel.",
    )
    matched_wigley.add_argument(
        "--control-image-scales",
        type=float,
        nargs="+",
        default=[1.0],
        help="Diagnostic scale factors applied to the Eq.24 instantaneous image terms Abar/Bbar on the control surface.",
    )
    matched_wigley.add_argument(
        "--control-potential-kernel-scales",
        type=float,
        nargs="+",
        default=[1.0],
        help="Diagnostic scale factors applied to the Eq.24 instantaneous (A-Abar) psi control-potential column.",
    )
    matched_wigley.add_argument(
        "--control-normal-derivative-kernel-scales",
        type=float,
        nargs="+",
        default=[1.0],
        help="Diagnostic scale factors applied to the Eq.24 instantaneous -(B-Bbar) psi_n control-normal column.",
    )
    matched_wigley.add_argument(
        "--control-diagonal-signs",
        type=float,
        nargs="+",
        default=[1.0],
        help="Diagnostic signs/scales for the non-image Eq.24 A diagonal term; A1 uses +1 for the outer equation.",
    )
    matched_wigley.add_argument(
        "--inner-a-scales",
        type=float,
        nargs="+",
        default=[1.0],
        help="Diagnostic scale factors applied to the A1 Eq.23 inner-domain Aij normal-derivative block.",
    )
    matched_wigley.add_argument(
        "--inner-b-scales",
        type=float,
        nargs="+",
        default=[1.0],
        help="Diagnostic scale factors applied to the A1 Eq.23 inner-domain Bij log-potential block.",
    )
    matched_wigley.add_argument(
        "--inner-diagonal-signs",
        type=float,
        nargs="+",
        default=[-1.0],
        help="Diagnostic signs/scales for the A1 Eq.23 self term; raw A1 alpha=1 uses -1.",
    )
    matched_wigley.add_argument(
        "--pressure-gradient-scales",
        type=float,
        nargs="+",
        default=[1.0],
        help="Diagnostic scale factors applied to the U*dphi/dx pressure-gradient term in A1 Eq.30.",
    )
    matched_wigley.add_argument(
        "--pressure-gradient-schemes",
        nargs="+",
        choices=["central", "forward", "backward"],
        default=["central"],
        help="Station differencing scheme for the A1 Eq.30 dphi/dx pressure-gradient diagnostic.",
    )
    matched_wigley.add_argument(
        "--write-station-diagnostics",
        action="store_true",
        help="Write station-level force/free-surface diagnostics for heave/pitch coefficient buildup.",
    )
    matched_wigley.add_argument(
        "--clip-inner-free-surface-to-waterline",
        action="store_true",
        help="Use station-wise inner free-surface panels outside the local waterline instead of one full-width line.",
    )
    matched_wigley.add_argument(
        "--compare-inner-free-surface-clipping",
        action="store_true",
        help="Run both full-width and waterline-clipped inner free-surface grids in one sensitivity matrix.",
    )
    matched_wigley.add_argument(
        "--two-zone-inner-free-surface",
        action="store_true",
        help=(
            "For waterline-clipped grids, split each outboard side into a waterline-near zone and an outer zone, "
            "following the A1 n2i/n2e grid idea."
        ),
    )
    matched_wigley.add_argument(
        "--compare-two-zone-inner-free-surface",
        action="store_true",
        help="Run both one-zone and two-zone waterline-clipped inner free-surface grids in one sensitivity matrix.",
    )
    matched_wigley.add_argument("--rho", type=float, default=1025.0, help="Water density in kg/m^3.")
    matched_wigley.add_argument("--gravity", type=float, default=9.80665, help="Gravity in m/s^2.")
    matched_wigley.add_argument(
        "--no-free-surface-marching",
        action="store_true",
        help="Disable inner free-surface marching for a zero-free-surface diagnostic comparison.",
    )
    matched_wigley.add_argument("--no-end-term", action="store_true", help="Disable A1 Eq.32 end-term helper.")
    matched_wigley.add_argument(
        "--compare-free-surface-marching",
        action="store_true",
        help="Run both enabled and disabled inner free-surface marching cases in one sensitivity matrix.",
    )
    matched_wigley.add_argument(
        "--compare-end-term",
        action="store_true",
        help="Run both enabled and disabled A1 Eq.32 end-term cases in one sensitivity matrix.",
    )
    matched_wigley.add_argument(
        "--compare-end-term-signs",
        action="store_true",
        help="For enabled end-term cases, run both +scale and -scale to diagnose sign convention.",
    )
    matched_wigley.set_defaults(func=matched_wigley_sensitivity_command)
    pdstrip = sub.add_parser("pdstrip-smoke", help="Compile and run the local open-source PDSTRIP smoke case.")
    pdstrip.add_argument("--out", required=True, help="Output directory.")
    pdstrip.add_argument("--pdstrip-source-dir", help="Optional local PDSTRIP source directory containing pdstrip.f90.")
    pdstrip.add_argument("--pdstrip-compiler", default="gfortran", help="Fortran compiler used for the smoke run.")
    pdstrip.set_defaults(func=pdstrip_smoke_command)
    pdstrip_station = sub.add_parser(
        "pdstrip-station-sections",
        help="Run external PDSTRIP section hydrodynamics for a station-hull YAML/JSON file.",
    )
    pdstrip_station.add_argument("station_hull", help="Path to station-hull YAML/JSON.")
    pdstrip_station.add_argument("--out", required=True, help="Output directory.")
    pdstrip_station.add_argument("--pdstrip-source-dir", help="Optional local PDSTRIP source directory containing pdstrip.f90.")
    pdstrip_station.add_argument("--pdstrip-compiler", default="gfortran", help="Fortran compiler used for PDSTRIP.")
    pdstrip_station.add_argument("--rho", type=float, default=1025.0, help="Water density in kg/m^3.")
    pdstrip_station.add_argument("--gravity", type=float, default=9.80665, help="Gravity in m/s^2.")
    pdstrip_station.add_argument("--omega", type=float, default=1.0, help="Reference omega for assembled 6DOF matrices.")
    pdstrip_station.add_argument(
        "--damping-sign-convention",
        choices=["section_bem", "pdstrip"],
        default="section_bem",
        help="Damping sign used when converting PDSTRIP complex added mass to real damping matrices.",
    )
    pdstrip_station.add_argument(
        "--no-symmetrize",
        action="store_true",
        help="Do not symmetrize the assembled zero-speed added-mass and damping matrices.",
    )
    pdstrip_station.add_argument(
        "--wave-headings-deg",
        type=float,
        nargs="+",
        default=[0.0],
        help="PDSTRIP section-hydrodynamics wave headings in degrees.",
    )
    pdstrip_station.add_argument(
        "--point-count-per-side",
        type=int,
        default=8,
        help="Generated V-section points per side when a station lacks explicit offsets.",
    )
    pdstrip_station.add_argument(
        "--compare-section-bem",
        action="store_true",
        help="Also compare external PDSTRIP section radiation to the local compact section-BEM.",
    )
    pdstrip_station.add_argument(
        "--bem-free-surface-panels",
        type=int,
        default=4,
        help="Free-surface panels per side for --compare-section-bem.",
    )
    pdstrip_station.add_argument(
        "--bem-body-panels",
        type=int,
        help="Optional target body panels for --compare-section-bem.",
    )
    pdstrip_station.set_defaults(func=pdstrip_station_sections_command)
    pdstrip_parse = sub.add_parser(
        "pdstrip-sectionresults",
        help="Parse a PDSTRIP sectionresults file into long-form radiation/excitation CSVs.",
    )
    pdstrip_parse.add_argument("sectionresults", help="Path to a PDSTRIP sectionresults file.")
    pdstrip_parse.add_argument("--out", required=True, help="Output directory.")
    pdstrip_parse.set_defaults(func=pdstrip_sectionresults_command)
    pdstrip_compare = sub.add_parser(
        "pdstrip-compare-section-bem",
        help="Compare external PDSTRIP section radiation matrices with the local section-BEM solver.",
    )
    pdstrip_compare.add_argument("sectionresults", help="Path to a PDSTRIP sectionresults file.")
    pdstrip_compare.add_argument("geomet", help="Path to the matching PDSTRIP geomet.out file.")
    pdstrip_compare.add_argument("--out", required=True, help="Output directory.")
    pdstrip_compare.add_argument("--station-indices", type=int, nargs="*", help="1-based station indices to compare.")
    pdstrip_compare.add_argument("--frequency-indices", type=int, nargs="*", help="1-based frequency indices to compare.")
    pdstrip_compare.add_argument("--rho", type=float, default=1025.0, help="Water density in kg/m^3.")
    pdstrip_compare.add_argument("--gravity", type=float, default=9.80665, help="Gravity in m/s^2.")
    pdstrip_compare.add_argument(
        "--bem-free-surface-panels",
        type=int,
        default=4,
        help="Free-surface panels per side for the local section-BEM comparison.",
    )
    pdstrip_compare.add_argument(
        "--bem-body-panels",
        type=int,
        help="Optional target body panels for local section-BEM arclength resampling.",
    )
    pdstrip_compare.set_defaults(func=pdstrip_compare_section_bem_command)
    station = sub.add_parser("station-prototype", help="Run the unvalidated station-based 6DOF prototype.")
    station.add_argument("station_hull", help="Path to station-hull YAML/JSON.")
    station.add_argument("--out", required=True, help="Output directory.")
    station.add_argument("--mass-kg", type=float, help="Rigid-body mass. Defaults to rho times integrated displacement volume.")
    station.add_argument("--roll-radius-m", type=float, help="Roll radius of gyration. Defaults to 0.35 max waterline beam.")
    station.add_argument("--pitch-radius-m", type=float, help="Pitch radius of gyration. Defaults to 0.25 L.")
    station.add_argument("--yaw-radius-m", type=float, help="Yaw radius of gyration. Defaults to 0.28 L.")
    station.add_argument("--rho", type=float, default=1025.0, help="Water density in kg/m^3.")
    station.add_argument("--gravity", type=float, default=9.80665, help="Gravity in m/s^2.")
    station.add_argument("--omega", type=float, default=1.0, help="Reference omega for matrix damping output.")
    station.add_argument("--damping-ratio", type=float, default=0.08, help="Prototype radiation damping ratio.")
    station.add_argument(
        "--radiation-model",
        choices=[
            "prototype",
            "section_bem",
            "pdstrip_style",
            "strip_2p5d_forward",
            "strip_2p5d_pdstrip_step",
            "pressure_transfer_forward",
            "pressure_transfer_pdstrip_step",
            "pressure_transfer_pdstrip_damping_forward",
            "pressure_transfer_pdstrip_damping_pdstrip_step",
            "hybrid_forward_coupling",
            "hybrid_pressure_damping_coupling",
        ],
        default="prototype",
        help="Station radiation model. Non-prototype models are experimental and slower.",
    )
    station.add_argument(
        "--bem-free-surface-panels",
        type=int,
        default=8,
        help="Free-surface panels per side for the experimental section_bem model.",
    )
    station.add_argument(
        "--bem-body-panels",
        type=int,
        help="Optional target body panels per section for arclength-resampled section_bem geometry.",
    )
    station.add_argument("--speed-mps", type=float, default=0.0, help="Forward speed for encounter frequency.")
    station.add_argument("--heading-deg", type=float, default=180.0, help="Wave heading; 180 deg is head sea.")
    station.add_argument("--period-min-s", type=float, default=1.0, help="Minimum wave period for RAO sweep.")
    station.add_argument("--period-max-s", type=float, default=8.0, help="Maximum wave period for RAO sweep.")
    station.add_argument("--period-count", type=int, default=80, help="Number of period samples for RAO sweep.")
    station.set_defaults(func=station_prototype_command)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
