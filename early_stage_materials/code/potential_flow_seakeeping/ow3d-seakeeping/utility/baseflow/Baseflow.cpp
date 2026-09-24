// This file implements the Baseflow class.

#include "CompositeGridOperators.h"
#include "Baseflow.h"
#include "OW3DConstants.h"

OW3DSeakeeping::Baseflow::Baseflow(
    CompositeGrid &cg,
    const OW3DSeakeeping::Grid::GridData &gridData,
    CompositeGridOperators &operators,
    Interpolant &interpolant) : cg_(&cg), gridData_(&gridData), boundariesData_(&gridData.boundariesData)
{
  g_ = OW3DSeakeeping::UserInput.g;
  resultsDirectory_ = OW3DSeakeeping::UserInput.project_name + '_' + OW3DSeakeeping::program_name;

  M1_.updateToMatchGrid(cg), M1_ = 0.0, M1_.setOperators(operators);
  M2_.updateToMatchGrid(cg), M2_ = 0.0, M2_.setOperators(operators);
  M3_.updateToMatchGrid(cg), M3_ = 0.0, M3_.setOperators(operators);
  M4_.updateToMatchGrid(cg), M4_ = 0.0, M4_.setOperators(operators);
  M5_.updateToMatchGrid(cg), M5_ = 0.0, M5_.setOperators(operators);
  M6_.updateToMatchGrid(cg), M6_ = 0.0, M6_.setOperators(operators);

  for (unsigned int Imf = 0; Imf < UserInput.number_of_gmodes; Imf++)
  {
    realCompositeGridFunction Mff_;
    Mff_.updateToMatchGrid(cg), Mff_ = 0.0, Mff_.setOperators(operators);
    MF_.push_back(Mff_);
  }

  data_.potential.updateToMatchGrid(cg), data_.potential = 0.0, data_.potential.setOperators(operators);
  data_.elevation.updateToMatchGrid(cg), data_.elevation = 0.0, data_.elevation.setOperators(operators);

  analytical_elevation_.updateToMatchGrid(cg), analytical_elevation_ = 0.0, analytical_elevation_.setOperators(operators);

  data_.BodySurfaceDerivatives.resize(boundariesData_->exciting.size());

  for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); surface++) // assign base-flow mterms (note: loop over exciting surface)
  {
    const Single_boundary_data &be = boundariesData_->exciting[surface];
    const vector<Index> &Ie = be.surface_indices;
    realArray temp(Ie[0], Ie[1], Ie[2]);
    temp = 0.0;

    data_.mterms.m1.push_back(temp);
    data_.mterms.m2.push_back(temp);
    data_.mterms.m3.push_back(temp);
    data_.mterms.m4.push_back(temp);
    data_.mterms.m5.push_back(temp);
    data_.mterms.m6.push_back(temp);

    // NOTE: these are used internally just for calculation of mterms

    derivative_on_body_.dx.push_back(temp);
    derivative_on_body_.dxx.push_back(temp);
    derivative_on_body_.dyz.push_back(temp);
    derivative_on_body_.dy.push_back(temp);
    derivative_on_body_.dyy.push_back(temp);
    derivative_on_body_.dxz.push_back(temp);
    derivative_on_body_.dz.push_back(temp);
    derivative_on_body_.dzz.push_back(temp);
    derivative_on_body_.dxy.push_back(temp);

    // Initialize the body velocity due to the action of propellor disk

    act_body_velocity_ux_.push_back(temp);
    act_body_velocity_uy_.push_back(temp);
    act_body_velocity_uz_.push_back(temp);

    data_.BodySurfaceDerivatives[surface].dx = temp;
    data_.BodySurfaceDerivatives[surface].dy = temp;
    data_.BodySurfaceDerivatives[surface].dz = temp;
    data_.BodySurfaceDerivatives[surface].dxx = temp;
    data_.BodySurfaceDerivatives[surface].dyy = temp;
    data_.BodySurfaceDerivatives[surface].dzz = temp;
    data_.BodySurfaceDerivatives[surface].dxy = temp;
    data_.BodySurfaceDerivatives[surface].dxz = temp;
    data_.BodySurfaceDerivatives[surface].dyz = temp;
  }

  for (unsigned int Imf = 0; Imf < UserInput.number_of_gmodes; Imf++)
  {
    vector<realArray> mflex;
    for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); surface++) // assign base-flow mterms (note: loop over exciting surface)
    {
      const Single_boundary_data &be = boundariesData_->exciting[surface];
      const vector<Index> &Ie = be.surface_indices;
      realArray temp(Ie[0], Ie[1], Ie[2]);
      temp = 0.0;
      mflex.push_back(temp);
    }
    data_.mterms.mf.push_back(mflex);
  }

  for (unsigned int surface = 0; surface < boundariesData_->free.size(); surface++) // Assign base-flow derivatives (note: loop over free surface)
  {
    const Single_boundary_data &bf = boundariesData_->free[surface];
    const vector<Index> &Is = bf.surface_indices;
    realArray temp(Is[0], Is[1], Is[2]);
    temp = 0.0;

    data_.fs_derivatives.dx.push_back(temp);
    data_.fs_derivatives.dxx.push_back(temp);
    data_.fs_derivatives.dyz.push_back(temp);
    data_.fs_derivatives.dz.push_back(temp);
    data_.fs_derivatives.dyy.push_back(temp);
    data_.fs_derivatives.dxz.push_back(temp);
    data_.fs_derivatives.dy.push_back(temp);
    data_.fs_derivatives.dzz.push_back(temp);
    data_.fs_derivatives.dxy.push_back(temp);

    data_.elevation_derivative.dx.push_back(temp);
    data_.elevation_derivative.dz.push_back(temp);
  }

  data_.DerivativesOnCompositeGrid.d_phib_dx.updateToMatchGrid(cg), data_.DerivativesOnCompositeGrid.d_phib_dx = 0.0;
  data_.DerivativesOnCompositeGrid.d_phib_dy.updateToMatchGrid(cg), data_.DerivativesOnCompositeGrid.d_phib_dy = 0.0;
  data_.DerivativesOnCompositeGrid.d_phib_dz.updateToMatchGrid(cg), data_.DerivativesOnCompositeGrid.d_phib_dz = 0.0;
  data_.DerivativesOnCompositeGrid.d_phib_dxx.updateToMatchGrid(cg), data_.DerivativesOnCompositeGrid.d_phib_dxx = 0.0;
  data_.DerivativesOnCompositeGrid.d_phib_dyy.updateToMatchGrid(cg), data_.DerivativesOnCompositeGrid.d_phib_dyy = 0.0;
  data_.DerivativesOnCompositeGrid.d_phib_dzz.updateToMatchGrid(cg), data_.DerivativesOnCompositeGrid.d_phib_dzz = 0.0;
  data_.DerivativesOnCompositeGrid.d_phib_dxy.updateToMatchGrid(cg), data_.DerivativesOnCompositeGrid.d_phib_dxy = 0.0;
  data_.DerivativesOnCompositeGrid.d_phib_dxz.updateToMatchGrid(cg), data_.DerivativesOnCompositeGrid.d_phib_dxz = 0.0;
  data_.DerivativesOnCompositeGrid.d_phib_dyz.updateToMatchGrid(cg), data_.DerivativesOnCompositeGrid.d_phib_dyz = 0.0;

  build_act_vels_ = 0; // Turn "on" to include the action of propeller disk in the double-body flow
  if (build_act_vels_)
    ComputeActBodyVelocities_();

  interpolant_ = interpolant;

  if (UserInput.base_flow_type == BASE_FLOW_TYPES::DB)
  {
    // Double-body system matrix and system right
    BuildBaseflowSystemMatrix_(gridData_->boundaryTypes, operators);
    BuildBaseflowSystemRight_();
  }

  // Assign the output file names
  base_show_file_ = resultsDirectory_ + '/' + OW3DSeakeeping::base_show_file;
  base_elevation_file_ = resultsDirectory_ + '/' + OW3DSeakeeping::base_elev_file;
  base_dervs_free_file_ = resultsDirectory_ + '/' + OW3DSeakeeping::base_free_dervs_file;
  base_dervs_body_file_ = resultsDirectory_ + '/' + OW3DSeakeeping::base_body_dervs_file;
  mterms_file_ = resultsDirectory_ + '/' + OW3DSeakeeping::base_m_terms_file;
  data_base_file_ = resultsDirectory_ + '/' + OW3DSeakeeping::base_database_file;
  base_force_file_ = resultsDirectory_ + '/' + OW3DSeakeeping::base_force_file;
  base_pressure_showfile_ = resultsDirectory_ + '/' + OW3DSeakeeping::base_pressure_show_file;

  // Mount the data-base file (for the case if the base flow is needed by POST program)

  dataBase_.mount(data_base_file_, "I");

  calcBaseElev_ = false;

  data_.dbForces.fx = 0.;
  data_.dbForces.fy = 0.;
  data_.dbForces.fz = 0.;

  data_.dbForces.mx = 0.;
  data_.dbForces.my = 0.;
  data_.dbForces.mz = 0.;

  data_.speed_hydrostatics.resize(UserInput.responses.size(), UserInput.responses.size());
  data_.speed_hydrostatics = 0.0;

} // End of constructor

OW3DSeakeeping::Baseflow::~Baseflow()
{
  dataBase_.unmount();
}

realCompositeGridFunction &OW3DSeakeeping::Baseflow::GetPotential()
{
  return data_.potential;
}

realCompositeGridFunction &OW3DSeakeeping::Baseflow::GetSystemMatrix()
{
  return system_matrix_;
}

realCompositeGridFunction &OW3DSeakeeping::Baseflow::GetSystemRight()
{
  return system_right_;
}