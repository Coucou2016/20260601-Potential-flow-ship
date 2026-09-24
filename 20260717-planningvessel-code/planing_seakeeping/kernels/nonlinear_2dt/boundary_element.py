from __future__ import annotations

from dataclasses import dataclass

import numpy as np


NONLINEAR_2DT_BEM_CORE_STATUS = "sun_ch2_direct_bem_mixed_boundary_analytic_identity_validated"
NONLINEAR_2DT_PRESSURE_BVP_STATUS = "sun_ch2_auxiliary_pressure_bvp_free_surface_identity_validated"


@dataclass(frozen=True)
class ClosedBoundary2D:
    """Straight-panel closed boundary of a two-dimensional fluid domain.

    Coordinates use ``y`` horizontal and ``z`` positive upward. Nodes may be
    clockwise or counter-clockwise; panel normals are always constructed to
    point out of the polygon interior, which is the fluid domain.
    """

    node_y_m: np.ndarray
    node_z_up_m: np.ndarray
    panel_labels: tuple[str, ...]

    def __post_init__(self) -> None:
        y = np.asarray(self.node_y_m, dtype=float)
        z = np.asarray(self.node_z_up_m, dtype=float)
        if y.ndim != 1 or z.shape != y.shape or len(y) < 5:
            raise ValueError("A closed BEM boundary needs matching one-dimensional node arrays.")
        if not np.isfinite(y).all() or not np.isfinite(z).all():
            raise ValueError("BEM boundary coordinates must be finite.")
        scale = max(float(np.ptp(y)), float(np.ptp(z)), 1.0)
        if np.hypot(y[-1] - y[0], z[-1] - z[0]) > 1e-12 * scale:
            raise ValueError("BEM boundary nodes must explicitly close at the first node.")
        length = np.hypot(np.diff(y), np.diff(z))
        if np.any(length <= 1e-12 * scale):
            index = int(np.argmin(length))
            raise ValueError(
                "BEM boundary contains a zero-length panel: "
                f"panel={index}, length={length[index]:.9g}, "
                f"scale={scale:.9g}, max_abs_y={np.max(np.abs(y)):.9g}, "
                f"max_abs_z={np.max(np.abs(z)):.9g}, "
                f"start=({y[index]:.9g},{z[index]:.9g}), "
                f"end=({y[index + 1]:.9g},{z[index + 1]:.9g})."
            )
        if len(self.panel_labels) != len(length):
            raise ValueError("panel_labels must contain one label per boundary panel.")
        signed_area = 0.5 * float(np.sum(y[:-1] * z[1:] - y[1:] * z[:-1]))
        if abs(signed_area) <= 1e-12 * scale**2:
            raise ValueError("BEM boundary encloses a near-zero area.")
        object.__setattr__(self, "node_y_m", y)
        object.__setattr__(self, "node_z_up_m", z)
        object.__setattr__(self, "panel_labels", tuple(str(label) for label in self.panel_labels))

    @property
    def panel_count(self) -> int:
        return len(self.panel_labels)

    @property
    def signed_area_m2(self) -> float:
        y = self.node_y_m
        z = self.node_z_up_m
        return 0.5 * float(np.sum(y[:-1] * z[1:] - y[1:] * z[:-1]))

    @property
    def panel_length_m(self) -> np.ndarray:
        return np.hypot(np.diff(self.node_y_m), np.diff(self.node_z_up_m))

    @property
    def panel_mid_y_m(self) -> np.ndarray:
        return 0.5 * (self.node_y_m[:-1] + self.node_y_m[1:])

    @property
    def panel_mid_z_up_m(self) -> np.ndarray:
        return 0.5 * (self.node_z_up_m[:-1] + self.node_z_up_m[1:])

    @property
    def panel_tangent(self) -> np.ndarray:
        length = self.panel_length_m
        return np.column_stack((np.diff(self.node_y_m) / length, np.diff(self.node_z_up_m) / length))

    @property
    def panel_normal(self) -> np.ndarray:
        tangent = self.panel_tangent
        if self.signed_area_m2 > 0.0:
            return np.column_stack((tangent[:, 1], -tangent[:, 0]))
        return np.column_stack((-tangent[:, 1], tangent[:, 0]))

    @property
    def node_tangent(self) -> np.ndarray:
        tangent = self.panel_tangent
        weighted = (
            np.roll(self.panel_length_m, 1)[:, None] * np.roll(tangent, 1, axis=0)
            + self.panel_length_m[:, None] * tangent
        )
        norm = np.linalg.norm(weighted, axis=1)
        return weighted / np.maximum(norm[:, None], np.finfo(float).eps)

    @property
    def node_normal(self) -> np.ndarray:
        tangent = self.node_tangent
        if self.signed_area_m2 > 0.0:
            return np.column_stack((tangent[:, 1], -tangent[:, 0]))
        return np.column_stack((-tangent[:, 1], tangent[:, 0]))


