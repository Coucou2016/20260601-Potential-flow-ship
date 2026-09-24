// This public member function belongs to the FisrtOrderResults class, and just for
// the convenience is written in a seperate file.

#include "FirstOrder.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::FirstOrder::ExtendFollowingSeasHydros_(RealArray &a, RealArray &b)
{
	if ((betar_ < Pi / 2 or betar_ > 3 * Pi / 2) and U_ != 0 and UserInput.dif_runs.size() != 0)
	{
		unsigned int number_of_responses = UserInput.responses.size();
		unsigned int number_of_frequencies = omegae_.size();
		Range all;
		a.resize(number_of_responses, omegaeAll_.size());
		b.resize(number_of_responses, omegaeAll_.size());

		Range R3(FSLimIndex_ * 2 + 2, omegaeAll_.size() - 1);
		Range rg(1, number_of_frequencies - 1);

		for (unsigned int resp = 0; resp < number_of_responses; resp++)
		{
			RealArray temp_a = a(resp, all);
			RealArray temp_b = b(resp, all);

			for (unsigned int i = 0; i <= FSLimIndex_; i++)
			{
				a(resp, i + FSLimIndex_ + 1) = temp_a(resp, FSLimIndex_ - i);
				b(resp, i + FSLimIndex_ + 1) = temp_b(resp, FSLimIndex_ - i);
			}

			a(resp, R3) = temp_a(resp, rg);
			b(resp, R3) = temp_b(resp, rg);
		}
	}
}

void OW3DSeakeeping::FirstOrder::ComputeHydrodynamicCoefficients()
{
	if (radiation_runs_.size() != 0 || gmodes_runs_.size() != 0)
	{
		if (!forceCalc_)
			throw runtime_error("Error, OW3DSeakeeping::FirstOrder::ComputeHydrodynamicCoefficients.cpp: Force has not been calculated yet.");

		// Calsulate added mass and damping

		unsigned int number_of_frequencies = omegae_.size(); // make shorter
		double dt = simulationData_.print_time_step;		 // names

		freq_pseudo_disp_.resize(transformData_.size_of_fft); // fft of the pseudo-impulse displacement brought to the body

		ComplexNumbers freq_domain_force(transformData_.size_of_fft); // fft of the radiation force due to pseudo-impulse
		ComplexNumbers force_analytical_transform(number_of_frequencies);
		ComplexNumbers ratio(number_of_frequencies);

		Range frequency_range(0, omegae_.size() - 1); // the frequency dependent results are stored over this range
		vector<double> za(2);						  // if no asymptotic padding is desired
		Range all;

		Fft_(displacement_, 0, freq_pseudo_disp_, transformData_, dt, za, "");

		// ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
		//                 Loop Over Radiation Runs
		// ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

		unsigned int number_of_responses = UserInput.responses.size(); // make a shorter name

		for (unsigned int runIndex = 0; runIndex < radiation_runs_.size(); runIndex++)
		{
			RealArray a(number_of_responses, number_of_frequencies); // added mass
			RealArray b(number_of_responses, number_of_frequencies); // damping

			for (unsigned int respIndex = 0; respIndex < number_of_responses; respIndex++)
			{
				Fft_(radiationBodyForces_[runIndex], respIndex, freq_domain_force, transformData_, dt, ls_fit_coeffs_rad_[runIndex][respIndex], "");

				if (U_ != 0)
					ComputeForceAnalyticalTransform_(force_analytical_transform, runIndex, respIndex, ls_fit_coeffs_rad_);

				ratio = (freq_domain_force(frequency_range) + force_analytical_transform) / freq_pseudo_disp_(frequency_range);

				a(respIndex, frequency_range) = ratio(0) / pow(omegaeArray_, 2); // real part (added mass)
				b(respIndex, frequency_range) = -ratio(1) / omegaeArray_;		 // imag part (damping)

			} // End of loop over responses.

			ExtendFollowingSeasHydros_(a, b); // Extend the added mass and the damping arrays for the following-sea cases
			addedMass_.push_back(a);
			damping_.push_back(b);
			OW3DSeakeeping::PrintLogMessage("Hydrodynamic coefficients computed for " + OW3DSeakeeping::ModeStrings.at(radiation_runs_[runIndex].mode));

		} // End of loop over radiation runs ++++

		// ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
		//                 Loop Over Generalized Modes Runs
		// ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

		for (unsigned int runIndex = 0; runIndex < gmodes_runs_.size(); runIndex++)
		{
			RealArray a(number_of_responses, number_of_frequencies); // added mass
			RealArray b(number_of_responses, number_of_frequencies); // damping

			for (unsigned int respIndex = 0; respIndex < number_of_responses; respIndex++)
			{
				Fft_(gmodesBodyForces_[runIndex], respIndex, freq_domain_force, transformData_, dt, ls_fit_coeffs_gmod_[runIndex][respIndex], "");

				if (U_ != 0)
					ComputeForceAnalyticalTransform_(force_analytical_transform, runIndex, respIndex, ls_fit_coeffs_gmod_);

				ratio = (freq_domain_force(frequency_range) + force_analytical_transform) / freq_pseudo_disp_(frequency_range);

				a(respIndex, frequency_range) = ratio(0) / pow(omegaeArray_, 2); // real part (added mass)
				b(respIndex, frequency_range) = -ratio(1) / omegaeArray_;		 // imag part (damping)

			} // End of loop over responses.

			ExtendFollowingSeasHydros_(a, b); // Extend the added mass and the damping arrays for the following-sea cases
			gmodes_addedMass_.push_back(a);
			gmodes_damping_.push_back(b);
			addedMass_.push_back(a);
			damping_.push_back(b);

			OW3DSeakeeping::PrintLogMessage("Hydrodynamic coefficients computed for " + OW3DSeakeeping::ModeStrings.at(gmodes_runs_[runIndex].mode));

		} // End of loop over gmodes runs ++++

		hydroCalc_ = true;

	} // end of radiation check
}

// note : hydrodynamic coefficient array for one specific excitation has a shape as follows:
//
//                      response(0) response(1) response(2) ...
// axis 0 ---> :           (0)         (1)         (2)
//
// axis 1 ( 0)  omega(0)    o           o           o   ...
// axis 1 ( 1)  omega(1)    o           o           o   ...
// axis 1 ( 2)  omega(2)    o           o           o   ...
// axis 1 ( 3)  omega(3)    o           o           o   ...
// axis 1 ( 4)  omega(4)    o           o           o   ...
// axis 1 ( 5)  omega(5)    o           o           o   ...
// ...
// ...
