from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image


FREQUENCIES = np.asarray([0.85, 1.13, 1.40, 1.70, 1.95])

# Marker centers were read from the frozen 300 dpi rendering of A3 PDF page
# 153. Each row is one connected open-marker series labelled NUM in Figs.
# 7.13-7.14. These are Sun's numerical results, not Troesch's EXP markers.
PLOTS = {
    "Fig. 7.13 added mass": {
        "variant": "sun_2dt_without_stern_3d_correction",
        "image": "e259a1bbe7f7df704bad5c18905faa162bd4da7f30acdc510f6f18ca24a654de.jpg",
        "axis_zero_y_px": 750.5,
        "pixels_per_unit": 161.0,
        "marker_y": {
            "A33": [598.5, 590.5, 588.5, 587.5, 586.5],
            "A53": [775.5, 781.0, 784.0, 785.5, 786.0],
            "A35": [435.5, 579.0, 646.5, 685.5, 706.5],
            "A55": [646.0, 650.0, 651.5, 652.5, 652.5],
        },
    },
    "Fig. 7.13 damping": {
        "variant": "sun_2dt_without_stern_3d_correction",
        "image": "9ac0599f902e944a0540a6424a54a6389b487ae215737a375a85273d0809c324.jpg",
        "axis_zero_y_px": 616.5,
        "pixels_per_unit": 53.625,
        "marker_y": {
            "B33": [479.5, 479.5, 478.5, 478.5, 477.5],
            "B53": [525.5, 526.5, 526.0, 526.5, 524.5],
            "B35": [805.5, 805.5, 804.5, 804.5, 803.5],
            "B55": [398.0, 398.5, 399.0, 399.5, 400.0],
        },
    },
    "Fig. 7.14 added mass": {
        "variant": "sun_2dt_with_stern_3d_correction",
        "image": "4ec8d928be8c720e258d5cbcd40aee421aab3e0e0a06a173f37be9c645b40cdc.jpg",
        "axis_zero_y_px": 1576.0,
        "pixels_per_unit": 152.0,
        "marker_y": {
            "A33": [1371.0, 1409.0, 1424.0, 1438.5, 1439.0],
            "A53": [1674.0, 1627.0, 1606.0, 1593.5, 1587.5],
            "A35": [1414.0, 1477.5, 1506.5, 1523.5, 1532.5],
            "A55": [1316.5, 1408.0, 1449.5, 1474.5, 1486.5],
        },
    },
    "Fig. 7.14 damping": {
        "variant": "sun_2dt_with_stern_3d_correction",
        "image": "0cb472e12d93f40ba4ee4fff460989dc6be23e9113b762bcb8b759de08960dba.jpg",
        "axis_zero_y_px": 1443.5,
        "pixels_per_unit": 62.5,
        "marker_y": {
            "B33": [1288.5, 1288.5, 1288.0, 1288.5, 1288.5],
            "B53": [1334.0, 1334.0, 1333.5, 1329.5, 1331.5],
            "B35": [1575.0, 1575.0, 1574.5, 1574.5, 1574.5],
            "B55": [1296.5, 1296.5, 1296.5, 1297.0, 1297.5],
        },
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    # Python 3.9 pathlib can mis-handle this Chinese Windows source path even
    # though the built-in file API and Pillow resolve it correctly.
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_paths(project_parent: Path) -> tuple[Path, Path]:
    collection = next(project_parent.glob("20260729-*/md/A3_images"), None)
    pdf = next(project_parent.glob("20260729-*/*A3_A Boundary Element Method.pdf"), None)
    if collection is None or pdf is None:
        raise FileNotFoundError("A3 PDF and A3_images must be available under the 20260729 literature folder.")
    return collection, pdf


def _normalization(coefficient: str) -> str:
    power = {"33": 3, "35": 4, "53": 4, "55": 5}[coefficient[1:]]
    if coefficient.startswith("A"):
        return f"rho*B^{power}"
    return f"rho*B^{power}*sqrt(g/B)"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Digitize the Sun (2007) Figs. 7.13-7.14 NUM reproduction curves."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("benchmarks/sun2007_troesch_forced_motion_coefficients.csv"),
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    image_dir, source_pdf = _source_paths(root.parent)
    coordinate_evidence = (
        root
        / "benchmarks"
        / "sun2007_troesch_forced_motion_evidence"
        / "A3_pdf_page_153_300dpi.png"
    )
    if not coordinate_evidence.exists():
        raise FileNotFoundError(
            "The frozen 300 dpi PDF-page rendering is required to reproduce marker coordinates."
        )
    with Image.open(coordinate_evidence) as image:
        coordinate_evidence_size = list(image.size)
    if coordinate_evidence_size != [2080, 2955]:
        raise RuntimeError(
            "The coordinate-evidence rendering must be exactly 2080 x 2955 pixels."
        )
    rows = []
    image_manifest = {}
    marker_half_height_px = 6.0
    for figure, spec in PLOTS.items():
        image_path = image_dir / str(spec["image"])
        with Image.open(image_path) as image:
            image_size = image.size
        image_hash = _sha256(image_path)
        image_manifest[image_path.name] = {
            "sha256": image_hash,
            "pixel_size": list(image_size),
        }
        zero = float(spec["axis_zero_y_px"])
        pixels_per_unit = float(spec["pixels_per_unit"])
        uncertainty = marker_half_height_px / pixels_per_unit
        for coefficient, marker_y in dict(spec["marker_y"]).items():
            if len(marker_y) != len(FREQUENCIES):
                raise RuntimeError(f"{figure} {coefficient} must contain five marker centers.")
            for omega, pixel_y in zip(FREQUENCIES, marker_y):
                rows.append(
                    {
                        "figure": figure,
                        "model_variant": spec["variant"],
                        "series": "NUM_open_marker",
                        "omega_sqrt_B_over_g": float(omega),
                        "coefficient": coefficient,
                        "value_nondimensional": (zero - float(pixel_y)) / pixels_per_unit,
                        "digitization_uncertainty_nondimensional": uncertainty,
                        "normalization": _normalization(coefficient),
                        "marker_center_y_px_300dpi": float(pixel_y),
                        "axis_zero_y_px_300dpi": zero,
                        "pixels_per_nondimensional_unit_300dpi": pixels_per_unit,
                        "printed_page": 141,
                        "pdf_page": 153,
                        "source_image_sha256": image_hash,
                    }
                )
    table = pd.DataFrame(rows).sort_values(
        ["model_variant", "coefficient", "omega_sqrt_B_over_g"]
    )
    output = args.out.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(output, index=False, float_format="%.9g")
    manifest = {
        "title": "Sun 2007 forced-motion numerical-reproduction coefficient benchmark",
        "benchmark_role": "same_model_NUM_reproduction_not_independent_EFD",
        "source_pdf": str(source_pdf.resolve()),
        "source_pdf_sha256": _sha256(source_pdf),
        "source_location": "Sun thesis, printed page 141, PDF page 153, Figs. 7.13-7.14",
        "test_condition": {
            "beam_m": 0.318,
            "fn_b": 2.5,
            "deadrise_deg": 20.0,
            "trim_deg": 4.0,
            "mean_wetted_length_over_beam": 3.0,
            "lcg_over_beam": 1.47,
            "vcg_over_beam": 0.65,
            "forced_heave_amplitude_over_beam": 0.036,
            "forced_pitch_amplitude_deg": 0.43,
        },
        "digitization": {
            "series": "NUM open-marker curves only",
            "render_resolution_dpi": 300,
            "marker_half_height_px_used_for_uncertainty": marker_half_height_px,
            "response_calibration_used": False,
            "note": (
                "This benchmark validates a forced-motion hydrodynamic-coefficient solver. "
                "It is not used to tune Begovic motion responses or to replace independent EFD validation."
            ),
        },
        "coordinate_evidence": {
            "image": str(coordinate_evidence.resolve()),
            "sha256": _sha256(coordinate_evidence),
            "pixel_size": coordinate_evidence_size,
            "render_contract": "A3 PDF page 153 rendered at 300 dpi with MuPDF 1.28.2",
        },
        "source_images": image_manifest,
        "output_csv": str(output),
        "output_csv_sha256": _sha256(output),
    }
    manifest_path = output.with_name(output.stem + "_manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(table.to_string(index=False))
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
