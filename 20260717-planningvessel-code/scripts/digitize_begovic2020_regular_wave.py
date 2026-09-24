from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from PIL import Image
from pypdf import PdfReader


PDF_SHA256 = "6dc44decbf2df3f1f561d187d76cd0c30d58ab0bacdf7ee9e8097758b0ca6826"
GRAVITY_M_S2 = 9.80665
EXPERIMENT_SPEED_BY_FN_B = {1.67: 3.4, 2.26: 4.6, 2.82: 5.75}

CASE_ROWS = (
    ("C1", 5.65, 3.260, 1.928, 0.020, 1.014),
    ("C2", 5.03, 2.576, 2.440, 0.020, 1.284),
    ("C3", 4.40, 1.972, 3.186, 0.020, 1.677),
    ("C4", 4.08, 1.700, 3.695, 0.032, 1.945),
    ("C5", 3.77, 1.449, 4.337, 0.032, 2.283),
    ("C6", 3.46, 1.217, 5.161, 0.035, 2.717),
    ("C7", 3.14, 1.006, 6.245, 0.035, 3.287),
    ("C8", 2.83, 0.815, 7.710, 0.045, 4.058),
)


@dataclass(frozen=True)
class FigureSpec:
    fn_b: float
    metric: str
    pdf_page_index: int
    pdf_page_number: int
    figure_number: str
    image_name: str
    image_sha256: str
    y_max: float


FIGURES = (
    FigureSpec(1.67, "heave", 8, 9, "6a", "Image127.jpg", "c67c3f92a0f7ca1906931d7f3665953dc2a2d43c5d8a8cfdb3031f162998bbbd", 1.6),
    FigureSpec(1.67, "pitch", 8, 9, "6b", "Image128.jpg", "2e48644583e045da81589010947db04a044397193d966cd40685ce596ca0e8c1", 1.6),
    FigureSpec(2.26, "heave", 8, 9, "7a", "Image129.jpg", "294fc7a006c2f85abdbf0be5c06561bc4b6afec32fe3aa438cc79345021dc7fb", 1.8),
    FigureSpec(2.26, "pitch", 8, 9, "7b", "Image130.jpg", "8ac2c95dda844554cd43cf94233b75e8bf179447656e8f4547148d205a5971fb", 1.8),
    FigureSpec(2.82, "heave", 9, 10, "8a", "Image133.jpg", "299bd78b96441ccda7eb42f18080a5d1acffe931e323abfcf71172e117356a0e", 2.0),
    FigureSpec(2.82, "pitch", 9, 10, "8b", "Image134.jpg", "caee8065f82f79a381a88b54d32c1502588ec2529c4d26a7ac8d9c7c22c8a073", 2.0),
)

# All six embedded plots use the same raster layout. The axis limits are read
# from the printed ticks; the pixel locations are the centers of the axis lines.
X_DATA_MIN = 0.5
X_DATA_MAX = 4.5
X_PIXEL_MIN = 79.0
X_PIXEL_MAX = 533.0
Y_PIXEL_ZERO = 479.0
Y_PIXEL_TOP = 63.0
SEARCH_HALF_WIDTH_PX = 7


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _extract_image(reader: PdfReader, spec: FigureSpec) -> bytes:
    matches = [image.data for image in reader.pages[spec.pdf_page_index].images if image.name == spec.image_name]
    unique = {_sha256_bytes(data): data for data in matches}
    if spec.image_sha256 not in unique:
        found = ", ".join(sorted(unique)) or "none"
        raise RuntimeError(
            f"Expected {spec.image_name} hash {spec.image_sha256}, found {found} on PDF page {spec.pdf_page_number}."
        )
    return unique[spec.image_sha256]


def _red_efd_mask(image: Image.Image) -> np.ndarray:
    rgb = np.asarray(image.convert("RGB"), dtype=np.float64)
    red, green, blue = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    return (
        (red > 90.0)
        & (red > 1.25 * green)
        & (red > 1.25 * blue)
        & (green < 130.0)
    )


def _row_groups(rows: np.ndarray, maximum_gap: int = 3) -> list[np.ndarray]:
    if len(rows) == 0:
        return []
    unique = np.unique(rows)
    split_at = np.flatnonzero(np.diff(unique) > maximum_gap) + 1
    return [part for part in np.split(unique, split_at) if len(part)]


def _weighted_median(values: np.ndarray) -> float:
    ordered = np.sort(values.astype(float))
    return float(np.median(ordered))


