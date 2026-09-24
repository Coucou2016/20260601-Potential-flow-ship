from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import subprocess

import numpy as np

from .section_bem import SectionOffsets, hard_chine_v_offsets, solve_radiation_modes, wigley_section_offsets


PDSTRIP_EXTERNAL_STATUS = "external_pdstrip_reference_smoke_not_a_validation_gate"
PDSTRIP_SMOKE_SECTION_COUNT = 5
PDSTRIP_SMOKE_FREQUENCY_COUNT = 52
PDSTRIP_SECTION_DOF_LABELS = ("sway", "heave", "roll")
PDSTRIP_SECTIONRESULTS_RADIATION_STORAGE = "radiation_force_matrix = omega**2 * complex_added_mass_matrix"
PDSTRIP_COMPLEX_ADDED_MASS_CONVENTION = "complex_added_mass = added_mass - 1j * damping / omega_e"
PDSTRIP_AS_WRITTEN_ORIENTATION = "as_written_section_force_rows"
PDSTRIP_INTERNAL_ORIENTATION = "pdstrip_internal_transposed"
PDSTRIP_SECTIONRESULTS_SOURCE_EVIDENCE = (
    "pdstrip.f90 sectiondata writes `om(i)**2*addedm(j,1:3,i)` as radiation force; "
    "the transfer-function reader reconstructs `transpose(fillcomplmatr(...)/omsec(ifre)**2)`."
)

_FLOAT_PATTERN = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?"
_COMPLEX_PAIR_PATTERN = re.compile(rf"\(\s*({_FLOAT_PATTERN})\s*,\s*({_FLOAT_PATTERN})\s*\)")


@dataclass(frozen=True)
class PDStripSectionResultsMetadata:
    title: str
    frequency_count: int
    frequency_block_count: int
    line_count: int
    file_size_bytes: int
    has_stop_message: bool

    @property
    def expected_frequency_block_count(self) -> int:
        return PDSTRIP_SMOKE_SECTION_COUNT * self.frequency_count

    @property
    def is_complete(self) -> bool:
        return (
            self.frequency_count == PDSTRIP_SMOKE_FREQUENCY_COUNT
            and self.frequency_block_count == self.expected_frequency_block_count
            and self.file_size_bytes > 0
            and not self.has_stop_message
        )


@dataclass(frozen=True)
class PDStripSmokeResult:
    status: str
    source_dir: Path
    work_dir: Path
    executable_path: Path
    compiler: str
    compile_returncode: int | None
    run_returncode: int | None
    sectionresults_path: Path
    pdstrip_out_path: Path
    metadata: PDStripSectionResultsMetadata | None
    message: str


@dataclass(frozen=True)
class PDStripStationHullSectionsResult:
    status: str
    source_dir: Path
    work_dir: Path
    executable_path: Path
    compiler: str
    compile_returncode: int | None
    run_returncode: int | None
    sectionresults_path: Path
    geomet_path: Path
    pdstrip_out_path: Path
    metadata: PDStripSectionResultsMetadata | None
    parsed: "PDStripSectionResults | None"
    message: str


@dataclass(frozen=True)
class PDStripSectionResultBlock:
    """One section-frequency block from PDSTRIP's ``sectionresults`` file.

    PDSTRIP writes the 3x3 radiation matrix as ``omega**2 * A_complex`` for the
    sectional sway/heave/roll modes. The convenience properties below expose the
    recovered complex added-mass convention without discarding the original
    force-level values.
    """

    station_index: int
    frequency_index: int
    omega_rad_s: float
    wave_heading_rad: tuple[float, ...]
    radiation_force_matrix: np.ndarray
    diffraction_force_by_heading: np.ndarray
    froude_krylov_force_by_heading: np.ndarray

    @property
    def complex_added_mass_matrix_per_m(self) -> np.ndarray:
        omega2 = max(float(self.omega_rad_s) ** 2, 1e-18)
        return self.radiation_force_matrix / omega2

    @property
    def added_mass_matrix_per_m(self) -> np.ndarray:
        return np.real(self.complex_added_mass_matrix_per_m)

    @property
    def damping_over_omega_matrix_per_m(self) -> np.ndarray:
        return np.imag(self.complex_added_mass_matrix_per_m)

    @property
    def damping_matrix_per_m(self) -> np.ndarray:
        return float(self.omega_rad_s) * self.damping_over_omega_matrix_per_m

    @property
    def pdstrip_convention_damping_matrix_per_m(self) -> np.ndarray:
        return -float(self.omega_rad_s) * self.damping_over_omega_matrix_per_m


@dataclass(frozen=True)
class PDStripSectionResults:
    title: str
    frequency_count: int
    blocks: tuple[PDStripSectionResultBlock, ...]
    checksum_line: str | None = None

    @property
    def section_count(self) -> int:
        if self.frequency_count <= 0:
            return 0
        return len(self.blocks) // self.frequency_count

    @property
    def has_complete_section_frequency_grid(self) -> bool:
        return self.frequency_count > 0 and len(self.blocks) == self.section_count * self.frequency_count

    @property
    def frequencies_rad_s(self) -> tuple[float, ...]:
        return tuple(block.omega_rad_s for block in self.blocks[: self.frequency_count])


@dataclass(frozen=True)
class PDStripGeometrySection:
    """One section from a PDSTRIP geometry file."""

    station_index: int
    x_m: float
    y_port_m: tuple[float, ...]
    z_up_m: tuple[float, ...]
    gaps_after_point_indices: tuple[int, ...] = ()

    def to_section_offsets(self) -> SectionOffsets:
        """Convert PDSTRIP section coordinates to the package section convention."""

        y_starboard = -np.asarray(self.y_port_m, dtype=float)
        z_down = -np.asarray(self.z_up_m, dtype=float)
        return SectionOffsets(y_m=y_starboard, z_down_m=z_down)


