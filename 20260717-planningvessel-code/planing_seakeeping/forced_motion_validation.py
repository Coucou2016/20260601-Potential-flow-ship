from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

from .forced_motion_identification import ForcedMotionMatrices


SUN2007_COEFFICIENTS = ("A33", "A35", "A53", "A55", "B33", "B35", "B53", "B55")


@dataclass(frozen=True)
class ForcedMotionBenchmarkRow:
    model_variant: str
    sigma: float
    coefficient: str
    reference_value: float
    uncertainty: float
    normalization: str
    source_figure: str
    source_pdf_page: int
    source_image_sha256: str


@dataclass(frozen=True)
class ForcedMotionComparisonRow:
    model_variant: str
    sigma: float
    coefficient: str
    computed_value: float
    reference_value: float
    uncertainty: float
    absolute_error: float
    relative_error: float
    normalized_residual: float
    normalization: str


@dataclass(frozen=True)
class ForcedMotionCoefficientMetric:
    coefficient: str
    point_count: int
    median_relative_error: float
    nrmse: float
    median_relative_error_limit: float
    nrmse_limit: float
    passed: bool


@dataclass(frozen=True)
class Sun2007TroeschAcceptance:
    model_variant: str
    comparisons: tuple[ForcedMotionComparisonRow, ...]
    metrics: tuple[ForcedMotionCoefficientMetric, ...]
    a35_monotonic_decrease: bool
    a35_a53_nonreciprocal: bool
    frequency_count: int
    coefficient_count: int
    passed: bool


