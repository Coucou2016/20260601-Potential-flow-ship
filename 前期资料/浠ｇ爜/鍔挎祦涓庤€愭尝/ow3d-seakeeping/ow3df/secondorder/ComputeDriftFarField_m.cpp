// This public member function belongs to the SecondOrder class, and just for
// the sake of convenience is written in a seperate file.

#include "SecondOrder.h"
#include "OW3DConstants.h"

// An outline of the function:
//
//  Data preparation for body and water line integrations
//
//   for (frequency)
//    |
//    |  First assign RAOs
//    |
//    |  for (integration counts)
//    |   |
//    |   |
//    |   |   for (body surface)
//    |   |    |
//    |   |    |
//    |   |    | for (i)
//    |   |    |  | for (j)
//    |   |    |  |  | for (k)
//    |   |    |  |  |
//    |   |    |  |  |  | for (type of data)
//    |   |    |  |  |  |  |
//    |   |    |  |  |  |  |  Read from binary file, and assign phi
//    |   |    |  |  |  |  |  and grad phi phasors on the body surfaces
//    |   |    |  |  |  |  |
//    |   |    |  |  |  | end for (type of data)
//    |   |    |  |  |  |
//    |   |    |  |  | end for (k)
//    |   |    |  | end for (j)
//    |   |    | end for (i)
//    |   |    |
//    |   |    |
//    |   |    | Here we need to build the data in to a
//    |   |    | ComplexArray, so it will be accessible
//    |   |    | outside this loop.
//    |   |    |
//    |   |    |
//    |   |   end for (body surface)
//    |   |
//    |   |
//    |   |   for (theta)
//    |   |    |
//    |   |    | for (body surface)                                         |
//    |   |    |  |                                                         |
//    |   |    |  |  Calculate Kochins function (H1) as a                   |
//    |   |    |  |  function of theta and kappa_j for                      |
//    |   |    |  |  this part of the body surface. By this                 |
//    |   |    |  |  the integrand for the final force integration          |  NOTE : THIS PART IS PERFORMED INSIDE
//    |   |    |  |  is built in to the RealCompositeGridFunction           |
//    |   |    |  |  needed for the composite grid integration.             |  THE "calcH1KappaTheta_" FUNCTION.
//    |   |    |  |                                                         |
//    |   |    | end for (body surface)                                     |
//    |   |    |                                                            |
//    |   |    |  Do the composite grid integration here, and store the     |
//    |   |    |  results for this angle in to a data structure as double*. |
//    |   |    |
//    |   |   end for (theta)
//    |   |
//    |   |
//    |   |   Do the line integration here, and by this
//    |   |   calculate and store the drift force for this frequency.
//    |   |
//    |   |
//    |  end for(integration counts)
//    |
//    |
//   end for(frequency)

