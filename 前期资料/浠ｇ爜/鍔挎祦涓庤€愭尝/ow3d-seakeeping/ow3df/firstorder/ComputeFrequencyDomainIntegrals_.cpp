//
// -----------------------------------------------------------------------------------------------------------------------
//
// NOTE : In this function we calculate (in frequency domain), the first-order forces in the Bernoulli equations,
// 	   which contain the incident wave velocity potential.
// 	   Instead of adding the velocity potential of the incident wave to the scattering velocity potential
//         in time domain, and then Fourier transform the results, we calculate the part related to the incident
//         wave, directly in the frequency domain. For example the Froude-Krylov force is calculated in this manner.
//         Or if there is a term like d( phis + phi0 )/dx in the time domain, the second term is calculated just in
//         the frequency domain and using the following function. Then for each frequency the function is integrated
//         over the body surface to give the whole contributions.
//
//         The function can be used together with the functions in the file "incidentWaveFunctions.cpp". A pointer to
//         the desired function in that file and a vector<ComplexNumbers> is passed as the arguments to the following
//         function.
//
//         Additional terms (not dependent on the frequency) which are needed to be included in the integration
//         can be added easily by the additional arguments. For example the base-flow term like grad(phib) which appears
//         in the Bernoulli eq. as grad(phib) * grad(phi0). Note that a default argument can be used for this purpose.
//
//         In all integrals a symmetric and an anti-symmetric is distinguished to be able to use the grid symmetry.
//
// -----------------------------------------------------------------------------------------------------------------------

