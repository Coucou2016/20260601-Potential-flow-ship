// This public member function belongs to the FreeSurface class, and just for
// the sake of convenience is written in a seperate file.

#include "FreeSurface.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::FreeSurface::ComputeSolutionSlope(
	MAT_TYPES runType,
	const realCompositeGridFunction &systemRight,
	const realCompositeGridFunction &stageFieldPhi,
	const int &stage,
	const Modes::Motion &motion)
{
	if (UserInput.U != 0)
	{
		// VERY IMPORTANT NOTE :: FOR THE FORWARD-SPEED PROBLMES IT IS ABSOLUTELY VITAL THAT BEFORE
		// TAKING THE DERIVATIVES OF THE FREE-SURFACE ELEVATION AND VELOCITY POTENTIAL, THE
		// INTERPOLATION AND THE GHOST POINTS OF THE FREE-SURFACE DATA STRUCTURES ARE SET CORRECTLY.
		//
		// THESE ARE DONE AS FOLLLOWS:

		// 1. INTERPOLATION OF THE FREE-SURFACE ELEVATION AND POTENTIAL BY THE CLASS MEMBER FUNCTION.
		// 2. APPLYING THE SYMMETRY/ANTI-SYMMETRY CONDITIONS AT THE SYMMETRY PLANE (IF ANY) USING THE
		//    OVERTURE RUTINE.
		// 3. APPLYING THE NEUMANN BOUNDARY CONDITION TO BOTH ELEVATION AND POTENTIAL EVERYWHERE AROUND
		//    THE NEUMANN BOUNDARIES USING "SNEUMANN" CLASS MEMBER.
		// 4. APPLYING THE EXTRAPOLATION WHEREVER ( W.N < 0 ), USING THE OVERTURE RUTINE. THIS IMPLIES
		//    THAT THE ABOVE NEUMANN CONDITION IS JUST APPLIED WHEREVER ( W.N > 0 )
		// 5. FINISHING THE PROCESS BY SETTING THE GHOST POINTS AT THE CORNERS, USING THE OVERTURE RUTINE.
		//
		// NOW THE FREE-SURFACE DATA STRUCTURES ARE READY FOR CALCULATION OF THE CONVECTIVE  DERIVATIVES
		// USING THE BIASED CLASS MEMBER FUNCTION "APPLY".

		// -------------------------------
		// 1. INTERPOLATION OF ETA AND PHI
		// -------------------------------

		InterpolateSolutions("stage");

		// ------------------------------------
		// 2. SYMMETRY/ANTI-SYMMETRY CONDITIONS
		// ------------------------------------

		if (runType == MAT_TYPES::SYMMAT) // Symmetric runs
		{
			freeSurface_.solution_stage.elevation.applyBoundaryCondition(0, BCTypes::evenSymmetry, boundaryTypes_->symmetry, 0);
			freeSurface_.solution_stage.potential.applyBoundaryCondition(0, BCTypes::evenSymmetry, boundaryTypes_->symmetry, 0);
		}
		else if (runType == MAT_TYPES::ASMMAT) // Anti-symmetric runs
		{
			freeSurface_.solution_stage.elevation.applyBoundaryCondition(0, BCTypes::oddSymmetry, boundaryTypes_->symmetry, 0);
			freeSurface_.solution_stage.potential.applyBoundaryCondition(0, BCTypes::oddSymmetry, boundaryTypes_->symmetry, 0);
		}

		// --------------------------------------------------
		// 3. NEUMANN CONDITIONS AROUND THE BODY AND THE WALL
		// --------------------------------------------------

		upwind_object_.ApplyNeumannCondition(freeSurface_.solution_stage.elevation, hom_frc_);
		upwind_object_.ApplyNeumannCondition(freeSurface_.solution_stage.potential, systemRight);

		// -------------------------------------
		// 4. EXTRAPOLATION WHERE ( W.N ) < 0 )
		// -------------------------------------

		int bc;
		int time = 0;

		// Around the body

		for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); surface++)
		{
			const Single_boundary_data &be = boundariesData_->exciting[surface];
			const MappedGrid &mg = (*cg_)[be.grid];
			const RealArray &vbn = mg.vertexBoundaryNormal(be.side, be.axis);

			if (be.side == 0 and be.axis == 0)
				bc = BCTypes::boundary1;
			if (be.side == 1 and be.axis == 0)
				bc = BCTypes::boundary2;
			if (be.side == 0 and be.axis == 1)
				bc = BCTypes::boundary3;
			if (be.side == 1 and be.axis == 1)
				bc = BCTypes::boundary4;
			if (be.side == 0 and be.axis == 2)
				bc = BCTypes::boundary5;
			if (be.side == 1 and be.axis == 2)
				bc = BCTypes::boundary6;

			BoundaryConditionParameters exparam1;
			exparam1.setUseMask();

			intArray mask(bodyInd_[surface].iG1, bodyInd_[surface].iG2, bodyInd_[surface].iG3);
			mask = 0;

			where(UserInput.U * vbn(bodyInd_[surface].iB1, bodyInd_[surface].iB2, bodyInd_[surface].iB3, axis1) < 0)
			{
				mask = 1;
			}

			exparam1.mask() = mask;

			// First ghost layer

			freeSurface_.solution_stage.elevation[be.grid].applyBoundaryCondition(0, BCTypes::extrapolate, bc, 0, time, exparam1);
			freeSurface_.solution_stage.potential[be.grid].applyBoundaryCondition(0, BCTypes::extrapolate, bc, 0, time, exparam1);

			// Second ghost layer

			if (gridData_->ghost_line == 2)
			{
				BoundaryConditionParameters exparam2;
				exparam2.setUseMask();

				exparam2.mask() = mask;
				exparam2.lineToAssign = gridData_->ghost_line;

				freeSurface_.solution_stage.elevation[be.grid].applyBoundaryCondition(0, BCTypes::extrapolate, bc, 0, time, exparam2);
				freeSurface_.solution_stage.potential[be.grid].applyBoundaryCondition(0, BCTypes::extrapolate, bc, 0, time, exparam2);
			}
		}

		// Around the wall

		for (unsigned int surface = 0; surface < boundariesData_->absorbing.size(); surface++)
		{
			const Single_boundary_data &ba = boundariesData_->absorbing[surface];
			const MappedGrid &mg = (*cg_)[ba.grid];
			const RealArray &vbn = mg.vertexBoundaryNormal(ba.side, ba.axis);

			if (ba.side == 0 and ba.axis == 0)
				bc = BCTypes::boundary1;
			if (ba.side == 1 and ba.axis == 0)
				bc = BCTypes::boundary2;
			if (ba.side == 0 and ba.axis == 1)
				bc = BCTypes::boundary3;
			if (ba.side == 1 and ba.axis == 1)
				bc = BCTypes::boundary4;
			if (ba.side == 0 and ba.axis == 2)
				bc = BCTypes::boundary5;
			if (ba.side == 1 and ba.axis == 2)
				bc = BCTypes::boundary6;

			BoundaryConditionParameters exparam1;
			exparam1.setUseMask();

			intArray mask(wallInd_[surface].iG1, wallInd_[surface].iG2, wallInd_[surface].iG3);
			mask = 0;

			where(UserInput.U * vbn(wallInd_[surface].iB1, wallInd_[surface].iB2, wallInd_[surface].iB3, axis1) < 0)
			{
				mask = 1;
			}

			exparam1.mask() = mask;

			// First ghost layer

			freeSurface_.solution_stage.elevation[ba.grid].applyBoundaryCondition(0, BCTypes::extrapolate, bc, 0, time, exparam1);
			freeSurface_.solution_stage.potential[ba.grid].applyBoundaryCondition(0, BCTypes::extrapolate, bc, 0, time, exparam1);

			// Second ghost layer

			if (gridData_->ghost_line == 2)
			{
				BoundaryConditionParameters exparam2;
				exparam2.setUseMask();

				exparam2.mask() = mask;
				exparam2.lineToAssign = gridData_->ghost_line;

				freeSurface_.solution_stage.elevation[ba.grid].applyBoundaryCondition(0, BCTypes::extrapolate, bc, 0, time, exparam2);
				freeSurface_.solution_stage.potential[ba.grid].applyBoundaryCondition(0, BCTypes::extrapolate, bc, 0, time, exparam2);
			}
		}

		// ----------------------------------
		// 5. EXTRAPOLATION AT CORNER POINTS
		// ----------------------------------

		freeSurface_.solution_stage.elevation.finishBoundaryConditions();
		freeSurface_.solution_stage.potential.finishBoundaryConditions();

		// -----------------------------------------------------------------------------------------------------------------
		// CALCULATE THE CONVECTIVE DERIVATIVES USING THE BIASED CLASS (IF FILTER IS ON, THE CENTERED STENCIL WILL BE USED)
		// -----------------------------------------------------------------------------------------------------------------

		upwind_object_.ComputeDerivatives(freeSurface_.solution_stage.elevation, d_eta_dx_, d_eta_dz_); // eta
		upwind_object_.ComputeDerivatives(freeSurface_.solution_stage.potential, d_phi_dx_, d_phi_dz_); // phi

	} // End of forward-speed block

	// ----------------------------------------------------------------
	// NOW CALCULATE D_PHI_DT AND D_ETA_DT (free surface Bc's)
	// ----------------------------------------------------------------

	for (unsigned int surface = 0; surface < boundariesData_->free.size(); ++surface)
	{
		const Single_boundary_data &bf = boundariesData_->free[surface];
		const vector<Index> &Is = bf.surface_indices;

		const realArray &ETA = freeSurface_.solution_stage.elevation[bf.grid](Is[0], Is[1], Is[2]);
		const realArray &PHI = freeSurface_.solution_stage.potential[bf.grid](Is[0], Is[1], Is[2]);
		const realArray &ETAB = baseFlowData_->elevation[bf.grid](Is[0], Is[1], Is[2]);
		const realArray &DPHIB_DX = baseFlowData_->fs_derivatives.dx[surface];
		const realArray &DPHIB_DZ = baseFlowData_->fs_derivatives.dz[surface];
		const realArray &D2PHIBDY2 = baseFlowData_->fs_derivatives.dyy[surface];
		const realArray &DETA_DX = d_eta_dx_[bf.grid](Is[0], Is[1], Is[2]);
		const realArray &DETAB_DX = baseFlowData_->elevation_derivative.dx[surface];
		const realArray &DETAB_DZ = baseFlowData_->elevation_derivative.dz[surface];
		const realArray &DETA_DZ = d_eta_dz_[bf.grid](Is[0], Is[1], Is[2]);
		const realArray &DPHI_DX = d_phi_dx_[bf.grid](Is[0], Is[1], Is[2]);
		const realArray &DPHI_DZ = d_phi_dz_[bf.grid](Is[0], Is[1], Is[2]);

		// SHORT NAMES FOR THE KINEMATIC CONDITION
		const realArray &DPHI_DY = stageFieldPhi[bf.grid].y()(Is[0], Is[1], Is[2]);							 // d(phi)/dy
		const realArray &U_MIN_DPHIB_DX_DETA_DX = (UserInput.U - gx_wu_bcs_tag_ * DPHIB_DX) * DETA_DX;		 // (U - d(phib)/dx) * deta/dx
		const realArray &U_DETAB_DX = (UserInput.U * DETAB_DX) * doubleBodyTag_;							 // U*detab/dx
		const realArray &GRAD_PHIB_GRAD_ETAB = (DPHIB_DX * DETAB_DX + DPHIB_DZ * DETAB_DZ) * doubleBodyTag_; // grad(phib)*grad(etab)
		const realArray &ETA_D2PHIB_DY2 = ETA * D2PHIBDY2 * gx_wu_bcs_tag_;									 // eta*d²(phib)/dy²
		const realArray &ETAB_D2PHIB_DY2 = (ETAB * D2PHIBDY2) * doubleBodyTag_;								 // etab*d²(phib)/dy²
		const realArray &DETA_DZ_DPHIB_DZ = DETA_DZ * DPHIB_DZ * gx_wu_bcs_tag_;							 // deta/dz*dphib/dz
		const realArray &ETA_SPONGE = sponge_[surface] * ETA;
		// SHORT NAMES FOR THE DYNAMIC CONDITION
		const realArray &G_ETA = UserInput.g * ETA;															 // g*eta
		const realArray &U_MIN_DPHIB_DX_DPHI_DX = (UserInput.U - gx_wu_bcs_tag_ * DPHIB_DX) * DPHI_DX;		 //(U - d(phib)/dx) * d(phi)/dx
		const realArray &U_DPHIB_DX = (UserInput.U * DPHIB_DX) * doubleBodyTag_;							 // U*d(phib)/dx
		const realArray &GRAD_PHIB_GRAD_PHIB = (DPHIB_DX * DPHIB_DX + DPHIB_DZ * DPHIB_DZ) * doubleBodyTag_; // grad(phib)*grad(phib)
		const realArray &DPHI_DZ_DPHIB_DZ = DPHI_DZ * DPHIB_DZ * gx_wu_bcs_tag_;							 // d(phi)/dz * d(phib)/dz
		const realArray &PHI_SPONGE = sponge_[surface] * PHI;

		// KINEMATIC CONDITION
		freeSurface_.slope[stage].elevation[bf.grid](Is[0], Is[1], Is[2]) =
			motion.fsbcRamp * (DPHI_DY + U_MIN_DPHIB_DX_DETA_DX + U_DETAB_DX - GRAD_PHIB_GRAD_ETAB + ETA_D2PHIB_DY2 + ETAB_D2PHIB_DY2 - DETA_DZ_DPHIB_DZ - ETA_SPONGE);

		// DYNAMIC CONDITION
		freeSurface_.slope[stage].potential[bf.grid](Is[0], Is[1], Is[2]) =
			motion.fsbcRamp * (-G_ETA + U_MIN_DPHIB_DX_DPHI_DX + U_DPHIB_DX - 0.5 * GRAD_PHIB_GRAD_PHIB - DPHI_DZ_DPHIB_DZ - PHI_SPONGE);

	} // end of loop over free-surface
}