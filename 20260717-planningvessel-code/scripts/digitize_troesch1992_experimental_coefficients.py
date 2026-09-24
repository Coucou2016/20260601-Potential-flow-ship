from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from PIL import Image


@dataclass(frozen=True)
class PlotCoordinates:
    figure: str
    zero_y_px: float
    pixels_per_value: float
    sigma_reference: float
    x_reference_px: float
    pixels_per_sigma: float


ADDED_MASS = PlotCoordinates(
    figure="Fig. 7.13 added mass",
    zero_y_px=750.5,
    pixels_per_value=161.0,
    sigma_reference=0.85,
    x_reference_px=426.5,
    pixels_per_sigma=505.0,
)
TOP_DAMPING = PlotCoordinates(
    figure="Fig. 7.13 damping",
    zero_y_px=616.5,
    pixels_per_value=53.625,
    sigma_reference=0.85,
    x_reference_px=1239.0,
    pixels_per_sigma=(1795.0 - 1239.0) / (1.95 - 0.85),
)
BOTTOM_DAMPING = PlotCoordinates(
    figure="Fig. 7.14 damping",
    zero_y_px=1443.5,
    pixels_per_value=62.5,
    sigma_reference=0.85,
    x_reference_px=1239.0,
    pixels_per_sigma=(1795.0 - 1239.0) / (1.95 - 0.85),
)


