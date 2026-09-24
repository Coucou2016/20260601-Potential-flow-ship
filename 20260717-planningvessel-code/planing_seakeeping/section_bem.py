from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np


SECTION_BEM_STATUS = "experimental_2d_free_surface_source_panel_not_validated"
SECTION_BEM_MULTIMODE_STATUS = "experimental_multimode_2d_free_surface_source_panel_not_validated"
SECTION_BEM_PRESSURE_STATUS = "experimental_section_pressure_transfer_not_validated"
PDSTRIP_STYLE_STATUS = "experimental_pdstrip_style_section_solver_not_validated"
SECTION_RADIATION_MODES = ("sway", "heave", "roll")


@dataclass(frozen=True)
class SectionOffsets:
    """Open wetted-section contour from starboard waterline to port waterline.

    Coordinates use y positive to starboard and z positive downward from the
    calm-water free surface. The contour is the wetted body only; the waterline
    segment is not closed.
    """

    y_m: np.ndarray
    z_down_m: np.ndarray

    def __post_init__(self) -> None:
        y = np.asarray(self.y_m, dtype=float)
        z = np.asarray(self.z_down_m, dtype=float)
        if y.shape != z.shape or y.ndim != 1:
            raise ValueError("SectionOffsets y_m and z_down_m must be 1D arrays of the same length.")
        if len(y) < 3:
            raise ValueError("At least three section offset points are required.")
        if np.any(~np.isfinite(y)) or np.any(~np.isfinite(z)):
            raise ValueError("Section offset coordinates must be finite.")
        if np.max(z) <= 0.0:
            raise ValueError("Section offsets must include positive draft below the free surface.")
        object.__setattr__(self, "y_m", y)
        object.__setattr__(self, "z_down_m", z)

    @property
    def beam_m(self) -> float:
        return float(np.max(self.y_m) - np.min(self.y_m))

    @property
    def draft_m(self) -> float:
        return float(np.max(self.z_down_m))

    def resample_by_arclength(self, body_panel_count: int) -> "SectionOffsets":
        """Return the same open contour with a target number of body panels."""

        panel_count = int(body_panel_count)
        if panel_count < 2:
            raise ValueError("body_panel_count must be at least 2.")
        dy = np.diff(self.y_m)
        dz = np.diff(self.z_down_m)
        segment_lengths = np.hypot(dy, dz)
        total_length = float(np.sum(segment_lengths))
        if total_length <= 1e-12:
            raise ValueError("Cannot resample a section with near-zero contour length.")
        s_old = np.concatenate([[0.0], np.cumsum(segment_lengths)])
        s_new = np.linspace(0.0, total_length, panel_count + 1)
        return SectionOffsets(
            y_m=np.interp(s_new, s_old, self.y_m),
            z_down_m=np.interp(s_new, s_old, self.z_down_m),
        )


@dataclass(frozen=True)
class SectionBEMResult:
    complex_force_per_m: complex
    added_mass_per_m: float
    damping_per_m: float
    condition_number: float
    residual_norm: float
    panel_count: int
    free_surface_panel_count: int
    status: str = SECTION_BEM_STATUS


@dataclass(frozen=True)
class SectionBEMMultimodeResult:
    modes: tuple[str, ...]
    complex_force_matrix_per_m: np.ndarray
    added_mass_matrix_per_m: np.ndarray
    damping_matrix_per_m: np.ndarray
    condition_number: float
    residual_norm_by_mode: dict[str, float]
    panel_count: int
    free_surface_panel_count: int
    status: str = SECTION_BEM_MULTIMODE_STATUS


@dataclass(frozen=True)
class SectionBEMPressureTransferResult:
    modes: tuple[str, ...]
    panel_mid_y_m: np.ndarray
    panel_mid_z_down_m: np.ndarray
    panel_length_m: np.ndarray
    panel_normal_y: np.ndarray
    panel_normal_z: np.ndarray
    radiation_potential_m2_s: np.ndarray
    radiation_pressure_pa: np.ndarray
    incident_pressure_pa: np.ndarray
    diffracted_pressure_pa: np.ndarray
    total_wave_pressure_pa: np.ndarray
    radiation_force_matrix_per_m: np.ndarray
    total_wave_force_vector_per_m: np.ndarray
    condition_number: float
    radiation_residual_norm_by_mode: dict[str, float]
    diffraction_residual_norm: float
    wavenumber_rad_m: float
    transverse_wavenumber_rad_m: float
    panel_count: int
    free_surface_panel_count: int
    status: str = SECTION_BEM_PRESSURE_STATUS


@dataclass(frozen=True)
class SectionBEMExcitationResult:
    complex_vertical_force_per_m: complex
    complex_lateral_force_per_m: complex
    complex_roll_moment_per_m: complex
    condition_number: float
    residual_norm: float
    panel_count: int
    free_surface_panel_count: int
    status: str = SECTION_BEM_STATUS


def hard_chine_v_offsets(
    beam_m: float,
    draft_m: float,
    point_count_per_side: int = 10,
) -> SectionOffsets:
    """Return a symmetric V-section contour."""

    n = max(int(point_count_per_side), 2)
    half_beam = 0.5 * float(beam_m)
    draft = float(draft_m)
    right_t = np.linspace(0.0, 1.0, n, endpoint=False)
    left_t = np.linspace(0.0, 1.0, n + 1)
    right_y = half_beam * (1.0 - right_t)
    right_z = draft * right_t
    left_y = -half_beam * left_t
    left_z = draft * (1.0 - left_t)
    return SectionOffsets(
        y_m=np.concatenate([right_y, left_y]),
        z_down_m=np.concatenate([right_z, left_z]),
    )


def wigley_section_offsets(
    beam_m: float,
    draft_m: float,
    point_count_per_side: int = 14,
) -> SectionOffsets:
    """Return a parabolic Wigley-style section contour."""

    n = max(int(point_count_per_side), 3)
    half_beam = 0.5 * float(beam_m)
    draft = float(draft_m)
    right_z = np.linspace(0.0, draft, n, endpoint=False)
    left_z = np.linspace(draft, 0.0, n + 1)
    right_y = half_beam * np.maximum(0.0, 1.0 - (right_z / draft) ** 2)
    left_y = -half_beam * np.maximum(0.0, 1.0 - (left_z / draft) ** 2)
    return SectionOffsets(
        y_m=np.concatenate([right_y, left_y]),
        z_down_m=np.concatenate([right_z, left_z]),
    )


