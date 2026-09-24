#include "Baseflow.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::Baseflow::BuildBaseflowSystemRight_()
{
  system_right_.updateToMatchGrid(*cg_);
  system_right_ = 0.;

  for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); surface++)
  {
    const Single_boundary_data &be = boundariesData_->exciting[surface];
    const vector<Index> &Ie = be.surface_indices;
    const vector<Index> &Ig = be.ghost_indices;
    const MappedGrid &mg = (*cg_)[be.grid];
    const RealArray &vbn = mg.vertexBoundaryNormal(be.side, be.axis);

    realArray n3(Ie[0], Ie[1], Ie[2]);
    n3 = 0.0;

    if (gridData_->nod != 2)
    {
      n3 = vbn(Ie[0], Ie[1], Ie[2], axis3);
    }

    // motion in the direction of the x-axis is positive

    system_right_[be.grid](Ig[0], Ig[1], Ig[2]) = vbn(Ie[0], Ie[1], Ie[2], axis1) * UserInput.U +

                                                  act_body_velocity_ux_[surface](Ie[0], Ie[1], Ie[2]) * vbn(Ie[0], Ie[1], Ie[2], axis1) +
                                                  act_body_velocity_uy_[surface](Ie[0], Ie[1], Ie[2]) * vbn(Ie[0], Ie[1], Ie[2], axis2) +
                                                  act_body_velocity_uz_[surface](Ie[0], Ie[1], Ie[2]) * n3;
  }
}