@dataclass(frozen=True)
class MixedBoundarySolution:
    potential_m2_s: np.ndarray
    normal_derivative_m_s: np.ndarray
    condition_number: float
    relative_residual: float
    max_abs_residual: float
    dirichlet_panel_count: int
    neumann_panel_count: int
    gauss_order: int
    status: str = NONLINEAR_2DT_BEM_CORE_STATUS


@dataclass(frozen=True)
class MixedBoundaryOperator:
    h_matrix: np.ndarray
    g_matrix: np.ndarray
    system_matrix: np.ndarray
    dirichlet_mask: np.ndarray
    condition_number: float
    gauss_order: int


@dataclass(frozen=True)
class PressureAuxiliaryResult:
    auxiliary_solution: MixedBoundarySolution
    velocity_mps: np.ndarray
    potential_time_derivative_m2_s2: np.ndarray
    gauge_pressure_pa: np.ndarray
    free_surface_pressure_max_abs_pa: float
    body_vertical_force_per_length_n_m: float
    body_panel_count: int
    status: str = NONLINEAR_2DT_PRESSURE_BVP_STATUS

    def __post_init__(self) -> None:
        count = len(self.auxiliary_solution.potential_m2_s)
        velocity = np.asarray(self.velocity_mps, dtype=float)
        phi_t = np.asarray(self.potential_time_derivative_m2_s2, dtype=float)
        pressure = np.asarray(self.gauge_pressure_pa, dtype=float)
        if velocity.shape != (count, 2):
            raise ValueError("velocity_mps must have shape (n_panel, 2).")
        if phi_t.shape != (count,) or pressure.shape != (count,):
            raise ValueError("pressure auxiliary panel arrays must have shape (n_panel,).")
        if not np.isfinite(velocity).all() or not np.isfinite(phi_t).all() or not np.isfinite(pressure).all():
            raise ValueError("Pressure auxiliary results must be finite.")
        object.__setattr__(self, "velocity_mps", velocity)
        object.__setattr__(self, "potential_time_derivative_m2_s2", phi_t)
        object.__setattr__(self, "gauge_pressure_pa", pressure)


def constant_panel_influence_matrices(
    boundary: ClosedBoundary2D,
    *,
    gauss_order: int = 12,
) -> tuple[np.ndarray, np.ndarray]:
    """Return the ``H`` and ``G`` matrices in Sun (2007), Eq. (2.17).

    The implemented identity is ``H*phi-G*phi_n=0``. ``H`` contains the
    smooth-boundary ``-pi`` jump term. Both straight-panel kernels are
    integrated analytically. This is essential when two panels bound a thin
    spray sheet: fixed-order quadrature can miss the nearly singular normal
    kernel while still yielding a small residual for the discretized system.

    ``gauss_order`` is retained as a validated compatibility argument because
    callers share configuration with the linear-element solvers.
    """

    order = int(gauss_order)
    if order < 4:
        raise ValueError("gauss_order must be at least four.")
    field_y = boundary.panel_mid_y_m[:, None]
    field_z = boundary.panel_mid_z_up_m[:, None]
    tangent = boundary.panel_tangent
    normal = boundary.panel_normal
    y0 = boundary.node_y_m[:-1][None, :]
    z0 = boundary.node_z_up_m[:-1][None, :]
    length = boundary.panel_length_m
    relative_y = field_y - y0
    relative_z = field_z - z0
    local_tangent = (
        relative_y * tangent[None, :, 0]
        + relative_z * tangent[None, :, 1]
    )
    local_normal = (
        relative_y * normal[None, :, 0]
        + relative_z * normal[None, :, 1]
    )
    lower = -local_tangent
    upper = length[None, :] - local_tangent
    absolute_normal = np.abs(local_normal)

    def logarithmic_primitive(coordinate: np.ndarray) -> np.ndarray:
        radius_squared = np.maximum(
            coordinate**2 + local_normal**2,
            np.finfo(float).tiny,
        )
        return (
            0.5 * coordinate * np.log(radius_squared)
            - coordinate
            + absolute_normal * np.arctan2(coordinate, absolute_normal)
        )

    g_matrix = logarithmic_primitive(upper) - logarithmic_primitive(lower)
    h_matrix = np.zeros_like(g_matrix)
    non_collinear = absolute_normal > 64.0 * np.finfo(float).eps * np.maximum(
        1.0,
        length[None, :],
    )
    normal_sign = np.sign(local_normal)
    lower_angle = np.arctan2(lower * normal_sign, absolute_normal)
    upper_angle = np.arctan2(upper * normal_sign, absolute_normal)
    h_matrix[non_collinear] = (
        lower_angle[non_collinear] - upper_angle[non_collinear]
    )

    np.fill_diagonal(h_matrix, -np.pi)
    self_integral = length * (np.log(np.maximum(0.5 * length, np.finfo(float).tiny)) - 1.0)
    np.fill_diagonal(g_matrix, self_integral)
    return h_matrix, g_matrix