def _marker_candidates(mask: np.ndarray, lambda_over_l: float) -> list[dict[str, float]]:
    x_pixel = X_PIXEL_MIN + (lambda_over_l - X_DATA_MIN) * (
        X_PIXEL_MAX - X_PIXEL_MIN
    ) / (X_DATA_MAX - X_DATA_MIN)
    x_center = int(round(x_pixel))
    x_start = max(0, x_center - SEARCH_HALF_WIDTH_PX)
    x_stop = min(mask.shape[1], x_center + SEARCH_HALF_WIDTH_PX + 1)
    y_rows, _ = np.where(mask[:, x_start:x_stop])
    y_rows = y_rows[(y_rows >= int(Y_PIXEL_TOP) - 8) & (y_rows <= int(Y_PIXEL_ZERO) + 8)]

    candidates: list[dict[str, float]] = []
    for group in _row_groups(y_rows):
        selected = y_rows[np.isin(y_rows, group)]
        if len(selected) < 12 or len(group) < 3:
            continue
        candidates.append(
            {
                "pixel_y": _weighted_median(selected),
                "red_pixel_count": float(len(selected)),
                "row_min": float(group.min()),
                "row_max": float(group.max()),
            }
        )
    if not candidates:
        raise RuntimeError(f"No EFD marker candidate found at lambda/L={lambda_over_l}.")
    return candidates


def _select_marker_path(
    lambda_over_l: np.ndarray, candidates: list[list[dict[str, float]]]
) -> list[dict[str, float]]:
    selected: list[dict[str, float] | None] = [None] * len(candidates)
    unique_indices = [index for index, values in enumerate(candidates) if len(values) == 1]
    for index in unique_indices:
        selected[index] = candidates[index][0]

    for index, values in enumerate(candidates):
        if selected[index] is not None:
            continue
        left = [candidate for candidate in unique_indices if candidate < index]
        right = [candidate for candidate in unique_indices if candidate > index]
        if left and right:
            li, ri = left[-1], right[0]
            fraction = (lambda_over_l[index] - lambda_over_l[li]) / (
                lambda_over_l[ri] - lambda_over_l[li]
            )
            expected = selected[li]["pixel_y"] + fraction * (
                selected[ri]["pixel_y"] - selected[li]["pixel_y"]
            )
        elif left:
            expected = selected[left[-1]]["pixel_y"]
        elif right:
            expected = selected[right[0]]["pixel_y"]
        else:
            raise RuntimeError("Every marker location has multiple candidates; path is indeterminate.")
        selected[index] = min(values, key=lambda item: abs(item["pixel_y"] - expected))
    return [item for item in selected if item is not None]


def _pixel_y_to_rao(pixel_y: float, y_max: float) -> float:
    return (Y_PIXEL_ZERO - pixel_y) * y_max / (Y_PIXEL_ZERO - Y_PIXEL_TOP)


def _digitize_figure(image_data: bytes, spec: FigureSpec) -> tuple[pd.DataFrame, pd.DataFrame]:
    image = Image.open(BytesIO(image_data))
    if image.size != (607, 540):
        raise RuntimeError(f"Unexpected image size {image.size} for {spec.image_name}.")
    mask = _red_efd_mask(image)
    lambda_values = np.asarray([row[-1] for row in CASE_ROWS], dtype=float)
    all_candidates = [_marker_candidates(mask, value) for value in lambda_values]
    selected = _select_marker_path(lambda_values, all_candidates)

    values: list[dict[str, object]] = []
    audit: list[dict[str, object]] = []
    digitization_uncertainty = max(0.01, 4.0 * spec.y_max / (Y_PIXEL_ZERO - Y_PIXEL_TOP))
    for case, lambda_over_l, candidates, marker in zip(
        (row[0] for row in CASE_ROWS), lambda_values, all_candidates, selected
    ):
        rao = _pixel_y_to_rao(marker["pixel_y"], spec.y_max)
        values.append(
            {
                "case_code": case,
                "fn_b": spec.fn_b,
                "metric": spec.metric,
                "efd_rao": rao,
                "digitization_uncertainty_abs": digitization_uncertainty,
                "source_figure": spec.figure_number,
                "source_pdf_page": spec.pdf_page_number,
            }
        )
        audit.append(
            {
                "case_code": case,
                "fn_b": spec.fn_b,
                "metric": spec.metric,
                "lambda_over_l": lambda_over_l,
                "image_name": spec.image_name,
                "image_sha256": spec.image_sha256,
                "candidate_count": len(candidates),
                "candidate_pixel_y": ";".join(f"{item['pixel_y']:.3f}" for item in candidates),
                "selected_pixel_y": marker["pixel_y"],
                "selected_red_pixel_count": int(marker["red_pixel_count"]),
                "efd_rao": rao,
                "digitization_uncertainty_abs": digitization_uncertainty,
            }
        )
    return pd.DataFrame(values), pd.DataFrame(audit)


def _hull_table() -> pd.DataFrame:
    displacement_n = 319.7
    return pd.DataFrame(
        [
            {
                "hull": "monohedral",
                "length_overall_m": 1.900,
                "beam_m": 0.424,
                "displacement_weight_n": displacement_n,
                "mass_kg_from_weight": displacement_n / GRAVITY_M_S2,
                "lcg_from_transom_m": 0.697,
                "vcg_m": 0.143,
                "pitch_radius_gyration_m": 0.583,
                "aft_draft_m": 0.096,
                "deadrise_deg": 16.70,
                "source": "Kahramanoglu_et_al_2020_Table_1",
            }
        ]
    )


