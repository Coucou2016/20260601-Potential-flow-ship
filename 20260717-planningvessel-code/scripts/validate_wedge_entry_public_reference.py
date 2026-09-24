from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _xy(rows: list[dict[str, str]], x_name: str, y_name: str) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray([float(row[x_name]) for row in rows], dtype=float)
    y = np.asarray([float(row[y_name]) for row in rows], dtype=float)
    order = np.argsort(x)
    return x[order], y[order]


def _curve_metrics(model: np.ndarray, reference: np.ndarray) -> dict[str, float]:
    residual = np.asarray(model) - np.asarray(reference)
    rmse = float(np.sqrt(np.mean(np.square(residual))))
    scale = max(float(np.ptp(reference)), 1.0e-12)
    return {
        "rmse": rmse,
        "nrmse_by_reference_range": rmse / scale,
        "mean_bias": float(np.mean(residual)),
        "maximum_absolute_error": float(np.max(np.abs(residual))),
    }


def _comparison_rows(
    model_x: np.ndarray,
    model_y: np.ndarray,
    reference_x: np.ndarray,
    reference_y: np.ndarray,
) -> tuple[list[dict[str, float]], dict[str, float]]:
    mask = (reference_x >= model_x[0]) & (reference_x <= model_x[-1])
    x = reference_x[mask]
    reference = reference_y[mask]
    model = np.interp(x, model_x, model_y)
    rows = [
        {
            "coordinate": float(coordinate),
            "model": float(model_value),
            "reference": float(reference_value),
            "residual": float(model_value - reference_value),
        }
        for coordinate, model_value, reference_value in zip(x, model, reference)
    ]
    return rows, {"point_count": len(rows), **_curve_metrics(model, reference)}


