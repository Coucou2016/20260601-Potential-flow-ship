
#include "OW3DUtilFunctions.h"

double OW3DSeakeeping::DepthCriticalFunction(
    double k,
    void *params)
{
  dispersion_params *p = (dispersion_params *)params; // typecast the void pointer

  double g = p->g;
  double h = p->depth;
  double U = p->U;

  return (U * cos(p->beta) - 0.5 * (1 + 2 * k * h / (sinh(2 * k * h))) * sqrt(g / k * tanh(k * h)));
}
