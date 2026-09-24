from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class CurveSpec:
    beta_deg: float
    quantity: str
    image_name: str
    x_name: str
    y_name: str
    x_pixel_at_value_0: float
    x_value_0: float
    x_pixel_at_value_1: float
    x_value_1: float
    y_pixel_at_value_0: float
    y_value_0: float
    y_pixel_at_value_1: float
    y_value_1: float
    roi: tuple[int, int, int, int]
    excluded_rectangles: tuple[tuple[int, int, int, int], ...] = ()


SPECS = (
    CurveSpec(10.0, "free_surface", "87cd7258419cf88d1169caeb3f1eeb31a9eafaa4b1295eb31f1e0b5f8c29c820.jpg", "y_over_Vt", "z_over_Vt", 73.0, 0.0, 514.0, 20.0, 354.0, -2.0, 19.0, 2.0, (250, 125, 520, 220)),
    CurveSpec(10.0, "pressure", "ea1a88cc8edd35ff7aaf7cdfae1aed568fd0a2894c397b169a38df7fc891c9fc.jpg", "z_over_Vt", "p_over_half_rho_V2", 84.0, -1.0, 525.0, 1.0, 307.0, 0.0, 42.0, 80.0, (75, 15, 530, 345), ((95, 45, 255, 155),)),
    CurveSpec(20.0, "free_surface", "f0fe6b08afe9bd3b39c3799011c2fcd9bc711e3ab0870b5be0ecaec81c0a7fd6.jpg", "y_over_Vt", "z_over_Vt", 78.0, 0.0, 516.0, 10.0, 340.0, -5.0, 18.0, 5.0, (250, 165, 522, 230)),
    CurveSpec(20.0, "pressure", "7f3140e6b370455490b99886c15efbca5fd5569e6879072976d19f13a395c304.jpg", "z_over_Vt", "p_over_half_rho_V2", 79.0, -1.0, 516.0, 1.0, 342.0, 0.0, 21.0, 20.0, (72, 15, 522, 347), ((95, 45, 270, 155),)),
    CurveSpec(30.0, "free_surface", "bffa4507d635a13274c955b90abe92d7685a16895ebbddc1fa6029bf2a34552e.jpg", "y_over_Vt", "z_over_Vt", 77.0, 0.0, 516.0, 6.0, 349.0, -3.0, 19.0, 3.0, (250, 145, 522, 230)),
    CurveSpec(30.0, "pressure", "b84b1bbf81acc517f7170824b0e7c59eaf5586219d72312ab56ce608295bbe65.jpg", "z_over_Vt", "p_over_half_rho_V2", 78.0, -1.0, 514.0, 1.0, 343.0, 0.0, 11.0, 8.0, (72, 8, 520, 348), ((95, 45, 260, 155),)),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _linear_map(pixel: np.ndarray, p0: float, v0: float, p1: float, v1: float) -> np.ndarray:
    return v0 + (pixel - p0) * (v1 - v0) / (p1 - p0)


def _contiguous_pixel_runs(pixel_rows: np.ndarray) -> list[np.ndarray]:
    rows = np.sort(np.asarray(pixel_rows, dtype=int))
    if rows.size == 0:
        return []
    return list(np.split(rows, np.flatnonzero(np.diff(rows) > 1) + 1))


def _select_outer_free_surface_clusters(
    pixel_x: np.ndarray,
    pixel_y: np.ndarray,
    *,
    backtrack_tolerance_px: float = 1.0,
) -> dict[int, tuple[float, int, int]]:
    """Trace the lower, outward-decaying branch without blending spray pixels."""

    selected: dict[int, tuple[float, int, int]] = {}
    running_lower_row: float | None = None
    for x_value in np.unique(pixel_x):
        column_rows = pixel_y[pixel_x == x_value]
        clusters = _contiguous_pixel_runs(column_rows)
        # Image rows grow downward.  The physical outer free surface is the
        # bottommost branch after the spray-root fold.
        cluster = max(clusters, key=lambda values: float(np.median(values)))
        representative = float(np.median(cluster))
        if (
            running_lower_row is not None
            and representative < running_lower_row - backtrack_tolerance_px
        ):
            # A dashed-gap can expose only the upward spray branch in a column.
            # Skipping it retains observed pixels and avoids fabricated points.
            continue
        selected[int(x_value)] = (representative, int(cluster.size), len(clusters))
        running_lower_row = (
            representative
            if running_lower_row is None
            else max(running_lower_row, representative)
        )
    return selected


def _extract(spec: CurveSpec, source_dir: Path) -> list[dict[str, object]]:
    path = source_dir / spec.image_name
    rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.int16)
    red, green, blue = np.moveaxis(rgb, -1, 0)
    mask = (blue >= 115) & ((blue - red) >= 25) & ((blue - green) >= 12)
    x0, y0, x1, y1 = spec.roi
    roi_mask = np.zeros(mask.shape, dtype=bool)
    roi_mask[y0 : y1 + 1, x0 : x1 + 1] = True
    mask &= roi_mask
    for rx0, ry0, rx1, ry1 in spec.excluded_rectangles:
        mask[ry0 : ry1 + 1, rx0 : rx1 + 1] = False
    pixel_y, pixel_x = np.where(mask)
    if len(pixel_x) < 30:
        raise RuntimeError(f"Too few similarity-curve pixels extracted from {path}: {len(pixel_x)}")

    if spec.quantity == "free_surface":
        selected_columns = _select_outer_free_surface_clusters(pixel_x, pixel_y)
        branch_policy = "bottommost_contiguous_cluster_monotone_outer_branch"
    else:
        selected_columns = {
            int(x): (
                float(np.median(pixel_y[pixel_x == x])),
                int(np.count_nonzero(pixel_x == x)),
                len(_contiguous_pixel_runs(pixel_y[pixel_x == x])),
            )
            for x in np.unique(pixel_x)
        }
        branch_policy = "all_blue_pixels_column_median"

    rows: list[dict[str, object]] = []
    for x, (y, selected_count, cluster_count) in selected_columns.items():
        y_values = pixel_y[pixel_x == x]
        x_value = float(
            _linear_map(
                np.asarray(float(x)),
                spec.x_pixel_at_value_0,
                spec.x_value_0,
                spec.x_pixel_at_value_1,
                spec.x_value_1,
            )
        )
        y_value = float(
            _linear_map(
                np.asarray(y),
                spec.y_pixel_at_value_0,
                spec.y_value_0,
                spec.y_pixel_at_value_1,
                spec.y_value_1,
            )
        )
        rows.append(
            {
                "beta_deg": spec.beta_deg,
                "quantity": spec.quantity,
                "x_name": spec.x_name,
                "x_nondimensional": x_value,
                "y_name": spec.y_name,
                "y_nondimensional": y_value,
                "pixel_x": int(x),
                "pixel_y_median": y,
                "pixel_count_in_column": int(len(y_values)),
                "selected_cluster_pixel_count": selected_count,
                "cluster_count_in_column": cluster_count,
                "branch_policy": branch_policy,
                "source_image": spec.image_name,
                "reference_curve": "Zhao-Faltinsen_similarity_SIM_blue_dashed",
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Digitize Sun 2007 Fig. 2.6 similarity curves.")
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    # Keep a relative source path intact on Windows. Some legacy Python builds
    # decode a Unicode current directory inconsistently after Path.resolve().
    source_dir = args.source_dir
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    sources: list[dict[str, object]] = []
    for spec in SPECS:
        path = source_dir / spec.image_name
        if not path.is_file():
            raise FileNotFoundError(path)
        curve_rows = _extract(spec, source_dir)
        rows.extend(curve_rows)
        sources.append(
            {
                "beta_deg": spec.beta_deg,
                "quantity": spec.quantity,
                "image_name": spec.image_name,
                "sha256": _sha256(path),
                "point_count": len(curve_rows),
                "calibration": asdict(spec),
            }
        )

    csv_path = out / "fig2_6_zhao_faltinsen_similarity_curves.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        "benchmark": "Sun 2007 Fig. 2.6 Zhao-Faltinsen wedge-entry similarity curves",
        "source": "A3, Section 2.8, Fig. 2.6, PDF page 41 / printed page 29",
        "curve_policy": "Only the blue dashed SIM curve is a reference; Sun's BEM curve is not a target.",
        "digitization_policy": (
            "Blue JPEG pixels are thresholded inside frozen plot ROIs and legend "
            "rectangles are excluded. Pressure uses the all-pixel column median. "
            "Free-surface columns are split into contiguous row clusters; the "
            "bottommost cluster is traced with a frozen 1 px monotonic-backtrack "
            "tolerance so the outward-decaying branch is never blended with the "
            "upward spray branch. Dashed-gap columns exposing only the spray branch "
            "are omitted rather than interpolated."
        ),
        "free_surface_branch": "lower outward-decaying branch after the spray-root fold",
        "free_surface_backtrack_tolerance_px": 1.0,
        "supersedes": {
            "artifact": "legacy_column_median_v1/fig2_6_zhao_faltinsen_similarity_curves.csv",
            "csv_sha256": "27501c457dbe61fa2ad9c2bea020ed66780cb7ab6214f3c3f7317d045eb8c994",
            "reason": (
                "The legacy all-pixel median can lie between separated spray and "
                "outer-free-surface pixel clusters."
            ),
        },
        "axis_calibration_uncertainty_px": 2.0,
        "source_directory": str(source_dir),
        "sources": sources,
        "row_count": len(rows),
        "csv": csv_path.name,
        "csv_sha256": _sha256(csv_path),
        "response_calibration_used": False,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"out": str(out), "row_count": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
