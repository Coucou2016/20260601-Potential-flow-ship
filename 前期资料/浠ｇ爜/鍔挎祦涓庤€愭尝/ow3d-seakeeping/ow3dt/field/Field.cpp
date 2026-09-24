// This file contains the implemetation of the Field class

#include "CompositeGridOperators.h"
#include "Field.h"
#include "OW3DConstants.h"

OW3DSeakeeping::Field::Field(
    const OW3DSeakeeping::Grid::GridData &gridData,
    const OW3DSeakeeping::Baseflow::baseFlowData *baseFlowData,
    CompositeGridOperators &operators) : boundariesData_(&gridData.boundariesData),
                                         gridData_(&gridData)
{
  cg_ = baseFlowData->potential.getCompositeGrid();
  potential_.updateToMatchGrid(*cg_);
  system_right_.updateToMatchGrid(*cg_);
  d_phiu_dx_.updateToMatchGrid(*cg_);
  d_phib_dx_.updateToMatchGrid(*cg_);
  d_phiu_dxx_.updateToMatchGrid(*cg_);
  grad_phiu_grad_phib_.updateToMatchGrid(*cg_);
  grad_phiu_grad_phiu_.updateToMatchGrid(*cg_);
  grad_phib_grad_phib_.updateToMatchGrid(*cg_);

  potential_.setOperators(operators); // apply operator
  resultsDirectory_ = OW3DSeakeeping::UserInput.project_name + '_' + OW3DSeakeeping::program_name;

  integralsFileName_ = resultsDirectory_ + '/' + OW3DSeakeeping::tdomain_body_integrals_binary_file;
  potentialsFileName_ = resultsDirectory_ + '/' + OW3DSeakeeping::tdomain_body_potentials_binary_file;

  PhiN_.updateToMatchGrid(*cg_);
  PhiN_ = 0;

  baseFlowData_ = baseFlowData;

  for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); surface++)
  {
    const Single_boundary_data &be = boundariesData_->exciting[surface];
    const vector<Index> &Is = be.surface_indices;
    realArray temp(Is[0], Is[1], Is[2]);
    temp = 0.;

    phiu_on_body_.push_back(temp);

    d_phiu_dx_on_body_.push_back(temp);
    d_phiu_dy_on_body_.push_back(temp);
    d_phiu_dz_on_body_.push_back(temp);

    d_phiu_dxx_on_body_.push_back(temp); // for wave drift
    d_phiu_dxy_on_body_.push_back(temp); // for wave drift
    d_phiu_dxz_on_body_.push_back(temp); // for wave drift
    d_phiu_dyy_on_body_.push_back(temp); // for wave drift
    d_phiu_dyz_on_body_.push_back(temp); // for wave drift
    d_phiu_dzz_on_body_.push_back(temp); // for wave drift

    grad_phiu_grad_phib_on_body_.push_back(temp);
    grad_phiu_grad_phiu_on_body_.push_back(temp);

    d_phib_dx_on_body_.push_back(baseFlowData_->BodySurfaceDerivatives[surface].dx);                   // these data
    grad_phib_grad_phib_on_body_.push_back(pow(baseFlowData_->BodySurfaceDerivatives[surface].dx, 2) + // will remain
                                           pow(baseFlowData_->BodySurfaceDerivatives[surface].dy, 2) + // intact throughout
                                           pow(baseFlowData_->BodySurfaceDerivatives[surface].dz, 2)); // the program run
  }

  // Define the integrator
  if (gridData_->triangulation.patches.size() == 0)
    integrator_ = GetIntegratorOverBody(*cg_, gridData.boundariesData);

} // End of constructor

void OW3DSeakeeping::Field::Initialise(HydrodynamicProblem run, CompositeGridOperators &operators)
{
  run_ = run;         // note : private data member "excitation_" is set here.
  potential_ = 0.;    // initialise the solution
  system_right_ = 0.; // initialise the system right
  PhiN_ = 0;
  d_phiu_dx_ = 0.; // These date are
  d_phib_dx_ = 0.; //  used for the body integration,
  d_phiu_dxx_ = 0.;
  grad_phiu_grad_phib_ = 0.; // and initialized
  grad_phiu_grad_phiu_ = 0.; // for each
  grad_phib_grad_phib_ = 0.; // mode

  for (unsigned int surface = 0; surface < boundariesData_->exciting.size(); surface++)
  {
    phiu_on_body_[surface] = 0.;

    d_phiu_dx_on_body_[surface] = 0.;
    d_phiu_dy_on_body_[surface] = 0.;
    d_phiu_dz_on_body_[surface] = 0.;

    d_phiu_dxx_on_body_[surface] = 0.; // for wave drift
    d_phiu_dyy_on_body_[surface] = 0.; // for wave drift
    d_phiu_dzz_on_body_[surface] = 0.; // for wave drift
    d_phiu_dxy_on_body_[surface] = 0.; // for wave drift
    d_phiu_dxz_on_body_[surface] = 0.; // for wave drift
    d_phiu_dyz_on_body_[surface] = 0.; // for wave drift

    grad_phiu_grad_phib_on_body_[surface] = 0.;
    grad_phiu_grad_phiu_on_body_[surface] = 0.;
  }

  BuildSystemMatrix_(operators); // system matrix for this excitation
}

OW3DSeakeeping::Field::~Field()
{
}

realCompositeGridFunction &OW3DSeakeeping::Field::GetPotential()
{
  return potential_;
}

realCompositeGridFunction &OW3DSeakeeping::Field::GetSystemMatrix()
{
  return system_matrix_;
}

realCompositeGridFunction &OW3DSeakeeping::Field::GetSystemRight()
{
  return system_right_;
}