@dataclass(frozen=True)
class PDStripGeometry:
    section_count: int
    symmetric: bool
    reference_draft_m: float
    sections: tuple[PDStripGeometrySection, ...]


def default_pdstrip_source_dir() -> Path:
    """Return the expected local PDSTRIP source path in this workspace."""

    return (
        Path(__file__).resolve().parents[2]
        / "early_stage_materials"
        / "code"
        / "potential_flow_seakeeping"
        / "pdstrip"
    )


def write_simple_full_v_case(work_dir: Path) -> None:
    """Write a small full-section V-hull case accepted by PDSTRIP.

    The bundled PDSTRIP example uses symmetric half-sections that can trigger
    the source-panel suitability check with modern gfortran builds. This smoke
    case uses explicit starboard-waterline to port-waterline full sections so
    first and last section points lie on the still-water line.
    """

    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "pdstrip.inp").write_text(
        "\n".join(
            [
                "0 t f f",
                "Simple full V smoke case",
                "9.80665 1025.0 0.0 -1e6 999.0",
                "1 0",
                "geomet.out",
                "",
            ]
        ),
        encoding="ascii",
    )
    stations = [
        (-1.0, 0.05, 0.15),
        (-0.5, 0.10, 0.20),
        (0.0, 0.15, 0.25),
        (0.5, 0.10, 0.20),
        (1.0, 0.05, 0.15),
    ]
    lines = ["5 F 0.30"]
    for x_m, half_beam_m, draft_m in stations:
        lines.append(f"{x_m:.6g} 3 0")
        lines.append(f"{-half_beam_m:.6g} 0.0 {half_beam_m:.6g}")
        lines.append(f"0.0 {-draft_m:.6g} 0.0")
    lines.append("")
    (work_dir / "geomet.out").write_text("\n".join(lines), encoding="ascii")


def _station_to_offsets(station: object, point_count_per_side: int = 8) -> SectionOffsets:
    section_offsets = getattr(station, "section_offsets", None)
    if callable(section_offsets):
        offsets = section_offsets()
        if offsets is not None:
            return offsets
    waterplane_beam = getattr(station, "waterplane_beam_m", None)
    if callable(waterplane_beam):
        beam = float(waterplane_beam())
    else:
        beam = float(getattr(station, "beam_m"))
    beam = max(beam, float(getattr(station, "beam_m", beam)), 1e-7)
    effective_draft = getattr(station, "effective_draft_m", None)
    if callable(effective_draft):
        draft = float(effective_draft())
    else:
        draft = float(getattr(station, "draft_m"))
    draft = max(draft, float(getattr(station, "draft_m", draft)), 1e-7)
    if float(getattr(station, "deadrise_deg", 0.0)) >= 89.0:
        return wigley_section_offsets(beam, draft, point_count_per_side=point_count_per_side)
    return hard_chine_v_offsets(beam, draft, point_count_per_side=point_count_per_side)


def _pdstrip_geometry_lines_from_sections(
    sections: list[tuple[float, SectionOffsets]],
    reference_draft_m: float,
    symmetry_flag: str = "F",
) -> list[str]:
    lines = [f"{len(sections)} {symmetry_flag} {reference_draft_m:.12g}"]
    for x_m, offsets in sections:
        y_port = -np.asarray(offsets.y_m, dtype=float)
        z_up = -np.asarray(offsets.z_down_m, dtype=float)
        if len(y_port) < 3:
            raise ValueError("PDSTRIP section geometry requires at least three offset points.")
        if abs(float(z_up[0])) > 1e-8 or abs(float(z_up[-1])) > 1e-8:
            raise ValueError("PDSTRIP section first and last z coordinates must lie on the still-water line.")
        lines.append(f"{x_m:.12g} {len(y_port)} 0")
        lines.append(" ".join(f"{value:.12g}" for value in y_port))
        lines.append(" ".join(f"{value:.12g}" for value in z_up))
    lines.append("")
    return lines


def write_station_hull_section_case(
    work_dir: Path,
    hull: object,
    title: str = "Station hull section hydrodynamics",
    gravity_m_s2: float = 9.80665,
    rho_water_kg_m3: float = 1025.0,
    wave_headings_deg: tuple[float, ...] = (0.0,),
    point_count_per_side: int = 8,
) -> None:
    """Write a PDSTRIP section-hydrodynamics case from a station hull object.

    ``hull`` is intentionally duck-typed so this adapter can consume the
    package's ``StationHull`` without making the external-reference module own
    the station-model implementation.
    """

    work_dir.mkdir(parents=True, exist_ok=True)
    stations = tuple(getattr(hull, "stations"))
    if len(stations) < 1:
        raise ValueError("Station hull must contain at least one station.")
    candidates: list[tuple[float, SectionOffsets, float]] = []
    max_draft = 0.0
    max_beam = 0.0
    max_area = 0.0
    for station in stations:
        x_m = float(getattr(station, "x_m"))
        offsets = _station_to_offsets(station, point_count_per_side=point_count_per_side)
        area_fn = getattr(station, "submerged_area_m2", None)
        area = float(area_fn()) if callable(area_fn) else float(offsets.beam_m * offsets.draft_m)
        candidates.append((x_m, offsets, area))
        max_draft = max(max_draft, offsets.draft_m)
        max_beam = max(max_beam, offsets.beam_m)
        max_area = max(max_area, area)
    sections = [
        (x_m, offsets)
        for x_m, offsets, area in candidates
        if area > max(max_area * 1e-10, 1e-14)
        and offsets.beam_m > max(max_beam * 1e-8, 1e-10)
        and offsets.draft_m > max(max_draft * 1e-8, 1e-10)
    ]
    if not sections:
        raise ValueError("Station hull has no non-degenerate sections for external PDSTRIP.")
    (work_dir / "pdstrip.inp").write_text(
        "\n".join(
            [
                "0 t f f",
                title[:80],
                f"{float(gravity_m_s2):.12g} {float(rho_water_kg_m3):.12g} 0.0 -1e6 999.0",
                f"{len(wave_headings_deg)} " + " ".join(f"{float(value):.12g}" for value in wave_headings_deg),
                "geomet.out",
                "",
            ]
        ),
        encoding="ascii",
    )
    geometry_lines = _pdstrip_geometry_lines_from_sections(
        sections,
        reference_draft_m=max(max_draft, 1e-9),
        symmetry_flag="F",
    )
    (work_dir / "geomet.out").write_text("\n".join(geometry_lines), encoding="ascii")


