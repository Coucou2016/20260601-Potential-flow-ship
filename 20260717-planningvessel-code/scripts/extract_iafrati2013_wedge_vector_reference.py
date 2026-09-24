from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from pypdf import PdfReader
from pypdf.generic import ContentStream


X_PIXEL_ZERO = 441.0
X_PIXEL_FORTY = 3465.0
Y_PIXEL_MINUS_TWO = 1161.0
Y_PIXEL_THREE = 1539.0
TARGET_BETA_DEG = 20.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _axis_map(value: float, p0: float, v0: float, p1: float, v1: float) -> float:
    return float(v0 + (value - p0) * (v1 - v0) / (p1 - p0))


def _stroked_polylines(pdf_path: Path) -> list[list[tuple[float, float]]]:
    reader = PdfReader(str(pdf_path))
    if len(reader.pages) != 1:
        raise RuntimeError(f"Expected one vector-figure page, got {len(reader.pages)}")
    stream = ContentStream(reader.pages[0].get_contents(), reader)
    segments: list[list[tuple[float, float]]] = []
    active: list[tuple[float, float]] = []

    def flush() -> None:
        nonlocal active
        if len(active) > 1:
            segments.append(active)
        active = []

    for operands, operator in stream.operations:
        operation = bytes(operator)
        if operation == b"m":
            flush()
            active = [(float(operands[0]), float(operands[1]))]
        elif operation == b"l" and active:
            active.append((float(operands[0]), float(operands[1])))
        elif operation in (b"S", b"s"):
            flush()
        elif operation in (b"re", b"h"):
            active = []
    flush()
    return segments


def _stitch_consecutive_segments(
    segments: list[list[tuple[float, float]]],
) -> list[list[tuple[float, float]]]:
    chains: list[list[tuple[float, float]]] = []
    for segment in segments:
        if chains and np.allclose(chains[-1][-1], segment[0], atol=1.0e-12, rtol=0.0):
            chains[-1].extend(segment[1:])
        else:
            chains.append(list(segment))
    return chains


def _nondimensionalize(
    chain: list[tuple[float, float]],
) -> tuple[np.ndarray, np.ndarray]:
    xi = np.asarray(
        [_axis_map(x, X_PIXEL_ZERO, 0.0, X_PIXEL_FORTY, 40.0) for x, _ in chain],
        dtype=float,
    )
    eta = np.asarray(
        [
            _axis_map(y, Y_PIXEL_MINUS_TWO, -2.0, Y_PIXEL_THREE, 3.0)
            for _, y in chain
        ],
        dtype=float,
    )
    return xi, eta


