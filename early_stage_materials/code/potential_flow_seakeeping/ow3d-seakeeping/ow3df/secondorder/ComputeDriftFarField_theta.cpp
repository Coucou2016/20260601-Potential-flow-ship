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

void OW3DSeakeeping::SecondOrder::ComputeDriftFarField_theta()
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
			throw runtime_error("Error, OW3DSeakeeping::SecondOrder::ComputeDriftFarField_theta.cpp: Frequency-domain potential file can not be opened.");

		// ---------------------------------------------
		// Data initializations
		// ----------------------------------------------

		struct comp
		{
			double sym_real;
			double sym_imag;
			double asm_real;
			double asm_imag;

		} cp; // The frequency domain data is stored in this variable.

		// THE FINAL DATA USED FOR THE LINE INTEGRATION

		double *LINE_INTEG_DATA = new double[NTHETA_];
		vector<double> real_HK2_half_th0_2pi, imag_HK2_half_th0_2pi;
		vector<double> omegaoVector = allKsAndOmegas_.omegao;
		vector<double> omegaeVector = allKsAndOmegas_.omegae;
		vector<double> koVector = allKsAndOmegas_.ko;

		// ---------------------------------------------------
		// Frequency loop (Start calculating the drift force)
		// ---------------------------------------------------

		for (unsigned int f = 0; f < flength_; f++)
		{
			double Rw = 0.; // The wave drift force initialized to 0 for each frequency

			const double omegao = omegaoVector[f];
			const double omegae = omegaeVector[f]; // ENCOUNTER FREQUENCY
			const double K = koVector[f];		   // WAVE NUMBER

			double th0 = 0.;
			const double OMEGA = U_ * omegae / g_;

			if (OMEGA > 1. / 4.)
				th0 = acos(1. / (4 * OMEGA));

			const double kappa_0 = g_ / (U_ * U_);
			const double DTheta = (2 * Pi - 2 * th0) / (NTHETA_ - 1); // Segment's length for  theta0 to 2*pi-theta0

			real_HK2_half_th0_2pi.clear(); //
			imag_HK2_half_th0_2pi.clear(); //

			// Assign the response amplitude operators.

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
					throw runtime_error("Error, OW3DSeakeeping::SecondOrder::ComputeDriftFarField_theta.cpp: The type of radiation run can not be recognized.");
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
					// The shift due to the previous surfaces
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

									int shift = surface_shift + i * l1 * l2 * NPOTENS_ * flength_ + j * l2 * NPOTENS_ * flength_ + k * NPOTENS_ * flength_ + pot * flength_ + f;

									bfin.seekg(shift * (sizeof cp), ios_base::beg);
									bfin.read((char *)&cp, sizeof cp);

									double real_phasor = 0.;
									double imag_phasor = 0.;

									real_phasor = cp.sym_real + cp.asm_real * symSign;
									imag_phasor = cp.sym_imag + cp.asm_imag * symSign;

									// Set the ComplexArrays

									if (pot == OW3DSeakeeping::POTENTIAL_TYPES::PHI)
									{
										phi_(0)[surface](i, j, k) = real_phasor;
										phi_(1)[surface](i, j, k) = imag_phasor;
									}
									else if (pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIX)
									{
										d_phi_dx_(0)[surface](i, j, k) = real_phasor;
										d_phi_dx_(1)[surface](i, j, k) = imag_phasor;
									}
									else if (pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIY)
									{
										d_phi_dy_(0)[surface](i, j, k) = real_phasor;
										d_phi_dy_(1)[surface](i, j, k) = imag_phasor;
									}
									else if (pot == OW3DSeakeeping::POTENTIAL_TYPES::PHIZ)
									{
										d_phi_dz_(0)[surface](i, j, k) = real_phasor;
										d_phi_dz_(1)[surface](i, j, k) = imag_phasor;
									}

								} // k

							} // j

						} // i

					} // End of data type loop

				} // End body surface loop

				ComputeDphiDnOnBody_(omegae, omegao, K, symSign);

				// -------------------------------------------
				// CALCULATE THE WAVE DRIFT FORCE
				// FROM (THETA0) TO (2*PI) - (THETA0)
				// -----------------------------------

				for (unsigned int t = 0; t < NTHETA_; t++)
				{
					double theta = 2 * (Pi - th0) * t / (NTHETA_ - 1) + th0;
					double kappa_2 = K;

					if (U_ != 0)
						kappa_2 = kappa_0 * (1 - 2 * OMEGA * cos(theta) - sqrt(1 - 4 * OMEGA * cos(theta))) / (2 * cos(theta) * cos(theta));

					// CALCULATE THE COMPLEX KOCHIN'S FUNCTION FOR "theta" AND "kappa_2"

					double HK_2[2];

					HK_2[0] = 0.;
					HK_2[1] = 0.;

					ComputeKochinFunction_(symSign, kappa_2, kappa_2 * cos(theta), kappa_2 * sin(theta), HK_2);
					if (keep_this_half)
					{
						real_HK2_half_th0_2pi.push_back(HK_2[0]);
						imag_HK2_half_th0_2pi.push_back(HK_2[1]);
					}
					if (!keep_this_half)
					{
						// NOTE : The contribution of the other half of the grid is added here (if any).
						double real_half = 0., imag_half = 0.;
						if (real_HK2_half_th0_2pi.size() != 0)
						{
							real_half = real_HK2_half_th0_2pi[t];
							imag_half = imag_HK2_half_th0_2pi[t];
						}

						HK_2[0] += real_half;
						HK_2[1] += imag_half;
						LINE_INTEG_DATA[t] = (HK_2[0] * HK_2[0] + HK_2[1] * HK_2[1]) * kappa_2 * (kappa_2 * cos(theta) - K * cos(betar_)) / sqrt(1 - 4 * OMEGA * cos(theta));
					}

				} // End of theta loop * * * * *

				if (!keep_this_half)
				{
					Rw += IntegrateLineDataBo(
						NTHETA_,
						LINE_INTEG_DATA,
						DTheta,
						fdC_,
						fdCleft_,
						fdCright_);

					forces_farField_(0, f) = rho_ / (8 * Pi) * Rw;
				}

			} // End integrals count loop

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

		delete[] LINE_INTEG_DATA;

	} // End of wave drift check
}