def _parse_complex_pairs(line: str) -> list[complex]:
    return [complex(float(real), float(imag)) for real, imag in _COMPLEX_PAIR_PATTERN.findall(line)]


def _parse_sectionresults_header(line: str) -> tuple[float, tuple[float, ...]] | None:
    parts = line.strip().split()
    if len(parts) < 3:
        return None
    try:
        omega = float(parts[0])
        n_heading = int(parts[1])
    except ValueError:
        return None
    if n_heading <= 0 or len(parts) < 2 + n_heading:
        return None
    try:
        headings = tuple(float(value) for value in parts[2 : 2 + n_heading])
    except ValueError:
        return None
    return omega, headings


def _consume_float_values(lines: list[str], idx: int, count: int) -> tuple[tuple[float, ...], int]:
    values: list[float] = []
    while idx < len(lines) and len(values) < count:
        stripped = lines[idx].strip()
        if stripped:
            values.extend(float(value) for value in stripped.split())
        idx += 1
    if len(values) < count:
        raise ValueError(f"Expected {count} float values in PDSTRIP geometry, found {len(values)}.")
    return tuple(values[:count]), idx


def _consume_int_values(lines: list[str], idx: int, count: int) -> tuple[tuple[int, ...], int]:
    values: list[int] = []
    while idx < len(lines) and len(values) < count:
        stripped = lines[idx].strip()
        if stripped:
            values.extend(int(float(value)) for value in stripped.split())
        idx += 1
    if len(values) < count:
        raise ValueError(f"Expected {count} integer values in PDSTRIP geometry, found {len(values)}.")
    return tuple(values[:count]), idx


def parse_sectionresults_metadata(sectionresults_path: Path, pdstrip_out_path: Path | None = None) -> PDStripSectionResultsMetadata:
    """Parse enough of PDSTRIP sectionresults to prove a smoke run completed."""

    path = Path(sectionresults_path)
    text = path.read_text(encoding="ascii", errors="ignore") if path.exists() else ""
    lines = text.splitlines()
    title = lines[0].strip() if lines else ""
    frequency_count = 0
    if len(lines) >= 2:
        try:
            frequency_count = int(lines[1].strip().split()[0])
        except (IndexError, ValueError):
            frequency_count = 0
    frequency_header = re.compile(r"^\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?\s+\d+\s+")
    frequency_block_count = sum(1 for line in lines[2:] if frequency_header.match(line))
    output_text = ""
    if pdstrip_out_path is not None and Path(pdstrip_out_path).exists():
        output_text = Path(pdstrip_out_path).read_text(encoding="ascii", errors="ignore")
    stop_phrases = (
        "First and last z of a section differ",
        "Unsuitable section discretisation",
        "Singular equation system",
        "must be equal to zwl",
        "STOP:",
    )
    has_stop_message = any(phrase in output_text for phrase in stop_phrases)
    return PDStripSectionResultsMetadata(
        title=title,
        frequency_count=frequency_count,
        frequency_block_count=frequency_block_count,
        line_count=len(lines),
        file_size_bytes=path.stat().st_size if path.exists() else 0,
        has_stop_message=has_stop_message,
    )


def parse_pdstrip_geometry(geomet_path: Path) -> PDStripGeometry:
    """Parse the PDSTRIP offset geometry format used by the local smoke case."""

    path = Path(geomet_path)
    lines = path.read_text(encoding="ascii", errors="ignore").splitlines()
    if not lines:
        raise ValueError("PDSTRIP geometry file is empty.")
    header = lines[0].strip().split()
    if len(header) < 3:
        raise ValueError("PDSTRIP geometry header must contain nse, symmetry flag, and reference draft.")
    try:
        section_count = int(float(header[0]))
        symmetric = header[1].strip().lower().startswith("s")
        reference_draft = float(header[2])
    except ValueError as exc:
        raise ValueError("Could not parse PDSTRIP geometry header.") from exc
    if section_count <= 0:
        raise ValueError("PDSTRIP geometry must contain at least one section.")

    sections: list[PDStripGeometrySection] = []
    idx = 1
    for station_index in range(1, section_count + 1):
        while idx < len(lines) and not lines[idx].strip():
            idx += 1
        if idx >= len(lines):
            raise ValueError(f"Missing station header for PDSTRIP section {station_index}.")
        station_header = lines[idx].strip().split()
        idx += 1
        if len(station_header) < 3:
            raise ValueError(f"PDSTRIP section {station_index} header must contain x, nof, and ngap.")
        try:
            x_m = float(station_header[0])
            point_count = int(float(station_header[1]))
            gap_count = int(float(station_header[2]))
        except ValueError as exc:
            raise ValueError(f"Could not parse PDSTRIP section {station_index} header.") from exc
        if point_count < 3:
            raise ValueError("PDSTRIP sections must contain at least three offset points.")
        gaps: tuple[int, ...] = ()
        if gap_count > 0:
            gaps, idx = _consume_int_values(lines, idx, gap_count)
        y_port, idx = _consume_float_values(lines, idx, point_count)
        z_up, idx = _consume_float_values(lines, idx, point_count)
        sections.append(
            PDStripGeometrySection(
                station_index=station_index,
                x_m=x_m,
                y_port_m=y_port,
                z_up_m=z_up,
                gaps_after_point_indices=gaps,
            )
        )
    return PDStripGeometry(
        section_count=section_count,
        symmetric=symmetric,
        reference_draft_m=reference_draft,
        sections=tuple(sections),
    )


