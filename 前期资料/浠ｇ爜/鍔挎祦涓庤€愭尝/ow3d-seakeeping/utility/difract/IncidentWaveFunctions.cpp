
#include "OW3DUtilFunctions.h"

// --------------------------------------------------------------------------------------------------------------------------------
//
// NOTE : In this file, one can include the desired close-form relations for the
//        incident wave velocity potentials. These are going to be used for the
//        frequency-domain calculation of the first-order pressure terms in the
//        Bernoulli equation. This means that no part of the incident wave
//        velocity potential is calculated in the time domain.
//
//       + The incident wave velocity potential in this solver is defined as: (beta = 180 head seas)
//
//        phi0(x, y, z, t) = Re{ i g/omega * cosh( k(y+h) )/cosh(kh) * exp [-i k(x*cos(beta) + z*sin(beta)) ] * exp [i omegae t] }
//
//       + The phasor must be splitted to the symmetric and anti-symmetric components. The symmetric parts
//         are proportional to cos (k z sin(beta)). The anti-symmetric parts are proportional to sin (k z sin(beta)).
//
//
//       + A pointer to each function in this file can be as the first argument for the private member function
//         called "frequencyDomainIntegrals_" in the FirstOrder class. Note that a void pointer is also supplied in the
//         following functions, which can be used to define the desired parameters for each function.
//
// --------------------------------------------------------------------------------------------------------------------------------

// -------------------------------------
//
// *** Fourier transform of -rho * dphi0/dt
//
// -------------------------------------

void OW3DSeakeeping::incidentWavePressure(
    vector<RealArray> &resy,
    vector<RealArray> &imsy,
    vector<RealArray> &reas,
    vector<RealArray> &imas,
    const RealArray &x,
    const RealArray &y,
    const RealArray &z,
    void *params)
{
  incidentWaveIntegralsParameters *p = (incidentWaveIntegralsParameters *)params; // typecast the void pointer

  double k = p->k;
  double h = p->h;
  double g = p->g;
  double betar = p->betar;
  double rho = p->rho;
  double U = p->U;
  unsigned int surface = p->surface;

  double S = 0;

  if (k == 0) // to remove the singularity at k=0
  {
    S = 1e-15;
  }

  if (p->isDif3)
  {
    //                                      (omegae/omegao)                                   cosh(k(h+y))/cosh(kh)                 exp( -i*k( x*cos(beeta) + z*sin(beta)) )

    resy[surface] = rho * g * (1. - k * U * cos(betar) / sqrt(g * (k + S) * tanh((k + S) * h))) * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * cos(k * z * sin(betar)) * cos(k * x * cos(betar));
    imsy[surface] = rho * g * (1. - k * U * cos(betar) / sqrt(g * (k + S) * tanh((k + S) * h))) * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * cos(k * z * sin(betar)) * sin(k * x * cos(betar));
    //
    reas[surface] = rho * g * (1. - k * U * cos(betar) / sqrt(g * (k + S) * tanh((k + S) * h))) * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * sin(k * z * sin(betar)) * sin(k * x * cos(betar));
    imas[surface] = rho * g * (1. - k * U * cos(betar) / sqrt(g * (k + S) * tanh((k + S) * h))) * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * sin(k * z * sin(betar)) * cos(k * x * cos(betar));
  }
  else
  {
    //                                      (omegae/omegao)                                   cosh(k(h+y))/cosh(kh)                 exp( -i*k( x*cos(beeta) + z*sin(beta)) )

    resy[surface] = rho * g * (1. - k * U * cos(betar) / sqrt(g * (k + S) * tanh((k + S) * h))) * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * cos(k * z * sin(betar)) * cos(k * x * cos(betar));
    imsy[surface] = -rho * g * (1. - k * U * cos(betar) / sqrt(g * (k + S) * tanh((k + S) * h))) * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * cos(k * z * sin(betar)) * sin(k * x * cos(betar));
    //
    reas[surface] = -rho * g * (1. - k * U * cos(betar) / sqrt(g * (k + S) * tanh((k + S) * h))) * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * sin(k * z * sin(betar)) * sin(k * x * cos(betar));
    imas[surface] = -rho * g * (1. - k * U * cos(betar) / sqrt(g * (k + S) * tanh((k + S) * h))) * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * sin(k * z * sin(betar)) * cos(k * x * cos(betar));
  }
}

// ------------------------------------------------------------------------------------------------------
//
// *** -rho * dphi0/dx in the frequency domain
//
// NOTE: this term must be multiplied by the relevant terms in "calculateWaveExcitationForces" function.
//
// ------------------------------------------------------------------------------------------------------

