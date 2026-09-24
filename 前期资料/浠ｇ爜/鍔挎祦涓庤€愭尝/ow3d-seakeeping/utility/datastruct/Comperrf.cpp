// this file implements the calculation of the complex error function
// based on the algorithm given in:
//
// Gautschi, W. 1969. Algorithm 363- The complex error function. In Collected algorithms from
// communications of the association for computing machinery., 12(1969), p.635
//
//   w(z) = exp(-z^2) erfc(-iz)
//
// Important note : The original algorithm is for calculation of
// the complex error function when the argument is in the first
// quadrant of the compelx plane.
// Following relationships are used to calculate the function value
// in the case the argument is in other quadrants than the first one.

// w(-z) = 2 * exp(-z^2) - w(z)
// w(ẑ)  = ŵ(-z)

// Gautschi, Walter. "Efficient computation of the complex error function."
// SIAM Journal on Numerical Analysis 7.1 (1970): 187-198.

#include "gsl/gsl_complex.h"
#include "gsl/gsl_complex_math.h"
#include "OW3DUtilFunctions.h"

void OW3DSeakeeping::Comperrf(double x, double y, double &re, double &im)
{
  double xf = fabs(x); // x in the first quadrant
  double yf = fabs(y); // y in the first quadrant

  int capn, nu, n, np1;
  double h, h2, lambda, r1, r2, s, s1, s2, t1, t2, c;
  bool b;

  if (yf < 4.29 and xf < 5.33)
  {
    s = (1 - yf / 4.29) * sqrt(1 - xf * xf / 28.41);
    h = 1.6 * s;
    h2 = 2 * h;
    capn = 6 + 23 * s;
    nu = 9 + 21 * s;
  }
  else
  {
    h = 0;
    capn = 0;
    nu = 8;
  }

  if (h > 0)
  {
    lambda = pow(h2, capn);
  }

  b = (h == 0 or lambda == 0);

  r1 = r2 = s1 = s2 = 0;

  for (n = nu; n >= 0; n--)
  {
    np1 = n + 1;
    t1 = yf + h + np1 * r1;
    t2 = xf - np1 * r2;
    c = 0.5 / (t1 * t1 + t2 * t2);
    r1 = c * t1;
    r2 = c * t2;

    if (h > 0 and n <= capn)
    {
      t1 = lambda + s1;
      s1 = r1 * t1 - r2 * s2;

      s2 = r2 * t1 + r1 * s2;
      lambda = lambda / h2;
    }
  }

  if (yf == 0)
  {
    re = exp(-xf * xf);
  }
  else
  {
    if (b)
    {
      re = 1.12837916709551 * r1;
    }
    else
    {
      re = 1.12837916709551 * s1;
    }
  }

  if (b)
  {
    im = 1.12837916709551 * r2;
  }
  else
  {
    im = 1.12837916709551 * s2;
  }

  // correct for the quadrants

  gsl_complex z = gsl_complex_rect(xf, yf);    //  make a complex number z in first quadrant
  gsl_complex z2 = gsl_complex_pow_real(z, 2); //  z^2
  gsl_complex nz2 = gsl_complex_negative(z2);  // -z^2
  gsl_complex enz2 = gsl_complex_exp(nz2);     // exp(-z^2)

  //

  gsl_complex cz = gsl_complex_rect(xf, -yf);    // make a complex number conjugate z in first quadrant
  gsl_complex cz2 = gsl_complex_pow_real(cz, 2); //  cz^2
  gsl_complex ncz2 = gsl_complex_negative(cz2);  // -cz^2
  gsl_complex encz2 = gsl_complex_exp(ncz2);     // exp(-cz^2)

  if (x < 0 and y <= 0) // 3rd quadrant
  {
    re = 2 * enz2.dat[0] - re;
    im = 2 * enz2.dat[1] - im;
  }

  else if (x >= 0 and y < 0) // 4th quadrant
  {
    re = 2 * enz2.dat[0] - re;
    im = -(2 * enz2.dat[1] - im);
  }

  else if (x < 0 and y > 0) // 2nd quadrant
  {
    re = 2 * encz2.dat[0] - 2 * enz2.dat[0] - re;
    im = 2 * encz2.dat[1] + 2 * enz2.dat[1] - im;
  }

} // end of comperrf function
