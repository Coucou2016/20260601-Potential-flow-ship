from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class PanelDigitization:
    panel: str
    coefficient: str
    image_name: str
    x_pixels: tuple[float, ...]
    y_pixels: tuple[float, ...]
    x_pixel_limits: tuple[float, float]
    x_axis_limits: tuple[float, float]
    y_pixel_limits: tuple[float, float]
    y_axis_limits: tuple[float, float]
    x_quantity: str
    y_quantity: str
    fit_indices: tuple[int, ...] = (1, 2, 3, 4, 5)


PANELS = (
    PanelDigitization(
        panel="7.4a",
        coefficient="C33",
        image_name="ec25dedb22831e74e285696ff8b33566c33cfe25be1e3029d0e78e31c9ca0110.jpg",
        x_pixels=(156, 198, 241, 283, 325, 368, 410),
        y_pixels=(79, 125, 168, 204, 234, 260, 281),
        x_pixel_limits=(71, 495),
        x_axis_limits=(-0.2, 0.2),
        y_pixel_limits=(332, 13),
        y_axis_limits=(0.0, 0.2),
        x_quantity="eta3_over_B",
        y_quantity="F3_over_rho_U2_B2",
    ),
    PanelDigitization(
        panel="7.4b",
        coefficient="C53",
        image_name="21b62106a197f81013fba6634ef4036a547f3857294fb359bfc353ca72ada1b3.jpg",
        x_pixels=(161, 204, 247, 290, 333, 376, 419),
        y_pixels=(116, 180, 225, 255, 273, 285, 291),
        x_pixel_limits=(75, 504),
        x_axis_limits=(-0.2, 0.2),
        y_pixel_limits=(330, 13),
        y_axis_limits=(-0.05, 0.15),
        x_quantity="eta3_over_B",
        y_quantity="F5_over_rho_U2_B3",
    ),
    PanelDigitization(
        panel="7.4c",
        coefficient="C35",
        image_name="5ac17c094bb26a53b984418b351e0fce09bbbd65cafb72e45114f198a7300366.jpg",
        x_pixels=(156, 199, 241, 284, 327, 369, 412),
        y_pixels=(225, 220, 212, 203, 195, 182, 169),
        x_pixel_limits=(71, 497),
        x_axis_limits=(-3.0, 3.0),
        y_pixel_limits=(331, 14),
        y_axis_limits=(0.0, 0.2),
        x_quantity="eta5_deg",
        y_quantity="F3_over_rho_U2_B2",
    ),
    PanelDigitization(
        panel="7.4d",
        coefficient="C55",
        image_name="2b8cb600563c160aa85af6638633ccd52ea3cb2ac1d63cd4dd096f53de02ce02.jpg",
        x_pixels=(161, 204, 247, 289, 332, 375, 418),
        y_pixels=(224, 239, 250, 258, 263, 273, 279),
        x_pixel_limits=(75, 503),
        x_axis_limits=(-3.0, 3.0),
        y_pixel_limits=(334, 15),
        y_axis_limits=(-0.05, 0.15),
        x_quantity="eta5_deg",
        y_quantity="F5_over_rho_U2_B3",
    ),
)


# Sun (2007), Sec. 7.4 states that Troesch's forced-motion reduction used
# restoring coefficients taken at zero displacement from the steady
# experimental data.  The square markers in Fig. 7.4(a-b) are therefore a
# distinct source from the numerical-circle benchmark above.  Only the heave
# column is digitized here because those two panels are the evidence needed by
# the forced-heave A33/A53 convergence study.
TROESCH_HEAVE_EXPERIMENTAL_PANELS = (
    PanelDigitization(
        panel="7.4a",
        coefficient="C33",
        image_name="ec25dedb22831e74e285696ff8b33566c33cfe25be1e3029d0e78e31c9ca0110.jpg",
        x_pixels=(150, 192, 235, 277, 319, 362, 404),
        y_pixels=(81, 126, 171, 206, 237, 263, 284),
        x_pixel_limits=(71, 495),
        x_axis_limits=(-0.2, 0.2),
        y_pixel_limits=(332, 13),
        y_axis_limits=(0.0, 0.2),
        x_quantity="eta3_over_B",
        y_quantity="F3_over_rho_U2_B2",
    ),
    PanelDigitization(
        panel="7.4b",
        coefficient="C53",
        image_name="21b62106a197f81013fba6634ef4036a547f3857294fb359bfc353ca72ada1b3.jpg",
        x_pixels=(156, 198, 241, 284, 327, 370, 413),
        y_pixels=(120, 181, 225, 247, 266, 274, 278),
        x_pixel_limits=(75, 504),
        x_axis_limits=(-0.2, 0.2),
        y_pixel_limits=(330, 13),
        y_axis_limits=(-0.05, 0.15),
        x_quantity="eta3_over_B",
        y_quantity="F5_over_rho_U2_B3",
    ),
)