def parse_sectionresults(sectionresults_path: Path) -> PDStripSectionResults:
    """Parse PDSTRIP ``sectionresults`` into radiation and excitation blocks.

    The file does not contain an explicit station id in each block. PDSTRIP
    writes all frequencies for one section before moving to the next section, so
    station and frequency indices are inferred from block order and the declared
    frequency count.
    """

    path = Path(sectionresults_path)
    text = path.read_text(encoding="ascii", errors="ignore")
    lines = text.splitlines()
    if len(lines) < 2:
        raise ValueError("sectionresults must contain a title and a frequency count line.")
    title = lines[0].strip()
    try:
        frequency_count = int(lines[1].strip().split()[0])
    except (IndexError, ValueError) as exc:
        raise ValueError("sectionresults line 2 must contain the number of frequencies.") from exc
    if frequency_count <= 0:
        raise ValueError("sectionresults frequency count must be positive.")

    blocks: list[PDStripSectionResultBlock] = []
    checksum_line: str | None = None
    idx = 2
    while idx < len(lines):
        header = _parse_sectionresults_header(lines[idx])
        if header is None:
            if lines[idx].strip():
                checksum_line = lines[idx].strip()
            idx += 1
            continue
        omega, headings = header
        n_heading = len(headings)
        idx += 1
        needed_value_count = 9 + 6 * n_heading
        values: list[complex] = []
        while idx < len(lines) and len(values) < needed_value_count:
            if _parse_sectionresults_header(lines[idx]) is not None:
                raise ValueError("Encountered a new sectionresults frequency header before the current block was complete.")
            values.extend(_parse_complex_pairs(lines[idx]))
            idx += 1
        if len(values) < needed_value_count:
            raise ValueError("sectionresults ended before a radiation/excitation block was complete.")

        block_index = len(blocks)
        station_index = block_index // frequency_count + 1
        frequency_index = block_index % frequency_count + 1
        radiation = np.asarray(values[:9], dtype=complex).reshape((3, 3))
        diff_start = 9
        fk_start = diff_start + 3 * n_heading
        diffraction = np.asarray(values[diff_start:fk_start], dtype=complex).reshape((3, n_heading))
        froude_krylov = np.asarray(values[fk_start : fk_start + 3 * n_heading], dtype=complex).reshape(
            (3, n_heading)
        )
        blocks.append(
            PDStripSectionResultBlock(
                station_index=station_index,
                frequency_index=frequency_index,
                omega_rad_s=float(omega),
                wave_heading_rad=headings,
                radiation_force_matrix=radiation,
                diffraction_force_by_heading=diffraction,
                froude_krylov_force_by_heading=froude_krylov,
            )
        )

    if not blocks:
        raise ValueError("No parseable frequency blocks found in sectionresults.")
    if len(blocks) % frequency_count != 0:
        raise ValueError(
            f"sectionresults contains {len(blocks)} blocks, which is not an integer multiple of "
            f"frequency_count={frequency_count}."
        )
    return PDStripSectionResults(
        title=title,
        frequency_count=frequency_count,
        blocks=tuple(blocks),
        checksum_line=checksum_line,
    )


def _relative_error(reference: float, actual: float, floor: float = 1e-12) -> float:
    return abs(float(actual) - float(reference)) / max(abs(float(reference)), floor)


