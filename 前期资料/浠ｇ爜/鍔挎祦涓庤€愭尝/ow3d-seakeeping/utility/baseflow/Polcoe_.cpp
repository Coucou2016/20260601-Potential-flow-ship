#include "Baseflow.h"

void OW3DSeakeeping::Baseflow::Polcoe_(
    const vector<double> &x,
    const vector<double> &y,
    vector<double> &cof)
{
  int n = x.size();
  double phi, ff, b;
  double s[n];

  for (int i = 0; i < n; i++)
  {
    s[i] = 0.0;
    cof[i] = 0.0;
  }
  s[n - 1] = -x[0];

  for (int i = 1; i < n; i++)
  {
    for (int j = n - 1 - i; j < n - 1; j++)
    {
      s[j] -= x[i] * s[j + 1];
    }
    s[n - 1] -= x[i];
  }
  for (int j = 0; j < n; j++)
  {
    phi = n;
    for (int k = n - 1; k > 0; k--)
      phi = k * s[k] + x[j] * phi;
    ff = y[j] / phi;
    b = 1.0;
    for (int k = n - 1; k >= 0; k--)
    {
      cof[k] += b * ff;
      b = s[k] + x[j] * b;
    }
  }
}