TROESCH_PITCH_EXPERIMENTAL_PANELS = (
    PanelDigitization(
        panel="7.4c",
        coefficient="C35",
        image_name="5ac17c094bb26a53b984418b351e0fce09bbbd65cafb72e45114f198a7300366.jpg",
        x_pixels=(157.568, 201.269, 243.301, 286.335, 328.368, 371.068, 414.102),
        y_pixels=(248.413, 246.578, 240.071, 233.564, 225.556, 215.545, 207.871),
        x_pixel_limits=(71, 497),
        x_axis_limits=(-3.0, 3.0),
        y_pixel_limits=(331, 14),
        y_axis_limits=(0.0, 0.2),
        x_quantity="eta5_deg",
        y_quantity="F3_over_rho_U2_B2",
    ),
    PanelDigitization(
        panel="7.4d",
        coefficient="C55",
        image_name="2b8cb600563c160aa85af6638633ccd52ea3cb2ac1d63cd4dd096f53de02ce02.jpg",
        x_pixels=(162.265, 206.564, 247.366, 290.499, 332.799, 376.099, 419.898),
        y_pixels=(229.718, 238.865, 244.853, 252.171, 255.165, 259.822, 256.495),
        x_pixel_limits=(75, 503),
        x_axis_limits=(-3.0, 3.0),
        y_pixel_limits=(334, 15),
        y_axis_limits=(-0.05, 0.15),
        x_quantity="eta5_deg",
        y_quantity="F5_over_rho_U2_B3",
    ),
)

TROESCH_EXPERIMENTAL_PANELS = (
    *TROESCH_HEAVE_EXPERIMENTAL_PANELS,
    *TROESCH_PITCH_EXPERIMENTAL_PANELS,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reproduce the Sun (2007) Fig. 7.4 zero-offset restoring slopes."
    )
    parser.add_argument(
        "--images",
        type=Path,
        default=Path("../20260729-文献收集/md/A3_images"),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("benchmarks/sun2007_fig7_4_restoring"),
    )
    parser.add_argument(
        "--series",
        choices=("numerical", "troesch_heave_experiment", "troesch_experiment"),
        default="numerical",
        help="Fig. 7.4 marker series to digitize.",
    )
    parser.add_argument("--pixel-uncertainty", type=float, default=2.0)
    return parser


def _linear_map(
    pixels: np.ndarray,
    pixel_limits: tuple[float, float],
    axis_limits: tuple[float, float],
) -> np.ndarray:
    p0, p1 = pixel_limits
    a0, a1 = axis_limits
    return a0 + (np.asarray(pixels, dtype=float) - p0) * (a1 - a0) / (p1 - p0)


