#include "Baseflow.h"

void OW3DSeakeeping::Baseflow::Poleval_(
    double *p,
    const vector<double> &c,
    const double &x)
{
  int n = c.size();
  p[0] = c[n - 1]; // zeroth derivative
  p[1] = 0.0;      // first derivative

  for (int j = n - 2; j >= 0; j--)
  {
    p[1] = p[1] * x + p[0];
    p[0] = p[0] * x + c[j];
  }
}
