
#include "OW3DUtilFunctions.h"

double OW3DSeakeeping::FSK0limFunction(
    double k,
    void *params)
{
  dispersion_params *p = (dispersion_params *)params; // typecast the void pointer

  double g = p->g;
  double depth = p->depth;
  // double omegae = p->omega;
  double beta = p->beta;
  double U = p->U;

  return (k - g * tanh(k * depth) / (4 * U * U * cos(beta) * cos(beta)));
}