void OW3DSeakeeping::incidentWaveDphiDx(
    vector<RealArray> &resy,
    vector<RealArray> &imsy,
    vector<RealArray> &reas,
    vector<RealArray> &imas,
    const RealArray &x,
    const RealArray &y,
    const RealArray &z,
    void *params)
{
  incidentWaveIntegralsParameters *p = (incidentWaveIntegralsParameters *)params; // typecast the void pointer

  double k = p->k;
  double h = p->h;
  double g = p->g;
  double betar = p->betar;
  double rho = p->rho;
  unsigned int surface = p->surface;

  double S = sqrt(g / h); // to remove the singularity at k=0

  if (k != 0)
  {
    S = sqrt(g * k / tanh(k * h));
  }

  if (p->isDif3)
  {
    resy[surface] = cos(betar) * rho * S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * cos(k * z * sin(betar)) * cos(k * x * cos(betar));
    imsy[surface] = cos(betar) * rho * S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * cos(k * z * sin(betar)) * sin(k * x * cos(betar));
    //
    reas[surface] = -cos(betar) * rho * S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * sin(k * z * sin(betar)) * sin(k * x * cos(betar));
    imas[surface] = -cos(betar) * rho * S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * sin(k * z * sin(betar)) * cos(k * x * cos(betar));
  }
  else
  {
    resy[surface] = -cos(betar) * rho * S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * cos(k * z * sin(betar)) * cos(k * x * cos(betar));
    imsy[surface] = cos(betar) * rho * S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * cos(k * z * sin(betar)) * sin(k * x * cos(betar));
    //
    reas[surface] = cos(betar) * rho * S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * sin(k * z * sin(betar)) * sin(k * x * cos(betar));
    imas[surface] = cos(betar) * rho * S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * sin(k * z * sin(betar)) * cos(k * x * cos(betar));
  }
}

// ------------------------------------------------------------------------------------------------------
//
//  *** -rho * dphi0/dy in the frequency domain
//
// NOTE: this term must be multiplied by the relevant terms in "calculateWaveExcitationForces" function.
//
// ------------------------------------------------------------------------------------------------------

void OW3DSeakeeping::incidentWaveDphiDy(
    vector<RealArray> &resy,
    vector<RealArray> &imsy,
    vector<RealArray> &reas,
    vector<RealArray> &imas,
    const RealArray &x,
    const RealArray &y,
    const RealArray &z,
    void *params)
{
  incidentWaveIntegralsParameters *p = (incidentWaveIntegralsParameters *)params; // typecast the void pointer

  double k = p->k;
  double h = p->h;
  double g = p->g;
  double betar = p->betar;
  double rho = p->rho;
  unsigned int surface = p->surface;

  double S = sqrt(g / h); // to remove the singularity at k=0

  if (k != 0)
  {
    S = sqrt(g * k / tanh(k * h));
  }

  if (p->isDif3)
  {
    resy[surface] = rho * S * (exp(k * y) - exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * cos(k * z * sin(betar)) * sin(k * x * cos(betar));
    imsy[surface] = -rho * S * (exp(k * y) - exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * cos(k * z * sin(betar)) * cos(k * x * cos(betar));
    //
    reas[surface] = rho * S * (exp(k * y) - exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * sin(k * z * sin(betar)) * cos(k * x * cos(betar));
    imas[surface] = -rho * S * (exp(k * y) - exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * sin(k * z * sin(betar)) * sin(k * x * cos(betar));
  }
  else
  {
    resy[surface] = -rho * S * (exp(k * y) - exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * cos(k * z * sin(betar)) * sin(k * x * cos(betar));
    imsy[surface] = -rho * S * (exp(k * y) - exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * cos(k * z * sin(betar)) * cos(k * x * cos(betar));
    //
    reas[surface] = -rho * S * (exp(k * y) - exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * sin(k * z * sin(betar)) * cos(k * x * cos(betar));
    imas[surface] = rho * S * (exp(k * y) - exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * sin(k * z * sin(betar)) * sin(k * x * cos(betar));
  }
}

// ------------------------------------------------------------------------------------------------------
//
// *** -rho * dphi0/dz in the frequency domain
//
// Note: this term must be multiplied by the relevant terms in "calculateWaveExcitationForces" function.
//
// ------------------------------------------------------------------------------------------------------

void OW3DSeakeeping::incidentWaveDphiDz(
    vector<RealArray> &resy,
    vector<RealArray> &imsy,
    vector<RealArray> &reas,
    vector<RealArray> &imas,
    const RealArray &x,
    const RealArray &y,
    const RealArray &z,
    void *params)
{
  incidentWaveIntegralsParameters *p = (incidentWaveIntegralsParameters *)params; // typecast the void pointer

  double k = p->k;
  double h = p->h;
  double g = p->g;
  double betar = p->betar;
  double rho = p->rho;
  unsigned int surface = p->surface;

  double S = sqrt(g / h); // to remove the singularity at k=0

  if (k != 0)
  {
    S = sqrt(g * k / tanh(k * h));
  }

  if (p->isDif3)
  {
    resy[surface] = sin(betar) * rho * S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * cos(k * z * sin(betar)) * cos(k * x * cos(betar));
    imsy[surface] = -sin(betar) * rho * S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * cos(k * z * sin(betar)) * sin(k * x * cos(betar));
    //
    reas[surface] = -sin(betar) * rho * S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * sin(k * z * sin(betar)) * sin(k * x * cos(betar));
    imas[surface] = sin(betar) * rho * S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * sin(k * z * sin(betar)) * cos(k * x * cos(betar));
  }
  else
  {
    resy[surface] = -sin(betar) * rho * S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * cos(k * z * sin(betar)) * cos(k * x * cos(betar));
    imsy[surface] = sin(betar) * rho * S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * cos(k * z * sin(betar)) * sin(k * x * cos(betar));
    //
    reas[surface] = sin(betar) * rho * S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * sin(k * z * sin(betar)) * sin(k * x * cos(betar));
    imas[surface] = sin(betar) * rho * S * (exp(k * y) + exp(-k * (y + 2 * h))) / (1 + exp(-2 * k * h)) * sin(k * z * sin(betar)) * cos(k * x * cos(betar));
  }
}
