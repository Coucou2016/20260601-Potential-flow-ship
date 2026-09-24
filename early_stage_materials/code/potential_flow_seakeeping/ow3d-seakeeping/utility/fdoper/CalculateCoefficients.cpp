// Calculate finite-difference coefficients.
// =============================================================================
// Name: calculate_coefficients.cpp
// Purpose: Calculate finite-difference coefficients using the Fornberg routine.
// Author: R. W. Read
// Version: 1
// Additional comments:
// z: approximation location
// x([0,n)): grid point locations
// m: highest derivative for which weights are sought
// c([0,m],[0,n)): finite-difference coefficients
// =============================================================================

#include "OW3DUtilFunctions.h"

RealArray OW3DSeakeeping::CalculateCoefficients(const double z, const RealArray &x, const int m)
{
  const int n = x.getLength(0); // number of stencil points
  if (m > n - 1)
  {
    throw runtime_error("Derivatives of this order cannot be calculated using this stencil.");
  }
  int mn;
  double c1;
  double c2;
  double c3;
  double c4;
  double c5;
  RealArray c(m + 1, n);

  c1 = 1.0;
  c4 = x(0) - z;
  c = 0.0;
  c(0, 0) = 1.0;

  for (int i = 1; i < n; ++i)
  {
    mn = min(i, m);
    c2 = 1.0;
    c5 = c4;
    c4 = x(i) - z;
    for (int j = 0; j < i; ++j)
    {
      c3 = x(i) - x(j);
      c2 *= c3;
      if (j == i - 1)
      {
        for (int k = mn; k > 0; --k)
        {
          c(k, i) = c1 * (k * c(k - 1, i - 1) - c5 * c(k, i - 1)) / c2;
        }
        c(0, i) = -c1 * c5 * c(0, i - 1) / c2;
      }
      for (int k = mn; k > 0; --k)
      {
        c(k, j) = (c4 * c(k, j) - k * c(k - 1, j)) / c3;
      }
      c(0, j) = c4 * c(0, j) / c3;
    }
    c1 = c2;
  }
  return c;
}
