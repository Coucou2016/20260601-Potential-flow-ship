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
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _curve(
    rows: list[dict[str, str]],
    *,
    beta_deg: float | None = None,
    quantity: str | None = None,
    x_column: str = "x_nondimensional",
    y_column: str = "y_nondimensional",
) -> tuple[np.ndarray, np.ndarray]:
    selected = [
        row
        for row in rows
        if (beta_deg is None or float(row["beta_deg"]) == beta_deg)
        and (quantity is None or row["quantity"] == quantity)
    ]
    x = np.asarray([float(row[x_column]) for row in selected], dtype=float)
    y = np.asarray([float(row[y_column]) for row in selected], dtype=float)
    order = np.argsort(x)
    return x[order], y[order]


def _metrics(predicted: np.ndarray, reference: np.ndarray) -> dict[str, float]:
    difference = np.asarray(predicted) - np.asarray(reference)
    rmse = float(np.sqrt(np.mean(np.square(difference))))
    reference_range = float(np.ptp(reference))
    return {
        "rmse": rmse,
        "nrmse_by_reference_range": rmse / reference_range,
        "mean_bias_predicted_minus_reference": float(np.mean(difference)),
        "maximum_absolute_error": float(np.max(np.abs(difference))),
        "reference_range": reference_range,
    }


