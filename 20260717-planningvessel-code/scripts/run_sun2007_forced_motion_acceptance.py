from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

from scripts.aggregate_sun2007_forced_motion_acceptance import (
    EXPECTED_SIGMAS,
    aggregate,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run and aggregate the production Sun--Troesch five-frequency gate."
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--bem-substeps-per-plane", type=int, default=16)
    parser.add_argument(
        "--ground-plane-spacing-rule",
        choices=("keel_over_nx", "bem_interval_over_nx_minus_one"),
        default="keel_over_nx",
    )
    parser.add_argument("--initial-leading-offset-beams", type=float, default=None)
    transom_group = parser.add_mutually_exclusive_group()
    transom_group.add_argument("--transom-correction", action="store_true")
    transom_group.add_argument("--transom-keel-reduction", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--restoring-matrix-file",
        type=Path,
        default=Path(
            "benchmarks/sun2007_fig7_4_troesch_restoring/restoring_matrices.csv"
        ),
    )
    return parser


def _sigma_label(sigma: float) -> str:
    return f"{float(sigma):.6g}".replace(".", "p")


def production_command(
    sigma: float,
    output: Path,
    restoring_matrix_file: Path,
    *,
    bem_substeps_per_plane: int = 16,
    transom_correction: bool = False,
    transom_keel_reduction: bool = False,
    ground_plane_spacing_rule: str = "keel_over_nx",
    initial_leading_offset_beams: float | None = None,
) -> list[str]:
    if transom_correction and transom_keel_reduction:
        raise ValueError("Transom source corrections are mutually exclusive.")
    command = [
        sys.executable,
        "-m",
        "scripts.probe_sun2007_planing_forced_motion",
        "--out",
        str(output),
        "--sigmas",
        f"{float(sigma):.12g}",
        "--cycles",
        "2",
        "--discard-cycles",
        "0.5",
        "--retained-cycles",
        "1.5",
        "--section-planes",
        "11",
        "--bem-substeps-per-plane",
        str(int(bem_substeps_per_plane)),
        "--body-panels",
        "12",
        "--free-surface-panels",
        "15",
        "--side-panels",
        "6",
        "--bottom-panels",
        "18",
        "--gauss-order",
        "8",
        "--element-interpolation",
        "linear_node",
        "--pressure-interpolation",
        "constant_panel",
        "--symmetry-half-domain",
        "--ground-plane-handoff-mode",
        "fixed_earth_grid",
        "--ground-plane-spacing-rule",
        ground_plane_spacing_rule,
        "--knuckle-separation-model",
        "artificial_surface",
        "--jet-cut",
        "--free-surface-spacing-mode",
        "body_matched_geometric",
        "--free-surface-remesh-updates-per-plane",
        "8",
        "--free-surface-smoothing",
        "--free-surface-smoothing-updates-per-plane",
        "8",
        "--uniform-near-body-panels",
        "6",
        "--restoring-mode",
        "external",
        "--restoring-matrix-file",
        str(restoring_matrix_file),
    ]
    if transom_correction:
        command.append("--transom-correction")
    if transom_keel_reduction:
        command.append("--transom-keel-reduction")
    if initial_leading_offset_beams is not None:
        command.extend(
            ("--initial-leading-offset-beams", f"{float(initial_leading_offset_beams):.12g}")
        )
    return command


def _run_complete(directory: Path) -> bool:
    required = (
        "run_input_snapshot.json",
        "identified_coefficients.csv",
        "run_diagnostics.json",
        "restoring_diagnostics.json",
    )
    return all((directory / name).exists() for name in required)


def run_acceptance(
    output: Path,
    restoring_matrix_file: Path,
    *,
    workers: int = 5,
    bem_substeps_per_plane: int = 16,
    transom_correction: bool = False,
    transom_keel_reduction: bool = False,
    ground_plane_spacing_rule: str = "keel_over_nx",
    initial_leading_offset_beams: float | None = None,
    force: bool = False,
) -> dict[str, object]:
    if workers < 1:
        raise ValueError("workers must be positive.")
    if bem_substeps_per_plane < 1:
        raise ValueError("bem-substeps-per-plane must be positive.")
    output = output.resolve()
    restoring_matrix_file = restoring_matrix_file.resolve()
    raw_root = output / "raw"
    log_root = output / "logs"
    raw_root.mkdir(parents=True, exist_ok=True)
    log_root.mkdir(parents=True, exist_ok=True)
    run_dirs = [raw_root / f"sigma_{_sigma_label(sigma)}" for sigma in EXPECTED_SIGMAS]

    def run_one(sigma: float, directory: Path) -> None:
        if _run_complete(directory) and not force:
            return
        directory.mkdir(parents=True, exist_ok=True)
        command = production_command(
            sigma,
            directory,
            restoring_matrix_file,
            bem_substeps_per_plane=bem_substeps_per_plane,
            transom_correction=transom_correction,
            transom_keel_reduction=transom_keel_reduction,
            ground_plane_spacing_rule=ground_plane_spacing_rule,
            initial_leading_offset_beams=initial_leading_offset_beams,
        )
        log_path = log_root / f"sigma_{_sigma_label(sigma)}.log"
        with log_path.open("w", encoding="utf-8") as log:
            completed = subprocess.run(
                command,
                cwd=Path(__file__).resolve().parents[1],
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        if completed.returncode != 0:
            raise RuntimeError(
                f"Sun--Troesch sigma={sigma} failed with return code "
                f"{completed.returncode}; inspect {log_path}."
            )

    with ThreadPoolExecutor(max_workers=min(workers, len(EXPECTED_SIGMAS))) as executor:
        futures = [
            executor.submit(run_one, sigma, directory)
            for sigma, directory in zip(EXPECTED_SIGMAS, run_dirs)
        ]
        for future in futures:
            future.result()
    return aggregate(
        run_dirs,
        output=output / "acceptance",
        benchmark=(
            Path(__file__).resolve().parents[1]
            / "benchmarks"
            / "sun2007_troesch_forced_motion_coefficients.csv"
        ),
    )


def main() -> int:
    args = _parser().parse_args()
    if args.dry_run:
        commands = [
            production_command(
                sigma,
                args.out / "raw" / f"sigma_{_sigma_label(sigma)}",
                args.restoring_matrix_file,
                bem_substeps_per_plane=args.bem_substeps_per_plane,
                transom_correction=args.transom_correction,
                transom_keel_reduction=args.transom_keel_reduction,
                ground_plane_spacing_rule=args.ground_plane_spacing_rule,
                initial_leading_offset_beams=args.initial_leading_offset_beams,
            )
            for sigma in EXPECTED_SIGMAS
        ]
        print(json.dumps(commands, indent=2, ensure_ascii=True))
        return 0
    acceptance = run_acceptance(
        args.out,
        args.restoring_matrix_file,
        workers=args.workers,
        bem_substeps_per_plane=args.bem_substeps_per_plane,
        transom_correction=args.transom_correction,
        transom_keel_reduction=args.transom_keel_reduction,
        ground_plane_spacing_rule=args.ground_plane_spacing_rule,
        initial_leading_offset_beams=args.initial_leading_offset_beams,
        force=args.force,
    )
    print(json.dumps(acceptance, indent=2, ensure_ascii=True))
    return 0 if acceptance["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