def load_sun2007_troesch_benchmark(
    csv_path: str | Path,
    *,
    model_variant: str,
) -> tuple[ForcedMotionBenchmarkRow, ...]:
    path = Path(csv_path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        raw_rows = list(csv.DictReader(handle))
    rows = tuple(
        ForcedMotionBenchmarkRow(
            model_variant=str(row["model_variant"]),
            sigma=float(row["omega_sqrt_B_over_g"]),
            coefficient=str(row["coefficient"]),
            reference_value=float(row["value_nondimensional"]),
            uncertainty=float(row["digitization_uncertainty_nondimensional"]),
            normalization=str(row["normalization"]),
            source_figure=str(row["figure"]),
            source_pdf_page=int(row["pdf_page"]),
            source_image_sha256=str(row["source_image_sha256"]),
        )
        for row in raw_rows
        if str(row["model_variant"]) == str(model_variant)
    )
    if len(rows) != 40:
        raise ValueError("A Sun 2007 model variant must contain five frequencies for all eight coefficients.")
    if {row.coefficient for row in rows} != set(SUN2007_COEFFICIENTS):
        raise ValueError("Sun 2007 benchmark does not contain the required eight coefficients.")
    for coefficient in SUN2007_COEFFICIENTS:
        coefficient_rows = [row for row in rows if row.coefficient == coefficient]
        if len(coefficient_rows) != 5 or len({row.sigma for row in coefficient_rows}) != 5:
            raise ValueError(f"Sun 2007 coefficient {coefficient} must contain five unique frequencies.")
    return rows


def _normalization_scale(
    coefficient: str,
    *,
    beam_m: float,
    rho_water_kg_m3: float,
    gravity_m_s2: float,
) -> float:
    if coefficient in ("A33",):
        length_power, damping = 3, False
    elif coefficient in ("A35", "A53"):
        length_power, damping = 4, False
    elif coefficient == "A55":
        length_power, damping = 5, False
    elif coefficient == "B33":
        length_power, damping = 3, True
    elif coefficient in ("B35", "B53"):
        length_power, damping = 4, True
    elif coefficient == "B55":
        length_power, damping = 5, True
    else:
        raise ValueError(f"Unsupported forced-motion coefficient {coefficient!r}.")
    scale = float(rho_water_kg_m3) * float(beam_m) ** length_power
    if damping:
        scale *= np.sqrt(float(gravity_m_s2) / float(beam_m))
    return float(scale)


def nondimensionalize_forced_motion_matrices(
    matrices: Iterable[ForcedMotionMatrices],
    *,
    beam_m: float,
    rho_water_kg_m3: float,
    gravity_m_s2: float,
) -> dict[tuple[float, str], float]:
    if beam_m <= 0.0 or rho_water_kg_m3 <= 0.0 or gravity_m_s2 <= 0.0:
        raise ValueError("beam, density, and gravity must be positive.")
    values: dict[tuple[float, str], float] = {}
    matrix_indices = {
        "A33": ("A", 0, 0),
        "A35": ("A", 0, 1),
        "A53": ("A", 1, 0),
        "A55": ("A", 1, 1),
        "B33": ("B", 0, 0),
        "B35": ("B", 0, 1),
        "B53": ("B", 1, 0),
        "B55": ("B", 1, 1),
    }
    for result in matrices:
        sigma = float(result.omega_rad_s) * np.sqrt(float(beam_m) / float(gravity_m_s2))
        for coefficient, (matrix_name, row, column) in matrix_indices.items():
            matrix = result.added_mass if matrix_name == "A" else result.damping
            dimensional = float(np.asarray(matrix, dtype=float)[row, column])
            scale = _normalization_scale(
                coefficient,
                beam_m=beam_m,
                rho_water_kg_m3=rho_water_kg_m3,
                gravity_m_s2=gravity_m_s2,
            )
            key = (sigma, coefficient)
            if key in values:
                raise ValueError("Forced-motion matrix frequencies must be unique.")
            values[key] = dimensional / scale
    return values


def compare_sun2007_troesch(
    matrices: Iterable[ForcedMotionMatrices],
    *,
    benchmark_csv_path: str | Path,
    model_variant: str,
    beam_m: float,
    rho_water_kg_m3: float,
    gravity_m_s2: float,
    frequency_match_tolerance: float = 1e-8,
    median_relative_error_limit: float = 0.10,
    nrmse_limit: float = 0.15,
) -> Sun2007TroeschAcceptance:
    benchmark = load_sun2007_troesch_benchmark(
        benchmark_csv_path,
        model_variant=model_variant,
    )
    computed = nondimensionalize_forced_motion_matrices(
        matrices,
        beam_m=beam_m,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
    )
    computed_sigmas = sorted({key[0] for key in computed})
    comparisons: list[ForcedMotionComparisonRow] = []
    for reference in benchmark:
        candidates = [sigma for sigma in computed_sigmas if abs(sigma - reference.sigma) <= frequency_match_tolerance]
        if len(candidates) != 1:
            raise ValueError(
                f"No unique computed matrix matches sigma={reference.sigma:.12g}; "
                "compute the five benchmark frequencies explicitly."
            )
        value = computed[(candidates[0], reference.coefficient)]
        absolute = abs(value - reference.reference_value)
        relative = absolute / max(abs(reference.reference_value), 1e-12)
        normalized = absolute / max(reference.uncertainty, 1e-12)
        comparisons.append(
            ForcedMotionComparisonRow(
                model_variant=model_variant,
                sigma=reference.sigma,
                coefficient=reference.coefficient,
                computed_value=float(value),
                reference_value=reference.reference_value,
                uncertainty=reference.uncertainty,
                absolute_error=float(absolute),
                relative_error=float(relative),
                normalized_residual=float(normalized),
                normalization=reference.normalization,
            )
        )

    metrics: list[ForcedMotionCoefficientMetric] = []
    for coefficient in SUN2007_COEFFICIENTS:
        rows = [row for row in comparisons if row.coefficient == coefficient]
        reference_values = np.asarray([row.reference_value for row in rows], dtype=float)
        residual = np.asarray([row.computed_value - row.reference_value for row in rows], dtype=float)
        median_relative = float(np.median([row.relative_error for row in rows]))
        nrmse = float(np.linalg.norm(residual) / max(np.linalg.norm(reference_values), 1e-12))
        metrics.append(
            ForcedMotionCoefficientMetric(
                coefficient=coefficient,
                point_count=len(rows),
                median_relative_error=median_relative,
                nrmse=nrmse,
                median_relative_error_limit=float(median_relative_error_limit),
                nrmse_limit=float(nrmse_limit),
                passed=bool(median_relative <= median_relative_error_limit and nrmse <= nrmse_limit),
            )
        )

    added_cross = sorted(
        (row for row in comparisons if row.coefficient in ("A35", "A53")),
        key=lambda row: (row.coefficient, row.sigma),
    )
    a35 = np.asarray([row.computed_value for row in added_cross if row.coefficient == "A35"], dtype=float)
    a53 = np.asarray([row.computed_value for row in added_cross if row.coefficient == "A53"], dtype=float)
    a35_decrease = bool(len(a35) == 5 and np.all(np.diff(a35) < 0.0))
    nonreciprocal = bool(len(a35) == len(a53) == 5 and np.linalg.norm(a35 - a53) > 0.10 * max(np.linalg.norm(a35), 1e-12))
    passed = bool(
        len({row.sigma for row in comparisons}) == 5
        and len({row.coefficient for row in comparisons}) == 8
        and all(metric.passed for metric in metrics)
        and a35_decrease
        and nonreciprocal
    )
    return Sun2007TroeschAcceptance(
        model_variant=model_variant,
        comparisons=tuple(comparisons),
        metrics=tuple(metrics),
        a35_monotonic_decrease=a35_decrease,
        a35_a53_nonreciprocal=nonreciprocal,
        frequency_count=len({row.sigma for row in comparisons}),
        coefficient_count=len({row.coefficient for row in comparisons}),
        passed=passed,
    )
