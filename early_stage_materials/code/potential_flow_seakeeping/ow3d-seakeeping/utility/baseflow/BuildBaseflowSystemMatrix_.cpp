#include "CompositeGridOperators.h"
#include "Baseflow.h"
#include "OW3DConstants.h"

void OW3DSeakeeping::Baseflow::BuildBaseflowSystemMatrix_(
    const OW3DSeakeeping::Grid::Boundary_integers &boundaryTypes,
    CompositeGridOperators &operators)
{
  int nod = cg_->numberOfDimensions();
  int orderSpace = gridData_->order_space;
  int stencil_points = floor(pow(orderSpace + 1, nod) + 1.5); // add 1 for interpolation equations
  int ghost_lines = orderSpace / 2;
  Range all;

  system_matrix_.updateToMatchGrid(*cg_, stencil_points, all, all, all);
  system_matrix_.setIsACoefficientMatrix(true, stencil_points, ghost_lines);
  system_matrix_.setOperators(operators);

  BoundaryConditionParameters parameters;
  parameters.ghostLineToAssign = ghost_lines;

  // the base flow has different boundary condition at the free surface
  // order of operations is as follows:
  // 1. apply Laplacian at all interior and boundary points,
  // 2. apply Dirichlet boundary condition at absorbing surfaces,
  // 3. extrapolate first ghost layer at absorbing surfaces,
  // 4. apply neumann boundary condition at exciting surfaces via first ghost layer,
  // 5. apply neumann boundary condition at free surafce and symmetry plane,
  // 7. extrapolate second ghost layer if required,
  // 8. extrapolate corner ghost points.

  system_matrix_ = operators.laplacianCoefficients(); // populate system matrix with finite-difference coefficients.
  system_matrix_.applyBoundaryConditionCoefficients(0, 0, BCTypes::dirichlet, boundaryTypes.absorbing);
  system_matrix_.applyBoundaryConditionCoefficients(0, 0, BCTypes::extrapolate, boundaryTypes.absorbing);
  system_matrix_.applyBoundaryConditionCoefficients(0, 0, BCTypes::neumann, boundaryTypes.impermeable);
  system_matrix_.applyBoundaryConditionCoefficients(0, 0, BCTypes::neumann, boundaryTypes.exciting);
  system_matrix_.applyBoundaryConditionCoefficients(0, 0, BCTypes::neumann, boundaryTypes.free);

  if (nod == 3)
  {
    system_matrix_.applyBoundaryConditionCoefficients(0, 0, BCTypes::neumann, boundaryTypes.symmetry);
  }
  if (orderSpace == 4)
  {
    system_matrix_.applyBoundaryConditionCoefficients(0, 0, BCTypes::extrapolate, BCTypes::allBoundaries, parameters);
  }

  system_matrix_.finishBoundaryConditions();
}
// =========================================================================================================