def pdstrip_sectionresults_rows(results: PDStripSectionResults) -> list[dict[str, float | int | str]]:
    """Flatten parsed PDSTRIP blocks to long-form CSV rows."""

    rows: list[dict[str, float | int | str]] = []
    for block in results.blocks:
        base = {
            "title": results.title,
            "station_index": block.station_index,
            "frequency_index": block.frequency_index,
            "omega_rad_s": float(block.omega_rad_s),
        }
        complex_added = block.complex_added_mass_matrix_per_m
        for orientation, matrix in (
            (PDSTRIP_AS_WRITTEN_ORIENTATION, complex_added),
            (PDSTRIP_INTERNAL_ORIENTATION, complex_added.T),
        ):
            added = np.real(matrix)
            damping_over_omega = np.imag(matrix)
            damping = block.omega_rad_s * damping_over_omega
            pdstrip_damping = -damping
            force_matrix = (
                block.radiation_force_matrix
                if orientation == PDSTRIP_AS_WRITTEN_ORIENTATION
                else block.radiation_force_matrix.T
            )
            for row_idx, row_mode in enumerate(PDSTRIP_SECTION_DOF_LABELS):
                for col_idx, col_mode in enumerate(PDSTRIP_SECTION_DOF_LABELS):
                    rows.append(
                        {
                            **base,
                            "quantity": "radiation",
                            "orientation": orientation,
                            "row_mode": row_mode,
                            "col_mode": col_mode,
                            "heading_index": "",
                            "wave_heading_rad": "",
                            "wave_heading_deg": "",
                            "force_real": float(np.real(force_matrix[row_idx, col_idx])),
                            "force_imag": float(np.imag(force_matrix[row_idx, col_idx])),
                            "complex_added_mass_real_per_m": float(np.real(matrix[row_idx, col_idx])),
                            "complex_added_mass_imag_per_m": float(np.imag(matrix[row_idx, col_idx])),
                            "added_mass_per_m": float(added[row_idx, col_idx]),
                            "damping_over_omega_per_m": float(damping_over_omega[row_idx, col_idx]),
                            "damping_per_m": float(damping[row_idx, col_idx]),
                            "pdstrip_convention_damping_per_m": float(pdstrip_damping[row_idx, col_idx]),
                            "radiation_storage_convention": PDSTRIP_SECTIONRESULTS_RADIATION_STORAGE,
                            "complex_added_mass_convention": PDSTRIP_COMPLEX_ADDED_MASS_CONVENTION,
                            "status": PDSTRIP_EXTERNAL_STATUS,
                        }
                    )
        for quantity, vector in (
            ("diffraction_force", block.diffraction_force_by_heading),
            ("froude_krylov_force", block.froude_krylov_force_by_heading),
        ):
            for heading_idx, heading in enumerate(block.wave_heading_rad):
                for row_idx, row_mode in enumerate(PDSTRIP_SECTION_DOF_LABELS):
                    value = vector[row_idx, heading_idx]
                    rows.append(
                        {
                            **base,
                            "quantity": quantity,
                            "orientation": "as_written_section_force_rows",
                            "row_mode": row_mode,
                            "col_mode": "",
                            "heading_index": heading_idx + 1,
                            "wave_heading_rad": float(heading),
                            "wave_heading_deg": float(np.degrees(heading)),
                            "force_real": float(np.real(value)),
                            "force_imag": float(np.imag(value)),
                            "complex_added_mass_real_per_m": "",
                            "complex_added_mass_imag_per_m": "",
                            "added_mass_per_m": "",
                            "damping_over_omega_per_m": "",
                            "damping_per_m": "",
                            "pdstrip_convention_damping_per_m": "",
                            "radiation_storage_convention": "",
                            "complex_added_mass_convention": "",
                            "status": PDSTRIP_EXTERNAL_STATUS,
                        }
                    )
    return rows


def pdstrip_sectionresults_convention_rows(
    sectionresults_path: str | Path | None = None,
    source_dir: str | Path | None = None,
) -> list[dict[str, str]]:
    """Return machine-readable PDSTRIP ``sectionresults`` convention notes.

    These rows keep the external-reference adapter tied to the local Fortran
    source conventions. They are diagnostics, not validation gates.
    """

    source = Path(source_dir) if source_dir is not None else default_pdstrip_source_dir()
    source_file = source / "pdstrip.f90"
    sectionresults = Path(sectionresults_path) if sectionresults_path is not None else None
    return [
        {
            "convention": "radiation_storage",
            "value": PDSTRIP_SECTIONRESULTS_RADIATION_STORAGE,
            "parser_action": "store raw values as radiation_force_matrix",
            "source_file": str(source_file),
            "source_evidence": "sectiondata: write(20,*)(om(i)**2*addedm(j,1:3,i),j=1,3)",
            "sectionresults_file": str(sectionresults) if sectionresults is not None else "",
            "status": PDSTRIP_EXTERNAL_STATUS,
        },
        {
            "convention": "complex_added_mass_recovery",
            "value": "complex_added_mass_matrix_per_m = radiation_force_matrix / omega**2",
            "parser_action": "PDStripSectionResultBlock.complex_added_mass_matrix_per_m",
            "source_file": str(source_file),
            "source_evidence": "reader: transpose(fillcomplmatr(3,3,cfsece)/omsec(ifre)**2)",
            "sectionresults_file": str(sectionresults) if sectionresults is not None else "",
            "status": PDSTRIP_EXTERNAL_STATUS,
        },
        {
            "convention": "matrix_orientation",
            "value": (
                f"export both `{PDSTRIP_AS_WRITTEN_ORIENTATION}` and "
                f"`{PDSTRIP_INTERNAL_ORIENTATION}`"
            ),
            "parser_action": "as-written rows preserve the file order; internal rows transpose to match PDSTRIP transfer-function assembly",
            "source_file": str(source_file),
            "source_evidence": "reader transposes the filled 3x3 radiation matrix before interpolation",
            "sectionresults_file": str(sectionresults) if sectionresults is not None else "",
            "status": PDSTRIP_EXTERNAL_STATUS,
        },
        {
            "convention": "damping_sign",
            "value": PDSTRIP_COMPLEX_ADDED_MASS_CONVENTION,
            "parser_action": (
                "`damping_per_m` preserves the package's historical omega*imag export; "
                "`pdstrip_convention_damping_per_m` applies the Fortran comment convention -omega*imag"
            ),
            "source_file": str(source_file),
            "source_evidence": "sectionhydrodynamics comments define complex added mass as mass-i/omegae*damping",
            "sectionresults_file": str(sectionresults) if sectionresults is not None else "",
            "status": PDSTRIP_EXTERNAL_STATUS,
        },
        {
            "convention": "coordinate_basis",
            "value": "section file geometry uses x forward, y port, z up; transfer functions use 1,2,3 forward, starboard, downward",
            "parser_action": "parse_pdstrip_geometry converts y_port,z_up to package y_starboard,z_down offsets",
            "source_file": str(source_file),
            "source_evidence": "PDSTRIP writes both coordinate-basis notices in the external program output",
            "sectionresults_file": str(sectionresults) if sectionresults is not None else "",
            "status": PDSTRIP_EXTERNAL_STATUS,
        },
    ]