def _body_panels(offsets: SectionOffsets) -> dict[str, np.ndarray]:
    y0 = offsets.y_m[:-1]
    z0 = offsets.z_down_m[:-1]
    y1 = offsets.y_m[1:]
    z1 = offsets.z_down_m[1:]
    dy = y1 - y0
    dz = z1 - z0
    length = np.hypot(dy, dz)
    if np.any(length <= 1e-10):
        raise ValueError("Section contains a zero-length body panel.")
    mid_y = 0.5 * (y0 + y1)
    mid_z = 0.5 * (z0 + z1)
    normal_y = dz / length
    normal_z = -dy / length
    return {
        "mid_y": mid_y,
        "mid_z": mid_z,
        "normal_y": normal_y,
        "normal_z": normal_z,
        "length": length,
    }


def _source_potential(
    field_y: np.ndarray,
    field_z: np.ndarray,
    source_y: np.ndarray,
    source_z: np.ndarray,
) -> np.ndarray:
    dy = field_y[:, None] - source_y[None, :]
    dz = field_z[:, None] - source_z[None, :]
    r2 = np.maximum(dy**2 + dz**2, 1e-16)
    return np.log(np.sqrt(r2)) / (2.0 * math.pi)


def _source_normal_derivative(
    field_y: np.ndarray,
    field_z: np.ndarray,
    normal_y: np.ndarray,
    normal_z: np.ndarray,
    source_y: np.ndarray,
    source_z: np.ndarray,
) -> np.ndarray:
    dy = field_y[:, None] - source_y[None, :]
    dz = field_z[:, None] - source_z[None, :]
    r2 = np.maximum(dy**2 + dz**2, 1e-16)
    return (dy * normal_y[:, None] + dz * normal_z[:, None]) / (2.0 * math.pi * r2)


def _pdstrip_pq(dy: np.ndarray | float, dz: np.ndarray | float) -> np.ndarray:
    """PDSTRIP-style 2D source potential kernel for unit 2*pi flux."""

    dy_array = np.asarray(dy, dtype=float)
    dz_array = np.asarray(dz, dtype=float)
    return 0.5 * np.log(np.maximum(dy_array**2 + dz_array**2, 1e-24))


def _pdstrip_pqn(
    dy1: np.ndarray | float,
    dz1: np.ndarray | float,
    dy2: np.ndarray | float,
    dz2: np.ndarray | float,
) -> np.ndarray:
    """PDSTRIP-style source flux through a straight segment."""

    return -np.arctan2(np.asarray(dy2) * np.asarray(dz1) - np.asarray(dz2) * np.asarray(dy1),
                       np.asarray(dy1) * np.asarray(dy2) + np.asarray(dz1) * np.asarray(dz2))


def _pdstrip_pqs(
    y: np.ndarray | float,
    z: np.ndarray | float,
    yq: np.ndarray,
    zq: np.ndarray,
    mirror_sign: int,
) -> np.ndarray:
    return _pdstrip_pq(np.asarray(y) - yq, np.asarray(z) - zq) + mirror_sign * _pdstrip_pq(
        np.asarray(y) + yq,
        np.asarray(z) - zq,
    )


def _pdstrip_pqsn(
    y1: float,
    z1: float,
    y2: float,
    z2: float,
    yq: np.ndarray,
    zq: np.ndarray,
    mirror_sign: int,
) -> np.ndarray:
    return _pdstrip_pqn(y1 - yq, z1 - zq, y2 - yq, z2 - zq) + mirror_sign * _pdstrip_pqn(
        y1 + yq,
        z1 - zq,
        y2 + yq,
        z2 - zq,
    )


def _pdstrip_half_section(offsets: SectionOffsets) -> SectionOffsets:
    """Return the port-side half section expected by the symmetric PDSTRIP path."""

    # A flat bottom has many deepest points; only the actual centreline splits
    # the symmetric contour. Selecting argmax(depth) can create a folded half.
    centres = np.flatnonzero(np.abs(offsets.y_m) <= 1e-12)
    if len(centres) == 1:
        centre = int(centres[0])
        y = offsets.y_m[centre:].copy()
        z = offsets.z_down_m[centre:].copy()
    elif len(centres) == 0:
        crossings = np.flatnonzero(offsets.y_m[:-1] * offsets.y_m[1:] < 0)
        if len(crossings) != 1:
            raise ValueError("Symmetric section requires a unique centreline crossing")
        i = int(crossings[0])
        fraction = -offsets.y_m[i] / (offsets.y_m[i + 1] - offsets.y_m[i])
        centre_depth = offsets.z_down_m[i] + fraction * (offsets.z_down_m[i + 1] - offsets.z_down_m[i])
        y = np.r_[0., offsets.y_m[i + 1:]]
        z = np.r_[centre_depth, offsets.z_down_m[i + 1:]]
    else:
        raise ValueError("Symmetric section requires a unique centreline point")
    if len(y) < 2:
        raise ValueError("Cannot extract a half section from the supplied offsets.")
    if abs(float(y[-1])) < 1e-12:
        raise ValueError("Half section must end at a nonzero waterline breadth.")
    if y[-1] > 0.0:
        y = -y
    if np.any(y > 1e-12):
        raise ValueError("Extracted half section crosses the centreline")
    y[0] = 0.0
    z[0] = max(float(z[0]), 1e-8)
    z[-1] = 0.0
    if len(y) < 3:
        y = np.asarray([y[0], 0.5 * (y[0] + y[-1]), y[-1]], dtype=float)
        z = np.asarray([z[0], 0.5 * z[0], z[-1]], dtype=float)
    return SectionOffsets(y_m=y, z_down_m=z)


def _build_free_surface(half_width: float, panel_count_per_side: int) -> dict[str, np.ndarray]:
    n = max(int(panel_count_per_side), 4)
    right_edges = np.linspace(0.0, float(half_width), n + 1)
    left_edges = -right_edges[::-1]
    right_mid = 0.5 * (right_edges[:-1] + right_edges[1:])
    left_mid = 0.5 * (left_edges[:-1] + left_edges[1:])
    mid_y = np.concatenate([left_mid, right_mid])
    panel_lengths = np.concatenate([np.diff(left_edges), np.diff(right_edges)])
    panel_lengths = np.abs(panel_lengths)
    return {
        "mid_y": mid_y,
        "mid_z": np.zeros_like(mid_y),
        "source_y": mid_y,
        "source_z": np.maximum(0.05 * panel_lengths, 1e-5),
        "panel_lengths": panel_lengths,
    }


