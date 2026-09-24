// This private  member function belongs to the Field class, and just for
// the sake of convenience is written in a seperate file.

#include "Field.h"
#include "OW3DConstants.h"

// Note : when we multiply the potential by the normal vector we do not write simply:
//
// potential_[be.grid](Is[0],Is[1],Is[2]) = potential_[be.grid](Is[0],Is[1],Is[2]) * vbn(Is[0],Is[1],Is[2],axis2);
//
// this will change the potential_ at the body surface. Then if we are going to integrate the potential for other responses
// the result is simply wrong. This is why we first store the velocity potential on the body surface in to a vector<RealArray>.
// Then we multiply the potential by the normal vector as follows:
//
// potential_[be.grid](Is[0],Is[1],Is[2]) = phiu_on_body_[surface] * vbn(Is[0],Is[1],Is[2],axis1);
//
// Now "phiu_on_body_[surface]" remains intact, and can be used to calculate other responses.

void OW3DSeakeeping::Field::MultiplyByNormals_(const MODE_NAMES &response, unsigned int gmode_resp_index)
{
	vector<double> rotation_centre = UserInput.rotation_centre;

	for (unsigned int surface = 0; surface < gridData_->boundariesData.exciting.size(); ++surface)
	{
		const Single_boundary_data &be = gridData_->boundariesData.exciting[surface];
		const vector<Index> &Is = be.surface_indices;
		const MappedGrid &mg = (*cg_)[be.grid];
		const RealArray &v = mg.vertex();
		const RealArray &vbn = mg.vertexBoundaryNormal(be.side, be.axis);

		if (response == MODE_NAMES::SURGE)
		{
			//
			potential_[be.grid](Is[0], Is[1], Is[2]) = phiu_on_body_[surface] * vbn(Is[0], Is[1], Is[2], axis1);
			//
			d_phiu_dx_[be.grid](Is[0], Is[1], Is[2]) = d_phiu_dx_on_body_[surface] * vbn(Is[0], Is[1], Is[2], axis1);
			//
			d_phib_dx_[be.grid](Is[0], Is[1], Is[2]) = d_phib_dx_on_body_[surface] * vbn(Is[0], Is[1], Is[2], axis1);
			//
			d_phiu_dxx_[be.grid](Is[0], Is[1], Is[2]) = d_phiu_dxx_on_body_[surface] * vbn(Is[0], Is[1], Is[2], axis1);
			//
			grad_phiu_grad_phib_[be.grid](Is[0], Is[1], Is[2]) = grad_phiu_grad_phib_on_body_[surface] * vbn(Is[0], Is[1], Is[2], axis1);
			//
			grad_phiu_grad_phiu_[be.grid](Is[0], Is[1], Is[2]) = grad_phiu_grad_phiu_on_body_[surface] * vbn(Is[0], Is[1], Is[2], axis1);
			//
			grad_phib_grad_phib_[be.grid](Is[0], Is[1], Is[2]) = grad_phib_grad_phib_on_body_[surface] * vbn(Is[0], Is[1], Is[2], axis1);
		}

		else if (response == MODE_NAMES::HEAVE)
		{
			potential_[be.grid](Is[0], Is[1], Is[2]) = phiu_on_body_[surface] * vbn(Is[0], Is[1], Is[2], axis2);
			//
			d_phiu_dx_[be.grid](Is[0], Is[1], Is[2]) = d_phiu_dx_on_body_[surface] * vbn(Is[0], Is[1], Is[2], axis2);
			//
			d_phib_dx_[be.grid](Is[0], Is[1], Is[2]) = d_phib_dx_on_body_[surface] * vbn(Is[0], Is[1], Is[2], axis2);
			//
			d_phiu_dxx_[be.grid](Is[0], Is[1], Is[2]) = d_phiu_dxx_on_body_[surface] * vbn(Is[0], Is[1], Is[2], axis2);
			//
			grad_phiu_grad_phib_[be.grid](Is[0], Is[1], Is[2]) = grad_phiu_grad_phib_on_body_[surface] * vbn(Is[0], Is[1], Is[2], axis2);
			//
			grad_phiu_grad_phiu_[be.grid](Is[0], Is[1], Is[2]) = grad_phiu_grad_phiu_on_body_[surface] * vbn(Is[0], Is[1], Is[2], axis2);
			//
			grad_phib_grad_phib_[be.grid](Is[0], Is[1], Is[2]) = grad_phib_grad_phib_on_body_[surface] * vbn(Is[0], Is[1], Is[2], axis2);
		}

		else if (response == MODE_NAMES::SWAY)
		{
			potential_[be.grid](Is[0], Is[1], Is[2]) = phiu_on_body_[surface] * vbn(Is[0], Is[1], Is[2], axis3);
			//
			d_phiu_dx_[be.grid](Is[0], Is[1], Is[2]) = d_phiu_dx_on_body_[surface] * vbn(Is[0], Is[1], Is[2], axis3);
			//
			d_phib_dx_[be.grid](Is[0], Is[1], Is[2]) = d_phib_dx_on_body_[surface] * vbn(Is[0], Is[1], Is[2], axis3);
			//
			d_phiu_dxx_[be.grid](Is[0], Is[1], Is[2]) = d_phiu_dxx_on_body_[surface] * vbn(Is[0], Is[1], Is[2], axis3);
			//
			grad_phiu_grad_phib_[be.grid](Is[0], Is[1], Is[2]) = grad_phiu_grad_phib_on_body_[surface] * vbn(Is[0], Is[1], Is[2], axis3);
			//
			grad_phiu_grad_phiu_[be.grid](Is[0], Is[1], Is[2]) = grad_phiu_grad_phiu_on_body_[surface] * vbn(Is[0], Is[1], Is[2], axis3);
			//
			grad_phib_grad_phib_[be.grid](Is[0], Is[1], Is[2]) = grad_phib_grad_phib_on_body_[surface] * vbn(Is[0], Is[1], Is[2], axis3);
		}

		else if (response == MODE_NAMES::ROLL)
		{
			potential_[be.grid](Is[0], Is[1], Is[2]) =

				phiu_on_body_[surface] * (vbn(Is[0], Is[1], Is[2], axis3) * (v(Is[0], Is[1], Is[2], axis2) - rotation_centre[1]) -
										  vbn(Is[0], Is[1], Is[2], axis2) * (v(Is[0], Is[1], Is[2], axis3) - rotation_centre[2]));
			//
			d_phiu_dx_[be.grid](Is[0], Is[1], Is[2]) =

				d_phiu_dx_on_body_[surface] * (vbn(Is[0], Is[1], Is[2], axis3) * (v(Is[0], Is[1], Is[2], axis2) - rotation_centre[1]) -
											   vbn(Is[0], Is[1], Is[2], axis2) * (v(Is[0], Is[1], Is[2], axis3) - rotation_centre[2]));
			//
			d_phib_dx_[be.grid](Is[0], Is[1], Is[2]) =

				d_phib_dx_on_body_[surface] * (vbn(Is[0], Is[1], Is[2], axis3) * (v(Is[0], Is[1], Is[2], axis2) - rotation_centre[1]) -
											   vbn(Is[0], Is[1], Is[2], axis2) * (v(Is[0], Is[1], Is[2], axis3) - rotation_centre[2]));
			//
			d_phiu_dxx_[be.grid](Is[0], Is[1], Is[2]) =

				d_phiu_dxx_on_body_[surface] * (vbn(Is[0], Is[1], Is[2], axis3) * (v(Is[0], Is[1], Is[2], axis2) - rotation_centre[1]) -
												vbn(Is[0], Is[1], Is[2], axis2) * (v(Is[0], Is[1], Is[2], axis3) - rotation_centre[2]));
			//
			grad_phiu_grad_phib_[be.grid](Is[0], Is[1], Is[2]) =

				grad_phiu_grad_phib_on_body_[surface] * (vbn(Is[0], Is[1], Is[2], axis3) * (v(Is[0], Is[1], Is[2], axis2) - rotation_centre[1]) -
														 vbn(Is[0], Is[1], Is[2], axis2) * (v(Is[0], Is[1], Is[2], axis3) - rotation_centre[2]));
			//
			grad_phiu_grad_phiu_[be.grid](Is[0], Is[1], Is[2]) =

				grad_phiu_grad_phiu_on_body_[surface] * (vbn(Is[0], Is[1], Is[2], axis3) * (v(Is[0], Is[1], Is[2], axis2) - rotation_centre[1]) -
														 vbn(Is[0], Is[1], Is[2], axis2) * (v(Is[0], Is[1], Is[2], axis3) - rotation_centre[2]));
			//
			grad_phib_grad_phib_[be.grid](Is[0], Is[1], Is[2]) =
				grad_phib_grad_phib_on_body_[surface] * (vbn(Is[0], Is[1], Is[2], axis3) * (v(Is[0], Is[1], Is[2], axis2) - rotation_centre[1]) -
														 vbn(Is[0], Is[1], Is[2], axis2) * (v(Is[0], Is[1], Is[2], axis3) - rotation_centre[2]));
		}

		else if (response == MODE_NAMES::YAW)
		{
			potential_[be.grid](Is[0], Is[1], Is[2]) =

				phiu_on_body_[surface] * (vbn(Is[0], Is[1], Is[2], axis1) * (v(Is[0], Is[1], Is[2], axis3) - rotation_centre[2]) -
										  vbn(Is[0], Is[1], Is[2], axis3) * (v(Is[0], Is[1], Is[2], axis1) - rotation_centre[0]));
			//
			d_phiu_dx_[be.grid](Is[0], Is[1], Is[2]) =

				d_phiu_dx_on_body_[surface] * (vbn(Is[0], Is[1], Is[2], axis1) * (v(Is[0], Is[1], Is[2], axis3) - rotation_centre[2]) -
											   vbn(Is[0], Is[1], Is[2], axis3) * (v(Is[0], Is[1], Is[2], axis1) - rotation_centre[0]));
			//
			d_phib_dx_[be.grid](Is[0], Is[1], Is[2]) =

				d_phib_dx_on_body_[surface] * (vbn(Is[0], Is[1], Is[2], axis1) * (v(Is[0], Is[1], Is[2], axis3) - rotation_centre[2]) -
											   vbn(Is[0], Is[1], Is[2], axis3) * (v(Is[0], Is[1], Is[2], axis1) - rotation_centre[0]));
			//
			d_phiu_dxx_[be.grid](Is[0], Is[1], Is[2]) =

				d_phiu_dxx_on_body_[surface] * (vbn(Is[0], Is[1], Is[2], axis1) * (v(Is[0], Is[1], Is[2], axis3) - rotation_centre[2]) -
											   vbn(Is[0], Is[1], Is[2], axis3) * (v(Is[0], Is[1], Is[2], axis1) - rotation_centre[0]));
			//
			grad_phiu_grad_phib_[be.grid](Is[0], Is[1], Is[2]) =

				grad_phiu_grad_phib_on_body_[surface] * (vbn(Is[0], Is[1], Is[2], axis1) * (v(Is[0], Is[1], Is[2], axis3) - rotation_centre[2]) -
														 vbn(Is[0], Is[1], Is[2], axis3) * (v(Is[0], Is[1], Is[2], axis1) - rotation_centre[0]));
			//
			grad_phiu_grad_phiu_[be.grid](Is[0], Is[1], Is[2]) =

				grad_phiu_grad_phiu_on_body_[surface] * (vbn(Is[0], Is[1], Is[2], axis1) * (v(Is[0], Is[1], Is[2], axis3) - rotation_centre[2]) -
														 vbn(Is[0], Is[1], Is[2], axis3) * (v(Is[0], Is[1], Is[2], axis1) - rotation_centre[0]));
			//
			grad_phib_grad_phib_[be.grid](Is[0], Is[1], Is[2]) =

				grad_phib_grad_phib_on_body_[surface] * (vbn(Is[0], Is[1], Is[2], axis1) * (v(Is[0], Is[1], Is[2], axis3) - rotation_centre[2]) -
														 vbn(Is[0], Is[1], Is[2], axis3) * (v(Is[0], Is[1], Is[2], axis1) - rotation_centre[0]));
		}

		else if (response == MODE_NAMES::PITCH)
		{
			potential_[be.grid](Is[0], Is[1], Is[2]) =

				phiu_on_body_[surface] * (vbn(Is[0], Is[1], Is[2], axis2) * (v(Is[0], Is[1], Is[2], axis1) - rotation_centre[0]) -
										  vbn(Is[0], Is[1], Is[2], axis1) * (v(Is[0], Is[1], Is[2], axis2) - rotation_centre[1]));
			//
			d_phiu_dx_[be.grid](Is[0], Is[1], Is[2]) =

				d_phiu_dx_on_body_[surface] * (vbn(Is[0], Is[1], Is[2], axis2) * (v(Is[0], Is[1], Is[2], axis1) - rotation_centre[0]) -
											   vbn(Is[0], Is[1], Is[2], axis1) * (v(Is[0], Is[1], Is[2], axis2) - rotation_centre[1]));
			//
			d_phib_dx_[be.grid](Is[0], Is[1], Is[2]) =

				d_phib_dx_on_body_[surface] * (vbn(Is[0], Is[1], Is[2], axis2) * (v(Is[0], Is[1], Is[2], axis1) - rotation_centre[0]) -
											   vbn(Is[0], Is[1], Is[2], axis1) * (v(Is[0], Is[1], Is[2], axis2) - rotation_centre[1]));
			//
			d_phiu_dxx_[be.grid](Is[0], Is[1], Is[2]) =

				d_phiu_dxx_on_body_[surface] * (vbn(Is[0], Is[1], Is[2], axis2) * (v(Is[0], Is[1], Is[2], axis1) - rotation_centre[0]) -
											   vbn(Is[0], Is[1], Is[2], axis1) * (v(Is[0], Is[1], Is[2], axis2) - rotation_centre[1]));
			//
			grad_phiu_grad_phib_[be.grid](Is[0], Is[1], Is[2]) =

				grad_phiu_grad_phib_on_body_[surface] * (vbn(Is[0], Is[1], Is[2], axis2) * (v(Is[0], Is[1], Is[2], axis1) - rotation_centre[0]) -
														 vbn(Is[0], Is[1], Is[2], axis1) * (v(Is[0], Is[1], Is[2], axis2) - rotation_centre[1]));
			//
			grad_phiu_grad_phiu_[be.grid](Is[0], Is[1], Is[2]) =

				grad_phiu_grad_phiu_on_body_[surface] * (vbn(Is[0], Is[1], Is[2], axis2) * (v(Is[0], Is[1], Is[2], axis1) - rotation_centre[0]) -
														 vbn(Is[0], Is[1], Is[2], axis1) * (v(Is[0], Is[1], Is[2], axis2) - rotation_centre[1]));
			//
			grad_phib_grad_phib_[be.grid](Is[0], Is[1], Is[2]) =

				grad_phib_grad_phib_on_body_[surface] * (vbn(Is[0], Is[1], Is[2], axis2) * (v(Is[0], Is[1], Is[2], axis1) - rotation_centre[0]) -
														 vbn(Is[0], Is[1], Is[2], axis1) * (v(Is[0], Is[1], Is[2], axis2) - rotation_centre[1]));
		}

		else if (response == MODE_NAMES::GMODE)
		{
			potential_[be.grid](Is[0], Is[1], Is[2]) = phiu_on_body_[surface] * gridData_->flexmodes[gmode_resp_index].flex_vbn[surface](Is[0], Is[1], Is[2]);
			//
			d_phiu_dx_[be.grid](Is[0], Is[1], Is[2]) = d_phiu_dx_on_body_[surface] * gridData_->flexmodes[gmode_resp_index].flex_vbn[surface](Is[0], Is[1], Is[2]);
			//
			d_phib_dx_[be.grid](Is[0], Is[1], Is[2]) = d_phib_dx_on_body_[surface] * gridData_->flexmodes[gmode_resp_index].flex_vbn[surface](Is[0], Is[1], Is[2]);
			//
			d_phiu_dxx_[be.grid](Is[0], Is[1], Is[2]) = d_phiu_dxx_on_body_[surface] * gridData_->flexmodes[gmode_resp_index].flex_vbn[surface](Is[0], Is[1], Is[2]);
			//
			grad_phiu_grad_phib_[be.grid](Is[0], Is[1], Is[2]) = grad_phiu_grad_phib_on_body_[surface] * gridData_->flexmodes[gmode_resp_index].flex_vbn[surface](Is[0], Is[1], Is[2]);
			//
			grad_phib_grad_phib_[be.grid](Is[0], Is[1], Is[2]) = grad_phib_grad_phib_on_body_[surface] * gridData_->flexmodes[gmode_resp_index].flex_vbn[surface](Is[0], Is[1], Is[2]);
		}
	}
}
