// This public  member function belongs to the Field class, and just for
// the sake of convenience is written in a seperate file.

#include "Field.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::Field::ApplyNeumannDirichletConditions(
	const realCompositeGridFunction &stagePhiAtSurface,
	const OW3DSeakeeping::Baseflow::baseFlowData *baseFlow,
	const Modes::Motion &motion)
{
	// Neumann condition on the body

	for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); ++surface)
	{
		const Single_boundary_data &be = boundariesData_->exciting[surface];
		const vector<Index> &Is = be.surface_indices;
		const vector<Index> &Ig = be.ghost_indices;
		const MappedGrid &mg = (*cg_)[be.grid];
		const RealArray &v = mg.vertex();
		const RealArray &vbn = mg.vertexBoundaryNormal(be.side, be.axis);

		RealArray n3(Is[0], Is[1], Is[2]);
		n3 = 0.0;

		RealArray n1FD;
		RealArray n2FD;
		RealArray n3FD;

		if ((*cg_).numberOfDimensions() == 3)
		{
			n3(Is[0], Is[1], Is[2]) = vbn(Is[0], Is[1], Is[2], axis3);
		}

		if (OW3DSeakeeping::ow3d_surface_derivative && gridData_->nod == 3)
		{
			n1FD = gridData_->body_fundamentals[surface].n1;
			n2FD = gridData_->body_fundamentals[surface].n2;
			n3FD = gridData_->body_fundamentals[surface].n3;
		}

		if (run_.mode == MODE_NAMES::RESISTANCE)
		{
			system_right_[be.grid](Ig[0], Ig[1], Ig[2]) = vbn(Is[0], Is[1], Is[2], axis1) * motion.velocity; // velocity here is 0 for DB linearisation
			if (OW3DSeakeeping::ow3d_surface_derivative && gridData_->nod == 3)
				PhiN_[be.grid](Is[0], Is[1], Is[2]) = n1FD * motion.velocity;
		}

		else if (run_.mode == MODE_NAMES::SURGE)
		{
			// motion in the direction of the x-axis is positive

			system_right_[be.grid](Ig[0], Ig[1], Ig[2]) = vbn(Is[0], Is[1], Is[2], axis1) * motion.velocity + motion.displacement * baseFlow->mterms.m1[surface];
			if (OW3DSeakeeping::ow3d_surface_derivative && gridData_->nod == 3)
				PhiN_[be.grid](Is[0], Is[1], Is[2]) = n1FD * motion.velocity + motion.displacement * baseFlow->mterms.m1[surface];
		}

		else if (run_.mode == MODE_NAMES::HEAVE)
		{
			// motion in the direction of the y-axis is positive

			system_right_[be.grid](Ig[0], Ig[1], Ig[2]) = vbn(Is[0], Is[1], Is[2], axis2) * motion.velocity + motion.displacement * baseFlow->mterms.m2[surface];
			if (OW3DSeakeeping::ow3d_surface_derivative && gridData_->nod == 3)
				PhiN_[be.grid](Is[0], Is[1], Is[2]) = n2FD * motion.velocity + motion.displacement * baseFlow->mterms.m2[surface];
		}

		else if (run_.mode == MODE_NAMES::SWAY)
		{
			// motion in the direction of the z-axis is positive

			system_right_[be.grid](Ig[0], Ig[1], Ig[2]) = vbn(Is[0], Is[1], Is[2], axis3) * motion.velocity + motion.displacement * baseFlow->mterms.m3[surface];
			if (OW3DSeakeeping::ow3d_surface_derivative && gridData_->nod == 3)
				PhiN_[be.grid](Is[0], Is[1], Is[2]) = n3FD * motion.velocity + motion.displacement * baseFlow->mterms.m3[surface];
		}

		else if (run_.mode == MODE_NAMES::ROLL) // %% (n3*y-n2*z) %%
		{
			// clockwise motion looking along the x-axis is positive

			system_right_[be.grid](Ig[0], Ig[1], Ig[2]) =
				(vbn(Is[0], Is[1], Is[2], axis3) * (v(Is[0], Is[1], Is[2], axis2) - UserInput.rotation_centre[1]) -
				 vbn(Is[0], Is[1], Is[2], axis2) * (v(Is[0], Is[1], Is[2], axis3) - UserInput.rotation_centre[2])) *
					motion.velocity +
				motion.displacement * baseFlow->mterms.m4[surface];

			if (OW3DSeakeeping::ow3d_surface_derivative && gridData_->nod == 3)
				PhiN_[be.grid](Is[0], Is[1], Is[2]) =
					(n3FD * (v(Is[0], Is[1], Is[2], axis2) - UserInput.rotation_centre[1]) -
					 n2FD * (v(Is[0], Is[1], Is[2], axis3) - UserInput.rotation_centre[2])) *
						motion.velocity +
					motion.displacement * baseFlow->mterms.m4[surface];
		}

		else if (run_.mode == MODE_NAMES::YAW) // %% -(n3*x-n1*z) %%
		{
			// clockwise motion looking along the y-axis is positive

			system_right_[be.grid](Ig[0], Ig[1], Ig[2]) =
				(vbn(Is[0], Is[1], Is[2], axis1) * (v(Is[0], Is[1], Is[2], axis3) - UserInput.rotation_centre[2]) -
				 vbn(Is[0], Is[1], Is[2], axis3) * (v(Is[0], Is[1], Is[2], axis1) - UserInput.rotation_centre[0])) *
					motion.velocity +
				motion.displacement * baseFlow->mterms.m5[surface];

			if (OW3DSeakeeping::ow3d_surface_derivative && gridData_->nod == 3)
				PhiN_[be.grid](Is[0], Is[1], Is[2]) =
					(n1FD * (v(Is[0], Is[1], Is[2], axis3) - UserInput.rotation_centre[2]) -
					 n3FD * (v(Is[0], Is[1], Is[2], axis1) - UserInput.rotation_centre[0])) *
						motion.velocity +
					motion.displacement * baseFlow->mterms.m5[surface];
		}

		else if (run_.mode == MODE_NAMES::PITCH) // %% (n2*x-n1*y) %%
		{
			// clockwise motion looking along the z-axis is positive

			system_right_[be.grid](Ig[0], Ig[1], Ig[2]) =
				(vbn(Is[0], Is[1], Is[2], axis2) * (v(Is[0], Is[1], Is[2], axis1) - UserInput.rotation_centre[0]) -
				 vbn(Is[0], Is[1], Is[2], axis1) * (v(Is[0], Is[1], Is[2], axis2) - UserInput.rotation_centre[1])) *
					motion.velocity +
				motion.displacement * baseFlow->mterms.m6[surface];

			if (OW3DSeakeeping::ow3d_surface_derivative && gridData_->nod == 3)
				PhiN_[be.grid](Is[0], Is[1], Is[2]) =
					(n2FD * (v(Is[0], Is[1], Is[2], axis1) - UserInput.rotation_centre[0]) -
					 n1FD * (v(Is[0], Is[1], Is[2], axis2) - UserInput.rotation_centre[1])) *
						motion.velocity +
					motion.displacement * baseFlow->mterms.m6[surface];
		}

		else if (run_.mode == MODE_NAMES::GMODE)
		{
			system_right_[be.grid](Ig[0], Ig[1], Ig[2]) = gridData_->flexmodes[run_.gmode_counter].flex_vbn[surface](Is[0], Is[1], Is[2]) * motion.velocity;
		}

		else // diffraction grad(phi_7) * n = - grad(phi0) * n. The solution becomes the velocity potential of the scattered waves.
		{
			system_right_[be.grid](Ig[0], Ig[1], Ig[2]) =
				-(motion.gradphi0x[surface] * vbn(Is[0], Is[1], Is[2], axis1) +
				  motion.gradphi0y[surface] * vbn(Is[0], Is[1], Is[2], axis2) +
				  motion.gradphi0z[surface] * n3(Is[0], Is[1], Is[2]));

			if (OW3DSeakeeping::ow3d_surface_derivative && gridData_->nod == 3)
				PhiN_[be.grid](Is[0], Is[1], Is[2]) = -(motion.gradphi0x[surface] * n1FD + motion.gradphi0y[surface] * n2FD + motion.gradphi0z[surface] * n3FD);
		}
	}

	// dirichlet condition at the free surface

	for (unsigned int surface = 0; surface < boundariesData_->free.size(); surface++)
	{
		const Single_boundary_data &bf = boundariesData_->free[surface];
		const vector<Index> &Is = bf.surface_indices;

		system_right_[bf.grid](Is[0], Is[1], Is[2]) = stagePhiAtSurface[bf.grid](Is[0], Is[1], Is[2]);
	}
}