def _build_source_system(
    offsets: SectionOffsets,
    omega_rad_s: float,
    gravity_m_s2: float,
    free_surface_panel_count_per_side: int,
    body_panel_count: int | None,
    body_source_offset_fraction: float,
    control_width_factor: float,
    radiation_damping: float,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], np.ndarray, np.ndarray, np.ndarray]:
    omega = max(float(omega_rad_s), 1e-6)
    working_offsets = offsets.resample_by_arclength(body_panel_count) if body_panel_count is not None else offsets
    body = _body_panels(working_offsets)
    body_count = len(body["length"])
    half_width = max(control_width_factor * working_offsets.beam_m, 4.0 * working_offsets.draft_m, 1.0e-3)
    free = _build_free_surface(half_width, free_surface_panel_count_per_side)

    body_source_y = body["mid_y"] - body_source_offset_fraction * body["length"] * body["normal_y"]
    body_source_z = body["mid_z"] - body_source_offset_fraction * body["length"] * body["normal_z"]
    source_y = np.concatenate([body_source_y, free["source_y"]])
    source_z = np.concatenate([body_source_z, free["source_z"]])

    body_derivative = _source_normal_derivative(
        body["mid_y"],
        body["mid_z"],
        body["normal_y"],
        body["normal_z"],
        source_y,
        source_z,
    )
    for idx in range(body_count):
        body_derivative[idx, idx] -= 0.5

    k_complex = (omega**2 / float(gravity_m_s2)) * (1.0 + 1j * max(float(radiation_damping), 0.0))
    free_potential = _source_potential(free["mid_y"], free["mid_z"], source_y, source_z)
    free_vertical_derivative = _source_normal_derivative(
        free["mid_y"],
        free["mid_z"],
        np.zeros_like(free["mid_y"]),
        np.ones_like(free["mid_y"]),
        source_y,
        source_z,
    )
    free_condition = free_vertical_derivative + k_complex * free_potential
    matrix = np.vstack([body_derivative, free_condition]).astype(complex)
    return body, free, source_y, source_z, matrix