def pdstrip_section_bem_comparison_rows(
    sectionresults: PDStripSectionResults,
    geometry: PDStripGeometry,
    station_indices: tuple[int, ...] | None = None,
    frequency_indices: tuple[int, ...] | None = None,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    free_surface_panel_count_per_side: int = 4,
    body_panel_count: int | None = None,
) -> list[dict[str, float | int | str]]:
    """Compare parsed external PDSTRIP section radiation to local section-BEM.

    The comparison is diagnostic only. It is useful for identifying sign,
    transpose, and magnitude differences before mapping external PDSTRIP data
    into the Ma 2005 vessel-level coefficient gates.
    """

    if geometry.section_count < sectionresults.section_count:
        raise ValueError("PDSTRIP geometry has fewer sections than sectionresults.")
    selected_stations = station_indices or tuple(range(1, sectionresults.section_count + 1))
    selected_frequencies = frequency_indices or (
        1,
        max(1, int(round(0.5 * sectionresults.frequency_count))),
        sectionresults.frequency_count,
    )
    blocks = {(block.station_index, block.frequency_index): block for block in sectionresults.blocks}
    geometry_by_station = {section.station_index: section for section in geometry.sections}
    rows: list[dict[str, float | int | str]] = []
    for station_index in selected_stations:
        if station_index not in geometry_by_station:
            raise ValueError(f"Station index {station_index} is not present in the PDSTRIP geometry.")
        offsets = geometry_by_station[station_index].to_section_offsets()
        for frequency_index in selected_frequencies:
            block = blocks.get((station_index, frequency_index))
            if block is None:
                raise ValueError(f"No sectionresults block for station={station_index}, frequency={frequency_index}.")
            local = solve_radiation_modes(
                offsets,
                omega_rad_s=block.omega_rad_s,
                rho_water_kg_m3=rho_water_kg_m3,
                gravity_m_s2=gravity_m_s2,
                free_surface_panel_count_per_side=free_surface_panel_count_per_side,
                body_panel_count=body_panel_count,
            )
            pdstrip_added = block.added_mass_matrix_per_m.T
            pdstrip_damping_same_sign = block.damping_matrix_per_m.T
            pdstrip_damping_section_bem_sign = -pdstrip_damping_same_sign
            max_residual = max(local.residual_norm_by_mode.values()) if local.residual_norm_by_mode else 0.0
            for row_idx, row_mode in enumerate(PDSTRIP_SECTION_DOF_LABELS):
                for col_idx, col_mode in enumerate(PDSTRIP_SECTION_DOF_LABELS):
                    bem_added = float(local.added_mass_matrix_per_m[row_idx, col_idx])
                    bem_damping = float(local.damping_matrix_per_m[row_idx, col_idx])
                    pd_added = float(pdstrip_added[row_idx, col_idx])
                    pd_damping_same = float(pdstrip_damping_same_sign[row_idx, col_idx])
                    pd_damping_adjusted = float(pdstrip_damping_section_bem_sign[row_idx, col_idx])
                    rows.append(
                        {
                            "station_index": int(station_index),
                            "frequency_index": int(frequency_index),
                            "x_m": float(geometry_by_station[station_index].x_m),
                            "omega_rad_s": float(block.omega_rad_s),
                            "row_mode": row_mode,
                            "col_mode": col_mode,
                            "pdstrip_added_mass_per_m": pd_added,
                            "section_bem_added_mass_per_m": bem_added,
                            "added_mass_rel_error_vs_pdstrip": _relative_error(pd_added, bem_added),
                            "pdstrip_damping_same_sign_per_m": pd_damping_same,
                            "pdstrip_damping_section_bem_sign_per_m": pd_damping_adjusted,
                            "section_bem_damping_per_m": bem_damping,
                            "damping_rel_error_same_sign_vs_pdstrip": _relative_error(pd_damping_same, bem_damping),
                            "damping_rel_error_sign_adjusted_vs_pdstrip": _relative_error(
                                pd_damping_adjusted,
                                bem_damping,
                            ),
                            "section_bem_condition_number": float(local.condition_number),
                            "section_bem_max_residual_norm": float(max_residual),
                            "body_panel_count": int(local.panel_count),
                            "free_surface_panel_count": int(local.free_surface_panel_count),
                            "status": PDSTRIP_EXTERNAL_STATUS,
                        }
                    )
    return rows


