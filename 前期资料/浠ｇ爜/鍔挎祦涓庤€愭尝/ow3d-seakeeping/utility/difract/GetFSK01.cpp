#include "gsl/gsl_roots.h"
#include "gsl/gsl_errno.h"
#include "OW3DUtilFunctions.h"

double OW3DSeakeeping::GetFSK01(
    double omegae,
    double depth,
    double FSK0lim,
    double beta,
    double U,
    double g,
    double bound)
{
  int status;
  const gsl_root_fsolver_type *T;
  gsl_root_fsolver *s;
  double r = 0.0;

  double x_lo = 0;     // A low bound for the wave number
  double x_hi = bound; // A high bound for the wave number
  double err = 1e-6;
  gsl_function F;

  dispersion_params params =

      {
          g,
          depth,
          omegae,
          beta,
          U,
          FSK0lim};

  F.function = FSK01Function;
  F.params = &params;

  T = gsl_root_fsolver_brent;
  s = gsl_root_fsolver_alloc(T);
  gsl_root_fsolver_set(s, &F, x_lo, x_hi);

  do
  {
    status = gsl_root_fsolver_iterate(s);
    r = gsl_root_fsolver_root(s);
    x_lo = gsl_root_fsolver_x_lower(s);
    x_hi = gsl_root_fsolver_x_upper(s);
    status = gsl_root_test_interval(x_lo, x_hi, 0, err);
  } while (status == GSL_CONTINUE);

  gsl_root_fsolver_free(s);

  return r;

} // end of waveNumber_ private member function