void OW3DSeakeeping::SecondOrder::ComputeDriftFarField_m()
{
	if (OW3DSeakeeping::UserInput.wave_drift)
	{
		// --------------------------------------------
		// Open the frequency-domain files (phasors)
		// --------------------------------------------

		// NOTE : For the far-field method no incident wave potentials are in the phasors.

		string bodyFile = results_folder_ + '/' + OW3DSeakeeping::fdomain_potentials_no_incident_binary_file;
		ifstream bfin(bodyFile, ios_base::in | ios_base::binary);
		if (!bfin.is_open())
			throw runtime_error("Error, OW3DSeakeeping::SecondOrder::ComputeDriftFarField_m.cpp: Frequency-domain potential file can not be opened.");
		string bodyFile_rd = results_folder_ + '/' + OW3DSeakeeping::fdomain_potentials_radiation_binary_file; // NOTE : Only radiation potentials
		ifstream bfin_rd(bodyFile_rd, ios_base::in | ios_base::binary);
		if (!bfin_rd.is_open())
			throw runtime_error("Error, OW3DSeakeeping::SecondOrder::ComputeDriftFarField_m.cpp: Frequency-domain potential file can not be opened.");
		string bodyFile_sc = results_folder_ + '/' + fdomain_potentials_scattering_binary_file; // NOTE : Only scattering potentials
		ifstream bfin_sc(bodyFile_sc, ios_base::in | ios_base::binary);
		if (!bfin_sc.is_open())
			throw runtime_error("Error, OW3DSeakeeping::SecondOrder::ComputeDriftFarField_m.cpp: Frequency-domain potential file can not be opened.");

		// ---------------------------------------------
		// Data initializations
		// ----------------------------------------------

		struct comp
		{
			double sym_real;
			double sym_imag;
			double asm_real;
			double asm_imag;

		} cp, cp_rd, cp_sc; // The frequency domain data is stored in this variable.

		double *LINE_INTEG_DATA_2 = new double[NTHETA_]; // THE FINAL DATA USED FOR THE LINE INTEGRATION
		vector<double> real_H2_half_kBar2_kBar3, imag_H2_half_kBar2_kBar3;

		vector<double> omegaoVector = allKsAndOmegas_.omegao;
		vector<double> omegaeVector = allKsAndOmegas_.omegae;
		vector<double> koVector = allKsAndOmegas_.ko;
		vector<double> koDeepVector = allKsAndOmegas_.koDeep; // NOTE : Only valid for deep water

		double kappa0;
		double kBar2, kBar3; // The integrations bounds (NOTE : kBar1 and kBar4 are only valid in forward-speed case.)

		// ---------------------------------------------------
		//
		// Frequency loop (Start calculating the drift force)
		//
		// ---------------------------------------------------

		for (unsigned int f = 0; f < flength_; f++)
		{
			double Rw = 0.; // The wave drift force initialized to 0 for each frequency

			const double omegae = omegaeVector[f]; // ENCOUNTER FREQUENCY
			const double omegao = omegaoVector[f]; // WAVE      FREQUENCY
			const double K = koVector[f];		   // WAVE NUMBER
			const double KDeep = koDeepVector[f];  // NOTE : Only valid for deep water

			const double tau = U_ * omegae / g_;

			// ---------------------------------
			// Assign the integration bounds
			// ---------------------------------

			if (U_ == 0)
			{
				kBar2 = -KDeep;
				kBar3 = KDeep;
			}
			else
			{
				kappa0 = g_ / (U_ * U_);
				kBar2 = -kappa0 / 2. * (1 + 2 * tau - sqrt(1 + 4 * tau)); // Is always negative. Also note kBar2 > kBar1.
				if (tau < 1. / 4)
				{
					kBar3 = kappa0 / 2. * (1 - 2 * tau - sqrt(1 - 4 * tau)); // Is always positive
				}
				else if (tau > 1. / 4)
				{
					kBar3 = kappa0 * tau;
				}
			}

			const double DL2 = Pi / (NTHETA_ - 1); // Segment's length for integration in [-pi/2, pi/2] corresponding to [kBar2 kBar3]

			// The following vectors must be cleared in
			// order to be ready for the next frequency.

			real_H2_half_kBar2_kBar3.clear();
			imag_H2_half_kBar2_kBar3.clear();

			// ------------------------------------------
			// Assign the response amplitude operators.
			// ------------------------------------------

			for (unsigned int run = 0; run < radiation_runs_.size(); run++)
			{
				MODE_NAMES mode_name = radiation_runs_[run].mode;

				if (mode_name == MODE_NAMES::SURGE)
				{
					xi1_re_ = RAOs_[run](0, f);
					xi1_im_ = RAOs_[run](1, f);
				}
				else if (mode_name == MODE_NAMES::HEAVE)
				{
					xi2_re_ = RAOs_[run](0, f);
					xi2_im_ = RAOs_[run](1, f);
				}
				else if (mode_name == MODE_NAMES::SWAY)
				{
					xi3_re_ = RAOs_[run](0, f);
					xi3_im_ = RAOs_[run](1, f);
				}
				else if (mode_name == MODE_NAMES::ROLL)
				{
					alpha1_re_ = RAOs_[run](0, f);
					alpha1_im_ = RAOs_[run](1, f);
				}
				else if (mode_name == MODE_NAMES::YAW)
				{
					alpha2_re_ = RAOs_[run](0, f);
					alpha2_im_ = RAOs_[run](1, f);
				}
				else if (mode_name == MODE_NAMES::PITCH)
				{
					alpha3_re_ = RAOs_[run](0, f);
					alpha3_im_ = RAOs_[run](1, f);
				}
				else
				{
					throw runtime_error("Error, OW3DSeakeeping::SecondOrder::ComputeDriftFarField_m.cpp: The type of radiation run can not be recognized.");
				}
			}

			// -------------------------------------
			// Loop due to symmetry of the grid.
			// -------------------------------------

			for (unsigned int count = 0; count < numberOFIntegrations_; count++)
			{
				int symSign = (count == 0) ? 1 : -1; // Means integration on the other half of the body

				// NOTE : "keep_this_half" TRUE means that we need to wait until the next "count" carries out
				//         in the loop. So we can add op the contributions from other half of the symmetric grid
				//         to the Kochins Function integral. For a whole grid model, and a symmetric grid when
				//         "count==1" and symSign==-1 the "keep_this_half" boolian variable is FALSE. This means
				//         the final integrands for the drift forces are ready.

				bool keep_this_half = (numberOFIntegrations_ == 2 and count == 0);

				// ---------------------------------------------------------
				// Body surface loop (to store the complex phasors)
				// ---------------------------------------------------------

				for (unsigned int surface = 0; surface < NES_; surface++)
				{
					const Single_boundary_data &be = boundariesData_->exciting[surface];
					const vector<Index> &Is = be.surface_indices;

					int l1 = Is[1].getLength();
					int l2 = Is[2].getLength();

					// ---------------------------------------------
					//
					// The shift due to the previous surfaces
					//
					// ---------------------------------------------

					int surface_shift = 0;

					for (int back = surface; back > 0; back--)
					{
						const Single_boundary_data &sbd = boundariesData_->exciting[back - 1];
						const vector<Index> &I = sbd.surface_indices;

						const int bcl0 = I[0].getLength();
						const int bcl1 = I[1].getLength();
						const int bcl2 = I[2].getLength();

						surface_shift += bcl0 * bcl1 * bcl2 * NPOTENS_ * flength_;
					}

					// ------------------------------------------------
					// Loop over the type of the data (phi or grad phi)
					// Loop over i
					// Loop over j
					// Loop over k
					// ------------------------------------------------

					for (unsigned int pot = 0; pot < FarPots_; pot++)
					{
						for (int i = Is[0].getBase(); i <= Is[0].getBound(); i++)
						{
							for (int j = Is[1].getBase(); j <= Is[1].getBound(); j++)
							{
								for (int k = Is[2].getBase(); k <= Is[2].getBound(); k++)
								{
									// Note : the data has been stored as [surface][i][j][k][type][f].

									const int shift = surface_shift + i * l1 * l2 * NPOTENS_ * flength_ + j * l2 * NPOTENS_ * flength_ + k * NPOTENS_ * flength_ + pot * flength_ + f;

									bfin.seekg(shift * (sizeof cp), ios_base::beg);
									bfin.read((char *)&cp, sizeof cp);

									bfin_rd.seekg(shift * (sizeof cp_rd), ios_base::beg);
									bfin_rd.read((char *)&cp_rd, sizeof cp_rd);

									bfin_sc.seekg(shift * (sizeof cp_sc), ios_base::beg);
									bfin_sc.read((char *)&cp_sc, sizeof cp_sc);

									double real_phasor = 0.;
									double imag_phasor = 0.;

									double real_phasor_rd = 0.;
									double imag_phasor_rd = 0.;

									double real_phasor_sc = 0.;
									double imag_phasor_sc = 0.;

									real_phasor = cp.sym_real + cp.asm_real * symSign;
									imag_phasor = cp.sym_imag + cp.asm_imag * symSign;

									real_phasor_rd = cp_rd.sym_real + cp_rd.asm_real * symSign;
									imag_phasor_rd = cp_rd.sym_imag + cp_rd.asm_imag * symSign;

									real_phasor_sc = cp_sc.sym_real + cp_sc.asm_real * symSign;
									imag_phasor_sc = cp_sc.sym_imag + cp_sc.asm_imag * symSign;

									// Set the ComplexArrays

									if (pot == OW3DSeakeeping::POTENTIAL_TYPES::PHI)
									{
										phi_(0)[surface](i, j, k) = real_phasor;
										phi_(1)[surface](i, j, k) = imag_phasor;

										phi_rd_(0)[surface](i, j, k) = real_phasor_rd;
										phi_rd_(1)[surface](i, j, k) = imag_phasor_rd;

										phi_sc_(0)[surface](i, j, k) = real_phasor_sc;
										phi_sc_(1)[surface](i, j, k) = imag_phasor_sc;
									}
									else if (pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIX)
									{
										d_phi_dx_(0)[surface](i, j, k) = real_phasor;
										d_phi_dx_(1)[surface](i, j, k) = imag_phasor;

										d_phi_dx_rd_(0)[surface](i, j, k) = real_phasor_rd;
										d_phi_dx_rd_(1)[surface](i, j, k) = imag_phasor_rd;

										d_phi_dx_sc_(0)[surface](i, j, k) = real_phasor_sc;
										d_phi_dx_sc_(1)[surface](i, j, k) = imag_phasor_sc;
									}
									else if (pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIY)
									{
										d_phi_dy_(0)[surface](i, j, k) = real_phasor;
										d_phi_dy_(1)[surface](i, j, k) = imag_phasor;

										d_phi_dy_rd_(0)[surface](i, j, k) = real_phasor_rd;
										d_phi_dy_rd_(1)[surface](i, j, k) = imag_phasor_rd;

										d_phi_dy_sc_(0)[surface](i, j, k) = real_phasor_sc;
										d_phi_dy_sc_(1)[surface](i, j, k) = imag_phasor_sc;
									}
									else if (pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIZ)
									{
										d_phi_dz_(0)[surface](i, j, k) = real_phasor;
										d_phi_dz_(1)[surface](i, j, k) = imag_phasor;

										d_phi_dz_rd_(0)[surface](i, j, k) = real_phasor_rd;
										d_phi_dz_rd_(1)[surface](i, j, k) = imag_phasor_rd;

										d_phi_dz_sc_(0)[surface](i, j, k) = real_phasor_sc;
										d_phi_dz_sc_(1)[surface](i, j, k) = imag_phasor_sc;
									}

								} // k

							} // j

						} // i

					} // End of data type loop

				} // End body surface loop

				// ----------------------------------------------------------------------------------------
				//  NOTE : dphi_dn_ private member function is assigned by calling the following function.
				// ----------------------------------------------------------------------------------------

				ComputeDphiDnOnBody_(omegae, omegao, K, symSign);

				// -------------------------------------------
				// CALCULATE THE WAVE DRIFT FORCE
				// -------------------------------------------------------------------------------------------
				// (* FROM kBar2 to kBar3 ) -> : A proper integral with singular integrands. This turns to
				//                               an integral over [-pi/2,pi/2].
				// NOTE : This interval contributes both for zero-speed and forward-speed cases.
				// -------------------------------------------------------------------------------------------

				for (unsigned int t = 0; t < NTHETA_; t++) // Both for zero-speed (tau = 0) and forward-speed cases.
				{
					double H2[2];
					double theta = Pi * t / (NTHETA_ - 1) - Pi / 2.;							 // (theta = -pi/2 to pi/2).
					double m = 1. / 2 * (kBar3 + kBar2) + 1. / 2 * (kBar3 - kBar2) * sin(theta); // m(theta) = kBar2 to kBar3 (-K to K for zero-speed case)
					double kappaBar = 1 / g_ * (omegae + m * U_) * (omegae + m * U_);
					if (U_ == 0)
						kappaBar = KDeep;

					if (t == 0) // To avoid negative argument in sqrt in the Kochin function (Happens due to round-off error)
					{
						kappaBar = -kBar2;
						m = kBar2;
					}
					else if (t == NTHETA_ - 1) // To avoid negative argument in sqrt in the Kochin function (Happens due to round-off error)
					{
						if (tau < 1. / 4)
							kappaBar = kBar3;
						m = kBar3;
					}

					// -----------------------------------------------------------------------
					// - CALCULATE THE COMPLEX KOCHIN'S FUNCTION FOR "m(theta)" AND "kappaBar"
					// -----------------------------------------------------------------------

					H2[0] = 0.;
					H2[1] = 0.;

					ComputeKochinFunction_(symSign, kappaBar, m, sqrt(kappaBar * kappaBar - m * m), H2);

					if (keep_this_half)
					{
						real_H2_half_kBar2_kBar3.push_back(H2[0]);
						imag_H2_half_kBar2_kBar3.push_back(H2[1]);
					}

					if (!keep_this_half)
					{
						// NOTE : The contribution of the other half of the grid (if any) is added here.

						double real_half = 0., imag_half = 0.;

						if (real_H2_half_kBar2_kBar3.size() != 0)
						{
							real_half = real_H2_half_kBar2_kBar3[t];
							imag_half = imag_H2_half_kBar2_kBar3[t];
						}

						H2[0] += real_half;
						H2[1] += imag_half;

						if (U_ == 0)
							LINE_INTEG_DATA_2[t] = kappaBar * (m - K * cos(betar_)) * (H2[0] * H2[0] + H2[1] * H2[1]);
						else
						{
							double integrand;

							if (t == 0) // Just to remove 0/0 sigularity at this index where kappaBar = -m, and m = kBar2.
							{
								integrand = kappaBar * (m - K * cos(betar_)) * (H2[0] * H2[0] + H2[1] * H2[1]) * sqrt((kBar3 - m) / (kappaBar - m));
							}
							else if (t == NTHETA_ - 1 and tau < 1. / 4) // Just to remove 0/0 sigularity at this index where kappaBar =  m, and m = kBar3.
							{
								integrand = kappaBar * (m - K * cos(betar_)) * (H2[0] * H2[0] + H2[1] * H2[1]) * sqrt((m - kBar2) / (kappaBar + m));
							}
							else
							{
								integrand = kappaBar * (m - K * cos(betar_)) * (H2[0] * H2[0] + H2[1] * H2[1]) * sqrt((m - kBar2) * (kBar3 - m) / ((kappaBar + m) * (kappaBar - m)));
							}

							LINE_INTEG_DATA_2[t] = integrand;
						}
					}

				} // End of loop over integrand's data points

				if (!keep_this_half)
				{
					Rw += IntegrateLineData(
						NTHETA_,
						LINE_INTEG_DATA_2,
						DL2,
						fdC_,
						fdCleft_,
						fdCright_);
				}

			} // End integrals count loop

			forces_farField_(0, f) = -rho_ / (4 * Pi) * Rw;

			// Note : the drift forces are stored in the array as follows:
			//
			// axis 0 ---> :  (0)
			//
			// axis 1 ( 0)     o
			// axis 1 ( 1)     o
			// axis 1 ( 2)     o
			// axis 1 ( 3)     o
			// axis 1 ( 4)     o
			// axis 1 ( 5)     o
			// ......          ...
			//
			// length of axis1 = number of frequencies
			// length of axix0 = 1 ( Just the resistance force )

		} // End of frequency loop

		delete[] LINE_INTEG_DATA_2;

		PrintLogMessage("Far-field wave drift force computed.");

	} // End of wave drift check

} // End of the function.
