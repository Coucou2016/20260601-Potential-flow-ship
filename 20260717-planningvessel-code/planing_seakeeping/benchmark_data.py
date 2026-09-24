from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_BENCHMARK_ROOT = Path(__file__).resolve().parents[1] / "benchmarks"


@dataclass(frozen=True)
class ReferenceCurve:
    benchmark: str
    path: Path
    x_column: str
    y_column: str
    data: pd.DataFrame


@dataclass(frozen=True)
class CurveComparison:
    reference_peak_x: float
    reference_peak_y: float
    computed_peak_x: float
    computed_peak_y: float
    peak_x_rel_error: float
    peak_y_rel_error: float
    normalized_rmse: float
    overlap_point_count: int


def resolve_benchmark_root(reference_root: str | Path | None = None) -> Path:
    if reference_root is None:
        return DEFAULT_BENCHMARK_ROOT
    return Path(reference_root).resolve()


def reference_curve_path(reference_root: str | Path | None, benchmark: str, filename: str) -> Path:
    return resolve_benchmark_root(reference_root) / benchmark / filename


def load_reference_curve(
    benchmark: str,
    filename: str,
    x_column: str,
    y_column: str,
    reference_root: str | Path | None = None,
) -> ReferenceCurve | None:
    path = reference_curve_path(reference_root, benchmark, filename)
    if not path.exists():
        return None
    data = pd.read_csv(path)
    missing = [column for column in (x_column, y_column) if column not in data.columns]
    if missing:
        raise ValueError(f"{path} is missing required column(s): {', '.join(missing)}")
    data = data[[x_column, y_column]].apply(pd.to_numeric, errors="coerce").dropna().sort_values(x_column)
    data = data.drop_duplicates(subset=[x_column], keep="last").reset_index(drop=True)
    if len(data) < 2:
        raise ValueError(f"{path} must contain at least two finite digitized points.")
    return ReferenceCurve(benchmark=benchmark, path=path, x_column=x_column, y_column=y_column, data=data)


def compare_reference_curve(
    computed: pd.DataFrame,
    computed_x_column: str,
    computed_y_column: str,
    reference: ReferenceCurve,
) -> CurveComparison:
    needed = [computed_x_column, computed_y_column]
    missing = [column for column in needed if column not in computed.columns]
    if missing:
        raise ValueError(f"Computed data missing required column(s): {', '.join(missing)}")
    calc = (
        computed[needed]
        .apply(pd.to_numeric, errors="coerce")
        .dropna()
        .sort_values(computed_x_column)
        .drop_duplicates(subset=[computed_x_column], keep="last")
    )
    if len(calc) < 2:
        raise ValueError("Computed curve must contain at least two finite points.")

    ref_x = reference.data[reference.x_column].to_numpy(dtype=float)
    ref_y = reference.data[reference.y_column].to_numpy(dtype=float)
    calc_x = calc[computed_x_column].to_numpy(dtype=float)
    calc_y = calc[computed_y_column].to_numpy(dtype=float)

    lo = max(float(np.min(ref_x)), float(np.min(calc_x)))
    hi = min(float(np.max(ref_x)), float(np.max(calc_x)))
    mask = (ref_x >= lo) & (ref_x <= hi)
    if int(np.count_nonzero(mask)) < 2:
        raise ValueError("Reference and computed curves do not overlap in the selected x-coordinate.")

    ref_x_overlap = ref_x[mask]
    ref_y_overlap = ref_y[mask]
    calc_mask = (calc_x >= lo) & (calc_x <= hi)
    calc_x_overlap = calc_x[calc_mask]
    calc_y_overlap = calc_y[calc_mask]

    ref_peak_idx = int(np.argmax(ref_y_overlap))
    calc_peak_idx = int(np.argmax(calc_y_overlap))
    reference_peak_x = float(ref_x_overlap[ref_peak_idx])
    reference_peak_y = float(ref_y_overlap[ref_peak_idx])
    computed_peak_x = float(calc_x_overlap[calc_peak_idx])
    computed_peak_y = float(calc_y_overlap[calc_peak_idx])
    interpolated = np.interp(ref_x_overlap, calc_x, calc_y)
    denom_x = max(abs(reference_peak_x), 1e-12)
    denom_y = max(abs(reference_peak_y), 1e-12)
    return CurveComparison(
        reference_peak_x=reference_peak_x,
        reference_peak_y=reference_peak_y,
        computed_peak_x=computed_peak_x,
        computed_peak_y=computed_peak_y,
        peak_x_rel_error=abs(computed_peak_x - reference_peak_x) / denom_x,
        peak_y_rel_error=abs(computed_peak_y - reference_peak_y) / denom_y,
        normalized_rmse=float(np.sqrt(np.mean((interpolated - ref_y_overlap) ** 2)) / denom_y),
        overlap_point_count=int(np.count_nonzero(mask)),
    )
