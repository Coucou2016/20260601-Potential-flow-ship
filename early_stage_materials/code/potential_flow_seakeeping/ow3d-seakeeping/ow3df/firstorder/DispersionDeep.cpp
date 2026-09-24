// This file returns the value of the dispersion equation for a specific wave
// number k and omegae (only for the deep water condition). For the arbitrary
// depth use the function "dispersion".
//
// It is written for root finding purpose where the "wavenumber_deep" function
// needs several evaluations of the dispersion equation before finding the "k" for the desired frequency.
//
// The disoerssion equation is for the general case of a
// forward speed U and heading angle of beta. The frequency, water depth, gravitational
// acceleration, beta and U are given as the parameters.
//
// we know that : omegae = omega - k*U*cos(beta)
//
// So: omegae = sqrt(gk) - k*U*cos(beta)
//
// And the function's return value for a specific k and omegae is:
//
// [ sqrt( g*k ) - omegae - U*k*cos(beta) ]
//
// The idea is to find the k, which is the root of above equation for an omegae
//
// For the zero speed problem this turns simply to omegae - sqrt(gk) = 0;

#include "OW3DUtilFunctions.h"

double OW3DSeakeeping::DispersionDeep(
    double k,
    void *params)
{
  dispersion_params *p = (dispersion_params *)params; // typecast the void pointer

  double g = p->g;
  // double depth = p->depth;
  double omegae = p->omega;
  double beta = p->beta;
  double U = p->U;

  return (sqrt(g * k) - omegae - U * k * cos(beta));
}
