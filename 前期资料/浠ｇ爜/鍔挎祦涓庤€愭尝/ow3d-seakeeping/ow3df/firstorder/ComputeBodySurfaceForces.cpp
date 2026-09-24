// This public member function belongs to the FirstOrder class, and just for
// the sake of convenience is written in a seperate file.

#include "FirstOrder.h"
#include "Field.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::FirstOrder::ComputeBodySurfaceForces()
{
	unsigned int steps = simulationData_.print_step_count;

	double gamma_Timo = OW3DSeakeeping::gamma_Timo;
	double gamma_square = pow(gamma_Timo, 2);

	OW3DSeakeeping::Field::integrals_n integsn;

	// open the binary file

	string filename = time_domain_folder_ + '/' + OW3DSeakeeping::tdomain_body_integrals_binary_file;
	ifstream fbin(filename, ios_base::in | ios_base::binary);

	if (!fbin.is_open())
		throw runtime_error("Error, OW3DSeakeeping::FirstOrder::ComputeBodySurfaceForces.cpp: File for the force data can not be opened.");

	// NOTE : this function calculates the first-order forces using the Bernoulli
	// equation. The integration of the pressure terms has already been carried out
	// while solving the hydrodynamic problems by "RUN" program. In this function first the
	// pressure term (d_phiu_dt) is calculated by the differencing scheme. Then other pressure
	// terms will be added to get the final force. These operations are performed based on a loop
	// over the number of runs. Each time the total forces for all responses of a run are
	// calculated.

	unsigned int respo_size = UserInput.responses.size(); // just shorter name

	for (unsigned int run = 0; run < allRuns_.size(); run++)
	{
		MODE_NAMES mode_name = allRuns_[run].mode; // just shorter name

		// find the correct value for the shift
		// based on the number of the runs and the
		// corresponding responses. Note that each run may have
		// a different number of responses.

		int runs_shift = 0;
		for (int back = run; back > 0; back--)
			runs_shift += respo_size * steps;

		Bernoulli bernoulliTerm;

		bernoulliTerm.phiu_n.resize(respo_size, steps);
		bernoulliTerm.d_phiu_dx_n.resize(respo_size, steps);
		bernoulliTerm.d_phib_dx_n.resize(respo_size, steps);
		bernoulliTerm.d_phiu_dxx_n.resize(respo_size, steps);
		bernoulliTerm.grad_phiu_grad_phib_n.resize(respo_size, steps);
		bernoulliTerm.grad_phiu_grad_phiu_n.resize(respo_size, steps);
		bernoulliTerm.grad_phib_grad_phib_n.resize(respo_size, steps);

		for (unsigned int t = 0; t < steps; t++)
		{
			for (unsigned int respo = 0; respo < respo_size; respo++)
			{
				int shift = runs_shift + t * respo_size + respo;

				fbin.seekg(shift * (sizeof integsn), ios_base::beg);
				fbin.read((char *)&integsn, sizeof integsn);

				bernoulliTerm.phiu_n(respo, t) = integsn.phiu_n;
				bernoulliTerm.d_phiu_dx_n(respo, t) = integsn.d_phiu_dx_n;
				bernoulliTerm.d_phib_dx_n(respo, t) = integsn.d_phib_dx_n;
				bernoulliTerm.d_phiu_dxx_n(respo, t) = integsn.d_phiu_dxx_n;
				bernoulliTerm.grad_phiu_grad_phib_n(respo, t) = integsn.grad_phiu_grad_phib_n;
				bernoulliTerm.grad_phiu_grad_phiu_n(respo, t) = integsn.grad_phiu_grad_phiu_n;
				bernoulliTerm.grad_phib_grad_phib_n(respo, t) = integsn.grad_phib_grad_phib_n;

			} // end of response loop

		} // end of time loop

		RealArray time_force(respo_size, steps);
		RealArray time_force_shear(respo_size, steps);
		time_force = 0.0;		// to calculate (dphiu/dt).n in the Bernoulli eq.
		time_force_shear = 0.0; // to calculate d^2(dphiu/dt)/dx^2.n in the Bernoulli eq.
		RealArray force(respo_size, steps);
		force = 0.0; // to store all first order components in the Bernoulli eq.

		const int stencil_point_count = OW3DSeakeeping::time_order + 1;
		Index Im(0, respo_size);
		vector<Index> It;

		for (int i = 0; i < stencil_point_count; ++i)
		{
			if (i < ((stencil_point_count - 1) / 2))
			{
				Index I(i, 1); // left-centred schemes
				It.push_back(I);
			}
			else if (i > ((stencil_point_count - 1) / 2))
			{
				Index I(steps - stencil_point_count + i, 1); // right-centred schemes
				It.push_back(I);
			}
			else
			{
				Index I(i, steps - stencil_point_count + 1); // centered schemes
				It.push_back(I);
			}
		}
		for (int i = 0; i < stencil_point_count; ++i) // schemes
		{
			for (int j = 0; j < stencil_point_count; ++j) // stencil points
			{
				time_force(Im, It[i]) += bernoulliTerm.phiu_n(Im, It[i] - i + j) * OW3DSeakeeping::C4(i, j);
			}
		}

		// THIS TERM HAS BEEN USED FOR SHEAR FORCE BASED ON TIMOSHENKO BEAM THEORY
		if (gmode_type == GMODE_TYPES::TIMOSHENKO_STRHY)
		{
			for (int i = 0; i < stencil_point_count; ++i) // schemes
			{
				for (int j = 0; j < stencil_point_count; ++j) // stencil points
				{
					time_force_shear(Im, It[i]) += bernoulliTerm.d_phiu_dxx_n(Im, It[i] - i + j) * OW3DSeakeeping::C4(i, j);
				}
			}
			time_force_shear = -gamma_square * time_force_shear / simulationData_.print_time_step;
		}
		// First-order Bernoulli : -rho * ( dphiu/dt - U*dphiu/dx + grad(phib)grad(phiu) )

		force = -rho_ * (time_force / simulationData_.print_time_step

						 - U_ * bernoulliTerm.d_phiu_dx_n

						 + bernoulliTerm.grad_phiu_grad_phib_n

						 + 0.5 * bernoulliTerm.grad_phiu_grad_phiu_n * gx_wu_bcs_tag_ + time_force_shear // THIS TERM HAS BEEN USED FOR THE VALIDATION OF THE RESISTANCE PROBLEM (SUBMERGED SPHERE GX WU)
						);

		// Multiply the forces by the symmetry coefficients

		Range all;

		for (unsigned int h = 0; h < respo_size; h++)
			force(h, all) *= gridData_->symmetryCoefficients[run][h];

		// store the force

		if (mode_name == MODE_NAMES::RESISTANCE)
			resistanceBodyForces_.push_back(force);

		else if (
			mode_name == MODE_NAMES::SURGE ||
			mode_name == MODE_NAMES::HEAVE ||
			mode_name == MODE_NAMES::PITCH ||
			mode_name == MODE_NAMES::ROLL ||
			mode_name == MODE_NAMES::SWAY ||
			mode_name == MODE_NAMES::YAW)
			radiationBodyForces_.push_back(force);

		else if (mode_name == MODE_NAMES::GMODE)
			gmodesBodyForces_.push_back(force);

		else
			diffractionBodyForces_.push_back(force);

		OW3DSeakeeping::PrintLogMessage("Time-domain forces on the body computed for " + OW3DSeakeeping::ModeStrings.at(mode_name));

	} // End of runs loop

	if (U_ != 0)
		ComputeAsymptoticCoefficients_();

	forceCalc_ = true;
}

//
//  NOTE : for each run the force array has a shape like :
//
//                      response(0) response(1) response(2) ...
// axis 0 ---> :           (0)         (1)         (2)
//
// axis 1 ( 0)  time(0)     o           o           o   ...
// axis 1 ( 1)  time(1)     o           o           o   ...
// axis 1 ( 2)  time(2)     o           o           o   ...
// axis 1 ( 3)  time(3)     o           o           o   ...
// axis 1 ( 4)  time(4)     o           o           o   ...
// axis 1 ( 5)  time(5)     o           o           o   ...
// ...
// ...