def _solve_source_strengths(matrix: np.ndarray, rhs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    try:
        strengths = np.linalg.solve(matrix, rhs)
        residual = matrix @ strengths - rhs
    except np.linalg.LinAlgError:
        strengths, *_ = np.linalg.lstsq(matrix, rhs, rcond=1e-10)
        residual = matrix @ strengths - rhs
    return strengths, residual


def _section_mode_shape(body: dict[str, np.ndarray], mode: str) -> tuple[np.ndarray, np.ndarray]:
    mode_name = mode.strip().lower()
    normal_y = body["normal_y"]
    normal_z = body["normal_z"]
    y = body["mid_y"]
    z = body["mid_z"]
    if mode_name == "sway":
        return normal_y, -normal_y
    if mode_name == "heave":
        return normal_z, -normal_z
    if mode_name == "roll":
        normal_velocity_shape = -z * normal_y + y * normal_z
        generalized_force_projection = -normal_velocity_shape
        return normal_velocity_shape, generalized_force_projection
    raise ValueError(f"Unsupported section radiation mode: {mode!r}.")


def solve_radiation_modes(
    offsets: SectionOffsets,
    omega_rad_s: float,
    modes: tuple[str, ...] = SECTION_RADIATION_MODES,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    free_surface_panel_count_per_side: int = 10,
    body_panel_count: int | None = None,
    body_source_offset_fraction: float = 0.08,
    control_width_factor: float = 6.0,
    radiation_damping: float = 0.04,
) -> SectionBEMMultimodeResult:
    """Solve a compact 2D section-radiation matrix for sway/heave/roll modes.

    The scalar heave solver is retained for the existing station path. This
    matrix interface is an audit step toward PDSTRIP/Ma-style section data,
    where each station provides a 3x3 complex radiation matrix and pressure
    transfer functions before the 2.5D forward-speed assembly.
    """

    omega = max(float(omega_rad_s), 1e-6)
    cleaned_modes: tuple[str, ...] = tuple(mode.strip().lower() for mode in modes)
    if not cleaned_modes:
        raise ValueError("At least one section radiation mode is required.")
    if len(set(cleaned_modes)) != len(cleaned_modes):
        raise ValueError("Section radiation modes must be unique.")
    unsupported = sorted(set(cleaned_modes).difference(SECTION_RADIATION_MODES))
    if unsupported:
        raise ValueError(f"Unsupported section radiation modes: {', '.join(unsupported)}.")

    body, free, source_y, source_z, matrix = _build_source_system(
        offsets,
        omega_rad_s=omega,
        gravity_m_s2=gravity_m_s2,
        free_surface_panel_count_per_side=free_surface_panel_count_per_side,
        body_panel_count=body_panel_count,
        body_source_offset_fraction=body_source_offset_fraction,
        control_width_factor=control_width_factor,
        radiation_damping=radiation_damping,
    )
    body_potential_influence = _source_potential(body["mid_y"], body["mid_z"], source_y, source_z).astype(complex)
    force_projections = []
    column_forces: list[np.ndarray] = []
    residual_norm_by_mode: dict[str, float] = {}
    rhs_norm_floor = 1e-12

    for response_mode in cleaned_modes:
        _, force_projection = _section_mode_shape(body, response_mode)
        force_projections.append(force_projection)

    for excitation_mode in cleaned_modes:
        normal_velocity_shape, _ = _section_mode_shape(body, excitation_mode)
        rhs_body = -1j * omega * normal_velocity_shape
        rhs = np.concatenate([rhs_body, np.zeros(len(free["mid_y"]), dtype=complex)])
        strengths, residual = _solve_source_strengths(matrix, rhs)
        potential = body_potential_influence @ strengths
        pressure = -1j * float(rho_water_kg_m3) * omega * potential
        generalized_forces = np.asarray(
            [np.sum(pressure * projection * body["length"]) for projection in force_projections],
            dtype=complex,
        )
        column_index = cleaned_modes.index(excitation_mode)
        diag_force = generalized_forces[column_index]
        diag_added = float(np.real(diag_force) / omega**2)
        diag_damping = float(-np.imag(diag_force) / omega)
        if diag_added < 0.0 and diag_damping < 0.0:
            generalized_forces = -generalized_forces
        column_forces.append(generalized_forces)
        residual_norm_by_mode[excitation_mode] = float(np.linalg.norm(residual) / max(np.linalg.norm(rhs), rhs_norm_floor))

    force_matrix = np.column_stack(column_forces)
    return SectionBEMMultimodeResult(
        modes=cleaned_modes,
        complex_force_matrix_per_m=force_matrix,
        added_mass_matrix_per_m=np.real(force_matrix) / omega**2,
        damping_matrix_per_m=-np.imag(force_matrix) / omega,
        condition_number=float(np.linalg.cond(matrix)),
        residual_norm_by_mode=residual_norm_by_mode,
        panel_count=int(len(body["length"])),
        free_surface_panel_count=int(len(free["mid_y"])),
    )


def section_bem_multimode_radiation_diagnostics(
    offsets: SectionOffsets,
    omega_rad_s: float,
    modes: tuple[str, ...] = SECTION_RADIATION_MODES,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    free_surface_panel_count_per_side: int = 10,
    body_panel_count: int | None = None,
) -> list[dict[str, float | str]]:
    """Return flattened diagnostics for the experimental multi-mode matrix."""

    result = solve_radiation_modes(
        offsets,
        omega_rad_s=omega_rad_s,
        modes=modes,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        free_surface_panel_count_per_side=free_surface_panel_count_per_side,
        body_panel_count=body_panel_count,
    )
    rows: list[dict[str, float | str]] = []
    for row_index, response_mode in enumerate(result.modes):
        for col_index, excitation_mode in enumerate(result.modes):
            force = result.complex_force_matrix_per_m[row_index, col_index]
            reciprocal_added_gap = ""
            reciprocal_damping_gap = ""
            if response_mode in result.modes and excitation_mode in result.modes:
                reciprocal_added_gap = float(
                    result.added_mass_matrix_per_m[row_index, col_index]
                    - result.added_mass_matrix_per_m[col_index, row_index]
                )
                reciprocal_damping_gap = float(
                    result.damping_matrix_per_m[row_index, col_index]
                    - result.damping_matrix_per_m[col_index, row_index]
                )
            rows.append(
                {
                    "omega_rad_s": float(omega_rad_s),
                    "response_mode": response_mode,
                    "excitation_mode": excitation_mode,
                    "complex_force_real_per_m": float(np.real(force)),
                    "complex_force_imag_per_m": float(np.imag(force)),
                    "added_mass_per_m": float(result.added_mass_matrix_per_m[row_index, col_index]),
                    "damping_per_m": float(result.damping_matrix_per_m[row_index, col_index]),
                    "reciprocal_added_gap_per_m": reciprocal_added_gap,
                    "reciprocal_damping_gap_per_m": reciprocal_damping_gap,
                    "condition_number": result.condition_number,
                    "residual_norm": result.residual_norm_by_mode[excitation_mode],
                    "body_panel_count": result.panel_count,
                    "free_surface_panel_count": result.free_surface_panel_count,
                    "status": result.status,
                }
            )
    return rows


def solve_pressure_transfer(
    offsets: SectionOffsets,
    omega_rad_s: float,
    wave_amplitude_m: float = 1.0,
    wavenumber_rad_m: float | None = None,
    transverse_wavenumber_rad_m: float = 0.0,
    modes: tuple[str, ...] = SECTION_RADIATION_MODES,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    free_surface_panel_count_per_side: int = 10,
    body_panel_count: int | None = None,
    body_source_offset_fraction: float = 0.08,
    control_width_factor: float = 6.0,
    radiation_damping: float = 0.04,
) -> SectionBEMPressureTransferResult:
    """Return experimental body-panel pressure transfer functions.

    Radiation pressures are reported for unit generalized displacement in each
    section mode. Wave pressures are reported as incident, diffracted, and total
    pressure for the fixed-section diffraction problem. This is still a compact
    source-panel diagnostic, not the validated Ma 2005 matched BIEM.
    """

    omega = max(float(omega_rad_s), 1e-6)
    cleaned_modes: tuple[str, ...] = tuple(mode.strip().lower() for mode in modes)
    if not cleaned_modes:
        raise ValueError("At least one section radiation mode is required.")
    if len(set(cleaned_modes)) != len(cleaned_modes):
        raise ValueError("Section radiation modes must be unique.")
    unsupported = sorted(set(cleaned_modes).difference(SECTION_RADIATION_MODES))
    if unsupported:
        raise ValueError(f"Unsupported section radiation modes: {', '.join(unsupported)}.")

    wave_number = float(wavenumber_rad_m) if wavenumber_rad_m is not None else omega**2 / float(gravity_m_s2)
    wave_number = max(wave_number, 1e-9)
    transverse = float(np.clip(float(transverse_wavenumber_rad_m), -wave_number, wave_number))
    body, free, source_y, source_z, matrix = _build_source_system(
        offsets,
        omega_rad_s=omega,
        gravity_m_s2=gravity_m_s2,
        free_surface_panel_count_per_side=free_surface_panel_count_per_side,
        body_panel_count=body_panel_count,
        body_source_offset_fraction=body_source_offset_fraction,
        control_width_factor=control_width_factor,
        radiation_damping=radiation_damping,
    )
    influence = _source_potential(body["mid_y"], body["mid_z"], source_y, source_z).astype(complex)
    force_projections = [_section_mode_shape(body, mode)[1] for mode in cleaned_modes]
    radiation_potentials: list[np.ndarray] = []
    radiation_pressures: list[np.ndarray] = []
    radiation_force_columns: list[np.ndarray] = []
    radiation_residuals: dict[str, float] = {}

    for excitation_mode in cleaned_modes:
        normal_velocity_shape, _ = _section_mode_shape(body, excitation_mode)
        rhs = np.concatenate([-1j * omega * normal_velocity_shape, np.zeros(len(free["mid_y"]), dtype=complex)])
        strengths, residual = _solve_source_strengths(matrix, rhs)
        potential = influence @ strengths
        pressure = -1j * float(rho_water_kg_m3) * omega * potential
        generalized_forces = np.asarray(
            [np.sum(pressure * projection * body["length"]) for projection in force_projections],
            dtype=complex,
        )
        column_index = cleaned_modes.index(excitation_mode)
        diag_force = generalized_forces[column_index]
        diag_added = float(np.real(diag_force) / omega**2)
        diag_damping = float(-np.imag(diag_force) / omega)
        if diag_added < 0.0 and diag_damping < 0.0:
            potential = -potential
            pressure = -pressure
            generalized_forces = -generalized_forces
        radiation_potentials.append(potential)
        radiation_pressures.append(pressure)
        radiation_force_columns.append(generalized_forces)
        radiation_residuals[excitation_mode] = float(np.linalg.norm(residual) / max(np.linalg.norm(rhs), 1e-12))

    phase_body = np.exp(1j * transverse * body["mid_y"] - wave_number * body["mid_z"])
    incident_potential = -1j * float(gravity_m_s2) * float(wave_amplitude_m) * phase_body / omega
    dphi_dy = 1j * transverse * incident_potential
    dphi_dz_down = -wave_number * incident_potential
    incident_normal_derivative = dphi_dy * body["normal_y"] + dphi_dz_down * body["normal_z"]
    diffraction_rhs = np.concatenate(
        [
            -incident_normal_derivative,
            np.zeros(len(free["mid_y"]), dtype=complex),
        ]
    )
    diffraction_strengths, diffraction_residual = _solve_source_strengths(matrix, diffraction_rhs)
    diffracted_potential = influence @ diffraction_strengths
    incident_pressure = -1j * float(rho_water_kg_m3) * omega * incident_potential
    diffracted_pressure = -1j * float(rho_water_kg_m3) * omega * diffracted_potential
    total_pressure = incident_pressure + diffracted_pressure

    force_y_panel = total_pressure * (-body["normal_y"]) * body["length"]
    force_up_panel = total_pressure * (-body["normal_z"]) * body["length"]
    roll_moment_panel = body["mid_y"] * force_up_panel + body["mid_z"] * force_y_panel
    wave_force_by_mode: list[complex] = []
    for mode in cleaned_modes:
        if mode == "sway":
            wave_force_by_mode.append(complex(np.sum(force_y_panel)))
        elif mode == "heave":
            wave_force_by_mode.append(complex(np.sum(force_up_panel)))
        elif mode == "roll":
            wave_force_by_mode.append(complex(np.sum(roll_moment_panel)))

    return SectionBEMPressureTransferResult(
        modes=cleaned_modes,
        panel_mid_y_m=body["mid_y"],
        panel_mid_z_down_m=body["mid_z"],
        panel_length_m=body["length"],
        panel_normal_y=body["normal_y"],
        panel_normal_z=body["normal_z"],
        radiation_potential_m2_s=np.column_stack(radiation_potentials),
        radiation_pressure_pa=np.column_stack(radiation_pressures),
        incident_pressure_pa=incident_pressure,
        diffracted_pressure_pa=diffracted_pressure,
        total_wave_pressure_pa=total_pressure,
        radiation_force_matrix_per_m=np.column_stack(radiation_force_columns),
        total_wave_force_vector_per_m=np.asarray(wave_force_by_mode, dtype=complex),
        condition_number=float(np.linalg.cond(matrix)),
        radiation_residual_norm_by_mode=radiation_residuals,
        diffraction_residual_norm=float(
            np.linalg.norm(diffraction_residual) / max(np.linalg.norm(diffraction_rhs), 1e-12)
        ),
        wavenumber_rad_m=wave_number,
        transverse_wavenumber_rad_m=transverse,
        panel_count=int(len(body["length"])),
        free_surface_panel_count=int(len(free["mid_y"])),
    )


def section_bem_pressure_transfer_diagnostics(
    offsets: SectionOffsets,
    omega_rad_s: float,
    wave_amplitude_m: float = 1.0,
    wavenumber_rad_m: float | None = None,
    transverse_wavenumber_rad_m: float = 0.0,
    modes: tuple[str, ...] = SECTION_RADIATION_MODES,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    free_surface_panel_count_per_side: int = 10,
    body_panel_count: int | None = None,
) -> list[dict[str, float | str]]:
    """Return flattened body-panel pressure-transfer diagnostics."""

    result = solve_pressure_transfer(
        offsets,
        omega_rad_s=omega_rad_s,
        wave_amplitude_m=wave_amplitude_m,
        wavenumber_rad_m=wavenumber_rad_m,
        transverse_wavenumber_rad_m=transverse_wavenumber_rad_m,
        modes=modes,
        rho_water_kg_m3=rho_water_kg_m3,
        gravity_m_s2=gravity_m_s2,
        free_surface_panel_count_per_side=free_surface_panel_count_per_side,
        body_panel_count=body_panel_count,
    )
    rows: list[dict[str, float | str]] = []

    def append_row(panel_index: int, pressure_kind: str, radiation_mode: str, pressure: complex, residual: float) -> None:
        rows.append(
            {
                "omega_rad_s": float(omega_rad_s),
                "wavenumber_rad_m": result.wavenumber_rad_m,
                "transverse_wavenumber_rad_m": result.transverse_wavenumber_rad_m,
                "wave_amplitude_m": float(wave_amplitude_m),
                "panel_index": int(panel_index),
                "panel_mid_y_m": float(result.panel_mid_y_m[panel_index]),
                "panel_mid_z_down_m": float(result.panel_mid_z_down_m[panel_index]),
                "panel_length_m": float(result.panel_length_m[panel_index]),
                "panel_normal_y": float(result.panel_normal_y[panel_index]),
                "panel_normal_z": float(result.panel_normal_z[panel_index]),
                "pressure_kind": pressure_kind,
                "radiation_mode": radiation_mode,
                "pressure_real_pa": float(np.real(pressure)),
                "pressure_imag_pa": float(np.imag(pressure)),
                "pressure_abs_pa": float(abs(pressure)),
                "condition_number": result.condition_number,
                "residual_norm": residual,
                "body_panel_count": result.panel_count,
                "free_surface_panel_count": result.free_surface_panel_count,
                "status": result.status,
            }
        )

    for panel_index in range(result.panel_count):
        for mode_index, mode in enumerate(result.modes):
            append_row(
                panel_index,
                "radiation",
                mode,
                result.radiation_pressure_pa[panel_index, mode_index],
                result.radiation_residual_norm_by_mode[mode],
            )
        append_row(panel_index, "wave_incident", "", result.incident_pressure_pa[panel_index], result.diffraction_residual_norm)
        append_row(
            panel_index,
            "wave_diffracted",
            "",
            result.diffracted_pressure_pa[panel_index],
            result.diffraction_residual_norm,
        )
        append_row(panel_index, "wave_total", "", result.total_wave_pressure_pa[panel_index], result.diffraction_residual_norm)
    return rows


def solve_heave_radiation(
    offsets: SectionOffsets,
    omega_rad_s: float,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    free_surface_panel_count_per_side: int = 10,
    body_panel_count: int | None = None,
    body_source_offset_fraction: float = 0.08,
    control_width_factor: float = 6.0,
    radiation_damping: float = 0.04,
) -> SectionBEMResult:
    """Solve an experimental 2D free-surface source-panel heave problem.

    This is a compact development solver, not yet the matched BIEM described by
    Ma 2005. It creates the boundary-integral API and diagnostics needed before
    replacing the empirical station radiation kernels.
    """

    omega = max(float(omega_rad_s), 1e-6)
    body, free, source_y, source_z, matrix = _build_source_system(
        offsets,
        omega_rad_s=omega,
        gravity_m_s2=gravity_m_s2,
        free_surface_panel_count_per_side=free_surface_panel_count_per_side,
        body_panel_count=body_panel_count,
        body_source_offset_fraction=body_source_offset_fraction,
        control_width_factor=control_width_factor,
        radiation_damping=radiation_damping,
    )
    rhs_body = -1j * omega * body["normal_z"]
    rhs = np.concatenate([rhs_body, np.zeros(len(free["mid_y"]), dtype=complex)])
    strengths, residual = _solve_source_strengths(matrix, rhs)

    body_potential = _source_potential(body["mid_y"], body["mid_z"], source_y, source_z).astype(complex) @ strengths
    pressure = -1j * float(rho_water_kg_m3) * omega * body_potential
    force_up = np.sum(pressure * (-body["normal_z"]) * body["length"])
    added = float(np.real(force_up) / omega**2)
    damping = float(-np.imag(force_up) / omega)
    if added < 0.0 and damping < 0.0:
        force_up = -force_up
        added = -added
        damping = -damping
    return SectionBEMResult(
        complex_force_per_m=complex(force_up),
        added_mass_per_m=float(added),
        damping_per_m=float(max(damping, 0.0)),
        condition_number=float(np.linalg.cond(matrix)),
        residual_norm=float(np.linalg.norm(residual) / max(np.linalg.norm(rhs), 1e-12)),
        panel_count=int(len(body["length"])),
        free_surface_panel_count=int(len(free["mid_y"])),
    )


def _solve_heave_radiation_pdstrip_near_count(
    offsets: SectionOffsets,
    omega_rad_s: float,
    rho_water_kg_m3: float,
    gravity_m_s2: float,
    free_surface_panel_count_per_side: int,
    body_panel_count: int | None,
    near_panel_count: int,
    strict: bool = False,
) -> tuple[complex, float, float, int, int]:
    """Solve one symmetric-section heave case with a PDSTRIP-style source system."""

    if strict and (not np.isfinite([omega_rad_s, rho_water_kg_m3, gravity_m_s2]).all()
                   or min(omega_rad_s, rho_water_kg_m3, gravity_m_s2) <= 0):
        raise ValueError("Strict section solve requires finite positive frequency/density/gravity")
    omega = max(float(omega_rad_s), 1e-6)
    half = _pdstrip_half_section(offsets)
    working = half.resample_by_arclength(body_panel_count) if body_panel_count is not None else half
    y_body = working.y_m
    z_body = working.z_down_m
    nof = len(y_body)
    body_count = nof - 1
    nfs = max(int(free_surface_panel_count_per_side), 8)
    nf = min(max(int(near_panel_count), 2), nfs - 2)
    unknown_count = nof + nfs

    y_nodes = np.zeros(nof + nfs + 1, dtype=float)
    z_nodes = np.zeros(nof + nfs + 1, dtype=float)
    y_nodes[1 : nof + 1] = y_body
    z_nodes[1 : nof + 1] = z_body

    source_y = np.zeros(unknown_count, dtype=float)
    source_z = np.zeros(unknown_count, dtype=float)

    for k in range(1, nof):
        dy = y_nodes[k + 1] - y_nodes[k]
        dz = z_nodes[k + 1] - z_nodes[k]
        source_y[k] = 0.5 * (y_nodes[k] + y_nodes[k + 1]) - dz / 20.0
        source_z[k] = 0.5 * (z_nodes[k] + z_nodes[k + 1]) + dy / 20.0

    wave_number = max(omega**2 / float(gravity_m_s2), 1e-9)
    h = math.hypot(y_nodes[nof] - y_nodes[nof - 1], z_nodes[nof] - z_nodes[nof - 1])
    h = max(h, 1e-6)
    h_end = 2.0 * math.pi / (12.0 * wave_number)
    for k in range(nof, nof + nfs):
        h = min(h * 1.5, h_end)
        y_nodes[k + 1] = y_nodes[k] - h
        z_nodes[k + 1] = 0.0
        source_y[k] = y_nodes[k] - 0.5 * h
        source_z[k] = -h

    source_y[0] = 0.0
    source_z[0] = -abs(float(y_nodes[nof + nfs])) / 2.0

    matrix = np.zeros((unknown_count, unknown_count), dtype=complex)
    rhs = np.zeros(unknown_count, dtype=complex)
    mirror_sign = 1
    ciom = 1j * omega

    matrix[0, :] = 1.0
    for k in range(1, nof):
        row = k
        y1, z1 = float(y_nodes[k]), float(z_nodes[k])
        y2, z2 = float(y_nodes[k + 1]), float(z_nodes[k + 1])
        dy = y2 - y1
        matrix[row, :] = _pdstrip_pqsn(y1, z1, y2, z2, source_y, source_z, mirror_sign)
        # PDSTRIP simqcd stores NEGATIVE right-hand sides (source lines 704-705).
        # numpy.linalg.solve expects the actual right-hand side.
        rhs[row] = -ciom * dy

    for k in range(nof, nof + nf + 1):
        row = k
        y1, y2 = float(y_nodes[k]), float(y_nodes[k + 1])
        dy = y2 - y1
        matrix[row, :] = _pdstrip_pqsn(y1, 0.0, y2, 0.0, source_y, source_z, mirror_sign)
        matrix[row, :] += (
            wave_number
            * abs(dy)
            * (
                _pdstrip_pqs(y1 + 0.316 * dy, 0.0, source_y, source_z, mirror_sign)
                + _pdstrip_pqs(y1 + 0.684 * dy, 0.0, source_y, source_z, mirror_sign)
            )
            / 2.0
        )

    far_denominator = max(nfs - nf - 1, 1)
    for k in range(nof + nf + 1, nof + nfs):
        row = k
        y1, y2 = float(y_nodes[k]), float(y_nodes[k + 1])
        dy = y2 - y1
        factor = ((k - nof - nf) / far_denominator) ** 2
        matrix[row, :] = (
            wave_number
            * abs(dy)
            * (
                _pdstrip_pqs(y1 + 0.316 * dy, 0.0, source_y, source_z, mirror_sign)
                + _pdstrip_pqs(y1 + 0.684 * dy, 0.0, source_y, source_z, mirror_sign)
            )
            / 2.0
        )
        matrix[row, :] += -1j * (
            _pdstrip_pqs(y2 - factor * dy, 0.0, source_y, source_z, mirror_sign)
            - _pdstrip_pqs(y1 - factor * dy, 0.0, source_y, source_z, mirror_sign)
        )

    try:
        strengths = np.linalg.solve(matrix, rhs)
        residual = matrix @ strengths - rhs
    except np.linalg.LinAlgError:
        if strict:
            raise
        strengths, *_ = np.linalg.lstsq(matrix, rhs, rcond=1e-10)
        residual = matrix @ strengths - rhs

    force = 0.0j
    for k in range(1, nof):
        y1, z1 = float(y_nodes[k]), float(z_nodes[k])
        y2, z2 = float(y_nodes[k + 1]), float(z_nodes[k + 1])
        dy = y2 - y1
        dz = z2 - z1
        force += np.sum(
            strengths
            * dy
            * (
                _pdstrip_pqs(y1 + 0.316 * dy, z1 + 0.316 * dz, source_y, source_z, mirror_sign)
                + _pdstrip_pqs(y1 + 0.684 * dy, z1 + 0.684 * dz, source_y, source_z, mirror_sign)
            )
            / 2.0
        )

    # This force integral covers one half-section. Original PDSTRIP sums two
    # discretizations: averaging and the symmetry factor cancel (line 622).
    # Here each solve returns the full-section value before outer averaging.
    complex_added = 2.0 * ciom * force / (-omega**2) * float(rho_water_kg_m3)
    residual_norm = float(np.linalg.norm(residual) / max(np.linalg.norm(rhs), 1e-12))
    condition_number = float(np.linalg.cond(matrix))
    return complex(complex_added), condition_number, residual_norm, body_count, nfs


def solve_heave_radiation_pdstrip_style(
    offsets: SectionOffsets,
    omega_rad_s: float,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    free_surface_panel_count_per_side: int = 16,
    body_panel_count: int | None = None,
    strict: bool = False,
) -> SectionBEMResult:
    """Solve heave radiation with a PDSTRIP-inspired integral source system.

    This ports the panel-integral source influence and free-surface radiation
    condition used by the open-source PDSTRIP section solver into the Python
    diagnostics path. It remains a development solver until it passes Ma 2005.
    """

    if strict and (type(free_surface_panel_count_per_side) is not int or free_surface_panel_count_per_side < 8
                   or (body_panel_count is not None and (type(body_panel_count) is not int or body_panel_count < 3))):
        raise ValueError("Strict section solve requires explicit valid panel counts")
    nfs = max(int(free_surface_panel_count_per_side), 8)
    near_counts = sorted({min(max(int(round(0.45 * nfs)), 2), nfs - 2), min(max(int(round(0.51 * nfs)), 2), nfs - 2)})
    complex_values: list[complex] = []
    conditions: list[float] = []
    residuals: list[float] = []
    body_count = 0
    for near_count in near_counts:
        value, condition, residual, body_count, actual_nfs = _solve_heave_radiation_pdstrip_near_count(
            offsets,
            omega_rad_s=omega_rad_s,
            rho_water_kg_m3=rho_water_kg_m3,
            gravity_m_s2=gravity_m_s2,
            free_surface_panel_count_per_side=nfs,
            body_panel_count=body_panel_count,
            near_panel_count=near_count,
            strict=strict,
        )
        complex_values.append(value)
        conditions.append(condition)
        residuals.append(residual)
    complex_added = complex(np.mean(complex_values))
    added = float(np.real(complex_added))
    damping = float(-np.imag(complex_added) * max(float(omega_rad_s), 1e-6))
    if not strict and added < 0.0 and damping < 0.0:
        complex_added = -complex_added
        added = -added
        damping = -damping
    return SectionBEMResult(
        complex_force_per_m=complex_added,
        added_mass_per_m=float(added if strict else max(added, 0.0)),
        damping_per_m=float(damping if strict else max(damping, 0.0)),
        condition_number=float(max(conditions)),
        residual_norm=float(max(residuals)),
        panel_count=int(body_count),
        free_surface_panel_count=int(actual_nfs),
        status="strict_raw_pdstrip_style_not_validated" if strict else PDSTRIP_STYLE_STATUS,
    )


def solve_wave_excitation(
    offsets: SectionOffsets,
    omega_rad_s: float,
    wave_amplitude_m: float = 1.0,
    wavenumber_rad_m: float | None = None,
    transverse_wavenumber_rad_m: float = 0.0,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    free_surface_panel_count_per_side: int = 10,
    body_panel_count: int | None = None,
    body_source_offset_fraction: float = 0.08,
    control_width_factor: float = 6.0,
    radiation_damping: float = 0.04,
) -> SectionBEMExcitationResult:
    """Solve an experimental 2D fixed-section incident/diffraction problem.

    The incident potential is a linear deep-water wave with optional transverse
    wavenumber. Body boundary condition is fixed-body diffraction,
    d(phi_D)/dn = -d(phi_I)/dn. This diagnostic path is intentionally compact
    and is not the Ma 2005 matched-domain 2.5D implementation.
    """

    omega = max(float(omega_rad_s), 1e-6)
    wave_number = float(wavenumber_rad_m) if wavenumber_rad_m is not None else omega**2 / float(gravity_m_s2)
    wave_number = max(wave_number, 1e-9)
    transverse = float(np.clip(float(transverse_wavenumber_rad_m), -wave_number, wave_number))
    body, free, source_y, source_z, matrix = _build_source_system(
        offsets,
        omega_rad_s=omega,
        gravity_m_s2=gravity_m_s2,
        free_surface_panel_count_per_side=free_surface_panel_count_per_side,
        body_panel_count=body_panel_count,
        body_source_offset_fraction=body_source_offset_fraction,
        control_width_factor=control_width_factor,
        radiation_damping=radiation_damping,
    )

    phase_body = np.exp(1j * transverse * body["mid_y"] - wave_number * body["mid_z"])
    incident_body = -1j * float(gravity_m_s2) * float(wave_amplitude_m) * phase_body / omega
    dphi_dy = 1j * transverse * incident_body
    dphi_dz_down = -wave_number * incident_body
    incident_normal_derivative = dphi_dy * body["normal_y"] + dphi_dz_down * body["normal_z"]

    rhs = np.concatenate(
        [
            -incident_normal_derivative,
            np.zeros(len(free["mid_y"]), dtype=complex),
        ]
    )
    strengths, residual = _solve_source_strengths(matrix, rhs)
    diffracted_body = _source_potential(body["mid_y"], body["mid_z"], source_y, source_z).astype(complex) @ strengths
    total_potential = incident_body + diffracted_body
    pressure = -1j * float(rho_water_kg_m3) * omega * total_potential

    force_y_panel = pressure * (-body["normal_y"]) * body["length"]
    force_up_panel = pressure * (-body["normal_z"]) * body["length"]
    roll_moment_panel = body["mid_y"] * force_up_panel + body["mid_z"] * force_y_panel
    return SectionBEMExcitationResult(
        complex_vertical_force_per_m=complex(np.sum(force_up_panel)),
        complex_lateral_force_per_m=complex(np.sum(force_y_panel)),
        complex_roll_moment_per_m=complex(np.sum(roll_moment_panel)),
        condition_number=float(np.linalg.cond(matrix)),
        residual_norm=float(np.linalg.norm(residual) / max(np.linalg.norm(rhs), 1e-12)),
        panel_count=int(len(body["length"])),
        free_surface_panel_count=int(len(free["mid_y"])),
    )


def section_bem_convergence_study(
    offsets: SectionOffsets,
    omega_rad_s: float,
    panel_counts_per_side: tuple[int, ...] = (6, 8, 10, 12),
    body_panel_count: int | None = None,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
) -> list[dict[str, float | str]]:
    """Run a free-surface-panel convergence sweep for one section."""

    rows: list[dict[str, float | str]] = []
    previous: SectionBEMResult | None = None
    for panel_count in panel_counts_per_side:
        result = solve_heave_radiation(
            offsets,
            omega_rad_s=omega_rad_s,
            rho_water_kg_m3=rho_water_kg_m3,
            gravity_m_s2=gravity_m_s2,
            free_surface_panel_count_per_side=int(panel_count),
            body_panel_count=body_panel_count,
        )
        added_change = ""
        damping_change = ""
        if previous is not None:
            added_change = abs(result.added_mass_per_m - previous.added_mass_per_m) / max(
                abs(result.added_mass_per_m),
                1e-12,
            )
            damping_change = abs(result.damping_per_m - previous.damping_per_m) / max(
                abs(result.damping_per_m),
                1e-12,
            )
        rows.append(
            {
                "free_surface_panels_per_side": int(panel_count),
                "omega_rad_s": float(omega_rad_s),
                "added_mass_per_m": result.added_mass_per_m,
                "damping_per_m": result.damping_per_m,
                "added_mass_rel_change_from_previous": added_change,
                "damping_rel_change_from_previous": damping_change,
                "condition_number": result.condition_number,
                "residual_norm": result.residual_norm,
                "body_panel_count": result.panel_count,
                "free_surface_panel_count": result.free_surface_panel_count,
                "status": result.status,
            }
        )
        previous = result
    return rows


def section_bem_body_panel_convergence_study(
    offsets: SectionOffsets,
    omega_rad_s: float,
    body_panel_counts: tuple[int, ...] = (8, 12, 16, 20),
    free_surface_panel_count_per_side: int = 12,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
) -> list[dict[str, float | str]]:
    """Run a body-panel convergence sweep for one section."""

    rows: list[dict[str, float | str]] = []
    previous: SectionBEMResult | None = None
    for body_panel_count in body_panel_counts:
        result = solve_heave_radiation(
            offsets,
            omega_rad_s=omega_rad_s,
            rho_water_kg_m3=rho_water_kg_m3,
            gravity_m_s2=gravity_m_s2,
            free_surface_panel_count_per_side=free_surface_panel_count_per_side,
            body_panel_count=int(body_panel_count),
        )
        added_change = ""
        damping_change = ""
        if previous is not None:
            added_change = abs(result.added_mass_per_m - previous.added_mass_per_m) / max(
                abs(result.added_mass_per_m),
                1e-12,
            )
            damping_change = abs(result.damping_per_m - previous.damping_per_m) / max(
                abs(result.damping_per_m),
                1e-12,
            )
        rows.append(
            {
                "body_panel_count_requested": int(body_panel_count),
                "omega_rad_s": float(omega_rad_s),
                "added_mass_per_m": result.added_mass_per_m,
                "damping_per_m": result.damping_per_m,
                "added_mass_rel_change_from_previous": added_change,
                "damping_rel_change_from_previous": damping_change,
                "condition_number": result.condition_number,
                "residual_norm": result.residual_norm,
                "body_panel_count": result.panel_count,
                "free_surface_panel_count": result.free_surface_panel_count,
                "status": result.status,
            }
        )
        previous = result
    return rows
