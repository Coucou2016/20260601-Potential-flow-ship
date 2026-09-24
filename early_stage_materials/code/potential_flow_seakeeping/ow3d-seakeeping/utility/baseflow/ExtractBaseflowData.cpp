#include "Ogshow.h"
#include "Baseflow.h"
#include "OW3DConstants.h"

const OW3DSeakeeping::Baseflow::baseFlowData *OW3DSeakeeping::Baseflow::ExtractBaseflowData()
{
  if (UserInput.base_flow_type != BASE_FLOW_TYPES::ZS)
  {
    if (UserInput.base_flow_type == BASE_FLOW_TYPES::DB)
    {
      // ----------------------------
      // ** Show base flow potential
      // ----------------------------

      Ogshow show(base_show_file_);
      show.startFrame();
      show.saveSolution(data_.potential);

      // ** Take field derivatives

      data_.DerivativesOnCompositeGrid.d_phib_dx = data_.potential.x();
      data_.DerivativesOnCompositeGrid.d_phib_dy = data_.potential.y();
      data_.DerivativesOnCompositeGrid.d_phib_dxx = data_.potential.xx();
      data_.DerivativesOnCompositeGrid.d_phib_dxy = data_.potential.xy();
      data_.DerivativesOnCompositeGrid.d_phib_dyy = data_.potential.yy();

      if (gridData_->nod != 2)
      {
        data_.DerivativesOnCompositeGrid.d_phib_dz = data_.potential.z();
        data_.DerivativesOnCompositeGrid.d_phib_dxz = data_.potential.xz();
        data_.DerivativesOnCompositeGrid.d_phib_dyz = data_.potential.yz();
        data_.DerivativesOnCompositeGrid.d_phib_dzz = data_.potential.zz();
      }

      // ----------------------------
      // ** Find base flow elevation
      // ----------------------------

      if (calcBaseElev_)
      {
        ComputeDoublebodyElevation_(
            data_.elevation,
            data_.DerivativesOnCompositeGrid.d_phib_dx,
            data_.DerivativesOnCompositeGrid.d_phib_dy,
            data_.DerivativesOnCompositeGrid.d_phib_dz);
        PrintBaseFlowElevation_(data_.elevation, base_elevation_file_);
      }

      // ----------------------------------------------------------------------------
      // ** Base-flow derivatives over the body surface (used just for the mterms)
      // ----------------------------------------------------------------------------

      for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); surface++)
      {
        const Single_boundary_data &be = boundariesData_->exciting[surface];
        if (OW3DSeakeeping::ow3d_surface_derivative && gridData_->nod == 3)
        {
          ComputeBaseDerivativesOnSurface_(derivative_on_body_, be, surface, 1);
        }
        else
          ComputeBaseDerivativesOnSurface_(derivative_on_body_, be, surface, 0);

        data_.BodySurfaceDerivatives[surface].dx = derivative_on_body_.dx[surface];
        data_.BodySurfaceDerivatives[surface].dy = derivative_on_body_.dy[surface];
        data_.BodySurfaceDerivatives[surface].dz = derivative_on_body_.dz[surface];
        data_.BodySurfaceDerivatives[surface].dxx = derivative_on_body_.dxx[surface];
        data_.BodySurfaceDerivatives[surface].dyy = derivative_on_body_.dyy[surface];
        data_.BodySurfaceDerivatives[surface].dzz = derivative_on_body_.dzz[surface];
        data_.BodySurfaceDerivatives[surface].dxy = derivative_on_body_.dxy[surface];
        data_.BodySurfaceDerivatives[surface].dxz = derivative_on_body_.dxz[surface];
        data_.BodySurfaceDerivatives[surface].dyz = derivative_on_body_.dyz[surface];
      }
      PrintBaseFlowDerivativesBody_(base_dervs_body_file_);

      // --------------------------------------------------------------------------------------
      // ** Base flow derivatives over the free surface (used just for the free-surfcae BC's)
      // --------------------------------------------------------------------------------------

      // ELEVATION

      if (calcBaseElev_)
      {
        ComputeBaseflowElevationDerivatives_(data_.elevation, data_.elevation_derivative);
      }

      // POTENTIAL

      for (unsigned int surface = 0; surface < boundariesData_->free.size(); surface++) // The derivatives of the "potential" over the free surface.
      {
        const Single_boundary_data &bf = boundariesData_->free[surface];
        ComputeBaseDerivativesOnSurface_(data_.fs_derivatives, bf, surface, 0);
      }

      // Correct the double-body derivatives

      for (unsigned int surface = 0; surface < boundariesData_->free.size(); surface++)
      {
        where(data_.fs_derivatives.dx[surface] > UserInput.U)
        {
          data_.fs_derivatives.dx[surface] = UserInput.U;
        }
      }
      PrintBaseFlowDerivatives_(data_.fs_derivatives, data_.elevation_derivative, base_dervs_free_file_);

      // -------------------------------------------------------------------------
      // ** Create analytical DB in the case of cylinder or sphere (only floating)
      // -------------------------------------------------------------------------

      vector<double> geometry = FindBodyGeometry(*cg_, *boundariesData_);

      if (geometry.size() == 1)
      {
        if (gridData_->nod == 2)
        {
          PrintAnalyticalDoublebody_(geometry, CylinderDoublebody);
        }
        if (gridData_->nod == 3)
        {
          PrintAnalyticalDoublebody_(geometry, SphereDoublebody);
        }
      }

      ComputeDoublebodyForces_();
      PrintDoubleBodyForces_();

      CheckDoublebodyBoundaryCondition_(); // Just to verify if DB with actuator disk is solved correctly

    } // -> End of DB block

    // ---------------------------------------------------------------------------
    // ** Calculate and output mterms (no mterms for the wave resistance problem)
    // ---------------------------------------------------------------------------

    if (UserInput.rad_runs.size() != 0 || UserInput.all_runs.size() == 0)
    {
      ComputeMTerms_(derivative_on_body_, data_.mterms);
      PrintMTerms_(data_.mterms, mterms_file_);
    }

  } // End of forward-speed case

  // ----------------------------------------------------------
  // Put the base-flow field derivatives in the hdf database
  // ----------------------------------------------------------

  if (OW3DSeakeeping::ow3d_surface_derivative && gridData_->nod == 3)
  {
    data_.DerivativesOnCompositeGrid.d_phib_dx = 0;
    data_.DerivativesOnCompositeGrid.d_phib_dy = 0;
    data_.DerivativesOnCompositeGrid.d_phib_dz = 0;
    data_.DerivativesOnCompositeGrid.d_phib_dxx = 0;
    data_.DerivativesOnCompositeGrid.d_phib_dyy = 0;
    data_.DerivativesOnCompositeGrid.d_phib_dzz = 0;
    data_.DerivativesOnCompositeGrid.d_phib_dxy = 0;
    data_.DerivativesOnCompositeGrid.d_phib_dxz = 0;
    data_.DerivativesOnCompositeGrid.d_phib_dyz = 0;

    for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); surface++)
    {
      const Single_boundary_data &bs = boundariesData_->exciting[surface];
      const vector<Index> &Is = bs.surface_indices;
      data_.DerivativesOnCompositeGrid.d_phib_dx[bs.grid](Is[0], Is[1], Is[2]) = data_.BodySurfaceDerivatives[surface].dx;
      data_.DerivativesOnCompositeGrid.d_phib_dy[bs.grid](Is[0], Is[1], Is[2]) = data_.BodySurfaceDerivatives[surface].dy;
      data_.DerivativesOnCompositeGrid.d_phib_dz[bs.grid](Is[0], Is[1], Is[2]) = data_.BodySurfaceDerivatives[surface].dz;
      data_.DerivativesOnCompositeGrid.d_phib_dxx[bs.grid](Is[0], Is[1], Is[2]) = data_.BodySurfaceDerivatives[surface].dxx;
      data_.DerivativesOnCompositeGrid.d_phib_dyy[bs.grid](Is[0], Is[1], Is[2]) = data_.BodySurfaceDerivatives[surface].dyy;
      data_.DerivativesOnCompositeGrid.d_phib_dzz[bs.grid](Is[0], Is[1], Is[2]) = data_.BodySurfaceDerivatives[surface].dzz;
      data_.DerivativesOnCompositeGrid.d_phib_dxy[bs.grid](Is[0], Is[1], Is[2]) = data_.BodySurfaceDerivatives[surface].dxy;
      data_.DerivativesOnCompositeGrid.d_phib_dxz[bs.grid](Is[0], Is[1], Is[2]) = data_.BodySurfaceDerivatives[surface].dxz;
      data_.DerivativesOnCompositeGrid.d_phib_dyz[bs.grid](Is[0], Is[1], Is[2]) = data_.BodySurfaceDerivatives[surface].dyz;
    }
  }

  data_.DerivativesOnCompositeGrid.d_phib_dx.put(dataBase_, OW3DSeakeeping::BaseflowStrings.at(PHIBX));
  data_.DerivativesOnCompositeGrid.d_phib_dy.put(dataBase_, OW3DSeakeeping::BaseflowStrings.at(PHIBY));
  data_.DerivativesOnCompositeGrid.d_phib_dz.put(dataBase_, OW3DSeakeeping::BaseflowStrings.at(PHIBZ));
  data_.DerivativesOnCompositeGrid.d_phib_dxx.put(dataBase_, OW3DSeakeeping::BaseflowStrings.at(PHIBXX));
  data_.DerivativesOnCompositeGrid.d_phib_dyy.put(dataBase_, OW3DSeakeeping::BaseflowStrings.at(PHIBYY));
  data_.DerivativesOnCompositeGrid.d_phib_dzz.put(dataBase_, OW3DSeakeeping::BaseflowStrings.at(PHIBZZ));
  data_.DerivativesOnCompositeGrid.d_phib_dxy.put(dataBase_, OW3DSeakeeping::BaseflowStrings.at(PHIBXY));
  data_.DerivativesOnCompositeGrid.d_phib_dxz.put(dataBase_, OW3DSeakeeping::BaseflowStrings.at(PHIBXZ));
  data_.DerivativesOnCompositeGrid.d_phib_dyz.put(dataBase_, OW3DSeakeeping::BaseflowStrings.at(PHIBYZ));

  // ----------------------------------------------------------------------------
  // Put the mterms in the hdf datebase file, to be used later by FREQ module.
  // ----------------------------------------------------------------------------

  M1_.put(dataBase_, OW3DSeakeeping::BaseflowStrings.at(M1));
  M2_.put(dataBase_, OW3DSeakeeping::BaseflowStrings.at(M2));
  M3_.put(dataBase_, OW3DSeakeeping::BaseflowStrings.at(M3));
  M4_.put(dataBase_, OW3DSeakeeping::BaseflowStrings.at(M4));
  M5_.put(dataBase_, OW3DSeakeeping::BaseflowStrings.at(M5));
  M6_.put(dataBase_, OW3DSeakeeping::BaseflowStrings.at(M6));

  if (UserInput.U != 0 and compute_speed_hydrostatics)
    ComputeForwardSpeedHydrostatics_();

  dataBase_.put(data_.speed_hydrostatics, "speed hydrostatics");

  return &data_; // For the case of zero speed problem, data is not changed after the assignments in the constructor.
}