def _write_rows(path: Path, rows: list[dict[str, float]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate a completed 20-degree self-similar wedge-entry solution against public references."
    )
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--zhao-curves", type=Path, required=True)
    parser.add_argument("--iafrati-free-surface", type=Path, required=True)
    parser.add_argument("--iafrati-scalars", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    pressure_path = args.candidate / "coupled_body_pressure.csv"
    free_surface_path = args.candidate / "coupled_checkpoint_outer_nodes.csv"
    summary_path = args.candidate / "resume_summary.json"

    pressure_rows = _read_csv(pressure_path)
    model_pressure_eta, model_pressure = _xy(pressure_rows, "eta", "pressure_coefficient")
    model_free_x, model_free_eta = _xy(_read_csv(free_surface_path), "xi", "eta")

    reference_rows = _read_csv(args.zhao_curves)
    zhao_pressure_rows = [
        row for row in reference_rows if float(row["beta_deg"]) == 20.0 and row["quantity"] == "pressure"
    ]
    reference_pressure_eta, reference_pressure = _xy(
        zhao_pressure_rows,
        "x_nondimensional",
        "y_nondimensional",
    )
    iafrati_free_x, iafrati_free_eta = _xy(
        _read_csv(args.iafrati_free_surface),
        "x_nondimensional",
        "y_nondimensional",
    )

    pressure_comparison, pressure_metrics = _comparison_rows(
        model_pressure_eta,
        model_pressure,
        reference_pressure_eta,
        reference_pressure,
    )
    free_comparison, free_metrics = _comparison_rows(
        model_free_x,
        model_free_eta,
        iafrati_free_x,
        iafrati_free_eta,
    )
    _write_rows(out / "pressure_comparison.csv", pressure_comparison)
    _write_rows(out / "free_surface_comparison.csv", free_comparison)

    scalar_row = next(
        row for row in _read_csv(args.iafrati_scalars) if np.isclose(float(row["deadrise_deg"]), 20.0)
    )
    candidate_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    final_state = candidate_summary["final_state"]
    scalar_metrics = candidate_summary["post_solve_scalar_reference_metrics"]
    model_force = float(final_state["body_vertical_force_coefficient"])
    trapezoid = np.trapezoid
    reference_force = float(trapezoid(reference_pressure, reference_pressure_eta) / np.tan(np.deg2rad(20.0)))
    force_error = abs(model_force - reference_force) / abs(reference_force)
    peak_error = abs(float(final_state["body_pressure_max"]) - float(scalar_row["pressure_coefficient_peak"])) / abs(
        float(scalar_row["pressure_coefficient_peak"])
    )
    location_error = abs(float(scalar_metrics["computed_peak_eta"]) - float(scalar_row["peak_eta"])) / abs(
        float(scalar_row["peak_eta"])
    )

    thresholds = {
        "free_surface_nrmse_max": 0.10,
        "pressure_nrmse_max": 0.15,
        "pressure_peak_relative_error_max": 0.10,
        "pressure_peak_location_relative_error_max": 0.10,
        "vertical_force_relative_error_max": 0.10,
    }
    checks = {
        "free_surface_shape": free_metrics["nrmse_by_reference_range"] <= thresholds["free_surface_nrmse_max"],
        "pressure_distribution": pressure_metrics["nrmse_by_reference_range"] <= thresholds["pressure_nrmse_max"],
        "pressure_peak": peak_error <= thresholds["pressure_peak_relative_error_max"],
        "pressure_peak_location": location_error <= thresholds["pressure_peak_location_relative_error_max"],
        "integrated_vertical_force": force_error <= thresholds["vertical_force_relative_error_max"],
    }

    figure, axes = plt.subplots(2, 2, figsize=(12.0, 8.0), constrained_layout=True)
    ax = axes[0, 0]
    wedge_half_width = 5.4
    apex_z = -1.0
    top_z = apex_z + wedge_half_width * np.tan(np.deg2rad(20.0))
    ax.fill(
        [-wedge_half_width, 0.0, wedge_half_width],
        [top_z, apex_z, top_z],
        color="#d9dde3",
        edgecolor="#202630",
        linewidth=1.2,
        label="closed finite 20 deg wedge body",
    )
    ax.plot(model_free_x, model_free_eta, color="#007c91", linewidth=2.0, label="computed free surface")
    ax.plot(-model_free_x, model_free_eta, color="#007c91", linewidth=2.0)
    contact_x = float(model_free_x[0])
    ax.plot([-contact_x, contact_x], [model_free_eta[0], model_free_eta[0]], "o", color="#cf4b32", ms=4)
    ax.axhline(0.0, color="#5a7896", linewidth=1.0, linestyle="--", label="undisturbed waterline")
    ax.set_xlim(-8.0, 8.0)
    ax.set_ylim(-1.15, 1.10)
    ax.set_aspect("equal", adjustable="box")
    ax.set_title("(a) Computed wedge and free-surface relation")
    ax.set_xlabel(r"horizontal similarity coordinate $y/(Vt)$")
    ax.set_ylabel(r"vertical similarity coordinate $z/(Vt)$")
    ax.grid(True, alpha=0.2)
    ax.legend(frameon=False, fontsize=8, loc="upper right")

    ax = axes[0, 1]
    ax.plot(iafrati_free_x, iafrati_free_eta, color="#202630", linewidth=2.0, label="Iafrati 2013 public solution")
    ax.plot(model_free_x, model_free_eta, color="#007c91", linewidth=1.8, linestyle="--", label="current solver")
    ax.set_xlim(4.0, 20.0)
    ax.set_title("(b) Outer free-surface validation")
    ax.set_xlabel(r"$y/(Vt)$")
    ax.set_ylabel(r"$z/(Vt)$")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False, fontsize=8)

    ax = axes[1, 0]
    ax.plot(reference_pressure_eta, reference_pressure, color="#202630", linewidth=2.0, label="Zhao-Faltinsen public curve")
    ax.plot(model_pressure_eta, model_pressure, color="#cf4b32", linewidth=1.4, linestyle="--", label="current solver")
    ax.set_title("(c) Wetted-body pressure validation")
    ax.set_xlabel(r"vertical similarity coordinate $z/(Vt)$")
    ax.set_ylabel(r"$C_p=2p/(\rho V^2)$")
    ax.grid(True, alpha=0.25)
    ax.legend(frameon=False, fontsize=8)

    ax = axes[1, 1]
    ax.bar(["current solver", "public curve integral"], [model_force, reference_force], color=["#007c91", "#69717d"])
    ax.set_title("(d) Integrated vertical-force coefficient")
    ax.set_ylabel(r"$C_F=\int C_p\,d[z/(Vt)]/\tan\beta$")
    ax.grid(True, axis="y", alpha=0.25)
    for index, value in enumerate((model_force, reference_force)):
        ax.text(index, value + 0.5, f"{value:.2f}", ha="center", va="bottom")
    figure_path = out / "wedge_entry_public_validation.png"
    figure.savefig(figure_path, dpi=200)
    plt.close(figure)

    report = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "gate": "W-1 self-similar 20-degree wedge-entry public-reference validation",
        "reference_used_during_solve": False,
        "evidence_class": (
            "Public nonlinear numerical/self-similar references. This is not an experimental EFD closure; "
            "the Aarsnes free-drop experiment remains a separate future gate."
        ),
        "thresholds": thresholds,
        "checks": checks,
        "metrics": {
            "free_surface": free_metrics,
            "pressure_distribution": pressure_metrics,
            "pressure_peak_relative_error": peak_error,
            "pressure_peak_location_relative_error": location_error,
            "computed_vertical_force_coefficient": model_force,
            "reference_vertical_force_coefficient_from_pressure_curve": reference_force,
            "vertical_force_relative_error": force_error,
        },
        "inputs": {
            "candidate_pressure": {"path": str(pressure_path.resolve()), "sha256": _sha256(pressure_path)},
            "candidate_free_surface": {"path": str(free_surface_path.resolve()), "sha256": _sha256(free_surface_path)},
            "zhao_pressure_curve": {"path": str(args.zhao_curves.resolve()), "sha256": _sha256(args.zhao_curves)},
            "iafrati_free_surface": {
                "path": str(args.iafrati_free_surface.resolve()),
                "sha256": _sha256(args.iafrati_free_surface),
            },
            "iafrati_table_1": {"path": str(args.iafrati_scalars.resolve()), "sha256": _sha256(args.iafrati_scalars)},
        },
        "outputs": {
            "figure": str(figure_path.resolve()),
            "free_surface_comparison": str((out / "free_surface_comparison.csv").resolve()),
            "pressure_comparison": str((out / "pressure_comparison.csv").resolve()),
        },
    }
    report_path = out / "wedge_entry_public_validation.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "metrics": report["metrics"]}, indent=2))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
