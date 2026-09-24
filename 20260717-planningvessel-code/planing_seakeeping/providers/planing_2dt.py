from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..kernels.nonlinear_2dt.prescribed_motion import (
    PrescribedMotion2DtCase,
    PrescribedMotion2DtResult,
    PrescribedMotionSectionSolver,
    solve_prescribed_motion_case,
)
from ..kernels.nonlinear_2dt.moving_wedge import MovingWedgeConfig
from ..kernels.nonlinear_2dt.planing_forced_motion import (
    IdentifiedPlaningIncidentWaveExcitation,
    IdentifiedPlaningForcedMotionColumn,
    PlaningForcedMotionCase,
    identify_planing_forced_motion_column,
    identify_planing_incident_wave_excitation,
    run_planing_forced_motion_2dt,
)
from ..schema import Nonlinear2DtProviderConfig
from ..types import HydroLoadResult, ModelCapabilities


@dataclass(frozen=True)
class ReducedOrderPlaningLoadProvider:
    """Reduced-order Savitsky/Faltinsen load provider.

    This is the renamed form of the earlier `ReducedOrderPlaning2DtProvider`.
    It deliberately avoids the `2Dt` name so users do not confuse it with the
    future Sun-Faltinsen fully nonlinear free-surface BEM.
    """

    production: bool = False

    @property
    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            frequency_domain=True,
            time_domain=True,
            six_dof=False,
            nonlinear_free_surface=False,
            instantaneous_wetted_surface=False,
            production=self.production,
            status="reduced_order_planing_load_provider",
            validated_benchmarks=("faltinsen_ch9_prescribed_state",),
            assumptions=(
                "Head-sea longitudinal heave/pitch is the trusted response surface.",
                "Planing loads are reduced-order Savitsky/Faltinsen loads, not Sun-Faltinsen 2D+t BEM.",
            ),
        )

    def zero_load(self) -> HydroLoadResult:
        return HydroLoadResult.zeros("Reduced-order provider placeholder call returned no incremental load.")


class ReducedOrderPlaning2DtProvider(ReducedOrderPlaningLoadProvider):
    """Backward-compatible alias for old configs.

    New code should import `ReducedOrderPlaningLoadProvider`.
    """


@dataclass(frozen=True)
class NonlinearBEM2DtProvider:
    """Sun-Faltinsen-style nonlinear 2D+t provider contract."""

    config: Nonlinear2DtProviderConfig = Nonlinear2DtProviderConfig()

    @property
    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            time_domain=True,
            six_dof=False,
            nonlinear_free_surface=True,
            instantaneous_wetted_surface=True,
            production=False,
            status="sun_faltinsen_ground_plane_forced_motion_and_direct_wave_validation_pending",
            assumptions=(
                "Lagrangian free-surface BEM, pressure auxiliary BVP, artificial hard-chine separation, remeshing, and moving ground planes are implemented.",
                "Wagner initialization, thin-jet cutting, foremost-part force, and an optional transom 3D correction are implemented and separately reported.",
                "Direct regular head-wave terms are implemented in the body, free-surface, pressure, wet-length, and foremost-force equations.",
                "Spray-sheet cutting, direct-wave convergence/experiment acceptance, and free-running motion coupling remain pending.",
                "Must pass wedge-entry, V-column, Fridsma, and Katayama benchmarks before production use.",
            ),
        )

    def validate_for_run(self) -> None:
        self.config.validate()

    def simulate_prescribed_motion(
        self,
        case: PrescribedMotion2DtCase,
        section_solver: PrescribedMotionSectionSolver,
        *,
        restoring_column: np.ndarray,
        discard_cycles: float = 1.0,
        retained_cycles: float | None = None,
        fitted_harmonics: int = 3,
    ) -> PrescribedMotion2DtResult:
        """Run forced-motion orchestration with an explicit section solver.

        No default section solver is selected until the nonlinear free-surface
        and pressure BVP kernel passes its component benchmarks.
        """

        self.validate_for_run()
        return solve_prescribed_motion_case(
            case,
            section_solver,
            restoring_column=np.asarray(restoring_column, dtype=float),
            discard_cycles=discard_cycles,
            retained_cycles=retained_cycles,
            fitted_harmonics=fitted_harmonics,
        )

    def simulate_planing_forced_motion(
        self,
        wedge_config: MovingWedgeConfig,
        case: PlaningForcedMotionCase,
        *,
        restoring_column: np.ndarray,
        discard_cycles: float = 1.0,
        retained_cycles: float | None = None,
        fitted_harmonics: int = 3,
        parallel_workers: int = 1,
    ) -> IdentifiedPlaningForcedMotionColumn:
        """Run the internal ground-plane free-surface BEM for one matrix column."""

        self.validate_for_run()
        simulation = run_planing_forced_motion_2dt(
            wedge_config,
            case,
            parallel_workers=parallel_workers,
        )
        return identify_planing_forced_motion_column(
            simulation,
            case,
            restoring_column=np.asarray(restoring_column, dtype=float),
            discard_cycles=discard_cycles,
            retained_cycles=retained_cycles,
            fitted_harmonics=fitted_harmonics,
        )

    def simulate_planing_incident_wave(
        self,
        wedge_config: MovingWedgeConfig,
        case: PlaningForcedMotionCase,
        *,
        discard_cycles: float = 1.0,
        retained_cycles: float | None = None,
        fitted_harmonics: int = 3,
        parallel_workers: int = 1,
    ) -> IdentifiedPlaningIncidentWaveExcitation:
        """Run direct regular-wave 2D+t excitation on a fixed hull."""

        self.validate_for_run()
        simulation = run_planing_forced_motion_2dt(
            wedge_config,
            case,
            parallel_workers=parallel_workers,
        )
        return identify_planing_incident_wave_excitation(
            simulation,
            case,
            discard_cycles=discard_cycles,
            retained_cycles=retained_cycles,
            fitted_harmonics=fitted_harmonics,
        )

    def simulate(self, *args, **kwargs):
        self.validate_for_run()
        raise NotImplementedError(
            "Free-running NonlinearBEM2DtProvider simulation is not implemented. "
            "Use simulate_planing_forced_motion for the internal ground-plane BEM or "
            "simulate_planing_incident_wave for direct fixed-hull wave excitation, or "
            "simulate_prescribed_motion with an explicit section solver while Troesch "
            "validation and free-running coupling remain pending."
        )
