"""Run the source-resolution Ma 2005 A33/A53 reproduction gate."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from planing_seakeeping.validation import (
    MA2005_MATCHED_BIE_MODEL,
    _ma2005_computed_coefficient,
    _ma2005_error_metrics,
    _coefficient_matrix_indices,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference",
        type=Path,
        default=Path("benchmarks/ma2005/wigley_iii_coefficients_digitized.csv"),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("outputs/ma2005_a33_a53_source_resolution"),
    )
    parser.add_argument("--free-surface-panels", type=int, default=20)
    parser.add_argument("--body-panels", type=int, default=30)
    parser.add_argument("--relative-error-limit", type=float, default=0.05)
    parser.add_argument("--gate-relative-tolerance", type=float, default=0.15)
    return parser


def main() -> int:
    args = _parser().parse_args()
    reference_path = args.reference.resolve()
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    reference = pd.read_csv(reference_path)
    target = reference[
        reference["coefficient"].astype(str).isin({"A33", "A53"})
        & reference["reference_role"].astype(str).eq("implementation_reproduction_gate")
    ].copy()
    if target.empty:
        raise ValueError("No A33/A53 implementation_reproduction_gate rows were found.")

    cache: dict[tuple[float | int | str, ...], object] = {}
    rows: list[dict[str, object]] = []
    for source_row, (_, reference_row) in enumerate(target.iterrows()):
        calc = _ma2005_computed_coefficient(
            reference_row,
            hydro_model=MA2005_MATCHED_BIE_MODEL,
            bem_free_surface_panel_count_per_side=args.free_surface_panels,
            bem_body_panel_count=args.body_panels,
            matrix_cache=cache,
            benchmark_base_dir=reference_path.parent,
        )
        coefficient = str(reference_row["coefficient"])
        expected = float(reference_row["reference_value"])
        computed = float(calc["computed_value"])
        relative_error = abs(computed - expected) / max(abs(expected), 1.0e-300)
        _, row_idx, col_idx = _coefficient_matrix_indices(coefficient)
        gate_metrics = _ma2005_error_metrics(
            expected,
            computed,
            float(args.gate_relative_tolerance),
            row_idx,
            col_idx,
            str(reference_row["normalization"]),
        )
        rows.append(
            {
                "source_row": source_row,
                "coefficient": coefficient,
                "omega_e_sqrt_l_over_g": float(reference_row["omega_e_sqrt_l_over_g"]),
                "reference_value": expected,
                "computed_value": computed,
                "signed_error": computed - expected,
                "relative_error": relative_error,
                "relative_error_limit": float(args.relative_error_limit),
                "source_reproduction_status": "PASS" if relative_error <= args.relative_error_limit else "FAIL",
                "digitization_uncertainty": float(reference_row["digitization_uncertainty"]),
                "gate_relative_tolerance": float(args.gate_relative_tolerance),
                "gate_error_ratio": float(gate_metrics["gate_error_ratio"]),
                "gate_status": str(gate_metrics["status"]),
                "station_count": int(reference_row["station_count"]),
                "body_panel_count": int(args.body_panels),
                "free_surface_panel_count_per_side": int(args.free_surface_panels),
                "control_surface_panel_count_per_side": int(max(2 * args.free_surface_panels, args.free_surface_panels)),
                "provider_route": str(calc.get("provider_route", "")),
                "force_assembly_route": str(calc.get("matched_force_assembly_route", "")),
                "apply_local_time_phase": bool(calc.get("matched_apply_local_time_phase", False)),
                "local_time_phase_gradient_correction": bool(
                    calc.get("matched_local_time_phase_gradient_correction", False)
                ),
                "clip_inner_free_surface_to_waterline": bool(
                    calc.get("matched_clip_inner_free_surface_to_waterline", False)
                ),
                "two_zone_inner_free_surface": bool(calc.get("matched_two_zone_inner_free_surface", False)),
                "reference_series": str(reference_row["reference_series"]),
                "reference_role": str(reference_row["reference_role"]),
                "source_figure": str(reference_row["source_figure"]),
                "source_page": str(reference_row["source_page"]),
                "source_image": str(reference_row["source_image"]),
                "empirical_output_scaling_used": False,
            }
        )

    detail = pd.DataFrame(rows)
    finite = bool(np.isfinite(detail[["reference_value", "computed_value", "relative_error"]]).all().all())
    all_pass = bool(detail["source_reproduction_status"].astype(str).eq("PASS").all())
    summary = pd.DataFrame(
        [
            {
                "row_count": len(detail),
                "pass_count": int(detail["source_reproduction_status"].astype(str).eq("PASS").sum()),
                "fail_count": int(detail["source_reproduction_status"].astype(str).eq("FAIL").sum()),
                "max_relative_error": float(detail["relative_error"].max()),
                "relative_error_limit": float(args.relative_error_limit),
                "finite_outputs": finite,
                "provider_route_unique": ";".join(sorted(set(detail["provider_route"].astype(str)))),
                "force_assembly_route_unique": ";".join(sorted(set(detail["force_assembly_route"].astype(str)))),
                "empirical_output_scaling_used": False,
                "acceptance_status": "PASS" if all_pass and finite else "FAIL",
                "reference_file": str(reference_path),
            }
        ]
    )
    detail.to_csv(out_dir / "ma2005_a33_a53_source_resolution.csv", index=False)
    summary.to_csv(out_dir / "ma2005_a33_a53_source_resolution_summary.csv", index=False)
    print(detail.to_string(index=False))
    print(summary.to_string(index=False))
    return 0 if all_pass and finite else 1


if __name__ == "__main__":
    raise SystemExit(main())