# Only isolated filled EXP markers are retained. Coordinates were measured on
# the frozen 300 dpi full-page rendering. Points obscured by another marker or
# by a NUM curve are deliberately absent and listed in the manifest.
MARKERS: dict[str, tuple[tuple[PlotCoordinates, float, float], ...]] = {
    "A33": tuple(
        (ADDED_MASS, x, y)
        for x, y in (
            (421.5, 582.0),
            (428.5, 564.5),
            (558.0, 604.5),
            (568.0, 599.0),
            (700.0, 602.0),
            (834.5, 600.5),
            (854.0, 609.0),
            (976.5, 605.0),
            (994.5, 617.0),
        )
    ),
    "A53": tuple(
        (ADDED_MASS, x, y)
        for x, y in (
            (422.5, 735.0),
            (559.5, 761.5),
            (570.0, 739.0),
            (704.0, 764.0),
            (837.0, 763.0),
            (853.5, 749.0),
            (978.5, 763.0),
            (998.0, 754.5),
        )
    ),
    "A35": tuple(
        (ADDED_MASS, x, y)
        for x, y in (
            (427.0, 761.0),
            (567.0, 758.0),
            (853.0, 739.0),
            (997.5, 739.0),
        )
    ),
    "A55": tuple(
        (ADDED_MASS, x, y)
        for x, y in (
            (423.5, 571.0),
            (565.0, 626.0),
            (853.0, 665.0),
            (996.0, 678.0),
        )
    ),
    "B33": tuple(
        (TOP_DAMPING, x, y)
        for x, y in (
            (1368.5, 498.5),
            (1380.5, 500.0),
            (1514.5, 496.0),
            (1651.0, 492.0),
            (1668.5, 499.5),
            (1795.5, 488.0),
            (1812.5, 502.0),
        )
    ),
    "B53": (
        (BOTTOM_DAMPING, 1237.0, 1338.5),
        (BOTTOM_DAMPING, 1376.0, 1340.0),
        (BOTTOM_DAMPING, 1521.0, 1337.5),
        (BOTTOM_DAMPING, 1659.0, 1338.0),
        (TOP_DAMPING, 1791.0, 522.5),
    ),
    "B35": tuple(
        (BOTTOM_DAMPING, x, y)
        for x, y in (
            (1239.0, 1607.0),
            (1381.0, 1607.0),
            (1675.0, 1604.0),
            (1821.0, 1609.0),
        )
    ),
    "B55": tuple(
        (BOTTOM_DAMPING, x, y)
        for x, y in (
            (1231.0, 1258.5),
            (1372.0, 1269.0),
            (1519.0, 1269.0),
            (1658.0, 1267.0),
            (1801.0, 1266.5),
        )
    ),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(str(path), "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalization(coefficient: str) -> str:
    power = {"33": 3, "35": 4, "53": 4, "55": 5}[coefficient[1:]]
    if coefficient.startswith("A"):
        return f"rho*B^{power}"
    return f"rho*B^{power}*sqrt(g/B)"


def digitize(output: Path) -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    evidence = (
        root
        / "benchmarks"
        / "sun2007_troesch_forced_motion_evidence"
        / "A3_pdf_page_153_300dpi.png"
    )
    if not evidence.exists():
        raise FileNotFoundError(evidence)
    with Image.open(evidence) as image:
        image_size = list(image.size)
    if image_size != [2080, 2955]:
        raise RuntimeError("Troesch coordinate evidence must be 2080 x 2955 pixels.")

    marker_half_height_px = 6.0
    marker_half_width_px = 6.0
    rows: list[dict[str, object]] = []
    for coefficient, markers in MARKERS.items():
        for plot, x_px, y_px in markers:
            sigma = plot.sigma_reference + (
                float(x_px) - plot.x_reference_px
            ) / plot.pixels_per_sigma
            value = (plot.zero_y_px - float(y_px)) / plot.pixels_per_value
            rows.append(
                {
                    "figure": plot.figure,
                    "series": "EXP_filled_marker",
                    "benchmark_role": "independent_EFD_digitization_not_acceptance_calibration",
                    "coefficient": coefficient,
                    "omega_sqrt_B_over_g": sigma,
                    "value_nondimensional": value,
                    "digitization_uncertainty_nondimensional": (
                        marker_half_height_px / plot.pixels_per_value
                    ),
                    "frequency_digitization_uncertainty": (
                        marker_half_width_px / plot.pixels_per_sigma
                    ),
                    "normalization": _normalization(coefficient),
                    "marker_center_x_px_300dpi": float(x_px),
                    "marker_center_y_px_300dpi": float(y_px),
                    "axis_zero_y_px_300dpi": plot.zero_y_px,
                    "pixels_per_nondimensional_unit_300dpi": plot.pixels_per_value,
                    "marker_visibility": "isolated_visible",
                    "printed_page": 141,
                    "pdf_page": 153,
                    "response_calibration_used": False,
                    "source_page_image_sha256": _sha256(evidence),
                }
            )

    table = pd.DataFrame(rows).sort_values(
        ["coefficient", "omega_sqrt_B_over_g", "value_nondimensional"]
    )
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(output, index=False, float_format="%.12g")
    manifest = {
        "title": "Troesch 1992 experimental forced-motion coefficients digitized from Sun 2007",
        "benchmark_role": "independent_EFD_digitization_not_acceptance_calibration",
        "source_location": "Sun thesis, printed page 141, PDF page 153, Figs. 7.13-7.14",
        "coordinate_evidence": {
            "image": str(evidence.resolve()),
            "sha256": _sha256(evidence),
            "pixel_size": image_size,
            "render_contract": "A3 PDF page 153 rendered at 300 dpi with MuPDF 1.28.2",
        },
        "digitization": {
            "series": "EXP filled markers only",
            "visible_marker_count": len(table),
            "marker_half_height_px_used_for_uncertainty": marker_half_height_px,
            "marker_half_width_px_used_for_uncertainty": marker_half_width_px,
            "response_calibration_used": False,
            "omission_policy": "Overlapped or merged markers are omitted rather than inferred.",
            "known_omissions": [
                "A35 and A55 markers hidden by another marker or a NUM curve near sigma=1.4",
                "Lowest-frequency B33 filled markers merge with one another",
                "B35 filled marker near sigma=1.4 is not separable",
                "No omitted marker value is interpolated or copied from the NUM curve",
            ],
        },
        "coefficient_point_counts": {
            str(key): int(value)
            for key, value in table.groupby("coefficient").size().items()
        },
        "output_csv": str(output),
        "output_csv_sha256": _sha256(output),
    }
    manifest_path = output.with_name(output.stem + "_manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"rows": len(table), "output": output, "manifest": manifest_path}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Digitize only independently visible Troesch EXP markers from Sun Figs. 7.13-7.14."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("benchmarks/troesch1992_experimental_forced_motion_coefficients.csv"),
    )
    args = parser.parse_args()
    result = digitize(args.out)
    print(result["output"])
    print(result["manifest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