#include "FirstOrder.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::FirstOrder::ComputeFrequencyDomainIntegrals_(
	void (*pf)(
		vector<RealArray> &,
		vector<RealArray> &,
		vector<RealArray> &,
		vector<RealArray> &,
		const RealArray &,
		const RealArray &,
		const RealArray &,
		void *),
	vector<ComplexNumbers> &finalC,
	const vector<RealArray> &base,
	string sym_asm_base)
{
	vector<double> rotation_centre = OW3DSeakeeping::UserInput.rotation_centre; // shorter name

	vector<RealArray> resy, imsy; // These variables
	vector<RealArray> reas, imas; // remain intact during the integration

	for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); surface++)
	{
		const Single_boundary_data &be = boundariesData_->exciting[surface];
		const vector<Index> &Is = be.surface_indices;
		realArray temp(Is[0], Is[1], Is[2]);
		temp = 0.0;

		resy.push_back(temp);
		imsy.push_back(temp);
		reas.push_back(temp);
		imas.push_back(temp);
	}

	realCompositeGridFunction n_re_s(*cg_), n_im_s(*cg_); // These are the variables which are multiplied by the surface normal vector and
	realCompositeGridFunction n_re_a(*cg_), n_im_a(*cg_); // are supplied to the Overture integrator( they must be "realCompositeGridFunction" )

	n_re_s = n_im_s = 0;
	n_re_a = n_im_a = 0;

	ComplexNumbers tempC(omegaeAll_.size());

	vector<ComplexNumbers> CSym;
	vector<ComplexNumbers> CAsm;

	for (unsigned int sp = 0; sp < UserInput.responses.size(); sp++)
	{
		CSym.push_back(tempC);
		CAsm.push_back(tempC);
	}

	incidentWaveIntegralsParameters params;

	params.g = g_;
	params.rho = rho_;
	params.betar = betar_;
	params.U = U_;
	params.h = gridData_->maximum_depth;
	params.isDif3 = false;

	// NOTE : The value of isDif3 becomes "true" only in the
	//        third case (omega03) for the following-seas
	//        diffraction problem. This is performed in the
	//        following loops.

	vector<double> waveNumbers;

	// --------------------------------------------------------------------------------------
	//
	// Transfer the data to the realCompositeGridFunctions (is necessary for the integration)
	//
	// --------------------------------------------------------------------------------------

	for (unsigned int rn = 0; rn < diffraction_runs_.size(); rn++) // LOOP OVER THE NUMBER OF THE DIFFRACTION RUNS
	{
		// ----------------------------------------------------------------
		// Determine the wave number vector in the case of following seas
		// ----------------------------------------------------------------

		if (
			diffraction_runs_[rn].diff_type == DIFF_TYPES::OM1 ||
			diffraction_runs_[rn].diff_type == DIFF_TYPES::OM1_HLF ||
			diffraction_runs_[rn].diff_type == DIFF_TYPES::OM1_SYM ||
			diffraction_runs_[rn].diff_type == DIFF_TYPES::OM1_ASM)
		{
			waveNumbers = k01_;
		}
		else if (
			diffraction_runs_[rn].diff_type == DIFF_TYPES::OM2 ||
			diffraction_runs_[rn].diff_type == DIFF_TYPES::OM2_HLF ||
			diffraction_runs_[rn].diff_type == DIFF_TYPES::OM2_SYM ||
			diffraction_runs_[rn].diff_type == DIFF_TYPES::OM2_ASM)
		{
			waveNumbers = k02_;
		}
		else if (
			diffraction_runs_[rn].diff_type == DIFF_TYPES::OM3 ||
			diffraction_runs_[rn].diff_type == DIFF_TYPES::OM3_HLF ||
			diffraction_runs_[rn].diff_type == DIFF_TYPES::OM3_SYM ||
			diffraction_runs_[rn].diff_type == DIFF_TYPES::OM3_ASM)
		{
			waveNumbers = k03_;

			params.isDif3 = true;
		}
		else // All other diffraction problems than the following-seas ones
		{
			waveNumbers = ko_;
		}

		for (unsigned int sp = 0; sp < UserInput.responses.size(); sp++) // LOOP OVER THE NUMBER OF DEGREES OF FREEDOM
		{
			for (unsigned int fr = 0; fr < waveNumbers.size(); fr++) // AT THIS FREQUENCY, TRANSFER THE DATA TO THE realCompositeGridFunctions.
			{
				params.k = waveNumbers[fr];

				for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); surface++)
				{
					params.surface = surface;

					const Single_boundary_data &be = boundariesData_->exciting[surface];
					const vector<Index> &Is = be.surface_indices;
					MappedGrid &mg = (*cg_)[be.grid];
					const RealArray &v = mg.vertex();
					const RealArray &vbn = mg.vertexBoundaryNormal(be.side, be.axis);
					RealArray x(Is[0], Is[1], Is[2]), y(Is[0], Is[1], Is[2]), z(Is[0], Is[1], Is[2]);

					x = v(Is[0], Is[1], Is[2], axis1);
					y = v(Is[0], Is[1], Is[2], axis2);
					z = 0.0;

					if (gridData_->nod == 3)
					{
						z = v(Is[0], Is[1], Is[2], axis3);
					}

					// Get the symmetric and anti-symmetric parts of the related frequency-domain
					// first-order pressure terms at this point x, y, z with these params:

					if (sym_asm_base == "sym")
					{
						pf(resy, imsy, reas, imas, x, y, z, &params);
					}
					else if (sym_asm_base == "asm")
					{
						pf(reas, imas, resy, imsy, x, y, z, &params);
					}
					else
					{
						throw runtime_error("Error, OW3DSeakeeping::FirstOrder::ComputeFrequencyDomainIntegrals_.cpp: Type of base flow should be sym or asm.");
					}

					// Multiply by the base flow derivatives

					if (base.size() != 0)
					{
						resy[surface] = resy[surface] * base[surface];
						imsy[surface] = imsy[surface] * base[surface];
						reas[surface] = reas[surface] * base[surface];
						imas[surface] = imas[surface] * base[surface];
					}

					// Multiply by the symmetry coefficients

					int half_coeff = gridData_->symmetryCoefficients[rn][sp];

					resy[surface] = half_coeff * resy[surface];
					imsy[surface] = half_coeff * imsy[surface];
					reas[surface] = half_coeff * reas[surface];
					imas[surface] = half_coeff * imas[surface];

					// Multiply by the normal vector

					if (UserInput.responses[sp] == MODE_NAMES::SURGE)
					{
						n_re_s[be.grid](Is[0], Is[1], Is[2]) = resy[surface] * vbn(Is[0], Is[1], Is[2], axis1);
						n_im_s[be.grid](Is[0], Is[1], Is[2]) = imsy[surface] * vbn(Is[0], Is[1], Is[2], axis1);
						n_re_a[be.grid](Is[0], Is[1], Is[2]) = reas[surface] * vbn(Is[0], Is[1], Is[2], axis1);
						n_im_a[be.grid](Is[0], Is[1], Is[2]) = imas[surface] * vbn(Is[0], Is[1], Is[2], axis1);
					}
					else if (UserInput.responses[sp] == MODE_NAMES::HEAVE)
					{
						n_re_s[be.grid](Is[0], Is[1], Is[2]) = resy[surface] * vbn(Is[0], Is[1], Is[2], axis2);
						n_im_s[be.grid](Is[0], Is[1], Is[2]) = imsy[surface] * vbn(Is[0], Is[1], Is[2], axis2);
						n_re_a[be.grid](Is[0], Is[1], Is[2]) = reas[surface] * vbn(Is[0], Is[1], Is[2], axis2);
						n_im_a[be.grid](Is[0], Is[1], Is[2]) = imas[surface] * vbn(Is[0], Is[1], Is[2], axis2);
					}
					else if (UserInput.responses[sp] == MODE_NAMES::SWAY)
					{
						n_re_s[be.grid](Is[0], Is[1], Is[2]) = resy[surface] * vbn(Is[0], Is[1], Is[2], axis3);
						n_im_s[be.grid](Is[0], Is[1], Is[2]) = imsy[surface] * vbn(Is[0], Is[1], Is[2], axis3);
						n_re_a[be.grid](Is[0], Is[1], Is[2]) = reas[surface] * vbn(Is[0], Is[1], Is[2], axis3);
						n_im_a[be.grid](Is[0], Is[1], Is[2]) = imas[surface] * vbn(Is[0], Is[1], Is[2], axis3);
					}
					else if (UserInput.responses[sp] == MODE_NAMES::ROLL)
					{
						n_re_s[be.grid](Is[0], Is[1], Is[2]) =
							resy[surface] * (vbn(Is[0], Is[1], Is[2], axis3) * (v(Is[0], Is[1], Is[2], axis2) - rotation_centre[1]) -
											 vbn(Is[0], Is[1], Is[2], axis2) * (v(Is[0], Is[1], Is[2], axis3) - rotation_centre[2]));

						n_im_s[be.grid](Is[0], Is[1], Is[2]) =
							imsy[surface] * (vbn(Is[0], Is[1], Is[2], axis3) * (v(Is[0], Is[1], Is[2], axis2) - rotation_centre[1]) -
											 vbn(Is[0], Is[1], Is[2], axis2) * (v(Is[0], Is[1], Is[2], axis3) - rotation_centre[2]));
						//
						n_re_a[be.grid](Is[0], Is[1], Is[2]) =
							reas[surface] * (vbn(Is[0], Is[1], Is[2], axis3) * (v(Is[0], Is[1], Is[2], axis2) - rotation_centre[1]) -
											 vbn(Is[0], Is[1], Is[2], axis2) * (v(Is[0], Is[1], Is[2], axis3) - rotation_centre[2]));

						n_im_a[be.grid](Is[0], Is[1], Is[2]) =
							imas[surface] * (vbn(Is[0], Is[1], Is[2], axis3) * (v(Is[0], Is[1], Is[2], axis2) - rotation_centre[1]) -
											 vbn(Is[0], Is[1], Is[2], axis2) * (v(Is[0], Is[1], Is[2], axis3) - rotation_centre[2]));
					}
					else if (UserInput.responses[sp] == MODE_NAMES::YAW)
					{
						n_re_s[be.grid](Is[0], Is[1], Is[2]) =
							resy[surface] * (vbn(Is[0], Is[1], Is[2], axis1) * (v(Is[0], Is[1], Is[2], axis3) - rotation_centre[2]) -
											 vbn(Is[0], Is[1], Is[2], axis3) * (v(Is[0], Is[1], Is[2], axis1) - rotation_centre[0]));

						n_im_s[be.grid](Is[0], Is[1], Is[2]) =
							imsy[surface] * (vbn(Is[0], Is[1], Is[2], axis1) * (v(Is[0], Is[1], Is[2], axis3) - rotation_centre[2]) -
											 vbn(Is[0], Is[1], Is[2], axis3) * (v(Is[0], Is[1], Is[2], axis1) - rotation_centre[0]));
						//
						n_re_a[be.grid](Is[0], Is[1], Is[2]) =
							reas[surface] * (vbn(Is[0], Is[1], Is[2], axis1) * (v(Is[0], Is[1], Is[2], axis3) - rotation_centre[2]) -
											 vbn(Is[0], Is[1], Is[2], axis3) * (v(Is[0], Is[1], Is[2], axis1) - rotation_centre[0]));

						n_im_a[be.grid](Is[0], Is[1], Is[2]) =
							imas[surface] * (vbn(Is[0], Is[1], Is[2], axis1) * (v(Is[0], Is[1], Is[2], axis3) - rotation_centre[2]) -
											 vbn(Is[0], Is[1], Is[2], axis3) * (v(Is[0], Is[1], Is[2], axis1) - rotation_centre[0]));
					}
					else if (UserInput.responses[sp] == MODE_NAMES::PITCH)
					{
						n_re_s[be.grid](Is[0], Is[1], Is[2]) =
							resy[surface] * (vbn(Is[0], Is[1], Is[2], axis2) * (v(Is[0], Is[1], Is[2], axis1) - rotation_centre[0]) -
											 vbn(Is[0], Is[1], Is[2], axis1) * (v(Is[0], Is[1], Is[2], axis2) - rotation_centre[1]));

						n_im_s[be.grid](Is[0], Is[1], Is[2]) =
							imsy[surface] * (vbn(Is[0], Is[1], Is[2], axis2) * (v(Is[0], Is[1], Is[2], axis1) - rotation_centre[0]) -
											 vbn(Is[0], Is[1], Is[2], axis1) * (v(Is[0], Is[1], Is[2], axis2) - rotation_centre[1]));
						//
						n_re_a[be.grid](Is[0], Is[1], Is[2]) =
							reas[surface] * (vbn(Is[0], Is[1], Is[2], axis2) * (v(Is[0], Is[1], Is[2], axis1) - rotation_centre[0]) -
											 vbn(Is[0], Is[1], Is[2], axis1) * (v(Is[0], Is[1], Is[2], axis2) - rotation_centre[1]));

						n_im_a[be.grid](Is[0], Is[1], Is[2]) =
							imas[surface] * (vbn(Is[0], Is[1], Is[2], axis2) * (v(Is[0], Is[1], Is[2], axis1) - rotation_centre[0]) -
											 vbn(Is[0], Is[1], Is[2], axis1) * (v(Is[0], Is[1], Is[2], axis2) - rotation_centre[1]));
					}
					else if (UserInput.responses[sp] == MODE_NAMES::GMODE)
					{
						unsigned int gm_resp_index = sp - UserInput.number_of_rigid_modes;
						n_re_s[be.grid](Is[0], Is[1], Is[2]) = resy[surface] * gridData_->flexmodes[gm_resp_index].flex_vbn[surface](Is[0], Is[1], Is[2]);
						n_im_s[be.grid](Is[0], Is[1], Is[2]) = imsy[surface] * gridData_->flexmodes[gm_resp_index].flex_vbn[surface](Is[0], Is[1], Is[2]);
						n_re_a[be.grid](Is[0], Is[1], Is[2]) = reas[surface] * gridData_->flexmodes[gm_resp_index].flex_vbn[surface](Is[0], Is[1], Is[2]);
						n_im_a[be.grid](Is[0], Is[1], Is[2]) = imas[surface] * gridData_->flexmodes[gm_resp_index].flex_vbn[surface](Is[0], Is[1], Is[2]);
					}

				} // End of loop over body surface

				// -----------------------------------------------
				//
				// Carry-out the integration for this frequency
				//
				// -----------------------------------------------

				// ------------------------------------------------------
				// + Following sea with sym. and anti-sym contributions:
				// ------------------------------------------------------

				if (U_ != 0 and gridData_->halfSymmetry and betar_ != 0 and (betar_ < Pi / 2 or betar_ > 3 * Pi / 2))
				{
					if (rn < 2) // OMEGA01 SYM. AND OMEGA01 ANTI-SYM.
					{
						CSym[sp](0, fr) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_re_s); // real symmetric
						CSym[sp](1, fr) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_im_s); // imag symmetric

						CAsm[sp](0, fr) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_re_a); // real anti-symmetric
						CAsm[sp](1, fr) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_im_a); // imag anti-symmetric
					}
					else if (rn < 4) // OMEGA02 SYM. AND OMEGA02 ANTI-SYM.
					{
						CSym[sp](0, FSLimIndex_ + 1 + fr) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_re_s); // real symmetric
						CSym[sp](1, FSLimIndex_ + 1 + fr) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_im_s); // imag symmetric

						CAsm[sp](0, FSLimIndex_ + 1 + fr) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_re_a); // real anti-symmetric
						CAsm[sp](1, FSLimIndex_ + 1 + fr) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_im_a); // imag anti-symmetric
					}
					else // OMEGA03 SYM. AND OMEGA03 ANTI-SYM.
					{
						CSym[sp](0, fr + 2 * FSLimIndex_ + 1) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_re_s); // real symmetric
						CSym[sp](1, fr + 2 * FSLimIndex_ + 1) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_im_s); // imag symmetric

						CAsm[sp](0, fr + 2 * FSLimIndex_ + 1) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_re_a); // real anti-symmetric
						CAsm[sp](1, fr + 2 * FSLimIndex_ + 1) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_im_a); // imag anti-symmetric
					}
				}

				// --------------------------------------------------------
				// + Following sea with NO sym. and anti-sym splitting
				// --------------------------------------------------------

				else if (U_ != 0 and (betar_ < Pi / 2 or betar_ > 3 * Pi / 2))
				{
					if (rn == 0) // OMEGA01 SYM. AND OMEGA01 ANTI-SYM.
					{
						CSym[sp](0, fr) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_re_s); // real symmetric
						CSym[sp](1, fr) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_im_s); // imag symmetric

						CAsm[sp](0, fr) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_re_a); // real anti-symmetric
						CAsm[sp](1, fr) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_im_a); // imag anti-symmetric
					}
					else if (rn == 1) // OMEGA02 SYM. AND OMEGA02 ANTI-SYM.
					{
						CSym[sp](0, FSLimIndex_ + 1 + fr) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_re_s); // real symmetric
						CSym[sp](1, FSLimIndex_ + 1 + fr) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_im_s); // imag symmetric

						CAsm[sp](0, FSLimIndex_ + 1 + fr) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_re_a); // real anti-symmetric
						CAsm[sp](1, FSLimIndex_ + 1 + fr) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_im_a); // imag anti-symmetric
					}
					else // OMEGA03 SYM. AND OMEGA03 ANTI-SYM.
					{
						CSym[sp](0, fr + 2 * FSLimIndex_ + 1) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_re_s); // real symmetric
						CSym[sp](1, fr + 2 * FSLimIndex_ + 1) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_im_s); // imag symmetric

						CAsm[sp](0, fr + 2 * FSLimIndex_ + 1) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_re_a); // real anti-symmetric
						CAsm[sp](1, fr + 2 * FSLimIndex_ + 1) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_im_a); // imag anti-symmetric
					}
				}

				// ----------------------------------------------
				// + All other cases which are not following sea:
				// ----------------------------------------------

				else
				{
					CSym[sp](0, fr) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_re_s); // real symmetric
					CSym[sp](1, fr) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_im_s); // imag symmetric

					CAsm[sp](0, fr) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_re_a); // real anti-symmetric
					CAsm[sp](1, fr) = ComputeSurfaceIntegral(integrator_, gridData_->triangulation, n_im_a); // imag anti-symmetric
				}

			} // End of frequency loop

			// * Whole grid with any headings ------------------------------------------------------------------------------------
			//
			//     In this scenario the user has builds the whole part of the grid. The
			//     symmetric "Cs" and the anti-symmetric "Ca" components are added
			//     together to get the final results.
			//
			// -------------------------------------------------------------------------------------------------------------------

			if (
				diffraction_runs_[rn].diff_type == DIFF_TYPES::FULL ||
				diffraction_runs_[rn].diff_type == DIFF_TYPES::OM3)
			{
				finalC[sp] = CSym[sp] + CAsm[sp];
			}

			// * Half grid and symmetric BC with arbitrary headings, or half grid in head waves --------------------------------------
			//
			//     Two scenarios are possible here :
			//
			//       1. The user has made just half of the grid and the heading angle is 180. This will be interpreted
			//          by the solver, as a symmetric grid with the head seas condition, which implies the anti-symmetric
			//          component is zero.
			//          Note by the anti-symmetric component it is meant, those components which are proportional to
			//          sin( k z sin(beta) ).
			//          Just one diffracion problem needs to be solved for this scenario, and only the symmetric phasors
			//          are non-trivial.
			//
			//       2. The user has built just half of the grid, and the heading is not necessarily 180. This case is
			//          quiet common for the seakeeping analysis with oblique waves.
			//          Two diffraction problems must be solved: the symmetric and the anti-symmetric. For the symmetric
			//          diffraction problem, the symmetric component of the incident wave is saved in C[pn] container.
			//          Note the anti-symmetric part from the other diffraction problem will be stored in the next loop
			//          index for the size of the diffraction problem.
			//
			// -------------------------------------------------------------------------------------------------------------------

			else if (
				diffraction_runs_[rn].diff_type == DIFF_TYPES::HEAD ||	  // NOTE : In two cases "diffraction_head" and  "diffraction_sym", the program enters
				diffraction_runs_[rn].diff_type == DIFF_TYPES::SYM ||	  //        this block just once. C[pn] is already zero initialized, to which the symmetric results will be added. For all other cases,
				diffraction_runs_[rn].diff_type == DIFF_TYPES::OM3_HLF || //        program enters this block three times. Each time symmetric results will be added to the previously calculated ones.
				diffraction_runs_[rn].diff_type == DIFF_TYPES::OM3_SYM	  //
			)
			{
				finalC[sp] = finalC[sp] + CSym[sp];
			}

			// * Half grid anti-symmetric BC with arbitrary headings -------------------------------------------------------------
			//
			//     This scenario is only related to the scenario #2 from above, and includes the anti-symmetric diffraction
			//     part. The anti-symmetric component "Ca" will be added here to the symmetric components which already in
			//     the previous loop for the number of diffraction problem, has been stored in C[pn].
			//
			// -------------------------------------------------------------------------------------------------------------------

			else
			{
				finalC[sp] = finalC[sp] + CAsm[sp]; // The sym. and anti-sym. are added at the corresponding responses.
			}

		} // End of response loop

	} // End of diffraction runs loop
}
