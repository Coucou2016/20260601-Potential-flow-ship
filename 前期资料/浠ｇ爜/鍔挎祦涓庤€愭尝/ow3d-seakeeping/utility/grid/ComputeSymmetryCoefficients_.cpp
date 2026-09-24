// This public  member function belongs to the Grid class, and just for
// the sake of convenience is written in a separate file.

#include "Grid.h"
#include "OW3DConstants.h"

// ---------------------------------------------------------------------------------------------------------------------------
//
// NOTE : After the type of valid excitations and responses have been defined in "extract_run_data_", the symmetry
//        coefficients are defined according to the sym. or anti-sym. excitation for the desired responses. This can
//        be done as in the case of body symmetry (heave surge pitch) are not coupled with the (sway roll yaw). This
//        is also true in the case of forward speed in the x direction.
//
//        So if there is symmetry boundary condition in the grid, then based on the type of the excitation
//        the following symmetry coefficients are defined:
//
//        + In the case of Radiation problems:
//
//          The motion of the body is by default either symmetric or anti-symmetric. This means that for example the
//          yaw motion is due to an an anti-symmetric boundary condition, or surge is due to an symmetric boundary
//          condition. So based on the type of the motions we define a set of symmetry coefficients. These coefficients
//          are multiplied by the results obtained form the half grid. For example surge motion will not contribute to
//          the yaw force so the coefficient is zero in this case.
//          The Resistance problem is also regarded as a symmetric excitation.
//
//        + In the case of Diffraction problems:
//
//          We have to build a symmetric and an anti-symmetric boundary condition in order to be able to define the
//          symmetry coefficients as in the Radiation problems. Then we have to run 2 diffraction problems, and then add
//          the symmetric and anti-symmetric components.
//
//----------------------------------------------------------------------------------------------------------------------------

void OW3DSeakeeping::Grid::ComputeSymmetryCoefficients_()
{
	// Allocate memory for and calculate the symmetry coefficients

	gridData_.symmetryCoefficients = new double *[runs_.size()];

	for (unsigned int i = 0; i < runs_.size(); i++)
	{
		gridData_.symmetryCoefficients[i] = new double[UserInput.responses.size()];
	}

	symMemory_ = true;

	unsigned int number_of_responses = UserInput.responses.size(); // Make a more descriptive name!

	for (unsigned int i = 0; i < runs_.size(); i++)
	{
		MAT_TYPES run_tag = runs_[i].mat_type; // Make a more descriptive name!

		for (unsigned int j = 0; j < number_of_responses; j++)
		{
			MODE_NAMES response = UserInput.responses[j]; // Make a more descriptive name!

			if (gridData_.halfSymmetry)
			{
				// All these excitations have symmetric BC w.r.t x axis ( z=0 plane )

				if (run_tag == MAT_TYPES::SYMMAT)
				{
					if (response == MODE_NAMES::SURGE or response == MODE_NAMES::HEAVE or response == MODE_NAMES::PITCH or response == MODE_NAMES::GMODE)
					{
						gridData_.symmetryCoefficients[i][j] = 2.0;
					}
					else
					{
						gridData_.symmetryCoefficients[i][j] = 0.0;
					}
				}

				// All these excitations have anti-symmetric BC w.r.t x axis ( z=0 plane )

				else if (run_tag == MAT_TYPES::ASMMAT)
				{
					if (response == MODE_NAMES::SWAY or response == MODE_NAMES::ROLL or response == MODE_NAMES::YAW)
					{
						gridData_.symmetryCoefficients[i][j] = 2.0;
					}
					else
					{
						gridData_.symmetryCoefficients[i][j] = 0.0;
					}
				}

			} // End of symmetry block

			else // If no symmetry plane defined for the grid
			{
				gridData_.symmetryCoefficients[i][j] = 1.0;
			}

		} // End of loop over responses

	} // End of loop over runs
}
