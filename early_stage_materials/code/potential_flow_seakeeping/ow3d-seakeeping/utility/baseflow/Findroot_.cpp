#include "Baseflow.h"

double OW3DSeakeeping::Baseflow::Findroot_(
    const vector<double> &interpCoeff,
    const vector<double> &yc,
    const vector<double> &fyc)
{
  double tolerance = 1e-14;
  double p[2];

  // estimate the root based on linear interpolation over 2nd and 4th data points
  double root_old = (-fyc[2] * (yc[4] - yc[2]) / (fyc[4] - fyc[2])) + yc[2];

  OW3DSeakeeping::Baseflow::Poleval_(p, interpCoeff, root_old);
  double root_new = root_old - p[0] / p[1];

  while (fabs(root_new - root_old) > tolerance)
  {
    root_old = root_new;
    OW3DSeakeeping::Baseflow::Poleval_(p, interpCoeff, root_old);
    root_new = root_old - p[0] / p[1];
  }

  return root_new;
}