def run_pdstrip_station_hull_sections(
    work_dir: Path,
    hull: object,
    source_dir: str | Path | None = None,
    compiler: str = "gfortran",
    title: str = "Station hull section hydrodynamics",
    gravity_m_s2: float = 9.80665,
    rho_water_kg_m3: float = 1025.0,
    wave_headings_deg: tuple[float, ...] = (0.0,),
    point_count_per_side: int = 8,
) -> PDStripStationHullSectionsResult:
    """Compile/run PDSTRIP section hydrodynamics for an arbitrary station hull."""

    source = Path(source_dir) if source_dir is not None else default_pdstrip_source_dir()
    work = Path(work_dir)
    exe = work / ("pdstrip.exe" if os.name == "nt" else "pdstrip")
    sectionresults = work / "sectionresults"
    geomet = work / "geomet.out"
    pdstrip_out = work / "pdstrip.out"
    if not (source / "pdstrip.f90").exists():
        return PDStripStationHullSectionsResult(
            status="NOT_EVALUATED",
            source_dir=source,
            work_dir=work,
            executable_path=exe,
            compiler=compiler,
            compile_returncode=None,
            run_returncode=None,
            sectionresults_path=sectionresults,
            geomet_path=geomet,
            pdstrip_out_path=pdstrip_out,
            metadata=None,
            parsed=None,
            message=f"PDSTRIP source not found at {source}",
        )
    if shutil.which(compiler) is None:
        return PDStripStationHullSectionsResult(
            status="NOT_EVALUATED",
            source_dir=source,
            work_dir=work,
            executable_path=exe,
            compiler=compiler,
            compile_returncode=None,
            run_returncode=None,
            sectionresults_path=sectionresults,
            geomet_path=geomet,
            pdstrip_out_path=pdstrip_out,
            metadata=None,
            parsed=None,
            message=f"Fortran compiler '{compiler}' not found on PATH",
        )

    work.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "pdstrip.f90", work / "pdstrip.f90")
    try:
        write_station_hull_section_case(
            work,
            hull,
            title=title,
            gravity_m_s2=gravity_m_s2,
            rho_water_kg_m3=rho_water_kg_m3,
            wave_headings_deg=wave_headings_deg,
            point_count_per_side=point_count_per_side,
        )
    except ValueError as exc:
        return PDStripStationHullSectionsResult(
            status="FAIL",
            source_dir=source,
            work_dir=work,
            executable_path=exe,
            compiler=compiler,
            compile_returncode=None,
            run_returncode=None,
            sectionresults_path=sectionresults,
            geomet_path=geomet,
            pdstrip_out_path=pdstrip_out,
            metadata=None,
            parsed=None,
            message=str(exc),
        )

    compile_cmd = [compiler, "-std=legacy", "-O2", "-o", exe.name, "pdstrip.f90"]
    compile_run = subprocess.run(compile_cmd, cwd=work, capture_output=True, text=True, timeout=120)
    if compile_run.returncode != 0:
        return PDStripStationHullSectionsResult(
            status="FAIL",
            source_dir=source,
            work_dir=work,
            executable_path=exe,
            compiler=compiler,
            compile_returncode=int(compile_run.returncode),
            run_returncode=None,
            sectionresults_path=sectionresults,
            geomet_path=geomet,
            pdstrip_out_path=pdstrip_out,
            metadata=None,
            parsed=None,
            message=(compile_run.stderr or compile_run.stdout or "PDSTRIP compilation failed").strip(),
        )

    run_cmd = [str((work / exe.name).resolve()), "pdstrip.inp"]
    pdstrip_run = subprocess.run(run_cmd, cwd=work, capture_output=True, text=True, timeout=120)
    metadata = parse_sectionresults_metadata(sectionresults, pdstrip_out)
    parsed: PDStripSectionResults | None = None
    parse_message = ""
    try:
        parsed = parse_sectionresults(sectionresults)
    except (OSError, ValueError) as exc:
        parse_message = f"; parse_error={type(exc).__name__}: {exc}"
    try:
        expected_sections = parse_pdstrip_geometry(geomet).section_count
    except (OSError, ValueError):
        expected_sections = len(tuple(getattr(hull, "stations")))
    status = "FAIL"
    if (
        pdstrip_run.returncode == 0
        and parsed is not None
        and parsed.section_count == expected_sections
        and parsed.has_complete_section_frequency_grid
        and not metadata.has_stop_message
    ):
        status = "PASS"
    message = (
        f"sections={parsed.section_count if parsed is not None else 0}/{expected_sections}; "
        f"frequency_blocks={metadata.frequency_block_count}; "
        f"nfre={metadata.frequency_count}; sectionresults={metadata.file_size_bytes} bytes"
        f"{parse_message}"
    )
    if pdstrip_run.returncode != 0:
        message = (pdstrip_run.stderr or pdstrip_run.stdout or message).strip()
    return PDStripStationHullSectionsResult(
        status=status,
        source_dir=source,
        work_dir=work,
        executable_path=exe,
        compiler=compiler,
        compile_returncode=int(compile_run.returncode),
        run_returncode=int(pdstrip_run.returncode),
        sectionresults_path=sectionresults,
        geomet_path=geomet,
        pdstrip_out_path=pdstrip_out,
        metadata=metadata,
        parsed=parsed,
        message=message,
    )


