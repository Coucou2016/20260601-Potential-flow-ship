// Define operators.
// =============================================================================
// Name: define_operators.cpp
// Purpose: Define the operators.
// Author: R. W. Read
// Version: 1
// Additional comments:
// =============================================================================

#include "CompositeGridOperators.h"
#include "OW3DUtilFunctions.h"

CompositeGridOperators OW3DSeakeeping::DefineOperators(
    CompositeGrid &composite_grid,
    const int order_space)
{

  const int &nod = composite_grid.numberOfDimensions();
  const int stencil_points = floor(pow(order_space + 1, nod) + 1.5); // add 1 for interpolation equations
  CompositeGridOperators operators(composite_grid);
  operators.setStencilSize(stencil_points);
  operators.setOrderOfAccuracy(order_space);

  return operators;
}
