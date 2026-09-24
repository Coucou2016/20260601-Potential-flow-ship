// This private member function belongs to the FisrtOrderResults class, and just for
// the sake of convenience is written in a seperate file.

#include "gsl/gsl_sf_expint.h"
#include "FirstOrder.h"

void OW3DSeakeeping::FirstOrder::ComputeForceAnalyticalTransform_(
	ComplexNumbers &analyticalTransform,
	unsigned int runIndex, unsigned int respIndex,
	vector<vector<vector<double>>> ls_fit_coeffs)
{
	// analytical transform is calculated at the corresponding frequencies already specified in
	// the numerical transforms of the relevant signal.

	double a1 = ls_fit_coeffs[runIndex][respIndex][0]; // make a shorter name
	double a2 = ls_fit_coeffs[runIndex][respIndex][1]; // make a shorter name

	for (unsigned int f = 0; f < omegae_.size(); f++) // frequencies
	{
		double xp = (omegae_[f] + transformData_.omegac) * transformData_.analytical_start_time;
		double xn = fabs(omegae_[f] - transformData_.omegac) * transformData_.analytical_start_time;

		int n = 1;
		if (omegae_[f] < transformData_.omegac)
			n = -1;

		gsl_sf_result Cip, Cin, Sip, Sin;

		if (gsl_sf_Ci_e(xp, &Cip) == GSL_SUCCESS and
			gsl_sf_Ci_e(xn, &Cin) == GSL_SUCCESS and
			gsl_sf_Si_e(xp, &Sip) == GSL_SUCCESS and
			gsl_sf_Si_e(xn, &Sin) == GSL_SUCCESS)
		{
			// refer to Bingham, H. B. (1994). Simulating ship motions in the time domain. (Harry's PhD thesis, pp 65-66). (I2 - i * I1)
			analyticalTransform(0, f) = -0.5 * (a2 * (Cip.val + Cin.val) - a1 * (-(Sip.val - Pi / 2) + n * (Sin.val - Pi / 2))) * (1 / simulationData_.print_time_step); // I2 real
			analyticalTransform(1, f) = -0.5 * (a1 * (Cip.val - Cin.val) - a2 * ((Sip.val - Pi / 2) + n * (Sin.val - Pi / 2))) * (1 / simulationData_.print_time_step);	 // I1 imag
		}
		else
		{
			throw runtime_error("Error, OW3DSeakeeping::FirstOrder::ComputeForceAnalyticalTransform_.cpp: Error in evaluation of special functions by gsl library.");
		}
	}
}