def run_pdstrip_external_smoke(
    work_dir: Path,
    source_dir: str | Path | None = None,
    compiler: str = "gfortran",
) -> PDStripSmokeResult:
    """Compile local PDSTRIP and run the small section-hydrodynamics smoke case."""

    source = Path(source_dir) if source_dir is not None else default_pdstrip_source_dir()
    work = Path(work_dir)
    exe = work / ("pdstrip.exe" if os.name == "nt" else "pdstrip")
    sectionresults = work / "sectionresults"
    pdstrip_out = work / "pdstrip.out"
    if not (source / "pdstrip.f90").exists():
        return PDStripSmokeResult(
            status="NOT_EVALUATED",
            source_dir=source,
            work_dir=work,
            executable_path=exe,
            compiler=compiler,
            compile_returncode=None,
            run_returncode=None,
            sectionresults_path=sectionresults,
            pdstrip_out_path=pdstrip_out,
            metadata=None,
            message=f"PDSTRIP source not found at {source}",
        )
    if shutil.which(compiler) is None:
        return PDStripSmokeResult(
            status="NOT_EVALUATED",
            source_dir=source,
            work_dir=work,
            executable_path=exe,
            compiler=compiler,
            compile_returncode=None,
            run_returncode=None,
            sectionresults_path=sectionresults,
            pdstrip_out_path=pdstrip_out,
            metadata=None,
            message=f"Fortran compiler '{compiler}' not found on PATH",
        )

    work.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "pdstrip.f90", work / "pdstrip.f90")
    write_simple_full_v_case(work)
    compile_cmd = [compiler, "-std=legacy", "-O2", "-o", exe.name, "pdstrip.f90"]
    compile_run = subprocess.run(compile_cmd, cwd=work, capture_output=True, text=True, timeout=120)
    if compile_run.returncode != 0:
        return PDStripSmokeResult(
            status="FAIL",
            source_dir=source,
            work_dir=work,
            executable_path=exe,
            compiler=compiler,
            compile_returncode=int(compile_run.returncode),
            run_returncode=None,
            sectionresults_path=sectionresults,
            pdstrip_out_path=pdstrip_out,
            metadata=None,
            message=(compile_run.stderr or compile_run.stdout or "PDSTRIP compilation failed").strip(),
        )

    run_cmd = [str((work / exe.name).resolve()), "pdstrip.inp"]
    pdstrip_run = subprocess.run(run_cmd, cwd=work, capture_output=True, text=True, timeout=120)
    metadata = parse_sectionresults_metadata(sectionresults, pdstrip_out)
    status = "PASS" if pdstrip_run.returncode == 0 and metadata.is_complete else "FAIL"
    message = (
        f"frequency_blocks={metadata.frequency_block_count}/"
        f"{metadata.expected_frequency_block_count}; "
        f"sectionresults={metadata.file_size_bytes} bytes"
    )
    if pdstrip_run.returncode != 0:
        message = (pdstrip_run.stderr or pdstrip_run.stdout or message).strip()
    return PDStripSmokeResult(
        status=status,
        source_dir=source,
        work_dir=work,
        executable_path=exe,
        compiler=compiler,
        compile_returncode=int(compile_run.returncode),
        run_returncode=int(pdstrip_run.returncode),
        sectionresults_path=sectionresults,
        pdstrip_out_path=pdstrip_out,
        metadata=metadata,
        message=message,
    )


def pdstrip_smoke_rows(result: PDStripSmokeResult) -> list[dict[str, float | str]]:
    """Convert a smoke result into validation-style rows."""

    rows: list[dict[str, float | str]] = [
        {
            "benchmark": "pdstrip_external_smoke",
            "metric": "pdstrip_external_source_available",
            "expected": "pdstrip.f90 source file",
            "actual": str(result.source_dir / "pdstrip.f90"),
            "rel_error": "",
            "tolerance": "",
            "status": "PASS" if (result.source_dir / "pdstrip.f90").exists() else "NOT_EVALUATED",
            "note": "Local open-source PDSTRIP source used as an external strip-theory reference path.",
        },
        {
            "benchmark": "pdstrip_external_smoke",
            "metric": "pdstrip_external_compiler_available",
            "expected": "Fortran compiler on PATH",
            "actual": result.compiler,
            "rel_error": "",
            "tolerance": "",
            "status": "PASS" if shutil.which(result.compiler) is not None else "NOT_EVALUATED",
            "note": "The smoke run compiles PDSTRIP in an output working directory.",
        },
        {
            "benchmark": "pdstrip_external_smoke",
            "metric": "pdstrip_external_compile_and_run",
            "expected": "compile and run return code 0",
            "actual": f"compile={result.compile_returncode}; run={result.run_returncode}",
            "rel_error": "",
            "tolerance": "",
            "status": result.status if result.status != "NOT_EVALUATED" else "NOT_EVALUATED",
            "note": result.message,
        },
    ]
    if result.metadata is not None:
        rows.append(
            {
                "benchmark": "pdstrip_external_smoke",
                "metric": "pdstrip_external_sectionresults_complete",
                "expected": f"{result.metadata.expected_frequency_block_count} section-frequency blocks",
                "actual": result.metadata.frequency_block_count,
                "rel_error": "",
                "tolerance": "",
                "status": "PASS" if result.metadata.is_complete else "FAIL",
                "note": (
                    f"nfre={result.metadata.frequency_count}; "
                    f"lines={result.metadata.line_count}; "
                    f"stop_message={result.metadata.has_stop_message}; "
                    f"file={result.sectionresults_path}"
                ),
            }
        )
        try:
            parsed = parse_sectionresults(result.sectionresults_path)
            rows.append(
                {
                    "benchmark": "pdstrip_external_smoke",
                    "metric": "pdstrip_external_sectionresults_parseable",
                    "expected": (
                        f"{result.metadata.expected_frequency_block_count} parsed blocks with "
                        f"{PDSTRIP_SMOKE_SECTION_COUNT} inferred sections"
                    ),
                    "actual": (
                        f"blocks={len(parsed.blocks)}; sections={parsed.section_count}; "
                        f"frequencies={parsed.frequency_count}"
                    ),
                    "rel_error": "",
                    "tolerance": "",
                    "status": (
                        "PASS"
                        if len(parsed.blocks) == result.metadata.expected_frequency_block_count
                        and parsed.section_count == PDSTRIP_SMOKE_SECTION_COUNT
                        else "FAIL"
                    ),
                    "note": "Parsed radiation, diffraction, and Froude-Krylov blocks for later coefficient comparison.",
                }
            )
        except (OSError, ValueError) as exc:
            rows.append(
                {
                    "benchmark": "pdstrip_external_smoke",
                    "metric": "pdstrip_external_sectionresults_parseable",
                    "expected": "parseable sectionresults radiation/excitation blocks",
                    "actual": type(exc).__name__,
                    "rel_error": "",
                    "tolerance": "",
                    "status": "FAIL",
                    "note": str(exc),
                }
            )
    return rows
