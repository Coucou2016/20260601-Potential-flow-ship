//
// -------------------------------------------------------------------------------------------------------------------------------------------------------
//
// NOTE : This part of the class is implemented here due to just readability of the main implementation file.
//
//       This file is for calculation of the analytical integrals derived by King(1987) "Time-domain analysis of wave exciting forces on ships and bodies".
//       for gradient of the incident wave velocity potentials for the deep water case.
//       For the arbitrary water depth the integrals are approximated by ifft. Of course one
//       can recover the deep water values by selecting a large water depth. This has been done
//       to verify the ifft approximation.
//
// NOTE : The analytical integrals for the deep water case have been obtained when the pseudo-impulse is based
//        on the absolute frequency. Since the ifft approximation is based on the encounter frequency, we need to
//        shift the encounter frequency in the pseudo-impulse if we are going to compare the approximations with the
//        analytical result. This shift can be done by turning on the "shift" bool variable which is among parameters
//        supplied to the continuous integrand of the inverse transform. Note that this shift will change the pseudo-impulse
//        in the time domain by exp(i*omega0*t) where omega0 = k*U*cos(beta) that is the shift we brought to the encounter frequency.
//
// -------------------------------------------------------------------------------------------------------------------------------------------------------
//

#include "Modes.h"
#include "gsl/gsl_complex_math.h"

void OW3DSeakeeping::Diffraction::DeepwaterDiffractionBCs_(double t)
{
  gsl_complex b = gsl_complex_rect(0, t / 2.); // Note b here is negated compared with the b in King's PhD thesis.
  gsl_complex i = gsl_complex_rect(0, 1.);

  deep_alpha_prime_p_(1) = (deep_omegaBarp_ + U_ * (t)*cos(betar_)) / g_; // The imaginary part
  deep_alpha_prime_n_(1) = (deep_omegaBarn_ + U_ * (t)*cos(betar_)) / g_; // The imaginary part

  deep_I0p_ = 1. / 2 * sqrt(Pi / deep_alpha_prime_p_) * comperrf((t) / (2. * sqrt(deep_alpha_prime_p_)));
  deep_I0n_ = 1. / 2 * sqrt(Pi / deep_alpha_prime_n_) * comperrf((t) / (2. * sqrt(deep_alpha_prime_n_)));

  deep_I1p_ = b / deep_alpha_prime_p_ * deep_I0p_ + 1. / (2 * deep_alpha_prime_p_);
  deep_I1n_ = b / deep_alpha_prime_n_ * deep_I0n_ + 1. / (2 * deep_alpha_prime_n_);

  deep_I2p_ = b / deep_alpha_prime_p_ * deep_I1p_ + 1. / (2 * deep_alpha_prime_p_) * deep_I0p_;
  deep_I2n_ = b / deep_alpha_prime_n_ * deep_I1n_ + 1. / (2 * deep_alpha_prime_n_) * deep_I0n_;

  deep_dphi0xp_ = 2 * multx_ * ((deep_I1p_ - 2 * U_ * cos(betar_) / g_ * deep_I2p_))(0);     // The real part
  deep_dphi0yp_ = 2 * multy_ * (i * (deep_I1p_ - 2 * U_ * cos(betar_) / g_ * deep_I2p_))(0); // The real part
  deep_dphi0zp_ = 2 * multz_ * ((deep_I1p_ - 2 * U_ * cos(betar_) / g_ * deep_I2p_))(0);     // The real part

  deep_dphi0xn_ = 2 * multx_ * ((deep_I1n_ - 2 * U_ * cos(betar_) / g_ * deep_I2n_))(0);     // The real part
  deep_dphi0yn_ = 2 * multy_ * (i * (deep_I1n_ - 2 * U_ * cos(betar_) / g_ * deep_I2n_))(0); // The real part
  deep_dphi0zn_ = 2 * multz_ * ((deep_I1n_ - 2 * U_ * cos(betar_) / g_ * deep_I2n_))(0);     // The real part

  if (diff_type_ == DIFF_TYPES::FULL || diff_type_ == DIFF_TYPES::HEAD)
  {
    deep_dphi0x_ = deep_dphi0xp_;
    deep_dphi0y_ = deep_dphi0yp_;
    deep_dphi0z_ = deep_dphi0zp_;
  }

  else if (diff_type_ == DIFF_TYPES::SYM)
  {
    deep_dphi0x_ = 0.5 * (deep_dphi0xp_ + deep_dphi0xn_);
    deep_dphi0y_ = 0.5 * (deep_dphi0yp_ + deep_dphi0yn_);
    deep_dphi0z_ = 0.5 * (deep_dphi0zp_ - deep_dphi0zn_); // Refer to the second NOTE in file "transformIntegrands.cpp"
  }

  else
  {
    deep_dphi0x_ = 0.5 * (deep_dphi0xp_ - deep_dphi0xn_);
    deep_dphi0y_ = 0.5 * (deep_dphi0yp_ - deep_dphi0yn_);
    deep_dphi0z_ = 0.5 * (deep_dphi0zp_ + deep_dphi0zn_); // Refer to the second NOTE in file "transformIntegrands.cpp"
  }
}
