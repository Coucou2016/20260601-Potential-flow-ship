//
// ----------------------------------------------------------------------------------------------------------------------------
//
// This function approximates the following real valued continuous inverse Fourier transform by gsl real ifft.
//
// f(t) = \int_{-\infty}^\infty S(w) exp(i*w*t) dw
//
// All other coefficients that are multiplied by the above integral must be included outside of this function.
//
// The frequency vector S(w) must be complex conjugate as the time doamin data is pure real. This is
// secured by using the gsl fft routines for real data and halfcompelx notation for the frequency.
// F in the parameter represents the infinity bound of the above integral, and should be taken large enough to
// get accurate result. Note that n should be accordingly large to make sure an adequate sampling from S(w).
//
// Since the data to be transformed are stroed assuming that the length of the signal is even, an error is thrown
// if n is odd. This is because in the case of even length, two frequency components are pure real ( the DC and the n/2),
// and their imaginary parts are not stored (simply is zero).
//
// ----------------------------------------------------------------------------------------------------------------------------

#include "Modes.h"

void OW3DSeakeeping::Diffraction::ComputeInverseTransform_(
    double *data,
    gsl_fft_halfcomplex_wavetable *hc,
    gsl_fft_real_workspace *work,
    int n,
    double dt,
    double *flip)
{
  if (n % 2 != 0)
  {
    throw runtime_error(GetColoredMessage("\t Error (OW3D), Diffraction::ComputeInverseTransform_.cpp.\n\t The sequence length must be even.", 0));
  }

  gsl_fft_halfcomplex_inverse(data, 1, n, hc, work);

  // scale and flip the array

  for (int p = 0; p < n; p++)
  {
    flip[p] = data[p] / dt;
  }
  for (int p = 0; p < n; p++)
  {
    if (p < n / 2)
      data[p] = flip[p + n / 2];
    else
      data[p] = flip[p - n / 2];
  }

} // data transformed and flipped
