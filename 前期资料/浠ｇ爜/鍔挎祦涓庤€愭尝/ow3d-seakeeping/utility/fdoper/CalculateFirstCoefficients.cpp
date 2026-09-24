// Calculate first-derivative coefficients.
// =============================================================================
// Name: calculate_first_coefficients.cpp
// Purpose: Calculate the first-derivative coefficients.
// Author: R. W. Read
// Version: 1
// Additional comments: maaf has added the boundary options
// =============================================================================

#include "OW3DUtilFunctions.h"

RealArray OW3DSeakeeping::CalculateFirstCoefficients(const int order, string boundary)
{
  const int stencil_point_count = order + 1;
  RealArray stencil_point_locations(stencil_point_count);
  for (int i = 0; i < stencil_point_count; ++i)
  {
    stencil_point_locations(i) = i;
  }
  Index If(1, 1); // first derivative line in array returned by calculate_coefficients
  Index Is(0, stencil_point_count);
  RealArray coefficients(stencil_point_count, stencil_point_count);
  for (int j = 0; j < stencil_point_count; ++j)
  {
    Index Ic(j, 1); // first derivative line in coefficients
    coefficients(Ic, Is) = CalculateCoefficients(j, stencil_point_locations, stencil_point_count - 1)(If, Is);
  }

  // Implementation of the boundary options

  RealArray cf = coefficients;

  if (boundary == "left-nm" and (order == 4 or order == 2)) // homogeneous neumann at left
  {
    Range all;
    coefficients(0, all) = 0.0; // Full mirror at the left boundary

    if (order == 4)
    {
      coefficients(1, 0) = cf(2, 1);
      coefficients(1, 1) = cf(2, 0) + cf(2, 2);
      coefficients(1, 2) = cf(2, 3);
      coefficients(1, 3) = cf(2, 4);
      coefficients(1, 4) = 0.;
    }
  }
  else if (boundary == "right-nm" and (order == 4 or order == 2)) // homogeneous neumann at right
  {
    Range all;
    coefficients(order, all) = 0.0; // Full mirror at the right boundary

    if (order == 4)
    {
      coefficients(3, 0) = 0.;
      coefficients(3, 1) = cf(2, 0);
      coefficients(3, 2) = cf(2, 1);
      coefficients(3, 3) = cf(2, 2) + cf(2, 4);
      coefficients(3, 4) = cf(2, 3);
    }
  }
  else if (boundary == "left-dr") // homogeneous dirichlet at left
  {
    if (order == 2)
    {
      coefficients(0, 0) = 0.;
      coefficients(0, 1) = cf(0, 2) - cf(0, 0);
      coefficients(0, 2) = 0.;
    }
    else if (order == 4)
    {
      coefficients(0, 0) = cf(2, 2);
      coefficients(0, 1) = cf(2, 3) - cf(2, 1);
      coefficients(0, 2) = cf(2, 4) - cf(2, 0);
      coefficients(0, 3) = 0.;
      coefficients(0, 4) = 0.;
      //
      coefficients(1, 0) = cf(2, 1);
      coefficients(1, 1) = cf(2, 2) - cf(2, 0);
      coefficients(1, 2) = cf(2, 3);
      coefficients(1, 3) = cf(2, 4);
      coefficients(1, 4) = 0.;
    }
  }
  else if (boundary == "right-dr") // homogeneous dirichlet at right
  {
    if (order == 2)
    {
      coefficients(2, 0) = 0.;
      coefficients(2, 1) = cf(0, 0) - cf(0, 2);
      coefficients(2, 2) = 0.;
    }
    else if (order == 4)
    {
      coefficients(3, 0) = 0.;
      coefficients(3, 1) = cf(2, 0);
      coefficients(3, 2) = cf(2, 1);
      coefficients(3, 3) = cf(2, 2) - cf(2, 4);
      coefficients(3, 4) = cf(2, 3);
      //
      coefficients(4, 0) = 0.;
      coefficients(4, 1) = 0.;
      coefficients(4, 2) = cf(2, 0) - cf(2, 4);
      coefficients(4, 3) = cf(2, 1) - cf(2, 3);
      coefficients(4, 4) = cf(2, 2);
    }
  }

  return coefficients;
}