def extract_20deg_outer_free_surface(
    pdf_path: Path,
) -> tuple[list[dict[str, object]], list[dict[str, float]]]:
    chains = _stitch_consecutive_segments(_stroked_polylines(pdf_path))
    candidates: list[
        tuple[float, float, list[tuple[float, float]], np.ndarray, np.ndarray, int]
    ] = []
    for chain in chains:
        x_pdf = np.asarray([point[0] for point in chain], dtype=float)
        if (
            len(chain) < 100
            or float(np.min(x_pdf)) > X_PIXEL_ZERO + 0.1
            or float(np.max(x_pdf)) < X_PIXEL_FORTY - 0.1
        ):
            continue
        xi, eta = _nondimensionalize(chain)
        root_index = int(np.argmax(eta))
        candidates.append(
            (
                float(xi[root_index]),
                float(eta[root_index]),
                chain,
                xi,
                eta,
                root_index,
            )
        )

    if len(candidates) != 5:
        raise RuntimeError(f"Expected five complete profile chains, found {len(candidates)}")
    selected = min(candidates, key=lambda item: item[0])
    root_xi, root_eta, chain, xi, eta, root_index = selected
    if not (4.0 <= root_xi <= 5.0 and 0.5 <= root_eta <= 0.7):
        raise RuntimeError(
            f"The smallest-root profile is not the expected 20-degree curve: "
            f"xi={root_xi}, eta={root_eta}"
        )

    outer_start = root_index + int(np.argmin(xi[root_index:]))
    outer_xi = xi[outer_start:]
    outer_eta = eta[outer_start:]
    if len(outer_xi) < 40 or np.any(np.diff(outer_xi) <= 0.0):
        raise RuntimeError("Extracted outer free-surface branch is not strictly outward")

    rows: list[dict[str, object]] = []
    for index, source_index in enumerate(range(outer_start, len(chain))):
        x_pdf, y_pdf = chain[source_index]
        rows.append(
            {
                "beta_deg": TARGET_BETA_DEG,
                "quantity": "free_surface",
                "x_name": "xi_equals_y_over_Vt",
                "x_nondimensional": float(xi[source_index]),
                "y_name": "eta_equals_z_over_Vt",
                "y_nondimensional": float(eta[source_index]),
                "pdf_x": x_pdf,
                "pdf_y": y_pdf,
                "vector_point_index": index,
                "source_curve": "Iafrati_2013_self_similar_solution",
            }
        )

    diagnostics = [
        {"root_xi": item[0], "root_eta": item[1], "point_count": float(len(item[2]))}
        for item in sorted(candidates, key=lambda item: item[0], reverse=True)
    ]
    return rows, diagnostics


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract Iafrati 2013 20-degree wedge free surface from vector PDF."
    )
    parser.add_argument("--source-pdf", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    source_pdf = args.source_pdf.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    rows, candidates = extract_20deg_outer_free_surface(source_pdf)

    csv_path = out / "iafrati2013_20deg_outer_free_surface.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    manifest = {
        "benchmark": "Iafrati 2013 self-similar wedge-entry scalar and vector references",
        "paper": "A fully nonlinear iterative solution method for self-similar potential flows with a free boundary",
        "source_url": "https://arxiv.org/abs/1212.6699",
        "source_version": "arXiv:1212.6699v2",
        "source_archive_sha256": "b883724cd4b5d168f59a332d64783c4c127132b1363293cc32804a9e97391905",
        "source_pdf": "iafrati2013_arxiv1212.6699v2.pdf",
        "source_pdf_sha256": "5b13b09118ac32a2a7257ddbdd55f14561c886d2f87a3a58b706e6e51c887559",
        "solver_reads_this_file": False,
        "post_solve_only": True,
        "scalar_reference": {
            "source_location": "Iafrati 2013 Table 1, Zhao-Faltinsen columns",
            "csv": "table1_pressure_peak.csv",
            "csv_sha256": "e1e3441db748733a95c691d6029b5cb1791556bc2c0e033a4baf0575b34fb8f6",
            "quantities": {
                "pressure_coefficient_peak": "max of 2p/(rho*V^2)",
                "peak_eta": "vertical similarity coordinate z/(Vt) at the pressure peak",
            },
        },
        "vector_free_surface_reference": {
            "source_figure": "cfg_5-20.pdf; comparison of 5, 7.5, 10 and 20 degree free-surface profiles",
            "source_figure_pdf": source_pdf.name,
            "source_figure_pdf_sha256": _sha256(source_pdf),
            "axis_calibration": {
                "xi": {"pixel_0": X_PIXEL_ZERO, "value_0": 0.0, "pixel_1": X_PIXEL_FORTY, "value_1": 40.0},
                "eta": {"pixel_0": Y_PIXEL_MINUS_TWO, "value_0": -2.0, "pixel_1": Y_PIXEL_THREE, "value_1": 3.0},
            },
            "extraction_policy": (
                "Parse vector move/line/stroke operations, stitch only consecutive "
                "segments sharing an exact endpoint, retain the five complete profiles, "
                "select the 20-degree profile by its uniquely smallest spray-root xi, "
                "then retain the strictly outward branch after the post-root xi minimum."
            ),
            "candidate_profiles": candidates,
            "point_count": len(rows),
            "csv": csv_path.name,
            "csv_sha256": _sha256(csv_path),
            "role": "independent_cross_audit_not_acceptance_replacement",
        },
        "response_calibration_used": False,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"out": str(out), "point_count": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
