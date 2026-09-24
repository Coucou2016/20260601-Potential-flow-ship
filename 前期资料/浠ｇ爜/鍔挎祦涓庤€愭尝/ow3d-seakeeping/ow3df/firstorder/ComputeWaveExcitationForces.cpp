// This public member function belongs to the FisrtOrder class, and just for
// the convenience is written in this separate file.

// ---------------------------------------------------------------------------------------------------------
//
// NOTE : sym. and ati-sym. components(if any) of the forces are added in the frequency domain.
//        But if the time domain results are printed to file (just for user), then we add these both
//        components in time domain just while printing. The class members for the time domain components
//        will not be changed by this.
//
// ---------------------------------------------------------------------------------------------------------

#include "FirstOrder.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::FirstOrder::ComputeWaveExcitationForces()
{
	if (diffraction_runs_.size() != 0)
	{
		ComputeFrequencyDomainIntegrals_(incidentWavePressure, FroudeKrylov_); // To get Froude-Krylov phasors

		ComputeFrequencyDomainIntegrals_(incidentWaveDphiDx, d_phi0_dx_); // To get dphi0/dx in frequency domain

		ComputeFrequencyDomainIntegrals_(incidentWaveDphiDx, d_phib_phi0_dx_, d_phib_dx_); // To get (dphib/dx * dphi0/dx) in frequency domain

		ComputeFrequencyDomainIntegrals_(incidentWaveDphiDy, d_phib_phi0_dy_, d_phib_dy_); // To get (dphib/dy * dphi0/dy) in frequency domain

		ComputeFrequencyDomainIntegrals_(incidentWaveDphiDz, d_phib_phi0_dz_, d_phib_dz_, "asm"); // To get (dphib/dz * dphi0/dz) in frequency domain

		// ----------------------------------------------------------------------------------------
		//
		// ALL the force terms related to the incident wave potential have been calculated now
		// by the "ComputeFrequencyDomainIntegrals_" function. The complex phasor of these force terms
		// has a symmetric and an antisymmetric component. We calculate them separately, as
		// in the case of the grid symmetry these components must be multiplied by the
		// symmetry coefficients. Note that the scattering force has been already multiplied
		// by these coefficients in the "calculateBodySurfaceForces" public member function.
		// Each component of these force terms itself has a real and an imaginary part, which are
		// calculated separately and stored in an object of the ComplexNumber class. The force is
		// calculated for each response and for the desired frequencies.
		//
		// ----------------------------------------------------------------------------------------

		// Now we calculate the scattering force phasors. Note that
		// the results of the fft is based on the encounter frequency, and the
		// symmetric and anti-symmetric components in the case of grid symmetry
		// are added inside the loop.

		double dt = simulationData_.print_time_step; // Shorter name

		freq_pseudo_elev_.resize(transformData_.size_of_fft); // fft of the pseudo-impulse incident wave elevation

		ComplexNumbers freq_domain_force(transformData_.size_of_fft); // fft of the scattering force due to pseudo-impulse

		Range frequency_range(0, omegaeAll_.size() - 1); // The frequency dependent results are stored over this range

		vector<double> za(2); // If no asymptotic padding is desired

		// ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
		//
		//                      NOTE: the loop over diffraction runs:
		//
		// ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

		unsigned int number_of_responses = UserInput.responses.size();

		for (unsigned int runIndex = 0; runIndex < diffraction_runs_.size(); runIndex++)
		{
			// string fName = input_ -> resultsDirectory + postFolder_ + '/' + "elevation" + "_fft.txt";
			string fName = "";

			Fft_(elevation_, 0, freq_pseudo_elev_, transformData_, dt, za, fName);

			for (unsigned int respIndex = 0; respIndex < number_of_responses; respIndex++)
			{
				// string fileName = input_ -> resultsDirectory + postFolder_ + '/' + diffraction_runs_[runIndex].excitation + "_" + diffraction_runs_[runIndex].response[resp] + "_fft.txt";
				string fileName = "";

				Fft_(diffractionBodyForces_[runIndex], respIndex, freq_domain_force, transformData_, dt, ls_fit_coeffs_scat_[runIndex][respIndex], fileName);

				if (U_ != 0 and gridData_->halfSymmetry and betar_ != 0 and (betar_ < Pi / 2 or betar_ > 3 * Pi / 2)) // Following sea with sym. and anti-sym contributions
				{
					Range to_lim_range(0, FSLimIndex_);								// NOTE : NO DUPLICATION
					Range omeg02_range(FSLimIndex_ + 1, FSLimIndex_ * 2 + 1);		//        AT THE
					Range omeg03_range(FSLimIndex_ * 2 + 2, omegaeAll_.size() - 1); //        BOUNDARIES!

					if (runIndex < 2) // OMEGA01 SYM. AND OMEGA01 ANTI-SYM.
					{
						// NOTE : The sym. and the anti-sym. are added here for the corresponding responses:

						scattering_force_[respIndex](to_lim_range, scattering_force_[respIndex](to_lim_range) + freq_domain_force(to_lim_range) / freq_pseudo_elev_(to_lim_range));
					}
					else if (runIndex < 4) // OMEGA02 SYM. AND OMEGA02 ANTI-SYM.
					{
						ComplexNumbers temp(FSLimIndex_ + 1);
						ComplexNumbers reversedTemp(FSLimIndex_ + 1);

						temp = freq_domain_force(to_lim_range) / freq_pseudo_elev_(to_lim_range);

						for (int i = temp(0).getBase(1); i <= temp(0).getBound(1); i++)
						{
							(reversedTemp(0))(0, i) = (temp(0))(0, temp(0).getBound(1) - i);
							(reversedTemp(1))(1, i) = (temp(1))(1, temp(0).getBound(1) - i);
						}

						// NOTE : The sym. and the anti-sym. are added here for the corresponding responses:

						scattering_force_[respIndex](omeg02_range, scattering_force_[respIndex](omeg02_range) + reversedTemp);
					}
					else // OMEGA03 SYM. AND OMEGA03 ANTI-SYM.
					{
						Range freq_no_0_range(1, omegae_.size() - 1);

						// NOTE : The sym. and the anti-sym. are added here for the corresponding responses:

						scattering_force_[respIndex](omeg03_range, scattering_force_[respIndex](omeg03_range) + freq_domain_force(freq_no_0_range) / freq_pseudo_elev_(freq_no_0_range));
					}
				}

				else if (U_ != 0 and (betar_ < Pi / 2 or betar_ > 3 * Pi / 2)) // Following sea with NO sym. and anti-sym contributions
				{
					Range to_lim_range(0, FSLimIndex_);								// NOTE : NO DUPLICATION
					Range omeg02_range(FSLimIndex_ + 1, FSLimIndex_ * 2 + 1);		//        AT THE
					Range omeg03_range(FSLimIndex_ * 2 + 2, omegaeAll_.size() - 1); //        BOUNDARIES!

					if (runIndex == 0) // OMEGA01 SYM. AND OMEGA01 ANTI-SYM.
					{
						scattering_force_[respIndex](to_lim_range, scattering_force_[respIndex](to_lim_range) + freq_domain_force(to_lim_range) / freq_pseudo_elev_(to_lim_range));
					}
					else if (runIndex == 1) // OMEGA02 SYM. AND OMEGA02 ANTI-SYM.
					{
						ComplexNumbers temp(FSLimIndex_ + 1);
						ComplexNumbers reversedTemp(FSLimIndex_ + 1);

						temp = freq_domain_force(to_lim_range) / freq_pseudo_elev_(to_lim_range);

						for (int i = temp(0).getBase(1); i <= temp(0).getBound(1); i++)
						{
							(reversedTemp(0))(0, i) = (temp(0))(0, temp(0).getBound(1) - i);
							(reversedTemp(1))(1, i) = (temp(1))(1, temp(0).getBound(1) - i);
						}

						scattering_force_[respIndex](omeg02_range, scattering_force_[respIndex](omeg02_range) + reversedTemp);
					}
					else // OMEGA03 SYM. AND OMEGA03 ANTI-SYM.
					{
						Range freq_no_0_range(1, omegae_.size() - 1);

						scattering_force_[respIndex](omeg03_range, scattering_force_[respIndex](omeg03_range) + freq_domain_force(freq_no_0_range) / freq_pseudo_elev_(freq_no_0_range));
					}
				}
				else // All other cases which are not following sea
				{
					// sym. and anti-sym. (if any) are added here for the corresponding responses:

					scattering_force_[respIndex] = scattering_force_[respIndex] + freq_domain_force(frequency_range) / freq_pseudo_elev_(frequency_range);
				}

			} // End of response loop

		} // End of diffraction runs loop ++++

		// Now for the corresponding responses, we just add the scattering phasors with those which are obtained in freq. domain.

		for (unsigned int i = 0; i < scattering_force_.size(); i++)
		{
			excitation_force_[i] = scattering_force_[i] + FroudeKrylov_[i] - U_ * d_phi0_dx_[i] + d_phib_phi0_dx_[i] + d_phib_phi0_dy_[i] + d_phib_phi0_dz_[i];
		}

		if (scattering_force_.size() != 0)
		{
			OW3DSeakeeping::PrintLogMessage("Wave excitation forces computed.");
			exciteCalc_ = true;
		}

	} // End of diffraction check
}

// Note : the complex force array has the following shape for each response direction:
//
//                         real    imag
// axis 0 ---> :            (0)     (1)
//
// axis 1 ( 0) omega(0)      o       o
// axis 1 ( 1) omega(1)      o       o
// axis 1 ( 2) omega(2)      o       o
// axis 1 ( 3) omega(3)      o       o
// axis 1 ( 4) omega(4)      o       o
// axis 1 ( 5) omega(5)      o       o
// ...                       ...
//