def _conditions_table() -> pd.DataFrame:
    rows = []
    for case_code, omega, wave_number, wavelength, amplitude, lambda_over_l in CASE_ROWS:
        rows.append(
            {
                "case_code": case_code,
                "wave_omega_rad_s": omega,
                "wave_number_rad_m": wave_number,
                "wavelength_m": wavelength,
                "wave_amplitude_m": amplitude,
                "lambda_over_l": lambda_over_l,
                "source": "Kahramanoglu_et_al_2020_Table_4",
            }
        )
    return pd.DataFrame(rows)


def _wide_motion_table(values: pd.DataFrame, conditions: pd.DataFrame) -> pd.DataFrame:
    wide = values.pivot(index=["case_code", "fn_b"], columns="metric", values="efd_rao").reset_index()
    uncertainty = values.pivot(
        index=["case_code", "fn_b"], columns="metric", values="digitization_uncertainty_abs"
    ).reset_index()
    uncertainty = uncertainty.rename(
        columns={"heave": "heave_digitization_uncertainty_abs", "pitch": "pitch_digitization_uncertainty_abs"}
    )
    wide = wide.rename(
        columns={
            "heave": "heave_rao_m_per_m",
            "pitch": "pitch_rao_rad_per_wave_slope",
        }
    )
    result = wide.merge(uncertainty, on=["case_code", "fn_b"], validate="one_to_one")
    result = result.merge(conditions, on="case_code", validate="many_to_one")
    result["speed_m_s"] = result["fn_b"].map(EXPERIMENT_SPEED_BY_FN_B)
    if result["speed_m_s"].isna().any():
        raise RuntimeError("Every digitized Begovic speed must map to an original experiment speed.")
    result["encounter_omega_rad_s"] = result["wave_omega_rad_s"] + (
        result["wave_number_rad_m"] * result["speed_m_s"]
    )
    result["benchmark"] = "begovic_2014_mono_efd_republished_2020"
    result["source_kind"] = "red_triangle_EFD_graph_digitization"
    columns = [
        "benchmark",
        "case_code",
        "fn_b",
        "speed_m_s",
        "wave_omega_rad_s",
        "encounter_omega_rad_s",
        "wave_number_rad_m",
        "wavelength_m",
        "wave_amplitude_m",
        "lambda_over_l",
        "heave_rao_m_per_m",
        "pitch_rao_rad_per_wave_slope",
        "heave_digitization_uncertainty_abs",
        "pitch_digitization_uncertainty_abs",
        "source_kind",
    ]
    return result[columns].sort_values(["fn_b", "case_code"]).reset_index(drop=True)


def digitize(pdf_path: Path, output_dir: Path, extracted_images_dir: Path | None = None) -> dict[str, object]:
    actual_pdf_hash = _sha256_file(pdf_path)
    if actual_pdf_hash != PDF_SHA256:
        raise RuntimeError(f"Source PDF hash mismatch: expected {PDF_SHA256}, got {actual_pdf_hash}.")

    reader = PdfReader(str(pdf_path))
    values_parts: list[pd.DataFrame] = []
    audit_parts: list[pd.DataFrame] = []
    image_hashes: dict[str, str] = {}
    if extracted_images_dir is not None:
        extracted_images_dir.mkdir(parents=True, exist_ok=True)
    for spec in FIGURES:
        image_data = _extract_image(reader, spec)
        image_hashes[spec.image_name] = _sha256_bytes(image_data)
        if extracted_images_dir is not None:
            (extracted_images_dir / spec.image_name).write_bytes(image_data)
        values, audit = _digitize_figure(image_data, spec)
        values_parts.append(values)
        audit_parts.append(audit)

    output_dir.mkdir(parents=True, exist_ok=True)
    hull = _hull_table()
    conditions = _conditions_table()
    values = pd.concat(values_parts, ignore_index=True)
    audit = pd.concat(audit_parts, ignore_index=True)
    motion = _wide_motion_table(values, conditions)

    files = {
        "hull": output_dir / "begovic2020_mono_hull.csv",
        "conditions": output_dir / "begovic2020_regular_wave_conditions.csv",
        "motion": output_dir / "begovic2020_mono_efd_motion_digitized.csv",
        "audit": output_dir / "begovic2020_digitization_audit.csv",
    }
    hull.to_csv(files["hull"], index=False, float_format="%.10g")
    conditions.to_csv(files["conditions"], index=False, float_format="%.10g")
    motion.to_csv(files["motion"], index=False, float_format="%.10g")
    audit.to_csv(files["audit"], index=False, float_format="%.10g")
    return {
        "pdf_sha256": actual_pdf_hash,
        "image_sha256": image_hashes,
        "motion_rows": len(motion),
        "audit_rows": len(audit),
        "files": {key: str(path) for key, path in files.items()},
    }


def _parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Reproduce the Begovic monohedral EFD motion digitization from the frozen 2020 PDF."
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=root / "benchmarks" / "begovic2020" / "source" / "jmse-08-00455-v2.pdf",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=root / "benchmarks" / "begovic2020",
    )
    parser.add_argument("--extract-images", type=Path, default=None)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    summary = digitize(args.pdf.resolve(), args.out.resolve(), args.extract_images)
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
