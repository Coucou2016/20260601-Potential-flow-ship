// This public member function belongs to the SecondOrder class, and just for
// the sake of convenience is written in a seperate file.

#include "SecondOrder.h"
#include "OW3DConstants.h"
#include <iomanip>

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

void OW3DSeakeeping::SecondOrder::ComputeDriftFarFieldDirect_m()
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
			throw runtime_error("Error, OW3DSeakeeping::SecondOrder::ComputeDriftFarFieldDirect_m.cpp: Frequency-domain potential file can not be opened.");
		string bodyFile_rd = results_folder_ + '/' + OW3DSeakeeping::fdomain_potentials_radiation_binary_file; // NOTE : Only radiation potentials
		ifstream bfin_rd(bodyFile_rd, ios_base::in | ios_base::binary);
		if (!bfin_rd.is_open())
			throw runtime_error("Error, OW3DSeakeeping::SecondOrder::ComputeDriftFarFieldDirect_m.cpp: Frequency-domain potential file can not be opened.");
		string bodyFile_sc = results_folder_ + '/' + fdomain_potentials_scattering_binary_file; // NOTE : Only scattering potentials
		ifstream bfin_sc(bodyFile_sc, ios_base::in | ios_base::binary);
		if (!bfin_sc.is_open())
			throw runtime_error("Error, OW3DSeakeeping::SecondOrder::ComputeDriftFarFieldDirect_m.cpp: Frequency-domain potential file can not be opened.");

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

		bool perfrom_first_integral = false;
		bool perfrom_third_integral = false;
		bool Kochin_1_Print = false;
		bool Kochin_2_Print = false;
		bool Kochin_3_Print = false;
		ofstream kochin1_fout, kochin2_fout, kochin3_fout;
		unsigned int freq_index_for_kochin_print = 1;

		if (Kochin_1_Print)
		{
			kochin1_fout.setf(ios_base::scientific);
			kochin1_fout.precision(OW3DSeakeeping::print_precision);
			string filename_H1 = results_folder_ + '/' + UserInput.project_name + ".H1";
			kochin1_fout.open(filename_H1, ios::out);
			kochin1_fout << "The Kochin Function (H1) for the selected frequency" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
		}
		if (Kochin_2_Print)
		{
			kochin2_fout.setf(ios_base::scientific);
			kochin2_fout.precision(OW3DSeakeeping::print_precision);
			string filename_H2 = results_folder_ + '/' + UserInput.project_name + ".H2";
			kochin2_fout.open(filename_H2, ios::out);
			kochin2_fout << "The Kochin Function (H2) for the selected frequency" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
		}
		if (Kochin_3_Print)
		{
			kochin3_fout.setf(ios_base::scientific);
			kochin3_fout.precision(OW3DSeakeeping::print_precision);
			string filename_H3 = results_folder_ + '/' + UserInput.project_name + ".H3";
			kochin3_fout.open(filename_H3, ios::out);
			kochin3_fout << "The Kochin Function (H3) for the selected frequency" + OW3DSeakeeping::print_logo + OW3DSeakeeping::GetTimeString() << '\n';
		}

		// THE FINAL DATA USED FOR THE LINE INTEGRATION
		unsigned int resolution_booster = 15;
		unsigned int NTHETA_1 = resolution_booster * NTHETA_;
		unsigned int NTHETA_3 = resolution_booster * NTHETA_;
		double *LINE_INTEG_DATA_1 = new double[NTHETA_1];
		double *LINE_INTEG_DATA_2 = new double[NTHETA_];
		double *LINE_INTEG_DATA_3 = new double[NTHETA_3];

		vector<double> real_H1_half_mInfy_kBar1, imag_H1_half_mInfy_kBar1; // These are used just in
		vector<double> real_H2_half_kBar2_kBar3, imag_H2_half_kBar2_kBar3; // the case of symmetric
		vector<double> real_H3_half_kBar4_pInfy, imag_H3_half_kBar4_pInfy; // grids in order to save the contributions from other half.

		vector<double> omegaoVector = allKsAndOmegas_.omegao;
		vector<double> omegaeVector = allKsAndOmegas_.omegae;
		vector<double> koVector = allKsAndOmegas_.ko;
		vector<double> koDeepVector = allKsAndOmegas_.koDeep; // NOTE : Only valid for deep water

		double kappa0;
		double kBar1, kBar2, kBar3, kBar4; // The integrations bounds (NOTE : kBar1 and kBar4 are only valid in forward-speed case.)
		const double kNyq = gridData_->kMax;

		// ---------------------------------------------------
		// Frequency loop (Start calculating the drift force)
		// ---------------------------------------------------
		for (unsigned int f = 0; f < flength_; f++)
		{
			double Rw = 0.;						   // The wave drift force initialized to 0 for each frequency
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
				kBar1 = -kappa0 / 2. * (1 + 2 * tau + sqrt(1 + 4 * tau)); // Is always negative
				kBar2 = -kappa0 / 2. * (1 + 2 * tau - sqrt(1 + 4 * tau)); // Is always negative. Also note kBar2 > kBar1.
				if (tau < 1. / 4)
				{
					kBar3 = kappa0 / 2. * (1 - 2 * tau - sqrt(1 - 4 * tau)); // Is always positive
					kBar4 = kappa0 / 2. * (1 - 2 * tau + sqrt(1 - 4 * tau)); // Is always positive. Also note kBar4 > kBar3.
				}
				else if (tau > 1. / 4)
				{
					kBar3 = kappa0 * tau;
					kBar4 = kappa0 * tau;
				}
			}

			if (fabs(kBar2) > kNyq || kBar3 > kNyq)
				continue;

			const double DL1 = (kBar1 + kNyq) / (NTHETA_1 - 1); // Segment's length for integration in [-infty kBar1]
			const double DL2 = (kBar3 - kBar2) / (NTHETA_ - 1); // Segment's length for integration in [kBar2  kBar3]
			const double DL3 = (kNyq - kBar4) / (NTHETA_3 - 1); // Segment's length for integration in [kBar4  infty]

			// The following vectors must be cleared in
			// order to be ready for the next frequency.

			real_H1_half_mInfy_kBar1.clear();
			imag_H1_half_mInfy_kBar1.clear();

			real_H2_half_kBar2_kBar3.clear();
			imag_H2_half_kBar2_kBar3.clear();

			real_H3_half_kBar4_pInfy.clear();
			imag_H3_half_kBar4_pInfy.clear();

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
					throw runtime_error("Error, OW3DSeakeeping::SecondOrder::ComputeDriftFarFieldDirect_m.cpp: The type of radiation run can not be recognized.");
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
				// -------------------------------------------

				if (U_ != 0 && fabs(kBar1) < kNyq && perfrom_first_integral) // Just in the case of forward-speed problems.
				{
					double H1[2];
					H1[0] = 0.;
					H1[1] = 0.;
					// ------------------------------------------------------------------------------------------------------
					// (* FROM mInfy to kBar1 ) -> : The first improper integral with singular integrands.
					//  NOTE : This interval contributes to the solution regardless of tau. Its upper bound is always kBar1.
					// ------------------------------------------------------------------------------------------------------
					for (unsigned int t = 0; t < NTHETA_1; t++)
					{
						double m = DL1 * t - kNyq;
						double kappaBar = 1 / g_ * (omegae + m * U_) * (omegae + m * U_);
						ComputeKochinFunction_(symSign, kappaBar, m, sqrt(kappaBar * kappaBar - m * m), H1); // NOTE : Results are stored in H1[0] (real) and H1[1] (imaginary)

						if (keep_this_half)
						{
							real_H1_half_mInfy_kBar1.push_back(H1[0]);
							imag_H1_half_mInfy_kBar1.push_back(H1[1]);
						}
						if (!keep_this_half)
						{
							// NOTE : The contribution of the other half of the grid (if any) is added here.

							double real_half = 0., imag_half = 0.;

							if (real_H1_half_mInfy_kBar1.size() != 0)
							{
								real_half = real_H1_half_mInfy_kBar1[t];
								imag_half = imag_H1_half_mInfy_kBar1[t];
							}

							H1[0] += real_half;
							H1[1] += imag_half;

							LINE_INTEG_DATA_1[t] = kappaBar * (m - K * cos(betar_)) * (H1[0] * H1[0] + H1[1] * H1[1]) / sqrt((kappaBar + m) * (kappaBar - m));
							if (f == freq_index_for_kochin_print && Kochin_1_Print)
								kochin1_fout << m << setw(OW3DSeakeeping::print_width) << sqrt(H1[0] * H1[0] + H1[1] * H1[1]) << endl;
						}

					} // End of loop over integrand's data points

					if (!keep_this_half)
						Rw = -IntegrateLineDataBo(NTHETA_1, LINE_INTEG_DATA_1, DL1, fdC_, fdCleft_, fdCright_);
				}

				if (U_ != 0 && kBar4 < kNyq && perfrom_third_integral)
				{
					// ------------------------------------------------------------------------------------------------------------------------------
					// (* FROM kBar4 to pInfy) -> : The second improper integral with singular integrands.
					//  NOTE : This interval contributes to the solution regardless of tau. Its lower bound is kBar4. When tau > 1/4 kBar4 = kBar3.
					// ------------------------------------------------------------------------------------------------------------------------------

					for (unsigned int t = 0; t < NTHETA_3; t++)
					{
						double H3[2];
						H3[0] = 0.;
						H3[1] = 0.;
						double m = DL3 * t + kBar4;
						double kappaBar = 1 / g_ * (omegae + m * U_) * (omegae + m * U_);
						ComputeKochinFunction_(symSign, kappaBar, m, sqrt(kappaBar * kappaBar - m * m), H3);
						if (keep_this_half)
						{
							real_H3_half_kBar4_pInfy.push_back(H3[0]);
							imag_H3_half_kBar4_pInfy.push_back(H3[1]);
						}

						if (!keep_this_half)
						{
							// NOTE : The contribution of the other half of the grid (if any) is added here.

							double real_half = 0., imag_half = 0.;

							if (real_H3_half_kBar4_pInfy.size() != 0)
							{
								real_half = real_H3_half_kBar4_pInfy[t];
								imag_half = imag_H3_half_kBar4_pInfy[t];
							}
							H3[0] += real_half;
							H3[1] += imag_half;

							LINE_INTEG_DATA_3[t] = kappaBar * (m - K * cos(betar_)) * (H3[0] * H3[0] + H3[1] * H3[1]) / sqrt((kappaBar + m) * (kappaBar - m));
							if (f == freq_index_for_kochin_print && Kochin_3_Print)
								kochin3_fout << m << setw(OW3DSeakeeping::print_width) << sqrt(H3[0] * H3[0] + H3[1] * H3[1]) << endl;
						}

					} // End of loop over integrand's data points

					if (!keep_this_half)
						Rw += IntegrateLineDataBo(NTHETA_3, LINE_INTEG_DATA_3, DL3, fdC_, fdCleft_, fdCright_);

				} // End of forward-speed check

				// -------------------------------------------------------------------------------------------
				// (* FROM kBar2 to kBar3 ) -> : A proper integral with singular integrands.
				// NOTE : This interval contributes both for zero-speed and forward-speed cases.
				// -------------------------------------------------------------------------------------------

				for (unsigned int t = 0; t < NTHETA_; t++) // Both for zero-speed (tau = 0) and forward-speed cases.
				{
					double H2[2];
					H2[0] = 0.;
					H2[1] = 0.;

					double m = DL2 * t + kBar2;
					double kappaBar = (U_ == 0) ? KDeep : 1 / g_ * (omegae + m * U_) * (omegae + m * U_);

					// -----------------------------------------------------------------------
					// - CALCULATE THE COMPLEX KOCHIN'S FUNCTION FOR "m(theta)" AND "kappaBar"
					// -----------------------------------------------------------------------

					ComputeKochinFunction_(symSign, kappaBar, m, sqrt(kappaBar * kappaBar - m * m), H2); // NOTE : Results are stored in H2[0] (real) and H2[1] (imaginary)

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

						LINE_INTEG_DATA_2[t] = kappaBar * (m - K * cos(betar_)) * (H2[0] * H2[0] + H2[1] * H2[1]) / sqrt((kappaBar + m) * (kappaBar - m));
						if (f == freq_index_for_kochin_print && Kochin_2_Print)
							kochin2_fout << m << setw(OW3DSeakeeping::print_width) << sqrt(H2[0] * H2[0] + H2[1] * H2[1]) << endl;
					}

				} // End of loop over integrand's data points

				if (!keep_this_half)
					Rw += IntegrateLineDataBo(NTHETA_, LINE_INTEG_DATA_2, DL2, fdC_, fdCleft_, fdCright_);

			} // End integrals count loop

			forces_farField_(0, f) = rho_ / (4 * Pi) * Rw;

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