def _stable_float(value: float) -> float:
    """Remove BLAS-level last-bit noise before writing benchmark artifacts."""
    # Twelve significant digits remain far below the source-image digitization
    # uncertainty while avoiding LAPACK-dependent last-bit drift in polyfit.
    return float(f"{float(value):.12g}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    # pathlib.Path.open() in the bundled Miniforge runtime can fail on this
    # Chinese source directory even after Path.exists()/stat() succeed. Passing
    # the Unicode path string to the built-in opener keeps the benchmark
    # reproducible without copying or renaming the source evidence.
    with open(str(path), "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _dimensional_coefficient(
    coefficient: str,
    normalized_slope: float,
    *,
    rho: float,
    speed: float,
    beam: float,
) -> float:
    if coefficient == "C33":
        return -normalized_slope * rho * speed**2 * beam
    if coefficient == "C53":
        return -normalized_slope * rho * speed**2 * beam**2
    radians_per_degree = math.pi / 180.0
    slope_per_radian = normalized_slope / radians_per_degree
    if coefficient == "C35":
        return -slope_per_radian * rho * speed**2 * beam**2
    if coefficient == "C55":
        return -slope_per_radian * rho * speed**2 * beam**3
    raise ValueError(f"Unknown restoring coefficient {coefficient!r}.")


def _find_source_pdf(images: Path) -> Path:
    candidates = sorted(images.parent.parent.glob("*A3_A Boundary Element Method.pdf"))
    if not candidates:
        raise FileNotFoundError(
            "A3_A Boundary Element Method.pdf must be beside the md directory."
        )
    return candidates[0]


def digitize(
    images: Path,
    output: Path,
    *,
    pixel_uncertainty: float = 2.0,
    source_pdf: Path | None = None,
    panels: tuple[PanelDigitization, ...] = PANELS,
    series_label: str = "Numerical_circle_marker",
) -> dict[str, object]:
    # Keep the user-supplied source path relative for file I/O. On the current
    # Windows Python runtime, resolving this Chinese path before ``open`` can
    # produce a false FileNotFoundError even though relative I/O succeeds.
    images = Path(images)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    pixel_uncertainty = float(pixel_uncertainty)
    if pixel_uncertainty <= 0.0:
        raise ValueError("pixel-uncertainty must be positive.")
    source_pdf = Path(source_pdf) if source_pdf is not None else _find_source_pdf(images)

    rho = 1000.0
    gravity = 9.80665
    beam = 0.318
    fn_b = 2.5
    speed = fn_b * math.sqrt(gravity * beam)
    point_rows: list[dict[str, object]] = []
    matrix_rows: list[dict[str, object]] = []
    sources: list[dict[str, object]] = []

    if not panels:
        raise ValueError("At least one Fig. 7.4 panel must be supplied.")
    for panel in panels:
        image_path = images / panel.image_name
        if not image_path.exists():
            raise FileNotFoundError(image_path)
        with Image.open(image_path) as source_image:
            dimensions = source_image.size
        sources.append(
            {
                "panel": panel.panel,
                "image": str(image_path.absolute()),
                "sha256": _sha256(image_path),
                "pixel_dimensions": list(dimensions),
            }
        )
        x = _linear_map(
            np.asarray(panel.x_pixels),
            panel.x_pixel_limits,
            panel.x_axis_limits,
        )
        y = _linear_map(
            np.asarray(panel.y_pixels),
            panel.y_pixel_limits,
            panel.y_axis_limits,
        )
        for index, (x_pixel, y_pixel, x_value, y_value) in enumerate(
            zip(panel.x_pixels, panel.y_pixels, x, y)
        ):
            point_rows.append(
                {
                    "panel": panel.panel,
                    "coefficient": panel.coefficient,
                    "series": series_label,
                    "point_index": index,
                    "used_in_zero_slope_fit": index in panel.fit_indices,
                    "x_pixel": x_pixel,
                    "y_pixel": y_pixel,
                    "x_value": _stable_float(x_value),
                    "y_value": _stable_float(y_value),
                    "x_quantity": panel.x_quantity,
                    "y_quantity": panel.y_quantity,
                }
            )
        fit_index = np.asarray(panel.fit_indices, dtype=int)
        fit_x = x[fit_index]
        fit_y = y[fit_index]
        polynomial = np.polyfit(fit_x, fit_y, deg=2)
        normalized_slope = _stable_float(polynomial[1])
        value = _stable_float(_dimensional_coefficient(
            panel.coefficient,
            normalized_slope,
            rho=rho,
            speed=speed,
            beam=beam,
        ))

        envelope: list[float] = []
        for signs in itertools.product((-1.0, 1.0), repeat=len(fit_index)):
            varied_pixels = np.asarray(panel.y_pixels, dtype=float).copy()
            varied_pixels[fit_index] += pixel_uncertainty * np.asarray(signs)
            varied_y = _linear_map(
                varied_pixels,
                panel.y_pixel_limits,
                panel.y_axis_limits,
            )
            varied_slope = float(np.polyfit(fit_x, varied_y[fit_index], deg=2)[1])
            envelope.append(
                _stable_float(_dimensional_coefficient(
                    panel.coefficient,
                    varied_slope,
                    rho=rho,
                    speed=speed,
                    beam=beam,
                ))
            )
        row_index = 0 if panel.coefficient[1] == "3" else 1
        column_index = 0 if panel.coefficient[2] == "3" else 1
        units = (("N/m", "N/rad"), ("N", "N m/rad"))[row_index][column_index]
        matrix_rows.append(
            {
                "coefficient": panel.coefficient,
                "row": ("heave_force", "pitch_moment")[row_index],
                "column": ("heave", "pitch")[column_index],
                "value": value,
                "lower_pixel_envelope": _stable_float(min(envelope)),
                "upper_pixel_envelope": _stable_float(max(envelope)),
                "units": units,
                "normalized_zero_slope": normalized_slope,
                "fit": "quadratic_central_five_points_derivative_at_zero",
                "pixel_center_uncertainty": pixel_uncertainty,
                "response_calibration_used": False,
            }
        )

    points_path = output / "digitized_points.csv"
    matrix_path = output / "restoring_matrix.csv"
    solver_matrix_path = output / "restoring_matrices.csv"
    with points_path.open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(point_rows[0]))
        writer.writeheader()
        writer.writerows(point_rows)
    with matrix_path.open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(matrix_rows[0]))
        writer.writeheader()
        writer.writerows(matrix_rows)
    with solver_matrix_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = ("component", "row", "column", "value", "units")
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in matrix_rows:
            writer.writerow(
                {
                    "component": "total",
                    "row": row["row"],
                    "column": row["column"],
                    "value": row["value"],
                    "units": row["units"],
                }
            )
    manifest = {
        "benchmark": f"Sun_2007_Fig7.4_{series_label}_zero_offset_slopes",
        "source": {
            "title": "A Boundary Element Method Applied to Strongly Nonlinear Wave-Body Interaction Problems",
            "chapter": 7,
            "figure": "7.4(a-d)",
            "equation": "7.18",
            "figure_pdf_page_1_based": 140,
            "figure_printed_page": 128,
            "equation_pdf_page_1_based": 142,
            "equation_printed_page": 130,
            "pdf": str(source_pdf.absolute()),
            "pdf_sha256": _sha256(source_pdf),
        },
        "rho_water_kg_m3": rho,
        "gravity_m_s2": gravity,
        "beam_m": beam,
        "beam_froude_number": fn_b,
        "speed_mps": speed,
        "pixel_uncertainty": pixel_uncertainty,
        "sources": sources,
        "generated_files": {
            points_path.name: _sha256(points_path),
            matrix_path.name: _sha256(matrix_path),
            solver_matrix_path.name: _sha256(solver_matrix_path),
        },
        "limitations": [
            "Pixel envelope covers digitization-center uncertainty only.",
            "It is not the Troesch experimental uncertainty.",
            "Overlapping markers can add systematic error beyond the pixel envelope.",
            f"The {series_label} series is used; no dynamic-response data are fitted.",
        ],
        "response_calibration_used": False,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )
    return {
        "output": output,
        "point_rows": len(point_rows),
        "matrix_rows": len(matrix_rows),
        "matrix": {str(row["coefficient"]): float(row["value"]) for row in matrix_rows},
    }


def main() -> int:
    args = _parser().parse_args()
    if args.series == "troesch_heave_experiment":
        panels = TROESCH_HEAVE_EXPERIMENTAL_PANELS
        series_label = "Troesch_experimental_square_marker"
    elif args.series == "troesch_experiment":
        panels = TROESCH_EXPERIMENTAL_PANELS
        series_label = "Troesch_experimental_square_marker"
    else:
        panels = PANELS
        series_label = "Numerical_circle_marker"
    result = digitize(
        args.images,
        args.out,
        pixel_uncertainty=args.pixel_uncertainty,
        panels=panels,
        series_label=series_label,
    )
    print(result["output"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