def _legacy_change_summary(
    current_rows: list[dict[str, str]], legacy_rows: list[dict[str, str]]
) -> list[dict[str, object]]:
    current_fields = set(current_rows[0]) if current_rows else set()
    legacy_fields = set(legacy_rows[0]) if legacy_rows else set()
    pixel_fields = {"pixel_x", "pixel_y_median"}
    if not pixel_fields.issubset(current_fields & legacy_fields):
        summaries: list[dict[str, object]] = []
        for beta_deg in (10.0, 20.0, 30.0):
            current_x, current_y = _curve(
                current_rows, beta_deg=beta_deg, quantity="free_surface"
            )
            legacy_x, legacy_y = _curve(
                legacy_rows, beta_deg=beta_deg, quantity="free_surface"
            )
            lower = max(float(current_x[0]), float(legacy_x[0]))
            upper = min(float(current_x[-1]), float(legacy_x[-1]))
            mask = (current_x >= lower) & (current_x <= upper)
            comparison_x = current_x[mask]
            interpolated_legacy = np.interp(comparison_x, legacy_x, legacy_y)
            summaries.append(
                {
                    "beta_deg": beta_deg,
                    "comparison_mode": "dimensionless_curve_interpolation",
                    "legacy_point_count": len(legacy_x),
                    "current_point_count": len(current_x),
                    "compared_point_count": len(comparison_x),
                    "x_min": float(comparison_x[0]),
                    "x_max": float(comparison_x[-1]),
                    **_metrics(current_y[mask], interpolated_legacy),
                }
            )
        return summaries

    summaries: list[dict[str, object]] = []
    for beta_deg in (10.0, 20.0, 30.0):
        current = {
            int(row["pixel_x"]): float(row["pixel_y_median"])
            for row in current_rows
            if float(row["beta_deg"]) == beta_deg and row["quantity"] == "free_surface"
        }
        legacy = {
            int(row["pixel_x"]): float(row["pixel_y_median"])
            for row in legacy_rows
            if float(row["beta_deg"]) == beta_deg and row["quantity"] == "free_surface"
        }
        shared = sorted(set(current) & set(legacy))
        changed = [x for x in shared if current[x] != legacy[x]]
        summaries.append(
            {
                "beta_deg": beta_deg,
                "legacy_point_count": len(legacy),
                "current_point_count": len(current),
                "removed_legacy_columns": sorted(set(legacy) - set(current)),
                "changed_shared_columns": changed,
                "maximum_absolute_pixel_row_change": (
                    max(abs(current[x] - legacy[x]) for x in changed) if changed else 0.0
                ),
            }
        )
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit Zhao-Faltinsen and Iafrati wedge free-surface references."
    )
    parser.add_argument("--zhao", type=Path, required=True)
    parser.add_argument("--zhao-legacy", type=Path, required=True)
    parser.add_argument("--iafrati", type=Path, required=True)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    current_rows = _read_rows(args.zhao)
    legacy_rows = _read_rows(args.zhao_legacy)
    iafrati_rows = _read_rows(args.iafrati)
    zhao_x, zhao_eta = _curve(
        current_rows, beta_deg=20.0, quantity="free_surface"
    )
    iafrati_x, iafrati_eta = _curve(iafrati_rows)
    common_mask = (zhao_x >= iafrati_x[0]) & (zhao_x <= iafrati_x[-1])
    common_x = zhao_x[common_mask]
    common_zhao = zhao_eta[common_mask]
    common_iafrati = np.interp(common_x, iafrati_x, iafrati_eta)

    pointwise: list[dict[str, object]] = []
    candidate_common: np.ndarray | None = None
    candidate_x: np.ndarray | None = None
    candidate_eta: np.ndarray | None = None
    candidate_metrics: dict[str, object] | None = None
    if args.candidate is not None:
        candidate_rows = _read_rows(args.candidate)
        candidate_x, candidate_eta = _curve(
            candidate_rows, x_column="xi", y_column="eta"
        )
        candidate_common = np.interp(common_x, candidate_x, candidate_eta)
        full_mask = (iafrati_x >= candidate_x[0]) & (iafrati_x <= candidate_x[-1])
        candidate_metrics = {
            "same_abscissae_zhao": _metrics(candidate_common, common_zhao),
            "same_abscissae_iafrati": _metrics(candidate_common, common_iafrati),
            "full_iafrati_overlap": {
                "point_count": int(np.count_nonzero(full_mask)),
                **_metrics(
                    np.interp(iafrati_x[full_mask], candidate_x, candidate_eta),
                    iafrati_eta[full_mask],
                ),
            },
        }

    for index, x_value in enumerate(common_x):
        row: dict[str, object] = {
            "x_nondimensional": float(x_value),
            "zhao_eta": float(common_zhao[index]),
            "iafrati_eta_interpolated": float(common_iafrati[index]),
            "zhao_minus_iafrati": float(common_zhao[index] - common_iafrati[index]),
        }
        if candidate_common is not None:
            row.update(
                {
                    "candidate_eta_interpolated": float(candidate_common[index]),
                    "candidate_minus_zhao": float(candidate_common[index] - common_zhao[index]),
                    "candidate_minus_iafrati": float(
                        candidate_common[index] - common_iafrati[index]
                    ),
                }
            )
        pointwise.append(row)

    pointwise_path = out / "free_surface_reference_pointwise.csv"
    with pointwise_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(pointwise[0]))
        writer.writeheader()
        writer.writerows(pointwise)

    report = {
        "status": "REFERENCE_DISCREPANCY_REQUIRES_DUAL_REPORTING",
        "acceptance_effect": (
            "The independent Iafrati curve is a cross-audit, not a replacement "
            "chosen to improve acceptance. Gate 2 remains unchanged until the "
            "declared Zhao-Faltinsen and convergence gates are resolved."
        ),
        "reference_used_during_solve": False,
        "inputs": {
            "zhao": {"path": str(args.zhao), "sha256": _sha256(args.zhao)},
            "zhao_legacy": {
                "path": str(args.zhao_legacy),
                "sha256": _sha256(args.zhao_legacy),
            },
            "iafrati": {"path": str(args.iafrati), "sha256": _sha256(args.iafrati)},
            "candidate": (
                {"path": str(args.candidate), "sha256": _sha256(args.candidate)}
                if args.candidate is not None
                else None
            ),
        },
        "legacy_digitization_changes": _legacy_change_summary(current_rows, legacy_rows),
        "zhao_vs_iafrati_same_abscissae": {
            "point_count": len(common_x),
            "x_min": float(common_x[0]),
            "x_max": float(common_x[-1]),
            **_metrics(common_zhao, common_iafrati),
        },
        "candidate_metrics": candidate_metrics,
        "pointwise_csv": pointwise_path.name,
        "pointwise_csv_sha256": _sha256(pointwise_path),
    }
    report_path = out / "free_surface_reference_audit.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    figure, axes = plt.subplots(1, 2, figsize=(11.0, 4.2), constrained_layout=True)
    for beta_deg, marker in ((10.0, "o"), (20.0, "s"), (30.0, "^")):
        x, y = _curve(current_rows, beta_deg=beta_deg, quantity="free_surface")
        axes[0].plot(x, y, marker, ms=3.0, linestyle="none", label=f"{beta_deg:g} deg")
    axes[0].set_title("Branch-aware Zhao-Faltinsen digitization")
    axes[0].set_xlabel(r"$y/(Vt)$")
    axes[0].set_ylabel(r"$z/(Vt)$")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(frameon=False)

    axes[1].plot(zhao_x, zhao_eta, "o", ms=3.0, label="Zhao-Faltinsen (Sun Fig. 2.6)")
    axes[1].plot(iafrati_x, iafrati_eta, "-", lw=1.5, label="Iafrati 2013 vector")
    if candidate_x is not None and candidate_eta is not None:
        axes[1].plot(candidate_x, candidate_eta, "--", lw=1.5, label="Current candidate")
    axes[1].set_xlim(4.0, 20.0)
    axes[1].set_title("Independent 20 deg reference audit")
    axes[1].set_xlabel(r"$y/(Vt)$")
    axes[1].set_ylabel(r"$z/(Vt)$")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(frameon=False)
    figure.savefig(out / "free_surface_reference_audit.png", dpi=180)
    plt.close(figure)

    print(json.dumps({"out": str(out), "status": report["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
