// This public member function belongs to the FisrtOrder class, and just for
// the convenience is written in a separate file.

#include "FirstOrder.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::FirstOrder::BuildFrequenciesAndWaveNumbers()
{
	if (resistance_runs_.size() == 0)
	{
		if (!transformSupplied_ or !motionSupplied_)
		{
			throw runtime_error("Error, OW3DSeakeeping::FirstOrder::BuildFrequenciesAndWaveNumbers.cpp: Transform or Motion data has not been provided.");
		}

		// ------------------------------------------------------------------------------------------------------------------------
		//
		// NOTE : In this file we assign the frequencies and the wave numbers based on the size of
		//        fft and sampling rate. Note that in our work, the fft is defined with respect to the encounter frequency. First
		//        the encounter frequencies are assigned based on the simulation data. The wave numbers are assigned only for the
		//        diffraction problems. In these case, the distinction is made between the following-seas and and the beam-seas
		//        situations.
		//
		// -----------------------------------------------------------------

		// ------------------------------------------------------------------------
		// Build the absolute encounter frequencies using the simulation data:
		// ------------------------------------------------------------------------

		double dt = simulationData_.print_time_step; // just
		double sampling_rate = 1.0 / dt;			 // make shorter
		double h = gridData_->maximum_depth;		 // names
		double mwl = 0.1;							 // Change this ASAP

		double f = 0.0, i = 0.0;
		vector<double> fr;

		// NOTE : The maximum frequency is defined based on the minimum resolvable wavelength.(Look in to Modes.cpp).
		while (f <= simulationData_.maximum_frequency / OW3DSeakeeping::max_freq_divisor)
		{
			fr.push_back(f);
			i++;
			f = i / transformData_.size_of_fft * sampling_rate;

			if (i >= transformData_.size_of_fft / 2)
			{
				throw runtime_error("Error, OW3DSeakeeping::FirstOrder::BuildFrequenciesAndWaveNumbers.cpp: Something strange happened while assigning the frequencies!.");
			}
		}

		// ------------------------------------------------
		// Build the angular encounter frequencies :
		// ------------------------------------------------

		omegaeArray_.resize(1, fr.size());

		for (unsigned int p = 0; p < fr.size(); p++)
		{
			omegae_.push_back(2 * Pi * fr[p]);

			omegaeArray_(0, p) = 2 * Pi * fr[p];
		}

		allKsAndOmegas_.omegae = omegae_;
		allKsAndOmegas_.omegaeArray = omegaeArray_;

		if (diffraction_runs_.size() == 0)
		{
			omegaeAll_ = omegae_;
			omegao_ = omegae_;
			allKsAndOmegas_.omegaeAll = omegaeAll_;
		}

		//
		// NOTE : the encounter frequency arrays is arranged as follows:
		//
		// axis 0 ---> :   ( 0)
		//
		// axis 1 ( 0)   omegaeArray(0,0)
		// axis 1 ( 1)   omegaeArray(0,1)
		// axis 1 ( 2)   omegaeArray(0,2)
		// axis 1 ( 3)   omegaeArray(0,3)
		// axis 1 ( 4)   omegaeArray(0,4)
		// axis 1 ( 5)   omegaeArray(0,5)
		// .......       ........
		//
		//

		// ------------------------------------------------------------------------------
		// NOTE : First the wave numbers for the following-seas cases are built.
		//        Also note that the wave numbers and the wave frequencies are
		//        defined only for the diffraction problems. For the radiation problems
		//        only encounter frequencies are defined. In the zero-speed case
		//        the wave frequency and the encounter frequency will be the same.
		//        Also note that the wave number "ko" and the wave frequency "omegao"
		//        are defined only for the diffraction problems. For the radiation
		//        problems only the encounter frequency is justified to be defined.
		// -------------------------------------------------------------------------------

		if (U_ != 0 and (betar_ < Pi / 2 or betar_ > 3 * Pi / 2) and diffraction_runs_.size() != 0)
		{
			FSK0lim_ = GetFSK0lim(0, h_, mwl_, betar_, U_, g_, 1e10); // The limit wave number;

			FSOmegaec_ = g_ * tanh(FSK0lim_ * h_) / (4 * U_ * cos(betar_)); // The encounter frequency at the this limit

			double k01, k02, k03;

			for (unsigned int p = 0; p < fr.size(); p++)
			{
				if (omegae_[p] <= FSOmegaec_)
				{
					if (omegae_[p] == 0)
					{
						k01 = 0.;
					}
					else
					{
						k01 = GetFSK01(omegae_[p], h_, FSK0lim_, betar_, U_, g_, 1e10);
					}

					k02 = GetFSK02(omegae_[p], h_, FSK0lim_, betar_, U_, g_, 1e10);
					k03 = GetFSK03(omegae_[p], h_, FSK0lim_, betar_, U_, g_, 1e10);

					k01_.push_back(k01);
					k02_.push_back(k02);
					k03_.push_back(k03);

					omega01_.push_back(sqrt(g_ * k01 * tanh(k01 * h))); // 0                             <= OMEGA0 <= g tanh(kh) / (2 U cos(beta) )
					omega02_.push_back(sqrt(g_ * k02 * tanh(k02 * h))); // g tanh(kh) / (2 U cos(beta) ) <= OMEGA0 <= g tanh(kh) / (  U cos(beta) )
					omega03_.push_back(sqrt(g_ * k03 * tanh(k03 * h))); // g tanh(kh) / (2 U cos(beta) ) <= OMEGA0 <= g tanh(kh) / (  U cos(beta) )

					omegaeAll_.push_back(omegae_[p]);
				}
				else
				{
					k03 = GetFSK03(omegae_[p], h_, FSK0lim_, betar_, U_, g_, 1e10);
					k03_.push_back(k03);
					omega03_.push_back(sqrt(g_ * k03 * tanh(k03 * h))); // g tanh(kh) / ( U cos(beta) ) < OMEGA0 <= .....
				}
			}

			// ------------------------------------------------
			// FIND THE INDEX WHERE OMEGA01 AND OMEGA02 MEET
			// ------------------------------------------------

			FSLimIndex_ = 0;

			int tempIndex = 0;

			while (omegae_[tempIndex] <= FSOmegaec_)
			{
				tempIndex++;
				if (tempIndex == omegae_.size())
					break;
			}

			FSLimIndex_ = tempIndex - 1;

			if (FSLimIndex_ > fr.size() - 1)
				FSLimIndex_ = fr.size() - 1;

			// NOTE : In the above case the encounter frequency at the limit is
			//        larger than maximum resolvable frequency based on the grid resolution.

			allKsAndOmegas_.FSLimIndex = FSLimIndex_;

			// -----------------------------------------------------
			//  REVERSE THE k02 and omega02 vectors
			// -----------------------------------------------------

			std::reverse(k02_.begin(), k02_.end());
			std::reverse(omega02_.begin(), omega02_.end());

			// ------------------------------------------------------
			// CONCATENATE THE VECTORS CONTAINING THE WAVE NUMBERS
			// ------------------------------------------------------

			ko_.insert(ko_.begin(), k01_.begin(), k01_.end());
			ko_.insert(ko_.end(), k02_.begin(), k02_.end());
			ko_.insert(ko_.end(), k03_.begin() + 1, k03_.end());

			omegao_.insert(omegao_.begin(), omega01_.begin(), omega01_.end());
			omegao_.insert(omegao_.end(), omega02_.begin(), omega02_.end());
			omegao_.insert(omegao_.end(), omega03_.begin() + 1, omega03_.end());

			// -----------------------------------------------------------
			// CONCATENATE ALL ENCOUNTER FREQUENCIES IN A SINGLE VECTOR
			// -----------------------------------------------------------

			vector<double> tempVec;

			tempVec = omegaeAll_;

			std::reverse(tempVec.begin(), tempVec.end());

			omegaeAll_.insert(omegaeAll_.end(), tempVec.begin(), tempVec.end());
			omegaeAll_.insert(omegaeAll_.end(), omegae_.begin() + 1, omegae_.end());

			// ------------------------------------------------------------
			// PUT ALL K's and OMEGA's in to "allKsAndOmegas_" variable
			// -----------------------------------------------------------

			allKsAndOmegas_.k01 = k01_;
			allKsAndOmegas_.k02 = k02_;
			allKsAndOmegas_.k03 = k03_;

			allKsAndOmegas_.omega01 = omega01_;
			allKsAndOmegas_.omega02 = omega02_;
			allKsAndOmegas_.omega03 = omega03_;

			allKsAndOmegas_.FSK0lim = FSK0lim_;
			allKsAndOmegas_.FSOmegaec = FSOmegaec_;

			allKsAndOmegas_.omegaeAll = omegaeAll_;
			allKsAndOmegas_.omegao = omegao_; // NOTE : These 3 lines are added as a quick fix only to perform
			allKsAndOmegas_.ko = ko_;		  //        test 4 which is related to following-seas added resistance.
			allKsAndOmegas_.koDeep = ko_;	  //        The correct values of these frequencies and wave numbers must be checked.

		} // End of following-seas block

		// ----------------------------------------------------
		// ALL DIFFRACTION CASES OTHER THAN FOLLOWING-SEAS CAES
		// ----------------------------------------------------

		else if (diffraction_runs_.size() != 0)
		{
			omegao_.resize(fr.size());
			koDeep_.resize(fr.size());

			ko_.resize(fr.size());
			ko_[0] = 0.;

			for (unsigned int p = 0; p < fr.size(); p++)
			{
				if (p != 0)
				{
					ko_[p] = Wavenumber(omegae_[p], h, mwl, betar_, U_, g_);

					omegao_[p] = sqrt(g_ * ko_[p] * tanh(ko_[p] * h));

					koDeep_[p] = WavenumberDeep(omegae_[p], h, mwl, betar_, U_, g_);
				}
			}

			omegaeAll_ = omegae_;

			allKsAndOmegas_.ko = ko_;
			allKsAndOmegas_.omegao = omegao_;
			allKsAndOmegas_.koDeep = koDeep_;

			allKsAndOmegas_.omegaeAll = omegaeAll_;

		} // End of head-seas diffraction block

		// --------------------------------------------------------------
		//
		// Initialize the frequency-domain vectors required for the
		// diffraction problems based on the size of desired frequencies
		//
		// --------------------------------------------------------------

		if (diffraction_runs_.size() != 0)
		{
			for (unsigned int s = 0; s < UserInput.responses.size(); s++)
			{
				// NOTE : IN THE CASE OF FOLLOWING SEAS, "omegaeAll_" IS
				//        THE CONCATENATED VECTOR INCLUDING ALL THREE REGIONS
				//        FOR THE WAVE FREQUENCIES.

				ComplexNumbers temp(omegaeAll_.size()); // YES!. Both real and imag. part are zero initialized.

				FroudeKrylov_.push_back(temp);
				scattering_force_.push_back(temp);
				excitation_force_.push_back(temp);
				if (UserInput.solve_motion)
					RAO_.push_back(temp);
				d_phi0_dx_.push_back(temp);
				d_phib_phi0_dx_.push_back(temp);
				d_phib_phi0_dy_.push_back(temp);
				d_phib_phi0_dz_.push_back(temp);
			}
		}

		std::vector<double>::iterator low = std::upper_bound(omegaeAll_.begin(), omegaeAll_.end(), simulationData_.minimum_frequency);
		if (!min_freq_print_index_option)
			allKsAndOmegas_.out_start_index = low - omegaeAll_.begin();
		else
			allKsAndOmegas_.out_start_index = min_freq_print_index_option;

		OW3DSeakeeping::PrintLogMessage("Vectors of frequencies and wave numbers are built.");

	} // End of the resistance!
}