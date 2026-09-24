//
// ------------------------------------------------------------------------------------------------------------
//
// Note : This part of the class is implemented here due to just readability of the main implementation file.
//
//
// This function interpolates the value of the gradient of the incident wave velocity potential at the
// whole time stages for a particular point on the body surface.
//
// The results of the inverse transforms are now stored in "s_ifftData" and "a_ifftData" for symmetric
// and anti-symmetric components respectively.
//
// ------------------------------------------------------------------------------------------------------------

#include "Modes.h"

void OW3DSeakeeping::Diffraction::InterpolateDiffractionBCs_(
	double *s_ifftData,
	double *a_ifftData,
	double *timeVector,
	int n,
	vector<VRealArrays> &bc,
	int surface,
	int i,
	int j,
	int k,
	gsl_interp *interpSym,
	gsl_interp *interpAsy,
	gsl_interp_accel *accel)
{
	double dt = _simulation_data.time_step;

	// initialize the interpolant with the new data for this point (i, j, k)

	gsl_interp_init(interpSym, timeVector, s_ifftData, n);
	gsl_interp_init(interpAsy, timeVector, a_ifftData, n);

	// time loop

	for (int step = 0; step < _simulation_data.step_count; step++) // time-step loop
	{
		for (int stage = 0; stage < rk_stage_count_; stage++)
		{
			double t = (step + rk_c_[stage]) * dt - 0.5 * _simulation_data.sample_time;

			int index = step * rk_stage_count_ + stage;

			if (SymOrAsymOrWhole_ == SymAsymWhole::Whole) // an arbitrary 3d non-symmetric grid or a 2d grid
			{
				bc[index][surface](i, j, k) = gsl_interp_eval(interpSym, timeVector, s_ifftData, t, accel) + gsl_interp_eval(interpAsy, timeVector, a_ifftData, t, accel);
			}

			else if (SymOrAsymOrWhole_ == SymAsymWhole::Sym) // sym. diffraction
			{
				bc[index][surface](i, j, k) = gsl_interp_eval(interpSym, timeVector, s_ifftData, t, accel);
			}

			else // anti-sym. diffraction
			{
				bc[index][surface](i, j, k) = gsl_interp_eval(interpAsy, timeVector, a_ifftData, t, accel);
			}
		}
	}
}
