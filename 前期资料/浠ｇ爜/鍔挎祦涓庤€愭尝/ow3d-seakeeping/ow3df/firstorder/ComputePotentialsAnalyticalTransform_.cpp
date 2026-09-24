// This private member function belongs to the FisrtOrderResults class, and just for
// the sake of convenience is written in a seperate file.

#include "gsl/gsl_sf_expint.h"
#include "FirstOrder.h"

void OW3DSeakeeping::FirstOrder::ComputePotentialsAnalyticalTransform_(
	double *re, double *im,
	double *cofs)
{
	// analytical transform is calculated at the corresponding frequencies already specified in
	// the numerical transforms of the relevant signal.

	Range frequency_range(0, omegae_.size() - 1);

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
			re[f] = -0.5 * (cofs[1] * (Cip.val + Cin.val) - cofs[0] * (-(Sip.val - Pi / 2) + n * (Sin.val - Pi / 2))); // I2 real
			im[f] = -0.5 * (cofs[0] * (Cip.val - Cin.val) - cofs[1] * ((Sip.val - Pi / 2) + n * (Sin.val - Pi / 2)));  // I1 imag
		}
		else
		{
			throw runtime_error("Error, OW3DSeakeeping::FirstOrder::ComputePotentialsAnalyticalTransform_.cpp: Error in evaluation of special functions by gsl library.");
		}
	}
}
