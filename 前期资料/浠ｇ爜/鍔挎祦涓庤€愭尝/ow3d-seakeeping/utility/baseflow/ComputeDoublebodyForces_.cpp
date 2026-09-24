#include "Ogshow.h"
#include "Baseflow.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::Baseflow::ComputeDoublebodyForces_()
{
  Integrate integrator;
  if (gridData_->triangulation.patches.size() == 0)
    integrator = GetIntegratorOverBody(*cg_, *boundariesData_); // Composite grid integrator

  db_pressure_on_body_.updateToMatchGrid(*cg_);

  realCompositeGridFunction tempDBfx(*cg_);
  tempDBfx = 0.;
  realCompositeGridFunction tempDBfy(*cg_);
  tempDBfy = 0.;
  realCompositeGridFunction tempDBfz(*cg_);
  tempDBfz = 0.;
  realCompositeGridFunction tempDBmx(*cg_);
  tempDBmx = 0.;
  realCompositeGridFunction tempDBmy(*cg_);
  tempDBmy = 0.;
  realCompositeGridFunction tempDBmz(*cg_);
  tempDBmz = 0.;

  int numberOFIntegrations = 1;

  if (gridData_->halfSymmetry)
  {
    numberOFIntegrations = 2;
  }

  for (int count = 0; count < numberOFIntegrations; count++)
  {
    int sign = (count == 1) ? -1 : 1; // Means integration on the other half of the body

    for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); surface++)
    {
      const Single_boundary_data &be = boundariesData_->exciting[surface];
      const vector<Index> &Is = be.surface_indices;
      const MappedGrid &mg = (*cg_)[be.grid];
      const RealArray &v = mg.vertex();
      const RealArray &vbn = mg.vertexBoundaryNormal(be.side, be.axis);

      RealArray x(Is[0], Is[1], Is[2]), y(Is[0], Is[1], Is[2]), z(Is[0], Is[1], Is[2]);
      RealArray n1(Is[0], Is[1], Is[2]), n2(Is[0], Is[1], Is[2]), n3(Is[0], Is[1], Is[2]);

      x = v(Is[0], Is[1], Is[2], axis1);
      y = v(Is[0], Is[1], Is[2], axis2); // Note : "y" vertical up
      z = 0.0;

      n1 = vbn(Is[0], Is[1], Is[2], axis1);
      n2 = vbn(Is[0], Is[1], Is[2], axis2); // Note : "n2" vertical up
      n3 = 0.;

      if (mg.numberOfDimensions() == 3)
      {
        z = v(Is[0], Is[1], Is[2], axis3) * sign;
        n3 = vbn(Is[0], Is[1], Is[2], axis3) * sign;
      }

      // surge

      tempDBfx[be.grid](Is[0], Is[1], Is[2]) =
          -OW3DSeakeeping::rho *
          (-OW3DSeakeeping::UserInput.U * (data_.DerivativesOnCompositeGrid.d_phib_dx[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_ux_[surface](Is[0], Is[1], Is[2])) +
           0.5 *
               (pow(data_.DerivativesOnCompositeGrid.d_phib_dx[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_ux_[surface](Is[0], Is[1], Is[2]), 2) +
                pow(data_.DerivativesOnCompositeGrid.d_phib_dy[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_uy_[surface](Is[0], Is[1], Is[2]), 2) +
                pow(data_.DerivativesOnCompositeGrid.d_phib_dz[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_uz_[surface](Is[0], Is[1], Is[2]), 2))) *
          n1;

      // heave

      tempDBfx[be.grid](Is[0], Is[1], Is[2]) =
          -OW3DSeakeeping::rho *
          (-OW3DSeakeeping::UserInput.U * (data_.DerivativesOnCompositeGrid.d_phib_dx[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_ux_[surface](Is[0], Is[1], Is[2])) +
           0.5 *
               (pow(data_.DerivativesOnCompositeGrid.d_phib_dx[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_ux_[surface](Is[0], Is[1], Is[2]), 2) +
                pow(data_.DerivativesOnCompositeGrid.d_phib_dy[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_uy_[surface](Is[0], Is[1], Is[2]), 2) +
                pow(data_.DerivativesOnCompositeGrid.d_phib_dz[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_uz_[surface](Is[0], Is[1], Is[2]), 2))) *
          n2;

      // sway

      tempDBfx[be.grid](Is[0], Is[1], Is[2]) =
          -OW3DSeakeeping::rho *
          (-OW3DSeakeeping::UserInput.U * (data_.DerivativesOnCompositeGrid.d_phib_dx[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_ux_[surface](Is[0], Is[1], Is[2])) +
           0.5 *
               (pow(data_.DerivativesOnCompositeGrid.d_phib_dx[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_ux_[surface](Is[0], Is[1], Is[2]), 2) +
                pow(data_.DerivativesOnCompositeGrid.d_phib_dy[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_uy_[surface](Is[0], Is[1], Is[2]), 2) +
                pow(data_.DerivativesOnCompositeGrid.d_phib_dz[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_uz_[surface](Is[0], Is[1], Is[2]), 2))) *
          n3;

      // roll

      tempDBmx[be.grid](Is[0], Is[1], Is[2]) =
          -OW3DSeakeeping::rho *
          (-OW3DSeakeeping::UserInput.U * (data_.DerivativesOnCompositeGrid.d_phib_dx[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_ux_[surface](Is[0], Is[1], Is[2])) +
           0.5 *
               (pow(data_.DerivativesOnCompositeGrid.d_phib_dx[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_ux_[surface](Is[0], Is[1], Is[2]), 2) +
                pow(data_.DerivativesOnCompositeGrid.d_phib_dy[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_uy_[surface](Is[0], Is[1], Is[2]), 2) +
                pow(data_.DerivativesOnCompositeGrid.d_phib_dz[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_uz_[surface](Is[0], Is[1], Is[2]), 2))) *
          (n3 * (y - OW3DSeakeeping::UserInput.rotation_centre[1]) - n2 * (z - OW3DSeakeeping::UserInput.rotation_centre[2]));

      // yaw

      tempDBmy[be.grid](Is[0], Is[1], Is[2]) =
          -OW3DSeakeeping::rho *
          (-OW3DSeakeeping::UserInput.U * (data_.DerivativesOnCompositeGrid.d_phib_dx[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_ux_[surface](Is[0], Is[1], Is[2])) +
           0.5 *
               (pow(data_.DerivativesOnCompositeGrid.d_phib_dx[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_ux_[surface](Is[0], Is[1], Is[2]), 2) +
                pow(data_.DerivativesOnCompositeGrid.d_phib_dy[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_uy_[surface](Is[0], Is[1], Is[2]), 2) +
                pow(data_.DerivativesOnCompositeGrid.d_phib_dz[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_uz_[surface](Is[0], Is[1], Is[2]), 2))) *
          (n1 * (z - OW3DSeakeeping::UserInput.rotation_centre[2]) - n3 * (x - OW3DSeakeeping::UserInput.rotation_centre[0]));

      // pitch

      tempDBmz[be.grid](Is[0], Is[1], Is[2]) =
          -OW3DSeakeeping::rho *
          (-OW3DSeakeeping::UserInput.U * (data_.DerivativesOnCompositeGrid.d_phib_dx[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_ux_[surface](Is[0], Is[1], Is[2])) +
           0.5 *
               (pow(data_.DerivativesOnCompositeGrid.d_phib_dx[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_ux_[surface](Is[0], Is[1], Is[2]), 2) +
                pow(data_.DerivativesOnCompositeGrid.d_phib_dy[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_uy_[surface](Is[0], Is[1], Is[2]), 2) +
                pow(data_.DerivativesOnCompositeGrid.d_phib_dz[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_uz_[surface](Is[0], Is[1], Is[2]), 2))) *
          (n2 * (x - OW3DSeakeeping::UserInput.rotation_centre[0]) - n1 * (y - OW3DSeakeeping::UserInput.rotation_centre[1]));

      // Save the pressure

      if (count == 0)
      {
        db_pressure_on_body_[be.grid](Is[0], Is[1], Is[2]) =
            -OW3DSeakeeping::rho *
            (-OW3DSeakeeping::UserInput.U * (data_.DerivativesOnCompositeGrid.d_phib_dx[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_ux_[surface](Is[0], Is[1], Is[2])) +
             0.5 *
                 (pow(data_.DerivativesOnCompositeGrid.d_phib_dx[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_ux_[surface](Is[0], Is[1], Is[2]), 2) +
                  pow(data_.DerivativesOnCompositeGrid.d_phib_dy[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_uy_[surface](Is[0], Is[1], Is[2]), 2) +
                  pow(data_.DerivativesOnCompositeGrid.d_phib_dz[be.grid](Is[0], Is[1], Is[2]) - act_body_velocity_uz_[surface](Is[0], Is[1], Is[2]), 2)));
      }

    } // End of surface loop

    data_.dbForces.fx += ComputeSurfaceIntegral(integrator, gridData_->triangulation, tempDBfx);
    data_.dbForces.fy += ComputeSurfaceIntegral(integrator, gridData_->triangulation, tempDBfy);
    data_.dbForces.fz += ComputeSurfaceIntegral(integrator, gridData_->triangulation, tempDBfz);
    data_.dbForces.mx += ComputeSurfaceIntegral(integrator, gridData_->triangulation, tempDBmx);
    data_.dbForces.my += ComputeSurfaceIntegral(integrator, gridData_->triangulation, tempDBmy);
    data_.dbForces.mz += ComputeSurfaceIntegral(integrator, gridData_->triangulation, tempDBmz);

    // Save the double-body pressure in to the show file.

    Ogshow show(base_pressure_showfile_);
    show.startFrame();
    show.saveSolution(db_pressure_on_body_);
    show.close();
  }

} // End of calculateDoubleBodyForces_ private member function