def _linear_panel_endpoint_influence_arrays_at_points(
    boundary: ClosedBoundary2D,
    field_y: np.ndarray,
    field_z: np.ndarray,
    *,
    gauss_order: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return exact linear shape-function influences at arbitrary field points.

    Rows are field points and columns are source panels. The arrays contain the
    left and right endpoint contributions before nodal assembly.
    """

    order = int(gauss_order)
    if order < 4:
        raise ValueError("gauss_order must be at least four.")
    field_y = np.asarray(field_y, dtype=float)
    field_z = np.asarray(field_z, dtype=float)
    if field_y.ndim != 1 or field_z.shape != field_y.shape:
        raise ValueError("Linear influence field coordinates must be matching vectors.")
    if not np.isfinite(field_y).all() or not np.isfinite(field_z).all():
        raise ValueError("Linear influence field coordinates must be finite.")
    y0 = boundary.node_y_m[:-1]
    z0 = boundary.node_z_up_m[:-1]
    tangent = boundary.panel_tangent
    normal = boundary.panel_normal
    length = boundary.panel_length_m
    count = boundary.panel_count
    field_count = len(field_y)
    h_left_all = np.zeros((field_count, count), dtype=float)
    h_right_all = np.zeros((field_count, count), dtype=float)
    g_left_all = np.zeros((field_count, count), dtype=float)
    g_right_all = np.zeros((field_count, count), dtype=float)
    tiny = np.finfo(float).tiny
    epsilon = np.finfo(float).eps

    for source in range(count):
        panel_length = float(length[source])
        relative_y = field_y - y0[source]
        relative_z = field_z - z0[source]
        field_tangent = (
            relative_y * tangent[source, 0]
            + relative_z * tangent[source, 1]
        )
        field_normal = (
            relative_y * normal[source, 0]
            + relative_z * normal[source, 1]
        )
        lower = -field_tangent
        upper = panel_length - field_tangent
        absolute_normal = np.abs(field_normal)

        def logarithmic_primitive(coordinate: np.ndarray) -> np.ndarray:
            radius_squared = coordinate**2 + field_normal**2
            logarithm = np.log(np.maximum(radius_squared, tiny))
            return (
                0.5 * coordinate * logarithm
                - coordinate
                + absolute_normal * np.arctan2(coordinate, absolute_normal)
            )

        def first_moment_primitive(coordinate: np.ndarray) -> np.ndarray:
            radius_squared = coordinate**2 + field_normal**2
            return np.where(
                radius_squared > tiny,
                0.25
                * radius_squared
                * (np.log(np.maximum(radius_squared, tiny)) - 1.0),
                0.0,
            )

        integral_g = logarithmic_primitive(upper) - logarithmic_primitive(lower)
        first_moment_g = (
            first_moment_primitive(upper)
            - first_moment_primitive(lower)
            + field_tangent * integral_g
        )
        g_right_all[:, source] = first_moment_g / panel_length
        g_left_all[:, source] = integral_g - g_right_all[:, source]

        non_collinear = absolute_normal > 64.0 * epsilon * max(1.0, panel_length)
        sign_normal = np.sign(field_normal)
        h_primitive_lower = -sign_normal * np.arctan2(lower, absolute_normal)
        h_primitive_upper = -sign_normal * np.arctan2(upper, absolute_normal)
        integral_h = h_primitive_upper - h_primitive_lower
        logarithm_lower = np.log(np.maximum(lower**2 + field_normal**2, tiny))
        logarithm_upper = np.log(np.maximum(upper**2 + field_normal**2, tiny))
        first_moment_h = (
            -0.5 * field_normal * (logarithm_upper - logarithm_lower)
            + field_tangent * integral_h
        )
        h_right = first_moment_h / panel_length
        h_left = integral_h - h_right
        h_left_all[non_collinear, source] = h_left[non_collinear]
        h_right_all[non_collinear, source] = h_right[non_collinear]

    return h_left_all, h_right_all, g_left_all, g_right_all


def _linear_panel_endpoint_influence_arrays(
    boundary: ClosedBoundary2D,
    *,
    gauss_order: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return endpoint influences collocated at the boundary nodes."""

    return _linear_panel_endpoint_influence_arrays_at_points(
        boundary,
        boundary.node_y_m[:-1],
        boundary.node_z_up_m[:-1],
        gauss_order=gauss_order,
    )


def linear_node_influence_matrices(
    boundary: ClosedBoundary2D,
    *,
    gauss_order: int = 12,
) -> tuple[np.ndarray, np.ndarray]:
    """Return Sun Eq. (2.17) matrices for continuous linear nodal elements."""

    h_left, h_right, g_left, g_right = _linear_panel_endpoint_influence_arrays(
        boundary,
        gauss_order=gauss_order,
    )
    count = boundary.panel_count
    h_matrix = np.zeros((count, count), dtype=float)
    g_matrix = np.zeros((count, count), dtype=float)
    for source in range(count):
        right_node = (source + 1) % count
        h_matrix[:, source] += h_left[:, source]
        h_matrix[:, right_node] += h_right[:, source]
        g_matrix[:, source] += g_left[:, source]
        g_matrix[:, right_node] += g_right[:, source]

    np.fill_diagonal(h_matrix, 0.0)
    np.fill_diagonal(h_matrix, -np.sum(h_matrix, axis=1))
    return h_matrix, g_matrix


def solve_linear_node_mixed_boundary_laplace(
    boundary: ClosedBoundary2D,
    *,
    dirichlet_mask: np.ndarray,
    known_value: np.ndarray,
    gauss_order: int = 12,
) -> MixedBoundarySolution:
    """Solve a mixed BVP using Sun Eq. (2.16) continuous linear elements."""

    count = boundary.panel_count
    mask = np.asarray(dirichlet_mask, dtype=bool)
    known = np.asarray(known_value, dtype=float)
    if mask.shape != (count,) or known.shape != (count,):
        raise ValueError("Linear nodal masks and values require one entry per unique node.")
    if not np.any(mask):
        raise ValueError("At least one Dirichlet node is required to fix the potential datum.")
    if not np.isfinite(known).all():
        raise ValueError("known_value must be finite.")
    h_matrix, g_matrix = linear_node_influence_matrices(
        boundary,
        gauss_order=gauss_order,
    )
    system = np.where(mask[None, :], -g_matrix, h_matrix)
    rhs = -(h_matrix[:, mask] @ known[mask])
    rhs += g_matrix[:, ~mask] @ known[~mask]
    try:
        unknown = np.linalg.solve(system, rhs)
    except np.linalg.LinAlgError:
        unknown, _, rank, _ = np.linalg.lstsq(system, rhs, rcond=1e-12)
        if rank < count:
            raise ValueError("Linear nodal mixed BEM system is rank deficient.")
    potential = np.where(mask, known, unknown)
    normal_derivative = np.where(mask, unknown, known)
    identity_residual = h_matrix @ potential - g_matrix @ normal_derivative
    scale = max(
        float(np.linalg.norm(h_matrix @ potential)),
        float(np.linalg.norm(g_matrix @ normal_derivative)),
        1e-12,
    )
    return MixedBoundarySolution(
        potential_m2_s=potential,
        normal_derivative_m_s=normal_derivative,
        condition_number=float(np.linalg.cond(system)),
        relative_residual=float(np.linalg.norm(identity_residual) / scale),
        max_abs_residual=float(np.max(np.abs(identity_residual))),
        dirichlet_panel_count=int(np.count_nonzero(mask)),
        neumann_panel_count=int(np.count_nonzero(~mask)),
        gauss_order=int(gauss_order),
        status="sun_ch2_linear_nodal_bem_mixed_boundary",
    )


def _linear_element_endpoint_influence_matrices(
    boundary: ClosedBoundary2D,
    *,
    gauss_order: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return aggregated H and per-element endpoint G contributions."""

    length = boundary.panel_length_m
    count = boundary.panel_count
    h_left_all, h_right_all, g_left_all, g_right_all = (
        _linear_panel_endpoint_influence_arrays(
            boundary,
            gauss_order=gauss_order,
        )
    )
    h_matrix = np.zeros((count, count), dtype=float)

    for source in range(count):
        right_node = (source + 1) % count
        h_matrix[:, source] += h_left_all[:, source]
        h_matrix[:, right_node] += h_right_all[:, source]

    np.fill_diagonal(h_matrix, 0.0)
    np.fill_diagonal(h_matrix, -np.sum(h_matrix, axis=1))
    g_matrix = np.zeros_like(h_matrix)
    for source in range(count):
        g_matrix[:, source] += g_left_all[:, source]
        g_matrix[:, (source + 1) % count] += g_right_all[:, source]
    return h_matrix, g_matrix, g_left_all, g_right_all, length


def linear_element_influence_components(
    boundary: ClosedBoundary2D,
    *,
    gauss_order: int = 12,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Expose continuous-linear H and endpoint G terms for augmented BVPs."""

    h_matrix, _, g_left, g_right, length = (
        _linear_element_endpoint_influence_matrices(
            boundary,
            gauss_order=gauss_order,
        )
    )
    return h_matrix, g_left, g_right, length


def linear_element_influence_rows(
    boundary: ClosedBoundary2D,
    *,
    field_y_m: np.ndarray,
    field_z_up_m: np.ndarray,
    field_panel_index: np.ndarray,
    field_panel_fraction: np.ndarray,
    gauss_order: int = 12,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return linear-element BIE rows collocated inside boundary panels.

    The field point on each declared panel is represented by its local linear
    coordinate. The jump coefficient is distributed to that panel's endpoint
    potential shape functions so every row preserves the constant-potential
    identity. This supports displaced double-node treatment at geometric
    corners without moving the actual boundary geometry.
    """

    panel_index = np.asarray(field_panel_index, dtype=int)
    fraction = np.asarray(field_panel_fraction, dtype=float)
    field_y = np.asarray(field_y_m, dtype=float)
    field_z = np.asarray(field_z_up_m, dtype=float)
    if not (
        panel_index.shape == fraction.shape == field_y.shape == field_z.shape
    ) or panel_index.ndim != 1:
        raise ValueError("Displaced linear collocation inputs must be matching vectors.")
    if (
        np.any(panel_index < 0)
        or np.any(panel_index >= boundary.panel_count)
        or not np.isfinite(fraction).all()
        or np.any(fraction <= 0.0)
        or np.any(fraction >= 1.0)
    ):
        raise ValueError(
            "Displaced linear collocation requires interior panel fractions."
        )
    h_left, h_right, g_left, g_right = (
        _linear_panel_endpoint_influence_arrays_at_points(
            boundary,
            field_y,
            field_z,
            gauss_order=gauss_order,
        )
    )
    row_count = len(field_y)
    h_matrix = np.zeros((row_count, boundary.panel_count), dtype=float)
    for source in range(boundary.panel_count):
        h_matrix[:, source] += h_left[:, source]
        h_matrix[:, (source + 1) % boundary.panel_count] += h_right[:, source]
    jump = -np.sum(h_matrix, axis=1)
    for row, (panel, coordinate) in enumerate(zip(panel_index, fraction)):
        h_matrix[row, panel] += jump[row] * (1.0 - coordinate)
        h_matrix[row, (panel + 1) % boundary.panel_count] += (
            jump[row] * coordinate
        )
    return h_matrix, g_left, g_right


def solve_linear_element_mixed_boundary_laplace(
    boundary: ClosedBoundary2D,
    *,
    dirichlet_panel_mask: np.ndarray,
    dirichlet_node_values: np.ndarray,
    neumann_endpoint_values: np.ndarray,
    gauss_order: int = 12,
) -> MixedBoundarySolution:
    """Solve Eq. (2.20) while retaining discontinuous normal data at corners."""

    count = boundary.panel_count
    panel_mask = np.asarray(dirichlet_panel_mask, dtype=bool)
    phi_known = np.asarray(dirichlet_node_values, dtype=float)
    q_known = np.asarray(neumann_endpoint_values, dtype=float)
    if panel_mask.shape != (count,):
        raise ValueError("dirichlet_panel_mask must contain one value per panel.")
    if phi_known.shape != (count,) or q_known.shape != (count, 2):
        raise ValueError("Linear element data require node phi and two endpoint q values per panel.")
    if not np.any(panel_mask) or not np.isfinite(phi_known).all() or not np.isfinite(q_known).all():
        raise ValueError("Linear element mixed BVP needs finite data and Dirichlet panels.")
    h_matrix, _, g_left, g_right, length = _linear_element_endpoint_influence_matrices(
        boundary,
        gauss_order=gauss_order,
    )
    node_dirichlet = np.zeros(count, dtype=bool)
    for panel in np.flatnonzero(panel_mask):
        node_dirichlet[panel] = True
        node_dirichlet[(panel + 1) % count] = True

    system = np.zeros((count, count), dtype=float)
    rhs = np.zeros(count, dtype=float)
    for node in range(count):
        if node_dirichlet[node]:
            column = np.zeros(count, dtype=float)
            previous_panel = (node - 1) % count
            if panel_mask[previous_panel]:
                column += g_right[:, previous_panel]
            if panel_mask[node]:
                column += g_left[:, node]
            system[:, node] = -column
            rhs -= h_matrix[:, node] * phi_known[node]
        else:
            system[:, node] = h_matrix[:, node]
    for panel in np.flatnonzero(~panel_mask):
        rhs += g_left[:, panel] * q_known[panel, 0]
        rhs += g_right[:, panel] * q_known[panel, 1]

    try:
        unknown = np.linalg.solve(system, rhs)
    except np.linalg.LinAlgError:
        unknown, _, rank, _ = np.linalg.lstsq(system, rhs, rcond=1e-12)
        if rank < count:
            raise ValueError("Linear element mixed BEM system is rank deficient.")
    potential = np.where(node_dirichlet, phi_known, unknown)
    q_nodes = np.zeros(count, dtype=float)
    q_weight = np.zeros(count, dtype=float)
    q_nodes[node_dirichlet] = unknown[node_dirichlet]
    for panel in np.flatnonzero(~panel_mask):
        for endpoint, node in ((0, panel), (1, (panel + 1) % count)):
            if not node_dirichlet[node]:
                q_nodes[node] += length[panel] * q_known[panel, endpoint]
                q_weight[node] += length[panel]
    q_nodes[~node_dirichlet] /= np.maximum(
        q_weight[~node_dirichlet],
        np.finfo(float).eps,
    )

    integral_q = np.zeros(count, dtype=float)
    for panel in range(count):
        if panel_mask[panel]:
            q_left = unknown[panel]
            q_right = unknown[(panel + 1) % count]
        else:
            q_left, q_right = q_known[panel]
        integral_q += g_left[:, panel] * q_left + g_right[:, panel] * q_right
    identity_residual = h_matrix @ potential - integral_q
    scale = max(float(np.linalg.norm(h_matrix @ potential)), float(np.linalg.norm(integral_q)), 1e-12)
    return MixedBoundarySolution(
        potential_m2_s=potential,
        normal_derivative_m_s=q_nodes,
        condition_number=float(np.linalg.cond(system)),
        relative_residual=float(np.linalg.norm(identity_residual) / scale),
        max_abs_residual=float(np.max(np.abs(identity_residual))),
        dirichlet_panel_count=int(np.count_nonzero(panel_mask)),
        neumann_panel_count=int(np.count_nonzero(~panel_mask)),
        gauss_order=int(gauss_order),
        status="sun_ch2_linear_element_mixed_corner_discontinuous_normal",
    )
def boundary_node_tangential_derivative(
    boundary: ClosedBoundary2D,
    node_values: np.ndarray,
) -> np.ndarray:
    values = np.asarray(node_values, dtype=float)
    if values.shape != (boundary.panel_count,) or not np.isfinite(values).all():
        raise ValueError("node_values must be finite with one value per unique node.")
    next_length = boundary.panel_length_m
    previous_length = np.roll(next_length, 1)
    forward = (np.roll(values, -1) - values) / next_length
    backward = (values - np.roll(values, 1)) / previous_length
    return (
        previous_length * forward + next_length * backward
    ) / (previous_length + next_length)


def boundary_node_velocity(
    boundary: ClosedBoundary2D,
    solution: MixedBoundarySolution,
) -> np.ndarray:
    tangential = boundary_node_tangential_derivative(
        boundary,
        solution.potential_m2_s,
    )
    return (
        tangential[:, None] * boundary.node_tangent
        + solution.normal_derivative_m_s[:, None] * boundary.node_normal
    )


def solve_mixed_boundary_laplace(
    boundary: ClosedBoundary2D,
    *,
    dirichlet_mask: np.ndarray,
    known_value: np.ndarray,
    gauss_order: int = 12,
    operator: MixedBoundaryOperator | None = None,
) -> MixedBoundarySolution:
    """Solve a mixed Dirichlet--Neumann Laplace boundary-value problem.

    ``known_value`` stores potential on Dirichlet panels and outward normal
    derivative on Neumann panels. At least one Dirichlet panel is required to
    fix the potential datum.
    """

    mask = np.asarray(dirichlet_mask, dtype=bool)
    known = np.asarray(known_value, dtype=float)
    if mask.shape != (boundary.panel_count,) or known.shape != mask.shape:
        raise ValueError("dirichlet_mask and known_value must contain one value per panel.")
    if not np.isfinite(known).all():
        raise ValueError("known_value must be finite.")
    if not np.any(mask):
        raise ValueError("At least one Dirichlet panel is required to fix the potential datum.")
    if operator is None:
        operator = build_mixed_boundary_operator(
            boundary,
            dirichlet_mask=mask,
            gauss_order=gauss_order,
        )
    elif (
        operator.system_matrix.shape != (boundary.panel_count, boundary.panel_count)
        or not np.array_equal(operator.dirichlet_mask, mask)
        or int(operator.gauss_order) != int(gauss_order)
    ):
        raise ValueError("MixedBoundaryOperator does not match the boundary problem.")
    h_matrix = operator.h_matrix
    g_matrix = operator.g_matrix
    system = operator.system_matrix
    rhs = -(h_matrix[:, mask] @ known[mask])
    rhs += g_matrix[:, ~mask] @ known[~mask]
    try:
        unknown = np.linalg.solve(system, rhs)
    except np.linalg.LinAlgError:
        unknown, _, rank, _ = np.linalg.lstsq(system, rhs, rcond=1e-12)
        if rank < boundary.panel_count:
            raise ValueError("Mixed boundary BEM system is rank deficient.")
    potential = np.where(mask, known, unknown)
    normal_derivative = np.where(mask, unknown, known)
    identity_residual = h_matrix @ potential - g_matrix @ normal_derivative
    scale = max(
        float(np.linalg.norm(h_matrix @ potential)),
        float(np.linalg.norm(g_matrix @ normal_derivative)),
        1e-12,
    )
    return MixedBoundarySolution(
        potential_m2_s=potential,
        normal_derivative_m_s=normal_derivative,
        condition_number=float(operator.condition_number),
        relative_residual=float(np.linalg.norm(identity_residual) / scale),
        max_abs_residual=float(np.max(np.abs(identity_residual))),
        dirichlet_panel_count=int(np.count_nonzero(mask)),
        neumann_panel_count=int(np.count_nonzero(~mask)),
        gauss_order=int(gauss_order),
    )


def build_mixed_boundary_operator(
    boundary: ClosedBoundary2D,
    *,
    dirichlet_mask: np.ndarray,
    gauss_order: int = 12,
) -> MixedBoundaryOperator:
    """Assemble the reusable mixed-BVP operator for one instantaneous boundary."""

    mask = np.asarray(dirichlet_mask, dtype=bool)
    if mask.shape != (boundary.panel_count,):
        raise ValueError("dirichlet_mask must contain one value per panel.")
    if not np.any(mask):
        raise ValueError("At least one Dirichlet panel is required to fix the potential datum.")
    h_matrix, g_matrix = constant_panel_influence_matrices(
        boundary,
        gauss_order=gauss_order,
    )
    system = np.where(mask[None, :], -g_matrix, h_matrix)
    return MixedBoundaryOperator(
        h_matrix=h_matrix,
        g_matrix=g_matrix,
        system_matrix=system,
        dirichlet_mask=mask.copy(),
        condition_number=float(np.linalg.cond(system)),
        gauss_order=int(gauss_order),
    )


def boundary_tangential_derivative(
    boundary: ClosedBoundary2D,
    panel_values: np.ndarray,
) -> np.ndarray:
    """Return a periodic second-order arc-length derivative at panel midpoints."""

    values = np.asarray(panel_values, dtype=float)
    if values.shape != (boundary.panel_count,) or not np.isfinite(values).all():
        raise ValueError("panel_values must be finite with one value per panel.")
    length = boundary.panel_length_m
    distance_to_next = 0.5 * (length + np.roll(length, -1))
    distance_to_previous = 0.5 * (length + np.roll(length, 1))
    forward = (np.roll(values, -1) - values) / distance_to_next
    backward = (values - np.roll(values, 1)) / distance_to_previous
    return (
        distance_to_previous * forward + distance_to_next * backward
    ) / (distance_to_previous + distance_to_next)


def boundary_segment_tangential_derivative(
    boundary: ClosedBoundary2D,
    panel_values: np.ndarray,
) -> np.ndarray:
    """Differentiate within continuous boundary-condition segments only."""

    values = np.asarray(panel_values, dtype=float)
    if values.shape != (boundary.panel_count,) or not np.isfinite(values).all():
        raise ValueError("panel_values must be finite with one value per panel.")
    groups = np.asarray(
        ["body" if label in ("body", "artificial_body") else label for label in boundary.panel_labels],
        dtype=object,
    )
    length = boundary.panel_length_m
    midpoint_s = np.cumsum(length) - 0.5 * length
    derivative = np.zeros(boundary.panel_count, dtype=float)
    start = 0
    while start < boundary.panel_count:
        stop = start + 1
        while stop < boundary.panel_count and groups[stop] == groups[start]:
            stop += 1
        segment_length = stop - start
        if segment_length == 2:
            slope = (values[stop - 1] - values[start]) / (
                midpoint_s[stop - 1] - midpoint_s[start]
            )
            derivative[start:stop] = slope
        elif segment_length >= 3:
            derivative[start:stop] = np.gradient(
                values[start:stop],
                midpoint_s[start:stop],
                edge_order=2,
            )
        start = stop
    return derivative


def boundary_velocity(
    boundary: ClosedBoundary2D,
    solution: MixedBoundarySolution,
    *,
    respect_label_boundaries: bool = False,
) -> np.ndarray:
    """Reconstruct ``grad(phi)`` from tangential and normal derivatives."""

    tangential = (
        boundary_segment_tangential_derivative(boundary, solution.potential_m2_s)
        if respect_label_boundaries
        else boundary_tangential_derivative(boundary, solution.potential_m2_s)
    )
    return (
        tangential[:, None] * boundary.panel_tangent
        + solution.normal_derivative_m_s[:, None] * boundary.panel_normal
    )


def solve_section_potential_bvp(
    boundary: ClosedBoundary2D,
    *,
    free_surface_potential_m2_s: np.ndarray,
    body_normal_velocity_mps: np.ndarray,
    gauss_order: int = 12,
    operator: MixedBoundaryOperator | None = None,
) -> MixedBoundarySolution:
    """Solve Sun (2007), Eqs. (2.1)-(2.6), for one cross-plane state.

    Panels labelled ``free_surface`` use the supplied Dirichlet potential;
    panels labelled ``body`` use the supplied outward-normal velocity. Other
    panels are impermeable truncation or bottom boundaries.
    """

    labels = np.asarray(boundary.panel_labels, dtype=object)
    free_mask = labels == "free_surface"
    body_mask = (labels == "body") | (labels == "artificial_body")
    free_values = np.asarray(free_surface_potential_m2_s, dtype=float)
    body_values = np.asarray(body_normal_velocity_mps, dtype=float)
    if free_values.shape != (int(np.count_nonzero(free_mask)),):
        raise ValueError("free_surface_potential_m2_s must contain one value per free-surface panel.")
    if body_values.shape != (int(np.count_nonzero(body_mask)),):
        raise ValueError("body_normal_velocity_mps must contain one value per body panel.")
    known = np.zeros(boundary.panel_count, dtype=float)
    known[free_mask] = free_values
    known[body_mask] = body_values
    return solve_mixed_boundary_laplace(
        boundary,
        dirichlet_mask=free_mask,
        known_value=known,
        gauss_order=gauss_order,
        operator=operator,
    )


def solve_pressure_auxiliary_bvp(
    boundary: ClosedBoundary2D,
    potential_solution: MixedBoundarySolution,
    *,
    body_velocity_yz_mps: tuple[float, float],
    body_acceleration_normal_mps2: np.ndarray,
    rho_water_kg_m3: float = 1025.0,
    gravity_m_s2: float = 9.80665,
    gauss_order: int = 12,
    operator: MixedBoundaryOperator | None = None,
    incident_vertical_velocity_mps: np.ndarray | None = None,
    incident_potential_time_derivative_m2_s2: np.ndarray | None = None,
) -> PressureAuxiliaryResult:
    """Solve Sun (2007), Eqs. (2.8)-(2.11), and recover pressure.

    The auxiliary function is ``psi=phi_t+V dot grad(phi)``. Its free-surface
    Dirichlet value follows the fully nonlinear dynamic condition, and its
    body Neumann value is the prescribed normal acceleration. Pressure follows
    Bernoulli Eq. (2.7). Atmospheric pressure is the zero gauge datum. Optional
    incident-wave arrays implement Sun--Faltinsen Eqs. (7), (16), and (18):
    ``phi_I,z`` enters the free-surface auxiliary datum and the pressure cross
    term, while ``phi_I,t`` enters both with the signs required for exactly zero
    gauge pressure on the instantaneous free surface.
    """

    rho = float(rho_water_kg_m3)
    gravity = float(gravity_m_s2)
    if rho <= 0.0 or gravity <= 0.0:
        raise ValueError("rho_water_kg_m3 and gravity_m_s2 must be positive.")
    if len(potential_solution.potential_m2_s) != boundary.panel_count:
        raise ValueError("potential_solution does not match boundary panel count.")
    labels = np.asarray(boundary.panel_labels, dtype=object)
    free_mask = labels == "free_surface"
    body_mask = (labels == "body") | (labels == "artificial_body")
    physical_body_mask = labels == "body"
    acceleration = np.asarray(body_acceleration_normal_mps2, dtype=float)
    if acceleration.shape != (int(np.count_nonzero(body_mask)),) or not np.isfinite(acceleration).all():
        raise ValueError("body_acceleration_normal_mps2 must be finite with one value per body panel.")
    body_velocity = np.asarray(body_velocity_yz_mps, dtype=float)
    if body_velocity.shape != (2,) or not np.isfinite(body_velocity).all():
        raise ValueError("body_velocity_yz_mps must contain finite y and z-up components.")

    incident_vertical_velocity = (
        np.zeros(boundary.panel_count, dtype=float)
        if incident_vertical_velocity_mps is None
        else np.asarray(incident_vertical_velocity_mps, dtype=float)
    )
    incident_potential_time_derivative = (
        np.zeros(boundary.panel_count, dtype=float)
        if incident_potential_time_derivative_m2_s2 is None
        else np.asarray(incident_potential_time_derivative_m2_s2, dtype=float)
    )
    for name, values in (
        ("incident_vertical_velocity_mps", incident_vertical_velocity),
        (
            "incident_potential_time_derivative_m2_s2",
            incident_potential_time_derivative,
        ),
    ):
        if values.shape != (boundary.panel_count,) or not np.isfinite(values).all():
            raise ValueError(f"{name} must be finite with one value per boundary panel.")

    velocity = boundary_velocity(
        boundary,
        potential_solution,
        respect_label_boundaries=True,
    )
    speed_squared = np.sum(velocity**2, axis=1)
    body_advection = velocity @ body_velocity
    known = np.zeros(boundary.panel_count, dtype=float)
    known[free_mask] = (
        body_advection[free_mask]
        - incident_vertical_velocity[free_mask] * velocity[free_mask, 1]
        - 0.5 * speed_squared[free_mask]
        - incident_potential_time_derivative[free_mask]
        - gravity * boundary.panel_mid_z_up_m[free_mask]
    )
    known[body_mask] = acceleration
    auxiliary = solve_mixed_boundary_laplace(
        boundary,
        dirichlet_mask=free_mask,
        known_value=known,
        gauss_order=gauss_order,
        operator=operator,
    )
    phi_t = auxiliary.potential_m2_s - body_advection
    pressure = -rho * (
        gravity * boundary.panel_mid_z_up_m
        + phi_t
        + 0.5 * speed_squared
        + incident_vertical_velocity * velocity[:, 1]
        + incident_potential_time_derivative
    )
    free_pressure = pressure[free_mask]
    normal_z = boundary.panel_normal[:, 1]
    body_vertical_force = float(
        np.sum(
            pressure[physical_body_mask]
            * normal_z[physical_body_mask]
            * boundary.panel_length_m[physical_body_mask]
        )
    )
    return PressureAuxiliaryResult(
        auxiliary_solution=auxiliary,
        velocity_mps=velocity,
        potential_time_derivative_m2_s2=phi_t,
        gauge_pressure_pa=pressure,
        free_surface_pressure_max_abs_pa=(float(np.max(np.abs(free_pressure))) if free_pressure.size else 0.0),
        body_vertical_force_per_length_n_m=body_vertical_force,
        body_panel_count=int(np.count_nonzero(physical_body_mask)),
    )
