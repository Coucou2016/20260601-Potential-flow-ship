
#include "OW3DUtilFunctions.h"

double OW3DSeakeeping::FSK02Function(
    double k,
    void *params)
{
  dispersion_params *p = (dispersion_params *)params; // typecast the void pointer

  double g = p->g;
  double depth = p->depth;
  double omegae = p->omega;
  double beta = p->beta;
  double U = p->U;
  double FSK0lim = p->FSK0lim;

  return (sqrt(g * k * tanh(k * depth)) - g * tanh(FSK0lim * depth) / (2 * U * cos(beta)) * (1 + sqrt(1 - omegae * 4. * U * cos(beta) / (g * tanh(FSK0lim * depth)))));
}

// NOTE : This function is related to the omega0_2 in the following-seas condition:
//
// omega0_2 = g*tanh(kh)/(2*U*cos(beta)) * (1 + sqrt(1 - omegae*4*U*cos(beta)/(g*tanh(kh)) ))
